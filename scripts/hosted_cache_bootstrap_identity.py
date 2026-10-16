"""Separate, dormant manual identity for a configuration-only cache producer.

No CLI, workflow, cache provider, producer, downloader or local-host fallback.
The real entry requires the existing native-owned Git query interface; the pure
decision seam does not attest that supplied events came from GitHub. Admission
is not a successful build, test, cache population or authority to lift a HOLD.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import time

import hosted_test_identity as ordinary


PROFILE = "cache-bootstrap"
SCOPE = "CACHE_BOOTSTRAP_HOSTED_IDENTITY_V1"
WORKFLOW = ".github/workflows/dependency-cache-bootstrap.yml"
JOB = "populate"
# A closed byte-reuse cohort is not the execution profile. In particular, a
# FULL cohort never creates ordinary FULL's simulator/ABI/transcript authority.
SELECTIONS = (
    ("desktop-linux-x64", "desktop", "linux-x64", "Linux", "X64"),
    ("desktop-windows-x64", "desktop", "windows-x64", "Windows", "X64"),
    ("desktop-macos-arm64", "desktop", "macos-arm64", "macOS", "ARM64"),
    ("desktop-macos-x64", "desktop", "macos-x64", "macOS", "X64"),
    ("full-macos-arm64", "full", "macos-arm64", "macOS", "ARM64"),
    ("full-macos-x64", "full", "macos-x64", "macOS", "X64"),
)
INPUTS = frozenset(("selection", "expected_sha", "expected_tree"))
COMMAND = ("help", "--console=plain", "--no-configure-on-demand")
PRODUCER_SCOPE = "CONFIGURATION_ONLY_NOT_COMPLETE_DEPENDENCIES_OR_TESTS"
CACHE_FIELDS = frozenset(("selection", "cacheCohort", "producerCommand", "producerScope", "testAcceptance"))


def require(value, code):
    ordinary.require(value, code)


def selection(value):
    require(type(value) is str, "BOOTSTRAP_SELECTION")
    for name, profile, role, system, architecture in SELECTIONS:
        if value == name:
            return profile, role, system, architecture
    raise ordinary.AdmissionError("BOOTSTRAP_SELECTION")


def cache_cohort(admitted_raw):
    """Route retained declarations, not a new admission or producer authority.

    None preserves the existing ordinary/model helper contract. Bootstrap-only
    fields cannot fall through that branch when its scope/profile is removed or
    relabelled. Original-byte custody and real source/policy re-admission remain
    mandatory in a future caller; a supplied record cannot authenticate itself.
    """
    value = ordinary.parse(admitted_raw, ordinary.EVENT_LIMIT)
    github = value.get("github")
    binding = github.get("eventBinding") if type(github) is dict else None
    nested = type(github) is dict and (github.get("workflow") == WORKFLOW or github.get("job") == JOB or
        type(binding) is dict and {"selection", "expectedCommit", "expectedTree"}.intersection(binding))
    if not (value.get("scope") == SCOPE or value.get("profile") == PROFILE or
            CACHE_FIELDS.intersection(value) or nested):
        require("scope" not in value or value["scope"] == "ORDINARY_HOSTED_TEST_CUSTODY_IDENTITY",
                "BOOTSTRAP_OR_ORDINARY_SCOPE")
        return None
    require(set(value) == {"schema", "scope", "profile", "source", "github", "policy"} | CACHE_FIELDS and
            type(value["schema"]) is int and value["schema"] == 1 and
            value["scope"] == SCOPE and value["profile"] == PROFILE, "BOOTSTRAP_CACHE_IDENTITY")
    profile, role, system, architecture = selection(value["selection"])
    require(value["cacheCohort"] == {"profile": profile, "role": role} and
            value["producerCommand"] == list(COMMAND) and value["producerScope"] == PRODUCER_SCOPE and
            value["testAcceptance"] == "NOT_PERFORMED", "BOOTSTRAP_CACHE_COHORT_OR_EXECUTION_CHANGED")
    source, github, policy = (ordinary.mapping(value[name]) for name in ("source", "github", "policy"))
    require(set(source) == {"commit", "tree"}, "BOOTSTRAP_CACHE_SOURCE")
    commit, tree, main = (ordinary.sha(source["commit"]), ordinary.sha(source["tree"]),
                          ordinary.sha(policy.get("commit")))
    require(github.get("repository") == ordinary.REPOSITORY and github.get("event") == "workflow_dispatch" and
            github.get("workflow") == WORKFLOW and github.get("workflowSha") == commit and github.get("job") == JOB and
            (github.get("runnerOS"), github.get("runnerArch")) == (system, architecture) and
            github.get("eventBinding") == {"policyMain": main, "selection": value["selection"],
                "expectedCommit": commit, "expectedTree": tree}, "BOOTSTRAP_CACHE_HOST_OR_SOURCE_CHANGED")
    require(admitted_raw == ordinary.encoded(value), "BOOTSTRAP_CACHE_ORIGINAL_RECORD_ENCODING")
    return profile, role


def _admit(env, event_raw, git, now):
    """Pure decision seam; modeled inputs remain models, not hosted evidence.

    Read recipient authority only from the original fetched main, never from a
    candidate/key input. The native owner must retain every original query and
    bound the whole operation, not just the existing per-query 15-second cap.
    """
    require(env.get("GITHUB_ACTIONS") == "true" and env.get("GITHUB_REPOSITORY") == ordinary.REPOSITORY and
            env.get("GITHUB_SERVER_URL") == "https://github.com" and
            env.get("GITHUB_API_URL") == "https://api.github.com" and
            env.get("RUNNER_ENVIRONMENT") == "github-hosted" and env.get("GITHUB_JOB") == JOB,
            "BOOTSTRAP_HOSTED_CALLER")
    require(env.get("GITHUB_EVENT_NAME") == "workflow_dispatch", "BOOTSTRAP_MANUAL_ONLY")
    for name in ("GITHUB_RUN_ID", "GITHUB_RUN_ATTEMPT"):
        require(type(env.get(name)) is str and ordinary.ID.fullmatch(env[name]), "BOOTSTRAP_RUN")
    ref = env.get("GITHUB_REF")
    require(type(ref) is str and ref.startswith("refs/heads/") and len("refs/heads/") < len(ref) <= 256 and
            ref != "refs/heads/audit/complete-2026-09-04" and
            not any(ord(char) < 32 or ord(char) == 127 for char in ref), "BOOTSTRAP_REF")
    source = ordinary.sha(env.get("GITHUB_SHA"))
    require(env.get("GITHUB_WORKFLOW_SHA") == source and
            env.get("GITHUB_WORKFLOW_REF") == ordinary.REPOSITORY + "/" + WORKFLOW + "@" + ref,
            "BOOTSTRAP_WORKFLOW")
    event = ordinary.parse(event_raw, ordinary.EVENT_LIMIT)
    repository = ordinary.mapping(event.get("repository"))
    require(repository.get("full_name") == ordinary.REPOSITORY and repository.get("default_branch") == "main",
            "BOOTSTRAP_REPOSITORY")
    require(event.get("ref") in (ref, ref.removeprefix("refs/heads/")), "BOOTSTRAP_EVENT_REF")
    inputs = event.get("inputs")
    require(type(inputs) is dict and set(inputs) == INPUTS, "BOOTSTRAP_INPUTS")
    cohort, role, system, architecture = selection(inputs["selection"])
    require((env.get("RUNNER_OS"), env.get("RUNNER_ARCH")) == (system, architecture),
            "BOOTSTRAP_HOST_LABELS")
    require(ordinary.sha(inputs["expected_sha"]) == source, "BOOTSTRAP_EXPECTED_SOURCE")
    expected_tree = ordinary.sha(inputs["expected_tree"])
    require(git.root_matches() and git.clean() and git.commit("HEAD") == source, "BOOTSTRAP_SOURCE")
    tree = git.tree(source)
    require(tree == expected_tree, "BOOTSTRAP_EXPECTED_TREE")
    require(git.query("rev-parse", "--is-shallow-repository").strip() == b"false", "BOOTSTRAP_FULL_HISTORY")
    # Source labels/input SHAs are bindings, not independent-review attestations.
    policy_commit = git.commit("refs/remotes/origin/main")
    ordinary.sha(policy_commit)
    require(git.query("merge-base", policy_commit, source).strip() == policy_commit.encode("ascii"),
            "BOOTSTRAP_MAIN_ANCESTRY")
    blob, policy_raw = git.policy(policy_commit)
    policy, key = ordinary._policy(policy_raw, now)
    require(git.root_matches() and git.clean() and git.commit("HEAD") == source and git.tree(source) == tree and
            git.commit("refs/remotes/origin/main") == policy_commit, "BOOTSTRAP_SOURCE_OR_MAIN_CHANGED")
    recipient = policy["recipient"]
    record = {
        "schema": 1, "scope": SCOPE, "profile": PROFILE, "selection": inputs["selection"],
        "cacheCohort": {"profile": cohort, "role": role}, "producerCommand": list(COMMAND),
        "producerScope": PRODUCER_SCOPE, "testAcceptance": "NOT_PERFORMED",
        "source": {"commit": source, "tree": tree},
        "github": {"repository": ordinary.REPOSITORY, "event": "workflow_dispatch", "ref": ref,
                   "workflow": WORKFLOW, "workflowSha": source, "job": JOB,
                   "runId": env["GITHUB_RUN_ID"], "runAttempt": env["GITHUB_RUN_ATTEMPT"],
                   "eventSha256": hashlib.sha256(event_raw).hexdigest(),
                   "eventBinding": {"policyMain": policy_commit, "selection": inputs["selection"],
                                    "expectedCommit": source, "expectedTree": tree},
                   "runnerOS": system, "runnerArch": architecture},
        "policy": {"commit": policy_commit, "blob": blob, "path": ordinary.POLICY_PATH,
                   "sha256": hashlib.sha256(policy_raw).hexdigest(), "fingerprint": recipient["fingerprint"],
                   "keySha256": recipient["sha256"], "expiresAt": policy["expiresAt"], "retentionDays": 14},
    }
    return ordinary.Admission(ordinary.encoded(record), event_raw, policy_raw, key, recipient["fingerprint"],
                              recipient["sha256"], policy["expiresAt"])


def admit(root, *, query_runner, expected=None):
    """Read actual original inputs through the existing owned query boundary.

    No injected environment, source fetch or candidate recipient override.
    Native host/clock/toolchain admission, GPG validation, bounded producer and
    retirement, frozen-byte/provider custody and a separate seal remain missing
    controller obligations. This function is deliberately not workflow-wired.
    """
    env = dict(os.environ)
    root = Path(root)
    try:
        require(root.is_absolute() and root == root.resolve(strict=True) and
                env.get("GITHUB_WORKSPACE") == str(root), "BOOTSTRAP_WORKSPACE")
    except OSError:
        raise ordinary.AdmissionError("BOOTSTRAP_WORKSPACE") from None
    raw = ordinary.read_regular(Path(env.get("GITHUB_EVENT_PATH", "")), ordinary.EVENT_LIMIT)
    result = _admit(env, raw, ordinary.GitView(root, env, query_runner), int(time.time()))
    if expected is not None:
        require(type(expected) is ordinary.Admission and result == expected, "BOOTSTRAP_CHANGED_BEFORE_SEAL")
    return result
