#!/usr/bin/env python3
"""Focused DATA/owner-model controls; no version probe, service or native run.

Native-looking rows below are explicitly supplied models. Passing this suite
does NOT qualify the actual hosted tool/path/retirement or provider behavior.
"""
from __future__ import annotations

import base64
from contextlib import contextmanager
import copy
import hashlib
import json
from pathlib import Path, PureWindowsPath
import stat
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
import hosted_cache_provider_tools as T
import hosted_cache_provider_return as R
import hosted_cache_provider_worker as W


def encoded(value):
    return T.canonical(value) + b"\n"


def model_bindings(role):
    return {name: hashlib.sha256(("MODEL_SOURCE:" + name).encode()).hexdigest() for name in W.names(role)}


def native(role, index, *, directory=False, link=False):
    if role == "windows-x64":
        return dict(identity=[1, format(index, "032x")], is_directory=directory, size=4096 if directory else 42,
            links=1, attributes=16 if directory else 128, creation_100ns=1, modified_100ns=2,
            change_100ns=3, owner_sid=None, protected_dacl=None)
    return dict(identity=[1, index], is_directory=directory, size=4096 if directory else 42,
        mode=(stat.S_IFDIR | 0o755 if directory else stat.S_IFLNK | 0o777 if link else stat.S_IFREG | 0o755),
        uid=1001, links=2 if directory else 1, mtime_ns=1, ctime_ns=2)


def retirement(frame, invocation, argv, scripts, *, pid=200):
    """Complete supplied DATA, never an actual process or retirement."""
    role, windows = frame["role"], frame["role"] == "windows-x64"
    launch = {"api": "CreateProcessW" if windows else "subprocess.Popen", "requestedArgv": argv,
        "resolvedArgv": argv.copy(), "cwd": str(scripts.parent), "created": True, "pid": pid,
        "outputMode": "caller-owned-native-files" if windows else "caller-owned-files"}
    if windows:
        launch.update(resumed=True, batch=False, applicationName=argv[0], commandLine=T.subprocess.list2cmdline(argv),
            jobAssignedBeforeResume=True, resourceCleanup=[{"phase": "launch-temporary", "resource": "primary-thread", "status": "RETIRED"}])
    else:
        launch.update(shell=False, executable=argv[0])
    value = {"backend": "windows-job-list-suspended" if windows else
        "linux-proc-pidfd" if role == "linux-x64" else "darwin-libproc-audit-token",
        "scope": "kernel-job-no-breakaway-kill-on-close" if windows else "controlled-marker-inheriting-descendants",
        "invocation": invocation, "job": frame["job"], "launches": [launch], "discoveryErrors": [],
        "startedIdentities": [{"pid": pid, "creationFileTime": 1, "jobAssignedBeforeResume": True}] if windows else []}
    if not windows:
        value["discoveryReconciliations"] = []
    if role.startswith("macos-"):
        value.update(observationReconciliations=[], drainReconciliations=[{
            "startedMonotonic": 100.0, "graceSeconds": 5.0, "killWaitSeconds": 5.0,
            "absoluteDeadlineMonotonic": 250.0, "finishedMonotonic": 100.3,
            "phases": [{"signal": 15, "deadlineMonotonic": 105.0}], "signalReconciliations": [], "outcome": "retired"}])
    return value


