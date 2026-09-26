#!/usr/bin/env python3
"""Closed ordinary-CI identities for private test-transcript custody.

This is admission, not execution, recipient cryptographic validation, approval or
upload. In particular, a PR reads policy ONLY from its original base commit; a
candidate policy cannot bootstrap itself. No bootstrap policy is shipped here.
Original event/policy bytes belong in private custody, not the Actions log.
"""
from __future__ import annotations

import dataclasses
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import time

import hosted_primary_abi as abi


REPOSITORY = "p2pKit/P2pKit"
POLICY_PATH = ".github/test-evidence-recipient.json"
POLICY_LIMIT = 96 * 1024
EVENT_LIMIT = 2 * 1024 * 1024
MESSAGE_LIMIT = 64 * 1024
RELEASE_MARKER = b"[release ci]"
PROFILES = {
    "desktop": (".github/workflows/desktop-cross-host.yml", "verify", ("cli",)),
    "full": (".github/workflows/ci.yml", "complete-gate", ("cli", "diagnostics")),
}
SHA = re.compile(r"[0-9a-f]{40}\Z")
ID = re.compile(r"[1-9][0-9]{0,19}\Z")


class AdmissionError(ValueError):
    """Fixed public-safe reason; never contains event or environment values."""


def require(condition, code):
    if not condition:
        raise AdmissionError(code)


def parse(raw, limit):
    require(isinstance(raw, bytes) and 0 < len(raw) <= limit, "IDENTITY_JSON_SIZE")

    def unique(pairs):
        value = {}
        for key, item in pairs:
            require(key not in value, "IDENTITY_JSON_DUPLICATE")
            value[key] = item
        return value

    try:
        value = json.loads(raw, object_pairs_hook=unique,
                           parse_constant=lambda _: require(False, "IDENTITY_JSON_NONFINITE"))
    except (UnicodeError, json.JSONDecodeError, RecursionError):
        raise AdmissionError("IDENTITY_JSON_MALFORMED") from None
    require(type(value) is dict, "IDENTITY_JSON_OBJECT")
    return value


def encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode("ascii")


def sha(value):
    require(type(value) is str and SHA.fullmatch(value), "IDENTITY_FULL_SHA")
    return value


def mapping(value):
    require(type(value) is dict, "IDENTITY_EVENT_SHAPE")
    return value


def read_regular(path, limit):
    """Public admission inputs only; this is NOT the Windows privacy backend."""
    path = Path(path)
    require(path.is_absolute() and ".." not in path.parts, "IDENTITY_INPUT_PATH")
    try:
        for part in (path, *path.parents):
            info = part.lstat()
            require(not stat.S_ISLNK(info.st_mode) and not getattr(info, "st_file_attributes", 0) & 0x400,
                    "IDENTITY_INPUT_LINK")
        before = path.lstat()
        require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and 0 < before.st_size <= limit,
                "IDENTITY_INPUT_FILE")
        with path.open("rb") as stream:
            opened = os.fstat(stream.fileno())
            require(os.path.samestat(before, opened), "IDENTITY_INPUT_CHANGED")
            raw = stream.read(limit + 1)
            after = os.fstat(stream.fileno())
        current = path.lstat()
        require(os.path.samestat(before, after) and os.path.samestat(before, current) and
                before.st_size == after.st_size == current.st_size == len(raw) and
                before.st_mtime_ns == after.st_mtime_ns == current.st_mtime_ns, "IDENTITY_INPUT_CHANGED")
        return raw
    except OSError:
        raise AdmissionError("IDENTITY_INPUT_UNAVAILABLE") from None


