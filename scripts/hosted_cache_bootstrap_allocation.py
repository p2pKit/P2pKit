"""Pure bootstrap allocation PROPOSAL and supplied-trace consistency only.

No clock/file reader, workflow, native owner or execution authority. The dormant
internal old-owner-close bridge consumes this proposal, not a productive caller.
The proposed 5400s is UNADMITTED / UNMEASURED. A complete roster or consistent
supplied trace is not scheduling fit, original outcome custody or single use.
In particular this cannot prolong/reconstitute the read-only OriginalEntry.
"""
from __future__ import annotations

import hosted_cache_bootstrap_service_time as service_time


origin = service_time.origin
NS = origin.NS
SCOPE = "BOOTSTRAP_ALLOCATION_SOURCE_PROPOSAL_V1"
TRACE_SCOPE = "BOOTSTRAP_SUPPLIED_ALLOCATION_TRACE_V1"
OBSERVATION_SCOPE = "BOOTSTRAP_SUPPLIED_PHASE_OBSERVATION_V1"
PROPOSED_JOB_SECONDS = 5400
OBSERVATION_LIMIT = 16384

# Serial proposal caps, NOT source-owned execution windows. Setup before this
# roster is charged through the original service basis, not granted anew.
# Final/read slots are separate from work; every native capture closes before
# its read slot. Provider/transition caps are unmeasured proposals too.
PHASES = (
    ("productive-entry", 120),
    ("recipient-validation", 240), ("recipient-final", 45), ("recipient-read", 30),
    ("canonical-init", 120), ("canonical-init-final", 45), ("canonical-init-read", 30),
    ("dependency-stage", 120), ("empty-seed", 120),
    ("custody-prepare", 120), ("custody-prepare-final", 45), ("custody-prepare-read", 30),
    ("producer-work", 600), ("producer-return", 225), ("producer-final", 45), ("producer-read", 30),
    ("custody-collect", 120), ("custody-collect-final", 45), ("custody-collect-read", 30),
    ("custody-uninstall", 90), ("custody-uninstall-final", 45), ("custody-uninstall-read", 30),
    ("dependency-export", 120), ("save-set-before", 120), ("producer-owner-return", 45),
    ("save-transition", 30), ("provider-save", 180), ("save-readmission", 120),
    ("save-set-after", 120), ("save-observation", 30), ("save-owner-return", 45),
    ("probe-transition", 30), ("provider-probe", 180), ("custody-readmission", 120),
    ("provider-observation", 30), ("custody-freeze", 180),
    ("custody-encrypt", 240), ("custody-encrypt-final", 45), ("custody-encrypt-read", 30),
    ("ciphertext-open", 90), ("ciphertext-verify", 90), ("custody-owner-return", 45),
    ("seal-transition", 30), ("separate-seal", 120), ("upload-transition", 30),
    ("evidence-upload", 180), ("upload-after-guard", 30), ("delivery-return", 45),
)
CAPTURE_GROUPS = (
    ("recipient", ("recipient-validation", "recipient-final")),
    ("initializer", ("canonical-init", "canonical-init-final")),
    ("custody-prepare", ("custody-prepare", "custody-prepare-final")),
    ("producer", ("producer-work", "producer-return", "producer-final")),
    ("custody-collect", ("custody-collect", "custody-collect-final")),
    ("custody-uninstall", ("custody-uninstall", "custody-uninstall-final")),
    ("custody-encrypt", ("custody-encrypt", "custody-encrypt-final")),
)
COPY_PHASES = ("empty-seed", "dependency-export", "save-set-before", "save-set-after")
OBSERVATION_FIELDS = {"schema", "scope", "phase", "clock", "previousSha256", "beganNs", "returnedNs",
                      "lastNewWorkNs", "originalOutcome", "retirement", "cancelled"}


class AllocationError(ValueError):
    """Finite source-owned reason, not a private observation diagnostic."""


def require(value, reason):
    if not value:
        raise AllocationError(reason)


def integer(value):
    require(type(value) is int and 0 <= value <= origin.clocks.UINT64, "BOOTSTRAP_ALLOCATION_INTEGER")
    return value


