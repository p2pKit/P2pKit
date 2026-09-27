"""Closed public-source compatibility DATA, never cache/native authority.

The seed roster/policy is unchanged; this is not the provider loader roster. All native
opens, known closes and deadlines belong to the calling original owner. H1's
canonical inventory is retained inside its existing private handoff; H2 must
read its own selected source afresh and match that exact inventory and digest.
"""
from __future__ import annotations

import hashlib
import json
import re


SCOPE = "HOSTED_CACHE_SOURCE_COMPATIBILITY_INPUTS_V1"
LIMIT, TOTAL_LIMIT = 2 * 1024 * 1024, 64 * 1024 * 1024
# Reviewed production reachability only. This is not an import list, a provider
# frame, a recursive discovery rule, or authority to invoke any of these paths.
PROVIDER_INPUTS = (
    "scripts/hosted_cache_compatibility.py",
    "scripts/hosted_dependency_cache.py",
    "scripts/hosted_primary_abi.py",
    "scripts/hosted_lock_resources.py",
    "scripts/hosted_evidence.py",
    "scripts/hosted_test_evidence.py",
    "scripts/hosted_test_query.py",
    "scripts/audit_processes.py",
    "scripts/hosted_job_clock.py",
    "scripts/hosted_full_job_budget.py",
    "scripts/hosted_full_simulator.py",
    "scripts/hosted_full_supplements.py",
    "scripts/inspect-ordinary-swift-results.py",
    "scripts/prepare-audit-central-bundle-metadata.py",
    "scripts/prepare-audit-consumer-metadata.py",
    "scripts/run-audit-host.py",
    "scripts/run-audit-command.py",
    "scripts/check-audit-receipt.py",
    "scripts/test-transcript-custody.py",
    "gradle/test-transcript-custody.init.gradle",
    "scripts/run-platform-tests.py",
    "scripts/application_release_version.py",
    "scripts/package-sample-apps.py",
    "scripts/sample_artifact_identity.py",
    "scripts/hosted_cache_bootstrap_allocation.py",
    "scripts/hosted_cache_bootstrap_canonical.py",
    "scripts/hosted_cache_bootstrap_collect_files.py",
    "scripts/hosted_cache_bootstrap_collection.py",
    "scripts/hosted_cache_bootstrap_custody.py",
    "scripts/hosted_cache_bootstrap_export.py",
    "scripts/hosted_cache_bootstrap_history.py",
    "scripts/hosted_cache_bootstrap_initialization.py",
    "scripts/hosted_cache_bootstrap_no_loader.py",
    "scripts/hosted_cache_bootstrap_origin.py",
    "scripts/hosted_cache_bootstrap_producer.py",
    "scripts/hosted_cache_bootstrap_producer_command.py",
    "scripts/hosted_cache_bootstrap_save_set.py",
    "scripts/hosted_cache_bootstrap_service_time.py",
    "scripts/hosted_cache_bootstrap_staging.py",
    "scripts/hosted-cache-provider-action.cjs",
    "scripts/hosted-cache-provider-node-bridge.cjs",
    "scripts/hosted-cache-provider-node-return.cjs",
    "scripts/hosted_cache_provider_cancel.py",
    "scripts/hosted_cache_provider_clock.py",
    "scripts/hosted_cache_provider_entry.py",
    "scripts/hosted_cache_provider_environment.py",
    "scripts/hosted_cache_provider_launch.py",
    "scripts/hosted_cache_provider_lifecycle.py",
    "scripts/hosted_cache_provider_native.py",
    "scripts/hosted_cache_provider_prepare.py",
    "scripts/hosted_cache_provider_readback.py",
    "scripts/hosted_cache_provider_return.py",
    "scripts/hosted_cache_provider_supervisor.py",
    "scripts/hosted_cache_provider_supervisor_return.py",
    "scripts/hosted_cache_provider_worker.py",
    "scripts/hosted_cache_provider_tools.py",
    "scripts/hosted_windows_evidence.py",
    "scripts/hosted_initial_recipient_originals.py",
    "scripts/hosted_initial_recipient_productive.py",
    "scripts/hosted_initial_recipient_productive_adapter.py",
    "scripts/hosted_initial_recipient_productive_data.py",
    "scripts/hosted_initial_recipient_use.py",
    "scripts/hosted_initial_recipient_public_origin.py",
    "scripts/hosted_initial_recipient_gate.py",
    "scripts/hosted_initial_recipient_before.py",
    "scripts/hosted_initial_recipient_continuity.py",
    "scripts/hosted_initial_recipient_evidence.py",
    "scripts/run-hosted-initial-recipient.py",
    "scripts/run-hosted-initial-recipient-custody.py",
    "scripts/run-hosted-initial-recipient-productive.py",
    "scripts/run-hosted-cache-bootstrap.py",
    "scripts/hosted_initial_recipient_productive_custody.py",
    "scripts/hosted_initial_recipient_productive_custody_data.py",
    "scripts/hosted_initial_recipient_productive_receiver.py",
    "scripts/hosted_initial_recipient_productive_receiver_data.py",
    "scripts/run-hosted-initial-recipient-productive-receiver.py",
    "scripts/hosted_initial_recipient_productive_tail.py",
    "scripts/hosted_initial_recipient_productive_tail_data.py",
    "scripts/run-hosted-initial-recipient-productive-tail.py",
    "scripts/hosted_initial_artifact_productive_delivery.py",
    "scripts/run-hosted-initial-recipient-productive-upload.py",
    "scripts/hosted_initial_artifact_zip.py",
    "scripts/hosted_initial_artifact_delivery.py",
    "scripts/hosted_initial_recipient_tail_carrier.py",
    "scripts/hosted_initial_recipient_tail_evidence.py",
    "scripts/hosted_initial_recipient_tail_handoff.py",
    "scripts/run-hosted-initial-recipient-tail.py",
    "scripts/run-hosted-initial-recipient-upload.py",
    "scripts/hosted-initial-artifact-action.cjs",
    "scripts/hosted-initial-artifact-action-data.cjs",
    "scripts/hosted-initial-artifact-productive-action-data.cjs",
    "scripts/hosted-initial-artifact-reader.cjs",
    "scripts/hosted-initial-artifact-observer.cjs",
    "scripts/hosted-initial-artifact-transport.cjs",
    "scripts/hosted_initial_ordinary_identity.py",
    "scripts/hosted_initial_ordinary_originals.py",
    "scripts/hosted_initial_ordinary_qualification.py",
    "scripts/hosted_initial_ordinary_productive_qualification.py",
    "scripts/hosted_initial_ordinary_adapter.py",
    "scripts/run-hosted-initial-ordinary.py",
    "scripts/run-hosted-recipient-routing.py",
    "scripts/run-hosted-test-admission.py",
    ".github/actions/initial-recipient-initialize/action.yml",
    ".github/actions/initial-recipient-cache-provider/action.yml",
    ".github/actions/initial-recipient-cache-provider/index.cjs",
    ".github/actions/dependency-cache-provider/action.yml",
    ".github/actions/dependency-cache-provider/index.cjs",
    ".github/actions/initial-ordinary-cache-provider/action.yml",
    ".github/actions/initial-ordinary-cache-provider/index.cjs",
    ".github/actions/ordinary-cache-provider/action.yml",
    ".github/actions/ordinary-cache-provider/index.cjs",
    ".github/actions/initial-recipient-upload/action.yml",
    ".github/actions/initial-recipient-upload/index.cjs",
    ".github/actions/initial-recipient-productive-upload/action.yml",
    ".github/actions/initial-recipient-productive-upload/index.cjs",
    "scripts/check-heavy-job-queue-policy.rb",
    ".github/workflows/dependency-cache-bootstrap.yml",
    ".github/workflows/ci.yml",
    ".github/workflows/desktop-cross-host.yml",
    "scripts/initial-recipient-runner-tools.py",
    "scripts/check-initial-recipient-bootstrap-workflow-policy.rb",
    "scripts/hosted_evidence_primitives.py",
    "scripts/hosted_jvm_library_custody.py",
)


