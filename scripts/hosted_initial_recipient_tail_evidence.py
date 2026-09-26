"""Closed finite Stage1 tail exporter, not a B/K owner or upload permission.

The fixed custody caller must own the ORIGINAL completed B return and its
irreversible one-use continuation, the new actual child/native/file owners,
all nine groups' real frozen bytes, and a NEW same-child PUBLIC Recipient.
Neither these supplied counters/hashes nor this adapter's bytes establish any
of those premises. No B/Recipient is deserialized here. In particular the old
three-origin/schema4 P0 exporter is not widened or invoked again.

Only the unchanged POSIX/Windows encryption mechanisms are called. Their two
literal internal output names stay unchanged. The caller subsequently copies
their exact closed bytes to the two fixed outer tail aliases; this module
never renames, edits, uploads or deletes an original. Final encryption/native
self-tail diagnostics are explicitly outside the finite private cut.

``check()`` is the original caller's guard, not an acquisition callback.
``read_manifest()`` owns the fixed tail-export-output/manifest.json reader
through exact bytes/EOF/metadata and KNOWN close before it returns. Both are
fixed zero-argument cooperating-call seams, not caller-selected path/command
or arbitrary-manifest APIs. All actual work/close/output must fit the already
inherited original seal ceiling; timeout_seconds is only a shorter subcap.
"""
from __future__ import annotations

import hashlib
import os
import time

import hosted_initial_recipient_evidence as original


posix, windows = original.posix, original.windows
I, S = original.I, original.S
SCOPE = "ENCRYPTED_PRIVATE_INITIAL_RECIPIENT_CUSTODY_TAIL_V1"
MANIFEST_LIMIT = original.MANIFEST_LIMIT
MAP_LIMIT = 2 * 1024 * 1024
MAP_NAME = "custody-tail-map.json"
ARTIFACT_MEMBER = "custody-tail.tar.gz.gpg"
MANIFEST_MEMBER = "custody-tail-manifest.json"
CARRIER_MEMBERS = (posix.ARTIFACT, posix.MANIFEST, ARTIFACT_MEMBER, MANIFEST_MEMBER)
GROUPS = (
    "RETURNED", "CRYPTO_SERVICE", "POST_EXPORT_AUTHORITY", "SEAL_AUTHORITY", "SEAL",
    "P0_EXPORT_DIAGNOSTICS", "P0_VALIDATION_MAP_REFERENCE", "BEFORE_AUTHORITY",
    "NEW_RECIPIENT_VALIDATION",
)
FIXED_COUNTS = {
    "RETURNED": 13, "CRYPTO_SERVICE": 6, "POST_EXPORT_AUTHORITY": 279,
    "SEAL_AUTHORITY": 279, "SEAL": 1, "P0_VALIDATION_MAP_REFERENCE": 1,
    "BEFORE_AUTHORITY": 280,
}
PREDECESSOR_FIELDS = {
    "cryptoStepSha256", "collectSha256", "sealSha256", "beforeAuthoritySha256", "originalWindowSha256",
}
CUT_FIELDS = {"mapSha256", "mapBytes", "memberCount", "totalBytes", "groups"}
P0_FIELDS = {
    "schema", "scope", "kind", "selection", "source", "github", "policy", "initialRecipient",
    "primary", "copy", "recipient", "testAcceptance", "productiveAuthority", "cacheAuthority",
    "exportSaveAuthority", "budgetAcceptance", "artifact",
}
CREDENTIAL_NAMES = (original.acquisition.origin.wire.TOKEN_ENV, "GITHUB_TOKEN", "GH_TOKEN",
    "ACTIONS_RUNTIME_TOKEN", "ACTIONS_CACHE_URL", "ACTIONS_RESULTS_URL")
