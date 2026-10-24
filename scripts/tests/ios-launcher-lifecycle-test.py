#!/usr/bin/env python3
"""Exercise the real launcher entry points; only macOS tool boundaries are fake."""

import json
import os
import pathlib
import shutil
import shlex
import signal
import stat
import subprocess
import sys
import tempfile
import time
import unittest
import uuid
from unittest import mock


REPO = pathlib.Path(__file__).resolve().parents[2]
sys.dont_write_bytecode = True
sys.path.insert(0, str(REPO / "scripts"))
import audit_processes as ownership
BASH = os.environ.get("P2PKIT_TEST_BASH", "bash")
UDID = "11111111-1111-1111-1111-111111111111"
FAKE_TOOL = r'''#!/usr/bin/env python3
import os, pathlib, sys, time, json
tool = pathlib.Path(sys.argv[0]).name
root = pathlib.Path(os.environ["FAKE_IOS_ROOT"])
args = sys.argv[1:]
with (root / "tools.log").open("a") as log:
    log.write(tool + " " + " ".join(args) + "\n")
if tool == "xcrun":
    if args[:2] == ["--sdk", "iphonesimulator"]:
        assert args[2:] in (["--show-sdk-path"], ["--show-sdk-platform-path"]), args
        print("/synthetic-sdk" if args[2] == "--show-sdk-path" else "/synthetic-platform")
        sys.exit(0)
    if args[0] == "swiftc":
        assert "-typecheck" in args and "-warnings-as-errors" in args, args
        if args[-1].endswith(("/KeyboardQueryCauseUITests.swift", "/KeyboardReflowCauseUITests.swift")):
            sys.exit(int(os.environ.get("FAKE_SWIFT_TYPECHECK_UI_EXIT", "0")))
        sys.exit(int(os.environ.get("FAKE_SWIFT_TYPECHECK_EXIT", "0")))
    assert args[0] == "simctl", args
    if args[1:3] == ["list", "--json"]:
        print(json.dumps({"devices": {"com.apple.CoreSimulator.SimRuntime.iOS-26-5": [
            {"name": "iPhone 17", "udid": "11111111-1111-1111-1111-111111111111",
             "state": "Shutdown", "isAvailable": True}],
            "com.apple.CoreSimulator.SimRuntime.iOS-26-2": [
            {"name": "iPhone 17", "udid": "22222222-2222-2222-2222-222222222222",
             "state": "Shutdown", "isAvailable": True}]}}))
    elif args[1] == "list":
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
        for name in ("SIM_RUNTIME", "IOS_RUN_DIR", "KEEP_IOS_RUN_ARTIFACTS", "FAKE_IOS_BLOCK", "FAKE_IOS_BUILD_FAILURE"):
            self.env.pop(name, None)
        self.processes = []
        self.addCleanup(self.stop_processes)

    def test_ui_runtime_selection_reaches_existing_launcher_without_explicit_udid(self):
        self.finish(self.start('run-ios-ui-tests.sh', SIM_UDID='',
                               SIM_RUNTIME='com.apple.CoreSimulator.SimRuntime.iOS-26-5'))
        tools = (self.root / 'tools.log').read_text()
        self.assertIn('simctl bootstatus ' + UDID + ' -b', tools)
        self.assertIn('-destination platform=iOS Simulator,id=' + UDID, tools)
        self.assertIn('xcodebuild ', tools)
        self.assertFalse(self.lock.exists())

    def test_ui_runtime_selection_rejects_conflicting_explicit_udid_before_mutation(self):
        self.finish(self.start('run-ios-ui-tests.sh', SIM_UDID='22222222-2222-2222-2222-222222222222',
                               SIM_RUNTIME='com.apple.CoreSimulator.SimRuntime.iOS-26-5'), expected=1)
        tools = (self.root / 'tools.log').read_text()
        self.assertNotIn('bootstatus', tools)
        self.assertNotIn('xcodegen', tools)
        self.assertNotIn('xcodebuild', tools)
        self.assertFalse(self.lock.exists())

    def test_ui_missing_runtime_refuses_without_name_fallback_or_mutation(self):
        self.finish(self.start('run-ios-ui-tests.sh', SIM_UDID='',
                               SIM_RUNTIME='com.apple.CoreSimulator.SimRuntime.iOS-27-0'), expected=5)
        tools = (self.root / 'tools.log').read_text()
        self.assertNotIn('bootstatus', tools)
        self.assertNotIn('xcodebuild', tools)
        self.assertFalse(self.lock.exists())

    def passive_capture_fixture(self):
        # Only the post-Xcode native log boundary is synthetic. Execute the real
        # shell's errexit, status selection, lock and run-directory finalizers.
        helper = self.repo / 'scripts/ios_keyboard_passive_capture.py'
        helper.write_text('''import json, os, pathlib, sys
root = pathlib.Path(os.environ["FAKE_IOS_ROOT"])
build = root / "checkout with spaces/samples/iosApp/build"
(root / "passive.json").write_text(json.dumps({"argv": sys.argv[1:],
    "lockPresent": (build / ".ios-launch.lock").is_dir(),
    "runsPresent": bool(list(build.glob("ios-ui-run.*")))}))
