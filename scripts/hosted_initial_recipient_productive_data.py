"""Closed initial productive/Step DATA, never an original owner or authority.

No native controller is loaded here. Supplied identities, histories, paths and
consistent records cannot supply a current use, producer, Step or provider.
The fixed adapter separately owns original reads/returns and irreversible use.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import math
from pathlib import Path
import re

import hosted_cache_bootstrap_allocation as allocation
import hosted_cache_bootstrap_initialization as initialization
import hosted_dependency_seed_files as files
import hosted_initial_recipient_bootstrap_identity as identity


O = allocation.origin
ROOT = Path(__file__).resolve().parents[1]
LIMIT = 2 * 1024 * 1024
SOURCE_KEYS = ("base_policy_entry", "ancestry_raw", "candidate_policy_entry", "candidate_policy_raw")
INITIALIZER_DIRECTORIES = ("I", "I/canonical-init", "I/control-home", "I/temporary", "I/state",
    "I/state/gradle-home", "I/state/evidence", "I/state/cancellations")
INITIALIZER_FILES = ("I/receiving-window.json", "I/initializer-context.json", "I/initialization-pending.json",
    *("I/canonical-init/" + name for name in
      ("baseline.json", "native-start.json", "request.json", "result.json", "start.json", "stderr.log", "stdout.log")),
    "I/state/context.json", "I/state/gradle-home/gradle.properties")
DIRECTORY_NAMES = ("session", "state", "gradle-home", "evidence", "cancellations")
DIRECTORY_KEYS = ("I", "I/state", "I/state/gradle-home", "I/state/evidence", "I/state/cancellations")
HISTORY_FIELDS = "schema scope kind observed clock originalBootDigest originalPreviousNs originalJobBasisNs " \
    "serviceArithmetic serviceJob firstUseAt matchSha256 originalLocalScope primaryStepScope currentAuthority " \
    "budgetAcceptance exportSaveAuthority"
RETIRED_SCOPE = "INITIAL_RECIPIENT_PRIMARY_RETIRED_FOR_PRODUCTIVE_V1"
INITIAL_CONTEXT_SCOPE = "INITIAL_RECIPIENT_CANONICAL_INITIALIZER_CONTEXT_V1"
INPUT_SCOPE = "INITIAL_RECIPIENT_PRODUCTIVE_ORIGINAL_INPUT_BINDING_V1"
STAGING_PARENT_SCOPE = "INITIAL_RECIPIENT_STAGING_PARENT_CLOSED_NO_EXECUTION_V1"
PARENT_SCOPE = "INITIAL_RECIPIENT_PRODUCTIVE_PARENT_CLOSED_OBSERVATIONS_V1"
HANDOFF_SCOPE = "INITIAL_RECIPIENT_SAVE_HANDOFF_PENDING_ORIGINAL_STEP_RETURN_V1"
RETURN_SCOPE = "INITIAL_RECIPIENT_HANDOFF_FUNCTION_RETURN_PENDING_COMMAND_V1"
OUTPUT_SCOPE = "INITIAL_RECIPIENT_PRODUCER_PENDING_ORIGINAL_STEP_RETURN_V1"
SAVE_PREPARATION_SCOPE = "INITIAL_RECIPIENT_BOOTSTRAP_SAVE_PREPARATION_PENDING_ORIGINAL_STEP_RETURN_V1"
PROBE_PREPARATION_SCOPE = "INITIAL_RECIPIENT_BOOTSTRAP_PROBE_PREPARATION_PENDING_ORIGINAL_STEP_RETURN_V1"
STEP_CLOSE_SCOPE = "INITIAL_RECIPIENT_STEP_ORIGINAL_OWNER_CLOSE_V1"
STEP_CHAIN_SCOPE = "INITIAL_RECIPIENT_STEP_PRIVATE_USE_CHAIN_PENDING_OWNER_CLOSE_V1"
AFTER_SAVE_SCOPE = "INITIAL_RECIPIENT_AFTER_SAVE_PENDING_ORIGINAL_STEP_RETURN_V1"
SAVE_OBSERVATIONS_SCOPE = "INITIAL_RECIPIENT_AFTER_SAVE_OBSERVATIONS_PENDING_WRITER_RETURN_V1"
PROBE_RESULT_SCOPE = "INITIAL_RECIPIENT_PROBE_PENDING_ORIGINAL_STEP_RETURN_V1"
STEP_USE_FILES = ("private-use-chain.json", "begin-use.json", "begin-use-index.json",
                  "final-use.json", "final-use-index.json")
AFTER_SAVE_FILES = (*STEP_USE_FILES, "after-leaf.json", "save-preparation.json", "provider-save.json",
                    "readmission-close.json", "after-parent-close.json", "provider-prepared.json", "provider-readback.json")
SAVE_CLAIMS = ("PRODUCER_OUTCOME", "HANDOFF_SHA256", "PRODUCER_RETURN_SHA256", "SAVE_PREPARE_OUTCOME",
               "SAVE_PREPARATION_SHA256", "SAVE_OUTCOME", "SAVE_READBACK_SHA256")
STEP_CAPS = {"save-transition": (30, 30), "probe-transition": (30, 30),
    "save-readmission": (120, 120), "custody-readmission": (120, 120), "save-set-after": (120, 90),
    "save-observation": (30, 30), "save-owner-return": (45, 45), "provider-observation": (30, 30)}
STEP_PHASES = {"prepare-save": "save-transition", "after-save": "save-readmission",
               "prepare-probe": "probe-transition", "after-probe": "custody-readmission"}
BLOB_NAMES = tuple(name + ".json" for name in (
    "stage-parent", "stage-leaf", "seed-parent", "seed-leaf", "custody-parent", "custody-leaf", "custody-request",
    "producer-parent", "producer-request", "producer-observation", "producer-command", "producer-native",
    "collection-parent", "collection-leaf", "collection-inventory", "no-loader-parent", "no-loader-leaf",
    "export-parent", "export-leaf", "before-parent", "before-leaf", "retired-prefix", "worker-identity",
    "history", "allocation-proposal")) + tuple(name + ".bin" for name in SOURCE_KEYS) + (
    "initial-inputs.json", "productive-use-index.json")
PENDING = "PENDING_NOT_OBSERVABLE_BY_THIS_FILE"
# Additional initial-origin provenance only. The ordinary source roster and
# dependency/provider keys are untouched; these hashes grant no current use.
INITIAL_SOURCE_INPUTS = tuple("scripts/" + name for name in (
    "hosted_initial_recipient_productive.py", "hosted_initial_recipient_use.py",
    "hosted_initial_recipient_productive_adapter.py", "hosted_initial_recipient_productive_data.py",
    "run-hosted-initial-recipient.py", "run-hosted-initial-recipient-custody.py",
    "hosted_initial_recipient_before.py", "hosted_initial_recipient_continuity.py",
    "hosted_initial_recipient_public_origin.py", "hosted_cache_provider_native.py",
    "hosted_cache_provider_prepare.py", "hosted_cache_provider_readback.py"))
PRODUCTIVE_PHASES = ("dependency-stage", "empty-seed", "custody-prepare", "configuration", "custody-collect",
                    "custody-uninstall", "dependency-export", "save-set-before")
PREPARATION_FIELDS = "schema scope source github selection cacheCohort directory directoryIdentity handoffSha256 " \
    "producerReturnSha256 producerOriginalOutcome workerIdentitySha256 privateUseChainSha256 proposalSha256 plan " \
    "planSha256 clock originalBootDigest firstNs hardEndNs producerObservedAfterReturnNs providerWindow providerRequest " \
    "writerReturn providerExecution budgetAcceptance testAcceptance exportSaveAuthority"


def nonacceptance(value):
    require(value["budgetAcceptance"] == "NOT_ADMITTED" and value["testAcceptance"] == "NOT_PERFORMED" and
        value["exportSaveAuthority"] is False, "NONACCEPTANCE")


def handoff_record(raw, blobs, inputs, first, claims, directory, directory_identity):
    value = fields(canonical(raw), "schema scope binding source github selection cacheCohort plan planSha256 directory "
        "directoryIdentity blobs references chain window writerReturn providerExecution nextPhaseAuthority "
        "budgetAcceptance testAcceptance exportSaveAuthority")
    require(type(value["schema"]) is int and value["schema"] == 1 and value["scope"] == HANDOFF_SCOPE and
        value["writerReturn"] == PENDING and value["providerExecution"] == "NOT_PERFORMED" and
        value["nextPhaseAuthority"] is False and claims["PRODUCER_OUTCOME"] == "success" and
        O.digest(raw) == sha(claims["HANDOFF_SHA256"]), "HANDOFF_SCOPE_OR_CLAIMS")
    nonacceptance(value)
    require(type(blobs) is dict and set(blobs) == set(BLOB_NAMES) and len(blobs) == 31 < 32, "HANDOFF_ORIGINAL_BLOBS")
    same(value["blobs"], {name: {"bytes": len(raw_bytes(blob, empty=name.endswith(".bin"))), "sha256": O.digest(blob)}
        for name, blob in blobs.items()}, "HANDOFF_ORIGINAL_BLOBS")
    same(value["binding"], inputs.binding(), "HANDOFF_INITIAL_BINDING")
    for name in ("source", "github", "selection", "cacheCohort"):
        same(value[name], inputs.admission[name], "HANDOFF_IDENTITY")
    require(value["directory"] == str(directory) and native_identity(value["directoryIdentity"], inputs.role) ==
        tuple(directory_identity) and value["planSha256"] == O.digest(O.encoded(value["plan"])), "HANDOFF_DIRECTORY_OR_PLAN")
    window = fields(value["window"], "phase clock originalBootDigest firstNs localStarted hardEndNs "
        "predecessorCheckedNs predecessorSha256")
    began, hard, prior = (O.integer(window[name]) for name in ("firstNs", "hardEndNs", "predecessorCheckedNs"))
    require(window["phase"] == "producer-owner-return" and window["clock"] == O.clock_value(first.clock) ==
        O.clock_value(inputs.clock) and window["originalBootDigest"] == inputs.history["originalBootDigest"] and
        window["predecessorSha256"] == O.digest(blobs["before-parent.json"]) and prior <= began < hard == min(
        began + 45 * O.NS, inputs.proposal["phaseFencesNs"]["producer-owner-return"], inputs.proposal["proposedJobEndNs"]),
        "HANDOFF_ORIGINAL45")
    require(type(window["localStarted"]) is float, "HANDOFF_ORIGINAL_LOCAL")
    local(window["localStarted"])
    chain = fields(value["chain"], "scope returns referenceScope")
    require(chain["scope"] == "INITIAL_RECIPIENT_ORIGINAL_PRODUCTIVE_CLOSED_CHAIN_V1" and
        chain["referenceScope"] == "RETAINED_ORIGINAL_BINDINGS_NOT_PROVIDER_OR_STEP_RESULT" and
        type(chain["returns"]) is dict and set(chain["returns"]) == {*PRODUCTIVE_PHASES, "before"} and
        chain["returns"]["before"]["checkedNs"] == prior, "HANDOFF_ORIGINAL_CHAIN")
    same(chain["returns"]["before"], chain["returns"]["save-set-before"], "HANDOFF_BEFORE_ALIAS")
    for name, leaf in (("dependency-stage", "stage"), ("empty-seed", "seed"), ("custody-prepare", "custody"),
                       ("configuration", "producer"), ("custody-collect", "collection"),
                       ("custody-uninstall", "no-loader"), ("dependency-export", "export"), ("save-set-before", "before")):
        row = fields(chain["returns"][name], "rawSha256 checkedNs checkedLocal leaf")
        require(row["rawSha256"] == O.digest(blobs[leaf + "-parent.json"]) and O.integer(row["checkedNs"]) <= prior,
                "HANDOFF_PHASE_RETURN")
        require(type(row["checkedLocal"]) is float, "HANDOFF_RETURN_LOCAL")
        local(row["checkedLocal"])
        fields(row["leaf"], "rawSha256 checkedNs localStarted checkedLocal")
        leaf_name = "producer-observation.json" if name == "configuration" else leaf + "-leaf.json"
        require(row["leaf"]["rawSha256"] == O.digest(blobs[leaf_name]) and
            O.integer(row["leaf"]["checkedNs"]) <= row["checkedNs"] and
            type(row["leaf"]["localStarted"]) is type(row["leaf"]["checkedLocal"]) is float and
            local(row["leaf"]["localStarted"]) <= local(row["leaf"]["checkedLocal"]) <= row["checkedLocal"],
            "HANDOFF_LEAF_RETURN")
    return value


def producer_return_record(raw, index_raw, inputs, first, expected_hash, directory_identity):
    value = fields(canonical(raw), "schema scope handoffSha256 handoffDirectory handoffDirectoryIdentity initializerIdentity "
        "clock originalBootDigest firstNs hardEndNs handoffReturnedNs handoffReturnedLocal observedAfterReturnNs "
        "observedAfterReturnLocal observationScope recordWriterReturn producerStepOutcome providerExecution "
        "budgetAcceptance testAcceptance exportSaveAuthority")
    index = canonical(index_raw)
    require(type(value["schema"]) is int and value["schema"] == 1 and value["scope"] == RETURN_SCOPE and
        O.digest(raw) == sha(expected_hash) and value["observationScope"] == "HANDOFF_FUNCTION_RETURN_ONLY" and
        value["recordWriterReturn"] == value["producerStepOutcome"] == PENDING and
        value["providerExecution"] == "NOT_PERFORMED", "FUNCTION_RETURN_MARKERS")
    nonacceptance(value)
    require(value["handoffSha256"] == O.digest(index_raw) and value["handoffDirectory"] == index["directory"] and
        native_identity(value["handoffDirectoryIdentity"], inputs.role) == tuple(directory_identity) and
        native_identity(value["initializerIdentity"], inputs.role) == inputs.directories["session"] and
        value["clock"] == O.clock_value(first.clock) == index["window"]["clock"] and
        value["originalBootDigest"] == index["window"]["originalBootDigest"], "FUNCTION_RETURN_BINDING")
    began, hard, returned, observed = (O.integer(value[name]) for name in
        ("firstNs", "hardEndNs", "handoffReturnedNs", "observedAfterReturnNs"))
    require(began == index["window"]["firstNs"] and hard == index["window"]["hardEndNs"] and
        began <= returned <= observed < hard and first.nanoseconds >= observed, "FUNCTION_RETURN_CHRONOLOGY")
    local_first = local(index["window"]["localStarted"])
    require(type(value["handoffReturnedLocal"]) is type(value["observedAfterReturnLocal"]) is float and
        local_first <= local(value["handoffReturnedLocal"]) <= local(value["observedAfterReturnLocal"]) <
        O.wire._directed_deadline(local_first, 45, hard, began), "FUNCTION_RETURN_LOCAL45_HISTORY")
    return value


def preparation_record(raw, inputs, handoff_raw, return_raw, first, phase, expected_hash, directory, directory_identity,
                       use_chain_raw, contract, *, after_save_hash=None):
    require(phase in ("save", "lookup"), "PREPARATION_FIXED_PHASE")
    value = fields(canonical(raw), PREPARATION_FIELDS + (" afterSaveSha256" if phase == "lookup" else ""))
    index, produced = canonical(handoff_raw), canonical(return_raw)
    prefix, transition, provider = (("SAVE", "save-transition", "provider-save") if phase == "save" else
                                     ("PROBE", "probe-transition", "provider-probe"))
    require(type(value["schema"]) is int and value["schema"] == 1 and value["scope"] ==
        (SAVE_PREPARATION_SCOPE if phase == "save" else PROBE_PREPARATION_SCOPE) and O.digest(raw) == sha(expected_hash) and
        value["producerOriginalOutcome"] == "success" and value["writerReturn"] == PENDING and
        value["providerExecution"] == "NOT_PERFORMED", "PREPARATION_MARKERS")
    nonacceptance(value)
    for name in ("source", "github", "selection", "cacheCohort"):
        same(value[name], inputs.admission[name], "PREPARATION_IDENTITY")
    require(value["directory"] == str(directory) and native_identity(value["directoryIdentity"], inputs.role) ==
        tuple(directory_identity) and value["handoffSha256"] == O.digest(handoff_raw) and
        value["producerReturnSha256"] == O.digest(return_raw) and
        value["workerIdentitySha256"] == O.digest(inputs.admitted.record) and
        value["proposalSha256"] == O.digest(inputs.proposal_raw) and
        value["privateUseChainSha256"] == O.digest(use_chain_raw) and
        value["planSha256"] == index["planSha256"] and value["clock"] == O.clock_value(first.clock) and
        value["originalBootDigest"] == inputs.history["originalBootDigest"], "PREPARATION_BINDING")
    same(value["plan"], index["plan"], "PREPARATION_PLAN")
    began, hard, prior = (O.integer(value[name]) for name in ("firstNs", "hardEndNs", "producerObservedAfterReturnNs"))
    require(prior == produced["observedAfterReturnNs"] and prior <= began < hard == min(began + 30 * O.NS,
        inputs.proposal["phaseFencesNs"][transition], inputs.proposal["proposedJobEndNs"]), "PREPARATION_ORIGINAL30")
    chain = private_chain_record(use_chain_raw, inputs, handoff_raw,
        "prepare-save" if phase == "save" else "prepare-probe", began, hard)
    checked = chain["checkedNs"]
    window = fields(value["providerWindow"], "issuedNs hardEndNs actualProviderStart")
    issued, end = O.integer(window["issuedNs"]), O.integer(window["hardEndNs"])
    require(checked <= issued < hard and issued < end == min(issued + 180 * O.NS,
        inputs.proposal["phaseFencesNs"][provider], inputs.proposal["proposedJobEndNs"]) and
        issued <= first.nanoseconds < end and window["actualProviderStart"] == "NOT_OBSERVED", "PREPARATION_PROVIDER_WINDOW")
    same(value["providerRequest"], contract["request"], "PREPARATION_PROVIDER_REQUEST")
    if phase == "lookup":
        require(value["afterSaveSha256"] == sha(after_save_hash), "PREPARATION_AFTER_SAVE_BINDING")
    return value


def private_chain_record(raw, inputs, handoff_raw, operation, first, work):
    """Historical private begin/final DATA. Actual per-use readers are separate."""
    require(operation in STEP_PHASES, "PRIVATE_CHAIN_OPERATION")
    chain = fields(canonical(raw), "schema scope operation clock originalBootDigest firstNs workEndNs "
        "handoffSha256 uses checkedNs ownerClose providerExecution exportSaveAuthority")
    require(type(chain["schema"]) is int and chain["schema"] == 1 and chain["scope"] == STEP_CHAIN_SCOPE and
        chain["operation"] == operation and O.integer(chain["firstNs"]) == O.integer(first) and
        O.integer(chain["workEndNs"]) == O.integer(work) and chain["clock"] == O.clock_value(inputs.clock) and
        chain["originalBootDigest"] == inputs.history["originalBootDigest"] and
        chain["handoffSha256"] == O.digest(handoff_raw) and chain["ownerClose"] == PENDING and
        chain["providerExecution"] == "NOT_PERFORMED" and chain["exportSaveAuthority"] is False and
        type(chain["uses"]) is list and len(chain["uses"]) == 2, "PRIVATE_CHAIN_BINDING")
    seconds = STEP_CAPS[STEP_PHASES[operation]][0]
    require(first < work == min(first + seconds * O.NS,
        inputs.proposal["phaseFencesNs"][STEP_PHASES[operation]], inputs.proposal["proposedJobEndNs"]),
        "PRIVATE_CHAIN_ORIGINAL_CAP")
    checked, previous = O.integer(chain["checkedNs"]), first
    require(first <= checked < work, "PRIVATE_CHAIN_CHECKED")
    for row, edge in zip(chain["uses"], ("begin", "final")):
        fields(row, "site root return inventory window returnSha256 inventorySha256 originalsSha256")
        returned, window = row["return"], row["window"]
        require(row["site"] == returned["site"] == window["site"] == operation + "/" + edge and
            O.integer(window["parentFirstNs"]) == first and O.integer(window["parentWorkEndNs"]) == work and
            window["clock"] == chain["clock"] and window["originalBootDigest"] == chain["originalBootDigest"] and
            row["returnSha256"] == O.digest(O.encoded(returned)) and
            row["inventorySha256"] == O.digest(O.encoded(row["inventory"])) and
            returned["windowSha256"] == O.digest(O.encoded(window)) and
            returned["workerIdentitySha256"] == O.digest(inputs.admitted.record) and
            previous <= O.integer(window["firstNs"]) <= O.integer(returned["preCloseNs"]) <=
            O.integer(returned["closedNs"]) <= checked and returned["closedNs"] < O.integer(window["workEndNs"]) <= work,
            "PRIVATE_CHAIN_ORIGINAL_USE_ORDER")
        previous = returned["closedNs"]
    return chain


def step_window_record(value, inputs, phase):
    fields(value, "phase clock originalBootDigest firstNs softEndNs hardEndNs localStarted localScope")
    require(phase in STEP_CAPS and value["phase"] == phase and
        value["clock"] == O.clock_value(inputs.clock) and
        value["originalBootDigest"] == inputs.history["originalBootDigest"] and
        value["localScope"] == "THIS_COMMAND_ONLY" and type(value["localStarted"]) is float,
        "STEP_WINDOW_IDENTITY")
    first, soft, hard = (O.integer(value[name]) for name in ("firstNs", "softEndNs", "hardEndNs"))
    seconds, new_seconds = STEP_CAPS[phase]
    require(first < soft == min(hard, first + new_seconds * O.NS) and hard == min(first + seconds * O.NS,
        inputs.proposal["phaseFencesNs"][phase], inputs.proposal["proposedJobEndNs"]), "STEP_WINDOW_ORIGINAL_CAP")
    local(value["localStarted"])
    return value


def step_close_record(raw, inputs, phase):
    value = fields(canonical(raw), "schema scope window predecessorSha256 predecessorCheckedNs privateUseChainSha256 "
        "leafSha256 leafCheckedNs leafCheckedLocal historicalBefore closedNs closedLocal resourceCount parentResourceClose "
        "nextPhaseAuthority budgetAcceptance testAcceptance exportSaveAuthority")
    require(type(value["schema"]) is int and value["schema"] == 1 and value["scope"] == STEP_CLOSE_SCOPE and
        value["parentResourceClose"] == "KNOWN_RESOURCE_CLOSE_ONLY" and value["nextPhaseAuthority"] is False and
        type(value["resourceCount"]) is int and 0 < value["resourceCount"] <= files.MEMBER_LIMIT,
        "STEP_CLOSE_MARKERS")
    nonacceptance(value)
    window = step_window_record(value["window"], inputs, phase)
    first, hard, began_local = window["firstNs"], window["hardEndNs"], window["localStarted"]
    sha(value["predecessorSha256"])
    require(O.integer(value["predecessorCheckedNs"]) <= first <= O.integer(value["closedNs"]) < hard and
        type(value["closedLocal"]) is float and began_local <= local(value["closedLocal"]) <
        O.wire._directed_deadline(began_local, STEP_CAPS[phase][0], hard, first), "STEP_CLOSE_ORIGINAL_FRONTIER")
    chain = value["privateUseChainSha256"]
    require((chain is None) == (phase not in ("save-readmission", "custody-readmission")), "STEP_CLOSE_USE_POSITION")
    if chain is not None:
        sha(chain)
    if value["leafSha256"] is None:
        require(value["leafCheckedNs"] is value["leafCheckedLocal"] is None, "STEP_CLOSE_NO_LEAF")
    else:
        sha(value["leafSha256"])
        require(first <= O.integer(value["leafCheckedNs"]) <= value["closedNs"] and
            type(value["leafCheckedLocal"]) is float and
            began_local <= local(value["leafCheckedLocal"]) <= value["closedLocal"], "STEP_CLOSE_LEAF_FRONTIER")
    if phase == "save-set-after":
        old = fields(value["historicalBefore"], "rawSha256 checkedNs checkedLocal localScope")
        sha(old["rawSha256"])
        require(O.integer(old["checkedNs"]) <= first and type(old["checkedLocal"]) is float and
            old["localScope"] == "ORIGINAL_PRODUCER_PROCESS_ONLY_NOT_COMPARED_WITH_THIS_COMMAND",
            "STEP_HISTORICAL_BEFORE")
        local(old["checkedLocal"])  # Deliberately no comparison with this process's LOCAL.
    else:
        require(value["historicalBefore"] is None, "STEP_NO_HISTORICAL_BEFORE")
    return value


def _provider_nonacceptance(value, clock, boot, claims):
    nonacceptance(value)
    require(value["writerReturn"] == PENDING and value["providerStorage"] == "UNPROVEN" and
        value["providerDeadlineEnforcement"] == "NOT_ESTABLISHED" and value["providerRetirement"] == "NOT_OBSERVED" and
        value["clock"] == clock and value["originalBootDigest"] == boot, "STEP_PROVIDER_NONACCEPTANCE")
    same(value["originalClaims"], claims, "STEP_ORIGINAL_CLAIMS")


def after_save_records(raw, observations_raw, retained, inputs, handoff_raw, producer_raw, claims, first,
                       directory, directory_identity):
    """Passive cross-Step chronology, never an expired parent/current callback.

    The new caller separately reads fixed native originals and validates the old
    Action against this genuinely hash-bound earliest post-Action RAW value.
    No old LOCAL is compared with the new command's LOCAL epoch.
    """
    returned = fields(canonical(raw), "schema scope source github selection cacheCohort directory directoryIdentity "
        "originalClaims planSha256 clock originalBootDigest observationsSha256 observationOwnerReturn returnWindow "
        "recordedNs recordedLocal providerStorage providerDeadlineEnforcement providerRetirement writerReturn "
        "budgetAcceptance testAcceptance exportSaveAuthority")
    observed = fields(canonical(observations_raw), "schema scope source github selection cacheCohort originalClaims "
        "planSha256 clock originalBootDigest firstPostProviderNs firstPostProviderLocal providerEndNs providerTimeScope "
        "providerStorage providerDeadlineEnforcement providerRetirement files window writerReturn "
        "budgetAcceptance testAcceptance exportSaveAuthority")
    require(claims["AFTER_SAVE_OUTCOME"] == "success" and O.digest(raw) == sha(claims["AFTER_SAVE_SHA256"]) and
        type(returned["schema"]) is type(observed["schema"]) is int and returned["schema"] == observed["schema"] == 1 and
        returned["scope"] == AFTER_SAVE_SCOPE and observed["scope"] == SAVE_OBSERVATIONS_SCOPE and
        returned["directory"] == str(directory) and native_identity(returned["directoryIdentity"], inputs.role) ==
        tuple(directory_identity) and returned["observationsSha256"] == O.digest(observations_raw), "AFTER_SAVE_ORIGINAL_RETURN")
    old_claims = {name: claims[name] for name in SAVE_CLAIMS}
    require(all(value == "success" if name.endswith("OUTCOME") else sha(value)
                for name, value in old_claims.items()) and old_claims["HANDOFF_SHA256"] == O.digest(handoff_raw) and
        old_claims["PRODUCER_RETURN_SHA256"] == O.digest(producer_raw), "AFTER_SAVE_ORIGINAL_CLAIMS")
    for value in (returned, observed):
        _provider_nonacceptance(value, O.clock_value(first.clock), inputs.history["originalBootDigest"], old_claims)
        require(value["planSha256"] == canonical(handoff_raw)["planSha256"], "AFTER_SAVE_ORIGINAL_PLAN")
        for name in ("source", "github", "selection", "cacheCohort"):
            same(value[name], inputs.admission[name], "AFTER_SAVE_ORIGINAL_IDENTITY")
    require(observed["providerTimeScope"] ==
        "POST_ACTION_UPPER_BOUND_ONLY_REQUIRES_TRUSTED_SEQUENTIAL_ORIGINAL_OUTCOME" and
        type(retained) is dict and set(retained) == set(AFTER_SAVE_FILES), "AFTER_SAVE_RETAINED_ROSTER")
    same(observed["files"], {name: O.digest(raw_bytes(value)) for name, value in retained.items()},
        "AFTER_SAVE_ORIGINAL_BYTES")
    readmission = step_close_record(retained["readmission-close.json"], inputs, "save-readmission")
    parent = step_close_record(retained["after-parent-close.json"], inputs, "save-set-after")
    observation = step_close_record(O.encoded(returned["observationOwnerReturn"]), inputs, "save-observation")
    return_window = step_window_record(returned["returnWindow"], inputs, "save-owner-return")
    require(readmission["window"]["firstNs"] == O.integer(observed["firstPostProviderNs"]) and
        type(observed["firstPostProviderLocal"]) is float and
        readmission["window"]["localStarted"] == local(observed["firstPostProviderLocal"]) and
        readmission["predecessorSha256"] == O.digest(producer_raw) and
        readmission["predecessorCheckedNs"] == canonical(producer_raw)["observedAfterReturnNs"] and
        readmission["leafSha256"] is None, "AFTER_SAVE_EARLIEST_POST_PROVIDER")
    require(readmission["privateUseChainSha256"] == O.digest(retained["private-use-chain.json"]),
        "AFTER_SAVE_PRIVATE_CHAIN_HASH")
    chain = private_chain_record(retained["private-use-chain.json"], inputs, handoff_raw, "after-save",
        readmission["window"]["firstNs"], readmission["window"]["hardEndNs"])
    require(chain["checkedNs"] <= readmission["closedNs"], "AFTER_SAVE_PRIVATE_CHAIN_RETURN")
    for raw_previous, previous, current in ((retained["readmission-close.json"], readmission, parent),
                                           (retained["after-parent-close.json"], parent, observation)):
        require(current["predecessorSha256"] == O.digest(raw_previous) and
            current["predecessorCheckedNs"] == previous["closedNs"] and
            previous["closedNs"] <= current["window"]["firstNs"] and
            previous["closedLocal"] <= current["window"]["localStarted"], "AFTER_SAVE_PHASE_ORDER")
    same(observed["window"], observation["window"], "AFTER_SAVE_OBSERVATION_WINDOW")
    require(observation["leafSha256"] == O.digest(observations_raw) and
        observation["closedNs"] <= return_window["firstNs"] and
        observation["closedLocal"] <= return_window["localStarted"] and
        return_window["firstNs"] <= O.integer(returned["recordedNs"]) < return_window["hardEndNs"] and
        returned["recordedNs"] <= first.nanoseconds and type(returned["recordedLocal"]) is float and
        return_window["localStarted"] <= local(returned["recordedLocal"]) < O.wire._directed_deadline(
            return_window["localStarted"], 45, return_window["hardEndNs"], return_window["firstNs"]),
        "AFTER_SAVE_ORIGINAL_RETURN45")
    require(observed["firstPostProviderNs"] < O.integer(observed["providerEndNs"]), "AFTER_SAVE_ORIGINAL_PROVIDER_END")
    return returned, observed, readmission, parent


def after_save_leaf(raw, before_raw, before_parent_raw, index, parent, proposal_raw):
    """Compare the actual complete after observation with the original whole set."""
    before, after = canonical(before_raw), canonical(raw)
    require(set(after) == set(before) and after["scope"] == "BOOTSTRAP_SAVE_SET_AFTER_LEAF_V1" and
        after["phase"] == "after-save" and after["status"] == "KNOWN_UNCHANGED" and
        after["beforeSaveSha256"] == O.digest(before_raw), "AFTER_SAVE_LEAF_KIND")
    same(before, {**after, "scope": "BOOTSTRAP_SAVE_SET_BEFORE_LEAF_V1", "phase": "before-save",
        "status": "KNOWN_FROZEN", "beforeSaveSha256": None, "window": before["window"]}, "AFTER_SAVE_WHOLE_SET_CHANGED")
    window = fields(after["window"], "phase clock firstNs hardEndNs softEndNs lastNewWorkNs finishedNs "
        "predecessorSha256 predecessorCheckedNs proposalSha256")
    previous = index["chain"]["returns"]["before"]
    require(window["phase"] == "save-set-after" and window["proposalSha256"] == O.digest(proposal_raw) and
        window["predecessorSha256"] == O.digest(before_parent_raw) and
        O.integer(window["predecessorCheckedNs"]) == previous["checkedNs"] and
        all(O.encoded(window[name]) == O.encoded(parent["window"][name]) for name in
            ("phase", "clock", "firstNs", "softEndNs", "hardEndNs")) and
        previous["checkedNs"] <= window["firstNs"] <= O.integer(window["lastNewWorkNs"]) <=
        O.integer(window["finishedNs"]) <= parent["leafCheckedNs"] <= parent["closedNs"] and
        window["lastNewWorkNs"] < window["softEndNs"] and parent["leafSha256"] == O.digest(raw),
        "AFTER_SAVE_LEAF_WINDOW")
    same(parent["historicalBefore"], {"rawSha256": O.digest(before_parent_raw), "checkedNs": previous["checkedNs"],
        "checkedLocal": previous["checkedLocal"],
        "localScope": "ORIGINAL_PRODUCER_PROCESS_ONLY_NOT_COMPARED_WITH_THIS_COMMAND"}, "AFTER_SAVE_HISTORICAL_BEFORE")
    return after


def require(value, reason):
    O.require(value, "INITIAL_PRODUCTIVE_DATA_" + reason)


def raw_bytes(raw, maximum=LIMIT, *, empty=False):
    require(type(raw) is bytes and (0 if empty else 1) <= len(raw) <= maximum, "ORIGINAL_BYTES")
    return raw


def canonical(raw, maximum=LIMIT):
    value = O.parse(raw_bytes(raw, maximum))
    require(type(value) is dict and O.encoded(value) == raw, "CANONICAL_RECORD")
    return value


def fields(value, names):
    require(type(value) is dict and set(value) == set(names.split()), "FIELDS")
    return value


def same(actual, expected, reason):
    require(O.encoded(actual) == O.encoded(expected), reason)


def local(value):
    require(type(value) in (int, float) and math.isfinite(value) and value >= 0, "LOCAL_CLOCK")
    return float(value)


def sha(value):
    require(type(value) is str and re.fullmatch(r"[0-9a-f]{64}", value), "HASH")
    return value


def native_identity(value, role):
    require(type(value) in (tuple, list) and files._identity(list(value)) and
        type(value[1]) is (str if role == "windows-x64" else int), "NATIVE_IDENTITY")
    return tuple(value)


def worker_values(value):
    require(type(value) is identity.InitialBootstrapIdentity, "INITIAL_IDENTITY_REQUIRED")
    raws = tuple(raw_bytes(getattr(value, name), files.RECEIPT_LIMIT) for name in
        ("record", "original_event", "original_policy", "public_key"))
    require(type(value.fingerprint) is str and type(value.key_sha256) is str and type(value.expires_at) is int,
        "IDENTITY_FIELDS")
    return (*raws, value.fingerprint, value.key_sha256, value.expires_at)


def checked_worker(value):
    snapshot = worker_values(value)
    record = canonical(snapshot[0])
    require(identity.cache_cohort(snapshot[0]) is not None, "INITIAL_IDENTITY_REQUIRED")
    # This is historical supplied-byte consistency, NOT policy currency. A new
    # actual acquisition must separately bind the match using its real now.
    match = identity.stages.BootstrapMatch(O.encoded(record["initialRecipient"]))
    expected = identity.bind_worker_match(match, event_raw=snapshot[1], policy_raw=snapshot[2],
        now=record["initialRecipient"]["firstUseAt"])
    require(worker_values(expected) == snapshot, "IDENTITY_ORIGINALS_CHANGED")
    return record


def original_proposal(raw, worker, history_raw, clock):
    """Original service arithmetic only; never derive a new budget from a recheck."""
    admitted = checked_worker(worker)
    history = fields(canonical(history_raw), HISTORY_FIELDS)
    value = canonical(raw)
    require(type(history["schema"]) is int and history["schema"] == 1 and
        history["scope"] == "INITIAL_CUSTODY_PRIMARY_HISTORICAL_BINDING_V1" and history["kind"] == "worker" and
        history["currentAuthority"] == "NOT_ACQUIRED" and history["budgetAcceptance"] == "NOT_ADMITTED" and
        history["exportSaveAuthority"] is False, "ORIGINAL_HISTORY")
    O.clocks.validate_identity(clock)
    first_use = admitted["initialRecipient"]["firstUseAt"]
    require(history["firstUseAt"] == first_use and
        history["matchSha256"] == O.digest(O.encoded(admitted["initialRecipient"])) and
        history["clock"] == O.clock_value(clock), "HISTORY_IDENTITY")
    sha(history["originalBootDigest"])
    basis = value.get("serviceTimeBasis")
    require(type(basis) is dict and type(basis.get("service")) is dict and
        type(basis.get("invocation")) is str and re.fullmatch(r"[0-9a-f]{32}", basis["invocation"]), "ORIGINAL_SERVICE")
    service = basis["service"]
    shared = {"schema": 1, "profile": admitted["profile"], "selection": admitted["selection"],
        "cacheCohort": admitted["cacheCohort"], "source": admitted["source"], "github": admitted["github"],
        "workerIdentitySha256": O.digest(worker.record), "clock": O.clock_value(clock), "firstUseAt": first_use,
        "budgetAcceptance": "NOT_ADMITTED", "testAcceptance": "NOT_PERFORMED", "exportSaveAuthority": False}
    expected_basis = {**shared, "scope": "INITIAL_RECIPIENT_BOOTSTRAP_SERVICE_TIME_BASIS_V1",
        "invocation": basis["invocation"], "service": service, "policy": allocation.service_time.policy(),
        **allocation.service_time.basis_arithmetic(service["jobsRequestStartedNs"],
            O.wire.utc_epoch(service["jobStartedAt"]), service["originDateEpochSeconds"])}
    expected = {**shared, "scope": "INITIAL_RECIPIENT_BOOTSTRAP_ALLOCATION_PROPOSAL_V1",
        "serviceTimeBasis": expected_basis, "serviceTimeBasisSha256": O.digest(O.encoded(expected_basis)),
        "policy": allocation.policy(), **allocation.fence_arithmetic(expected_basis["jobStartBasisNs"]),
        "productiveOwner": "NOT_CREATED"}
    require(raw == O.encoded(expected) and expected_basis["jobStartBasisNs"] == history["originalJobBasisNs"],
        "ORIGINAL_PROPOSAL_CHANGED")
    return value


def retired_input_close(value):
    """Exact DATA roster of C's twelve-reader/four-directory retirement only."""
    fields(value, "schema scope resources retirement exportSaveAuthority")
    require(type(value["schema"]) is int and value["schema"] == 1 and
        value["scope"] == "INITIAL_CUSTODY_PRIMARY_NATIVE_CLOSE_V1" and
        value["retirement"] == "KNOWN_RESOURCE_CLOSE_ONLY" and value["exportSaveAuthority"] is False,
        "RETIRED_INPUT_CLOSE")
    labels, parents = [], set()
    for name in INITIALIZER_FILES:
        parent = name.rsplit("/", 1)[0]
        if parent not in parents:
            parents.add(parent)
            labels.append("directory")
        labels.append("reader")
    same(value["resources"], [{"ordinal": number, "label": label, "closeAttempted": True, "closed": True}
        for number, label in enumerate(labels)], "RETIRED_INPUT_CLOSE_ROSTER")
    return value


