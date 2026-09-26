"""Fixed native provider files, not admission, acquisition or an Action caller.

The caller must have freshly admitted/rederived the original preparation and
plan. It supplies the actual preceding step outcome/hash and acquired public
bundle bytes. This leaf creates only the two fixed private roots and provider.cjs
under its borrowed Owner. It neither downloads nor starts a provider, and cannot
authenticate a supplied step/source/tool identity. No caller is wired yet.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import uuid

import hosted_cache_provider_clock as clock_source
import hosted_cache_provider_readback as readback


L, O = readback.launch, readback.outer
PREPARATION_LIMIT = 2 * 1024 * 1024


@dataclass(frozen=True, repr=False)
class PreparedProvider:
    request: bytes = field(repr=False)
    bindings: tuple = field(repr=False)
    clock_bindings: tuple = field(repr=False)
    preparation_sha256: str
    checked_ns: int
    scope: str = "PROVIDER_NATIVE_FILES_PENDING_ORIGINAL_OWNER_CLOSE_V1"
    enclosing_owner_close: str = "NOT_OBSERVED"
    provider_execution: str = "NOT_PERFORMED"
    provider_acceptance: str = "NOT_ESTABLISHED"


def materialize(owner, prepared_directory, preparation_raw, expected_sha256, original_outcome, *,
                phase, plan, bundle_raw, node, tool_path, worker_cutoff_ns):
    """Retain verified public bundle bytes and a full native supervisor request.

    This is deliberately not another descriptor/admission parser. The original
    fixed caller must use _save_preparation_record/_probe_preparation_record,
    real native admission and current source/staging/plan rederivation first.
    These checks join that supplied result to the actual borrowed native roots.
    Their enclosing Owner remains live on return; a successful step is external.
    """
    L.require(type(original_outcome) is str and original_outcome == "success" and
        type(expected_sha256) is str and L.re.fullmatch(r"[0-9a-f]{64}", expected_sha256) and
        type(preparation_raw) is bytes and hashlib.sha256(preparation_raw).hexdigest() == expected_sha256,
        "PROVIDER_PREPARE_ORIGINAL_STEP")
    prepared = L.transport._parse(preparation_raw, PREPARATION_LIMIT)
    L.require(phase in ("save", "lookup") and preparation_raw == L.files.encoded(prepared) and
        prepared.get("scope") == ("BOOTSTRAP_SAVE_PREPARATION_PENDING_ORIGINAL_STEP_RETURN_V1" if phase == "save"
            else "BOOTSTRAP_PROBE_PREPARATION_PENDING_ORIGINAL_STEP_RETURN_V1") and
        prepared.get("writerReturn") == "PENDING_NOT_OBSERVABLE_BY_THIS_FILE" and
        prepared.get("providerExecution") == "NOT_PERFORMED" and prepared.get("exportSaveAuthority") is False,
        "PROVIDER_PREPARE_DESCRIPTOR")
    contract = L.cache.bootstrap_provider_contract(plan, phase)
    plan_raw = L.files.encoded(plan)
    L.require(L.files.encoded(prepared.get("plan")) == plan_raw and
        prepared.get("planSha256") == hashlib.sha256(plan_raw).hexdigest() and
        prepared.get("providerRequest") == contract["request"] and
        all(prepared.get(name) == plan[name] for name in ("source", "github")),
        "PROVIDER_PREPARE_PLAN")
    L.require(type(bundle_raw) is bytes and len(bundle_raw) == contract["bundle"]["bytes"] and
        hashlib.sha256(bundle_raw).hexdigest() == contract["bundle"]["sha256"], "PROVIDER_PREPARE_BUNDLE")
    first, fence, ledger, callback = owner.first, owner.fence, owner.resources, owner.cancelled
    limits = owner.local_end, owner.work_limit, owner.final_limit
    L.clocks.validate_reading(first)
    role = first.clock.role
    directory_type = L.files.windows_files.PrivateDirectory if role == "windows-x64" else L.files._PosixDirectory
    L.require(type(prepared_directory) is directory_type and
        any(row["owner"] is prepared_directory for row in ledger) and plan["role"] == role,
        "PROVIDER_PREPARE_ORIGINAL_OWNER")
    L.require(prepared.get("directory") == str(prepared_directory.path) and
        tuple(prepared.get("directoryIdentity", ())) == tuple(prepared_directory.identity),
        "PROVIDER_PREPARE_DIRECTORY")
    clock = prepared.get("clock")
    L.require(clock == {"role": role, "domain": first.clock.domain,
                       "ticksPerSecond": first.clock.ticks_per_second}, "PROVIDER_PREPARE_CLOCK")
    window = prepared.get("providerWindow")
    L.require(type(window) is dict and set(window) == {"issuedNs", "hardEndNs", "actualProviderStart"} and
              window["actualProviderStart"] == "NOT_OBSERVED", "PROVIDER_PREPARE_WINDOW")
    issued, end = (L.clocks.integer(window[name]) for name in ("issuedNs", "hardEndNs"))
    cut = L.clocks.integer(worker_cutoff_ns)
    work_end = min(cut, end - 45 * L.clocks.NS)
    L.require(issued <= first.nanoseconds < work_end and
        issued + 45 * L.clocks.NS < cut < end <= issued + 180 * L.clocks.NS,
        "PROVIDER_PREPARE_ORIGINAL_END")
    L.require(L._path(node, role).name == ("node.exe" if role == "windows-x64" else "node") and
              type(tool_path) is str and tool_path, "PROVIDER_PREPARE_TOOLS")
    for part in tool_path.split(";" if role == "windows-x64" else ":"):
        L._path(part, role)
    # Existing original-interval implementation, not a new180 or a transplanted
    # Node LOCAL epoch. The fixed caller must already own its own outer deadline.
    native = L._Window(first, issued, end, work_end)
    identity = tuple(prepared_directory.identity)

    def same():
        L.require(owner.first is first and owner.fence is fence and owner.resources is ledger and
            owner.cancelled is callback and owner.original is None and not owner.unknown and not owner.closed and
            (owner.local_end, owner.work_limit, owner.final_limit) == limits and
            L.files.encoded(plan) == plan_raw, "PROVIDER_PREPARE_INPUT_CHANGED")

    def checked():
        same()
        callback()
        same()
        local_end = owner.end()
        same()
        prepared_directory.verify()
        L.require(str(prepared_directory.path) == prepared["directory"] and
                  tuple(prepared_directory.identity) == identity, "PROVIDER_PREPARE_DIRECTORY_CHANGED")
        native.check(work=True)
        callback()
        same()
        owner.end()
        same()
        native.check(work=True)
        return min(local_end, native.local_end)

    directory = home = writer = reader = None
    try:
        deadline = checked()
        directory = owner.acquire("provider-directory", lambda: prepared_directory.create_directory(
            "provider", deadline=deadline))
        deadline = checked()
        home = owner.acquire("provider-home", lambda: prepared_directory.create_directory(
            "provider-home", deadline=deadline))
        checked()
        L.require(directory is not home and type(directory) is type(home) is directory_type and
                  len({identity, tuple(directory.identity), tuple(home.identity)}) == 3,
                  "PROVIDER_PREPARE_DISTINCT_DIRECTORIES")
        directory.verify()
        home.verify()
        deadline = checked()
        try:
            writer = owner.acquire("provider-bundle-writer", lambda: directory.create_file(
                "provider.cjs", max_bytes=len(bundle_raw), deadline=deadline))
            checked()
            L.require(writer.write(bundle_raw) == len(bundle_raw), "PROVIDER_PREPARE_SHORT_WRITE")
            writer.sync()
            checked()
            original_info = writer.verify()
            L.require(original_info.size == len(bundle_raw), "PROVIDER_PREPARE_BUNDLE_SIZE")
        finally:
            if writer is not None:
                owner.close_one(writer)
        checked()
        deadline = checked()
        try:
            reader = owner.acquire("provider-bundle-reader", lambda: L._open_bundle(
                directory, role, deadline, len(bundle_raw)))
            checked()
            info = L._bundle_bytes(reader, directory, role, contract)
            L.require(L.transport.file_identity(info, role) == L.transport.file_identity(original_info, role),
                      "PROVIDER_PREPARE_BUNDLE_REPLACED")
        finally:
            if reader is not None:
                owner.close_one(reader)
        checked()
        sources = {}
        for name in L.worker_source.outer_names(role):
            checked()
            sources[name] = L.worker_source.read_source(L.SCRIPTS, name)
        clock_bytes = {}
        for name in clock_source.roster(role):
            checked()
            clock_bytes[name] = clock_source.read_source(L.SCRIPTS, name)
            L.require(name not in sources or sources[name] == clock_bytes[name], "PROVIDER_PREPARE_SOURCE_CHANGED")
        ids = tuple(uuid.uuid4().hex for _ in range(3))
        L.require(len(set(ids)) == 3, "PROVIDER_PREPARE_DISTINCT_INVOCATIONS")
        request = L.transport._json({"schema": "P2PKIT_PROVIDER_SUPERVISOR_REQUEST_V1", "role": role,
            "frequency": first.clock.ticks_per_second, "firstNs": str(first.nanoseconds),
            "issuedNs": str(issued), "hardEndNs": str(end), "workerCutoffNs": str(cut),
            "phase": phase, "job": ids[0], "outerId": ids[1], "innerId": ids[2],
            "directory": str(directory.path), "directoryIdentity": list(directory.identity),
            "home": str(home.path), "homeIdentity": list(home.identity),
            "node": node, "toolPath": tool_path, "plan": plan})
        O._context(request)
        for name, raw in sources.items():
            checked()
            L.require(L.worker_source.read_source(L.SCRIPTS, name) == raw, "PROVIDER_PREPARE_SOURCE_CHANGED")
        for name, raw in clock_bytes.items():
            checked()
            L.require(clock_source.read_source(L.SCRIPTS, name) == raw, "PROVIDER_PREPARE_SOURCE_CHANGED")
        directory.verify()
        home.verify()
        checked()
        return PreparedProvider(request, tuple((name, hashlib.sha256(raw).hexdigest()) for name, raw in sources.items()),
            tuple((name, hashlib.sha256(raw).hexdigest()) for name, raw in clock_bytes.items()),
            expected_sha256, native.highest)
    except BaseException as error:
        owner.error("provider-prepare", error)
        raise
