"""Closed ordinary-FULL supplemental composition, not a second executor.

Every producer uses the existing canonical leaf and native controller phase.
This module contains no process backend, installer, cache seeder or workflow
entrypoint. Its original roster is mandatory: failed/unreached work stays unmet.
"""
from __future__ import annotations

import base64
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import stat
import time
import uuid

import hosted_full_job_budget as job_time
import hosted_full_simulator as simulator

MODULES = ("p2p-core", "p2p-transport-lan", "p2p-network-provisioning-android", "p2p-network-provisioning-desktop")
NAMES = ("lock-policy", "android-abi-graph", "ios-project-generation", "dokka-sbom", "sbom",
         "published-consumers", "publication-shape", "xcframework-build", "xcframework-minimum-os",
         "swift-ui", "central-bundle")
SWIFT_PRELAUNCH = "swift-simulator-prelaunch"
SWIFT_RETIRE = ("swift-simulator-before", "swift-simulator-shutdown", "swift-simulator-after")
SWIFT_INSPECT = "swift-results"
CENTRAL_RETIRE = "central-retire-prepare"
PRODUCTIVE = (*NAMES, SWIFT_PRELAUNCH, SWIFT_INSPECT)
STAGES = {**{name: "product-return" for name in NAMES}, SWIFT_PRELAUNCH: "productive",
          SWIFT_INSPECT: "productive", CENTRAL_RETIRE: "uninstall",
          **dict(zip(SWIFT_RETIRE, simulator.RETIRE))}
ORDER = (*NAMES[:9], SWIFT_PRELAUNCH, "swift-ui", *SWIFT_RETIRE, SWIFT_INSPECT, "central-bundle", CENTRAL_RETIRE)
SIDECARS = ("BUILD_COMMIT.txt", "BUILD_SOURCE_STATE.txt", "BUILD_INPUTS_SHA256.txt", "BUILD_ARTIFACTS_SHA256.txt")
LIMIT = 4 * 1024 * 1024


def require(value, reason):
    if not value:
        raise ValueError(reason)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def encoded(value):
    return simulator.encoded(value)


def commands(state):
    return (
        ("command", ["bash", "scripts/tests/check-lock-write-policy-test.sh"]),
        ("command", ["bash", "scripts/check-android-abi-guard.sh"]),
        ("command", ["python3", "scripts/tests/ios-project-generation-test.py"]),
        ("gradle", [":" + module + ":dokkaGeneratePublicationHtml" for module in MODULES] + ["cyclonedxBom"]),
        ("command", ["bash", "scripts/check-sbom.sh", "build/reports/cyclonedx/bom.json", "build/reports/cyclonedx/bom.xml"]),
        ("command", ["bash", "scripts/check-published-consumers.sh"]),
        ("command", ["bash", "scripts/check-publish-artifacts.sh", str(state / "work/consumer/repository")]),
        ("gradle", [":p2p-transport-lan:verifyP2pKitSharedReleaseXCFrameworkProvenance"]),
        ("command", ["bash", "scripts/check-xcframework-minimum-os.sh"]),
        ("command", ["bash", "scripts/run-ios-ui-tests.sh"]),
        ("command", ["bash", "scripts/tests/build-central-portal-bundle-test.sh"]),
    )


def canonical_argv(api, context, spec, state):
    args = ["--cwd", api["ROOT"], "--wrapper", api["ROOT"] / "gradlew", "--kind", spec["kind"],
            "--purpose", spec["purpose"], "--id", spec["id"], "--timeout", 7200, "--stop-timeout", 120]
    if spec["name"] == "xcframework-build":
        args += ["--receipt", state / "host-xcframework-build.json"]
    return api["canonical_python"](context["python"], context["canonicalSources"], *args, "--", *spec["argv"])


def environment(label, state, selected):
    if label == "published-consumers":
        return {"P2PKIT_CONSUMER_WORK_DIR": str(state / "work/consumer"), "P2PKIT_CONSUMER_AUDIT_METADATA": "1"}
    if label == "swift-ui":
        return {"IOS_RUN_DIR": str(state / "work/swift-ui"), "KEEP_IOS_RUN_ARTIFACTS": "1",
                "SIM_UDID": selected["device"]["udid"], "P2PKIT_XCODE_JOBS": "2"}
    if label in ("central-bundle", CENTRAL_RETIRE):
        return {"P2PKIT_CENTRAL_BUNDLE_AUDIT": "1", "P2PKIT_CENTRAL_BUNDLE_WORK_DIR": str(state / "work/central-bundle"),
                "P2PKIT_CENTRAL_BUNDLE_EVIDENCE_DIR": str(state / "evidence/central-bundle")}
    return {}


def validate_intent(intent, state):
    require(type(intent) is list and len(intent) == len(NAMES), "FULL_SUPPLEMENT_ROSTER_REQUIRED")
    ids = []
    for row, name, (kind, argv) in zip(intent, NAMES, commands(state)):
        require(type(row) is dict and set(row) == {"name", "id", "kind", "purpose", "argv"} and row["name"] == name and
                row["kind"] == kind and row["argv"] == argv and row["purpose"] ==
                ("xcframework-build" if name == "xcframework-build" else "ordinary-full-" + name) and
                type(row["id"]) is str and re.fullmatch(r"[0-9a-f]{32}", row["id"]), "FULL_SUPPLEMENT_ROSTER_CHANGED")
        ids.append(row["id"])
    require(len(set(ids)) == len(ids), "FULL_SUPPLEMENT_ID_REUSED")
    return intent


def verify_abi_accounting(accounting, result, context, *, partial=False):
    required = context.get("primaryAbiAccounting")
    budget = result["jobBudget"]
    require(required == {"modes": ["productive", "terminal"], "oneShot": True,
                        "productiveCutoffRawNs": budget["productiveCutoffRawNs"], "localSeconds": 180},
            "ABI_ACCOUNTING_INTENT_CHANGED")
    require(type(accounting) is dict and set(accounting) == {"mode", "startedRawNs", "finishedRawNs",
            "productiveCutoffRawNs", "endRawNs", "rosterSha256", "acquisitionStarted"} and accounting["mode"] in required["modes"] and
            type(accounting["acquisitionStarted"]) is bool and
            accounting["productiveCutoffRawNs"] == required["productiveCutoffRawNs"] and
            accounting["rosterSha256"] == digest(encoded(context["fullSupplementIntent"])), "ABI_ACCOUNTING_CHANGED")
    start, finish, end = (accounting[key] for key in ("startedRawNs", "finishedRawNs", "endRawNs"))
    cutoff = required["productiveCutoffRawNs"]
    if not accounting["acquisitionStarted"]:
        require(partial and finish is None and (start is None and end is None or
                type(start) is int and 0 <= start < budget["controllerReturnRawNs"] and
                (end is None or type(end) is int and start < end <= min(start + 180 * job_time.NS,
                 cutoff + (0 if accounting["mode"] == "productive" else 1530 * job_time.NS), budget["controllerReturnRawNs"]))) and
                result.get("primaryAbi", {}).get("status") == "HOLD" and
                result["primaryAbi"].get("manifestSha256") is None and result.get("errors"),
                "ABI_UNACQUIRED_ACCOUNTING_CHANGED")
    else:
        require(all(type(value) is int and 0 <= value < job_time.UINT64 for value in (start, end)) and
                start < end <= start + 180 * job_time.NS and
                ((partial and finish is None) or type(finish) is int and start <= finish < end) and
                end <= cutoff + (0 if accounting["mode"] == "productive" else 1530 * job_time.NS) and
                end <= budget["controllerReturnRawNs"], "ABI_ACCOUNTING_INTERVAL_CHANGED")
    rows = result["phases"]
    prior = [row for row in rows if row["phase"] in ("product", "custody-collect", "custody-uninstall", *simulator.RETIRE)]
    if accounting["mode"] == "productive":
        require({row["phase"] for row in prior} >= {"product", "custody-collect", "custody-uninstall", simulator.BEFORE, simulator.AFTER} and
                all((start is None or row["finalizedRawNs"] <= start) and row["exitCode"] == 0 and row["retirement"] == "KNOWN" and
                    row["errors"] == [] for row in prior) and
                result.get("custody", {}).get("result") == "RETAINED" and
                result.get("simulator", {}).get("terminal", {}).get("status") == "KNOWN_SHUTDOWN",
                "ABI_ACCOUNTING_PRIMARY_BARRIER_CHANGED")
    later = [row for row in rows if row["phase"] in PRODUCTIVE]
    require(not later or (accounting["acquisitionStarted"] and accounting["mode"] == "productive" and type(finish) is int and
                          finish <= later[0]["startedRawNs"]),
            "ABI_TERMINAL_MODE_CANNOT_AUTHORIZE_SUPPLEMENTS")


def passing_labels(result):
    value = result.get("fullSupplements", {})
    labels = list(NAMES[:9]) + [SWIFT_PRELAUNCH, "swift-ui", SWIFT_RETIRE[0]]
    if value.get("swift", {}).get("shutdownAttempted"):
        labels.append(SWIFT_RETIRE[1])
    return labels + [SWIFT_RETIRE[2], SWIFT_INSPECT, "central-bundle", CENTRAL_RETIRE]


def profile_passed(result):
    value = result.get("fullSupplements")
    if type(value) is not dict or value.get("status") != "PASS" or value.get("pending") is not None:
        return False
    try:
        intent = validate_intent(value["intent"], Path(value["state"]))
        return (value["contextSha256"] == result["contextSha256"] and value["completed"] == list(NAMES) and
                value["central"].get("status") == "SCREENED_AND_REMOVED" and
                value["swift"].get("status") == "KNOWN_SHUTDOWN" and
                type(value["manifestSha256"]) is str and re.fullmatch(r"[0-9a-f]{64}", value["manifestSha256"]) and
                type(result.get("primaryAbiAccounting")) is dict and result["primaryAbiAccounting"]["mode"] == "productive" and
                [row["scope"] for row in value["scopes"]] == [row["name"] for row in intent] and
                all(row["status"] == "PASS" and row["canonicalId"] == spec["id"] and
                    row["phaseSha256"] == result["phaseSha256"].get(spec["name"])
                    for row, spec in zip(value["scopes"], intent)))
    except (KeyError, ValueError, TypeError):
        return False


