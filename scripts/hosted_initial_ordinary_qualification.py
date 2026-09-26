"""Closed Stage2 reference readers; NOT productive-bootstrap qualification.

These pure readers validate SUPPLIED public comment/API bytes. The actual native
owner must acquire their fixed-origin originals with complete private custody.
No function here returns admission, current authority, a native owned object or
qualification acceptance. In particular, an artifact digest/expiry is not proof
of a productive packet, its plaintext, independent review or a compatible cache.

The productive K/P packet roster and safe historical export are not implemented
by this increment. No gate/initializer/P0+tail packet is promoted to productive
qualification. Full ZIP/member, original-history, provider and compatibility
validation remain necessary before a future caller can accept any qualification.
"""
from __future__ import annotations

import hashlib

import hosted_initial_recipient_stages as stages


I = stages.identity
API = "https://api.github.com/repos/" + I.REPOSITORY
COMMENT_LIMIT = 4 * 1024 * 1024
PAGE_LIMIT, PAGE_COUNT, PAGE_SIZE = 1024 * 1024, 10, 100
PACKET_LIMIT = 512 * 1024 * 1024
RETENTION_SECONDS = 14 * 24 * 60 * 60


def require(value, code):
    I.require(value, "INITIAL_ORDINARY_REFERENCE_" + code)


def metadata_path(reference):
    stages.comment_reference(reference)
    return "/repos/" + I.REPOSITORY + "/issues/comments/" + str(reference["commentId"])


def metadata_body(comment_raw, reference, *, completed_at, authority_created_at):
    """Select exact unedited owner-posted metadata, never a comment search.

    Hash/size cover the ASCII body alone, without a trailing newline. The body
    must be canonical JSON, but this reader deliberately does NOT interpret an
    unknown inventory/review/compatibility schema as an accepted record. These
    are public evidence references, not a second personal-authorization kind.
    """
    path = metadata_path(reference)
    require(type(comment_raw) is bytes, "COMMENT_BYTES")
    value = I.parse(comment_raw, COMMENT_LIMIT)
    identifier = reference["commentId"]
    require(type(value.get("id")) is int and value["id"] == identifier and
            value.get("url") == "https://api.github.com" + path and
            value.get("issue_url") == API + "/issues/" + str(stages.joint.ISSUE) and
            value.get("html_url") == "https://github.com/" + I.REPOSITORY + "/issues/" +
            str(stages.joint.ISSUE) + "#issuecomment-" + str(identifier), "COMMENT_LOCATION")
    require(stages.joint.owner(value.get("user")) and "performed_via_github_app" in value and
            value["performed_via_github_app"] is None, "COMMENT_AUTHOR")
    created = stages.joint.timestamp(value.get("created_at"))
    require(value.get("updated_at") == value["created_at"], "COMMENT_EDITED")
    require(type(completed_at) is int and type(authority_created_at) is int and
            0 < completed_at <= created < authority_created_at, "COMMENT_WINDOW")
    body = value.get("body")
    require(type(body) is str and 0 < len(body) <= COMMENT_LIMIT, "COMMENT_BODY")
    try:
        raw = body.encode("ascii")
    except UnicodeError:
        raise I.AdmissionError("INITIAL_ORDINARY_REFERENCE_COMMENT_BODY") from None
    require(len(raw) == reference["bytes"] and hashlib.sha256(raw).hexdigest() == reference["sha256"],
            "COMMENT_DIGEST")
    parsed = I.parse(raw, COMMENT_LIMIT)
    require(raw == I.encoded(parsed).removesuffix(b"\n"), "COMMENT_ENCODING")
    return raw  # Reference data only. No productive-schema success is returned.


def inventory_path(run_id, page):
    require(type(run_id) is str and I.ID.fullmatch(run_id), "RUN_ID")
    require(type(page) is int and 1 <= page <= PAGE_COUNT, "PAGE_NUMBER")
    return "/repos/" + I.REPOSITORY + "/actions/runs/" + run_id + "/artifacts?per_page=100&page=" + str(page)


