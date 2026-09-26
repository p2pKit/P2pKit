"""Read the fixed ACK-bound provider originals under an existing native Owner.

This is a success-only readback, not runner/source admission or cache acceptance.
The caller must first observe the original supervisor's successful exit/close,
then supply a NEW Owner whose RAW/local fences still end at the original end.
No failed, incomplete or cancelled bridge result permits this read. The borrowed
owner still needs its own known close and the enclosing Action/runner return.
No provider output or path-bearing original is suitable for public logs.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import os

import hosted_cache_provider_clock as clock_source
import hosted_cache_provider_launch as launch
import hosted_cache_provider_supervisor_return as outer
import hosted_initial_recipient_before as initial_records
import hosted_initial_recipient_use as initial_use


ACTION_FILES = ("provider-prepared.json", "provider-readback.json")
INITIAL_USE_FILES = ("initial-use-chain.json", "begin-use.json", "begin-use-index.json",
                     "final-use.json", "final-use-index.json")
BASE_CLAIMS = ("PRODUCER_OUTCOME", "HANDOFF_SHA256", "PRODUCER_RETURN_SHA256",
               "SAVE_PREPARE_OUTCOME", "SAVE_PREPARATION_SHA256")
LOOKUP_CLAIMS = ("SAVE_OUTCOME", "SAVE_READBACK_SHA256", "AFTER_SAVE_OUTCOME", "AFTER_SAVE_SHA256",
                 "PROBE_PREPARE_OUTCOME", "PROBE_PREPARATION_SHA256")


def validate_action_return(originals, preparation_raw, claims, first, *, phase, outputs):
    """Historical trusted-main entry; never accepts an initial descriptor."""
    return _validate_action_return("trusted-main", originals, preparation_raw, claims, first, phase=phase, outputs=outputs)


def validate_initial_action_return(originals, preparation_raw, claims, first, *, phase, outputs, use_originals):
    """Historical initial-only entry; neither a fresh use nor hosted admission."""
    _validate_action_return("initial-recipient", originals, preparation_raw, claims, first,
        phase=phase, outputs=outputs)
    validate_initial_use_chain(use_originals, originals["provider-prepared.json"], preparation_raw, first, phase=phase)


def _validate_action_return(origin_kind, originals, preparation_raw, claims, first, *, phase, outputs):
    """Bind two retained metadata files to the actual preceding Action outputs.

    The trusted sequential caller supplies original step outcome/hash/outputs
    and its earliest post-Action RAW observation, then must complete its existing
    fresh admission and full descriptor/plan validation. This is supplied historical
    consistency, NOT native-file reread, receiving-owner close, current source
    admission or provider/cache qualification. Do not revive an old Owner or
    recompute a provider allowance from this receiving step's start.
    """
    launch.require(origin_kind in ("trusted-main", "initial-recipient") and phase in ("save", "lookup"),
        "PROVIDER_ACTION_RETURN_PHASE")
    scope_prefix = "BOOTSTRAP_" if origin_kind == "trusted-main" else "INITIAL_RECIPIENT_BOOTSTRAP_"
    native_prefix = "" if origin_kind == "trusted-main" else "INITIAL_RECIPIENT_"
    extra = set() if origin_kind == "trusted-main" else {"initialUseChainSha256"}
    prefix = "SAVE" if phase == "save" else "PROBE"
    input_names = BASE_CLAIMS + (LOOKUP_CLAIMS if phase == "lookup" else ())
    launch.require(type(claims) is dict and set(claims) == set(input_names) |
        {prefix + "_OUTCOME", prefix + "_READBACK_SHA256"} and
        all(type(value) is str and (value == "success" if name.endswith("OUTCOME") else
            launch.re.fullmatch(r"[0-9a-f]{64}", value)) for name, value in claims.items()),
        "PROVIDER_ACTION_RETURN_ORIGINAL_CLAIMS")
    launch.require(type(originals) is dict and set(originals) == set(ACTION_FILES),
                   "PROVIDER_ACTION_RETURN_FILE_ROSTER")
    prepared_raw, raw = (originals[name] for name in ACTION_FILES)
    prepared = launch.transport._parse(prepared_raw, 16384)
    value = launch.transport._parse(raw, 16384)
    descriptor = launch.transport._parse(preparation_raw, 2 * 1024 * 1024)
    launch.require(raw == launch.files.encoded(value) and prepared_raw == launch.files.encoded(prepared) and
        preparation_raw == launch.files.encoded(descriptor) and
        hashlib.sha256(raw).hexdigest() == claims[prefix + "_READBACK_SHA256"] and
        hashlib.sha256(preparation_raw).hexdigest() == claims[prefix + "_PREPARATION_SHA256"],
        "PROVIDER_ACTION_RETURN_ORIGINAL_HASH")
    launch.require(set(value) == {"scope", "phase", "preparedSha256", "preparationSha256", "acknowledgement",
        "acknowledgementSha256", "python", "workerRequestSha256", "outputs", "checkedNs", "originalClaims",
        "enclosingActionReturn", "providerAcceptance"} | extra and
        value["scope"] == native_prefix + "PROVIDER_NATIVE_READBACK_PENDING_HELPER_RETURN_V1" and value["phase"] == phase and
        value["enclosingActionReturn"] == "NOT_OBSERVED" and value["providerAcceptance"] == "NOT_ESTABLISHED",
        "PROVIDER_ACTION_RETURN_READBACK_RECORD")
    launch.require(set(prepared) == {"scope", "phase", "preparationSha256", "request", "bindings", "clockBindings",
        "firstNs", "originalClaims", "providerExecution", "enclosingActionReturn"} | extra and
        prepared["scope"] == native_prefix + "PROVIDER_NATIVE_PREPARATION_PENDING_HELPER_RETURN_V1" and prepared["phase"] == phase and
        prepared["providerExecution"] == "NOT_PERFORMED" and prepared["enclosingActionReturn"] == "NOT_OBSERVED" and
        value["preparedSha256"] == hashlib.sha256(prepared_raw).hexdigest() and
        value["preparationSha256"] == prepared["preparationSha256"] == claims[prefix + "_PREPARATION_SHA256"],
        "PROVIDER_ACTION_RETURN_PREPARED_RECORD")
    if extra:
        launch.require(type(prepared["initialUseChainSha256"]) is str and
            launch.re.fullmatch(r"[0-9a-f]{64}", prepared["initialUseChainSha256"]) and
            prepared["initialUseChainSha256"] == value["initialUseChainSha256"],
            "PROVIDER_ACTION_RETURN_INITIAL_USE_CHAIN")
    original_claims = {name: claims[name] for name in input_names}
    launch.require(launch.files.encoded(value["originalClaims"]) == launch.files.encoded(original_claims) ==
        launch.files.encoded(prepared["originalClaims"]), "PROVIDER_ACTION_RETURN_PREDECESSOR")
    launch.require(type(prepared["request"]) is str and prepared["request"].isascii() and
        type(value["acknowledgement"]) is str and value["acknowledgement"].isascii(),
        "PROVIDER_ACTION_RETURN_ORIGINAL_BYTES")
    request, acknowledgement = prepared["request"].encode("ascii"), value["acknowledgement"].encode("ascii")
    context, _ = outer._context(request)
    ack = outer.read_ack(acknowledgement, request, 0)
    launch.require(ack.kind == ack.provider_kind == "success" and ack.worker_exit_code == 0 and
        value["acknowledgementSha256"] == hashlib.sha256(acknowledgement).hexdigest() and
        value["workerRequestSha256"] == ack.worker_request_sha256, "PROVIDER_ACTION_RETURN_ACK_BINDING")
    launch.clocks.validate_reading(first)
    role, clock = context["role"], first.clock
    launch.require(clock == launch.clocks.ClockIdentity(role, launch.clocks.DOMAINS[role], context["frequency"]),
                   "PROVIDER_ACTION_RETURN_CLOCK")
    directory = launch._path(descriptor["directory"], role)
    launch._identity(descriptor["directoryIdentity"], role)
    launch._path(value["python"], role)  # Original lexical spelling retained privately for later custody.
    launch.require(descriptor["scope"] == scope_prefix + prefix + "_PREPARATION_PENDING_ORIGINAL_STEP_RETURN_V1" and
        launch.files.encoded(descriptor["clock"]) == launch.files.encoded({"role": role, "domain": clock.domain,
            "ticksPerSecond": clock.ticks_per_second}) and
        context["phase"] == phase and context["directory"] == str(directory / "provider") and
        context["home"] == str(directory / "provider-home") and
        launch.files.encoded(context["plan"]) == launch.files.encoded(descriptor["plan"]) and
        descriptor["planSha256"] == hashlib.sha256(launch.files.encoded(context["plan"])).hexdigest() and
        prepared["firstNs"] == context["firstNs"], "PROVIDER_ACTION_RETURN_DESCRIPTOR")
    window = descriptor["providerWindow"]
    launch.require(type(window) is dict and set(window) == {"issuedNs", "hardEndNs", "actualProviderStart"} and
        window["actualProviderStart"] == "NOT_OBSERVED" and
        launch.clocks.integer(window["issuedNs"]) == launch._ns(context["issuedNs"]) and
        launch.clocks.integer(window["hardEndNs"]) == launch._ns(context["hardEndNs"]) and
        launch._ns(context["firstNs"]) <= ack.observed_ns <= launch._ns(value["checkedNs"]) <=
        first.nanoseconds < window["hardEndNs"], "PROVIDER_ACTION_RETURN_ORIGINAL_END")
    for name, names in (("bindings", launch.worker_source.outer_names(role)), ("clockBindings", clock_source.roster(role))):
        bound = prepared[name]
        launch.require(type(bound) is dict and set(bound) == set(names) and all(type(digest) is str and
            launch.re.fullmatch(r"[0-9a-f]{64}", digest) for digest in bound.values()),
            "PROVIDER_ACTION_RETURN_SOURCE_BINDINGS")
    launch.require(all(prepared["bindings"].get(name, digest) == digest
        for name, digest in prepared["clockBindings"].items()), "PROVIDER_ACTION_RETURN_SOURCE_BINDINGS")
    expected_names = set() if phase == "save" else {"cache-primary-key", "cache-matched-key", "cache-hit"}
    launch.require(type(outputs) is dict and set(outputs) == expected_names and
        all(type(item) is str and len(item) <= 512 and all(32 <= ord(char) < 127 for char in item)
            for item in outputs.values()) and launch.files.encoded(value["outputs"]) == launch.files.encoded(outputs),
        "PROVIDER_ACTION_RETURN_ORIGINAL_OUTPUTS")


def _initial_record(raw):
    value = launch.transport._parse(raw, 2 * 1024 * 1024)
    launch.require(raw == launch.files.encoded(value), "PROVIDER_INITIAL_USE_CANONICAL")
    return value


def _initial_use_index(index, root, site, window, returned):
    """Exact index DATA roster; complete original native rereads remain mandatory."""
    initial_use.site_scope(site)
    _clock, original = initial_use.checked_frame(window)
    launch.require(original["site"] == site, "PROVIDER_INITIAL_USE_INDEX_SITE")
    launch.require(type(index) is dict and set(index) == {"schema", "scope", "site", "root", "clock",
        "contextSha256", "pendingSha256", "files", "directories", "fileCount", "directoryCount", "totalBytes",
        "copyState", "exportSaveAuthority"} and type(index["schema"]) is int and index["schema"] == 1 and
        index["scope"] == "INITIAL_RECIPIENT_PER_USE_ORIGINAL_INDEX_V1" and index["site"] == site and
        index["root"] == str(root) and index["clock"] == window["clock"] and
        index["copyState"] == "ORIGINAL_BYTES_NOT_COPIED" and index["exportSaveAuthority"] is False and
        type(index["files"]) is list and type(index["directories"]) is list and
        type(index["fileCount"]) is int and index["fileCount"] == len(index["files"]) == 281 and
        type(index["directoryCount"]) is int and index["directoryCount"] == len(index["directories"]) == 58,
        "PROVIDER_INITIAL_USE_INDEX")
    directories = {}
    for row in index["directories"]:
        launch.require(type(row) is dict and set(row) == {"relative", "identity", "provenance"} and
            type(row["relative"]) is str and row["relative"] not in directories, "PROVIDER_INITIAL_USE_DIRECTORIES")
        directories[row["relative"]] = row
    pinned = {".", "control-home", "temporary", "service", "source-before", "source-after", "acquisition-queries"}
    expected_directories = set(pinned)
    available = {"use-window.json", "context.json", "use-pending.json", "service/child-result.json"}
    available.update("service/" + name for name in initial_records.PHASE_FILES)
    query_files = set()
    for section, count in (("source-before", 12), ("acquisition-queries", 24), ("source-after", 12)):
        expected_directories.add(section + "/query-home")
        children = {name for name in directories if launch.re.fullmatch(section + r"/query-[0-9a-f]{32}", name)}
        launch.require(len(children) == count, "PROVIDER_INITIAL_USE_QUERY_ROSTER")
        expected_directories.update(children)
        query_files.update(name + "/" + leaf for name in children for leaf in initial_records.QUERY_FILES)
        query_files.add(section + "/owner.json")
        keys = initial_records.ORIGINAL_KEYS if section == "acquisition-queries" else initial_records.SOURCE_KEYS
        available.update(section + "/" + name + ".bin" for name in keys)
        available.add(section + "/session-result.json")
        if section != "acquisition-queries":
            available.add(section + "/source-return.json")
    launch.require(set(directories) == expected_directories and len(available) == 38 and
        list(directories) == sorted(directories), "PROVIDER_INITIAL_USE_EXACT_ROSTER")
    identities = []
    for name, row in directories.items():
        if name in pinned:
            identities.append(launch._identity(row["identity"], window["clock"]["role"]))
            launch.require(row["provenance"] == "ORIGINAL_NATIVE_PIN", "PROVIDER_INITIAL_USE_ORIGINAL_PIN")
        else:
            launch.require(row["identity"] is None and row["provenance"] == "ORIGINAL_QUERY_DECLARATION",
                "PROVIDER_INITIAL_USE_DECLARED_DIRECTORY")
    launch.require(len(set(identities)) == len(pinned), "PROVIDER_INITIAL_USE_DIRECTORY_ALIAS")
    files = {}
    for row in index["files"]:
        launch.require(type(row) is dict and set(row) == {"relative", "maximum", "bytes", "sha256", "provenance"} and
            type(row["relative"]) is str and row["relative"] not in files and type(row["maximum"]) is int and
            type(row["bytes"]) is int and 0 <= row["bytes"] <= row["maximum"] <= 2 * 1024 * 1024 and
            row["maximum"] > 0 and type(row["sha256"]) is str and launch.re.fullmatch(r"[0-9a-f]{64}", row["sha256"]) and
            (row["bytes"] != 0 or row["sha256"] == hashlib.sha256(b"").hexdigest()), "PROVIDER_INITIAL_USE_FILE_ROW")
        name = row["relative"]
        # Fixed top-level/per-session maxima are knowable from this roster.
        # Query stdout's exact slot-dependent limit is checked against its
        # retained original session by the complete original reader, not by
        # lexically sorting the random query ids into an invented order.
        if name == "service/stdout.log":
            maximum = 16384
        elif name == "service/stderr.log":
            maximum = 65536
        elif "/query-" in name and name.endswith("/stderr.log"):
            maximum = 4096
        elif name.startswith(("source-before/", "source-after/", "acquisition-queries/")) and \
                not name.endswith(("/session-result.json", "/source-return.json", "/stdout.log")):
            maximum = max(1, row["bytes"])
        elif name in available:
            maximum = 2 * 1024 * 1024
        else:
            maximum = row["maximum"]
        launch.require(row["maximum"] == maximum, "PROVIDER_INITIAL_USE_FIXED_MAXIMUM")
        launch.require(row["provenance"] == ("ACTUAL_RETAINED_BYTES" if name in available else
            "ORIGINAL_QUERY_DECLARATION"), "PROVIDER_INITIAL_USE_FILE_PROVENANCE")
        files[name] = row
    launch.require(set(files) == available | query_files and list(files) == sorted(files) and
        type(index["totalBytes"]) is int and index["totalBytes"] == sum(row["bytes"] for row in files.values()) and
        index["totalBytes"] <= 512 * 1024 * 1024 and
        files["use-window.json"]["sha256"] == returned["windowSha256"] and
        files["context.json"]["sha256"] == index["contextSha256"] and
        files["use-pending.json"]["sha256"] == index["pendingSha256"] == returned["pendingSha256"],
        "PROVIDER_INITIAL_USE_INDEX_BINDING")
    chain = returned["originalChain"]
    launch.require(type(chain) is dict and set(chain) == {"phaseSha256", "childSha256", "querySessionSha256",
        "originalsSha256", "checkedNs"} and type(chain["phaseSha256"]) is dict and
        set(chain["phaseSha256"]) == set(initial_records.PHASE_FILES) and type(chain["originalsSha256"]) is dict and
        set(chain["originalsSha256"]) == set(initial_records.ORIGINAL_KEYS) and
        all(files["service/" + name]["sha256"] == digest for name, digest in chain["phaseSha256"].items()) and
        all(files["acquisition-queries/" + name + ".bin"]["sha256"] == digest
            for name, digest in chain["originalsSha256"].items()) and
        files["service/child-result.json"]["sha256"] == chain["childSha256"] and
        files["acquisition-queries/session-result.json"]["sha256"] == chain["querySessionSha256"],
        "PROVIDER_INITIAL_USE_NATIVE_INDEX_BINDING")


def validate_initial_use_chain(originals, prepared_raw, preparation_raw, first, *, phase):
    """Five actual retained files' DATA, not a recreated owner or fresh grant.

    The fixed caller must read these exact files under its current native owner
    and verify that owner's close. The complete281-file episodes are still
    required by final productive custody;38 available blobs are NOT full copy.
    """
    launch.require(phase in ("save", "lookup") and type(originals) is dict and set(originals) == set(INITIAL_USE_FILES),
        "PROVIDER_INITIAL_USE_FILES")
    launch.clocks.validate_reading(first)
    packet, descriptor = _initial_record(prepared_raw), _initial_record(preparation_raw)
    chain = _initial_record(originals["initial-use-chain.json"])
    prefix = "SAVE" if phase == "save" else "PROBE"
    launch.require(packet.get("scope") == "INITIAL_RECIPIENT_PROVIDER_NATIVE_PREPARATION_PENDING_HELPER_RETURN_V1" and
        packet.get("phase") == phase and descriptor.get("scope") == "INITIAL_RECIPIENT_BOOTSTRAP_" + prefix +
            "_PREPARATION_PENDING_ORIGINAL_STEP_RETURN_V1" and
        packet.get("initialUseChainSha256") == hashlib.sha256(originals["initial-use-chain.json"]).hexdigest() and
        packet.get("preparationSha256") == hashlib.sha256(preparation_raw).hexdigest(), "PROVIDER_INITIAL_USE_PACKET")
    launch.require(type(chain) is dict and set(chain) == {"schema", "scope", "phase", "clock", "originalBootDigest",
        "helperFirstNs", "helperWorkEndNs", "providerIssuedNs", "providerHardEndNs", "handoffSha256",
        "producerReturnSha256", "preparationSha256", "workerIdentitySha256", "directory", "directoryIdentity",
        "source", "github", "materializedNs", "uses", "checkedNs", "helperOwnerClose", "providerExecution",
        "exportSaveAuthority"} and type(chain["schema"]) is int and chain["schema"] == 1 and
        chain["scope"] == "INITIAL_RECIPIENT_PROVIDER_ORIGINAL_USE_CHAIN_V1" and chain["phase"] == phase and
        chain["helperOwnerClose"] == "PENDING_NOT_OBSERVABLE_BY_THIS_FILE" and
        chain["providerExecution"] == "NOT_PERFORMED" and chain["exportSaveAuthority"] is False and
        chain["clock"] == descriptor["clock"] == {"role": first.clock.role, "domain": first.clock.domain,
            "ticksPerSecond": first.clock.ticks_per_second}, "PROVIDER_INITIAL_USE_CHAIN")
    for name in ("originalBootDigest", "handoffSha256", "producerReturnSha256", "preparationSha256", "workerIdentitySha256"):
        launch.require(type(chain[name]) is str and launch.re.fullmatch(r"[0-9a-f]{64}", chain[name]),
            "PROVIDER_INITIAL_USE_DIGEST")
    directory = launch._path(descriptor["directory"], first.clock.role)
    launch._identity(chain["directoryIdentity"], first.clock.role)
    suffix = "-save" if phase == "save" else "-probe"
    launch.require(directory.name.endswith(suffix) and chain["directory"] == str(directory / "native-preparation") and
        chain["handoffSha256"] == packet["originalClaims"]["HANDOFF_SHA256"] and
        chain["producerReturnSha256"] == packet["originalClaims"]["PRODUCER_RETURN_SHA256"] and
        chain["preparationSha256"] == packet["preparationSha256"] and
        all(chain[name] == descriptor["plan"][name] for name in ("source", "github")), "PROVIDER_INITIAL_USE_BINDING")
    root = directory.with_name(directory.name.removesuffix(suffix))
    began, work, issued, end, materialized, checked = (launch.clocks.integer(chain[name]) for name in
        ("helperFirstNs", "helperWorkEndNs", "providerIssuedNs", "providerHardEndNs", "materializedNs", "checkedNs"))
    launch.require(began == launch._ns(packet["firstNs"]) and issued == descriptor["providerWindow"]["issuedNs"] and
        end == descriptor["providerWindow"]["hardEndNs"] and issued <= began <= materialized <= checked < work ==
        min(began + 45 * launch.clocks.NS, end - 45 * launch.clocks.NS) and
        issued + 45 * launch.clocks.NS < end <= issued + 180 * launch.clocks.NS and
        type(chain["uses"]) is list and len(chain["uses"]) == 2, "PROVIDER_INITIAL_USE_HELPER45")
    previous = began
    for number, edge in enumerate(("begin", "final")):
        use = chain["uses"][number]
        site = ("provider-save" if phase == "save" else "provider-probe") + "/native-prepare/" + edge
        launch.require(type(use) is dict and set(use) == {"site", "root", "window", "returnSha256", "inventorySha256"} and
            use["site"] == site and use["root"] == str(root.with_name(root.name + "-" + initial_use.site_leaf(site))) and
            use["returnSha256"] == hashlib.sha256(originals[edge + "-use.json"]).hexdigest() and
            use["inventorySha256"] == hashlib.sha256(originals[edge + "-use-index.json"]).hexdigest(),
            "PROVIDER_INITIAL_USE_ORIGINAL_EPISODE")
        clock, window = initial_use.checked_frame(use["window"])
        launch.require(clock == first.clock and window["site"] == site and window["parentFirstNs"] == began and
            window["parentWorkEndNs"] == work and window["originalBootDigest"] == chain["originalBootDigest"],
            "PROVIDER_INITIAL_USE_ORIGINAL_PARENT")
        returned = _initial_record(originals[edge + "-use.json"])
        launch.require(type(returned) is dict and set(returned) == {"schema", "scope", "site", "windowSha256",
            "workerIdentitySha256", "inventorySha256", "pendingSha256", "originalChain", "preCloseNs", "closedNs",
            "resourceCount", "retirement", "budgetAcceptance", "exportSaveAuthority"} and
            type(returned["schema"]) is int and returned["schema"] == 1 and returned["scope"] == initial_use.RETURN_SCOPE and
            returned["site"] == site and returned["windowSha256"] == hashlib.sha256(launch.files.encoded(use["window"])).hexdigest() and
            returned["workerIdentitySha256"] == chain["workerIdentitySha256"] and
            returned["inventorySha256"] == use["inventorySha256"] and returned["retirement"] == "KNOWN_RESOURCE_CLOSE_ONLY" and
            returned["budgetAcceptance"] == "NOT_ADMITTED" and returned["exportSaveAuthority"] is False and
            type(returned["resourceCount"]) is int and returned["resourceCount"] > 0, "PROVIDER_INITIAL_USE_RETURN")
        index = _initial_record(originals[edge + "-use-index.json"])
        _initial_use_index(index, launch._path(use["root"], first.clock.role), site, use["window"], returned)
        read, preclose, closed = (launch.clocks.integer(value) for value in
            (returned["originalChain"]["checkedNs"], returned["preCloseNs"], returned["closedNs"]))
        launch.require(previous <= window["firstNs"] <= read <= preclose <= closed < window["workEndNs"] and
            closed <= (materialized if number == 0 else checked), "PROVIDER_INITIAL_USE_ORDER")
        previous = materialized
    return chain


@dataclass(frozen=True, repr=False)
class ProviderReadback:
    provider: launch.transport.TransportedProvider = field(repr=False)
    acknowledgement: outer.Acknowledgement = field(repr=False)
    worker_request: bytes = field(repr=False)
    originals: tuple = field(repr=False)
    checked_ns: int
    scope: str = "PROVIDER_ORIGINAL_READBACK_PENDING_OWNER_CLOSE_V1"
    enclosing_owner_close: str = "NOT_OBSERVED"
    original_action_outcome: str = "NOT_OBSERVED"
    provider_acceptance: str = "NOT_ESTABLISHED"


def _worker_request(native, request, ack, python, bindings):
    """Recover the actual retained argv token; never reconstruct a worker frame."""
    context, _ = outer._context(request)
    role = context["role"]
    value = launch.transport._parse(native, outer.NATIVE_BYTES)
    backend, api, mode = (("windows-job-list-suspended", "CreateProcessW", "caller-owned-native-files")
        if role == "windows-x64" else
        ("linux-proc-pidfd" if role == "linux-x64" else "darwin-libproc-audit-token",
         "subprocess.Popen", "caller-owned-files"))
    launch.require(value.get("backend") == backend and value.get("job") == context["job"] and
        value.get("invocation") == context["outerId"] and value.get("discoveryErrors") == [] and
        type(value.get("launches")) is list and len(value["launches"]) == 1, "PROVIDER_READBACK_NATIVE_RECORD")
    record = value["launches"][0]
    argv = record.get("requestedArgv") if type(record) is dict else None
    launch.require(type(argv) is list and len(argv) == 7 and all(type(arg) is str for arg in argv) and
        argv[:5] == [python, "-I", "-B", "-S", str(launch.SCRIPTS / "hosted_cache_provider_worker.py")] and
        record.get("resolvedArgv") == argv and record.get("api") == api and record.get("created") is True and
        type(record.get("pid")) is int and record["pid"] > 0 and
        record.get("cwd") == str(launch.SCRIPTS.parent) and record.get("outputMode") == mode,
        "PROVIDER_READBACK_NATIVE_LAUNCH")
    launch._path(python, role)
    if role == "windows-x64":
        launch.require(record.get("resumed") is True and record.get("batch") is False and
            record.get("applicationName") == python and
            record.get("commandLine") == launch.subprocess.list2cmdline(argv), "PROVIDER_READBACK_NATIVE_FRAMING")
    else:
        launch.require(record.get("shell") is False and record.get("executable") == python,
                       "PROVIDER_READBACK_NATIVE_FRAMING")
    roster = launch.worker_source.names(role)
    launch.require(type(bindings) is dict and set(bindings) == set(launch.worker_source.outer_names(role)),
                   "PROVIDER_READBACK_SOURCE_ROSTER")
    sources = {name: bindings[name] for name in roster}
    launch.require(all(type(value) is str and launch.re.fullmatch(r"[0-9a-f]{64}", value)
                       for value in bindings.values()) and argv[5] == launch._json(sources),
                   "PROVIDER_READBACK_SOURCE_BINDING")
    raw = argv[6].encode("ascii")
    frame, digest = launch.transport._context(raw)
    launch._frame(frame)
    launch.require(digest == ack.worker_request_sha256 and all(frame.get(name) == value
        for name, value in context.items() if name not in ("schema", "firstNs")), "PROVIDER_READBACK_WORKER_REQUEST")
    return raw


def read_success(owner, directory, request, acknowledgement, supervisor_exit, *, python, bindings):
    """Read actual fixed files, binding their native identities AND exact bytes.

    Owner is the maintained bootstrap Owner, supplied by its fixed caller. This
    function does not authenticate that caller or the supplied original ACK.
    No new deadline, owner, process, source loader, cache classifier or writer is
    created. Failed transport remains private for separate failure custody.
    """
    context, _ = outer._context(request)
    ack = outer.read_ack(acknowledgement, request, supervisor_exit)
    launch.require(ack.kind == ack.provider_kind == "success" and ack.worker_exit_code == 0,
                   "PROVIDER_READBACK_SUCCESS_REQUIRED")
    first, fence, ledger, callback = owner.first, owner.fence, owner.resources, owner.cancelled
    limits = owner.local_end, owner.work_limit, owner.final_limit
    binding_raw = launch._json(bindings)
    launch.clocks.validate_reading(first)
    launch.require(first.clock == launch.clocks.ClockIdentity(context["role"],
        launch.clocks.DOMAINS[context["role"]], context["frequency"]) and
        ack.observed_ns <= first.nanoseconds < int(context["hardEndNs"]) and
        any(row["owner"] is directory for row in ledger), "PROVIDER_READBACK_ORIGINAL_OWNER")
    directory_type = launch.files.windows_files.PrivateDirectory if context["role"] == "windows-x64" else launch.files._PosixDirectory
    launch.require(type(directory) is directory_type, "PROVIDER_READBACK_NATIVE_DIRECTORY")
    directory_identity = tuple(context["directoryIdentity"])

    def same():
        launch.require(owner.first is first and owner.fence is fence and owner.resources is ledger and
            owner.cancelled is callback and owner.original is None and not owner.unknown and not owner.closed,
            "PROVIDER_READBACK_OWNER_CHANGED")
        launch.require((owner.local_end, owner.work_limit, owner.final_limit) == limits and
                       launch._json(bindings) == binding_raw, "PROVIDER_READBACK_INPUT_CHANGED")

    def checked():
        same()
        callback()
        same()
        end = owner.end()
        same()
        directory.verify()
        launch.require(str(directory.path) == context["directory"] and
                       tuple(directory.identity) == directory_identity, "PROVIDER_READBACK_DIRECTORY_CHANGED")
        now = launch.clocks.checked_now(first.clock, minimum_ns=checked.last)
        launch.require(now < int(context["hardEndNs"]), "PROVIDER_READBACK_ORIGINAL_END")
        checked.last = now
        callback()
        same()
        owner.end()
        same()
        return end

    checked.last = first.nanoseconds
    originals = []
    references = dict(ack.files)
    for slot, name in (("native", outer.NATIVE_NAME), ("stdout", "provider-stdout.log"),
                       ("stderr", "provider-stderr.log"), ("packet", launch.transport.PACKET_NAME)):
        end = checked()
        reference = references[slot]
        launch.require(type(reference) is outer.FileReference, "PROVIDER_READBACK_FILE_REFERENCE")
        maximum, reader = outer._LIMITS[slot], None
        try:
            reader = owner.acquire("provider-" + slot + "-reader", lambda: (
                directory.open_file(name, max_bytes=maximum, deadline=end) if context["role"] == "windows-x64" else
                launch.files._posix_stream(directory.path / name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, "rb")))
            checked()
            def info():
                return (reader.verify() if context["role"] == "windows-x64" else
                        launch.files._file_info(directory.path / name, reader, maximum))
            before = info()
            launch.require(before.size == reference.size and
                launch.transport.file_identity(before, context["role"]) == reference.identity,
                "PROVIDER_READBACK_FILE_REPLACED")
            checked()
            raw = reader.read(maximum + 1)
            checked()
            launch.require(info() == before and type(raw) is bytes and len(raw) == reference.size and
                hashlib.sha256(raw).hexdigest() == reference.sha256, "PROVIDER_READBACK_FILE_CHANGED")
            originals.append((slot, raw))
            checked()
        except BaseException as error:
            owner.error("provider-readback", error)
            raise
        finally:
            if reader is not None:
                owner.close_one(reader)
        checked()  # Known original reader close is required before interpretation.
    raw_files = dict(originals)
    worker_request = _worker_request(raw_files["native"], request, ack, python, bindings)
    checked()
    worker_ack = launch.transport.read_ack(raw_files["stdout"], worker_request)
    packet_ref = references["packet"]
    launch.require((worker_ack.packet_bytes, worker_ack.packet_sha256, worker_ack.packet_identity) ==
                   (packet_ref.size, packet_ref.sha256, packet_ref.identity), "PROVIDER_READBACK_PACKET_BINDING")
    provider = launch.transport.decode(raw_files["packet"], worker_ack, worker_request, ack.worker_exit_code)
    launch.require(provider.kind == "success" and provider.observed_ns <= ack.observed_ns,
                   "PROVIDER_READBACK_PROVIDER_RETURN")
    checked()
    return ProviderReadback(provider, ack, worker_request, tuple(originals), checked.last)