def policy():
    caps = dict(PHASES)
    return {"scope": "CLOSED_SOURCE_PROPOSAL_NOT_ADMITTED_OR_MEASURED_FIT",
            "proposedJobSeconds": PROPOSED_JOB_SECONDS,
            "phases": [{"name": name, "maximumSeconds": seconds} for name, seconds in PHASES],
            "allocatedSeconds": sum(caps.values()),
            "unallocatedSetupHeadroomSeconds": PROPOSED_JOB_SECONDS - sum(caps.values()),
            "headroomScope": "ARITHMETIC_ONLY_ALREADY_ELAPSED_SETUP_AND_SERVICE_CHARGES_STILL_APPLY",
            "nativeCaptureSpans": [{"name": name, "phases": list(phases),
                "maximumSeconds": sum(caps[phase] for phase in phases)} for name, phases in CAPTURE_GROUPS],
            "nativeCaptureScope": "ORIGINAL_FIRST_WORK_ANCHOR_INCLUDING_IDLE_GAPS_NOT_PER_CALL_RENEWAL",
            "windowsNativeFileSeconds": 900,
            "producerReturn": {"seconds": 225, "sameHomeStopSeconds": 120,
                "sameHomeStopIncluded": True, "scope": "STOP_AND_CANONICAL_TAIL_SHARE_ORIGINAL_RETURN_CAP"},
            "dependencyObservations": {"phases": list(COPY_PHASES), "hardSeconds": 120,
                "newWorkSeconds": 90, "fileBytes": 512 * 1024 * 1024, "aggregateBytes": 2 * 1024 * 1024 * 1024,
                "strategy": "STREAM_PER_FILE_NOT_WINDOWS_AGGREGATE_SNAPSHOT"},
            "originalEntry": "SEPARATE_UNCHANGED_ORIGINAL75_LOCAL45_ORIGINAL120_NOT_EXTENDED",
            "failureCustody": "RESERVED_CUSTODY_CAPS_NOT_A_FAILED_OR_UNKNOWN_OWNER_EXECUTOR",
            "providerScope": "PROPOSED_CAPS_NOT_STORAGE_CONTENTS_OR_RESOLVER_QUALIFICATION"}


def derive(admitted, originals, invocation, clock, runner_name):
    """Rederive the basis; never accept a supplied digest/summary as authority."""
    basis = service_time.derive(admitted, originals, invocation, clock, runner_name)
    fixed = policy()
    total = integer(fixed["allocatedSeconds"])
    require(0 < total < PROPOSED_JOB_SECONDS and len(dict(PHASES)) == len(PHASES),
            "BOOTSTRAP_ALLOCATION_ACCOUNTING")
    end = integer(basis["jobStartBasisNs"] + PROPOSED_JOB_SECONDS * NS)
    start = integer(end - total * NS)
    cursor, fences = start, {}
    for name, seconds in PHASES:
        cursor = integer(cursor + integer(seconds) * NS)
        fences[name] = cursor
    require(cursor == end and all(row["maximumSeconds"] < 900 for row in fixed["nativeCaptureSpans"]),
            "BOOTSTRAP_ALLOCATION_ACCOUNTING")
    return {"schema": 1, "scope": SCOPE, "profile": origin.bootstrap.PROFILE,
            "selection": basis["selection"], "cacheCohort": basis["cacheCohort"],
            "source": basis["source"], "github": basis["github"], "clock": basis["clock"],
            "serviceTimeBasis": basis, "serviceTimeBasisSha256": origin.digest(origin.encoded(basis)),
            "policy": fixed, "allocationStartBasisNs": start, "proposedJobEndNs": end,
            "phaseFencesNs": fences, "budgetAcceptance": "NOT_ADMITTED", "testAcceptance": "NOT_PERFORMED",
            "productiveOwner": "NOT_CREATED", "exportSaveAuthority": False}


def validate_proposal(raw, admitted, originals, invocation, clock, runner_name):
    expected = derive(admitted, originals, invocation, clock, runner_name)
    require(type(raw) is bytes and raw == origin.encoded(expected), "BOOTSTRAP_ALLOCATION_PROPOSAL_CHANGED")
    return expected


