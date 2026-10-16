"""Bootstrap service originals; no productive/job-budget authority.

Used only by the separate, dormant acquisition controller. The 120/75-second
prelude is a conservative, UNMEASURED evidence-only source cap, not a service-job
allocation or execution permission. No ordinary profile is substituted here.
Private and initial-provider public transports have distinct response scopes;
neither can serve as a fallback for the other.
Imports do not acquire clocks, files, native owners, credentials or network.
"""
from __future__ import annotations

import base64
import http.client
import math
import re
import ssl
import time

import hosted_cache_bootstrap_identity as bootstrap
import hosted_full_job_budget as wire
import hosted_job_clock as clocks
import hosted_initial_recipient_public_origin as public_provider


NS = clocks.NS
PRELUDE_SECONDS, WORK_SECONDS = 120, 75
RESPONSE_SCOPE = "PRIVATE_BOOTSTRAP_SERVICE_RESPONSE_V1"
PRELUDE_SCOPE = "BOOTSTRAP_EVIDENCE_ONLY_PRELUDE_V1"
SERVICE_SELECTORS = {
    "linux-x64": "ubuntu-latest", "windows-x64": "windows-latest",
    "macos-arm64": "macos-26", "macos-x64": "macos-15-intel",
}


class OriginError(ValueError):
    """Finite source-owned reason, never a token/HTTP/private-path diagnostic."""


def require(value, reason):
    if not value:
        raise OriginError(reason)


def integer(value, minimum=0):
    require(type(value) is int and minimum <= value <= clocks.UINT64, "BOOTSTRAP_ORIGIN_INTEGER")
    return value


def digest(raw):
    return wire.digest(raw)


def encoded(value):
    return wire.encoded(value)


def parse(raw):
    return wire.parse(raw)


def clock_value(clock):
    return wire.clock_value(clock)


def prelude(first):
    clocks.validate_reading(first)
    return {"schema": 1, "scope": PRELUDE_SCOPE, "clock": clock_value(first.clock),
            "firstNs": first.nanoseconds,
            "workEndNs": integer(first.nanoseconds + WORK_SECONDS * NS),
            "finalEndNs": integer(first.nanoseconds + PRELUDE_SECONDS * NS),
            "policy": "UNMEASURED_EVIDENCE_ONLY_SOURCE_CAP", "budgetAcceptance": "NOT_ADMITTED",
            "exportSaveAuthority": False}


def validate_prelude(value):
    require(type(value) is dict, "BOOTSTRAP_PRELUDE")
    clock = wire.clock_identity(value.get("clock"))
    expected = prelude(clocks.Reading(clock, integer(value.get("firstNs"))))
    require(encoded(value) == encoded(expected), "BOOTSTRAP_PRELUDE_CHANGED")
    return clock


class Fence:
    """One original shared-clock chain; local conversions only shorten it.

    Construction from data is NOT admission. Only the actual owning caller may
    supply the first observation or adopt its privately retained predecessor.
    """
    def __init__(self, value, *, minimum, cancelled):
        self.clock = validate_prelude(value)
        self.raw = encoded(value)
        self.first = value["firstNs"]
        self.work, self.final = value["workEndNs"], value["finalEndNs"]
        self.last = integer(minimum, self.first)
        require(callable(cancelled), "BOOTSTRAP_CANCELLATION_OWNER")
        self.cancelled = cancelled

    def now(self, *, final=False, minimum=0, limit=None):
        # Preserve the validated high-water even when a deadline then fails.
        self.last = clocks.checked_now(self.clock, minimum_ns=max(self.last, integer(minimum)))
        ceiling = self.final if final else self.work
        if limit is not None:
            ceiling = min(ceiling, integer(limit))
        require(self.last < ceiling, "BOOTSTRAP_ORIGINAL_FENCE_EXPIRED")
        if not final:
            self.cancelled()
        return self.last

    def deadline(self, maximum, *, final=False, limit=None):
        require(type(maximum) in (int, float), "BOOTSTRAP_OPERATION_MAXIMUM")
        try:
            maximum = float(maximum)
        except (OverflowError, ValueError):
            raise OriginError("BOOTSTRAP_OPERATION_MAXIMUM") from None
        require(math.isfinite(maximum) and maximum > 0, "BOOTSTRAP_OPERATION_MAXIMUM")
        local = time.monotonic()
        now = self.now(final=final, limit=limit)
        ceiling = self.final if final else self.work
        if limit is not None:
            ceiling = min(ceiling, integer(limit))
        # Unlike a clock helper returning only a float, this preserves the RAW
        # observation used in conversion for the next boundary's minimum.
        return wire._directed_deadline(local, maximum, ceiling, now)


