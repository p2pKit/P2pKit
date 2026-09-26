"""Fixed Stage1 productive authority over ONE custody/primary/native graph.

This is not ordinary Admission, a receipt-to-capability adapter or a workflow
activation. Each source-owned use has new source12/native24/source12 originals
and a new known-closed native owner. The only provider sites are public; every
productive and cross-Step site remains private. No credential broker exists.
"""
from __future__ import annotations

from dataclasses import dataclass
import importlib.util
import os
from pathlib import Path
import re
import sys
import time
import uuid

import hosted_initial_recipient_use as U

SCRIPTS = Path(__file__).resolve().parent
ROOT = SCRIPTS.parent
_spec = importlib.util.spec_from_file_location("_initial_recipient_productive_custody",
    SCRIPTS / "run-hosted-initial-recipient-custody.py")
C = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = C
_spec.loader.exec_module(C)
N, B, A, O, I, Q = C.N, C.N.native, C.N.acquisition, C.O, C.I, C.Q
_USE_ATTEMPTS, _USE_RETURNS, _USE_CONSUMED = {}, {}, {}
_CONTEXT_FIELDS = "schema scope site window observed expectedMatch history originalProposal eventSha256 root session " \
    "job inheritedContext sourceReturnSha256 sourceReturnedNs prefixSha256 initializer initializerIdentity " \
    "directoryIdentity budgetAcceptance exportSaveAuthority"
_CREDENTIAL_NAMES = (*U.public.CREDENTIAL_NAMES, "ACTIONS_CACHE_URL")


def require(value, code):
    I.require(value, "INITIAL_PRODUCTIVE_" + code)


def _path(site):
    leaf = U.site_leaf(site)
    kind, primary = N.location()
    require(kind == "worker", "WORKER_ONLY")
    return primary.with_name(primary.name + "-" + leaf)


def _credential_free():
    require(not any(name in os.environ for name in _CREDENTIAL_NAMES), "CREDENTIAL_BOUNDARY")


def _proposal(raw, identity, history, clock):
    """Recheck the ORIGINAL proposal without making fresh service time a basis."""
    value = C.canonical(raw)
    service = value["serviceTimeBasis"]
    _basis, expected = N._worker_time_values(identity, service["service"], clock, service["invocation"])
    require(raw == expected and service["jobStartBasisNs"] == history["originalJobBasisNs"] and
        value["firstUseAt"] == history["firstUseAt"] and value["clock"] == history["clock"] and
        value["budgetAcceptance"] == "NOT_ADMITTED", "ORIGINAL_PROPOSAL_CHANGED")
    return value


def _parent(parent, site):
    """Only fixed native parent registries; never a supplied dictionary/callback."""
    U.site_scope(site)
    if site in U.PRIVATE_SITES:
        import hosted_initial_recipient_productive_adapter as adapter
        binding = adapter.checked_use_parent(parent, site)
        if site in U.PRODUCTIVE_SITES:
            require(C.checked_retired_primary(binding.prefix) is binding.prefix, "PARENT_RETIRED_PREFIX")
    else:
        import hosted_cache_provider_native as provider
        binding = provider.checked_initial_use_parent(parent, site)
    require(type(binding) is U.ParentBinding and binding.parent is parent and binding.site == site and
        type(binding.identity) is N.initial_identity.InitialBootstrapIdentity and
        type(binding.source_records) is tuple and tuple(name for name, _raw in binding.source_records) == N.SOURCE_KEYS and
        all(type(raw) is bytes for _name, raw in binding.source_records), "ORIGINAL_PARENT_BINDING")
    O.clocks.validate_reading(binding.first)
    require(binding.first.nanoseconds < O.integer(binding.work_end_ns) and
        0 <= U.local_value(binding.local_first) < U.local_value(binding.local_work_end) and
        type(binding.original_boot) is str and re.fullmatch(r"[0-9a-f]{64}", binding.original_boot), "PARENT_ORIGINAL_CAP")
    require(binding.initializer == N._receiving_path() and
        tuple(B.directory_identity(list(binding.initializer_identity), binding.first.clock.role)) == binding.initializer_identity,
        "PARENT_ORIGINAL_INITIALIZER")
    history = C.canonical(binding.history)
    _proposal(binding.proposal, binding.identity, history, binding.first.clock)
    require(history["kind"] == "worker" and history["originalBootDigest"] == binding.original_boot and
        history["clock"] == O.clock_value(binding.first.clock), "PARENT_ORIGINAL_HISTORY")
    return binding


