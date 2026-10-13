"""Routine Stage1 orchestration primitives, NOT native admission or approval.

The lead must verify an explicit owner delegation and independently reviewed
source, and supply its existing bounded original-API acquisition/preflight.
Nothing here acquires credentials, extends policy, dispatches a run, approves an
environment, or authorizes a final PR/tag/publication. A callback returning DATA
is not proof that GitHub was queried. Original transport receipts remain the
caller's responsibility. No global Actions-idleness requirement exists.
"""
from __future__ import annotations

import dataclasses
import datetime
import hashlib
import os
from pathlib import Path
import stat
import time

import hosted_initial_recipient_stages as stages


identity = stages.identity
MAX_PAGES, PAGE_SIZE = 20, 100  # Existing allocator collection bounds.
ADMIN_PREFLIGHT_SECONDS = 120  # Original API acquisition, not native acceptance.
WORKFLOW_RUNS = "repos/p2pKit/P2pKit/actions/workflows/364235112/runs"
SCOPE = "OWNER_DELEGATED_STAGE1_C1_REGISTRATION_V1"
# Shared with the historical personal handler: another output directory/copy
# must not reset an allocation's possibly consumed comment POST.
CONSUMED = "OWNER-C1-POST-CONSUMED.json"


def require(value, code):
    identity.require(value, "ROUTINE_" + code)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


@dataclasses.dataclass(frozen=True)
class Page:
    endpoint: str
    raw: bytes


@dataclasses.dataclass(frozen=True)
class Collection:
    rows: tuple
    originals: tuple[Page, ...]


def collect_bootstrap_runs(get):
    """All original pages, never a fabricated expanded page-one response.

    `get(endpoint)` performs one bounded GET and returns original response bytes;
    it must reject transport failures. The caller retains those transport
    records. Unrelated RPC workflow activity is not part of this inventory.
    """
    rows, originals, total = [], [], None
    for page in range(1, MAX_PAGES + 1):
        endpoint = WORKFLOW_RUNS + f"?per_page={PAGE_SIZE}&page={page}"
        raw = get(endpoint)
        require(type(raw) is bytes, "PAGE_BYTES")
        value = identity.parse(raw, 2 * 1024 * 1024)
        count, entries = value.get("total_count"), value.get("workflow_runs")
        require(type(count) is int and 0 <= count <= MAX_PAGES * PAGE_SIZE and
                type(entries) is list and len(entries) <= PAGE_SIZE, "PAGE_SHAPE")
        if total is None:
            total = count
        require(count == total, "COLLECTION_TOTAL_DRIFT")
        require(all(type(row) is dict and type(row.get("id")) is int and row["id"] > 0
                    for row in entries), "ROW_ID")
        rows.extend(entries)
        originals.append(Page(endpoint, raw))
        require(len(rows) <= total and len({row["id"] for row in rows}) == len(rows), "DUPLICATE_OR_EXTRA_ROW")
        if len(rows) == total:
            return Collection(tuple(rows), tuple(originals))
        require(len(entries) == PAGE_SIZE, "INCOMPLETE_PAGE")
    raise identity.AdmissionError("ROUTINE_COLLECTION_PAGINATION_BOUND")