def load_helper(path, label):
    spec = importlib.util.spec_from_file_location(label, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Full:
    def __init__(self, controller, api):
        self.c, self.a = controller, api
        self.specs = [{"name": name, "id": uuid.uuid4().hex, "kind": kind, "purpose":
                       "xcframework-build" if name == "xcframework-build" else "ordinary-full-" + name, "argv": argv}
                      for name, (kind, argv) in zip(NAMES, commands(controller.state_path))]
        self.pending = None
        self.scopes, self.completed, self.retained = [], [], {}
        self.directory = self.work = None
        self.central = {"status": "NOT_REACHED"}
        self.swift = {"status": "NOT_REACHED"}
        self.manifest = None
        self.helper_argv = {}
        self.central_attempted = self.central_retire_attempted = self.swift_retire_attempted = False
        self.central_end = self.central_raw_end = None

    def intent(self):
        return validate_intent(self.specs, self.c.state_path)

    def allocate(self, state):
        end = self.c.window("productive", 30)
        self.state = state  # Original init owner, never a post-writer replacement.
        self.work = self.c.child(state, "work", end, create=True)
        self.directory = self.c.child(self.c.evidence, "full-supplements", end, create=True)

    def bind_owners(self):
        # Original roots after protected allocation, before the first writer.
        roots = [*self.c.build_owners.values(), self.state, self.work]
        selected = {str(root.path): list(root.identity) for root in roots if root.path in
                    {self.a["ROOT"] / "build", *[self.a["ROOT"] / "library" / module / "build" for module in MODULES],
                     self.state.path, self.work.path}}
        self.c.write(self.directory, "prewriter-roots.json", {"schema": 1, "contextSha256": self.c.context_hash,
                     "roots": selected}, self.end())

    def spec(self, name):
        return next(row for row in self.specs if row["name"] == name)

    def argv(self, spec):
        return canonical_argv(self.a, self.a["parse"](self.c.run_context_raw), spec, self.c.state_path)

    def admit_phase(self, label, argv, spec, helper):
        require(self.pending is not None and self.c.active_canonical is None, "SUPPLEMENT_SCOPE_OWNER_REQUIRED")
        if helper:
            require(spec is None and label in (CENTRAL_RETIRE, SWIFT_INSPECT) and
                    argv == self.helper_argv.get(label) and self.pending ==
                    ("central-bundle" if label == CENTRAL_RETIRE else "swift-ui"), "SUPPLEMENT_HELPER_DOMAIN")
        else:
            require(spec == self.spec(self.pending) and label == self.pending and argv == self.argv(spec),
                    "SUPPLEMENT_CLOSED_SELECTOR")

    def environment(self, label):
        return environment(label, self.c.state_path, self.c.simulator)

    def end(self, *, terminal=False):
        if terminal:
            return self.c.freeze_end()
        self.c.check()
        return self.c.window("productive", 180)

    def read_path(self, path, end, maximum=LIMIT):
        # Existing snapshot/open-member suppliers handle mixed-case build names;
        # do not widen the query component namespace or follow caller paths.
        return read_path(self.c, self.a, path, end, maximum)

    def keep_tree(self, path, name, end):
        owner = tree_source(self.c, self.a, path)
        target = self.a["copy_tree"](self.c, owner, self.directory.path / name, end)
        raw = self.c.read(target, "original-path-map.json", end)
        self.retained[name] = {"source": str(path), "mapSha256": digest(raw), "prewriter": owner.prewriter}
        return json.loads(raw)

    def keep_file(self, path, name, end, maximum=LIMIT):
        view = tree_source(self.c, self.a, path.parent)
        raw = self.read_path(path, end, maximum)
        self.c.write(self.directory, name, raw, end)
        self.retained[name] = {"source": str(path), "bytes": len(raw), "sha256": digest(raw), "prewriter": view.prewriter}
        return raw

    def canonical(self, spec, row, end):
        return canonical(self.c, self.a, self.c.state_path, self.c.context, spec, row, end)

    def run(self):
        c = self.c
        require(c.primary_barrier_passed() and c.primary_abi["status"] == "PASS" and
                c.primary_abi_accounting["mode"] == "productive", "SUPPLEMENT_PRIMARY_BARRIER_REQUIRED")
        for spec in self.specs:
            c.check()
            require(not c.errors and self.pending is None and c.active_canonical is None, "SUPPLEMENT_PRIOR_OWNER_UNRETIRED")
            name = spec["name"]
            require(spec["id"] != c.request["owner"]["productInvocation"], "SUPPLEMENT_REUSES_PRIMARY_ID")
            self.pending = name  # Pending resources survive canonical return; not a cancellation target.
            entry = {"scope": name, "canonicalId": spec["id"], "status": "HOLD", "phaseSha256": None,
                     "canonical": None, "retained": {}}
            self.scopes.append(entry)
            if name == "central-bundle":
                self.central_attempted = True
                self.central = {"status": "PENDING_PRIVATE_QUARANTINE"}
            failure = None
            row = None
            before = set(self.retained)
            try:
                if name == "swift-ui":
                    self.prepare_swift()
                row = c.phase(name, self.argv(spec), 7530, supplement=spec)
                entry["phaseSha256"] = c.phase_hashes[name]
                entry["canonical"] = self.canonical(spec, row, c.window("product-final", 30))
                require(row["exitCode"] == 0, "SUPPLEMENT_PRODUCT_FAILED")
                if name not in ("swift-ui", "central-bundle"):
                    self.retain_scope(name, entry["canonical"], self.end())
            except BaseException as error:
                failure = error
            finally:
                entry["phaseSha256"] = c.phase_hashes.get(name)
                if name == "swift-ui":
                    try:
                        self.finish_swift(row, spec, failed=failure is not None)
                    except BaseException as error:
                        c.error("swift-finalizer", error)
                        failure = failure or error
                if name == "central-bundle":
                    try:
                        self.finish_central(row, spec)
                    except BaseException as error:
                        c.error("central-finalizer", error)
                        failure = failure or error
                entry["retained"] = {key: value for key, value in self.retained.items() if key not in before}
            if failure is not None:
                # Never erase the first producer error after successful cleanup.
                raise failure
            c.check()
            require(not c.unknown and c.active_canonical is None, "SUPPLEMENT_RETIREMENT_UNKNOWN")
            entry["status"] = "PASS"
            self.completed.append(name)
            self.pending = None

    def retain_scope(self, name, binding, end):
        c, root, state = self.c, self.a["ROOT"], self.c.state_path
        if name == "lock-policy":
            paths = sorted(self.work.path.glob("lock-policy.*"))
            require(len(paths) == 1, "LOCK_POLICY_WORK_ROSTER")
            mapping = self.keep_tree(paths[0], "lock-policy-work", end)
            names = {row["original"] for row in mapping["files"]}
            require({"ownership.json", "locks-before.txt", "locks-after.txt", *[label + ".log.receipt.json"
                for label in ("abbreviated", "indirect", "ordinary-write", "configure-on-demand-write", "authorized")]} <= names,
                "LOCK_POLICY_FIVE_ORIGINALS_REQUIRED")
            validate_nested(binding, "lock-policy", state)
        elif name == "android-abi-graph":
            validate_nested(binding, "android-abi-graph", state)
        elif name == "dokka-sbom":
            for module in MODULES:
                rows = self.keep_tree(root / "library" / module / "build/dokka/html", "dokka-" + module, end)
                require(any(row["original"].endswith(".html") and row["size"] for row in rows["files"]), "DOKKA_OUTPUT_MISSING")
            for suffix in ("json", "xml"):
                self.keep_file(root / ("build/reports/cyclonedx/bom." + suffix), "sbom." + suffix, end)
        elif name == "sbom":
            for suffix in ("json", "xml"):
                path = root / ("build/reports/cyclonedx/bom." + suffix)
                require(self.read_path(path, end) == c.read(self.directory, "sbom." + suffix, end), "SBOM_PRODUCER_PAIR_CHANGED")
        elif name == "published-consumers":
            validate_nested(binding, "published-consumers", state)
            candidates = list(state.glob("consumer-receipts.*"))
            require(len(candidates) == 1, "CONSUMER_ORIGINAL_RECEIPTS_AMBIGUOUS")
            self.keep_tree(candidates[0], "consumer-receipts", end)
            required = ("consumer-admission.json", "consumer-publication-manifest.json", "consumer-metadata-verification.json")
            values = {name: json.loads(self.read_path(candidates[0] / name, end)) for name in required}
            admission = values[required[0]]
            require(admission.get("source") == c.context["source"] and admission.get("workDir") == str(state / "work/consumer") and
                    admission.get("repository") == str(state / "work/consumer/repository") and
                    admission.get("repositoryInitiallyAbsent") is True, "CONSUMER_REPOSITORY_NOT_ADMITTED_FRESH")
            self.retain_publication(state / "work/consumer/repository", end)
            framework = state / "work/consumer/consumer/kmpConsumer/build/bin/iosSimulatorArm64/debugFramework/P2pKitConsumer.framework"
            self.keep_tree(framework, "consumer-framework", end)
        elif name == "publication-shape":
            require(self.publication_inventory(state / "work/consumer/repository", end) == self.publication_rows,
                    "PUBLICATION_CHANGED_AFTER_CONSUMER")
        elif name == "xcframework-build":
            release = root / "library/p2p-transport-lan/build/XCFrameworks/release"
            evidence = c.child(c.child(c.private, "state", end), "evidence", end)
            rows = []
            for name in SIDECARS:
                raw = self.read_path(release / name, end)
                write_sidecar(c, self.a, evidence, name, raw, end)
                rows.append({"path": name, "sha256": digest(raw), "result": "RETAINED"})
            manifest = {"files": rows, "sourceInvocationId": self.spec(name="xcframework-build")["id"]}
            c.write(evidence, "xcframework-sidecars.json", manifest, end)
            require(self.read_path(state / "host-xcframework-build.json", end) ==
                    self.read_path(state / "evidence" / self.spec("xcframework-build")["id"] / "receipt.json", end),
                    "XCF_PRODUCER_OPTIONAL_COPY_DIFFERS")
            self.keep_file(state / "host-xcframework-build.json", "xcframework-producer.json", end)
            # The canonical supplier is still the sole reuse authority; literal
            # copies/manifest above satisfy its existing exact public contract.
            self.a["audit"].xcframework_reuse_binding(state, c.context, root, root / "gradlew")
        c.check()
        c.check_window("productive", end)

    def publication_inventory(self, path, end):
        return inventory(self.c, self.a, path, end)

    def retain_publication(self, path, end):
        self.publication_rows = self.publication_inventory(path, end)
        require(self.publication_rows, "PUBLICATION_EMPTY")
        # Original POM/GMM/XML only; packages are hash-bound, not redundantly exported.
        target = self.c.child(self.directory, "publication-metadata", end, create=True)
        files = []
        for index, row in enumerate(self.publication_rows):
            if Path(row["path"]).suffix in (".pom", ".module", ".xml"):
                name = "metadata-" + str(index).zfill(5) + ".bin"
                raw = self.read_path(path / row["path"], end)
                self.c.write(target, name, raw, end)
                files.append({**row, "member": name})
        self.c.write(target, "manifest.json", {"source": str(path), "artifacts": self.publication_rows, "files": files}, end)
        self.retained["publication-metadata"] = {"manifestSha256": digest(self.c.read(target, "manifest.json", end))}

    def observe_swift(self, label):
        finalizing = label in SWIFT_RETIRE
        original = simulator.PRELAUNCH if not finalizing else simulator.RETIRE[SWIFT_RETIRE.index(label)]
        row = self.c.phase(label, simulator.command(original, self.c.simulator), simulator.SECONDS, finalizing=finalizing)
        end = self.c.window(original + "-read" if finalizing else "productive", 30)
        directory = self.c.child(self.c.commands, label, end)
        stdout, stderr = (self.c.read(directory, name, end) for name in ("stdout.log", "stderr.log"))
        require(row["exitCode"] == 0 and row["retirement"] == "KNOWN", "SWIFT_SIMULATOR_OBSERVATION_FAILED")
        self.c.check_window(original + "-read" if finalizing else "productive", end)
        return row, stdout, stderr

    def prepare_swift(self):
        c = self.c
        require(c.simulator_terminal.get("status") == "KNOWN_SHUTDOWN" and c.simulator_terminal.get("retirement") == "KNOWN",
                "SWIFT_PRIMARY_DEVICE_NOT_RETIRED")
        end = self.end()
        # Exact original producer/sidecars remain prerequisites, not a Boolean reuse flag.
        producer = self.a["audit"].xcframework_reuse_binding(c.state_path, c.context, self.a["ROOT"], self.a["ROOT"] / "gradlew")
        require(producer is not None, "SWIFT_FRESH_XCF_PRODUCER_REQUIRED")
        observed = self.observe_swift(SWIFT_PRELAUNCH)
        device = simulator.terminal_device(observed[1], c.simulator)
        require(device["state"] == "Shutdown", "SWIFT_PRELAUNCH_EXTERNAL_DEVICE")
        self.swift_prelaunch = encoded({"schema": 1, "scope": "CURRENT_SHUTDOWN_BEFORE_ORDINARY_SWIFT",
            "contextSha256": c.context_hash, "canonicalContextSha256": digest(c.canonical_context_raw),
            "spec": self.spec("swift-ui"), "device": device, "runtime": c.simulator["runtime"],
            "producer": producer, "primaryRetirementSha256": digest(encoded(c.simulator_terminal)),
            "original": simulator.phase_reference(*observed)})
        c.write(self.directory, "swift-prelaunch.json", self.swift_prelaunch, end)
        self.swift = {"status": "PENDING", "prelaunchSha256": digest(self.swift_prelaunch), "launchSha256": None,
                      "before": None, "after": None, "shutdownAttempted": False, "phases": {}, "bundles": [], "cases": None,
                      "inspectionReturnSha256": None, "inspectionRetirement": "NOT_REACHED"}

    def finish_swift(self, row, spec, *, failed):
        c = self.c
        if self.swift_retire_attempted or self.swift.get("status") == "NOT_REACHED":
            return
        self.swift_retire_attempted = True  # One shared615s envelope, never a new one.
        errors = []
        authority = None
        try:
            c.check(finalizing=True)
            row = next((item for item in c.records if item["phase"] == "swift-ui"), None)
            if row is not None and row.get("retirement") == "KNOWN" and row.get("launchAttempted"):
                end = c.window("product-final", 30)
                authority = swift_authority(c, self.a, spec, row, self.swift_prelaunch, end)
                raw = encoded(authority)
                c.write(self.directory, "swift-launch.json", raw, end)
                self.swift["launchSha256"] = digest(raw)
        except BaseException as error:
            errors.append(error)
        try:
            before = self.observe_swift(SWIFT_RETIRE[0])
            self.swift["phases"][SWIFT_RETIRE[0]] = simulator.phase_reference(*before)
            self.swift["before"] = simulator.terminal_device(before[1], c.simulator)
            if self.swift["before"]["state"] != "Shutdown":
                require(authority is not None, "SWIFT_UNLAUNCHED_EXTERNAL_STATE_CHANGE")
                self.swift["shutdownAttempted"] = True
                observed = self.observe_swift(SWIFT_RETIRE[1])
                self.swift["phases"][SWIFT_RETIRE[1]] = simulator.phase_reference(*observed)
        except BaseException as error:
            errors.append(error)
        finally:
            if not c.unknown:
                try:
                    after = self.observe_swift(SWIFT_RETIRE[2])
                    self.swift["phases"][SWIFT_RETIRE[2]] = simulator.phase_reference(*after)
                    self.swift["after"] = simulator.terminal_device(after[1], c.simulator)
                    require(self.swift["after"]["state"] == "Shutdown", "SWIFT_SIMULATOR_NOT_RETIRED")
                except BaseException as error:
                    errors.append(error)
        if c.unknown or self.swift["after"] is None or self.swift["after"]["state"] != "Shutdown":
            c.unknown = True
            self.swift["status"] = "UNKNOWN"
            raise errors[0] if errors else ValueError("SWIFT_RETIREMENT_UNKNOWN")
        self.swift["status"] = "HOLD" if errors or authority is None else "KNOWN_SHUTDOWN"
        # Original failed xcresults are retained BEFORE any inspection or cleanup.
        end = self.end(terminal=failed or bool(errors) or c.cancelled or c.budget_exhausted)
        parent = c.state_path / "work/swift-ui/DerivedData/Logs/Test"
        bundles = sorted(parent.glob("*.xcresult")) if parent.exists() else []
        require(len(bundles) <= 4, "SWIFT_XCRESULT_ROSTER_BOUND")
        for index, path in enumerate(bundles):
            name = "swift-xcresult-" + str(index)
            mapping = self.keep_tree(path, name, end)
            require(mapping["files"], "SWIFT_XCRESULT_EMPTY")
            self.swift["bundles"].append({"path": str(path), "retained": name, "mapSha256": digest(encoded(mapping))})
        if errors:
            raise errors[0]
        if failed:
            return
        c.check()
        require(bundles and authority is not None, "SWIFT_ACTUAL_RESULTS_REQUIRED")
        input_raw = encoded({"schema": 1, "contextSha256": c.context_hash, "canonicalId": spec["id"],
                             "bundles": [str(path) for path in bundles]})
        c.write(self.directory, "swift-inspection-input.json", input_raw, self.end())
        argv = c.python(self.a["SCRIPTS"] / "inspect-ordinary-swift-results.py", "--session", c.path,
                        "--input-sha256", digest(input_raw))
        self.helper_argv[SWIFT_INSPECT] = argv
        first = None
        try:
            row = c.phase(SWIFT_INSPECT, argv, 120, helper=True)
        except BaseException as error:
            first = error
            row = next((item for item in c.records if item["phase"] == SWIFT_INSPECT), None)
        try:
            # Parent-native KNOWN does not prove helper sink retirement. A
            # missing/ambiguous terminal keeps this original domain quarantined
            # and prevents even a failed-evidence export; never retry inspection.
            require(not c.unknown and row is not None, "SWIFT_HELPER_NATIVE_RETURN_REQUIRED")
            end = c.window("productive", 30)
            terminal_raw = self.read_path(c.state_path / "evidence/swift-inspection-return.json", end)
            inspector = load_helper(Path(__file__).parent / "inspect-ordinary-swift-results.py", "full_swift_inspector")
            retirement = inspector.assess_return(c.state_path / "evidence/swift-inspection", self.a["parse"](terminal_raw), row,
                context_sha=c.context_hash, input_sha=digest(input_raw), canonical_id=spec["id"],
                raw_limit=c.budget.fence("productive"), reader=lambda path: self.read_path(path, end),
                check=lambda: (c.check_window("productive", end), self.a["posix"]._deadline(end)))
            self.swift["inspectionReturnSha256"] = digest(terminal_raw)
            self.swift["inspectionRetirement"] = retirement["retirement"]
        except BaseException as error:
            self.swift["inspectionRetirement"] = "UNKNOWN"
            c.error("swift-inspection-resource", error, unknown=True)
            raise first or error
        if first is not None:
            raise first
        require(row["exitCode"] == 0 and retirement["status"] == "PASS", "SWIFT_XCRESULT_INSPECTION_FAILED")
        raw = self.read_path(c.state_path / "evidence/swift-case-results.json", end)
        value = self.a["parse"](raw)
        require(value.get("contextSha256") == c.context_hash and value.get("inputSha256") == digest(input_raw) and
                value.get("canonicalId") == spec["id"], "SWIFT_RESULTS_CONTEXT_CHANGED")
        self.swift["cases"] = inspector.assess_retained(c.state_path / "evidence/swift-inspection", value,
            reader=lambda path: self.read_path(path, end), check=lambda: (c.check(), c.check_window("productive", end)))
        self.swift["inspectionSha256"] = digest(raw)
        c.check()

    def finish_central(self, row, spec):
        c = self.c
        require(not self.central_retire_attempted, "CENTRAL_RETIREMENT_ONE_SHOT")
        self.central_retire_attempted = True
        require(not c.unknown and c.active_canonical is None, "CENTRAL_CANONICAL_RETURN_UNKNOWN")
        row = next((item for item in c.records if item["phase"] == "central-bundle"), None)
        require(row is not None and row.get("retirement") == "KNOWN" and not row.get("errors"), "CENTRAL_NATIVE_RETURN_REQUIRED")
        # One whole transaction includes context's five Git calls, full source
        # checks, all later Git, reads/scans/native close and final file removal.
        start = c.now_raw()
        self.central_raw_end = min(start + 360 * job_time.NS, c.budget.fence("uninstall-read"))
        self.central_end = c.window("uninstall-read", 360)
        helper_raw_end = min(start + 285 * job_time.NS, c.budget.fence("uninstall"), self.central_raw_end - 75 * job_time.NS)
        require(start < helper_raw_end, "CENTRAL_RETIREMENT_TRANSACTION_EXPIRED")
        argv = c.python(self.a["SCRIPTS"] / "prepare-audit-central-bundle-metadata.py", "prepare-retire",
            "--outer-receipt", c.state_path / "evidence" / spec["id"] / "receipt.json", "--deadline-raw-ns", helper_raw_end)
        self.helper_argv[CENTRAL_RETIRE] = argv
        self.central.update(startedRawNs=start, endRawNs=self.central_raw_end, helperEndRawNs=helper_raw_end)
        helper_row = c.phase(CENTRAL_RETIRE, argv, 285, finalizing=True, helper=True)
        require(helper_row["exitCode"] == 0 and helper_row["retirement"] == "KNOWN", "CENTRAL_PREPARE_FAILED_PRIVATE_HOLD")
        def check():
            c.check(finalizing=True)
            self.a["posix"]._deadline(self.central_end)
            require(c.now_raw() < self.central_raw_end, "CENTRAL_RETIREMENT_TRANSACTION_EXPIRED")
        check()
        metadata = c.state_path / "evidence/central-bundle"
        prepared_raw = self.read_path(metadata / "retirement-prepared.json", self.central_end)
        prepared = self.a["parse"](prepared_raw)
        require(prepared.get("deadlineRawNs") == helper_raw_end and prepared.get("outerId") == spec["id"] and
                prepared.get("contextSha256") == digest(c.canonical_context_raw), "CENTRAL_PREPARE_BOUND_CHANGED")
        module = load_helper(Path(__file__).parent / "prepare-audit-central-bundle-metadata.py", "full_central_retirement")
        work = c.state_path / "work/central-bundle"
        context = {"state": c.state_path, "root": self.a["ROOT"], "home": c.state_path / "gradle-home",
                   "work": work, "evidence": metadata, "fixture": work / "release-source", "repository": work / "repository",
                   "value": c.context, "source": c.context["source"], "contextSha256": digest(c.canonical_context_raw)}
        result = self.a["parse"](self.read_path(metadata / "result.json", self.central_end))
        # The parent's one original RAW/local transaction also bounds the
        # existing metadata readers and matcher construction, not just Git.
        module.BOUND_CHECK = check
        require(result.get("retentionStatus") == "RETAINED" and result.get("errors") == [] and
                module.key_input_records(context, result) == prepared["keyInputs"], "CENTRAL_KEY_OR_RETENTION_UNAVAILABLE")
        # Matchers remain only in this private interpreter; no receipt contains
        # raw key bytes, passphrases or fragment needles. No erasure claim.
        needles = module.secret_needles(context)
        check()
        scanned = {}
        for label, path in (("canonical", c.state_path / "evidence"), ("controller", c.evidence.path)):
            scanned[label] = inventory(c, self.a, path, self.central_end, needles=needles, check=check)
            check()
        require(all(any(item["path"] == spec["id"] + "/" + suffix for item in scanned["canonical"])
                    for suffix in ("product.stdout.log", "product.stderr.log", "stop.stdout.log", "stop.stderr.log")) and
                all(any(item["path"] == "commands/" + label + "/" + suffix for item in scanned["controller"])
                    for label in ("central-bundle", CENTRAL_RETIRE) for suffix in ("stdout.log", "stderr.log")),
                "CENTRAL_CLOSED_ENCLOSING_STREAMS_MISSING")
        # Recheck the closed set immediately BEFORE destruction; native/late
        # helper captures are all now closed, and this tail creates no child.
        for label, path in (("canonical", c.state_path / "evidence"), ("controller", c.evidence.path)):
            require(inventory(c, self.a, path, self.central_end, check=check) == scanned[label], "CENTRAL_SCREENED_BYTES_CHANGED")
            check()
        removal = module.complete_prepared_retirement(context, prepared_raw, check=check)
        require(removal["workRemoved"] is True and removal["gpgHomesRemoved"] is True, "CENTRAL_REMOVAL_UNKNOWN")
        screen = {"schema": 1, "scope": "CLOSED_CENTRAL_ENCLOSING_STREAM_SCREEN", "contextSha256": c.context_hash,
                  "canonicalId": spec["id"], "preparedSha256": digest(prepared_raw),
                  "canonicalPhaseSha256": c.phase_hashes["central-bundle"],
                  "helperPhaseSha256": c.phase_hashes[CENTRAL_RETIRE], "startedRawNs": start,
                  "finishedRawNs": c.now_raw(), "endRawNs": self.central_raw_end, "files": scanned, "removal": removal}
        raw = encoded(screen)
        c.write(self.directory, "central-screen.json", raw, self.central_end)
        canonical_evidence = c.child(c.child(self.state, "evidence", self.central_end), "central-bundle", self.central_end)
        c.write(canonical_evidence, "screen-result.json", raw, self.central_end)
        check()
        self.central = {"status": "SCREENED_AND_REMOVED", "screenSha256": digest(raw), "canonicalId": spec["id"],
                        "startedRawNs": start, "endRawNs": self.central_raw_end,
                        "helperEndRawNs": helper_raw_end, "finishedRawNs": screen["finishedRawNs"]}

    def result(self):
        return {"status": "PASS" if self.completed == list(NAMES) and self.pending is None and self.manifest is not None else "HOLD",
                "contextSha256": getattr(self.c, "context_hash", None), "state": str(self.c.state_path), "intent": self.intent(),
                "completed": list(self.completed), "pending": self.pending, "scopes": self.scopes,
                "swift": self.swift, "central": self.central, "manifestSha256": None if self.manifest is None else digest(self.manifest)}

    def freeze(self, end):
        # Central was not reached: prove that no key-capable scope or namespace
        # was created, instead of inventing a successful screening receipt.
        if self.central_attempted:
            require(self.central.get("status") == "SCREENED_AND_REMOVED", "CENTRAL_RAW_EXPORT_QUARANTINED")
            verify_central_screen(self.c, self.a, self.c.private, self.central, end)
        else:
            require(not any(row["phase"] == "central-bundle" for row in self.c.records) and
                    not os.path.lexists(self.c.state_path / "work/central-bundle") and
                    not os.path.lexists(self.c.state_path / "evidence/central-bundle"), "CENTRAL_UNREACHED_NAMESPACE_CHANGED")
        if self.directory is not None:
            require(self.manifest is None, "SUPPLEMENT_FREEZE_ONE_SHOT")
            value = {"schema": 1, "scope": "ORDINARY_FULL_SUPPLEMENT_ORIGINALS", "contextSha256": self.c.context_hash,
                     "intent": self.intent(), "completed": self.completed, "pending": self.pending,
                     "scopes": self.scopes, "retained": self.retained, "swift": self.swift, "central": self.central,
                     "files": inventory(self.c, self.a, self.directory.path, end)}
            raw = encoded(value)
            self.c.write(self.directory, "manifest.json", raw, end)
            self.c.check_window("export-freeze", end)
            self.manifest = raw
        # Actual original validators run BEFORE even the first canonical raw
        # copy. A key quarantine/missing role is not deferred to encryption/seal.
        verify(self.c, self.a, self.c.private, self.c.result(), self.a["parse"](self.c.run_context_raw), end)


def tree_source(owner, api, path):
    """Non-owning view of a fixed caller's existing tree; existing readers do I/O."""
    from types import SimpleNamespace
    path = api["posix"]._path(path)
    prewriter = None
    if hasattr(owner, "build_owners"):
        # On the producing controller, relevant original roots were protected
        # before any product. Newly sampling a replaced build is not admission.
        roots = list(owner.build_owners.values())
        if getattr(owner, "full", None) is not None and owner.full.work is not None:
            roots += [owner.full.work, owner.full.state]
        roots += [owner.private] if owner.private is not None else []
        guards = [root for root in roots if path == root.path or root.path in path.parents]
        require(guards, "SUPPLEMENT_PREWRITER_OWNER_REQUIRED")
        guard = max(guards, key=lambda value: len(value.path.parts))
        guard.verify()
        prewriter = {"path": str(guard.path), "identity": list(guard.identity)}
    before = path.lstat()
    require(stat.S_ISDIR(before.st_mode) and before.st_uid == os.getuid() and not before.st_mode & 0o022,
            "SUPPLEMENT_SOURCE_TREE_UNSAFE")
    chain = {p: (p.lstat().st_dev, p.lstat().st_ino, p.lstat().st_mode) for p in (path, *path.parents)}
    def verify():
        if prewriter is not None:
            guard.verify()
        for parent, original in chain.items():
            now = parent.lstat()
            require((now.st_dev, now.st_ino, now.st_mode) == original and not stat.S_ISLNK(now.st_mode),
                    "SUPPLEMENT_SOURCE_TREE_REPLACED")
        require(not owner.unknown, "SUPPLEMENT_SOURCE_OWNER_UNKNOWN")
    return SimpleNamespace(path=path, verify=verify, prewriter=prewriter)


def read_path(owner, api, path, end, maximum=LIMIT):
    view = tree_source(owner, api, path.parent)
    view.verify()
    info = path.lstat()
    require(stat.S_ISREG(info.st_mode) and info.st_uid == os.getuid() and not info.st_mode & 0o022 and
            info.st_nlink == 1 and 0 <= info.st_size <= maximum, "SUPPLEMENT_ORIGINAL_FILE_BOUND")
    rows = {"": api["posix"]._stamp(path.parent.lstat()), path.name: api["posix"]._stamp(info)}
    reader = owner.acquire("supplement-reader", lambda: api["posix"]._open_member(path.parent, path.name, rows))
    original = None
    try:
        api["posix"]._deadline(end)
        raw = reader.read(maximum + 1)
        require(len(raw) == info.st_size and reader.read(1) == b"" and api["posix"]._stamp(os.fstat(reader.fileno())) == rows[path.name],
                "SUPPLEMENT_ORIGINAL_CHANGED")
    except BaseException as error:
        original = error
        owner.error("supplement-read", error)
    finally:
        owner.close_one(reader)
    if original is not None:
        raise original
    require(not owner.unknown and api["posix"]._stamp(path.lstat()) == rows[path.name], "SUPPLEMENT_ORIGINAL_CHANGED")
    view.verify()
    api["posix"]._deadline(end)
    return raw


def post_screen_addition(name):
    # Closed, already-proved copies/controller records created after screening.
    # No arbitrary scanner inputs or path/prefix list comes from the caller.
    return name in {"full-supplements/central-screen.json", "full-supplements/manifest.json",
                    "canonical-context.json", "recipient.json", "profile-result-before-export.json"} or any(
        name == prefix or name.startswith(prefix + "/") for prefix in
        ("canonical-audit", "recipient-validation", "commands/export"))


def inventory(owner, api, path, end, *, needles=None, check=lambda: None, after_screen=False, canonical_screen=False):
    view = tree_source(owner, api, path)
    view.verify()
    snapshot = api["posix_snapshot"](owner, path, api["posix"].MAX_BYTES, api["posix"].MAX_MEMBERS, end)
    selected = lambda rows: {name: value for name, value in rows.items()
        if not (after_screen and post_screen_addition(name)) and not (canonical_screen and name == "central-bundle/screen-result.json")}
    records = []
    for name, stamp in sorted(selected(snapshot).items()):
        check()
        if not stat.S_ISREG(stamp[2]):
            continue
        reader = owner.acquire("supplement-inventory-reader", lambda: api["posix"]._open_member(path, name, snapshot))
        original = None
        try:
            size, checksum, tail = 0, hashlib.sha256(), b""
            while True:
                check()
                api["posix"]._deadline(end)
                raw = reader.read(65536)
                if not raw:
                    break
                size += len(raw)
                require(size <= stamp[5], "SUPPLEMENT_INVENTORY_GREW")
                checksum.update(raw)
                if needles is not None:
                    require(not any(needle in tail + raw for needle in needles), "CENTRAL_ORIGINAL_CREDENTIAL_QUARANTINE")
                    tail = (tail + raw)[-256:]
            require(size == stamp[5] and api["posix"]._stamp(os.fstat(reader.fileno())) == stamp,
                    "SUPPLEMENT_INVENTORY_CHANGED")
            records.append({"path": name, "bytes": size, "sha256": checksum.hexdigest()})
        except BaseException as error:
            original = error
            owner.error("supplement-inventory", error)
        finally:
            owner.close_one(reader)
        if original is not None:
            raise original
        require(not owner.unknown, "SUPPLEMENT_INVENTORY_CLOSE_UNKNOWN")
    require(selected(api["posix_snapshot"](owner, path, api["posix"].MAX_BYTES, api["posix"].MAX_MEMBERS, end)) == selected(snapshot),
            "SUPPLEMENT_INVENTORY_TREE_CHANGED")
    view.verify()
    check()
    return records


def write_sidecar(owner, api, directory, name, raw, end):
    # Exactly four uppercase literal compatibility roles. Reuse the existing
    # POSIX descriptor supplier; the query component namespace remains unchanged.
    require(name in SIDECARS and type(raw) is bytes and 0 < len(raw) <= LIMIT, "XCF_LITERAL_SIDECAR")
    directory.verify()
    stream = owner.acquire("xcframework-sidecar", lambda: api["query"]._posix_stream(directory.path / name,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, "wb"))
    original = None
    try:
        api["posix"]._deadline(end)
        require(stream.write(raw) == len(raw), "XCF_SIDECAR_SHORT_WRITE")
        stream.flush()
        os.fsync(stream.fileno())
        api["query"]._file_info(directory.path / name, stream, len(raw))
    except BaseException as error:
        original = error
        owner.error("xcframework-sidecar-write", error)
    finally:
        owner.close_one(stream)
    if original is not None:
        raise original
    require(not owner.unknown and read_path(owner, api, directory.path / name, end) == raw, "XCF_SIDECAR_CHANGED")
    directory.verify()


def canonical(owner, api, state, context, spec, phase, end):
    root = api["ROOT"]
    directory = state / "evidence" / spec["id"]
    start_raw = read_path(owner, api, directory / "start.json", end)
    raw = read_path(owner, api, directory / "receipt.json", end)
    start, receipt = (api["parse"](value) for value in (start_raw, raw))
    checker = load_helper(Path(__file__).parent / "check-audit-receipt.py", "full_supplement_receipt_checker")
    checker.validate(receipt, phase["exitCode"], spec["purpose"], root, root / "gradlew", spec["argv"])
    require(receipt.get("id") == spec["id"] and receipt.get("kind") == spec["kind"] and receipt.get("jobId") == context["id"] and
            receipt.get("gradleHome") == context["gradleHome"] and receipt.get("host") == context["host"] and
            receipt.get("sourceBefore") == context["source"] and receipt.get("ancestorInvocationIds") == phase["childAncestorInvocationIds"] and
            receipt.get("evidenceDirectory") == str(directory) and phase["state"] == str(state) and
            phase["job"] == context["id"] and phase["home"] == context["gradleHome"], "SUPPLEMENT_CANONICAL_DOMAIN_CHANGED")
    immutable = ("schema", "id", "kind", "purpose", "requestedArgv", "cwd", "wrapper", "host", "jobId", "gradleHome",
                 "startedUtc", "controllerPid", "ancestorInvocationIds", "evidenceDirectory")
    require(all(start.get(key) == receipt.get(key) for key in immutable) and
            start.get("sourceBefore") is None and start.get("sourceAfter") is None and
            start.get("productExitCode") is None and start.get("stopExitCode") is None and start.get("finalExitCode") == 125,
            "SUPPLEMENT_CANONICAL_START_CHANGED")
    executed = spec["argv"] if spec["kind"] == "command" else [str(root / "gradlew"), *api["audit"].gradle_arguments(spec["argv"])]
    require(receipt.get("executedArgv") == executed and receipt.get("cancelRequested", False) is False and
            receipt.get("cancelledSignals", []) == [], "SUPPLEMENT_EXECUTION_OR_CANCELLATION_CHANGED")
    native = simulator.created_native_launch(phase["ownership"], 0, phase["argv"], str(root), context["id"], phase["invocation"])
    require(start.get("controllerPid") == native["launch"]["pid"], "SUPPLEMENT_CANONICAL_NATIVE_PARENT_CHANGED")
    product = simulator.created_native_launch(receipt.get("ownership"), receipt.get("productLaunchIndex"), executed,
                                               str(root), context["id"], spec["id"])
    require(receipt.get("productPid") == product["launch"]["pid"], "SUPPLEMENT_PRODUCT_BIRTH_CHANGED")
    # The canonical supplier owns nested receipt/stop domains; bind every actual
    # reached child here, including expected policy-red leaves, not a log marker.
    descendants = []
    for path in sorted((state / "evidence").glob("*/receipt.json")):
        value_raw = read_path(owner, api, path, end)
        value = api["parse"](value_raw)
        ancestors = value.get("ancestorInvocationIds", [])
        if spec["id"] not in ancestors:
            continue
        require(ancestors[:len(receipt["ancestorInvocationIds"]) + 1] == [*receipt["ancestorInvocationIds"], spec["id"]],
                "SUPPLEMENT_NESTED_ANCESTORS_CHANGED")
        checker.validate(value, value.get("finalExitCode"), value.get("purpose"), root, root / "gradlew", value.get("requestedArgv"))
        require(path.parent.name == value["id"] and value.get("jobId") == context["id"] and
                value.get("gradleHome") == context["gradleHome"] and value.get("sourceBefore") == context["source"] and
                value.get("ownership", {}).get("job") == context["id"] and
                value.get("ownership", {}).get("invocation") == value["id"] and
                value.get("ownership", {}).get("discoveryErrors") == [], "SUPPLEMENT_NESTED_DOMAIN_CHANGED")
        child_start = api["parse"](read_path(owner, api, path.parent / "start.json", end))
        require(all(child_start.get(key) == value.get(key) for key in immutable), "SUPPLEMENT_NESTED_START_CHANGED")
        descendants.append({"id": value["id"], "purpose": value["purpose"], "kind": value["kind"],
                            "requestedArgv": value["requestedArgv"], "finalExitCode": value["finalExitCode"],
                            "receiptSha256": digest(value_raw)})
    return {"receiptSha256": digest(raw), "startSha256": digest(start_raw), "descendants": descendants,
            "canonicalNative": native, "productNative": product}


def validate_nested(binding, name, state):
    rows = binding["descendants"]
    require(len({row["purpose"] for row in rows}) == len(rows), "SUPPLEMENT_NESTED_DUPLICATE_PURPOSE")
    by_name = {row["purpose"]: row for row in rows}
    if name == "lock-policy":
        suffixes = ("abbreviated", "indirect", "ordinary-write", "configure-on-demand-write", "authorized")
        require(set(by_name) == {"lock-policy-" + value for value in suffixes}, "LOCK_POLICY_FIVE_LEAVES_REQUIRED")
        for label in suffixes:
            row = by_name["lock-policy-" + label]
            require(row["kind"] == "gradle" and type(row["finalExitCode"]) is int and
                    (row["finalExitCode"] == 0 if label == "authorized" else row["finalExitCode"] not in (0, 125)),
                    "LOCK_POLICY_EXPECTED_OUTCOME_CHANGED")
    elif name == "android-abi-graph":
        require(set(by_name) == {"android-abi-graph"} and by_name[name]["kind"] == "gradle" and
                by_name[name]["finalExitCode"] == 0 and by_name[name]["requestedArgv"] == [
                    ":p2p-core:check", ":p2p-transport-lan:check", ":p2p-network-provisioning-android:check",
                    "--dependency-verification=strict", "--dry-run", "--console=plain"], "ANDROID_ABI_REAL_GRAPH_REQUIRED")
    elif name == "published-consumers":
        require(set(by_name) == {"consumer-publish", "consumer-build"} and
                all(row["kind"] == "gradle" and row["finalExitCode"] == 0 for row in rows), "COMPLETE_CONSUMER_LEAVES_REQUIRED")
        helper = load_helper(Path(__file__).parent / "prepare-audit-consumer-metadata.py", "full_consumer_contract")
        require(by_name["consumer-publish"]["requestedArgv"] == ["--no-daemon", "--console=plain", "publishToMavenLocal",
                    "-Dmaven.repo.local=" + str(state / "work/consumer/repository")] and
                by_name["consumer-build"]["requestedArgv"] == ["--no-daemon", "--console=plain", "-p",
                    str(state / "work/consumer/consumer"), "-PconsumerRepo=" + str(state / "work/consumer/repository"),
                    *helper.CONSUMER_TASKS], "COMPLETE_CONSUMER_SELECTOR_CHANGED")


def swift_authority(owner, api, spec, phase, prelaunch_raw, end, *, private=None):
    """Cleanup authority from actual native births, even for a failed Swift test.

    This is not a product PASS predicate and does not borrow the primary launch.
    A failed canonical start without a created script grants no simulator rights.
    """
    private = private or owner.private
    run_raw = read_path(owner, api, private.path / "run-context.json", end)
    run = api["parse"](run_raw)
    state = private.path / "state"
    context_raw = read_path(owner, api, state / "context.json", end)
    context, before = api["parse"](context_raw), api["parse"](prelaunch_raw)
    require(spec in validate_intent(run["fullSupplementIntent"], state) and spec["name"] == "swift-ui" and
            before.get("scope") == "CURRENT_SHUTDOWN_BEFORE_ORDINARY_SWIFT" and before.get("spec") == spec and
            before.get("contextSha256") == digest(run_raw) and before.get("canonicalContextSha256") == digest(context_raw) and
            before.get("device", {}).get("state") == "Shutdown" and phase.get("phase") == "swift-ui" and
            phase.get("argv") == canonical_argv(api, run, spec, state) and phase.get("retirement") == "KNOWN" and
            phase.get("survivors") == [] and phase.get("job") == context["id"] and phase.get("state") == str(state) and
            phase.get("home") == context["gradleHome"] and phase.get("canonicalInvocation") == spec["id"] and
            phase.get("supplementEnvironment") == environment("swift-ui", state, {"device": before["device"]}),
            "SWIFT_ACTUAL_LAUNCH_AUTHORITY_REQUIRED")
    native = simulator.created_native_launch(phase.get("ownership"), 0, phase["argv"], str(api["ROOT"]),
                                            context["id"], phase["invocation"])
    directory = state / "evidence" / spec["id"]
    start_raw, raw = (read_path(owner, api, directory / name, end) for name in ("start.json", "receipt.json"))
    start, receipt = (api["parse"](value) for value in (start_raw, raw))
    expected = {"schema": 1, "id": spec["id"], "kind": spec["kind"], "purpose": spec["purpose"], "requestedArgv": spec["argv"],
               "cwd": str(api["ROOT"]), "wrapper": str(api["ROOT"] / "gradlew"), "host": context["host"], "jobId": context["id"],
               "gradleHome": context["gradleHome"], "ancestorInvocationIds": phase["childAncestorInvocationIds"],
               "controllerPid": native["launch"]["pid"], "evidenceDirectory": str(directory)}
    require(all(start.get(key) == value == receipt.get(key) for key, value in expected.items()) and
            start.get("sourceBefore") is None and start.get("sourceAfter") is None and start.get("productExitCode") is None and
            start.get("stopExitCode") is None and start.get("finalExitCode") == 125 and
            type(start.get("startedUtc")) is str and start["startedUtc"] == receipt.get("startedUtc") and
            receipt.get("sourceBefore") == context["source"] and receipt.get("executedArgv") == spec["argv"] and
            receipt.get("ownedSurvivors") == [], "SWIFT_ACTUAL_CANONICAL_START_REQUIRED")
    product = simulator.created_native_launch(receipt.get("ownership"), receipt.get("productLaunchIndex"), spec["argv"],
                                             str(api["ROOT"]), context["id"], spec["id"])
    require(receipt.get("productPid") == product["launch"]["pid"], "SWIFT_ACTUAL_PRODUCT_BIRTH_REQUIRED")
    return {"schema": 1, "scope": "CREATED_ORDINARY_SWIFT_AFTER_CURRENT_SHUTDOWN", "contextSha256": digest(run_raw),
            "canonicalId": spec["id"], "prelaunchSha256": digest(prelaunch_raw), "canonicalStartSha256": digest(start_raw),
            "canonicalReceiptSha256": digest(raw), "outerPhaseSha256": digest(encoded(phase)),
            "canonicalNative": native, "productNative": product, "device": before["device"]}


def retained_producer(owner, api, private, context, spec, end):
    state, retained = private.path / "state", private.path / "evidence/full-supplements"
    raw = read_path(owner, api, retained / "xcframework-producer.json", end)
    require(raw == read_path(owner, api, state / "host-xcframework-build.json", end) ==
            read_path(owner, api, state / "evidence" / spec["id"] / "receipt.json", end), "XCF_ORIGINAL_PRODUCER_CHANGED")
    value = api["parse"](raw)
    checker = load_helper(Path(__file__).parent / "check-audit-receipt.py", "full_xcf_receipt")
    checker.validate(value, 0, "xcframework-build", api["ROOT"], api["ROOT"] / "gradlew", spec["argv"])
    require(value.get("id") == spec["id"] and value.get("kind") == "gradle" and value.get("jobId") == context["id"] and
            value.get("gradleHome") == context["gradleHome"] and value.get("sourceBefore") == context["source"] and
            value.get("executedArgv") == [str(api["ROOT"] / "gradlew"), *api["audit"].gradle_arguments(spec["argv"])],
            "XCF_ORIGINAL_SELECTOR_CHANGED")
    manifest_raw = read_path(owner, api, state / "evidence/xcframework-sidecars.json", end)
    manifest, sidecars = api["parse"](manifest_raw), {}
    require(manifest.get("sourceInvocationId") == spec["id"] and type(manifest.get("files")) is list and
            len(manifest["files"]) == len(SIDECARS), "XCF_ORIGINAL_SIDECARS_REQUIRED")
    for row in manifest["files"]:
        require(row.get("path") in SIDECARS and row["path"] not in sidecars and row.get("result") == "RETAINED",
                "XCF_ORIGINAL_SIDECAR_ROSTER")
        original = read_path(owner, api, state / "evidence" / row["path"], end)
        require(digest(original) == row.get("sha256"), "XCF_ORIGINAL_SIDECAR_CHANGED")
        sidecars[row["path"]] = digest(original)
    return {"producerInvocationId": spec["id"], "producerReceiptSha256": digest(raw),
            "sidecarsManifestSha256": digest(manifest_raw), "sidecars": sidecars}


def verify_swift(owner, api, private, result, context, manifest, canonical_context, end):
    value = manifest["swift"]
    rows = {row["phase"]: row for row in result["phases"]}
    directory = private.path / "evidence/full-supplements"
    if value.get("status") == "NOT_REACHED":
        require(not any(label in rows for label in ("swift-ui", *SWIFT_RETIRE, SWIFT_INSPECT)) and
                not os.path.lexists(directory / "swift-prelaunch.json"), "SWIFT_UNREACHED_RELABELLED")
        return
    spec = next(row for row in manifest["intent"] if row["name"] == "swift-ui")
    selected = result["simulator"]["selected"]
    prelaunch_raw = read_path(owner, api, directory / "swift-prelaunch.json", end)
    row = rows.get(SWIFT_PRELAUNCH)
    require(row is not None and row["exitCode"] == 0 and row["retirement"] == "KNOWN" and row["errors"] == [],
            "SWIFT_PRELAUNCH_ORIGINAL_REQUIRED")
    def observation(label):
        row = rows[label]
        path = private.path / "evidence/commands" / label
        out, err = (read_path(owner, api, path / name, end) for name in ("stdout.log", "stderr.log"))
        return row, out, err
    device = simulator.terminal_device(observation(SWIFT_PRELAUNCH)[1], selected)
    producer = retained_producer(owner, api, private, canonical_context,
                                next(row for row in manifest["intent"] if row["name"] == "xcframework-build"), end)
    expected = {"schema": 1, "scope": "CURRENT_SHUTDOWN_BEFORE_ORDINARY_SWIFT", "contextSha256": result["contextSha256"],
                "canonicalContextSha256": digest(read_path(owner, api, private.path / "state/context.json", end)),
                "spec": spec, "device": device, "runtime": selected["runtime"], "producer": producer,
                "primaryRetirementSha256": digest(encoded(result["simulator"]["terminal"])),
                "original": simulator.phase_reference(*observation(SWIFT_PRELAUNCH))}
    require(device["state"] == "Shutdown" and api["parse"](prelaunch_raw) == expected and
            digest(prelaunch_raw) == value.get("prelaunchSha256"), "SWIFT_CURRENT_PRELAUNCH_CHANGED")
    if value.get("launchSha256") is not None:
        launch = swift_authority(owner, api, spec, rows.get("swift-ui", {}), prelaunch_raw, end, private=private)
        raw = read_path(owner, api, directory / "swift-launch.json", end)
        require(raw == encoded(launch) and digest(raw) == value["launchSha256"], "SWIFT_ORIGINAL_LAUNCH_CHANGED")
    else:
        require(value.get("shutdownAttempted") is False and value.get("status") != "KNOWN_SHUTDOWN",
                "SWIFT_SHUTDOWN_WITHOUT_ACTUAL_LAUNCH")
    references, devices = {}, {}
    for label in SWIFT_RETIRE:
        if label not in rows:
            continue
        row, out, err = observation(label)
        require(row["exitCode"] == 0 and row["retirement"] == "KNOWN" and row["errors"] == [],
                "SWIFT_RETIREMENT_ORIGINAL_FAILED")
        references[label] = simulator.phase_reference(row, out, err)
        if label != SWIFT_RETIRE[1]:
            devices[label] = simulator.terminal_device(out, selected)
    require(set(devices) == {SWIFT_RETIRE[0], SWIFT_RETIRE[2]} and value.get("phases") == references and
            value.get("before") == devices[SWIFT_RETIRE[0]] and value.get("after") == devices[SWIFT_RETIRE[2]] and
            value["after"]["state"] == "Shutdown" and type(value.get("shutdownAttempted")) is bool and
            value["shutdownAttempted"] == (SWIFT_RETIRE[1] in rows) == (value["before"]["state"] != "Shutdown"),
            "SWIFT_DISTINCT_RETIREMENT_CHANGED")
    bundles = value.get("bundles")
    require(type(bundles) is list and len(bundles) <= 4, "SWIFT_RAW_RESULTS_ROSTER")
    for index, bundle in enumerate(bundles):
        path = Path(bundle["path"])
        require(path.parent == private.path / "state/work/swift-ui/DerivedData/Logs/Test" and path.suffix == ".xcresult" and
                bundle.get("retained") == "swift-xcresult-" + str(index), "SWIFT_RAW_RESULT_PATH")
        raw = read_path(owner, api, directory / bundle["retained"] / "original-path-map.json", end)
        require(digest(raw) == bundle.get("mapSha256") and api["abi_copy_map"](raw, path)["files"], "SWIFT_RAW_RESULTS_CHANGED")
    if SWIFT_INSPECT in rows:
        input_raw = read_path(owner, api, directory / "swift-inspection-input.json", end)
        terminal_raw = read_path(owner, api, private.path / "state/evidence/swift-inspection-return.json", end)
        inspector = load_helper(Path(__file__).parent / "inspect-ordinary-swift-results.py", "full_swift_retirement")
        retirement = inspector.assess_return(private.path / "state/evidence/swift-inspection", api["parse"](terminal_raw),
            rows[SWIFT_INSPECT], context_sha=result["contextSha256"], input_sha=digest(input_raw), canonical_id=spec["id"],
            raw_limit=result["jobBudget"]["productiveCutoffRawNs"], reader=lambda path: read_path(owner, api, path, end),
            check=lambda: api["posix"]._deadline(end))
        require(value.get("inspectionReturnSha256") == digest(terminal_raw) and
                value.get("inspectionRetirement") == retirement["retirement"], "SWIFT_HELPER_ORIGINAL_RETURN_CHANGED")
    else:
        require(value.get("inspectionReturnSha256") is None and value.get("inspectionRetirement") == "NOT_REACHED",
                "SWIFT_UNREACHED_HELPER_RELABELLED")
    if value.get("cases") is not None:
        require(bundles and SWIFT_INSPECT in rows and rows[SWIFT_INSPECT]["exitCode"] == 0, "SWIFT_ACTUAL_CASES_REQUIRED")
        input_raw = read_path(owner, api, directory / "swift-inspection-input.json", end)
        require(api["parse"](input_raw) == {"schema": 1, "contextSha256": result["contextSha256"], "canonicalId": spec["id"],
                "bundles": [row["path"] for row in bundles]}, "SWIFT_INSPECTION_INPUT_CHANGED")
        raw = read_path(owner, api, private.path / "state/evidence/swift-case-results.json", end)
        cases = api["parse"](raw)
        require(digest(raw) == value.get("inspectionSha256") and cases.get("contextSha256") == result["contextSha256"] and
                cases.get("inputSha256") == digest(input_raw) and cases.get("canonicalId") == spec["id"], "SWIFT_CASE_RESULT_CHANGED")
        inspector = load_helper(Path(__file__).parent / "inspect-ordinary-swift-results.py", "full_retained_swift")
        assessed = inspector.assess_retained(private.path / "state/evidence/swift-inspection", cases,
            reader=lambda path: read_path(owner, api, path, end), check=lambda: api["posix"]._deadline(end))
        require(assessed == value["cases"] == cases.get("cases"), "SWIFT_CASE_ASSESSMENT_CHANGED")
    if "swift-ui" in manifest["completed"]:
        require(value.get("status") == "KNOWN_SHUTDOWN" and value.get("cases") is not None,
                "SWIFT_REQUIRED_ACCEPTANCE_INCOMPLETE")


def verify_central_screen(owner, api, private, value, end):
    """Original closed inventories, prepared authority and absence; no key reread.

    Exact hashes authorize only the original closed bytes already screened while
    key inputs existed. No new raw byte or arbitrary namespace is grandfathered.
    """
    require(value.get("status") == "SCREENED_AND_REMOVED", "CENTRAL_RAW_EXPORT_QUARANTINED")
    state, directory = private.path / "state", private.path / "evidence/full-supplements"
    raw = read_path(owner, api, directory / "central-screen.json", end)
    screen = api["parse"](raw)
    context_raw = read_path(owner, api, private.path / "run-context.json", end)
    context = api["parse"](context_raw)
    spec = next(row for row in validate_intent(context["fullSupplementIntent"], state) if row["name"] == "central-bundle")
    budget_raw = read_path(owner, api, private.path / "evidence/job-time/budget.json", end)
    budget = job_time.Budget(budget_raw)
    start, finish, limit = (screen.get(key) for key in ("startedRawNs", "finishedRawNs", "endRawNs"))
    require(digest(raw) == value.get("screenSha256") and screen.get("schema") == 1 and
            screen.get("scope") == "CLOSED_CENTRAL_ENCLOSING_STREAM_SCREEN" and
            screen.get("contextSha256") == digest(context_raw) and screen.get("canonicalId") == value.get("canonicalId") == spec["id"] and
            digest(budget_raw) == context["jobBudgetSha256"] and all(type(v) is int for v in (start, finish, limit)) and
            start <= finish < limit == min(start + 360 * job_time.NS, budget.fence("uninstall-read")) and
            value.get("startedRawNs") == start and value.get("finishedRawNs") == finish and value.get("endRawNs") == limit,
            "CENTRAL_SCREEN_BINDING_CHANGED")
    require(read_path(owner, api, state / "evidence/central-bundle/screen-result.json", end) == raw,
            "CENTRAL_CANONICAL_SCREEN_CHANGED")
    helper_end = min(start + 285 * job_time.NS, budget.fence("uninstall"), limit - 75 * job_time.NS)
    metadata = state / "evidence/central-bundle"
    prepared_raw = read_path(owner, api, metadata / "retirement-prepared.json", end)
    prepared = api["parse"](prepared_raw)
    result_raw = read_path(owner, api, metadata / "result.json", end)
    result = api["parse"](result_raw)
    require(digest(prepared_raw) == screen.get("preparedSha256") and prepared.get("deadlineRawNs") == helper_end == value.get("helperEndRawNs") and
            prepared.get("outerId") == spec["id"] and prepared.get("resultSha256") == digest(result_raw) and
            result.get("outerId") == spec["id"] and result.get("retentionStatus") == "RETAINED" and result.get("errors") == [],
            "CENTRAL_PREPARED_AUTHORITY_CHANGED")
    for label, key in (("central-bundle", "canonicalPhaseSha256"), (CENTRAL_RETIRE, "helperPhaseSha256")):
        phase_raw = read_path(owner, api, private.path / "evidence/commands" / label / "result.json", end)
        phase = api["parse"](phase_raw)
        require(digest(phase_raw) == screen.get(key) and phase.get("retirement") == "KNOWN" and phase.get("errors") == [],
                "CENTRAL_ORIGINAL_RETURN_CHANGED")
        require((phase["finalizedRawNs"] <= start if label == "central-bundle" else
                 start <= phase["startedRawNs"] <= phase["finalizedRawNs"] <= finish and
                 phase.get("completedRawNs") is not None and phase["completedRawNs"] < helper_end),
                "CENTRAL_ORIGINAL_TRANSACTION_SEQUENCE_CHANGED")
    outer_raw = read_path(owner, api, state / "evidence" / spec["id"] / "receipt.json", end)
    removal = screen.get("removal")
    require(type(removal) is dict and removal == {"schema": 1, "workRemoved": True, "gpgHomesRemoved": True,
            "preparedSha256": digest(prepared_raw), "outerReceiptSha256": digest(outer_raw),
            "productExitCode": result["productExitCode"], "productPassed": result["finalExitCode"] == 0} and
            prepared.get("outerReceiptSha256") == digest(outer_raw) and not os.path.lexists(state / "work/central-bundle"),
            "CENTRAL_ORIGINAL_REMOVAL_CHANGED")
    homes = []
    for role in ("signer", "verifier"):
        if role in result["gpgStopExitCodes"]:
            record = api["parse"](read_path(owner, api, metadata / (role + "-home.json"), end))
            path = Path(record["path"])
            require(record.get("outerId") == spec["id"] and record.get("role") == role and path.is_absolute() and
                    path.name.startswith("p2pkit-gpg.") and not os.path.lexists(path) and result["gpgStopExitCodes"][role] == 0,
                    "CENTRAL_ORIGINAL_HOME_NOT_REMOVED")
            homes.append({"path": str(path), "identity": record["identity"]})
    require(homes == prepared.get("homes"), "CENTRAL_ORIGINAL_HOME_ROSTER_CHANGED")
    files = screen.get("files")
    require(type(files) is dict and set(files) == {"canonical", "controller"}, "CENTRAL_CLOSED_INVENTORY_REQUIRED")
    for label, path in (("canonical", state / "evidence"), ("controller", private.path / "evidence")):
        actual = inventory(owner, api, path, end, after_screen=label == "controller", canonical_screen=label == "canonical")
        require(actual == files[label], "CENTRAL_SCREENED_BYTES_CHANGED")
    return screen


def verify_phase_role(owner, api, private, row, result, context, end):
    """Independent closed selector/domain validation, not a caller PASS flag."""
    state, label = private.path / "state", row["phase"]
    specs = {entry["name"]: entry for entry in validate_intent(context["fullSupplementIntent"], state)}
    canonical_context = None
    if label == "product" or label in NAMES or label in (SWIFT_INSPECT, CENTRAL_RETIRE):
        canonical_context = api["parse"](read_path(owner, api, state / "context.json", end))
        require(row["job"] == canonical_context["id"] and row["state"] == str(state) and
                row["home"] == canonical_context["gradleHome"], "SUPPLEMENT_PHASE_CANONICAL_DOMAIN_CHANGED")
    else:
        require(row["job"] == context["job"] and row["state"] == context["session"] and
                row["home"] == context["session"] + "/control-home", "PHASE_CONTROLLER_DOMAIN_CHANGED")
    require(type(row.get("supplementPhase")) is bool and row["supplementPhase"] == (label in NAMES) and
            type(row.get("postReturnHelper")) is bool and row["postReturnHelper"] == (label in (SWIFT_INSPECT, CENTRAL_RETIRE)),
            "SUPPLEMENT_PHASE_ROLE_CHANGED")
    if label in NAMES:
        require(row.get("canonicalInvocation") == specs[label]["id"] and
                row["argv"] == canonical_argv(api, context, specs[label], state), "SUPPLEMENT_PHASE_SELECTOR_CHANGED")
    elif label == "product":
        request = api["parse"](read_path(owner, api, private.path / "evidence/custody/request.json", end))
        require(row.get("canonicalInvocation") == request["owner"]["productInvocation"], "SUPPLEMENT_PRIMARY_ID_CHANGED")
    else:
        require(row.get("canonicalInvocation") is None, "SUPPLEMENT_HELPER_IS_NOT_CANONICAL")
    expected_environment = environment(label, state, result["simulator"]["selected"]) if label in NAMES or row["postReturnHelper"] else None
    require(row.get("supplementEnvironment") == expected_environment, "SUPPLEMENT_ENVIRONMENT_CHANGED")
    if label == SWIFT_PRELAUNCH or label in SWIFT_RETIRE:
        original = simulator.PRELAUNCH if label == SWIFT_PRELAUNCH else simulator.RETIRE[SWIFT_RETIRE.index(label)]
        require(row["argv"] == simulator.command(original, result["simulator"]["selected"]), "SWIFT_SIMULATOR_SELECTOR_CHANGED")
    if row["postReturnHelper"]:
        prefix = [context["python"], "-I", "-B", "-S"]
        if label == SWIFT_INSPECT:
            raw = read_path(owner, api, private.path / "evidence/full-supplements/swift-inspection-input.json", end)
            expected = [*prefix, str(api["SCRIPTS"] / "inspect-ordinary-swift-results.py"), "--session", str(private.path),
                        "--input-sha256", digest(raw)]
        else:
            limit = result["fullSupplements"]["central"]["helperEndRawNs"]
            expected = [*prefix, str(api["SCRIPTS"] / "prepare-audit-central-bundle-metadata.py"), "prepare-retire",
                        "--outer-receipt", str(state / "evidence" / specs["central-bundle"]["id"] / "receipt.json"),
                        "--deadline-raw-ns", str(limit)]
        require(row["argv"] == expected, "SUPPLEMENT_HELPER_SELECTOR_CHANGED")
    if label in (SWIFT_PRELAUNCH, *SWIFT_RETIRE, SWIFT_INSPECT, CENTRAL_RETIRE):
        seconds = 285 if label == CENTRAL_RETIRE else 120
        raw_end = row["startedRawNs"] + seconds * job_time.NS
        if label == CENTRAL_RETIRE:
            raw_end = min(raw_end, result["fullSupplements"]["central"]["helperEndRawNs"])
        require(row["finalizedRawNs"] < raw_end + api["FINAL_SECONDS"] * job_time.NS and
                (row["completedRawNs"] is None or row["completedRawNs"] < raw_end), "SUPPLEMENT_HELPER_BOUND_CHANGED")
    return canonical_context


def retained_maps(owner, api, private, manifest, end):
    """Retained artifacts are actual copied bytes, never a map's self-assertion."""
    directory = private.path / "evidence/full-supplements"
    allowed = {"lock-policy-work", "consumer-receipts", "consumer-framework", "publication-metadata", "xcframework-producer.json",
               "sbom.json", "sbom.xml", *["dokka-" + module for module in MODULES],
               *["swift-xcresult-" + str(i) for i in range(4)]}
    require(type(manifest.get("retained")) is dict and set(manifest["retained"]) <= allowed, "SUPPLEMENT_RETAINED_ROSTER")
    roots = None
    if manifest["retained"]:
        roots = api["parse"](read_path(owner, api, directory / "prewriter-roots.json", end))
        require(roots.get("schema") == 1 and roots.get("contextSha256") == manifest["contextSha256"] and
                type(roots.get("roots")) is dict, "SUPPLEMENT_PREWRITER_ROOTS_CHANGED")
    maps = {}
    for name, value in manifest["retained"].items():
        path = directory / name
        if "mapSha256" in value:
            raw = read_path(owner, api, path / "original-path-map.json", end)
            require(digest(raw) == value["mapSha256"], "SUPPLEMENT_RETAINED_MAP_CHANGED")
            mapping = api["abi_copy_map"](raw, Path(value["source"]))
            actual = inventory(owner, api, path, end)
            expected = sorted([{"path": row["member"], "bytes": row["size"], "sha256": row["sha256"]}
                               for row in mapping["files"]] + [{"path": "original-path-map.json", "bytes": len(raw), "sha256": digest(raw)}],
                              key=lambda row: row["path"])
            require(actual == expected, "SUPPLEMENT_RETAINED_BYTES_CHANGED")
            maps[name] = mapping
        elif "sha256" in value:
            raw = read_path(owner, api, path, end)
            require(len(raw) == value.get("bytes") and digest(raw) == value["sha256"], "SUPPLEMENT_RETAINED_BYTES_CHANGED")
        else:
            require(name == "publication-metadata", "SUPPLEMENT_RETAINED_ROLE_CHANGED")
            raw = read_path(owner, api, path / "manifest.json", end)
            require(digest(raw) == value.get("manifestSha256"), "PUBLICATION_RETAINED_MANIFEST_CHANGED")
            metadata = api["parse"](raw)
            require(metadata.get("source") == str(private.path / "state/work/consumer/repository") and
                    type(metadata.get("artifacts")) is list and metadata["artifacts"] and type(metadata.get("files")) is list,
                    "PUBLICATION_RETAINED_ROSTER_CHANGED")
            for row in metadata["files"]:
                require(re.fullmatch(r"metadata-[0-9]{5}\.bin", row.get("member", "")) and
                        {key: row[key] for key in ("path", "bytes", "sha256")} in metadata["artifacts"] and
                        Path(row["path"]).suffix in (".pom", ".module", ".xml"), "PUBLICATION_METADATA_ROLE_CHANGED")
                original = read_path(owner, api, path / row["member"], end)
                require(len(original) == row["bytes"] and digest(original) == row["sha256"], "PUBLICATION_METADATA_BYTES_CHANGED")
            require({row["path"] for row in metadata["files"]} == {row["path"] for row in metadata["artifacts"]
                    if Path(row["path"]).suffix in (".pom", ".module", ".xml")}, "PUBLICATION_METADATA_MISSING")
            maps[name] = metadata
        if name != "publication-metadata":
            guard = value.get("prewriter")
            source = Path(value["source"])
            allowed_roots = [api["ROOT"] / "build", *[api["ROOT"] / "library" / module / "build" for module in MODULES],
                             private.path / "state", private.path / "state/work"]
            require(type(guard) is dict and set(guard) == {"path", "identity"} and Path(guard["path"]) in allowed_roots and
                    (Path(guard["path"]) == source or Path(guard["path"]) in source.parents) and
                    type(guard["identity"]) is list and len(guard["identity"]) == 2 and
                    all(type(part) is int and part >= 0 for part in guard["identity"]) and
                    roots["roots"].get(guard["path"]) == guard["identity"], "SUPPLEMENT_PREWRITER_BINDING_CHANGED")
    return maps


def verify_artifacts(owner, api, private, manifest, canonical_context, end):
    maps = retained_maps(owner, api, private, manifest, end)
    directory, state = private.path / "evidence/full-supplements", private.path / "state"
    def copied(role, name):
        rows = [row for row in maps[role]["files"] if row["original"] == name]
        require(len(rows) == 1, "SUPPLEMENT_COPIED_ORIGINAL_MISSING")
        return read_path(owner, api, directory / role / rows[0]["member"], end)
    by_scope = {row["scope"]: row for row in manifest["scopes"]}
    if "lock-policy" in manifest["completed"]:
        require("lock-policy-work" in maps and copied("lock-policy-work", "locks-before.txt") ==
                copied("lock-policy-work", "locks-after.txt"), "LOCK_POLICY_ORIGINAL_LOCKS_CHANGED")
        work = Path(maps["lock-policy-work"]["originalRoot"])
        require(work.parent == state / "work" and work.name.startswith("lock-policy."), "LOCK_POLICY_ORIGINAL_WORK_CHANGED")
        value = api["parse"](copied("lock-policy-work", "ownership.json"))
        require(value.get("workDirectory") == str(work) and value.get("stateDirectory") == str(state) and
                value.get("jobId") == canonical_context["id"] and value.get("contextSha256") ==
                digest(read_path(owner, api, state / "context.json", end)), "LOCK_POLICY_ORIGINAL_OWNERSHIP_CHANGED")
        args = {"abbreviated": ["rALl", "--dry-run"], "indirect": ["indirectLockRefresh", "--dry-run", "--init-script",
                str(work / "indirect.init.gradle.kts")], "ordinary-write": ["help", "--write-locks", "--dry-run"],
                "configure-on-demand-write": ["rALl", "--write-locks", "--dry-run", "--configure-on-demand"],
                "authorized": ["rALl", "--write-locks", "--dry-run"]}
        for row in by_scope["lock-policy"]["canonical"]["descendants"]:
            label = row["purpose"].removeprefix("lock-policy-")
            raw = copied("lock-policy-work", label + ".log.receipt.json")
            require(digest(raw) == row["receiptSha256"] and row["requestedArgv"] ==
                    [*args[label], "--no-daemon", "--max-workers=2", "--console=plain"], "LOCK_POLICY_ORIGINAL_SELECTOR_CHANGED")
    if "dokka-sbom" in manifest["completed"]:
        for module in MODULES:
            role = "dokka-" + module
            require(role in maps and maps[role]["originalRoot"] == str(api["ROOT"] / "library" / module / "build/dokka/html") and
                    any(row["original"].endswith(".html") and row["size"] for row in maps[role]["files"]), "DOKKA_RETAINED_HTML_MISSING")
        require({"sbom.json", "sbom.xml"} <= set(manifest["retained"]), "SBOM_RETAINED_PAIR_MISSING")
    if "published-consumers" in manifest["completed"]:
        require({"consumer-receipts", "publication-metadata", "consumer-framework"} <= set(maps), "CONSUMER_ACTUAL_OUTPUTS_MISSING")
        raw = copied("consumer-receipts", "consumer-admission.json")
        admission = api["parse"](raw)
        require(admission.get("source") == canonical_context["source"] and admission.get("contextId") == canonical_context["id"] and
                admission.get("workDir") == str(state / "work/consumer") and admission.get("repository") == str(state / "work/consumer/repository") and
                admission.get("repositoryInitiallyAbsent") is True, "CONSUMER_ADMISSION_CHANGED")
        publication_raw = copied("consumer-receipts", "consumer-publication-manifest.json")
        publication = api["parse"](publication_raw)
        verification = api["parse"](copied("consumer-receipts", "consumer-metadata-verification.json"))
        leaves = {row["purpose"]: row for row in by_scope["published-consumers"]["canonical"]["descendants"]}
        require(publication.get("source") == canonical_context["source"] and publication.get("admissionSha256") == digest(raw) and
                publication.get("publicationId") == leaves["consumer-publish"]["id"] and
                publication.get("publicationReceiptSha256") == leaves["consumer-publish"]["receiptSha256"] and
                verification.get("source") == canonical_context["source"] and verification.get("result") == "PASS" and
                verification.get("publicationManifestSha256") == digest(publication_raw) and
                verification.get("consumerBuildId") == leaves["consumer-build"]["id"] and
                verification.get("consumerBuildReceiptSha256") == leaves["consumer-build"]["receiptSha256"] and
                publication.get("publicationCount") == verification.get("publicationCount") == 15,
                "CONSUMER_ORIGINAL_VERIFICATION_CHANGED")
        artifacts = maps["publication-metadata"]["artifacts"]
        require(publication.get("repositoryFiles") == {row["path"]: {key: row[key] for key in ("sha256", "bytes")} for row in artifacts},
                "CONSUMER_PUBLICATION_BYTES_CHANGED")
        framework = maps["consumer-framework"]
        require(framework["originalRoot"] == str(state / "work/consumer/consumer/kmpConsumer/build/bin/iosSimulatorArm64/debugFramework/P2pKitConsumer.framework") and
                any(row["original"] == "P2pKitConsumer" and row["size"] > 0 for row in framework["files"]), "CONSUMER_NATIVE_FRAMEWORK_MISSING")
    if "xcframework-build" in manifest["completed"]:
        retained_producer(owner, api, private, canonical_context,
                         next(row for row in manifest["intent"] if row["name"] == "xcframework-build"), end)


def verify(owner, api, private, result, context, end):
    """Independent original B2 predicates, also for safely retained failed scope."""
    state, path = private.path / "state", private.path / "evidence/full-supplements"
    intent = validate_intent(context.get("fullSupplementIntent"), state)
    value = result.get("fullSupplements")
    require(type(value) is dict and value.get("contextSha256") == result["contextSha256"] and
            value.get("state") == str(state) and value.get("intent") == intent, "SUPPLEMENT_RESULT_CONTEXT_CHANGED")
    if value.get("manifestSha256") is None:
        require(value.get("status") == "HOLD" and value.get("completed") == [] and value.get("scopes") == [] and
                not os.path.lexists(path), "SUPPLEMENT_UNATTEMPTED_RELABELLED")
        return
    raw = read_path(owner, api, path / "manifest.json", end)
    manifest = api["parse"](raw)
    require(raw == encoded(manifest) and digest(raw) == value["manifestSha256"] and manifest.get("schema") == 1 and
            manifest.get("scope") == "ORDINARY_FULL_SUPPLEMENT_ORIGINALS" and
            all(manifest.get(key) == value.get(key) for key in ("contextSha256", "intent", "completed", "pending", "scopes", "swift", "central")),
            "SUPPLEMENT_MANIFEST_CHANGED")
    files = inventory(owner, api, path, end)
    require([row for row in files if row["path"] != "manifest.json"] == manifest.get("files"), "SUPPLEMENT_ORIGINAL_FILES_CHANGED")
    scopes, complete = manifest["scopes"], manifest["completed"]
    require(type(scopes) is list and len(scopes) <= len(intent) and type(complete) is list and
            complete == list(NAMES[:len(complete)]) and len(scopes) in (len(complete), len(complete) + 1) and
            [row["scope"] for row in scopes] == list(NAMES[:len(scopes)]) and
            manifest["pending"] == (None if len(scopes) == len(complete) else scopes[-1]["scope"]), "SUPPLEMENT_SCOPE_SEQUENCE_CHANGED")
    require(value["status"] == ("PASS" if complete == list(NAMES) and manifest["pending"] is None else "HOLD"),
            "SUPPLEMENT_FAILED_SCOPE_RELABELLED")
    canonical_context = api["parse"](read_path(owner, api, state / "context.json", end))
    rows = {row["phase"]: row for row in result["phases"]}
    require(set(rows) & set(NAMES) <= {row["scope"] for row in scopes}, "SUPPLEMENT_UNRESERVED_PHASE")
    require(not scopes or result.get("primaryAbi", {}).get("status") == "PASS", "SUPPLEMENT_PRIMARY_ABI_REQUIRED")
    for spec, row in zip(intent, scopes):
        phase = rows.get(spec["name"])
        require(row.get("canonicalId") == spec["id"] and row.get("phaseSha256") == result["phaseSha256"].get(spec["name"]) and
                row.get("status") == ("PASS" if spec["name"] in complete else "HOLD"), "SUPPLEMENT_ORIGINAL_PHASE_BINDING_CHANGED")
        if row.get("canonical") is not None:
            require(phase is not None and row["canonical"] == canonical(owner, api, state, canonical_context, spec, phase, end),
                    "SUPPLEMENT_CANONICAL_ORIGINAL_CHANGED")
        if row["status"] == "PASS":
            require(phase is not None and phase["exitCode"] == 0 and phase["errors"] == [] and phase["retirement"] == "KNOWN" and
                    row["canonical"] is not None, "SUPPLEMENT_CANONICAL_REQUIRED")
            if spec["name"] in ("lock-policy", "android-abi-graph", "published-consumers"):
                validate_nested(row["canonical"], spec["name"], state)
        require(type(row.get("retained")) is dict and all(manifest["retained"].get(key) == entry for key, entry in row["retained"].items()),
                "SUPPLEMENT_SCOPE_ARTIFACT_CHANGED")
    retained = {key: entry for row in scopes for key, entry in row["retained"].items()}
    require(retained == manifest["retained"] and sum(len(row["retained"]) for row in scopes) == len(retained),
            "SUPPLEMENT_UNOWNED_OR_REUSED_ARTIFACT")
    for phase in result["phases"]:
        if phase["phase"] in STAGES:
            verify_phase_role(owner, api, private, phase, result, context, end)
    if scopes:
        verify_abi_accounting(result.get("primaryAbiAccounting"), result, context)
    verify_artifacts(owner, api, private, manifest, canonical_context, end)
    verify_swift(owner, api, private, result, context, manifest, canonical_context, end)
    if manifest["central"].get("status") == "NOT_REACHED":
        require("central-bundle" not in rows and not os.path.lexists(state / "work/central-bundle") and
                not os.path.lexists(state / "evidence/central-bundle"), "CENTRAL_UNREACHED_NAMESPACE_CHANGED")
    else:
        verify_central_screen(owner, api, private, manifest["central"], end)
    require(inventory(owner, api, path, end) == files, "SUPPLEMENT_ORIGINAL_FILES_CHANGED")


def verify_cancellation(owner, api, private, result, context, end, budget):
    """One actual active canonical ID; pending returned work is not a target."""
    timing = result["jobBudget"]
    cancellation = timing.get("cooperativeCancellation")
    rows = [row for row in result["phases"] if row.get("cooperativeCancellation") is not None]
    if cancellation is None:
        require(not rows, "SEALED_CANCELLATION_CHANGED")
        return
    require(len(rows) == 1 and rows[0]["cooperativeCancellation"] == cancellation and
            rows[0]["phase"] in ("product", *NAMES) and rows[0]["launchAttempted"] is True and
            type(cancellation) is dict and set(cancellation) == {"reason", "job", "invocation", "attemptedRawNs",
              "returnedRawNs", "requested", "requestSha256"} and
            cancellation.get("invocation") == rows[0].get("canonicalInvocation") and
            cancellation.get("job") == rows[0]["job"] and
            cancellation.get("reason") in ("job-budget", "signal") and type(cancellation.get("requested")) is bool,
            "SEALED_CANCELLATION_CHANGED")
    row = rows[0]
    # A reservation or failed spawn cannot create cooperative cancellation
    # authority. Recheck the actual native birth independently at sealing.
    simulator.created_native_launch(row.get("ownership"), 0, row["argv"], str(api["ROOT"]), row["job"], row["invocation"])
    attempted = cancellation["attemptedRawNs"]
    require(type(attempted) is int and row["startedRawNs"] <= attempted <= row["finalizedRawNs"],
            "SEALED_CANCELLATION_CHANGED")
    if cancellation["reason"] == "job-budget":
        require(timing["exhausted"] and attempted >= budget.fence("productive"), "SEALED_CANCELLATION_CHANGED")
    else:
        require(result["cancelled"] is True, "SEALED_CANCELLATION_CHANGED")
    after = result["phases"][result["phases"].index(row) + 1:]
    require(not any(item["phase"] in ("product", *PRODUCTIVE) for item in after), "CANCELLED_SCOPE_FOLLOWED_BY_PRODUCT")
    if cancellation["requested"]:
        require(type(cancellation["returnedRawNs"]) is int and attempted <= cancellation["returnedRawNs"] <= row["finalizedRawNs"],
                "SEALED_CANCELLATION_CHANGED")
        raw = read_path(owner, api, private.path / "evidence/job-time/product-cancellation.json", end)
        require(raw == read_path(owner, api, private.path / "state/cancellations" / (cancellation["invocation"] + ".json"), end) and
                digest(raw) == cancellation["requestSha256"], "SEALED_CANCELLATION_ORIGINAL_CHANGED")
        value = api["parse"](raw)
        require(value.get("schema") == 1 and value.get("jobId") == cancellation["job"] and
                value.get("id") == cancellation["invocation"], "SEALED_CANCELLATION_CHANGED")
    else:
        require(cancellation["returnedRawNs"] is None and cancellation["requestSha256"] is None,
                "SEALED_FAILED_CANCELLATION_RELABELLED")


def frozen_packet(owner, api, private, frozen, outer, end):
    """B2 originals through both flat maps and the ACTUAL exported member bytes.

    Neither map's self-consistency certifies content. All reached canonical
    originals (including failed/stop/late helper streams), closed supplemental
    commands and retained artifact copies must equal their independently read
    originals. No original build output is reacquired after a later writer.
    This predicate is called before/after the original exporter and at seal.
    """
    context_raw = read_path(owner, api, private.path / "run-context.json", end)
    context = api["parse"](context_raw)
    before_raw = read_path(owner, api, private.path / "evidence/profile-result-before-export.json", end)
    before = api["parse"](before_raw)
    require(before.get("contextSha256") == digest(context_raw) and before.get("profile") == "full" and
            before.get("encrypted") is False and before.get("exportReturn") is None, "SUPPLEMENT_FROZEN_CONTEXT_CHANGED")
    verify(owner, api, private, before, context, end)
    frozen_files = inventory(owner, api, frozen.path, end)
    actual = {row["path"]: row for row in frozen_files}
    require(set(actual) == {"original-path-map.json", *[row["member"] for row in outer.values()]},
            "SUPPLEMENT_FROZEN_MEMBER_ROSTER_CHANGED")
    originals = []
    def match(source, copy_name, *, inner=None):
        row = outer.get(copy_name)
        require(row is not None and (row["size"], row["sha256"]) == (source["bytes"], source["sha256"]),
                "SUPPLEMENT_FROZEN_ORIGINAL_DIFFERS")
        if inner is not None:
            require((inner["size"], inner["sha256"]) == (source["bytes"], source["sha256"]),
                    "SUPPLEMENT_FROZEN_INNER_MAP_DIFFERS")
        retained = actual[row["member"]]
        require((retained["bytes"], retained["sha256"]) == (source["bytes"], source["sha256"]),
                "SUPPLEMENT_FROZEN_BYTES_CHANGED")
        originals.append({"original": source["path"], "copy": copy_name, "member": row["member"],
                          "bytes": source["bytes"], "sha256": source["sha256"]})
    controller_files = inventory(owner, api, private.path / "evidence", end, after_screen=True)
    def direct(name):
        return name.startswith("full-supplements/") or any(name.startswith("commands/" + label + "/") for label in ORDER)
    # post_screen filtering deliberately omits these newly written, independently
    # bound records. Add them here by their closed literal roles, never caller paths.
    direct_files = [row for row in controller_files if direct(row["path"])]
    for name in ("profile-result-before-export.json", "full-supplements/manifest.json", "full-supplements/central-screen.json"):
        path = private.path / "evidence" / name
        if os.path.lexists(path):
            raw = read_path(owner, api, path, end)
            direct_files.append({"path": name, "bytes": len(raw), "sha256": digest(raw)})
    require({name for name in outer if direct(name) or name == "profile-result-before-export.json"} ==
            {row["path"] for row in direct_files}, "SUPPLEMENT_FROZEN_DIRECT_ROSTER_CHANGED")
    for row in sorted(direct_files, key=lambda value: value["path"]):
        match(row, row["path"])
    canonical_map_hash = None
    if "canonical-audit/original-path-map.json" in outer:
        map_path = private.path / "evidence/canonical-audit/original-path-map.json"
        map_raw = read_path(owner, api, map_path, end)
        mapping = api["abi_copy_map"](map_raw, private.path / "state/evidence")
        canonical_map_hash = digest(map_raw)
        match({"path": "canonical-audit/original-path-map.json", "bytes": len(map_raw), "sha256": canonical_map_hash},
              "canonical-audit/original-path-map.json")
        canonical_files = inventory(owner, api, private.path / "state/evidence", end)
        inner = {row["original"]: row for row in mapping["files"]}
        require(set(inner) == {row["path"] for row in canonical_files}, "SUPPLEMENT_FROZEN_CANONICAL_ROSTER_CHANGED")
        for row in canonical_files:
            copied = inner[row["path"]]
            match(row, "canonical-audit/" + copied["member"], inner=copied)
        canonical_raw = read_path(owner, api, private.path / "state/context.json", end)
        match({"path": "state/context.json", "bytes": len(canonical_raw), "sha256": digest(canonical_raw)}, "canonical-context.json")
        require(read_path(owner, api, map_path, end) == map_raw and
                inventory(owner, api, private.path / "state/evidence", end) == canonical_files,
                "SUPPLEMENT_CANONICAL_ORIGINAL_CHANGED")
    else:
        require(before["fullSupplements"]["manifestSha256"] is None and
                not any(name.startswith("canonical-audit/") for name in outer), "SUPPLEMENT_FROZEN_CANONICAL_COPY_MISSING")
    require(inventory(owner, api, private.path / "evidence", end, after_screen=True) == controller_files and
            inventory(owner, api, frozen.path, end) == frozen_files, "SUPPLEMENT_POST_COPY_ORIGINAL_CHANGED")
    for row in direct_files:
        if post_screen_addition(row["path"]):
            raw = read_path(owner, api, private.path / "evidence" / row["path"], end)
            require(len(raw) == row["bytes"] and digest(raw) == row["sha256"], "SUPPLEMENT_POST_COPY_ORIGINAL_CHANGED")
    require(read_path(owner, api, private.path / "run-context.json", end) == context_raw and
            read_path(owner, api, private.path / "evidence/profile-result-before-export.json", end) == before_raw,
            "SUPPLEMENT_POST_COPY_CONTEXT_CHANGED")
    return {"contextSha256": digest(context_raw), "profileBeforeExportSha256": digest(before_raw),
            "manifestSha256": before["fullSupplements"]["manifestSha256"], "canonicalMapSha256": canonical_map_hash,
            "originals": originals}
