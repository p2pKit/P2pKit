"""Small NEW synthetic finite-delivery DATA, never hosted/custody authority.

No old fixture, key, file owner, process, network or runtime observation is
acquired. The caller supplies the maintained DATA module being tested.
"""
from datetime import datetime, timezone
import hashlib
import json


NS = 1_000_000_000
NOW = int(datetime(2026, 9, 26, 0, 0, 30, tzinfo=timezone.utc).timestamp())
DATE = "Sat, 26 Sep 2026 00:00:30 GMT"
MEMBERS = ("evidence.tar.gz.gpg", "manifest.json", "custody-tail.tar.gz.gpg", "custody-tail-manifest.json")
CARRIER_CLOSE = b'{"model":"K_ORIGINAL_CARRIER_CLOSE_NOT_AUTHORITY"}\n'


def wire(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
        allow_nan=False) + "\n").encode("ascii")


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def copy(value):
    return json.loads(wire(value))


def headers(raw):
    return ["Date", DATE, "Content-Type", "application/json; charset=utf-8",
        "X-GitHub-Api-Version-Selected", "2022-11-28", "X-GitHub-Request-Id", "SYNTHETIC:12345678",
        "Cache-Control", "public, max-age=60, s-maxage=60", "Content-Length", str(len(raw)),
        "X-Model-Private", "MODEL_HEADER_NOT_PUBLIC"]


def seed():
    return {"initialSealSha256": "b" * 64, "initialSealEndNs": str(346 * NS),
        "initialSealClockRole": "linux-x64", "initialSealClockDomain":
        "linux.clock_gettime_ns(CLOCK_MONOTONIC_RAW)", "initialSealClockTicksPerSecond": str(NS),
        "initialSealBootSha256": "a" * 64}


def before(D):
    window = {"schema": 1, "scope": "INITIAL_RECIPIENT_CUSTODY_ABSOLUTE_WINDOW_V1",
        "clock": {"role": "linux-x64", "domain": seed()["initialSealClockDomain"], "ticksPerSecond": NS},
        "originalBootDigest": "a" * 64, "kind": "worker", "originalJobBasisNs": 0,
        "jobEndNs": 1200 * NS, "startNs": NS, "workEndNs": 241 * NS,
        "nativeFinalEndNs": 286 * NS, "readEndNs": 316 * NS,
        "sealEndNs": 346 * NS, "uploadEndNs": 406 * NS, "afterEndNs": 421 * NS}
    return {"schema": 1, "scope": "INITIAL_RECIPIENT_BEFORE_UPLOAD_PENDING_V1", "kind": "worker",
        "selection": "desktop-linux-x64", "source": {"commit": "1" * 40, "tree": "2" * 40},
        "github": {"repository": "p2pKit/P2pKit", "runId": "9001", "runAttempt": "2",
            "job": "populate", "jobId": 9002, "role": "linux-x64"},
        "originalWindow": window, "deadline": seed(),
        "originals": {"eventSha256": "3" * 64, "policySha256": D.S.POLICY_SHA256, "matchSha256": "4" * 64},
        "predecessors": {"cryptoStepSha256": "5" * 64, "collectSha256": "6" * 64, "sealSha256": "b" * 64,
            "beforeAuthoritySha256": "7" * 64, "originalWindowSha256": sha(wire(window))},
        "manifests": {"p0Sha256": "d" * 64, "tailSha256": "f" * 64}, "cutMapSha256": "8" * 64,
        "members": [{"name": name, "bytes": 1, "sha256": digit * 64} for name, digit in zip(MEMBERS, "cdef")],
        "totalBytes": 4, "zipBytes": 556,
        "knownCloses": {name: "9" * 64 for name in
            ("beforeReadbackSha256", "beforeCloseWriterSha256", "tailChildCloseSha256", "carrierCloseSha256")},
        "times": {"beforeClosedNs": 2 * NS, "tailChildClosedNs": 3 * NS,
            "carrierClosedNs": 4 * NS, "pendingPreparedNs": 5 * NS},
        "writerReturn": "PENDING_OWNER_CLOSE", "originalStepOutcome": "NOT_OBSERVED", "upload": "NOT_PERFORMED",
        "testAcceptance": "NOT_PERFORMED", "productiveAuthority": False, "cacheAuthority": False,
        "exportSaveAuthority": False, "budgetAcceptance": "NOT_ADMITTED"}


