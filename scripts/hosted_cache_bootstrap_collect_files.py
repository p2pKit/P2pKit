"""Dormant configuration-file copy leaf, NOT original-call collection authority.

Supplied records/identities cannot attest a producer, successful native retirement
or single use. The future same-call parent must invoke the producer itself, wait
for its actual close/return, then provide a NEW owner under the original RAW/LOCAL
allocation. This leaf opens only new files/directories; it never calls a producer,
recollects checkout reports, installs a loader or grants export/save authority.

One local120 ceiling only shortens the caller's deadlines. It is not an admitted
job/phase budget, a hard filesystem watchdog or a substitute for that parent.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import math
import os
from pathlib import Path
import time

import hosted_cache_bootstrap_collection as inventory
import hosted_dependency_seed_files as files


SCOPE = "BOOTSTRAP_CONFIGURATION_FILE_COPY_LEAF_V1"
BLOCK = 65536
SECONDS = 120
MEMBERS = 10000
DEPTH = 64
RESOURCES = 4096
METADATA = ("start.json", "receipt.json", "report-manifest.json")
MAX_BYTES = 3 * inventory.METADATA_BYTES + len(inventory.LOGS) * inventory.LOG_BYTES + inventory.REPORT_BYTES


class CollectionFilesError(RuntimeError):
    """Finite file-copy refusal; private originals/resources stay on the error."""


def require(value, reason):
    if not value:
        raise CollectionFilesError(reason)


def _local(value):
    require(type(value) in (int, float), "BOOTSTRAP_COLLECT_LOCAL_CLOCK")
    try:
        value = float(value)
    except (ValueError, OverflowError):
        raise CollectionFilesError("BOOTSTRAP_COLLECT_LOCAL_CLOCK") from None
    require(math.isfinite(value) and value >= 0, "BOOTSTRAP_COLLECT_LOCAL_CLOCK")
    return value


@dataclass(frozen=True)
class FileOriginals:
    """Supplied data, not a ConfigurationPrefix, owner or provenance token."""
    request_raw: bytes = field(repr=False)
    admitted_raw: bytes = field(repr=False)
    canonical_raw: bytes = field(repr=False)
    start_raw: bytes = field(repr=False)
    receipt_raw: bytes = field(repr=False)
    manifest_raw: bytes = field(repr=False)
    original_exit_code: int
    evidence_identity: tuple = field(repr=False)
    retained_identity: tuple = field(repr=False)
    metadata_bindings_raw: bytes = field(repr=False)


@dataclass(frozen=True)
class FileCollectionEvidence:
    raw: bytes = field(repr=False)
    inventory_raw: bytes = field(repr=False)
    local_started: float
    checked_local: float


def _capture(value):
    require(type(value) is FileOriginals, "BOOTSTRAP_COLLECT_INPUT_KIND")
    raw = tuple(getattr(value, name) for name in ("request_raw", "admitted_raw", "canonical_raw",
        "start_raw", "receipt_raw", "manifest_raw", "metadata_bindings_raw"))
    for item in raw:
        inventory._bytes(item)
    require(type(value.original_exit_code) is int and value.original_exit_code == 0,
            "BOOTSTRAP_COLLECT_ORIGINAL_EXIT")
    identities = (value.evidence_identity, value.retained_identity)
    require(all(type(item) is tuple and files._identity(list(item)) for item in identities) and
            identities[0] != identities[1], "BOOTSTRAP_COLLECT_DIRECTORY_IDENTITIES")
    return (*raw, value.original_exit_code, *identities)


@dataclass(frozen=True)
class _Member:
    maximum: int
    size: object = None
    sha256: object = None
    raw: object = field(default=None, repr=False)
    binding_raw: object = field(default=None, repr=False)


class _Inputs:
    def __init__(self, original):
        self.original, self.captured = original, _capture(original)
        request, admitted, canonical, start, receipt, manifest, bindings, code, source_id, target_id = self.captured
        self.inventory_raw = inventory.describe_inventory(request, admitted, canonical, start, receipt, manifest,
                                                          original_exit_code=code)
        self.inventory = inventory.producer.parse(self.inventory_raw)
        request_value = inventory.producer.parse(request)
        self.role = request_value["host"]
        require((os.name == "nt") == (self.role == "windows-x64"), "BOOTSTRAP_COLLECT_FILE_PLATFORM")
        require(all(type(item[1]) is (str if self.role == "windows-x64" else int) for item in (source_id, target_id)),
                "BOOTSTRAP_COLLECT_NATIVE_IDENTITIES")
        self.source = Path(request_value["evidenceDirectory"])
        self.target = Path(request_value["gradleHome"]).parent.parent / "configuration-custody" / "retained"
        self.identities = {"source": source_id, "destination": target_id}
        require(self.source.is_absolute() and self.target.is_absolute() and
                self.source != self.target and self.source not in self.target.parents and
                self.target not in self.source.parents, "BOOTSTRAP_COLLECT_DIRECTORY_LAYOUT")
        bound = files.record(bindings)
        require(set(bound) == set(METADATA) and all(files._file_binding(row) for row in bound.values()),
                "BOOTSTRAP_COLLECT_METADATA_BINDINGS")
        require(all(type(row["identity"][1]) is type(source_id[1]) for row in bound.values()),
                "BOOTSTRAP_COLLECT_METADATA_NATIVE_BINDINGS")
        self.tree, self.members = {}, 0
        for row, raw in zip(self.inventory["requiredMetadata"], (start, receipt, manifest)):
            self.insert(row["path"], _Member(inventory.METADATA_BYTES, row["bytes"], row["sha256"], raw,
                                           files.encoded(bound[row["path"]])))
        for name in inventory.LOGS:
            self.insert(name, _Member(inventory.LOG_BYTES))
        for row in self.inventory["retainedReports"]:
            self.insert(row["path"], _Member(inventory.REPORT_BYTES, row["bytes"], row["sha256"]))

    def insert(self, name, member):
        parts, tree = name.split("/"), self.tree
        # The supplied-inventory grammar is wider. Do not expand native selected
        # basenames or depth to make an otherwise valid declaration executable.
        for part in parts:
            files.authority._basename(part)
        require(max(len(self.source.parts), len(self.target.parts)) + len(parts) <= DEPTH,
                "BOOTSTRAP_COLLECT_NATIVE_DEPTH")
        for index, part in enumerate(parts):
            last = index == len(parts) - 1
            if part not in tree:
                self.members += 1
                require(self.members <= MEMBERS, "BOOTSTRAP_COLLECT_NATIVE_MEMBERS")
                tree[part] = member if last else {}
            else:
                require(not last and type(tree[part]) is dict, "BOOTSTRAP_COLLECT_MEMBER_COLLISION")
            tree = tree[part]

    def unchanged(self):
        require(_capture(self.original) == self.captured, "BOOTSTRAP_COLLECT_INPUT_CHANGED")


@dataclass(eq=False)
class _Resource:
    value: object = field(repr=False)
    kind: type
    row: object = field(default=None, repr=False)
    attempted: bool = False
    closed: bool = False


def _owner_row(row):
    return (type(row) is dict and set(row) == {"label", "owner", "attempted", "closed"} and
            type(row["label"]) is str and type(row["attempted"]) is bool and type(row["closed"]) is bool and
            (not row["closed"] or row["attempted"]))


class _Copy:
    def __init__(self, parent, inputs, began):
        self.parent, self.inputs = parent, inputs
        self.began, self.last, self.end_local = began, began, _local(began + SECONDS)
        self.caller_end = self.end_local
        self.ledger, self.cancelled = parent.resources, parent.cancelled
        require(type(self.ledger) is list and callable(self.cancelled) and
                len(self.ledger) <= RESOURCES and all(_owner_row(row) for row in self.ledger),
                "BOOTSTRAP_COLLECT_PARENT_PROTOCOL")
        self.previous = tuple((row, row["owner"], type(row["owner"]), row["label"], row["attempted"], row["closed"])
                              for row in self.ledger)
        self.acquire_original, self.close_original = parent.acquire, parent.close_one
        self.error_original, self.end_original = parent.error, parent.end
        require(all(callable(value) for value in (self.acquire_original, self.close_original,
                self.error_original, self.end_original)), "BOOTSTRAP_COLLECT_PARENT_PROTOCOL")
        self.resources, self.first, self.unknown = [], None, False
        self.sample_expiry, self.expiry_recorded = None, False
        self.aliases, self.bindings, self.rows = {}, {"source": {}, "destination": {}}, []
        self.counts = {name: 0 for name in ("sourceReadBytes", "destinationReadBytes", "outputBytesRequested",
            "outputBytesAcknowledged", "sourceMembers", "destinationMembers", "sourceFinalMembers", "destinationFinalMembers")}

    def error(self, stage, error, *, unknown=False):
        if self.sample_expiry is not None and error is self.sample_expiry:
            self.expiry_recorded = True
        if self.first is None:
            self.first = self.parent.original if self.parent.original is not None else error
        self.unknown |= unknown or self.parent.unknown
        try:
            self.error_original("bootstrap-collection-" + stage, error, unknown=self.unknown)
        except BaseException as secondary:
            self.unknown = True
            try:
                files._note(self.first, "owner-error-record", secondary)
            except BaseException:
                pass  # The first failure and independent resource references survive.
        self.unknown |= self.parent.unknown

    def state(self):
        self.inputs.unchanged()
        require(self.parent.closed is False and self.parent.unknown is False and not self.unknown and
                self.parent.resources is self.ledger and self.parent.cancelled is self.cancelled,
                "BOOTSTRAP_COLLECT_PARENT_NOT_LIVE")
        require(len(self.ledger) == len(self.previous) + len(self.resources) <= RESOURCES and
                all(self.ledger[index] is row and _owner_row(row) and row["owner"] is value and
                    type(value) is kind and row["label"] == label and row["attempted"] is attempted and
                    row["closed"] is closed for index, (row, value, kind, label, attempted, closed)
                    in enumerate(self.previous)), "BOOTSTRAP_COLLECT_PARENT_ROSTER")
        for row, pin in zip(self.ledger[len(self.previous):], self.resources):
            require(row is pin.row and _owner_row(row) and row.get("owner") is pin.value and
                    type(pin.value) is pin.kind and row.get("attempted") is pin.attempted and
                    row.get("closed") is pin.closed, "BOOTSTRAP_COLLECT_RESOURCE_CHANGED")
        if self.first is not None:
            raise self.first
        if self.parent.original is not None:
            raise self.parent.original

    def sample(self):
        # Only an exception made by THIS observation can mark local expiry.
        # A clock supplier rethrowing an earlier exception is a distinct error.
        self.sample_expiry = None
        value = _local(time.monotonic())
        require(value >= self.last, "BOOTSTRAP_COLLECT_LOCAL_BACKWARDS")
        self.last = value
        if value >= self.end_local:
            self.sample_expiry = CollectionFilesError("BOOTSTRAP_COLLECT_LOCAL_EXPIRED")
            raise self.sample_expiry

    def close_clock(self, stage):
        try:
            self.sample()
        except BaseException as error:
            # Still sample every original close. Re-observing the SAME fixed
            # local ceiling is not a new error event and must not consume the
            # parent's finite error ledger until known cleanup becomes UNKNOWN.
            # General error()/actual close failures never use this suppression.
            if error is not self.sample_expiry or not self.expiry_recorded:
                self.error(stage, error)

    def check(self):
        self.state()
        self.sample()
        self.cancelled()
        self.sample()
        self.state()
        end = _local(self.end_original())
        self.caller_end = min(self.caller_end, end)
        self.sample()
        self.state()
        # A later callback cannot renew an earlier returned caller ceiling.
        require(self.last < self.caller_end, "BOOTSTRAP_COLLECT_CALLER_EXPIRED")
        return self.caller_end

    def acquire(self, label, factory):
        self.check()
        require(len(self.ledger) < RESOURCES, "BOOTSTRAP_COLLECT_RESOURCE_LIMIT")
        before, captured, invoked = tuple(self.ledger), [], False
        before_owners = tuple(row["owner"] for row in before)
        def retain():
            nonlocal invoked
            require(not invoked, "BOOTSTRAP_COLLECT_FACTORY_REPEATED")
            invoked = True
            value = factory()
            # Independent references precede the parent's post-factory callback.
            captured.append(value)
            if not any(old is value for old in before_owners):
                self.resources.append(_Resource(value, type(value)))
            return value
        acquire_error = None
        try:
            result = self.acquire_original("bootstrap-collection-" + label, retain)
        except BaseException as error:
            acquire_error = error
            raise
        finally:
            for value in captured:
                # An earlier leaf object is just as borrowed as a caller's
                # preexisting object. Do not reinterpret its old pin as a new
                # unregistered obligation or overwrite the duplicate failure.
                if any(old is value for old in before_owners):
                    continue
                pins = [pin for pin in self.resources if pin.value is value]
                if not pins:
                    continue  # A borrowed object remains its original owner's duty.
                rows = [row for row in self.ledger if type(row) is dict and row.get("owner") is value and
                        not any(row is old for old in before)]
                if len(rows) == 1:
                    pins[-1].row = rows[0]
                else:
                    # A real earlier acquisition failure precedes uncertainty
                    # discovered here. Falsey exceptions are still originals.
                    if acquire_error is not None:
                        self.error("acquire", acquire_error)
                    self.error("registration", CollectionFilesError("BOOTSTRAP_COLLECT_UNREGISTERED_RETURN"), unknown=True)
        require(len(captured) == 1 and result is captured[0] and
                not any(old is result for old in before_owners), "BOOTSTRAP_COLLECT_BORROWED_OR_CHANGED_RETURN")
        self.check()
        return result

    def close_binding(self, pin, value):
        require(not self.unknown and self.parent.unknown is False and self.parent.closed is False and
                self.parent.resources is self.ledger and pin.row is not None and
                any(row is pin.row for row in self.ledger) and pin.row.get("owner") is value and
                type(value) is pin.kind and pin.row.get("attempted") is False and pin.row.get("closed") is False,
                "BOOTSTRAP_COLLECT_CLOSE_BINDING")

    def close_one(self, value):
        pin = next((row for row in self.resources if row.value is value), None)
        require(pin is not None, "BOOTSTRAP_COLLECT_FOREIGN_CLOSE")
        if pin.attempted:
            return
        self.close_binding(pin, value)
        # Expiry is recorded, but never excuses the known original close duty.
        self.close_clock("preclose-clock")
        # A failed sample/recorder may have made ownership UNKNOWN. Do not
        # dispatch a new close (or mark attempted) from the earlier binding.
        self.close_binding(pin, value)
        pin.attempted = True
        try:
            self.close_original(value)
            require(pin.row.get("attempted") is True and pin.row.get("closed") is True and
                    self.parent.unknown is False, "BOOTSTRAP_COLLECT_CLOSE_UNKNOWN")
            pin.closed = True
        except BaseException as error:
            self.error("close", error, unknown=True)
            raise
        finally:
            self.close_clock("postclose-clock")
        if self.first is not None:
            raise self.first
        if self.parent.original is not None:
            raise self.parent.original

    def close(self):
        for pin in reversed(self.resources):
            if self.unknown or self.parent.unknown:
                break
            if pin.attempted:
                continue
            try:
                self.close_one(pin.value)
            except BaseException as error:
                # A known successful close may propagate the already recorded
                # first failure. It is not another error event: duplicating it
                # can exhaust the parent's finite error roster and strand duty.
                if error is not self.first or not pin.closed:
                    self.error("final-close", error, unknown=not pin.closed)
        if self.first is not None:
            raise self.first
        require(not self.unknown and not self.parent.unknown and
                all(pin.attempted and pin.closed for pin in self.resources), "BOOTSTRAP_COLLECT_CLOSE_INCOMPLETE")

    def info(self, info, *, directory, side, path):
        kind = files.windows.FileInfo if self.inputs.role == "windows-x64" else files.PosixInfo
        require(type(info) is kind and info.is_directory is directory and type(info.size) is int and info.size >= 0,
                "BOOTSTRAP_COLLECT_FILE_INFO")
        binding = files._info_binding(info)
        require(files._file_binding(binding) and
                type(binding["identity"][1]) is (str if self.inputs.role == "windows-x64" else int),
                "BOOTSTRAP_COLLECT_FILE_INFO_BINDING")
        identity = tuple(binding["identity"])
        key = (side, path)
        require(identity not in self.aliases or self.aliases[identity] == key, "BOOTSTRAP_COLLECT_FILE_ALIAS")
        self.aliases[identity] = key
        return binding

    def names(self, directory, tree, side, *, final=False, empty=False):
        end = self.check()
        names = directory.names(max_names=MEMBERS, deadline=end)
        require(type(names) is tuple and all(type(name) is str for name in names), "BOOTSTRAP_COLLECT_DIRECTORY_NAMES")
        key = side + ("FinalMembers" if final else "Members")
        self.counts[key] += len(names)  # Includes prefixes and unexpected entries, not just manifest rows.
        require(self.counts[key] <= MEMBERS, "BOOTSTRAP_COLLECT_DIRECTORY_MEMBER_LIMIT")
        require(names == tuple(sorted(tree)), "BOOTSTRAP_COLLECT_TARGET_NOT_EMPTY" if empty else
                "BOOTSTRAP_COLLECT_UNLISTED_OR_MISSING_MEMBER")
        self.check()

    def charge(self, kind, count):
        require(type(count) is int and count >= 0, "BOOTSTRAP_COLLECT_BYTE_COUNT")
        self.counts[kind] += count
        limit = 2 * MAX_BYTES + 3 * inventory.METADATA_BYTES if kind == "sourceReadBytes" else MAX_BYTES
        require(self.counts[kind] <= limit, "BOOTSTRAP_COLLECT_BYTE_LIMIT")

    def stream(self, reader, before, member, side, *, writer=None):
        count, digest = 0, hashlib.sha256()
        while count < before.size:
            self.check()
            requested = min(BLOCK, before.size - count)
            part = reader.read(requested)
            if type(part) is bytes:
                self.charge(side + "ReadBytes", len(part))
            require(type(part) is bytes and 0 < len(part) <= requested, "BOOTSTRAP_COLLECT_SHORT_OR_EXCESS_READ")
            if member.raw is not None:
                require(part == member.raw[count:count + len(part)], "BOOTSTRAP_COLLECT_METADATA_BYTES_CHANGED")
            digest.update(part)
            count += len(part)
            self.check()
            if writer is not None:
                self.charge("outputBytesRequested", len(part))
                written = writer.write(part)
                if type(written) is int and 0 < written <= len(part):
                    self.charge("outputBytesAcknowledged", written)
                require(type(written) is int and written == len(part), "BOOTSTRAP_COLLECT_SHORT_WRITE")
                self.check()
        self.check()
        tail = reader.read(1)  # Positive request even for zero-byte originals.
        if type(tail) is bytes:
            self.charge(side + "ReadBytes", len(tail))
        require(type(tail) is bytes and tail == b"" and reader.verify() == before,
                "BOOTSTRAP_COLLECT_SIZE_OR_STAMP_CHANGED")
        # Windows read(1) at initial_info.size is adapter exhaustion, NOT a
        # kernel EOF probe. Its unchanged same-descriptor verify is essential.
        result = digest.hexdigest()
        require(member.sha256 is None or result == member.sha256, "BOOTSTRAP_COLLECT_HASH_CHANGED")
        self.check()
        return count, result

    def reader(self, directory, name, member, side, path, *, expected=None):
        end = self.check()
        reader = self.acquire("reader", lambda: directory.open_file(name, max_bytes=member.maximum, deadline=end))
        before = reader.initial_info
        binding = self.info(before, directory=False, side=side, path=path)
        require(before.size <= member.maximum and (member.size is None or before.size == member.size),
                "BOOTSTRAP_COLLECT_FILE_SIZE")
        expected = expected if expected is not None else member.binding_raw if side == "source" else None
        require(expected is None or files.encoded(binding) == expected, "BOOTSTRAP_COLLECT_ORIGINAL_FILE_REPLACED")
        self.check()
        return reader, before, binding

    def metadata(self, source):
        # All three original metadata files are admitted before any copy output.
        for name in METADATA:
            member = self.inputs.tree[name]
            reader, before, _binding = self.reader(source, name, member, "source", name)
            self.stream(reader, before, member, "source")
            self.close_one(reader)

    def copy_file(self, source, target, name, member, path):
        reader, before, source_binding = self.reader(source, name, member, "source", path)
        count, digest = self.stream(reader, before, member, "source")
        self.check()
        position = reader.seek(0)
        require(type(position) is int and position == 0 and reader.verify() == before,
                "BOOTSTRAP_COLLECT_REWIND_CHANGED")
        end = self.check()
        writer = self.acquire("writer", lambda: target.create_file(name, max_bytes=count, deadline=end))
        self.info(writer.initial_info, directory=False, side="destination", path=path)
        require(writer.initial_info.size == 0, "BOOTSTRAP_COLLECT_NEW_OUTPUT_NOT_EMPTY")
        require(self.stream(reader, before, member, "source", writer=writer) == (count, digest),
                "BOOTSTRAP_COLLECT_COPY_CHANGED")
        self.check()
        writer.sync()
        written = writer.verify()
        destination_binding = self.info(written, directory=False, side="destination", path=path)
        require(written.size == count, "BOOTSTRAP_COLLECT_OUTPUT_SIZE")
        self.check()
        self.close_one(writer)
        self.close_one(reader)
        readback, copied, _binding = self.reader(target, name, _Member(member.maximum, count, digest, member.raw),
            "destination", path, expected=files.encoded(destination_binding))
        require(self.stream(readback, copied, _Member(member.maximum, count, digest, member.raw), "destination") ==
                (count, digest), "BOOTSTRAP_COLLECT_READBACK_CHANGED")
        self.close_one(readback)
        self.bindings["source"][path] = source_binding
        self.bindings["destination"][path] = destination_binding
        self.rows.append({"path": path, "bytes": count, "sha256": digest,
            "sourceBinding": source_binding, "destinationBinding": destination_binding})

    def copy_tree(self, source, target, tree, prefix=""):
        before = source.verify()
        source_binding = self.info(before, directory=True, side="source", path=prefix)
        self.names(source, tree, "source")
        self.names(target, {}, "destination", empty=True)
        for name, member in sorted(tree.items()):
            path = prefix + ("/" if prefix else "") + name
            if type(member) is _Member:
                self.copy_file(source, target, name, member, path)
            else:
                end = self.check()
                child = self.acquire("directory", lambda: source.open_directory(name, deadline=end))
                end = self.check()
                created = self.acquire("directory", lambda: target.create_directory(name, deadline=end))
                self.info(created.verify(), directory=True, side="destination", path=path)
                self.copy_tree(child, created, member, path)
                self.close_one(created)
                self.close_one(child)
        self.names(target, tree, "destination")
        require(source.verify() == before, "BOOTSTRAP_COLLECT_SOURCE_DIRECTORY_CHANGED")
        self.bindings["source"][prefix] = source_binding
        self.bindings["destination"][prefix] = self.info(target.verify(), directory=True, side="destination", path=prefix)
        self.check()

    def final_tree(self, directory, tree, side, prefix=""):
        require(self.info(directory.verify(), directory=True, side=side, path=prefix) == self.bindings[side][prefix],
                "BOOTSTRAP_COLLECT_DIRECTORY_REPLACED")
        self.names(directory, tree, side, final=True)
        for name, member in sorted(tree.items()):
            path = prefix + ("/" if prefix else "") + name
            if type(member) is _Member:
                reader, before, _binding = self.reader(directory, name, member, side, path,
                    expected=files.encoded(self.bindings[side][path]))
                require(reader.verify() == before, "BOOTSTRAP_COLLECT_FINAL_FILE_CHANGED")
                self.close_one(reader)
            else:
                end = self.check()
                child = self.acquire("directory", lambda: directory.open_directory(name, deadline=end))
                self.final_tree(child, member, side, path)
                self.close_one(child)
        require(self.info(directory.verify(), directory=True, side=side, path=prefix) == self.bindings[side][prefix],
                "BOOTSTRAP_COLLECT_FINAL_DIRECTORY_CHANGED")
        self.check()


def collect_inventory(parent, originals):
    """Copy the supplied positive inventory; retain failures without deleting.

