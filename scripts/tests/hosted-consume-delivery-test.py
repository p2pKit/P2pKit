#!/usr/bin/env python3
"""Connected consume/delivery regression models; never hosted or native proof.

Only tiny, explicitly synthetic filesystem fixtures are created. No application,
Gradle, emulator, GPG, HTTP, socket or native process owner may execute. Original
budget arithmetic, private file accounting, snapshot hashes and delivery guards
run normally; native admission/service/Windows handles are modeled explicitly.
"""
from __future__ import annotations

from contextlib import ExitStack, redirect_stdout
from dataclasses import replace
import copy
import ctypes
import hashlib
import importlib.util
import io
import os
from pathlib import Path
import socket
import stat
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


M = module("connected_controller_fixtures", ROOT / "scripts/tests/hosted-test-controller-test.py")
D = module("connected_desktop_budget_fixtures", ROOT / "scripts/tests/hosted-desktop-job-budget-test.py")
P = module("connected_sample_packager", ROOT / "scripts/package-sample-apps.py")
C, J = M.C, M.C.job_time


S, K = C.seed, C.cache
Owner, Controller = C.PrivateOwner, C.Controller
NS = J.NS


def forbid_external_operations(stack):
    """Fixture-local prohibitions; no global monkeypatch survives a test."""
    for target, names in ((subprocess, ("Popen", "run", "call", "check_call", "check_output")),
                          (socket, ("socket", "create_connection", "getaddrinfo")),
                          (ctypes, ("CDLL", "PyDLL", "WinDLL", "OleDLL")),
                          (os, ("fork", "forkpty", "posix_spawn", "posix_spawnp", "system", "popen"))):
        for name in names:
            if hasattr(target, name):
                stack.enter_context(patch.object(target, name,
                    side_effect=AssertionError("OFFLINE_TEST_FORBIDS_NATIVE_PROCESS_OR_NETWORK:" + name)))


class ConnectedBase(M.Base):
    def setUp(self):
        super().setUp()
        forbid_external_operations(self.stack)
        self.role = "linux-x64"
        self.exact_clock = D.clock(self.role)
        self.admitted = D.admission(self.role, package_samples=True)
        self.budget = J.derive(self.admitted, D.originals(self.admitted, self.exact_clock),
                              D.F.provenance(), clock=self.exact_clock)
        self.stack.enter_context(patch.object(C.processes, "host_role", side_effect=lambda: self.role))
        self.stack.enter_context(patch.object(D.C, "observe", side_effect=lambda:
            D.C.Reading(self.exact_clock, self.clock.raw())))
        self.clock.set_raw(10020 * J.NS)
        self.output = self.path / "outputs"
        self.output.write_bytes(b"")
        os.environ["GITHUB_OUTPUT"] = str(self.output)

    def write(self, path, value):
        missing, parent = [], path.parent
        while not parent.exists():
            missing.append(parent)
            parent = parent.parent
        for directory in reversed(missing):
            directory.mkdir(mode=0o700)
        raw = value if isinstance(value, bytes) else C.encoded(value)
        path.write_bytes(raw)
        path.chmod(0o600)
        return raw

    def sample_fixture(self, role=None, version="0.7.0-SNAPSHOT"):
        role = role or self.role
        admitted = D.admission(role, package_samples=True)
        original = C.parse(admitted.record)
        github = original["github"]
        platform = "linux" if role == "linux-x64" else "windows" if role == "windows-x64" else "macos"
        arch = "arm64" if role == "macos-arm64" else "x64"
        # These are supplied schema3 inspection records, not actual packages or
        # results of APK/MSI/DMG/DEB inspection. No native inspector is called.
        self.write(self.root / "gradle.properties", ("VERSION_NAME=" + version + "\n").encode("ascii"))
        versions = P.IDENTITY.VERSION.version_fields(version)
        embedded = P.IDENTITY.VERSION.embedded_identity(version, original["source"]["commit"])
        current = {"repository": C.identity.REPOSITORY, **original["source"], "run_id": github["runId"],
            "run_attempt": github["runAttempt"], "event_name": github["event"], "ref": github["ref"],
            "workflow_ref": C.identity.REPOSITORY + "/" + github["workflow"] + "@" + github["ref"],
            "workflow_sha": github["workflowSha"], "job": github["job"], "platform": platform,
            "architecture": arch, "canonicalVersion": version, "osRelease": "SYNTHETIC", "python": "SYNTHETIC",
            "translation": "NATIVE_0" if platform == "macos" else "NOT_APPLICABLE"}
        output = self.runner_temp / "p2pkit-sample-apps"
        output.mkdir(mode=0o700)
        self.write(output / ".prepare.json", {"schema": 1, "context": current, "root": str(self.root),
            "outputIdentity": P.signature(output)[:2], "generatedRoots": P.generated_roots(current)})
        self.write(output / ".complete.json", {"schema": 1, "context": current, "scope": P.SCOPE})
        for name, relative in P.LICENSES.items():
            self.write(self.root / relative, ("SYNTHETIC LICENSE " + name + "\n").encode())
        label = platform + "-" + arch + "-" + current["commit"][:12]
        suffix = ".zip" if platform == "windows" else ".tar.gz"
        extension = {"linux": "deb", "macos": "dmg", "windows": "msi"}[platform]
        desktop = output / "desktop"
        desktop.mkdir(mode=0o700)
        native = {"reader": {"linux": "dpkg-deb control + data-only tar",
                             "windows": "MsiOpenDatabaseW/READONLY + embedded cabinet",
                             "macos": "hdiutil read-only / Info.plist"}[platform],
                  "fields": {"linux": {"Package": "p2pkit-sample", "Version": versions["debianVersion"], "Architecture": "amd64"},
                             "windows": {"ProductName": "P2pKit Sample", "ProductVersion": versions["nativeVersion"],
                                         "Template": "x64;1033", "WordCount": 2},
                             "macos": {"CFBundleShortVersionString": versions["nativeVersion"],
                                       "CFBundleVersion": versions["nativeVersion"]}}[platform],
                  "embeddedIdentity": embedded}
        artifacts = []
        for name in ("desktop-ui-" + label + suffix, "desktop-cli-" + label + suffix,
                     "desktop-installer-" + label + "." + extension):
            self.write(desktop / name, b"SYNTHETIC; NOT AN APPLICATION OR INSTALLER\n")
            row = {"file": name, **P.file_hash(desktop / name)}
            if name.startswith("desktop-installer-"):
                row["nativeMetadata"] = native
            else:
                row["entries"] = [{"path": "", "mode": 0o755, "type": "directory"},
                    {"path": "synthetic.txt", "mode": 0o644, "type": "file",
                     "bytes": row["bytes"], "sha256": row["sha256"]}]
            artifacts.append(row)
        layout = {"launcher": [arch], "runtimeVm": [arch], "runtimeJava": [arch], "javaVersion": "SYNTHETIC-JAVA",
                  "releaseArchitecture": "aarch64" if arch == "arm64" else "amd64", "embeddedIdentity": embedded,
                  "jarCount": 1, "cliRequiresExternalJava": "17+", "layoutOnlyNotRuntimeExecution": True}
        P.finish_manifest(self.root, desktop, current, {"artifacts": artifacts, "layoutInspection": layout,
            "installerInspection": "Native version metadata and byte hashes; not installed or signature-verified"})
        if platform == "linux":
            android = output / "android"
            android.mkdir(mode=0o700)
            self.write(android / "sample-debug.apk", b"SYNTHETIC; NOT AN APK\n")
            binary = {"applicationId": "dev.p2pkit.sample.android", "versionCode": versions["androidVersionCode"],
                      "versionName": version}
            agp = {**binary, "variant": "debug"}
            raw_metadata = C.encoded({"SYNTHETIC_AGP_INSPECTION_INPUT": agp})
            P.finish_manifest(self.root, android, current, {
                "artifact": {"file": "sample-debug.apk", **P.file_hash(android / "sample-debug.apk")},
                "agpMetadata": agp, "apkInspection": {"binaryManifest": binary, "embeddedIdentity": embedded,
                                                      "signerIdentity": "NOT_VERIFIED"},
                "metadataFile": {"bytes": len(raw_metadata), "sha256": C.digest(raw_metadata)}})
        return output, admitted

    def snapshot(self, admitted=None):
        return C.sample_snapshot(self.owner(), C.session_path("desktop", self.role),
                                 admitted or self.admitted, self.role, 1000., lambda: None)

    def delivery_fixture(self, *, package_samples=True):
        """Synthetic already-sealed producer; not a substitute for seal tests.

        Retained admission/service results are explicit inputs. All downstream
        guard reads, originals/copies/hashes, clocks and outcome predicates run.
        """
        if package_samples:
            self.sample_output, self.admitted = self.sample_fixture()
        else:
            self.sample_output, self.admitted = None, D.admission(self.role, package_samples=False)
        self.budget = J.derive(self.admitted, D.originals(self.admitted, self.exact_clock),
                              D.F.provenance(), clock=self.exact_clock)
        owner = self.owner()
        private = owner.new(C.session_path("desktop", self.role))
        evidence = owner.child(private, "evidence", 1000., create=True)
        source = C.parse(self.admitted.record)["source"]
        context = {"schema": 1, "profile": "desktop", "role": self.role, "source": source,
            "root": str(self.root), "session": str(private.path), "canonicalSources": C.canonical_bindings(),
            "admissionSha256": C.digest(self.admitted.record), "jobBudgetSha256": self.budget.sha256,
            "samplePackagingRequired": package_samples, "dependencyCache": {"scope": "SYNTHETIC_ALREADY_ADMITTED_CACHE"}}
        context["kind"], context["command"] = C.profile_command("desktop", self.role, package_samples=package_samples)
        context_raw = self.write(private.path / "run-context.json", context)
        original_admission = evidence.path / "admission"
        for name, raw in (("admission.json", self.admitted.record), ("original-event.json", self.admitted.original_event),
                          ("original-policy.json", self.admitted.original_policy), ("recipient-public.asc", self.admitted.public_key)):
            self.write(original_admission / name, raw)
        phases = [{"phase": label, "exitCode": 0, "launchAttempted": True, "scopeAttempted": True,
                   "retirement": "KNOWN", "errors": [], "survivors": [], "ownership": {"discoveryErrors": []},
                   "jobBudgetSha256": self.budget.sha256, "completedRawNs": 10001 * J.NS} for label in C.DESKTOP_ORDER
                  if package_samples or label != "sample-packaging"]
        hashes = {row["phase"]: C.digest(C.encoded(row)) for row in phases}
        result = {"schema": 1, "scope": "ORDINARY_PROFILE_CUSTODY_ONLY", "profile": "desktop", "role": self.role,
            "source": source, "contextSha256": C.digest(context_raw), "retirement": "KNOWN", "encrypted": True,
            "readyForPostReturnSeal": True, "productAttempted": True, "cancelled": False, "errors": [],
            "phases": phases, "phaseSha256": hashes,
            "custody": {"result": "RETAINED", "retirement": "KNOWN", "errors": [],
                        "productExitCode": 0, "stopExitCode": 0, "ownerFinalExitCode": 0},
            "jobBudget": {"sha256": self.budget.sha256, "productiveCutoffRawNs": self.budget.fence("productive"),
                          "terminalRawNs": 10010 * J.NS, "exhausted": False, "cutoffObservation": None,
                          "cooperativeCancellation": None}}
        report = None
        result["exportReturn"] = {"result": {}}
        if package_samples:
            packaged = next(row for row in phases if row["phase"] == "sample-packaging")
            report = {"schema": 1, "scope": "ORIGINAL_PACKAGED_SAMPLES", "source": source,
                "contextSha256": C.digest(context_raw), "role": self.role, "phaseSha256": hashes["sample-packaging"],
                "snapshot": self.snapshot(self.admitted)}
            report_raw = self.write(evidence.path / "sample-packaging.json", report)
            result["samplePackaging"] = {"required": True, "status": "PASS", "manifestSha256": C.digest(report_raw)}
            before = copy.deepcopy(result)
            before.update(encrypted=False, phases=phases[:-1], phaseSha256={k: v for k, v in hashes.items() if k != "export"})
            self.write(evidence.path / "profile-result-before-export.json", before)
            for name, raw in (("start.json", C.encoded(packaged)), ("result.json", C.encoded(packaged)),
                              ("baseline.json", C.encoded({"scope": "SYNTHETIC"})),
                              ("stdout.log", b"SYNTHETIC PACKAGING LOG\n"), ("stderr.log", b"")):
                self.write(evidence.path / "commands/sample-packaging" / name, raw)
            C.copy_tree(owner, evidence, private.path / "frozen-evidence", 1000.)
            frozen = C.frozen_package_packet(owner, private, 1000., lambda: None)
            result["exportReturn"] = {"result": {"samplePackagingFrozen": frozen}}
        result["profilePassed"] = C.profile_passed(result)
        self.assertTrue(result["profilePassed"])
        result_raw = self.write(private.path / "controller-result.json", result)
        ciphertext = b"SYNTHETIC; NOT ENCRYPTED EVIDENCE\n"
        manifest = {"artifact": {"name": C.posix.ARTIFACT, "size": len(ciphertext), "sha256": C.digest(ciphertext)}}
        self.write(private.path / "export" / C.posix.ARTIFACT, ciphertext)
        manifest_raw = self.write(private.path / "export" / C.posix.MANIFEST, manifest)
        fence = C.desktop_delivery_end(self.budget, result)
        seal = {"jobBudgetSha256": self.budget.sha256, "clockDomain": self.budget.value["clockDomain"],
            "controllerResultSha256": C.digest(result_raw), "source": source, "profilePassed": True,
            "retirement": "KNOWN", "sealedAtRawNs": 10011 * J.NS, "deliveryEndRawNs": fence,
            "upload": {"seconds": J.UPLOAD_SECONDS, "latestStartRawNs": self.budget.fence("upload-start"), "endRawNs": fence},
            "manifestSha256": C.digest(manifest_raw), "artifact": manifest["artifact"]}
        self.write(private.path / "post-return-validation/seal.json", seal)
        self.stack.enter_context(patch.object(C, "load_job_budget", return_value=self.budget))
        def admitted(_owner, profile, _path, check, expected=None):
            self.assertEqual(profile, "desktop")
            self.assertEqual(expected, self.admitted)
            check()
            return expected
        self.stack.enter_context(patch.object(C, "admission", side_effect=admitted))
        original_owner = C.PrivateOwner
        def new_owner():
            value = original_owner()
            self.owners.append(value)
            return value
        self.stack.enter_context(patch.object(C, "PrivateOwner", side_effect=new_owner))
        self.original_owner = original_owner
        self.session, self.context, self.result, self.report = private.path, context, result, report
        for name in ("RUN", "SEAL", "UPLOAD", "UPLOAD_AFTER"):
            os.environ["P2PKIT_HOSTED_TEST_" + name + "_OUTCOME"] = "success"
        return private.path

    def guard(self, function, *args):
        begin = len(self.output.read_bytes())
        with redirect_stdout(io.StringIO()): function(*args)
        return dict(line.split("=", 1) for line in self.output.read_text()[begin:].splitlines())

    def evidence_uploaded(self):
        values = self.guard(C.upload_guard, "before", "desktop")
        os.environ["P2PKIT_HOSTED_TEST_UPLOAD_GUARD_SHA256"] = values["upload_guard_sha256"]
        self.clock.now += 2
        self.assertEqual(self.guard(C.upload_guard, "after", "desktop"), {"upload_complete": "true"})

    def package_ready(self):
        self.evidence_uploaded()
        values = self.guard(C.package_samples_guard, "desktop")
        os.environ.update(P2PKIT_SAMPLE_PACKAGE_OUTCOME="success", P2PKIT_SAMPLE_PACKAGE_SHA256=values["packaging_sha256"])

    def sample_uploaded(self, platform):
        before = self.guard(C.sample_upload_guard, "before", platform, "desktop")
        os.environ.update(P2PKIT_SAMPLE_UPLOAD_OUTCOME="success", P2PKIT_SAMPLE_UPLOAD_GUARD_SHA256=before["upload_guard_sha256"])
        self.clock.now += 2
        self.assertEqual(self.guard(C.sample_upload_guard, "after", platform, "desktop"), {"upload_complete": "true"})
        for name in ("BEFORE", "UPLOAD", "AFTER"):
            os.environ["P2PKIT_SAMPLE_" + platform.upper() + "_" + name + "_OUTCOME"] = "success"