def job(D, stage):
    current = 4 if stage == "upload" else 5
    steps = []
    names = ("P2pKit initial custody export", "P2pKit initial post-export custody", "P2pKit initial custody seal",
        "P2pKit initial before-upload custody", "P2pKit initial custody upload", "P2pKit initial after-upload custody")
    for index, name in enumerate(names):
        steps.append({"name": name, "number": index + 1,
            "status": "completed" if index < current else "in_progress" if index == current else "queued",
            "conclusion": "success" if index < current else None,
            "started_at": "2026-09-26T00:00:" + str(index * 2 + 1).zfill(2) + "Z" if index <= current else None,
            "completed_at": "2026-09-26T00:00:" + str(index * 2 + 2).zfill(2) + "Z" if index < current else None})
    return {"id": 9002, "run_id": 9001, "run_attempt": 2, "name": "populate", "head_sha": "1" * 40,
        "head_branch": D.S.SOURCE_REF.removeprefix("refs/heads/"),
        "url": "https://api.github.com/repos/p2pKit/P2pKit/actions/jobs/9002",
        "run_url": "https://api.github.com/repos/p2pKit/P2pKit/actions/runs/9001",
        "status": "in_progress", "conclusion": None, "completed_at": None,
        "started_at": "2026-09-26T00:00:00Z", "runner_name": "MODEL_RUNNER_NOT_AUTHORITY", "runner_id": 9003,
        "labels": ["ubuntu-latest"], "runner_group_id": 0, "runner_group_name": "GitHub Actions", "steps": steps}


def original(kind, identifier, value):
    raw = wire(value)
    import base64
    return {"kind": kind, "id": identifier, "bodyBase64": base64.b64encode(raw).decode("ascii"),
        "rawHeaderVector": headers(raw)}


def observer(D, stage, rows, request, *, start, end):
    requests = []
    for index, row in enumerate(rows):
        import base64
        raw = base64.b64decode(row["bodyBase64"])
        requests.append({"kind": row["kind"], "id": row["id"], "startedNs": str(start + (100 + 200 * index) * 10 ** 6),
            "closedNs": str(start + (200 + 200 * index) * 10 ** 6), "endNs": str(end), "status": 200,
            "bodyBytes": len(raw), "bodySha256": sha(raw), "rawHeaderVectorSha256": sha(json.dumps(
                row["rawHeaderVector"], separators=(",", ":"), ensure_ascii=False).encode("utf-8")),
            "date": DATE, "dateEpochSeconds": NOW, **{name: True for name in D.OBSERVER_FLAGS}})
    return {"scope": "INITIAL_ARTIFACT_PUBLIC_TERMINAL_TRANSPORT_ONLY_V1", "stage": stage, "transport": "closed",
        "code": None, "requestSha256": request, "jobId": "9002", "artifactId": None if stage == "before" else "9010",
        "enteredNs": str(start + 50 * 10 ** 6), "lastObservationNs": str(start + (210 + 200 * (len(rows) - 1)) * 10 ** 6),
        "agentDestroyReturned": True, "originalResourceCount": len(rows) * 3, "requests": requests,
        "originalStepOutcome": "NOT_OBSERVED", "qualification": "NOT_ESTABLISHED"}