def canonical_c1(request_raw, policy_raw, *, authorized_instruction_sha256, now):
    """Validate routine request DATA; caller-provided digest is not authority.

    The caller must have actually verified the owner's delegation independently
    before supplying authorized_instruction_sha256. We do not accept generic
    final-approval kinds, a replacement policy, or a source-free authorization.
    """
    stages.digest(authorized_instruction_sha256)
    request = identity.parse(request_raw, stages.LIMIT)
    stages.fields(request, "schema scope ownerInstructionSha256 allocationResultSha256 source environment "
                  "bootstrap handoffDeadlineEpoch", "ROUTINE_REQUEST_FIELDS")
    require(type(request["schema"]) is int and request["schema"] == 1 and request["scope"] == SCOPE,
            "REQUEST_SCOPE")
    require(request["ownerInstructionSha256"] == authorized_instruction_sha256, "DELEGATION_BINDING")
    stages.digest(request["allocationResultSha256"])
    source = stages.joint.source(request["source"])
    require(source["commit"] != stages.BASE["commit"] and source["tree"] != stages.BASE["tree"], "REVIEWED_SOURCE")
    stages.environment(request["environment"])
    stages.bootstrap_roster(request["bootstrap"])
    require(type(policy_raw) is bytes and digest(policy_raw) == stages.POLICY_SHA256, "POLICY_CHANGED")
    policy, _ = identity._policy(policy_raw, now)
    require(policy["retrievalOwner"] == stages.joint.OWNER_LOGIN, "POLICY_OWNER")
    deadline = request["handoffDeadlineEpoch"]
    require(type(deadline) is int and now < deadline < policy["expiresAt"] - 12600,
            "HANDOFF_OR_ENTRY_CUTOFF")
    declaration = {"schema": 1, "scope": stages.STAGE1, "repository": identity.REPOSITORY,
        "base": dict(stages.BASE), "reviewed": source, "sourceRef": stages.SOURCE_REF,
        "policySha256": stages.POLICY_SHA256, "notBefore": policy["notBefore"],
        "expiresAt": policy["expiresAt"], "environment": request["environment"], "bootstrap": request["bootstrap"]}
    body = stages.COMMANDS[stages.STAGE1].encode("ascii") + identity.encoded(declaration).removesuffix(b"\n")
    return request, body


def _service_epoch(http_date):
    """Original GitHub HTTP Date, kept separate from the local operation clock."""
    require(type(http_date) is str and len(http_date) == 29, "SERVICE_DATE")
    try:
        value = datetime.datetime.strptime(http_date, "%a, %d %b %Y %H:%M:%S GMT")
    except ValueError:
        raise identity.AdmissionError("ROUTINE_SERVICE_DATE") from None
    require(value.strftime("%a, %d %b %Y %H:%M:%S GMT") == http_date, "SERVICE_DATE")
    return int(value.replace(tzinfo=datetime.timezone.utc).timestamp())


def _write_once(directory_fd, name, raw):
    fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o400, dir_fd=directory_fd)
    try:
        remaining = memoryview(raw)
        while remaining:
            size = os.write(fd, remaining)
            require(size > 0, "SHORT_WRITE")
            remaining = remaining[size:]
        os.fsync(fd)
    finally:
        os.close(fd)
    os.fsync(directory_fd)