class SnapshotModels(ConnectedBase):
    def test_posix_sample_roster_matches_actual_packager_manifest_and_checksums(self):
        output, admitted = self.sample_fixture()
        result = self.snapshot(admitted)
        self.assertEqual(result["path"], str(output))
        self.assertEqual(set(result["directories"]), {"", "desktop", "desktop/licenses", "android", "android/licenses"})
        self.assertEqual(len(result["files"]), 16)
        for name, row in result["files"].items():
            self.assertEqual((row["size"], row["sha256"]), (len((output / name).read_bytes()), C.digest((output / name).read_bytes())))

    def test_source_roster_checksum_and_byte_mutations_are_not_accepted(self):
        output, admitted = self.sample_fixture()
        good = self.snapshot(admitted)
        self.assertTrue(good["files"])
        paths = (output / ".complete.json", output / "desktop/manifest.json", output / "android/checksums.sha256")
        for path in paths:
            old = path.read_bytes()
            try:
                if path.suffix == ".json":
                    value = C.parse(old)
                    (value["context"] if "context" in value else value["sourceAndRun"])["commit"] = "f" * 40
                    self.write(path, value)
                else:
                    self.write(path, old.replace(b"  ", b" ", 1))
                with self.subTest(path=path.name), self.assertRaises(C.ControllerError):
                    self.snapshot(admitted)
            finally:
                self.write(path, old)
        extra = output / "desktop/not-a-sample"
        self.write(extra, b"not admitted")
        with self.assertRaisesRegex(C.ControllerError, "SAMPLE_ARTIFACT_ROSTER"):
            self.snapshot(admitted)

    def test_windows_native_file_ids_are_not_python_stat_inode_ids(self):
        self.role = "windows-x64"
        output, admitted = self.sample_fixture(self.role)
        owner = self.owner()

        class NativeReader:
            def __init__(reader, path):
                reader.stream = path.open("rb")
                info = path.stat()
                reader.initial_info = SimpleNamespace(size=info.st_size, identity=(700, format(info.st_ino, "032x")))
            def read(reader, count): return reader.stream.read(count)
            def verify(reader): return reader.initial_info
            def close(reader): reader.stream.close()

        class NativeDirectory:
            # Exact FileInfo.identity shape; native APIs are NOT executed.
            def __init__(directory, path):
                directory.path = path
                directory.identity = (700, format(path.stat().st_ino, "032x"))
            def verify(directory): return SimpleNamespace(identity=directory.identity)
            def names(directory, **_): return tuple(path.name for path in directory.path.iterdir())
            def open_file(directory, name, **_): return NativeReader(directory.path / name)
            def open_directory(directory, name, **_): return NativeDirectory(directory.path / name)
            def close(directory): pass

        # Patch only this module's platform branch, not pathlib or actual os.
        proxy = SimpleNamespace(**{name: getattr(os, name) for name in dir(os)})
        proxy.name = "nt"
        with patch.object(C, "os", proxy), patch.object(C.seed, "public_root", side_effect=NativeDirectory):
            result = C.sample_snapshot(owner, C.session_path("desktop", self.role), admitted, self.role, 1000., lambda: None)
        self.assertEqual(result["directories"][""], [700, format(output.stat().st_ino, "032x")])
        self.assertNotEqual(result["directories"][""], P.signature(output)[:2])

    def test_posix_fifo_swap_requires_nonblocking_acquisition_and_retires_leaf(self):
        output, _ = self.sample_fixture()
        owner = self.owner()
        directory = owner.acquire("fixture-public-root", lambda: C.seed.public_root(output))
        original_open = os.open
        descriptors = []
        swapped = []

        def opening(path, flags, *args, **kwargs):
            if str(path) == ".complete.json" and "dir_fd" in kwargs:
                self.assertTrue(flags & os.O_NONBLOCK, "sample acquisition may block on a swapped FIFO")
                (output / ".complete.json").unlink()
                os.mkfifo(output / ".complete.json", 0o600)
                swapped.append(True)
                fd = original_open(path, flags, *args, **kwargs)
                descriptors.append(fd)
                return fd
            return original_open(path, flags, *args, **kwargs)

        with patch.object(os, "open", side_effect=opening), self.assertRaises(C.ControllerError):
            C.sample_file(owner, directory, ".complete.json", 1000., lambda: None, metadata=True)
        self.assertEqual(swapped, [True])
        for fd in descriptors:
            with self.assertRaises(OSError): os.fstat(fd)

    def test_fdopen_failure_closes_the_acquired_leaf_once(self):
        output, _ = self.sample_fixture()
        owner = self.owner()
        directory = owner.acquire("fixture-public-root", lambda: C.seed.public_root(output))
        snapshot = C.posix_snapshot(owner, output, C.seed.TOTAL_LIMIT, 64, 1000.)
        original_open, original_close = os.open, os.close
        acquired, closed = [], []
        def opening(*args, **kwargs):
            fd = original_open(*args, **kwargs)
            acquired.append(fd)
            return fd
        def closing(fd):
            closed.append(fd)
            original_close(fd)
        with patch.object(os, "open", side_effect=opening), patch.object(os, "close", side_effect=closing), \
                patch.object(os, "fdopen", side_effect=RuntimeError("ORIGINAL_FDOPEN_FAILURE")), \
                self.assertRaisesRegex(RuntimeError, "ORIGINAL_FDOPEN_FAILURE"):
            C.sample_posix_reader(directory, ".complete.json", snapshot, 1000.)
        self.assertEqual(closed, acquired)
        self.assertEqual(len(acquired), 1)