def _context(raw, path, first, boot, site, original_seed):
    context = C.fields(C.canonical(raw), _CONTEXT_FIELDS, "PRODUCTIVE_USE_CONTEXT_FIELDS")
    clock, value = U.checked_frame(context["window"])
    require(type(context["schema"]) is int and context["schema"] == 1 and context["scope"] == U.site_scope(site) and
        context["site"] == site == value["site"] and value == original_seed and clock == first.clock and
        value["originalBootDigest"] == boot and value["parentFirstNs"] <= value["firstNs"] <= first.nanoseconds and
        context["root"] == str(ROOT) and context["session"] == str(path) and path == _path(site) and
        context["budgetAcceptance"] == "NOT_ADMITTED" and context["exportSaveAuthority"] is False,
        "USE_CONTEXT_BINDING")
    history = C.fields(context["history"], C._AUTHORITY_HISTORY_FIELDS, "PRODUCTIVE_USE_HISTORY_FIELDS")
    expected_raw = O.encoded(context["expectedMatch"])
    N.initial_identity._match(context["expectedMatch"])
    expected = A.stages.BootstrapMatch(expected_raw)
    observed, _primary, event = N.host_context(context["expectedMatch"]["firstUseAt"])
    require(context["observed"] == observed and observed["kind"] == "worker" and observed["role"] == first.clock.role and
        context["eventSha256"] == O.digest(event) and history["observed"] == observed and
        history["kind"] == "worker" and history["clock"] == O.clock_value(clock) and
        history["originalBootDigest"] == boot and history["firstUseAt"] == observed["firstUseAt"] and
        history["matchSha256"] == O.digest(expected_raw) and history["currentAuthority"] == "NOT_ACQUIRED" and
        context["initializer"] == str(N._receiving_path()), "USE_ACTUAL_SOURCE_AND_HISTORY")
    B.directory_identity(context["initializerIdentity"], first.clock.role)
    B.directory_identity(context["directoryIdentity"], first.clock.role)
    C.digest(context["prefixSha256"])
    C.digest(context["sourceReturnSha256"])
    require(type(context["job"]) is str and re.fullmatch(r"[0-9a-f]{32}", context["job"]) and
        value["firstNs"] <= O.integer(context["sourceReturnedNs"]) < value["workEndNs"], "USE_SOURCE_RETURN")
    inherited = context["inheritedContext"]
    require(type(inherited) is dict and all(type(item) is str for item in inherited.values()) and
        (set(inherited).issubset({"GRADLE_USER_HOME"}) or set(inherited) == set(Q._CONTEXT)), "USE_INHERITED_CONTEXT")
    return context, expected, event