class CompatibilityError(RuntimeError):
    """Finite public reason, not original contents or native authority."""


def require(value, reason):
    if not value:
        raise CompatibilityError("CACHE_SOURCE_COMPATIBILITY_" + reason)


def _fields(value, names):
    require(type(value) is dict and set(value) == set(names), "FIELDS")
    return value


def _sha(value, width=64):
    require(type(value) is str and re.fullmatch("[0-9a-f]{" + str(width) + "}", value), "HASH")
    return value


def encoded(value):
    raw = (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
                      allow_nan=False) + "\n").encode("ascii")
    require(len(raw) <= LIMIT, "ENCODED_BYTES")
    return raw


def checked_inputs(value):
    # Local import only: the isolated provider preloads the unchanged seed leaf
    # before any compatibility caller. This module introduces no loader cycle.
    import hosted_dependency_seed_files as files
    _fields(value, ("seed", "provider"))
    seed = _fields(value["seed"], ("files", "allowlistSha256", "artifacts", "components", "policy"))
    _fields(seed["files"], files.INPUTS)
    _fields(value["provider"], PROVIDER_INPUTS)
    for checksum in (*seed["files"].values(), *value["provider"].values(), seed["allowlistSha256"]):
        _sha(checksum)
    for name, maximum in (("artifacts", files.authority.MAX_ARTIFACTS),
                          ("components", files.authority.MAX_COMPONENTS)):
        require(type(seed[name]) is int and 0 < seed[name] <= maximum, "ALLOWLIST_COUNTS")
    require(encoded(seed["policy"]) == encoded(files.policy()), "SEED_POLICY")
    require(len(PROVIDER_INPUTS) == len(set(PROVIDER_INPUTS)) == 123 and len(files.INPUTS) == 12 and
            not set(PROVIDER_INPUTS).intersection(files.INPUTS), "FIXED_ROSTERS")
    encoded(value)
    return value