class Schema3SnapshotModels(ConnectedBase):
    """New source-only controls; first execution requires independent review.

    These tiny POSIX files carry explicitly supplied schema3/native-inspection
    records. Role labels do not turn the files into native packages, a Windows
    filesystem, actual hosted identity or executed inspection. No old suite or
    accepted1066 reader is called by this class.
    """

    def fixture(self, role="linux-x64", version="0.7.0-SNAPSHOT"):
        self.role = role
        output, self.admitted = self.sample_fixture(role, version)
        return output, self.admitted

    def manifest(self, output, kind):
        return C.parse((output / kind / "manifest.json").read_bytes())

    def rewrite_manifest(self, output, kind, value):
        directory = output / kind
        self.write(directory / "manifest.json", value)
        paths = sorted(path for path in directory.rglob("*")
                       if path.is_file() and path != directory / "checksums.sha256")
        self.write(directory / "checksums.sha256", "".join(
            C.digest(path.read_bytes()) + "  " + path.relative_to(directory).as_posix() + "\n"
            for path in paths).encode("ascii"))

    def refused(self, output, kind, change, reason):
        before = self.manifest(output, kind)
        changed = copy.deepcopy(before)
        change(changed)
        try:
            # Recompute the public checksums: the semantic guard, not a stale
            # checksum, must reject this otherwise coherent modified record.
            self.rewrite_manifest(output, kind, changed)
            with self.assertRaisesRegex(C.ControllerError, reason):
                self.snapshot()
        finally:
            self.rewrite_manifest(output, kind, before)

    def installer(self, manifest):
        return next(row for row in manifest["artifacts"] if row["file"].startswith("desktop-installer-"))

    def accepted(self, role, version="0.7.0-SNAPSHOT"):
        output, admitted = self.fixture(role, version)
        result = self.snapshot(admitted)
        self.assertEqual(result["versionBinding"], P.IDENTITY.VERSION.version_fields(version))
        self.assertEqual(result["versionSourceSha256"], C.digest((self.root / "gradle.properties").read_bytes()))
        self.assertEqual(set(result["directories"]), {"", "desktop", "desktop/licenses"} |
                         ({"android", "android/licenses"} if role == "linux-x64" else set()))
        self.assertEqual(len(result["files"]), 16 if role == "linux-x64" else 10)
        self.assertNotIn("gradle.properties", result["files"])
        self.assertEqual(self.output.read_bytes(), b"")
        return output, result

    def test_linux_schema3_binds_source_and_both_platform_records(self):
        self.accepted("linux-x64")

    def test_windows_inspection_record_uses_exact_native_version(self):
        self.accepted("windows-x64", "0.8.0-rc1")

    def test_arm64_macos_inspection_record_binds_embedded_identity(self):
        self.accepted("macos-arm64", "0.8.0-beta2")

    def test_intel_macos_inspection_record_keeps_exact_role(self):
        self.accepted("macos-x64", "0.8.0")

    def test_optional_runtime_java_and_release_architecture_preserve_producer_contract(self):
        output, admitted = self.fixture("macos-arm64")
        value = self.manifest(output, "desktop")
        for release_arch in (None, ""):
            with self.subTest(releaseArchitecture=release_arch):
                value["layoutInspection"].update(launcher=["arm64", "x64"], runtimeVm=["arm64", "x64"],
                                                 runtimeJava=None, releaseArchitecture=release_arch)
                self.rewrite_manifest(output, "desktop", value)
                self.assertEqual(self.snapshot(admitted)["versionBinding"], value["versionBinding"])

    def test_source_properties_are_bounded_reread_and_closed_without_new_time(self):
        _output, admitted = self.fixture()
        calls = []
        original = C.seed._small_read
        def reading(owners, directory, name, end, maximum, check):
            calls.append((directory, directory.path, name, end, maximum))
            return original(owners, directory, name, end, maximum, check)
        with patch.object(C.seed, "_small_read", side_effect=reading):
            self.snapshot(admitted)
        self.assertEqual(len(calls), 2)
        self.assertIs(calls[0][0], calls[1][0])
        self.assertEqual(calls[0][1:], (self.root, "gradle.properties", 1000., 65536))
        self.assertEqual(calls[1][1:], calls[0][1:])
        self.assertTrue(calls[0][0].closed)
        self.assertEqual(self.calls, [], "Snapshot cannot run packaging, native inspectors or any process")

    def test_schema2_missing_version_or_unknown_manifest_field_refuses(self):
        output, _ = self.fixture()
        for change, reason in (
                (lambda value: value.update(schema=2), "SAMPLE_MANIFEST_SOURCE_CHANGED"),
                (lambda value: value.update(schema=True), "SAMPLE_MANIFEST_SOURCE_CHANGED"),
                (lambda value: value.pop("versionBinding"), "SAMPLE_MANIFEST_FIELDS"),
                (lambda value: value.update(unreviewed="extra"), "SAMPLE_MANIFEST_FIELDS")):
            for kind in ("desktop", "android"):
                with self.subTest(kind=kind, reason=reason):
                    self.refused(output, kind, change, reason)

    def test_original_prepare_complete_and_scope_are_closed_records(self):
        output, admitted = self.fixture()
        for name, change in (
                (".prepare.json", lambda value: value.update(schema=True)),
                (".prepare.json", lambda value: value["generatedRoots"].reverse()),
                (".prepare.json", lambda value: value["generatedRoots"].append("unreviewed/generated")),
                (".complete.json", lambda value: value.update(schema=True)),
                (".complete.json", lambda value: value.update(unreviewed=True)),
                (".complete.json", lambda value: value["scope"].update(installationTest="PERFORMED")),
                (".complete.json", lambda value: value["scope"].update(desktopInstaller=1)),
                (".complete.json", lambda value: value["context"].update(translation="SYNTHETIC"))):
            path = output / name
            before = path.read_bytes()
            value = C.parse(before)
            change(value)
            try:
                self.write(path, value)
                with self.subTest(name=name), self.assertRaisesRegex(
                        C.ControllerError, "SAMPLE_ORIGINAL_SOURCE_OR_OUTPUT_CHANGED"):
                    self.snapshot(admitted)
            finally:
                self.write(path, before)
        for kind in ("desktop", "android"):
            self.refused(output, kind, lambda value: value["scope"].update(productionSigning="VERIFIED"),
                         "SAMPLE_MANIFEST_SOURCE_CHANGED")
            self.refused(output, kind, lambda value: value["scope"].update(desktopInstaller=1),
                         "SAMPLE_MANIFEST_SOURCE_CHANGED")

    def test_duplicate_json_identity_fields_refuse_even_with_updated_checksums(self):
        output, admitted = self.fixture()
        for kind in ("desktop", "android"):
            before = self.manifest(output, kind)
            for marker, replacement in (
                    (b'"schema":3', b'"schema":3,"schema":3'),
                    (b'"versionBinding":{', b'"versionBinding":{"canonicalVersion":"0.7.0-SNAPSHOT",')):
                raw = C.encoded(before)
                self.assertIn(marker, raw)
                try:
                    self.rewrite_manifest(output, kind, raw.replace(marker, replacement, 1))
                    with self.subTest(kind=kind, field=marker), self.assertRaisesRegex(
                            C.identity.AdmissionError, "IDENTITY_JSON_DUPLICATE"):
                        self.snapshot(admitted)
                finally:
                    self.rewrite_manifest(output, kind, before)

    def test_every_version_binding_field_is_required_and_source_derived(self):
        output, _ = self.fixture()
        changes = {"canonicalVersion": "0.8.0-SNAPSHOT", "androidVersionCode": 1,
                   "nativeVersion": "0.7.0", "debianVersion": "0.7.0-1"}
        for field, wrong in changes.items():
            for kind in ("desktop", "android"):
                with self.subTest(kind=kind, field=field):
                    self.refused(output, kind, lambda value: value["versionBinding"].update({field: wrong}),
                                 "SAMPLE_VERSION_BINDING_CHANGED")
                    self.refused(output, kind, lambda value: value["versionBinding"].pop(field),
                                 "SAMPLE_VERSION_BINDING_CHANGED")

    def test_coherently_rewritten_version_records_cannot_replace_original_source(self):
        _output, admitted = self.fixture(version="0.8.0-rc1")
        # Every packager record agrees with rc1, but the admitted source fixture
        # has a different VERSION_NAME. Manifest-to-manifest equality is not enough.
        self.write(self.root / "gradle.properties", b"VERSION_NAME=0.7.0-SNAPSHOT\n")
        with self.assertRaisesRegex(C.ControllerError, "SAMPLE_ORIGINAL_SOURCE_OR_OUTPUT_CHANGED"):
            self.snapshot(admitted)

    def test_duplicate_escaped_noncanonical_and_invalid_version_source_refuse(self):
        _output, admitted = self.fixture()
        for raw in (b"", b"VERSION_NAME=0.7.0-SNAPSHOT\nVERSION_NAME=0.7.0-SNAPSHOT\n",
                    b"VERSION_NAME=0.7.0-SNAPSHOT\nVERSION_\\u004eAME=0.7.0-SNAPSHOT\n",
                    b" VERSION_NAME=0.7.0-SNAPSHOT\n", b"VERSION_NAME=0.7.0-rc0\n", b"\xff"):
            self.write(self.root / "gradle.properties", raw)
            with self.subTest(raw=raw), self.assertRaisesRegex(C.ControllerError, "SAMPLE_SOURCE_VERSION_INVALID"):
                self.snapshot(admitted)

    def test_source_file_bound_is_not_the_larger_manifest_bound(self):
        _output, admitted = self.fixture()
        self.write(self.root / "gradle.properties", b"VERSION_NAME=0.7.0-SNAPSHOT\n#" + b"x" * 65536)
        with self.assertRaisesRegex(C.seed.SeedError, "SEED_FILE_LIMIT"):
            self.snapshot(admitted)

    def test_source_changed_during_delivery_hashing_refuses_final_reread(self):
        _output, admitted = self.fixture()
        original = C.sample_file
        changed = []
        def reading(*args, **kwargs):
            result = original(*args, **kwargs)
            if not changed:
                self.write(self.root / "gradle.properties", b"VERSION_NAME=0.8.0-SNAPSHOT\n")
                changed.append(True)
            return result
        with patch.object(C, "sample_file", side_effect=reading), \
                self.assertRaisesRegex(C.ControllerError, "SAMPLE_SOURCE_VERSION_CHANGED"):
            self.snapshot(admitted)
        self.assertEqual(changed, [True])

    def test_embedded_source_version_and_integer_types_cannot_drift(self):
        output, _ = self.fixture(version="0.0.0-SNAPSHOT")  # Android code1 exercises bool==int aliases.
        targets = (("desktop", lambda value: value["layoutInspection"]["embeddedIdentity"]),
                   ("desktop", lambda value: self.installer(value)["nativeMetadata"]["embeddedIdentity"]),
                   ("android", lambda value: value["apkInspection"]["embeddedIdentity"]))
        for kind, target in targets:
            for key, wrong in (("sourceCommit", "f" * 40), ("canonicalVersion", "0.8.0-SNAPSHOT"),
                               ("nativeVersion", "2.0.0"), ("schema", True), ("androidVersionCode", True)):
                with self.subTest(kind=kind, key=key):
                    self.refused(output, kind, lambda value: target(value).update({key: wrong}),
                                 "SAMPLE_EMBEDDED_IDENTITY_CHANGED")
        for kind in ("desktop", "android"):
            self.refused(output, kind, lambda value: value["versionBinding"].update(androidVersionCode=True),
                         "SAMPLE_VERSION_BINDING_CHANGED")

    def test_layout_architecture_and_scope_are_not_inferred_from_filename(self):
        output, _ = self.fixture()
        for key, wrong, reason in (("launcher", ["arm64"], "SAMPLE_LAYOUT_ARCHITECTURE_CHANGED"),
                ("runtimeVm", ["x64", "x64"], "SAMPLE_LAYOUT_ARCHITECTURE_CHANGED"),
                ("runtimeJava", [], "SAMPLE_LAYOUT_ARCHITECTURE_CHANGED"),
                ("releaseArchitecture", "aarch64", "SAMPLE_LAYOUT_INSPECTION_CHANGED"),
                ("jarCount", True, "SAMPLE_LAYOUT_INSPECTION_CHANGED"),
                ("layoutOnlyNotRuntimeExecution", False, "SAMPLE_LAYOUT_INSPECTION_CHANGED"),
                ("cliRequiresExternalJava", "11+", "SAMPLE_LAYOUT_INSPECTION_CHANGED")):
            with self.subTest(key=key):
                self.refused(output, "desktop", lambda value: value["layoutInspection"].update({key: wrong}), reason)
        self.refused(output, "desktop", lambda value: value.pop("layoutInspection"), "SAMPLE_MANIFEST_FIELDS")
        self.refused(output, "desktop", lambda value: value.update(installerInspection="INSTALLED"),
                     "SAMPLE_INSTALLER_SCOPE_CHANGED")

    def test_linux_native_metadata_reader_package_architecture_and_version_are_bound(self):
        output, _ = self.fixture()
        for key, wrong in (("Package", "another-package"), ("Version", "0.7.0-1"), ("Architecture", "arm64")):
            with self.subTest(key=key):
                self.refused(output, "desktop", lambda value:
                    self.installer(value)["nativeMetadata"]["fields"].update({key: wrong}), "SAMPLE_NATIVE_VERSION_CHANGED")
        self.refused(output, "desktop", lambda value: self.installer(value)["nativeMetadata"].update(reader="NOT_INSPECTED"),
                     "SAMPLE_NATIVE_READER_CHANGED")
        self.refused(output, "desktop", lambda value: self.installer(value).pop("nativeMetadata"), "SAMPLE_INSTALLER_FIELDS")

    def test_windows_native_metadata_preserves_template_and_word_count_types(self):
        output, _ = self.fixture("windows-x64")
        for key, wrong in (("ProductName", "Another Sample"), ("ProductVersion", "0.7.0"),
                           ("Template", "Arm64;1033"), ("WordCount", True), ("WordCount", -1)):
            with self.subTest(key=key, wrong=wrong):
                self.refused(output, "desktop", lambda value:
                    self.installer(value)["nativeMetadata"]["fields"].update({key: wrong}), "SAMPLE_NATIVE_VERSION_CHANGED")

    def test_macos_both_native_version_fields_are_bound(self):
        output, _ = self.fixture("macos-arm64")
        for key in ("CFBundleVersion", "CFBundleShortVersionString"):
            with self.subTest(key=key):
                self.refused(output, "desktop", lambda value:
                    self.installer(value)["nativeMetadata"]["fields"].update({key: "0.7.0"}), "SAMPLE_NATIVE_VERSION_CHANGED")

    def test_android_binary_manifest_and_agp_cannot_disagree_or_claim_signing(self):
        output, _ = self.fixture(version="0.0.0-SNAPSHOT")
        for container, reason in ((lambda value: value["agpMetadata"], "SAMPLE_AGP_IDENTITY_CHANGED"),
                                  (lambda value: value["apkInspection"]["binaryManifest"], "SAMPLE_APK_IDENTITY_CHANGED")):
            for key, wrong in (("applicationId", "other.application"), ("versionName", "0.8.0-SNAPSHOT"), ("versionCode", True)):
                with self.subTest(key=key, reason=reason):
                    self.refused(output, "android", lambda value: container(value).update({key: wrong}), reason)
        self.refused(output, "android", lambda value: value["agpMetadata"].update(variant="release"), "SAMPLE_AGP_IDENTITY_CHANGED")
        self.refused(output, "android", lambda value: value["apkInspection"].update(signerIdentity="VERIFIED"),
                     "SAMPLE_APK_IDENTITY_CHANGED")
        for key, wrong in (("bytes", True), ("bytes", 0), ("bytes", C.MIB + 1), ("sha256", "not-a-digest")):
            with self.subTest(key=key, wrong=wrong):
                self.refused(output, "android", lambda value: value["metadataFile"].update({key: wrong}),
                             "SAMPLE_AGP_SOURCE_BINDING")

    def test_source_reader_failure_retires_the_actual_leaf_and_preserves_primary_error(self):
        _output, admitted = self.fixture()
        owner, error = self.owner(), RuntimeError("SYNTHETIC_VERSION_READ_FAILURE")
        original = C.seed.PosixFile.read
        def reading(reader, count):
            if reader.path == self.root / "gradle.properties":
                raise error
            return original(reader, count)
        with patch.object(C.seed.PosixFile, "read", new=reading), self.assertRaises(RuntimeError) as caught:
            C.sample_snapshot(owner, C.session_path("desktop", self.role), admitted, self.role, 1000., lambda: None)
        self.assertIs(caught.exception, error)
        self.assertIs(owner.original, error)
        self.assertFalse(owner.unknown)
        leaves = [row for row in owner.resources if isinstance(row["owner"], C.seed.PosixFile)]
        self.assertEqual(len(leaves), 1)
        self.assertTrue(leaves[0]["attempted"] and leaves[0]["closed"])
        owner.close()
        self.assertTrue(all(row["closed"] for row in owner.resources))

    def test_unknown_source_directory_close_never_returns_a_snapshot(self):
        _output, admitted = self.fixture()
        owner, closes = self.owner(), []
        original = C.seed.PosixSourceDirectory.close
        def closing(directory):
            selected = directory.path == self.root and not directory.closed
            original(directory)
            if selected:
                closes.append(directory)
                raise OSError("SYNTHETIC_VERSION_SOURCE_CLOSE_UNKNOWN")
        with patch.object(C.seed.PosixSourceDirectory, "close", new=closing), \
                self.assertRaisesRegex(C.seed.SeedError, "SEED_RETIREMENT_UNKNOWN"):
            C.sample_snapshot(owner, C.session_path("desktop", self.role), admitted, self.role, 1000., lambda: None)
        self.assertEqual(len(closes), 1)
        self.assertTrue(owner.unknown)
        row = next(row for row in owner.resources if row["owner"] is closes[0])
        self.assertTrue(row["attempted"])
        self.assertFalse(row["closed"])
        self.assertEqual(self.output.read_bytes(), b"")

    def test_source_read_close_dual_failure_preserves_primary_without_close_retry(self):
        _output, admitted = self.fixture()
        owner, error, closes = self.owner(), RuntimeError("SYNTHETIC_VERSION_READ_FAILURE"), []
        original_read, original_close = C.seed.PosixFile.read, C.seed.PosixFile.close
        def reading(reader, count):
            if reader.path == self.root / "gradle.properties":
                raise error
            return original_read(reader, count)
        def closing(reader):
            selected = reader.path == self.root / "gradle.properties" and not reader.closed
            original_close(reader)
            if selected:
                closes.append(reader)
                raise OSError("SYNTHETIC_VERSION_LEAF_CLOSE_UNKNOWN")
        with patch.object(C.seed.PosixFile, "read", new=reading), \
                patch.object(C.seed.PosixFile, "close", new=closing):
            with self.assertRaises(RuntimeError) as caught:
                C.sample_snapshot(owner, C.session_path("desktop", self.role), admitted, self.role, 1000., lambda: None)
            self.assertIs(caught.exception, error)
            self.assertIs(owner.original, error)
            self.assertTrue(owner.unknown)
            self.assertEqual(len(closes), 1)
            row = next(row for row in owner.resources if row["owner"] is closes[0])
            self.assertTrue(row["attempted"])
            self.assertFalse(row["closed"])
            self.assertTrue(any("retirement UNKNOWN" in note for note in getattr(error, "__notes__", ())))
            with self.assertRaisesRegex(C.ControllerError, "CONTROLLER_RESOURCE_RETIREMENT_UNKNOWN"):
                owner.close()
            self.assertEqual(len(closes), 1)
            self.assertIn(owner, C.QUARANTINE)
        self.assertEqual(self.output.read_bytes(), b"")

    def test_final_source_reread_and_output_cannot_extend_original_deadline(self):
        _output, admitted = self.fixture()
        owner, calls = self.owner(), []
        original = C.seed._small_read
        def reading(*args, **kwargs):
            raw = original(*args, **kwargs)
            calls.append(True)
            if len(calls) == 2:
                self.clock.now = 1000.
            return raw
        with patch.object(C.seed, "_small_read", side_effect=reading), \
                self.assertRaisesRegex(C.posix.EvidenceError, "deadline"):
            C.sample_snapshot(owner, C.session_path("desktop", self.role), admitted, self.role, 1000.,
                              lambda: C.posix._deadline(1000.))
        self.assertEqual(len(calls), 2)
        self.assertEqual(self.output.read_bytes(), b"")


