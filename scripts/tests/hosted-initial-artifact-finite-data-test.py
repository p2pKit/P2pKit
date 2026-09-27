#!/usr/bin/env python3
"""New finite R/I/F and safe pending DATA controls; NOT native qualification."""
from __future__ import annotations

import _strptime
import base64
import ctypes
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch


GUARDED = False


def offline(event, _args):
    if event.startswith(("subprocess.", "socket.")) or event in (
            "os.system", "os.exec", "os.posix_spawn", "os.fork", "os.forkpty", "pty.spawn", "ctypes.dlopen",
            "os.putenv", "os.unsetenv") or GUARDED and event in ("open", "os.listdir", "os.scandir"):
        raise AssertionError("FINITE_DATA_SIDE_EFFECT")


sys.dont_write_bytecode = True
sys.addaudithook(offline)
SCRIPTS = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(SCRIPTS), str(SCRIPTS / "tests")]
import hosted_initial_artifact_delivery as D
import hosted_initial_artifact_finite_fixtures as F

NS, NOW = F.NS, F.NOW


def parsed(value, mode="finish"):
    return D.control_input(F.wire(value), mode)


def finish(value):
    return D.finish_observations(parsed(value), now=NOW)


def rebind_original(value, mode, index, body):
    """Rebind all transport hashes so the semantic predicate is decisive."""
    rows = value["beforeOriginals" if mode == "finish" else "afterOriginals"]
    row = rows[index]
    raw = F.wire(body)
    row.update(bodyBase64=base64.b64encode(raw).decode("ascii"), rawHeaderVector=F.headers(raw))
    request = value["beforeClosed" if mode == "finish" else "afterClosed"]["requests"][index]
    request.update(bodyBytes=len(raw), bodySha256=F.sha(raw), rawHeaderVectorSha256=F.sha(json.dumps(
        row["rawHeaderVector"], separators=(",", ":"), ensure_ascii=False).encode("utf-8")))