@contextmanager
def fixture(role="linux-x64", phase="save", compression="zstd-without-long"):
    """Supply a complete tools record while stubbing ONLY the plan contract.

    Real bootstrap/consume contract controls remain a separate suite. No native
    acquisition, executable read, process, runtime service or clock is invoked.
    """
    windows = role == "windows-x64"
    scripts = PureWindowsPath(r"C:\source\scripts") if windows else SCRIPTS
    root = PureWindowsPath(r"C:\tools") if windows else Path("/tools")
    private = PureWindowsPath(r"C:\private") if windows else Path("/private")
    name = lambda tool: str(root / (tool + ".exe" if windows else tool))
    python, node = name("python3"), name("node")
    frame = dict(schema=1, role=role, frequency=10_000_000 if windows else 1_000_000_000,
        issuedNs=str(100 * T.clocks.NS), hardEndNs=str(280 * T.clocks.NS), workerCutoffNs=str(250 * T.clocks.NS),
        phase=phase, job="1" * 32, outerId="2" * 32, innerId="3" * 32,
        directory=str(private / "provider"), home=str(private / "provider-home"),
        directoryIdentity=[1, "a" * 32 if windows else 10], homeIdentity=[1, "b" * 32 if windows else 11],
        captureIdentity=[1, "c" * 32 if windows else 12], node=node, toolPath=str(root),
        systemRoot=r"C:\Windows" if windows else None,
        plan={"role": role, "path": str(private / "dependencies"), "key": "MODEL_KEY_NOT_SERVICE_DATA"}, prefix=[])
    frame["prefix"] = [[frame["outerId"], frame["job"], frame["directory"], frame["home"]]]
    request, bindings = T.canonical(frame), model_bindings(role)
    contract = {"bundle": {"sha256": "f" * 64}}
    with patch.object(T, "SCRIPTS", scripts), patch.object(T.cache, "_native_provider_contract", return_value=contract):
        _parsed, context = T._context(request, bindings)
        selected, rows, candidates, links = dict.fromkeys(T.TOOLS), [], [], []
        def select(tool, literal, path, *, ordinal=0, alias=None):
            index = len(rows) if alias is None else alias
            selected[tool] = index
            if alias is None:
                info = native(role, index + 101)
                passes = {}
                for label, start in (("initial", 101), ("prelaunch", 130), ("postProvider", 181)):
                    passes[label] = {"startedNs": str(start * T.clocks.NS), "endedNs": str((start + 1) * T.clocks.NS),
                        "native": copy.deepcopy(info), "bytes": info["size"], "sha256": format(index + 1, "064x")}
                rows.append(dict(id=index, tools=[tool], requestedPath=path, resolvedPath=path, aliasFamily="NONE", **passes))
            else:
                rows[index]["tools"] = sorted([*rows[index]["tools"], tool])
                rows[index]["aliasFamily"] = "ZSTD_ALIASES"
                if not windows:
                    links.append({"path": path, "target": "zstd", "native": native(role, 400, link=True)})
            candidates.append(dict(tool=tool, literal=literal, path=path, pathEntry=ordinal, status="SELECTED", executable=index))
            return index
        select("python", python, python, ordinal=None)
        select("node", node, node, ordinal=None)
        zstd = select("zstd", "zstd", name("zstd"))
        flavor = None if phase == "lookup" else "GNU"
        if phase != "lookup":
            if windows:
                for literal in (r"undefined\Git\usr\bin\tar.exe", r"undefined\Windows\System32\tar.exe"):
                    candidates.append(dict(tool="tar", literal=literal, path=str(scripts.parent / literal),
                                           pathEntry=None, status="ABSENT", executable=None))
            literal = "gtar" if role.startswith("macos-") else "tar"
            select("tar", literal, name(literal))
        mode = T._expected_mode(role, phase, compression, flavor)
        if mode not in ("LOOKUP_ONLY", "BSD_TAR_GZIP"):
            compressor = {"GNU_GZIP": "gzip", "POSIX_ZSTDMT": "zstdmt", "POSIX_UNZSTD": "unzstd",
                "WINDOWS_ZSTD_CREATE": "zstd", "WINDOWS_ZSTD_EXTRACT": "zstd"}[mode]
            select("compressor", compressor, name(compressor), alias=None if compression == "gzip" else zstd)
        probes = []
        roster = [("NODE_VERSION", selected["node"]), ("ZSTD_VERSION", zstd)]
        if phase != "lookup":
            roster.append(("TAR_VERSION", selected["tar"]))
        if selected["compressor"] is not None and selected["compressor"] != zstd:
            roster.append(("COMPRESSOR_VERSION", selected["compressor"]))
        for ordinal, (purpose, index) in enumerate(roster):
            invocation = format(ordinal + 100, "032x")
            argv = T._command(purpose, rows[index]["requestedPath"], compression)
            native_record = retirement(frame, invocation, argv, scripts, pid=ordinal + 200)
            out = {"NODE_VERSION": b"v24.1.0\n", "ZSTD_VERSION": b"zstd 1.5.7\n" if compression != "gzip" else b" \n",
                   "TAR_VERSION": b"tar (GNU tar) 1.35\n", "COMPRESSOR_VERSION": b"gzip 1.14\n"}[purpose]
            start = (105 + ordinal * 3) * T.clocks.NS
            probes.append({"purpose": purpose, "executable": index, "invocation": invocation,
                "firstNs": str(start), "returnedNs": str(start + T.clocks.NS), "closedNs": str(start + 2 * T.clocks.NS),
                "exitCode": 0, "stdout": base64.b64encode(out).decode(), "stderr": "",
                "nativeRetirement": base64.b64encode(encoded(native_record)).decode(), "closedResources": list(T.PROBE_RESOURCES)})
        value = {"schema": 1, "scope": T.SCOPE, "context": context,
            "resolution": {"environment": T._public_environment(frame), "pathEntries": [{"path": str(root), "native": native(role, 5, directory=True)}],
                "candidates": candidates, "symlinks": links, "selected": selected, "compression": compression,
                "tarFlavor": flavor, "compressorMode": mode}, "executables": rows, "probes": probes,
            "chronology": {"firstNs": str(100 * T.clocks.NS), "prelaunchNs": str(140 * T.clocks.NS),
                "providerClosedNs": str(180 * T.clocks.NS), "postCheckNs": str(190 * T.clocks.NS), "closedNs": str(195 * T.clocks.NS),
                "publicBytes": sum(row["initial"]["bytes"] * 3 for row in rows), "resourceCount": 100,
                "state": "TOOLS_KNOWN_CLOSED_PENDING_WORKER_RETURN"}}
        supplier_argv = [node, str(private / "provider" / "provider.cjs")]
        yield SimpleNamespace(value=value, request=request, bindings=bindings, python=python, frame=frame,
            supplier_native=encoded(retirement(frame, frame["innerId"], supplier_argv, scripts)),
            decode=lambda raw: T.decode(raw, request, bindings=bindings, python=python))