with (root / "tools.log").open("a") as stream:
    stream.write("passive-capture\\n")
sys.exit(int(os.environ.get("FAKE_PASSIVE_EXIT", "0")))
''')
        self.env.update(COMPONENT='compatibility', GITHUB_ACTIONS='true')

    def passive_record(self, command_status, launcher_status, *, expect_build=True):
        record = json.loads((self.root / 'passive.json').read_text())
        self.assertEqual([UDID, command_status, str(launcher_status)], record['argv'])
        self.assertTrue(record['lockPresent'])
        self.assertTrue(record['runsPresent'])
        tools = (self.root / 'tools.log').read_text()
        if expect_build:
            self.assertLess(tools.index('xcodebuild '), tools.index('passive-capture'))
        self.assertEqual(1, tools.count('passive-capture'))
        self.assertFalse(self.lock.exists())
        return tools

    def test_passive_full_suite_keeps_original_target_command_and_cleanup(self):
        self.passive_capture_fixture()
        self.finish(self.start('run-ios-ui-tests.sh'))
        tools = self.passive_record('0', 0)
        build = next(line for line in tools.splitlines() if line.startswith('xcodebuild '))
        self.assertIn('-scheme p2pkit-sample-ui ', build)
        self.assertIn('-parallel-testing-enabled NO ', build)
        self.assertIn('OTHER_SWIFT_FLAGS=$(inherited) -D P2PKIT_KEYBOARD_CAUSE_PROBE', build)
        self.assertTrue(build.endswith(' test'))
        for forbidden in ('only-testing', 'skip-testing', 'resultBundlePath', 'maximum-concurrent',
                          'open ', 'simctl create', 'simctl delete', 'swift test', 'defaults '):
            self.assertNotIn(forbidden, tools)
        self.assertEqual([], list(self.build.glob('ios-ui-run.*')))

    def test_passive_original_ui_failure_is_preserved_after_successful_capture(self):
        self.passive_capture_fixture()
        self.finish(self.start('run-ios-ui-tests.sh', FAKE_IOS_BUILD_FAILURE='1'), expected=42)
        self.passive_record('42', 42)
        self.assertEqual(1, len(list(self.build.glob('ios-ui-run.*'))))

    def test_passive_capture_failure_cannot_erase_original_ui_failure(self):
        self.passive_capture_fixture()
        self.finish(self.start('run-ios-ui-tests.sh', FAKE_IOS_BUILD_FAILURE='1',
                               FAKE_PASSIVE_EXIT='125'), expected=42)
        self.passive_record('42', 42)

    def test_passive_capture_failure_invalidates_only_otherwise_successful_run(self):
        self.passive_capture_fixture()
        self.finish(self.start('run-ios-ui-tests.sh', FAKE_PASSIVE_EXIT='125'), expected=125)
        self.passive_record('0', 0)
        self.assertEqual(1, len(list(self.build.glob('ios-ui-run.*'))))

    def test_passive_capture_does_not_wrap_helper_in_errexit_ignoring_context(self):
        self.passive_capture_fixture()
        environment = pathlib.Path(self.env['BASH_ENV'])
        with environment.open('a') as stream:
            stream.write(r'''
trap 'case "$BASH_COMMAND" in run_ios_xcodebuild\ *)
    run_ios_xcodebuild() { false; echo ERREXIT_WAS_DISABLED; }
    trap - DEBUG;; esac' DEBUG
