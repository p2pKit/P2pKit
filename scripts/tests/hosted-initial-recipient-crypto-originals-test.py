#!/usr/bin/env python3
"""New shallow crypto custody controls, not real GPG/native/hosted evidence.

Tiny ordinary-UID files, explicit native-return/clock/Windows models and the
existing synthetic supplier fixtures only. No old test method, complete reader,
1066-file generator, key, toolchain, provider or subprocess is executed.
"""
from __future__ import annotations

import dataclasses
import importlib.util
import os
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(filename))
    value = importlib.util.module_from_spec(spec)
    sys.modules[name] = value
    spec.loader.exec_module(value)
    return value


V = load("crypto_originals_validation_models", "hosted-initial-recipient-validation-test.py")
# V installs its existing process/network/native-loader guard BEFORE project import.
T = load("crypto_originals_sender_models", "hosted-initial-recipient-continuity-test.py")
N, S, O, I, Q = V.N, V.S, V.O, V.I, V.Q
ARMOR = b"EXPLICIT_SYNTHETIC_PUBLIC_ARMOR_NOT_A_KEY\n"


class CryptoInventoryControls(unittest.TestCase):
    def setUp(self):
        self.fx = V.F.NativeModels("runTest")
        self.addCleanup(self.fx.doCleanups)
        self.fx.setUp()
        self.owners, self.serial = [], 0
        self.addCleanup(self.close_models)

    def close_models(self):
        # Only these tiny synthetic resources exist; not native UNKNOWN recovery.
        for owner in self.owners:
            for row in reversed(owner.resources):
                row["owner"].close()
        N._RECIPIENT_CRYPTO_ORIGINALS.clear()
        N._RECIPIENT_NATIVE_RETURNS.clear()

    def layout(self, *, windows=False):
        self.serial += 1
        parent = self.fx.base / ("inventory-" + str(self.serial))
        parent.mkdir(mode=0o700)
        path = parent / "crypto"
        path.mkdir(mode=0o700)
        for name in ("gnupg", "tmp"):
            (path / name).mkdir(mode=0o700)
        operations = tuple("gpg-" + (f"{number:032x}" if windows else "model00" + str(number))
            for number in range(1, 4 if windows else 3))
        files = {"recipient.asc": ARMOR, "recipient.gpg": b"SYNTHETIC_PUBLIC_RING_NOT_A_KEY\n"}
        for name in operations:
            (path / name).mkdir(mode=0o700)
            files.update({name + "/stdout": b"SYNTHETIC_PUBLIC_LISTING\n", name + "/stderr": b""})
            if not windows:
                files.update({name + "/status": b"", name + "/process.json": b'{"synthetic":true}\n'})
        if windows:
            files["recipient-validation-result-" + "a" * 32 + ".json"] = b'{"synthetic":true}\n'
        for name, raw in files.items():
            self.write(path / name, raw)
        role = "windows-x64" if windows else "linux-x64"
        clock = O.clocks.ClockIdentity(role, O.clocks.DOMAINS[role], O.NS)
        ns = self.fx.fixture.ns
        state = SimpleNamespace(phase="READ", read_end=ns + 30 * O.NS, read_local=ns / O.NS + 30)
        case = self

        class ReadWindow:
            def __init__(self):
                self.clock, self.last = clock, ns
            def state(self):
                return state
            def now(self, *, final=False, minimum=0, limit=None):
                self.last = max(self.last, case.fx.fixture.ns, minimum)
                I.require(self.last < min(state.read_end, limit if limit is not None else state.read_end) and
                    N.time.monotonic() < state.read_local, "SYNTHETIC_ORIGINAL_READ_EXPIRED")
                return self.last
            def deadline(self, _maximum, *, final=False, limit=None):
                self.now(final=final, limit=limit)
                return state.read_local

        window = ReadWindow()
        owner = S.Owner(state.read_local, window, first=O.clocks.Reading(clock, ns), cancelled=lambda: None)
        self.owners.append(owner)
        if windows:
            # Native Windows directory/file-ID/roster suppliers are MODELED.
            # Real tiny POSIX file reads retain their own privacy/close checks.
            class WindowsDirectoryModel:
                def __init__(self, target):
                    self.inner = Q._PosixDirectory(target)
                    self.path = target
                    self.identity = (self.inner.identity[0], f"{self.inner.identity[1]:032x}")
                def verify(self):
                    self.inner.verify()
                def names(self, *, max_names, deadline):
                    self.verify()
                    names = tuple(entry.name for entry in self.path.iterdir())
                    I.require(len(names) <= max_names, "SYNTHETIC_DIRECTORY_LIMIT")
                    return names
                def read_bytes(self, name, *, max_bytes, deadline):
                    return self.inner.read_bytes(name, max_bytes=max_bytes, deadline=deadline)
                def close(self):
                    self.inner.close()
            root = owner.acquire("directory", lambda: WindowsDirectoryModel(path), final=True)
            child = S.Owner.child
            def open_child(actual, directory, name, *, create=False, final=False):
                if actual is not owner:
                    return child(actual, directory, name, create=create, final=final)
                self.assertFalse(create)
                return actual.acquire("directory", lambda: WindowsDirectoryModel(directory.path / name), final=final)
            self.fx.stack.enter_context(patch.object(S.Owner, "child", open_child))
        else:
            root = owner.open(path, final=True)
        context = O.encoded({"session": str(parent), "directories": {"crypto": list(root.identity)}})
        phase = N._RecipientNativeReturn(context, (("result.json", b'{"synthetic":"native-return"}\n'),),
            O.encoded({"recipient": {"key_sha256": O.digest(ARMOR)}}))
        owner.phase_originals = phase
        N._RECIPIENT_NATIVE_RETURNS[id(phase)] = (phase, owner, window, context, phase.records, phase.child)
        self.owner, self.root, self.phase, self.window = owner, root, phase, window
        return path, files, operations

    def write(self, path, raw):
        path.write_bytes(raw)
        path.chmod(0o600)

    def capture(self):
        return N._capture_recipient_crypto_originals(self.owner, self.root, self.phase, self.window)

    def test_posix_complete_shallow_roster_hashes_and_zero_length_logs(self):
        path, files, _ops = self.layout()
        self.write(path / "gnupg/model-public-cache", b"public-only-model\n")
        files["gnupg/model-public-cache"] = b"public-only-model\n"
        inventory = self.capture()
        value = O.parse(inventory.raw)
        self.assertEqual(value["scope"], N.CRYPTO_ORIGINALS_SCOPE)
        self.assertEqual(value["files"], [{"relative": name, "bytes": len(raw), "sha256": O.digest(raw)}
            for name, raw in sorted(files.items())])
        self.assertEqual(value["totalBytes"], sum(map(len, files.values())))
        self.assertEqual(len(value["directories"]), 5)
        self.assertTrue(any(row["bytes"] == 0 for row in value["files"]))
        self.assertEqual(value["readEndNs"], self.window.state().read_end)
        self.assertEqual(value["copyState"], "ORIGINAL_BYTES_NOT_COPIED")
        self.assertIs(inventory.phase, self.phase)

    def test_windows_fixed_three_operations_session_record_and_empty_homes(self):
        _path, files, _ops = self.layout(windows=True)
        value = O.parse(self.capture().raw)
        self.assertEqual(len(value["files"]), 9)
        self.assertEqual(len(value["directories"]), 6)
        self.assertEqual({row["relative"] for row in value["files"]}, set(files))
        self.assertTrue(all(type(row["identity"][1]) is str for row in value["directories"]))
        self.assertEqual([row["members"] for row in value["directories"] if row["relative"] in ("gnupg", "tmp")], [[], []])

    def test_missing_extra_and_wrong_count_root_members_refuse(self):
        for mutation in ("missing", "extra", "wrong-count"):
            with self.subTest(mutation=mutation):
                path, _files, ops = self.layout()
                if mutation == "missing":
                    (path / "recipient.gpg").unlink()
                elif mutation == "extra":
                    self.write(path / "undeclared", b"model\n")
                else:
                    (path / ops[0]).rename(path / "not-a-gpg-operation")
                with self.assertRaisesRegex(I.AdmissionError, "CRYPTO_ORIGINAL_ROOT_ROSTER"):
                    self.capture()

    def test_missing_operation_capture_refuses_instead_of_becoming_empty(self):
        path, _files, ops = self.layout()
        (path / ops[0] / "status").unlink()
        with self.assertRaisesRegex(I.AdmissionError, "CRYPTO_ORIGINAL_OPERATION_ROSTER"):
            self.capture()

    def test_wrong_native_return_or_unowned_root_refuses(self):
        self.layout()
        with self.assertRaisesRegex(I.AdmissionError, "CRYPTO_ORIGINAL_NATIVE_RETURN"):
            N._capture_recipient_crypto_originals(self.owner, self.root, dataclasses.replace(self.phase), self.window)
        other = Q._PosixDirectory(self.root.path)
        try:
            with self.assertRaisesRegex(I.AdmissionError, "CRYPTO_ORIGINAL_ROOT"):
                N._capture_recipient_crypto_originals(self.owner, other, self.phase, self.window)
        finally:
            other.close()

    def test_key_change_and_empty_ring_refuse(self):
        for name, raw, code in (("recipient.asc", b"truncated", "CRYPTO_ORIGINAL_KEY_CHANGED"),
                ("recipient.gpg", b"", "CRYPTO_ORIGINAL_EMPTY_RING")):
            with self.subTest(name=name):
                path, _files, _ops = self.layout()
                self.write(path / name, raw)
                with self.assertRaisesRegex(I.AdmissionError, code):
                    self.capture()

    def test_posix_home_special_link_and_nested_directory_refuse_before_read(self):
        for kind in ("fifo", "link", "directory"):
            with self.subTest(kind=kind):
                path, _files, _ops = self.layout()
                member = path / "gnupg/special"
                if kind == "fifo":
                    os.mkfifo(member, 0o600)
                elif kind == "link":
                    member.symlink_to(path / "recipient.asc")
                else:
                    member.mkdir(mode=0o700)
                read = S.Owner.read
                def checked(actual, directory, name, *args, **kwargs):
                    self.assertNotEqual(name, "special", "must classify before potentially blocking read")
                    return read(actual, directory, name, *args, **kwargs)
                with patch.object(S.Owner, "read", checked), self.assertRaisesRegex(I.AdmissionError, "CRYPTO_ORIGINAL_REGULAR_FILE"):
                    self.capture()

    def test_windows_nonempty_home_refuses(self):
        path, _files, _ops = self.layout(windows=True)
        self.write(path / "tmp/unexpected", b"model\n")
        with self.assertRaisesRegex(I.AdmissionError, "CRYPTO_ORIGINAL_WINDOWS_HOME_NOT_EMPTY"):
            self.capture()

    def test_unsafe_or_excess_home_names_refuse(self):
        path, _files, _ops = self.layout()
        self.write(path / "gnupg/Unsafe", b"")
        with self.assertRaisesRegex(Q.QueryError, "QUERY_COMPONENT"):
            self.capture()
        path, _files, _ops = self.layout()
        for number in range(33):
            self.write(path / "gnupg" / ("file-" + str(number)), b"")
        with self.assertRaisesRegex(O.OriginError, "DIRECTORY_LIMIT"):
            self.capture()

    def test_original_key_and_diagnostic_reader_limits_remain_enforced(self):
        for kind in ("key", "diagnostic"):
            with self.subTest(kind=kind):
                path, _files, ops = self.layout()
                name = "recipient.asc" if kind == "key" else ops[0] + "/stdout"
                maximum = S.posix.MAX_KEY_BYTES if kind == "key" else S.posix.MAX_DIAGNOSTIC_BYTES
                self.write(path / name, b"x" * (maximum + 1))
                with self.assertRaisesRegex(Q.QueryError, "QUERY_PRIVATE_FILE_CHANGED"):
                    self.capture()
                self.assertTrue(self.owner.unknown)

    def test_combined_limit_counts_all_original_bytes_once(self):
        self.layout()
        self.assertEqual(N.CRYPTO_ORIGINALS_LIMIT, 16 * 1024 * 1024)
        # Exercise the aggregate predicate with tiny files and a LOWER model cap.
        with patch.object(N, "CRYPTO_ORIGINALS_LIMIT", len(ARMOR)), self.assertRaisesRegex(I.AdmissionError, "CRYPTO_ORIGINAL_TOTAL_LIMIT"):
            self.capture()

    def test_changed_or_truncated_second_read_refuses(self):
        for replacement in (b"", b"changed\n"):
            with self.subTest(replacement=replacement):
                path, _files, ops = self.layout()
                target = path / ops[0] / "stdout"
                read, count = S.Owner.read, [0]
                def changing(actual, directory, name, *args, **kwargs):
                    if directory.path / name == target:
                        count[0] += 1
                        if count[0] == 2:
                            self.write(target, replacement)
                    return read(actual, directory, name, *args, **kwargs)
                with patch.object(S.Owner, "read", changing), self.assertRaisesRegex(I.AdmissionError, "CRYPTO_ORIGINAL_BYTES_CHANGED"):
                    self.capture()
                self.assertEqual(count[0], 2)

    def test_final_roster_addition_and_native_registry_replacement_refuse(self):
        path, _files, _ops = self.layout()
        names, count = S._initializer_names, [0]
        def changed(owner, directory):
            if directory is self.root:
                count[0] += 1
                if count[0] == 2:
                    self.write(path / "added-after-capture", b"")
            return names(owner, directory)
        with patch.object(S, "_initializer_names", changed), self.assertRaisesRegex(I.AdmissionError, "CRYPTO_ORIGINAL_DIRECTORY_CHANGED"):
            self.capture()
        self.layout()
        read = S.Owner.read
        def replaced(*args, **kwargs):
            raw = read(*args, **kwargs)
            saved = N._RECIPIENT_NATIVE_RETURNS[id(self.phase)]
            N._RECIPIENT_NATIVE_RETURNS[id(self.phase)] = tuple(list(saved))
            return raw
        with patch.object(S.Owner, "read", replaced), self.assertRaisesRegex(I.AdmissionError, "CRYPTO_ORIGINAL_NATIVE_RETURN_CHANGED"):
            self.capture()

    def test_original_raw_and_local_read_expiry_do_not_gain_a_new_window(self):
        self.layout()
        self.fx.fixture.ns = self.window.state().read_end
        with self.assertRaisesRegex(I.AdmissionError, "SYNTHETIC_ORIGINAL_READ_EXPIRED"):
            self.capture()
        self.layout()
        with patch.object(N.time, "monotonic", return_value=self.window.state().read_local), \
                self.assertRaisesRegex(I.AdmissionError, "SYNTHETIC_ORIGINAL_READ_EXPIRED"):
            self.capture()