class SelectorControls(unittest.TestCase):
    def test_zstd_both_complete_streams_choose_exact_supplier_branch(self):
        for out, err, expected in ((b"", b"zstd 1.5.7\n", "zstd-without-long"),
                (b" \r\n", b"\t\v\f", "gzip"), (b"", b"", "gzip"), (b"\x1c", b"", "zstd-without-long"),
                (b"", b"\x1d\x1e\x1f", "zstd-without-long")):
            with self.subTest(out=out, err=err):
                self.assertEqual(T.compression_from_streams(out, err), expected)

    def test_zstd_nonascii_or_oversize_is_not_guessed(self):
        for out, err in ((b"\xff", b""), (b"", b"\xc2\xa0"), (b"x" * 4097, b"")):
            with self.subTest(size=len(out)), self.assertRaises(T.ProviderToolsError):
                T.compression_from_streams(out, err)

    def test_windows_gnu_tar_uses_one_nonempty_original_stream(self):
        self.assertTrue(T.windows_gnu_tar(b"", b"\tTAR (GNU TAR) 1.35\r\n"))
        self.assertFalse(T.windows_gnu_tar(b"bsdtar 3.8\n", b""))
        for out, err in ((b"GNU tar", b" "), (b"GNU", b" tar"), (b"", b"")):
            with self.subTest(out=out, err=err), self.assertRaises(T.ProviderToolsError):
                T.windows_gnu_tar(out, err)

    def test_cache_version_uses_literal_path_compression_platform_and_salt(self):
        for role, path in (("linux-x64", "/tmp/exact/files-2.1"), ("macos-arm64", "/tmp/exact/files-2.1"),
                           ("windows-x64", r"D:\exact\files-2.1")):
            for compression in ("gzip", "zstd-without-long"):
                pieces = [path, compression, *(["windows-only"] if role == "windows-x64" else []), "1.0"]
                self.assertEqual(T.cache.provider_cache_version(path, compression, role), hashlib.sha256("|".join(pieces).encode()).hexdigest())
        with self.assertRaises(T.cache.files.SeedError):
            T.cache.provider_cache_version("/tmp/files-2.1", "zstd", "linux-x64")

    def test_posix_selector_keeps_primary_gid_and_real_uid_not_access_shortcut(self):
        owner = object.__new__(T.ToolObserver)
        owner.frame, owner._uid, owner._gid = {"role": "linux-x64"}, 1001, 2001
        for mode, uid, gid, expected in ((0o001, 0, 0, True), (0o010, 0, 2001, True),
                (0o010, 0, 3001, False), (0o100, 1001, 0, True), (0o100, 0, 2001, False), (0, 1001, 2001, False)):
            info = SimpleNamespace(mode=stat.S_IFREG | mode, uid=uid)
            self.assertEqual(owner._executable((Path("/tools/model"), info, gid, None)), expected)


