#!/usr/bin/env python3
"""Closed ordinary FULL job-time acquisition and immutable shared-RAW fences.

This is not a workflow activator, clock fallback, generic HTTP client or process
backend. The caller must first admit the actual ordinary Actions identity and
own the acquisition child with the existing native controller. Imports do no I/O.
All original responses stay private. A response/receipt is not hosted acceptance.

The 180s upload and two 30s step-transition windows are scheduling CAPS, not
measurements or a guarantee that evidence can always be delivered. They cannot
extend the unchanged 60-minute job or any existing operation maximum.
"""
from __future__ import annotations

import base64
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import format_datetime, parsedate_to_datetime
import hashlib
import http.client
import json
import math
import re
import ssl
import time

import hosted_test_identity as identity
from hosted_lock_resources import RAW_CLOCK_DOMAIN, shared_raw_ns

NS = 1_000_000_000
UINT64 = (1 << 64) - 1
ORIGIN, HOST = "https://api.github.com", "api.github.com"
TOKEN_ENV = "P2PKIT_ACTIONS_READ_TOKEN"
JOB_SECONDS = 3600
ACQUIRE_SECONDS, REQUEST_SECONDS, SOCKET_SECONDS = 45, 15, 5
BODY_LIMIT, HEADER_LIMIT, HEADER_LINE_LIMIT = 1024 * 1024, 16 * 1024, 2048
RECORD_LIMIT = 2 * 1024 * 1024
UPLOAD_SECONDS, TRANSITION_SECONDS, SEAL_SECONDS = 180, 30, 120
# Request no-cache/max-age=0 and direct verified TLS disallow local/proxy reuse.
# The service currently advertises up to 60s private freshness. Charge that whole
# advertised maximum AGAIN, even when Age is absent/zero, plus a 5s source margin
# and Date's separate 1s quantization. This is conservative service-clock policy,
# not proof of arbitrary HTTP Date correctness or of observed in-progress jobs.
CACHE_SECONDS, CLOCK_MARGIN_SECONDS = 60, 5
CONTROLLER_TAIL = (
    ("product-return", 330), ("product-final", 45),
    ("collect", 120), ("collect-final", 45), ("collect-read", 30),
    ("uninstall", 90), ("uninstall-final", 45), ("uninstall-read", 30),
    ("export-freeze", 180), ("export", 240), ("export-final", 45), ("export-read", 30),
    ("export-open", 90), ("export-verify", 90), ("controller-return", 45),
)
TAIL_SECONDS = sum(seconds for _, seconds in CONTROLLER_TAIL)
RESERVE_SECONDS = TAIL_SECONDS + SEAL_SECONDS + UPLOAD_SECONDS + 2 * TRANSITION_SECONDS


class BudgetError(ValueError):
    """Finite public-safe reason; never an HTTP/token/response diagnostic."""


def require(value, code):
    if not value:
        raise BudgetError(code)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def encoded(value):
    raw = (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
                      allow_nan=False) + "\n").encode("ascii")
    require(len(raw) <= RECORD_LIMIT, "JOB_TIME_RECORD_LIMIT")
    return raw


def parse(raw):
    return identity.parse(raw, RECORD_LIMIT)


def integer(value, minimum=0, maximum=UINT64):
    require(type(value) is int and minimum <= value <= maximum, "JOB_TIME_INTEGER")
    return value


def raw_now(minimum=0):
    value = shared_raw_ns()  # Never time.time(), another process's monotonic(), or observer startup.
    return integer(value, minimum)


def utc_epoch(value):
    require(type(value) is str and re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z", value),
            "JOB_TIME_UTC")
    try:
        result = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        return integer(int(result.timestamp()), 1, 253402300799)
    except (ValueError, OverflowError):
        raise BudgetError("JOB_TIME_UTC") from None


def http_epoch(value):
    require(type(value) is str and len(value) == 29, "JOB_TIME_HTTP_DATE")
    try:
        date = parsedate_to_datetime(value)
        require(date.tzinfo == timezone.utc and format_datetime(date, usegmt=True) == value,
                "JOB_TIME_HTTP_DATE")
        return integer(int(date.timestamp()), 1, 253402300799)
    except (TypeError, ValueError, OverflowError):
        raise BudgetError("JOB_TIME_HTTP_DATE") from None