def admitted_value(admitted):
    require(type(admitted) is bootstrap.ordinary.Admission, "BOOTSTRAP_ORIGINAL_ADMISSION")
    cohort = bootstrap.cache_cohort(admitted.record)
    require(cohort is not None, "BOOTSTRAP_ORIGINAL_ADMISSION")
    value = parse(admitted.record)
    github, policy = value["github"], value["policy"]
    require(set(github) == {"repository", "event", "ref", "workflow", "workflowSha", "job", "runId", "runAttempt",
            "eventSha256", "eventBinding", "runnerOS", "runnerArch"} and
            set(policy) == {"commit", "blob", "path", "sha256", "fingerprint", "keySha256", "expiresAt", "retentionDays"} and
            policy["path"] == bootstrap.ordinary.POLICY_PATH and type(policy["retentionDays"]) is int and
            policy["retentionDays"] == 14, "BOOTSTRAP_ORIGINAL_ADMISSION_FIELDS")
    bootstrap.ordinary.sha(policy["blob"])
    for name in ("runId", "runAttempt"):
        require(type(github.get(name)) is str and bootstrap.ordinary.ID.fullmatch(github[name]),
                "BOOTSTRAP_ORIGINAL_RUN")
        integer(int(github[name]), 1)
    require(github.get("eventSha256") == digest(admitted.original_event) and
            policy.get("sha256") == digest(admitted.original_policy) and
            policy.get("keySha256") == digest(admitted.public_key) == admitted.key_sha256 and
            policy.get("fingerprint") == admitted.fingerprint and
            policy.get("expiresAt") == admitted.expires_at, "BOOTSTRAP_ORIGINAL_ADMISSION_BYTES")
    event = bootstrap.ordinary.parse(admitted.original_event, bootstrap.ordinary.EVENT_LIMIT)
    require(event.get("inputs") == {"selection": value["selection"], "expected_sha": value["source"]["commit"],
            "expected_tree": value["source"]["tree"]}, "BOOTSTRAP_ORIGINAL_EVENT")
    ref = github.get("ref")
    require(type(ref) is str and ref.startswith("refs/heads/") and 11 < len(ref) <= 256 and
            not any(ord(char) < 32 or ord(char) == 127 for char in ref) and
            event.get("ref") in (ref, ref[11:]), "BOOTSTRAP_ORIGINAL_BRANCH")
    return value


def paths(admitted):
    github = admitted_value(admitted)["github"]
    base = "/repos/" + bootstrap.ordinary.REPOSITORY + "/actions/runs/" + github["runId"] + "/attempts/" + github["runAttempt"]
    return {"attempt": base, "jobs": base + "/jobs?per_page=100&page=1"}


def response_bytes(raw, path, invocation, clock):
    """Check the retained transport envelope before parsing its original body.

    The approval-history endpoint returns a JSON list, unlike run/job endpoints.
    Exposing the exact checked body avoids rewriting an original response into
    an invented object. This is transport validation, not caller admission.
    """
    return _response_bytes(raw, path, invocation, clock, RESPONSE_SCOPE)


def initial_provider_response_bytes(raw, path, invocation, clock):
    """Distinct public envelope; not accepted by the legacy private reader."""
    public_provider.endpoint(path)
    return _response_bytes(raw, path, invocation, clock, public_provider.RESPONSE_SCOPE)


