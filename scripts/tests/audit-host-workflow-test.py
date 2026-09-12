#!/usr/bin/env python3
"""Exercise the maintained workflow's actual inline allocation/handoff bodies.

These are synthetic evidence and orchestration-policy fixtures, not GitHub-hosted
execution, native link/reparse validation, product tests, or device acceptance.
The Git/process/descriptor boundaries are controlled; hashes, copies, manifests,
and the extracted Python bodies are real. Smaller MAX_* values exercise the same
salvage code without allocating production-sized evidence. No Gradle is launched.
"""

import ast
import contextlib
import copy
import hashlib
import io
import itertools
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import tempfile
import types
import unittest
from unittest import mock


sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github/workflows/audit-host-validation.yml"
TEXT = WORKFLOW.read_text(encoding="utf-8")
REF = "refs/heads/audit/complete-2026-09-04"
COMMIT = "1" * 40
TREE = "2" * 40
JOB_ID = "3" * 32
CONTROL_ID = "4" * 32
PRODUCT_ID = "5" * 32
NESTED_ID = "6" * 32
EMPTY_HASH = hashlib.sha256(b"").hexdigest()
GIT_ENVIRONMENT = ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_OBJECT_DIRECTORY",
                   "GIT_ALTERNATE_OBJECT_DIRECTORIES", "GIT_EXTERNAL_DIFF")


def anchored_step(name):
    """Strict extraction for this workflow's plain-anchor, native-Python shape.

    This is not a replacement for a complete GitHub Actions YAML validator.
    Shape changes deliberately fail rather than silently testing old copied code.
    """
    lines = TEXT.splitlines()
    indices = [index for index, line in enumerate(lines) if line == "      - &" + name]
    if len(indices) != 1:
        raise AssertionError("Expected one canonical workflow step: " + name)
    start = indices[0]
    end = start + 1
    while end < len(lines) and (not lines[end].strip() or lines[end].startswith("        ")):
        end += 1
    return "\n".join(lines[start:end]) + "\n"


def job_block(name):
    lines = TEXT.splitlines()
    indices = [index for index, line in enumerate(lines) if line == "  " + name + ":"]
    if len(indices) != 1:
        raise AssertionError("Expected one host job: " + name)
    start = indices[0]
    end = start + 1
    while end < len(lines) and (not lines[end].strip() or lines[end].startswith("    ")):
        end += 1
    return "\n".join(lines[start:end]) + "\n"


def yaml_value(block, name, indent):
    """Read an exact scalar/literal/folded field in the maintained plain shape."""
    lines = block.splitlines()
    prefix = " " * indent + name + ":"
    indices = [index for index, line in enumerate(lines) if line.startswith(prefix)]
    if len(indices) != 1:
        raise AssertionError("Expected one field: " + prefix)
    index = indices[0]
    value = lines[index][len(prefix):].strip()
    if value not in ("|", ">-"):
        return value
    continued = []
    for line in lines[index + 1:]:
        if line.strip() and len(line) - len(line.lstrip()) <= indent:
            break
        continued.append(line[indent + 2:] if line.strip() else "")
    separator = " " if value == ">-" else "\n"
    return separator.join(continued).strip()


def python_body(name):
    if name == "run_host":
        lines = TEXT.splitlines()
        marker = "        run: &run_host |"
    else:
        lines = anchored_step(name).splitlines()
        marker = "        run: |"
    indices = [index for index, line in enumerate(lines) if line == marker]
    if len(indices) != 1:
        raise AssertionError("Expected one native Python literal: " + name)
    result = []
    for line in lines[indices[0] + 1:]:
        if line.strip() and not line.startswith("          "):
            break
        result.append(line[10:] if line.strip() else "")
    body = "\n".join(result).rstrip() + "\n"
    if not body.strip() or "${{" in body:
        raise AssertionError("Empty/interpolated Python literal: " + name)
    return body


HANDOFF_BODY = python_body("handoff")
HANDOFF_AST = ast.parse(HANDOFF_BODY, filename=str(WORKFLOW) + ":handoff")
MAIN_INDEX = next(index for index, node in enumerate(HANDOFF_AST.body) if isinstance(node, ast.Try))
if not any(isinstance(node, ast.FunctionDef) and node.name == "salvage_text"
           for node in HANDOFF_AST.body[:MAIN_INDEX]):
    raise AssertionError("Handoff no longer defines actual salvage before bootstrap admission")
HANDOFF_SETUP = compile(ast.Module(body=HANDOFF_AST.body[:MAIN_INDEX], type_ignores=[]),
                        str(WORKFLOW) + ":handoff", "exec")
HANDOFF_MAIN = compile(ast.Module(body=HANDOFF_AST.body[MAIN_INDEX:], type_ignores=[]),
                       str(WORKFLOW) + ":handoff", "exec")