def policy():
    return {"schema": 1, "jobSeconds": JOB_SECONDS, "clockDomain": RAW_CLOCK_DOMAIN,
            "dateQuantizationSeconds": 1, "maximumServiceCacheSeconds": CACHE_SECONDS,
            "clockMarginSeconds": CLOCK_MARGIN_SECONDS, "controllerTail": [list(row) for row in CONTROLLER_TAIL],
            "controllerTailSeconds": TAIL_SECONDS, "sealSeconds": SEAL_SECONDS,
            "uploadSeconds": UPLOAD_SECONDS, "eachTransitionSeconds": TRANSITION_SECONDS,
            "reserveSeconds": RESERVE_SECONDS, "scope": "SOURCE_OWNED_SCHEDULING_CAPS_NOT_DURATION_GUARANTEES",
            "acquisitionSeconds": ACQUIRE_SECONDS, "requestSeconds": REQUEST_SECONDS,
            "socketSeconds": SOCKET_SECONDS, "bodyLimit": BODY_LIMIT, "headerLimit": HEADER_LIMIT,
            "requests": 2, "retries": 0, "redirects": False, "ambientProxy": False}


def admitted_identity(admitted):
    require(type(admitted) is identity.Admission, "JOB_TIME_ORDINARY_ADMISSION_REQUIRED")
    value = parse(admitted.record)
    github = value.get("github", {})
    source = value.get("source", {})
    require(value.get("profile") == "full" and github.get("repository") == identity.REPOSITORY and
            github.get("workflow") == identity.PROFILES["full"][0] and github.get("job") == "complete-gate" and
            github.get("workflowSha") == source.get("commit") and github.get("runnerOS") == "macOS" and
            github.get("runnerArch") in ("ARM64", "X64"), "JOB_TIME_ADMISSION_IDENTITY")
    for name in ("commit", "tree"):
        identity.sha(source.get(name))
    for name in ("runId", "runAttempt"):
        require(type(github.get(name)) is str and identity.ID.fullmatch(github[name]), "JOB_TIME_RUN_ID")
        integer(int(github[name]), 1, (1 << 63) - 1)
    require(github.get("event") in ("push", "schedule", "workflow_dispatch", "pull_request"), "JOB_TIME_EVENT")
    require(digest(admitted.original_event) == github.get("eventSha256"), "JOB_TIME_EVENT_BYTES")
    event = identity.parse(admitted.original_event, identity.EVENT_LIMIT)
    if github["event"] == "pull_request":
        binding = github.get("eventBinding", {})
        pr = event.get("pull_request", {})
        head, base = pr.get("head", {}), pr.get("base", {})
        require(type(binding.get("number")) is int and binding["number"] == event.get("number") == pr.get("number") and
                head.get("sha") == binding.get("head") and base.get("sha") == binding.get("base") and
                head.get("repo", {}).get("full_name") == binding.get("headRepository") and
                base.get("repo", {}).get("full_name") == identity.REPOSITORY and base.get("ref") == "main" and
                github.get("ref") == "refs/pull/" + str(binding["number"]) + "/merge", "JOB_TIME_PR_BINDING")
        head_sha, branch, head_repo = identity.sha(binding["head"]), head.get("ref"), binding["headRepository"]
    else:
        ref = github.get("ref")
        require(type(ref) is str and ref.startswith("refs/heads/"), "JOB_TIME_BRANCH")
        head_sha, branch, head_repo = source["commit"], ref[len("refs/heads/"):], identity.REPOSITORY
    require(type(branch) is str and 0 < len(branch) <= 256 and
            not any(ord(char) < 32 or ord(char) == 127 for char in branch), "JOB_TIME_BRANCH")
    return value, head_sha, branch, head_repo


def paths(admitted):
    value, _, _, _ = admitted_identity(admitted)
    github = value["github"]
    base = "/repos/" + identity.REPOSITORY + "/actions/runs/" + github["runId"] + "/attempts/" + github["runAttempt"]
    return {"attempt": base, "jobs": base + "/jobs?per_page=100&page=1"}