CONTEXT_NAMES = (
    "GITHUB_ACTIONS", "GITHUB_REPOSITORY", "GITHUB_SERVER_URL", "GITHUB_API_URL", "RUNNER_ENVIRONMENT",
    "GITHUB_EVENT_NAME", "GITHUB_REF", "GITHUB_SHA", "GITHUB_WORKFLOW_SHA", "GITHUB_WORKFLOW_REF",
    "GITHUB_JOB", "GITHUB_RUN_ID", "GITHUB_RUN_ATTEMPT", "RUNNER_OS", "RUNNER_ARCH", "RUNNER_NAME",
    "GITHUB_WORKSPACE", "GITHUB_EVENT_PATH",
)


def require(value, code):
    if not value:
        raise posix.EvidenceError("INITIAL_TAIL_EVIDENCE_" + code)


def _fields(value, names):
    require(type(value) is dict and all(type(key) is str for key in value) and set(value) == names, "FIELDS")


def _integer(value, minimum, maximum):
    require(type(value) is int and minimum <= value <= maximum, "INTEGER")
    return value


def _artifact(value):
    _fields(value, {"name", "sha256", "size"})
    require(type(value["name"]) is str and value["name"] == posix.ARTIFACT, "INTERNAL_ARTIFACT_NAME")
    original._sha(value["sha256"])
    _integer(value["size"], 1, posix.MAX_CIPHERTEXT_BYTES)
    return value


def _p0(raw):
    """Old-schema preflight only; _current_p0 checks EVERY field before export.

    This is not a historical/producer-original validator. The actual custody
    caller owns that proof. Exact re-derivation below additionally prevents
    otherwise uninspected P0 fields from being copied into this public schema.
    """
    require(type(raw) is bytes and 0 < len(raw) <= MANIFEST_LIMIT, "P0_BYTES")
    value = I.parse(raw, MANIFEST_LIMIT)
    original._graph(value)
    require(original._canonical(value) == raw, "P0_CANONICAL")
    _fields(value, P0_FIELDS)
    require(type(value["schema"]) is int and value["schema"] == 4 and value["scope"] == original.SCOPE and
        type(value["kind"]) is str and value["kind"] in ("gate", "worker") and
        type(value["selection"]) is str and value["testAcceptance"] == "NOT_PERFORMED" and
        value["productiveAuthority"] is False and value["cacheAuthority"] is False and
        value["exportSaveAuthority"] is False and value["budgetAcceptance"] == "NOT_ADMITTED", "P0_SCOPE")
    S.bootstrap.selection(value["selection"])
    S.joint.source(value["source"])
    for name in ("github", "policy", "initialRecipient", "recipient"):
        require(type(value[name]) is dict, "P0_BINDING_TYPE")
    _fields(value["primary"], original.PRIMARY_FIELDS)
    require(value["primary"]["outcome"] == "success" and value["primary"]["step"] ==
        ("initial-originals" if value["kind"] == "gate" else "canonical-initialization"), "P0_PRIMARY")
    for name in ("resultSha256", "handoffSha256", "inventorySha256"):
        original._sha(value["primary"][name])
    copied = value["copy"]
    _fields(copied, original.COPY_FIELDS)
    _fields(copied["origins"], set(original.ORIGINS))
    for checksum in (copied["mapSha256"], *copied["origins"].values()):
        original._sha(checksum)
    require(len(set(copied["origins"].values())) == len(original.ORIGINS), "P0_ORIGINS")
    _integer(copied["memberCount"], 1, posix.MAX_MEMBERS - 1)
    _integer(copied["totalBytes"], 1, posix.MAX_BYTES)
    _artifact(value["artifact"])
    return value