def checked_envelope(value):
    _fields(value, ("schema", "scope", "source", "inputs"))
    require(type(value["schema"]) is int and value["schema"] == 1 and value["scope"] == SCOPE, "SCOPE")
    _fields(value["source"], ("commit", "tree"))
    for checksum in value["source"].values():
        _sha(checksum, 40)
    checked_inputs(value["inputs"])
    encoded(value)
    return value


def envelope(source, inputs):
    return checked_envelope({"schema": 1, "scope": SCOPE, "source": source, "inputs": inputs})


def envelope_digest(value):
    # One canonical byte representation INCLUDING one LF; no optional newline.
    return hashlib.sha256(encoded(checked_envelope(value))).hexdigest()


def source_read_labels():
    """Exact DATA projection of one seed12 + provider123 original read pass."""
    import hosted_dependency_seed_files as files
    labels = []
    for roster in (files.INPUTS, PROVIDER_INPUTS):
        opened = {()}
        labels.append("dependency-seed-source-root")
        for relative in roster:
            parts = tuple(relative.split("/"))
            for count in range(1, len(parts)):
                prefix = parts[:count]
                if prefix not in opened:
                    opened.add(prefix)
                    labels.append("dependency-seed-source-parent")
            labels.append("dependency-seed-input")
    require(len(labels) == 152, "FIXED_SOURCE_READ_SEQUENCE")
    return tuple(labels)