class DeliveryModels(ConnectedBase):
    def test_unmarked_run_delivers_encrypted_evidence_without_sample_outputs(self):
        self.delivery_fixture(package_samples=False)
        self.evidence_uploaded()
        self.assertFalse((self.runner_temp / "p2pkit-sample-apps").exists())
        self.assertNotIn("samplePackaging", self.result)
        self.assertEqual(self.context["command"], [*C.DESKTOP_TASKS, "--console=plain"])
        with self.assertRaisesRegex(C.ControllerError, "SAMPLES_REQUIRE_PASSING_PROFILE"):
            self.guard(C.package_samples_guard, "desktop")
        self.assertEqual(self.calls, [])

    def test_marked_delivery_cannot_drop_required_packaging(self):
        self.delivery_fixture()
        self.context["samplePackagingRequired"] = False
        raw = self.write(self.session / "run-context.json", self.context)
        self.result["contextSha256"] = C.digest(raw)
        self.result.pop("samplePackaging")
        self.write(self.session / "controller-result.json", self.result)
        with self.assertRaisesRegex(C.ControllerError, "DELIVERY_SAMPLE_INTENT_CHANGED"):
            self.guard(C.upload_guard, "before", "desktop")
        self.assertEqual(self.output.read_bytes(), b"")

    def test_unmarked_delivery_cannot_forge_packaging_with_matching_context_hash(self):
        self.delivery_fixture(package_samples=False)
        self.context["samplePackagingRequired"] = True
        raw = self.write(self.session / "run-context.json", self.context)
        self.result["contextSha256"] = C.digest(raw)
        self.result["samplePackaging"] = {"required": True, "status": "PASS", "manifestSha256": "a" * 64}
        self.write(self.session / "controller-result.json", self.result)
        with self.assertRaisesRegex(C.ControllerError, "DELIVERY_SAMPLE_INTENT_CHANGED"):
            self.guard(C.upload_guard, "before", "desktop")
        self.assertEqual(self.output.read_bytes(), b"")

    def test_unmarked_delivery_cannot_keep_a_release_installer_command(self):
        self.delivery_fixture(package_samples=False)
        self.context["command"] = C.profile_command("desktop", self.role, package_samples=True)[1]
        raw = self.write(self.session / "run-context.json", self.context)
        self.result["contextSha256"] = C.digest(raw)
        self.write(self.session / "controller-result.json", self.result)
        with self.assertRaisesRegex(C.ControllerError, "DELIVERY_SAMPLE_INTENT_CHANGED"):
            self.guard(C.upload_guard, "before", "desktop")

    def test_successful_linux_chain_uses_original_package_and_one_sample_window(self):
        self.delivery_fixture()
        self.package_ready()
        original_report = (self.session / "evidence/sample-packaging.json").read_bytes()
        self.sample_uploaded("desktop")
        window = (self.session / "sample-window.json").read_bytes()
        self.sample_uploaded("android")
        self.guard(C.sample_delivery_guard, "desktop")
        terminal = C.parse((self.session / "sample-delivery.json").read_bytes())
        self.assertEqual(set(terminal["uploads"]), {"desktop", "android"})
        self.assertEqual(window, (self.session / "sample-window.json").read_bytes())
        self.assertEqual(original_report, (self.session / "evidence/sample-packaging.json").read_bytes())
        self.assertEqual(self.calls, [], "No packaging/build/native process may be started by delivery guards")
        self.assertLess(terminal["observedRawNs"], terminal["deliveryEndRawNs"])

    def test_non_linux_delivery_requires_android_steps_to_be_skipped(self):
        self.role = "macos-arm64"
        self.exact_clock = D.clock(self.role)
        self.admitted = D.admission(self.role)
        self.budget = J.derive(self.admitted, D.originals(self.admitted, self.exact_clock),
                              D.F.provenance(), clock=self.exact_clock)
        self.delivery_fixture()
        self.package_ready()
        self.sample_uploaded("desktop")
        with self.assertRaisesRegex(C.ControllerError, "ANDROID_SAMPLE_LINUX_ONLY"):
            self.guard(C.sample_upload_guard, "before", "android", "desktop")
        for phase in ("BEFORE", "UPLOAD", "AFTER"):
            os.environ["P2PKIT_SAMPLE_ANDROID_" + phase + "_OUTCOME"] = "skipped"
        for phase in ("BEFORE", "UPLOAD", "AFTER"):
            with self.subTest(phase=phase), patch.dict(os.environ, {
                    "P2PKIT_SAMPLE_ANDROID_" + phase + "_OUTCOME": "success"}), \
                    self.assertRaisesRegex(C.ControllerError, "SAMPLE_DELIVERY_ORIGINAL_OUTCOME_FAILED"):
                self.guard(C.sample_delivery_guard, "desktop")
        self.guard(C.sample_delivery_guard, "desktop")
        terminal = C.parse((self.session / "sample-delivery.json").read_bytes())
        self.assertEqual(set(terminal["uploads"]), {"desktop"})
        self.assertFalse((self.session / "sample-android-before.json").exists())
        self.assertEqual(self.calls, [])

    def test_package_guard_does_not_repackage_changed_output(self):
        self.delivery_fixture()
        self.evidence_uploaded()
        path = self.sample_output / "android/sample-debug.apk"
        self.write(path, b"MUTATED")
        with self.assertRaisesRegex(C.ControllerError, "SAMPLE_ARTIFACT_CHANGED"):
            self.guard(C.package_samples_guard, "desktop")
        self.assertFalse((self.session / "packaging-ready.json").exists())
        self.assertEqual(self.calls, [])

    def test_frozen_package_log_cannot_be_replaced_even_with_matching_copy_map(self):
        self.delivery_fixture()
        self.evidence_uploaded()
        frozen_path = self.session / "frozen-evidence"
        mapping = C.parse((frozen_path / "original-path-map.json").read_bytes())
        row = next(r for r in mapping["files"] if r["original"] == "commands/sample-packaging/stdout.log")
        raw = b"REPLACED BOTH ORIGINAL AND COPY"
        self.write(self.session / "evidence" / row["original"], raw)
        self.write(frozen_path / row["member"], raw)
        row.update(size=len(raw), sha256=C.digest(raw))
        self.write(frozen_path / "original-path-map.json", mapping)
        with self.assertRaisesRegex(C.ControllerError, "SAMPLE_ORIGINAL_FROZEN_PACKAGE_CHANGED"):
            self.guard(C.package_samples_guard, "desktop")

    def test_original_outcome_failure_blocks_despite_convincing_files(self):
        self.delivery_fixture()
        for key in ("P2PKIT_HOSTED_TEST_RUN_OUTCOME", "P2PKIT_HOSTED_TEST_SEAL_OUTCOME"):
            for failure in ("failure", "cancelled", "skipped", ""):
                with self.subTest(key=key, failure=failure), patch.dict(os.environ, {key: failure}), \
                        self.assertRaisesRegex(C.ControllerError, "DELIVERY_REQUIRES_ORIGINAL_SUCCESS"):
                    self.guard(C.upload_guard, "before", "desktop")
        self.assertFalse((self.session / "upload-before.json").exists())
        self.package_ready()
        for key in ("P2PKIT_HOSTED_TEST_UPLOAD_OUTCOME", "P2PKIT_HOSTED_TEST_UPLOAD_AFTER_OUTCOME",
                    "P2PKIT_SAMPLE_PACKAGE_OUTCOME"):
            with self.subTest(key=key), patch.dict(os.environ, {key: "failure"}), self.assertRaises(C.ControllerError):
                self.guard(C.sample_upload_guard, "before", "desktop", "desktop")

    def test_first_after_read_below_before_highwater_is_rejected_without_recovery(self):
        self.delivery_fixture()
        before = self.guard(C.upload_guard, "before", "desktop")
        os.environ["P2PKIT_HOSTED_TEST_UPLOAD_GUARD_SHA256"] = before["upload_guard_sha256"]
        row = C.parse((self.session / "upload-before.json").read_bytes())
        self.clock.set_raw(row["timeoutObservedRawNs"] - 1)
        with self.assertRaises(D.C.ClockError): self.guard(C.upload_guard, "after", "desktop")
        self.assertFalse((self.session / "upload-after.json").exists())

    def test_second_platform_never_gets_a_fresh_180_second_window(self):
        self.delivery_fixture()
        self.package_ready()
        self.sample_uploaded("desktop")
        window = C.parse((self.session / "sample-window.json").read_bytes())
        self.clock.set_raw(window["endRawNs"] - 59 * J.NS)
        with self.assertRaisesRegex(C.ControllerError, "SAMPLE_UPLOAD_NO_COMPLETE_MINUTE_LEFT"):
            self.guard(C.sample_upload_guard, "before", "android", "desktop")
        self.assertFalse((self.session / "sample-android-before.json").exists())

    def test_cancellation_and_close_failure_do_not_emit_success(self):
        self.delivery_fixture()
        with self.assertRaises(KeyboardInterrupt):
            C.upload_guard("before", "desktop", cancelled=[15])
        self.assertEqual(self.output.read_bytes(), b"")
        original_close = self.original_owner.close
        def late_close(owner):
            original_close(owner)
            raise RuntimeError("ORIGINAL_CLOSE_FAILURE")
        with patch.object(self.original_owner, "close", late_close), self.assertRaisesRegex(RuntimeError, "ORIGINAL_CLOSE_FAILURE"):
            self.guard(C.upload_guard, "before", "desktop")
        self.assertEqual(self.output.read_bytes(), b"")

    def test_output_close_past_original_fence_cannot_turn_provisional_output_into_success(self):
        self.delivery_fixture()
        original = Path.open
        fixture = self
        class LateClose:
            def __init__(value, stream): value.stream = stream
            def __enter__(value): return value.stream
            def __exit__(value, *args):
                value.stream.close()
                fixture.clock.set_raw(10200 * J.NS)
        def opened(path, *args, **kwargs):
            stream = original(path, *args, **kwargs)
            return LateClose(stream) if path == self.output and args and args[0] == "a" else stream
        with patch.object(Path, "open", opened), self.assertRaisesRegex(C.ControllerError, "ORIGINAL_DELIVERY_WINDOW_EXPIRED"):
            self.guard(C.upload_guard, "before", "desktop")
        self.assertIn(b"upload_ready=true", self.output.read_bytes())

    def test_final_guard_requires_all_original_upload_outcomes(self):
        self.delivery_fixture()
        self.package_ready()
        self.sample_uploaded("desktop")
        self.sample_uploaded("android")
        for platform in ("DESKTOP", "ANDROID"):
            for phase in ("BEFORE", "UPLOAD", "AFTER"):
                key = "P2PKIT_SAMPLE_" + platform + "_" + phase + "_OUTCOME"
                with self.subTest(key=key), patch.dict(os.environ, {key: "failure"}), \
                        self.assertRaisesRegex(C.ControllerError, "SAMPLE_DELIVERY_ORIGINAL_OUTCOME_FAILED"):
                    self.guard(C.sample_delivery_guard, "desktop")
        self.assertFalse((self.session / "sample-delivery.json").exists())