The parent remains open and owns enclosing retirement. This operation supplies
neither the pending original-call bridge nor a post-close/failure-custody owner.
Only the derived existing retained directory is used, never an arbitrary path.
"""
    began = _local(time.monotonic())
    inputs = _Inputs(originals)  # Snapshot/rederive before any owner callback.
    copy = _Copy(parent, inputs, began)
    result = {"schema": 1, "scope": SCOPE, "inventorySha256": files.digest(inputs.inventory_raw),
        "inputProvenance": "SUPPLIED_RECORDS_NOT_ORIGINAL_CALL", "collectionState": "FAILED", "completed": False,
        "leafHandleClose": "PENDING", "enclosingOwnerRetirement": "NOT_OBSERVED_HERE",
        "noLoaderObservation": "NOT_OBSERVED", "dependencyPopulation": "NOT_ATTESTED",
        "budgetAcceptance": "NOT_ADMITTED", "testAcceptance": "NOT_PERFORMED",
        "nextPhaseAuthority": False, "exportSaveAuthority": False,
        "readBoundary": "WINDOWS_DECLARED_SIZE_AND_SAME_DESCRIPTOR_VERIFY" if inputs.role == "windows-x64" else
                        "POSIX_POSITIVE_READ_EMPTY_AND_SAME_DESCRIPTOR_VERIFY"}
    try:
        copy.check()
        source = copy.acquire("root", lambda: files.private_root(inputs.source))
        target = copy.acquire("root", lambda: files.private_root(inputs.target))
        for side, directory in (("source", source), ("destination", target)):
            require(tuple(copy.info(directory.verify(), directory=True, side=side, path="")["identity"]) ==
                    inputs.identities[side], "BOOTSTRAP_COLLECT_ORIGINAL_DIRECTORY_REPLACED")
        copy.names(target, {}, "destination", empty=True)
        copy.metadata(source)
        copy.copy_tree(source, target, inputs.tree)
        copy.final_tree(source, inputs.tree, "source")
        copy.final_tree(target, inputs.tree, "destination")
        require(all(copy.counts[name] == inputs.members for name in ("sourceMembers", "destinationMembers",
            "sourceFinalMembers", "destinationFinalMembers")), "BOOTSTRAP_COLLECT_FINAL_MEMBERS")
        copy.close()
        copy.check()
        result.update(collectionState="COPIED_AND_READ_BACK", completed=True, leafHandleClose="KNOWN",
            sourceDirectory=str(inputs.source), retainedDirectory=str(inputs.target),
            directoryBindings=inputs.identities, counts=dict(copy.counts), files=copy.rows,
            localWindow={"started": began, "end": copy.end_local, "observed": copy.last,
                         "scope": "LOCAL120_SHORTENS_CALLER_NOT_SHARED_CLOCK_OR_JOB_ADMISSION"})
        raw = files.encoded(result)
        copy.check()  # Serialization and final callbacks still spend the original ceiling.
        return FileCollectionEvidence(raw, inputs.inventory_raw, began, copy.last)
    except BaseException as error:
        copy.error("body", error)
        try:
            copy.close()
        except BaseException as secondary:
            if secondary is not copy.first:
                copy.error("cleanup", secondary)
        result.update(collectionState="UNKNOWN" if copy.unknown or parent.unknown else "FAILED", completed=False,
            leafHandleClose="UNKNOWN" if copy.unknown or parent.unknown else
                "KNOWN" if all(pin.attempted and pin.closed for pin in copy.resources) else "INCOMPLETE",
            counts=dict(copy.counts), files=copy.rows)
        try:
            copy.first.bootstrap_collection_result = result
            copy.first.bootstrap_collection_resources = tuple(copy.resources)
        except BaseException:
            pass
        raise copy.first
