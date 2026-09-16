#!/usr/bin/env python3
"""Small actual Windows controls, NOT_RUN unless this native CLI is invoked.

One fixed case per child interpreter, under the genuine helper's native Job.
No key generation/private key/decryption, product Gradle, SDK, install or network.
Faults explicitly labeled AFTER_REAL_CLOSE are injected only after the real API
returned; they do not claim a real OS CloseHandle failure. Original UNKNOWN
production receipts remain UNKNOWN. Pin-hold cases end the interpreter without
clearing quarantine; the outer actual Job must prove whole-child retirement.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import signal
import sys
import tarfile
import threading
import time
from unittest.mock import patch
import uuid

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
spec = importlib.util.spec_from_file_location("native_windows_helper", SCRIPTS / "run-hosted-windows-helper-controls.py")
H = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = H
spec.loader.exec_module(H)
F, P, W, C = H.files, H.processes, H.encrypted, H.witness
A = C.audit
PAYLOAD = bytes(range(256)) * 513
LINES = b"fixture-only\r\nzero=\x00 high=\xff\n"
_RETAIN_TO_EXIT = []


def check(value, code):
    H.require(value, "NATIVE_" + code)


def emitter(stdout, stderr=b""):
    program = "import os,msvcrt;msvcrt.setmode(1,os.O_BINARY);msvcrt.setmode(2,os.O_BINARY);"
    program += "os.write(1," + repr(stdout) + ");os.write(2," + repr(stderr) + ")"
    check(len(program) < 8000, "EMITTER_COMMAND_BOUND")
    return [sys.executable, "-I", "-B", "-S", "-c", program]


def source_identity():
    check(os.environ.get("GITHUB_ACTIONS") == "true" and os.environ.get("GITHUB_EVENT_NAME") == "workflow_dispatch" and
          os.environ.get("GITHUB_REPOSITORY") == H.REPOSITORY, "REAL_MANUAL_ENVIRONMENT_REQUIRED")
    return {"commit": os.environ["GITHUB_SHA"], "tree": os.environ["P2PKIT_HELPER_SOURCE_TREE"]}


class Fixture:
    def __init__(self, name, destination):
        check(os.name == "nt" and P.host_role() == "windows-x64", "WINDOWS_X64_REQUIRED")
        state = Path(os.environ[P.STATE_ENV])
        domains = P.ownership_domains(os.environ[P.CHAIN_ENV], os.environ[P.DOMAINS_ENV])
        check(domains and domains[-1]["state"] == str(state) and domains[-1]["job"] == os.environ[P.JOB_ENV] and
              state.name == name and Path(destination) == state.parents[1] / "evidence" / name,
              "EXACT_HELPER_CHILD_STATE_REQUIRED")
        self.name, self.owners, self.observations = name, [], []
        self.root = self.hold(F.create_private_directory(destination))
        self.state = self.directory("fixture-state")
        self.job = os.environ[P.JOB_ENV]
        self.environment = dict(os.environ)
        self.expected_hold = False
        self.unknown = False
        self.result = {"schema": 1, "case": name, "native": True, "passed": False,
                       "source": source_identity(), "run": {"id": os.environ["GITHUB_RUN_ID"],
                                                              "attempt": os.environ["GITHUB_RUN_ATTEMPT"]},
                       "observations": self.observations, "privateDecryption": "NOT_RUN"}

    def hold(self, owner):
        self.owners.append(owner)
        return owner

    def directory(self, name):
        return self.hold(self.root.create_directory(name))

    def record(self, name, value):
        H.private_json(self.root, name + ".json", value)
        self.observations.append({"path": name + ".json", "sha256": H.digest(H.encoded(value))})

    def commands(self, label):
        evidence, state = self.directory(label), self.directory(label + "-state")
        return H.Commands(evidence, state, self.job, deadline=time.monotonic() + 90)

    def native_scope(self):
        invocation = uuid.uuid4().hex
        env = P.ownership_environment(H.command_environment(dict(os.environ)), self.job, invocation,
                                     str(self.state.path), str(self.state.path / "unused-home"), allow_new_context=True)
        scope = P.make_scope(self.job, invocation, str(self.state.path), env["GRADLE_USER_HOME"])
        return scope, env

    def ordinary_retire(self, scope, pipes=(), tees=()):
        errors, description = [], None
        # Drain before Tee completion/pipe release even on an early assertion.
        # Each exact action is attempted once; never retry uncertain handles.
        try:
            check(scope.drain(grace=0, kill_wait=5) == [], "DOMAIN_DRAIN_UNKNOWN")
        except BaseException as error:
            errors.append(error)
        try:
            description = scope.description()
            check(description.get("discoveryErrors") == [], "DOMAIN_OBSERVATION_UNKNOWN")
        except BaseException as error:
            errors.append(error)
        for tee in tees:
            try:
                tee.finish()
                check(tee._complete.is_set() and not tee.thread.is_alive(), "TEE_WORKER_RETIREMENT_UNKNOWN")
                check(not tee.errors, "TEE_STREAM_RETIREMENT_UNKNOWN")
            except BaseException as error:
                errors.append(error)
        for stream in pipes:
            # A registered Tee owns its source until its own completion. No
            # caller-side close races a copy worker whose retirement is unknown.
            if stream is not None and not any(tee.source is stream for tee in tees):
                try:
                    stream.close()
                except BaseException as error:
                    errors.append(error)
        try:
            scope.close()
        except BaseException as error:
            errors.append(error)
        if errors:
            self.unknown = True
            for error in errors:
                self.observations.append({"unexpectedRetirementFailure": H.error_detail(error)})
            original = sys.exc_info()[1]
            if original is not None:
                for error in errors:
                    F._note(original, H.encoded(H.error_detail(error)).decode("ascii"))
            else:
                raise errors[0]
        return description

    def _stream_query_controls(self):
        """Actual NTFS queries/writes; deterministic interleaving, not an OS fault.

        No result buffer is fabricated. One owned WriteFile occurs after the real
        FileStandardInfo reply and before the real FileStreamInfo query. Existing
        native_sinks separately exercises an actual child and inherited handles.
        """
        results = []
        for mode in ("strict", "live"):
            name = "interquery-" + mode + ".bin"
            stream = self.hold(self.root.create_file(name, max_bytes=16, deadline=time.monotonic() + 20))
            api, handle = stream._api, stream.native_handle
            information = api._information
            writes, earlier = [], []
            def query(selected, kind, structure):
                value = information(selected, kind, structure)
                if selected == handle and kind == 1 and not writes:
                    check(value.size == 0, "INTERQUERY_INITIAL_SIZE_DIFFERS")
                    earlier.append(value.size)
                    writes.append(api.write(handle, b"G"))
                return value
            try:
                with patch.object(api, "_information", side_effect=query):
                    if mode == "strict":
                        try:
                            stream.verify()
                        except F.FilesystemError as error:
                            check(str(error) == "Alternate data streams are not admitted", "STRICT_INTERQUERY_CAUSE_DIFFERS")
                        else:
                            raise H.HelperError("NATIVE_STRICT_INTERQUERY_GROWTH_ACCEPTED")
                    else:
                        check(stream.observe_live_output().size == 1 and stream.final_info is None,
                              "LIVE_INTERQUERY_SIZE_OR_FINAL_AUTHORITY_DIFFERS")
                check(earlier == [0] and writes == [1] and stream.verify().size == 1,
                      "INTERQUERY_NATIVE_WRITE_OR_STRICT_FINAL_SIZE_DIFFERS")
            finally:
                original = sys.exc_info()[1]
                try:
                    stream.close()
                except BaseException as error:
                    self.unknown = True
                    if original is None:
                        raise
                    F._note(original, H.encoded(H.error_detail(error)).decode("ascii"))
            check(stream.closed and stream._retired, "INTERQUERY_NATIVE_PIN_NOT_CLOSED")
            raw = H.private_read(self.root, name, 16)
            check(raw == b"G", "INTERQUERY_REOPEN_BYTES_DIFFER")
            results.append({"mode": mode, "writeBoundary": "AFTER_REAL_STANDARD_BEFORE_REAL_STREAM_QUERY",
                            "earlierSize": 0, "laterSize": 1, "writeBytes": 1, "writeCount": 1,
                            "strictFinalSize": 1, "closedThenReopened": True, "sha256": H.digest(raw),
                            "outcome": "STRICT_REJECTED" if mode == "strict" else "LIVE_OBSERVED"})
        return results

    def native_sinks(self):
        command = self.commands("real-sinks")
        observations = []
        original = P.make_scope
        def actual_factory(*args):
            scope = original(*args)
            actual_spawn, actual_close = scope.spawn, scope.close
            borrowed = []
            def spawn(*arguments, **keywords):
                borrowed[:] = [keywords["stdout"], keywords["stderr"]]
                child = actual_spawn(*arguments, **keywords)
                observations.append({"phase": "after-native-spawn", "pins": [v.observe_live_output().as_dict() for v in borrowed],
                                     "handles": [v.native_handle for v in borrowed]})
                return child
            def close():
                before = [v.native_handle for v in borrowed]
                actual_close()
                check(before == [v.native_handle for v in borrowed] and all(v.writable() for v in borrowed),
                      "BORROWED_ORIGINALS_CLOSED_WITH_DUPLICATES")
                observations.append({"phase": "after-real-scope-close", "pins": [v.verify().as_dict() for v in borrowed]})
            scope.spawn, scope.close = spawn, close
            return scope
        stdout, stderr = bytes(range(256)) * 4 + b"\x00\r\n\xff", bytes(reversed(range(256))) + b"\r\n"
        try:
            with patch.object(P, "make_scope", side_effect=actual_factory):
                row, directory = command.run(emitter(stdout, stderr), "known-bytes", timeout=20, output_limit=8192)
            check(row["waitExitCode"] == 0 and row["retirement"] == "KNOWN", "SINK_COMMAND_FAILED")
            check(H.private_read(directory, "stdout.bin") == stdout and H.private_read(directory, "stderr.bin") == stderr,
                  "NATIVE_BINARY_BYTES_CHANGED")
            launch = row["ownership"]["launches"]
            check(len(launch) == 1 and launch[0].get("outputMode") == "caller-owned-native-files" and
                  launch[0].get("jobAssignedBeforeResume") is True and launch[0].get("resumed") is True,
                  "JOB_OR_BORROWED_OUTPUT_PROOF_MISSING")
            self.record("native-sinks-observed", {"actualNativeObservations": observations,
                        "liveInterqueryChecks": self._stream_query_controls(),
                        "stdout": {"bytes": len(stdout), "sha256": H.digest(stdout)},
                        "stderr": {"bytes": len(stderr), "sha256": H.digest(stderr)}})
        finally:
            command.close()

    def native_output_bound(self):
        command = self.commands("real-bound")
        original = None
        try:
            command.run(emitter(b"B" * 1024), "over-limit", timeout=20, output_limit=128)
        except W.WindowsEvidenceError as error:
            original = error
        check(original is not None, "CHILD_NATIVE_OUTPUT_BOUND_NOT_ENFORCED")
        detail = H.error_detail(original)
        check("byte bound" in json.dumps(detail).lower() and command.records[0]["ownership"]["launches"][0]["created"],
              "OUTPUT_BOUND_DID_NOT_REACH_NATIVE_CHILD")
        self.record("expected-native-bound-failure", {"expectedFailure": detail, "bytesEmitted": 1024,
                    "admittedBytes": 128, "productionRecordNeverPromoted": True})
        # Output-limit finalization is deliberately conservative; preserve its
        # original UNKNOWN until this isolated interpreter exits. No next GPG.
        self.expected_hold = bool(W._QUARANTINE or command.unknown)
        if self.expected_hold:
            _RETAIN_TO_EXIT.append(command)
        else:
            command.close()

    def native_launch_close(self):
        directory = self.directory("launch-files")
        out = self.hold(directory.create_file("stdout.bin", max_bytes=4096))
        err = self.hold(directory.create_file("stderr.bin", max_bytes=4096))
        scope, env = self.native_scope()
        real_close, attempts = scope.api.close, []
        fault = OSError("LABELED_AFTER_REAL_CLOSE_RETURN")
        injected = []
        def close(handle):
            real_close(handle)
            attempts.append({"handle": int(handle.value if hasattr(handle, "value") else handle), "realCloseReturned": True})
            if not injected:
                injected.append(True)
                raise fault
        original = None
        try:
            with patch.object(scope.api, "close", side_effect=close):
                try:
                    scope.spawn(emitter(b"native-launch"), str(self.root.path), env, stdout=out, stderr=err)
                except BaseException as error:
                    original = error
                check(original is not None and P.retirement_details(original).get("status") == "UNKNOWN",
                      "LAUNCH_TEMPORARY_FAULT_NOT_PRESERVED")
                check(scope.drain(grace=0, kill_wait=5) == [], "INJECTED_SCOPE_DRAIN_UNKNOWN")
                description = scope.description()
                scope.close()
            check(attempts and all(row["realCloseReturned"] for row in attempts), "REAL_CLOSE_WITNESS_MISSING")
            check(description["discoveryErrors"] and any(row.get("status") == "UNKNOWN"
                  for launch in description["launches"] for row in launch.get("resourceCleanup", ())),
                  "INJECTED_PRODUCTION_RECORD_REWRITTEN")
            out.verify(); err.verify()
            self.record("injected-native-close", {"injection": "AFTER_REAL_CLOSE_RETURN_NOT_AN_OS_FAULT",
                        "original": H.error_detail(original), "realCloseAttempts": attempts, "ownership": description,
                        "productionRetirement": "UNKNOWN", "actualFixtureDomainDrained": True})
        finally:
            # scope.close was attempted exactly once above. If setup/body failed
            # earlier, preserve instead of guessing or retrying native handles.
            if scope.job is not None:
                self.ordinary_retire(scope)

    def native_tee(self):
        records = []
        for mode in ("constructor", "not-started", "started-cancel"):
            scope, env = self.native_scope()
            child = tee = None
            errors = []
            target = self.root.path / ("tee-" + mode + ".bin")
            try:
                child = scope.spawn(emitter(b"tee-original", b""), str(self.root.path), env)
                if mode == "constructor":
                    expected = MemoryError("LABELED_THREAD_ALLOCATION_AFTER_OUTPUT_OPEN")
                    try:
                        with patch.object(A.threading, "Thread", side_effect=expected):
                            A.Tee(child.stdout, target, None, errors, False)
                    except MemoryError as caught:
                        check(caught is expected and not child.stdout.closed, "TEE_CONSTRUCTOR_STOLE_SOURCE")
                    else:
                        raise H.HelperError("NATIVE_TEE_CONSTRUCTOR_FAULT_NOT_REACHED")
                    # Exclusive rename proves the real output descriptor closed;
                    # it is restored before the retained private inventory.
                    renamed = target.with_suffix(".retired")
                    target.rename(renamed); renamed.rename(target)
                    records.append({"mode": mode, "outputRenamedAfterFailure": True,
                                    "sourceStillCallerOwned": not child.stdout.closed})
                else:
                    tee = A.Tee(child.stdout, target, None, errors, False)
                    if mode == "started-cancel":
                        real_start = tee.thread.start
                        expected = KeyboardInterrupt("LABELED_AFTER_REAL_THREAD_START")
                        def start():
                            real_start()
                            raise expected
                        try:
                            with patch.object(tee.thread, "start", side_effect=start):
                                tee.start()
                        except KeyboardInterrupt as caught:
                            check(caught is expected, "TEE_START_CANCELLATION_CHANGED")
                    check(scope.drain(grace=0, kill_wait=5) == [], "TEE_CHILD_DRAIN_UNKNOWN")
                    tee.finish()
                    check(tee._complete.is_set() and not tee.thread.is_alive() and tee.output.closed and child.stdout.closed,
                          "TEE_FINALIZATION_INCOMPLETE")
                    check(not errors, "TEE_NATIVE_ERRORS")
                    records.append({"mode": mode, "startAttempted": tee._start_attempted, "completionAcknowledged": True,
                                    "workerRetired": True, "originalCancellation": mode == "started-cancel"})
            finally:
                description = self.ordinary_retire(scope, (() if child is None else
                                     tuple(stream for stream in (child.stdout, child.stderr) if stream is not None and not stream.closed)),
                                     (() if tee is None else (tee,)))
        self.record("actual-tee-paths", {"cases": records, "finishPolicySeconds": 3})

    def actual_controller(self):
        temporary = self.directory("controller-private-parent")
        # Only this test's RUNNER_TEMP allocation target is redirected; actual
        # GitHub identity is not forged, and the production Controller is used.
        identity = {"sourceSha": os.environ["GITHUB_SHA"], "runId": os.environ["GITHUB_RUN_ID"],
                    "runAttempt": os.environ["GITHUB_RUN_ATTEMPT"], "fixture": "HELPER_NOT_PRODUCT_WITNESS"}
        with patch.dict(os.environ, {"RUNNER_TEMP": str(temporary.path)}):
            return C.Controller(H.ROOT, identity)

    def native_controller_command(self):
        controller = self.actual_controller()
        observed = []
        try:
            code, output = controller.command(emitter(b"controller-native\x00\xff\r\n", b"original-stderr"),
                                              self.root.path, controller.env, "tiny-emitter", timeout=20)
            check(code == 0 and C.regular(output / "stdout.log") == b"controller-native\x00\xff\r\n" and
                  C.regular(output / "stderr.log") == b"original-stderr", "ACTUAL_CONTROLLER_BYTES_DIFFER")
            first, original_tee = [], A.Tee
            expected = MemoryError("LABELED_SECOND_TEE_ALLOCATION_AFTER_FIRST_START")
            def tee(*args):
                if first:
                    check(first[0]._start_attempted, "FIRST_TEE_NOT_REGISTERED_AND_STARTED")
                    raise expected
                item = original_tee(*args)
                first.append(item)
                return item
            try:
                with patch.object(C.audit, "Tee", side_effect=tee):
                    controller.command(emitter(b"partial-original", b"sibling-original"), self.root.path,
                                       controller.env, "second-stream-fault", timeout=20)
            except C.CommandFailure as error:
                record = C.read_json(error.capture / "command.json")
                check(any("LABELED_SECOND_TEE" in row for row in record["errors"]) and
                      record["survivors"] == [] and record["ownership"]["discoveryErrors"] == [],
                      "ACTUAL_CONTROLLER_PARTIAL_FAILURE_MISSING")
                check(first[0]._complete.is_set() and not first[0].thread.is_alive(), "FIRST_TEE_WORKER_NOT_RETIRED")
                observed.append({"actualCommandRecord": str(error.capture / "command.json"),
                                 "originalFailureRetained": True, "firstTeeRetired": True})
            else:
                raise H.HelperError("NATIVE_CONTROLLER_SECOND_STREAM_FAULT_NOT_REACHED")
        finally:
            description = self.ordinary_retire(controller.scope)
            observed.append({"actualOuterOwnership": description})
        self.record("controller-command-observed", {"cases": observed, "productGradleExecuted": False})

    def native_controller_retirement(self):
        controller = self.actual_controller()
        originals, cases = [], []
        finalization_attempted = False
        try:
            for name in ("current", "preimage"):
                case = controller.allocate(name)
                case["state"].mkdir()
                for leaf in ("gradle-home", "fixtures", "konan", "android-user"):
                    path = case["state"] / leaf
                    path.mkdir()
                    info = path.stat()
                    case["roots"][str(path)] = {"device": info.st_dev, "inode": info.st_ino}
                for spelling in case["roots"]:
                    (Path(spelling) / "unstarted-sentinel").write_bytes(b"UNSTARTED_FIXTURE_NOT_PRODUCT")
                invocation = uuid.uuid4().hex
                case["scope"] = P.make_scope(self.job, invocation, str(case["state"]), str(case["state"] / "gradle-home"))
                cases.append(case)
            expected = KeyboardInterrupt("LABELED_CASE_CLOSE_AFTER_REAL_NATIVE_CLOSE")
            actual = cases[0]["scope"].close
            def close():
                actual()
                originals.append({"firstCaseRealCloseReturned": True})
                raise expected
            errors = []
            with patch.object(cases[0]["scope"], "close", side_effect=close), \
                    patch.object(C.shutil, "rmtree", side_effect=AssertionError("UNEXPECTED_UNSTARTED_FIXTURE_DISPOSAL")) as removal:
                try:
                    finalization_attempted = True
                    controller.finalize_resources(None, errors)
                except KeyboardInterrupt as caught:
                    check(caught is expected, "ACTUAL_CONTROLLER_CANCELLATION_CHANGED")
                else:
                    raise H.HelperError("NATIVE_CONTROLLER_FINALIZER_CANCELLATION_NOT_REACHED")
                check(not removal.called, "UNSTARTED_ROOT_DISPOSAL_ATTEMPTED")
            for case in cases:
                check(case["retirementAttempted"] and case["scope"].job is None and not case["started"] and
                      not case["initialized"], "PARTIAL_CASE_OR_SIBLING_NOT_FINALIZED")
                record = C.read_json(case["public"] / "retirement.json")
                check(record["complete"] is False and record["removed"] == [], "NEGATIVE_RETIREMENT_RECORD_REWRITTEN")
                check(len(case["roots"]) == 5 and all((Path(path) / "unstarted-sentinel").read_bytes() ==
                      b"UNSTARTED_FIXTURE_NOT_PRODUCT" for path in case["roots"]), "UNSTARTED_FIVE_ROOTS_NOT_PRESERVED")
            outer = C.read_json(controller.public / "admission/controller-retirement.json")
            check(controller.scope.job is None and outer["retirementKnown"] is True and outer["complete"] is False,
                  "ACTUAL_OUTER_NATIVE_FINALIZER_NOT_RETAINED")
            self.record("controller-native-retirement", {"injection": "AFTER_REAL_CLOSE_RETURN_NOT_AN_OS_FAULT",
                        "nativeCloseWitness": originals, "originalCancellation": H.error_detail(expected),
                        "allFiveRootsPreservedPerCase": True, "bothCasesAndOuterAttempted": True,
                        "originalNegativeReceiptsRemainFailed": True, "productGradleExecuted": False})
        finally:
            if not finalization_attempted:
                # Actual early allocation failure still reaches both already
                # registered cases and the outer Job; no product path is started.
                original = sys.exc_info()[1]
                try:
                    controller.finalize_resources(None, [])
                except BaseException as error:
                    self.unknown = True
                    if original is None:
                        raise
                    F._note(original, H.encoded(H.error_detail(error)).decode("ascii"))

    def prepare_crypto(self):
        work, data, output = self.directory("crypto-work"), self.directory("data"), self.directory("crypto-output")
        with data.create_directory("nested"):
            pass
        expected = {"payload.bin": PAYLOAD, "empty": b"", "nested/line-é.txt": LINES}
        for name, raw in expected.items():
            H.private_write(data, name, raw)
        key = os.environ["P2PKIT_EVIDENCE_PUBLIC_KEY"].encode("ascii")
        recipient = W.validate_recipient(key, os.environ["P2PKIT_EVIDENCE_FINGERPRINT"], work, job_id=self.job)
        self.record("fixture-byte-contract", {"members": {"evidence/" + name: {"size": len(raw), "sha256": H.digest(raw)}
                    for name, raw in expected.items()}, "directories": ["evidence", "evidence/nested"],
                    "publicRecipientSha256": H.digest(key), "encryptionFingerprint": recipient.encryption_fingerprint,
                    "privateKeyOnRunner": False, "privateDecryption": "NOT_RUN"})
        return work, data, output, recipient, expected

    def export(self, data, output, recipient):
        source = self.result["source"]
        return W.export_encrypted(data, output, recipient, source_commit=source["commit"], source_tree=source["tree"],
                                  run_id=self.result["run"]["id"], run_attempt=self.result["run"]["attempt"],
                                  max_bytes=1024 * 1024, max_members=16, timeout_seconds=60)

    def native_export(self):
        work, data, output, recipient, expected = self.prepare_crypto()
        manifest = self.export(data, output, recipient)
        raw = H.private_read(output, W.portable.ARTIFACT)
        check(manifest["artifact"] == {"name": W.portable.ARTIFACT, "sha256": H.digest(raw), "size": len(raw)},
              "ACTUAL_CIPHERTEXT_MANIFEST_DIFFERS")
        # Actual native-generated plaintext archive inspection is NOT decryption.
        with work.snapshot(max_bytes=8 * 1024 * 1024, max_members=256) as snapshot:
            archives = [name for name in snapshot.entries if name.startswith("export-") and name.endswith("/evidence.tar.gz")]
            check(len(archives) == 1, "ONE_NATIVE_GENERATED_ARCHIVE_REQUIRED")
            with snapshot.open_file(archives[0]) as stream:
                archived = stream.read()
        with tarfile.open(fileobj=io.BytesIO(gzip.decompress(archived)), mode="r:") as archive:
            members = archive.getmembers()
            check(len(members) == 5 and {item.name for item in members if item.isdir()} == {"evidence", "evidence/nested"},
                  "ACTUAL_ARCHIVE_MEMBER_INVENTORY_DIFFERS")
            observed = {}
            for item in members:
                if item.isdir():
                    continue
                check(item.isfile() and item.name.startswith("evidence/") and item.size <= len(PAYLOAD), "ARCHIVE_FILE_KIND")
                with archive.extractfile(item) as stream:
                    observed[item.name[len("evidence/"):]] = stream.read(item.size + 1)
            check(observed == expected, "ACTUAL_ARCHIVE_ORIGINAL_BYTES_DIFFER")
        negatives = self.directory("decrypt-controls")
        corrupt = raw[:-1] + bytes([raw[-1] ^ 1])
        truncated = raw[:-1]
        H.private_write(negatives, "corrupt-last-byte.gpg", corrupt)
        H.private_write(negatives, "truncated.gpg", truncated)
        # Shape rejection of truncation is native I/O/parser acceptance only;
        # integrity rejection of the corrupt packet is a later private check.
        try:
            with negatives.open_file("truncated.gpg", max_bytes=len(truncated)) as stream:
                W.portable._ciphertext_stream(stream, len(truncated), recipient.encryption_fingerprint)
        except W.portable.EvidenceError:
            pass
        else:
            raise H.HelperError("NATIVE_TRUNCATED_CIPHERTEXT_SHAPE_ACCEPTED")
        self.record("native-crypto-observed", {"manifest": manifest, "actualNativeArchiveBytesMatched": True,
                    "actualInstalledGpgEncryptionReturned": True, "actualTruncationParserRejected": True,
                    "privateDecryption": "NOT_RUN", "expectedPrivateChecks": {
                        "crypto-output/evidence.tar.gz.gpg": "AUTHENTICATE_AND_COMPARE_EXACT_BYTE_CONTRACT",
                        "decrypt-controls/corrupt-last-byte.gpg": "REJECT_INTEGRITY_NO_AUTHENTICATED_PLAINTEXT",
                        "decrypt-controls/truncated.gpg": "REJECT_TRUNCATION_NO_AUTHENTICATED_PLAINTEXT"},
                    "negativeHashes": {"corrupt-last-byte.gpg": H.digest(corrupt), "truncated.gpg": H.digest(truncated)}})

    def native_export_wrong_recipient(self):
        work = self.directory("wrong-recipient-work")
        fingerprint = os.environ["P2PKIT_EVIDENCE_FINGERPRINT"].upper()
        wrong = ("0" if fingerprint[0] != "0" else "1") + fingerprint[1:]
        original = None
        try:
            W.validate_recipient(os.environ["P2PKIT_EVIDENCE_PUBLIC_KEY"].encode("ascii"), wrong, work, job_id=self.job)
        except W.WindowsEvidenceError as error:
            original = error
        check(original is not None and not original.retirement_unknown, "WRONG_RECIPIENT_NOT_SAFELY_REJECTED")
        record = H.decode(original.private_record)
        check(record["commands"] and any("--import" in command["argv"] and command["waitExitCode"] == 0
              for command in record["commands"]) and all(command["retirement"] == "KNOWN" for command in record["commands"]),
              "WRONG_RECIPIENT_DID_NOT_REACH_REAL_GPG_KEY_READ")
        check(any(node.get("message") == "Public-key fingerprint mismatch" for failure in record["failures"]
                  for node in failure["detail"]["nodes"]), "WRONG_RECIPIENT_FAILURE_CAUSE_DIFFERS")
        self.record("actual-gpg-wrong-recipient", {"expectedFailure": H.error_detail(original),
                    "providedFingerprint": wrong, "actualFingerprint": fingerprint, "actualGpgListingExecuted": True})

    def native_export_input_quarantine(self):
        work, data, output, recipient, _ = self.prepare_crypto()
        real_scope, real_gpg = P.WindowsScope, W._gpg
        inputs, closes = [], []
        def gpg(session, selected, arguments, end, **kwargs):
            if kwargs.get("encryption"):
                inputs[:] = list(kwargs.get("borrowed_owners", ()))
            return real_gpg(session, selected, arguments, end, **kwargs)
        def scope_factory(*args):
            scope = real_scope(*args)
            actual_spawn, actual_close = scope.spawn, scope.close
            encryption = []
            def spawn(argv, *rest, **kwargs):
                encryption[:] = ["--encrypt" in argv]
                return actual_spawn(argv, *rest, **kwargs)
            def close():
                actual_close()
                if encryption == [True]:
                    closes.append({"realScopeCloseReturned": True, "jobHandleCleared": scope.job is None})
                    raise OSError("LABELED_ENCRYPTION_AFTER_REAL_SCOPE_CLOSE")
            scope.spawn, scope.close = spawn, close
            return scope
        original = None
        with patch.object(P, "WindowsScope", side_effect=scope_factory), patch.object(W, "_gpg", side_effect=gpg):
            try:
                self.export(data, output, recipient)
            except W.WindowsEvidenceError as error:
                original = error
        check(original is not None and original.retirement_unknown and len(inputs) == 2 and closes and
              all(row["realScopeCloseReturned"] and row["jobHandleCleared"] for row in closes),
              "ENCRYPTION_UNKNOWN_NATIVE_PATH_NOT_OBSERVED")
        directory, plaintext = inputs
        check(not plaintext.closed and plaintext.native_handle and not directory._closed,
              "INPUT_NATIVE_PINS_CLOSED_UNDER_UNKNOWN")
        info = plaintext.verify()
        directory_info = directory.verify()
        check(W._QUARANTINE and any(row["owner"] is plaintext and row["quarantined"] for session in W._QUARANTINE
              for row in session.resources), "REAL_INPUT_NOT_QUARANTINED")
        try:
            W._native()
        except W.portable.EvidenceError:
            pass
        else:
            raise H.HelperError("NATIVE_UNKNOWN_LATCH_WAS_RESET")
        self.record("actual-encryption-input-pin-hold", {"injection": "AFTER_REAL_SCOPE_CLOSE_NOT_AN_OS_FAULT",
                    "original": H.error_detail(original), "realScopeCloseWitness": closes,
                    "plaintextPinAfterExportRaises": info.as_dict(), "ancestorPinAfterExportRaises": directory_info.as_dict(),
                    "newInvocationBlocked": True, "productionRetirement": "UNKNOWN",
                    "heldThroughInterpreterExit": True, "noPinResetOrRetry": True})
        self.expected_hold = True
        _RETAIN_TO_EXIT.extend((self, directory, plaintext, original))

    def execute(self):
        original = None
        try:
            getattr(self, self.name.replace("-", "_"))()
        except BaseException as error:
            original = error
        # Child-root close is deliberately last. Every earlier failure/secondary
        # is retained privately while a still-owned journal pin remains usable.
        unexpected_hold = (self.unknown or bool(W._QUARANTINE or H._HELD) and not self.expected_hold or
                           original is not None and H.error_detail(original)["retirementUnknown"])
        if not self.expected_hold and not unexpected_hold:
            for owner in reversed(self.owners[1:]):
                try:
                    owner.close()
                except BaseException as error:
                    self.unknown = unexpected_hold = True
                    if original is None:
                        original = error
                    else:
                        F._note(original, H.encoded(H.error_detail(error)).decode("ascii"))
        self.result.update(passed=original is None and not unexpected_hold,
                           expectedPinHoldToInterpreterExit=self.expected_hold,
                           retirement=("UNKNOWN" if unexpected_hold else
                               "EXPECTED_PIN_HOLD_TO_EXIT" if self.expected_hold else "KNOWN"),
                           acceptanceAuthority="PARENT_ZERO_EXIT_AND_NATIVE_JOB_RETIREMENT")
        if original is not None:
            self.result["failure"] = H.error_detail(original)
        try:
            H.private_json(self.root, "result.json", self.result)
        except BaseException as error:
            self.unknown = True
            original = original or error
        if self.expected_hold or self.unknown or unexpected_hold:
            _RETAIN_TO_EXIT.append(self)
        else:
            try:
                self.root.close()
            except BaseException as error:
                # result.json is expressly provisional. Parent exit=1 refuses
                # it even if the very last close fails after its write.
                _RETAIN_TO_EXIT.append(self)
                original = original or error
        return 0 if original is None and not unexpected_hold else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", required=True, choices=H.NATIVE_CASES)
    parser.add_argument("--evidence-dir", required=True)
    args = parser.parse_args()
    fixture = Fixture.__new__(Fixture)
    try:
        Fixture.__init__(fixture, args.case, args.evidence_dir)
        result = fixture.execute()
    except BaseException as error:
        # Preserve construction/late-body failures when a private root was
        # obtained; never print raw paths, SIDs, key material or exception text.
        root = getattr(fixture, "root", None)
        if root is not None:
            try:
                H.private_json(root, "uncaught-failure.json", H.error_detail(error))
            except BaseException:
                _RETAIN_TO_EXIT.append(fixture)
            try:
                if H.error_detail(error)["retirementUnknown"]:
                    _RETAIN_TO_EXIT.append(fixture)
                else:
                    H.close_all(getattr(fixture, "owners", []))
            except BaseException:
                _RETAIN_TO_EXIT.append(fixture)
        result = 1
    print("NATIVE_WINDOWS_HELPER=" + ("CASE_COMPLETED_PENDING_OUTER_RETIREMENT" if result == 0 else "FAIL"))
    return result


if __name__ == "__main__":
    sys.exit(main())