def _cut(value, p0, native_windows):
    """Finite accounting DATA, never evidence of an original read/copy/close.

    P0 already counts its four maps. Tail counts its own map exactly once, but
    the private map never includes/hashes itself recursively. Each flat TAR
    root is charged separately. Equal duplicate contents retain separate cost.
    """
    require(type(native_windows) is bool, "PLATFORM_TYPE")
    _fields(value, CUT_FIELDS)
    original._sha(value["mapSha256"])
    _integer(value["mapBytes"], 1, MAP_LIMIT)
    _fields(value["groups"], set(GROUPS))
    counts, sizes = 0, 0
    for name in GROUPS:
        row = value["groups"][name]
        _fields(row, {"memberCount", "totalBytes"})
        count = _integer(row["memberCount"], 1, posix.MAX_MEMBERS)
        size = _integer(row["totalBytes"], 1, posix.MAX_BYTES)
        if name in FIXED_COUNTS:
            require(count == FIXED_COUNTS[name], "REQUIRED_GROUP_COUNT")
        elif name == "P0_EXPORT_DIAGNOSTICS":
            require(count == (4 if native_windows else 7), "P0_DIAGNOSTIC_COUNT")
        else:
            # Windows: nine genuine validation files plus the actual summary.
            # POSIX: ten..74 genuine files plus that same-process summary.
            require(name == "NEW_RECIPIENT_VALIDATION" and
                (count == 10 if native_windows else 11 <= count <= 75), "NEW_VALIDATION_COUNT")
        counts += count
        sizes += size
    require(type(value["memberCount"]) is int and value["memberCount"] == counts + 1 and
        type(value["totalBytes"]) is int and value["totalBytes"] == sizes + value["mapBytes"], "CUT_MAP_ACCOUNTING")
    copied = p0["copy"]
    require(copied["memberCount"] + value["memberCount"] + 2 <= posix.MAX_MEMBERS and
        copied["totalBytes"] + value["totalBytes"] <= posix.MAX_BYTES, "SHARED_PLAINTEXT_OR_MEMBER_CAP")
    return value


def _predecessors(value):
    _fields(value, PREDECESSOR_FIELDS)
    for checksum in value.values():
        original._sha(checksum)
    return value


def _fixed_paths(pin, native_windows, evidence, output):
    recipient = pin[0]
    if native_windows:
        work_path, evidence_path, output_path = recipient.work.path, evidence.path, output.path
    else:
        work_path, evidence_path, output_path = recipient.work_dir, evidence, output
    require((work_path.name, evidence_path.name, output_path.name) ==
        ("tail-public-crypto", "tail-copied-evidence", "tail-export-output") and
        work_path.parent == evidence_path.parent == output_path.parent, "FIXED_SIBLING_PATHS")


def _current_p0(p0, original_raw, event_raw, policy_raw, recipient, native_windows):
    """Use the UNCHANGED identity validator, not its old exporter or schema API.

    It checks the current real event/host/policy/key and the closed match. Its
    complete builtin graph must equal P0 minus artifact, including all fields
    not needed by the new public manifest. This cannot create or authenticate
    the original B/native/Step returns, which remain the caller's obligation.
    """
    authority = p0["initialRecipient"]
    require(type(authority.get("freshReturnSha256")) is str and type(authority.get("matchSha256")) is str,
        "P0_AUTHORITY_HASHES")
    for name in ("freshReturnSha256", "matchSha256"):
        original._sha(authority[name])
    require(authority["matchSha256"] == hashlib.sha256(original_raw).hexdigest(), "P0_ORIGINAL_MATCH_HASH")
    current = original._manifest(kind=p0["kind"], selection=p0["selection"],
        source_commit=p0["source"]["commit"], source_tree=p0["source"]["tree"], match_raw=original_raw,
        event_raw=event_raw, policy_raw=policy_raw, primary=p0["primary"], copied=p0["copy"],
        authority={"returnSha256": authority["freshReturnSha256"], "matchSha256": authority["matchSha256"]},
        recipient=recipient, native_windows=native_windows)
    pin = original._graph(current)
    require(pin[1] == original._graph({name: value for name, value in p0.items() if name != "artifact"})[1],
        "P0_CURRENT_IDENTITY")
    return current