''')
        output = self.finish(self.start('run-ios-ui-tests.sh'), expected=1)
        self.assertNotIn('ERREXIT_WAS_DISABLED', output)
        self.passive_record('1', 1, expect_build=False)

    def test_query_diagnostic_keeps_shared_capture_status_and_cleanup(self):
        for failure in (False, True):
            with self.subTest(failure=failure):
                self.passive_capture_fixture()
                before = (self.root / 'tools.log').read_text().splitlines() if (self.root / 'tools.log').exists() else []
                self.finish(self.start('run-ios-ui-tests.sh', arguments=('run-keyboard-query-cause',),
                    COMPONENT='apple-keyboard-query-diagnostic', FAKE_IOS_BUILD_FAILURE='1' if failure else '0'),
                    expected=42 if failure else 0)
                record = json.loads((self.root / 'passive.json').read_text())
                self.assertEqual([UDID, '42' if failure else '0', '42' if failure else '0'], record['argv'])
                self.assertTrue(record['lockPresent'])
                calls = (self.root / 'tools.log').read_text().splitlines()[len(before):]
                builds = [line for line in calls if line.startswith('xcodebuild ')]
                self.assertEqual(1, len(builds))
                self.assertIn('-scheme p2pkit-sample-keyboard-query ', builds[0])
                self.assertIn('-parallel-testing-enabled NO ', builds[0])
                self.assertIn('-maximum-concurrent-test-simulator-destinations 1 ', builds[0])
                self.assertIn('P2PKIT_KEYBOARD_QUERY_PROBE', builds[0])
                self.assertIn('SWIFT_TREAT_WARNINGS_AS_ERRORS=YES test', builds[0])
                self.assertEqual(1, calls.count('passive-capture'))
                self.assertLess(calls.index(builds[0]), calls.index('passive-capture'))
                typechecks = [line for line in calls if line.startswith('xcrun swiftc ')]
                self.assertEqual(2, len(typechecks))
                for check in typechecks:
                    self.assertLess(calls.index(check), calls.index('xcodegen generate'))
                    self.assertIn('-typecheck -warnings-as-errors -swift-version 5 ', check)
                # Match Xcode's test compiler search paths: the framework
                # headers alone do not expose XCTest's Swift assertions.
                self.assertIn('-F /synthetic-platform/Developer/Library/Frameworks ', typechecks[1])
                self.assertIn('-F /synthetic-sdk/Developer/Library/Frameworks ', typechecks[1])
                self.assertIn('-Isystem /synthetic-platform/Developer/usr/lib ', typechecks[1])
                self.assertFalse(self.lock.exists())
                for forbidden in ('skip-testing', 'test-iterations', 'retry-tests', 'open ', 'simctl create', 'defaults '):
                    self.assertFalse(any(forbidden in line for line in calls))

    def test_query_typecheck_failure_precedes_native_build_and_preserves_nonzero(self):
        self.finish(self.start('run-ios-ui-tests.sh', arguments=('run-keyboard-query-cause',),
                               FAKE_SWIFT_TYPECHECK_EXIT='19'), expected=19)
        calls = (self.root / 'tools.log').read_text().splitlines()
        self.assertEqual(1, sum(line.startswith('xcrun swiftc ') for line in calls))
        for forbidden in ('xcodegen', 'xcodebuild', 'bootstatus', 'passive-capture'):
            self.assertFalse(any(forbidden in line for line in calls))
        self.assertFalse(self.lock.exists())

    def test_query_xctest_typecheck_failure_preserves_nonzero_before_framework_build(self):
        self.finish(self.start('run-ios-ui-tests.sh', arguments=('run-keyboard-query-cause',),
                               FAKE_SWIFT_TYPECHECK_UI_EXIT='23'), expected=23)
        calls = (self.root / 'tools.log').read_text().splitlines()
        self.assertEqual(2, sum(line.startswith('xcrun swiftc ') for line in calls))
        for forbidden in ('xcodegen', 'xcodebuild', 'bootstatus', 'passive-capture'):
            self.assertFalse(any(forbidden in line for line in calls))
        self.assertFalse(self.lock.exists())

    def test_reflow_diagnostic_runs_only_two_case_class_with_original_capture_and_cleanup(self):
        for failure in (False, True):
            with self.subTest(failure=failure):
                self.passive_capture_fixture()
                before = (self.root / 'tools.log').read_text().splitlines() if (self.root / 'tools.log').exists() else []
                self.finish(self.start('run-ios-ui-tests.sh', arguments=('run-keyboard-reflow-cause',),
                    COMPONENT='apple-keyboard-reflow-diagnostic', FAKE_IOS_BUILD_FAILURE='1' if failure else '0'),
                    expected=42 if failure else 0)
                record = json.loads((self.root / 'passive.json').read_text())
                self.assertEqual([UDID, '42' if failure else '0', '42' if failure else '0'], record['argv'])
                self.assertTrue(record['lockPresent'])
                calls = (self.root / 'tools.log').read_text().splitlines()[len(before):]
                typechecks = [line for line in calls if line.startswith('xcrun swiftc ')]
                self.assertEqual(2, len(typechecks))
                self.assertTrue(typechecks[0].endswith('/KeyboardReflowProbe.swift'))
                self.assertTrue(typechecks[1].endswith('/KeyboardReflowCauseUITests.swift'))
                for check in typechecks:
                    self.assertIn('-D P2PKIT_KEYBOARD_REFLOW_PROBE ', check)
                    self.assertIn('-typecheck -warnings-as-errors -swift-version 5 ', check)
                    self.assertLess(calls.index(check), calls.index('xcodegen generate'))
                self.assertIn('-Isystem /synthetic-platform/Developer/usr/lib ', typechecks[1])
                builds = [line for line in calls if line.startswith('xcodebuild ')]
                self.assertEqual(1, len(builds))
                self.assertIn('-scheme p2pkit-sample-keyboard-query ', builds[0])
                self.assertIn('-only-testing:p2pkit-sample-keyboard-query-tests/KeyboardReflowCauseUITests ', builds[0])
                self.assertIn('SWIFT_TREAT_WARNINGS_AS_ERRORS=YES test', builds[0])
                self.assertIn('-maximum-concurrent-test-simulator-destinations 1 ', builds[0])
                self.assertIn('-parallel-testing-enabled NO ', builds[0])
                self.assertNotIn('P2PKIT_KEYBOARD_QUERY_PROBE', builds[0])
                self.assertEqual(1, calls.count('passive-capture'))
                self.assertLess(calls.index(builds[0]), calls.index('passive-capture'))
                self.assertFalse(self.lock.exists())
                for forbidden in ('skip-testing', 'test-iterations', 'retry-tests', 'open ', 'simctl create', 'defaults '):
                    self.assertFalse(any(forbidden in line for line in calls))

    def test_reflow_both_typecheck_failures_stop_before_app_build(self):
        for variable, count in (('FAKE_SWIFT_TYPECHECK_EXIT', 1), ('FAKE_SWIFT_TYPECHECK_UI_EXIT', 2)):
            with self.subTest(variable=variable):
                before = (self.root / 'tools.log').read_text().splitlines() if (self.root / 'tools.log').exists() else []
                self.finish(self.start('run-ios-ui-tests.sh', arguments=('run-keyboard-reflow-cause',),
                                       **{variable: '23'}), expected=23)
                calls = (self.root / 'tools.log').read_text().splitlines()[len(before):]
                self.assertEqual(count, sum(line.startswith('xcrun swiftc ') for line in calls))
                for forbidden in ('xcodegen', 'xcodebuild', 'bootstatus', 'passive-capture'):
                    self.assertFalse(any(forbidden in line for line in calls))
                self.assertFalse(self.lock.exists())

    def test_passive_capture_is_not_added_to_focused_diagnostic(self):
        self.passive_capture_fixture()
        self.finish(self.start('run-ios-ui-tests.sh', arguments=('run-keyboard-readiness',)))
        self.assertFalse((self.root / 'passive.json').exists())
        self.assertNotIn('P2PKIT_KEYBOARD_CAUSE_PROBE', (self.root / 'tools.log').read_text())

    def test_passive_signal_preserves_unknown_command_result_and_original_exit(self):
        self.passive_capture_fixture()
        process = self.start('run-ios-ui-tests.sh', FAKE_IOS_BLOCK='1')
        self.wait_for_build(process)
        os.kill(process.pid, signal.SIGTERM)
        (self.root / 'release-build').touch()
        self.finish(process, expected=143)
        self.passive_record('UNOBSERVED', 143)

    def stop_processes(self):
        for process in self.processes:
            # Every child was started in its own session; never target a user's process group.
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.communicate(timeout=5)

    def launcher_environment(self, overrides):
        # Fixture inputs may select a different audit state, but must not mutate
        # an inherited controller's ownership domain in a new OS process.
        state = overrides.get(ownership.STATE_ENV)
        environment = dict(self.env)
        if state and environment.get(ownership.CHAIN_ENV):
            environment = ownership.ownership_environment(
                environment, environment[ownership.JOB_ENV], uuid.uuid4().hex,
                state, environment["GRADLE_USER_HOME"], allow_new_context=True)
        environment.update({key: value for key, value in overrides.items()
                            if key != ownership.STATE_ENV or state})
        if ownership.STATE_ENV in overrides and not state:
            # Exercise the real missing-state refusal INSIDE Bash, after its
            # path lookup children and before the child-free case/exit boundary.
            # The initial OS environment remains coherently owned. Never erase
            # the ancestor markers or exempt this child from outer supervision.
            boundary = 'action="${1:-}"'
            self.assertIn("\n" + boundary + "\n", (self.repo / "scripts/run-ios-ui-tests.sh").read_text())
            hook = ('if [[ "$BASH_COMMAND" == ' + shlex.quote(boundary) + ' ]]; then '
                    'printf "%s\\n" fired > "$FAKE_IOS_ROOT/missing-state-hook"; '
                    'unset P2PKIT_AUDIT_STATE_DIR; trap - DEBUG; fi')
            bash_env = self.root / ("missing-state-env-" + uuid.uuid4().hex)
            bash_env.write_text(pathlib.Path(environment["BASH_ENV"]).read_text() +
                                "trap " + shlex.quote(hook) + " DEBUG\n")
            environment["BASH_ENV"] = str(bash_env)
        return environment

    def test_fixture_state_inputs_preserve_original_ancestor_ownership(self):
        job, invocation = uuid.uuid4().hex, uuid.uuid4().hex
        state, home = str(self.root / "outer-state"), str(self.root / "outer-home")
        self.env = ownership.ownership_environment(self.env, job, invocation, state, home, allow_new_context=True)
        controller = object.__new__(ownership.PosixScope)
        controller.job, controller.invocation, controller.state, controller.home = job, invocation, state, home
        for selected in (str(self.root / "nested-state"), ""):
            environment = self.launcher_environment({ownership.STATE_ENV: selected})
            self.assertTrue(controller._ours({key.encode(): value.encode() for key, value in environment.items()}))
            domains = ownership.ownership_domains(environment[ownership.CHAIN_ENV], environment[ownership.DOMAINS_ENV])
            self.assertIn({"id": invocation, "job": job, "state": state, "home": home}, domains)
            self.assertEqual(selected or state, domains[-1]["state"])
            self.assertEqual(home, domains[-1]["home"])
            self.assertEqual(selected or state, environment[ownership.STATE_ENV])

    def start(self, script="run-ios-app.sh", cwd=None, absolute=False, arguments=(), **overrides):
        cwd = cwd or self.repo
        path = self.repo / "scripts" / script
        # The default matches Gradle's repository-root, relative-path invocation.
        argument = str(path) if absolute else os.path.relpath(path, cwd)
        process = subprocess.Popen([BASH, argument, *arguments], cwd=cwd,
                                   env=self.launcher_environment(overrides), stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT, text=True, start_new_session=True)
        self.processes.append(process)
        return process

    def finish(self, process, expected=0):
        wait_started = time.monotonic()
        try:
            output, _ = process.communicate(timeout=10)
        except subprocess.TimeoutExpired as error:
            wait_elapsed_millis = int((time.monotonic() - wait_started) * 1000)
            # The synthetic checkout is removed by cleanup. Preserve the last
            # observed phase before that happens, without renewing the deadline,
            # retrying a launcher, or treating a later exit as a passing result.
            observed = self.timeout_diagnostics(process, error)
            observed["waitElapsedMillis"] = wait_elapsed_millis
            self.fail("Synthetic launcher exceeded the unchanged 10-second deadline: " +
                      json.dumps(observed, sort_keys=True))
        self.assertEqual(expected, process.returncode, output)
        self.assertNotIn("unbound variable", output)
        return output

    def timeout_diagnostics(self, process, error):
        """Bounded synthetic-fixture observations, never live ownership proof."""
        limit = 4096

        def text_tail(value):
            truncated = isinstance(value, (bytes, str)) and len(value) > limit
            if isinstance(value, bytes):
                value = value[-limit:].decode("utf-8", errors="replace")
            value = value if isinstance(value, str) else ""
            return {"tail": value[-limit:].replace(str(self.root), "<fixture>"),
                    "truncated": truncated}

        def read_record(path, directory=None):
            try:
                fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW, dir_fd=directory)
                with os.fdopen(fd, "rb") as stream:
                    info = os.fstat(stream.fileno())
                    if not stat.S_ISREG(info.st_mode):
                        return {"state": "NOT_REGULAR"}
                    if directory is not None:
                        raw = stream.read(65)
                        value = raw.strip()
                        return {"state": "RECORDED" if 0 < len(raw) <= 64 and value.isdigit() else "INVALID",
                                "pid": int(value) if 0 < len(raw) <= 64 and value.isdigit() else None}
                    stream.seek(max(0, info.st_size - limit))
                    result = text_tail(stream.read(limit))
                    result["truncated"] = info.st_size > limit
                    return {"state": "READ", **result}
            except OSError as failure:
                return {"state": "UNAVAILABLE", "errno": failure.errno}

        snapshot = {"scope": "SYNTHETIC_TIMEOUT_OBSERVATION_NOT_OWNERSHIP_PROOF",
                    "launchOrdinal": next((i + 1 for i, child in enumerate(self.processes)
                                           if child is process), None),
                    "launcherReturnCode": process.poll(), "output": text_tail(error.output),
                    "tools": read_record(self.root / "tools.log")}
        try:
            guard = pathlib.Path(str(self.lock) + ".guard").lstat()
            snapshot["guard"] = {"regular": stat.S_ISREG(guard.st_mode), "inode": guard.st_ino,
                                 "bytes": guard.st_size, "links": guard.st_nlink}
        except OSError as failure:
            snapshot["guard"] = {"state": "UNAVAILABLE", "errno": failure.errno}
        try:
            directory = os.open(self.lock, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_NONBLOCK)
            try:
                snapshot["lock"] = {"state": "DIRECTORY", "owner": read_record("pid", directory),
                                    "worker": read_record("worker", directory)}
            finally:
                os.close(directory)
        except OSError as failure:
            snapshot["lock"] = {"state": "UNAVAILABLE", "errno": failure.errno}
        return snapshot

    def test_timeout_preserves_bounded_phase_and_lock_records_without_retry_or_pass(self):
        self.seed_lock(12345)
        (self.lock / "worker").write_text("12346\n")
        (self.root / "tools.log").write_text("x" * 6000 + "\nxcodebuild synthetic-build\n")
        error = subprocess.TimeoutExpired(["bash", "scripts/run-ios-app.sh"], 10,
                                          output=b"x" * 6000 + b"\n[ios-run] Building iOS app...\n")
        process = mock.Mock()
        process.communicate.side_effect = error
        process.poll.return_value = None
        with mock.patch.object(self, "processes", [object(), process]):
            with self.assertRaises(AssertionError) as failed:
                self.finish(process)
        process.communicate.assert_called_once_with(timeout=10)
        self.assertIn("unchanged 10-second deadline", str(failed.exception))
        snapshot = json.loads(str(failed.exception).split(": ", 1)[1])
        self.assertIn("[ios-run] Building iOS app...", snapshot["output"]["tail"])
        self.assertTrue(snapshot["output"]["truncated"])
        self.assertIn("xcodebuild synthetic-build", snapshot["tools"]["tail"])
        self.assertTrue(snapshot["tools"]["truncated"])
        self.assertEqual(12345, snapshot["lock"]["owner"]["pid"])
        self.assertEqual(12346, snapshot["lock"]["worker"]["pid"])
        self.assertEqual(2, snapshot["launchOrdinal"])
        self.assertIsNone(snapshot["launcherReturnCode"])
        self.assertLess(len(str(failed.exception)), 10000)
        self.assertEqual("12345\n", (self.lock / "pid").read_text())
        self.assertEqual("12346\n", (self.lock / "worker").read_text())

    def test_timeout_diagnostics_do_not_follow_symlinks_or_block_on_fifo(self):
        other = self.root / "unrelated"
        other.write_text("MUST_NOT_READ_UNRELATED_CONTENT")
        tools = self.root / "tools.log"
        tools.symlink_to(other)
        self.build.mkdir()
        self.lock.symlink_to(self.root, target_is_directory=True)
        process = mock.Mock()
        process.poll.return_value = 0  # Even a post-deadline exit cannot erase the timeout.
        process.communicate.side_effect = subprocess.TimeoutExpired(["synthetic"], 10)
        with self.assertRaises(AssertionError) as failed:
            self.finish(process)
        self.assertNotIn("MUST_NOT_READ_UNRELATED_CONTENT", str(failed.exception))
        tools.unlink()
        os.mkfifo(tools)
        observed = self.timeout_diagnostics(process, subprocess.TimeoutExpired(["synthetic"], 10))
        self.assertEqual("NOT_REGULAR", observed["tools"]["state"])
        self.assertTrue(self.lock.is_symlink())

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

    def test_absolute_invocation_remains_supported(self):
        self.finish(self.start(absolute=True))
        self.assertFalse(self.lock.exists())
        self.assertEqual([], self.run_dirs())

    def test_relative_launch_from_scripts_directory_repeats(self):
        for _ in range(2):
            self.finish(self.start(cwd=self.repo / "scripts"))
            self.assertFalse(self.lock.exists())
            self.assertEqual([], self.run_dirs())

    def test_relative_missing_framework_bootstrap_from_scripts_directory(self):
        shutil.rmtree(self.repo / "library")
        (self.repo / "gradlew").write_text('''#!/bin/sh