class CryptoParentControls(unittest.TestCase):
    def setUp(self):
        self.fx = V.RecipientModels("runTest")
        self.addCleanup(self.fx.doCleanups)
        self.fx.setUp()

    def test_real_parent_model_registers_only_after_native_readback_and_known_close(self):
        capture, observed = N._capture_recipient_crypto_originals, []
        def checked(owner, root, phase, window):
            self.assertEqual(window.state().phase, "READ")
            resources = [row for row in owner.resources if row["label"] in ("native-scope", "stdout", "stderr")]
            self.assertEqual(len(resources), 3)
            self.assertTrue(all(row["attempted"] and row["closed"] for row in resources))
            self.assertFalse(N._RECIPIENT_CRYPTO_ORIGINALS)
            value = capture(owner, root, phase, window)
            observed.append(value)
            return value
        with patch.object(N, "_capture_recipient_crypto_originals", checked):
            result = self.fx.worker()
        self.assertEqual(len(observed), 1)
        saved = N._RECIPIENT_RETURNS[id(result)]
        self.assertEqual(len(saved), 7)
        self.assertTrue(saved[3].terminal)
        saved[3].roster.known()
        with patch.object(S.Owner, "read", side_effect=AssertionError("NO_RETIRED_OWNER_IO")):
            self.assertEqual(N._checked_recipient_crypto_originals(result), observed[0].raw)
        object.__setattr__(observed[0], "raw", b"CHANGED_MODEL_MANIFEST\n")
        with self.assertRaisesRegex(I.AdmissionError, "RECIPIENT_HISTORY_CHANGED"):
            N._checked_recipient_crypto_originals(result)

    def test_unknown_parent_close_never_registers_inventory_authority(self):
        close = S.Owner.close
        def failed(owner):
            close(owner)  # Model handles really close; reported original is deliberately UNKNOWN.
            if type(owner.fence) is N._RecipientUseWindow:
                owner.error("synthetic-crypto-parent-close", RuntimeError("SYNTHETIC_PARENT_CLOSE"), unknown=True)
        with patch.object(S.Owner, "close", failed), self.assertRaisesRegex(RuntimeError, "SYNTHETIC_PARENT_CLOSE"):
            self.fx.worker()
        self.assertFalse(N._RECIPIENT_CRYPTO_ORIGINALS)

    def test_inventory_changed_after_capture_cannot_be_learned_as_original_at_close(self):
        capture, source, captured = N._capture_recipient_crypto_originals, N.source_queries, []
        def retained(*args):
            value = capture(*args)
            captured.append(value)
            return value
        def changed(owner, window, context, path):
            if path.name == "source-final":
                self.assertEqual(len(captured), 1)
                object.__setattr__(captured[0], "raw", b"CHANGED_AFTER_ORIGINAL_CAPTURE\n")
            return source(owner, window, context, path)
        with patch.object(N, "_capture_recipient_crypto_originals", retained), \
                patch.object(N, "source_queries", changed), self.assertRaisesRegex(I.AdmissionError, "RECIPIENT_HISTORY_CHANGED"):
            self.fx.worker()
        self.assertFalse(N._RECIPIENT_CRYPTO_ORIGINALS)