def service_child(scope, context_hash, minimum, original_seed, caps, original_clock, cancelled):
    """Own a genuine fixed private/public HTTP child, no provider credentials."""
    require(scope in (U.PRIVATE_CONTEXT, U.PUBLIC_CONTEXT), "CHILD_ROUTE")
    token = os.environ.pop(O.wire.TOKEN_ENV, None) if scope == U.PRIVATE_CONTEXT else None
    metadata = owner = window = None
    result_raw = None
    failure = None
    links = []
    try:
        local = U.local_value(time.monotonic())
        first = O.clocks.validate_reading(O.clocks.observe())
        first_graph = N._history_graph(first)
        U.checked_seed(original_seed)
        U.phase_caps(original_seed, caps)
        require(original_clock == first.clock and first.nanoseconds >= O.integer(minimum) and
            caps[0] <= minimum < caps[1] and U.site_scope(original_seed["site"]) == scope and callable(cancelled),
            "CHILD_ORIGINAL_LAUNCH")
        boot = C.digest(N.continuity.boot_digest(first.clock.role))
        require(boot == original_seed["originalBootDigest"], "CHILD_ORIGINAL_BOOT")
        _credential_free()
        require(token is None if scope == U.PUBLIC_CONTEXT else
            type(token) is str and re.fullmatch(r"[A-Za-z0-9_.-]{16,4096}", token), "CHILD_CREDENTIAL_ROUTE")
        C.digest(context_hash)

        def current():
            _credential_free()
            N._check_history(first_graph)
            for graph in links:
                N._check_history(graph)
            if metadata is not None:
                metadata.structural()
            if owner is not None:
                owner.check()
            cancelled()
            _credential_free()
            N._check_history(first_graph)
            for graph in links:
                N._check_history(graph)
            if metadata is not None:
                metadata.structural()
            if owner is not None:
                owner.check()

        window = U.UseWindow(first, local, boot, original_seed, current, side="child", caps=caps)
        metadata = C._PrimaryOwner(B.Owner(window.local_end, window, first=first, cancelled=cancelled))
        path = _path(original_seed["site"])
        private = C._private(metadata, path)
        private_pin = tuple(private.identity)
        context_raw = C._read_private(metadata, private, "context.json", B.LIMIT)
        require(O.digest(context_raw) == context_hash, "CHILD_CONTEXT_HASH")
        context, expected, event = _context(context_raw, path, first, boot, original_seed["site"], original_seed)
        require(tuple(context["directoryIdentity"]) == private_pin, "CHILD_DIRECTORY_PIN")
        service = C._private(metadata, path / "service")
        service_pin = tuple(service.identity)
        start_raw = C._read_private(metadata, service, "start.json", B.LIMIT)
        start = C.productive_use_start_fields(start_raw, context_raw, context, path, first.clock)
        inherited = Q._inherited_context()
        require(tuple(start[name] for name in U.PHASE_NAMES) == caps and inherited == start["inheritedContext"] and
            start["startedNs"] <= minimum <= first.nanoseconds < start["workEndNs"], "CHILD_ORIGINAL_START")
        domain = B.processes.ownership_domains(inherited[B.processes.CHAIN_ENV], inherited[B.processes.DOMAINS_ENV])[-1]
        require(domain == {"id": start["invocation"], "job": start["job"], "state": str(path),
            "home": str(path / "control-home")}, "CHILD_ORIGINAL_DOMAIN")
        links.append(N._history_graph(context, start, expected.__dict__, inherited, original_seed, caps))
        metadata_close = metadata.finish()
        metadata_last = window.now()
        # A DISTINCT native owner is created only after the metadata owner's
        # actual close, inside the same first/LOCAL/original parent native WORK.
        owner = C._CustodyOwner(window.local_end, window, first=first, cancelled=cancelled)
        private = owner.open(path)
        require(tuple(private.identity) == private_pin and owner.read(private, "context.json") == context_raw,
            "CHILD_CONTEXT_READBACK")
        service = owner.child(private, "service")
        require(tuple(service.identity) == service_pin and owner.read(service, "start.json") == start_raw,
            "CHILD_START_READBACK")
        supplier = None
        query_failure = None
        try:
            supplier = N.query_owner(owner, window, path / "acquisition-queries")
            N._initial_service_query_git(supplier)
            supplier.native_host_matches_actions()

            def retain(name, raw, *, failed):
                require(name in N.ORIGINAL_KEYS and type(raw) is bytes and type(failed) is bool, "CHILD_ORIGINAL_NAME")
                owner.end(final=failed)
                supplier._write(supplier.private, name + ".bin", raw)
                owner.end(final=failed)

            if scope == U.PRIVATE_CONTEXT:
                match, originals = A.acquire_bootstrap(ROOT, kind="worker", query_runner=supplier,
                    invocation=domain["id"], token=token, retain=retain, fence=window,
                    original_work_end=start["workEndNs"], first_use_at=context["observed"]["firstUseAt"], expected=expected)
            else:
                match, originals = A.acquire_provider_public(ROOT, site=original_seed["site"], query_runner=supplier,
                    invocation=domain["id"], retain=retain, fence=window, original_work_end=start["workEndNs"],
                    first_use_at=context["observed"]["firstUseAt"], expected=expected)
            token = None
            links.append(N._history_graph(match.__dict__, originals))
            acquired = window.now(limit=start["workEndNs"])
            require(type(match) is A.stages.BootstrapMatch and match.record == expected.record and
                type(originals) is tuple and tuple(name for name, _raw in originals) == N.ORIGINAL_KEYS and
                all(type(raw) is bytes for _name, raw in originals) and dict(originals)["event"] == event,
                "CHILD_ORIGINAL_MATCH")
            identity = N.initial_identity.bind_worker_match(match, event_raw=event,
                policy_raw=dict(originals)["candidate_policy_raw"], now=int(time.time()))
            _proposal(O.encoded(context["originalProposal"]), identity, context["history"], first.clock)
        except BaseException as error:
            query_failure = error
        finally:
            token = None
            C._custody_finish_queries(owner, supplier, query_failure)
        returned = window.now(limit=start["workEndNs"])
        queries = owner.open(path / "acquisition-queries")
        session = N.query_session(owner, queries)
        require(all(owner.read(queries, name + ".bin") == raw for name, raw in originals), "CHILD_ORIGINAL_READBACK")
        captured = (context_raw, originals, domain["id"], start["startedNs"], start["workEndNs"])
        service_job = (N._public_provider_service_job if scope == U.PUBLIC_CONTEXT else N._service_job)(captured, first.clock)
        require(list(service_job) == context["history"]["serviceJob"], "CHILD_RUNNER_CONTINUITY")
        current()
        result_raw = owner.write(service, "child-result.json", {"schema": 1,
            "scope": U.PUBLIC_CHILD if scope == U.PUBLIC_CONTEXT else U.PRIVATE_CHILD,
            "contextSha256": context_hash, "startSha256": O.digest(start_raw), "invocation": domain["id"],
            "clock": O.clock_value(first.clock), "bootDigest": boot, "launchMinimumNs": minimum,
            "beganNs": first.nanoseconds, "metadataLastNs": metadata_last, "acquiredNs": acquired,
            "queryReturnedNs": returned, "querySessionSha256": O.digest(session),
            "originalsSha256": {name: O.digest(raw) for name, raw in originals}, "matchSha256": O.digest(match.record),
            "directoryIdentities": {".": list(private_pin), "service": list(service_pin)},
            "metadataClose": C.canonical(metadata_close), "completedNs": window.now(limit=start["workEndNs"]),
            "retirement": "KNOWN", "errors": []})
        current()
        window.now()
    except BaseException as error:
        failure = error
        if owner is not None:
            owner.error("productive-use-child", error)
            failure = owner._anchor().failure
        elif metadata is not None:
            failure = metadata.remember(error)
    finally:
        token = None
        if metadata is not None and not metadata.finished:
            try:
                metadata.finish()
            except BaseException as error:
                if failure is None:
                    failure = error
        if owner is not None:
            if failure is None and owner._anchor().failure is None:
                try:
                    owner.freeze()
                except BaseException as error:
                    owner.error("productive-use-child-roster", error, unknown=True)
            try:
                owner.close()
            except BaseException as error:
                owner.error("productive-use-child-close", error)
            if failure is None and owner._anchor().failure is not None:
                failure = owner._anchor().failure
            if failure is None:
                try:
                    owner.known()
                except BaseException as error:
                    failure = error
    if failure is not None:
        raise failure
    require(owner is not None and window is not None and result_raw is not None, "CHILD_NO_ORIGINAL_RETURN")
    current()
    closed = window.now(limit=start["workEndNs"])
    owner.known()
    return {"schema": 1, "scope": U.PUBLIC_ACK if scope == U.PUBLIC_CONTEXT else U.PRIVATE_ACK,
        "invocation": domain["id"], "terminalSha256": O.digest(result_raw), "clock": O.clock_value(first.clock),
        "closedNs": closed}, window, start["workEndNs"]