class _BorrowedSources:
    """Read accounting/alias checks only; every resource stays on the real parent.

    No close record, clock, acquisition authority or independent owner exists
    here. Seed and provider subreads use fresh directory maps but share the
    actual byte total. The caller's aggregate may additionally charge repeated
    passes, as the Stage2 native owner does.
    """

    def __init__(self, parent, check):
        self.parent, self._check = parent, check
        self.bytes, self.identities = 0, set()

    @property
    def unknown(self):
        return self.parent.unknown

    def end(self, *, new=False):
        return self.parent.end(new=new)

    def check(self, *, new=False):
        return self.parent.check(new=True) if new else self._check()

    def error(self, stage, error, *, unknown=False):
        self.parent.error(stage, error, unknown=unknown)

    def close_one(self, resource):
        self.parent.close_one(resource)

    def acquire(self, label, factory):
        import hosted_dependency_seed_files as files
        # Retain on the original parent BEFORE any fallible validation below.
        # On refusal the parent still owns this return, even if F._Owners has
        # not yet received it into its per-subread reference list.
        resource = self.parent.acquire(label, factory)
        try:
            if label in ("dependency-seed-source-root", "dependency-seed-source-parent", "dependency-seed-input"):
                directory = label != "dependency-seed-input"
                kinds = ((files.PosixSourceDirectory, files.windows.DependencySourceDirectory) if directory else
                         (files.PosixFile, files.windows.NativeFile))
                require(type(resource) in kinds, "ORIGINAL_NATIVE_SOURCE_TYPE")
                info = resource.verify()
                pin = tuple(info.identity)
                require(info.is_directory is directory and pin == tuple(resource.identity) and
                        files._identity(list(pin)) and pin not in self.identities, "SOURCE_IDENTITY_OR_ALIAS")
                self.identities.add(pin)
                if not directory:
                    before = resource.initial_info
                    require(info == before and type(before.size) is int and
                            0 <= before.size <= files.authority.MAX_XML_BYTES, "ORIGINAL_SOURCE_SIZE")
                    require(self.bytes + before.size <= TOTAL_LIMIT, "SOURCE_TOTAL_BYTES")
                    self.bytes += before.size
                self.check()
            return resource
        except BaseException as error:
            self.error("cache-compatibility-adopted-source", error)
            raise


def borrowed_sources(parent, check):
    return _BorrowedSources(parent, check)


def read_provider(borrowed, root, end, check):
    """Read only the constant123 paths using original descriptor-relative opens."""
    import hosted_dependency_seed_files as files
    require(type(borrowed) is _BorrowedSources, "BORROWED_SOURCE_READER")
    # Seed and provider roots are intentionally separate original acquisitions.
    # Their identical root inode is not an alias within either fresh subread.
    borrowed.identities = set()
    owners, values, first = files._Owners(borrowed), {}, None
    try:
        check()
        opened = {(): owners.acquire("source-root", lambda: files.public_root(root))}
        for relative in PROVIDER_INPUTS:
            check()
            require(type(relative) is str and relative.isascii() and "\\" not in relative, "SOURCE_PATH")
            parts = tuple(relative.split("/"))
            require(parts and all(part not in ("", ".", "..") for part in parts), "SOURCE_PATH")
            for count in range(1, len(parts)):
                prefix = parts[:count]
                if prefix not in opened:
                    parent = opened[prefix[:-1]]
                    opened[prefix] = owners.acquire("source-parent", lambda: parent.open_directory(
                        prefix[-1], deadline=end))
            raw = files._small_read(owners, opened[parts[:-1]], parts[-1], end, files.authority.MAX_XML_BYTES, check)
            values[relative] = hashlib.sha256(raw).hexdigest()
        for directory in opened.values():
            directory.verify()
        check()
    except BaseException as error:
        first = error
        borrowed.error("cache-compatibility-source-inputs", error)
        raise
    finally:
        try:
            owners.close()
        except BaseException as error:
            if first is None:
                raise
            files._note(first, "compatibility-source-inputs", error)
    check()
    return values


def read_inputs(parent, root, end, check):
    """One fresh152-acquisition pass, same original owner/end, no source cache."""
    import hosted_dependency_seed_files as files
    borrowed = borrowed_sources(parent, check)
    seed, _compiled = files.source_inputs(borrowed, root, end, check)
    provider = read_provider(borrowed, root, end, check)
    return checked_inputs({"seed": seed, "provider": provider})
