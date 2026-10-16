#!/usr/bin/env python3
"""NEW three-origin/Recipient/export/READ controls; authored, not executed.

Tiny owned POSIX bytes exercise the NEW copy/freeze/carrier seams at unchanged
positive limits. Prior PRIMARY/AUTHORITY maps and Step/host/native/validator
returns are explicitly supplied boundaries, not repeated upstream producer
qualification. Every origin remains present; public validation retains its
complete shallow grammar. No earlier TestCase/fixture module is imported.

The native GPG/export suppliers are never invoked. Supplied validator outcomes
construct their returned public Recipient only at that supplier edge; files or
replacement equal objects are negative controls, never live-object restoration.
Windows cases model only declared grammar/backend shapes and must not be reported
as native Windows execution. No private key, current HTTP authority, authentic
hosted original, build, download, provider admission or delivery is established.
"""
from __future__ import annotations

import base64
from contextlib import ExitStack
import ctypes  # Stdlib setup precedes native-load refusal.
from datetime import datetime, timezone
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch


def offline(event, _args):
    if event.startswith(("subprocess.", "socket.")) or event in (
            "os.system", "os.exec", "os.posix_spawn", "os.fork", "os.forkpty", "pty.spawn", "ctypes.dlopen"):
        raise RuntimeError("OFFLINE_CUSTODY_EXPORT_PROCESS_NETWORK_NATIVE_FORBIDDEN")


sys.addaudithook(offline)
sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("new_custody_recipient_export_controls",
    ROOT / "scripts/run-hosted-initial-recipient-custody.py")
D = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = D
_spec.loader.exec_module(D)
NS, BOOT = 1_000_000_000, "a" * 64


def wire(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
        allow_nan=False) + "\n").encode("ascii")


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def put(path, raw):
    with path.open("xb") as stream:
        if stream.write(raw) != len(raw):
            raise AssertionError("SUPPLIED_FIXTURE_SHORT_WRITE")
    path.chmod(0o600)


def metadata(entries):
    return [[name, directory, list(identity), count, json.loads(raw)]
        for name, directory, identity, count, raw in D._snapshot_metadata(entries, False)]


class FalseyFailure(RuntimeError):
    def __bool__(self):
        return False


class Clock:
    def __init__(self):
        self.identity = D.O.clocks.ClockIdentity("linux-x64", D.O.clocks.DOMAINS["linux-x64"], NS)
        self.raw, self.local, self.boot = 1100 * NS, 100.0, BOOT
        self.hook, self.observations = lambda: None, []

    def reading(self):
        return D.O.clocks.Reading(self.identity, self.raw)

    def checked(self, expected, *, minimum_ns=0):
        if expected is not self.identity or self.raw < minimum_ns:
            raise AssertionError("SUPPLIED_EXPORT_CLOCK_FRONTIER")
        self.observations.append((expected, minimum_ns, self.raw))
        return self.raw

    def advance(self, seconds):
        self.raw, self.local = 1100 * NS + seconds * NS, 100.0 + seconds

    def cancelled(self):
        self.hook()