@dataclass(frozen=True, repr=False)
class InitialOriginals:
    """Supplied initial leaf DATA. Constructing it grants no original-call rights."""
    worker: object
    history_raw: bytes
    proposal_raw: bytes
    retired_raw: bytes
    source_records: tuple
    initializer: str
    initializer_originals: tuple
    initializer_directories: tuple
    checked_ns: int
    checked_local: float


def capture_originals(value):
    require(type(value) is InitialOriginals, "INITIAL_ORIGINALS_REQUIRED")
    worker = worker_values(value.worker)
    raws = tuple(raw_bytes(getattr(value, name)) for name in ("history_raw", "proposal_raw", "retired_raw"))
    require(type(value.source_records) is tuple and tuple(name for name, _raw in value.source_records) == SOURCE_KEYS and
        all(type(row) is tuple and len(row) == 2 for row in value.source_records), "SOURCE_ROSTER")
    sources = tuple((name, raw_bytes(raw, empty=True)) for name, raw in value.source_records)
    require(type(value.initializer) is str and type(value.initializer_originals) is tuple and
        tuple(name for name, _raw in value.initializer_originals) == INITIALIZER_FILES and
        all(type(row) is tuple and len(row) == 2 for row in value.initializer_originals), "INITIALIZER_ROSTER")
    originals = tuple((name, raw_bytes(raw, empty=name.endswith(".log"))) for name, raw in value.initializer_originals)
    require(type(value.initializer_directories) is tuple and len(value.initializer_directories) == 8 and
        all(type(row) is tuple and len(row) == 3 for row in value.initializer_directories), "INITIALIZER_DIRECTORIES")
    clock = O.wire.clock_identity(canonical(value.history_raw)["clock"])
    directories = tuple((name, native_identity(pin, clock.role), provenance)
        for name, pin, provenance in value.initializer_directories)
    require({name for name, _pin, _provenance in directories} == set(INITIALIZER_DIRECTORIES) and
        all(provenance == "ORIGINAL_INITIALIZER_NATIVE_PIN" for _name, _pin, provenance in directories) and
        len({pin for _name, pin, _provenance in directories}) == 8, "INITIALIZER_DIRECTORY_PINS")
    require(type(value.checked_local) is float, "INITIALIZER_ORIGINAL_LOCAL")
    return (worker, *raws, sources, value.initializer, originals, directories,
        O.integer(value.checked_ns), local(value.checked_local))