class GitView:
    """Closed read-only Git queries delegated to the REQUIRED native owner.

    The invoking owner must already have obtained the full-history intended
    checkout. No fetch, credential, automatic object acquisition or source write
    occurs here. ``query_runner`` must capture both streams privately with live
    byte/time bounds, retain the complete original receipt and return stdout ONLY
    after exit zero, untruncated output and known full native-domain retirement.
    It must inject its own real ownership markers into the sanitized environment
    below and handle cancellation before returning/raising. This module neither
    launches children nor supplies a fallback process/thread implementation.

    The return-size check is defensive, not the live capture bound. Native owner
    controls and real caller integration remain separate required acceptance.
    This is not a sandbox against same-user candidate code (#120).
    """

    def __init__(self, root, environment, query_runner):
        require(callable(query_runner), "IDENTITY_OWNED_QUERY_REQUIRED")
        self.query_runner = query_runner
        require(not any(name.startswith("GIT_") and name != "GIT_TERMINAL_PROMPT"
                        for name in environment), "IDENTITY_GIT_OVERRIDE")
        self.root = Path(root)
        executable = shutil.which("git")
        require(executable is not None, "IDENTITY_GIT_UNAVAILABLE")
        self.executable = str(Path(executable).resolve(strict=True))
        self.environment = {"PATH": os.defpath, "LANG": "C", "LC_ALL": "C", "GIT_TERMINAL_PROMPT": "0",
                            "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull,
                            "GIT_NO_LAZY_FETCH": "1", "GIT_NO_REPLACE_OBJECTS": "1", "GIT_OPTIONAL_LOCKS": "0"}
        if os.name == "nt":
            # Windows os.environ normalizes keys to uppercase. admit freezes it
            # with dict(), which no longer has case-insensitive lookup behavior.
            require(type(environment.get("SYSTEMROOT")) is str and environment["SYSTEMROOT"],
                    "IDENTITY_WINDOWS_SYSTEM_ROOT")
            self.environment["SYSTEMROOT"] = environment["SYSTEMROOT"]

    def query(self, *args, limit=4096):
        require(type(limit) is int and 0 < limit <= EVENT_LIMIT, "IDENTITY_GIT_OUTPUT_LIMIT")
        try:
            result = self.query_runner(
                argv=(self.executable, "--no-replace-objects", "--no-pager", "-c", "core.fsmonitor=false",
                      "-C", str(self.root), *args),
                cwd=self.root, environment=dict(self.environment), stdout_limit=limit, stderr_limit=4096,
                timeout_seconds=15,
            )
        except Exception:
            # The owner retains the original private failure and retires its
            # domain. Do not publish raw stderr, paths or exception text here.
            # BaseException (including cancellation) is deliberately preserved.
            raise AdmissionError("IDENTITY_GIT_QUERY_FAILED") from None
        require(type(result) is bytes and len(result) <= limit, "IDENTITY_GIT_QUERY_OUTPUT")
        return result

    def commit(self, ref):
        return sha(self.query("rev-parse", "--verify", ref + "^{commit}").decode("ascii").strip())

    def tree(self, commit):
        return sha(self.query("rev-parse", "--verify", sha(commit) + "^{tree}").decode("ascii").strip())

    def parents(self, commit):
        values = self.query("show", "-s", "--format=%P", sha(commit)).decode("ascii").strip().split()
        return [sha(value) for value in values]

    def message(self, commit):
        return self.query("show", "-s", "--format=%B", sha(commit), limit=MESSAGE_LIMIT)

    def clean(self):
        return self.query("status", "--porcelain=v1", "--untracked-files=all", limit=EVENT_LIMIT) == b""

    def root_matches(self):
        return Path(os.fsdecode(self.query("rev-parse", "--show-toplevel").rstrip(b"\r\n"))) == self.root

    def policy(self, commit):
        # Inspect the tree entry first: symlink/submodule/executable policies do
        # not count. Its blob hash binds the separately retained complete bytes.
        value = self.query("ls-tree", "-z", sha(commit), "--", POLICY_PATH)
        match = re.fullmatch(rb"100644 blob ([0-9a-f]{40})\t" + re.escape(POLICY_PATH.encode()) + rb"\x00", value)
        require(match is not None, "MISSING_TRUSTED_RECIPIENT_POLICY")
        blob = match.group(1).decode("ascii")
        size = self.query("cat-file", "-s", blob).strip()
        require(re.fullmatch(rb"[1-9][0-9]{0,5}", size) and int(size) <= POLICY_LIMIT, "RECIPIENT_POLICY_SIZE")
        raw = self.query("cat-file", "blob", blob, limit=POLICY_LIMIT)
        require(len(raw) == int(size), "RECIPIENT_POLICY_CHANGED")
        actual = hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\x00" + raw).hexdigest()
        require(actual == blob, "RECIPIENT_POLICY_BLOB")
        return blob, raw

    def abi_baseline(self, commit, path):
        """Eight public reference blobs at the admitted full SHA; never a live API path."""
        require(type(path) is str and path in abi.BASELINES, "ABI_BASELINE_CLOSED_PATH")
        value = self.query("ls-tree", "-z", sha(commit), "--", path)
        match = re.fullmatch(rb"100644 blob ([0-9a-f]{40})\t" + re.escape(path.encode("ascii")) + rb"\x00", value)
        require(match is not None, "ABI_BASELINE_REGULAR_BLOB_REQUIRED")
        blob = match.group(1).decode("ascii")
        size = self.query("cat-file", "-s", blob).strip()
        require(re.fullmatch(rb"[1-9][0-9]{0,6}", size) and int(size) <= abi.FILE_LIMIT, "ABI_BASELINE_SIZE")
        raw = self.query("cat-file", "blob", blob, limit=abi.FILE_LIMIT)
        require(len(raw) == int(size), "ABI_BASELINE_CHANGED")
        require(abi.blob(raw) == blob, "ABI_BASELINE_BLOB")
        return blob, raw


