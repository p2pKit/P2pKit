"""Closed BEFORE declarations and an in-memory entry latch, never native proof.

The DATA codecs and process-local latch are used by the actual BEFORE protocol.
Neither can restore a retired clock, grant recipient authority, supply original
hosted identity, or stand in for real owned reads/known closes. The latch owns
no native resource and does not observe time or serialize an authority handle.
"""
from __future__ import annotations

import re

import hosted_full_job_budget as wire
import hosted_initial_recipient_continuity as continuity
import hosted_job_clock as clocks


CONTEXT_SCOPE = "INITIAL_RECIPIENT_BEFORE_AUTHORITY_CONTEXT_V1"
CHILD_SCOPE = "INITIAL_BEFORE_AUTHORITY_PENDING_CHILD_CLOSE_V1"
ACK_SCOPE = "INITIAL_BEFORE_AUTHORITY_ORIGINAL_POST_CLOSE_ACK_V1"
CLOSE_SCOPE = "INITIAL_BEFORE_AUTHORITY_PENDING_CLOSE_WRITER_V1"
SEAL_OUTCOME_ENV = "P2PKIT_INITIAL_SEAL_OUTCOME"
SEED_FIELDS = (
    ("initialSealSha256", "P2PKIT_INITIAL_SEAL_SHA256", "--seal-sha256"),
    ("initialSealEndNs", "P2PKIT_INITIAL_SEAL_END_NS", "--seal-end-ns"),
    ("initialSealClockRole", "P2PKIT_INITIAL_SEAL_CLOCK_ROLE", "--seal-clock-role"),
    ("initialSealClockDomain", "P2PKIT_INITIAL_SEAL_CLOCK_DOMAIN", "--seal-clock-domain"),
    ("initialSealClockTicksPerSecond", "P2PKIT_INITIAL_SEAL_CLOCK_TICKS_PER_SECOND", "--seal-clock-ticks-per-second"),
    ("initialSealBootSha256", "P2PKIT_INITIAL_SEAL_BOOT_SHA256", "--seal-boot-sha256"),
)
PHASE_FIELDS = (("startedNs", "--before-started-ns"), ("workEndNs", "--before-work-end-ns"),
    ("finalEndNs", "--before-final-end-ns"))
STEP_NAMES = (
    ("export", "P2pKit initial custody export"),
    ("collect", "P2pKit initial post-export custody"),
    ("seal", "P2pKit initial custody seal"),
    ("before", "P2pKit initial before-upload custody"),
)
SOURCE_KEYS = ("base_policy_entry", "ancestry_raw", "candidate_policy_entry", "candidate_policy_raw")
HTTP_KEYS = ("attempt", "jobs", "approvals", "comment", "environment", "branches", "main", "reviewed_ref")
ORIGINAL_KEYS = ("event", *SOURCE_KEYS, *HTTP_KEYS, "observation", "match")
PHASE_FILES = ("start.json", "baseline.json", "result.json", "native-start.json", "stdout.log", "stderr.log")
QUERY_FILES = ("start.json", "baseline.json", "stdout.log", "stderr.log", "result.json")
DIRECTORY_TARGETS = (".", "control-home", "temporary", "service", "source-before", "source-after", "acquisition-queries")
STEP_FIELDS = frozenset(("name", "status", "conclusion", "number", "started_at", "completed_at"))
CONCLUSIONS = frozenset(("success", "failure", "neutral", "cancelled", "skipped", "timed_out", "action_required"))


class BeforeError(ValueError):
    """Finite public-safe DATA refusal, never an original record transcript."""


def require(value, code):
    if not value:
        raise BeforeError("INITIAL_BEFORE_" + code)


_ENTRY_LATCHES = {}


