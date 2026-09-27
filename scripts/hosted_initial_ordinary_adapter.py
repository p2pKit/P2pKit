"""Fixed Stage2 controller adapter; no serialized current or credential broker.

Only this module loads the hyphenated current owner for production consumers.
Retained history and immutable budgets are DATA; later controllers acquire NEW
real native/source returns and reread every original packet. All activation
HOLDs, C1/C2 approvals, real provider/native/custody/scheduling qualification and
Release gates remain independent prerequisites. Import performs no I/O.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import http.client
import importlib.util
import math
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
import re
import ssl
import sys
import threading
import time

import audit_processes as processes
import hosted_cache_provider_environment as provider_environment
import hosted_full_job_budget as job_time
import hosted_initial_ordinary_identity as identity
import hosted_initial_ordinary_originals as originals
import hosted_test_query as query


SCRIPTS = Path(__file__).absolute().parent
ROOT = SCRIPTS.parent
I = identity.I
NS = job_time.NS
MODULE_NAME = "p2pkit_initial_ordinary_current"
HISTORY_NAME = "initial-current-history.json"
HISTORY_FILES = (HISTORY_NAME, "current.json", "context.json", "match.json", "identity.json", "original-event.json",
    "original-policy.json", "recipient-public.asc", "owner-close.json", "native-start.json", "native-return.json",
    "first-session.json", "child-result.json", "child-ack.bin", "attempt.bin", "jobs.bin",
    *("qualification-" + str(n) + ".json" for n in range(1, 5)),
    *("archive-" + str(n) + "-" + name + ".json" for n in range(1, 5) for name in ("acquisition", "redirect", "download")))
INITIAL_CONTEXT_SCOPE = "CLOSED_INITIAL_ORDINARY_TEST_CONTROLLER"
INITIAL_RESULT_SCOPE = "INITIAL_ORDINARY_PROFILE_CUSTODY_ONLY"
CRYPTO_SCOPE = "INITIAL_ORDINARY_FIXED_CRYPTO_REQUEST_V1"
_MODULE = None
_KEY = object()
_SESSIONS = {}
_EPISODES = {}
_QUARANTINE = []


def require(value, reason):
    I.require(value, "INITIAL_ORDINARY_ADAPTER_" + reason)


def digest(raw):
    require(type(raw) is bytes, "BYTES_REQUIRED")
    return hashlib.sha256(raw).hexdigest()


def current_module():
    """One fixed registry/namespace, never a configurable loader or lookalike."""
    global _MODULE
    path = SCRIPTS / "run-hosted-initial-ordinary.py"
    if _MODULE is None:
        require(MODULE_NAME not in sys.modules, "PRELOADED_CURRENT_NAMESPACE")
        spec = importlib.util.spec_from_file_location(MODULE_NAME, path)
        require(spec is not None and spec.loader is not None, "CURRENT_SOURCE_SPEC")
        module = importlib.util.module_from_spec(spec)
        sys.modules[MODULE_NAME] = module
        try:
            spec.loader.exec_module(module)
        except BaseException:
            # Never retry a partly loaded owner or replace its registry.
            _QUARANTINE.append(module)
            raise
        _MODULE = module
    require(not _QUARANTINE and sys.modules.get(MODULE_NAME) is _MODULE and
            Path(_MODULE.__file__) == path, "CURRENT_NAMESPACE_CHANGED")
    return _MODULE


def take_service_environment():
    """Consume actual runner service fields without exposing or serializing them.

    The legitimate API token is deliberately NOT consumed here: only the fixed
    current owner may consume it. No caller may reinsert it after construction.
    """
    raw = {name: os.environ.pop(name) for name in provider_environment.SERVICE_FIELDS if name in os.environ}
    return provider_environment.runtime_service_fragment(raw)


def forbid_service_environment():
    require(not any(name in os.environ for name in (*provider_environment.SERVICE_FIELDS, "ACTIONS_CACHE_URL",
            "ACTIONS_ID_TOKEN_REQUEST_TOKEN", "ACTIONS_ID_TOKEN_REQUEST_URL", "GH_TOKEN", "GITHUB_TOKEN")),
            "CREDENTIAL_DOMAIN")


class CurrentSession:
    """Actual currency owner inside one real Python controller process."""
    def __init__(self, key, current, cancelled):
        require(key is _KEY and callable(cancelled), "SESSION_FACTORY")
        native = current_module()
        native.checked_initial_ordinary(current)
        self.current, self.identity, self.cancelled = current, native.initial_ordinary_identity(current), cancelled
        self.pid, self.thread = os.getpid(), threading.get_ident()
        self.failed, self.original, self.claimed = False, None, False
        self.source_uses = []
        _SESSIONS[id(self)] = (self, self.identity, self.cancelled, self.pid, self.thread)

    def check(self, *, current=True):
        saved = _SESSIONS.get(id(self))
        require(type(self) is CurrentSession and saved is not None and saved[0] is self and
                self.identity is saved[1] and self.cancelled is saved[2] and self.pid == saved[3] == os.getpid() and
                self.thread == saved[4] == threading.get_ident() and not self.failed, "ORIGINAL_SESSION_CHANGED")
        forbid_service_environment()
        self.cancelled()
        if current:
            native = current_module()
            native.checked_initial_ordinary(self.current)
            require(native.initial_ordinary_identity(self.current).record == self.identity.record, "SESSION_IDENTITY_CHANGED")
        return self

    def fail(self, error):
        if self.original is None:
            self.original = error
        self.failed = True

    def claim(self, purpose):
        try:
            self.check()
            require(not self.claimed, "SESSION_CURRENT_ALREADY_CLAIMED")
            native = current_module()
            native.claim_initial_ordinary(self.current, purpose)
            self.claimed = True
            raw = native.initial_ordinary_record(self.current)
            self.source_uses.append((purpose, raw))
            return raw
        except BaseException as error:
            self.fail(error)
            raise

    def refresh(self, *, work_end_ns, final_end_ns, purpose):
        """Old source is HISTORY during a long operation, never its authority."""
        try:
            self.check(current=False)
            require(self.claimed, "REFRESH_REQUIRES_ORIGINAL_CLAIM")
            native = current_module()
            self.current = native.refresh_initial_ordinary(self.current, cancelled=self.cancelled,
                original_work_end_ns=work_end_ns, original_final_end_ns=final_end_ns)
            self.claimed = False
            return self.claim(purpose)
        except BaseException as error:
            self.fail(error)
            raise


def acquire_first(*, cancelled, original_work_end_ns, original_final_end_ns):
    forbid_service_environment()
    current = current_module().acquire_initial_ordinary(kind="worker", cancelled=cancelled,
        original_work_end_ns=original_work_end_ns, original_final_end_ns=original_final_end_ns)
    return CurrentSession(_KEY, current, cancelled)


def read_history(owner, directory, end):
    """Fixed owner-read DATA set, including bounded originals rather than hashes."""
    import hosted_dependency_seed_files as files
    guard = owner.acquire("initial-history-roster", lambda: files.private_root(directory.path))
    try:
        names = guard.names(max_names=len(HISTORY_FILES), deadline=end)
        require(set(names) == set(HISTORY_FILES), "HISTORY_FILE_ROSTER")
    finally:
        owner.close_one(guard)
    data = {name: owner.read(directory, name, end, 4 * 1024 * 1024) for name in HISTORY_FILES}
    require(sum(map(len, data.values())) <= 64 * 1024 * 1024 and not owner.unknown, "HISTORY_BYTES_OR_CLOSE")
    return data


def retain_first(session, owner, directory, end):
    session.check()
    require(not session.claimed, "RETAIN_BEFORE_PROVIDER_CLAIM")
    native = current_module()
    native.initial_ordinary_budget_originals(session.current)  # Refreshed data cannot become a new origin.
    data = dict(native.initial_ordinary_retained_data(session.current))
    require(set(data) == set(HISTORY_FILES), "FIXED_ORIGINAL_DATA")
    for name in HISTORY_FILES:
        session.check()
        owner.write(directory, name, data[name], end)
    require(read_history(owner, directory, end) == data, "ORIGINAL_HISTORY_COPY_CHANGED")
    session.check()
    return digest(data[HISTORY_NAME])


def reacquire(owner, directory, expected_sha256, end, *, cancelled, original_work_end_ns,
              original_final_end_ns, preceding_outcome):
    require(preceding_outcome == "success", "ACTUAL_PRECEDING_STEP_REQUIRED")
    forbid_service_environment()
    data = read_history(owner, directory, end)
    current = current_module().reacquire_initial_ordinary(data, expected_sha256, cancelled=cancelled,
        original_work_end_ns=original_work_end_ns, original_final_end_ns=original_final_end_ns)
    require(read_history(owner, directory, end) == data, "HISTORY_CHANGED_DURING_FRESH_ACQUISITION")
    return CurrentSession(_KEY, current, cancelled)


def budget_originals(data):
    require(type(data) is dict and set(data) == set(HISTORY_FILES), "BUDGET_FIXED_DATA")
    return {"current_raw": data["current.json"], "context_raw": data["context.json"], "identity_raw": data["identity.json"],
        "attempt_raw": data["attempt.bin"], "jobs_raw": data["jobs.bin"], "first_session_raw": data["first-session.json"],
        "child_raw": data["child-result.json"], "child_ack_raw": data["child-ack.bin"],
        "native_start_raw": data["native-start.json"], "native_return_raw": data["native-return.json"],
        "owner_close_raw": data["owner-close.json"]}


def load_identity(owner, directory, end):
    """Explicit initial-only DATA reader; the ordinary Admission loader stays strict."""
    return identity.retained_identity(owner.read(directory, "admission.json", end),
        owner.read(directory, "original-event.json", end), owner.read(directory, "original-policy.json", end),
        owner.read(directory, "recipient-public.asc", end), now=int(time.time()))


def retain_identity(session, owner, directory, end):
    session.check()
    bound = session.identity
    for name, raw in (("admission.json", bound.record), ("original-event.json", bound.original_event),
            ("original-policy.json", bound.original_policy), ("recipient-public.asc", bound.public_key)):
        owner.write(directory, name, raw, end)
    require(load_identity(owner, directory, end).record == bound.record, "RETAINED_IDENTITY_CHANGED")
    session.check()


def check_local(owner, bound, destination, check, *, end):
    """Fixed credential-free crypto/native Git supplier; no current reconstruction."""
    require(type(bound) is identity.InitialOrdinaryIdentity, "LOCAL_INITIAL_IDENTITY")
    supplier, failure, checked = None, None, None
    try:
        check()
        supplier = query.NativeGitQueries(ROOT, destination, check_cancel=check, owner_deadlines=(end, end))
        supplier.native_host_matches_actions()
        checked = originals.check_local_worker(ROOT, bound, query_runner=supplier, check=check)
        check()
    except BaseException as error:
        failure = error
    finally:
        if supplier is not None:
            try:
                supplier._finalize(failure)
            except BaseException as error:
                failure = failure or error
            if supplier.unknown or not supplier.closed:
                owner.error("initial-local-source-close", failure or I.AdmissionError("INITIAL_LOCAL_UNKNOWN"), unknown=True)
    if failure is not None:
        raise failure
    require(checked is not None and not owner.unknown and not query.QUARANTINE, "LOCAL_SOURCE_NOT_RETURNED")
    check()
    return checked


def initial_context(value):
    require(type(value) is dict and value.get("scope") == INITIAL_CONTEXT_SCOPE and
            type(value.get("initialOrdinary")) is dict and set(value["initialOrdinary"]) ==
            {"historySha256", "identitySha256", "sourceBudgetSha256", "samplePackagingRequired"} and
            value["initialOrdinary"]["samplePackagingRequired"] is False and
            value.get("admissionSha256") == value["initialOrdinary"]["identitySha256"] and
            value.get("jobBudgetSha256") == value["initialOrdinary"]["sourceBudgetSha256"], "CONTEXT_FIELDS")
    for name in ("historySha256", "identitySha256", "sourceBudgetSha256"):
        require(type(value["initialOrdinary"][name]) is str and re.fullmatch(r"[0-9a-f]{64}", value["initialOrdinary"][name]),
                "CONTEXT_DIGEST")
    require(value.get("samplePackagingRequired", False) is False, "FIRST_PR_CANNOT_PACKAGE")
    return value["initialOrdinary"]


def claim_within(session, purpose, budget, stage, local_end):
    """New genuine source use clipped to the ORIGINAL caller/stage deadline."""
    require(type(session) is CurrentSession and type(budget) is job_time.Budget and
            budget.value["schema"] == 3 and budget.value["identitySha256"] == digest(session.identity.record),
            "CURRENT_BUDGET_BINDING")
    session.check(current=False)
    now = budget.check(stage)
    # Mapping LOCAL->RAW uses the LATER local sample. The opposite ordering
    # would give the new source child the elapsed clock-call time again.
    local = time.monotonic()
    require(type(local_end) in (int, float) and math.isfinite(local_end) and local < local_end,
            "CURRENT_ORIGINAL_LOCAL_END")
    cap = local_raw_cap(now, budget.fence(stage), local, local_end)
    if session.claimed:
        return session.refresh(work_end_ns=cap, final_end_ns=cap, purpose=purpose)
    # A newly acquired unclaimed current is checked; an expired current cannot
    # fail then be retried/refreshed to erase that failure.
    return session.claim(purpose)


def local_raw_cap(now, fence, local, local_end):
    """Conservative LOCAL->RAW mapping, with no new time allowance.

    The real caller samples RAW before LOCAL. Round both float operations
    downward before truncating to integer nanoseconds, never past the caller's
    original local end or immutable RAW fence.
    """
    require(type(now) is int and type(fence) is int and 0 <= now < fence < job_time.UINT64 and
            type(local) in (int, float) and type(local_end) in (int, float) and
            math.isfinite(local) and math.isfinite(local_end) and 0 <= local < local_end,
            "CURRENT_ORIGINAL_CLOCK_CAP")
    remaining = math.nextafter(local_end - local, 0.0)
    nanoseconds = math.nextafter(remaining * NS, 0.0)
    require(math.isfinite(nanoseconds) and nanoseconds > 0, "CURRENT_ORIGINAL_CLOCK_CAP")
    cap = min(fence, now + int(nanoseconds))
    require(now < cap, "CURRENT_NO_ORIGINAL_TIME_LEFT")
    return cap


def current_qualifications(session):
    session.check()
    rows = current_module().initial_ordinary_qualification_records(session.current)
    require(type(rows) is tuple and len(rows) == 4 and all(type(raw) is bytes for raw in rows),
            "FOUR_ORIGINAL_QUALIFICATIONS")
    return rows


def provider_current_binding(session, plan, provider, previous_qualifications):
    """Real freshly checked current joined to already-decoded native V2 tools.

    The caller must have closed the actual Node and both resource episodes;
    neither this DATA result nor cache metadata establishes that ownership.
    """
    current = current_qualifications(session)
    require(current == previous_qualifications, "PROVIDER_QUALIFICATIONS_CHANGED")
    result = provider_join_data(current, plan, provider)
    session.check()
    return result


def provider_join_data(qualifications, plan, provider):
    """Retained original consistency only; no current/native capability granted."""
    import hosted_dependency_cache as cache
    import hosted_cache_provider_return as transport
    import hosted_initial_ordinary_productive_qualification as qualification
    require(type(provider) is transport.TransportedProvider and provider.kind == "success" and
            provider.phase == "restore" and type(qualifications) is tuple and len(qualifications) == 4,
            "ACTUAL_RESTORE_TRANSPORT_REQUIRED")
    selected = [raw for raw in qualifications if qualification.S.bootstrap.selection(
        I.parse(raw, 4 * 1024 * 1024)["selection"])[:2] == (plan["profile"], plan["role"])]
    require(len(selected) == 1, "UNIQUE_PROVIDER_QUALIFICATION_REQUIRED")
    qualified = I.parse(selected[0], 4 * 1024 * 1024)
    expected = qualified["provider"]
    tools = I.parse(provider.tools, 262144)
    compression = tools["resolution"]["compression"]
    require(compression in ("gzip", "zstd-without-long") and tools["context"]["role"] == plan["role"] and
            tools["context"]["phase"] == "restore" and tools["context"]["literalPath"] == plan["path"] and
            tools["context"]["key"] == plan["key"] and expected["key"] == plan["key"] and
            expected["literalPath"] == plan["path"] and expected["compression"] == compression and
            expected["cacheVersion"] == cache.provider_cache_version(plan["path"], compression, plan["role"]),
            "CURRENT_H1_NATIVE_H2_PROVIDER_MISMATCH")
    return {"scope": "INITIAL_ORDINARY_CURRENT_H1_NATIVE_H2_PROVIDER_JOIN_V1",
        "qualificationSha256": digest(selected[0]), "qualificationsSha256": [digest(raw) for raw in qualifications],
        "toolsSha256": digest(provider.tools), "compression": compression, "cacheVersion": expected["cacheVersion"],
        "cacheEntry": expected["cacheEntry"], "refs": expected["refs"],
        "globalVisibilityIsRestore": False, "resolverAcceptance": "NOT_PERFORMED"}


def current_budget_disposition(budget, history_sha256):
    value = budget.value
    require(value["schema"] == 3 and type(history_sha256) is str and
            re.fullmatch(r"[0-9a-f]{64}", history_sha256), "SOURCE_BUDGET_DISPOSITION")
    return {"scope": "ORIGINAL_INITIAL_ORDINARY_CURRENT_JOB_BUDGET_DATA_V1", "budgetSha256": budget.sha256,
        "historySha256": history_sha256, "identitySha256": value["identitySha256"],
        "originalsSha256": value["originalsSha256"], "provenance": value["provenance"],
        "ordinaryJobTimePhase": "NOT_EXECUTED_NOT_CLAIMED"}


@dataclass(frozen=True, repr=False)
class CryptoRequest:
    """Closed fixed-child DATA. This is not a live current or Admission."""
    raw: bytes = field(repr=False)
    bound: identity.InitialOrdinaryIdentity = field(repr=False)


def crypto_request_data(raw, bound, context_raw, budget, started, operation):
    """Closed retained DATA grammar; never creates a current or native owner.

    Seal processes use this reader to check original bytes. The actual child
    must additionally call crypto_request against its inherited native domain.
    A seal must not synthesize that domain from the record it is inspecting.
    """
    require(type(bound) is identity.InitialOrdinaryIdentity and type(budget) is job_time.Budget and
            operation in ("validate", "export"), "CRYPTO_REQUEST_TYPES")
    value, context, record = (I.parse(item, 4 * 1024 * 1024) for item in (raw, context_raw, bound.record))
    binding = initial_context(context)
    keys = {"schema", "scope", "operation", "source", "github", "identitySha256", "policySha256",
        "contextSha256", "historySha256", "jobBudgetSha256", "currentSha256", "current", "native", "window"}
    require(type(value) is dict and set(value) == keys and raw == I.encoded(value) and
            type(value["schema"]) is int and value["schema"] == 1 and value["scope"] == CRYPTO_SCOPE and
            value["operation"] == operation and value["source"] == record["source"] and
            value["github"] == record["github"] and value["identitySha256"] == binding["identitySha256"] == digest(bound.record) and
            value["policySha256"] == digest(bound.original_policy) and value["contextSha256"] == digest(context_raw) and
            value["historySha256"] == binding["historySha256"] and
            value["jobBudgetSha256"] == binding["sourceBudgetSha256"] == budget.sha256 and
            budget.value["schema"] == 3 and budget.value["identitySha256"] == digest(bound.record) and
            type(value["current"]) is str and value["current"].isascii(), "CRYPTO_REQUEST_BINDING")
    current_raw = value["current"].encode("ascii")
    identity.retained_current(current_raw, bound, context["role"])
    require(digest(current_raw) == value["currentSha256"], "CRYPTO_REQUEST_CURRENT_DATA")
    native = value["native"]
    require(type(native) is dict and set(native) == {"job", "invocation", "state", "home", "cwd", "phase"} and
            native == {name: started[name] for name in native} and
            native["phase"] == ("recipient-validation" if operation == "validate" else "export") and
            type(native["job"]) is str and re.fullmatch(r"[0-9a-f]{32}", native["job"]) and
            type(native["invocation"]) is str and re.fullmatch(r"[0-9a-f]{32}", native["invocation"]) and
            native["job"] == context["job"] and native["state"] == context["session"] and
            native["home"] == str(Path(context["session"]) / "control-home") and
            native["cwd"] == str(ROOT) == context["root"] and
            started.get("jobBudgetSha256") == budget.sha256 and started.get("clock") == job_time.clock_value(budget.clock),
            "CRYPTO_ORIGINAL_NATIVE_START_DATA")
    window = value["window"]
    require(type(window) is dict and set(window) == {"clock", "startedNs", "workEndNs", "finalEndNs"} and
            window["clock"] == job_time.clock_value(budget.clock) and
            all(type(window[name]) is int for name in ("startedNs", "workEndNs", "finalEndNs")) and
            window["startedNs"] == started["startedRawNs"] and window["startedNs"] < window["workEndNs"] <=
            window["finalEndNs"] and window["workEndNs"] <= window["startedNs"] + 240 * NS and
            window["finalEndNs"] <= window["startedNs"] + 285 * NS and
            window["workEndNs"] <= budget.fence("productive" if operation == "validate" else "export") and
            window["finalEndNs"] <= budget.fence("preparation-final" if operation == "validate" else "export-final"),
            "CRYPTO_ORIGINAL_WINDOW")
    return CryptoRequest(raw, bound)


def crypto_request(raw, bound, context_raw, budget, started, inherited, operation):
    """Actual fixed-child reader: DATA plus real inherited native ownership."""
    request = crypto_request_data(raw, bound, context_raw, budget, started, operation)
    require(type(inherited) is dict and set(inherited) == set(query._CONTEXT), "CRYPTO_NATIVE_DOMAIN_REQUIRED")
    domains = processes.ownership_domains(inherited[processes.CHAIN_ENV], inherited[processes.DOMAINS_ENV])
    native = I.parse(raw, 4 * 1024 * 1024)["native"]
    require(native["job"] == domains[-1]["job"] == inherited[processes.JOB_ENV] and
            native["invocation"] == domains[-1]["id"] and native["state"] == domains[-1]["state"] ==
            inherited[processes.STATE_ENV] and native["home"] == domains[-1]["home"] == inherited["GRADLE_USER_HOME"],
            "CRYPTO_ACTUAL_NATIVE_DOMAIN")
    return request


def manifest_data(request):
    """Exact public schema5 fields, not proof of current/crypto/owner inspection."""
    require(type(request) is CryptoRequest and type(request.bound) is identity.InitialOrdinaryIdentity,
            "MANIFEST_FIXED_REQUEST")
    value = I.parse(request.raw, 4 * 1024 * 1024)
    record = I.parse(request.bound.record, 4 * 1024 * 1024)
    match = record["initialRecipient"]
    current = I.parse(value["current"].encode("ascii"), 4 * 1024 * 1024)
    require(value["scope"] == CRYPTO_SCOPE and value["operation"] == "export" and
            value["identitySha256"] == digest(request.bound.record) and value["source"] == record["source"] and
            value["github"] == record["github"] and value["policySha256"] == digest(request.bound.original_policy),
            "MANIFEST_ORIGINAL_REQUEST")
    return {"schema": 5, "scope": "ENCRYPTED_PRIVATE_INITIAL_ORDINARY_TEST_EVIDENCE",
        "source": record["source"], "github": record["github"], "policy": record["policy"],
        "custody": {"profile": record["profile"], "suites": record["suites"]},
        "initialOrdinary": {"identitySha256": digest(request.bound.record), "requestSha256": digest(request.raw),
            "historySha256": value["historySha256"], "jobBudgetSha256": value["jobBudgetSha256"],
            "authority": match["authority"], "originalBase": match["originalBase"], "reviewed": match["reviewed"],
            "firstUseAt": match["firstUseAt"], "notBefore": match["notBefore"], "expiresAt": match["expiresAt"],
            "histories": match["historicalRecords"], "qualificationRecordsSha256": current["qualifications"],
            "lateSourceOriginals": "OPERATIONAL_NOT_IN_FROZEN_PAYLOAD",
            "privateOwnerInspection": "NOT_PERFORMED_BY_WORKFLOW", "samplePackagingRequired": False}}


def acquire_provider_bundle(episode, plan):
    """One fixed public source GET inside the actual preparation episode.

    This is not a dependency/tool installer, runtime-service request or generic
    URL client. The maintained descriptor fixes the exact pin/path/size/hash.
    Response/parser/connection closes are real once-only operations; failures
    retain their original owners and can never be retried by this function.
    """
    import hosted_dependency_cache as cache
    contract = cache.restore_provider_contract(plan)["bundle"]
    prefix = "https://raw.githubusercontent.com/"
    require(contract["url"].startswith(prefix) and contract["basename"] == "provider.cjs", "PUBLIC_BUNDLE_DESCRIPTOR")
    expected = contract["bytes"]
    require(type(expected) is int and 0 < expected <= 4 * 1024 * 1024, "PUBLIC_BUNDLE_LIMIT")
    forbid_service_environment()
    require(job_time.TOKEN_ENV not in os.environ, "API_TOKEN_IN_PUBLIC_ACQUISITION")
    connection = response = reader = None
    original, completed, raw = None, False, bytearray()

    class Connection(http.client.HTTPSConnection):
        close_attempted, close_error = False, None

        def close(self):
            # getresponse may close the connection before returning its parser.
            # Do not erase a failed implicit close by retrying the raw socket.
            if self.close_attempted:
                if self.close_error is not None:
                    raise self.close_error
                return
            self.close_attempted = True
            try:
                super().close()
            except BaseException as error:
                self.close_error = error
                episode.error("public-bundle-connection-close", error, unknown=True)
                raise

    class Reader:
        def __init__(self, stream, socket):
            self.stream, self.socket = stream, socket
            self.header, self.wire_bytes = bytearray(), 0
            self.headers, self.closed, self.close_error = True, False, None

        def _read(self, method, amount):
            end = episode.end()
            self.socket.settimeout(min(5, max(0, end - time.monotonic())))
            block = getattr(self.stream, method)(amount)
            self.wire_bytes += len(block)
            require(self.wire_bytes <= 2 * expected + job_time.HEADER_LIMIT, "PUBLIC_BUNDLE_WIRE_LIMIT")
            if self.headers:
                self.header.extend(block)
                require(len(self.header) <= job_time.HEADER_LIMIT, "PUBLIC_BUNDLE_HEADERS_LIMIT")
            episode.end()
            return block

        def readline(self, limit=-1):
            amount = min(job_time.HEADER_LINE_LIMIT + 1, limit) if limit >= 0 else job_time.HEADER_LINE_LIMIT + 1
            block = self._read("readline", amount)
            require(len(block) <= job_time.HEADER_LINE_LIMIT and (not block or block.endswith(b"\r\n")),
                    "PUBLIC_BUNDLE_HEADER_LINE")
            return block

        def read(self, amount=-1):
            require(type(amount) is int and 0 <= amount <= 65536, "PUBLIC_BUNDLE_READ_BOUND")
            return self._read("read", amount)

        def readinto(self, target):
            block = self.read(len(target))
            target[:len(block)] = block
            return len(block)

        def flush(self):
            self.stream.flush()

        def close(self):
            if self.closed:
                if self.close_error is not None:
                    raise self.close_error
                return
            self.closed = True
            try:
                self.stream.close()
            except BaseException as error:
                self.close_error = error
                episode.error("public-bundle-parser-close", error, unknown=True)
                raise

    try:
        end = episode.end()
        connection = episode.acquire("public-bundle-connection", lambda: Connection(
            "raw.githubusercontent.com", timeout=min(5, max(0, end - time.monotonic())), context=ssl.create_default_context()))

        class Response(http.client.HTTPResponse):
            close_attempted, close_error = False, None

            def __init__(self, sock, **kwargs):
                nonlocal reader, response
                # Own the actual response BEFORE begin()/getresponse can throw
                # or internally close it. Register the returned parser before
                # any later deadline check can fail and lose the reference.
                self.fp = None
                response = episode.hold("public-bundle-response", self)
                try:
                    super().__init__(sock, **kwargs)
                except BaseException as error:
                    episode.error("public-bundle-parser-allocation", error, unknown=True)
                    raise
                reader = episode.hold("public-bundle-parser", Reader(self.fp, sock))
                self.fp = reader
                episode.end()

            def close(self):
                if self.close_attempted:
                    if self.close_error is not None:
                        raise self.close_error
                    return
                self.close_attempted = True
                try:
                    super().close()
                except BaseException as error:
                    self.close_error = error
                    episode.error("public-bundle-response-close", error, unknown=True)
                    raise

        connection.response_class = Response
        # http.client has no proxy/redirect/retry machinery. No credential from
        # either private domain is placed in these public request headers.
        connection.request("GET", "/" + contract["url"][len(prefix):], headers={
            "Accept": "application/octet-stream", "Accept-Encoding": "identity", "Connection": "close"})
        returned = connection.getresponse()
        require(returned is response and response is not None and reader is not None, "PUBLIC_BUNDLE_RESPONSE_OWNER")
        status, fields = job_time.headers(bytes(reader.header))
        require(status == response.status == 200 and "location" not in fields and "content-range" not in fields and
                fields.get("content-encoding", "identity").lower() == "identity", "PUBLIC_BUNDLE_RESPONSE")
        require(not ("content-length" in fields and "transfer-encoding" in fields),
                "PUBLIC_BUNDLE_HEADER_DUPLICATE")
        length, transfer = fields.get("content-length"), fields.get("transfer-encoding")
        require(length is None or length == str(expected), "PUBLIC_BUNDLE_DECLARED_LENGTH")
        require(transfer is None or transfer.lower() == "chunked", "PUBLIC_BUNDLE_TRANSFER")
        reader.headers = False
        while True:
            episode.end()
            block = response.read(min(65536, expected + 1 - len(raw)))
            require(type(block) is bytes and len(raw) + len(block) <= expected, "PUBLIC_BUNDLE_BYTES")
            raw.extend(block)
            if not block:
                break
        require(len(raw) == expected and digest(bytes(raw)) == contract["sha256"] and
                response.isclosed() and reader.closed and reader.close_error is None, "PUBLIC_BUNDLE_EOF_OR_HASH")
        completed = True
    except BaseException as error:
        original = error
        episode.error("public-bundle-acquisition", error)
    finally:
        # Response implicit EOF may have retired the parser already. Its
        # once-only close retains any ambiguity and never recloses a raw fd.
        for resource in (response, reader, connection):
            if resource is not None:
                episode.close_one(resource)
    if original is not None:
        raise original
    episode.end()  # Late/failed original closes cannot become source success.
    require(completed and not episode.unknown and episode.original is None, "PUBLIC_BUNDLE_NOT_RETURNED")
    return bytes(raw)


def service_frame(prepared, python, *, initial_ordinary):
    import hosted_cache_provider_prepare as preparation
    require(type(initial_ordinary) is bool and type(python) is str, "SERVICE_FIXED_ORIGIN")
    require(type(prepared) is preparation.PreparedProvider, "SERVICE_ORIGINAL_PREPARATION")
    value = {"schema": 1, "scope": "P2PKIT_" + ("INITIAL_ORDINARY_" if initial_ordinary else "ORDINARY_") +
        "RESTORE_SERVICE_REQUEST_V1", "python": python, "request": prepared.request.decode("ascii"),
        "bindings": dict(prepared.bindings), "clockBindings": dict(prepared.clock_bindings)}
    raw = I.encoded(value)
    require(len(raw) <= 16384 and not value["request"].endswith("\n"), "SERVICE_STDIN_FRAME_BOUND")
    service_request_data(raw, prepared.request, initial_ordinary=initial_ordinary)
    return raw


def service_request_data(raw, request_raw, *, initial_ordinary):
    """Strict original frame DATA; neither a provider nor a live resource owner."""
    import hosted_cache_provider_clock as clock
    import hosted_cache_provider_supervisor_return as outer
    import hosted_cache_provider_worker as worker
    require(type(initial_ordinary) is bool and type(raw) is bytes and 0 < len(raw) <= 16384 and
            type(request_raw) is bytes and 0 < len(request_raw) <= 16384 and not request_raw.endswith(b"\n"),
            "SERVICE_FRAME_BYTES")
    value = I.parse(raw, 16384)
    require(type(value) is dict and set(value) == {"schema", "scope", "python", "request", "bindings", "clockBindings"} and
            raw == I.encoded(value) and type(value["schema"]) is int and value["schema"] == 1 and value["scope"] ==
            "P2PKIT_" + ("INITIAL_ORDINARY_" if initial_ordinary else "ORDINARY_") + "RESTORE_SERVICE_REQUEST_V1" and
            type(value["request"]) is str and value["request"].isascii() and value["request"].encode("ascii") == request_raw,
            "SERVICE_FRAME_FIELDS")
    request, _ = outer._context(request_raw)
    require(request["phase"] == "restore" and request["plan"]["mode"] == "consume", "SERVICE_FRAME_RESTORE_ONLY")
    role = request["role"]
    for field, names in (("bindings", worker.outer_names(role)), ("clockBindings", clock.roster(role))):
        bindings = value[field]
        require(type(bindings) is dict and set(bindings) == set(names) and all(type(sha) is str and
                re.fullmatch(r"[0-9a-f]{64}", sha) for sha in bindings.values()), "SERVICE_FRAME_SOURCE_BINDINGS")
    require(all(name == clock.NAME or sha == value["bindings"].get(name) for name, sha in value["clockBindings"].items()),
            "SERVICE_FRAME_CLOCK_SOURCES")
    python = value["python"]
    require(type(python) is str and python and all(ord(char) >= 32 for char in python), "SERVICE_FRAME_PYTHON")
    path = (PureWindowsPath if role == "windows-x64" else PurePosixPath)(python)
    require(path.is_absolute() and ".." not in path.parts and
            re.fullmatch(r"python(?:3(?:\.\d+)?)?(?:\.exe)?", path.name), "SERVICE_FRAME_FIXED_PYTHON")
    return value


def service_return(raw, frame_raw, request_raw, *, initial_ordinary):
    """Original Node output DATA; real native Node close is a caller prerequisite."""
    import hosted_cache_provider_supervisor_return as outer
    require(type(initial_ordinary) is bool and type(raw) is bytes and len(raw) <= 16384,
            "SERVICE_RETURN_BYTES")
    service_request_data(frame_raw, request_raw, initial_ordinary=initial_ordinary)
    value = I.parse(raw, 16384)
    require(set(value) == {"schema", "scope", "controllerRequestSha256", "supervisorRequestSha256", "acknowledgement",
            "prelaunchClock", "postCloseClock", "enclosingNodeReturn", "providerAcceptance"} and raw == I.encoded(value) and
            type(value["schema"]) is int and value["schema"] == 1 and value["scope"] == "P2PKIT_" +
            ("INITIAL_ORDINARY_" if initial_ordinary else "ORDINARY_") + "RESTORE_SERVICE_RETURN_V1" and
            value["controllerRequestSha256"] == digest(frame_raw) and value["supervisorRequestSha256"] == digest(request_raw) and
            value["enclosingNodeReturn"] == "NOT_OBSERVED" and value["providerAcceptance"] == "NOT_ESTABLISHED" and
            all(type(value[name]) is str and value[name].isascii() and value[name].endswith("\n")
                for name in ("acknowledgement", "prelaunchClock", "postCloseClock")), "SERVICE_RETURN_BINDING")
    request, _ = outer._context(request_raw)
    ack_raw = value["acknowledgement"].encode("ascii")
    ack = outer.read_ack(ack_raw, request_raw, 0)
    require(ack.kind == ack.provider_kind == "success", "SERVICE_ACK_NOT_SUCCESSFUL")
    minimum = int(request["firstNs"])
    for field, phase, floor in (("prelaunchClock", "PRELAUNCH", minimum),
                                ("postCloseClock", "POST_CLOSE", ack.observed_ns)):
        clock_raw = value[field].encode("ascii")
        clock = I.parse(clock_raw, 1024)
        require(clock_raw == I.encoded(clock) and set(clock) == {"schema", "invocationSha256", "role", "frequency",
                "minimumNs", "hardEndNs", "domain", "observedNs"} and clock["schema"] ==
                "P2PKIT_PROVIDER_" + phase + "_CLOCK_OBSERVATION_V1" and clock["invocationSha256"] == digest(request_raw) and
                clock["role"] == request["role"] and clock["frequency"] == str(request["frequency"]) and
                clock["minimumNs"] == str(floor) and clock["hardEndNs"] == request["hardEndNs"] and
                clock["domain"] == job_time._clocks().DOMAINS[request["role"]], "SERVICE_CLOCK_BINDING")
        require(type(clock["observedNs"]) is str and re.fullmatch(r"0|[1-9][0-9]{0,19}", clock["observedNs"]) and
                floor <= int(clock["observedNs"]) < int(request["hardEndNs"]), "SERVICE_CLOCK_ORIGINAL_INTERVAL")
    require(int(I.parse(value["prelaunchClock"].encode("ascii"), 1024)["observedNs"]) <= ack.observed_ns,
            "SERVICE_CLOCK_ORDER")
    return value, ack