@dataclasses.dataclass(frozen=True)
class Admission:
    # Bytes avoid mutable dictionaries altering an already admitted record.
    record: bytes
    original_event: bytes
    original_policy: bytes
    public_key: bytes
    fingerprint: str
    key_sha256: str
    expires_at: int


def _policy(raw, now):
    value = parse(raw, POLICY_LIMIT)
    require(set(value) == {"schema", "repository", "purpose", "notBefore", "expiresAt", "retentionDays",
                           "retrievalOwner", "recipient"} and type(value["schema"]) is int and
            value["schema"] == 1 and value["repository"] == REPOSITORY and
            value["purpose"] == "P2PKIT_TEST_TRANSCRIPTS", "RECIPIENT_POLICY_CONTRACT")
    require(type(now) is int and type(value["notBefore"]) is int and type(value["expiresAt"]) is int and
            0 < value["notBefore"] <= now < value["expiresAt"], "RECIPIENT_POLICY_VALIDITY")
    require(type(value["retentionDays"]) is int and value["retentionDays"] == 14, "RECIPIENT_POLICY_RETENTION")
    require(type(value["retrievalOwner"]) is str and
            re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?", value["retrievalOwner"]),
            "RECIPIENT_POLICY_RETRIEVAL_OWNER")
    recipient = mapping(value["recipient"])
    require(set(recipient) == {"publicKey", "fingerprint", "sha256"}, "RECIPIENT_POLICY_KEY")
    require(type(recipient["publicKey"]) is str and type(recipient["fingerprint"]) is str and
            re.fullmatch(r"[0-9A-F]{40}", recipient["fingerprint"]) and type(recipient["sha256"]) is str and
            re.fullmatch(r"[0-9a-f]{64}", recipient["sha256"]), "RECIPIENT_POLICY_KEY")
    try:
        key = recipient["publicKey"].encode("ascii")
    except UnicodeError:
        raise AdmissionError("RECIPIENT_POLICY_KEY") from None
    require(0 < len(key) <= 65536 and hashlib.sha256(key).hexdigest() == recipient["sha256"] and
            key.startswith(b"-----BEGIN PGP PUBLIC KEY BLOCK-----\n") and
            key.rstrip(b"\n").endswith(b"-----END PGP PUBLIC KEY BLOCK-----") and b"PRIVATE KEY" not in key,
            "RECIPIENT_POLICY_KEY")
    # Packet allowlist, actual full fingerprint, encryption capability, expiry,
    # and no-secret-key checks remain mandatory in the native GPG backend.
    return value, key