def headers(raw):
    require(type(raw) is bytes and 0 < len(raw) <= HEADER_LIMIT and raw.endswith(b"\r\n\r\n"), "JOB_TIME_HEADERS")
    lines = raw[:-4].split(b"\r\n")
    require(1 < len(lines) <= 65 and all(len(line) <= HEADER_LINE_LIMIT for line in lines), "JOB_TIME_HEADERS")
    match = re.fullmatch(rb"HTTP/1\.[01] ([0-9]{3}) [\x20-\x7e]{0,128}", lines[0])
    require(match is not None, "JOB_TIME_HTTP_STATUS")
    fields = {}
    for line in lines[1:]:
        key, separator, value = line.partition(b":")
        require(separator and re.fullmatch(rb"[!#$%&'*+.^_`|~0-9A-Za-z-]+", key) and
                all(byte == 9 or 32 <= byte <= 126 for byte in value), "JOB_TIME_HEADERS")
        name = key.decode("ascii").lower()
        require(name not in fields, "JOB_TIME_HEADER_DUPLICATE")
        fields[name] = value.decode("ascii").strip()
    return int(match[1]), fields


def freshness(fields):
    require(fields.get("content-type", "").lower() in ("application/json", "application/json; charset=utf-8") and
            fields.get("content-encoding", "identity").lower() == "identity" and
            fields.get("x-github-api-version-selected") == "2022-11-28", "JOB_TIME_HTTP_TYPE")
    require(type(fields.get("x-github-request-id")) is str and
            re.fullmatch(r"[A-Za-z0-9:-]{8,128}", fields["x-github-request-id"]), "JOB_TIME_REQUEST_ID")
    require(fields.get("age") in (None, "0") and not any(key in fields for key in
            ("warning", "via", "location", "content-range", "retry-after")) and
            fields.get("x-cache", "MISS").upper() in ("MISS", "BYPASS"), "JOB_TIME_STALE_OR_INTERMEDIARY")
    cache = {}
    for item in fields.get("cache-control", "").lower().split(","):
        name, equals, value = item.strip().partition("=")
        require(name not in cache and name in {"private", "no-cache", "no-store", "must-revalidate", "max-age",
                "s-maxage"}, "JOB_TIME_CACHE_POLICY")
        if name in {"max-age", "s-maxage"}:
            require(equals and re.fullmatch(r"[0-9]{1,2}", value) and int(value) <= CACHE_SECONDS, "JOB_TIME_CACHE_POLICY")
        else:
            require(not equals, "JOB_TIME_CACHE_POLICY")
        cache[name] = value
    require("private" in cache and ("no-cache" in cache or "no-store" in cache or "max-age" in cache),
            "JOB_TIME_CACHE_POLICY")
    return http_epoch(fields.get("date"))