def _artifact_location(item):
    require(type(item) is dict, "ARTIFACT_OBJECT")
    identifier = stages.positive(item.get("id"))
    location = API + "/actions/artifacts/" + str(identifier)
    require(item.get("url") == location and item.get("archive_download_url") == location + "/zip",
            "ARTIFACT_LOCATION")
    return identifier


def complete_inventory(pages, *, run_id):
    """Validate complete ordered supplied pages under one caller-owned fence.

    Each pair is (exact requested path, original response BODY). Authentication,
    response headers, failed originals and native retirement are the actual
    supplier's separate duties. This does not follow links, retry or create a
    fresh time allowance per page. It neither selects nor qualifies a packet.
    """
    require(type(pages) is tuple and 1 <= len(pages) <= PAGE_COUNT, "PAGES")
    rows, identifiers, total = [], set(), None
    for number, page in enumerate(pages, 1):
        require(type(page) is tuple and len(page) == 2 and page[0] == inventory_path(run_id, number) and
                type(page[1]) is bytes, "PAGE_ORIGINAL")
        value = I.parse(page[1], PAGE_LIMIT)
        require(set(value) == {"total_count", "artifacts"} and type(value["total_count"]) is int and
                0 <= value["total_count"] <= PAGE_COUNT * PAGE_SIZE, "PAGE_FIELDS")
        if total is None:
            total = value["total_count"]
        require(value["total_count"] == total, "CHANGED_TOTAL")
        items = value["artifacts"]
        require(type(items) is list and len(items) <= PAGE_SIZE and
                (number == len(pages) or len(items) == PAGE_SIZE), "PAGE_COUNT")
        for item in items:
            identifier = _artifact_location(item)
            require(identifier not in identifiers, "DUPLICATE_ARTIFACT")
            workflow = I.mapping(item.get("workflow_run"))
            require(type(workflow.get("id")) is int and workflow["id"] == int(run_id), "INVENTORY_RUN")
            identifiers.add(identifier)
            rows.append(item)
    require(len(rows) == total and len(pages) == max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE),
            "INCOMPLETE_INVENTORY")
    return tuple(rows)  # Supplied API data, not a live acquisition result.


def artifact_reference(artifact_raw, reference, *, run_id, reviewed, now):
    """Bind exact current artifact metadata to H1, not current H2 or merge M.

    The declared bytes/hash identify the COMPLETE artifact ZIP. Run-attempt
    provenance still needs original attempt/jobs and the real productive packet;
    the artifact API alone cannot prove an attempt or plaintext acceptance.
    """
    stages.fields(reference, "artifactId bytes sha256", "PACKET_FIELDS")
    stages.positive(reference["artifactId"])
    stages._reference({name: reference[name] for name in ("bytes", "sha256")}, maximum=PACKET_LIMIT)
    require(type(run_id) is str and I.ID.fullmatch(run_id), "RUN_ID")
    stages.joint.source(reviewed)
    require(type(now) is int and now > 0 and type(artifact_raw) is bytes, "ARTIFACT_INPUT")
    item = I.parse(artifact_raw, PAGE_LIMIT)
    require(_artifact_location(item) == reference["artifactId"], "ARTIFACT_ID")
    require(type(item.get("size_in_bytes")) is int and item["size_in_bytes"] == reference["bytes"] and
            item.get("digest") == "sha256:" + reference["sha256"] and item.get("expired") is False,
            "ARTIFACT_DIGEST_OR_EXPIRY")
    name = item.get("name")
    require(type(name) is str and 0 < len(name) <= 256 and
            not any(ord(char) < 32 or ord(char) == 127 for char in name), "ARTIFACT_NAME")
    workflow = I.mapping(item.get("workflow_run"))
    require(type(workflow.get("id")) is int and workflow["id"] == int(run_id) and
            workflow.get("head_sha") == reviewed["commit"] and
            workflow.get("head_branch") == stages.SOURCE_REF.removeprefix("refs/heads/"), "ARTIFACT_SOURCE")
    created, expires = (stages.joint.timestamp(item.get(name)) for name in ("created_at", "expires_at"))
    require(0 < created <= now < expires <= created + RETENTION_SECONDS, "ARTIFACT_WINDOW")
    return item  # No packet name/schema, native output or qualification claim.