def _admit(profile, env, event_raw, git, now):
    """Pure decision seam; tests supply synthetic events and a modeled Git view."""
    require(profile in PROFILES, "IDENTITY_PROFILE")
    workflow, job, scopes = PROFILES[profile]
    require(env.get("GITHUB_ACTIONS") == "true" and env.get("GITHUB_REPOSITORY") == REPOSITORY and
            env.get("GITHUB_SERVER_URL") == "https://github.com" and
            env.get("GITHUB_API_URL") == "https://api.github.com" and
            env.get("RUNNER_ENVIRONMENT") == "github-hosted" and env.get("GITHUB_JOB") == job,
            "IDENTITY_HOSTED_CALLER")
    host = (env.get("RUNNER_OS"), env.get("RUNNER_ARCH"))
    require(host in {("Linux", "X64"), ("Windows", "X64"), ("macOS", "ARM64"), ("macOS", "X64")} and
            (profile != "full" or host[0] == "macOS"), "IDENTITY_HOST_LABELS")
    for name in ("GITHUB_RUN_ID", "GITHUB_RUN_ATTEMPT"):
        require(type(env.get(name)) is str and ID.fullmatch(env[name]), "IDENTITY_RUN")
    event_name, ref = env.get("GITHUB_EVENT_NAME"), env.get("GITHUB_REF")
    require(event_name in {"push", "pull_request", "schedule", "workflow_dispatch"}, "IDENTITY_EVENT")
    require(type(ref) is str and 0 < len(ref) <= 256 and
            not any(ord(char) < 32 or ord(char) == 127 for char in ref), "IDENTITY_REF")
    source = sha(env.get("GITHUB_SHA"))
    require(env.get("GITHUB_WORKFLOW_SHA") == source and
            env.get("GITHUB_WORKFLOW_REF") == REPOSITORY + "/" + workflow + "@" + ref,
            "IDENTITY_WORKFLOW")
    require(git.root_matches() and git.clean() and git.commit("HEAD") == source, "IDENTITY_SOURCE")
    tree = git.tree(source)
    event = parse(event_raw, EVENT_LIMIT)
    repo = mapping(event.get("repository"))
    require(repo.get("full_name") == REPOSITORY and repo.get("default_branch") == "main", "IDENTITY_REPOSITORY")
    detail = {}
    sample_required = False
    if event_name == "pull_request":
        pr = mapping(event.get("pull_request"))
        number = event.get("number")
        require(type(number) is int and 0 < number <= 10 ** 10 and type(pr.get("number")) is int and
                pr["number"] == number and
                ref == f"refs/pull/{number}/merge" and pr.get("state") == "open" and pr.get("merged") is False and
                event.get("action") in {"opened", "reopened", "synchronize"}, "IDENTITY_PR")
        base, head = mapping(pr.get("base")), mapping(pr.get("head"))
        require(mapping(base.get("repo")).get("full_name") == REPOSITORY and base.get("ref") == "main",
                "IDENTITY_PR_BASE")
        head_repo = mapping(head.get("repo")).get("full_name")
        require(type(head_repo) is str and re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", head_repo),
                "IDENTITY_PR_HEAD")
        base_sha, head_sha = sha(base.get("sha")), sha(head.get("sha"))
        require(git.parents(source) == [base_sha, head_sha], "IDENTITY_PR_PARENTS")
        policy_commit = base_sha
        detail = {"number": number, "base": base_sha, "head": head_sha, "headRepository": head_repo}
    elif event_name == "push":
        require(ref == event.get("ref") == "refs/heads/main" and event.get("after") == source and
                event.get("deleted") is False, "IDENTITY_PUSH")
        detail = {"before": sha(event.get("before"))}
        if profile == "desktop":
            # Only the actual admitted main merge commit can request Release
            # packaging. PR text, earlier commits and manual inputs do not count.
            message, parents = git.message(source), git.parents(source)
            require(type(message) is bytes and len(message) <= MESSAGE_LIMIT, "IDENTITY_COMMIT_MESSAGE")
            sample_required = len(parents) == 2 and RELEASE_MARKER in message
            detail.update(releaseMessageSha256=hashlib.sha256(message).hexdigest(), releaseParents=parents)
        policy_commit = source
    elif event_name == "schedule":
        require(profile == "full" and ref == "refs/heads/main" and event.get("schedule") == "17 4 * * 1",
                "IDENTITY_SCHEDULE")
        policy_commit = source
        detail = {"schedule": event["schedule"]}
    else:
        require(ref.startswith("refs/heads/") and ref != "refs/heads/audit/complete-2026-09-04" and
                event.get("ref") in (ref, ref.removeprefix("refs/heads/")), "IDENTITY_MANUAL_REF")
        inputs = event.get("inputs")
        # Both ordinary workflows are input-free. The former campaign's
        # preview/lock/key fields cannot authorize or alter ordinary custody,
        # even when their submitted values are empty.
        require(inputs is None or inputs == {}, "IDENTITY_MANUAL_INPUTS")
        # Fresh full-history checkout supplies origin/main; never policy from
        # arbitrary manual candidate bytes or the lock-only public-key input.
        policy_commit = git.commit("refs/remotes/origin/main")
        detail = {"policyMain": policy_commit}
    blob, policy_raw = git.policy(policy_commit)
    policy, key = _policy(policy_raw, now)
    require(git.root_matches() and git.clean() and git.commit("HEAD") == source and git.tree(source) == tree,
            "IDENTITY_SOURCE_CHANGED")
    recipient = policy["recipient"]
    record = {
        "schema": 1, "scope": "ORDINARY_HOSTED_TEST_CUSTODY_IDENTITY", "profile": profile, "suites": list(scopes),
        "source": {"commit": source, "tree": tree},
        "github": {"repository": REPOSITORY, "event": event_name, "ref": ref, "workflow": workflow,
                   "workflowSha": source, "job": job, "runId": env["GITHUB_RUN_ID"],
                   "runAttempt": env["GITHUB_RUN_ATTEMPT"], "eventSha256": hashlib.sha256(event_raw).hexdigest(),
                   "eventBinding": detail, "runnerOS": host[0], "runnerArch": host[1]},
        "policy": {"commit": policy_commit, "blob": blob, "path": POLICY_PATH,
                   "sha256": hashlib.sha256(policy_raw).hexdigest(), "fingerprint": recipient["fingerprint"],
                   "keySha256": recipient["sha256"], "expiresAt": policy["expiresAt"], "retentionDays": 14},
    }
    if profile == "desktop":
        record["samplePackagingRequired"] = sample_required
    return Admission(encoded(record), event_raw, policy_raw, key, recipient["fingerprint"],
                     recipient["sha256"], policy["expiresAt"])