def _manifest(p0, p0_raw, current, service_job_id, predecessors, cut):
    # Every field below comes from the exact current closed P0 graph or the
    # caller's separately pinned fixed typed B/cut data. No raw original leaks.
    _integer(service_job_id, 1, 10 ** 20 - 1)
    _predecessors(predecessors)
    _, selected_role, _system, _arch = S.bootstrap.selection(p0["selection"])
    role = "linux-x64" if p0["kind"] == "gate" else selected_role
    _cut(cut, p0, role == "windows-x64")
    require(original._graph(current)[1] ==
        original._graph({name: value for name, value in p0.items() if name != "artifact"})[1], "CURRENT_GRAPH")
    policy = current["policy"]
    _fields(policy, {"origin", "commit", "blob", "path", "sha256", "fingerprint", "keySha256", "expiresAt", "retentionDays"})
    require(type(policy["retentionDays"]) is int and policy["retentionDays"] == 14, "FINITE_RETENTION")
    github = current["github"]
    S.joint.run({"runId": github["runId"], "runAttempt": github["runAttempt"]})
    result = {"schema": 1, "scope": SCOPE, "kind": p0["kind"], "selection": p0["selection"],
        "source": original._copy(current["source"]),
        "github": {"repository": I.REPOSITORY, "runId": github["runId"], "runAttempt": github["runAttempt"],
            "job": github["job"], "jobId": service_job_id, "role": role},
        "policy": {name: policy[name] for name in ("sha256", "fingerprint", "keySha256", "expiresAt", "retentionDays")},
        "recipient": original._copy(current["recipient"]),
        "p0": {"manifestSha256": hashlib.sha256(p0_raw).hexdigest(), "artifact": original._copy(p0["artifact"]),
            "privateMemberCount": p0["copy"]["memberCount"], "privateTotalBytes": p0["copy"]["totalBytes"]},
        "predecessors": original._copy(predecessors), "cut": {"mapName": MAP_NAME, **original._copy(cut)},
        "transport": {"artifactMember": ARTIFACT_MEMBER, "manifestMember": MANIFEST_MEMBER,
            "backendArtifact": posix.ARTIFACT, "backendManifest": posix.MANIFEST},
        "finalPrivateOriginals": {"disposition": "NOT_DELIVERED", "coverage": "EXCLUDED_FROM_K_AND_R",
            "requiredEvidence": "NOT_USED_AS_QUALIFICATION_ORIGINALS"},
        "testAcceptance": "NOT_PERFORMED", "productiveAuthority": False, "cacheAuthority": False,
        "exportSaveAuthority": False, "budgetAcceptance": "NOT_ADMITTED"}
    original._graph(result)
    return result


def _carrier_limit(p0_raw, p0, raw, artifact):
    """Charge four INNER literal files, not a provider ZIP/digest/expiry claim."""
    require(type(p0_raw) is bytes and 0 < len(p0_raw) <= MANIFEST_LIMIT and
        type(raw) is bytes and 0 < len(raw) <= MANIFEST_LIMIT, "CARRIER_MANIFEST_BYTES")
    _artifact(artifact)
    ciphertext = p0["artifact"]["size"] + artifact["size"]
    require(ciphertext <= posix.MAX_CIPHERTEXT_BYTES and
        ciphertext + len(p0_raw) + len(raw) <= posix.MAX_CIPHERTEXT_BYTES, "SHARED_CARRIER_CAP")


