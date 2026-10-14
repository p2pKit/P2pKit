"""Pure, closed admission rules for a future ordinary-CI Apple context adapter.

These rules do not launch Terminal, authenticate GitHub metadata, inspect Git,
allocate an audit session, or prove native ownership/cleanup. The future caller
must independently acquire the exact GitHub event/run and checkout observations.
Old feature-push admission/proofs are deliberately neither imported nor expanded.
"""
from __future__ import annotations

import copy
import math
from pathlib import PurePosixPath
import re


SCOPE = "ORDINARY_CI_APPLE_CONTEXT_ADMISSION_NOT_NATIVE_OR_RELEASE_QUALIFICATION"
REPOSITORY = "p2pKit/P2pKit"
SCHEMA = 1
JOB_SECONDS = 60 * 60
CLOCK_UNCERTAINTY_SECONDS = 1.0
SHELL_QUIT_SECONDS = 30
PROFILES = ("platform-full", "consumers-complete")
EVENTS = ("pull_request", "push", "workflow_dispatch", "schedule")
BINDING_KEYS = {
    "schema", "scope", "repository", "event", "ref", "runId", "runAttempt", "profile",
    "source", "ciScope", "pr", "root", "python", "argv",
}
CLOCK_KEYS = {
    "jobStartedWall", "observedWall", "observedMonotonic", "nowWall", "nowMonotonic",
    "observedBootSession", "nowBootSession",
}
BOOT_KEYS = {"observedBootSession", "nowBootSession"}
RUN_KEYS = {"repository", "event", "ref", "runId", "runAttempt", "sha", "profile"}


def require(condition: bool, reason: str) -> None:
    if not condition:
        raise ValueError(reason)


def exact_keys(value: object, expected: set[str], label: str) -> None:
    require(type(value) is dict and set(value) == expected, "Invalid closed " + label)


def positive_integer(value: object, maximum: int, label: str) -> None:
    require(type(value) is int and 0 < value <= maximum, "Invalid " + label)


def oid(value: object) -> bool:
    return (type(value) is str and re.fullmatch(r"(?:[0-9a-f]{40}|[0-9a-f]{64})", value) is not None
            and set(value) != {"0"})


def absolute_path(value: object, label: str) -> str:
    require(type(value) is str and value.startswith("/") and value != "/" and
            not any(ord(character) < 32 or ord(character) == 127 for character in value),
            "Invalid absolute " + label)
    path = PurePosixPath(value)
    require(str(path) == value and path.anchor == "/" and ".." not in path.parts,
            "Noncanonical " + label)
    return value


def command_for(profile: str, root: str, python: str) -> list[str]:
    """Return only the original complete command, without shell-fragment parsing.

    Paths are checked lexically only. Physical ownership/symlink/tool validation
    remains a runtime-adapter obligation and cannot be inferred from this result.
    """
    require(type(profile) is str and profile in PROFILES, "Unknown complete CI profile")
    root = absolute_path(root, "checkout root")
    python = absolute_path(python, "Python executable")
    if profile == "platform-full":
        return [python, root + "/scripts/run-platform-tests.py", "full"]
    return ["/bin/bash", root + "/scripts/check-published-consumers.sh"]


def branch_ref(value: object) -> bool:
    if type(value) is not str or not value.startswith("refs/heads/"):
        return False
    name = value.removeprefix("refs/heads/")
    return (0 < len(name) <= 255 and re.fullmatch(r"[A-Za-z0-9_./-]+", name) is not None and
            ".." not in name and not name.endswith(".") and
            all(part and not part.startswith(".") and not part.endswith(".lock") for part in name.split("/")))


def admit_context(binding: dict, checkout: dict, observed_run: dict) -> dict:
    """Validate separately supplied event binding and clean checkout observations.

    `source.commit` is the event's actual github.sha, not a separately advertised
    PR head. `checkout.parents` is its real ordered Git parent list. `ciScope`
    comes from the maintained resolver; only its full execution path enters this
    adapter. `observed_run` separately binds the current authenticated run/event
    facts and workflow-selected profile, rather than trusting a saved binding's
    run/attempt labels. This validator does not authenticate caller-supplied facts.
    """
    exact_keys(binding, BINDING_KEYS, "CI binding")
    require(type(binding["schema"]) is int and binding["schema"] == SCHEMA and binding["scope"] == SCOPE,
            "Wrong ordinary-CI schema/scope")
    require(binding["repository"] == REPOSITORY, "Wrong repository")
    require(type(binding["event"]) is str and binding["event"] in EVENTS, "Unsupported CI event")
    positive_integer(binding["runId"], 2**63 - 1, "run identity")
    positive_integer(binding["runAttempt"], 2**31 - 1, "run attempt")
    exact_keys(binding["source"], {"commit", "tree"}, "source")
    commit, tree = binding["source"]["commit"], binding["source"]["tree"]
    require(oid(commit) and oid(tree) and len(commit) == len(tree), "Invalid exact source identity")
    exact_keys(observed_run, RUN_KEYS, "current run observation")
    expected_run = {key: binding[key] for key in RUN_KEYS - {"sha"}}
    expected_run["sha"] = commit
    require(all(type(observed_run[key]) is type(expected_run[key]) and observed_run[key] == expected_run[key]
                for key in RUN_KEYS), "Current run/event/attempt/profile differs from the saved binding")
    exact_keys(checkout, {"commit", "tree", "parents", "status"}, "checkout observation")
    require(checkout["commit"] == commit and checkout["tree"] == tree and checkout["status"] == "",
            "Actual checkout is not the bound clean source/tree")
    parents = checkout["parents"]
    require(type(parents) is list and len(parents) <= 256 and
            all(oid(parent) and len(parent) == len(commit) for parent in parents), "Invalid Git parent inventory")
    exact_keys(binding["ciScope"], {"full", "head"}, "resolved scope")
    require(binding["ciScope"]["full"] is True and binding["ciScope"]["head"] == commit,
            "Complete same-source resolver scope required")

    if binding["event"] == "pull_request":
        exact_keys(binding["pr"], {"number", "base", "head"}, "PR event")
        pr = binding["pr"]
        positive_integer(pr["number"], 2**63 - 1, "PR number")
        require(binding["ref"] == f'refs/pull/{pr["number"]}/merge', "Actual PR merge ref required")
        require(oid(pr["base"]) and oid(pr["head"]) and parents == [pr["base"], pr["head"]],
                "PR synthetic merge must have exactly the event's ordered base/head parents")
        require(commit not in parents, "PR branch head cannot substitute for its synthetic merge")
    else:
        require(binding["pr"] is None, "PR metadata is not admitted for another event")
        require(branch_ref(binding["ref"]), "Canonical branch ref required")
        if binding["event"] in ("push", "schedule"):
            require(binding["ref"] == "refs/heads/main", "Main push/default-branch schedule required")

    require(type(binding["argv"]) is list and
            binding["argv"] == command_for(binding["profile"], binding["root"], binding["python"]),
            "Only the fixed original complete command is admitted")
    return copy.deepcopy(binding)


