#!/usr/bin/env python3
"""Real receipt acquisition/file/HTTP-parser composition over synthetic service.

No network, child, native-loader or credential supplier is available. Actual
nonroot POSIX descriptor-relative files and retained codecs/readers/closers run;
RAW/boot, authenticated metadata-envelope and socket suppliers are explicitly
modeled, NOT hosted acceptance.
"""
from contextlib import ExitStack
from copy import deepcopy
import ctypes  # Stdlib setup before rejecting subsequent native loads.
from email.utils import formatdate
import importlib.util
import io
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True
SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))


def offline(event, _args):
    if event.startswith(("subprocess.", "socket.")) or event in (
            "os.system", "os.exec", "os.posix_spawn", "os.fork", "os.forkpty", "pty.spawn", "ctypes.dlopen"):
        raise RuntimeError("RECEIPT_OFFLINE_PROCESS_NETWORK_NATIVE_FORBIDDEN")


sys.addaudithook(offline)


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


M = load("receipt_acquisition_subject", SCRIPTS / "run-hosted-initial-ordinary.py")
F = load("receipt_acquisition_fixture", Path(__file__).with_name("hosted-initial-public-receipt-data-test.py"))
I, D, Q, NS = M.I, F.D, F.Q, M.NS
FIRST = 10 * NS
MODEL_TOKEN = "SYNTHETIC_NOT_A_CREDENTIAL_1234567890"
BLOB = "https://model.blob.core.windows.net/receipt.zip?sig=SYNTHETIC_NOT_SECRET"


def reply(status, body=b"", *, extra=(), date=0):
    fields = [("Date", formatdate(date, usegmt=True)), ("Content-Length", str(len(body))),
        ("Connection", "close"), *extra]
    return ("HTTP/1.1 " + str(status) + " SYNTHETIC\r\n" + "".join(
        key + ": " + value + "\r\n" for key, value in fields) + "\r\n").encode("ascii") + body