class PackagingModels(ConnectedBase):
    def test_setup_derives_packaging_after_admission_not_from_environment(self):
        for required in (False, True):
            with self.subTest(required=required):
                controller = C.Controller("desktop", consume_dependencies=True)
                self.owners.append(controller)
                self.assertFalse(controller.sample_required)
                admitted = D.admission(self.role, package_samples=required)
                def adopt(value):
                    value.admitted = admitted
                with patch.object(C, "adopt_preparation", side_effect=adopt), \
                        patch.object(C, "canonical_bindings", side_effect=RuntimeError("MODEL_STOP_BEFORE_CRYPTO")), \
                        patch.dict(os.environ, {"P2PKIT_SAMPLE_PACKAGING_REQUIRED": str(not required).lower()}), \
                        self.assertRaisesRegex(RuntimeError, "MODEL_STOP_BEFORE_CRYPTO"):
                    controller.setup()
                self.assertIs(controller.sample_required, required)
                self.assertEqual((controller.kind, controller.command),
                                 C.profile_command("desktop", self.role, package_samples=required))
        self.assertEqual(self.calls, [])

    def prepared_controller(self):
        controller = C.Controller("desktop", consume_dependencies=True)
        self.owners.append(controller)
        controller.allocate()
        controller.admitted, controller.budget, controller.clock = self.admitted, self.budget, self.exact_clock
        controller.sample_required = C.identity.sample_packaging_required(self.admitted)
        controller.last_raw = 10010 * J.NS
        context = {"profile": "desktop", "role": self.role, "source": C.parse(self.admitted.record)["source"],
                   "samplePackagingRequired": True}
        raw = self.write(controller.path / "run-context.json", context)
        controller.context_hash = C.digest(raw)
        controller.product_attempted = controller.collect_attempted = controller.uninstall_attempted = True
        controller.seed_requested = False  # This test begins AFTER the separately tested seeding boundary.
        controller.custody = {"result": "RETAINED", "retirement": "KNOWN", "errors": [],
                             "productExitCode": 0, "stopExitCode": 0, "ownerFinalExitCode": 0}
        controller.records = [{"phase": label, "exitCode": 0, "launchAttempted": True, "scopeAttempted": True,
                   "retirement": "KNOWN", "errors": [], "survivors": [], "ownership": {"discoveryErrors": []},
                   "jobBudgetSha256": self.budget.sha256, "completedRawNs": 10001 * J.NS}
                   for label in C.DESKTOP_ORDER[:-2]]
        controller.phase_hashes = {row["phase"]: C.digest(C.encoded(row)) for row in controller.records}
        self.model_child = lambda _argv, _environment: self.sample_fixture()
        return controller

    def test_original_owned_packaging_phase_precedes_the_only_frozen_packet(self):
        controller = self.prepared_controller()
        controller.package_samples()
        self.assertEqual(controller.sample_result["status"], "PASS")
        self.assertEqual(len(self.calls), 1)
        call = self.calls[0]
        self.assertEqual(call["argv"], controller.python(C.SCRIPTS / "package-sample-apps.py", "package", "--output",
                                                     self.runner_temp / "p2pkit-sample-apps"))
        self.assertNotIn("gradlew", " ".join(call["argv"]))
        self.assertTrue(controller.result()["profilePassed"])
        self.write(controller.evidence.path / "profile-result-before-export.json", controller.result())
        C.copy_tree(controller, controller.evidence, controller.path / "frozen-evidence", 1000.)
        packet = C.frozen_package_packet(controller, controller.private, 1000., lambda: None)
        self.assertIn("commands/sample-packaging/stdout.log", {row["original"] for row in packet["files"]})
        with self.assertRaisesRegex(C.ControllerError, "SAMPLE_PACKAGING_ONE_SHOT"):
            controller.package_samples()

    def test_failed_original_product_never_packages(self):
        controller = self.prepared_controller()
        controller.custody["productExitCode"] = 1
        with self.assertRaisesRegex(C.ControllerError, "SAMPLE_PACKAGING_REQUIRES_SUCCESSFUL_RETIRED_PRODUCT"):
            controller.package_samples()
        self.assertEqual(self.calls, [])
        self.assertFalse((controller.evidence.path / "sample-packaging.json").exists())

    def test_nonzero_packager_keeps_original_command_failure_and_no_success_manifest(self):
        controller = self.prepared_controller()
        self.exit_code = 1
        with self.assertRaisesRegex(C.ControllerError, "SAMPLE_PACKAGER_FAILED"):
            controller.package_samples()
        self.assertEqual(controller.records[-1]["exitCode"], 1)
        self.assertEqual(controller.sample_result["status"], "FAILED")
        self.assertFalse((controller.evidence.path / "sample-packaging.json").exists())
        self.assertFalse(controller.result()["profilePassed"])

    def test_packaging_cancellation_retires_original_phase_but_cannot_report_success(self):
        controller = self.prepared_controller()
        self.after_launch = lambda: controller.cancelled.append(15)
        with self.assertRaises(KeyboardInterrupt): controller.package_samples()
        self.assertEqual(controller.records[-1]["retirement"], "KNOWN")
        self.assertIn("drain", self.events)
        self.assertEqual(controller.sample_result["status"], "FAILED")

    def test_packaging_uses_original_75_plus_45_ceiling(self):
        controller = self.prepared_controller()
        def late():
            self.clock.now += 75
        self.after_launch = late
        with self.assertRaisesRegex(C.ControllerError, "FULL_JOB_PHASE_EXPIRED"):
            controller.package_samples()
        self.assertEqual(controller.records[-1]["retirement"], "KNOWN")
        self.assertEqual(controller.sample_result["status"], "FAILED")

    def test_unknown_packaging_retirement_never_freezes_success(self):
        controller = self.prepared_controller()
        self.drain_error = RuntimeError("SYNTHETIC_UNKNOWN_PACKAGER")
        with self.assertRaises(C.ControllerError): controller.package_samples()
        self.assertTrue(controller.unknown)
        self.assertEqual(controller.records[-1]["retirement"], "UNKNOWN")
        self.assertFalse((controller.evidence.path / "sample-packaging.json").exists())


class SignalModels(ConnectedBase):
    def test_guarded_operation_preserves_first_error_if_signal_restoration_fails(self):
        original = RuntimeError("ORIGINAL_OPERATION_FAILURE")
        def operation(*, cancelled):
            self.assertEqual(cancelled, [])
            raise original
        def handlers(_number, value):
            if value == "MODEL_PREVIOUS_HANDLER": raise RuntimeError("SECONDARY_RESTORE_FAILURE")
        with patch.object(C.signal, "signal", side_effect=handlers), self.assertRaises(RuntimeError) as raised:
            C.guarded_operation(operation)
        self.assertIs(raised.exception, original)

    def test_guarded_operation_cancellation_after_return_is_not_success(self):
        def operation(*, cancelled): cancelled.append(15)
        with self.assertRaises(KeyboardInterrupt): C.guarded_operation(operation)


class CryptoClockModels(unittest.TestCase):
    """Reuse only the synthetic fixture, never discover/run its old test suite."""
    def fixture(self):
        case = M.WholeControllerModels(methodName="runTest")
        case.setUp()
        self.addCleanup(case.tearDown)
        forbid_external_operations(case.stack)
        return case

    def test_first_crypto_child_read_preserves_original_parent_phase_start(self):
        case = self.fixture()
        phase = C.Controller.phase
        excursions = []
        def delayed(controller, label, *args, **kwargs):
            if label == "recipient-validation":
                case.clock.now += 10
            return phase(controller, label, *args, **kwargs)
        def reading():
            current = case.clock.raw()
            if case.active_crypto_operation == "validate" and not excursions:
                session = C.session_path("full", "macos-arm64")
                start = C.parse((session / "evidence/commands/recipient-validation/start.json").read_bytes())
                budget = C.job_time.Budget((session / "evidence/job-time/budget.json").read_bytes())
                lower = start["startedRawNs"] - 1
                self.assertGreater(lower, budget.value["responseFinishedRawNs"])
                self.assertLess(lower, current)
                excursions.append(lower)
                return lower
            return current
        with patch.object(C.Controller, "phase", delayed), \
                patch.object(C.job_time, "shared_raw_ns", side_effect=reading):
            try:
                case.full_controller()
            except BaseException:
                pass  # The exact original child failure is asserted below.
        self.assertEqual(len(excursions), 1)
        self.assertTrue(case.crypto_child_errors, "backward first child observation was accepted")
        self.assertIsInstance(case.crypto_child_errors[0][1], C.job_time.BudgetError)
        self.assertFalse(any("init" in row["argv"] for row in case.calls))

    def test_first_job_time_child_read_preserves_original_parent_phase_start(self):
        case = self.fixture()
        model = case.model_child
        active, excursions = [], []
        def child(argv, environment):
            if "_job-time" in argv:
                active.append(True)
                try:
                    return model(argv, environment)
                finally:
                    active.pop()
            return model(argv, environment)
        def reading():
            current = case.clock.raw()
            if active and not excursions:
                session = C.session_path("full", "macos-arm64")
                start = C.parse((session / "evidence/commands/job-time/start.json").read_bytes())
                lower = start["startedRawNs"] - 1
                excursions.append(lower)
                return lower
            return current
        with patch.object(case, "model_child", side_effect=child), \
                patch.object(C.job_time, "shared_raw_ns", side_effect=reading):
            try:
                case.full_controller()
            except BaseException:
                pass  # It must fail before crypto/product admission below.
        self.assertEqual(len(excursions), 1)
        self.assertTrue(case.job_time_child_errors, "backward first acquisition observation was accepted")
        self.assertFalse(any("_crypto" in row["argv"] for row in case.calls))

    def test_budget_binding_preserves_original_native_phase_highwater(self):
        case = self.fixture()
        model = case.model_child
        excursions = []
        def child(argv, environment):
            result = model(argv, environment)
            if "_job-time" in argv:
                case.clock.now += 10
            return result
        def reading():
            current = case.clock.raw()
            controller = case.owners[-1] if case.owners else None
            if controller is not None and controller.budget is not None and \
                    controller.records[-1]["phase"] == "job-time" and not excursions:
                lower = controller.last_raw - 1
                self.assertGreater(lower, controller.budget.value["responseFinishedRawNs"])
                excursions.append(lower)
                return lower
            return current
        error = None
        with patch.object(case, "model_child", side_effect=child), \
                patch.object(C.job_time, "shared_raw_ns", side_effect=reading):
            try:
                case.full_controller()
            except BaseException as caught:
                error = caught
        self.assertEqual(len(excursions), 1)
        self.assertIsInstance(error, J.BudgetError)
        self.assertFalse(any("_crypto" in row["argv"] for row in case.calls))

    def test_job_time_return_preserves_acquisitions_post_retention_highwater(self):
        case = self.fixture()
        acquire = J.acquire
        returned = []
        def late_return(admitted, invocation, token, retain, **options):
            def retained(name, raw):
                retain(name, raw)
                if name == "jobs":
                    case.clock.now += 10
            originals, completed = acquire(admitted, invocation, token, retained, **options)
            self.assertEqual(completed, case.clock.raw())
            self.assertGreater(completed, max(J.parse(raw)["finishedRawNs"] for raw in originals.values()))
            returned.append(completed)
            case.clock.now -= 1  # One backward caller sample after the real supplier return.
            return originals, completed
        with patch.object(J, "acquire", side_effect=late_return):
            try:
                case.full_controller()
            except BaseException:
                pass
        self.assertEqual(len(returned), 1)
        self.assertTrue(case.job_time_child_errors)
        self.assertIsInstance(case.job_time_child_errors[0], J.BudgetError)
        self.assertFalse(any("_crypto" in row["argv"] for row in case.calls))