def export_encrypted(evidence, output, recipient, *, p0_manifest_raw, original_match, before_match,
        event_raw, policy_raw, service_job_id, predecessors, cut, check, read_manifest, timeout_seconds) -> bytes:
    """Return exact original tail manifest bytes, not K/U/runtime acceptance.

    No optional manifest/name/group/cap override exists. ``cut`` is exactly
    mapSha256/mapBytes/memberCount/totalBytes/groups; all nine groups and the
    separately closed private map are mandatory. The backend receives only the
    actual tail's already-accounted count/bytes, never another full allowance.
    The caller must reject a too-short original interval before this entry,
    including the unchanged Windows backend's possible30-second finish work.
    """
    require(os.name in ("posix", "nt") and callable(check) and callable(read_manifest), "CALLER")
    platform_name, native_windows = os.name, os.name == "nt"
    require(not any(name in os.environ for name in CREDENTIAL_NAMES), "CREDENTIAL_IN_CRYPTO")
    require(type(event_raw) is bytes and 0 < len(event_raw) <= I.EVENT_LIMIT and
        type(policy_raw) is bytes and 0 < len(policy_raw) <= I.POLICY_LIMIT, "ORIGINAL_BYTES")
    _integer(timeout_seconds, 1, 240)
    p0 = _p0(p0_manifest_raw)
    p0_pin = original._graph(p0)
    input_pins = tuple(original._graph(value) for value in (predecessors, cut))
    original_pin = original._match_pin(original_match, p0["kind"])
    before_pin = original._match_pin(before_match, p0["kind"])
    require(original_pin[3] == before_pin[3], "BEFORE_MATCH_DIFFERS")
    recipient_pin = original._recipient_pin(recipient, native_windows, evidence, output)
    _fixed_paths(recipient_pin, native_windows, evidence, output)
    _integer(service_job_id, 1, 10 ** 20 - 1)
    _predecessors(predecessors)
    _cut(cut, p0, native_windows)
    retained_env = tuple((name, os.environ.get(name)) for name in CONTEXT_NAMES)

    def passive():
        require(os.name == platform_name and not any(name in os.environ for name in CREDENTIAL_NAMES) and
            all(os.environ.get(name) == value for name, value in retained_env), "CONTEXT_CHANGED")
        original._graph_current(p0_pin)
        original._match_current(original_pin)
        original._match_current(before_pin)
        original._recipient_current(recipient_pin)
        for pin in input_pins:
            original._graph_current(pin)
        _fixed_paths(recipient_pin, native_windows, evidence, output)

    def manifest():
        passive()
        check()
        passive()
        current = _current_p0(p0, original_pin[3], event_raw, policy_raw, recipient, native_windows)
        current_pin = original._graph(current)  # Pin this supplier result before the next callback.
        result = _manifest(p0, p0_manifest_raw, current, service_job_id, predecessors, cut)
        result_pin = original._graph(result)
        passive()
        check()
        passive()
        now = int(time.time())
        passive()
        original._graph_current(current_pin)
        original._graph_current(result_pin)
        require(current["initialRecipient"]["firstUseAt"] <= now < current["initialRecipient"]["expiresAt"] <=
            current["policy"]["expiresAt"] <= recipient.expires_at, "FINAL_POLICY_OR_KEY_WINDOW")
        return result

    expected = manifest()
    expected_shape = original._graph(expected)[1]

    def factory():
        result = manifest()
        require(original._graph(result)[1] == expected_shape, "MANIFEST_IDENTITY_CHANGED")
        return result  # Windows mutates only the first returned dict with artifact.

    # Each backend counts its flat archive root. Both private roots were already
    # charged jointly in _cut, so neither can consume the other's budget again.
    max_bytes, max_members = cut["totalBytes"], cut["memberCount"] + 1
    if native_windows:
        returned = windows._export(evidence, output, recipient, factory, max_bytes=max_bytes,
            max_members=max_members, timeout_seconds=timeout_seconds)
    else:
        returned = posix._export_bound_manifest(evidence, output, recipient, manifest=factory(),
            max_bytes=max_bytes, max_members=max_members, timeout_seconds=timeout_seconds)
    returned_pin = original._graph(returned)  # FIRST action after actual backend return.
    _fields(returned, set(expected) | {"artifact"})
    require(original._graph({name: value for name, value in returned.items() if name != "artifact"})[1] == expected_shape,
        "RETURN_IDENTITY")
    _artifact(returned["artifact"])
    passive()
    raw = original._canonical(returned)  # Canonical-encode the actual return ONCE, before readback.
    original._graph_current(returned_pin)
    _carrier_limit(p0_manifest_raw, p0, raw, returned["artifact"])
    require(original._graph(manifest())[1] == expected_shape, "RETURN_CURRENT_IDENTITY")
    original._graph_current(returned_pin)
    actual = read_manifest()
    original._graph_current(returned_pin)
    passive()
    require(type(actual) is bytes and actual == raw, "ORIGINAL_MANIFEST_READBACK")
    require(original._graph(manifest())[1] == expected_shape, "FINAL_CURRENT_IDENTITY")
    original._graph_current(returned_pin)
    passive()
    return raw