class EntryLatch:
    """One in-memory entry, with first failure independent of its visible dict.

    Only the custody caller's single original instance participates in B. Tests
    may exercise this same small state machine, but creating one is not creating
    a B owner/capability. Public operations never expose the private state tuple;
    restoring exposed dictionary fields cannot clear a recorded first failure.
    """
    __slots__ = ()

    def __init__(self, attempts):
        if id(self) in _ENTRY_LATCHES:
            raise self.fail(BeforeError("INITIAL_BEFORE_ENTRY_REINITIALIZED"))
        require(type(self) is EntryLatch and type(attempts) is dict, "ENTRY_LATCH_TYPE")
        _ENTRY_LATCHES[id(self)] = (self, attempts, None, "NEW", None, None)

    def _original(self):
        saved = _ENTRY_LATCHES.get(id(self))
        require(type(self) is EntryLatch and type(saved) is tuple and len(saved) == 6 and saved[0] is self,
            "ENTRY_LATCH_ORIGINAL")
        return saved

    def fail(self, error):
        saved = self._original()
        if not isinstance(error, BaseException):
            error = BeforeError("INITIAL_BEFORE_ENTRY_FAILURE_TYPE")
        failure = saved[4] if saved[4] is not None else error
        _ENTRY_LATCHES[id(self)] = (*saved[:3], "FAILED", failure, saved[5])
        if saved[2] is not None:
            # This only records failure. Never repair a changed dictionary to
            # an accepted state or adopt the replacement in the visible table.
            saved[2]["state"], saved[2]["failure"] = "FAILED", failure
        return failure

    def begin(self, attempts):
        saved = self._original()
        try:
            if saved[4] is not None:
                raise saved[4]
            require(attempts is saved[1] and saved[2] is None and saved[3] == "NEW" and
                "entry" not in attempts, "ENTRY_ATTEMPT_REUSE_OR_REGISTRY")
            attempt = {"state": "STARTED", "failure": None, "return": None}
            attempts["entry"] = attempt
            _ENTRY_LATCHES[id(self)] = (self, attempts, attempt, "STARTED", None, None)
            return attempt
        except BaseException as error:
            raise self.fail(error)

    def check(self, attempts, attempt):
        saved = self._original()
        try:
            if saved[4] is not None:
                raise saved[4]
            require(attempts is saved[1] and type(attempt) is dict and attempt is saved[2] and
                attempts.get("entry") is attempt and saved[3] in ("STARTED", "RETURNED") and
                all(type(key) is str for key in attempt) and set(attempt) == {"state", "failure", "return"} and
                type(attempt["state"]) is str and
                attempt["state"] == saved[3] and attempt["failure"] is None and attempt["return"] is saved[5],
                "ENTRY_ORIGINAL_CHANGED")
        except BaseException as error:
            raise self.fail(error)

    def complete(self, attempts, attempt, result):
        try:
            self.check(attempts, attempt)
            saved = self._original()
            require(saved[3] == "STARTED" and result is not None and saved[5] is None, "ENTRY_COMPLETE_ONCE")
            _ENTRY_LATCHES[id(self)] = (*saved[:3], "RETURNED", None, result)
            attempt["state"], attempt["return"] = "RETURNED", result
        except BaseException as error:
            raise self.fail(error)

    def returned(self, attempts, attempt, result):
        try:
            self.check(attempts, attempt)
            saved = self._original()
            require(saved[3] == "RETURNED" and result is not None and saved[5] is result, "ENTRY_EXACT_RETURN")
        except BaseException as error:
            raise self.fail(error)


def write_close_metadata(role, preclose, postclose, count):
    """Compare two actual observations' DATA, not their acquisition or close.

    Windows may finalize only modified/change times across the writing handle's
    close here. Retain both full observations; no timestamp equality, direction
    or normalized replacement is invented. POSIX keeps full metadata equality.
    The caller still supplies the actual same-file byte/hash/EOF/private-native
    proofs and known writer/reader closes. Each reader's own lifetime is strict.
    """
    require(type(role) is str and role in clocks.DOMAINS and type(count) is int and
        0 <= count <= wire.RECORD_LIMIT, "WRITE_CLOSE_ROLE_COUNT")
    windows = role == "windows-x64"
    names = frozenset(("identity", "is_directory", "size", "links", "attributes", "creation_100ns",
        "modified_100ns", "change_100ns", "owner_sid", "protected_dacl") if windows else
        ("device", "inode", "size", "mtime_ns", "ctime_ns"))
    allowed = frozenset(("modified_100ns", "change_100ns")) if windows else frozenset()
    for value in (preclose, postclose):
        require(type(value) is dict and set(value) == names and type(value["size"]) is int and
            value["size"] == count, "WRITE_CLOSE_METADATA_FIELDS_SIZE")
        if windows:
            identity = value["identity"]
            require(type(identity) is list and len(identity) == 2 and type(identity[0]) is int and
                0 <= identity[0] <= clocks.UINT64 and type(identity[1]) is str and
                re.fullmatch(r"[0-9a-f]{32}", identity[1]) and value["is_directory"] is False and
                type(value["links"]) is int and value["links"] == 1 and type(value["owner_sid"]) is str and
                re.fullmatch(r"S-1-[0-9-]{1,180}", value["owner_sid"]) and value["protected_dacl"] is True,
                "WRITE_CLOSE_WINDOWS_IDENTITY_PRIVACY")
            integers = ("attributes", "creation_100ns", "modified_100ns", "change_100ns")
        else:
            wire.integer(value["inode"], 1)
            integers = ("device", "mtime_ns", "ctime_ns")
        for name in integers:
            wire.integer(value[name])
    require(wire.encoded({name: value for name, value in preclose.items() if name not in allowed}) ==
        wire.encoded({name: value for name, value in postclose.items() if name not in allowed}),
        "WRITE_CLOSE_STABLE_METADATA_CHANGED")
    return "WINDOWS_WRITE_CLOSE_MODIFIED_CHANGE_ONLY" if windows else "POSIX_FULL_METADATA_EQUAL"