class CryptoSenderControls(unittest.TestCase):
    def setUp(self):
        self.fx = T.SenderStepControls("runTest")
        self.addCleanup(self.fx.doCleanups)
        self.fx.setUp()

    def test_new_inventory_closes_before_single_three_hash_append_and_two_final_checks(self):
        append, close, observed, owners = T.C.append_outputs, T.S.Owner.close, [], []
        def closed(owner):
            value = close(owner)
            owners.append(owner)
            return value
        def checked(values, check):
            claim = next(iter(T.N._SENDER_STEP_ATTEMPTS.values()))
            self.assertIs(claim[0], self.fx.returned)
            self.assertEqual(len(owners), 1)
            owner = owners[0]
            self.assertTrue(owner.closed)
            self.assertFalse(owner.unknown)
            self.assertIsNone(owner.original)
            self.assertTrue(all(row["attempted"] and row["closed"] for row in owner.resources))
            self.assertEqual([row["label"] for row in owner.resources].count("writer"), 2)
            self.assertEqual({row["owner"].path for row in owner.resources if row["label"] == "directory"},
                {T.N._step_path(), T.N._crypto_originals_path()})
            observed.append(dict(values))
            return append(values, check)
        with patch.object(T.C, "append_outputs", checked), patch.object(T.S.Owner, "close", closed):
            returned = self.fx.retain()
        raw = (T.N._crypto_originals_path() / T.N.CRYPTO_ORIGINALS_FILE).read_bytes()
        value = T.O.parse(raw)
        step = (T.N._step_path() / T.C.STEP_FILE).read_bytes()
        self.assertEqual(value["inventory"], T.O.parse(self.fx.crypto.raw))
        self.assertEqual(value["writerReturn"], "PENDING_OWNER_CLOSE")
        self.assertEqual(value["originalStepOutcome"], "NOT_OBSERVED")
        self.assertEqual(observed, [{"recipientSenderSha256": self.fx.value["recipientSenderSha256"],
            "recipientStepSha256": T.O.digest(step), "recipientCryptoOriginalsSha256": T.O.digest(raw)}])
        self.assertEqual(dict(line.split("=", 1) for line in self.fx.output.read_text().splitlines()), observed[0])
        self.assertEqual(self.fx.calls, [])
        returned[1].now(final=True, limit=returned[2])
        returned[1].now(final=True, limit=returned[2])
        with self.assertRaises(T.I.AdmissionError):
            returned[1].now(final=True, limit=returned[2])
        self.assertEqual(len(self.fx.calls), 2)

    def test_missing_or_changed_original_inventory_blocks_output(self):
        original = self.fx.crypto.raw
        object.__setattr__(self.fx.crypto, "raw", b"CHANGED_ORIGINAL\n")
        with self.assertRaisesRegex(T.I.AdmissionError, "CRYPTO_ORIGINAL_RETURN_CHANGED"):
            self.fx.retain()
        self.assertEqual(self.fx.output.read_bytes(), b"")
        self.assertEqual(self.fx.calls, [])
        object.__setattr__(self.fx.crypto, "raw", original)
        key, saved = next(iter(T.N._RECIPIENT_CRYPTO_ORIGINALS.items()))
        forged = dataclasses.replace(self.fx.crypto, raw=T.O.encoded({"model": "FORGED_SELF_CONSISTENT_INVENTORY"}))
        T.N._RECIPIENT_CRYPTO_ORIGINALS[key] = (saved[0], saved[1], forged, forged.raw, forged.phase,
            forged.directories, T.N._history_graph(forged))
        with self.assertRaisesRegex(T.I.AdmissionError, "CRYPTO_ORIGINAL_PARENT_BINDING"):
            self.fx.retain()
        self.assertEqual(self.fx.output.read_bytes(), b"")
        self.assertEqual(self.fx.calls, [])

    def test_registry_substitution_during_metadata_is_sticky_failure(self):
        new = T.S.Owner.new
        def changed(owner, path):
            directory = new(owner, path)
            T.N._RECIPIENT_CRYPTO_ORIGINALS = dict(T.N._RECIPIENT_CRYPTO_ORIGINALS)
            return directory
        with patch.object(T.S.Owner, "new", changed), self.assertRaisesRegex(T.I.AdmissionError, "STEP_CRYPTO_ORIGINALS_CHANGED"):
            self.fx.retain()
        self.assertEqual(self.fx.output.read_bytes(), b"")
        self.assertEqual(self.fx.calls, [])

    def test_sidecar_readback_failure_prevents_output_and_original_sender_calls(self):
        read = T.S.Owner.read
        def changed(owner, directory, name, *args, **kwargs):
            raw = read(owner, directory, name, *args, **kwargs)
            return b"changed\n" if name == T.N.CRYPTO_ORIGINALS_FILE else raw
        with patch.object(T.S.Owner, "read", changed), self.assertRaisesRegex(T.O.OriginError, "PRIVATE_READBACK"):
            self.fx.retain()
        self.assertEqual(self.fx.output.read_bytes(), b"")
        self.assertEqual(self.fx.calls, [])

    def test_sidecar_unknown_close_retains_owner_and_cannot_emit_hash(self):
        close = T.Q._PosixDirectory.close
        def failed(directory):
            close(directory)
            if directory.path == T.N._crypto_originals_path():
                raise OSError("SYNTHETIC_CRYPTO_DIRECTORY_CLOSE_UNKNOWN")
        with patch.object(T.Q._PosixDirectory, "close", failed), self.assertRaises(OSError):
            self.fx.retain()
        self.assertEqual(self.fx.output.read_bytes(), b"")
        self.assertEqual(self.fx.calls, [])
        self.assertTrue(T.S.QUARANTINE)

    def test_three_hash_output_failure_does_not_allow_final_sender_handoff(self):
        with patch.object(T.C, "append_outputs", side_effect=RuntimeError("SYNTHETIC_OUTPUT_FAILURE")), \
                self.assertRaisesRegex(RuntimeError, "SYNTHETIC_OUTPUT_FAILURE"):
            self.fx.retain()
        self.assertEqual(self.fx.calls, [])
        self.assertEqual(self.fx.output.read_bytes(), b"")
        with self.assertRaisesRegex(T.I.AdmissionError, "STEP_SENDER_ALREADY_CLAIMED"):
            self.fx.retain()

    def test_new_output_shape_rejects_inventory_alone_extra_flags_and_nonhash(self):
        values = {"recipientSenderSha256": "a" * 64, "recipientStepSha256": "b" * 64,
            "recipientCryptoOriginalsSha256": "c" * 64}
        for value in ({"recipientCryptoOriginalsSha256": "c" * 64}, {**values, "ready": "d" * 64},
                {**values, "recipientCryptoOriginalsSha256": "NOT_A_HASH"}):
            with self.subTest(fields=sorted(value)), self.assertRaisesRegex(T.C.ContinuityError, "STEP_OUTPUT_FIELDS"):
                T.C.append_outputs(value, lambda: None)
        self.assertEqual(self.fx.output.read_bytes(), b"")


if __name__ == "__main__":
    unittest.main(failfast=True)