def consume_metadata(raw):
    return ('<?xml version="1.0" encoding="UTF-8"?><verification-metadata xmlns="' + S.authority.NAMESPACE +
        '" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="' + S.authority.SCHEMA_LOCATION +
        '"><configuration><verify-metadata>true</verify-metadata><verify-signatures>false</verify-signatures>' +
        '</configuration><components><component group="org.fixture" name="toy" version="1.0">' +
        '<artifact name="toy.jar"><sha256 value="' + S.digest(raw) +
        '"/></artifact></component></components></verification-metadata>').encode("ascii")


class ConsumeClock:
    def __init__(self):
        self.local, self.raw = 100.0, 10010 * NS
        self.sequence, self.samples = [], []

    def monotonic(self):
        return self.local

    def read(self):
        if self.sequence:
            self.raw = self.sequence.pop(0)
        self.samples.append(self.raw)
        return self.raw

    def advance(self, seconds):
        self.local += seconds
        self.raw += int(seconds * NS)


class ConsumeBase(unittest.TestCase):
    profile = "desktop"
    role = "macos-arm64"

    def setUp(self):
        parent = Path(os.environ.get("P2PKIT_OFFLINE_TEST_TEMP", str(ROOT.parent))).resolve(strict=True)
        self.temp = tempfile.TemporaryDirectory(prefix="consume-model-", dir=parent)
        self.path = Path(self.temp.name).resolve(strict=True)
        self.root, self.runner = self.path / "source", self.path / "runner"
        self.root.mkdir(mode=0o700)
        self.runner.mkdir(mode=0o700)
        self.output = self.path / "github-output"
        self.output.write_bytes(b"")
        self.output.chmod(0o600)
        self.payload = b"small synthetic allowlisted bytes; not a real dependency"
        self.source_inputs()
        self.clock = ConsumeClock()
        self.stack, self.owners, self.admissions = ExitStack(), [], []
        forbid_external_operations(self.stack)
        self.prepared_controller = None
        self.quarantines = [(q, list(q)) for q in (C.QUARANTINE, C.query.QUARANTINE, C.windows._QUARANTINE)]
        self.admitted = D.admission(self.role) if self.profile == "desktop" else D.F.model_admission()
        self.exact_clock = D.clock(self.role) if self.profile == "desktop" else None
        self.stack.enter_context(patch.dict(os.environ, {
            "RUNNER_TEMP": str(self.runner), "GITHUB_RUN_ID": "123", "GITHUB_RUN_ATTEMPT": "1",
            "GITHUB_OUTPUT": str(self.output), "PATH": "/synthetic/no-executable-directory",
            "JAVA_HOME": "/synthetic/jdk17", "P2PKIT_AUDIT_JDK21": "/synthetic/jdk21",
            "RUNNER_NAME": D.F.RUNNER,
        }, clear=True))
        self.stack.enter_context(patch.object(C, "ROOT", self.root))
        self.stack.enter_context(patch.object(C, "SCRIPTS", self.root / "scripts"))
        self.stack.enter_context(patch.object(C.processes, "host_role", return_value=self.role))
        self.stack.enter_context(patch.object(C.processes, "make_scope", side_effect=AssertionError("NO_NATIVE_OWNER")))
        self.stack.enter_context(patch.object(C.query, "NativeGitQueries", side_effect=AssertionError("NO_GIT_CHILD")))
        self.stack.enter_context(patch.object(J.http.client, "HTTPSConnection", side_effect=AssertionError("NO_HTTP")))
        self.stack.enter_context(patch.object(J.ssl, "create_default_context", side_effect=AssertionError("NO_TLS")))
        self.stack.enter_context(patch.object(C.posix, "validate_recipient", side_effect=AssertionError("NO_GPG")))
        self.stack.enter_context(patch.object(C.windows, "validate_recipient", side_effect=AssertionError("NO_GPG")))
        self.stack.enter_context(patch.object(C.ordinary, "export_encrypted", side_effect=AssertionError("NO_GPG")))
        self.stack.enter_context(patch.object(C.windows, "export_test_encrypted", side_effect=AssertionError("NO_GPG")))
        self.stack.enter_context(patch.object(C.time, "monotonic", side_effect=self.clock.monotonic))
        self.stack.enter_context(patch.object(J, "shared_raw_ns", side_effect=self.clock.read))
        self.stack.enter_context(patch.object(J._clocks(), "observe", side_effect=lambda:
            J._clocks().Reading(D.clock(self.role), self.clock.read())))
        self.stack.enter_context(patch.object(C, "admission", side_effect=self.admission))
        self.stack.enter_context(patch.object(C, "PrivateOwner", side_effect=self.owner))
        self.stack.enter_context(patch.object(Controller, "phase", side_effect=AssertionError("NO_CHILD_OR_PRODUCT_PHASE")))

    def tearDown(self):
        # Tests own only synthetic files, never OS workers. UNKNOWN is asserted
        # before this fixture-only disposal, not recovered as production success.
        for owner in reversed(self.owners):
            for row in reversed(owner.resources):
                resource = row["owner"]
                if isinstance(resource, (C.query._PosixDirectory, C.query._PosixSink,
                                         S._PosixDirectory, S.PosixFile)):
                    try:
                        resource.close()
                    except BaseException:
                        pass
        for q, original in self.quarantines:
            q[:] = original
        self.stack.close()
        self.temp.cleanup()

    def source_inputs(self):
        for index, name in enumerate(S.INPUTS):
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            path.write_bytes(consume_metadata(self.payload) if index == 0 else ("synthetic source: " + name + "\n").encode())
            path.chmod(0o600)

    def owner(self):
        value = Owner()
        self.owners.append(value)
        return value

    def admission(self, owner, profile, destination, check_cancel, expected=None):
        self.assertEqual(profile, self.profile)
        if expected is not None:
            self.assertEqual(expected, self.admitted)
        check_cancel()
        directory = owner.new(destination)
        end = self.clock.local + 30
        for name, raw in (("admission.json", self.admitted.record), ("original-event.json", self.admitted.original_event),
                          ("original-policy.json", self.admitted.original_policy), ("recipient-public.asc", self.admitted.public_key)):
            owner.write(directory, name, raw, end)
        self.admissions.append(str(destination))
        check_cancel()
        return self.admitted

    def acquire_job_time(self, controller):
        """Synthetic native child originals; derive_job_budget itself is real."""
        self.assertTrue(controller.preflight)
        self.assertIsNone(controller.budget)
        end = self.clock.local + 30
        phase = controller.child(controller.commands, "job-time", end, create=True)
        directory = controller.child(controller.evidence, "job-time", end, create=True)
        args = [str(Path(sys.executable).resolve(strict=True)), "-I", "-B", "-S", str(Path(C.__file__)),
                "_job-time", "--profile", self.profile, "--admission-sha256", C.digest(self.admitted.record)]
        invocation = "e" * 32
        start = {"phase": "job-time", "argv": args, "cwd": str(self.root), "job": controller.job,
                 "invocation": invocation, "state": str(controller.path),
                 "home": str(controller.path / "control-home"), "startedRawNs": 10000 * NS}
        original = (D.originals(self.admitted, self.exact_clock) if self.exact_clock is not None else
                    D.F.model_responses(self.admitted))
        row = {**start, "exitCode": 0, "retirement": "KNOWN", "launchAttempted": True,
            "scopeAttempted": True, "errors": [], "survivors": [], "jobBudgetSha256": None,
            "cooperativeCancellation": None, "completedRawNs": 10001 * NS, "finalizedRawNs": 10002 * NS,
            "ownership": {"backend": "darwin-libproc-audit-token", "job": controller.job,
                "invocation": invocation, "discoveryErrors": [], "launches": [{"created": True}],
                "startedIdentities": [{"pid": 100001, "model": True}]}}
        returned = {"schema": 1 if self.exact_clock is None else 2,
            "scope": "ORDINARY_" + self.profile.upper() + "_JOB_TIME_ACQUISITION", "returned": True,
            "retirement": "KNOWN", "errors": [], "admissionSha256": C.digest(self.admitted.record),
            "job": controller.job, "invocation": invocation,
            "clockDomain": J.RAW_CLOCK_DOMAIN if self.exact_clock is None else self.exact_clock.domain,
            "originalsSha256": {name: C.digest(raw) for name, raw in original.items()},
            "completedRawNs": 10001 * NS, "runnerName": D.F.RUNNER}
        if self.exact_clock is not None:
            clock = J.clock_value(self.exact_clock)
            start["clock"] = row["clock"] = returned["clock"] = clock
        start_raw, phase_raw, returned_raw = map(C.encoded, (start, row, returned))
        controller.write(phase, "start.json", start_raw, end)
        controller.write(phase, "result.json", phase_raw, end)
        for name, raw in original.items():
            controller.write(directory, name + ".json", raw, end)
        controller.write(controller.runtime, "job-time-result.json", returned_raw, end)
        budget = C.derive_job_budget(controller, controller.private, self.admitted, end)
        controller.write(directory, "child-return.json", returned_raw, end)
        controller.write(directory, "budget.json", budget.record, end)
        controller.budget, controller.clock = budget, self.exact_clock
        controller.phase_hashes["job-time"] = C.digest(phase_raw)
        controller.records.append(row)
        controller.deadline = min(controller.deadline, budget.deadline("controller-return", C.TOTAL_SECONDS[self.profile]))
        self.budget = budget

    def prepare(self, *, cancelled=None):
        def factory(profile, *, preflight):
            self.assertEqual(profile, self.profile)
            self.assertIs(preflight, True)
            value = Controller(profile, preflight=preflight)
            self.owners.append(value)
            self.prepared_controller = value
            return value
        with patch.object(C, "Controller", side_effect=factory), \
                patch.object(Controller, "acquire_job_time", new=lambda controller: self.acquire_job_time(controller)), \
                redirect_stdout(io.StringIO()):
            C.prepare_consume(self.profile, cancelled=cancelled)
        self.session = self.prepared_controller.path
        self.cache_dir = self.session / "evidence/dependency-cache"
        self.prepared_raw = (self.cache_dir / "preparation.json").read_bytes()
        self.prepared = C.parse(self.prepared_raw)
        self.plan = C.parse((self.cache_dir / "plan.json").read_bytes())
        self.stage_raw = (self.cache_dir / "staging.json").read_bytes()
        return self.prepared_controller

    def restore_environment(self):
        os.environ.update(P2PKIT_HOSTED_PREPARE_OUTCOME="success",
            P2PKIT_HOSTED_PREPARE_SHA256=C.digest(self.prepared_raw),
            P2PKIT_CACHE_RESTORE_OUTCOME="success", P2PKIT_CACHE_RESTORE_PRIMARY_KEY=self.plan["key"],
            P2PKIT_CACHE_RESTORE_MATCHED_KEY=self.plan["key"], P2PKIT_CACHE_RESTORE_HIT="true")
        self.output.write_bytes(b"")

    def guard(self, *, cancelled=None):
        with redirect_stdout(io.StringIO()):
            C.restore_guard(self.profile, cancelled=cancelled)

    def restored(self):
        self.prepare()
        self.restore_environment()
        self.clock.raw = 10020 * NS
        self.guard()
        self.restored_raw = (self.cache_dir / "restoration.json").read_bytes()
        self.restored_value = C.parse(self.restored_raw)
        os.environ.update(P2PKIT_CACHE_GUARD_OUTCOME="success",
                          P2PKIT_CACHE_RESTORATION_SHA256=C.digest(self.restored_raw))
        self.output.write_bytes(b"")

    def adopter(self):
        value = Controller(self.profile, consume_dependencies=True)
        self.owners.append(value)
        return value

    def adopt(self, controller=None):
        value = self.adopter() if controller is None else controller
        # A different process identity is explicit fixture data, not CI spoofing.
        with patch.object(C.os, "getpid", return_value=self.prepared["pid"] + 1):
            C.adopt_preparation(value)
        return value

    def binding(self, *, staging_raw=None):
        owner = self.owner()
        directory = owner.open(self.session)
        try:
            return C.consume_binding(owner, directory, self.admitted, self.budget, self.clock.local + 30,
                                     staging_raw=staging_raw)
        finally:
            owner.close()

    def change(self, name, mutate):
        path = self.cache_dir / name
        value = C.parse(path.read_bytes())
        mutate(value)
        raw = C.encoded(value)
        path.write_bytes(raw)
        return raw

    def assert_closed(self, owner):
        self.assertFalse(owner.unknown)
        self.assertTrue(all(row["attempted"] and row["closed"] for row in owner.resources))

    def seed_setup(self, controller):
        os.environ.update(P2PKIT_DEPENDENCY_SEED_STAGE_OUTCOME="success",
                          P2PKIT_DEPENDENCY_SEED_STAGE_SHA256=C.digest(self.stage_raw))
        controller.prepare_seed_intent()
        end = self.clock.local + 30
        state = controller.child(controller.private, "state", end, create=True)
        home = controller.child(state, "gradle-home", end, create=True)
        properties = b"org.gradle.workers.max=2\n"
        controller.write(home, "gradle.properties", properties, end)
        context = {"session": str(controller.path), "profile": self.profile, "role": self.role,
                   "source": C.parse(self.admitted.record)["source"], "dependencySeed": controller.seed_intent,
                   "dependencyCache": controller.cache_binding}
        controller.run_context_raw = C.encoded(context)
        controller.canonical_context_raw = C.encoded({"gradleHome": str(home.path),
                                                       "gradlePropertiesSha256": C.digest(properties)})
        controller.context_hash = C.digest(controller.run_context_raw)
        controller.write(controller.private, "run-context.json", controller.run_context_raw, end)

    def candidate(self, raw):
        directory = Path(self.plan["restoreHome"])
        path = directory.joinpath(*S.PREFIX, "org.fixture", "toy", "1.0", hashlib.sha1(raw).hexdigest(), "toy.jar")
        path.parent.mkdir(parents=True, mode=0o755, exist_ok=True)
        path.write_bytes(raw)
        path.chmod(0o644)
        return path


