#!/usr/bin/env python3
"""Offline DATA and source assertions, not a real manual/native invocation."""
import ast
import copy
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

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


class DarwinStartupEnvironmentControls(unittest.TestCase):
    """Source-bound synthetic controls, not a CoreFoundation/native execution claim."""

    KEY = "__CF_USER_TEXT_ENCODING"

    class Poison:
        def forbidden(self, *_args, **_kwargs):
            raise AssertionError("startup environment inspected poisoned input")
        __str__ = __repr__ = __format__ = __int__ = __index__ = forbidden
        __eq__ = __ne__ = __lt__ = __le__ = __gt__ = __ge__ = forbidden

    def setUp(self):
        self.parent = Path("/controlled/new")
        self.inherited = {"GITHUB_SHA": "a" * 40, "PATH": "/tools", "JAVA_HOME": "/jdk17",
            "P2PKIT_AUDIT_JDK21": "/jdk21", "DEVELOPER_DIR": "/xcode", "ANDROID_HOME": "/android"}
        self.prior = {**self.inherited, "HOME": str(self.parent / "home"), "TMPDIR": str(self.parent / "tmp"),
            "XDG_CONFIG_HOME": str(self.parent / "home/config"), "XDG_CACHE_HOME": str(self.parent / "home/cache"),
            "GNUPGHOME": str(self.parent / "home/gnupg"), "GH_CONFIG_DIR": str(self.parent / "home/gh"),
            "KONAN_DATA_DIR": str(self.parent / "konan"), "ANDROID_USER_HOME": str(self.parent / "android-user"),
            "PYTHONDONTWRITEBYTECODE": "1", "PYTHONUNBUFFERED": "1", "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": M.os.devnull, "GIT_TERMINAL_PROMPT": "0", "LC_ALL": "C", "TZ": "UTC"}

    def construct(self, env, uid, platform="darwin"):
        with patch.object(M.sys, "platform", platform), \
                patch.object(M.os, "getuid", return_value=uid, create=True) as getuid, \
                patch.object(M.os, "geteuid", side_effect=AssertionError("effective UID is not the cache key"),
                             create=True) as geteuid, \
                patch.object(M.sys, "stdout") as stdout, patch.object(M.sys, "stderr") as stderr:
            try:
                return M.child_environment(env, self.parent)
            finally:
                if platform == "darwin":
                    getuid.assert_called_once_with()
                else:
                    getuid.assert_not_called()
                geteuid.assert_not_called()
                stdout.write.assert_not_called()
                stderr.write.assert_not_called()

    def test_darwin_synthesizes_exact_real_uid_roman_us_cache_before_launch(self):
        for uid, value in ((0, "0x0:0:0"), (501, "0x1F5:0:0"), (0xABCD, "0xABCD:0:0"),
                           (0x7FFFFFFF, "0x7FFFFFFF:0:0")):
            with self.subTest(uid=uid):
                actual = self.construct(self.inherited, uid)
                self.assertEqual(actual, {**self.prior, self.KEY: value})
        self.assertNotIn(self.KEY, M.IDENTITY_ENV)
        self.assertNotIn(self.KEY, M.TOOL_ENV)

    def test_caller_cf_and_unapproved_inputs_are_not_read_inherited_or_mutated(self):
        key = self.KEY

        class CallerEnvironment(dict):
            def __getitem__(self, name):
                if name == key:
                    raise AssertionError("caller CF value must not be read")
                return super().__getitem__(name)

            def get(self, name, default=None):
                if name == key:
                    raise AssertionError("caller CF value must not be read")
                return super().get(name, default)

        for index, value in enumerate((None, "0xDEAD:99:99", self.Poison())):
            env = CallerEnvironment({**self.inherited, "HOME": "/unapproved/home", "LC_ALL": "unapproved",
                "GH_TOKEN": self.Poison(), "GITHUB_TOKEN": self.Poison(), "GITHUB_ENV": "/unapproved/env",
                "JAVA_OPTS": "unapproved", "SDKROOT": "/unapproved/sdk", "__PYVENV_LAUNCHER__": "unapproved",
                **{name: "unapproved-owner" for name in M.NATIVE_OWNER_ENV}})
            if value is not None:
                env[key] = value
            before = tuple(dict.items(env))
            with self.subTest(case=index):
                self.assertEqual(self.construct(env, 501), {**self.prior, key: "0x1F5:0:0"})
                after = tuple(dict.items(env))
                self.assertEqual(len(after), len(before))
                for old, new in zip(before, after):
                    self.assertIs(new[0], old[0])
                    self.assertIs(new[1], old[1])

    def test_signed_exact_int_uid_guard_refuses_before_formatting_or_output(self):
        class IntSubclass(int):
            __format__ = __repr__ = __str__ = DarwinStartupEnvironmentControls.Poison.forbidden
            __lt__ = __le__ = __gt__ = __ge__ = DarwinStartupEnvironmentControls.Poison.forbidden

        invalid = (True, False, -1, 0x80000000, 501.0, "501", None, self.Poison(), IntSubclass(501))
        for index, value in enumerate(invalid):
            with self.subTest(case=index):
                with self.assertRaises(M.UpdateError) as caught:
                    self.construct(self.inherited, value)
                self.assertEqual(caught.exception.args, ("CF_USER_ENCODING_UID",))

    def test_non_darwin_keeps_prior_environment_without_any_uid_query(self):
        env = {**self.inherited, self.KEY: self.Poison(), "SDKROOT": "unapproved"}
        for platform in ("linux", "win32", "freebsd14", "darwin-not-exact"):
            with self.subTest(platform=platform):
                self.assertEqual(self.construct(env, self.Poison(), platform), self.prior)


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

    def candidate_report_fixture(self, code=0):
        """Tiny DATA/call fixture, not real report copying or native retirement."""
        temporary = tempfile.TemporaryDirectory(prefix="p2pkit-candidate-report-controls-")
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name).resolve(strict=True)
        candidate, state = root / "candidate", root / "state"
        receipt, context, invocation, _, _ = self.command_fixture(code)
        receipt["sourceBefore"] = receipt["sourceAfter"] = {
            **context["source"], "commit": self.request["controller_sha"], "tree": self.request["controller_tree"]}
        candidate_source = {**context["source"], "commit": self.request["candidate_sha"],
                            "tree": self.request["candidate_tree"]}
        records = state / "evidence/maintenance"
        for path in (candidate, state, state / "evidence", records, state / "evidence" / invocation):
            path.mkdir(mode=0o700)
        receipt_raw = M.encoded(receipt)
        M.write_new(state / "evidence" / invocation / "receipt.json", receipt_raw)
        label = "library/example/build/test-results/jvmTest/TEST-example.xml"
        baseline = {label: {"sha256": M.digest(b"old synthetic report"), "bytes": 20}}
        M.write_new(records / "candidate-report-baseline.json", M.encoded(baseline))

        class ReportRunner:
            def __init__(self):
                self.calls, self.error = [], None
                self.source = {**candidate_source, "status": " M gradle/verification-metadata.xml\n",
                               "diffSha256": M.digest(b"synthetic dependency delta")}
                self.retained = [{"source": label, "sha256": M.digest(b"new synthetic report"), "bytes": 20,
                    "classification": "changed-since-admission", "retained": "reports/" + label}]
                self.manifest = {"schema": 1, "records": copy.deepcopy(self.retained),
                    "limitation": "Changed bytes are not proof of test execution; use the unchanged product assessor."}

            def source_snapshot(self, root):
                self.calls.append(("source_snapshot", root))
                return copy.deepcopy(self.source)

            def retain_reports(self, root, state, original, before, anchor):
                self.calls.append(("retain_reports", root, state, original, before, anchor))
                if self.error is not None:
                    raise self.error
                M.write_new(anchor / "report-manifest.json", M.encoded(self.manifest))
                return copy.deepcopy(self.retained)

        return {"runner": ReportRunner(), "candidate": candidate, "state": state, "records": records,
            "request": copy.deepcopy(self.request), "candidate_source": candidate_source, "baseline": baseline,
            "receipt": receipt, "receipt_hash": M.digest(receipt_raw)}

    def test_candidate_report_binding_preserves_success_and_closed_failure_identity(self):
        for code in (0, 1, 123):
            with self.subTest(code=code):
                args = self.candidate_report_fixture(code)
                runner, records = args["runner"], args["records"]
                anchor = records / "candidate-reports"
                before = copy.deepcopy({key: args[key] for key in ("request", "candidate_source", "baseline", "receipt")})
                receipt_path = args["state"] / "evidence" / args["receipt"]["id"] / "receipt.json"
                receipt_raw = receipt_path.read_bytes()
                baseline_raw = (records / "candidate-report-baseline.json").read_bytes()
                manifest_raw = M.encoded(runner.manifest)
                expected = {"schema": 1, "scope": "MANUAL_DEPENDENCY_CANDIDATE_REPORT_CUSTODY_V1",
                    "request": before["request"], "candidateBefore": before["candidate_source"],
                    "candidateAfter": copy.deepcopy(runner.source), "invocationId": before["receipt"]["id"],
                    "purpose": "dependency-maintenance-generator", "productExitCode": code,
                    "receiptSha256": M.digest(receipt_raw), "beforeManifestSha256": M.digest(baseline_raw),
                    "afterManifestSha256": M.digest(manifest_raw),
                    "limitation": "Retained report bytes are diagnostics, not candidate or test acceptance."}
                self.assertEqual(M.retain_candidate_reports(**args), expected)
                self.assertEqual((anchor / "binding.json").read_bytes(), M.encoded(expected))
                self.assertEqual((anchor / "report-manifest.json").read_bytes(), manifest_raw)
                self.assertEqual(receipt_path.read_bytes(), receipt_raw)
                self.assertEqual((records / "candidate-report-baseline.json").read_bytes(), baseline_raw)
                self.assertEqual({key: args[key] for key in before}, before)
                self.assertNotEqual(before["candidate_source"], before["receipt"]["sourceBefore"])
                self.assertNotEqual(expected["candidateAfter"]["status"], "")
                self.assertEqual(runner.calls, [("source_snapshot", args["candidate"]),
                    ("retain_reports", args["candidate"], args["state"], [], before["baseline"], anchor)])
                self.assertEqual(anchor.stat().st_mode & 0o777, 0o700)
                self.assertEqual((anchor / "binding.json").stat().st_mode & 0o777, 0o600)

    def test_candidate_report_original_receipt_hash_and_bytes_cannot_drift(self):
        for changed in ("hash", "bytes"):
            with self.subTest(changed=changed):
                args = self.candidate_report_fixture()
                if changed == "hash":
                    args["receipt_hash"] = "f" * 64
                else:
                    path = args["state"] / "evidence" / args["receipt"]["id"] / "receipt.json"
                    path.write_bytes(path.read_bytes() + b"\n")
                with self.assertRaisesRegex(M.UpdateError, "^CANDIDATE_REPORT_RECEIPT_CHANGED$"):
                    M.retain_candidate_reports(**args)
                self.assertEqual(args["runner"].calls, [])
                self.assertFalse((args["records"] / "candidate-reports").exists())

    def test_candidate_report_receipt_arguments_must_equal_original_body(self):
        for field, value in (("productExitCode", 1), ("sourceAfter", {}), ("purpose", "another")):
            with self.subTest(field=field):
                args = self.candidate_report_fixture()
                args["receipt"][field] = value
                with self.assertRaisesRegex(M.UpdateError, "^CANDIDATE_REPORT_RECEIPT_CHANGED$"):
                    M.retain_candidate_reports(**args)
                self.assertEqual(args["runner"].calls, [])
                self.assertFalse((args["records"] / "candidate-reports").exists())

    def test_candidate_reports_refuse_self_consistent_prerequisite_receipt(self):
        args = self.candidate_report_fixture(1)
        args["receipt"]["purpose"] = "dependency-maintenance-prerequisites"
        raw = M.encoded(args["receipt"])
        (args["state"] / "evidence" / args["receipt"]["id"] / "receipt.json").write_bytes(raw)
        args["receipt_hash"] = M.digest(raw)
        with self.assertRaisesRegex(M.UpdateError, "^CANDIDATE_REPORT_RECEIPT_CHANGED$"):
            M.retain_candidate_reports(**args)
        self.assertEqual(args["runner"].calls, [])
        self.assertFalse((args["records"] / "candidate-reports").exists())

    def test_candidate_report_baseline_bytes_and_argument_cannot_drift(self):
        for changed in ("bytes", "argument"):
            with self.subTest(changed=changed):
                args = self.candidate_report_fixture()
                if changed == "bytes":
                    path = args["records"] / "candidate-report-baseline.json"
                    path.write_bytes(path.read_bytes() + b"\n")
                else:
                    args["baseline"] = {}
                with self.assertRaisesRegex(M.UpdateError, "^CANDIDATE_REPORT_BASELINE_CHANGED$"):
                    M.retain_candidate_reports(**args)
                self.assertEqual(args["runner"].calls, [])
                self.assertFalse((args["records"] / "candidate-reports").exists())

    def test_candidate_report_commit_or_tree_drift_prevents_retention(self):
        for field in ("commit", "tree"):
            with self.subTest(field=field):
                args = self.candidate_report_fixture()
                args["runner"].source[field] = "f" * 40
                with self.assertRaisesRegex(M.UpdateError, "^CANDIDATE_REPORT_SOURCE_CHANGED$"):
                    M.retain_candidate_reports(**args)
                self.assertEqual(args["runner"].calls, [("source_snapshot", args["candidate"])])
                self.assertFalse((args["records"] / "candidate-reports").exists())

    def test_candidate_report_manifest_must_match_retainer_return_before_binding(self):
        for manifest in ([], {"schema": 1}, {"schema": 1, "records": []}):
            with self.subTest(manifest=manifest):
                args = self.candidate_report_fixture()
                args["runner"].manifest = manifest
                with self.assertRaisesRegex(M.UpdateError, "^CANDIDATE_REPORT_MANIFEST_CHANGED$"):
                    M.retain_candidate_reports(**args)
                self.assertEqual(len(args["runner"].calls), 2)
                self.assertFalse((args["records"] / "candidate-reports/binding.json").exists())

    def test_candidate_report_copy_exception_is_preserved_without_a_binding(self):
        args = self.candidate_report_fixture(1)
        failure = OSError("synthetic report-copy failure")
        args["runner"].error = failure
        with self.assertRaises(OSError) as stopped:
            M.retain_candidate_reports(**args)
        self.assertIs(stopped.exception, failure)
        self.assertEqual(len(args["runner"].calls), 2)
        self.assertEqual(list((args["records"] / "candidate-reports").iterdir()), [])

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
        node = next(node for node in self.tree.body if isinstance(node, ast.FunctionDef) and node.name == "owned_command")
        self.assertEqual([arg.arg for arg in node.args.kwonlyargs], ["command_returns"])
        self.assertEqual(node.args.kw_defaults, [None])
        self.assertIn('cwd=str(ROOT), wrapper=str(ROOT / "gradlew")', text)
        self.assertIn('kind="command"', text)
        self.assertIn('stop_timeout=STOP_SECONDS', text)
        self.assertIn('code = runner.execute(args)', text)
        self.assertIn('with environment({**os.environ, "P2PKIT_AUDIT_STATE_DIR": str(parent / "state")})', text)
        execution = next(item for item in node.body if isinstance(item, ast.With))
        self.assertEqual([ast.unparse(item) for item in execution.body],
                         ["code = runner.execute(args)", "returned_raw_ns = shared_raw_ns()"])
        self.assertLess(text.index("code = runner.execute(args)"), text.index("command_return_data("))
        self.assertLess(text.index("returned_raw_ns = shared_raw_ns()"), text.index("raw = read_file("))
        self.assertLess(text.index("command_return_data("), text.index("command_returns.append("))
        self.assertIn('"returnedRawNs": returned_raw_ns', text)
        self.assertLess(text.index("command_returns.append("), text.index("raise ClosedProductFailure("))
        checks = self.functions["command_return_data"]
        for field in ("sourceBefore", "sourceAfter", "sourceUnchanged", "ownedSurvivors", "errors", "discoveryErrors",
                      "productExitCode", "stopExitCode", "finalExitCode", "cancelledSignals", "cancelRequested"):
            self.assertIn(field, checks)

    def test_key_validation_precedes_all_owned_commands_and_crypto_is_after_capture(self):
        text = self.functions["generate"]
        producer = self.functions["produce"]
        # Assert the actual F -> run_case/P -> original F return order, not
        # unrelated lexical line numbers across the two function definitions.
        foreground_order = ("exporter.validate_recipient(", "os.fsync(stream.fileno())",
            "prefix_captures =", 'owner.prepare_case("GENERATION")', 'owner.run_case("GENERATION", case_path)',
            "owner.production_result(outcome)", "owner.finish()",
            'for name in ("controller.stdout", "controller.stderr"):', "retain_bridge_files(",
            "exporter.export_encrypted(")
        for before, after in zip(foreground_order, foreground_order[1:]):
            self.assertLess(text.index(before), text.index(after))
        producer_order = ("runner.initialize(", "endpoint.ready(", "owned_command(",
            "os.fsync(stream.fileno())", 'require(out.closed and err.closed, "PRODUCER_CAPTURE_NOT_CLOSED")',
            'for name in ("producer.stdout", "producer.stderr"):', "write_new(endpoint.producer_result_path",
            "return endpoint.complete(endpoint.producer_result_path)")
        for before, after in zip(producer_order, producer_order[1:]):
            self.assertLess(producer.index(before), producer.index(after))
        self.assertNotIn("owned_command(", text)
        self.assertNotIn("runner.initialize(", text)
        self.assertLess(text.index("exporter.export_encrypted("), text.index('write_new(parent / ("generator-success.json"'))
        self.assertIn('source_commit=request["controller_sha"], source_tree=request["controller_tree"]', text)
        self.assertIn('str(candidate / "scripts/prepare-dependency-update.sh")', producer)
        self.assertIn("with environment(safe_environment)", text)
        self.assertIn("contextlib.redirect_stdout(out), contextlib.redirect_stderr(err)", text)
        self.assertIn("contextlib.redirect_stdout(out), contextlib.redirect_stderr(err)", producer)
        self.assertIn("return produce(int(sys.argv[2]))", self.functions["main"])

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
        producer = self.functions["produce"]
        node = next(node for node in self.tree.body if isinstance(node, ast.FunctionDef) and node.name == "produce")
        handlers = [handler for item in ast.walk(node) if isinstance(item, ast.Try) for handler in item.handlers]
        self.assertEqual(len(handlers), 1)
        self.assertEqual(ast.unparse(handlers[0].type), "ClosedProductFailure")
        foreground = next(node for node in self.tree.body if isinstance(node, ast.FunctionDef) and node.name == "generate")
        self.assertFalse(any(isinstance(item, ast.Name) and item.id == "ClosedProductFailure"
                             for item in ast.walk(foreground)))
        foreground_handlers = [handler for item in ast.walk(foreground) if isinstance(item, ast.Try)
                               for handler in item.handlers]
        self.assertEqual(len(foreground_handlers), 1)
        self.assertEqual(ast.unparse(foreground_handlers[0].type), "BaseException")
        self.assertEqual([ast.unparse(item) for item in foreground_handlers[0].body], ["owner.abort()", "raise"])
        self.assertIn('"FAILED_CONTROLLER_CHANGED"', producer)
        self.assertLess(producer.index("except ClosedProductFailure as original:"),
                        producer.index("os.fsync(stream.fileno())"))
        self.assertIn('"code": 0 if failed is None else failed.code', producer)
        self.assertIn('"disposition": "SUCCESS" if failed is None else "CLOSED_FAILED_PRODUCT"', producer)
        self.assertIn("code, disposition = owner.production_result(outcome)", text)
        self.assertIn('producer_result["code"] == code and producer_result["disposition"] == disposition', text)
        self.assertLess(text.index("owner.run_case("), text.index("owner.production_result(outcome)"))
        self.assertLess(text.index("owner.production_result(outcome)"), text.index("owner.finish()"))
        self.assertLess(text.index("owner.finish()"),
                        text.index('for name in ("controller.stdout", "controller.stderr"):'))
        self.assertLess(text.index('for name in ("controller.stdout", "controller.stderr"):'),
                        text.index("exporter.export_encrypted("))
        self.assertIn("failed = code != 0", text)
        self.assertIn('encrypted_group = "failed-encrypted" if failed else "encrypted"', text)
        self.assertIn('("successSha256=" if not failed else "failedProductSha256=")', text)
        self.assertIn('"FAILED_OUTPUT_NOT_EXCLUSIVE"', text)
        self.assertIn("return code", text)
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

    def test_candidate_report_baseline_and_success_capture_keep_closed_order(self):
        text = self.functions["produce"]
        foreground = self.functions["generate"]
        node = next(node for node in self.tree.body if isinstance(node, ast.FunctionDef) and node.name == "produce")
        guarded = next(item for item in ast.walk(node) if isinstance(item, ast.Try))
        self.assertLess(foreground.index('candidate_source = clean_source(runner, candidate, request["candidate_sha"], request["candidate_tree"])'),
                        foreground.index('owner.run_case("GENERATION", case_path)'))
        self.assertIn('candidate_source, controller_source = inputs["candidateBefore"], inputs["controllerBefore"]', text)
        self.assertLess(text.index('clean_source(runner, candidate, request["candidate_sha"], request["candidate_tree"])'),
                        text.index("candidate_reports_before = None"))
        self.assertLess(text.index("candidate_reports_before = None"), text.index("try:"))
        self.assertLess(text.index("endpoint.ready("), text.index("try:"))
        steps = [ast.unparse(item) for item in guarded.body]
        self.assertEqual(steps[0], "generation_budget(allocation, step_started_ns, ENTRY_RESERVE)")
        self.assertEqual(steps[2], "candidate_reports_before = runner.report_snapshot(candidate, state, [])")
        self.assertEqual(steps[3], "write_new(records / 'candidate-report-baseline.json', encoded(candidate_reports_before))")
        self.assertEqual(steps[4], "generation_budget(allocation, step_started_ns, WRITER_RESERVE)")
        self.assertEqual(steps[6], "generation_budget(allocation, step_started_ns, FINAL_RESERVE, "
                                 "returned_ns=command_returns[-1]['returnedRawNs'])")
        self.assertEqual(steps[7], "retain_candidate_reports(runner, candidate, state, records, request, candidate_source, "
                                 "candidate_reports_before, receipt, receipt_hash)")
        for index, purpose, names, seconds in (
                (1, "dependency-maintenance-prerequisites", ["prerequisites_receipt", "prerequisites_hash"], "PREREQUISITES_SECONDS"),
                (5, "dependency-maintenance-generator", ["receipt", "receipt_hash"], "PRODUCT_SECONDS")):
            step = guarded.body[index]
            self.assertIsInstance(step, ast.Assign)
            self.assertEqual([target.id for target in step.targets[0].elts], names)
            self.assertEqual(ast.unparse(step.value.func), "owned_command")
            self.assertEqual([ast.unparse(arg) for arg in step.value.args[:3]], ["runner", "parent", "context"])
            self.assertEqual(step.value.args[3].value, purpose)
            self.assertEqual(ast.unparse(step.value.args[-1]), seconds)
            self.assertEqual([(keyword.arg, ast.unparse(keyword.value)) for keyword in step.value.keywords],
                             [("command_returns", "command_returns")])
        self.assertEqual(text.count("runner.report_snapshot("), 1)
        self.assertNotIn("runner.report_snapshot(", foreground)

    def test_failed_candidate_capture_requires_closed_generator_and_admitted_baseline(self):
        node = next(node for node in self.tree.body if isinstance(node, ast.FunctionDef) and node.name == "produce")
        guarded = next(item for item in ast.walk(node) if isinstance(item, ast.Try))
        handler = guarded.handlers[0]
        self.assertEqual(ast.unparse(handler.type), "ClosedProductFailure")
        self.assertEqual(ast.unparse(handler.body[0]), "failed = original")
        self.assertEqual(ast.unparse(handler.body[1]), "generation_budget(allocation, step_started_ns, FINAL_RESERVE, "
                                                    "returned_ns=command_returns[-1]['returnedRawNs'])")
        self.assertIn("'FAILED_CONTROLLER_CHANGED'", ast.unparse(handler.body[2]))
        branch = handler.body[3]
        self.assertIsInstance(branch, ast.If)
        self.assertEqual(ast.unparse(branch.test), "failed.receipt['purpose'] == 'dependency-maintenance-generator'")
        self.assertEqual(branch.orelse, [])
        self.assertEqual([ast.unparse(item) for item in branch.body], [
            "require(candidate_reports_before is not None, 'CANDIDATE_REPORTS_NOT_ADMITTED')",
            "retain_candidate_reports(runner, candidate, state, records, request, candidate_source, "
            "candidate_reports_before, failed.receipt, failed.receipt_hash)"])
        self.assertEqual(len(handler.body), 5)
        failure_record = ast.unparse(handler.body[4])
        for original in ("records / 'failed-product.json'", "'productExitCode': failed.code",
                         "'purpose': failed.receipt['purpose']", "'receiptSha256': failed.receipt_hash",
                         "'candidateAcceptance': 'NOT_ACCEPTED'"):
            self.assertIn(original, failure_record)

    def test_candidate_report_copy_failures_have_no_new_export_or_catch_path(self):
        helper = next(node for node in self.tree.body if isinstance(node, ast.FunctionDef) and
                      node.name == "retain_candidate_reports")
        self.assertFalse(any(isinstance(node, ast.Try) for node in ast.walk(helper)))
        self.assertIn("runner.retain_reports(candidate, state, [], baseline, anchor)",
                      self.functions["retain_candidate_reports"])
        self.assertNotIn("ClosedProductFailure", self.functions["retain_candidate_reports"])
        self.assertNotIn("export_encrypted", self.functions["retain_candidate_reports"])
        produce = next(node for node in self.tree.body if isinstance(node, ast.FunctionDef) and node.name == "produce")
        guarded = next(item for item in ast.walk(produce) if isinstance(item, ast.Try))
        self.assertEqual(guarded.orelse, [])
        self.assertEqual(guarded.finalbody, [])
        calls = [node for node in ast.walk(produce) if isinstance(node, ast.Call)]
        captures = [node for node in calls if ast.unparse(node.func) == "retain_candidate_reports"]
        self.assertFalse(any(ast.unparse(node.func) == "exporter.export_encrypted" for node in calls))
        results = [node for node in calls if ast.unparse(node.func) == "write_new" and node.args and
                   ast.unparse(node.args[0]) == "endpoint.producer_result_path"]
        completions = [node for node in calls if ast.unparse(node.func) == "endpoint.complete"]
        self.assertEqual(len(captures), 2)
        self.assertEqual(len(results), 1)
        self.assertEqual(len(completions), 1)
        self.assertTrue(all(node.lineno < results[0].lineno for node in captures))
        self.assertLess(guarded.end_lineno, results[0].lineno)
        self.assertLess(results[0].lineno, completions[0].lineno)
        generate = next(node for node in self.tree.body if isinstance(node, ast.FunctionDef) and node.name == "generate")
        foreground_guard = next(item for item in ast.walk(generate) if isinstance(item, ast.Try))
        self.assertEqual(foreground_guard.orelse, [])
        self.assertEqual(foreground_guard.finalbody, [])
        self.assertEqual(len(foreground_guard.handlers), 1)
        self.assertEqual(ast.unparse(foreground_guard.handlers[0].type), "BaseException")
        self.assertEqual([ast.unparse(item) for item in foreground_guard.handlers[0].body], ["owner.abort()", "raise"])
        foreground_calls = [node for node in ast.walk(generate) if isinstance(node, ast.Call)]
        self.assertFalse(any(ast.unparse(node.func) == "retain_candidate_reports" for node in foreground_calls))
        exports = [node for node in foreground_calls if ast.unparse(node.func) == "exporter.export_encrypted"]
        run_cases = [node for node in foreground_calls if ast.unparse(node.func) == "owner.run_case"]
        original_results = [node for node in foreground_calls if ast.unparse(node.func) == "owner.production_result"]
        finishes = [node for node in foreground_calls if ast.unparse(node.func) == "owner.finish"]
        bridge_copies = [node for node in foreground_calls if ast.unparse(node.func) == "retain_bridge_files"]
        closed_copies = [node for node in foreground_calls if ast.unparse(node.func) == "write_new" and node.args and
                        ast.unparse(node.args[0]) in ("records / name", "records / 'generation-inputs.json'")]
        self.assertEqual(len(exports), 1)
        self.assertEqual(len(run_cases), 1)
        self.assertEqual(len(original_results), 1)
        self.assertEqual(len(finishes), 1)
        self.assertEqual(len(bridge_copies), 1)
        self.assertEqual(len(closed_copies), 2)
        self.assertLess(run_cases[0].lineno, original_results[0].lineno)
        self.assertLess(original_results[0].lineno, finishes[0].lineno)
        self.assertTrue(all(finishes[0].lineno < node.lineno < exports[0].lineno
                            for node in closed_copies + bridge_copies))
        self.assertLess(foreground_guard.end_lineno, exports[0].lineno)
        self.assertEqual((M.FINALIZE_SECONDS, M.EXPORT_SECONDS, M.UPLOAD_SECONDS), (300, 120, 1320))


if __name__ == "__main__":
    unittest.main()