def observation(raw, expected_path, invocation):
    value = parse(raw)
    require(set(value) == {"schema", "scope", "origin", "method", "path", "invocation", "clockDomain",
            "startedRawNs", "finishedRawNs", "status", "headersBase64", "bodyBase64", "complete", "retirement",
            "error"} and type(value["schema"]) is int and value["schema"] == 1 and
            value["scope"] == "PRIVATE_ACTIONS_JOB_TIME_RESPONSE" and value["origin"] == ORIGIN and
            value["method"] == "GET" and value["path"] == expected_path and value["invocation"] == invocation and
            value["clockDomain"] == RAW_CLOCK_DOMAIN and value["complete"] is True and
            value["retirement"] == "KNOWN" and value["error"] is None, "JOB_TIME_RESPONSE_BINDING")
    start, finish = integer(value["startedRawNs"]), integer(value["finishedRawNs"])
    require(start <= finish <= start + REQUEST_SECONDS * NS, "JOB_TIME_REQUEST_INTERVAL")
    decoded = []
    for key, limit in (("headersBase64", HEADER_LIMIT), ("bodyBase64", BODY_LIMIT)):
        require(type(value[key]) is str and 0 < len(value[key]) <= 4 * ((limit + 2) // 3), "JOB_TIME_RESPONSE_SIZE")
        try:
            data = base64.b64decode(value[key], validate=True)
        except (ValueError, UnicodeError):
            raise BudgetError("JOB_TIME_RESPONSE_ENCODING") from None
        require(len(data) <= limit and base64.b64encode(data).decode("ascii") == value[key], "JOB_TIME_RESPONSE_ENCODING")
        decoded.append(data)
    status, fields = headers(decoded[0])
    require(type(value["status"]) is int and value["status"] == status == 200, "JOB_TIME_HTTP_STATUS")
    date = freshness(fields)
    if "content-length" in fields:
        require(re.fullmatch(r"[0-9]{1,7}", fields["content-length"]) and
                int(fields["content-length"]) == len(decoded[1]) and "transfer-encoding" not in fields,
                "JOB_TIME_HTTP_LENGTH")
    if "transfer-encoding" in fields:
        require(fields["transfer-encoding"].lower() == "chunked", "JOB_TIME_HTTP_TRANSFER")
    return value, identity.parse(decoded[1], BODY_LIMIT), date


def response_identity(admitted, attempt, jobs, runner_name):
    record, head_sha, branch, head_repo = admitted_identity(admitted)
    github = record["github"]
    run, number = int(github["runId"]), int(github["runAttempt"])
    require(integer(attempt.get("id"), 1) == run and integer(attempt.get("run_attempt"), 1) == number and
            attempt.get("repository", {}).get("full_name") == identity.REPOSITORY and
            attempt.get("head_repository", {}).get("full_name") == head_repo and
            attempt.get("path") == github["workflow"] and attempt.get("event") == github["event"] and
            attempt.get("head_sha") == head_sha and attempt.get("head_branch") == branch and
            attempt.get("status") == "in_progress" and "conclusion" in attempt and attempt["conclusion"] is None,
            "JOB_TIME_ATTEMPT_IDENTITY")
    prs = attempt.get("pull_requests")
    if github["event"] == "pull_request":
        binding = github["eventBinding"]
        require(type(prs) is list and len(prs) == 1, "JOB_TIME_API_PR")
        pr = prs[0]
        require(type(pr) is dict and integer(pr.get("number"), 1) == binding["number"] and
                pr.get("base", {}).get("sha") == binding["base"] and pr.get("base", {}).get("ref") == "main" and
                pr.get("head", {}).get("sha") == binding["head"] and pr.get("head", {}).get("ref") == branch and
                pr.get("base", {}).get("repo", {}).get("url") == ORIGIN + "/repos/" + identity.REPOSITORY and
                pr.get("head", {}).get("repo", {}).get("url") == ORIGIN + "/repos/" + head_repo,
                "JOB_TIME_API_PR")
    else:
        require(prs == [], "JOB_TIME_API_PR")
    rows = jobs.get("jobs")
    require(type(rows) is list and 0 < len(rows) <= 100 and integer(jobs.get("total_count"), 1, 100) == len(rows) and
            all(type(row) is dict for row in rows), "JOB_TIME_COMPLETE_PAGE_REQUIRED")
    ids = [integer(row.get("id"), 1, (1 << 63) - 1) for row in rows]
    require(len(set(ids)) == len(ids), "JOB_TIME_DUPLICATE_JOB")
    selected = [row for row in rows if row.get("name") == "complete-gate"]
    require(len(selected) == 1, "JOB_TIME_EXACT_JOB_REQUIRED")
    job = selected[0]
    require(integer(job.get("run_id"), 1) == run and integer(job.get("run_attempt"), 1) == number and
            job.get("head_sha") == head_sha and job.get("head_branch") == branch and
            job.get("run_url") == ORIGIN + "/repos/" + identity.REPOSITORY + "/actions/runs/" + str(run) and
            job.get("url") == ORIGIN + "/repos/" + identity.REPOSITORY + "/actions/jobs/" + str(job["id"]) and
            job.get("status") == "in_progress" and "completed_at" in job and job["completed_at"] is None and
            "conclusion" in job and job["conclusion"] is None, "JOB_TIME_JOB_IDENTITY")
    # API labels are workflow selectors, not an OS/CPU attestation. Native host
    # matching is the unchanged ordinary admission; exact real RUNNER_NAME binds
    # its current service job. Do not invent GITHUB_JOB_ID or OS/arch job labels.
    require(type(runner_name) is str and 0 < len(runner_name) <= 256 and
            not any(ord(c) < 32 or ord(c) == 127 for c in runner_name) and job.get("runner_name") == runner_name and
            integer(job.get("runner_id"), 1) > 0 and job.get("labels") == ["macos-latest"] and
            type(job.get("runner_group_id")) is int and job["runner_group_id"] == 0 and
            job.get("runner_group_name") == "GitHub Actions", "JOB_TIME_RUNNER_IDENTITY")
    start = utc_epoch(job.get("started_at"))
    require(utc_epoch(attempt.get("created_at")) <= utc_epoch(attempt.get("run_started_at")) <= start,
            "JOB_TIME_JOB_START")
    return record, job, start


def derive(admitted, originals, provenance):
    """Pure recomputation. No new observation/derivation may renew this record."""
    require(type(originals) is dict and set(originals) == {"attempt", "jobs"} and type(provenance) is dict and
            set(provenance) == {"controllerJob", "invocation", "phaseStartSha256", "phaseResultSha256",
                                "childReturnSha256", "runnerName"}, "JOB_TIME_PROVENANCE")
    for key in ("controllerJob", "invocation"):
        require(type(provenance[key]) is str and re.fullmatch(r"[0-9a-f]{32}", provenance[key]), "JOB_TIME_PROVENANCE")
    for key in ("phaseStartSha256", "phaseResultSha256", "childReturnSha256"):
        require(type(provenance[key]) is str and re.fullmatch(r"[0-9a-f]{64}", provenance[key]), "JOB_TIME_PROVENANCE")
    expected_paths = paths(admitted)
    left, attempt, left_date = observation(originals["attempt"], expected_paths["attempt"], provenance["invocation"])
    right, jobs, right_date = observation(originals["jobs"], expected_paths["jobs"], provenance["invocation"])
    require(left["finishedRawNs"] <= right["startedRawNs"] <= right["finishedRawNs"] <=
            left["startedRawNs"] + ACQUIRE_SECONDS * NS, "JOB_TIME_ACQUISITION_INTERVAL")
    require(0 <= right_date - left_date <= math.ceil((right["finishedRawNs"] - left["startedRawNs"]) / NS) +
            CACHE_SECONDS + 1, "JOB_TIME_SERVICE_CLOCK_CHANGED")
    record, job, started = response_identity(admitted, attempt, jobs, provenance["runnerName"])
    require(started <= right_date, "JOB_TIME_FUTURE_START")
    job_end = right["startedRawNs"] + (started + JOB_SECONDS - right_date - 1 - CACHE_SECONDS - CLOCK_MARGIN_SECONDS) * NS
    integer(job_end)
    require(right["finishedRawNs"] < job_end, "JOB_TIME_ALREADY_EXPIRED")
    cutoff = integer(job_end - RESERVE_SECONDS * NS)
    fences, cursor = {"productive": cutoff, "preparation-final": cutoff + 45 * NS}, cutoff
    for label, seconds in CONTROLLER_TAIL:
        cursor += seconds * NS
        fences[label] = integer(cursor)
    fences["seal-start"] = cursor + TRANSITION_SECONDS * NS
    fences["seal"] = fences["seal-start"] + SEAL_SECONDS * NS
    fences["upload-start"] = fences["seal"] + TRANSITION_SECONDS * NS
    fences["upload"] = fences["upload-start"] + UPLOAD_SECONDS * NS
    require(fences["upload"] == job_end, "JOB_TIME_RESERVE_ACCOUNTING")
    value = {"schema": 1, "scope": "IMMUTABLE_ORDINARY_FULL_JOB_BUDGET", "admissionSha256": digest(admitted.record),
             "source": record["source"], "github": record["github"], "numericJobId": job["id"],
             "runner": {key: job[key] for key in ("runner_id", "runner_name", "runner_group_id", "runner_group_name", "labels")},
             "jobStartedAt": job["started_at"], "jobStartedEpochSeconds": started,
             "originDateEpochSeconds": right_date, "requestStartRawNs": right["startedRawNs"],
             "responseFinishedRawNs": right["finishedRawNs"], "clockDomain": RAW_CLOCK_DOMAIN,
             "originalsSha256": {key: digest(raw) for key, raw in originals.items()}, "provenance": provenance,
             "policy": policy(), "fencesRawNs": fences}
    return Budget(encoded(value))


@dataclass(frozen=True)
class Budget:
    record: bytes

    @property
    def value(self):
        return parse(self.record)

    @property
    def sha256(self):
        return digest(self.record)

    def fence(self, stage):
        values = self.value["fencesRawNs"]
        require(stage in values, "JOB_TIME_CLOSED_STAGE")
        return integer(values[stage])

    def check(self, stage, *, minimum=None):
        now = raw_now(self.value["responseFinishedRawNs"] if minimum is None else minimum)
        require(now < self.fence(stage), "JOB_TIME_FENCE_EXPIRED")
        return now

    def deadline(self, stage, seconds):
        require(type(seconds) in (int, float) and math.isfinite(seconds) and 0 < seconds <= 8400,
                "JOB_TIME_OPERATION_MAXIMUM")
        # The local sample precedes RAW. Processing between samples can only
        # shorten, not lengthen, the computed local deadline. Never serialize it.
        local = time.monotonic()
        now = self.check(stage)
        return local + min(seconds, (self.fence(stage) - now) / NS)


class BudgetClock:
    """Per-process observation state; immutable authority remains Budget.record."""
    def __init__(self, budget):
        self.budget, self.last = budget, budget.value["responseFinishedRawNs"]

    def check(self, stage):
        self.last = self.budget.check(stage, minimum=self.last)
        return self.last

    def deadline(self, stage, seconds):
        require(type(seconds) in (int, float) and math.isfinite(seconds) and 0 < seconds <= 8400,
                "JOB_TIME_OPERATION_MAXIMUM")
        local = time.monotonic()
        now = self.check(stage)
        return local + min(seconds, (self.budget.fence(stage) - now) / NS)


class _Reader:
    """Bound all HTTP parser reads, including status/headers/chunk framing."""
    def __init__(self, stream, sock, end, start):
        self.stream, self.sock, self.end, self.last = stream, sock, end, start
        self.header = bytearray()
        self.in_headers, self.wire_bytes = True, 0

    def _read(self, name, amount):
        now = raw_now(self.last)
        self.last = now
        require(now < self.end, "JOB_TIME_HTTP_TIMEOUT")
        sock = self.sock
        require(sock is not None, "JOB_TIME_HTTP_SOCKET")
        sock.settimeout(min(SOCKET_SECONDS, (self.end - now) / NS))
        data = getattr(self.stream, name)(amount)
        self.wire_bytes += len(data)
        require(self.wire_bytes <= 2 * BODY_LIMIT + HEADER_LIMIT, "JOB_TIME_HTTP_WIRE_LIMIT")
        if self.in_headers:
            self.header.extend(data)
            require(len(self.header) <= HEADER_LIMIT, "JOB_TIME_HTTP_HEADERS_LIMIT")
        self.last = raw_now(now)
        require(self.last < self.end, "JOB_TIME_HTTP_TIMEOUT")
        return data

    def readline(self, limit=-1):
        bound = min(HEADER_LINE_LIMIT + 1, limit) if limit >= 0 else HEADER_LINE_LIMIT + 1
        raw = self._read("readline", bound)
        require(len(raw) <= HEADER_LINE_LIMIT and (not raw or raw.endswith(b"\r\n")), "JOB_TIME_HTTP_LINE")
        return raw

    def read(self, amount=-1):
        require(type(amount) is int and 0 <= amount <= BODY_LIMIT + 1, "JOB_TIME_HTTP_READ_BOUND")
        return self._read("read", amount)

    def readinto(self, target):
        raw = self.read(len(target))
        target[:len(raw)] = raw
        return len(raw)

    def flush(self):
        self.stream.flush()

    def close(self):
        self.stream.close()


def _request(path, token, invocation):
    """Only called by acquire(); native outer phase is also a whole-call bound."""
    start = raw_now()
    connection = response = reader = None
    body, header, status, complete = bytearray(), b"", None, False
    error, retired = None, True
    try:
        # http.client has no proxy/environment redirect/retry facility. One fixed
        # origin with default certificate/hostname verification, never urllib's
        # ambient ProxyHandler or a caller-supplied SSL context/URL.
        connection = http.client.HTTPSConnection(HOST, timeout=SOCKET_SECONDS, context=ssl.create_default_context())

        class Response(http.client.HTTPResponse):
            def __init__(self, sock, **kwargs):
                nonlocal reader
                super().__init__(sock, **kwargs)
                reader = _Reader(self.fp, sock, start + REQUEST_SECONDS * NS, start)
                self.fp = reader

        connection.response_class = Response
        connection.request("GET", path, headers={"Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "P2pKit-ordinary-full-job-time",
            "Authorization": "Bearer " + token, "Cache-Control": "no-cache, max-age=0",
            "Pragma": "no-cache", "Accept-Encoding": "identity", "Connection": "close"})
        response = connection.getresponse()
        header = bytes(reader.header)
        reader.in_headers = False
        status, fields = headers(header)
        require(status == response.status == 200, "JOB_TIME_HTTP_STATUS")
        freshness(fields)
        require(not ("content-length" in fields and "transfer-encoding" in fields), "JOB_TIME_HTTP_LENGTH")
        if "content-length" in fields:
            require(re.fullmatch(r"[0-9]{1,7}", fields["content-length"]) and
                    0 < int(fields["content-length"]) <= BODY_LIMIT, "JOB_TIME_HTTP_LENGTH")
        if "transfer-encoding" in fields:
            require(fields["transfer-encoding"].lower() == "chunked", "JOB_TIME_HTTP_TRANSFER")
        while True:
            raw = response.read(min(65536, BODY_LIMIT + 1 - len(body)))
            body.extend(raw)
            require(len(body) <= BODY_LIMIT, "JOB_TIME_HTTP_BODY_LIMIT")
            if not raw:
                break
        require(body and ("content-length" not in fields or int(fields["content-length"]) == len(body)),
                "JOB_TIME_HTTP_TRUNCATED")
        complete = True
    except BaseException as caught:
        if isinstance(caught, http.client.IncompleteRead) and type(caught.partial) is bytes:
            body.extend(caught.partial[:max(0, BODY_LIMIT - len(body))])
        error = caught if isinstance(caught, BudgetError) else BudgetError("JOB_TIME_HTTP_FAILED")
    finally:
        if reader is not None:
            header = bytes(reader.header)
        for value in (response if response is not None else reader, connection):
            if value is not None:
                try:
                    value.close()
                except BaseException:
                    retired = False
                    error = error or BudgetError("JOB_TIME_HTTP_CLOSE_FAILED")
    try:
        finish = raw_now(start)
        if finish - start > REQUEST_SECONDS * NS:
            error = error or BudgetError("JOB_TIME_HTTP_TIMEOUT")
    except BaseException:
        # Preserve bytes already observed even when no valid final RAW sample
        # exists. Null + failed completion CANNOT be used by observation/derive;
        # this is failure evidence, never a substitute clock or extra allowance.
        finish = None
        error = error or BudgetError("JOB_TIME_CLOCK_FAILED")
    value = {"schema": 1, "scope": "PRIVATE_ACTIONS_JOB_TIME_RESPONSE", "origin": ORIGIN, "method": "GET", "path": path,
             "invocation": invocation, "clockDomain": RAW_CLOCK_DOMAIN, "startedRawNs": start, "finishedRawNs": finish,
             "status": status, "headersBase64": base64.b64encode(header[:HEADER_LIMIT]).decode("ascii"),
             "bodyBase64": base64.b64encode(bytes(body[:BODY_LIMIT])).decode("ascii"), "complete": complete and error is None,
             "retirement": "KNOWN" if retired else "UNKNOWN", "error": None if error is None else str(error)}
    return encoded(value), error


def acquire(admitted, invocation, token, retain):
    """Exactly two fixed GETs; each original is retained before parsing/refusal."""
    expected = paths(admitted)
    require(type(invocation) is str and re.fullmatch(r"[0-9a-f]{32}", invocation), "JOB_TIME_INVOCATION")
    require(type(token) is str and re.fullmatch(r"[A-Za-z0-9_.-]{16,4096}", token), "JOB_TIME_READ_TOKEN_REQUIRED")
    result, start = {}, raw_now()
    for label in ("attempt", "jobs"):
        require(raw_now(start) < start + ACQUIRE_SECONDS * NS, "JOB_TIME_HTTP_TIMEOUT")
        raw, error = _request(expected[label], token, invocation)
        retain(label, raw)
        if error is not None:
            raise error
        observation(raw, expected[label], invocation)
        result[label] = raw
    require(raw_now(start) < start + ACQUIRE_SECONDS * NS, "JOB_TIME_HTTP_TIMEOUT")
    return result