def _response_bytes(raw, path, invocation, clock, scope):
    require(type(scope) is str and scope in (RESPONSE_SCOPE, public_provider.RESPONSE_SCOPE),
            "BOOTSTRAP_SERVICE_TRANSPORT_SCOPE")
    require(type(invocation) is str and re.fullmatch(r"[0-9a-f]{32}", invocation), "BOOTSTRAP_ORIGIN_INVOCATION")
    value = parse(raw)
    require(set(value) == {"schema", "scope", "origin", "method", "path", "invocation", "clock",
            "startedNs", "finishedNs", "status", "headersBase64", "bodyBase64", "complete", "retirement", "error"} and
            type(value["schema"]) is int and value["schema"] == 1 and value["scope"] == scope and
            value["origin"] == wire.ORIGIN and value["method"] == "GET" and value["path"] == path and
            value["invocation"] == invocation and value["clock"] == clock_value(clock) and
            value["complete"] is True and value["retirement"] == "KNOWN" and value["error"] is None,
            "BOOTSTRAP_SERVICE_RESPONSE")
    start, finish = integer(value["startedNs"]), integer(value["finishedNs"])
    require(start <= finish < start + wire.REQUEST_SECONDS * NS, "BOOTSTRAP_SERVICE_INTERVAL")
    decoded = []
    for name, maximum in (("headersBase64", wire.HEADER_LIMIT), ("bodyBase64", wire.BODY_LIMIT)):
        item = value[name]
        require(type(item) is str and 0 < len(item) <= 4 * ((maximum + 2) // 3), "BOOTSTRAP_SERVICE_SIZE")
        try:
            data = base64.b64decode(item, validate=True)
        except (ValueError, UnicodeError):
            raise OriginError("BOOTSTRAP_SERVICE_ENCODING") from None
        require(0 < len(data) <= maximum and base64.b64encode(data).decode("ascii") == item,
                "BOOTSTRAP_SERVICE_ENCODING")
        decoded.append(data)
    status, headers = wire.headers(decoded[0])
    require(type(value["status"]) is int and value["status"] == status == 200, "BOOTSTRAP_SERVICE_STATUS")
    date = wire.freshness(headers) if scope == RESPONSE_SCOPE else public_provider.freshness(headers)
    if "content-length" in headers:
        require(re.fullmatch(r"[0-9]{1,7}", headers["content-length"]) and
                int(headers["content-length"]) == len(decoded[1]) and "transfer-encoding" not in headers,
                "BOOTSTRAP_SERVICE_LENGTH")
    if "transfer-encoding" in headers:
        require(headers["transfer-encoding"].lower() == "chunked", "BOOTSTRAP_SERVICE_TRANSFER")
    return value, decoded[1], date


def observation(raw, path, invocation, clock):
    value, body, date = response_bytes(raw, path, invocation, clock)
    return value, bootstrap.ordinary.parse(body, wire.BODY_LIMIT), date


def service_identity(admitted, originals, invocation, clock, runner_name):
    """Recheck retained supplied originals. No budget or authenticity is inferred."""
    record = admitted_value(admitted)
    require(record["cacheCohort"]["role"] == clock.role, "BOOTSTRAP_SERVICE_NATIVE_ROLE")
    require(type(originals) is dict and set(originals) == {"attempt", "jobs"}, "BOOTSTRAP_SERVICE_ORIGINALS")
    expected = paths(admitted)
    left, attempt, left_date = observation(originals["attempt"], expected["attempt"], invocation, clock)
    right, jobs, date = observation(originals["jobs"], expected["jobs"], invocation, clock)
    require(left["finishedNs"] <= right["startedNs"] <= right["finishedNs"] <
            left["startedNs"] + wire.ACQUIRE_SECONDS * NS, "BOOTSTRAP_SERVICE_ACQUISITION_INTERVAL")
    require(0 <= date - left_date <= math.ceil((right["finishedNs"] - left["startedNs"]) / NS) +
            wire.CACHE_SECONDS + 1, "BOOTSTRAP_SERVICE_DATE_DRIFT")
    github, source = record["github"], record["source"]
    run, number, branch = int(github["runId"]), int(github["runAttempt"]), github["ref"][11:]
    require(integer(attempt.get("id"), 1) == run and integer(attempt.get("run_attempt"), 1) == number and
            attempt.get("repository", {}).get("full_name") == bootstrap.ordinary.REPOSITORY and
            attempt.get("head_repository", {}).get("full_name") == bootstrap.ordinary.REPOSITORY and
            attempt.get("path") == bootstrap.WORKFLOW and attempt.get("event") == "workflow_dispatch" and
            attempt.get("head_sha") == source["commit"] and attempt.get("head_branch") == branch and
            attempt.get("status") == "in_progress" and "conclusion" in attempt and attempt["conclusion"] is None and
            attempt.get("pull_requests") == [], "BOOTSTRAP_SERVICE_ATTEMPT")
    rows = jobs.get("jobs")
    require(type(rows) is list and 0 < len(rows) <= 100 and integer(jobs.get("total_count"), 1) == len(rows) and
            all(type(row) is dict for row in rows), "BOOTSTRAP_SERVICE_COMPLETE_PAGE")
    ids = [integer(row.get("id"), 1) for row in rows]
    require(len(set(ids)) == len(ids), "BOOTSTRAP_SERVICE_DUPLICATE_JOB")
    selected = [row for row in rows if row.get("name") == bootstrap.JOB]
    require(len(selected) == 1, "BOOTSTRAP_SERVICE_EXACT_JOB")
    job = selected[0]
    require(integer(job.get("run_id"), 1) == run and integer(job.get("run_attempt"), 1) == number and
            job.get("head_sha") == source["commit"] and job.get("head_branch") == branch and
            job.get("run_url") == wire.ORIGIN + "/repos/" + bootstrap.ordinary.REPOSITORY + "/actions/runs/" + github["runId"] and
            job.get("url") == wire.ORIGIN + "/repos/" + bootstrap.ordinary.REPOSITORY + "/actions/jobs/" + str(job["id"]) and
            job.get("status") == "in_progress" and "completed_at" in job and job["completed_at"] is None and
            "conclusion" in job and job["conclusion"] is None, "BOOTSTRAP_SERVICE_JOB")
    require(type(runner_name) is str and 0 < len(runner_name) <= 256 and
            not any(ord(char) < 32 or ord(char) == 127 for char in runner_name) and
            job.get("runner_name") == runner_name and integer(job.get("runner_id"), 1) > 0 and
            job.get("labels") == [SERVICE_SELECTORS[clock.role]] and type(job.get("runner_group_id")) is int and
            job["runner_group_id"] == 0 and job.get("runner_group_name") == "GitHub Actions",
            "BOOTSTRAP_SERVICE_RUNNER")
    require(wire.utc_epoch(attempt.get("created_at")) <= wire.utc_epoch(attempt.get("run_started_at")) <=
            wire.utc_epoch(job.get("started_at")) <= date, "BOOTSTRAP_SERVICE_JOB_START")
    return {"numericJobId": job["id"], "runnerName": runner_name, "selector": SERVICE_SELECTORS[clock.role],
            "jobStartedAt": job["started_at"], "originDateEpochSeconds": date,
            "firstNs": left["startedNs"], "lastNs": right["finishedNs"],
            "originalsSha256": {name: digest(raw) for name, raw in originals.items()},
            "budgetAcceptance": "NOT_ADMITTED", "exportSaveAuthority": False}


def _request(path, token, invocation, fence, end):
    """Unchanged PRIVATE entry: always sends its original Bearer credential."""
    return _request_transport(path, token, invocation, fence, end, RESPONSE_SCOPE)


def _request_initial_provider_public(path, invocation, fence, end):
    """Fixed public-provider sibling, never an authenticated fallback/retry."""
    public_provider.endpoint(path)
    public_provider.credential_free()
    return _request_transport(path, None, invocation, fence, end, public_provider.RESPONSE_SCOPE)


def _request_transport(path, token, invocation, fence, end, scope):
    require(type(scope) is str and scope in (RESPONSE_SCOPE, public_provider.RESPONSE_SCOPE),
            "BOOTSTRAP_SERVICE_TRANSPORT_SCOPE")
    if scope == public_provider.RESPONSE_SCOPE:
        public_provider.endpoint(path)
        public_provider.credential_free()
        require(token is None, "BOOTSTRAP_PUBLIC_SERVICE_NO_TOKEN")
    start = fence.now(limit=end)
    request_end = min(end, start + wire.REQUEST_SECONDS * NS)
    connection = response = reader = None
    body, header, status, complete, error, retired = bytearray(), b"", None, False, None, True

    def close_unknown(error, label):
        nonlocal retired
        retired = False
        prior = getattr(error, "_p2pkit_retirement", {"resources": [], "omitted": 0})
        error._p2pkit_retirement = {"status": "UNKNOWN", "resources": [*prior["resources"],
            {"phase": "bootstrap-http-close", "resource": label, "status": "UNKNOWN",
             "error": "BOOTSTRAP_SERVICE_CLOSE_FAILED"}], "omitted": prior["omitted"]}

    class Reader(wire._Reader):
        close_attempted, close_error = False, None

        def close(self):
            # HTTPResponse can detach fp BEFORE its implicit EOF close. Keep
            # the original disposition here, not only at the outer finally.
            # An ambiguous underlying close is never retried.
            if self.close_attempted:
                if self.close_error is not None:
                    raise self.close_error
                return
            self.close_attempted = True
            try:
                super().close()
            except BaseException as caught:
                self.close_error = caught
                close_unknown(caught, "response-reader")
                raise

    try:
        # No redirects/retries/proxy handlers, caller URL, alternate TLS context
        # or ordinary profile. Native outer ownership bounds blocking suppliers.
        connection = http.client.HTTPSConnection(wire.HOST,
            timeout=min(wire.SOCKET_SECONDS, (request_end - start) / NS), context=ssl.create_default_context())

        class Response(http.client.HTTPResponse):
            def __init__(self, sock, **kwargs):
                nonlocal reader
                super().__init__(sock, **kwargs)
                reader = Reader(self.fp, sock, request_end, fence.last, clock=fence.clock)
                self.fp = reader

        connection.response_class = Response
        fence.now(limit=request_end)
        headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "P2pKit-cache-bootstrap-originals"}
        if scope == RESPONSE_SCOPE:
            headers["Authorization"] = "Bearer " + token
        else:
            public_provider.credential_free()
        headers.update({"Cache-Control": "no-cache, max-age=0", "Pragma": "no-cache",
            "Accept-Encoding": "identity", "Connection": "close"})
        connection.request("GET", path, headers=headers)
        fence.now(limit=request_end)
        response = connection.getresponse()
        header = bytes(reader.header)
        reader.in_headers = False
        status, fields = wire.headers(header)
        require(status == response.status == 200, "BOOTSTRAP_SERVICE_STATUS")
        if scope == RESPONSE_SCOPE:
            wire.freshness(fields)
        else:
            public_provider.freshness(fields)
        require(not ("content-length" in fields and "transfer-encoding" in fields), "BOOTSTRAP_SERVICE_LENGTH")
        if "content-length" in fields:
            require(re.fullmatch(r"[0-9]{1,7}", fields["content-length"]) and
                    0 < int(fields["content-length"]) <= wire.BODY_LIMIT, "BOOTSTRAP_SERVICE_LENGTH")
        if "transfer-encoding" in fields:
            require(fields["transfer-encoding"].lower() == "chunked", "BOOTSTRAP_SERVICE_TRANSFER")
        while True:
            raw = response.read(min(65536, wire.BODY_LIMIT + 1 - len(body)))
            body.extend(raw)
            require(len(body) <= wire.BODY_LIMIT, "BOOTSTRAP_SERVICE_BODY_LIMIT")
            if not raw:
                break
        require(body and ("content-length" not in fields or int(fields["content-length"]) == len(body)),
                "BOOTSTRAP_SERVICE_TRUNCATED")
        complete = True
    except BaseException as caught:
        if isinstance(caught, http.client.IncompleteRead) and type(caught.partial) is bytes:
            body.extend(caught.partial[:max(0, wire.BODY_LIMIT - len(body))])
        error = caught if isinstance(caught, (OriginError, wire.BudgetError, clocks.ClockError, KeyboardInterrupt)) else OriginError(
            "BOOTSTRAP_SERVICE_HTTP_FAILED")
        if error is not caught:
            error.__cause__ = caught  # Private owner diagnostics, never public output.
    finally:
        if reader is not None:
            header = bytes(reader.header)
        for label, value in (("response", response if response is not None else reader), ("connection", connection)):
            if value is not None:
                try:
                    value.close()
                except BaseException as caught:
                    if error is None:
                        error = caught if isinstance(caught, KeyboardInterrupt) else OriginError("BOOTSTRAP_SERVICE_CLOSE_FAILED")
                        if error is not caught:
                            error.__cause__ = caught
                    # Explicit carrier preserves uncertainty through the real
                    # child owner, even if the first failure was cancellation.
                    close_unknown(error, label)
    try:
        finish = fence.now(minimum=max(start, reader.last if reader is not None else start), limit=request_end)
    except BaseException as caught:
        finish = None
        error = error or caught
    result = {"schema": 1, "scope": scope, "origin": wire.ORIGIN, "method": "GET", "path": path,
              "invocation": invocation, "clock": clock_value(fence.clock), "startedNs": start, "finishedNs": finish,
              "status": status, "headersBase64": base64.b64encode(header[:wire.HEADER_LIMIT]).decode("ascii"),
              "bodyBase64": base64.b64encode(bytes(body[:wire.BODY_LIMIT])).decode("ascii"),
              "complete": complete and error is None, "retirement": "KNOWN" if retired else "UNKNOWN",
              "error": None if error is None else "BOOTSTRAP_SERVICE_FAILED"}
    return encoded(result), error


def acquire(admitted, invocation, token, retain, fence, *, original_work_end):
    """Actual closed HTTP supplier, invoked only in its original native child.

    The immutable parent phase end also bounds the two GETs, retention and return;
    child startup cannot renew 45 seconds. Failed observed bytes are retained
    before propagating the first failure. No API refresh/retry is supported.
    """
    expected = paths(admitted)
    require(type(invocation) is str and re.fullmatch(r"[0-9a-f]{32}", invocation), "BOOTSTRAP_ORIGIN_INVOCATION")
    require(type(token) is str and re.fullmatch(r"[A-Za-z0-9_.-]{16,4096}", token), "BOOTSTRAP_ACTIONS_READ_TOKEN")
    require(callable(retain), "BOOTSTRAP_ORIGINAL_RETAINER")
    start = fence.now(limit=original_work_end)
    end = min(original_work_end, start + wire.ACQUIRE_SECONDS * NS)
    result = {}
    for label in ("attempt", "jobs"):
        fence.now(limit=end)
        raw, error = _request(expected[label], token, invocation, fence, end)
        try:
            retain(label, raw, failed=error is not None)
        except BaseException as secondary:
            if error is None:
                raise
            error.__notes__ = [*getattr(error, "__notes__", ()), "Original response retention also failed"]
            raise error from secondary
        if error is not None:
            raise error
        observed, _, _ = observation(raw, expected[label], invocation, fence.clock)
        fence.now(minimum=observed["finishedNs"], limit=end)
        result[label] = raw
    return result, fence.now(limit=end)