class PreparationModels(ConsumeBase):
    def test_preparation_runs_real_record_source_plan_and_original_budget_validation(self):
        controller = self.prepare()
        self.assertEqual(self.prepared["jobBudgetSha256"], self.budget.sha256)
        self.assertEqual(self.prepared["phaseResultSha256"], self.budget.value["provenance"]["phaseResultSha256"])
        self.assertEqual(self.prepared["completedRawNs"], self.prepared["restoreWindow"]["beganRawNs"])
        self.assertEqual(self.prepared["restoreWindow"]["endRawNs"], self.prepared["completedRawNs"] + 180 * NS)
        self.assertEqual(self.prepared["restoreWindow"]["timeoutMinutes"], 3)
        self.assertIsNone(controller.actions_token)
        self.assert_closed(controller)
        self.assertEqual(self.plan["mode"], "consume")
        output = self.output.read_text()
        self.assertIn("preparation_sha256=" + C.digest(self.prepared_raw) + "\n", output)
        self.assertFalse((self.cache_dir / "provider.json").exists())
        self.assertFalse((self.session / "state").exists())

    def test_preparation_cancellation_before_allocation_has_no_ready_output(self):
        with self.assertRaisesRegex(KeyboardInterrupt, "ORDINARY_TEST_CONTROLLER_CANCELLED"):
            self.prepare(cancelled=[15])
        self.assertEqual(self.output.read_bytes(), b"")
        self.assertIsNone(self.prepared_controller.actions_token)
        self.assert_closed(self.prepared_controller)
        self.assertEqual(list(self.runner.iterdir()), [])

    def test_preparation_late_close_cannot_renew_original120_second_local_window(self):
        close = Owner.close
        def late(controller):
            close(controller)
            self.clock.advance(121)
        with patch.object(Controller, "close", new=late), \
                self.assertRaisesRegex(C.posix.EvidenceError, "deadline"):
            self.prepare()
        self.assertEqual(self.output.read_bytes(), b"")
        self.assertLess(self.clock.raw, 10010 * NS + 180 * NS)
        self.assert_closed(self.prepared_controller)

    def test_preparation_output_flush_crossing_original_window_fails_after_provisional_bytes(self):
        fsync = os.fsync
        output_identity = self.output.stat().st_ino
        def late(fd):
            result = fsync(fd)
            if os.fstat(fd).st_ino == output_identity:
                self.clock.advance(121)
            return result
        with patch.object(os, "fsync", side_effect=late), \
                self.assertRaisesRegex(C.posix.EvidenceError, "deadline"):
            self.prepare()
        self.assertIn(b"dependency_seed_ready=true\n", self.output.read_bytes())
        self.assert_closed(self.prepared_controller)

    def test_preparation_unknown_retirement_cannot_emit_ready_output(self):
        close = Owner.close
        def unknown(controller):
            close(controller)
            controller.unknown = True
            raise C.ControllerError("SYNTHETIC_RETIREMENT_UNKNOWN")
        with patch.object(Controller, "close", new=unknown), \
                self.assertRaisesRegex(C.ControllerError, "SYNTHETIC_RETIREMENT_UNKNOWN"):
            self.prepare()
        self.assertEqual(self.output.read_bytes(), b"")
        self.assertTrue(self.prepared_controller.unknown)


class RestoreModels(ConsumeBase):
    def test_exact_success_is_only_metadata_restoration_not_byte_or_resolver_admission(self):
        self.restored()
        self.assertEqual(self.restored_value["observedRawNs"], 10020 * NS)
        self.assertEqual(self.restored_value["jobBudgetSha256"], self.budget.sha256)
        self.assertEqual(self.binding()["restoredAtRawNs"], 10020 * NS)
        self.assertEqual(list(Path(self.plan["restoreHome"]).iterdir()), [])
        self.assertFalse((self.session / "state").exists())
        for owner in self.owners:
            self.assert_closed(owner)

    def test_failed_cancelled_skipped_restore_outcomes_cannot_be_rescued_by_exact_hit_outputs(self):
        self.prepare()
        for outcome in ("failure", "cancelled", "skipped", ""):
            with self.subTest(outcome=outcome):
                self.restore_environment()
                os.environ["P2PKIT_CACHE_RESTORE_OUTCOME"] = outcome
                with self.assertRaisesRegex(C.ControllerError, "CACHE_NO_QUALIFIED_EXACT_HIT"):
                    self.guard()
                observed = C.parse((self.cache_dir / "provider.json").read_bytes())
                self.assertEqual(observed["originalOutcome"], outcome)
                self.assertEqual(observed["status"], "STEP_NOT_SUCCESSFUL")
                self.assertEqual(self.output.read_bytes(), b"")
                self.assertFalse((self.cache_dir / "restoration.json").exists())
                self.assert_closed(self.owners[-1])
                (self.cache_dir / "provider.json").unlink()

    def test_miss_prefix_or_wrong_primary_is_not_an_exact_hit_and_never_runs_cold(self):
        self.prepare()
        for field, value in (("P2PKIT_CACHE_RESTORE_HIT", "false"), ("P2PKIT_CACHE_RESTORE_HIT", ""),
                             ("P2PKIT_CACHE_RESTORE_MATCHED_KEY", "prefix-match"),
                             ("P2PKIT_CACHE_RESTORE_PRIMARY_KEY", "different-primary")):
            with self.subTest(field=field, value=value):
                self.restore_environment()
                os.environ[field] = value
                with self.assertRaisesRegex(C.ControllerError, "CACHE_NO_QUALIFIED_EXACT_HIT"):
                    self.guard()
                self.assertEqual(C.parse((self.cache_dir / "provider.json").read_bytes())["status"],
                                 "NO_QUALIFIED_EXACT_HIT")
                self.assertFalse((self.cache_dir / "restoration.json").exists())
                self.assertEqual(self.output.read_bytes(), b"")
                (self.cache_dir / "provider.json").unlink()

    def test_guard_preserves_preparation_clock_high_water_before_any_recovery(self):
        self.prepare()
        self.restore_environment()
        self.clock.sequence = [self.prepared["completedRawNs"] - NS, self.prepared["completedRawNs"] + NS]
        samples = len(self.clock.samples)
        with self.assertRaisesRegex(J._clocks().ClockError, "JOB_CLOCK_BACKWARDS"):
            self.guard()
        self.assertEqual(len(self.clock.samples) - samples, 1)
        self.assertEqual(self.output.read_bytes(), b"")
        self.assertFalse((self.cache_dir / "provider.json").exists())
        self.assert_closed(self.owners[-1])

    def test_original_restore_fence_is_not_restarted_by_new_guard_process(self):
        self.prepare()
        self.restore_environment()
        self.clock.raw = self.prepared["restoreWindow"]["endRawNs"]
        with self.assertRaisesRegex(C.ControllerError, "ORIGINAL_DELIVERY_WINDOW_EXPIRED"):
            self.guard()
        self.assertEqual(self.output.read_bytes(), b"")
        self.assertFalse((self.cache_dir / "provider.json").exists())

    def test_guard_cancellation_or_unretired_owner_never_authorizes_consume(self):
        self.prepare()
        self.restore_environment()
        with self.assertRaisesRegex(KeyboardInterrupt, "ORDINARY_TEST_CONTROLLER_CANCELLED"):
            self.guard(cancelled=[15])
        self.assertEqual(self.output.read_bytes(), b"")
        self.assertFalse((self.cache_dir / "restoration.json").exists())
        close = Owner.close
        def unknown(owner):
            close(owner)
            owner.unknown = True
            raise C.ControllerError("SYNTHETIC_RETIREMENT_UNKNOWN")
        with patch.object(Owner, "close", new=unknown), \
                self.assertRaisesRegex(C.ControllerError, "SYNTHETIC_RETIREMENT_UNKNOWN"):
            self.guard()
        self.assertEqual(self.output.read_bytes(), b"")
        self.assertTrue((self.cache_dir / "restoration.json").exists())
        # A provisional receipt from a failed step is not authority at adoption.
        os.environ["P2PKIT_CACHE_GUARD_OUTCOME"] = "failure"
        with self.assertRaisesRegex(C.ControllerError, "CACHE_ORIGINAL_STEPS_REQUIRED"):
            C.adopt_preparation(self.adopter())

    def test_guard_rejects_original_output_hash_source_and_role_replay(self):
        self.prepare()
        original = self.prepared_raw
        mutations = (lambda v: v["source"].update(commit="c" * 40), lambda v: v.update(role="macos-x64"),
                     lambda v: v["github"].update(runAttempt="2"))
        for mutate in mutations:
            with self.subTest(mutate=mutate):
                (self.cache_dir / "preparation.json").write_bytes(original)
                changed = self.change("preparation.json", mutate)
                self.restore_environment()
                os.environ["P2PKIT_HOSTED_PREPARE_SHA256"] = C.digest(changed)
                with self.assertRaisesRegex(C.ControllerError, "CACHE_ORIGINAL_PREPARATION_CHANGED"):
                    self.guard()
                self.assertEqual(self.output.read_bytes(), b"")
        (self.cache_dir / "preparation.json").write_bytes(original)
        self.restore_environment()
        os.environ["P2PKIT_HOSTED_PREPARE_SHA256"] = "0" * 64
        with self.assertRaisesRegex(C.ControllerError, "CACHE_PREPARATION_OUTPUT_CHANGED"):
            self.guard()