def derive_trace(proposal_raw, admitted, originals, invocation, clock, runner_name, *,
                 predecessor_raw, predecessor, observations):
    """Validate a supplied linear prefix, not actual one-shot phase execution.

    Opaque predecessor bytes and observation originals cannot attest themselves.
    The future caller must retain the real close/step/clock/source provenance.
    Consistent copies/replays remain possible, but never gain authority here.

    An adverse final observation is retained as FAILED, not dropped or promoted
    by later success. This trace cannot continue after failure/cancellation/
    UNKNOWN. A real failed-custody path must preserve those originals separately
    under the same proposed fences; this function neither performs nor admits it.
    """
    proposal = validate_proposal(proposal_raw, admitted, originals, invocation, clock, runner_name)
    origin.clocks.validate_reading(predecessor)
    require(predecessor.clock == clock and predecessor.nanoseconds >=
            proposal["serviceTimeBasis"]["service"]["lastNs"], "BOOTSTRAP_TRACE_PREDECESSOR_CLOCK")
    require(type(predecessor_raw) is bytes and 0 < len(predecessor_raw) <= origin.wire.RECORD_LIMIT,
            "BOOTSTRAP_TRACE_PREDECESSOR_BYTES")
    require(type(observations) in (list, tuple) and len(observations) <= len(PHASES) and
            all(type(raw) is bytes and 0 < len(raw) <= OBSERVATION_LIMIT for raw in observations),
            "BOOTSTRAP_TRACE_ORIGINALS")
    originals_copy = tuple(observations)
    previous = origin.digest(predecessor_raw)
    last = predecessor.nanoseconds
    rows, failures, group_starts = [], [], {}
    caps = dict(PHASES)
    for index, raw in enumerate(originals_copy):
        require(not failures, "BOOTSTRAP_TRACE_TERMINAL_REUSE")
        value = origin.bootstrap.ordinary.parse(raw, OBSERVATION_LIMIT)
        name, seconds = PHASES[index]
        require(set(value) == OBSERVATION_FIELDS and type(value["schema"]) is int and value["schema"] == 1 and
                value["scope"] == OBSERVATION_SCOPE and value["phase"] == name,
                "BOOTSTRAP_TRACE_PHASE_OR_FIELDS")
        require(origin.encoded(value["clock"]) == origin.encoded(proposal["clock"]), "BOOTSTRAP_TRACE_CLOCK_CHANGED")
        require(value["previousSha256"] == previous, "BOOTSTRAP_TRACE_PREDECESSOR_CHANGED")
        began, returned = integer(value["beganNs"]), integer(value["returnedNs"])
        require(last <= began <= returned, "BOOTSTRAP_TRACE_BACKWARDS")
        require(type(value["originalOutcome"]) is str and value["originalOutcome"] in
                ("success", "failure", "cancelled", "skipped", "") and
                value["retirement"] in ("KNOWN", "UNKNOWN") and type(value["cancelled"]) is bool,
                "BOOTSTRAP_TRACE_DISPOSITION")
        end = min(proposal["phaseFencesNs"][name], integer(began + seconds * NS))
        group_end = None
        for group, members in CAPTURE_GROUPS:
            if name not in members:
                continue
            if name == members[0]:
                group_starts[group] = began
            # Cumulative original span, not a new225 after a delayed poll or a
            # new45 for a still-live stream. Readback has its own later slot.
            group_end = integer(group_starts[group] + sum(caps[member] for member in
                members[:members.index(name) + 1]) * NS)
            if returned >= group_end:
                failures.append("NATIVE_CAPTURE_FENCE_EXPIRED")
        if returned >= end:
            failures.append("PHASE_FENCE_EXPIRED")
        soft = None
        if name in COPY_PHASES:
            work = integer(value["lastNewWorkNs"])
            require(began <= work <= returned, "BOOTSTRAP_TRACE_NEW_WORK_CLOCK")
            soft = min(end, integer(began + 90 * NS))
            if work >= soft:
                failures.append("NEW_WORK_FENCE_EXPIRED")
        else:
            require(value["lastNewWorkNs"] is None, "BOOTSTRAP_TRACE_UNEXPECTED_NEW_WORK")
        if value["originalOutcome"] != "success":
            failures.append("STEP_NOT_SUCCESSFUL")
        if value["cancelled"] or value["originalOutcome"] == "cancelled":
            failures.append("CANCELLED")
        if value["retirement"] == "UNKNOWN":
            failures.append("RETIREMENT_UNKNOWN")
        previous, last = origin.digest(raw), returned
        rows.append({"originalSha256": previous, "observation": value, "phaseEndNs": end,
                     "nativeCaptureEndNs": group_end, "newWorkEndNs": soft})
    status = ("FAILED_SUPPLIED_TRACE" if failures else "COMPLETE_SUPPLIED_TRACE" if len(rows) == len(PHASES)
              else "PREFIX_ONLY_SUPPLIED_TRACE")
    return {"schema": 1, "scope": TRACE_SCOPE, "proposalSha256": origin.digest(proposal_raw),
            "clock": proposal["clock"], "predecessorSha256": origin.digest(predecessor_raw),
            "predecessorNs": predecessor.nanoseconds, "observations": rows, "lastNs": last,
            "lastOriginalSha256": previous, "status": status, "failureReasons": failures,
            "consistencyScope": "SUPPLIED_PREFIX_NOT_ORIGINAL_OUTCOME_CUSTODY_OR_SINGLE_USE",
            "budgetAcceptance": "NOT_ADMITTED", "testAcceptance": "NOT_PERFORMED", "exportSaveAuthority": False}


def validate_trace(raw, proposal_raw, admitted, originals, invocation, clock, runner_name, *,
                   predecessor_raw, predecessor, observations):
    expected = derive_trace(proposal_raw, admitted, originals, invocation, clock, runner_name,
                            predecessor_raw=predecessor_raw, predecessor=predecessor, observations=observations)
    require(type(raw) is bytes and raw == origin.encoded(expected), "BOOTSTRAP_ALLOCATION_TRACE_CHANGED")
    return expected