def phase_caps(seed, caps):
    """Validate the supplied ORIGINAL parent phase tuple, not child-first time."""
    _sha, end, _clock, _boot = continuity.seal_deadline_data(seed)
    require(type(caps) is tuple and len(caps) == 3 and
        all(type(value) is int and 0 < value <= clocks.UINT64 for value in caps), "PHASE_TUPLE")
    started, work, final = caps
    require(started < work <= final <= end and work == min(end, started + 45 * clocks.NS) and
        final == min(end, work + 45 * clocks.NS), "PHASE_ORIGINAL_CAPS")
    return caps


def decimal_caps(seed, values):
    """Only fixed CLI decimal strings. This does not authenticate their origin."""
    require(type(values) is tuple and len(values) == 3 and all(type(value) is str and
        re.fullmatch(r"[1-9][0-9]{0,19}", value) for value in values), "PHASE_DECIMAL")
    return phase_caps(seed, tuple(int(value) for value in values))


def first_caps(seed, first, boot, *, inherited=None):
    """Compare supplied FIRST reading DATA with seed; never observe a clock.

    The actual caller takes LOCAL/RAW/boot before any owner and registers its
    own irreversible state. No allowance is computed from child FIRST here.
    """
    _sha, end, clock, original_boot = continuity.seal_deadline_data(seed)
    clocks.validate_reading(first)
    require(wire.encoded(wire.clock_value(first.clock)) == wire.encoded(wire.clock_value(clock)) and
        type(boot) is str and boot == original_boot, "FIRST_CLOCK_OR_BOOT")
    if inherited is None:
        require(first.nanoseconds < end, "FIRST_EXPIRED")
        return end, end
    started, work, final = phase_caps(seed, inherited)
    require(started <= first.nanoseconds < work, "CHILD_FIRST_EXPIRED_OR_EARLY")
    return work, final


def step_rows(job, service_date):
    """Validate a complete selected job's Step DATA, never query/poll GitHub.

    The caller first authenticates this exact job with acquire_bootstrap/_run
    and retained original response dates. Unknown service fields/values refuse
    until separately reviewed. A skipped completed Step may have BOTH nullable
    timestamps; other completed Steps need real times. No Date yields RAW time.
    """
    require(type(job) is dict and type(service_date) is int and 0 < service_date <= 253402300799, "STEP_JOB_DATE")
    began = wire.utc_epoch(job.get("started_at"))
    require(began <= service_date, "STEP_JOB_START")
    rows = job.get("steps")
    require(type(rows) is list and 0 < len(rows) <= 256, "STEP_COMPLETE_ARRAY")
    previous, names, selected = 0, set(), {}
    for row in rows:
        require(type(row) is dict and set(row) == STEP_FIELDS, "STEP_FIELDS")
        name, number, status, conclusion = row["name"], row["number"], row["status"], row["conclusion"]
        require(type(name) is str and 0 < len(name) <= 256 and
            not any(ord(char) < 32 or ord(char) == 127 for char in name) and name not in names and
            type(number) is int and previous < number <= 2147483647 and type(status) is str and
            status in ("queued", "in_progress", "completed"), "STEP_NAME_NUMBER_STATUS")
        previous = number
        names.add(name)
        started, completed = row["started_at"], row["completed_at"]
        if status == "queued":
            require(conclusion is None and started is None and completed is None, "STEP_QUEUED")
        elif status == "in_progress":
            require(conclusion is None and completed is None and
                began <= wire.utc_epoch(started) <= service_date, "STEP_RUNNING")
        else:
            require(type(conclusion) is str and conclusion in CONCLUSIONS, "STEP_CONCLUSION")
            if started is None or completed is None:
                require(conclusion == "skipped" and started is None and completed is None, "STEP_MISSING_TIMES")
            else:
                require(began <= wire.utc_epoch(started) <= wire.utc_epoch(completed) <= service_date, "STEP_TIMES")
        for role, expected in STEP_NAMES:
            if name == expected:
                require(role not in selected, "STEP_AMBIGUOUS")
                selected[role] = dict(row)
    require(set(selected) == {role for role, _name in STEP_NAMES}, "STEP_MISSING_PREDECESSOR")
    ordered = [selected[role] for role, _name in STEP_NAMES]
    require(all(row["status"] == "completed" and row["conclusion"] == "success" and
        type(row["started_at"]) is str and type(row["completed_at"]) is str for row in ordered[:3]) and
        ordered[3]["status"] == "in_progress", "STEP_REQUIRED_SUCCESS_OR_CURRENT")
    require([row["number"] for row in ordered] == sorted(row["number"] for row in ordered) and
        all(wire.utc_epoch(left["completed_at"]) <= wire.utc_epoch(right["started_at"])
            for left, right in zip(ordered, ordered[1:])), "STEP_PREDECESSOR_ORDER")
    current = ordered[3]["number"]
    require(all(row["status"] == ("completed" if row["number"] < current else "queued")
        for row in rows if row["number"] != current), "STEP_UNIQUE_CURRENT_FRONTIER")
    return tuple((role, selected[role]) for role, _name in STEP_NAMES)