set -eu
[ "$1" = :p2p-transport-lan:verifyP2pKitSharedReleaseXCFrameworkProvenance ]
framework=library/p2p-transport-lan/build/XCFrameworks/release/P2pKitShared.xcframework
for slice in ios-arm64 ios-arm64_x86_64-simulator; do
    mkdir -p "$framework/$slice/P2pKitShared.framework"
    : > "$framework/$slice/P2pKitShared.framework/P2pKitShared"
done
printf 'invoked\\n' >> fake-gradle-invocations
''')
        for _ in range(2):
            self.finish(self.start(cwd=self.repo / "scripts"))
            self.assertFalse(self.lock.exists())
            self.assertEqual([], self.run_dirs())
        self.assertEqual("invoked\n", (self.repo / "fake-gradle-invocations").read_text())

    def test_ui_entry_point_releases_lock_and_owned_outputs(self):
        self.finish(self.start("run-ios-ui-tests.sh"))
        self.assertFalse(self.lock.exists())
        self.assertEqual([], self.run_dirs())
        xcode = [call for call in (self.root / "tools.log").read_text().splitlines()
                 if call.startswith("xcodebuild ")]
        self.assertEqual(1, len(xcode))
        self.assertIn("-scheme p2pkit-sample-ui", xcode[0])
        self.assertNotIn("-only-testing:", xcode[0], "The ordinary both-target suite remains unfiltered")

    def assert_keyboard_readiness_call(self, calls):
        xcode = [call for call in calls if call.startswith("xcodebuild ")]
        self.assertEqual(1, len(xcode), "The diagnostic must not retry either XCTest case")
        self.assertIn(" -derivedDataPath ", xcode[0])
        self.assertIn(" -resultBundlePath ", xcode[0])
        derived = pathlib.Path(xcode[0].split(" -derivedDataPath ", 1)[1].split(" -resultBundlePath ", 1)[0])
        expected = [
            "xcodebuild", "-project", str(self.project / "p2pkit-sample.xcodeproj"),
            "-scheme", "p2pkit-sample-ui", "-configuration", "Debug", "-sdk", "iphonesimulator",
            "-destination", "platform=iOS Simulator,id=" + UDID, "-derivedDataPath", str(derived),
            "-resultBundlePath", str(derived / "Logs/Test/swift-keyboard-readiness.xcresult"),
            "-parallel-testing-enabled", "NO", "-maximum-concurrent-test-simulator-destinations", "1",
            "-only-testing:p2pkit-sample-uitests/ContentViewPresentationUITests/"
            "testRenderedPortRoundTripsThroughManualInputInEnglishLocale",
            "-only-testing:p2pkit-sample-uitests/ContentViewPresentationUITests/"
            "testRenderedPortRoundTripsThroughManualInputInGermanLocale",
            "SWIFT_TREAT_WARNINGS_AS_ERRORS=YES", "test",
        ]
        jobs = self.env.get("P2PKIT_XCODE_JOBS", "")
        if jobs:
            self.assertIn(jobs, ("1", "2"), "Only the existing bounded compilation override is admissible")
            expected[1:1] = ["-jobs", jobs]
        self.assertEqual(" ".join(expected), xcode[0])
        self.assertEqual(["xcodegen generate"], [call for call in calls if call.startswith("xcodegen ")])
        self.assertLess(calls.index("xcodegen generate"), calls.index(xcode[0]))
        self.assertIn("xcrun simctl bootstatus " + UDID + " -b", calls)
        return derived

    def test_keyboard_readiness_action_keeps_default_runtime_generation_and_owned_cleanup(self):
        self.finish(self.start("run-ios-ui-tests.sh", arguments=("run-keyboard-readiness",), SIM_UDID="",
                               SIM_RUNTIME="com.apple.CoreSimulator.SimRuntime.iOS-26-5"))
        calls = (self.root / "tools.log").read_text().splitlines()
        derived = self.assert_keyboard_readiness_call(calls)
        self.assertEqual(self.build, derived.parent.parent)
        self.assertTrue(derived.parent.name.startswith("ios-ui-run."))
        self.assertEqual("DerivedData", derived.name)
        self.assertFalse(self.lock.exists())
        self.assertEqual([], self.run_dirs())

    def test_keyboard_readiness_failure_stays_nonzero_and_retains_owned_diagnostics(self):
        self.finish(self.start("run-ios-ui-tests.sh", arguments=("run-keyboard-readiness",),
                               FAKE_IOS_BUILD_FAILURE="1"), expected=42)
        derived = self.assert_keyboard_readiness_call((self.root / "tools.log").read_text().splitlines())
        self.assertEqual([derived.parent], self.run_dirs())
        self.assertFalse(self.lock.exists())

    def test_keyboard_readiness_borrowed_directory_is_preserved_on_success_and_failure(self):
        for failure in (False, True):
            with self.subTest(failure=failure):
                external = self.root / ("borrowed-keyboard-failure" if failure else "borrowed-keyboard-success")
                external.mkdir()
                sentinel = external / "keep.txt"
                sentinel.write_text("caller data")
                before = (self.root / "tools.log").read_text().splitlines() if (self.root / "tools.log").exists() else []
                self.finish(self.start("run-ios-ui-tests.sh", arguments=("run-keyboard-readiness",),
                                       IOS_RUN_DIR=str(external), FAKE_IOS_BUILD_FAILURE="1" if failure else "0"),
                            expected=42 if failure else 0)
                calls = (self.root / "tools.log").read_text().splitlines()[len(before):]
                self.assertEqual(external / "DerivedData", self.assert_keyboard_readiness_call(calls))
                self.assertEqual("caller data", sentinel.read_text())
                self.assertFalse(self.lock.exists())

    def test_keyboard_readiness_action_rejects_extra_arguments_and_unknown_aliases_before_tools(self):
        for arguments in (("run-keyboard-readiness", "extra"), ("keyboard-readiness",),
                          ("run-keyboard-readiness-extra",)):
            with self.subTest(arguments=arguments):
                self.finish(self.start("run-ios-ui-tests.sh", arguments=arguments), expected=2)
                self.assertFalse((self.root / "tools.log").exists())
                self.assertFalse(self.build.exists())

    def test_keyboard_readiness_selection_oracle_rejects_broadening_repetition_and_relaxed_policy(self):
        self.finish(self.start("run-ios-ui-tests.sh", arguments=("run-keyboard-readiness",)))
        calls = (self.root / "tools.log").read_text().splitlines()
        self.assert_keyboard_readiness_call(calls)
        selector = "-only-testing:p2pkit-sample-uitests/ContentViewPresentationUITests/"
        english = selector + "testRenderedPortRoundTripsThroughManualInputInEnglishLocale"
        german = selector + "testRenderedPortRoundTripsThroughManualInputInGermanLocale"
        mutations = (
            (english, ""), (german, ""), (english, selector.rstrip("/")),
            (german, english), (english, english + " " + english),
            (german, german + " -test-iterations 2"), (german, german + " -retry-tests-on-failure"),
            (german, german + " -skip-testing:p2pkit-sample-uitests"),
            (german, german + " -test-timeouts-enabled NO"),
            ("-parallel-testing-enabled NO", "-parallel-testing-enabled YES"),
            ("-maximum-concurrent-test-simulator-destinations 1", "-maximum-concurrent-test-simulator-destinations 2"),
            ("SWIFT_TREAT_WARNINGS_AS_ERRORS=YES", "SWIFT_TREAT_WARNINGS_AS_ERRORS=NO"),
            ("swift-keyboard-readiness.xcresult", "outside-owned-result.xcresult"),
        )
        for original, replacement in mutations:
            with self.subTest(mutation=original, replacement=replacement), self.assertRaises(AssertionError):
                self.assert_keyboard_readiness_call([call.replace(original, replacement) for call in calls])
        with self.assertRaises(AssertionError):
            self.assert_keyboard_readiness_call(calls + [call for call in calls if call.startswith("xcodebuild ")])

    def test_cancellation_probe_selects_one_case_without_invalid_repetition_option(self):
        external = self.root / "owned-probe-output"
        self.finish(self.start("run-ios-ui-tests.sh", arguments=("run-cancellation-probe",),
                               IOS_RUN_DIR=str(external), P2PKIT_AUDIT_STATE_DIR=str(self.root / "audit-state")))
        calls = (self.root / "tools.log").read_text().splitlines()
        xcode = [call for call in calls if call.startswith("xcodebuild ")]
        self.assertEqual(1, len(xcode))
        self.assertNotIn("-test-iterations", xcode[0])
        self.assertIn("-parallel-testing-enabled NO", xcode[0])
        self.assertIn("-maximum-concurrent-test-simulator-destinations 1", xcode[0])
        self.assertIn("-only-testing:p2pkit-sample-cancellation-probe-tests/"
                      "SwiftFlowCancellationProbeTests/testSwiftTaskCancellationFinishesActualDiagnosticCollection",
                      xcode[0])
        self.assertEqual(["-only-testing:p2pkit-sample-cancellation-probe-tests/SwiftFlowCancellationProbeTests/"
                          "testSwiftTaskCancellationFinishesActualDiagnosticCollection"],
                         [arg for arg in xcode[0].split() if arg.startswith("-only-testing:")])
        self.assertIn("-resultBundlePath " + str(external / "DerivedData/Logs/Test/swift-cancellation-probe.xcresult"),
                      xcode[0])
        self.assertIn("-scheme p2pkit-sample-cancellation-probe", xcode[0])
        self.assertIn("SWIFT_TREAT_WARNINGS_AS_ERRORS=YES", xcode[0])
        self.assertFalse(any(call.startswith("xcodegen ") for call in calls))
        self.assertFalse(self.lock.exists())
        self.assertTrue(external.is_dir())

    def test_owned_actions_select_exact_cases_without_bootstrap_and_retain_failed_output(self):
        shutil.rmtree(self.repo / "library")  # Any forbidden bootstrap now fails at its real boundary.
        selections = {
            "run-owned-flow-lifecycle": ("p2pkit-sample-ui", "swift-owned-flow-lifecycle", [
                "p2pkit-sample-tests/OwnedFlowCollectionTests",
                "p2pkit-sample-tests/SampleRunLifecycleTests",
                "p2pkit-sample-tests/IosLanDiagnosticsLeaseTests"]),
            "run-owned-cancellation": ("p2pkit-sample-cancellation-probe", "swift-owned-cancellation", [
                "p2pkit-sample-cancellation-probe-tests/SwiftOwnedFlowCancellationTests/"
                "testOwnedAdapterCancellationFinishesActualDiagnosticCollection"]),
        }
        for action, (scheme, bundle, selectors) in selections.items():
            for failure in (False, True):
                with self.subTest(action=action, failure=failure):
                    external = self.root / (action + ("-failure" if failure else "-success"))
                    before = (self.root / "tools.log").read_text().splitlines() if (self.root / "tools.log").exists() else []
                    self.finish(self.start("run-ios-ui-tests.sh", arguments=(action,), IOS_RUN_DIR=str(external),
                        P2PKIT_AUDIT_STATE_DIR=str(self.root / "audit-state"),
                        FAKE_IOS_BUILD_FAILURE="1" if failure else "0"), expected=42 if failure else 0)
                    calls = (self.root / "tools.log").read_text().splitlines()[len(before):]
                    xcode = [call for call in calls if call.startswith("xcodebuild ")]
                    self.assertEqual(1, len(xcode))
                    self.assertEqual(["-only-testing:" + name for name in selectors],
                                     [arg for arg in xcode[0].split() if arg.startswith("-only-testing:")])
                    for fragment in ("-scheme " + scheme, "-destination platform=iOS Simulator,id=" + UDID,
                                     "-resultBundlePath " + str(external / "DerivedData/Logs/Test" / (bundle + ".xcresult")),
                                     "-parallel-testing-enabled NO", "-maximum-concurrent-test-simulator-destinations 1",
                                     "SWIFT_TREAT_WARNINGS_AS_ERRORS=YES"):
                        self.assertIn(fragment, xcode[0])
                    self.assertNotIn("-test-iterations", xcode[0])
                    self.assertFalse(any(call.startswith("xcodegen ") for call in calls))
                    self.assertFalse(self.lock.exists())
                    self.assertTrue(external.is_dir(), "Borrowed result/evidence belongs to the outer finalizer")

    def test_focused_actions_require_audit_state_run_directory_and_exact_udid_before_tools(self):
        for action in ("run-cancellation-probe", "run-owned-flow-lifecycle", "run-owned-cancellation"):
            for missing in ("P2PKIT_AUDIT_STATE_DIR", "IOS_RUN_DIR", "SIM_UDID"):
                with self.subTest(action=action, missing=missing):
                    environment = {"P2PKIT_AUDIT_STATE_DIR": str(self.root / "audit-state"),
                                   "IOS_RUN_DIR": str(self.root / action), "SIM_UDID": UDID, missing: ""}
                    hook = self.root / "missing-state-hook"
                    hook.unlink(missing_ok=True)
                    self.finish(self.start("run-ios-ui-tests.sh", arguments=(action,), **environment), expected=2)
                    self.assertEqual(missing == ownership.STATE_ENV, hook.exists())
                    if hook.exists():
                        self.assertEqual("fired\n", hook.read_text())
                    self.assertFalse((self.root / "tools.log").exists())
                    self.assertFalse(self.build.exists())

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
