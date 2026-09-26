"""Dormant, data-only configuration-producer argv; NOT a launcher or admission.

Join the existing strict producer request to the source-bound canonical loader.
No environment, owner, clock, state/home, process or producer outcome is created.
The proposed flags cannot enforce original phase anchors or attest retirement;
a future source-owned parent must independently fence and own actual execution.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path, PurePosixPath, PureWindowsPath
import sys

import hosted_cache_bootstrap_allocation as allocation
import hosted_cache_bootstrap_canonical as canonical
import hosted_cache_bootstrap_producer as producer


SCRIPTS = Path(__file__).resolve().parent
ROOT = SCRIPTS.parent
SCOPE = "BOOTSTRAP_CANONICAL_PRODUCER_COMMAND_REQUEST_ONLY_V1"
INITIAL_SCOPE = "INITIAL_RECIPIENT_CANONICAL_PRODUCER_COMMAND_REQUEST_ONLY_V1"
_PHASES = (("producer-work", 600), ("producer-return", 225),
           ("producer-final", 45), ("producer-read", 30))


class CommandError(RuntimeError):
    """Finite source/descriptor refusal, not private path or execution evidence."""


def require(value, code):
    if not value:
        raise CommandError(code)


def _proposal():
    """Check the existing closed counterpart; do not derive or admit a budget."""
    fixed = allocation.policy()
    phases = [{"name": name, "maximumSeconds": seconds} for name, seconds in _PHASES]
    selected = [row for row in fixed["phases"] if row["name"] in dict(_PHASES)]
    captures = [row for row in fixed["nativeCaptureSpans"] if row["name"] == "producer"]
    expected_return = {"seconds": 225, "sameHomeStopSeconds": 120, "sameHomeStopIncluded": True,
                       "scope": "STOP_AND_CANONICAL_TAIL_SHARE_ORIGINAL_RETURN_CAP"}
    expected_capture = [{"name": "producer", "phases": [name for name, _ in _PHASES[:3]],
                         "maximumSeconds": 870}]
    # Canonical JSON comparison distinguishes booleans from numeric counterparts.
    require(producer.encoded(selected) == producer.encoded(phases) and
            producer.encoded(captures) == producer.encoded(expected_capture) and
            producer.encoded(fixed["producerReturn"]) == producer.encoded(expected_return) and
            type(fixed["proposedJobSeconds"]) is int and fixed["proposedJobSeconds"] == 5400 and
            type(fixed["windowsNativeFileSeconds"]) is int and fixed["windowsNativeFileSeconds"] == 900 and
            fixed["nativeCaptureScope"] == "ORIGINAL_FIRST_WORK_ANCHOR_INCLUDING_IDLE_GAPS_NOT_PER_CALL_RENEWAL",
            "BOOTSTRAP_PRODUCER_COMMAND_ALLOCATION_CHANGED")
    start = fixed["phases"].index(selected[0])
    require(fixed["phases"][start:start + len(phases)] == selected,
            "BOOTSTRAP_PRODUCER_COMMAND_ALLOCATION_CHANGED")
    return {"scope": "FIXED_SOURCE_PROPOSAL_NOT_LIVE_DEADLINES", "phases": phases,
            "producerReturn": expected_return, "nativeCapture": expected_capture[0],
            "windowsNativeFileSeconds": 900, "proposedJobSeconds": 5400,
            "deadlineEnforcement": "NOT_PERFORMED_HERE_OR_BY_FLAGS_ALONE",
            "parentObligation": "SHORTEN_AGAINST_ORIGINAL_SHARED_CLOCK_JOB_PHASE_AND_CAPTURE_FENCES"}


def command_request(admitted_raw, canonical_raw, *, invocation, ancestor_invocations):
    """Return private canonical JSON, never a directly launch-admitted request.

    Immutable originals are supplied data, not authenticated custody. Existing
    producer validation owns cohort/context/invocation/ancestry and detaches the
    request before any source supplier. Repeated calls grant no single-use right.
    """
    location = _request_inputs(admitted_raw, canonical_raw)
    request = producer.make_request(admitted_raw, canonical_raw, invocation=invocation,
                                    ancestor_invocations=ancestor_invocations)
    return _command_fields(admitted_raw, canonical_raw, request, SCOPE, location)


def initial_recipient_command_request(worker_raw, canonical_raw, *, invocation, ancestor_invocations):
    """Fixed initial-origin sibling; the descriptor remains DATA, never a launch."""
    location = _request_inputs(worker_raw, canonical_raw)
    request = producer.make_initial_recipient_request(worker_raw, canonical_raw, invocation=invocation,
                                                      ancestor_invocations=ancestor_invocations)
    return _command_fields(worker_raw, canonical_raw, request, INITIAL_SCOPE, location)


def _request_inputs(admitted_raw, canonical_raw):
    require(sys.flags.isolated == 1 and sys.flags.no_site == 1 and sys.dont_write_bytecode,
            "BOOTSTRAP_PRODUCER_COMMAND_ISOLATION")
    require(type(admitted_raw) is bytes and type(canonical_raw) is bytes,
            "BOOTSTRAP_PRODUCER_COMMAND_ORIGINAL_BYTES")
    root, scripts = ROOT, SCRIPTS
    require(isinstance(root, Path) and isinstance(scripts, Path) and root.is_absolute() and
            ".." not in root.parts and scripts == root / "scripts" and
            canonical.ROOT == root and canonical.SCRIPTS == scripts,
            "BOOTSTRAP_PRODUCER_COMMAND_LOCATION")
    return root, scripts


def _command_fields(admitted_raw, canonical_raw, request, scope, location):
    root, scripts = location  # Original pre-request snapshot, including the legacy route.
    request_raw = producer.encoded(request)
    ancestors = tuple(request["ancestorInvocationIds"])
    path = PureWindowsPath if request["host"] == "windows-x64" else PurePosixPath
    state = path(request["gradleHome"]).parent
    wrapper = root / ("gradlew.bat" if request["host"] == "windows-x64" else "gradlew")
    require(request["cwd"] == str(root) and request["wrapper"] == str(wrapper),
            "BOOTSTRAP_PRODUCER_COMMAND_SOURCE_ROOT")
    proposal = _proposal()
    helper_hash, helper_limit = canonical._CANONICAL_HELPER_SHA256, canonical._CANONICAL_HELPER_LIMIT
    interpreter = canonical._interpreter()
    helper = canonical._load_canonical_helper()
    originals = {name: canonical._canonical_source(name, helper["CANONICAL_SOURCE_LIMIT"])
                 for name in helper["CANONICAL_NAMES"]}
    bindings = {name: hashlib.sha256(raw).hexdigest() for name, raw in originals.items()}
    bindings_json = json.dumps(bindings, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)
    argv = helper["assemble"](interpreter[1], str(scripts), bindings_json,
        "--cwd", str(root), "--wrapper", str(wrapper), "--purpose", request["purpose"],
        "--kind", "gradle", "--id", request["id"], "--timeout", "600", "--stop-timeout", "120",
        "--", *request["requestedArgv"])
    # Existing readers own their handles and preserve first failures. No catch,
    # recovery/fallback supplier, canonical execution or state read occurs here.
    for name, raw in originals.items():
        require(canonical._canonical_source(name, helper["CANONICAL_SOURCE_LIMIT"]) == raw,
                "BOOTSTRAP_PRODUCER_COMMAND_SOURCE_CHANGED")
    require(hashlib.sha256(canonical._canonical_source("hosted_canonical_python.py", helper_limit)).hexdigest() ==
            helper_hash and canonical._CANONICAL_HELPER_SHA256 == helper_hash and
            canonical._CANONICAL_HELPER_LIMIT == helper_limit and canonical._interpreter() == interpreter,
            "BOOTSTRAP_PRODUCER_COMMAND_BINDING_CHANGED")
    require(ROOT == root and SCRIPTS == scripts and canonical.ROOT == root and canonical.SCRIPTS == scripts,
            "BOOTSTRAP_PRODUCER_COMMAND_LOCATION_CHANGED")
    return producer.encoded({"schema": 1, "scope": scope,
        "requestBytes": request_raw.decode("ascii"), "requestSha256": producer.digest(request_raw),
        "admissionSha256": producer.digest(admitted_raw), "canonicalContextSha256": producer.digest(canonical_raw),
        "root": str(root), "state": str(state), "gradleHome": request["gradleHome"],
        "ancestorInvocationIds": list(ancestors), "role": request["host"], "python": interpreter[1],
        "interpreterObservation": "CURRENT_PATH_AND_METADATA_NOT_EXECUTABLE_BYTE_AUTHENTICATION",
        "helperSourceSha256": helper_hash, "canonicalSources": bindings, "argv": argv,
        "timingProposal": proposal, "environment": "NOT_BUILT_OR_ADMITTED",
        "sourceAdmission": "NOT_ATTESTED_HERE", "hostAdmission": "NOT_ATTESTED_HERE",
        "stateOwnership": "NOT_ACQUIRED_OR_ATTESTED", "recipientAuthority": "NOT_ATTESTED_HERE",
        "originalDomainChain": "NOT_OBSERVED_HERE", "producerStopRetirement": "NOT_OBSERVED_HERE",
        "custodyAcceptance": "NOT_OBSERVED_HERE", "nextPhaseAuthority": False,
        "budgetAcceptance": "NOT_ADMITTED", "testAcceptance": "NOT_PERFORMED", "exportSaveAuthority": False})