def fixture(D):
    import base64
    pending = before(D)
    context = {"originalServiceJob": [9002, "2026-09-26T00:00:00Z", "MODEL_RUNNER_NOT_AUTHORITY", 9003],
        "observed": {"runnerName": "MODEL_RUNNER_NOT_AUTHORITY"}}
    policy = {"notBefore": NOW - 3600, "expiresAt": NOW + 3600}
    match = {"notBefore": NOW - 60, "expiresAt": NOW + 60}
    ready_raw = D.ready(pending, context, policy=policy, match=match, first_raw=340 * NS,
        before_sha256="8" * 64, carrier_sha256=sha(CARRIER_CLOSE), now=NOW)
    ready = json.loads(ready_raw)
    final = {"schema": 1, "scope": D.FINAL_SCOPE, "beforeSha256": ready["beforeSha256"], "readySha256": sha(ready_raw),
        "zipBytes": 556, "zipSha256": "6" * 64, "nativeCloseSha256": "7" * 64, "closedNs": str(344 * NS),
        "nativeFileRetirement": "KNOWN_NATIVE_CLOSE", "originalReaderOutcome": "PENDING_ENCLOSING_PROCESS_CLOSE",
        "qualification": "NOT_ESTABLISHED"}
    final_raw = wire(final)
    reader = {"scope": "INITIAL_ARTIFACT_FIXED_READER_TRANSPORT_ONLY", "transport": "closed", "code": None,
        "preSpawnLocalNs": str(100 * NS), "returnedLocalNs": str(104 * NS), **{name: True for name in D.READER_FLAGS},
        "originalPipeCloses": {name: True for name in ("stdin", "stdout", "stderr")}, "stderrBytes": 0,
        "readySha256": sha(ready_raw), "finalSha256": sha(final_raw), "zipBytes": 556, "zipSha256": "6" * 64,
        "nativeFileRetirement": "FIXED_HELPER_RETURN_REQUIRES_CALLER_VALIDATION",
        "originalStepOutcome": "NOT_OBSERVED", "qualification": "NOT_ESTABLISHED"}
    rows = [original("job", "9002", job(D, "upload"))]
    before_closed = observer(D, "before", rows, sha(ready_raw), start=100 * NS, end=106 * NS)
    name = "initial-recipient-custody-9001-2-worker-desktop-linux-x64"
    backend = {"workflow_run_backend_id": "", "workflow_job_run_backend_id": "", "name": name}
    expiry = "2026-10-10T00:00:30.000Z"
    create_bytes = len(json.dumps({**backend, "version": 7, "mime_type": "application/zip", "expires_at": expiry},
        separators=(",", ":")).encode("ascii")) + 72
    finalize_bytes = len(json.dumps({**backend, "size": "556", "hash": "sha256:" + "6" * 64},
        separators=(",", ":")).encode("ascii")) + 72
    blocklist_bytes = len('<?xml version="1.0" encoding="utf-8"?><BlockList><Uncommitted>MDAwMDAw</Uncommitted></BlockList>')
    requests = [{"kind": kind, "startNs": str(start), "status": 200 if kind in ("create", "finalize") else 201,
        "bodyBytes": size, "responseBytes": 40 if kind in ("create", "finalize") else 0,
        **{flag: True for flag in D.TRANSPORT_FLAGS}} for kind, start, size in (
            ("create", 100 * NS + 310 * 10 ** 6, create_bytes), ("block", 101 * NS, 556),
            ("blocklist", 104 * NS + 100 * 10 ** 6, blocklist_bytes),
            ("finalize", 104 * NS + 200 * 10 ** 6, finalize_bytes))]
    transport = {"scope": "INITIAL_ARTIFACT_STREAM_TRANSPORT_ONLY", "transport": "closed", "code": None,
        "requestSha256": sha(ready_raw), "artifactName": name, "inputBytes": 556, "sentBytes": 556,
        "observedZipSha256": "6" * 64, "submittedFinalizeHash": "sha256:" + "6" * 64, "artifactId": "9010",
        "createInvokedAt": "2026-09-26T00:00:30.000Z", "requestedExpiresAt": expiry, "requestedRetentionDays": 14,
        "enteredNs": str(100 * NS + 300 * 10 ** 6), "returnedObservationNs": str(104 * NS + 300 * 10 ** 6),
        "inputEndObserved": True, "inputCloseObserved": True, "requests": requests, "serviceDigest": "NOT_OBSERVED",
        "actualServiceExpiry": "NOT_OBSERVED", "nativeFileRetirement": "NOT_ESTABLISHED",
        "originalRunnerOutcome": "NOT_OBSERVED", "qualification": "NOT_ESTABLISHED"}
    control = {"schema": 1, "scope": D.FINISH_INPUT_SCOPE, "readerReadyBase64": base64.b64encode(ready_raw).decode("ascii"),
        "readerFinalBase64": base64.b64encode(final_raw).decode("ascii"), "readerClosed": reader,
        "transportClosed": transport, "beforeClosed": before_closed, "beforeOriginals": rows}
    return {"pending": pending, "context": context, "policy": policy, "match": match, "ready": ready,
        "ready_raw": ready_raw, "final": final, "final_raw": final_raw, "control": control}


def upload(D, model):
    control = D.control_input(wire(model["control"]), "finish")
    observed = D.finish_observations(control, now=NOW)
    return D.upload_pending(model["pending"], model["context"], policy=model["policy"], match=model["match"],
        control=control, observed=observed, finish_first=345 * NS, prepared=346 * NS, now=NOW)


def after(D, model):
    upload_raw = upload(D, model)
    ready_raw = D.after_ready(model["pending"], upload_raw, policy=model["policy"], match=model["match"],
        first=405 * NS, before_sha256=model["ready"]["beforeSha256"], now=NOW)
    value = json.loads(upload_raw)["artifact"]
    artifact = {"id": 9010, "name": value["name"], "size_in_bytes": value["zipBytes"], "digest": "sha256:" + value["zipSha256"],
        "expired": False, "url": "https://api.github.com/repos/p2pKit/P2pKit/actions/artifacts/9010",
        "archive_download_url": "https://api.github.com/repos/p2pKit/P2pKit/actions/artifacts/9010/zip",
        "created_at": "2026-09-26T00:00:30Z", "expires_at": "2026-10-09T00:00:30Z",
        "workflow_run": {"id": 9001, "head_sha": "1" * 40, "head_branch": D.S.SOURCE_REF.removeprefix("refs/heads/")}}
    rows = [original("job", "9002", job(D, "after")), original("artifact", "9010", artifact)]
    control = {"schema": 1, "scope": D.AFTER_INPUT_SCOPE,
        "afterClosed": observer(D, "after", rows, sha(ready_raw), start=200 * NS, end=215 * NS), "afterOriginals": rows}
    carrier = {"directoryIdentitySha256": "1" * 64, "fileMetadataSha256": "2" * 64, "fileOwnerCloseSha256": "3" * 64}
    return {"upload_raw": upload_raw, "ready_raw": ready_raw, "control": control, "carrier": carrier, "artifact": artifact}


def delivery(D, model, after_model):
    return D.delivery_pending(model["pending"], model["context"], after_model["upload_raw"], after_model["ready_raw"],
        policy=model["policy"], match=model["match"], control=D.control_input(wire(after_model["control"]), "after"),
        carrier=after_model["carrier"], prepared=407 * NS, now=NOW)
