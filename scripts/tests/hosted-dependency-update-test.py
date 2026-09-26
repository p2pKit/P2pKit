#!/usr/bin/env python3
"""Offline DATA and source assertions, not a real manual/native invocation."""
import ast
import copy
import importlib.util
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "scripts/run-hosted-dependency-update.py"
spec = importlib.util.spec_from_file_location("dependency_update_controls", SOURCE)
M = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = M
spec.loader.exec_module(M)


def offline(event, _args):
    if event.startswith("socket.") or event in ("subprocess.Popen", "os.system", "os.exec", "os.posix_spawn",
                                               "ctypes.dlopen", "os.putenv", "os.unsetenv"):
        raise AssertionError("offline controls attempted observation or execution: " + event)


sys.addaudithook(offline)


class DataControls(unittest.TestCase):
    def setUp(self):
        self.request = {name: chr(ord("a") + index) * 40 for index, name in enumerate(sorted(M.REQUEST_KEYS))}
        self.env = {"GITHUB_ACTIONS": "true", "GITHUB_REPOSITORY": M.REPOSITORY,
            "GITHUB_EVENT_NAME": "workflow_dispatch", "RUNNER_ENVIRONMENT": "github-hosted",
            "GITHUB_JOB": "generate", "GITHUB_ACTOR": M.OWNER, "GITHUB_ACTOR_ID": M.OWNER_ID,
            "GITHUB_TRIGGERING_ACTOR": M.OWNER, "GITHUB_REF": "refs/heads/main",
            "GITHUB_SHA": self.request["controller_sha"], "GITHUB_WORKFLOW_SHA": self.request["controller_sha"],
            "GITHUB_WORKFLOW_REF": M.REPOSITORY + "/" + M.WORKFLOW + "@refs/heads/main",
            "GITHUB_RUN_ID": "123", "GITHUB_RUN_ATTEMPT": "1"}

    def test_exact_manual_data_and_foundation_ref(self):
        self.assertEqual(M.request_data(self.request, self.env)["runId"], "123")
        changed = dict(self.env, GITHUB_REF="refs/heads/work/release-foundation-example")
        changed["GITHUB_WORKFLOW_REF"] = M.REPOSITORY + "/" + M.WORKFLOW + "@" + changed["GITHUB_REF"]
        self.assertEqual(M.request_data(self.request, changed)["ref"], changed["GITHUB_REF"])

    def test_missing_extra_and_nonsha_request(self):
        for key in self.request:
            for value in ("main", "A" * 40, "1" * 39, "1" * 41, 1, None, "a" * 40 + "\n"):
                with self.subTest(key=key, value=value), self.assertRaises(M.UpdateError):
                    M.request_data({**self.request, key: value}, self.env)
        for changed in ({**self.request, "version": "1.0.0"}, {key: value for key, value in self.request.items()
                                                               if key != "candidate_tree"}):
            with self.assertRaises(M.UpdateError):
                M.request_data(changed, self.env)

    def test_real_environment_fields_are_not_optional(self):
        for key in self.env:
            with self.subTest(key=key), self.assertRaises(M.UpdateError):
                M.request_data(self.request, {name: value for name, value in self.env.items() if name != key})

    def test_reject_other_identity_origin_actor_event(self):
        for key, value in (("GITHUB_EVENT_NAME", "push"), ("GITHUB_EVENT_NAME", "pull_request"),
                           ("RUNNER_ENVIRONMENT", "self-hosted"), ("GITHUB_REPOSITORY", "fork/P2pKit"),
                           ("GITHUB_ACTOR", "other"), ("GITHUB_TRIGGERING_ACTOR", "other"),
                           ("GITHUB_ACTOR_ID", "1"), ("GITHUB_JOB", "complete-gate")):
            with self.subTest(key=key), self.assertRaises(M.UpdateError):
                M.request_data(self.request, {**self.env, key: value})

    def test_reject_tag_campaign_pr_and_mismatched_controller(self):
        for ref in ("refs/tags/v1.0.0", "refs/pull/1/merge", "refs/heads/work/nonphysical-integration-test", "main"):
            changed = {**self.env, "GITHUB_REF": ref, "GITHUB_WORKFLOW_REF": M.REPOSITORY + "/" + M.WORKFLOW + "@" + ref}
            with self.subTest(ref=ref), self.assertRaises(M.UpdateError):
                M.request_data(self.request, changed)
        for key in ("GITHUB_SHA", "GITHUB_WORKFLOW_SHA", "GITHUB_WORKFLOW_REF"):
            with self.subTest(key=key), self.assertRaises(M.UpdateError):
                M.request_data(self.request, {**self.env, key: "f" * 40})

    def test_run_attempt_positive_canonical_numbers(self):
        for key in ("GITHUB_RUN_ID", "GITHUB_RUN_ATTEMPT"):
            for value in ("0", "01", "-1", "1.0", " 1", "1\n", "1" * 21, True):
                with self.subTest(key=key, value=value), self.assertRaises(M.UpdateError):
                    M.request_data(self.request, {**self.env, key: value})

    def test_policy_exact_owner_and_key_pins(self):
        raw = (ROOT / M.POLICY_PATH).read_bytes()
        policy = M.parsed(raw)
        actual = M.policy_data(raw, policy["notBefore"], M.JOB_SECONDS)
        self.assertEqual(actual["recipient"]["fingerprint"], M.FINGERPRINT)
        self.assertEqual(M.digest(actual["recipient"]["publicKey"].encode("ascii")), M.KEY_SHA256)
        self.assertEqual(actual["retrievalOwner"], M.OWNER)
        for changed in (raw + b"\n", raw.replace(M.OWNER.encode(), b"another-owner"),
                        raw.replace(M.FINGERPRINT.encode(), b"F" * 40)):
            with self.assertRaises(M.UpdateError):
                M.policy_data(changed, policy["notBefore"], M.JOB_SECONDS)

    def test_policy_finite_expiry_and_full_reserve(self):
        raw = (ROOT / M.POLICY_PATH).read_bytes()
        policy = M.parsed(raw)
        end, start = policy["expiresAt"], policy["notBefore"]
        self.assertIsInstance(M.policy_data(raw, end - M.UPLOAD_SECONDS - 1, M.UPLOAD_SECONDS), dict)
        for now, reserve in ((start - 1, 0), (end, 0), (end - M.UPLOAD_SECONDS, M.UPLOAD_SECONDS),
                             (start, -1), (start, M.JOB_SECONDS + 1), (float("nan"), 0), (True, 0)):
            with self.subTest(now=now, reserve=reserve), self.assertRaises(M.UpdateError):
                M.policy_data(raw, now, reserve)

    def test_environment_does_not_inherit_credentials_or_config(self):
        poisoned = {**self.env, "PATH": "/tools", "JAVA_HOME": "/jdk17", "P2PKIT_AUDIT_JDK21": "/jdk21",
            "DEVELOPER_DIR": "/xcode", "ANDROID_HOME": "/android", "GH_TOKEN": "not-a-token",
            "GITHUB_TOKEN": "not-a-token", "ACTIONS_RUNTIME_TOKEN": "not-a-token", "GITHUB_ENV": "/outer/env",
            "GITHUB_OUTPUT": "/outer/output", "JAVA_OPTS": "arbitrary", "GRADLE_OPTS": "arbitrary",
            "GIT_CONFIG_COUNT": "1", "BASH_ENV": "/outer/script", "SSH_AUTH_SOCK": "/outer/socket",
            "HOME": "/outer/home", "ORG_GRADLE_PROJECT_signingInMemoryKey": "not-a-key"}
        saved = dict(poisoned)
        actual = M.child_environment(poisoned, Path("/private/new"))
        self.assertEqual(poisoned, saved)
        for key in set(poisoned) - set(M.IDENTITY_ENV) - set(M.TOOL_ENV) - {"HOME"}:
            self.assertNotIn(key, actual)
        self.assertEqual(actual["HOME"], "/private/new/home")
        self.assertTrue(set(M.NATIVE_OWNER_ENV).isdisjoint(actual))
        self.assertEqual(actual["GITHUB_SHA"], self.env["GITHUB_SHA"])
        self.assertEqual(actual["GIT_CONFIG_NOSYSTEM"], "1")

    def baseline(self):
        row = {"gitMode": "100644", "mode": 0o644, "gitBlob": "a" * 40, "uid": 501, "sha256": "b" * 64}
        return {path: dict(row) for path in ("build.gradle.kts", "library/core/gradle.lockfile", "gradle/verification-metadata.xml")}

    def generated(self):
        before = self.baseline()
        after = copy.deepcopy(before)
        for path in ("library/core/gradle.lockfile", "gradle/verification-metadata.xml"):
            after[path]["sha256"] = "c" * 64
        return before, after

    def test_only_original_tracked_content_can_change(self):
        before, after = self.generated()
        self.assertEqual(M.delta_data(before, after, staged=b"", untracked=b""),
                         ["gradle/verification-metadata.xml", "library/core/gradle.lockfile"])

    def test_no_added_deleted_staged_or_untracked_source(self):
        before, after = self.generated()
        for changed in ({**after, "new.lockfile": after["library/core/gradle.lockfile"]},
                        {path: row for path, row in after.items() if path != "build.gradle.kts"}):
            with self.assertRaises(M.UpdateError):
                M.delta_data(before, changed, staged=b"", untracked=b"")
        for staged, untracked in ((b"staged", b""), (b"", b"unknown")):
            with self.assertRaises(M.UpdateError):
                M.delta_data(before, after, staged=staged, untracked=untracked)

    def test_type_mode_index_or_owner_change_refused(self):
        before, after = self.generated()
        for field, value in (("gitMode", "120000"), ("mode", 0o755), ("gitBlob", "d" * 40), ("uid", 0)):
            changed = copy.deepcopy(after)
            changed["library/core/gradle.lockfile"][field] = value
            with self.subTest(field=field), self.assertRaises(M.UpdateError):
                M.delta_data(before, changed, staged=b"", untracked=b"")

    def test_other_product_source_cannot_change(self):
        before, after = self.generated()
        after["build.gradle.kts"]["sha256"] = "e" * 64
        with self.assertRaises(M.UpdateError):
            M.delta_data(before, after, staged=b"", untracked=b"")

    def test_no_empty_or_lock_only_candidate_pass(self):
        before, after = self.generated()
        for changed in (before, {**after, "gradle/verification-metadata.xml": before["gradle/verification-metadata.xml"]}):
            with self.assertRaises(M.UpdateError):
                M.delta_data(before, changed, staged=b"", untracked=b"")

    def test_duplicate_nonfinite_and_oversize_json_refused(self):
        for raw in (b'{"a":1,"a":2}', b'{"a":NaN}', b'{"a":Infinity}', b"{} ", b"", b"{bad"):
            with self.subTest(raw=raw), self.assertRaises(M.UpdateError):
                M.parsed(raw, limit=2 if raw == b"{} " else M.FILE_LIMIT)

    def test_budgets_leave_real_finalization_and_upload_headroom(self):
        self.assertEqual((M.PRODUCT_SECONDS, M.STOP_SECONDS, M.EXPORT_SECONDS), (7200, 120, 120))
        self.assertGreater(M.ENTRY_RESERVE, M.WRITER_RESERVE)
        self.assertGreater(M.WRITER_RESERVE, M.PRODUCT_SECONDS + M.STOP_SECONDS)
        self.assertLess(M.ENTRY_RESERVE, M.JOB_SECONDS)
        self.assertEqual(M.UPLOAD_SECONDS, 22 * 60)

    def provenance_fixture(self):
        def xml(version, value):
            return ('<verification-metadata xmlns="' + M.VERIFICATION_NAMESPACE + '" xmlns:xsi="' + M.XSI_NAMESPACE +
                '" xsi:schemaLocation="' + M.VERIFICATION_SCHEMA + '"><configuration><verify-metadata>true</verify-metadata>'
                '<verify-signatures>false</verify-signatures></configuration><components>'
                '<component group="example" name="library" version="' + version +
                '"><artifact name="library.jar"><sha256 value="' + value +
                '"/></artifact></component></components></verification-metadata>').encode("ascii")
        old, new = xml("1.0", "a" * 64), xml("1.1", "b" * 64)
        row = ("REVIEWED example:library:1.1 library.jar sha256=" + "b" * 64 + " signer=" + "C" * 40 +
               " evidence=signature-bound-bytes repository=https://repo.maven.apache.org/maven2\n").encode("ascii")
        end = ("RESULT: PASS — reviewed 1 newly admitted artifacts by exact SHA-256 and publisher provenance; "
               "unsigned Gradle metadata is structurally bound to a trusted implementation JAR\n").encode("utf-8")
        return old, new, row, end

    def test_public_provenance_is_roster_bound_not_raw_logs_or_attribution_approval(self):
        old, new, row, end = self.provenance_fixture()
        log = b"not-public log: /private/path\n\xff\n" + row + end
        result = M.provenance_data(log, old, new)
        self.assertEqual(result["sourceLogSha256"], M.digest(log))
        self.assertEqual(result["publisherKeyAttribution"], "INDEPENDENT_REVIEW_REQUIRED")
        self.assertEqual(result["records"][0]["signer"], "C" * 40)
        self.assertNotIn(b"/private/path", M.encoded(result))
        self.assertNotIn(b"not-public", M.encoded(result))

    def test_public_provenance_rejects_incomplete_forged_duplicate_or_unbounded_fields(self):
        old, new, row, end = self.provenance_fixture()
        for log in (row, end, row + row + end, row + end + end,
                    row.replace(b"signer=" + b"C" * 40, b"signer=none") + end,
                    row.replace(b"b" * 64, b"d" * 64) + end,
                    row.replace(b"https://repo.maven.apache.org/maven2", b"https://untrusted.invalid/maven2") + end,
                    row.replace(b"signature-bound-bytes", b"claimed") + end,
                    row.replace(b"library.jar", b"/private/path") + end,
                    row + end.replace(b"reviewed 1", b"reviewed 2")):
            with self.subTest(log=M.digest(log)), self.assertRaises(M.UpdateError):
                M.provenance_data(log, old, new)
        with self.assertRaises(M.UpdateError):
            M.provenance_data(row + end, new, new)

    def test_verification_data_refuses_entities_missing_or_unsafe_components(self):
        old, new, row, end = self.provenance_fixture()
        self.assertEqual(len(M.verification_entries(new)), 1)
        for raw in (b"", b"<bad", b"<verification-metadata/>",
                    b'<!DOCTYPE root [<!ENTITY x "unsafe">]>' + new,
                    new.replace(b'name="library"', b'name="../private"'),
                    new.replace(b"b" * 64, b"not-a-sha256")):
            with self.subTest(raw=raw), self.assertRaises(M.UpdateError):
                M.verification_entries(raw)


    def test_actual_public_metadata_uses_the_supported_namespace(self):
        raw = (ROOT / "gradle/verification-metadata.xml").read_bytes()
        self.assertIn(('xmlns="' + M.VERIFICATION_NAMESPACE + '"').encode("ascii"), raw)
        # The maintained source keeps one literal SHA-256 per artifact. This
        # independent raw count catches a silently skipped namespace/subtree,
        # without freezing today's dependency roster against future updates.
        self.assertEqual(len(M.verification_entries(raw)), raw.count(b'<sha256 value="'))
        self.assertGreater(len(M.verification_entries(raw)), 0)

    def test_namespace_schema_and_mixed_subtree_refused(self):
        _, xml, _, _ = self.provenance_fixture()
        ns = M.VERIFICATION_NAMESPACE.encode("ascii")
        for raw in (xml.replace(b'xmlns="' + ns + b'"', b''),
                    xml.replace(b'xmlns="' + ns + b'"', b'xmlns="https://invalid.example/schema"'),
                    xml.replace(b'dependency-verification-1.4.xsd', b'dependency-verification-1.3.xsd'),
                    xml.replace(b'<components>', b'<components xmlns="">'),
                    xml.replace(b'<artifact name=', b'<artifact xmlns="https://invalid.example/schema" name='),
                    xml.replace(b'<sha256 value=', b'<sha256 xmlns="" value=')):
            with self.subTest(raw=M.digest(raw)), self.assertRaises(M.UpdateError):
                M.verification_entries(raw)

    def test_exact_sha256_structure_rejects_missing_duplicate_or_weak_rows(self):
        _, xml, _, _ = self.provenance_fixture()
        checksum = b'<sha256 value="' + b'b' * 64 + b'"/>'
        artifact = b'<artifact name="library.jar">' + checksum + b'</artifact>'
        for raw in (xml.replace(b'>true</verify-metadata>', b'>false</verify-metadata>'),
                    xml.replace(b'>false</verify-signatures>', b'>true</verify-signatures>'),
                    xml.replace(checksum, b''), xml.replace(checksum, checksum + checksum),
                    xml.replace(artifact, artifact + artifact), xml.replace(b'<sha256 ', b'<sha1 '),
                    xml.replace(b'<components>', b'<components><trusted-artifacts/>'),
                    xml.replace(b'<components>', b'<components>unexpected'),
                    xml.replace(b'<configuration>', b'<configuration unknown="true">')):
            with self.subTest(raw=M.digest(raw)), self.assertRaises(M.UpdateError):
                M.verification_entries(raw)

    def command_fixture(self, code):
        source = {"commit": "a" * 40, "tree": "b" * 40, "status": "", "diffSha256": M.digest(b"")}
        context = {"id": "c" * 32, "source": source}
        invocation, purpose, argv = "d" * 32, "dependency-maintenance-generator", ["/candidate/fixed", "e" * 40]
        receipt = {"schema": 1, "id": invocation, "jobId": context["id"], "kind": "command", "purpose": purpose,
            "requestedArgv": argv, "sourceBefore": source, "sourceAfter": source, "sourceUnchanged": True,
            "productExitCode": code, "finalExitCode": code, "stopExitCode": 0, "ownedSurvivors": [], "errors": [],
            "ownership": {"discoveryErrors": []}}
        return receipt, context, invocation, purpose, argv

    def test_original_return_data_distinguishes_success_and_failed_product(self):
        for code in (0, 1, 2, 123):
            args = self.command_fixture(code)
            self.assertEqual(M.command_return_data(code, *args), "SUCCESS" if code == 0 else "FAILED_PRODUCT")

    def test_failed_diagnostics_refuse_timeout_reserved_signal_and_noninteger_exits(self):
        for code in (124, 125, 126, 127, 128, 137, 143, 255, -9, 256, None, True, 1.0):
            with self.subTest(code=code), self.assertRaises(M.UpdateError):
                M.command_return_data(code, *self.command_fixture(code))

    def test_failed_diagnostics_require_unchanged_source_stop_and_known_retirement(self):
        receipt, context, invocation, purpose, argv = self.command_fixture(1)
        for name, value in (("id", "f" * 32), ("jobId", "f" * 32), ("kind", "gradle"),
                            ("purpose", "another"), ("requestedArgv", ["another"]), ("schema", True),
                            ("sourceBefore", {}), ("sourceAfter", {}), ("sourceUnchanged", False),
                            ("productExitCode", 0), ("finalExitCode", 125), ("stopExitCode", 1),
                            ("stopExitCode", False), ("ownedSurvivors", [{"status": "UNKNOWN"}]),
                            ("errors", ["stream close failed"]), ("ownership", {}),
                            ("ownership", {"discoveryErrors": ["failed"]}),
                            ("cancelledSignals", [15]), ("cancelRequested", True)):
            with self.subTest(name=name, value=value), self.assertRaises(M.UpdateError):
                M.command_return_data(1, {**receipt, name: value}, context, invocation, purpose, argv)
        for name in receipt:
            with self.subTest(missing=name), self.assertRaises(M.UpdateError):
                M.command_return_data(1, {key: value for key, value in receipt.items() if key != name},
                                      context, invocation, purpose, argv)

    def failed_fixture(self):
        env = {**self.env, "P2PKIT_DEPENDENCY_GENERATOR_OUTCOME": "failure", "P2PKIT_DEPENDENCY_SUCCESS_SHA256": ""}
        value = {"schema": 1, "scope": M.FAILED_SCOPE, "request": self.request,
            "github": M.request_data(self.request, self.env),
            "files": {"failed-encrypted/" + name: {} for name in M.ENCRYPTED_FILES},
            "policySha256": M.POLICY_SHA256, "exportManifestSha256": "1" * 64,
            "producerReturn": "FAILED_PRODUCT_AFTER_KNOWN_COMMAND_AND_EXPORT_RETURN", "productExitCode": 1,
            "purpose": "dependency-maintenance-generator", "receiptSha256": "2" * 64}
        return value, env

    def test_failed_return_requires_actual_failure_and_no_success_output(self):
        value, env = self.failed_fixture()
        self.assertEqual(M.failed_return_data(value, env), value)
        for outcome in ("success", "cancelled", "skipped", "", None):
            with self.subTest(outcome=outcome), self.assertRaises(M.UpdateError):
                M.failed_return_data(value, {**env, "P2PKIT_DEPENDENCY_GENERATOR_OUTCOME": outcome})
        with self.assertRaises(M.UpdateError):
            M.failed_return_data(value, {**env, "P2PKIT_DEPENDENCY_SUCCESS_SHA256": "a" * 64})

    def test_failed_return_cannot_be_success_candidate_or_another_source(self):
        value, env = self.failed_fixture()
        for key, changed in (("scope", M.SCOPE), ("schema", True), ("productExitCode", 0),
                             ("productExitCode", 124), ("productExitCode", 125), ("productExitCode", True),
                             ("policySha256", "f" * 64), ("exportManifestSha256", "not-a-hash"),
                             ("receiptSha256", "a" * 63), ("purpose", "/private/path"),
                             ("github", {**value["github"], "runAttempt": "2"}),
                             ("producerReturn", "SUCCESS_AFTER_KNOWN_COMMAND_AND_EXPORT_RETURN"),
                             ("files", {"public/generated-dependencies.patch": {}})):
            with self.subTest(key=key, value=changed), self.assertRaises(M.UpdateError):
                M.failed_return_data({**value, key: changed}, env)
        for changed in ({**value, "patch": "not-a-candidate"}, {key: item for key, item in value.items() if key != "files"}):
            with self.assertRaises(M.UpdateError):
                M.failed_return_data(changed, env)


class SourceControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = SOURCE.read_text()
        cls.tree = ast.parse(cls.source)
        cls.functions = {node.name: ast.get_source_segment(cls.source, node) for node in cls.tree.body
                         if isinstance(node, ast.FunctionDef)}

    def test_native_command_retains_immutable_controller_and_stop(self):
        text = self.functions["owned_command"]
        self.assertIn('cwd=str(ROOT), wrapper=str(ROOT / "gradlew")', text)
        self.assertIn('kind="command"', text)
        self.assertIn('stop_timeout=STOP_SECONDS', text)
        self.assertIn('code = runner.execute(args)', text)
        self.assertIn('with environment({**os.environ, "P2PKIT_AUDIT_STATE_DIR": str(parent / "state")})', text)
        self.assertLess(text.index("code = runner.execute(args)"), text.index("command_return_data("))
        checks = self.functions["command_return_data"]
        for field in ("sourceBefore", "sourceAfter", "sourceUnchanged", "ownedSurvivors", "errors", "discoveryErrors",
                      "productExitCode", "stopExitCode", "finalExitCode", "cancelledSignals", "cancelRequested"):
            self.assertIn(field, checks)

    def test_key_validation_precedes_all_owned_commands_and_crypto_is_after_capture(self):
        text = self.functions["generate"]
        self.assertLess(text.index("exporter.validate_recipient("), text.index("owned_command("))
        self.assertLess(text.index('for name in ("controller.stdout", "controller.stderr")'),
                        text.index("exporter.export_encrypted("))
        self.assertLess(text.index("exporter.export_encrypted("), text.index('write_new(parent / ("generator-success.json"'))
        self.assertIn('source_commit=request["controller_sha"], source_tree=request["controller_tree"]', text)
        self.assertIn('str(candidate / "scripts/prepare-dependency-update.sh")', text)
        self.assertIn("with environment(safe_environment)", text)
        self.assertIn("contextlib.redirect_stdout(out), contextlib.redirect_stderr(err)", text)

    def test_no_private_exporter_release_or_cache_entry(self):
        for forbidden in ("_export_bound_manifest", "cache.save", "cache.restore", "bootstrap.admit", "Admission(",
                          "--write-verification-metadata", "--write-locks", "secret-key.asc", "gh release", "git tag"):
            self.assertNotIn(forbidden, self.source)
        self.assertIn('"scripts/prepare-dependency-update.sh"', self.source)

    def test_successful_step_return_files_and_policy_checked_before_and_after_upload(self):
        text = self.functions["guard_upload"]
        self.assertIn('P2PKIT_DEPENDENCY_GENERATOR_OUTCOME") == "success"', text)
        self.assertIn("digest(raw) == expected", text)
        self.assertIn("budget(allocation, 0 if after else UPLOAD_SECONDS)", text)
        self.assertIn('success["files"][group + "/" + name]', text)
        self.assertIn('P2PKIT_" + group + "_OUTCOME") == "success"', text)

    def test_only_closed_product_exception_can_reach_failure_export(self):
        text = self.functions["generate"]
        node = next(node for node in self.tree.body if isinstance(node, ast.FunctionDef) and node.name == "generate")
        handlers = [handler for item in ast.walk(node) if isinstance(item, ast.Try) for handler in item.handlers]
        self.assertEqual(len(handlers), 1)
        self.assertEqual(ast.unparse(handlers[0].type), "ClosedProductFailure")
        self.assertIn('"FAILED_CONTROLLER_CHANGED"', text)
        self.assertLess(text.index("except ClosedProductFailure as original:"), text.index("os.fsync(stream.fileno())"))
        self.assertLess(text.index('for name in ("controller.stdout", "controller.stderr")'),
                        text.index("exporter.export_encrypted("))
        self.assertIn('encrypted_group = "failed-encrypted" if failed is not None else "encrypted"', text)
        self.assertIn('("successSha256=" if failed is None else "failedProductSha256=")', text)
        self.assertIn("return failed.code", text)
        self.assertIn("return generate()", self.functions["main"])

    def test_failure_guards_recheck_original_hash_bytes_expiry_and_upload_return(self):
        text = self.functions["guard_failed_upload"]
        self.assertIn('raw = read_file(parent / "generator-failed-product.json", MIB)[0]', text)
        self.assertIn("digest(raw) == expected", text)
        self.assertIn("failed_return_data(parsed(raw), os.environ)", text)
        self.assertIn("budget(allocation, 0 if after else UPLOAD_SECONDS)", text)
        self.assertIn('not os.path.lexists(parent / "generator-success.json")', text)
        self.assertIn('failed["files"]["failed-encrypted/" + name]', text)
        self.assertIn('P2PKIT_FAILED_ENCRYPTED_OUTCOME") == "success"', text)
        self.assertNotIn("export_encrypted", text)


if __name__ == "__main__":
    unittest.main()
