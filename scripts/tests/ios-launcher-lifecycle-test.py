#!/usr/bin/env python3
"""Exercise the real launcher entry points; only macOS tool boundaries are fake."""

import os
import pathlib
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import unittest


REPO = pathlib.Path(__file__).resolve().parents[2]
BASH = os.environ.get("P2PKIT_TEST_BASH", "bash")
UDID = "11111111-1111-1111-1111-111111111111"
FAKE_TOOL = r'''#!/usr/bin/env python3
import os, pathlib, sys, time
tool = pathlib.Path(sys.argv[0]).name
root = pathlib.Path(os.environ["FAKE_IOS_ROOT"])
args = sys.argv[1:]
with (root / "tools.log").open("a") as log:
    log.write(tool + " " + " ".join(args) + "\n")
if tool == "xcrun":
    assert args[0] == "simctl", args
    if args[1] == "list":
        print("    iPhone 17 (11111111-1111-1111-1111-111111111111) (Shutdown)")
    elif args[1] == "install":
        (root / "installed-path").write_text(args[3])
    elif args[1] == "get_app_container":
        print((root / "installed-path").read_text())
    else:
        assert args[1] in ("bootstatus", "launch"), args
elif tool == "xcodebuild":
    if os.environ.get("FAKE_IOS_BLOCK") == "1":
        (root / "build-started").touch()
        deadline = time.monotonic() + 20
        while not (root / "release-build").exists():
            if time.monotonic() > deadline:
                sys.exit("test did not release the synthetic build")
            time.sleep(0.01)
    if os.environ.get("FAKE_IOS_BUILD_FAILURE") == "1":
        sys.exit(42)
    derived = pathlib.Path(args[args.index("-derivedDataPath") + 1])
    app = derived / "Build/Products/Debug-iphonesimulator/p2pkit-sample.app"
    app.mkdir(parents=True)
    (app / "Info.plist").write_text("synthetic plist")
    (app / "p2pkit-sample").write_bytes(b"synthetic executable, not a device artifact")
elif tool == "plutil":
    print("NSLocalNetworkUsageDescription NSBonjourServices _p2pkit2._tcp")
else:
    assert tool in ("xcodegen", "open"), tool
'''


class LauncherLifecycleTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="p2pkit-ios-lifecycle-")
        self.addCleanup(self.temp.cleanup)
        self.root = pathlib.Path(self.temp.name)
        self.repo = self.root / "checkout with spaces"
        scripts = self.repo / "scripts"
        scripts.mkdir(parents=True)
        self.project = self.repo / "samples/iosApp"
        self.project.mkdir(parents=True)
        self.build = self.project / "build"
        self.lock = self.build / ".ios-launch.lock"
        for name in ("run-ios-app.sh", "run-ios-ui-tests.sh", "ios-run-lock.py"):
            source = REPO / "scripts" / name
            if source.exists():
                shutil.copy2(source, scripts / name)
        framework = self.repo / "library/p2p-transport-lan/build/XCFrameworks/release/P2pKitShared.xcframework"
        for slice_name in ("ios-arm64", "ios-arm64_x86_64-simulator"):
            binary = framework / slice_name / "P2pKitShared.framework/P2pKitShared"
            binary.parent.mkdir(parents=True)
            binary.touch()
        fake_bin = self.root / "fake-bin"
        fake_bin.mkdir()
        for name in ("xcrun", "xcodegen", "xcodebuild", "plutil", "open"):
            tool = fake_bin / name
            tool.write_text(FAKE_TOOL)
            tool.chmod(0o755)
        # Bash resolves functions before executable paths, including this macOS-only tool.
        bash_env = self.root / "bash-env"
        bash_env.write_text("function /usr/libexec/PlistBuddy { printf '%s\\n' p2pkit-sample; }\n")
        self.env = dict(os.environ, PATH=str(fake_bin) + os.pathsep + os.environ["PATH"],
                        FAKE_IOS_ROOT=str(self.root), BASH_ENV=str(bash_env), SIM_UDID=UDID)
        for name in ("IOS_RUN_DIR", "KEEP_IOS_RUN_ARTIFACTS", "FAKE_IOS_BLOCK", "FAKE_IOS_BUILD_FAILURE"):
            self.env.pop(name, None)
        self.processes = []
        self.addCleanup(self.stop_processes)

    def stop_processes(self):
        for process in self.processes:
            # Every child was started in its own session; never target a user's process group.
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.communicate(timeout=5)

    def start(self, script="run-ios-app.sh", **overrides):
        process = subprocess.Popen([BASH, str(self.repo / "scripts" / script)],
                                   env=dict(self.env, **overrides), stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT, text=True, start_new_session=True)
        self.processes.append(process)
        return process

    def finish(self, process, expected=0):
        output, _ = process.communicate(timeout=10)
        self.assertEqual(expected, process.returncode, output)
        self.assertNotIn("unbound variable", output)
        return output

    def wait_for_build(self, process):
        deadline = time.monotonic() + 5
        while not (self.root / "build-started").exists():
            self.assertIsNone(process.poll(), "launcher exited before the controlled build")
            self.assertLess(time.monotonic(), deadline, "controlled build did not start")
            time.sleep(0.01)

    def run_dirs(self):
        return list(self.build.glob("ios*-run.*"))

    def test_success_and_immediate_repeat_release_lock_and_owned_outputs(self):
        guard_inode = None
        for _ in range(2):
            output = self.finish(self.start())
            self.assertIn("[ios-run] Done.", output)
            self.assertFalse(self.lock.exists(), output)
            self.assertEqual([], self.run_dirs())
            guard = self.build / ".ios-launch.lock.guard"
            self.assertEqual(0, guard.stat().st_size)
            if guard_inode is not None:
                self.assertEqual(guard_inode, guard.stat().st_ino)
            guard_inode = guard.stat().st_ino

    def test_selection_failure_does_not_create_build_outputs(self):
        self.finish(self.start(SIM_UDID="22222222-2222-2222-2222-222222222222"), expected=1)
        self.assertFalse(self.build.exists())

    def test_ui_entry_point_releases_lock_and_owned_outputs(self):
        self.finish(self.start("run-ios-ui-tests.sh"))
        self.assertFalse(self.lock.exists())
        self.assertEqual([], self.run_dirs())

    def test_external_run_directory_creates_missing_lock_parent_and_is_preserved(self):
        external = self.root / "external-owned-output"
        external.mkdir()
        sentinel = external / "keep.txt"
        sentinel.write_text("caller data")
        for script in ("run-ios-app.sh", "run-ios-ui-tests.sh"):
            with self.subTest(script=script):
                if self.build.exists():
                    shutil.rmtree(self.build)
                derived = external / "DerivedData"
                if derived.exists():
                    shutil.rmtree(derived)
                self.finish(self.start(script, IOS_RUN_DIR=str(external)))
                self.assertFalse(self.lock.exists())
                self.assertEqual("caller data", sentinel.read_text())
                self.assertTrue(derived.is_dir())

    def test_failure_releases_lock_and_retains_evidence(self):
        output = self.finish(self.start(FAKE_IOS_BUILD_FAILURE="1"), expected=1)
        self.assertIn("xcodebuild failed", output)
        self.assertFalse(self.lock.exists())
        self.assertEqual(1, len(self.run_dirs()))
        self.assertTrue((self.run_dirs()[0] / "xcodebuild.log").is_file())

    def test_ui_failure_preserves_original_exit_status_and_evidence(self):
        self.finish(self.start("run-ios-ui-tests.sh", FAKE_IOS_BUILD_FAILURE="1"), expected=42)
        self.assertFalse(self.lock.exists())
        self.assertEqual(1, len(self.run_dirs()))

    def test_keep_override_retains_successful_owned_outputs(self):
        self.finish(self.start(KEEP_IOS_RUN_ARTIFACTS="1"))
        self.assertFalse(self.lock.exists())
        self.assertEqual(1, len(self.run_dirs()))

    def test_signal_exit_keeps_lock_until_foreground_work_finishes(self):
        for script in ("run-ios-app.sh", "run-ios-ui-tests.sh"):
            for signum in (signal.SIGINT, signal.SIGTERM):
                with self.subTest(script=script, signal=signum):
                    for marker in ("build-started", "release-build"):
                        (self.root / marker).unlink(missing_ok=True)
                    process = self.start(script, FAKE_IOS_BLOCK="1")
                    self.wait_for_build(process)
                    os.kill(process.pid, signum)
                    # A signal to Bash alone is deferred while its foreground command runs.
                    # Releasing the lock sooner would admit writes alongside that command.
                    time.sleep(0.05)
                    self.assertTrue(self.lock.is_dir())
                    (self.root / "release-build").touch()
                    self.finish(process, expected=128 + signum)
                    self.assertFalse(self.lock.exists())

    def dead_pid(self):
        child = subprocess.Popen([sys.executable, "-c", "pass"])
        child.wait(timeout=5)
        return child.pid

    def seed_lock(self, pid):
        self.lock.mkdir(parents=True)
        (self.lock / "pid").write_text(str(pid) + "\n")

    def test_dead_owner_is_reclaimed(self):
        self.seed_lock(self.dead_pid())
        output = self.finish(self.start())
        self.assertIn("Reclaimed stale launcher lock", output)
        self.assertFalse(self.lock.exists())

    def test_killed_launcher_cannot_be_reclaimed_while_its_build_worker_is_alive(self):
        process = self.start(FAKE_IOS_BLOCK="1")
        self.wait_for_build(process)
        worker = int((self.lock / "worker").read_text())
        os.kill(process.pid, signal.SIGKILL)
        self.assertEqual(-signal.SIGKILL, process.wait(timeout=5))
        output = self.finish(self.start(), expected=1)
        self.assertIn("another launcher owns", output)
        self.assertEqual(str(worker) + "\n", (self.lock / "worker").read_text())
        (self.root / "release-build").touch()
        process.communicate(timeout=5)
        deadline = time.monotonic() + 5
        while True:
            try:
                os.kill(worker, 0)
            except ProcessLookupError:
                break
            self.assertLess(time.monotonic(), deadline, "owned synthetic worker did not exit")
            time.sleep(0.01)
        output = self.finish(self.start())
        self.assertIn("Reclaimed stale launcher lock", output)
        self.assertFalse(self.lock.exists())

    def test_live_owner_is_never_removed(self):
        self.seed_lock(os.getpid())
        output = self.finish(self.start(), expected=1)
        self.assertIn("another launcher owns", output)
        self.assertEqual(str(os.getpid()) + "\n", (self.lock / "pid").read_text())
        self.assertFalse((self.root / "tools.log").exists() and
                         "xcodebuild" in (self.root / "tools.log").read_text())

    def test_missing_or_invalid_owner_is_not_blindly_reclaimed(self):
        for contents in (None, "", "not-a-pid", "0", "-1", "9" * 100):
            with self.subTest(contents=contents):
                self.lock.mkdir(parents=True)
                if contents is not None:
                    (self.lock / "pid").write_text(contents)
                output = self.finish(self.start(), expected=1)
                self.assertIn("cannot establish", output)
                self.assertTrue(self.lock.is_dir())
                shutil.rmtree(self.lock)

    def test_storage_failure_is_not_misreported_as_a_live_owner(self):
        self.build.write_text("not a directory")
        external = self.root / "external"
        output = self.finish(self.start(IOS_RUN_DIR=str(external)), expected=1)
        self.assertIn("cannot prepare launcher lock", output)
        self.assertNotIn("another launcher owns", output)
        self.assertEqual("not a directory", self.build.read_text())

    def test_non_owner_release_preserves_lock(self):
        self.seed_lock(os.getpid())
        script = 'source "$1"; release_ios_run_lock "$2"'
        result = subprocess.run([BASH, "-c", script, "bash", str(self.repo / "scripts/run-ios-app.sh"),
                                 str(self.lock)], env=self.env, text=True, capture_output=True, timeout=5)
        self.assertNotEqual(0, result.returncode)
        self.assertEqual(str(os.getpid()) + "\n", (self.lock / "pid").read_text())

    def test_cleanup_covers_acquisition_before_shell_flag_assignment(self):
        script = 'source "$1"; initialize_ios_run_cleanup "$2" ios-run; acquire_ios_run_lock "$3"; exit 143'
        result = subprocess.run([BASH, "-c", script, "bash", str(self.repo / "scripts/run-ios-app.sh"),
                                 str(self.project), str(self.lock)], env=self.env,
                                text=True, capture_output=True, timeout=5)
        self.assertEqual(143, result.returncode, result.stdout + result.stderr)
        self.assertFalse(self.lock.exists())

    def test_concurrent_stale_recovery_admits_exactly_one_launcher(self):
        self.seed_lock(self.dead_pid())
        first = self.start(FAKE_IOS_BLOCK="1")
        second = self.start("run-ios-ui-tests.sh", FAKE_IOS_BLOCK="1")
        deadline = time.monotonic() + 5
        while first.poll() is None and second.poll() is None:
            self.assertLess(time.monotonic(), deadline, "one concurrent launcher must refuse")
            time.sleep(0.01)
        loser, winner = (first, second) if first.poll() is not None else (second, first)
        output = self.finish(loser, expected=1)
        self.assertIn("another launcher owns", output)
        self.wait_for_build(winner)
        self.assertEqual(str(winner.pid) + "\n", (self.lock / "pid").read_text())
        (self.root / "release-build").touch()
        self.finish(winner)
        self.assertFalse(self.lock.exists())

    def test_symlink_lock_is_not_followed_or_removed(self):
        target = self.root / "caller-lock"
        target.mkdir()
        (target / "pid").write_text(str(self.dead_pid()) + "\n")
        self.build.mkdir()
        self.lock.symlink_to(target, target_is_directory=True)
        self.finish(self.start(), expected=1)
        self.assertTrue(self.lock.is_symlink())
        self.assertTrue((target / "pid").is_file())

    def test_symlink_guard_is_not_followed(self):
        target = self.root / "caller-file"
        target.write_text("preserve")
        self.build.mkdir()
        guard = self.build / ".ios-launch.lock.guard"
        guard.symlink_to(target)
        self.finish(self.start(), expected=1)
        self.assertTrue(guard.is_symlink())
        self.assertEqual("preserve", target.read_text())
        self.assertFalse(self.lock.exists())

    def test_unexpected_lock_contents_are_preserved(self):
        self.seed_lock(self.dead_pid())
        sentinel = self.lock / "unexpected.txt"
        sentinel.write_text("do not delete")
        self.finish(self.start(), expected=1)
        self.assertEqual("do not delete", sentinel.read_text())
        self.assertTrue((self.lock / "pid").is_file())

    def test_invalid_worker_record_is_not_reclaimed(self):
        self.seed_lock(self.dead_pid())
        (self.lock / "worker").write_text("invalid")
        self.finish(self.start(), expected=1)
        self.assertEqual("invalid", (self.lock / "worker").read_text())


if __name__ == "__main__":
    unittest.main(verbosity=2)