@dataclass(frozen=True, repr=False)
class InitialUse:
    """Original closed per-use return, never deserialized or an ordinary lease."""
    parent: object
    site: str
    identity: object
    raw: bytes
    inventory: bytes
    originals: tuple
    path: object


def _read_phase(owner, private, source, phase, window, binding):
    require(type(owner) is C._CustodyOwner and type(phase) is B.OriginalPhase and owner.phase_originals is phase and
        owner.fence is window and any(row["owner"] is private and not row["attempted"] for row in owner.resources),
        "ORIGINAL_NATIVE_PHASE")
    graph = N._history_graph(source, phase)
    path = private.path
    frame_clock, original_seed = U.checked_frame(C.canonical(window.raw))
    context, expected, event = _context(phase.context, path, window._view().bound[0], binding.original_boot,
        binding.site, original_seed)
    require(frame_clock == window.clock and context["history"] == C.canonical(binding.history) and
        context["originalProposal"] == C.canonical(binding.proposal) and
        owner.read(private, "context.json") == phase.context and owner.read(private, "use-window.json") == window.raw,
        "ORIGINAL_CONTEXT_READBACK")
    source_bytes = N.source_readback(owner, path / "source-before", source)
    require(tuple(source_bytes.items()) == binding.source_records and
        context["sourceReturnSha256"] == O.digest(source.raw) and
        context["sourceReturnedNs"] == C.canonical(source.raw)["returnedNs"], "ORIGINAL_SOURCE_READBACK")
    service = owner.child(private, "service")
    require(all(owner.read(service, name) == raw for name, raw in phase.records), "ORIGINAL_NATIVE_READBACK")
    child_raw = owner.read(service, "child-result.json")
    start, row, birth, child, ack = C.productive_use_phase_bytes(phase.context, path, window.clock,
        dict(phase.records), child_raw, tuple(private.identity), tuple(service.identity))
    queries = owner.open(path / "acquisition-queries")
    session = N.query_session(owner, queries)
    originals = tuple((name, owner.read(queries, name + ".bin")) for name in N.ORIGINAL_KEYS)
    raw = dict(originals)
    require(child["querySessionSha256"] == O.digest(session) and
        child["originalsSha256"] == {name: O.digest(blob) for name, blob in originals} and
        child["matchSha256"] == O.digest(raw["match"]) and raw["event"] == event and
        raw["match"] == expected.record and {name: raw[name] for name in N.SOURCE_KEYS} == source_bytes,
        "ORIGINAL_AUTHORITY_READBACK")
    public = binding.site in U.public.SITES
    match, service_time = (N.retained_public_provider_match if public else N.retained_match)(context, raw,
        start["invocation"], window.clock, start["startedNs"], start["workEndNs"])
    captured = (phase.context, originals, start["invocation"], start["startedNs"], start["workEndNs"])
    service_job = (N._public_provider_service_job if public else N._service_job)(captured, window.clock)
    require(match.record == expected.record and list(service_job) == context["history"]["serviceJob"],
        "CURRENT_MATCH_OR_RUNNER_CHANGED")
    identity = N.initial_identity.bind_worker_match(match, event_raw=event, policy_raw=raw["candidate_policy_raw"],
        now=int(time.time()))
    require(N._worker_fields(identity) == N._worker_fields(binding.identity), "CURRENT_IDENTITY_CHANGED")
    minimum = N._service_chain_minimum(window.first, context["sourceReturnedNs"], start, row, birth, child, service_time, ack)
    checked = window.now(minimum=minimum)
    N._check_history(graph)
    owner.check()
    return identity, match, {"phaseSha256": {name: O.digest(blob) for name, blob in phase.records},
        "childSha256": O.digest(child_raw), "querySessionSha256": O.digest(session),
        "originalsSha256": {name: O.digest(blob) for name, blob in originals}, "checkedNs": checked}, \
        captured, (child_raw, session)


