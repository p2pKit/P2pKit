"""Bootstrap-only H-to-original-empty-S copy; no provider or execution entry.

The same-call parent owns original predecessor/producer/retirement authority.
Supplied records alone do not authenticate those facts. Ordinary export/seed
guards are unchanged; this never fabricates a Desktop/FULL execution context.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import hosted_cache_bootstrap_custody as custody


staging, files, origin = custody.staging, custody.files, custody.origin
SCOPE = "BOOTSTRAP_DEPENDENCY_EXPORT_LEAF_V1"
STATUSES = ("KNOWN_EMPTY", "KNOWN_PARTIAL", "KNOWN_EXPORTED")


@dataclass(frozen=True)
class ExportEvidence:
    """Closed leaf data, not enclosing retirement or save/freeze authority."""
    raw: bytes = field(repr=False)
    checked_ns: int
    local_started: float
    checked_local: float


class _Window(staging._Window):
    def __init__(self, inputs, phase, previous):
        super().__init__(inputs, phase, staging._capture_phase(phase), previous, "dependency-export")
        # Only shorten the unchanged source-proposed120-second interval.
        self.soft = min(self.hard, origin.integer(self.first + 90 * origin.NS))
        self.local_soft = origin.wire._directed_deadline(self.local_start, 90, self.soft, self.first)


def export_snapshot(parent, inputs, window):
    """Copy only allowlisted artifact bytes after the parent's original return.

    Existing copy/native suppliers enforce512MiB/file,2GiB total and bounded
    inventories; there is no aggregate Windows Snapshot or replacement of H/S.
    The caller supplies a NEW owner and the original shared input/window pair.
    This leaf is repeatable supplied-data code, not public execution authority.
    """
    origin.require(type(inputs) is custody._Inputs and type(window) is _Window and window.inputs is inputs,
                   "BOOTSTRAP_EXPORT_INPUT_WINDOW")
    completion = False

    class CopyLeaf(staging._Leaf):
        def check(self, *, new=False):
            # During copying, the shared copier admits new candidates at90s;
            # their fixed writes/readbacks and final observations may finish
            # inside120s. A completion handle is not another candidate/window.
            super().check(new=new and not completion)

    leaf = CopyLeaf(parent, window)
    result = {"schema": 1, "scope": SCOPE, "binding": inputs.binding(),
        "predecessors": inputs.predecessors(), "plan": inputs.stage_value["plan"],
        "home": str(inputs.home), "restoreHome": str(inputs.restore),
        "sourceIdentity": list(inputs.directories["gradle-home"]),
        "destinationIdentity": inputs.stage["sourceIdentity"],
        "propertiesSha256": files.digest(inputs.properties_raw), "policy": files.policy(),
        "status": "FAILED", "completed": False, "retirement": "PENDING", "errors": [],
        "counts": {name: 0 for name in staging.COUNTERS}, "admitted": [], "misses": [],
        "enclosingOwnerRetirement": "NOT_OBSERVED_HERE", "inputProvenance": "SUPPLIED_RECORDS_NOT_ORIGINAL_CALL",
        "dependencyPopulation": "BOUNDED_ALLOWLISTED_SUBSET_ONLY", "nextPhaseAuthority": False,
        "budgetAcceptance": "NOT_ADMITTED", "testAcceptance": "NOT_PERFORMED", "exportSaveAuthority": False}
    try:
        leaf.check(new=True)
        source_inputs, compiled, extra = staging._sources(leaf, inputs)
        custody._equal(source_inputs, inputs.stage_value["inputs"], "BOOTSTRAP_EXPORT_SOURCE_INPUT_CHANGED")
        custody._equal(extra, inputs.stage_value["bootstrapInputs"], "BOOTSTRAP_EXPORT_SOURCE_INPUT_CHANGED")
        root = leaf.acquire("export-source-root", lambda: files.public_root(inputs.root))
        end = leaf.end(new=True)
        scripts = leaf.acquire("export-source-scripts", lambda: root.open_directory("scripts", deadline=end))
        result["exportInputs"] = {}
        for name in ("hosted_cache_bootstrap_export.py", "hosted_cache_bootstrap_custody.py", "hosted_dependency_cache.py"):
            raw, _binding = staging._read(leaf, scripts, name)
            result["exportInputs"]["scripts/" + name] = files.digest(raw)
        scripts.verify()
        root.verify()
        leaf.close_one(scripts)
        leaf.close_one(root)
        staging.cache.validate_plan(result["plan"], inputs.admitted.record, inputs.staging_raw, compiled,
            source_inputs, session=inputs.session, profile=inputs.profile, role=inputs.role, mode="bootstrap")
        # Recheck original directories and metadata, not the pre-producer empty H.
        handles = staging._initialized(leaf, inputs)
        original_bindings = inputs.seed_value["fileBindings"]
        for key, directory, name, raw in (
                ("initializer-context", handles["session"], "initializer-context.json", inputs.context_raw),
                ("canonical-context", handles["state"], "context.json", inputs.canonical_raw),
                ("properties", handles["gradle-home"], "gradle.properties", inputs.properties_raw)):
            staging._read(leaf, directory, name, expected=raw, binding=original_bindings[key])
        container = leaf.acquire("export-container", lambda: files.private_root(inputs.container))
        end = leaf.end(new=True)
        output = leaf.acquire("export-stage", lambda: container.open_directory("restore-home", deadline=end))
        custody._stage_readback(leaf, inputs, container, output)
        source = handles["gradle-home"]
        origin.require(tuple(source.identity) == inputs.directories["gradle-home"] and
                       list(output.identity) == inputs.stage["sourceIdentity"] and
                       tuple(source.identity) != tuple(output.identity), "BOOTSTRAP_EXPORT_ROOT_CHANGED")

        copy_interval = {"softEndNs": window.soft}

        def now():
            leaf.check()
            if window.local_last >= window.local_soft:
                # LOCAL expiry may shorten the RAW candidate cutoff, never
                # fabricate a clock reading or extend the original interval.
                copy_interval["softEndNs"] = min(copy_interval["softEndNs"], window.last)
            if window.last < copy_interval["softEndNs"]:
                window.last_new = window.last
            return window.last

        budget = files.RECEIPT_LIMIT - len(files.encoded(result)) - 512 * 1024
        origin.require(budget > 0, "BOOTSTRAP_EXPORT_RECEIPT_BUDGET")
        leaf.check(new=True)
        completion = True
        # Only the shared primitive's cutoff is supplied: no ordinary context,
        # primaryAbiAccounting, jobBudget digest or test acceptance is invented.
        files._copy_allowlisted(leaf, source, output, compiled, result, leaf.end(), leaf.check, now,
                               copy_interval, budget, empty_destination=True)
        staging._read(leaf, source, "gradle.properties", expected=inputs.properties_raw,
                      binding=original_bindings["properties"])
        staging._read(leaf, container, "staging.json", expected=inputs.staging_raw,
                      binding=inputs.stage_value["fileBindings"]["staging"])
        staging._names(leaf, container, ("restore-home", "staging.json"))
        for name, directory in handles.items():
            origin.require(tuple(directory.verify().identity) == inputs.directories[name],
                           "BOOTSTRAP_EXPORT_HOME_CHANGED")
        files.validate_stage(inputs.stage, inputs.admitted.record, inputs.profile, inputs.role, inputs.container,
                             container.verify(), output.verify(), source_inputs)
        leaf.check()
        leaf.close()
        leaf.check()
        result.update(status=STATUSES[0] if not result["admitted"] else
                      STATUSES[1] if result["misses"] else STATUSES[2], completed=True, retirement="KNOWN",
                      window=window.record())
        files._validate_inventory(result, compiled, statuses=STATUSES,
                                  destination_identity=result["destinationIdentity"])
        raw = files.encoded(result)
        leaf.check()  # Validation/serialization also spend the original interval.
        return ExportEvidence(raw, window.last, window.local_start, window.local_last)
    except BaseException as failure:
        first = failure if parent.original is None else parent.original
        leaf.error("bootstrap-export", first)
        try:
            leaf.close()
        except BaseException as secondary:
            leaf.error("bootstrap-export-close", secondary)
        result.update(status="UNKNOWN" if parent.unknown else "FAILED", completed=False,
                      retirement="UNKNOWN" if parent.unknown else "FAILED", errors=[type(first).__name__],
                      window=window.record())
        # First/falsey/unannotatable errors still escape unchanged. The parent
        # retains its own original handles; this is not an encrypted receipt.
        try:
            first.bootstrap_export_result = result
            first.bootstrap_export_resources = tuple(leaf.resources)
        except BaseException:
            pass
        raise first