class InitialInputs:
    """Detached supplied-data view for shared leaves, deliberately not ordinary _Inputs."""
    def __init__(self, published, snapshot):
        self.published, self.snapshot = published, snapshot
        (worker, self.history_raw, self.proposal_raw, self.closed_raw, self.source_records, initializer,
         self.initializer_originals, self.initializer_directories, self.previous_ns, self.previous_local) = snapshot
        self.admitted = identity.InitialBootstrapIdentity(*worker)
        self.admission = checked_worker(self.admitted)
        self.history = canonical(self.history_raw)
        self.clock = O.wire.clock_identity(self.history["clock"])
        self.proposal = original_proposal(self.proposal_raw, self.admitted, self.history_raw, self.clock)
        self.profile, self.role = identity.cache_cohort(self.admitted.record)
        self.invocation = self.proposal["serviceTimeBasis"]["invocation"]
        require(self.source_records[-1][1] == self.admitted.original_policy, "SOURCE_POLICY_CHANGED")
        self.session = Path(initialization.producer._path(initializer, self.role))
        self.state, self.home, self.root = self.session / "state", self.session / "state/gradle-home", str(ROOT)
        self.container = files.stage_path(self.session, self.profile, self.role, admitted_raw=self.admitted.record)
        self.restore = self.container / "restore-home"
        pins = {name: pin for name, pin, _provenance in self.initializer_directories}
        self.directories = {name: pins[key] for name, key in zip(DIRECTORY_NAMES, DIRECTORY_KEYS)}
        originals = dict(self.initializer_originals)
        self.context_raw, self.canonical_raw, self.properties_raw = (originals[name] for name in
            ("I/initializer-context.json", "I/state/context.json", "I/state/gradle-home/gradle.properties"))
        context = fields(canonical(self.context_raw), "schema scope job receivingWindowSha256 authoritySha256 "
            "senderSha256 stepSha256 requestSha256 workerIdentitySha256 budgetAcceptance testAcceptance exportSaveAuthority")
        require(type(context["schema"]) is int and context["schema"] == 1 and context["scope"] == INITIAL_CONTEXT_SCOPE and
            context["workerIdentitySha256"] == O.digest(self.admitted.record) and
            context["receivingWindowSha256"] == O.digest(originals["I/receiving-window.json"]) and
            context["requestSha256"] == O.digest(originals["I/canonical-init/request.json"]) and
            context["budgetAcceptance"] == "NOT_ADMITTED" and context["testAcceptance"] == "NOT_PERFORMED" and
            context["exportSaveAuthority"] is False, "INITIAL_CONTEXT")
        for name in ("authoritySha256", "senderSha256", "stepSha256"):
            sha(context[name])
        canonical_context = initialization.producer.parse(self.canonical_raw)
        require(type(canonical_context.get("javaHomes")) is list, "CANONICAL_HOMES")
        self.canonical = initialization.initial_recipient_context_record(self.canonical_raw,
            worker_raw=self.admitted.record, root=self.root, state=str(self.state), role=self.role,
            outer_job=context["job"], homes=tuple(canonical_context["javaHomes"]), policy_raw=self.properties_raw)
        retired = fields(canonical(self.closed_raw), "schema scope clock originalBootDigest primaryResultSha256 "
            "primaryCopySha256 authoritySha256 authorityInventorySha256 workerIdentitySha256 originalProposalSha256 "
            "initializer initializerFilesSha256 inputOwnerClose inputsClosedNs originalPrepWorkEndNs prepDisposition "
            "receivingDisposition currentAuthority budgetAcceptance testAcceptance exportSaveAuthority")
        require(type(retired["schema"]) is int and retired["schema"] == 1 and retired["scope"] == RETIRED_SCOPE and
            retired["clock"] == O.clock_value(self.clock) and retired["originalBootDigest"] == self.history["originalBootDigest"] and
            retired["workerIdentitySha256"] == O.digest(self.admitted.record) and
            retired["originalProposalSha256"] == O.digest(self.proposal_raw) and retired["initializer"] == initializer and
            retired["initializerFilesSha256"] == {name: O.digest(raw) for name, raw in self.initializer_originals} and
            retired["prepDisposition"] == "TERMINALLY_RETIRED" and retired["receivingDisposition"] == "HISTORICAL_NOT_REVIVED" and
            retired["currentAuthority"] == "NEW_PER_USE_REQUIRED" and retired["budgetAcceptance"] == "NOT_ADMITTED" and
            retired["testAcceptance"] == "NOT_PERFORMED" and retired["exportSaveAuthority"] is False and
            O.integer(self.history["originalPreviousNs"]) <= O.integer(retired["inputsClosedNs"]) <= self.previous_ns <
            O.integer(retired["originalPrepWorkEndNs"]), "RETIRED_PREFIX")
        for name in ("primaryResultSha256", "primaryCopySha256", "authoritySha256", "authorityInventorySha256"):
            sha(retired[name])
        retired_input_close(retired["inputOwnerClose"])
        self.parent_scope = STAGING_PARENT_SCOPE

    def unchanged(self):
        require(capture_originals(self.published) == self.snapshot, "INITIAL_INPUT_CHANGED")

    def binding(self):
        return {"scope": INPUT_SCOPE, "workerIdentitySha256": O.digest(self.admitted.record),
            "proposalSha256": O.digest(self.proposal_raw), "historySha256": O.digest(self.history_raw),
            "retiredPrefixSha256": O.digest(self.closed_raw), "clock": O.clock_value(self.clock),
            "originalBootDigest": self.history["originalBootDigest"], "invocation": self.invocation,
            "sourceRecordsSha256": {name: O.digest(raw) for name, raw in self.source_records},
            "initializerContextSha256": O.digest(self.context_raw), "canonicalContextSha256": O.digest(self.canonical_raw),
            "propertiesSha256": O.digest(self.properties_raw), "initializerCheckedNs": self.previous_ns,
            "initializerDirectories": {name: list(pin) for name, pin in self.directories.items()},
            "allInitializerDirectories": {name: {"identity": list(pin), "provenance": provenance}
                for name, pin, provenance in self.initializer_directories},
            "initializerFilesSha256": {name: O.digest(raw) for name, raw in self.initializer_originals},
            "session": str(self.session), "state": str(self.state), "home": str(self.home),
            "container": str(self.container), "restoreHome": str(self.restore)}