def _index(owner, path, window, originals, pending, before, after, phase, captured):
    require(type(originals) is tuple and len(originals) == len(dict(originals)) == 37 and
        owner.phase_originals is phase and owner.initial_sources.get(str(path / "source-before")) is before and
        owner.initial_sources.get(str(path / "source-after")) is after, "USE_INDEX_ORIGINALS")
    available = dict((*originals, ("use-pending.json", pending)))
    data = dict(captured[1])
    indexed, directories = [], [path, path / "control-home", path / "temporary", path / "service"]
    for name, source, session, values in (
        ("source-before", before, before.session, dict(before.records)),
        ("acquisition-queries", None, available["acquisition-queries/session-result.json"], data),
        ("source-after", after, after.session, dict(after.records)),
    ):
        rows, paths = N._gate_query_index(path / name, session, values, source=source)
        indexed.extend(rows)
        directories.extend(paths)
    for name in ("use-window.json", "context.json", "use-pending.json",
        *("service/" + name for name in sorted(B.PHASE_FILES)), "service/child-result.json"):
        raw = available[name]
        maximum = B.ACK_LIMIT if name == "service/stdout.log" else B.STDERR_LIMIT if name == "service/stderr.log" else B.LIMIT
        require(len(raw) <= maximum, "USE_INDEX_RECORD_LIMIT")
        indexed.append((path / name, maximum, len(raw), O.digest(raw)))
    require(len(indexed) == len({target for target, *_rest in indexed}) == 281 and
        len(directories) == len(set(directories)) == 58, "USE_INDEX_COMPLETE_ROSTER")
    targets = {".": path, **{name: path / name for name in
        ("control-home", "temporary", "service", "source-before", "source-after", "acquisition-queries")}}
    pins = N._worker_pins(owner, window.clock.role, targets)
    identities = {name: identity for name, _row, _directory, _path, identity in pins}
    files = []
    for target, maximum, count, checksum in sorted(indexed):
        name = target.relative_to(path).as_posix()
        require(name not in available or (len(available[name]), O.digest(available[name])) == (count, checksum),
            "USE_INDEX_RETAINED_BYTES")
        files.append({"relative": name, "maximum": maximum, "bytes": count, "sha256": checksum,
            "provenance": "ACTUAL_RETAINED_BYTES" if name in available else "ORIGINAL_QUERY_DECLARATION"})
    require(len(identities) == 7 and sum(row["provenance"] == "ACTUAL_RETAINED_BYTES" for row in files) == 38 and
        sum(row["bytes"] for row in files) <= C.MAX_BYTES, "USE_INDEX_BOUNDS")
    dirs = []
    for target in sorted(directories):
        name = "." if target == path else target.relative_to(path).as_posix()
        dirs.append({"relative": name, "identity": None if name not in identities else list(identities[name]),
            "provenance": "ORIGINAL_NATIVE_PIN" if name in identities else "ORIGINAL_QUERY_DECLARATION"})
    raw = O.encoded({"schema": 1, "scope": "INITIAL_RECIPIENT_PER_USE_ORIGINAL_INDEX_V1",
        "site": C.canonical(phase.context)["site"], "root": str(path), "clock": O.clock_value(window.clock),
        "contextSha256": O.digest(phase.context), "pendingSha256": O.digest(pending), "files": files,
        "directories": dirs, "fileCount": len(files), "directoryCount": len(dirs),
        "totalBytes": sum(row["bytes"] for row in files), "copyState": "ORIGINAL_BYTES_NOT_COPIED",
        "exportSaveAuthority": False})
    C.canonical(raw)
    return raw, pins


