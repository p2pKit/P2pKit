"""Dormant exact-loader absence leaf; NOT an uninstall or original-call parent.

Configuration reservation never installed the ordinary Test loader. Its ordinary
uninstall operation therefore cannot honestly run here. This separate read-only
leaf observes only that fixed name in the supplied original canonical home. It
does not establish past absence, nonexecution, other initializer contents, a
completed producer/collection, enclosing retirement or export/save authority.

A future parent must supply NEW ownership and original RAW/job phase fences
after its actual producer and collection returns. LOCAL90 only shortens that
parent's ceiling; it is not an admitted/measured uninstall90/final45/read30 phase,
a filesystem watchdog or a new budget. There is no CLI or workflow caller.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import os
from pathlib import Path
import time

import hosted_cache_bootstrap_collect_files as collection


files = collection.files
producer = collection.inventory.producer
SCOPE = "BOOTSTRAP_EXACT_CUSTODY_LOADER_ABSENCE_LEAF_V1"
INIT_DIRECTORY = "init.d"
LOADER = "p2pkit-test-transcript-custody.gradle"
SECONDS = 90
NAMES = files.NAMES_LIMIT


class NoLoaderError(RuntimeError):
    """Finite refusal; never expose a supplied path or initializer content."""


def require(value, reason):
    if not value:
        raise NoLoaderError(reason)


@dataclass(frozen=True)
class HomeOriginals:
    """Supplied bytes/native identity, NOT an original producer or phase token."""
    request_raw: bytes = field(repr=False)
    admitted_raw: bytes = field(repr=False)
    canonical_raw: bytes = field(repr=False)
    home_identity: tuple = field(repr=False)


@dataclass(frozen=True)
class AbsenceEvidence:
    raw: bytes = field(repr=False)
    local_started: float
    checked_local: float


def _capture(value):
    require(type(value) is HomeOriginals, "BOOTSTRAP_NO_LOADER_INPUT_KIND")
    raw = tuple(collection.inventory._bytes(getattr(value, name)) for name in
                ("request_raw", "admitted_raw", "canonical_raw"))
    identity = value.home_identity
    require(type(identity) is tuple and files._identity(list(identity)), "BOOTSTRAP_NO_LOADER_HOME_IDENTITY")
    return (*raw, identity)


class _Inputs:
    def __init__(self, originals):
        self.originals, self.captured = originals, _capture(originals)
        request_raw, admitted_raw, canonical_raw, self.identity = self.captured
        request = producer.parse(request_raw)
        expected = producer.make_request(admitted_raw, canonical_raw, invocation=request.get("id"),
                                        ancestor_invocations=request.get("ancestorInvocationIds"))
        require(request_raw == producer.encoded(expected), "BOOTSTRAP_NO_LOADER_REQUEST_CHANGED")
        self.role, self.home = expected["host"], Path(expected["gradleHome"])
        require((os.name == "nt") == (self.role == "windows-x64") and self.home.is_absolute() and
                type(self.identity[1]) is (str if self.role == "windows-x64" else int),
                "BOOTSTRAP_NO_LOADER_PLATFORM")
        self.kind = files.windows.DependencySourceDirectory if self.role == "windows-x64" else files.PosixSourceDirectory

    def unchanged(self):
        require(_capture(self.originals) == self.captured, "BOOTSTRAP_NO_LOADER_INPUT_CHANGED")

    def binding(self):
        return {"requestSha256": files.digest(self.captured[0]), "admissionSha256": files.digest(self.captured[1]),
                "canonicalContextSha256": files.digest(self.captured[2]), "home": str(self.home),
                "homeIdentity": list(self.identity), "target": INIT_DIRECTORY + "/" + LOADER}


class _Observation(collection._Copy):
    """Reuse exact leaf ownership/UNKNOWN/once-close barriers, not its copier."""
    def __init__(self, parent, inputs, began):
        super().__init__(parent, inputs, began)
        # Narrow BOTH ceilings: check() returns caller_end to native operations.
        # No old120, per-listing restart, or final/read allowance is inherited.
        self.end_local = self.caller_end = collection._local(began + SECONDS)
        self.observations = []

    def listing(self, directory, path):
        self.check()
        require(type(directory) is self.inputs.kind and directory.path == self.inputs.home.joinpath(*path),
                "BOOTSTRAP_NO_LOADER_DIRECTORY_KIND_OR_PATH")
        before = directory.verify()
        binding = self.info(before, directory=True, side="home", path="/".join(path))
        require(tuple(binding["identity"])[0] == self.inputs.identity[0] and
                (path or tuple(binding["identity"]) == self.inputs.identity), "BOOTSTRAP_NO_LOADER_HOME_REPLACED")
        end = self.check()
        names = directory.names(max_names=NAMES, deadline=end)
        self.check()
        require(type(names) is tuple and len(names) <= NAMES and
                all(type(name) is str and 0 < len(name) <= 255 and name not in (".", "..") and
                    "/" not in name and "\0" not in name for name in names), "BOOTSTRAP_NO_LOADER_NAMES")
        require(names == tuple(sorted(names)) and len({name.casefold() for name in names}) == len(names),
                "BOOTSTRAP_NO_LOADER_NAME_ORDER_OR_ALIAS")
        require(directory.verify() == before, "BOOTSTRAP_NO_LOADER_DIRECTORY_CHANGED")
        self.check()
        self.observations.append({"directory": "/".join(path) or ".", "binding": binding,
                                  "names": len(names), "namesSha256": files.digest(files.encoded(names))})
        return binding, names

    def selected(self, names, target):
        # Never normalize a name into a path to open. Refuse ambiguous spellings
        # of the one selected name; unrelated dotfiles remain counted/unopened.
        aliases = tuple(name for name in names if name.rstrip(" .").casefold() == target.casefold())
        require(aliases in ((), (target,)), "BOOTSTRAP_NO_LOADER_SELECTED_ALIAS")
        return aliases == (target,)

    def observe(self):
        self.check()
        home = self.acquire("no-loader-home", lambda: files.public_root(self.inputs.home))
        home_first = self.listing(home, ())
        init_present = self.selected(home_first[1], INIT_DIRECTORY)
        if init_present:
            # acquire() and the parent's factory callback can shorten the known
            # ceiling. Recheck at dispatch; never forward an earlier saved end.
            init = self.acquire("no-loader-init",
                                lambda: home.open_directory(INIT_DIRECTORY, deadline=self.check()))
            init_first = self.listing(init, (INIT_DIRECTORY,))
            require(not self.selected(init_first[1], LOADER), "BOOTSTRAP_NO_LOADER_TARGET_PRESENT")
            init_last = self.listing(init, (INIT_DIRECTORY,))
            require(not self.selected(init_last[1], LOADER), "BOOTSTRAP_NO_LOADER_TARGET_PRESENT")
            require(init_last == init_first, "BOOTSTRAP_NO_LOADER_INIT_CHANGED")
        home_last = self.listing(home, ())
        require(home_last == home_first and self.selected(home_last[1], INIT_DIRECTORY) is init_present,
                "BOOTSTRAP_NO_LOADER_HOME_CHANGED")
        self.check()
        return "OBSERVED_DIRECTORY" if init_present else "ABSENT_IN_HOME_LISTINGS"


def observe_absence(parent, originals):
    """Observe the fixed target only; never read, delete or create a file.

    This repeatable data leaf is not a same-call transition or single-use token.
    Its own handles close; the supplied parent stays open and retains enclosing
    close/failure custody. A successful return cannot authorize later phases.
    """
    began = collection._local(time.monotonic())
    inputs = _Inputs(originals)
    observation = _Observation(parent, inputs, began)
    result = {"schema": 1, "scope": SCOPE, "binding": inputs.binding(), "completed": False,
        "observationState": "FAILED", "inputProvenance": "SUPPLIED_RECORDS_NOT_ORIGINAL_CALL",
        "leafHandleClose": "PENDING", "enclosingOwnerRetirement": "NOT_OBSERVED_HERE",
        "producerAndCollectionReturn": "NOT_OBSERVED_HERE", "historicalLoaderExecution": "NOT_OBSERVED",
        "otherInitializerContents": "NOT_INSPECTED", "deletionPerformed": False, "fileContentsRead": False,
        "observationBoundary": "PINNED_LISTINGS_AND_SAME_HANDLE_VERIFY_NOT_ATOMIC_OR_HISTORICAL_ABSENCE",
        "dependencyPopulation": "NOT_ATTESTED", "budgetAcceptance": "NOT_ADMITTED",
        "testAcceptance": "NOT_PERFORMED", "nextPhaseAuthority": False, "exportSaveAuthority": False}
    try:
        disposition = observation.observe()
        observation.close()
        observation.check()
        result.update(completed=True, observationState="EXACT_TARGET_ABSENT_AT_LISTINGS",
            initDirectory=disposition, leafHandleClose="KNOWN", listings=observation.observations,
            localWindow={"started": began, "end": observation.end_local, "observed": observation.last,
                         "scope": "LOCAL90_SHORTENS_CALLER_NOT_SHARED_CLOCK_OR_JOB_ADMISSION"})
        raw = files.encoded(result)
        observation.check()
        return AbsenceEvidence(raw, began, observation.last)
    except BaseException as error:
        observation.error("no-loader-body", error)
        try:
            observation.close()
        except BaseException as secondary:
            if secondary is not observation.first:
                observation.error("no-loader-cleanup", secondary)
        result.update(completed=False, observationState="UNKNOWN" if observation.unknown or parent.unknown else "FAILED",
            leafHandleClose="UNKNOWN" if observation.unknown or parent.unknown else
                "KNOWN" if all(pin.attempted and pin.closed for pin in observation.resources) else "INCOMPLETE",
            listings=observation.observations)
        try:
            observation.first.bootstrap_no_loader_result = result
            observation.first.bootstrap_no_loader_resources = tuple(observation.resources)
        except BaseException:
            pass
        raise observation.first