class FiniteDataControls(unittest.TestCase):
    def setUp(self):
        global GUARDED
        GUARDED = True
        self.model = F.fixture(D)

    def tearDown(self):
        global GUARDED
        GUARDED = False

    def reject(self, value, mutate, validate):
        validate(value)
        changed = F.copy(value)
        mutate(changed)
        self.assertNotEqual(F.wire(changed), F.wire(value), "negative mutation must not be a no-op")
        with self.assertRaises(ValueError):
            validate(changed)

    def test_finish_retains_exact_raw_frames_and_complete_original_projections(self):
        value = self.model["control"]
        control = parsed(value)
        self.assertEqual(control[2:], (self.model["ready_raw"], self.model["final_raw"]))
        actual = finish(value)
        self.assertEqual(actual[0], self.model["ready"])
        self.assertEqual(actual[2:5], tuple(value[name] for name in ("readerClosed", "beforeClosed", "transportClosed")))
        self.assertEqual(actual[5]["steps"]["upload"]["number"], 5)

    def test_complete_input_bound_includes_five_byte_header_and_rejects_noncanonical_json(self):
        raw = F.wire(self.model["control"])
        self.assertEqual(D.INPUT_BYTES + 5, 2 * 1024 * 1024)
        for invalid in (raw[:-1], b" " + raw, raw + b"\n", b'{"schema":1,"schema":1}\n',
                raw.replace(b'"schema":1', b'"schema":1.0', 1), b"x" * (D.INPUT_BYTES + 1)):
            with self.subTest(size=len(invalid)), self.assertRaises(ValueError):
                D.control_input(invalid, "finish")

    def test_all_rosters_and_encoded_body_bounds_precede_either_body_decode(self):
        after = F.after(D, self.model)["control"]
        for mutate in (lambda value: value["afterOriginals"][1].update(bodyBase64="A" * (4 * ((D.HTTP_LIMIT + 2) // 3) + 4)),
                lambda value: value["afterOriginals"][1].update(private="MODEL_PRIVATE"),
                lambda value: value["afterOriginals"][1].update(kind="job")):
            changed = F.copy(after)
            mutate(changed)
            with patch.object(D, "_base64", side_effect=AssertionError("DECODE_BEFORE_ALL_SHAPE_CHECKS")), \
                    self.assertRaises(ValueError):
                parsed(changed, "after")

    def test_two_maximal_originals_cannot_be_truncated_or_omitted_to_fit_input(self):
        after = F.after(D, self.model)["control"]
        for row in after["afterOriginals"]:
            row["bodyBase64"] = base64.b64encode(b" " * D.HTTP_LIMIT).decode("ascii")
        self.assertGreater(len(F.wire(after)) + 5, 2 * 1024 * 1024)
        with patch.object(D, "_base64", side_effect=AssertionError("OVERSIZE_INPUT_DECODE")), self.assertRaises(ValueError):
            parsed(after, "after")
        short = F.after(D, self.model)["control"]
        short["afterOriginals"].pop()
        with self.assertRaises(ValueError):
            parsed(short, "after")

    def test_base64_alias_padding_and_original_frame_caps_fail_closed(self):
        for value in ("YR==", "YQ", "YQ==\n", "===="):
            with self.subTest(value=value), self.assertRaises(ValueError):
                D._base64(value, 1)
        self.assertEqual(D._base64("YQ==", 1), b"a")
        self.reject(self.model["control"], lambda value: value.update(
            readerReadyBase64=base64.b64encode(b" " * (D.LIMIT + 1)).decode("ascii")), parsed)

    def test_ready_requires_exact_uint64_identity_policy_and_original_window(self):
        validate = lambda value: D.stream_ready(F.wire(value))
        for mutate in (lambda value: value.update(workEndNs=True),
                lambda value: value["github"].update(jobId=True),
                lambda value: value["originals"].update(policySha256="0" * 64),
                lambda value: value.update(jobOriginal=[9002, "2026-09-26T00:00:00Z", "bad\nrunner", 9003])):
            self.reject(self.model["ready"], mutate, validate)
        # This lower handoff predicate has its own precise RuntimeError subtype.
        validate(self.model["ready"])
        changed = F.copy(self.model["ready"])
        changed["originalWindow"]["uploadEndNs"] = 407 * NS
        self.assertNotEqual(F.wire(changed), F.wire(self.model["ready"]), "negative mutation must change bytes")
        with self.assertRaises(D.E.posix.EvidenceError) as caught:
            validate(changed)
        self.assertIs(type(caught.exception), D.E.posix.EvidenceError)
        self.assertEqual(str(caught.exception), "INITIAL_TAIL_EVIDENCE_HANDOFF_WINDOW_ORIGINAL_ARITHMETIC")

    def test_finite_validity_has_same_finite_fourteen_day_authority_cap(self):
        changed = F.copy(self.model["ready"])
        changed.update(policyNotBefore=NOW - 20 * 86400, authorityNotBefore=NOW - 15 * 86400)
        with self.assertRaises(ValueError):
            D.stream_ready(F.wire(changed))
        for field in D.UTC_FIELDS:
            self.reject(self.model["ready"], lambda value, name=field: value.update({name: True}),
                lambda value: D.stream_ready(F.wire(value)))

    def test_stream_final_binds_native_close_and_cannot_self_attest_process(self):
        validate = lambda value: D.stream_closed(F.wire(value), self.model["ready_raw"])
        for mutate in (lambda value: value.update(readySha256="0" * 64),
                lambda value: value.update(zipBytes=True), lambda value: value.update(nativeCloseSha256="bad"),
                lambda value: value.update(closedNs=self.model["ready"]["workEndNs"]),
                lambda value: value.update(originalReaderOutcome="RETURNED")):
            self.reject(self.model["final"], mutate, validate)

    def test_all_reader_pipe_process_eof_and_write_callbacks_remain_mandatory(self):
        for flag in D.READER_FLAGS:
            self.reject(self.model["control"], lambda value, name=flag: value["readerClosed"].update({name: False}), finish)
        for name in ("stdin", "stdout", "stderr"):
            self.reject(self.model["control"], lambda value, key=name: value["readerClosed"]["originalPipeCloses"].update(
                {key: False}), finish)

    def test_reader_original_metadata_and_local_return_cannot_be_replaced(self):
        for mutate in (lambda value: value["readerClosed"].update(stderrBytes=1),
                lambda value: value["readerClosed"].update(finalSha256="0" * 64),
                lambda value: value["readerClosed"].update(returnedLocalNs=str(155 * NS)),
                lambda value: value["readerClosed"].update(preSpawnLocalNs=str(101 * NS))):
            self.reject(self.model["control"], mutate, finish)

    def test_before_all_original_tls_http_closes_and_complete_bodies_are_required(self):
        for flag in D.OBSERVER_FLAGS:
            self.reject(self.model["control"], lambda value, name=flag: value["beforeClosed"]["requests"][0].update(
                {name: False}), finish)
        for field, wrong in (("bodyBytes", 1), ("bodySha256", "0" * 64), ("rawHeaderVectorSha256", "0" * 64),
                ("id", "9003"), ("dateEpochSeconds", NOW + 1)):
            self.reject(self.model["control"], lambda value, key=field, item=wrong:
                value["beforeClosed"]["requests"][0].update({key: item}), finish)

    def test_before_current_step_and_original_runner_checks_survive_rehashed_body(self):
        for mutate in (lambda value: value.update(runner_id=9004), lambda value: value.update(run_attempt=3),
                lambda value: value["steps"][3].update(conclusion="failure"),
                lambda value: value["steps"][4].update(number=6)):
            changed = F.copy(self.model["control"])
            body = F.job(D, "upload")
            mutate(body)
            rebind_original(changed, "finish", 0, body)
            with self.assertRaises(ValueError):
                finish(changed)

    def test_original_observer_clock_cannot_move_past_its_cap_or_precede_reader(self):
        for mutate in (lambda value: value["beforeClosed"].update(enteredNs=str(99 * NS)),
                lambda value: value["beforeClosed"].update(lastObservationNs=str(106 * NS)),
                lambda value: value["beforeClosed"]["requests"][0].update(endNs=str(107 * NS)),
                lambda value: value["beforeClosed"]["requests"][0].update(closedNs=str(100 * NS))):
            self.reject(self.model["control"], mutate, finish)

    def test_transport_full_create_block_blocklist_finalize_roster_and_closes(self):
        for flag in D.TRANSPORT_FLAGS:
            self.reject(self.model["control"], lambda value, name=flag: value["transportClosed"]["requests"][1].update(
                {name: False}), finish)
        for mutate in (lambda value: value["transportClosed"]["requests"].pop(),
                lambda value: value["transportClosed"]["requests"].reverse(),
                lambda value: value["transportClosed"].update(inputCloseObserved=False),
                lambda value: value["transportClosed"].update(submittedFinalizeHash="sha256:" + "0" * 64)):
            self.reject(self.model["control"], mutate, finish)

    def test_each_transport_body_size_status_and_response_bound_is_validated(self):
        for index in range(4):
            for field in ("bodyBytes", "status"):
                self.reject(self.model["control"], lambda value, row=index, key=field:
                    value["transportClosed"]["requests"][row].update({key:
                        value["transportClosed"]["requests"][row][key] + 1}), finish)
        self.reject(self.model["control"], lambda value: value["transportClosed"]["requests"][1].update(responseBytes=1), finish)

    def test_transport_clocks_do_not_refresh_at_finalization_or_finish(self):
        for mutate in (lambda value: value["transportClosed"].update(enteredNs=str(106 * NS)),
                lambda value: value["transportClosed"].update(returnedObservationNs=str(160 * NS)),
                lambda value: value["transportClosed"]["requests"][0].update(startNs=str(106 * NS)),
                lambda value: value["transportClosed"]["requests"][3].update(startNs=str(155 * NS))):
            self.reject(self.model["control"], mutate, finish)

    def test_original_requested_retention_is_fourteen_days_not_a_later_reissue(self):
        for field, changed in (("requestedRetentionDays", 15), ("requestedExpiresAt", "2026-10-11T00:00:30.000Z"),
                ("createInvokedAt", "2026-09-27T00:00:30.000Z"), ("artifactId", "09010")):
            self.reject(self.model["control"], lambda value, name=field, item=changed:
                value["transportClosed"].update({name: item}), finish)

    def test_finish_rechecks_current_utc_and_complete_http_freshness(self):
        control = parsed(self.model["control"])
        with self.assertRaises(ValueError):
            D.finish_observations(control, now=self.model["match"]["expiresAt"])
        changed = F.copy(self.model["control"])
        changed["beforeOriginals"][0]["rawHeaderVector"][1] = "Sat, 26 Sep 2026 00:00:31 GMT"
        with self.assertRaises(ValueError):
            finish(changed)

    def test_upload_pending_projects_actual_complete_hashes_without_private_originals(self):
        raw = F.upload(D, self.model)
        value = D.parse_delivery(raw, "finish")
        self.assertEqual(value["artifact"]["id"], "9010")
        self.assertEqual(value["times"]["finishFirstRawNs"], str(345 * NS))
        self.assertEqual(value["observations"]["transportClosedSha256"], F.sha(F.wire(self.model["control"]["transportClosed"])))
        for text in (b"MODEL_RUNNER", b"MODEL_HEADER", b"bodyBase64", b"rawHeaderVector", b"jobOriginal"):
            self.assertNotIn(text, raw)
        self.assertEqual(value["privateOriginals"], "TERMINAL_SELF_TAIL_NOT_DELIVERED")
        self.assertLessEqual(len(raw), D.LIMIT)

    def test_safe_pending_rosters_refuse_arbitrary_private_fields_at_every_map(self):
        value = json.loads(F.upload(D, self.model))
        for path in ((), ("source",), ("github",), ("originals",), ("artifact",), ("times",), ("observations",)):
            def mutate(changed):
                target = changed
                for name in path:
                    target = target[name]
                target["private"] = "MODEL_PRIVATE"
            self.reject(value, mutate, lambda supplied: D.pending_value(supplied, "finish"))
        for path, error, code in (
                (("deadline",), D.B.continuity.ContinuityError, "SEAL_DEADLINE_FIELDS"),
                (("originalWindow",), D.E.posix.EvidenceError, "INITIAL_TAIL_EVIDENCE_HANDOFF_FIELDS"),
                (("members", 0), D.E.posix.EvidenceError, "INITIAL_TAIL_EVIDENCE_HANDOFF_FIELDS")):
            D.pending_value(value, "finish")
            changed = F.copy(value)
            target = changed
            for name in path:
                target = target[name]
            target["private"] = "MODEL_PRIVATE"
            self.assertNotEqual(F.wire(changed), F.wire(value), "negative mutation must change bytes")
            with self.assertRaises(error) as caught:
                D.pending_value(changed, "finish")
            self.assertIs(type(caught.exception), error)
            self.assertEqual(str(caught.exception), code)

    def test_pending_times_step_adjacency_and_nonacceptance_constants_are_closed(self):
        value = json.loads(F.upload(D, self.model))
        for mutate in (lambda supplied: supplied["times"].update(finishFirstRawNs=str(343 * NS)),
                lambda supplied: supplied["times"].update(pendingPreparedNs=str(395 * NS)),
                lambda supplied: supplied["observations"].update(uploadStepNumber=6),
                lambda supplied: supplied["observations"].update(transportRequestCount=3),
                lambda supplied: supplied.update(writerReturn="RETURNED"),
                lambda supplied: supplied.update(qualification="PASS")):
            self.reject(value, mutate, lambda supplied: D.pending_value(supplied, "finish"))

    def test_finish_binds_actual_current_k_source_members_and_utc(self):
        for mutate in (lambda model: model["pending"]["source"].update(tree="a" * 40),
                lambda model: model["pending"]["members"][0].update(sha256="a" * 64),
                lambda model: model["policy"].update(notBefore=NOW - 3500)):
            changed = {**self.model, "pending": F.copy(self.model["pending"]), "policy": dict(self.model["policy"])}
            mutate(changed)
            with self.assertRaises(ValueError):
                F.upload(D, changed)

    def test_after_ready_rechecks_actual_original_u_and_k_not_only_hash_shapes(self):
        after = F.after(D, self.model)
        original = json.loads(after["upload_raw"])
        def validate(value):
            return D.after_ready(self.model["pending"], F.wire(value), policy=self.model["policy"], match=self.model["match"],
                first=405 * NS, before_sha256=self.model["ready"]["beforeSha256"], now=NOW)
        for mutate in (lambda value: value["source"].update(tree="a" * 40),
                lambda value: value.update(beforeSha256="0" * 64), lambda value: value["members"][0].update(sha256="0" * 64),
                lambda value: value.update(authorityNotBefore=NOW - 59)):
            self.reject(original, mutate, validate)

    def test_after_keeps_both_original_responses_on_one_observer_end(self):
        after = F.after(D, self.model)
        validate = lambda value: F.delivery(D, self.model, {**after, "control": value})
        for mutate in (lambda value: value["afterOriginals"].reverse(),
                lambda value: value["afterClosed"]["requests"][1].update(endNs=str(216 * NS)),
                lambda value: value["afterClosed"]["requests"][1].update(startedNs=str(200 * NS)),
                lambda value: value["afterClosed"].update(requestSha256="0" * 64),
                lambda value: value["afterClosed"]["requests"][1].update(socketCloseObserved=False)):
            self.reject(after["control"], mutate, validate)

    def test_after_retains_service_shortened_expiry_and_original_u_owner_close(self):
        after = F.after(D, self.model)
        value = D.parse_delivery(F.delivery(D, self.model, after), "after")
        self.assertEqual(value["uploadSha256"], F.sha(after["upload_raw"]))
        self.assertEqual(value["uploadCarrier"], after["carrier"])
        self.assertEqual(value["artifact"]["expiresAt"], after["artifact"]["expires_at"])
        self.assertLess(value["artifact"]["expiresAt"], value["artifact"]["requestedExpiresAt"])
        self.assertEqual(value["observations"]["observerRequestCount"], 2)
        self.assertEqual(value["originalStepOutcome"], "NOT_OBSERVED")

    def test_after_artifact_checks_real_id_source_digest_expiry_even_after_rehash(self):
        after = F.after(D, self.model)
        for mutate in (lambda value: value.update(id=9011), lambda value: value.update(size_in_bytes=557),
                lambda value: value.update(digest="sha256:" + "0" * 64), lambda value: value.update(expired=True),
                lambda value: value["workflow_run"].update(id=9002),
                lambda value: value["workflow_run"].update(head_sha="0" * 40),
                lambda value: value.update(expires_at="2026-10-10T00:00:31Z"),
                lambda value: value.update(created_at="2026-09-26T00:00:29Z")):
            changed = F.copy(after["control"])
            artifact = F.copy(after["artifact"])
            mutate(artifact)
            rebind_original(changed, "after", 1, artifact)
            with self.assertRaises(ValueError):
                F.delivery(D, self.model, {**after, "control": changed})

    def test_after_rehashed_job_requires_original_runner_u_success_and_a_adjacency(self):
        after = F.after(D, self.model)
        for mutate in (lambda value: value.update(runner_id=9004),
                lambda value: value["steps"][4].update(conclusion="failure"),
                lambda value: value["steps"][5].update(number=7)):
            changed = F.copy(after["control"])
            body = F.job(D, "after")
            mutate(body)
            rebind_original(changed, "after", 0, body)
            with self.assertRaises(ValueError):
                F.delivery(D, self.model, {**after, "control": changed})

    def test_finite_f_hashes_actual_independent_preimages_and_cannot_claim_own_close(self):
        for mode in ("finish", "after"):
            after = F.after(D, self.model) if mode == "after" else None
            pending = F.delivery(D, self.model, after) if after else F.upload(D, self.model)
            ready = after["ready_raw"] if after else self.model["ready_raw"]
            control = F.wire(after["control"] if after else self.model["control"])
            directory, metadata, closed = b'[1,2]\n', b'{"model":"full-readback-metadata"}\n', b'{"model":"original-close"}\n'
            raw = D.finite_result(mode, pending, ready_raw=ready, input_raw=control, directory_identity_raw=directory,
                file_metadata_raw=metadata, file_owner_close_raw=closed, closed_ns=(408 if after else 347) * NS)
            value = D.canonical(raw)
            self.assertEqual(value["inputSha256"], F.sha(control))
            self.assertEqual(value["directoryIdentitySha256"], F.sha(directory))
            self.assertEqual(value["fileMetadataSha256"], F.sha(metadata))
            self.assertEqual(value["fileOwnerCloseSha256"], F.sha(closed))
            self.assertEqual(F.wire(value["pending"]), pending)
            self.assertEqual(value["originalHelperOutcome"], "PENDING_ENCLOSING_PROCESS_CLOSE")
            self.assertLessEqual(len(raw), D.LIMIT)

    def test_finite_f_cannot_return_before_pending_or_at_original_end(self):
        pending = F.upload(D, self.model)
        for closed in (345 * NS, 395 * NS, True):
            with self.subTest(closed=closed), self.assertRaises(ValueError):
                D.finite_result("finish", pending, ready_raw=self.model["ready_raw"], input_raw=F.wire(self.model["control"]),
                    directory_identity_raw=b"[]\n", file_metadata_raw=b"{}\n", file_owner_close_raw=b"{}\n", closed_ns=closed)


if __name__ == "__main__":
    unittest.main(failfast=True)
