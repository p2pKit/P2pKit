#!/usr/bin/python3
"""Offline curator workspace tests with real GPG and disposable synthetic keys."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[2]
SOCKET_SUFFIX = "/p2pkit-gpg.XXXXXX/S.gpg-agent.browser"

# Only downloads/attestations are faked. The other wrappers observe and invoke
# real tools; no personal HOME, GPG keyring, Git configuration or network is used.
TOOL = r'''
import json, os, pathlib, signal, subprocess, sys, time
name = pathlib.Path(sys.argv[0]).name
args = sys.argv[1:]
event = {"tool": name, "args": args, "home": os.environ.get("GNUPGHOME")}
def record():
    with open(os.environ["TRACE"], "a", encoding="utf-8") as stream:
        stream.write(json.dumps(event) + "\n")
if name == "curl":
    destination = pathlib.Path(args[args.index("-o") + 1])
    url = next(value for value in args if value.startswith("https://"))
    event["destination"] = str(destination.resolve())
    event["workMode"] = destination.parent.stat().st_mode & 0o777
    record()
    if url.endswith("/sample-1.0.jar") and os.environ.get("BARRIER"):
        pathlib.Path(os.environ["BARRIER"] + ".ready").touch()
        deadline = time.monotonic() + 10
        while not pathlib.Path(os.environ["BARRIER"] + ".release").exists():
            if time.monotonic() >= deadline:
                sys.exit(92)
            time.sleep(0.01)
    relative = "signing-key.asc" if "keyserver.ubuntu.com/" in url or "keys.openpgp.org/" in url else url.rsplit("/", 1)[1]
    source = pathlib.Path(os.environ["REPOSITORY"]) / relative
    if not source.is_file():
        sys.exit(22)
    destination.write_bytes(source.read_bytes())
    sys.exit(0)
if name == "gh":
    record()
    sys.exit(91)  # Never use an authenticated CLI/network in these fixtures.
if name == "mktemp":
    kind = "work" if "p2pkit-dependency-review." in args[-1] else "gpg"
    if os.environ.get("FAIL_ALLOCATION") == kind:
        record()
        print("injected temporary-directory allocation failure", file=sys.stderr)
        sys.exit(72)
    result = subprocess.run([os.environ["REAL_MKTEMP"], *args], stdout=subprocess.PIPE)
    if result.returncode == 0:
        path = pathlib.Path(os.fsdecode(result.stdout).strip()).resolve()
        event.update(path=str(path), mode=path.stat().st_mode & 0o777)
    record()
    sys.stdout.buffer.write(result.stdout)
    sys.exit(result.returncode)
if name == "gpgconf":
    home = pathlib.Path(args[args.index("--homedir") + 1])
    event.update(home=str(home), homeExists=home.is_dir())
    record()
    if os.environ.get("FAIL_CLEANUP"):
        sys.exit(73)
else:
    record()
result = subprocess.run([os.environ["REAL_" + name.upper()], *args])
if name == "gpg" and "--import" in args and result.returncode == 0 and os.environ.get("SIGNAL_AFTER_IMPORT"):
    # Each curator is launched in its own session; do not signal the test runner.
    os.killpg(os.getpgrp(), getattr(signal, os.environ["SIGNAL_AFTER_IMPORT"]))
sys.exit(result.returncode)
'''


class TemporaryDirectoryTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.gpg = shutil.which("gpg")
        cls.gpgconf = shutil.which("gpgconf")
        if not cls.gpg or not cls.gpgconf:
            raise RuntimeError("these offline tests require GnuPG (gpg and gpgconf)")
        cls.short = Path(tempfile.mkdtemp(prefix="p2pg.", dir=os.environ.get("P2PKIT_GPG_TMPDIR") or "/tmp")).resolve()
        cls.addClassCleanup(shutil.rmtree, cls.short)
        cls.signer = cls.short / "signer"
        cls.signer.mkdir(mode=0o700)
        cls.addClassCleanup(cls.stop_home, cls.signer)
        environment = dict(os.environ, HOME=str(cls.short), GNUPGHOME=str(cls.signer))

        def gpg(*args, data=None):
            return subprocess.check_output([cls.gpg, "--no-options", "--homedir", str(cls.signer), "--batch",
                                            "--pinentry-mode", "loopback", "--passphrase", "", *args],
                                           input=data, env=environment, stderr=subprocess.PIPE, timeout=60)

        gpg("--quick-generate-key", "P2pKit Synthetic Test <fixture@p2pkit.invalid>", "ed25519", "sign", "0")
        cls.payload = b"synthetic artifact bytes, never executed\n"
        cls.public_key = gpg("--armor", "--export")
        cls.signature = gpg("--armor", "--detach-sign", data=cls.payload)
        cls.bad_signature = gpg("--armor", "--detach-sign", data=b"different synthetic bytes\n")

    @classmethod
    def stop_home(cls, home):
        # Test finalization must also work when a broken curator deleted its
        # sockets before stopping the daemon. Match only these newly allocated
        # synthetic homes; never use a blanket process-name kill.
        def owned_workers():
            aliases = {str(home), str(home.resolve())}
            result = set()
            listing = subprocess.check_output(["ps", "-axo", "pid=,command="], text=True)
            for line in listing.splitlines():
                fields = line.strip().split(None, 1)
                if len(fields) != 2:
                    continue
                pid, command = fields
                if Path(command.split()[0]).name not in ("gpg-agent", "keyboxd", "dirmngr"):
                    continue
                if any(f"--homedir {alias} " in command + " " for alias in aliases):
                    result.add(int(pid))
            return result

        try:
            if home.is_dir():
                subprocess.run([cls.gpgconf, "--homedir", str(home), "--kill", "all"],
                               check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=15)
        finally:
            for signum in (signal.SIGTERM, signal.SIGKILL):
                for pid in owned_workers():
                    try:
                        os.kill(pid, signum)
                    except ProcessLookupError:
                        pass
                deadline = time.monotonic() + 2
                while owned_workers() and time.monotonic() < deadline:
                    time.sleep(0.05)
            if owned_workers():
                raise RuntimeError("synthetic-home GPG workers survived test finalization")

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="p2pkit-review-paths.")
        self.addCleanup(self.temporary.cleanup)
        self.fixture = Path(self.temporary.name).resolve()
        self.key_parent = Path(tempfile.mkdtemp(prefix="k.", dir=self.short))
        self.addCleanup(shutil.rmtree, self.key_parent)
        self.ambient = self.key_parent / "ambient"
        self.ambient.mkdir(mode=0o700)
        self.addCleanup(self.stop_home, self.ambient)
        for directory in ("scripts", "gradle", "bin", "repository", "home"):
            (self.fixture / directory).mkdir()
        for name in ("review-dependency-verification.sh", "validate-gradle-plugin-marker.sh",
                     "validate-gradle-plugin-metadata.py", "resolve-gradle-variant-artifact.py"):
            shutil.copy2(ROOT / "scripts" / name, self.fixture / "scripts" / name)
        self.repository = self.fixture / "repository"
        (self.repository / "sample-1.0.jar").write_bytes(self.payload)
        (self.repository / "sample-1.0.jar.asc").write_bytes(self.signature)
        (self.repository / "signing-key.asc").write_bytes(self.public_key)
        self.trace = self.fixture / "trace.jsonl"
        self.trace.touch()
        self.workspace = self.fixture / ("large artifact volume " + "a" * 80)
        self.workspace.mkdir()
        (self.workspace / "preserve.txt").write_text("caller-owned sentinel\n")
        self.environment = dict(os.environ, HOME=str(self.fixture / "home"), GNUPGHOME=str(self.ambient),
                                GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull,
                                TMPDIR=str(self.workspace), P2PKIT_GPG_TMPDIR=str(self.key_parent),
                                P2PKIT_PYTHON3=sys.executable, TRACE=str(self.trace), REPOSITORY=str(self.repository),
                                REAL_MKTEMP=shutil.which("mktemp"), REAL_GPG=self.gpg, REAL_GPGCONF=self.gpgconf)
        for key in ("FAIL_ALLOCATION", "FAIL_CLEANUP", "SIGNAL_AFTER_IMPORT", "BARRIER"):
            self.environment.pop(key, None)
        for name in ("mktemp", "gpg", "gpgconf", "curl", "gh"):
            path = self.fixture / "bin" / name
            path.write_text(f"#!{sys.executable}\n" + TOOL)
            path.chmod(0o755)
        self.environment["PATH"] = str(self.fixture / "bin") + os.pathsep + os.environ["PATH"]
        self.metadata = self.fixture / "gradle/verification-metadata.xml"
        self.metadata.write_text("<verification-metadata>\n<components>\n</components>\n</verification-metadata>\n")
        (self.fixture / "gradle/plugin-provenance-policy.txt").write_text("# No unsigned exceptions\n")
        self.git("init", "-q")
        for key, value in (("user.name", "P2pKit Test"), ("user.email", "test@p2pkit.invalid"),
                           ("commit.gpgsign", "false"), ("core.hooksPath", os.devnull)):
            self.git("config", key, value)
        self.git("add", "gradle")
        self.git("commit", "-qm", "synthetic baseline")
        self.base = self.git("rev-parse", "HEAD").strip()
        sha = hashlib.sha256(self.payload).hexdigest()
        self.metadata.write_text(self.metadata.read_text().replace("</components>", f'''<component group="example" name="sample" version="1.0">
<artifact name="sample-1.0.jar">
<sha256 value="{sha}"/>
</artifact>
</component>
</components>'''))
        self.addCleanup(self.cleanup_created_homes)

    def git(self, *args):
        return subprocess.check_output(["git", "-C", str(self.fixture), *args], env=self.environment, text=True)

    def events(self):
        return [json.loads(line) for line in self.trace.read_text().splitlines()]

    def cleanup_created_homes(self):
        # A deliberately failed production shutdown retains the directory so a
        # real retry can still reach its sockets. Always perform that retry here.
        created = {Path(event["path"]) for event in self.events() if event["tool"] == "mktemp" and "path" in event}
        homes = {path for path in created if path.name.startswith("p2pkit-gpg.")}
        for event in self.events():
            if event["tool"] == "gpg" and event["home"]:
                home = Path(event["home"]).resolve()
                if any(home == path or path in home.parents for path in created):
                    homes.add(home)
        for home in homes:
            self.stop_home(home)
        for path in created:
            if path.is_dir():
                shutil.rmtree(path)

    def start(self, environment=None):
        process = subprocess.Popen([str(self.fixture / "scripts/review-dependency-verification.sh"), self.base],
                                   cwd=self.fixture, env=environment or self.environment, stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT, text=True, start_new_session=True)
        self.addCleanup(self.stop_process, process)
        return process

    @staticmethod
    def stop_process(process):
        if process.poll() is None:
            os.killpg(process.pid, signal.SIGTERM)
            try:
                process.communicate(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.communicate(timeout=10)

    def curate(self, error=None):
        process = self.start()
        output, _ = process.communicate(timeout=45)
        if error is None:
            self.assertEqual(process.returncode, 0, output)
            self.assertIn("RESULT: PASS — reviewed 1 newly admitted artifacts", output)
        else:
            self.assertNotEqual(process.returncode, 0, output)
            self.assertIn(error, output)
        return process.returncode

    def assert_clean(self):
        imported_homes = {event["home"] for event in self.events()
                          if event["tool"] == "gpg" and "--import" in event["args"]}
        stopped_homes = {event["home"] for event in self.events() if event["tool"] == "gpgconf"}
        self.assertTrue(imported_homes <= stopped_homes, "every importing keyring needs owned-worker shutdown")
        for event in self.events():
            if event["tool"] == "mktemp" and "path" in event:
                self.assertEqual(event["mode"], 0o700)
                self.assertFalse(Path(event["path"]).exists(), event)
            if event["tool"] == "gpgconf":
                self.assertTrue(event["homeExists"], "workers must stop before removing their socket directory")
                self.assertEqual(event["args"], ["--homedir", event["home"], "--kill", "all"])
                self.assertNotEqual(event["home"], str(self.ambient))
        self.assertEqual((self.workspace / "preserve.txt").read_text(), "caller-owned sentinel\n")

    def test_ambient_gpg_configuration_is_ignored_and_untouched(self):
        config = self.ambient / "gpg.conf"
        # Unittest cleanups run last-in-first-out: remove the synthetic poison
        # before the existing fixture-owned ambient-home shutdown, even on failure.
        self.addCleanup(config.unlink, missing_ok=True)
        contents = b"p2pkit-probe-invalid-option\n"
        config.write_bytes(contents)

        self.curate()
        events = self.events()
        homes = {event["path"] for event in events
                 if event["tool"] == "mktemp" and "path" in event
                 and Path(event["path"]).name.startswith("p2pkit-gpg.")}
        self.assertEqual(len(homes), 1)
        calls = [event for event in events if event["tool"] == "gpg"]
        self.assertEqual({event["home"] for event in calls}, homes)
        for operation in ("--list-packets", "--list-keys", "--show-keys", "--import", "--verify"):
            self.assertTrue(any(operation in event["args"] for event in calls), operation)
        self.assertEqual(list(self.ambient.iterdir()), [config])
        self.assertEqual(config.read_bytes(), contents)
        self.assert_clean()

    def test_long_artifact_volume_and_default_short_keyring(self):
        del self.environment["P2PKIT_GPG_TMPDIR"]
        self.curate()
        for event in self.events():
            if event["tool"] == "curl":
                self.assertEqual(Path(event["destination"]).parent.parent, self.workspace)
                self.assertEqual(event["workMode"], 0o700)
            if event["tool"] == "gpgconf":
                self.assertEqual(Path(event["home"]).parent, Path("/tmp").resolve())
        self.assert_clean()

    def test_explicit_keyring_root_with_spaces_and_repeated_runs(self):
        selected = self.key_parent / "short kéys"
        selected.mkdir()
        self.environment["P2PKIT_GPG_TMPDIR"] = str(selected) + "/"
        self.curate()
        self.curate()
        homes = [event["home"] for event in self.events() if event["tool"] == "gpgconf"]
        self.assertEqual(len(set(homes)), 2)
        self.assertTrue(all(Path(home).parent == selected for home in homes))
        self.assert_clean()

    def test_relative_workspace_and_trailing_slash(self):
        (self.fixture / "relative space").mkdir()
        self.environment["TMPDIR"] = "relative space/"
        self.curate()
        for event in self.events():
            if event["tool"] == "curl":
                self.assertEqual(Path(event["destination"]).parent.parent, self.fixture / "relative space")
        self.assert_clean()

    def test_unavailable_workspace_does_not_fall_back(self):
        # Even an empty review must not silently replace the operator's volume.
        # The same case rejects the old hardcoded-/tmp implementation before GPG.
        self.metadata.write_text(self.git("show", f"{self.base}:gradle/verification-metadata.xml"))
        self.environment["TMPDIR"] = str(self.fixture / "absent")
        self.curate("mktemp")
        self.assertFalse(any(event["tool"] == "curl" or "path" in event for event in self.events()))
        self.assert_clean()

    def test_unavailable_gpg_root_cleans_workspace(self):
        self.environment["P2PKIT_GPG_TMPDIR"] = str(self.key_parent / "absent")
        self.curate("mktemp")
        self.assertEqual(len([event for event in self.events() if "path" in event]), 1)
        self.assert_clean()

    def test_second_allocation_failure_cleans_first(self):
        self.environment["FAIL_ALLOCATION"] = "gpg"
        self.assertEqual(self.curate("injected temporary-directory allocation failure"), 72)
        self.assertEqual(len([event for event in self.events() if "path" in event]), 1)
        self.assert_clean()

    def socket_root(self, socket_bytes):
        length = socket_bytes - len(os.fsencode(str(self.key_parent))) - 1 - len(SOCKET_SUFFIX)
        self.assertGreater(length, 0)
        path = self.key_parent / ("s" * length)
        path.mkdir()
        return path

    def test_exact_portable_socket_boundary_with_real_gpg(self):
        self.environment["P2PKIT_GPG_TMPDIR"] = str(self.socket_root(102))
        self.curate()
        self.assert_clean()

    def test_overlong_socket_is_rejected_before_downloads(self):
        for length in (103, 104):
            with self.subTest(socket_bytes=length):
                self.environment["P2PKIT_GPG_TMPDIR"] = str(self.socket_root(length))
                self.curate("GPG socket path is too long")
        self.assertFalse(any(event["tool"] in ("curl", "gpg", "gpgconf") for event in self.events()))
        self.assert_clean()

    def test_socket_limit_uses_physical_path_and_byte_length(self):
        long_root = self.socket_root(103)
        alias = self.key_parent / "alias"
        alias.symlink_to(long_root, target_is_directory=True)
        self.environment["P2PKIT_GPG_TMPDIR"] = str(alias)
        self.curate("GPG socket path is too long")
        self.assertTrue(alias.is_symlink())
        available = 103 - len(os.fsencode(str(self.key_parent))) - 1 - len(SOCKET_SUFFIX)
        unicode_root = self.key_parent / ("é" * (available // 2 + 1))
        unicode_root.mkdir()
        candidate = str(unicode_root) + SOCKET_SUFFIX
        self.assertLess(len(candidate), 103)
        self.assertGreaterEqual(len(os.fsencode(candidate)), 103)
        self.environment["P2PKIT_GPG_TMPDIR"] = str(unicode_root)
        self.curate("GPG socket path is too long")
        self.assert_clean()

    def test_checksum_failure_removes_both_directories(self):
        (self.repository / "sample-1.0.jar").write_bytes(b"incorrect bytes")
        self.curate("downloaded bytes disagree with metadata")
        self.assert_clean()

    def test_signature_failure_removes_both_directories(self):
        (self.repository / "sample-1.0.jar.asc").write_bytes(self.bad_signature)
        self.curate("invalid detached signature")
        self.assert_clean()

    def test_signals_after_import_stop_workers_and_clean_both_directories(self):
        for name, code in (("SIGHUP", 129), ("SIGINT", 130), ("SIGTERM", 143)):
            with self.subTest(signal=name):
                self.environment["SIGNAL_AFTER_IMPORT"] = name
                self.assertEqual(self.curate(""), code)
        self.assert_clean()

    def test_shutdown_failure_is_not_success_and_keeps_retry_path(self):
        selected = self.key_parent / "retry ' keys"
        selected.mkdir()
        self.environment["P2PKIT_GPG_TMPDIR"] = str(selected)
        self.environment["FAIL_CLEANUP"] = "1"
        self.curate("could not stop review GPG workers; retry")
        homes = [Path(event["home"]) for event in self.events() if event["tool"] == "gpgconf"]
        self.assertEqual(len(homes), 1)
        self.assertTrue(homes[0].is_dir())
        self.assertFalse(list(self.workspace.glob("p2pkit-dependency-review.*")))
        self.cleanup_created_homes()
        self.assert_clean()

    def test_concurrent_reviews_have_independent_workspaces_and_keyrings(self):
        barriers = [self.fixture / str(index) for index in range(2)]
        processes = [self.start(dict(self.environment, BARRIER=str(barrier))) for barrier in barriers]
        deadline = time.monotonic() + 10
        while not all(Path(str(barrier) + ".ready").exists() for barrier in barriers):
            self.assertLess(time.monotonic(), deadline, "both downloads must reach the controlled barrier")
            self.assertTrue(all(process.poll() is None for process in processes))
            time.sleep(0.01)
        for barrier in barriers:
            Path(str(barrier) + ".release").touch()
        for process in processes:
            output, _ = process.communicate(timeout=45)
            self.assertEqual(process.returncode, 0, output)
        paths = [event["path"] for event in self.events() if event["tool"] == "mktemp" and "path" in event]
        self.assertEqual(len(paths), 4)
        self.assertEqual(len(set(paths)), 4)
        self.assert_clean()


if __name__ == "__main__":
    unittest.main()