def sample_packaging_required(admitted):
    """Read the source-derived decision, not an environment/caller override.

    The controller and each post-return guard must still re-admit the original
    Admission. This accessor is not independent source or publication approval.
    """
    require(type(admitted) is Admission, "IDENTITY_ADMISSION_REQUIRED")
    record = parse(admitted.record, EVENT_LIMIT)
    require(record.get("profile") in PROFILES, "IDENTITY_PROFILE")
    if record["profile"] == "full":
        require("samplePackagingRequired" not in record, "IDENTITY_SAMPLE_INTENT")
        return False
    required = record.get("samplePackagingRequired")
    require(type(required) is bool, "IDENTITY_SAMPLE_INTENT")
    return required


def admit(profile, root, *, query_runner, expected=None):
    """Read actual Actions/Git inputs and reject changed admission on reseal.

    No environment substitution is performed. Native host/ownership admission,
    recipient encryption validation, original-byte retention and empty execution
    scopes are separate required controller responsibilities.
    """
    env = dict(os.environ)
    root = Path(root)
    try:
        require(root.is_absolute() and root == root.resolve(strict=True) and
                env.get("GITHUB_WORKSPACE") == str(root), "IDENTITY_WORKSPACE")
    except OSError:
        raise AdmissionError("IDENTITY_WORKSPACE") from None
    raw = read_regular(Path(env.get("GITHUB_EVENT_PATH", "")), EVENT_LIMIT)
    result = _admit(profile, env, raw, GitView(root, env, query_runner), int(time.time()))
    if expected is not None:
        require(type(expected) is Admission and result == expected, "IDENTITY_CHANGED_BEFORE_SEAL")
    return result