def member_grammar(source_before_ids, acquisition_ids, source_after_ids):
    """Declare exactly280 names/58 dirs, including the not-self-hashed close.

    UUIDs must come from actual independently bound query sessions in production.
    Supplied names here are not directory pins, byte custody or native proof.
    """
    groups = (("source-before", source_before_ids, 12), ("acquisition-queries", acquisition_ids, 24),
        ("source-after", source_after_ids, 12))
    seen, files, directories = set(), [], [".", "control-home", "temporary", "service"]
    for side, identifiers, count in groups:
        require(type(identifiers) is tuple and len(identifiers) == count and all(type(value) is str and
            re.fullmatch(r"[0-9a-f]{32}", value) for value in identifiers), "QUERY_IDS")
        require(len(set(identifiers)) == count and not seen.intersection(identifiers), "QUERY_ID_ALIAS")
        seen.update(identifiers)
        directories.extend((side, side + "/query-home"))
        keys = ORIGINAL_KEYS if side == "acquisition-queries" else SOURCE_KEYS
        files.extend(side + "/" + name for name in ("owner.json", "session-result.json", *(key + ".bin" for key in keys)))
        if side != "acquisition-queries":
            files.append(side + "/source-return.json")
        for identifier in identifiers:
            directory = side + "/query-" + identifier
            directories.append(directory)
            files.extend(directory + "/" + name for name in QUERY_FILES)
    files.extend(("context.json", "service/child-result.json", *("service/" + name for name in PHASE_FILES),
        "authority-close.json"))
    require(len(files) == len(set(files)) == 280 and len(directories) == len(set(directories)) == 58,
        "COMPLETE_GRAMMAR")
    return tuple(sorted(files)), tuple(sorted(directories))


def directory_members(files, directories, *, closed):
    """Exact immediate membership; max42 is B-only, never an old32-cap change."""
    require(type(files) is tuple and type(directories) is tuple and type(closed) is bool and
        all(type(name) is str for name in (*files, *directories)) and
        len(files) == len(set(files)) == 280 and len(directories) == len(set(directories)) == 58 and
        "." in directories and "authority-close.json" in files, "MEMBER_GRAMMAR_INPUT")
    selected = files if closed else tuple(name for name in files if name != "authority-close.json")
    members = {name: [] for name in directories}
    for name in (*selected, *(name for name in directories if name != ".")):
        require(type(name) is str and name and not name.startswith("/") and all(re.fullmatch(r"[a-z0-9_.-]+", part)
            and part not in (".", "..") for part in name.split("/")), "MEMBER_PATH")
        parent, _, leaf = name.rpartition("/")
        parent = parent or "."
        require(parent in members, "MEMBER_PARENT")
        members[parent].append(leaf)
    require(all(len(values) == len(set(value.casefold() for value in values)) <= 42 for values in members.values()),
        "MEMBER_ALIAS_OR_LIMIT")
    return tuple((name, tuple(sorted(values))) for name, values in sorted(members.items()))