def json_bytes(value):
    return (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n").encode("utf-8")


def put(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data if isinstance(data, bytes) else json_bytes(data))


def json_file(path):
    return json.loads(path.read_text(encoding="utf-8"))


def outputs(path):
    if not path.exists():
        return {}
    result = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        key, separator, value = line.partition("=")
        if not separator or key in result:
            raise AssertionError("Invalid/duplicate synthetic GitHub output: " + line)
        result[key] = value
    return result


def temporary(test):
    parent = Path(tempfile.gettempdir()).resolve(strict=True)
    if parent == ROOT or ROOT in parent.parents:
        test.fail("Synthetic evidence must be external to the source checkout")
    owned = tempfile.TemporaryDirectory(prefix="p2pkit-workflow-fixture-", dir=parent)
    test.addCleanup(owned.cleanup)
    return Path(owned.name)


class Fixture:
    def __init__(self, test, role="windows-x64", controls=True, logs=True, scope=None):
        self.test = test
        self.work = temporary(test)
        self.root = self.work / "checkout with spaces Ω"
        self.root.mkdir()
        put(self.root / "untouched-source.txt", b"synthetic source; never an owned output\n")
        self.parent = self.work / ("p2pkit-audit-" + role + "-synthetic")
        self.bootstrap = self.parent / "bootstrap-evidence"
        self.bootstrap.mkdir(parents=True)
        self.state = self.parent / "state"
        self.evidence = self.state / "evidence"
        self.evidence.mkdir(parents=True)
        self.role = role
        self.scope = scope or ("windows-diagnostics" if role == "windows-x64" else "full")
        self.current = {"commit": COMMIT, "tree": TREE, "status": "", "diffSha256": EMPTY_HASH}
        self.git_current = copy.deepcopy(self.current)
        self.git_diff = b""
        self.git_errors = {}
        self.git_calls = []
        self.invocations = 0
        self.environment = {
            "GITHUB_WORKSPACE": str(self.root), "RUNNER_TEMP": str(self.work),
            "GITHUB_SHA": COMMIT, "GITHUB_RUN_ID": "101", "GITHUB_RUN_ATTEMPT": "2",
            "GITHUB_REPOSITORY": "p2pKit/P2pKit", "GITHUB_EVENT_NAME": "push", "GITHUB_REF": REF,
            "GITHUB_ENV": str(self.work / "github.env"), "P2PKIT_AUDIT_ROLE": role,
            "P2PKIT_AUDIT_SCOPE": self.scope,
            "P2PKIT_AUDIT_BOOTSTRAP_DIR": str(self.bootstrap), "P2PKIT_AUDIT_STATE_DIR": str(self.state),
            "P2PKIT_AUDIT_DRIVER_TIMEOUT_SECONDS": "8400", "AUDIT_DRIVER_SAFE": "true",
            **{"AUDIT_" + name + "_OUTCOME": "success"
               for name in ("CHECKOUT", "JAVA21", "KEEP_JAVA21", "JAVA17", "DRIVER")},
        }
        self.allocation = {"schema": 1, "role": role, "requestedScope": self.scope, "expectedCommit": COMMIT,
                           "runId": "101", "runAttempt": "2", "sourceAdmitted": False}
        put(self.bootstrap / "workflow-start.json", self.allocation)
        if logs:
            put(self.bootstrap / "driver.stdout.log", b"synthetic driver fixture only\n")
            put(self.bootstrap / "driver.stderr.log", b"")
        if controls:
            context = {"schema": 1, "id": JOB_ID, "host": role, "root": str(self.root),
                       "expectedCommit": COMMIT, "tree": TREE, "source": copy.deepcopy(self.current)}
            put(self.evidence / "context.json", context)
            self.summary = {
                "schema": 1, "role": role, "safeToContinue": True, "result": "PASS", "requestedScope": self.scope,
                "hostQualification": "FULL_COMPONENT_SCOPE" if self.scope == "full" else
                    "NOT_ESTABLISHED_BY_FOCUSED_SCOPE",
                "source": {"commit": COMMIT, "tree": TREE, "role": role, "ref": REF, "requestedScope": self.scope,
                           "runId": "101", "runAttempt": "2"},
                "sourceAfter": copy.deepcopy(self.current), "components": [
                    {"component": "executor-native-controls", "result": "PASS", "exitCode": 0,
                     "cleanupComplete": True, "receipt": "host-executor-native-controls.json"},
                    {"component": "gradle-check", "result": "PASS", "exitCode": 0,
                     "cleanupComplete": True, "receipt": "host-gradle-check.json"},
                    {"component": "metadata-inspection", "result": "PASS", "inspectionOnly": True},
                ],
                "releaseGateMonolith": "NOT_EXECUTED_COMPONENT_REPLAY",
            }
            self.save_summary()
            for identity, component in ((CONTROL_ID, "executor-native-controls"), (PRODUCT_ID, "gradle-check")):
                self.write_receipt(identity, component)
                put(self.evidence / identity / "product.stdout.log", b"fixture output, not product execution\n")
                put(self.evidence / identity / "product.stderr.log", b"")
                put(self.evidence / identity / "stop.stdout.log", b"fixture owned-wrapper --stop result\n")
                put(self.evidence / identity / "stop.stderr.log", b"")
            self.seal()

    def save_summary(self):
        put(self.evidence / "host-summary.json", self.summary)

    def receipt(self, identity, component, **changes):
        return {"schema": 1, "id": identity, "jobId": JOB_ID, "host": self.role, "purpose": component,
                "sourceBefore": copy.deepcopy(self.current), "sourceAfter": copy.deepcopy(self.current),
                "sourceUnchanged": True, "stopExitCode": 0, "finalExitCode": 0,
                "errors": [], "ownedSurvivors": [], **changes}

    def write_receipt(self, identity, component, **changes):
        receipt = self.receipt(identity, component, **changes)
        put(self.evidence / ("host-" + component + ".json"), receipt)
        put(self.evidence / identity / "receipt.json", receipt)
        return receipt

    def seal(self):
        rows = []
        for path in sorted(self.evidence.rglob("*")):
            if path.is_file() and path != self.evidence / "manifest.sha256":
                rows.append(hashlib.sha256(path.read_bytes()).hexdigest() + "  " + path.relative_to(self.evidence).as_posix())
        put(self.evidence / "manifest.sha256", ("\n".join(rows) + "\n").encode("utf-8"))

    def git(self, argv, **kwargs):
        self.test.assertEqual(argv[:4], ["git", "--no-replace-objects", "-C", str(self.root)])
        self.test.assertEqual(set(kwargs), {"env", "stderr", "timeout"})
        self.test.assertEqual(kwargs["stderr"], subprocess.PIPE)
        self.test.assertEqual(kwargs["timeout"], 30)
        self.test.assertTrue(all(name not in kwargs["env"] for name in GIT_ENVIRONMENT))
        args = tuple(argv[4:])
        self.git_calls.append(args)
        if args in self.git_errors:
            raise self.git_errors[args]
        replies = {
            ("rev-parse", "HEAD"): (self.git_current["commit"] + "\n").encode("ascii"),
            ("rev-parse", "HEAD^{tree}"): (self.git_current["tree"] + "\n").encode("ascii"),
            ("status", "--porcelain=v1", "--untracked-files=all"): self.git_current["status"].encode("utf-8"),
            ("diff", "--binary", "--no-ext-diff", "--no-textconv", "HEAD", "--"): self.git_diff,
        }
        self.test.assertIn(args, replies, "No fallback Git/native command is allowed in these fixtures")
        return replies[args]

    def invoke(self, limits=None, patches=()):
        self.invocations += 1
        output = self.work / ("github.output." + str(self.invocations))
        summary = self.work / ("github.summary." + str(self.invocations))
        environment = {**self.environment, "GITHUB_OUTPUT": str(output), "GITHUB_STEP_SUMMARY": str(summary)}
        namespace = {"__name__": "__audit_workflow_fixture__"}
        stdout, stderr = io.StringIO(), io.StringIO()
        exception, exit_code = None, 0
        with contextlib.ExitStack() as stack:
            stack.enter_context(mock.patch.dict(os.environ, environment, clear=True))
            stack.enter_context(mock.patch.object(subprocess, "check_output", side_effect=self.git))
            stack.enter_context(mock.patch.object(subprocess, "Popen", side_effect=AssertionError("Unexpected native process")))
            stack.enter_context(contextlib.redirect_stdout(stdout))
            stack.enter_context(contextlib.redirect_stderr(stderr))
            for patch in patches:
                stack.enter_context(patch)
            try:
                # Compile/execute the actual AST unchanged; only production bounds are reduced.
                exec(HANDOFF_SETUP, namespace)
                for name, value in (limits or {}).items():
                    self.test.assertTrue(name.startswith("MAX_") and name in namespace)
                    self.test.assertIs(type(value), int)
                    self.test.assertGreater(value, 0)
                    self.test.assertLessEqual(value, namespace[name])
                    namespace[name] = value
                exec(HANDOFF_MAIN, namespace)
            except SystemExit as failure:
                exception, exit_code = failure, failure.code
            except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as failure:
                exception, exit_code = failure, 1
        record = self.bootstrap / "workflow-handoff.json"
        return types.SimpleNamespace(exit_code=exit_code, exception=exception, namespace=namespace,
                                     stdout=stdout.getvalue(), stderr=stderr.getvalue(), outputs=outputs(output),
                                     step_summary=summary.read_text(encoding="utf-8") if summary.exists() else "",
                                     record=json_file(record) if record.is_file() else None)


class StatView:
    """Portable link/reparse/race observation at the real Path stat boundary."""
    def __init__(self, original, changes):
        self.original = original
        self.changes = changes

    def __getattr__(self, name):
        return self.changes[name] if name in self.changes else getattr(self.original, name)


def metadata_patch(path, method="lstat", **changes):
    original = getattr(Path, method)

    def observed(candidate, *args, **kwargs):
        value = original(candidate, *args, **kwargs)
        return StatView(value, changes) if candidate == path else value

    return mock.patch.object(Path, method, new=observed)


class StreamHook:
    def __init__(self, stream, read=None, write=None, close=None):
        self.stream = stream
        self.on_read, self.on_write, self.on_close = read, write, close
        self.reads = 0

    def __enter__(self):
        self.stream.__enter__()
        return self

    def __exit__(self, *args):
        result = self.stream.__exit__(*args)
        if self.on_close:
            self.on_close()
        return result

    def __getattr__(self, name):
        return getattr(self.stream, name)

    def read(self, size=-1):
        value = self.stream.read(size)
        self.reads += 1
        if self.on_read:
            self.on_read(value, self.reads)
        return value

    def write(self, value):
        if self.on_write:
            return self.on_write(self.stream, value)
        return self.stream.write(value)


def stream_patch(path, mode, **hooks):
    original = Path.open

    def opened(candidate, *args, **kwargs):
        stream = original(candidate, *args, **kwargs)
        actual_mode = args[0] if args else kwargs.get("mode", "r")
        return StreamHook(stream, **hooks) if candidate == path and actual_mode == mode else stream

    return mock.patch.object(Path, "open", new=opened)


class WorkflowTestCase(unittest.TestCase):
    def assert_manifest(self, root, name="manifest.sha256"):
        manifest = root / name
        rows = {}
        for line in manifest.read_text(encoding="utf-8").splitlines():
            digest, separator, relative = line.partition("  ")
            self.assertEqual(separator, "  ")
            self.assertRegex(digest, r"^[0-9a-f]{64}$")
            self.assertNotIn(relative, rows)
            rows[relative] = digest
        actual = {path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
                  for path in root.rglob("*") if path.is_file() and path != manifest}
        self.assertEqual(rows, actual, "Published manifest must bind every retained file, including hidden files")
        return rows

    def assert_safe(self, case, result, product="PASS"):
        self.assertEqual(result.exit_code, 0, result.stderr + str(result.exception))
        self.assertIsNone(result.exception)
        self.assertEqual(result.outputs, {"bootstrap_path": str(case.bootstrap),
                                         "driver_evidence_path": str(case.evidence), "safe_to_continue": "true"})
        self.assertIs(result.record["safeToContinue"], True)
        self.assertEqual(result.record["hostResult"], product)
        self.assertEqual(result.record["evidenceUploadKind"], "FULL_SEALED")
        self.assertEqual(result.record["fullTreeCompleteness"], "PROVED")
        self.assertIsNone(result.record["salvage"])
        self.assertIn("Not release/physical acceptance", result.step_summary)
        self.assert_manifest(case.bootstrap, "bootstrap-manifest.sha256")
        self.assert_manifest(case.evidence)

    def assert_salvaged(self, case, result, error=None):
        self.assertEqual(result.exit_code, 1)
        self.assertIsInstance(result.exception, SystemExit, str(result.exception))
        self.assertEqual(result.outputs, {"bootstrap_path": str(case.bootstrap),
                                         "driver_evidence_path": "", "safe_to_continue": "false"})
        self.assertIs(result.record["safeToContinue"], False)
        self.assertEqual(result.record["fullTreeCompleteness"], "NOT_PROVEN")
        if error:
            self.assertIn(error, result.record["handoffError"])
        salvage = case.bootstrap / "evidence-salvage"
        details = result.record["salvage"]
        self.assertEqual(details["fullTreeCompleteness"], "NOT_PROVEN")
        self.assertIn("no cleanup, completeness or acceptance proof", details["limitation"])
        self.assertEqual(details["manifestSha256"], hashlib.sha256((salvage / "manifest.sha256").read_bytes()).hexdigest())
        retained = self.assert_manifest(salvage)
        self.assertEqual(details["retainedFiles"], len(retained) - 1)
        self.assertEqual(details["retainedBytes"], sum((salvage / name).stat().st_size
                                                     for name in retained if name != "salvage-summary.json"))
        self.assertEqual(result.record["evidenceUploadKind"],
                         "PARTIAL_SALVAGE" if details["retainedFiles"] else "BOOTSTRAP_ONLY")
        self.assert_manifest(case.bootstrap, "bootstrap-manifest.sha256")
        return details


class HandoffTest(WorkflowTestCase):
    def test_focused_scope_cannot_be_relabelled_as_full_qualification(self):
        scopes = [("windows-x64", scope) for scope in ("full", "windows-followup", "windows-diagnostics")]
        scopes.extend(("macos-arm64", scope) for scope in (
            "apple-provenance", "apple-native-compilation", "apple-owned-cancellation", "apple-owned-helper"))
        scopes.append(("macos-x64", "apple-owned-helper"))
        for role, scope in scopes:
            case = Fixture(self, role=role, scope=scope)
            self.assert_safe(case, case.invoke())
        for role, scope in (("windows-x64", "windows-diagnostics"), ("macos-arm64", "apple-provenance"),
                            ("macos-arm64", "apple-native-compilation"), ("macos-arm64", "apple-owned-cancellation"),
                            ("macos-arm64", "apple-owned-helper"), ("macos-x64", "apple-owned-helper")):
            for target, key, value in (("summary", "requestedScope", "full"),
                                       ("source", "requestedScope", "full"),
                                       ("summary", "hostQualification", "FULL_COMPONENT_SCOPE")):
                with self.subTest(role=role, scope=scope, target=target, key=key):
                    case = Fixture(self, role=role, scope=scope)
                    destination = case.summary if target == "summary" else case.summary["source"]
                    destination[key] = value
                    case.save_summary()
                    case.seal()
                    self.assert_salvaged(case, case.invoke())

    def test_full_walk_entry_limit_includes_empty_directories(self):
        case = Fixture(self)
        # Leave room for the bootstrap/salvage tree, which has its own strict scan.
        # Every original file still fits; empty directories must consume capacity.
        file_count = len([path for path in case.evidence.rglob("*") if path.is_file()])
        limit = file_count + 20
        nested = case.evidence / "empty-directories"
        for number in range(limit):
            (nested / str(number)).mkdir(parents=True)
        result = case.invoke(limits={"MAX_FILES": limit})
        self.assert_salvaged(case, result, "Traversal cap")
        self.assertTrue(nested.is_dir())

    def test_unreadable_descendant_cannot_disappear_from_full_evidence(self):
        case = Fixture(self)
        hidden = case.evidence / "unlisted-unreadable"
        put(hidden / "required.log", b"retained original despite traversal failure\n")
        original = os.scandir

        def scan(path):
            if Path(path) == hidden:
                raise PermissionError("fixture evidence descendant scan failed")
            return original(path)

        result = case.invoke(patches=(mock.patch.object(os, "scandir", side_effect=scan),))
        self.assert_salvaged(case, result, "fixture evidence descendant scan failed")
        self.assertEqual(b"retained original despite traversal failure\n", (hidden / "required.log").read_bytes())

    def test_unreadable_bootstrap_descendant_never_exports_upload_paths(self):
        case = Fixture(self)
        hidden = case.bootstrap / "evidence-salvage/unreadable"
        put(hidden / "required.log", b"bootstrap fixture evidence\n")
        original = os.scandir

        def scan(path):
            if Path(path) == hidden:
                raise PermissionError("fixture bootstrap descendant scan failed")
            return original(path)

        result = case.invoke(patches=(mock.patch.object(os, "scandir", side_effect=scan),))
        self.assertEqual(1, result.exit_code)
        self.assertIsInstance(result.exception, PermissionError)
        self.assertEqual({}, result.outputs)
        self.assertFalse((case.bootstrap / "bootstrap-manifest.sha256").exists())
        self.assertEqual(b"bootstrap fixture evidence\n", (hidden / "required.log").read_bytes())

    def test_actual_handoff_passes_only_complete_source_bound_owned_evidence_for_each_role(self):
        for role in ("windows-x64", "macos-arm64", "macos-x64"):
            with self.subTest(role=role):
                case = Fixture(self, role)
                before = {path: path.read_bytes() for path in case.evidence.rglob("*") if path.is_file()}
                case.environment.update({name: "competing-boundary-fixture" for name in GIT_ENVIRONMENT})
                result = case.invoke()
                self.assert_safe(case, result)
                self.assertEqual(len(case.git_calls), 4)
                self.assertEqual(before, {path: path.read_bytes() for path in before})
                self.assertEqual((case.root / "untouched-source.txt").read_bytes(),
                                 b"synthetic source; never an owned output\n")

    def test_cleaned_product_failure_stays_failed_but_may_release_the_next_host_after_upload(self):
        for inspection_only in (False, True):
            with self.subTest(inspection_only=inspection_only):
                case = Fixture(self)
                case.summary["result"] = "FAIL"
                index = 2 if inspection_only else 1
                if inspection_only:
                    case.summary["components"][index].update(result="FAIL")
                else:
                    case.summary["components"][index].update(result="FAIL", exitCode=17)
                    case.write_receipt(PRODUCT_ID, "gradle-check", finalExitCode=17)
                case.save_summary()
                case.seal()
                case.environment["AUDIT_DRIVER_OUTCOME"] = "failure"
                result = case.invoke()
                self.assert_safe(case, result, product="FAIL")
                self.assertEqual(result.record["setupAndDriverOutcomes"]["driver"], "failure")
                self.assertEqual(json_file(case.evidence / "host-summary.json")["components"][index]["result"], "FAIL")

    def test_false_missing_or_nonliteral_driver_output_cannot_borrow_an_optimistic_summary(self):
        for value in (None, "", "false", "True", "1", " true"):
            with self.subTest(value=value):
                case = Fixture(self)
                if value is None:
                    case.environment.pop("AUDIT_DRIVER_SAFE")
                else:
                    case.environment["AUDIT_DRIVER_SAFE"] = value
                original = (case.evidence / "host-summary.json").read_bytes()
                result = case.invoke()
                self.assert_salvaged(case, result, "Unsafe driver output")
                self.assertEqual(case.git_calls, [])
                self.assertEqual((case.bootstrap / "evidence-salvage/files/host-summary.json").read_bytes(), original)
                self.assertEqual((case.evidence / "host-summary.json").read_bytes(), original)

    def test_skipped_cancelled_missing_or_failed_setup_outcomes_are_retained_without_continuation(self):
        for key, value in itertools.product(("CHECKOUT", "JAVA21", "KEEP_JAVA21", "JAVA17"),
                                            ("failure", "cancelled", "skipped", "")):
            with self.subTest(key=key, value=value):
                case = Fixture(self)
                case.environment["AUDIT_" + key + "_OUTCOME"] = value
                result = case.invoke()
                self.assert_salvaged(case, result, "Setup failed")
                self.assertEqual(result.record["setupAndDriverOutcomes"][key.lower()], value)
                self.assertEqual(case.git_calls, [])
        for value in ("cancelled", "skipped", ""):
            with self.subTest(driver=value):
                case = Fixture(self)
                case.environment["AUDIT_DRIVER_OUTCOME"] = value
                self.assert_salvaged(case, case.invoke(), "Unsafe driver output")

    def test_actual_driver_outcome_must_agree_with_pass_or_fail_summary(self):
        for host_result, step_result in (("PASS", "failure"), ("FAIL", "success")):
            with self.subTest(host_result=host_result):
                case = Fixture(self)
                case.summary["result"] = host_result
                case.save_summary()
                case.seal()
                case.environment["AUDIT_DRIVER_OUTCOME"] = step_result
                self.assert_salvaged(case, case.invoke(), "Step/result mismatch")

    def test_fresh_git_head_tree_status_and_diff_are_checked_without_fallbacks(self):
        for field, value in (("commit", "7" * 40), ("tree", "8" * 40), ("tree", "not-a-tree"),
                             ("status", " M tracked.kt\n"), ("status", "?? hidden.txt\n"),
                             ("status", "A  staged.kt\n"), ("diff", b"nonempty binary diff\n")):
            with self.subTest(field=field, value=value):
                case = Fixture(self)
                if field == "diff":
                    case.git_diff = value
                else:
                    case.git_current[field] = value
                self.assert_salvaged(case, case.invoke())
                self.assertEqual(len(case.git_calls), 4)
        case = Fixture(self)
        case.git_errors[("rev-parse", "HEAD")] = subprocess.CalledProcessError(128, ["git", "rev-parse", "HEAD"])
        self.assert_salvaged(case, case.invoke(), "CalledProcessError")
        self.assertEqual(case.git_calls, [("rev-parse", "HEAD")])

    def test_summary_binds_exact_source_role_ref_run_id_and_attempt(self):
        for field, value in (("commit", "7" * 40), ("tree", "8" * 40), ("role", "another-host"),
                             ("ref", "refs/heads/main"), ("runId", "100"), ("runAttempt", "1"),
                             ("runId", 101), ("runAttempt", 2)):
            with self.subTest(field=field, value=value):
                case = Fixture(self)
                case.summary["source"][field] = value
                case.save_summary()
                case.seal()
                self.assert_salvaged(case, case.invoke(), "Source/attempt differs")
        case = Fixture(self)
        case.summary["sourceAfter"]["extra-unbound-field"] = True
        case.save_summary()
        case.seal()
        self.assert_salvaged(case, case.invoke(), "Source/attempt differs")

    def test_owned_context_cannot_rebind_root_source_identity_or_host(self):
        changes = (("schema", True), ("id", "G" * 32), ("id", "4" * 31), ("host", "another-host"),
                   ("root", "foreign-checkout"), ("expectedCommit", "8" * 40), ("tree", "9" * 40),
                   ("source", {"commit": COMMIT}))
        for key, value in changes:
            with self.subTest(key=key, value=value):
                case = Fixture(self)
                path = case.evidence / "context.json"
                context = json_file(path)
                context[key] = value
                put(path, context)
                case.seal()
                self.assert_salvaged(case, case.invoke(), "Wrong context")

    def test_summary_schema_safety_role_and_result_are_not_truthiness_checks(self):
        for key, value in (("schema", True), ("schema", "1"), ("schema", 2),
                           ("safeToContinue", 1), ("safeToContinue", "true"), ("safeToContinue", False),
                           ("role", "another-host"), ("result", "NOT_STARTED"), ("result", True)):
            with self.subTest(key=key, value=value):
                case = Fixture(self)
                case.summary[key] = value
                case.save_summary()
                case.seal()
                self.assert_salvaged(case, case.invoke())

    def test_receipts_need_strict_identity_binding_stop_and_finalization_evidence(self):
        for changes in ({"schema": True}, {"id": "7" * 31}, {"jobId": "8" * 32}, {"host": "other"},
                        {"purpose": "other-leaf"}, {"sourceUnchanged": 1}, {"sourceBefore": {}},
                        {"sourceAfter": {}}, {"stopExitCode": False}, {"stopExitCode": 1},
                        {"finalExitCode": False}, {"finalExitCode": 125}, {"finalExitCode": 3},
                        {"errors": ["lost evidence"]}, {"errors": {}}, {"ownedSurvivors": [424242]},
                        {"ownedSurvivors": None}):
            with self.subTest(changes=changes):
                case = Fixture(self)
                case.write_receipt(PRODUCT_ID, "gradle-check", **changes)
                case.seal()
                self.assert_salvaged(case, case.invoke())

    def test_component_rows_cannot_forge_cleanup_inspection_or_receipt_paths(self):
        for changes in ({"cleanupComplete": 1}, {"cleanupComplete": False}, {"exitCode": False},
                        {"exitCode": "0"}, {"exitCode": 125}, {"inspectionOnly": False},
                        {"inspectionOnly": True}, {"component": "../escape"},
                        {"receipt": "../foreign.json"}, {"receipt": "host-other.json"}):
            with self.subTest(changes=changes):
                case = Fixture(self)
                case.summary["components"][1].update(changes)
                case.save_summary()
                case.seal()
                self.assert_salvaged(case, case.invoke())
        for rows in ([], None, ["not a component"]):
            with self.subTest(rows=rows):
                case = Fixture(self)
                case.summary["components"] = rows
                case.save_summary()
                case.seal()
                self.assert_salvaged(case, case.invoke())
        case = Fixture(self)
        case.summary["components"].append(copy.deepcopy(case.summary["components"][0]))
        case.save_summary()
        case.seal()
        self.assert_salvaged(case, case.invoke(), "Invalid/duplicate component")

    def test_inspections_cannot_substitute_for_successful_native_process_controls(self):
        for kind in ("missing", "inspection", "failure"):
            with self.subTest(kind=kind):
                case = Fixture(self)
                if kind == "missing":
                    case.summary["components"].pop(0)
                elif kind == "inspection":
                    case.summary["components"][0] = {"component": "executor-native-controls", "result": "PASS",
                                                    "inspectionOnly": True}
                else:
                    case.summary["result"] = "FAIL"
                    case.summary["components"][0].update(result="FAIL", exitCode=1)
                    case.write_receipt(CONTROL_ID, "executor-native-controls", finalExitCode=1)
                    case.environment["AUDIT_DRIVER_OUTCOME"] = "failure"
                case.save_summary()
                case.seal()
                self.assert_salvaged(case, case.invoke(), "Native controls failed")

    def test_pass_summary_cannot_hide_failed_products_or_claim_full_release_gate_execution(self):
        case = Fixture(self)
        case.summary["components"][1].update(result="FAIL", exitCode=7)
        case.write_receipt(PRODUCT_ID, "gradle-check", finalExitCode=7)
        case.save_summary()
        case.seal()
        self.assert_salvaged(case, case.invoke(), "False PASS summary")
        case = Fixture(self)
        case.summary["releaseGateMonolith"] = "PASS"
        case.save_summary()
        case.seal()
        self.assert_salvaged(case, case.invoke(), "Unexpected gate scope")

    def test_all_direct_nested_invocations_must_be_finalized_even_if_outer_components_pass(self):
        for changes in (None, {"finalExitCode": 125}, {"stopExitCode": 1}, {"errors": ["unfinished"]},
                        {"ownedSurvivors": [424242]}, {"id": "7" * 32}, {"sourceAfter": {}}):
            with self.subTest(changes=changes):
                case = Fixture(self)
                put(case.evidence / NESTED_ID / "start.json", {"schema": 1, "id": NESTED_ID})
                if changes is not None:
                    put(case.evidence / NESTED_ID / "receipt.json", case.receipt(NESTED_ID, "nested-leaf", **changes))
                case.seal()
                self.assert_salvaged(case, case.invoke())
        case = Fixture(self)
        put(case.evidence / NESTED_ID / "receipt.json", case.receipt(NESTED_ID, "nested-leaf"))
        case.seal()
        self.assert_safe(case, case.invoke())

    def test_outer_and_canonical_receipt_copies_are_byte_exact_not_just_equivalent_json(self):
        for change in ("metadata", "format"):
            with self.subTest(change=change):
                case = Fixture(self)
                canonical = case.evidence / PRODUCT_ID / "receipt.json"
                receipt = json_file(canonical)
                if change == "metadata":
                    receipt["laterUnboundField"] = True
                    put(canonical, receipt)
                else:
                    put(canonical, json.dumps(receipt, separators=(",", ":")).encode("utf-8"))
                case.seal()
                self.assert_salvaged(case, case.invoke(), "Receipt copies differ")

    def test_hidden_files_are_manifested_and_preserved_in_safe_full_evidence(self):
        case = Fixture(self)
        put(case.evidence / ".hidden.log", b"hidden synthetic log\n")
        put(case.evidence / ".hidden-directory/.receipt.json", {"fixture": True})
        case.seal()
        result = case.invoke()
        self.assert_safe(case, result)
        self.assertIn(".hidden-directory/.receipt.json", self.assert_manifest(case.evidence))

    def test_unlisted_hidden_missing_or_modified_files_cannot_satisfy_a_manifest(self):
        for change in ("hidden", "nested-hidden", "missing", "modified"):
            with self.subTest(change=change):
                case = Fixture(self)
                victim = case.evidence / PRODUCT_ID / "product.stdout.log"
                if change == "hidden":
                    put(case.evidence / ".unlisted.log", b"not in the sealed evidence set\n")
                elif change == "nested-hidden":
                    put(case.evidence / ".unlisted/trace.log", b"not in the sealed evidence set\n")
                elif change == "missing":
                    victim.unlink()
                else:
                    put(victim, b"changed after seal\n")
                self.assert_salvaged(case, case.invoke())

    def test_manifest_rejects_malformed_duplicate_self_referential_and_unsafe_names(self):
        bad_lines = ("", "\n", "not a manifest\n", "A" * 64 + "  log.txt\n",
                     "a" * 63 + "  log.txt\n", "a" * 64 + " log.txt\n",
                     "a" * 64 + "  manifest.sha256\n")
        bad_names = ("/absolute.log", "../escape.log", "a/../escape.log", "./dot.log", "a//file.log",
                     "a\\file.log", "C:/file.log", "control\x01.log", "control\x7f.log", "a/./file.log")
        for raw in (*bad_lines, *("a" * 64 + "  " + name + "\n" for name in bad_names)):
            with self.subTest(raw=raw):
                case = Fixture(self)
                put(case.evidence / "manifest.sha256", raw.encode("utf-8"))
                self.assert_salvaged(case, case.invoke())
        case = Fixture(self)
        manifest = case.evidence / "manifest.sha256"
        raw = manifest.read_bytes()
        put(manifest, raw + raw.splitlines(keepends=True)[0])
        self.assert_salvaged(case, case.invoke(), "Manifest duplicate/cap")

    def test_bounded_control_parsing_rejects_duplicate_nonfinite_nonobject_and_invalid_json(self):
        for raw in (b"{", b"[]\n", b'{"schema":1,"schema":1}\n', b'{"value":NaN}\n', b"\xff\n"):
            with self.subTest(raw=raw):
                case = Fixture(self)
                put(case.evidence / "host-summary.json", raw)
                case.seal()
                self.assert_salvaged(case, case.invoke())
        case = Fixture(self)
        case.summary["oversizeFixture"] = "x" * 4096
        case.save_summary()
        case.seal()
        self.assert_salvaged(case, case.invoke(limits={"MAX_JSON": 2048}), "Invalid control file")
        case = Fixture(self)
        self.assert_salvaged(case, case.invoke(limits={"MAX_MANIFEST": 64}), "Invalid control file")

    def test_full_tree_file_and_total_byte_limits_are_enforced_before_safe_output(self):
        for limit, value, suffix in (("MAX_FILE_BYTES", 4096, ".log"), ("MAX_TOTAL_BYTES", 20000, ".bin")):
            with self.subTest(limit=limit):
                case = Fixture(self)
                put(case.evidence / ("oversize" + suffix), b"x" * 30000)
                case.seal()
                self.assert_salvaged(case, case.invoke(limits={limit: value}))

    def test_bootstrap_allocation_is_exactly_bound_before_any_path_is_exported(self):
        for key, value in (("schema", True), ("role", "other-host"), ("requestedScope", "full"),
                           ("expectedCommit", "8" * 40),
                           ("runId", "100"), ("runAttempt", "1"), ("runId", 101), ("runAttempt", 2)):
            with self.subTest(key=key, value=value):
                case = Fixture(self)
                case.allocation[key] = value
                put(case.bootstrap / "workflow-start.json", case.allocation)
                before = {path: path.read_bytes() for path in case.bootstrap.iterdir() if path.is_file()}
                result = case.invoke()
                self.assertEqual(result.exit_code, 1)
                self.assertEqual(result.outputs, {})
                self.assertIn("FATAL: unsafe bootstrap", result.stderr)
                self.assertEqual(before, {path: path.read_bytes() for path in before})
                self.assertEqual(case.git_calls, [])
                self.assertFalse((case.bootstrap / "evidence-salvage").exists())

    def test_unsafe_bootstrap_names_locations_and_link_ancestors_never_become_upload_roots(self):
        for kind in ("relative", "inside-source", "ancestor-of-source", "wrong-name", "link", "reparse"):
            with self.subTest(kind=kind):
                case = Fixture(self)
                patches = []
                if kind == "relative":
                    case.environment["P2PKIT_AUDIT_BOOTSTRAP_DIR"] = "bootstrap-evidence"
                elif kind == "inside-source":
                    target = case.root / "p2pkit-audit-windows-x64-fixture/bootstrap-evidence"
                    target.mkdir(parents=True)
                    case.environment["P2PKIT_AUDIT_BOOTSTRAP_DIR"] = str(target)
                elif kind == "ancestor-of-source":
                    checkout = case.parent / "checkout"
                    checkout.mkdir()
                    case.environment["GITHUB_WORKSPACE"] = str(checkout)
                elif kind == "wrong-name":
                    target = case.parent / "foreign-evidence"
                    target.mkdir()
                    case.environment["P2PKIT_AUDIT_BOOTSTRAP_DIR"] = str(target)
                elif kind == "link":
                    patches.append(metadata_patch(case.parent, st_mode=stat.S_IFLNK | 0o777))
                else:
                    patches.append(metadata_patch(case.parent, st_file_attributes=0x400))
                result = case.invoke(patches=patches)
                self.assertEqual(result.exit_code, 1)
                self.assertEqual(result.outputs, {})
                self.assertIn("FATAL: unsafe bootstrap", result.stderr)
                self.assertEqual(case.git_calls, [])

    def test_wrong_missing_or_linked_state_is_zero_copy_salvage_not_a_full_tree_upload(self):
        for kind in ("relative", "foreign-parent", "wrong-name", "missing", "link", "reparse"):
            with self.subTest(kind=kind):
                case = Fixture(self)
                patches = []
                if kind == "relative":
                    case.environment["P2PKIT_AUDIT_STATE_DIR"] = "state"
                elif kind == "foreign-parent":
                    foreign = case.root / "state/evidence"
                    foreign.mkdir(parents=True)
                    put(foreign / "foreign.log", b"not owned\n")
                    case.environment["P2PKIT_AUDIT_STATE_DIR"] = str(foreign.parent)
                elif kind == "wrong-name":
                    case.environment["P2PKIT_AUDIT_STATE_DIR"] = str(case.parent / "foreign-state")
                elif kind == "missing":
                    case.evidence.rename(case.state / "preserved-evidence")
                elif kind == "link":
                    patches.append(metadata_patch(case.state, st_mode=stat.S_IFLNK | 0o777))
                else:
                    patches.append(metadata_patch(case.state, st_file_attributes=0x400))
                result = case.invoke(patches=patches)
                details = self.assert_salvaged(case, result)
                self.assertEqual(details["retainedFiles"], 0)
                self.assertIn("Evidence root unavailable", details["omissions"][0]["reason"])

    def test_link_reparse_and_nonregular_evidence_nodes_are_not_read_or_salvaged(self):
        for kind in ("link", "reparse", "nonregular"):
            with self.subTest(kind=kind):
                case = Fixture(self)
                victim = case.evidence / "unsafe.log"
                put(victim, b"not an admissible evidence node\n")
                case.seal()
                patches = []
                if kind == "link":
                    patches.append(metadata_patch(victim, st_mode=stat.S_IFLNK | 0o777))
                elif kind == "reparse":
                    patches.append(metadata_patch(victim, st_file_attributes=0x400))
                else:
                    patches.append(metadata_patch(victim, method="stat", st_mode=stat.S_IFIFO | 0o600))
                original_open = Path.open

                def opened(path, *args, **kwargs):
                    self.assertNotEqual(path, victim, "A rejected evidence node must never be opened")
                    return original_open(path, *args, **kwargs)

                patches.append(mock.patch.object(Path, "open", new=opened))
                result = case.invoke(patches=patches)
                details = self.assert_salvaged(case, result)
                self.assertTrue(any(row["path"] == "unsafe.log" for row in details["omissions"]))
                self.assertFalse((case.bootstrap / "evidence-salvage/files/unsafe.log").exists())
                self.assertEqual(victim.read_bytes(), b"not an admissible evidence node\n")

    def test_linked_evidence_subdirectory_is_not_descended_during_full_or_salvage_inspection(self):
        case = Fixture(self)
        directory = case.evidence / "unsafe-directory"
        nested = directory / "foreign.log"
        put(nested, b"never traverse a rejected directory\n")
        case.seal()
        result = case.invoke(patches=[metadata_patch(directory, st_mode=stat.S_IFLNK | 0o777)])
        details = self.assert_salvaged(case, result)
        self.assertTrue(any(row["path"] == "unsafe-directory" for row in details["omissions"]))
        self.assertFalse((case.bootstrap / "evidence-salvage/files/unsafe-directory").exists())
        self.assertEqual(nested.read_bytes(), b"never traverse a rejected directory\n")

    def test_unexpected_bootstrap_nodes_and_reused_handoff_are_preserved_without_upload_outputs(self):
        for name in ("unexpected.txt", ".hidden-unknown.json", "foreign/trace.log"):
            with self.subTest(name=name):
                case = Fixture(self)
                path = case.bootstrap / name
                put(path, b"foreign bootstrap material\n")
                result = case.invoke()
                self.assertEqual(result.exit_code, 1)
                self.assertEqual(result.outputs, {})
                self.assertEqual(path.read_bytes(), b"foreign bootstrap material\n")
        case = Fixture(self)
        self.assert_safe(case, case.invoke())
        original = (case.bootstrap / "workflow-handoff.json").read_bytes()
        result = case.invoke()
        self.assertEqual(result.exit_code, 1)
        self.assertIsInstance(result.exception, FileExistsError)
        self.assertEqual(result.outputs, {})
        self.assertEqual((case.bootstrap / "workflow-handoff.json").read_bytes(), original)


class SalvageTest(WorkflowTestCase):
    def case(self, files):
        case = Fixture(self, controls=False)
        case.environment["AUDIT_DRIVER_SAFE"] = "false"
        for name, content in files.items():
            put(case.evidence / name, content)
        return case

    def test_only_allowlisted_regular_text_is_copied_with_originals_and_hidden_files_preserved(self):
        files = {"context.json": b"{malformed historical control\n", "trace.log": b"log\n", "note.txt": b"note\n",
                 "result.xml": b"<synthetic/>\n", "manifest.sha256": b"not a full manifest\n",
                 ".hidden/trace.log": b"hidden\n", "binary.bin": b"\x00\x01", "private.key": b"synthetic-only\n",
                 "uppercase.LOG": b"not allowlisted\n", "empty.log": b""}
        case = self.case(files)
        result = case.invoke()
        details = self.assert_salvaged(case, result, "Unsafe driver output")
        expected = set(files) - {"binary.bin", "private.key", "uppercase.LOG"}
        copies = case.bootstrap / "evidence-salvage/files"
        self.assertEqual({path.relative_to(copies).as_posix() for path in copies.rglob("*") if path.is_file()}, expected)
        self.assertEqual(details["retainedFiles"], len(expected))
        self.assertEqual(details["omissionCount"], 3)
        for name, content in files.items():
            self.assertEqual((case.evidence / name).read_bytes(), content)
            if name in expected:
                self.assertEqual((copies / name).read_bytes(), content)

    def test_count_bound_prefers_context_and_invocation_logs_over_arbitrary_text(self):
        files = {"b.log": b"b", "a.log": b"a", "z/receipt.json": b"receipt",
                 "z/product.stdout.log": b"product", "context.json": b"context"}
        case = self.case(files)
        result = case.invoke(limits={"MAX_SALVAGE_FILES": 2})
        details = self.assert_salvaged(case, result)
        self.assertEqual(details["retainedFiles"], 2)
        self.assertEqual(details["omissionCount"], 3)
        copies = case.bootstrap / "evidence-salvage/files"
        self.assertEqual({path.relative_to(copies).as_posix() for path in copies.rglob("*") if path.is_file()},
                         {"context.json", "z/product.stdout.log"})
        self.assertEqual(details["limits"]["files"], 2)

    def test_per_file_and_total_byte_bounds_omit_only_excess_copies(self):
        cases = (({"a.log": b"12345", "b.log": b"12"}, {"MAX_SALVAGE_FILE_BYTES": 4}, {"b.log"}, 2),
                 ({"a.log": b"1234", "b.log": b"5678", "c.log": b"x"}, {"MAX_SALVAGE_BYTES": 6},
                  {"a.log", "c.log"}, 5))
        for files, limits, expected, size in cases:
            with self.subTest(limits=limits):
                case = self.case(files)
                details = self.assert_salvaged(case, case.invoke(limits=limits))
                copies = case.bootstrap / "evidence-salvage/files"
                self.assertEqual({path.name for path in copies.iterdir()}, expected)
                self.assertEqual(details["retainedBytes"], size)
                self.assertEqual(details["omissionCount"], 1)
                for name, content in files.items():
                    self.assertEqual((case.evidence / name).read_bytes(), content)

    def test_traversal_and_omission_detail_bounds_are_real_without_large_fixture_allocations(self):
        case = self.case({"file-%03d.log" % index: b"x" for index in range(50)})
        result = case.invoke(limits={"MAX_FILES": 32, "MAX_SALVAGE_FILES": 2, "MAX_OMISSION_DETAILS": 1})
        details = self.assert_salvaged(case, result)
        self.assertEqual(details["retainedFiles"], 2)
        self.assertEqual(details["limits"]["traversedEntries"], 32)
        self.assertEqual(len(details["omissions"]), 1)
        self.assertGreater(details["omissionCount"], len(details["omissions"]))
        self.assertIs(details["omissionDetailsTruncated"], True)
        self.assertIn("Salvage entry cap", details["omissions"][0]["reason"])
        self.assertEqual(len(list(case.evidence.iterdir())), 50)

    def test_source_changed_after_copy_is_omitted_and_its_partial_destination_is_removed(self):
        case = self.case({"changing.log": b"old", "z-safe.log": b"safe"})
        source = case.evidence / "changing.log"
        original_open = Path.open

        def mutate(value, reads):
            if not value:
                with original_open(source, "wb") as stream:
                    stream.write(b"changed source after EOF")

        result = case.invoke(patches=[stream_patch(source, "rb", read=mutate)])
        details = self.assert_salvaged(case, result)
        self.assertEqual(details["retainedFiles"], 1)
        self.assertTrue(any("Salvage source changed" in row["reason"] for row in details["omissions"]))
        self.assertFalse((case.bootstrap / "evidence-salvage/files/changing.log").exists())
        self.assertEqual(source.read_bytes(), b"changed source after EOF")

    def test_source_growth_during_streaming_hits_both_file_and_total_bounds(self):
        for limits in ({"MAX_SALVAGE_FILE_BYTES": 4}, {"MAX_SALVAGE_BYTES": 4}):
            with self.subTest(limits=limits):
                case = self.case({"growing.log": b"123"})
                source = case.evidence / "growing.log"
                original_open = Path.open

                def append(value, reads):
                    if reads == 1:
                        with original_open(source, "ab") as stream:
                            stream.write(b"456")

                details = self.assert_salvaged(case, case.invoke(limits=limits,
                                              patches=[stream_patch(source, "rb", read=append)]))
                self.assertEqual(details["retainedFiles"], 0)
                self.assertTrue(any("Salvage file grew" in row["reason"] for row in details["omissions"]))
                self.assertFalse((case.bootstrap / "evidence-salvage/files/growing.log").exists())
                self.assertEqual(source.read_bytes(), b"123456")

    def test_partial_write_failure_removes_only_its_created_regular_copy_and_keeps_other_logs(self):
        case = self.case({"partial.log": b"payload", "z-safe.log": b"safe"})
        target = case.bootstrap / "evidence-salvage/files/partial.log"
        unlinked = []
        original_unlink = Path.unlink

        def partial(stream, value):
            stream.write(value[:2])
            raise OSError("fixture partial write failed")

        def unlink(path, *args, **kwargs):
            unlinked.append(path)
            return original_unlink(path, *args, **kwargs)

        result = case.invoke(patches=[stream_patch(target, "xb", write=partial),
                                      mock.patch.object(Path, "unlink", new=unlink)])
        details = self.assert_salvaged(case, result)
        self.assertEqual(unlinked, [target])
        self.assertFalse(target.exists())
        self.assertEqual(details["retainedFiles"], 1)
        self.assertTrue(any("fixture partial write failed" in row["reason"] for row in details["omissions"]))
        self.assertEqual((case.evidence / "partial.log").read_bytes(), b"payload")

    def test_corrupted_destination_is_hashed_and_removed_rather_than_sealed_as_a_good_copy(self):
        case = self.case({"copy.log": b"source"})
        target = case.bootstrap / "evidence-salvage/files/copy.log"
        original_open = Path.open

        def corrupt():
            with original_open(target, "wb") as stream:
                stream.write(b"corrupt destination")

        result = case.invoke(patches=[stream_patch(target, "xb", close=corrupt)])
        details = self.assert_salvaged(case, result)
        self.assertEqual(details["retainedFiles"], 0)
        self.assertTrue(any("Salvage copy changed" in row["reason"] for row in details["omissions"]))
        self.assertFalse(target.exists())
        self.assertEqual((case.evidence / "copy.log").read_bytes(), b"source")

    def test_failed_or_unsafe_partial_copy_removal_refuses_all_upload_outputs(self):
        for failure in ("unlink", "link-replacement"):
            with self.subTest(failure=failure):
                case = self.case({"partial.log": b"payload"})
                target = case.bootstrap / "evidence-salvage/files/partial.log"
                original_lstat = Path.lstat
                original_unlink = Path.unlink
                failed = []
                unlinked = []

                def partial(stream, value):
                    stream.write(value[:2])
                    failed.append(True)
                    raise OSError("fixture partial write failed")

                def lstat(path, *args, **kwargs):
                    info = original_lstat(path, *args, **kwargs)
                    if path == target and failed and failure == "link-replacement":
                        return StatView(info, {"st_mode": stat.S_IFLNK | 0o777})
                    return info

                def unlink(path, *args, **kwargs):
                    unlinked.append(path)
                    if path == target:
                        raise PermissionError("fixture cannot remove partial copy")
                    return original_unlink(path, *args, **kwargs)

                result = case.invoke(patches=[stream_patch(target, "xb", write=partial),
                                              mock.patch.object(Path, "lstat", new=lstat),
                                              mock.patch.object(Path, "unlink", new=unlink)])
                self.assertEqual(result.exit_code, 1)
                self.assertIsInstance(result.exception, ValueError)
                self.assertIn("Unsafe partial-copy removal", str(result.exception))
                self.assertEqual(result.outputs, {})
                self.assertEqual(unlinked, [target] if failure == "unlink" else [])
                self.assertEqual(target.read_bytes(), b"pa")
                self.assertFalse((case.bootstrap / "workflow-handoff.json").exists())
                self.assertFalse((case.bootstrap / "bootstrap-manifest.sha256").exists())
                self.assertEqual((case.evidence / "partial.log").read_bytes(), b"payload")

    def test_salvage_destination_must_be_fresh_and_never_overwrites_prior_evidence(self):
        case = self.case({"log.txt": b"new fixture"})
        previous = case.bootstrap / "evidence-salvage/files/log.txt"
        put(previous, b"prior fixture evidence")
        result = case.invoke()
        self.assertEqual(result.exit_code, 1)
        self.assertIsInstance(result.exception, ValueError)
        self.assertIn("Nonfresh salvage", str(result.exception))
        self.assertEqual(result.outputs, {})
        self.assertEqual(previous.read_bytes(), b"prior fixture evidence")


def expression_value(expression, values, cancelled=False):
    """Evaluate only the small boolean/property grammar actually used by the YAML.

    This tests actual expressions, not retyped continuation predicates. It does
    not implement GitHub coercion/general expressions: fixture outputs are real
    Actions-style strings, and unknown syntax fails for deliberate review.
    """
    if not expression.startswith("${{") or not expression.endswith("}}"):
        raise AssertionError("Expected a complete GitHub expression: " + expression)
    source = expression[3:-2].strip().replace("&&", " and ").replace("||", " or ")
    source = re.sub(r"!(?!=)", "not ", source)
    tree = ast.parse(source, mode="eval")

    def value(node):
        if isinstance(node, ast.Expression):
            return value(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (str, bool)):
            return node.value
        if isinstance(node, ast.Name) and node.id in values:
            return values[node.id]
        if isinstance(node, ast.Attribute):
            parent = value(node.value)
            return parent.get(node.attr, "") if isinstance(parent, dict) else ""
        if isinstance(node, ast.Subscript):
            parent, key = value(node.value), value(node.slice)
            return parent.get(key, "") if isinstance(parent, dict) else ""
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and not node.args and not node.keywords:
            if node.func.id == "always":
                return True
            if node.func.id == "cancelled":
                return cancelled
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "contains"
                and len(node.args) == 2 and not node.keywords):
            haystack, needle = (value(argument) for argument in node.args)
            if isinstance(haystack, str) and isinstance(needle, str):
                return needle.casefold() in haystack.casefold()
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
            return not value(node.operand)
        if isinstance(node, ast.BoolOp):
            operands = [bool(value(part)) for part in node.values]
            if isinstance(node.op, ast.And):
                return all(operands)
            if isinstance(node.op, ast.Or):
                return any(operands)
        if isinstance(node, ast.Compare) and len(node.ops) == 1:
            left, right = value(node.left), value(node.comparators[0])
            if isinstance(node.ops[0], ast.Eq):
                return left == right
            if isinstance(node.ops[0], ast.NotEq):
                return left != right
        raise AssertionError("Unsupported workflow expression syntax: " + ast.dump(node))

    return value(tree)