def acquire_private(parent, site, token):
    require(site in U.PRIVATE_SITES, "PRIVATE_FIXED_SITE")
    try:
        return _acquire(parent, site, token)
    finally:
        token = None


def acquire_public(parent, site):
    require(site in U.public.SITES, "PUBLIC_FIXED_SITE")
    _credential_free()
    return _acquire(parent, site, None)


def _acquire(parent, site, token):
    key = (id(parent), site)
    previous = _USE_ATTEMPTS.get(key)
    if previous is not None:
        previous[0].begin(previous[1])  # Refusal invalidates this original attempt, even if caught by a callback.
        raise O.OriginError("INITIAL_PRODUCTIVE_UNREACHABLE_USE_REENTRY")
    attempts = {}
    entry = C.B.EntryLatch(attempts)
    attempt = entry.begin(attempts)
    state = {"owner": None, "window": None, "consumed": False, "return": None}
    registration = (entry, attempts, attempt, parent, state)
    _USE_ATTEMPTS[key] = registration
    owner = window = result = None
    failure = None
    links, source_links, pins = [], (), ()
    phase_link = None
    try:
        _credential_free()
        require(token is None if site in U.public.SITES else
            type(token) is str and re.fullmatch(r"[A-Za-z0-9_.-]{16,4096}", token), "USE_CREDENTIAL_ROUTE")
        binding = _parent(parent, site)
        links.append(N._history_graph(binding.__dict__, binding.identity.__dict__, binding.first))
        local = U.local_value(time.monotonic())
        first = O.clocks.validate_reading(O.clocks.observe())
        require(first.clock == binding.first.clock and first.nanoseconds >= binding.first.nanoseconds and
            local >= binding.local_first, "USE_PARENT_CHRONOLOGY")
        original_seed = U.seed(site, binding.first.nanoseconds, binding.work_end_ns, first.nanoseconds, binding.original_boot)
        path = _path(site)

        def current():
            entry.check(attempts, attempt)
            require(_USE_ATTEMPTS.get(key) is registration and
                not state["consumed"] and _parent(parent, site) is binding and
                state["owner"] is owner and state["window"] is window, "USE_ORIGINAL_PARENT_CHANGED")
            _credential_free()
            for graph in links:
                N._check_history(graph)
            if owner is not None:
                owner.check()
                require(owner.phase_originals is phase_link and set(owner.initial_sources) ==
                    {name for name, _value in source_links} and all(owner.initial_sources[name] is value
                        for name, value in source_links), "USE_ORIGINAL_LINKS_CHANGED")
            if pins:
                N._check_worker_pins(pins, first.clock.role, closed=owner.closed)
            entry.check(attempts, attempt)

        window = U.UseWindow(first, local, binding.original_boot, original_seed, current, side="parent",
            parent_local_end=binding.local_work_end)
        state["window"] = window
        window.now()
        owner = C._CustodyOwner(window.local_end, window, first=first, cancelled=current)
        state["owner"] = owner
        owner_anchor = owner._anchor()
        private = owner.new(path)
        private_pin = tuple(private.identity)
        window_raw = owner.write(private, "use-window.json", window.raw)
        owner.child(private, "control-home", create=True)
        owner.child(private, "temporary", create=True)
        history = C.canonical(binding.history)
        observed, _root, event = N.host_context(history["firstUseAt"])
        require(observed == history["observed"] and event == binding.identity.original_event, "USE_ACTUAL_CONTEXT")
        before = N.source_queries(owner, window, observed, path / "source-before")
        source_links = ((str(path / "source-before"), before),)
        links.append(N._history_graph(before))
        require(before.records == binding.source_records, "USE_SOURCE_CHANGED")
        current()
        expected_match = C.canonical(binding.identity.record)["initialRecipient"]
        context_raw = owner.write(private, "context.json", {"schema": 1, "scope": U.site_scope(site), "site": site,
            "window": C.canonical(window_raw), "observed": observed, "expectedMatch": expected_match,
            "history": history, "originalProposal": C.canonical(binding.proposal), "eventSha256": O.digest(event),
            "root": str(ROOT), "session": str(path), "job": uuid.uuid4().hex, "inheritedContext": Q._inherited_context(),
            "sourceReturnSha256": O.digest(before.raw), "sourceReturnedNs": C.canonical(before.raw)["returnedNs"],
            "prefixSha256": O.digest(binding.prefix.raw), "initializer": str(binding.initializer),
            "initializerIdentity": list(binding.initializer_identity), "directoryIdentity": list(private_pin),
            "budgetAcceptance": "NOT_ADMITTED", "exportSaveAuthority": False})
        _, phase = N._initial_service_phase(owner, private, context_raw, token, window, before)
        phase_link = phase
        token = None
        links.append(N._history_graph(phase))
        current()
        _read_phase(owner, private, before, phase, window, binding)
        after = N.source_queries(owner, window, observed, path / "source-after")
        source_links = (*source_links, (str(path / "source-after"), after))
        links.append(N._history_graph(after))
        current()
        require(N.source_readback(owner, path / "source-after", after) == dict(before.records), "USE_FINAL_SOURCE_CHANGED")
        identity, match, chain, captured, (child_raw, session) = _read_phase(owner, private, before, phase, window, binding)
        links.append(N._history_graph(identity.__dict__, match.__dict__, chain, captured))
        files = [("use-window.json", window_raw), ("context.json", context_raw),
            ("service/child-result.json", child_raw), ("acquisition-queries/session-result.json", session)]
        files.extend(("service/" + name, raw) for name, raw in phase.records)
        files.extend(("acquisition-queries/" + name + ".bin", raw) for name, raw in captured[1])
        for name, source in (("source-before", before), ("source-after", after)):
            files.extend(((name + "/source-return.json", source.raw), (name + "/session-result.json", source.session)))
            files.extend((name + "/" + key + ".bin", raw) for key, raw in source.records)
        originals = tuple(files)
        pending = owner.write(private, "use-pending.json", {"schema": 1,
            "scope": "INITIAL_RECIPIENT_PER_USE_PENDING_OWNER_CLOSE_V1", "site": site,
            "windowSha256": O.digest(window_raw), "prefixSha256": O.digest(binding.prefix.raw),
            "workerIdentitySha256": O.digest(identity.record), "matchSha256": O.digest(match.record),
            "filesSha256": {name: O.digest(raw) for name, raw in originals}, "originalChain": chain,
            "retainedNs": window.now(), "retirement": "PENDING_OWNER_CLOSE", "exportSaveAuthority": False})
        inventory, pins = _index(owner, path, window, originals, pending, before, after, phase, captured)
        links.append(N._history_graph(originals, tuple(p for _name, _row, _directory, p, _pin in pins),
            tuple(pin for _name, _row, _directory, _path, pin in pins)))
        current()
        before_close = window.now()
        owner.freeze()
    except BaseException as error:
        failure = entry.fail(error)
        if owner is not None:
            owner.error("productive-use", failure)
            failure = owner._anchor().failure
    finally:
        token = None
        if owner is not None:
            try:
                owner.close()
            except BaseException as error:
                owner.error("productive-use-close", error)
            if failure is None and owner._anchor().failure is not None:
                failure = owner._anchor().failure
    try:
        if failure is not None:
            raise failure
        require(owner is not None and owner._anchor() is owner_anchor, "USE_INCOMPLETE")
        owner.known()
        current()
        closed = window.now(minimum=before_close)
        raw = O.encoded({"schema": 1, "scope": U.RETURN_SCOPE, "site": site, "windowSha256": O.digest(window.raw),
            "workerIdentitySha256": O.digest(identity.record), "inventorySha256": O.digest(inventory),
            "pendingSha256": O.digest(pending), "originalChain": chain, "preCloseNs": before_close,
            "closedNs": closed, "resourceCount": len(owner_anchor.frozen), "retirement": "KNOWN_RESOURCE_CLOSE_ONLY",
            "budgetAcceptance": "NOT_ADMITTED", "exportSaveAuthority": False})
        C.canonical(raw)
        all_originals = (*originals, ("use-pending.json", pending))
        result = InitialUse(parent, site, identity, raw, inventory, all_originals, path)
        graph = N._history_graph(result.__dict__, identity.__dict__, all_originals)
        # Include serialization and the actual closed return preparation in
        # the same bounded WORK. No JSON timestamp grants a later use.
        window.now(minimum=closed)
        _USE_RETURNS[id(result)] = (result, parent, site, binding, entry, attempts, attempt, state, owner, owner_anchor,
            window, graph, tuple(links), pins, registration)
        state["return"] = result
        entry.complete(attempts, attempt, result)
        checked_use(result, parent, site)
        return result
    except BaseException as error:
        raise entry.fail(error)


