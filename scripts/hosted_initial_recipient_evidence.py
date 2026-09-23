"""Closed Stage1 evidence adapter, not acquisition, a launcher or admission.

The fixed caller owns actual primary Step success, original fresh HTTP/native
returns, the three-origin frozen copy, same-process PUBLIC Recipient provenance,
all original absolute fences and known retirement. Typed records/digests supplied
here do not establish those facts. No ordinary Admission, arbitrary manifest or
JSON-restored live Recipient is accepted. The terminal transport self-tail is
not declared inside the already-frozen evidence packet.

``read_manifest()`` must read only the fixed output/manifest.json through the
caller's bounded native owner and return after known file closure. ``check()``
is that owner's original guard, not a replacement HTTP acquisition. Neither
callback receives a caller-selected command, path, URL or manifest.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path, PosixPath, WindowsPath
import re
import time

import hosted_evidence as posix
import hosted_windows_evidence as windows
import hosted_initial_recipient_originals as acquisition


ROOT = Path(__file__).resolve().parents[1]
I, G, S = acquisition.identity, acquisition.gate, acquisition.stages
SCOPE = "ENCRYPTED_PRIVATE_INITIAL_RECIPIENT_EVIDENCE"
ORIGINS = ("PRIMARY", "AUTHORITY_PRE_EXPORT", "RECIPIENT_PRE_EXPORT")
MANIFEST_LIMIT = 64 * 1024
PRIMARY_FIELDS = {"step", "outcome", "resultSha256", "handoffSha256", "inventorySha256"}
COPY_FIELDS = {"mapSha256", "memberCount", "totalBytes", "origins"}
AUTHORITY_FIELDS = {"returnSha256", "matchSha256"}
COMMON_MATCH = {"schema", "scope", "authority", "originalBase", "reviewed", "source", "github", "policy",
                "environment", "firstUseAt", "notBefore", "expiresAt"}


def require(value, code):
    if not value:
        raise posix.EvidenceError("INITIAL_EVIDENCE_" + code)


def _fields(value, names):
    require(type(value) is dict and set(value) == names and all(type(key) is str for key in value), "FIELDS")


def _sha(value):
    require(type(value) is str and re.fullmatch(r"[0-9a-f]{64}", value), "DIGEST")
    return value


def _graph(value):
    """Finite exact builtin graph; capture before any fallible external supplier.

    References and independent immutable shapes are both retained. In particular,
    replacing a nested dict/list by an equal one cannot detach the saved graph.
    This is a cooperating-call contract, not a sandbox against replaced code.
    """
    rows, seen, count = [], set(), 0

    def visit(current, depth):
        nonlocal count
        count += 1
        require(depth <= 16 and count <= 2048, "GRAPH_LIMIT")
        kind = type(current)
        if kind in (dict, list):
            require(id(current) not in seen and len(current) <= 128, "GRAPH_ALIAS_OR_SIZE")
            seen.add(id(current))
            if kind is dict:
                items = tuple(dict.items(current))
                require(all(type(key) is str and len(key) <= 128 for key, _ in items), "GRAPH_KEY")
                children = tuple((key, visit(child, depth + 1)) for key, child in items)
                shape = (dict, tuple(sorted(children)))
                rows.append((current, dict, items))
            else:
                items = tuple(current)
                shape = (list, tuple(visit(child, depth + 1) for child in items))
                rows.append((current, list, items))
            return shape
        require(kind in (str, int, bool, type(None)), "GRAPH_TYPE")
        require(kind is not str or len(current) <= 4096, "GRAPH_STRING")
        require(kind is not int or 0 <= current < 2 ** 128, "GRAPH_INTEGER")
        return kind, current

    shape = visit(value, 0)
    return value, shape, tuple(rows)


def _graph_current(pin):
    for original, kind, items in pin[2]:
        require(type(original) is kind, "GRAPH_CHANGED")
        current = tuple(dict.items(original)) if kind is dict else tuple(original)
        require(len(current) == len(items), "GRAPH_CHANGED")
        for actual, saved in zip(current, items):
            if kind is dict:
                require(type(actual[0]) is str and actual[0] == saved[0], "GRAPH_CHANGED")
                actual, saved = actual[1], saved[1]
            require(type(actual) is type(saved) and
                    (actual is saved if type(saved) in (dict, list) else actual == saved), "GRAPH_CHANGED")


def _copy(value):
    # Only already-checked JSON builtins; never deepcopy a live object/owner.
    if type(value) is dict:
        return {key: _copy(child) for key, child in value.items()}
    if type(value) is list:
        return [_copy(child) for child in value]
    return value


def _canonical(value):
    # EXACT maintained POSIX export / Windows _manifest_bytes spelling.
    raw = (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
                      allow_nan=False) + "\n").encode("ascii")
    require(0 < len(raw) <= MANIFEST_LIMIT, "MANIFEST_LIMIT")
    return raw


def _match_pin(value, kind):
    expected = G.GateEligibility if kind == "gate" else S.BootstrapMatch
    require(type(value) is expected and type(value.__dict__) is dict and
            set(value.__dict__) == {"record"} and type(value.record) is bytes and
            0 < len(value.record) <= S.LIMIT, "MATCH_TYPE")
    return value, expected, value.__dict__, value.record


def _match_current(pin):
    value, kind, dictionary, raw = pin
    require(type(value) is kind and value.__dict__ is dictionary and set(dictionary) == {"record"} and
            type(value.record) is bytes and value.record == raw, "MATCH_CHANGED")


def _paths_pin(paths):
    result = []
    for path in paths:
        require(type(path) in (PosixPath, WindowsPath) and path.is_absolute() and ".." not in path.parts,
                "PATH_TYPE")
        result.append((path, type(path), str(path), tuple(path.parts)))
    return tuple(result)


def _paths_current(pins):
    for path, kind, text, parts in pins:
        require(type(path) is kind and str(path) == text and tuple(path.parts) == parts, "PATH_CHANGED")


def _recipient_pin(recipient, native_windows, evidence, output):
    kind = windows.Recipient if native_windows else posix.Recipient
    names = (("work", "executable", "executable_sha256", "work_identity", "fingerprint",
              "encryption_fingerprint", "expires_at", "key_sha256", "job_id") if native_windows else
             ("work_dir", "home", "executable", "fingerprint", "encryption_fingerprint",
              "expires_at", "key_sha256", "work_identity"))
    require(type(recipient) is kind and type(recipient.__dict__) is dict and
            set(recipient.__dict__) == set(names), "RECIPIENT_TYPE")
    values = tuple(recipient.__dict__[name] for name in names)
    require(all(type(getattr(recipient, name)) is str and re.fullmatch(r"[0-9A-F]{40}", getattr(recipient, name))
                for name in ("fingerprint", "encryption_fingerprint")) and
            type(recipient.expires_at) is int and recipient.expires_at > 0, "RECIPIENT_PUBLIC_FIELDS")
    _sha(recipient.key_sha256)
    identity = recipient.work_identity
    require(type(identity) is tuple and len(identity) == 2 and type(identity[0]) is int and
            0 <= identity[0] < 2 ** 64, "RECIPIENT_IDENTITY")
    directories = []
    if native_windows:
        _sha(recipient.executable_sha256)
        require(type(recipient.job_id) is str and re.fullmatch(r"[0-9a-f]{32}", recipient.job_id) and
                type(identity[1]) is str and re.fullmatch(r"[0-9a-f]{32}", identity[1]), "RECIPIENT_IDENTITY")
        for directory in (recipient.work, evidence, output):
            require(type(directory) is windows.files.PrivateDirectory and directory._closed is False and
                    type(directory.identity) is tuple, "WINDOWS_PINNED_DIRECTORY")
            directories.append((directory, directory.__dict__, directory.path, directory.identity))
        require(recipient.work.identity == identity, "RECIPIENT_IDENTITY")
        paths = (recipient.executable, *(row[2] for row in directories))
    else:
        require(type(identity[1]) is int and 0 < identity[1] < 2 ** 64, "RECIPIENT_IDENTITY")
        paths = (recipient.work_dir, recipient.home, recipient.executable, evidence, output)
    return recipient, kind, recipient.__dict__, names, values, _paths_pin(paths), tuple(directories)


def _recipient_current(pin):
    recipient, kind, dictionary, names, values, paths, directories = pin
    require(type(recipient) is kind and recipient.__dict__ is dictionary and set(dictionary) == set(names),
            "RECIPIENT_CHANGED")
    for name, saved in zip(names, values):
        actual = dictionary[name]
        require(type(actual) is type(saved) and
                (actual == saved if type(saved) in (str, int) else actual is saved), "RECIPIENT_CHANGED")
    for directory, dictionary, path, identity in directories:
        require(type(directory) is windows.files.PrivateDirectory and directory.__dict__ is dictionary and
                directory.path is path and directory.identity is identity and directory._closed is False,
                "WINDOWS_DIRECTORY_CHANGED")
    _paths_current(paths)


def _manifest(*, kind, selection, source_commit, source_tree, match_raw, event_raw, policy_raw,
              primary, copied, authority, recipient, native_windows):
    """Current local binding only: this does not acquire HTTP or query Git."""
    require(acquisition.origin.wire.TOKEN_ENV not in os.environ, "TOKEN_IN_CRYPTO")
    value = I.parse(match_raw, S.LIMIT)
    require(match_raw == I.encoded(value), "MATCH_ENCODING")
    extras = ({"stage", "selector", "workerAdmission", "qualificationAcceptance"} if kind == "gate" else set())
    _fields(value, COMMON_MATCH | extras)
    require(type(value["schema"]) is int and value["schema"] == 1 and value["scope"] ==
            ("NONPRODUCTIVE_ELIGIBILITY" if kind == "gate" else S.STAGE1 + "_MATCH_ONLY_NOT_ADMISSION"), "MATCH_SCOPE")
    source = {"commit": I.sha(source_commit), "tree": I.sha(source_tree)}
    require(S.joint.source(value["originalBase"]) == S.BASE and
            S.joint.source(value["source"]) == S.joint.source(value["reviewed"]) == source and
            source["commit"] != S.BASE["commit"] and source["tree"] != S.BASE["tree"], "MATCH_SOURCE")
    current = int(time.time())
    policy, _public_key = I._policy(policy_raw, current)
    start, first, expires = (value[key] for key in ("notBefore", "firstUseAt", "expiresAt"))
    require(all(type(x) is int for x in (start, first, expires)) and
            policy["notBefore"] <= start <= first <= current < expires <= policy["expiresAt"] and
            expires - start <= 14 * 24 * 60 * 60 and policy["retrievalOwner"] == S.joint.OWNER_LOGIN,
            "MATCH_WINDOW")
    blob = hashlib.sha1(b"blob " + str(len(policy_raw)).encode("ascii") + b"\0" + policy_raw).hexdigest()
    require(hashlib.sha256(policy_raw).hexdigest() == S.POLICY_SHA256 and value["policy"] == {
        "origin": "reviewed-head", "commit": source_commit, "blob": blob,
        "path": I.POLICY_PATH, "sha256": S.POLICY_SHA256}, "POLICY_ORIGIN")
    declared = policy["recipient"]
    require(recipient.fingerprint == declared["fingerprint"] and recipient.key_sha256 == declared["sha256"] and
            current < policy["expiresAt"] <= recipient.expires_at, "RECIPIENT_POLICY")
    author = value["authority"]
    _fields(author, {"id", "url", "bodySha256", "owner", "ownerId", "createdAt"})
    S.positive(author["id"])
    _sha(author["bodySha256"])
    require(author["owner"] == S.joint.OWNER_LOGIN and type(author["ownerId"]) is int and
            author["ownerId"] == S.joint.OWNER_ID and author["url"] ==
            "https://github.com/" + I.REPOSITORY + "/issues/437#issuecomment-" + str(author["id"]) and
            0 < S.joint.timestamp(author["createdAt"]) <= first, "AUTHORITY_IDENTITY")
    S.environment(value["environment"])
    env = dict(os.environ)
    require(ROOT == ROOT.resolve(strict=True) and env.get("GITHUB_WORKSPACE") == str(ROOT), "WORKSPACE")
    actual_event = I.read_regular(Path(env.get("GITHUB_EVENT_PATH", "")), I.EVENT_LIMIT)
    require(type(actual_event) is bytes and actual_event == event_raw, "EVENT_CHANGED")
    observed = acquisition._context(env, event_raw, kind, first)
    require(observed["source"] == source and observed["inputs"]["selection"] == selection and
            native_windows is (observed["role"] == "windows-x64"), "ACTUAL_SELECTION")
    github = dict(observed["github"])
    if kind == "worker":
        github.update(profile=S.bootstrap.PROFILE, selection=selection)
    require(value["github"] == github, "MATCH_JOB")
    if kind == "gate":
        require(value["stage"] == "stage1" and value["workerAdmission"] == "NOT_PERFORMED" and
                value["qualificationAcceptance"] == "NOT_ESTABLISHED_BY_GATE", "GATE_ONLY")
        selected = {"schema": 1, "scope": "INITIAL_RECIPIENT_SELECTED_APPROVAL_ONLY", "stage": "stage1",
            "runId": github["runId"], "runAttempt": github["runAttempt"], "commentId": author["id"],
            "bodySha256": author["bodySha256"], "environmentId": value["environment"]["id"],
            "environmentName": S.ENVIRONMENT,
            "approvalLine": "AUTHORIZE_INITIAL_RECIPIENT stage1 " + github["runId"] + "/" +
                github["runAttempt"] + " " + str(author["id"]) + " " + author["bodySha256"],
            "owner": {"login": S.joint.OWNER_LOGIN, "id": S.joint.OWNER_ID}}
        require(_graph(value["selector"])[1] == _graph(selected)[1], "GATE_SELECTOR")
    return {"schema": 4, "scope": SCOPE, "kind": kind, "selection": selection, "source": source,
        "github": {**github, "repository": I.REPOSITORY, "eventSha256": hashlib.sha256(event_raw).hexdigest()},
        "policy": {**value["policy"], "fingerprint": declared["fingerprint"], "keySha256": declared["sha256"],
                   "expiresAt": policy["expiresAt"], "retentionDays": 14},
        "initialRecipient": {"authority": author, "environment": value["environment"],
            "originalBase": value["originalBase"], "reviewed": value["reviewed"], "firstUseAt": first,
            "notBefore": start, "expiresAt": expires, "matchSha256": authority["matchSha256"],
            "freshReturnSha256": authority["returnSha256"]},
        "primary": _copy(primary), "copy": _copy(copied),
        "recipient": {"fingerprint": recipient.fingerprint, "encryptionFingerprint": recipient.encryption_fingerprint,
                      "keySha256": recipient.key_sha256, "expiresAt": recipient.expires_at},
        "testAcceptance": "NOT_PERFORMED", "productiveAuthority": False, "cacheAuthority": False,
        "exportSaveAuthority": False, "budgetAcceptance": "NOT_ADMITTED"}


def export_encrypted(evidence, output, recipient, *, kind, selection, source_commit, source_tree,
                     original_match, fresh_match, event_raw, policy_raw, primary, copied, authority,
                     check, read_manifest, timeout_seconds, max_bytes=posix.MAX_BYTES,
                     max_members=posix.MAX_MEMBERS) -> bytes:
    """Return canonical ORIGINAL manifest bytes, not success/custody/Step authority.

    primary: step/outcome/resultSha256/handoffSha256/inventorySha256.
    copied: mapSha256/memberCount/totalBytes/origins, where origins is exactly
    PRIMARY/AUTHORITY_PRE_EXPORT/RECIPIENT_PRE_EXPORT -> original map SHA256.
    authority: returnSha256/matchSha256 of the actual fresh acquisition binding.
    All mappings are closed supplied data, never arbitrary public manifests.

    POSIX output is an ABSENT path reserved by the backend. Native Windows
    output/evidence are already-pinned, new-empty/read-only private directories.
    The caller keeps its owners and the same-process Recipient alive through
    actual backend return/readback and subsequent original known retirement.
    """
    require(type(kind) is str and kind in ("gate", "worker") and type(selection) is str, "KIND")
    require(os.name in ("posix", "nt") and callable(check) and callable(read_manifest), "CALLER")
    platform_name = os.name
    native_windows = platform_name == "nt"
    require(type(event_raw) is bytes and 0 < len(event_raw) <= I.EVENT_LIMIT and
            type(policy_raw) is bytes and 0 < len(policy_raw) <= I.POLICY_LIMIT, "ORIGINAL_BYTES")
    original_pin, fresh_pin = _match_pin(original_match, kind), _match_pin(fresh_match, kind)
    require(original_pin[3] == fresh_pin[3], "FRESH_MATCH_DIFFERS")
    input_pins = tuple(_graph(value) for value in (primary, copied, authority))
    recipient_pin = _recipient_pin(recipient, native_windows, evidence, output)
    _fields(primary, PRIMARY_FIELDS)
    require(primary["step"] == ("initial-originals" if kind == "gate" else "canonical-initialization") and
            primary["outcome"] == "success", "PRIMARY_STEP")
    for key in ("resultSha256", "handoffSha256", "inventorySha256"):
        _sha(primary[key])
    _fields(copied, COPY_FIELDS)
    _fields(copied["origins"], set(ORIGINS))
    _sha(copied["mapSha256"])
    for digest in copied["origins"].values():
        _sha(digest)
    require(len(set(copied["origins"].values())) == 3, "COPY_ORIGINS")
    _fields(authority, AUTHORITY_FIELDS)
    for digest in authority.values():
        _sha(digest)
    require(authority["matchSha256"] == hashlib.sha256(fresh_pin[3]).hexdigest(), "FRESH_MATCH_HASH")
    for value, maximum in ((max_bytes, posix.MAX_BYTES), (max_members, posix.MAX_MEMBERS), (timeout_seconds, 240)):
        require(type(value) is int and 0 < value <= maximum, "BOUNDS")
    require(type(copied["memberCount"]) is int and 0 < copied["memberCount"] <= max_members and
            type(copied["totalBytes"]) is int and 0 < copied["totalBytes"] <= max_bytes, "COPY_BOUNDS")
    retained_env = tuple((name, os.environ.get(name)) for name in (
        "GITHUB_ACTIONS", "GITHUB_REPOSITORY", "GITHUB_SERVER_URL", "GITHUB_API_URL", "RUNNER_ENVIRONMENT",
        "GITHUB_EVENT_NAME", "GITHUB_REF", "GITHUB_SHA", "GITHUB_WORKFLOW_SHA", "GITHUB_WORKFLOW_REF",
        "GITHUB_JOB", "GITHUB_RUN_ID", "GITHUB_RUN_ATTEMPT", "RUNNER_OS", "RUNNER_ARCH", "RUNNER_NAME",
        "GITHUB_WORKSPACE", "GITHUB_EVENT_PATH"))

    def passive():
        require(os.name == platform_name and acquisition.origin.wire.TOKEN_ENV not in os.environ and
                all(os.environ.get(name) == value for name, value in retained_env), "CONTEXT_CHANGED")
        _match_current(original_pin)
        _match_current(fresh_pin)
        _recipient_current(recipient_pin)
        for pin in input_pins:
            _graph_current(pin)

    def manifest():
        passive()
        check()
        passive()
        result = _manifest(kind=kind, selection=selection, source_commit=source_commit, source_tree=source_tree,
            match_raw=original_pin[3], event_raw=event_raw, policy_raw=policy_raw, primary=primary,
            copied=copied, authority=authority, recipient=recipient, native_windows=native_windows)
        result_pin = _graph(result)
        passive()
        check()
        passive()
        # A successful final guard can still expose expiry or changed fields.
        # This local currency sample is NOT another remote acquisition.
        current = int(time.time())
        passive()
        _graph_current(result_pin)
        require(result["initialRecipient"]["firstUseAt"] <= current < result["initialRecipient"]["expiresAt"] <=
                result["policy"]["expiresAt"] <= result["recipient"]["expiresAt"], "FINAL_WINDOW")
        return result

    expected = manifest()
    expected_shape = _graph(expected)[1]

    def factory():
        result = manifest()
        require(_graph(result)[1] == expected_shape, "MANIFEST_IDENTITY_CHANGED")
        return result  # A NEW dict each call; Windows will add artifact only to the first.

    if native_windows:
        returned = windows._export(evidence, output, recipient, factory, max_bytes=max_bytes,
                                   max_members=max_members, timeout_seconds=timeout_seconds)
    else:
        returned = posix._export_bound_manifest(evidence, output, recipient, manifest=factory(),
            max_bytes=max_bytes, max_members=max_members, timeout_seconds=timeout_seconds)
    returned_pin = _graph(returned)  # FIRST action after actual backend return; no callback/reader/encoder.
    require(type(returned) is dict and set(returned) == set(expected) | {"artifact"}, "RETURN_FIELDS")
    require(_graph({key: value for key, value in returned.items() if key != "artifact"})[1] == expected_shape,
            "RETURN_IDENTITY")
    artifact = returned["artifact"]
    _fields(artifact, {"name", "sha256", "size"})
    require(artifact["name"] == posix.ARTIFACT and type(artifact["size"]) is int and
            0 < artifact["size"] <= posix.MAX_CIPHERTEXT_BYTES, "RETURN_ARTIFACT")
    _sha(artifact["sha256"])
    passive()
    raw = _canonical(returned)  # The actual return is canonical-encoded ONCE, before any file reread.
    _graph_current(returned_pin)
    require(_graph(manifest())[1] == expected_shape, "RETURN_CURRENT_IDENTITY")
    _graph_current(returned_pin)
    actual = read_manifest()
    _graph_current(returned_pin)
    passive()
    require(type(actual) is bytes and 0 < len(actual) <= MANIFEST_LIMIT and actual == raw, "MANIFEST_READBACK")
    require(_graph(manifest())[1] == expected_shape, "FINAL_CURRENT_IDENTITY")
    _graph_current(returned_pin)
    passive()
    return raw
