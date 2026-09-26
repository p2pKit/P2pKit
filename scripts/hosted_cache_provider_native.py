#!/usr/bin/env python3
"""Fixed credential-free native helpers for the bootstrap provider Action.

This command is not a workflow, initial-recipient exception or activation.
The current trusted-main bootstrap admission is reused without a fallback.
All stdout is a PRIVATE child pipe, never a runner command/log stream. A helper
return remains provisional until its original child exit/EOF/close is observed.
No provider, network download, credential acquisition or application runs here.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import importlib.util
import math
import os
from pathlib import Path
import sys
import time

SCRIPTS = Path(__file__).absolute().parent
sys.path.insert(0, str(SCRIPTS))
import hosted_cache_provider_prepare as materializer
import hosted_cache_provider_readback as readback

L = materializer.L
B = None
SOURCE_NAME = "provider-source.cjs"
PREPARED_NAME = "provider-prepared.json"
READBACK_NAME = "provider-readback.json"
WORKER_MARGIN_SECONDS = 30  # Inside the old end, not an added retirement budget.
_BASE_CLAIMS = readback.BASE_CLAIMS
_LOOKUP_CLAIMS = readback.LOOKUP_CLAIMS


def _bootstrap():
    global B
    if B is None:
        spec = importlib.util.spec_from_file_location("fixed_provider_bootstrap", SCRIPTS / "run-hosted-cache-bootstrap.py")
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        B = module
    return B


class _Fence:
    """Owner API adapter for the existing provider RAW/LOCAL interval only."""
    def __init__(self, first, issued, end, environment, *, readback_only=False):
        L.require(type(readback_only) is bool, "PROVIDER_NATIVE_FENCE_MODE")
        self.window = L._Window(first, issued, end, end)
        self.environment = environment
        self.clock, self.hard_end = first.clock, end
        # Success-only readback follows the actual supervisor close. It spends
        # the remaining shared final45, not a new allowance. Owner's ordinary
        # end/read/write still check cancellation and original failure state.
        self.work_end = end if readback_only else end - 45 * L.clocks.NS
        self._binding = self.window, environment, self.clock, end, self.work_end

    @property
    def local_end(self):
        return self.window.local_end

    def _local_cap(self, cap):
        # Round the subtracted interval outward, then the resulting deadline
        # inward. This uses the original conversion, never a fresh allowance.
        delta = math.nextafter((self.hard_end - cap) / L.clocks.NS, math.inf)
        return math.nextafter(self.window.local_end - delta, -math.inf)

    def now(self, *, final=False, minimum=0, limit=None):
        L.require(type(final) is bool and
                  (self.window, self.environment, self.clock, self.hard_end, self.work_end) == self._binding,
                  "PROVIDER_NATIVE_FENCE_CHANGED")
        if not final:
            self.environment()
        observed = self.window.check()
        cap = self.hard_end if final else self.work_end
        if limit is not None:
            cap = min(cap, L.clocks.integer(limit))
        L.require(observed >= L.clocks.integer(minimum) and observed < cap and
                  self.window.local_highest < self._local_cap(cap), "PROVIDER_NATIVE_ORIGINAL_END")
        if not final:
            self.environment()
            return self.now(final=True, minimum=observed, limit=cap)
        return observed

    def deadline(self, maximum, *, final=False, limit=None):
        L.require(type(maximum) in (int, float) and math.isfinite(maximum) and maximum > 0,
                  "PROVIDER_NATIVE_MAXIMUM")
        self.now(final=final, limit=limit)
        cap = self.hard_end if final else self.work_end
        if limit is not None:
            cap = min(cap, L.clocks.integer(limit))
        return min(self._local_cap(cap), math.nextafter(self.window.local_highest + maximum, -math.inf))


class _Reader:
    """Only the existing bound-file reader interface on the same live Owner."""
    def __init__(self, owner):
        self.owner = owner

    def end(self, *, new=False):
        return self.owner.end()

    def check(self):
        self.owner.end()

    def acquire(self, label, factory):
        return self.owner.acquire(label, factory)

    def error(self, stage, error):
        self.owner.error(stage, error)

    def close_one(self, value):
        L.require(not self.owner.unknown, "PROVIDER_NATIVE_READER_UNKNOWN")
        self.owner.close_one(value)
        if self.owner.original is not None:
            raise self.owner.original
        L.require(not self.owner.unknown, "PROVIDER_NATIVE_READER_UNKNOWN")


def _claims(phase):
    L.require(phase in ("save", "lookup"), "PROVIDER_NATIVE_PHASE")
    return {name: os.environ.get("P2PKIT_BOOTSTRAP_" + name)
            for name in _BASE_CLAIMS + (_LOOKUP_CLAIMS if phase == "lookup" else ())}


def _descriptor(raw, expected_hash, phase, first, directory):
    """Read old issuance for early denial, NOT native admission or rederivation."""
    L.require(type(raw) is bytes and hashlib.sha256(raw).hexdigest() == expected_hash,
              "PROVIDER_NATIVE_PREPARATION_HASH")
    value = L.transport._parse(raw, materializer.PREPARATION_LIMIT)
    prefix = "SAVE" if phase == "save" else "PROBE"
    L.require(raw == L.files.encoded(value) and value.get("scope") ==
        "BOOTSTRAP_" + prefix + "_PREPARATION_PENDING_ORIGINAL_STEP_RETURN_V1" and
        value.get("directory") == str(directory.path) and value.get("directoryIdentity") == list(directory.identity)
        and value.get("clock") == {"role": first.clock.role, "domain": first.clock.domain,
                                  "ticksPerSecond": first.clock.ticks_per_second}, "PROVIDER_NATIVE_DESCRIPTOR")
    window = value.get("providerWindow")
    L.require(type(window) is dict and set(window) == {"issuedNs", "hardEndNs", "actualProviderStart"} and
              window["actualProviderStart"] == "NOT_OBSERVED", "PROVIDER_NATIVE_WINDOW")
    issued, end = (L.clocks.integer(window[name]) for name in ("issuedNs", "hardEndNs"))
    L.require(issued <= first.nanoseconds < end <= issued + 180 * L.clocks.NS and
              issued + 45 * L.clocks.NS < end, "PROVIDER_NATIVE_ORIGINAL_END")
    contract = L.cache.bootstrap_provider_contract(value["plan"], phase)
    L.require(value.get("providerRequest") == contract["request"] and value["plan"]["role"] == first.clock.role,
              "PROVIDER_NATIVE_REQUEST")
    return value, issued, end, contract


def _graph(owner, fence, phase, claims, first, selection, original_path, event, runner_name,
           prepared_directory, preparation_raw, target):
    """Rederive the fixed graph with the maintained native admission/readers.

    SAVE/PROBE success is never manufactured. Lookup alone consumes the genuine
    preceding save/after-save originals; no later outcome is a preparation input.
    """
    b = _bootstrap()
    session = original_path.with_name(original_path.name + "-productive") / "initializer"
    initializer = owner.open(session)
    handoff_directory = owner.child(initializer, "dependency-save-handoff")
    handoff_raw = owner.read(handoff_directory, "save-handoff.json")
    L.require(b.origin.digest(handoff_raw) == claims["HANDOFF_SHA256"], "PROVIDER_NATIVE_HANDOFF_HASH")
    index = b.origin.parse(handoff_raw)
    proposal_raw = owner.read(handoff_directory, "allocation-proposal.json")
    row = index["blobs"]["allocation-proposal.json"]
    L.require(type(row["bytes"]) is int and row["bytes"] == len(proposal_raw) and
              row["sha256"] == b.origin.digest(proposal_raw), "PROVIDER_NATIVE_PROPOSAL_HASH")
    producer_raw = owner.read(initializer, "producer-function-return.json")
    b._producer_return_record(producer_raw, handoff_raw, claims["PRODUCER_RETURN_SHA256"], first,
                              initializer, handoff_directory)
    admitted, _ = b.admit(owner, fence, target.path / "admission")
    L.require(admitted.original_event == event, "PROVIDER_NATIVE_EVENT_CHANGED")
    owner.write(target, "admission-return.json", owner.admissions[str(target.path / "admission")][2])
    actual_raw, supplied = b._read_save_handoff(owner, initializer, handoff_directory, admitted,
        producer_outcome=claims["PRODUCER_OUTCOME"], expected_sha256=claims["HANDOFF_SHA256"])
    blobs = dict(supplied)
    L.require(actual_raw == handoff_raw and blobs["allocation-proposal.json"] == proposal_raw,
              "PROVIDER_NATIVE_HANDOFF_CHANGED")
    references = []
    reader = _Reader(owner)

    def reference(directory, label, name, *, bound):
        item = index["references"][label]
        L.require(type(item) is dict and set(item) == {"directory", "directoryIdentity", "name", "maximumBytes",
            "bytes", "sha256", "fileBinding", "bindingScope"} and item["directory"] == str(directory.path) and
            item["name"] == name and type(item["maximumBytes"]) is int and item["maximumBytes"] == b.LIMIT and
            type(item["bytes"]) is int and 0 < item["bytes"] <= b.LIMIT and b.staging.cache._sha(item["sha256"]),
            "PROVIDER_NATIVE_REFERENCE")
        b._new_entry_owned(owner, directory, directory.path, item["directoryIdentity"])
        if bound:
            L.require(item["fileBinding"] is not None and item["bindingScope"] == "ORIGINAL_FILE_BINDING",
                      "PROVIDER_NATIVE_REFERENCE_BINDING")
            raw, _ = b.staging._read(reader, directory, name, binding=item["fileBinding"], maximum=item["bytes"])
        else:
            L.require(item["fileBinding"] is None and item["bindingScope"] ==
                "ORIGINAL_DIRECTORY_AND_BYTES_OR_HASH_ONLY_NOT_FILE_IDENTITY", "PROVIDER_NATIVE_REFERENCE_BINDING")
            raw = owner.read(directory, name, item["bytes"])
        L.require(len(raw) == item["bytes"] and b.origin.digest(raw) == item["sha256"], "PROVIDER_NATIVE_REFERENCE_CHANGED")
        references.append((directory, name, item, raw, bound))
        return raw

    service = owner.open(original_path / "service")
    responses = {name: reference(service, "service/" + name, name + ".json", bound=False) for name in ("attempt", "jobs")}
    L.require(index["binding"]["runnerName"] == runner_name, "PROVIDER_NATIVE_RUNNER_CHANGED")
    proposal = b.allocation.validate_proposal(proposal_raw, admitted, responses,
        index["binding"]["invocation"], first.clock, runner_name)
    phase_name = "provider-save" if phase == "save" else "provider-probe"
    L.require(fence.hard_end <= proposal["phaseFencesNs"][phase_name] and
              fence.hard_end <= proposal["proposedJobEndNs"], "PROVIDER_NATIVE_PROPOSAL_END")
    inputs, compiled = b.staging.files.source_inputs(owner, b.ROOT, owner.end(), owner.end)
    profile, role = b.bootstrap.cache_cohort(admitted.record)
    container_path = b.staging.files.stage_path(session, profile, role, admitted_raw=admitted.record)
    container = owner.acquire("provider-stage-container", lambda: b.staging.files.private_root(container_path))
    staging_raw = reference(container, "staging/staging", "staging.json", bound=True)
    deadline = owner.end()
    source = owner.acquire("provider-stage-source", lambda: container.open_directory("restore-home", deadline=deadline))
    stage = b.origin.parse(staging_raw)
    b.staging.files.validate_stage(stage, admitted.record, profile, role, container_path,
                                  container.verify(), source.verify(), inputs)
    plan = b.staging.cache.validate_plan(index["plan"], admitted.record, staging_raw, compiled, inputs,
                                        session=session, profile=profile, role=role, mode="bootstrap")
    b._save_original_inventory(index, blobs, compiled, stage, index["references"]["staging/staging"]["fileBinding"], proposal)
    after_directory = after_raw = after_originals = saved_directory = None
    if phase == "save":
        b._save_preparation_record(preparation_raw, claims["SAVE_PREPARATION_SHA256"], admitted,
            handoff_raw, producer_raw, proposal, first, prepared_directory)
    else:
        after_directory = owner.open(original_path.with_name(original_path.name + "-after-save"))
        saved_directory = owner.open(original_path.with_name(original_path.name + "-save"))
        after_raw, after_originals = b._probe_after_save_records(owner, after_directory, claims["AFTER_SAVE_SHA256"],
            claims, admitted, index, blobs, producer_raw, proposal, first, saved_directory)
        prepared = b._probe_preparation_record(preparation_raw, claims["PROBE_PREPARATION_SHA256"], claims,
            admitted, plan, proposal, first, prepared_directory)
        L.require(b.origin.parse(after_raw)["returnWindow"]["firstNs"] <= prepared["firstNs"],
                  "PROVIDER_NATIVE_PROBE_PREDECESSOR")

    def final_readback():
        final, _ = b.admit(owner, fence, target.path / "final-admission", expected=admitted)
        L.require(final == admitted and b.host_inputs(role) == (selection, original_path, event) and
                  os.environ.get("RUNNER_NAME") == runner_name, "PROVIDER_NATIVE_FINAL_ADMISSION_CHANGED")
        fence.environment()
        b.child_environment(original_path)
        owner.write(target, "final-admission-return.json", owner.admissions[str(target.path / "final-admission")][2])
        L.require(owner.read(handoff_directory, "save-handoff.json") == handoff_raw and
                  owner.read(initializer, "producer-function-return.json") == producer_raw,
                  "PROVIDER_NATIVE_FINAL_ORIGINALS_CHANGED")
        for directory, name, item, raw, bound in references:
            b._new_entry_owned(owner, directory, directory.path, item["directoryIdentity"])
            if bound:
                b.staging._read(reader, directory, name, expected=raw, binding=item["fileBinding"], maximum=len(raw))
            else:
                L.require(owner.read(directory, name) == raw, "PROVIDER_NATIVE_FINAL_REFERENCE_CHANGED")
        if phase == "lookup":
            b._new_entry_owned(owner, after_directory, after_directory.path, b.origin.parse(after_raw)["directoryIdentity"])
            for name, raw in after_originals.items():
                L.require(owner.read(after_directory, name) == raw, "PROVIDER_NATIVE_AFTER_SAVE_CHANGED")
            L.require(owner.read(saved_directory, "save-preparation.json") == after_originals["save-preparation.json"],
                      "PROVIDER_NATIVE_SAVE_PREPARATION_CHANGED")
        fence.now()

    return plan, final_readback


def operate(operation, phase, cancelled, *, node=None, tool_path=None, prepared_sha256=None,
            acknowledgement=None, minimum_ns=None):
    """Three fixed private child operations; no arbitrary path/command/budget."""
    b = _bootstrap()
    L.require(operation in ("window", "prepare", "readback"), "PROVIDER_NATIVE_OPERATION")
    local = time.monotonic()
    first = L.clocks.validate_reading(L.clocks.observe())
    claims = _claims(phase)

    def environment():
        L.require(_claims(phase) == claims and b.origin.wire.TOKEN_ENV not in os.environ and
            not any(name in os.environ for name in (*L.environment.SERVICE_FIELDS, "GH_TOKEN", "GITHUB_TOKEN")),
            "PROVIDER_NATIVE_CREDENTIAL_FREE_CONTEXT")
        L.require(all(type(value) is str and value == "success" for name, value in claims.items() if name.endswith("OUTCOME"))
            and all(type(value) is str and L.re.fullmatch(r"[0-9a-f]{64}", value)
                    for name, value in claims.items() if name.endswith("SHA256")), "PROVIDER_NATIVE_ORIGINAL_CLAIMS")
        b.cancellation(cancelled)

    owner = fence = result = directory = target = None
    failure = None
    try:
        environment()
        L.require(not b.QUARANTINE and not b.query.QUARANTINE and not b.diagnostics._QUARANTINE,
                  "PROVIDER_NATIVE_PRIOR_UNKNOWN")
        selection, original_path, event = b.host_inputs(first.clock.role)
        b.child_environment(original_path)
        runner_name = os.environ.get("RUNNER_NAME")
        # Existing Owner metadata ceiling, immediately shortened by old issuance.
        # It is not a new provider interval, admission or allocation.
        owner = b.Owner(math.nextafter(local + 45, -math.inf), first=first, cancelled=environment)
        suffix, prefix = ("-save", "SAVE") if phase == "save" else ("-probe", "PROBE")
        directory = owner.open(original_path.with_name(original_path.name + suffix))
        filename = "save-preparation.json" if phase == "save" else "probe-preparation.json"
        preparation_raw = owner.read(directory, filename)
        expected_hash = claims[prefix + "_PREPARATION_SHA256"]
        prepared, issued, end, contract = _descriptor(preparation_raw, expected_hash, phase, first, directory)
        fence = _Fence(first, issued, end, environment, readback_only=operation == "readback")
        cap = end if operation == "readback" else end - 45 * L.clocks.NS
        owner.bind(fence, work_limit=cap, final_limit=end)
        fence.now(final=operation == "readback", limit=cap)
        if operation == "window":
            result = {"scope": "PROVIDER_ORIGINAL_WINDOW_PENDING_HELPER_RETURN_V1", "phase": phase,
                "preparationSha256": expected_hash, "directory": str(directory.path),
                "directoryIdentity": list(directory.identity), "bundle": contract["bundle"],
                "clock": b.origin.clock_value(first.clock), "firstNs": str(first.nanoseconds),
                "issuedNs": str(issued), "hardEndNs": str(end), "providerAdmission": "NOT_ESTABLISHED"}
        elif operation == "prepare":
            target = owner.child(directory, "native-preparation", create=True)
            plan, final_readback = _graph(owner, fence, phase, claims, first, selection, original_path, event,
                                         runner_name, directory, preparation_raw, target)
            bundle = owner.read(directory, SOURCE_NAME, contract["bundle"]["bytes"])
            cut = end - WORKER_MARGIN_SECONDS * L.clocks.NS
            value = materializer.materialize(owner, directory, preparation_raw, expected_hash,
                claims[prefix + "_PREPARE_OUTCOME"], phase=phase, plan=plan, bundle_raw=bundle,
                node=node, tool_path=tool_path, worker_cutoff_ns=cut)
            final_readback()
            packet = {"scope": "PROVIDER_NATIVE_PREPARATION_PENDING_HELPER_RETURN_V1", "phase": phase,
                "preparationSha256": expected_hash, "request": value.request.decode("ascii"),
                "bindings": dict(value.bindings), "clockBindings": dict(value.clock_bindings),
                "firstNs": str(first.nanoseconds), "originalClaims": claims,
                "providerExecution": "NOT_PERFORMED", "enclosingActionReturn": "NOT_OBSERVED"}
            raw = owner.write(directory, PREPARED_NAME, packet)
            result = {**packet, "preparedSha256": hashlib.sha256(raw).hexdigest()}
        else:
            L.require(type(prepared_sha256) is str and L.re.fullmatch(r"[0-9a-f]{64}", prepared_sha256) and
                      type(acknowledgement) is bytes, "PROVIDER_NATIVE_READBACK_INPUT")
            raw = owner.read(directory, PREPARED_NAME)
            L.require(hashlib.sha256(raw).hexdigest() == prepared_sha256, "PROVIDER_NATIVE_PREPARED_HASH")
            packet = b.origin.parse(raw)
            L.require(raw == b.origin.encoded(packet) and packet.get("scope") ==
                "PROVIDER_NATIVE_PREPARATION_PENDING_HELPER_RETURN_V1" and packet.get("phase") == phase and
                packet.get("preparationSha256") == expected_hash and packet.get("originalClaims") == claims and
                packet.get("providerExecution") == "NOT_PERFORMED" and packet.get("enclosingActionReturn") == "NOT_OBSERVED",
                "PROVIDER_NATIVE_PREPARED_BINDING")
            request = packet["request"].encode("ascii")
            context, _ = readback.outer._context(request)
            L.require(context["phase"] == phase and context["plan"] == prepared["plan"] and
                int(context["issuedNs"]) == issued and int(context["hardEndNs"]) == end and
                context["directory"] == str(directory.path / "provider") and
                context["home"] == str(directory.path / "provider-home") and
                int(context["firstNs"]) <= L.clocks.integer(minimum_ns) <= first.nanoseconds,
                "PROVIDER_NATIVE_READBACK_CONTEXT")
            provider_directory = owner.child(directory, "provider")
            value = readback.read_success(owner, provider_directory, request, acknowledgement, 0,
                python=str(L._path(sys.executable, first.clock.role)), bindings=packet["bindings"])
            # Actual fixed-file readback stays private; only checked output fields
            # and binding hashes leave this helper. Acceptance is still external.
            retained = owner.write(directory, READBACK_NAME, {"scope": "PROVIDER_NATIVE_READBACK_PENDING_HELPER_RETURN_V1",
                "phase": phase, "preparedSha256": prepared_sha256, "preparationSha256": expected_hash,
                "acknowledgement": acknowledgement.decode("ascii"),
                "acknowledgementSha256": hashlib.sha256(acknowledgement).hexdigest(),
                "python": str(L._path(sys.executable, first.clock.role)),
                "workerRequestSha256": hashlib.sha256(value.worker_request).hexdigest(),
                "outputs": dict(value.provider.outputs), "checkedNs": str(value.checked_ns),
                "originalClaims": claims, "enclosingActionReturn": "NOT_OBSERVED", "providerAcceptance": "NOT_ESTABLISHED"})
            result = {"scope": "PROVIDER_NATIVE_READBACK_PENDING_HELPER_RETURN_V1", "phase": phase,
                "readbackSha256": hashlib.sha256(retained).hexdigest(), "outputs": dict(value.provider.outputs),
                "providerAcceptance": "NOT_ESTABLISHED"}
        L.require(owner.read(directory, filename) == preparation_raw, "PROVIDER_NATIVE_FINAL_PREPARATION_CHANGED")
        L.require(b.host_inputs(first.clock.role) == (selection, original_path, event) and
                  os.environ.get("RUNNER_NAME") == runner_name, "PROVIDER_NATIVE_FINAL_HOST_CHANGED")
        environment()
        b.child_environment(original_path)
        fence.now(final=operation == "readback", limit=cap)
        ledger, errors = owner.resources, owner.errors
        roster = tuple((row, row["label"], row["owner"]) for row in ledger)
    except BaseException as error:
        failure = owner.original if owner is not None and owner.original is not None else error
        if owner is not None:
            try:
                owner.error("provider-native", error)
            except BaseException:
                owner.unknown = True
    finally:
        if owner is not None:
            try:
                owner.close()
                if owner.original is not None:
                    failure = owner.original
            except BaseException as error:
                failure = owner.original if owner.original is not None else failure or error
    if failure is not None:
        raise failure
    L.require(owner.closed and not owner.unknown and not errors and owner.resources is ledger and owner.errors is errors
        and len(ledger) == len(roster) and all(row is old and row["label"] == label and row["owner"] is resource and
            row["attempted"] is row["closed"] is True for row, (old, label, resource) in zip(ledger, roster)) and
        not b.QUARANTINE and not b.query.QUARANTINE and not b.diagnostics._QUARANTINE, "PROVIDER_NATIVE_OWNER_CLOSE")
    result["observedNs"] = str(fence.now(final=True, limit=cap))
    result["ownerClose"] = "KNOWN_RESOURCE_CLOSE_ONLY"
    result["originalHelperReturn"] = "PENDING"
    environment()
    return result, fence, cap


def main():
    try:
        L.require(sys.flags.isolated and sys.flags.no_site and sys.flags.dont_write_bytecode and
            os.environ.get("GITHUB_ACTIONS") == "true" and os.environ.get("RUNNER_ENVIRONMENT") == "github-hosted" and
            os.environ.get("GITHUB_REPOSITORY") == "p2pKit/P2pKit", "PROVIDER_NATIVE_ACTUAL_HOSTED_CALLER")
        parser = argparse.ArgumentParser(description=__doc__)
        parser.add_argument("operation", choices=("window", "prepare", "readback"))
        parser.add_argument("phase", choices=("save", "lookup"))
        parser.add_argument("--node")
        parser.add_argument("--tool-path")
        parser.add_argument("--prepared-sha256")
        parser.add_argument("--acknowledgement")
        parser.add_argument("--minimum-ns")
        args = parser.parse_args()
        ack = None if args.acknowledgement is None else base64.b64decode(args.acknowledgement, validate=True)
        minimum = None if args.minimum_ns is None else L._ns(args.minimum_ns)
        b = _bootstrap()
        b.guarded(lambda cancelled: operate(args.operation, args.phase, cancelled, node=args.node,
            tool_path=args.tool_path, prepared_sha256=args.prepared_sha256, acknowledgement=ack, minimum_ns=minimum))
        return 0
    except BaseException:
        print("CACHE_PROVIDER_NATIVE_NOT_ACCEPTED", file=sys.stderr)
        return 125


if __name__ == "__main__":
    raise SystemExit(main())