class BindingAdoptionModels(ConsumeBase):
    def test_binding_and_adoption_keep_original_budget_and_new_owner_identity(self):
        self.restored()
        self.clock.raw = 10021 * NS
        controller = self.adopt()
        self.assertEqual(controller.cache_binding, self.binding(staging_raw=self.stage_raw))
        self.assertEqual(controller.budget.record, self.budget.record)
        self.assertNotEqual(controller.job, self.prepared["job"])
        self.assertEqual(controller.records[0]["job"], self.prepared["job"])
        self.assertEqual(controller.phase_hashes["job-time"], self.prepared["phaseResultSha256"])
        self.assertGreaterEqual(controller.last_raw, self.restored_value["observedRawNs"])
        self.assertTrue(any(path.endswith("/adoption-admission") for path in self.admissions))
        controller.close()
        self.assert_closed(controller)

    def test_adoption_rejects_backward_entry_below_restoration_even_above_preparation(self):
        self.restored()
        self.clock.sequence = [self.restored_value["observedRawNs"] - NS, self.restored_value["observedRawNs"] + NS]
        samples = len(self.clock.samples)
        with self.assertRaisesRegex(J._clocks().ClockError, "JOB_CLOCK_BACKWARDS"):
            self.adopt()
        self.assertEqual(len(self.clock.samples) - samples, 1)
        self.assertFalse(any(path.endswith("/adoption-admission") for path in self.admissions))

    def test_adoption_requires_original_success_and_matching_output_hashes(self):
        self.restored()
        for key in ("P2PKIT_HOSTED_PREPARE_OUTCOME", "P2PKIT_CACHE_GUARD_OUTCOME"):
            for outcome in ("failure", "cancelled", "skipped", ""):
                with self.subTest(key=key, outcome=outcome), patch.dict(os.environ, {key: outcome}), \
                        self.assertRaisesRegex(C.ControllerError, "CACHE_ORIGINAL_STEPS_REQUIRED"):
                    self.adopt()
        for key, code in (("P2PKIT_HOSTED_PREPARE_SHA256", "CACHE_PREPARATION_REPLAYED_OR_CHANGED"),
                          ("P2PKIT_CACHE_RESTORATION_SHA256", "CACHE_ORIGINAL_RESTORE_OUTPUT_CHANGED")):
            with self.subTest(key=key), patch.dict(os.environ, {key: "0" * 64}), \
                    self.assertRaisesRegex(C.ControllerError, code):
                self.adopt()

    def test_adoption_never_reuses_producer_pid_or_job(self):
        self.restored()
        controller = self.adopter()
        with self.assertRaisesRegex(C.ControllerError, "CACHE_PREPARATION_REPLAYED_OR_CHANGED"):
            C.adopt_preparation(controller)
        other = self.adopter()
        other.job = self.prepared["job"]
        with self.assertRaisesRegex(C.ControllerError, "CACHE_PREPARATION_REPLAYED_OR_CHANGED"):
            self.adopt(other)

    def test_binding_rejects_original_stage_and_direct_plan_stage_reread_changes(self):
        self.restored()
        with self.assertRaisesRegex(C.ControllerError, "CACHE_RESTORED_STAGE_CHANGED"):
            self.binding(staging_raw=b"different-stage")
        for name in ("plan.json", "staging.json"):
            original = (self.cache_dir / name).read_bytes()
            with self.subTest(name=name):
                self.change(name, lambda value: value.update(profile="full"))
                with self.assertRaisesRegex(C.ControllerError, "CACHE_PREPARATION_INPUT_CHANGED"):
                    self.binding()
                (self.cache_dir / name).write_bytes(original)

    def test_binding_rejects_validly_encoded_but_forged_restoration_or_provider(self):
        self.restored()
        path = self.cache_dir / "restoration.json"
        original = path.read_bytes()
        for change in (lambda v: v.update(preparationSha256="0" * 64),
                       lambda v: v.update(jobBudgetSha256="0" * 64),
                       lambda v: v["source"].update(tree="d" * 40),
                       lambda v: v.update(retirement="UNKNOWN"),
                       lambda v: v.update(observedRawNs=self.prepared["completedRawNs"] - 1),
                       lambda v: v.update(observedRawNs=self.prepared["restoreWindow"]["endRawNs"]),
                       lambda v: v.update(observedRawNs=True)):
            with self.subTest(change=change):
                path.write_bytes(original)
                self.change("restoration.json", change)
                with self.assertRaisesRegex(C.ControllerError, "CACHE_ORIGINAL_RESTORE_RECEIPT_CHANGED"):
                    self.binding()
        path.write_bytes(original)
        self.change("provider.json", lambda value: value.update(originalOutcome="failure"))
        with self.assertRaisesRegex(S.SeedError, "CACHE_OBSERVATION_CHANGED_OR_REPLAYED"):
            self.binding()

    def test_binding_reread_is_anchored_even_when_all_new_dependent_receipts_agree(self):
        self.restored()
        stage = C.parse(self.stage_raw)
        stage["sourceIdentity"][1] += 100000
        stage_raw = S.encoded(stage)
        compiled = S.authority.parse_allowlist((self.root / S.INPUTS[0]).read_bytes())
        plan = K.make_plan(self.admitted.record, stage_raw, compiled, self.plan["inputs"],
                          session=self.session, profile=self.profile, role=self.role, mode="consume")
        plan_raw = C.encoded(plan)
        provider = K.provider_observation(plan, "restore", original_outcome="success", outputs={
            "cache-primary-key": plan["key"], "cache-matched-key": plan["key"], "cache-hit": "true"})
        provider_raw = C.encoded(provider)
        restoration = {**self.restored_value, "planSha256": C.digest(plan_raw),
                       "stagingSha256": C.digest(stage_raw), "providerSha256": C.digest(provider_raw)}
        # This second set is semantically consistent, not just an invalid plan.
        self.assertEqual(K.validate_plan(plan, self.admitted.record, stage_raw, compiled, self.plan["inputs"],
            session=self.session, profile=self.profile, role=self.role, mode="consume"), plan)
        self.assertEqual(K.validate_provider_observation(provider, plan, "restore"), provider)
        changed = []
        original_read = Owner.read
        phase_path = self.session / "evidence/commands/job-time"
        def changing(owner, directory, name, end, maximum=C.RECORD_LIMIT):
            raw = original_read(owner, directory, name, end, maximum)
            if directory.path == phase_path and name == "result.json" and not changed:
                # The reader has validated the first plan/stage and preparation.
                # Actually replace the tiny files before consume_binding rereads.
                for member, value in (("plan.json", plan_raw), ("staging.json", stage_raw),
                                      ("provider.json", provider_raw), ("restoration.json", C.encoded(restoration))):
                    (self.cache_dir / member).write_bytes(value)
                changed.append(True)
            return raw
        with patch.object(Owner, "read", new=changing), \
                self.assertRaisesRegex(C.ControllerError, "CACHE_PREPARATION_INPUT_CHANGED"):
            self.binding()
        self.assertEqual(changed, [True])
        self.assertEqual((self.cache_dir / "plan.json").read_bytes(), plan_raw)

    def test_original_clock_preserves_maximum_and_rejects_non_integer_predecessors(self):
        self.restored()
        clock = C.original_clock(self.budget, self.restored_value["observedRawNs"], self.prepared["completedRawNs"])
        self.assertEqual(clock.last, self.restored_value["observedRawNs"])
        for invalid in (True, 1.0, -1, J.UINT64 + 1, self.budget.value["responseFinishedRawNs"] - 1):
            with self.subTest(invalid=invalid), self.assertRaisesRegex(C.ControllerError, "ORIGINAL_CLOCK_OBSERVATION"):
                C.original_clock(self.budget, invalid)


class FrozenConsumeModels(ConsumeBase):
    def packet(self):
        """Real original-record/copy readers around explicitly synthetic phases."""
        self.restored()
        controller = self.adopt()
        end = self.clock.local + 30
        context = {"profile": self.profile, "role": self.role, "session": str(self.session),
            "source": C.parse(self.admitted.record)["source"], "job": controller.job,
            "jobBudgetSha256": self.budget.sha256, "jobTimeAcquisitionSha256": C.digest(self.prepared_raw),
            "dependencyCache": controller.cache_binding}
        context_raw = C.encoded(context)
        controller.write(controller.private, "run-context.json", context_raw, end)
        directory = C.cache_directory(controller, controller.private, end)
        controller.write(directory, "controller-context.json", context_raw, end)
        phase = controller.child(controller.commands, "job-time", end)
        for name, raw in (("baseline.json", C.encoded({"scope": "SYNTHETIC_NATIVE_BASELINE"})),
                          ("stdout.log", b"SYNTHETIC JOB TIME LOG; NO API REQUEST EXECUTED\n"),
                          ("stderr.log", b"")):
            controller.write(phase, name, raw, end)
        controller.write(controller.evidence, "profile-result-before-export.json", C.encoded({
            "contextSha256": C.digest(context_raw), "dependencyCache": controller.cache_binding}), end)
        frozen = self.session / "frozen-evidence"
        C.copy_tree(controller, controller.evidence, frozen, end)
        return controller, context_raw, frozen, end

    def test_frozen_consume_binds_real_original_records_to_the_exact_flat_copies(self):
        controller, context_raw, frozen, end = self.packet()
        result = C.frozen_consume_packet(controller, controller.private, end, controller.check)
        expected = {"dependency-cache/" + name + ".json" for name in
                    ("plan", "staging", "preparation", "provider", "restoration", "controller-context")}
        expected |= {"job-time/" + name + ".json" for name in ("attempt", "jobs", "child-return", "budget")}
        expected |= {"commands/job-time/" + name for name in
                     ("start.json", "result.json", "baseline.json", "stdout.log", "stderr.log")}
        expected.add("profile-result-before-export.json")
        self.assertEqual(result["contextSha256"], C.digest(context_raw))
        self.assertEqual(result["binding"], controller.cache_binding)
        self.assertEqual(result["mapSha256"], C.digest((frozen / "original-path-map.json").read_bytes()))
        self.assertEqual([row["original"] for row in result["files"]], sorted(expected))
        for row in result["files"]:
            original = (controller.evidence.path / row["original"]).read_bytes()
            self.assertEqual((row["size"], row["sha256"]), (len(original), C.digest(original)))
            self.assertEqual((frozen / row["member"]).read_bytes(), original)
        controller.close()
        self.assert_closed(controller)

    def test_coherent_original_and_copy_map_substitution_cannot_replace_validated_binding(self):
        controller, _context_raw, frozen, end = self.packet()
        original_binding = C.consume_binding
        changes = []

        def substitute(*args, **kwargs):
            bound = original_binding(*args, **kwargs)
            self.assertEqual(changes, [])
            restored = dict(self.restored_value, observedRawNs=self.restored_value["observedRawNs"] + 1)
            changed = C.encoded(restored)
            self.assertLess(restored["observedRawNs"], self.prepared["restoreWindow"]["endRawNs"])
            self.assertNotEqual(C.digest(changed), bound["restorationSha256"])
            (self.cache_dir / "restoration.json").write_bytes(changed)
            map_path = frozen / "original-path-map.json"
            mapping = C.parse(map_path.read_bytes())
            row = next(row for row in mapping["files"] if row["original"] == "dependency-cache/restoration.json")
            row.update(size=len(changed), sha256=C.digest(changed))
            (frozen / row["member"]).write_bytes(changed)
            map_raw = C.encoded(mapping)
            map_path.write_bytes(map_raw)
            self.assertEqual(C.seed_copy_map(map_raw, controller.evidence.path), mapping)
            changes.append(changed)
            return bound

        with patch.object(C, "consume_binding", side_effect=substitute), \
                self.assertRaisesRegex(C.ControllerError, "CACHE_VALIDATED_ORIGINALS_CHANGED_BEFORE_FREEZE"):
            C.frozen_consume_packet(controller, controller.private, end, controller.check)
        self.assertEqual(len(changes), 1)
        # The changed restoration is itself valid. Rejection above came from
        # the original validated binding, not a malformed replacement or map.
        rebound = original_binding(controller, controller.private, self.admitted, self.budget, end)
        self.assertEqual(rebound["restorationSha256"], C.digest(changes[0]))
        self.assertNotEqual(rebound, controller.cache_binding)
        controller.close()
        self.assert_closed(controller)


class SeedAdmissionModels(ConsumeBase):
    def test_exact_provider_hit_but_empty_restore_fails_real_seed_boundary_before_product(self):
        self.restored()
        controller = self.adopt()
        self.seed_setup(controller)
        with self.assertRaisesRegex(C.ControllerError, "CACHE_EXACT_HIT_WITHOUT_ADMITTED_BYTES"):
            controller.seed_dependencies()
        raw = (controller.seed_directory.path / "manifest.json").read_bytes()
        value = S.record(raw)
        self.assertEqual(value["admitted"], [])
        self.assertEqual(value["status"], "KNOWN_MISS")
        self.assertEqual(value["counts"]["outputBytes"], 0)
        self.assertFalse(controller.product_attempted)

    def test_hash_rejected_restore_also_fails_real_seed_boundary(self):
        self.restored()
        self.candidate(b"wrong toy bytes")
        controller = self.adopt()
        self.seed_setup(controller)
        with self.assertRaisesRegex(C.ControllerError, "CACHE_EXACT_HIT_WITHOUT_ADMITTED_BYTES"):
            controller.seed_dependencies()
        value = S.record((controller.seed_directory.path / "manifest.json").read_bytes())
        self.assertEqual(value["admitted"], [])
        self.assertEqual(value["counts"]["sha256Rejected"], 1)
        self.assertFalse(controller.product_attempted)

    def test_positive_allowlisted_bytes_are_copied_without_running_loader_or_product(self):
        self.restored()
        original = self.candidate(self.payload)
        controller = self.adopt()
        self.seed_setup(controller)
        controller.seed_dependencies()
        value = S.record((controller.seed_directory.path / "manifest.json").read_bytes())
        self.assertEqual(value["status"], "KNOWN_SEEDED")
        self.assertEqual(value["counts"]["outputBytes"], len(self.payload))
        self.assertEqual(len(value["admitted"]), 1)
        destination = controller.state_path / "gradle-home" / value["admitted"][0]["path"]
        self.assertEqual(destination.read_bytes(), original.read_bytes())
        self.assertNotEqual(destination.stat().st_ino, original.stat().st_ino)
        self.assertFalse(controller.product_attempted)
        self.assertEqual(controller.seed_result["admittedBytes"], len(self.payload))

    def test_zero_length_allowlisted_file_does_not_satisfy_positive_bytes(self):
        self.payload = b""
        self.source_inputs()
        self.restored()
        self.candidate(b"")
        controller = self.adopt()
        self.seed_setup(controller)
        with self.assertRaisesRegex(C.ControllerError, "CACHE_EXACT_HIT_WITHOUT_ADMITTED_BYTES"):
            controller.seed_dependencies()
        value = S.record((controller.seed_directory.path / "manifest.json").read_bytes())
        self.assertEqual(value["counts"]["outputBytes"], 0)
        self.assertEqual(sum(row["size"] for row in value["admitted"]), 0)
        self.assertFalse(controller.product_attempted)


class FullOriginalClockModels(ConsumeBase):
    profile = "full"

    def test_full_original_preparation_clock_also_refuses_backward_guard_entry(self):
        self.prepare()
        self.restore_environment()
        self.assertIsNone(self.budget.clock)
        self.assertEqual(J.RESERVE_SECONDS, 2430)
        self.clock.sequence = [self.prepared["completedRawNs"] - NS, self.prepared["completedRawNs"] + NS]
        with self.assertRaisesRegex(J.BudgetError, "JOB_TIME_INTEGER"):
            self.guard()
        self.assertEqual(self.output.read_bytes(), b"")
        self.assertFalse((self.cache_dir / "provider.json").exists())


if __name__ == "__main__":
    unittest.main()