class ToolsDataControls(unittest.TestCase):
    def test_exact_models_cover_all_four_roles_and_three_phases(self):
        for role in ("linux-x64", "macos-arm64", "macos-x64", "windows-x64"):
            for phase in ("save", "lookup", "restore"):
                with self.subTest(role=role, phase=phase), fixture(role, phase) as f:
                    actual = f.decode(encoded(f.value))
                    self.assertEqual(actual, f.value)
                    self.assertEqual(actual["context"]["observation"], T.OBSERVATION)

    def test_known_nonzero_zstd_exit_keeps_nonempty_selection(self):
        with fixture() as f:
            row = f.value["probes"][1]
            row.update(exitCode=19, stdout="", stderr=base64.b64encode(b"zstd version\n").decode())
            self.assertEqual(f.decode(encoded(f.value))["resolution"]["compression"], "zstd-without-long")

    def test_gzip_branch_keeps_mandatory_real_compressor_record(self):
        with fixture(compression="gzip") as f:
            self.assertEqual(f.decode(encoded(f.value))["resolution"]["compressorMode"], "GNU_GZIP")
            f.value["probes"].pop()
            with self.assertRaises(T.ProviderToolsError):
                f.decode(encoded(f.value))

    def test_request_source_bundle_or_environment_substitution_refuses(self):
        with fixture() as f:
            for field in ("requestSha256", "sourceMapSha256", "providerBundleSha256"):
                changed = copy.deepcopy(f.value)
                changed["context"][field] = "e" * 64
                with self.subTest(field=field), self.assertRaises(T.ProviderToolsError):
                    f.decode(encoded(changed))
            changed = copy.deepcopy(f.value)
            changed["resolution"]["environment"]["ACTIONS_RUNTIME_TOKEN"] = "MODEL_FORBIDDEN"
            with self.assertRaises(T.ProviderToolsError):
                f.decode(encoded(changed))

    def test_duplicate_noncanonical_extra_and_oversized_record_refuse(self):
        with fixture() as f:
            raw = encoded(f.value)
            for changed in (raw[:-1], b" " + raw, raw.replace(b"{", b'{"schema":1,', 1),
                    encoded({**f.value, "unexpected": True}), b"x" * (T.MAX_BYTES + 1)):
                with self.subTest(length=len(changed)), self.assertRaises(T.ProviderToolsError):
                    f.decode(changed)

    def test_all_three_native_hash_size_and_close_bindings_are_mandatory(self):
        with fixture() as f:
            changes = (("prelaunch", "sha256", "e" * 64), ("postProvider", "bytes", 41), ("postProvider", "endedNs", "0"))
            for phase, field, replacement in changes:
                changed = copy.deepcopy(f.value)
                changed["executables"][0][phase][field] = replacement
                with self.subTest(phase=phase, field=field), self.assertRaises(T.ProviderToolsError):
                    f.decode(encoded(changed))
            changed = copy.deepcopy(f.value)
            changed["probes"][0]["closedResources"].pop()
            with self.assertRaises(T.ProviderToolsError):
                f.decode(encoded(changed))

    def test_search_order_early_absence_and_extra_candidates_cannot_be_relabelled(self):
        with fixture() as f:
            for edit in (lambda value: value["resolution"]["candidates"][2].update(pathEntry=True),
                         lambda value: value["resolution"]["candidates"].append(copy.deepcopy(value["resolution"]["candidates"][2])),
                         lambda value: value["resolution"]["pathEntries"].clear()):
                changed = copy.deepcopy(f.value)
                edit(changed)
                with self.assertRaises(T.ProviderToolsError):
                    f.decode(encoded(changed))

    def test_cross_tool_alias_wrong_native_argv_and_wrong_raw_epoch_refuse(self):
        with fixture() as f:
            for mutation in ("alias", "argv", "clock"):
                changed = copy.deepcopy(f.value)
                if mutation == "alias":
                    changed["executables"][0]["tools"] = ["node", "python"]
                elif mutation == "clock":
                    changed["context"]["clock"]["domain"] = "MODEL_OTHER_EPOCH"
                else:
                    row = changed["probes"][0]
                    native_value = json.loads(base64.b64decode(row["nativeRetirement"]))
                    native_value["launches"][0]["requestedArgv"].append("MODEL_EXTRA_ARGUMENT")
                    row["nativeRetirement"] = base64.b64encode(encoded(native_value)).decode("ascii")
                with self.subTest(mutation=mutation), self.assertRaises(T.ProviderToolsError):
                    f.decode(encoded(changed))

    def test_v2_packet_requires_tools_and_rejects_stale_v1(self):
        with fixture() as f:
            capture = R.lifecycle.CapturedProvider("save", 0, b"", b"", b"", f.supplier_native, (),
                180 * T.clocks.NS, R.lifecycle.ProviderCapture._NAMES)
            packet = R.encode(capture, f.request, encoded(f.value), bindings=f.bindings, python=f.python)
            ack = R.read_ack(R.acknowledge(packet, (1, 88), f.request), f.request)
            result = R.decode(packet, ack, f.request, 0, bindings=f.bindings, python=f.python)
            self.assertEqual(result.tools, encoded(f.value))
            self.assertEqual(result.scope, "TRANSPORTED_PROVIDER_CAPTURE_ONLY_V2")
            self.assertEqual(result.tools_closed_ns, 195 * T.clocks.NS)
            for mutation in ("old", "missing"):
                value = json.loads(packet)
                if mutation == "old":
                    value["schema"] = "P2PKIT_PROVIDER_RETURN_V1"
                else:
                    value.pop("tools")
                changed = encoded(value)
                changed_ack = R.read_ack(R.acknowledge(changed, (1, 88), f.request), f.request)
                with self.assertRaises(R.ProviderReturnError):
                    R.decode(changed, changed_ack, f.request, 0, bindings=f.bindings, python=f.python)

    def test_inner_supplier_native_is_not_substituted_by_valid_tool_probes(self):
        with fixture() as f:
            for mutation in ("invocation", "argv", "scope", "opaque"):
                value = json.loads(f.supplier_native)
                if mutation == "invocation":
                    value["invocation"] = "f" * 32
                elif mutation == "argv":
                    value["launches"][0]["requestedArgv"].append("MODEL_OTHER_EXECUTION")
                elif mutation == "scope":
                    value["scope"] = "MODEL_UNOWNED"
                else:
                    value = {"model": "NOT_A_NATIVE_DESCRIPTION"}
                capture = R.lifecycle.CapturedProvider("save", 0, b"", b"", b"", encoded(value), (),
                    180 * T.clocks.NS, R.lifecycle.ProviderCapture._NAMES)
                with self.subTest(mutation=mutation), self.assertRaises(T.ProviderToolsError):
                    R.encode(capture, f.request, encoded(f.value), bindings=f.bindings, python=f.python)

    def test_probe_cannot_precede_its_original_executable_read_or_reuse_parent_invocation(self):
        with fixture() as f:
            for mutation in ("time", "invocation"):
                value = copy.deepcopy(f.value)
                row = value["probes"][0]
                if mutation == "time":
                    row["firstNs"] = str(100 * T.clocks.NS)
                else:
                    row["invocation"] = f.frame["outerId"]
                with self.subTest(mutation=mutation), self.assertRaises(T.ProviderToolsError):
                    f.decode(encoded(value))

    def test_existing_six_mib_transport_cap_still_contains_five_maximum_fields(self):
        encoded_maxima = sum(4 * ((maximum + 2) // 3) for maximum in R._LIMITS.values())
        self.assertEqual(encoded_maxima, 5947404)
        self.assertEqual((R.PACKET_BYTES, R.ACK_BYTES, T.FILE_BYTES, T.TOTAL_BYTES),
            (6291456, 1024, 268435456, 536870912))
        self.assertEqual(R.PACKET_BYTES - encoded_maxima, 344052)


class OwnerModelControls(unittest.TestCase):
    def test_windows_walk_starts_at_actual_pinned_parent_not_unsupported_volume_root(self):
        # Supplied native-owner shapes only; this does NOT acquire Windows handles.
        owner = object.__new__(T.ToolObserver)
        owner._check = lambda **_kwargs: 100
        owner._resources = []
        files, closed, opened = [], [], []
        info = SimpleNamespace(is_directory=False, size=42, identity=(1, "a" * 32))
        def directory(path, names):
            result = SimpleNamespace(path=PureWindowsPath(path))
            stamp = SimpleNamespace(is_directory=True, identity=(1, path))
            result.verify = lambda: stamp
            result.names = lambda **_kwargs: tuple(names)
            def read(name, **_kwargs):
                files.append((str(result.path), name))
                return SimpleNamespace(initial_info=info, verify=lambda: info)
            result.open_file = read
            return result
        tool = directory(r"C:\tools", ["node.EXE"])
        workspace = directory(r"C:\source", ["scripts"])
        owner._public_dirs = {str(item.path): item for item in (tool, workspace)}
        owner.window = SimpleNamespace(local_end=200.0)
        owner._take = lambda name, factory: factory()
        owner._close = lambda reader: closed.append(reader)
        def unavailable(path):
            opened.append(str(path))
            raise AssertionError("unexpected new directory or bare volume open")
        owner._windows_directory = unavailable
        selected = owner._windows_inspect(r"C:\tools\node.exe")
        self.assertEqual(str(selected[0]), r"C:\tools\node.EXE")
        self.assertIs(selected[1], info)
        self.assertEqual(files, [(r"C:\tools", "node.EXE")])
        self.assertEqual(len(closed), 1)
        for path in (r"C:\tools\zstd.EXE", r"C:\source\undefined\Git\usr\bin\tar.exe",
                     r"C:\source\undefined\Windows\System32\tar.exe"):
            with self.subTest(path=path):
                self.assertIsNone(owner._windows_inspect(path))
        self.assertEqual(opened, [])
        self.assertEqual(len(files), 1)

    def test_windows_runtime_uses_real_existing_parent_and_refuses_bare_volume_parent(self):
        owner = object.__new__(T.ToolObserver)
        owner._check = lambda **_kwargs: 100
        owner._public_dirs, owner._resources = {}, []
        owner.window = SimpleNamespace(local_end=200.0)
        opened = []
        stamp = SimpleNamespace(is_directory=True)
        parent = SimpleNamespace(path=PureWindowsPath(r"C:\runtime"), verify=lambda: stamp,
                                 names=lambda **_kwargs: ())
        owner._windows_directory = lambda path: opened.append(str(path)) or parent
        self.assertIsNone(owner._windows_inspect(r"C:\runtime\python.exe"))
        self.assertEqual(opened, [r"C:\runtime"])
        with self.assertRaisesRegex(T.ProviderToolsError, "WINDOWS_VOLUME_ROOT_UNQUALIFIED"):
            owner._windows_inspect(r"C:\node.exe")
        self.assertEqual(opened, [r"C:\runtime"])

    def test_missing_path_directory_refuses_without_dropping_or_fabricating_stamp(self):
        owner = object.__new__(T.ToolObserver)
        owner._state, owner._error, owner._first = "NEW", None, None
        owner.frame = {"role": "linux-x64", "directory": "/private/provider", "directoryIdentity": [1, 2], "toolPath": "/missing"}
        owner.directory = SimpleNamespace(path=Path("/private/provider"), identity=(1, 2), verify=lambda: None)
        owner._check = lambda **_kwargs: 100
        owner._posix_inspect = lambda _path: None
        with self.assertRaisesRegex(T.ProviderToolsError, "MISSING_PATH_DIRECTORY"):
            owner.prepare()
        self.assertIsNotNone(owner._error)

    def test_supplied_copy_cannot_replace_original_closed_tools_return(self):
        owner = object.__new__(T.ToolObserver)
        owner._check = lambda **_kwargs: 100
        owner._state, owner._resources = "CLOSED", [T._Resource("model", object(), True, True)]
        owner._closed_resources = tuple((slot, slot.name, slot.owner) for slot in owner._resources)
        owner._result_bytes = b"MODEL_REGISTERED_RETURN"
        original = owner._result = T.ToolObservation(owner._result_bytes)
        self.assertIs(owner.check_result(original), original.raw)
        with self.assertRaisesRegex(T.ProviderToolsError, "ORIGINAL_RETURN_CHANGED"):
            owner.check_result(T.ToolObservation(original.raw))


if __name__ == "__main__":
    unittest.main()