def register_c1_once(request_raw, policy_raw, *, authorized_instruction_sha256,
                     allocation_directory, preflight, post, read_comment, clock=time.time):
    """One delegated POST plus actual readback, retaining shared consumption.

    The existing reviewed caller owns transport limits/originals and must supply:
    * preflight(request, body): fresh actual account, source/tree/ref, policy,
      environment, complete carrier inventory, exact unused run/attempt roster,
      original allocation hash/deadline, and no existing matching C1. Raise on
      failure. Return None, never an invented approval/capability.
    * post(body): one bounded issue437 POST; (actual status, bytes, HTTP Date).
    * read_comment(id): one bounded GET of that exact comment; (bytes, HTTP Date).
    HTTP Date is the exact, unique original response-header value, not a local
    timestamp or a synthesized value. The caller retains the original headers
    and body with each transport receipt. All callbacks are no-retry.

    allocation_directory is the genuine original allocation directory checked
    by preflight, not a disposable output directory. A failed/ambiguous POST,
    readback or close cannot be replayed by invoking this operation again.
    """
    started = clock()
    require(type(started) in (int, float), "CLOCK")
    request, body = canonical_c1(request_raw, policy_raw,
        authorized_instruction_sha256=authorized_instruction_sha256, now=int(started))
    request_snapshot = identity.encoded(request)
    directory = Path(allocation_directory)
    require(directory.is_absolute() and directory.resolve() == directory, "ALLOCATION_PATH")
    fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        info = os.fstat(fd)
        require(stat.S_ISDIR(info.st_mode) and info.st_uid == os.getuid() and
                stat.S_IMODE(info.st_mode) == 0o700, "ALLOCATION_DIRECTORY")
        # Avoid API calls on an already consumed allocation, including a prior
        # personal handler POST. O_EXCL below also protects against races.
        try:
            os.stat(CONSUMED, dir_fd=fd, follow_symlinks=False)
        except FileNotFoundError:
            pass
        else:
            raise identity.AdmissionError("ROUTINE_POST_ALREADY_CONSUMED")
        _write_once(fd, "ROUTINE-C1-REQUEST.json", request_raw)
        require(preflight(request, body) is None, "PREFLIGHT_CONTRACT")
        observed = clock()
        require(started <= observed <= started + ADMIN_PREFLIGHT_SECONDS, "PREFLIGHT_TOO_OLD")
        require(identity.encoded(request) == request_snapshot, "REQUEST_MUTATED_BY_PREFLIGHT")
        canonical_c1(request_raw, policy_raw, authorized_instruction_sha256=authorized_instruction_sha256,
                     now=int(observed))
        bound = identity.parse(request_snapshot, stages.LIMIT)
        intent = {"schema": 1, "scope": SCOPE, "executor": "OWNER_DELEGATED_ROUTINE",
            "personalApproval": False, "ownerInstructionSha256": authorized_instruction_sha256,
            "requestSha256": digest(request_raw), "allocationResultSha256": bound["allocationResultSha256"],
            "source": bound["source"], "bootstrap": bound["bootstrap"], "bodySha256": digest(body),
            "handoffDeadlineEpoch": bound["handoffDeadlineEpoch"], "mayHavePostedIfInterrupted": True,
            "retryAllowed": False, "releaseStatus": "NOT_READY"}
        _write_once(fd, CONSUMED, identity.encoded(intent))
        after_intent = clock()
        require(observed <= after_intent <= started + ADMIN_PREFLIGHT_SECONDS, "PREFLIGHT_TOO_OLD_AFTER_INTENT")
        require(identity.encoded(request) == request_snapshot, "REQUEST_MUTATED_BEFORE_POST")
        canonical_c1(request_raw, policy_raw, authorized_instruction_sha256=authorized_instruction_sha256,
                     now=int(after_intent))
        status, response, post_date = post(body)
        require(identity.encoded(request) == request_snapshot, "REQUEST_MUTATED_BY_POST")
        require(type(status) is int and status == 201 and type(response) is bytes, "POST_NOT_CONFIRMED_NO_RETRY")
        post_time = _service_epoch(post_date)
        posted = identity.parse(response, stages.LIMIT)
        comment_id = posted.get("id")
        declaration, authority, created = stages.statement(stages.STAGE1, response, comment_id, digest(body))
        require(declaration["reviewed"] == request["source"], "POST_SOURCE")
        original, readback_date = read_comment(comment_id)
        readback_time = _service_epoch(readback_date)
        actual, selected, actual_created = stages.statement(stages.STAGE1, original, comment_id, digest(body))
        ended = clock()
        require(identity.encoded(request) == request_snapshot, "REQUEST_MUTATED_BY_READBACK")
        canonical_c1(request_raw, policy_raw, authorized_instruction_sha256=authorized_instruction_sha256,
                     now=int(ended))
        require(after_intent <= ended, "LOCAL_CLOCK_REVERSED")
        # UTC policy/handoff bounds apply in each domain independently. A new
        # original 201 reply plus exact GET proves freshness; a GitHub timestamp
        # is not required to fall between two timestamps from this local host.
        require(declaration["notBefore"] <= created == actual_created <= post_time <= readback_time <
                request["handoffDeadlineEpoch"] and actual == declaration and selected == authority,
                "READBACK_CHANGED_OR_SERVICE_CLOCK")
        result = {**intent, "result": "C1_REGISTERED_AND_READ_BACK_NOT_ENVIRONMENT_APPROVAL",
            "commentId": comment_id, "url": authority["url"],
            "serviceTimes": {"createdAt": created, "postHttpDate": post_date, "readbackHttpDate": readback_date},
            "postResponse": {"bytes": len(response), "sha256": digest(response)},
            "readback": {"bytes": len(original), "sha256": digest(original)},
            "environmentApproved": False, "nativeQualification": False}
        _write_once(fd, "ROUTINE-C1-RESULT.json", identity.encoded(result))
        return result
    finally:
        os.close(fd)