def _checked_use(result, parent, site, *, consumed):
    """Shared immutable original/closed checks, with two fixed lifecycle views."""
    saved = _USE_RETURNS.get(id(result))
    require(type(result) is InitialUse and type(saved) is tuple and saved[0] is result and saved[1] is parent and
        saved[2] == site, "USE_NOT_ORIGINAL_RETURN")
    _, _parent_value, _site, binding, entry, attempts, attempt, state, owner, owner_anchor, window, graph, links, pins, \
        registration = saved
    try:
        entry.returned(attempts, attempt, result)
        require(type(consumed) is bool and _USE_ATTEMPTS.get((id(parent), site)) is registration and
            state["owner"] is owner and state["window"] is window and state["return"] is result and
            state["consumed"] is consumed and result.parent is parent and result.site == site and
            owner._anchor() is owner_anchor and window._view().failure is None,
            "USE_ORIGINAL_RETURN_CHANGED")
        if consumed:
            historical = _USE_CONSUMED.get(id(result))
            require(type(historical) is tuple and len(historical) == 6 and historical[0] is result and
                historical[1] is saved and historical[2] is state and historical[3] is window._view() and
                historical[4] == window.last and historical[5] == window.local_last,
                "USE_CONSUMED_FRONTIER_CHANGED")
        else:
            require(id(result) not in _USE_CONSUMED and _parent(parent, site) is binding,
                "USE_ORIGINAL_PARENT_CHANGED")
        N._check_history(graph)
        for item in links:
            N._check_history(item)
        owner.known()
        N._check_worker_pins(pins, window.clock.role, closed=True)
        if not consumed:
            value = C.canonical(result.identity.record)
            require(value["initialRecipient"]["notBefore"] <= int(time.time()) < value["initialRecipient"]["expiresAt"],
                "USE_CURRENT_POLICY_EXPIRED")
        entry.returned(attempts, attempt, result)
        return result
    except BaseException as error:
        raise entry.fail(error)