class WorkflowOrchestrationTest(WorkflowTestCase):
    def test_retired_audit_branch_deletion_cannot_allocate_any_optional_job(self):
        workflows = {
            "audit-host-validation.yml": "selected_host",
            "audit-jmdns-startup.yml": "jmdns_startup",
            "audit-lock-refresh.yml": "lock_refresh",
            "audit-android-art.yml": "android_art",
        }
        for filename, job in workflows.items():
            text = (WORKFLOW.parent / filename).read_text(encoding="utf-8")
            with mock.patch.dict(globals(), {"TEXT": text}):
                expression = yaml_value(job_block(job), "if", 4)
            prefix = text.split("\njobs:\n", 1)[0]
            self.assertIn("branches: [audit/complete-2026-09-04]", prefix)
            self.assertIn("paths: [.github/workflows/" + filename + "]", prefix)
            for deleted, event, marked, repository in (
                    (False, "push", True, "p2pKit/P2pKit"),
                    (True, "push", True, "p2pKit/P2pKit"),
                    (False, "workflow_dispatch", True, "p2pKit/P2pKit"),
                    (False, "push", False, "p2pKit/P2pKit"),
                    (False, "push", True, "other/repository")):
                with self.subTest(workflow=filename, deleted=deleted, event=event,
                                  marked=marked, repository=repository):
                    values = {"github": {"repository": repository, "event_name": event,
                                         "event": {"deleted": deleted, "head_commit": {
                                             "message": "[audit-art]" if marked else "ordinary push"}}}}
                    expected = (not deleted and event == "push"
                                and (job == "selected_host" or repository == "p2pKit/P2pKit")
                                and (job != "android_art" or marked))
                    self.assertEqual(expected, expression_value(expression, values))

    def test_handoff_job_output_requires_successful_step_and_literal_safe_value(self):
        expression = yaml_value(job_block("selected_host"), "safe_to_continue", 6)
        for outcome, safe in itertools.product(("success", "failure", "cancelled", "skipped", ""),
                                                ("true", "false", "", "TRUE")):
            with self.subTest(outcome=outcome, safe=safe):
                values = {"steps": {"handoff": {"outcome": outcome, "outputs": {"safe_to_continue": safe}}}}
                self.assertEqual(outcome == "success" and safe == "true", expression_value(expression, values))
        self.assertIs(expression_value(expression, {"steps": {}}), False)

    def test_late_summary_write_failure_blocks_safe_output_despite_emitted_outputs(self):
        case = Fixture(self)

        def fail_write(stream, value):
            raise OSError("fixture late workflow summary write failed")

        result = case.invoke(patches=(stream_patch(case.work / "github.summary.1", "a", write=fail_write),))
        self.assertEqual(1, result.exit_code)
        self.assertIsInstance(result.exception, OSError)
        self.assertIn("fixture late workflow summary write failed", str(result.exception))
        self.assertEqual("true", result.outputs["safe_to_continue"], "Exercise failure after optimistic step output")
        self.assert_manifest(case.bootstrap, "bootstrap-manifest.sha256")
        values = {"steps": {"handoff": {"outcome": "failure", "outputs": result.outputs},
                             "evidence": {"outcome": "success", "outputs": {"artifact-id": "947"}}}}
        block = job_block("selected_host")
        safe = expression_value(yaml_value(block, "safe_to_continue", 6), values)
        self.assertIs(safe, False, "Failed handoff must not export a safe job outcome")
        uploaded = expression_value(yaml_value(block, "artifact_uploaded", 6), values)
        self.assertIs(uploaded, True, "Retaining already-proved evidence is still allowed")

    def test_actual_native_python_run_literals_fit_actions_limit_for_one_selected_host(self):
        for name in ("allocate", "keep_java21", "run_host", "handoff"):
            with self.subTest(name=name):
                body = python_body(name)
                self.assertLessEqual(len(body.encode("utf-8")), 21000,
                                     "GitHub run script exceeds its limit; fixtures must not validate an unrunnable workflow")
                ast.parse(body, filename=str(WORKFLOW) + ":" + name)
        self.assertEqual(re.findall(r"^  ([a-z][a-z0-9_]*):\s*$", TEXT.split("\njobs:\n", 1)[1], re.MULTILINE),
                         ["selected_host"])
        self.assertNotIn("matrix:", TEXT)
        self.assertNotIn("continue-on-error:", TEXT)
        self.assertIn("cancel-in-progress: false", TEXT)
        self.assertNotIn("needs:", TEXT)
        block = job_block("selected_host")
        self.assertIn("# Run revision: 23.", TEXT)
        self.assertEqual(yaml_value(block, "name", 4), "Audit native Intel owned Flow helper")
        self.assertEqual(yaml_value(block, "runs-on", 4), "macos-15-intel")
        self.assertEqual(yaml_value(block, "shell", 8), "python3 {0}")
        self.assertEqual(yaml_value(block, "P2PKIT_AUDIT_ROLE", 6), "macos-x64")
        self.assertEqual(yaml_value(block, "P2PKIT_AUDIT_SCOPE", 6), "apple-owned-helper")
        self.assertEqual(yaml_value(block, "P2PKIT_AUDIT_DRIVER_TIMEOUT_SECONDS", 6), '"8400"')
        self.assertEqual(yaml_value(block, "timeout-minutes", 4), "180")
        self.assertIn("        id: audit\n        timeout-minutes: 150\n        run: &run_host |", block)
        self.assertEqual(yaml_value(block, "DEVELOPER_DIR", 6), "/Applications/Xcode_26.3.app/Contents/Developer")

    def test_actual_artifact_output_requires_success_and_a_nonempty_upload_id(self):
        expression = yaml_value(job_block("selected_host"), "artifact_uploaded", 6)
        for outcome, identity in itertools.product(("success", "failure", "cancelled", "skipped", ""), ("947", "")):
            with self.subTest(outcome=outcome, identity=identity):
                values = {"steps": {"evidence": {"outcome": outcome, "outputs": {"artifact-id": identity}}}}
                self.assertEqual(expression_value(expression, values), outcome == "success" and bool(identity))
        self.assertIs(expression_value(expression, {"steps": {"evidence": {"outcome": "success", "outputs": {}}}}), False)
        self.assertIs(expression_value(expression, {"steps": {}}), False)

    def test_actual_upload_runs_after_failure_only_for_proved_paths_and_includes_hidden_evidence(self):
        block = anchored_step("evidence")
        expression = yaml_value(block, "if", 8)
        for allocation, bootstrap, handoff_outcome in itertools.product(
                ("success", "failure", "skipped", ""), ("/synthetic/bootstrap-evidence", ""),
                ("success", "failure", "cancelled")):
            with self.subTest(allocation=allocation, bootstrap=bootstrap, handoff_outcome=handoff_outcome):
                values = {"steps": {"allocate": {"outcome": allocation},
                                    "handoff": {"outcome": handoff_outcome, "outputs": {"bootstrap_path": bootstrap}}}}
                self.assertEqual(expression_value(expression, values, cancelled=True),
                                 allocation == "success" and bootstrap != "")
        self.assertEqual(yaml_value(block, "path", 10).splitlines(),
                         ["${{ steps.handoff.outputs.bootstrap_path }}", "${{ steps.handoff.outputs.driver_evidence_path }}"])
        self.assertEqual(yaml_value(block, "include-hidden-files", 10), "true")
        self.assertEqual(yaml_value(block, "if-no-files-found", 10), "error")
        self.assertEqual(yaml_value(block, "overwrite", 10), "false")
        self.assertRegex(yaml_value(block, "uses", 8), r"^actions/upload-artifact@[0-9a-f]{40}(?:\s|$)")
        self.assertEqual(yaml_value(job_block("selected_host"), "safe_to_continue", 6),
                         "${{ steps.handoff.outcome == 'success' && steps.handoff.outputs.safe_to_continue == 'true' }}")
        self.assertEqual(yaml_value(job_block("selected_host"), "artifact_id", 6),
                         "${{ steps.evidence.outputs['artifact-id'] }}")

    def test_handoff_itself_requires_successful_allocation_but_preserves_cancelled_driver_attempts(self):
        expression = yaml_value(anchored_step("handoff"), "if", 8)
        for allocation, bootstrap, state in itertools.product(("success", "failure", "skipped", ""),
                                                               ("/owned/bootstrap-evidence", ""), ("/owned/state", "")):
            with self.subTest(allocation=allocation, bootstrap=bootstrap, state=state):
                values = {"steps": {"allocate": {"outcome": allocation}},
                          "env": {"P2PKIT_AUDIT_BOOTSTRAP_DIR": bootstrap, "P2PKIT_AUDIT_STATE_DIR": state}}
                self.assertEqual(expression_value(expression, values, cancelled=True),
                                 allocation == "success" and bootstrap != "" and state != "")

    def test_workflow_keeps_exact_audit_trigger_read_only_permissions_and_nonpersisted_checkout(self):
        prefix = TEXT.split("\njobs:\n", 1)[0]
        self.assertIn("branches: [audit/complete-2026-09-04]", prefix)
        self.assertIn("paths: [.github/workflows/audit-host-validation.yml]", prefix)
        self.assertIn("permissions:\n  contents: read", prefix)
        for forbidden in ("pull_request:", "pull_request_target:", "workflow_dispatch:", "tags:", "contents: write"):
            self.assertNotIn(forbidden, TEXT)
        checkout = anchored_step("checkout")
        self.assertEqual(yaml_value(checkout, "ref", 10), "${{ github.sha }}")
        self.assertEqual(yaml_value(checkout, "fetch-depth", 10), "0")
        self.assertEqual(yaml_value(checkout, "persist-credentials", 10), "false")
        self.assertRegex(yaml_value(checkout, "uses", 8), r"^actions/checkout@[0-9a-f]{40}(?:\s|$)")

    def test_actual_allocation_creates_fresh_external_bootstrap_without_claiming_source_or_driver_state(self):
        case = Fixture(self, controls=False)
        allocations = []
        for _ in range(2):
            namespace = {"__name__": "__allocation_fixture__"}
            with mock.patch.dict(os.environ, case.environment, clear=True), \
                    mock.patch("platform.platform", return_value="Synthetic host fixture"), \
                    mock.patch("platform.machine", return_value="synthetic-architecture"), \
                    mock.patch("platform.python_version", return_value="synthetic-python"), \
                    mock.patch.object(subprocess, "Popen", side_effect=AssertionError("Unexpected native process")):
                exec(compile(python_body("allocate"), str(WORKFLOW) + ":allocate", "exec"), namespace)
            bootstrap, state = namespace["bootstrap"], namespace["state"]
            allocations.append(bootstrap)
            self.assertTrue(bootstrap.is_dir())
            self.assertEqual(bootstrap.name, "bootstrap-evidence")
            self.assertTrue(bootstrap.parent.name.startswith("p2pkit-audit-windows-x64-"))
            self.assertFalse(bootstrap.is_relative_to(case.root))
            self.assertEqual(state, bootstrap.parent / "state")
            self.assertFalse(state.exists(), "Only the admitted driver may create/own its state")
            record = json_file(bootstrap / "workflow-start.json")
            self.assertIs(record["sourceAdmitted"], False)
            self.assertEqual({key: record[key] for key in ("role", "requestedScope", "expectedCommit", "runId", "runAttempt")},
                             {key: case.allocation[key] for key in ("role", "requestedScope", "expectedCommit", "runId", "runAttempt")})
        self.assertNotEqual(*allocations)
        env_lines = Path(case.environment["GITHUB_ENV"]).read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(env_lines), 4)
        for bootstrap in allocations:
            self.assertIn("P2PKIT_AUDIT_BOOTSTRAP_DIR=" + str(bootstrap), env_lines)
            self.assertIn("P2PKIT_AUDIT_STATE_DIR=" + str(bootstrap.parent / "state"), env_lines)

    def test_actual_allocation_rejects_temp_under_checkout_without_creating_outputs(self):
        for nested in (False, True):
            with self.subTest(nested=nested):
                case = Fixture(self, controls=False)
                target = case.root / "temporary" if nested else case.root
                target.mkdir(exist_ok=True)
                case.environment["RUNNER_TEMP"] = str(target)
                with mock.patch.dict(os.environ, case.environment, clear=True):
                    with self.assertRaisesRegex(RuntimeError, "RUNNER_TEMP must be outside"):
                        exec(compile(python_body("allocate"), str(WORKFLOW) + ":allocate", "exec"), {})
                self.assertFalse(Path(case.environment["GITHUB_ENV"]).exists())
                self.assertEqual(list(target.glob("p2pkit-audit-*")), [])

    def test_actual_driver_body_runs_exact_checked_out_driver_in_process_with_owned_bootstrap_logs(self):
        for exit_code in (0, 7):
            with self.subTest(exit_code=exit_code):
                case = Fixture(self, controls=False, logs=False)
                driver = case.root / "scripts/run-audit-host.py"
                put(driver, b"# synthetic driver is intercepted, never executed\n")
                descriptors, calls = [], []
                stdout, stderr = io.StringIO(), io.StringIO()

                def dup(source, destination):
                    self.assertTrue(stat.S_ISREG(os.fstat(source).st_mode))
                    descriptors.append(destination)

                def run(path, **kwargs):
                    calls.append((path, kwargs))
                    self.assertEqual(sys.argv, [str(driver), case.role, "--timeout-seconds", "8400",
                                                "--scope", case.scope])
                    raise SystemExit(exit_code)

                with mock.patch.dict(os.environ, case.environment, clear=True), \
                        mock.patch.object(sys, "argv", ["fixture-parent"]), \
                        mock.patch.object(os, "dup2", side_effect=dup), \
                        mock.patch.object(os, "chdir") as chdir, \
                        mock.patch("runpy.run_path", side_effect=run), \
                        mock.patch.object(subprocess, "Popen", side_effect=AssertionError("No driver wrapper child")), \
                        contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                    with self.assertRaises(SystemExit) as failure:
                        exec(compile(python_body("run_host"), str(WORKFLOW) + ":run_host", "exec"), {})
                    self.assertEqual(failure.exception.code, exit_code)
                    chdir.assert_called_once_with(case.root)
                self.assertEqual(calls, [(str(driver), {"run_name": "__main__"})])
                self.assertEqual(descriptors, [1, 2])
                self.assertEqual((case.bootstrap / "driver.stdout.log").read_bytes(), b"")
                self.assertEqual((case.bootstrap / "driver.stderr.log").read_bytes(), b"")

    def test_missing_linked_driver_or_existing_logs_never_fall_back_to_another_script(self):
        for kind in ("missing", "linked", "old-log"):
            with self.subTest(kind=kind):
                case = Fixture(self, controls=False, logs=kind == "old-log")
                driver = case.root / "scripts/run-audit-host.py"
                if kind != "missing":
                    put(driver, b"# synthetic driver\n")
                with contextlib.ExitStack() as stack:
                    stack.enter_context(mock.patch.dict(os.environ, case.environment, clear=True))
                    dup = stack.enter_context(mock.patch.object(os, "dup2"))
                    run = stack.enter_context(mock.patch("runpy.run_path"))
                    stack.enter_context(mock.patch.object(subprocess, "Popen", side_effect=AssertionError("Unexpected native process")))
                    if kind == "linked":
                        original_is_symlink = Path.is_symlink

                        def is_symlink(path):
                            return path == driver or original_is_symlink(path)

                        # Model the predicate the workflow calls, not pathlib's version-specific stat internals.
                        stack.enter_context(mock.patch.object(Path, "is_symlink", new=is_symlink))
                    with self.assertRaises(FileExistsError if kind == "old-log" else RuntimeError):
                        exec(compile(python_body("run_host"), str(WORKFLOW) + ":run_host", "exec"), {})
                    dup.assert_not_called()
                    run.assert_not_called()
                if kind == "old-log":
                    self.assertEqual((case.bootstrap / "driver.stdout.log").read_bytes(), b"synthetic driver fixture only\n")


if __name__ == "__main__":
    unittest.main(verbosity=2)