class Workspace:
    """Tiny real files at SUPPLIED prior-map and public-validator boundaries.

The few prior members are not a reduced PRIMARY/authority producer fixture:
neither producer is invoked. The new downstream map/bytes checks still see the
complete supplied rosters, all three origins and unchanged positive limits.
The public key is repository candidate SOURCE, not a private original or owner
approval. Fixture wall time is explicit and never evidence of current currency.
"""
    def __init__(self, kind="gate", *, parent_mode=False):
        self.kind, self.stack, self.clock = kind, ExitStack(), Clock()
        self.parent_mode = parent_mode
        self.copy_owner = self.operative = None
        self.validation_calls, self.exports = [], []
        self.returned_recipient = None
        self.validation_hook = self.export_hook = self.export_after = lambda: None
        self.validation_return = self.export_return = lambda value: value
        self.child_mutation = lambda _child, _ack: None
        self.copy_calls, self.scopes = [], []
        self.parent_closed_hook = lambda: None

    def __enter__(self):
        try:
            if os.name != "posix":
                raise AssertionError("THIS_TINY_FILE_ENVELOPE_IS_POSIX_NOT_A_PLATFORM_SKIP")
            self.stack.enter_context(patch.dict(D.os.environ, {}, clear=True))
            self.stack.enter_context(patch.object(D.time, "monotonic", lambda: self.clock.local))
            self.stack.enter_context(patch.object(D.O.clocks, "checked_now", self.clock.checked))
            self.stack.enter_context(patch.object(D.C, "boot_digest", lambda _role: self.clock.boot))
            for name in ("_WINDOWS", "_CUSTODY_CHILD_CLOCKS", "_CUSTODY_OWNERS", "_PRIMARY_OWNERS",
                    "_CRYPTO_ATTEMPTS", "_CRYPTO_RETURNS", "_CRYPTO_NATIVE_RETURNS", "_CRYPTO_READ_FENCES", "_CRYPTO_CARRIERS"):
                self.stack.enter_context(patch.object(D, name, {}))
            self.stack.enter_context(patch.object(D, "_PRIMARY_QUARANTINE", []))
            self.stack.enter_context(patch.object(D.native, "QUARANTINE", []))
            self.base = Path(self.stack.enter_context(tempfile.TemporaryDirectory(prefix="custody-crypto-new-")))
            self.primary_path, self.custody = self.base / "primary", self.base / "primary-custody"
            self.destination = self.custody / "copied-evidence"
            self.transport, self.work, self.output = (self.custody / name
                for name in ("returned", "public-crypto", "export-output"))
            paths = (self.custody, self.custody / "authority-1", self.destination)
            if not self.parent_mode:
                paths += (self.transport, self.work, self.transport / "control-home",
                    self.transport / "temporary", self.transport / "crypto-service")
            for path in paths:
                path.mkdir(mode=0o700)
            self.parent_first = self.clock.reading()
            self.parent = D.Window(self.parent_first, self.clock.local, BOOT,
                D.schedule(self.kind, 1000 * NS, self.clock.raw), self.clock.cancelled)
            self.policy_raw = (ROOT / ".github/test-evidence-recipient.json").read_bytes()
            if sha(self.policy_raw) != D.A.stages.POLICY_SHA256:
                raise AssertionError("SUPPLIED_PUBLIC_POLICY_SOURCE_BINDING_CHANGED")
            self.policy = json.loads(self.policy_raw)
            self.public = self.policy["recipient"]["publicKey"].encode("ascii")
            self.ring = D.native.posix._public_armor(self.public)  # Public packet parser only, never GPG.
            self.use = self.policy["notBefore"] + 120
            self.stack.enter_context(patch.object(D.time, "time", lambda: self.use))
            self.event = wire({"scope": "SUPPLIED_ORIGINAL_EVENT_BOUNDARY_NOT_HOSTED_EXECUTION"})
            self.observed = {"kind": self.kind, "role": self.clock.identity.role, "firstUseAt": self.use,
                "source": {"commit": "1" * 40, "tree": "2" * 40},
                "inputs": {"selection": "desktop-linux-x64"},
                "github": {"repository": D.I.REPOSITORY, "runId": "12345", "runAttempt": "1"}}
            self.match_raw = wire({"scope": "SUPPLIED_CLOSED_TYPED_MATCH_NOT_CURRENT_HTTP",
                "firstUseAt": self.use, "source": self.observed["source"]})
            self.stack.enter_context(patch.object(D, "_paths", self.paths))
            self.stack.enter_context(patch.object(D.N, "location", lambda: (self.kind, self.primary_path)))
            self.stack.enter_context(patch.object(D.N, "host_context", self.host_context))
            self.stack.enter_context(patch.object(D.O.clocks, "observe", self.clock.reading))
            self.stack.enter_context(patch.object(D.native.posix, "validate_recipient", self.validate))
            self.stack.enter_context(patch.object(D.E, "export_encrypted", self.export))
            self.make_prior_maps()
            self.primary = D.Primary(self.kind, self.clock.identity.role, b"SUPPLIED_PRIOR_HANDOFF",
                wire({"scope": "SUPPLIED_PRIOR_PRIMARY_INVENTORY"}), (), (), (), (), self.primary_result_sha)
            self.primary_fields = {"step": "initial-originals" if self.kind == "gate" else "canonical-initialization",
                "outcome": "success", "resultSha256": self.primary_result_sha,
                "handoffSha256": sha(self.primary.handoff_raw), "inventorySha256": sha(self.primary.inventory_raw)}
            self.clock.advance(10)
            if self.parent_mode:
                self.setup_parent()
            else:
                self.make_frame()
            return self
        except BaseException:
            self.stack.close()
            raise

    def __exit__(self, *args):
        # Do not retry UNKNOWN closure or restore hostile ledger/directory
        # substitutions. Available native handles remain under their original
        # fixture owner; test bodies explicitly close successful owners.
        if self.copy_owner is not None and not self.copy_owner.finished and not self.copy_owner.owner.unknown:
            try:
                self.copy_owner.finish()
            except BaseException:
                pass
        if self.operative is not None and not self.operative.closed and not self.operative.unknown:
            try:
                self.operative.close()
            except BaseException:
                pass
        return self.stack.__exit__(*args)

    def snapshot(self, path):
        return D.native.posix._snapshot(path, D.MAX_BYTES, D.MAX_MEMBERS, 300.0)

    def member(self, ordinal, raw, origin, original):
        name = D._member_name(ordinal)
        put(self.destination / name, raw)
        stamp = D.native.posix._stamp((self.destination / name).stat())
        return {"member": name, "bytes": len(raw), "sha256": sha(raw), "origin": origin,
            "original": original, "originalMaximum": D.native.LIMIT,
            "provenance": "SUPPLIED_PRIOR_MAP_BOUNDARY_NOT_NATIVE_EVIDENCE", "carrier": "INDEXED_DISK_ORIGINAL",
            "destinationWriteMetadata": {"device": stamp[0], "inode": stamp[1], "size": stamp[5],
                "mtime_ns": stamp[6], "ctime_ns": stamp[7]}}

    def make_prior_maps(self):
        self.primary_bytes = (b"SUPPLIED_PRIMARY\x00\xff", b"")
        self.authority_bytes = (b"SUPPLIED_FRESH_AUTHORITY_NOT_PRIMARY", b"SUPPLIED_CLOSED_RETURN")
        primary = [self.member(number, raw, D.ORIGINS[0], "P/model-" + str(number))
            for number, raw in enumerate(self.primary_bytes)]
        prior = self.snapshot(self.destination)
        self.primary_map = {"schema": 1, "scope": D.PRIMARY_SCOPE, "origin": D.ORIGINS[0], "members": primary,
            "sourceMetadata": [], "originalDirectories": [], "handoffMetadata": [],
            "destination": str(self.destination), "destinationIdentity": list(prior[""][:2]),
            "destinationMetadata": metadata(prior), "memberCount": len(primary),
            "totalBytes": sum(map(len, self.primary_bytes)), "nextOrdinal": len(primary),
            "freeze": "NOT_FINAL_THREE_ORIGIN_FREEZE", "remainingOrigins": list(D.ORIGINS[1:]),
            "productiveAuthority": False, "currentAuthority": "NOT_ACQUIRED", "exportSaveAuthority": False}
        self.primary_raw = wire(self.primary_map)
        authority = [self.member(len(primary) + number, raw, D.ORIGINS[1], "authority/model-" + str(number))
            for number, raw in enumerate(self.authority_bytes)]
        current = self.snapshot(self.destination)
        self.prior_stamps = dict(current)
        self.prior_members = tuple((*primary, *authority))
        self.primary_result_sha = sha(b"SUPPLIED_PRIMARY_SUCCESS_RESULT_BOUNDARY")
        self.authority_index = wire({"schema": 1, "scope": "SUPPLIED_AUTHORITY_INDEX_BOUNDARY_NOT_A_PRODUCER",
            "matchSha256": sha(self.match_raw), "pendingSha256": "b" * 64})
        self.authority_return = wire({"schema": 1, "scope": D._AUTHORITY_RETURN_SCOPE,
            "windowSha256": sha(D._custody_authority_window(self.parent)),
            "primaryResultSha256": self.primary_result_sha, "primaryCopySha256": sha(self.primary_raw),
            "inventorySha256": sha(self.authority_index), "matchSha256": sha(self.match_raw),
            "pendingSha256": "b" * 64, "retirement": "KNOWN_RESOURCE_CLOSE_ONLY", "exportSaveAuthority": False})
        self.authority_map = {"schema": 1, "scope": "INITIAL_RECIPIENT_CUSTODY_AUTHORITY_COPY_V1",
            "origin": D.ORIGINS[1], "primaryResultSha256": self.primary_result_sha,
            "primaryCopySha256": sha(self.primary_raw), "authorityReturnSha256": sha(self.authority_return),
            "authorityInventorySha256": sha(self.authority_index),
            "authorityInventoryBase64": base64.b64encode(self.authority_index).decode("ascii"),
            "members": authority, "sourceMetadata": [], "originalDirectories": [],
            "destination": str(self.destination), "destinationIdentity": list(current[""][:2]),
            "destinationBeforeMetadataSha256": sha(wire({"metadata": metadata(prior)})),
            "destinationRootBefore": metadata(prior)[0], "destinationMetadata": metadata(current),
            "previousMemberCount": len(primary), "memberCount": len(authority),
            "totalBytes": sum(map(len, self.authority_bytes)), "aggregateMemberCount": len(self.prior_members),
            "aggregateTotalBytes": sum(map(len, (*self.primary_bytes, *self.authority_bytes))),
            "nextOrdinal": len(self.prior_members), "freeze": "NOT_FINAL_THREE_ORIGIN_FREEZE",
            "remainingOrigins": [D.ORIGINS[2]], "productiveAuthority": False,
            "currentAuthority": "CLOSED_HISTORY_NOT_LIVE_LEASE", "exportSaveAuthority": False}
        self.authority_raw = wire(self.authority_map)

    def validate(self, key_path, fingerprint, owned_work_dir):
        """Explicit public validator RETURN supplier; no GPG process exists."""
        if self.validation_calls or Path(key_path).read_bytes() != self.public or Path(owned_work_dir) != self.work or \
                fingerprint != self.policy["recipient"]["fingerprint"] or any(self.work.iterdir()):
            raise AssertionError("SUPPLIED_VALIDATOR_INPUT_OR_REUSE")
        self.validation_calls.append((key_path, fingerprint, owned_work_dir))
        for name in ("gnupg", "tmp", "gpg-supplied_one", "gpg-supplied_two"):
            (self.work / name).mkdir(mode=0o700)
        put(self.work / "recipient.asc", self.public)
        put(self.work / "recipient.gpg", self.ring)
        for number, name in enumerate(("gpg-supplied_one", "gpg-supplied_two")):
            for leaf, raw in (("stdout", b"SUPPLIED_PUBLIC_LISTING_" + str(number).encode("ascii")),
                    ("stderr", b""), ("status", b""), ("process.json", wire({"schema": 1,
                        "waitExitCode": 0, "retired": True, "interruption": None}))):
                put(self.work / name / leaf, raw)
        # This object originates here, at the explicit supplier boundary. Tests
        # must retain it through the real caller; no file-derived reconstruction.
        result = D.native.posix.Recipient(self.work, self.work / "gnupg", Path("/SUPPLIED/installed-gpg"),
            fingerprint, "E" * 40, self.policy["expiresAt"] + 3600, sha(self.public),
            D.native.posix._identity(self.work))
        self.returned_recipient = result
        self.validation_hook()
        return self.validation_return(result)

    def paths(self, kind):
        if kind != self.kind:
            raise AssertionError("SUPPLIED_FIXED_KIND_CHANGED")
        return {"P": self.primary_path}, self.base / "primary-handoff", self.custody

    def host_context(self, first_use):
        if first_use != self.use:
            raise AssertionError("SUPPLIED_ORIGINAL_FIRST_USE_CHANGED")
        return self.observed, self.primary_path, self.event

    def make_frame(self):
        self.raw_inputs = {"primary-map.json": self.primary_raw, "authority-map.json": self.authority_raw,
            "authority-return.json": self.authority_return, "original-match.json": self.match_raw,
            "fresh-match.json": self.match_raw, "event.json": self.event,
            "candidate-policy.json": self.policy_raw, "recipient-public.asc": self.public}
        self.context = {"schema": 1, "scope": D._CRYPTO_CONTEXT_SCOPE, "kind": self.kind, "root": str(ROOT),
            "session": str(self.transport), "job": "c" * 32, "observed": self.observed,
            "window": json.loads(D._custody_authority_window(self.parent)), "primary": self.primary_fields,
            "authority": {"returnSha256": sha(self.authority_return), "matchSha256": sha(self.match_raw),
                "copySha256": sha(self.authority_raw)},
            "filesSha256": {name: sha(raw) for name, raw in self.raw_inputs.items()},
            "directories": {name: list(D.native.posix._identity(path)) if name != "export-output" else None
                for name, path in D._crypto_directory_paths(self.kind).items()},
            "inheritedContext": {}, "budgetAcceptance": "NOT_ADMITTED", "exportSaveAuthority": False}
        self.context_raw = wire(self.context)
        inherited = D.native.processes.ownership_environment({}, self.context["job"], "d" * 32,
            str(self.transport), str(self.transport / "control-home"), allow_new_context=True)
        self.inherited = {name: inherited[name] for name in D.Q._CONTEXT}
        work = min(self.parent.work, self.clock.raw + 210 * NS)
        self.start = {"schema": 1, "scope": D._CRYPTO_START_SCOPE, "contextSha256": sha(self.context_raw),
            "argv": D._custody_crypto_command(sha(self.context_raw)), "cwd": str(ROOT), "role": self.clock.identity.role,
            "job": self.context["job"], "invocation": "d" * 32, "state": str(self.transport),
            "home": str(self.transport / "control-home"), "inheritedContext": dict(self.inherited),
            "startedNs": self.clock.raw, "workEndNs": work, "finalEndNs": min(self.parent.final, work + 45 * NS),
            "exitCode": None, "launchAttempted": False, "scopeAttempted": False, "retirement": "UNKNOWN"}
        self.start_raw, self.minimum = wire(self.start), self.clock.raw
        for name, raw in self.raw_inputs.items():
            put(self.transport / name, raw)
        put(self.transport / "context.json", self.context_raw)
        put(self.transport / "crypto-service" / "start.json", self.start_raw)
        self.stack.enter_context(patch.object(D.Q, "_inherited_context", lambda: dict(self.inherited)))
        self.clock.advance(11)

    def child(self):
        return D.custody_crypto_child(sha(self.context_raw), self.minimum, self.clock.cancelled)

    def child_owners(self):
        if len(D._CUSTODY_CHILD_CLOCKS) != 1:
            raise AssertionError("SUPPLIED_CONTROL_REQUIRES_ONE_ACTUAL_CHILD_CLOCK")
        clock = next(iter(D._CUSTODY_CHILD_CLOCKS.values())).handle
        self.operative = clock._anchor().operative
        copies = [anchor.handle for anchor in D._PRIMARY_OWNERS.values()
            if anchor.handle is not clock._anchor().metadata]
        if len(copies) != 1:
            raise AssertionError("SUPPLIED_CONTROL_REQUIRES_SEPARATE_ACTUAL_COPY_OWNER")
        self.copy_owner = copies[0]
        return clock, clock._anchor().metadata, self.copy_owner, self.operative

    def manifest(self, *, context, copied, recipient):
        """Canonical supplied ADAPTER RETURN shape; never an exporter operation."""
        stages = D.A.stages
        github = {**context["observed"]["github"], "eventSha256": sha(self.event)}
        if self.kind == "worker":
            github.update(profile=stages.bootstrap.PROFILE, selection=context["observed"]["inputs"]["selection"])
        return {"schema": 4, "scope": D.E.SCOPE, "kind": self.kind,
            "selection": context["observed"]["inputs"]["selection"], "source": context["observed"]["source"],
            "github": github,
            "policy": {"origin": "reviewed-head", "commit": context["observed"]["source"]["commit"],
                "blob": hashlib.sha1(b"blob " + str(len(self.policy_raw)).encode("ascii") + b"\0" + self.policy_raw).hexdigest(),
                "path": D.I.POLICY_PATH, "sha256": sha(self.policy_raw),
                "fingerprint": self.policy["recipient"]["fingerprint"], "keySha256": sha(self.public),
                "expiresAt": self.policy["expiresAt"], "retentionDays": 14},
            "initialRecipient": {"authority": {"id": 12345,
                    "url": "https://github.com/" + D.I.REPOSITORY + "/issues/437#issuecomment-12345",
                    "bodySha256": sha(b"SUPPLIED_AUTHORITY_DECLARATION_NOT_AN_OWNER_STATEMENT"),
                    "owner": stages.joint.OWNER_LOGIN, "ownerId": stages.joint.OWNER_ID,
                    "createdAt": datetime.fromtimestamp(self.policy["notBefore"], timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")},
                "environment": {"name": stages.ENVIRONMENT, "id": 23456,
                    "branchPolicies": [{"id": 34560 + number, "name": name, "type": "branch"}
                        for number, name in enumerate(stages.BRANCHES)]},
                "originalBase": dict(stages.BASE), "reviewed": dict(context["observed"]["source"]),
                "firstUseAt": self.use, "notBefore": self.policy["notBefore"],
                "expiresAt": self.policy["expiresAt"], "matchSha256": context["authority"]["matchSha256"],
                "freshReturnSha256": context["authority"]["returnSha256"]},
            "primary": context["primary"], "copy": copied, "recipient": recipient,
            "artifact": {"name": D.native.posix.ARTIFACT, "sha256": sha(b"SUPPLIED_CIPHERTEXT_NOT_CREATED"), "size": 1},
            "testAcceptance": "NOT_PERFORMED", "productiveAuthority": False, "cacheAuthority": False,
            "exportSaveAuthority": False, "budgetAcceptance": "NOT_ADMITTED"}

    def export(self, evidence, output, recipient, **kwargs):
        """Explicit maintained-adapter supplier; call the ACTUAL driver guards."""
        if self.exports or recipient is not self.returned_recipient or Path(evidence) != self.destination or \
                Path(output) != self.output or self.output.exists():
            raise AssertionError("SUPPLIED_EXPORT_REQUIRES_ORIGINAL_RECIPIENT_AND_ABSENT_OUTPUT")
        self.exports.append((evidence, output, recipient, kwargs))
        self.child_owners()
        kwargs["check"]()
        self.export_hook()
        kwargs["check"]()
        value = self.manifest(context=self.context, copied=kwargs["copied"], recipient={
            "fingerprint": recipient.fingerprint, "encryptionFingerprint": recipient.encryption_fingerprint,
            "keySha256": recipient.key_sha256, "expiresAt": recipient.expires_at})
        self.manifest_raw = wire(value)
        self.output.mkdir(mode=0o700)
        put(self.output / D.native.posix.MANIFEST, self.manifest_raw)
        if kwargs["read_manifest"]() != self.manifest_raw:
            raise AssertionError("SUPPLIED_EXPORT_MANIFEST_READBACK")
        self.export_after()
        return self.export_return(self.manifest_raw)

    def open_copy(self):
        """Direct new copy-helper seam; no claim of upstream producer execution."""
        if self.copy_owner is not None:
            raise AssertionError("SUPPLIED_COPY_OWNER_REUSE")
        native = D.native.Owner(self.parent.deadline(45), self.parent,
            first=self.parent_first, cancelled=self.clock.cancelled)
        self.copy_owner = D._PrimaryOwner(native)
        self.copy_destination = D._private(self.copy_owner, self.destination)
        self.copy_work = D._private(self.copy_owner, self.work)
        return self.copy_owner

    def recipient_copy(self):
        if not self.validation_calls:
            self.validate(self.transport / "recipient-public.asc", self.policy["recipient"]["fingerprint"], self.work)
        if self.copy_owner is None:
            self.open_copy()
        pin = D.E._recipient_pin(self.returned_recipient, False, self.destination, self.output)
        self.summary_raw = wire({"schema": 1, "scope": "INITIAL_CUSTODY_ACTUAL_RECIPIENT_RETURN_V1",
            "contextSha256": sha(self.context_raw), "startSha256": sha(self.start_raw),
            "recipient": D._crypto_recipient_value(pin), "supplierReturned": True,
            "outerChild": "STILL_LIVE", "exportSaveAuthority": False})
        return D._copy_recipient(self.copy_owner, self.copy_destination, self.copy_work,
            self.primary_raw, self.authority_raw, self.context_raw, self.start_raw, self.summary_raw,
            self.public, lambda: D.E._recipient_current(pin))

    def freeze(self, copied, check=lambda: None):
        return D._freeze_custody_copy(self.copy_owner, self.copy_destination,
            self.primary_raw, self.authority_raw, copied, check)

    def setup_parent(self):
        """Supplied checked PRIOR outcomes; actual new parent owns every new row.

No PRIMARY, acquisition or AUTHORITY copy suite is imported or rerun. The new
parent checks/phase/close/registry/READ implementation is not patched out.
"""
        self.primary_input, self.authority_input = object(), object()
        match_type = D.A.gate.GateEligibility if self.kind == "gate" else D.A.stages.BootstrapMatch
        self.fresh = match_type(self.match_raw)
        self.history_raw = wire({"firstUseAt": self.use, "observed": self.observed, "matchSha256": sha(self.match_raw)})
        self.historical = tuple({"P/acquisition-queries/event.bin": self.event,
            "P/acquisition-queries/match.bin": self.match_raw,
            "P/acquisition-queries/candidate_policy_raw.bin": self.policy_raw}.items())
        self.captured, self.originals = {}, ()
        self.primary_bound = (self.parent, self.primary, self.history_raw, self.primary_raw, self.historical)
        self.authority_bound = (self.parent, self.fresh, self.captured, self.authority_return,
            self.authority_index, self.originals)
        self.stack.enter_context(patch.object(D, "checked_primary", self.checked_primary))
        self.stack.enter_context(patch.object(D, "checked_custody_authority", self.checked_authority))
        self.stack.enter_context(patch.object(D, "_copy_authority", self.supplied_authority_copy))
        self.stack.enter_context(patch.object(D.Q, "_inherited_context", lambda: {}))
        self.stack.enter_context(patch.object(D.native.processes, "make_scope", self.make_scope))

    def checked_primary(self, value):
        if value is not self.primary_input:
            raise AssertionError("SUPPLIED_PRIOR_PRIMARY_RETURN_IDENTITY")
        return self.primary_bound

    def checked_authority(self, value, primary):
        if value is not self.authority_input or primary is not self.primary_input:
            raise AssertionError("SUPPLIED_PRIOR_AUTHORITY_RETURN_IDENTITY")
        return self.authority_bound

    def supplied_authority_copy(self, owner, primary, authority, destination):
        if self.copy_calls or type(owner) is not D._PrimaryOwner or primary is not self.primary_input or \
                authority is not self.authority_input or destination.path != self.destination:
            raise AssertionError("SUPPLIED_PRIOR_AUTHORITY_COPY_BOUNDARY")
        self.copy_calls.append((owner, primary, authority, destination))
        return self.authority_raw

    def make_scope(self, job, invocation, state, home):
        scope = ParentScope(self, job, invocation, state, home)
        self.scopes.append(scope)
        return scope

    def closed_parent(self):
        returned = D.custody_crypto(self.primary_input, self.authority_input)
        self.parent_closed_hook()
        return returned


class ParentScope:
    """Memory-only native process supplier for the NEW parent/READ controls.

Real native.Owner rows/capture files/close checks and the parent registry run.
The child result below is an explicitly SUPPLIED closed-child outcome, not a
claim of authentic process, GPG, completed payload, or child timing evidence.
No helper here writes a private production return registry.
"""
    def __init__(self, rig, job, invocation, state, home):
        self.rig, self.job, self.invocation, self.state, self.home = rig, job, invocation, state, home
        self.name, self.baseline = D.native.BACKENDS["linux-x64"], {(8000, 4000)}
        self.leader = {"pid": os.getpid() + 100000, "startTicks": 5000}
        self.launch, self.child = None, None
        self.closed, self.close_calls, self.spawn_calls, self.drains = False, 0, 0, []

    def _identity(self, pid):
        return {"pid": pid, "startTicks": 4000, "live": True}

    def spawn(self, argv, cwd, environment, *, stdout, stderr):
        if self.spawn_calls or any(name in environment for name in D._CREDENTIAL_NAMES):
            raise AssertionError("SUPPLIED_PARENT_SINGLE_TOKEN_FREE_LAUNCH")
        self.spawn_calls += 1
        self.launch = {"created": True, "requestedArgv": list(argv), "resolvedArgv": list(argv),
            "cwd": cwd, "pid": self.leader["pid"], "api": "subprocess.Popen", "shell": False,
            "executable": argv[0], "outputMode": "caller-owned-files"}
        rig = self.rig
        context_raw = (Path(self.state) / "context.json").read_bytes()
        start_raw = (Path(self.state) / "crypto-service" / "start.json").read_bytes()
        context, start = json.loads(context_raw), json.loads(start_raw)
        rig.context_raw, rig.context, rig.start_raw, rig.start = context_raw, context, start_raw, start
        copied = {"mapSha256": "9" * 64, "memberCount": 8, "totalBytes": 99,
            "origins": {origin: str(number) * 64 for number, origin in enumerate(D.ORIGINS, 1)}}
        recipient = {"fingerprint": rig.policy["recipient"]["fingerprint"], "encryptionFingerprint": "E" * 40,
            "keySha256": sha(rig.public), "expiresAt": rig.policy["expiresAt"] + 3600}
        rig.manifest_raw = wire(rig.manifest(context=context, copied=copied, recipient=recipient))
        now = rig.clock.raw
        child = {"schema": 1, "scope": D._CRYPTO_CHILD_SCOPE, "contextSha256": sha(context_raw),
            "startSha256": sha(start_raw), "invocation": self.invocation, "clock": D.O.clock_value(rig.clock.identity),
            "bootDigest": BOOT, "launchMinimumNs": int(argv[-1]), "beganNs": now,
            "metadataLastNs": now, "metadataCloseSha256": "c" * 64,
            "validationStartedNs": now, "validationReturnedNs": now, "exportedNs": now,
            "recipientReturnSha256": "d" * 64, "recipient": recipient, "copy": copied,
            "freezeMetadataSha256": "e" * 64,
            "sourceMetadataSha256": {origin: str(number) * 64 for number, origin in enumerate(D.ORIGINS, 4)},
            "manifest": {"bytes": len(rig.manifest_raw), "sha256": sha(rig.manifest_raw),
                "base64": base64.b64encode(rig.manifest_raw).decode("ascii")},
            "retirement": "PENDING_CHILD_CLOSE", "budgetAcceptance": "NOT_ADMITTED", "exportSaveAuthority": False}
        ack = {"schema": 1, "scope": D._CRYPTO_ACK_SCOPE, "invocation": self.invocation,
            "terminalSha256": sha(wire(child)), "clock": D.O.clock_value(rig.clock.identity), "closedNs": now,
            "ownerCloseSha256": "f" * 64, "fileResourceCount": 1, "operativeResourceCount": 1}
        rig.child_mutation(child, ack)
        rig.child_raw, rig.ack_raw = wire(child), wire(ack)
        put(Path(self.state) / "crypto-child-result.json", rig.child_raw)
        rig.output.mkdir(mode=0o700)
        put(rig.output / D.native.posix.MANIFEST, rig.manifest_raw)
        if stdout.write(rig.ack_raw) != len(rig.ack_raw) or stderr.verify().size != 0:
            raise AssertionError("SUPPLIED_PARENT_CAPTURE_INPUTS")
        self.child = SimpleNamespace(pid=self.leader["pid"], stdout=None, stderr=None, poll=lambda: 0)
        return self.child

    def description(self):
        return {"backend": self.name, "job": self.job, "invocation": self.invocation,
            "scope": "controlled-marker-inheriting-descendants", "discoveryErrors": [],
            "launches": [] if self.launch is None else [dict(self.launch)],
            "startedIdentities": [] if self.launch is None else [dict(self.leader)], "discoveryReconciliations": []}

    def discover(self):
        return []

    def drain(self, *, grace, kill_wait, deadline):
        self.drains.append((grace, kill_wait, deadline))
        if self.rig.clock.local >= deadline:
            raise RuntimeError("SUPPLIED_PARENT_ORIGINAL_NATIVE_CEILING")
        return []

    def close(self):
        if self.closed:
            raise AssertionError("SUPPLIED_PARENT_SCOPE_CLOSE_RETRY")
        self.close_calls += 1
        self.closed = True


class WindowsInventory:
    """Full6-directory/9-file Windows grammar, supplied snapshot/read boundary.

No Windows os.name override, WinDLL, NativeFile or real native Windows owner is
constructed. Actual new inventory grammar and unchanged byte consumption run
against immutable explicitly modeled FileInfo declarations and tiny memory.
"""
    def __init__(self, rig):
        self.rig, self.stack = rig, ExitStack()
        self.operations = tuple("gpg-" + str(number) * 32 for number in (1, 2, 3))
        self.result = "recipient-validation-result-" + "4" * 32 + ".json"
        self.directory_names = ("", "gnupg", "tmp", *self.operations)
        self.files = {"recipient.asc": rig.public, "recipient.gpg": rig.ring,
            self.result: wire({"scope": "SUPPLIED_WINDOWS_PUBLIC_VALIDATION_RESULT"})}
        for name in self.operations:
            self.files[name + "/stdout"] = b"SUPPLIED_WINDOWS_STDOUT"
            self.files[name + "/stderr"] = b""
        self.entries, self.reads = {}, []
        self.path = Path("/SUPPLIED/windows-validation-roster")

    def rebuild(self):
        self.entries = {}
        for number, name in enumerate(sorted((*self.directory_names, *self.files)), 1):
            self.entries[name] = D.native.windows.FileInfo((17, format(number, "032x")),
                name in self.directory_names, 0 if name in self.directory_names else len(self.files[name]),
                1, 0x10 if name in self.directory_names else 0x80, 100, 101, 102)

    def __enter__(self):
        self.rebuild()
        owner = self.rig.open_copy()
        self.work = SimpleNamespace(path=self.path, identity=self.entries[""].identity)
        self.snapshot = D._PrimarySnapshot(D.ORIGINS[2], self.path, self.work, self.work.identity,
            None, self.entries, D._snapshot_metadata(self.entries, True), D.N._history_graph(self.entries, self.path), True)
        owner.retain_snapshot(self.snapshot)
        self.stack.enter_context(patch.object(D, "_snapshot", self.supplied_snapshot))
        self.stack.enter_context(patch.object(D, "_snapshot_reader", self.supplied_reader))
        self.stack.enter_context(patch.object(D, "_snapshot_current", self.supplied_current))
        return self

    def __exit__(self, *args):
        return self.stack.__exit__(*args)

    def supplied_snapshot(self, owner, group, work):
        if owner is not self.rig.copy_owner or group != D.ORIGINS[2] or work is not self.work:
            raise AssertionError("SUPPLIED_WINDOWS_SINGLE_SNAPSHOT")
        return self.snapshot

    def supplied_reader(self, owner, snapshot, name):
        if owner is not self.rig.copy_owner or snapshot is not self.snapshot or name not in self.files:
            raise AssertionError("SUPPLIED_WINDOWS_READER_BOUNDARY")
        self.reads.append(name)
        raw = self.files[name]
        reader = owner.acquire("reader", lambda: io.BytesIO(raw))
        def verify():
            if reader.getvalue() != raw or self.files[name] != raw:
                raise AssertionError("SUPPLIED_WINDOWS_READER_CHANGED")
        return reader, verify

    def supplied_current(self, owner, snapshot, *, rescan=False):
        if owner is not self.rig.copy_owner or snapshot is not self.snapshot or \
                D._snapshot_metadata(self.entries, True) != self.snapshot.metadata:
            raise AssertionError("SUPPLIED_WINDOWS_SNAPSHOT_CHANGED")

    def inventory(self):
        return D._recipient_inventory(self.rig.copy_owner, self.work, self.rig.public)


class RecipientExportTests(unittest.TestCase):
    def test_same_child_validation_copy_freeze_export_preserves_all_three_origins(self):
        for kind in ("gate", "worker"):
            with self.subTest(kind=kind), Workspace(kind) as rig:
                ack, clock, limit = rig.child()
                actual_clock, metadata_owner, copy_owner, operative = rig.child_owners()
                self.assertIs(clock, actual_clock)
                self.assertEqual(limit, clock.work)
                self.assertEqual(ack["scope"], D._CRYPTO_ACK_SCOPE)
                self.assertEqual(len(rig.validation_calls), 1)
                self.assertEqual(len(rig.exports), 1)
                evidence, output, recipient, kwargs = rig.exports[0]
                self.assertIs(recipient, rig.returned_recipient)
                self.assertEqual((Path(evidence), Path(output)), (rig.destination, rig.output))
                self.assertEqual(kwargs["kind"], kind)
                self.assertEqual(kwargs["selection"], rig.observed["inputs"]["selection"])
                self.assertEqual((kwargs["source_commit"], kwargs["source_tree"]),
                    (rig.observed["source"]["commit"], rig.observed["source"]["tree"]))
                self.assertEqual(kwargs["primary"], rig.primary_fields)
                self.assertEqual(kwargs["authority"], {"returnSha256": sha(rig.authority_return),
                    "matchSha256": sha(rig.match_raw)})
                self.assertEqual(kwargs["event_raw"], rig.event)
                self.assertEqual(kwargs["policy_raw"], rig.policy_raw)
                self.assertIsNot(kwargs["original_match"], kwargs["fresh_match"])
                self.assertEqual(kwargs["original_match"].record, rig.match_raw)
                self.assertEqual(kwargs["fresh_match"].record, rig.match_raw)
                self.assertEqual((kwargs["max_bytes"], kwargs["max_members"]), (512 * 1024 * 1024, 10000))
                self.assertGreater(kwargs["timeout_seconds"], 0)
                self.assertLessEqual(kwargs["timeout_seconds"], 240)
                self.assertLessEqual(kwargs["timeout_seconds"], (clock.work - rig.clock.raw) // NS)
                self.assertTrue(metadata_owner.finished and copy_owner.finished and operative.closed)
                self.assertIsNot(metadata_owner.owner, copy_owner.owner)
                self.assertIsNot(copy_owner.owner, operative)
                self.assertIs(copy_owner.owner.fence, clock)
                self.assertIs(copy_owner.owner.first, operative.first)
                self.assertIs(metadata_owner.owner.first, operative.first)
                self.assertTrue(all(a and c for _r, _l, _v, a, c in metadata_owner.rows))
                self.assertTrue(all(a and c for _r, _l, _v, a, c in copy_owner.rows))
                operative.known()
                self.assertEqual(ack["fileResourceCount"], len(copy_owner.rows))
                self.assertEqual(ack["operativeResourceCount"], len(operative._anchor().rows))
                child_raw = (rig.transport / "crypto-child-result.json").read_bytes()
                child = json.loads(child_raw)
                self.assertEqual(ack["terminalSha256"], sha(child_raw))
                self.assertEqual(child["retirement"], "PENDING_CHILD_CLOSE")
                self.assertEqual(child["manifest"], {"bytes": len(rig.manifest_raw), "sha256": sha(rig.manifest_raw),
                    "base64": base64.b64encode(rig.manifest_raw).decode("ascii")})
                maps = {name: (rig.destination / name).read_bytes()
                    for name in ("primary-map.json", "authority-map.json", "recipient-map.json", "copy-map.json")}
                self.assertEqual(maps["primary-map.json"], rig.primary_raw)
                self.assertEqual(maps["authority-map.json"], rig.authority_raw)
                recipient_map = json.loads(maps["recipient-map.json"])
                self.assertEqual(recipient_map["origin"], D.ORIGINS[2])
                self.assertEqual(recipient_map["validationInventory"]["fileCount"], 10)
                self.assertEqual(recipient_map["validationInventory"]["directoryCount"], 5)
                self.assertEqual(recipient_map["memberCount"], 13)
                self.assertEqual(recipient_map["previousMemberCount"], 4)
                self.assertEqual(recipient_map["aggregateMemberCount"], 17)
                self.assertEqual(recipient_map["outerChild"], "STILL_LIVE")
                for number, raw in enumerate((*rig.primary_bytes, *rig.authority_bytes)):
                    name = D._member_name(number)
                    self.assertEqual((rig.destination / name).read_bytes(), raw)
                    self.assertEqual(D.native.posix._stamp((rig.destination / name).stat()), rig.prior_stamps[name])
                for item in recipient_map["members"]:
                    raw = (rig.destination / item["member"]).read_bytes()
                    self.assertEqual((len(raw), sha(raw)), (item["bytes"], item["sha256"]))
                    self.assertEqual(item["origin"], D.ORIGINS[2])
                complete = [snapshot for snapshot in copy_owner.snapshots if snapshot.group == "COMPLETED_THREE_ORIGIN_FREEZE"]
                self.assertEqual(len(complete), 1)
                actual_bytes = sum(path.stat().st_size for path in rig.destination.iterdir())
                self.assertEqual(kwargs["copied"]["memberCount"], 21)
                self.assertEqual(kwargs["copied"]["totalBytes"], actual_bytes)
                self.assertEqual(len(complete[0].metadata), 22)  # Root also consumes the aggregate member allowance.
                self.assertEqual(child["copy"], kwargs["copied"])
                self.assertEqual(child["freezeMetadataSha256"],
                    sha(wire({"metadata": D._crypto_metadata(complete[0])})))
                self.assertEqual(child["sourceMetadataSha256"], {origin: sha(wire({"metadata": json.loads(maps[name])["sourceMetadata"]}))
                    for origin, name in zip(D.ORIGINS, ("primary-map.json", "authority-map.json", "recipient-map.json"))})
                self.assertFalse((rig.transport / "custody-return.json").exists())
                self.assertEqual(D._CRYPTO_RETURNS, {})  # A leaf ACK never mints the parent return.

    def test_recipient_return_cannot_be_replaced_by_files_or_equal_object_graph(self):
        for label in ("no-return", "dictionary-return", "wrong-work-pin", "wrong-key", "expires-before-policy",
                "equal-dictionary", "equal-object-graph", "equal-home-path", "equal-work-tuple", "late-field"):
            with self.subTest(refused=label), Workspace() as rig:
                fired = []
                if label == "no-return":
                    rig.validation_return = lambda _recipient: None
                elif label == "dictionary-return":
                    rig.validation_return = lambda recipient: dict(recipient.__dict__)
                elif label in ("wrong-work-pin", "wrong-key", "expires-before-policy"):
                    def wrong_supplier_value():
                        recipient = rig.returned_recipient
                        if label == "wrong-work-pin":
                            object.__setattr__(recipient, "work_identity", (17, 999))
                        elif label == "wrong-key":
                            object.__setattr__(recipient, "key_sha256", "0" * 64)
                        else:
                            object.__setattr__(recipient, "expires_at", rig.policy["expiresAt"] - 1)
                    rig.validation_hook = wrong_supplier_value
                else:
                    def mutate_after_actual_pin():
                        if rig.returned_recipient is None or fired:
                            return
                        fired.append(True)
                        recipient = rig.returned_recipient
                        if label == "equal-dictionary":
                            object.__setattr__(recipient, "__dict__", dict(recipient.__dict__))
                        elif label == "equal-object-graph":
                            lookalike = D.native.posix.Recipient(**recipient.__dict__)
                            # The supplier's SAME object now has a replacement
                            # equal graph, not a newly accepted live Recipient.
                            object.__setattr__(recipient, "__dict__", lookalike.__dict__)
                        elif label == "equal-home-path":
                            object.__setattr__(recipient, "home", Path(str(recipient.home)))
                        elif label == "equal-work-tuple":
                            object.__setattr__(recipient, "work_identity", tuple(list(recipient.work_identity)))
                        else:
                            object.__setattr__(recipient, "fingerprint", "F" * 40)
                    rig.clock.hook = mutate_after_actual_pin
                with self.assertRaises(Exception) as caught:
                    rig.child()
                self.assertNotIsInstance(caught.exception, (AttributeError, NameError, TypeError))
                self.assertEqual(len(rig.validation_calls), 1)
                self.assertEqual(rig.exports, [])
                self.assertFalse((rig.transport / "crypto-child-result.json").exists())
                self.assertEqual(D._CRYPTO_RETURNS, {})
                if label in ("equal-dictionary", "equal-object-graph", "equal-home-path", "equal-work-tuple", "late-field"):
                    self.assertEqual(fired, [True])

    def test_recipient_copy_enforces_complete_shallow_public_validation_inventory(self):
        for additional in (0, 32):
            with self.subTest(posix_public_files_per_home=additional), Workspace() as rig:
                rig.validate(rig.transport / "recipient-public.asc", rig.policy["recipient"]["fingerprint"], rig.work)
                for directory in ("gnupg", "tmp"):
                    for number in range(additional):
                        put(rig.work / directory / ("public-" + format(number, "02d")), b"SUPPLIED_PUBLIC_METADATA")
                rig.open_copy()
                source, inventory = D._recipient_inventory(rig.copy_owner, rig.copy_work, rig.public)
                self.assertEqual(inventory["fileCount"], 10 + 2 * additional)
                self.assertEqual(inventory["directoryCount"], 5)
                self.assertEqual(len(source.metadata), inventory["fileCount"] + 5)
                self.assertEqual(inventory["totalBytes"], sum(item["bytes"] for item in inventory["files"]))
                self.assertTrue(all(item["provenance"] == "ACTUAL_SAME_CHILD_VALIDATION_ORIGINAL"
                    for item in inventory["files"]))
                self.assertEqual({item["relative"] for item in inventory["directories"]},
                    {"", "gnupg", "tmp", "gpg-supplied_one", "gpg-supplied_two"})
                rig.copy_owner.finish()

        for label in ("extra-root", "deep", "fifo", "symlink", "hardlink", "case-unsafe", "missing-process",
                "private-home", "too-many-home-members", "wrong-public", "wrong-ring", "diagnostic-cap", "total-cap"):
            with self.subTest(posix_refused=label), Workspace() as rig:
                rig.validate(rig.transport / "recipient-public.asc", rig.policy["recipient"]["fingerprint"], rig.work)
                if label == "extra-root":
                    put(rig.work / "unexpected", b"x")
                elif label == "deep":
                    (rig.work / "gnupg" / "nested").mkdir(mode=0o700)
                    put(rig.work / "gnupg" / "nested" / "item", b"x")
                elif label == "fifo":
                    os.mkfifo(rig.work / "gnupg" / "pipe", 0o600)
                elif label == "symlink":
                    (rig.work / "gnupg" / "linked").symlink_to(rig.work / "recipient.asc")
                elif label == "hardlink":
                    os.link(rig.work / "recipient.asc", rig.work / "gnupg" / "linked")
                elif label == "case-unsafe":
                    put(rig.work / "Recipient.asc", rig.public)
                elif label == "missing-process":
                    (rig.work / "gpg-supplied_one" / "process.json").unlink()
                elif label == "private-home":
                    put(rig.work / "gnupg" / "private-key", b"SUPPLIED_FORBIDDEN_NAME_NOT_A_KEY")
                elif label == "too-many-home-members":
                    for number in range(33):
                        put(rig.work / "tmp" / ("public-" + format(number, "02d")), b"")
                elif label in ("wrong-public", "wrong-ring"):
                    target = rig.work / ("recipient.asc" if label == "wrong-public" else "recipient.gpg")
                    target.write_bytes(b"SUPPLIED_CHANGED_PUBLIC_ENCODING")
                rig.open_copy()
                with ExitStack() as negative:
                    if label == "diagnostic-cap":
                        negative.enter_context(patch.object(D.native.posix, "MAX_DIAGNOSTIC_BYTES", 1))
                    elif label == "total-cap":
                        negative.enter_context(patch.object(D.N, "CRYPTO_ORIGINALS_LIMIT", len(rig.public) - 1))
                    with self.assertRaises(Exception) as caught:
                        D._recipient_inventory(rig.copy_owner, rig.copy_work, rig.public)
                self.assertNotIsInstance(caught.exception, (AttributeError, NameError, TypeError))
                self.assertEqual(rig.exports, [])

        with Workspace() as rig, WindowsInventory(rig) as model:
            source, inventory = model.inventory()
            self.assertTrue(source.windows)
            self.assertEqual((inventory["directoryCount"], inventory["fileCount"]), (6, 9))
            self.assertEqual(set(model.reads), set(model.files))
            homes = {row["relative"]: row["members"] for row in inventory["directories"]}
            self.assertEqual((homes["gnupg"], homes["tmp"]), ([], []))
            self.assertTrue(all(homes[name] == ["stderr", "stdout"] for name in model.operations))
            rig.copy_owner.finish()
        for label in ("nonempty-home", "missing-result", "missing-operation", "fourth-operation", "bad-operation-name",
                "extra-status", "wrong-ring"):
            with self.subTest(windows_model_refused=label), Workspace() as rig:
                model = WindowsInventory(rig)
                if label == "nonempty-home":
                    model.files["gnupg/public"] = b"x"
                elif label == "missing-result":
                    del model.files[model.result]
                elif label == "missing-operation":
                    model.directory_names = tuple(name for name in model.directory_names if name != model.operations[0])
                    for leaf in ("stdout", "stderr"):
                        del model.files[model.operations[0] + "/" + leaf]
                elif label in ("fourth-operation", "bad-operation-name"):
                    name = "gpg-" + ("5" * 32 if label == "fourth-operation" else "not-a-windows-uuid")
                    model.directory_names += (name,)
                    model.files[name + "/stdout"] = model.files[name + "/stderr"] = b""
                elif label == "extra-status":
                    model.files[model.operations[0] + "/status"] = b""
                else:
                    model.files["recipient.gpg"] = b"SUPPLIED_CHANGED_RING"
                with model:
                    with self.assertRaises(Exception) as caught:
                        model.inventory()
                    self.assertNotIsInstance(caught.exception, (AttributeError, NameError, TypeError))

    def test_map_files_are_exact_separate_bounded_and_nonselfreferential(self):
        with Workspace() as rig:
            copied = rig.recipient_copy()
            frozen = rig.freeze(copied)
            self.assertEqual(tuple(name for name, _raw in frozen.maps),
                ("primary-map.json", "authority-map.json", "recipient-map.json", "copy-map.json"))
            self.assertEqual(frozen.maps[:3], (("primary-map.json", rig.primary_raw),
                ("authority-map.json", rig.authority_raw), ("recipient-map.json", copied.raw)))
            combined = json.loads(frozen.maps[3][1])
            self.assertEqual(set(combined), {"schema", "scope", "origins", "dataMemberCount", "dataTotalBytes",
                "payloadMembersExcludingThisMap", "payloadBytesExcludingThisMap", "destination",
                "destinationIdentity", "contentState", "exportSaveAuthority"})
            self.assertEqual(set(combined["origins"]), set(D.ORIGINS))
            for origin, (name, raw) in zip(D.ORIGINS, frozen.maps[:3]):
                origin_map = json.loads(raw)
                self.assertEqual(combined["origins"][origin], {"mapFile": name, "bytes": len(raw), "sha256": sha(raw),
                    "memberCount": origin_map["memberCount"], "totalBytes": origin_map["totalBytes"]})
                self.assertLessEqual(len(raw), 2 * 1024 * 1024)
                self.assertNotIn("mapBase64", origin_map)
                self.assertNotIn("finalMetadata", origin_map)
            self.assertLessEqual(len(frozen.maps[3][1]), 65536)
            self.assertEqual(combined["payloadMembersExcludingThisMap"], len(frozen.members) + 3)
            data_bytes = sum(item["bytes"] for item in frozen.members)
            self.assertEqual(combined["dataTotalBytes"], data_bytes)
            self.assertEqual(combined["payloadBytesExcludingThisMap"], data_bytes + sum(len(raw) for _, raw in frozen.maps[:3]))
            summary = json.loads(frozen.copied)
            self.assertEqual(summary["totalBytes"], combined["payloadBytesExcludingThisMap"] + len(frozen.maps[3][1]))
            self.assertEqual(summary["memberCount"], len(frozen.members) + 4)
            total, count = D._aggregate(tuple(rig.copy_owner.snapshots))
            self.assertEqual(total, sum(row[3] for snap in rig.copy_owner.snapshots for row in snap.metadata if not row[1]))
            self.assertEqual(count, sum(len(snap.metadata) for snap in rig.copy_owner.snapshots))
            self.assertGreater(count, summary["memberCount"] + 1)
            rig.copy_owner.finish()

        for label in ("empty-primary", "primary-relabel", "authority-relabel", "duplicate-prior", "changed-origin-bytes"):
            with self.subTest(map_refused=label), Workspace() as rig:
                if label == "empty-primary":
                    rig.primary_map["members"] = []
                elif label == "primary-relabel":
                    rig.primary_map["origin"] = D.ORIGINS[1]
                elif label == "authority-relabel":
                    rig.authority_map["origin"] = D.ORIGINS[0]
                elif label == "duplicate-prior":
                    rig.authority_map["members"][0]["member"] = D._member_name(0)
                else:
                    (rig.destination / D._member_name(0)).write_bytes(b"SUPPLIED_REPLACED_PRIOR")
                rig.primary_raw = wire(rig.primary_map)
                rig.authority_map["primaryCopySha256"] = sha(rig.primary_raw)
                rig.authority_raw = wire(rig.authority_map)
                with self.assertRaises(Exception) as caught:
                    rig.recipient_copy()
                self.assertNotIsInstance(caught.exception, (AttributeError, NameError, TypeError))
                self.assertEqual(rig.exports, [])

        for label in ("origin-map-cap", "combined-map-cap", "arbitrary-map-name", "aggregate-map-bytes", "aggregate-root-members"):
            with self.subTest(bound_refused=label), Workspace() as rig:
                copied = rig.recipient_copy()
                owner, destination = rig.copy_owner, rig.copy_destination
                with ExitStack() as negative:
                    if label == "origin-map-cap":
                        negative.enter_context(patch.object(D.native, "LIMIT", len(rig.primary_raw) - 1))
                        operation = lambda: D._write_custody_map(owner, destination, "primary-map.json", rig.primary_raw)
                    elif label == "combined-map-cap":
                        original = D.canonical
                        def artificial_small_combined(raw, maximum=D.native.LIMIT):
                            return original(raw, 8 if maximum == 65536 else maximum)
                        negative.enter_context(patch.object(D, "canonical", artificial_small_combined))
                        operation = lambda: D._write_custody_map(owner, destination, "copy-map.json", wire({"tiny": "combined"}))
                    elif label == "arbitrary-map-name":
                        operation = lambda: D._write_custody_map(owner, destination, "foreign-map.json", wire({"x": 1}))
                    elif label == "aggregate-map-bytes":
                        used = sum(row[3] for snap in owner.snapshots for row in snap.metadata if not row[1])
                        negative.enter_context(patch.object(D, "MAX_BYTES", used))
                        operation = lambda: rig.freeze(copied)
                    else:
                        used = sum(len(snap.metadata) for snap in owner.snapshots)
                        negative.enter_context(patch.object(D, "MAX_MEMBERS", used + 3))
                        operation = lambda: rig.freeze(copied)
                    with self.assertRaisesRegex(Exception, "RECORD_LIMIT|CRYPTO_FIXED_MAP_NAME|COPY_AGGREGATE_CAP"):
                        operation()
                # All artificial negative caps are restored before actual cleanup.
                self.assertFalse(any((rig.destination / name).exists() for name in
                    ("primary-map.json", "authority-map.json", "recipient-map.json", "copy-map.json")))

    def test_export_requires_complete_unchanged_freeze_and_retired_validation_readers(self):
        with Workspace() as rig:
            at_export = []
            def inspect_cut_and_add_backend_work():
                clock, metadata_owner, owner, operative = rig.child_owners()
                at_export.append(True)
                self.assertTrue(metadata_owner.finished)
                self.assertFalse(owner.finished)
                self.assertFalse(operative.closed)
                self.assertIs(operative.fence, clock)
                self.assertIsNot(owner.owner, operative)
                source = next(snap for snap in owner.snapshots if snap.group == D.ORIGINS[2])
                frozen = [snap for snap in owner.snapshots if snap.group == "COMPLETED_THREE_ORIGIN_FREEZE"]
                self.assertEqual(len(frozen), 1)
                self.assertTrue(source.directory.closed)
                self.assertFalse(frozen[0].directory.closed)
                for _row, label, resource, attempted, closed in owner.rows:
                    if resource is frozen[0].directory:
                        self.assertEqual((attempted, closed), (False, False))
                    else:
                        self.assertTrue(attempted and closed, "Every source reader/Snapshot/writer must retire before export")
                    if label == "writer":
                        self.assertTrue(closed)
                live_work = [resource for _row, label, resource, _a, _c in operative._anchor().rows
                    if label == "directory" and resource.path == rig.work]
                self.assertEqual(len(live_work), 1)
                self.assertFalse(live_work[0].closed)
                self.assertEqual(len(tuple(rig.destination.iterdir())), 21)
                # New backend work belongs OUTSIDE the frozen copied payload.
                # The original validation snapshot remains immutable history.
                put(rig.work / "supplied-export-work-record", b"SUPPLIED_POST_VALIDATION_BACKEND_ADDITION")
            rig.export_hook = inspect_cut_and_add_backend_work
            ack, _clock, _limit = rig.child()
            self.assertEqual(at_export, [True])
            self.assertEqual(ack["scope"], D._CRYPTO_ACK_SCOPE)
            self.assertTrue((rig.work / "supplied-export-work-record").exists())
            copied_map = json.loads((rig.destination / "recipient-map.json").read_bytes())
            self.assertNotIn("supplied-export-work-record", {row["relative"] for row in copied_map["validationInventory"]["files"]})

        for label in ("changed-data", "late-added-data", "changed-map", "missing-map", "equal-freeze-dictionary",
                "same-dictionary-recipient-map-bytes"):
            with self.subTest(export_cut_refused=label), Workspace() as rig:
                returned, copies = [], []
                original_freeze, original_copy = D._freeze_custody_copy, D._copy_recipient
                def record_actual_freeze(*args, **kwargs):
                    value = original_freeze(*args, **kwargs)
                    returned.append(value)
                    return value
                def record_actual_copy(*args, **kwargs):
                    value = original_copy(*args, **kwargs)
                    copies.append(value)
                    return value
                def corrupt_cut():
                    if label == "changed-data":
                        (rig.destination / D._member_name(0)).write_bytes(b"SUPPLIED_LATE_PAYLOAD_CHANGE")
                    elif label == "late-added-data":
                        put(rig.destination / "late-member", b"x")
                    elif label == "changed-map":
                        (rig.destination / "recipient-map.json").write_bytes(wire({"changed": True}))
                    elif label == "missing-map":
                        (rig.destination / "authority-map.json").unlink()
                    elif label == "equal-freeze-dictionary":
                        object.__setattr__(returned[0], "__dict__", dict(returned[0].__dict__))
                    else:
                        changed = json.loads(copies[0].raw)
                        changed["sourceMetadata"] = [["SUPPLIED_CHANGED_SOURCE_AFTER_FREEZE"]]
                        copies[0].__dict__["raw"] = wire(changed)
                rig.export_hook = corrupt_cut
                with patch.object(D, "_freeze_custody_copy", record_actual_freeze), \
                        patch.object(D, "_copy_recipient", record_actual_copy):
                    with self.assertRaises(Exception) as caught:
                        rig.child()
                self.assertNotIsInstance(caught.exception, (AttributeError, NameError, TypeError))
                self.assertEqual(len(returned), 1)
                self.assertEqual(len(rig.exports), 1)
                self.assertFalse((rig.transport / "crypto-child-result.json").exists())
                self.assertFalse(rig.output.exists())

        with Workspace() as rig:
            first = FalseyFailure("SUPPLIED_VALIDATION_READER_CLOSE_UNKNOWN")
            closing, close_calls = [], []
            original_copy, original_close = D._copy_recipient, D.Q._PosixDirectory.close
            def capture_copy_owner(owner, *args, **kwargs):
                rig.copy_owner = owner
                return original_copy(owner, *args, **kwargs)
            def refuse_original_source_close(directory):
                source = (next((snap for snap in rig.copy_owner.snapshots if snap.group == D.ORIGINS[2]), None)
                    if rig.copy_owner is not None else None)
                if source is not None and directory is source.directory:
                    close_calls.append(directory)
                    closing.append(source)
                    original_close(directory)
                    raise first  # Unknown supplier close return, despite a now-closed file facade.
                return original_close(directory)
            with patch.object(D, "_copy_recipient", capture_copy_owner), \
                    patch.object(D.Q._PosixDirectory, "close", refuse_original_source_close):
                with self.assertRaises(FalseyFailure) as caught:
                    rig.child()
            self.assertIs(caught.exception, first)
            self.assertEqual(len(close_calls), 1)
            self.assertEqual(rig.exports, [])
            self.assertIs(rig.copy_owner.failure, first)
            self.assertTrue(rig.copy_owner.owner.unknown)
            self.assertFalse(any(snap.group == "COMPLETED_THREE_ORIGIN_FREEZE" for snap in rig.copy_owner.snapshots))
            self.assertTrue(closing[0].directory.closed)

    def test_child_retains_actual_export_bytes_and_requires_known_owner_close(self):
        for label in ("file-only-no-return", "dictionary-not-bytes", "changed-return", "changed-readback",
                "late-export-return", "falsey-file-owner-close", "falsey-operative-close"):
            with self.subTest(child_return_refused=label), Workspace() as rig:
                primary = FalseyFailure("SUPPLIED_CHILD_ORIGINAL_CLOSE_FAILURE")
                close_calls, late = [], []
                original_close = D.Q._PosixDirectory.close
                if label == "file-only-no-return":
                    rig.export_return = lambda _raw: None
                elif label == "dictionary-not-bytes":
                    rig.export_return = json.loads
                elif label == "changed-return":
                    rig.export_return = lambda raw: wire({**json.loads(raw), "testAcceptance": "SUPPLIED_CHANGED_RETURN"})
                elif label == "changed-readback":
                    def replace_file_after_adapter_read():
                        (rig.output / D.native.posix.MANIFEST).write_bytes(wire({"changedAfterAdapterRead": True}))
                    rig.export_after = replace_file_after_adapter_read
                elif label == "late-export-return":
                    def expire_after_adapter_return():
                        def expire():
                            if late:
                                return
                            late.append(True)
                            guard = next(iter(D._CUSTODY_CHILD_CLOCKS.values())).handle
                            rig.clock.raw = guard.work
                        rig.clock.hook = expire
                    rig.export_after = expire_after_adapter_return
                def close_original_once(directory):
                    target = None
                    if rig.copy_owner is not None:
                        if label == "falsey-file-owner-close":
                            target = next((snap.directory for snap in rig.copy_owner.snapshots
                                if snap.group == "COMPLETED_THREE_ORIGIN_FREEZE"), None)
                        elif label == "falsey-operative-close" and rig.operative._anchor().frozen is not None:
                            target = next(resource for _row, name, resource, _a, _c in rig.operative._anchor().rows
                                if name == "directory" and resource.path == rig.transport)
                    if directory is target:
                        close_calls.append(directory)
                        original_close(directory)
                        raise primary
                    return original_close(directory)
                with patch.object(D.Q._PosixDirectory, "close", close_original_once):
                    with self.assertRaises(Exception) as caught:
                        rig.child()
                self.assertNotIsInstance(caught.exception, (AttributeError, NameError, TypeError))
                self.assertEqual(len(rig.exports), 1)
                self.assertTrue((rig.output / D.native.posix.MANIFEST).exists())
                self.assertEqual(D._CRYPTO_RETURNS, {})
                self.assertEqual(D._CRYPTO_CARRIERS, {})
                if label.startswith("falsey-"):
                    self.assertIs(caught.exception, primary)
                    self.assertEqual(len(close_calls), 1)
                    owner = rig.copy_owner.owner if label == "falsey-file-owner-close" else rig.operative
                    self.assertTrue(owner.unknown)
                    self.assertIs(owner.original, primary)
                    child = json.loads((rig.transport / "crypto-child-result.json").read_bytes())
                    self.assertEqual(child["retirement"], "PENDING_CHILD_CLOSE")
                elif label == "late-export-return":
                    self.assertEqual(late, [True])
                    self.assertFalse((rig.transport / "crypto-child-result.json").exists())

    def test_read_stage_owner_requires_original_known_closed_parent_return(self):
        for kind in ("gate", "worker"):
            with self.subTest(read_delegation=kind), Workspace(kind, parent_mode=True) as rig:
                returned = rig.closed_parent()
                saved = D._CRYPTO_RETURNS[id(returned)]
                parent_owner = saved[2]
                self.assertTrue(parent_owner.closed)
                parent_owner.known()
                self.assertIs(saved[1], rig.parent)
                original_first = rig.parent._view().binding[0]
                original_binding = rig.parent._view().binding
                before_metadata = set(D._PRIMARY_OWNERS)
                # The native parent is already known closed. READ can use only
                # the earlier original readEnd, including after nativeFinal.
                rig.clock.raw = rig.parent.final + NS
                rig.clock.local = 100.0 + (rig.clock.raw - original_first.nanoseconds) / NS
                calls = []
                original_now, original_deadline = D.Window.now, D.Window.deadline
                def observe(window, **kwargs):
                    calls.append(("now", window, kwargs))
                    return original_now(window, **kwargs)
                def deadline(window, maximum, **kwargs):
                    calls.append(("deadline", window, {"maximum": maximum, **kwargs}))
                    return original_deadline(window, maximum, **kwargs)
                with patch.object(D.Window, "now", observe), patch.object(D.Window, "deadline", deadline):
                    carrier = D._custody_crypto_carrier(returned)
                facade = saved[10]["reader"]
                self.assertIs(type(facade), D._CryptoReadFence)
                self.assertIs(facade._binding[0], returned)
                self.assertIs(facade._binding[1], saved)
                self.assertIs(facade._binding[2], rig.parent)
                self.assertIs(facade._binding[3], saved[10])
                self.assertIs(facade.clock, rig.clock.identity)
                self.assertIs(rig.parent._view().binding, original_binding)
                self.assertTrue(calls)
                self.assertTrue(all(window is rig.parent and values["stage"] == "readEndNs" for _name, window, values in calls))
                self.assertTrue(all(values["maximum"] == 45 for name, _window, values in calls if name == "deadline"))
                metadata = D._CRYPTO_CARRIERS[id(carrier)][4]
                self.assertEqual(set(D._PRIMARY_OWNERS) - before_metadata, {id(metadata)})
                self.assertIs(metadata.owner.first, original_first)
                self.assertIs(metadata.owner.fence, facade)
                self.assertTrue(metadata.finished and metadata.owner.closed)
                self.assertLessEqual(metadata.owner.local_end, original_binding[5][2])
                self.assertGreaterEqual(rig.parent.last, rig.parent.final + NS)
                self.assertLess(rig.parent.last, original_binding[4][2])
                count = len(D._PRIMARY_OWNERS)
                with self.assertRaisesRegex(Exception, "CRYPTO_READ_WRITER_REUSE"):
                    D._custody_crypto_carrier(returned)
                with self.assertRaisesRegex(Exception, "CRYPTO_READ_ORIGINAL_CLAIM"):
                    D._CryptoReadFence(returned)
                self.assertEqual(len(D._PRIMARY_OWNERS), count)
                with self.assertRaises(TypeError):
                    facade.now(stage="uploadEndNs")
                with self.assertRaises(TypeError):
                    facade.deadline(45, stage="sealEndNs")

        for label in ("arbitrary", "foreign-equal-return", "native-only-return", "equal-parent-dictionary",
                "mutated-manifest", "owner-not-closed", "unknown-owner-row", "equal-window-binding", "unclaimed-facade"):
            with self.subTest(parent_refused=label), Workspace(parent_mode=True) as rig:
                original = rig.closed_parent()
                saved = D._CRYPTO_RETURNS[id(original)]
                metadata_count = len(D._PRIMARY_OWNERS)
                candidate = original
                if label == "arbitrary":
                    candidate = object()
                elif label == "foreign-equal-return":
                    candidate = D._ClosedCrypto(original.context, original.phase, original.manifest, original.parent_close)
                elif label == "native-only-return":
                    candidate = original.phase
                elif label == "equal-parent-dictionary":
                    object.__setattr__(original, "__dict__", dict(original.__dict__))
                elif label == "mutated-manifest":
                    original.__dict__["manifest"] = wire({"suppliedChangedManifest": True})
                elif label == "owner-not-closed":
                    saved[2].closed = False
                elif label == "unknown-owner-row":
                    saved[2].resources[-1]["closed"] = False
                elif label == "equal-window-binding":
                    rig.parent._bound = tuple(list(rig.parent._bound))
                with self.assertRaises(Exception) as caught:
                    if label == "unclaimed-facade":
                        D._CryptoReadFence(candidate)
                    else:
                        D._custody_crypto_carrier(candidate)
                self.assertNotIsInstance(caught.exception, (AttributeError, NameError, TypeError))
                self.assertEqual(len(D._PRIMARY_OWNERS), metadata_count)
                self.assertEqual(D._CRYPTO_READ_FENCES, {})
                self.assertEqual(D._CRYPTO_CARRIERS, {})
                self.assertFalse((rig.transport / "custody-return.json").exists())

        with Workspace(parent_mode=True) as rig:
            returned = rig.closed_parent()
            first = FalseyFailure("SUPPLIED_ORIGINAL_READ_WINDOW_FAILURE")
            def cancelled():
                raise first
            rig.clock.hook = cancelled
            with self.assertRaises(FalseyFailure) as observed:
                rig.parent.now(stage="readEndNs")
            self.assertIs(observed.exception, first)
            rig.clock.hook = lambda: None  # Removing a supplier trigger does not repair its consumed clock.
            with self.assertRaises(Exception) as refused:
                D._custody_crypto_carrier(returned)
            with self.assertRaises(Exception) as replay:
                D._custody_crypto_carrier(returned)
            self.assertIs(replay.exception, refused.exception)
            self.assertIs(rig.parent._anchor().failure, first)
            with self.assertRaises(FalseyFailure) as still_failed:
                rig.parent.now(stage="readEndNs")
            self.assertIs(still_failed.exception, first)
            self.assertEqual(D._CRYPTO_READ_FENCES, {})
            self.assertFalse((rig.transport / "custody-return.json").exists())

    def test_closed_carrier_has_bounded_original_bytes_and_no_success_on_late_failure(self):
        with Workspace(parent_mode=True) as rig:
            returned = rig.closed_parent()
            stdout = io.StringIO()
            with patch.object(D.sys, "stdout", stdout):
                carrier = D._custody_crypto_carrier(returned)
            self.assertEqual(stdout.getvalue(), "")
            self.assertIs(carrier.parent, returned)
            self.assertEqual((rig.transport / "custody-return.json").read_bytes(), carrier.raw)
            self.assertLessEqual(len(carrier.raw), 2 * 1024 * 1024)
            value = json.loads(carrier.raw)
            self.assertEqual(set(value), {"schema", "scope", "kind", "selection", "source", "github", "policy",
                "authority", "primary", "window", "copy", "recipient", "exporter", "parentClose", "writerReturn",
                "originalStepOutcome", "testAcceptance", "productiveAuthority", "cacheAuthority", "exportSaveAuthority",
                "budgetAcceptance"})
            self.assertEqual(value["scope"], "INITIAL_RECIPIENT_CUSTODY_CLOSED_RETURN_V1")
            self.assertEqual(value["writerReturn"], "PENDING_OWNER_CLOSE")
            self.assertEqual(value["originalStepOutcome"], "NOT_OBSERVED")
            self.assertEqual(value["testAcceptance"], "NOT_PERFORMED")
            self.assertEqual(value["budgetAcceptance"], "NOT_ADMITTED")
            self.assertTrue(all(value[name] is False for name in ("productiveAuthority", "cacheAuthority", "exportSaveAuthority")))
            exporter = value["exporter"]
            self.assertEqual(set(exporter), {"manifestBase64", "manifestBytes", "manifestSha256", "childSha256",
                "ackSha256", "phaseSha256", "nativeResources"})
            self.assertEqual(base64.b64decode(exporter["manifestBase64"], validate=True), returned.manifest)
            self.assertEqual((exporter["manifestBytes"], exporter["manifestSha256"]),
                (len(returned.manifest), sha(returned.manifest)))
            self.assertLessEqual(exporter["manifestBytes"], 65536)
            self.assertEqual(exporter["childSha256"], sha(returned.phase.child))
            self.assertEqual(exporter["ackSha256"], sha(dict(returned.phase.records)["stdout.log"]))
            self.assertEqual(exporter["phaseSha256"], {name: sha(raw) for name, raw in returned.phase.records})
            self.assertEqual(exporter["nativeResources"], json.loads(returned.parent_close)["resources"])
            self.assertTrue(all(item["closeAttempted"] and item["closed"] for item in exporter["nativeResources"]))
            self.assertEqual(value["parentClose"], json.loads(returned.parent_close))
            self.assertEqual(value["copy"]["directoryIdentity"], rig.context["directories"]["copied-evidence"])
            self.assertEqual(value["copy"]["sourceMetadataSha256"], json.loads(returned.phase.child)["sourceMetadataSha256"])
            self.assertEqual(value["window"]["readEndNs"], rig.parent._view().binding[4][2])
            close = json.loads(carrier.metadata_close)
            self.assertEqual(close["retirement"], "KNOWN_RESOURCE_CLOSE_ONLY")
            self.assertTrue(all(row["closeAttempted"] and row["closed"] for row in close["resources"]))
            self.assertEqual(D._CRYPTO_RETURNS[id(returned)][10]["state"], "RETURNED")
            self.assertEqual(dict(D.os.environ), {})

        for label in ("nested-copy-map", "dict-valued-origin", "duplicate-origin-digest", "root-member-overflow",
                "copy-bytes-overflow", "oversized-manifest-declaration", "unexpected-child-map", "changed-child-hash"):
            with self.subTest(child_carrier_refused=label), Workspace(parent_mode=True) as rig:
                def malformed_child(child, ack):
                    if label in ("nested-copy-map", "dict-valued-origin", "duplicate-origin-digest",
                            "root-member-overflow", "copy-bytes-overflow"):
                        if label == "nested-copy-map":
                            child["copy"]["mapsBase64"] = {"PRIMARY": base64.b64encode(b"SUPPLIED_NOT_A_MAP_CARRIER").decode("ascii")}
                        elif label == "dict-valued-origin":
                            child["copy"]["origins"][D.ORIGINS[0]] = {"sha256": "1" * 64}
                        elif label == "duplicate-origin-digest":
                            child["copy"]["origins"][D.ORIGINS[1]] = child["copy"]["origins"][D.ORIGINS[0]]
                        elif label == "root-member-overflow":
                            child["copy"]["memberCount"] = D.MAX_MEMBERS
                        else:
                            child["copy"]["totalBytes"] = D.MAX_BYTES + 1
                        manifest = json.loads(rig.manifest_raw)
                        manifest["copy"] = child["copy"]
                        rig.manifest_raw = wire(manifest)
                        child["manifest"] = {"bytes": len(rig.manifest_raw), "sha256": sha(rig.manifest_raw),
                            "base64": base64.b64encode(rig.manifest_raw).decode("ascii")}
                    elif label == "oversized-manifest-declaration":
                        child["manifest"]["bytes"] = D.E.MANIFEST_LIMIT + 1
                    elif label == "unexpected-child-map":
                        child["originalMaps"] = {"PRIMARY": {"tiny": "SUPPLIED_FORBIDDEN_NESTING"}}
                    else:
                        ack["terminalSha256"] = "0" * 64
                    if label != "changed-child-hash":
                        ack["terminalSha256"] = sha(wire(child))
                rig.child_mutation = malformed_child
                with self.assertRaises(Exception) as caught:
                    rig.closed_parent()
                self.assertNotIsInstance(caught.exception, (AttributeError, NameError, TypeError))
                self.assertEqual(D._CRYPTO_RETURNS, {})
                self.assertEqual(D._CRYPTO_READ_FENCES, {})
                self.assertEqual(D._CRYPTO_CARRIERS, {})
                self.assertFalse((rig.transport / "custody-return.json").exists())

        for label in ("manifest-readback", "metadata-write", "metadata-close", "read-end-before-allocation", "read-end-after-close"):
            with self.subTest(read_carrier_refused=label), Workspace(parent_mode=True) as rig:
                returned = rig.closed_parent()
                first = FalseyFailure("SUPPLIED_CARRIER_FIRST_IO_FAILURE")
                fired, close_calls = [], []
                original_create, original_close = D.Q._PosixDirectory.create_file, D.Q._PosixDirectory.close
                if label == "manifest-readback":
                    (rig.output / D.native.posix.MANIFEST).write_bytes(wire({"suppliedChangedOutput": True}))
                elif label == "read-end-before-allocation":
                    rig.clock.raw = rig.parent._view().binding[4][2]
                def create(directory, name, **kwargs):
                    if label == "metadata-write" and name == "custody-return.json":
                        fired.append(True)
                        raise first
                    return original_create(directory, name, **kwargs)
                def close(directory):
                    active = [anchor.handle for anchor in D._PRIMARY_OWNERS.values()
                        if type(anchor.handle.owner.fence) is D._CryptoReadFence]
                    if active and any(resource is directory for _r, _l, resource, _a, _c in active[0].rows):
                        if label == "metadata-close" and directory.path == rig.transport:
                            close_calls.append(directory)
                            original_close(directory)
                            raise first
                        result = original_close(directory)
                        if label == "read-end-after-close" and directory.path == rig.output:
                            fired.append(True)
                            rig.clock.raw = rig.parent._view().binding[4][2]
                        return result
                    return original_close(directory)
                with patch.object(D.Q._PosixDirectory, "create_file", create), patch.object(D.Q._PosixDirectory, "close", close):
                    with self.assertRaises(Exception) as caught:
                        D._custody_crypto_carrier(returned)
                self.assertNotIsInstance(caught.exception, (AttributeError, NameError, TypeError))
                attempt = D._CRYPTO_RETURNS[id(returned)][10]
                self.assertTrue(attempt["readClaimed"])
                self.assertEqual(attempt["state"], "FAILED")
                self.assertIs(attempt["failure"], caught.exception)
                self.assertEqual(D._CRYPTO_CARRIERS, {})
                if label in ("metadata-write", "metadata-close"):
                    self.assertIs(caught.exception, first)
                if label == "metadata-close":
                    self.assertEqual(len(close_calls), 1)
                if label in ("metadata-write", "read-end-after-close"):
                    self.assertEqual(fired, [True])
                count = len(D._PRIMARY_OWNERS)
                with self.assertRaises(Exception) as replay:
                    D._custody_crypto_carrier(returned)
                self.assertIs(replay.exception, caught.exception)
                self.assertEqual(len(D._PRIMARY_OWNERS), count)
                # A file left by failed close/expiry remains PENDING, never a
                # returned carrier, Actions Step outcome, seal or upload proof.
                if (rig.transport / "custody-return.json").exists():
                    pending = json.loads((rig.transport / "custody-return.json").read_bytes())
                    self.assertEqual(pending["writerReturn"], "PENDING_OWNER_CLOSE")
                    self.assertEqual(pending["originalStepOutcome"], "NOT_OBSERVED")


if __name__ == "__main__":
    unittest.main(verbosity=2, failfast=True)