def checked_use(result, parent, site):
    """Same-call live receiver/known-close check, not another HTTP acquisition."""
    return _checked_use(result, parent, site, consumed=False)


def checked_consumed_use(result, parent, site):
    """Passive historical provenance ONLY; no old parent/current/RAW revival."""
    return _checked_use(result, parent, site, consumed=True)


def consume_use(result, parent, site):
    """Consume the exact once-only return while its original receiving phase lives."""
    checked_use(result, parent, site)
    saved = _USE_RETURNS[id(result)]
    entry, state, window = saved[4], saved[7], saved[10]
    try:
        require(not state["consumed"], "USE_ALREADY_CONSUMED")
        window.now()
        checked_use(result, parent, site)
        state["consumed"] = True
        _USE_CONSUMED[id(result)] = (result, saved, state, window._view(), window.last, window.local_last)
        checked_consumed_use(result, parent, site)
        return result.identity
    except BaseException as error:
        raise entry.fail(error)


def productive(cancelled):
    """One honest token frame; no crypto or provider Action inherits the token."""
    token = os.environ.pop(O.wire.TOKEN_ENV, None)
    try:
        _credential_free()
        require(type(token) is str and re.fullmatch(r"[A-Za-z0-9_.-]{16,4096}", token), "PRODUCTIVE_READ_TOKEN")
        primary = C.copy_primary("worker", cancelled=cancelled)
        authority = C.custody_authority(primary, token)
        prefix = C.retire_primary_for_productive(primary, authority)
        import hosted_initial_recipient_productive_adapter as adapter
        pending = adapter.produce(prefix, token, cancelled)
        completed = adapter.complete_productive_handoff(pending, prefix)
        result = adapter.checked_productive_handoff(completed, prefix)
        return result.public_result, result.fence, result.hard_end_ns
    finally:
        token = None


def step(command, cancelled):
    """Four fixed private Step routes; never a provider/service credential alias."""
    token = os.environ.pop(O.wire.TOKEN_ENV, None)
    try:
        _credential_free()
        require(type(token) is str and re.fullmatch(r"[A-Za-z0-9_.-]{16,4096}", token), "STEP_READ_TOKEN")
        import hosted_initial_recipient_productive_adapter as adapter
        operations = {"prepare-save": adapter.prepare_save, "after-save": adapter.after_save,
            "prepare-probe": adapter.prepare_probe, "after-probe": adapter.after_probe}
        require(type(command) is str and command in operations and callable(cancelled), "STEP_FIXED_ROUTE")
        return operations[command](token, cancelled)
    finally:
        token = None