def finite_number(value: object, label: str, *, positive: bool = False) -> float:
    require(type(value) in (int, float), "Non-numeric " + label)
    try:
        result = float(value)
    except (OverflowError, ValueError):
        raise ValueError("Unrepresentable " + label) from None
    require(math.isfinite(result) and (result > 0 if positive else result >= 0), "Invalid finite " + label)
    return result


def plan_envelope(clock: dict, *, product_seconds: float, finalization_seconds: float,
                  enclosing_cutoff: float) -> dict:
    """Allocate within the original job, not a fresh lease after setup.

    `jobStartedWall` must come from the exact current job/run/attempt metadata.
    The observed wall/monotonic pair is retained, not refreshed to renew a lease.
    The same observed/current kernel boot-session UUID is required; monotonic
    values alone cannot establish continuity across a reboot. One second is
    conservatively charged for timestamp precision/clock agreement.
    `finalization_seconds` MUST already include the independently reviewed entire
    executor/stop/evidence/guardian budget, including the original 30-second shared
    shell/Quit phase. This function enforces that minimum but cannot establish a
    sufficient native finalization contract or guarantee survival of GHA tree kill.
    """
    exact_keys(clock, CLOCK_KEYS, "clock observation")
    for key in BOOT_KEYS:
        require(type(clock[key]) is str and re.fullmatch(
            r"[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}", clock[key]) is not None and
            set(clock[key].replace("-", "")) != {"0"}, "Invalid boot-session observation")
    require(clock["observedBootSession"].lower() == clock["nowBootSession"].lower(),
            "Boot session changed after clock binding")
    values = {key: finite_number(value, key) for key, value in clock.items() if key not in BOOT_KEYS}
    product = finite_number(product_seconds, "product interval", positive=True)
    finalization = finite_number(finalization_seconds, "finalization interval", positive=True)
    enclosing = finite_number(enclosing_cutoff, "enclosing cutoff", positive=True)
    require(finalization >= SHELL_QUIT_SECONDS, "Original shell/Quit interval cannot be omitted")
    started = values["jobStartedWall"]
    wall, monotonic = values["observedWall"], values["observedMonotonic"]
    now_wall, now = values["nowWall"], values["nowMonotonic"]
    require(started <= wall <= now_wall and monotonic <= now, "Clock reversal/future job start refused")
    wall_delta, monotonic_delta = now_wall - wall, now - monotonic
    require(abs(wall_delta - monotonic_delta) <= CLOCK_UNCERTAINTY_SECONDS,
            "Observed wall and monotonic clocks disagree")
    elapsed = max(now_wall - started, wall - started + monotonic_delta) + CLOCK_UNCERTAINTY_SECONDS
    require(math.isfinite(elapsed) and elapsed < JOB_SECONDS, "Original CI job allowance exhausted")
    # Taking the earlier clock mapping prevents a wall-clock lag from renewing
    # the retained monotonic deadline. nextafter rounds toward earlier refusal.
    job_cutoff = math.nextafter(now + (JOB_SECONDS - elapsed), -math.inf)
    cutoff = min(job_cutoff, enclosing)
    latest_product_end = math.nextafter(cutoff - finalization, -math.inf)
    proposed_product_end = now + product
    require(all(math.isfinite(value) for value in (job_cutoff, cutoff, latest_product_end, proposed_product_end)) and
            now < proposed_product_end <= latest_product_end < cutoff and proposed_product_end - now >= product,
            "Insufficient representable remaining time for product and complete finalization")
    return {"scope": SCOPE, "jobSeconds": JOB_SECONDS, "elapsedSetupSeconds": elapsed,
            "jobCutoffMonotonic": job_cutoff, "enclosingCutoffMonotonic": cutoff,
            "productCutoffMonotonic": proposed_product_end, "finalizationSeconds": finalization,
            "nativeExecutionAuthorized": False, "cleanupVerified": False}