class ServiceModel:
    """Only clock/boot/socket suppliers modeled; complete original grammar real."""

    def __init__(self, fixture):
        self.f, self.expected, self.args, self.members = deepcopy(fixture)
        self.zip, self.packet = F.archive(self.members)
        self.entry, self.primary, self.artifact, self.pages = F.service_fixture(self.f, self.packet)
        self.source = self.f["after"]["source"]
        self.job = self.f["job"]
        self.attempt = {"id": int(self.entry["runId"]), "run_attempt": int(self.entry["runAttempt"]),
            "head_sha": self.source["commit"], "head_branch": self.job["head_branch"],
            "path": M.S.bootstrap.WORKFLOW, "event": "workflow_dispatch", "status": "completed",
            "conclusion": "success", "pull_requests": [], "repository": {"full_name": I.REPOSITORY},
            "head_repository": {"full_name": I.REPOSITORY}}
        self.jobs = {"total_count": 1, "jobs": [deepcopy(self.job)]}
        self.raw = FIRST
        self.boot = "e" * 64
        self.clock = M.origin.clocks.ClockIdentity("linux-x64", M.origin.clocks.DOMAINS["linux-x64"], NS)
        self.http, self.requests, self.connections = [], [], []
        self.envelope_change = self.archive_change = None
        self.connection_error = None

    def body(self, path):
        base = Q.API + "/actions/runs/" + self.entry["runId"] + "/attempts/" + self.entry["runAttempt"]
        values = {base: self.attempt, base + "/jobs?per_page=100&page=1": self.jobs,
            Q.API + "/actions/jobs/" + str(self.job["id"]): self.job,
            Q.API + "/actions/artifacts/" + str(self.primary["id"]): self.primary,
            Q.API + "/actions/artifacts/" + str(self.artifact["id"]): self.artifact}
        for original_path, raw in self.pages:
            if path == original_path:
                return raw
        if path not in values:
            raise AssertionError("UNEXPECTED_MODEL_METADATA_PATH")
        return I.encoded(values[path])

    def request(self, path, token, invocation, fence, end):
        if token != MODEL_TOKEN or not path.startswith(Q.API + "/actions/"):
            raise AssertionError("MODEL_GET_ONLY_CREDENTIAL_BOUNDARY")
        self.http.append(path)
        first = fence.now(limit=end)
        body = self.body(path)
        headers = reply(200, body, date=self.f["service_date"], extra=(
            ("Content-Type", "application/json"), ("Cache-Control", "private, no-cache"),
            ("X-GitHub-Api-Version-Selected", "2022-11-28"), ("X-GitHub-Request-Id", "SYNTHETIC:1234")))
        header = headers[:-len(body)]
        value = {"schema": 1, "scope": M.origin.RESPONSE_SCOPE, "origin": M.origin.wire.ORIGIN,
            "method": "GET", "path": path, "invocation": invocation, "clock": M.origin.clock_value(self.clock),
            "startedNs": first, "finishedNs": first, "status": 200,
            "headersBase64": M.base64.b64encode(header).decode("ascii"),
            "bodyBase64": M.base64.b64encode(body).decode("ascii"), "complete": True,
            "retirement": "KNOWN", "error": None}
        if self.envelope_change:
            self.envelope_change(value)
        return I.encoded(value), None

    def checked_now(self, expected, *, minimum_ns=0):
        if expected != self.clock or self.raw < minimum_ns:
            raise M.origin.clocks.ClockError("SYNTHETIC_RAW_IDENTITY_OR_BACKWARDS")
        return self.raw

    def connection_type(self):
        model = self

        class Socket:
            def __init__(self, raw):
                self.stream = io.BytesIO(raw)
            def makefile(self, mode):
                if mode != "rb": raise AssertionError("MODEL_BINARY_SOCKET")
                return self.stream
            def settimeout(self, value):
                if not 0 < value <= M.origin.wire.SOCKET_SECONDS: raise AssertionError("MODEL_SOCKET_BOUND")

        class Connection:
            def __init__(self, host, *, timeout, context):
                if context != "SYNTHETIC_TLS" or not 0 < timeout <= M.origin.wire.SOCKET_SECONDS:
                    raise AssertionError("MODEL_TLS_OR_TIMEOUT")
                self.host, self.closed, self.sock = host, False, None
                model.connections.append(self)
            def request(self, method, path, *, headers):
                model.requests.append((self.host, method, path, dict(headers)))
                if method != "GET": raise AssertionError("MODEL_NO_WRITES")
                if self.host == M.origin.wire.HOST:
                    if headers.get("Authorization") != "Bearer " + MODEL_TOKEN:
                        raise AssertionError("MODEL_API_AUTH_REQUIRED")
                    if path != Q.API + "/actions/artifacts/" + str(model.packet["artifactId"]) + "/zip":
                        raise AssertionError("MODEL_COMPANION_ONLY_DOWNLOAD")
                    raw = reply(302, date=model.f["service_date"], extra=(("Location", BLOB),
                        ("X-GitHub-Api-Version-Selected", "2022-11-28"), ("X-GitHub-Request-Id", "SYNTHETIC:5678")))
                elif self.host == "model.blob.core.windows.net":
                    if "Authorization" in headers or "X-GitHub-Api-Version" in headers:
                        raise AssertionError("MODEL_CREDENTIAL_LEAK")
                    raw = reply(200, model.zip, date=model.f["service_date"])
                else:
                    raise AssertionError("MODEL_UNEXPECTED_ORIGIN")
                if model.archive_change:
                    raw = model.archive_change(self.host, raw)
                self.sock = Socket(raw)
            def getresponse(self):
                response = self.response_class(self.sock, method="GET")
                try:
                    response.begin()
                    return response
                except BaseException:
                    response.close()
                    raise
            def close(self):
                self.closed = True
                if self.sock is not None:
                    self.sock.stream.close()
                if model.connection_error is not None:
                    raise model.connection_error
        return Connection

    def install(self, stack):
        stack.enter_context(patch.object(M.origin.clocks, "observe", side_effect=lambda:
            M.origin.clocks.Reading(self.clock, self.raw)))
        stack.enter_context(patch.object(M.origin.clocks, "checked_now", side_effect=self.checked_now))
        stack.enter_context(patch.object(M.continuity, "boot_digest", side_effect=lambda role: self.boot))
        stack.enter_context(patch.object(M.origin, "_request", side_effect=self.request))
        stack.enter_context(patch.object(M.http.client, "HTTPSConnection", self.connection_type()))
        stack.enter_context(patch.object(M.ssl, "create_default_context", return_value="SYNTHETIC_TLS"))
        stack.enter_context(patch.object(M.time, "time", return_value=self.f["service_date"]))

    def acquire(self, path, **changes):
        args = dict(entry=self.entry, source=self.source, artifact_id=self.packet["artifactId"], private_path=path,
            token=MODEL_TOKEN, cancelled=lambda: None, original_work_end_ns=FIRST + 45 * NS,
            original_final_end_ns=FIRST + 60 * NS)
        return M.acquire_public_receipt(**{**args, **changes})


class PublicReceiptAcquisitionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if os.name != "posix" or os.geteuid() == 0:
            raise AssertionError("RECEIPT_CONTROLS_REQUIRE_REAL_NONROOT_POSIX_FILES")
        cls.fixture = F.fixture()

    def setUp(self):
        self.stack = ExitStack()
        self.temp = self.stack.enter_context(tempfile.TemporaryDirectory(prefix="receipt-acquisition-"))
        self.path = Path(self.temp) / "private"
        for registry in (M._RECEIPT_OWNERS, M._RECEIPT_RETURNS, M._RECEIPT_ATTEMPTS, M._RECEIPT_FENCES,
                M._RECEIPT_OWNER_BINDINGS):
            registry.clear()
        M._RECEIPT_QUARANTINE.clear()
        self.model = ServiceModel(self.fixture)
        self.model.install(self.stack)
        self.addCleanup(self.stack.close)
        self.addCleanup(self.cleanup_resources)
        # Synthetic UNKNOWN injections first close the failing descriptor then
        # report UNKNOWN. The harness separately closes any still-unattempted
        # sibling/directory handles, never replaying an unknown close or making
        # a production success claim from that test-only physical cleanup.

    def cleanup_resources(self):
        for owner in M._RECEIPT_OWNERS.values():
            for row in reversed(owner.resources):
                if not row[2]:
                    row[2] = True
                    try:
                        row[1].close()
                        row[3] = True
                    except Exception:
                        # A failed original pathname check still closes the
                        # actual PosixFile/PosixDirectory descriptor pins.
                        if not row[1].closed:
                            raise
                self.assertTrue(getattr(row[1], "closed", False))

    def test_real_original_files_http_parser_close_and_separate_typed_result(self):
        old = tuple(len(value) for value in (M._OWNERS, M._CLOSES, M._RETURNS, M._NATIVE_RETURNS))
        result = self.model.acquire(self.path)
        self.assertIs(M.checked_public_receipt(result), result)
        self.assertEqual(dict(result.members), self.model.members)
        self.assertEqual(result.packet_raw, self.model.zip)
        record = I.parse(result.record, M.SMALL_LIMIT)
        self.assertEqual((record["qualification"], record["h2Authority"]), ("NOT_ESTABLISHED", "NOT_CREATED"))
        self.assertEqual(old, tuple(len(value) for value in (M._OWNERS, M._CLOSES, M._RETURNS, M._NATIVE_RETURNS)))
        self.assertEqual(len(self.model.http), 6)
        self.assertEqual(len(self.model.requests), 2)
        self.assertTrue(all(connection.closed for connection in self.model.connections))
        self.assertNotIn(MODEL_TOKEN.encode(), result.record)
        self.assertNotIn(BLOB.encode(), result.record)
        originals = dict(result.originals)
        for name, raw in originals.items():
            self.assertEqual((self.path / name).read_bytes(), raw)
        self.assertEqual(I.parse(originals["archive-download.json"], M.SMALL_LIMIT)["retirement"], "KNOWN")
        owner = M._RECEIPT_RETURNS[id(result)][1]
        self.assertTrue(all(row[2] is row[3] is True for row in owner.resources))
        with self.assertRaises(I.AdmissionError):
            M.checked_public_receipt(M.PublicReceiptAcquisition(result.record, result.members, result.packet_raw, result.originals))
        object.__setattr__(result, "packet_raw", result.packet_raw + b"x")
        with self.assertRaises(I.AdmissionError): M.checked_public_receipt(result)

    def test_original_target_job_primary_and_http_envelope_joins(self):
        changes = (
            lambda m: m.job.update(id=m.job["id"] + 1),
            lambda m: m.job.update(runner_name="DIFFERENT_MODEL_RUNNER"),
            lambda m: m.attempt.update(run_attempt=99),
            lambda m: m.primary.update(digest="sha256:" + "f" * 64),
            lambda m: setattr(m, "pages", ((m.pages[0][0], I.encoded({"total_count": 3,
                "artifacts": [m.primary, m.artifact, m.artifact]})),)),
            lambda m: setattr(m, "envelope_change", lambda value: value.update(complete=False)),
            lambda m: setattr(m, "envelope_change", lambda value: value.update(method="POST")),
        )
        for index, change in enumerate(changes):
            with self.subTest(index=index), ExitStack() as nested:
                M._RECEIPT_ATTEMPTS.clear()
                model = ServiceModel(self.fixture); change(model); model.install(nested)
                with self.assertRaises(Exception): model.acquire(Path(self.temp) / ("case-" + str(index)))
                self.assertEqual(model.requests, [])
        self.assertEqual(M._RECEIPT_RETURNS, {})

    def test_completed_service_and_original_member_external_identity_join(self):
        original_service = D.public_receipt_service_inputs
        # Call actual codecs first. Changing only the declared outside tree is
        # invisible to GitHub artifact metadata but MUST fail the U/A join.
        source = {**self.model.source, "tree": "f" * 40}
        called = []
        def service(*args):
            called.append(True)
            return original_service(*args)
        with patch.object(D, "public_receipt_service_inputs", side_effect=service):
            with self.assertRaisesRegex(I.AdmissionError, "RECEIPT_ORIGINAL_SOURCE_AND_RUN"):
                self.model.acquire(self.path, source=source)
        self.assertEqual(called, [True])
        self.assertEqual(M._RECEIPT_RETURNS, {})

    def test_same_bytes_replacement_after_download_and_real_private_path_rejected(self):
        original_download = M._download
        def replace(owner, directory, packet, token, invocation, end):
            original_download(owner, directory, packet, token, invocation, end)
            current = Path(directory.path) / "packet.zip"
            changed = Path(directory.path) / "substitute.zip"
            changed.write_bytes(current.read_bytes()); changed.chmod(0o600)
            os.replace(changed, current)
        with patch.object(M, "_download", side_effect=replace):
            with self.assertRaisesRegex(I.AdmissionError, "RECEIPT_DOWNLOAD_READER_IDENTITY"):
                self.model.acquire(self.path)
        self.assertEqual(M._RECEIPT_RETURNS, {})
        link = Path(self.temp) / "symlink"
        link.symlink_to(self.path, target_is_directory=True)
        for path in (self.path, link, Path(self.temp) / ".." / "wrong"):
            with self.subTest(path=path.name), self.assertRaises(I.AdmissionError): self.model.acquire(path)
        # The reused Windows DATA policy allows only genuine write-close times,
        # not identity/ACL/size drift; this is NOT native Windows execution.
        before = {"identity": [123, "a" * 32], "is_directory": False, "size": 5, "links": 1,
            "attributes": 0, "creation_100ns": 100, "modified_100ns": 101, "change_100ns": 102,
            "owner_sid": "S-1-5-21-100", "protected_dacl": True}
        after = {**before, "modified_100ns": 120, "change_100ns": 121}
        self.assertEqual(D.B.write_close_metadata("windows-x64", before, after, 5),
            "WINDOWS_WRITE_CLOSE_MODIFIED_CHANGE_ONLY")
        for key, value in (("identity", [123, "b" * 32]), ("size", 6), ("owner_sid", "S-1-5-21-101"),
                ("protected_dacl", False), ("links", 2), ("creation_100ns", 999), ("attributes", 1)):
            with self.subTest(field=key), self.assertRaises(Exception):
                D.B.write_close_metadata("windows-x64", before, {**after, key: value}, 5)

    def test_archive_digest_redirect_and_connection_unknown_stop_without_retry(self):
        cases = (
            lambda m: setattr(m, "zip", m.zip[:-1] + bytes([m.zip[-1] ^ 1])),
            lambda m: setattr(m, "archive_change", lambda host, raw:
                raw.replace(BLOB.encode(), b"https://api.github.com/forbidden") if host == M.origin.wire.HOST else raw),
            lambda m: setattr(m, "connection_error", OSError("SYNTHETIC_ALREADY_CLOSED_BUT_UNKNOWN")),
        )
        for index, change in enumerate(cases):
            with self.subTest(index=index), ExitStack() as nested:
                M._RECEIPT_ATTEMPTS.clear(); M._RECEIPT_QUARANTINE.clear()
                model = ServiceModel(self.fixture); change(model); model.install(nested)
                path = Path(self.temp) / ("bad-download-" + str(index))
                with self.assertRaises(Exception): model.acquire(path)
                before = len(model.requests)
                with self.assertRaises(I.AdmissionError): model.acquire(path)
                self.assertEqual(len(model.requests), before)
                self.assertLessEqual(before, 2)
                self.assertTrue(all(connection.closed for connection in model.connections))
        self.assertTrue(M._RECEIPT_QUARANTINE)
        self.assertEqual(M._RECEIPT_RETURNS, {})

    def test_reader_and_writer_unknown_close_are_not_success_or_retried(self):
        original_close = M.files.PosixFile.close
        for index, kind in enumerate(("writer", "reader")):
            with self.subTest(kind=kind):
                M._RECEIPT_ATTEMPTS.clear(); M._RECEIPT_QUARANTINE.clear()
                calls = []
                def close(resource):
                    target = resource.path.name == "packet.zip" and resource.writable == (kind == "writer")
                    original_close(resource)
                    if target:
                        calls.append(resource)
                        raise OSError("SYNTHETIC_CLOSE_RETURN_UNKNOWN_AFTER_REAL_CLOSE")
                with patch.object(M.files.PosixFile, "close", close):
                    with self.assertRaises(OSError): self.model.acquire(Path(self.temp) / kind)
                self.assertEqual(len(calls), 1)
                self.assertTrue(calls[0].closed)
                self.assertTrue(M._RECEIPT_QUARANTINE)
        self.assertEqual(M._RECEIPT_RETURNS, {})
        M._RECEIPT_QUARANTINE.clear()
        fence = M._ReceiptFence(FIRST + 45 * NS, FIRST + 60 * NS, lambda: None)
        owner = M._ReceiptOwner(M._RECEIPT_KEY, fence)
        directory = owner.directory(Path(self.temp) / "known-failure", create=True)
        writer = owner.acquire("archive-writer", lambda: directory.create_file("packet.zip", max_bytes=16,
            deadline=fence.work_local))
        writer.write(b"MODEL")
        verify, visits = writer.verify, []
        failure = ValueError("SYNTHETIC_KNOWN_PRECLOSE_METADATA_FAILURE")
        def fail_first_only():
            visits.append(True)
            if len(visits) == 1: raise failure
            return verify()
        with patch.object(writer, "verify", side_effect=fail_first_only):
            with self.assertRaises(ValueError) as caught: owner.close()
        self.assertIs(caught.exception, failure)
        self.assertEqual(len(visits), 2)  # preclose fails; real close succeeds.
        self.assertFalse(owner.unknown)
        self.assertTrue(owner.closed)
        self.assertTrue(all(row[2] is row[3] is True for row in owner.resources))
        self.assertTrue(directory.closed and writer.closed)
        self.assertEqual(M._RECEIPT_RETURNS, {})

    def test_original_clipped_ends_boot_local_raw_and_callback_reentry_latch(self):
        fence = M._ReceiptFence(FIRST + 90 * NS, FIRST + 100 * NS, lambda: None)
        self.assertEqual((fence.work, fence.final), (FIRST + 45 * NS, FIRST + 60 * NS))
        short = M._ReceiptFence(FIRST + 2 * NS, FIRST + 3 * NS, lambda: None)
        self.assertEqual((short.work, short.final), (FIRST + 2 * NS, FIRST + 3 * NS))
        for ends in ((FIRST, FIRST + NS), (FIRST + 10 * NS, FIRST + 9 * NS), (True, FIRST + NS)):
            with self.subTest(ends=ends), self.assertRaises(Exception): M._ReceiptFence(*ends, lambda: None)
        for change in ("raw", "boot", "local", "end", "reentry", "cancel"):
            with self.subTest(change=change):
                self.model.raw, self.model.boot = FIRST, "e" * 64
                current = None
                def callback():
                    if change == "raw": self.model.raw = FIRST + 45 * NS
                    elif change == "boot": self.model.boot = "f" * 64
                    elif change == "local": current.work_local = 10 ** 15
                    elif change == "end": current.work += NS
                    elif change == "cancel": raise KeyboardInterrupt("SYNTHETIC_CANCELLATION")
                    elif change == "reentry":
                        try: current.now()
                        except Exception: pass
                current = M._ReceiptFence(FIRST + 45 * NS, FIRST + 60 * NS, callback)
                with self.assertRaises(BaseException): current.now()
                first_failure = current.failure
                with self.assertRaises(BaseException) as caught: current.now()
                self.assertIs(caught.exception, first_failure)
        self.model.raw, self.model.boot = FIRST, "e" * 64
        original = M._ReceiptFence(FIRST + 45 * NS, FIRST + 60 * NS, lambda: None)
        local = M._RECEIPT_FENCES[id(original)][3]
        with patch.object(M.time, "monotonic", return_value=local - 0.5):
            with self.assertRaisesRegex(I.AdmissionError, "LOCAL_BACKWARDS"): original.now()
        backwards = M._ReceiptFence(FIRST + 45 * NS, FIRST + 60 * NS, lambda: None)
        self.model.raw = FIRST - 1
        with self.assertRaises(M.origin.clocks.ClockError): backwards.now()

    def test_cancellation_final_cleanup_owner_mutation_and_no_h2_factory(self):
        def cancel(): raise KeyboardInterrupt("SYNTHETIC_NO_LIVE_TASK")
        with self.assertRaises(KeyboardInterrupt): self.model.acquire(self.path, cancelled=cancel)
        self.assertEqual(self.model.http, [])
        owner = next(iter(M._RECEIPT_OWNERS.values()))
        self.assertTrue(owner.closed)
        self.assertFalse(owner.unknown)
        self.assertEqual(M._RECEIPT_RETURNS, {})
        self.model.raw = FIRST
        M._RECEIPT_ATTEMPTS.clear()
        swapped = []
        def swap_owner_fence():
            current = list(M._RECEIPT_OWNERS.values())[-1]
            if current.resources and not swapped:
                swapped.append(current)
                current.fence = M._ReceiptFence(FIRST + 100 * NS, FIRST + 120 * NS, lambda: None)
        with self.assertRaisesRegex(I.AdmissionError, "RECEIPT_OWNER_BINDING_CHANGED"):
            self.model.acquire(Path(self.temp) / "swap-owner-fence", cancelled=swap_owner_fence)
        self.assertEqual(len(swapped), 1)
        self.assertTrue(swapped[0].closed)
        self.assertFalse(swapped[0].unknown)
        self.assertTrue(all(row[2] is row[3] is True for row in swapped[0].resources))
        self.assertEqual(self.model.http, [])
        self.assertEqual(M._RECEIPT_RETURNS, {})
        fence = M._ReceiptFence(FIRST + 45 * NS, FIRST + 60 * NS, lambda: None)
        with self.assertRaises(I.AdmissionError): M._Owner(M._OWNER_KEY, fence)
        with self.assertRaises(I.AdmissionError): M._ReceiptOwner(object(), fence)
        normal = M._ReceiptOwner(M._RECEIPT_KEY, fence)
        normal.thread += 1
        with self.assertRaises(I.AdmissionError): normal.guard()
        with self.assertRaises(I.AdmissionError): normal.close()


if __name__ == "__main__":
    unittest.main(failfast=True)
