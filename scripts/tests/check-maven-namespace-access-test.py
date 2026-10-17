#!/usr/bin/env python3
"""Mocked supported-API preflight controls; no authenticated network requests."""
import base64
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import stat
import tempfile
import types
import unittest
from unittest import mock
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("namespace_check", ROOT / "scripts/check-maven-namespace-access.py")
C = importlib.util.module_from_spec(spec)
spec.loader.exec_module(C)
USER = "synthetic-user"
PASSWORD = "synthetic-password"
PRIVATE = "private-response-value"
SHA = "a" * 40


def page(rows=None, total=None):
    if rows is None:
        rows = [{"namespace": C.NAMESPACE, "deploymentId": PRIVATE, "deploymentState": "PUBLISHED"}]
    if total is None:
        total = len(rows)
    return {"deployments": rows, "page": 0, "pageSize": 1,
            "pageCount": total, "totalResultCount": total}


class Response:
    def __init__(self, data=None, raw=None, status=200):
        self.raw = raw if raw is not None else json.dumps(page() if data is None else data).encode()
        self.status = status
        self.closed = False
        self.read_sizes = []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.closed = True

    def read(self, size):
        self.read_sizes.append(size)
        return self.raw[:size]


class ErrorBody(io.BytesIO):
    def read(self, *args):
        raise AssertionError("Error bodies must not be read")


class NamespaceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name).resolve() / "reports"
        self.report = self.directory / C.REPORT

    def invoke(self, response=None, env=None, argv=None):
        values = {"MAVEN_CENTRAL_USERNAME": USER, "MAVEN_CENTRAL_PASSWORD": PASSWORD,
                  "MAVEN_CENTRAL_NAMESPACE": C.NAMESPACE, "MAVEN_NAMESPACE_REPORT_DIR": str(self.directory)}
        if env:
            values.update(env)
        values = {k: v for k, v in values.items() if v is not None}
        opener = mock.Mock()
        response = Response() if response is None else response
        if isinstance(response, Exception):
            opener.open.side_effect = response
        else:
            opener.open.return_value = response
        output, errors = io.StringIO(), io.StringIO()
        with mock.patch.dict(os.environ, values, clear=True), \
                mock.patch.object(C, "source_commit", return_value=SHA), \
                mock.patch.object(C.urllib.request, "build_opener", return_value=opener) as factory, \
                mock.patch.object(C.urllib.request, "urlopen", side_effect=AssertionError("No network")), \
                contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
            code = C.main([] if argv is None else argv)
        text = output.getvalue() + errors.getvalue()
        if self.report.is_file() and not self.report.is_symlink():
            text += self.report.read_text()
        for secret in (USER, PASSWORD, PRIVATE, base64.b64encode((USER + ":" + PASSWORD).encode()).decode()):
            self.assertNotIn(secret, text)
        self.assertNotIn("Traceback", text)
        return code, opener, factory, output.getvalue(), errors.getvalue()

    def stale(self):
        self.directory.mkdir(parents=True, exist_ok=True)
        self.report.write_text('{"oldSuccess":true}')

    def test_supported_exact_request_and_honest_source_bound_report(self):
        response = Response()
        code, opener, factory, output, errors = self.invoke(response)
        self.assertEqual(code, 0)
        self.assertEqual(errors, "")
        self.assertIn("RESULT: PASS", output)
        opener.open.assert_called_once()
        request = opener.open.call_args.args[0]
        self.assertEqual(request.full_url, C.URL)
        self.assertEqual(request.get_method(), "GET")
        self.assertIsNone(request.data)
        self.assertEqual(request.get_header("Authorization"), "Bearer " + base64.b64encode((USER + ":" + PASSWORD).encode()).decode())
        self.assertEqual(opener.open.call_args.kwargs, {"timeout": 20})
        self.assertEqual(factory.call_args.args[0].proxies, {})
        self.assertIsInstance(factory.call_args.args[1], C.NoRedirect)
        self.assertEqual(response.read_sizes, [256 * 1024 + 1])
        self.assertTrue(response.closed)
        data = json.loads(self.report.read_text())
        self.assertEqual(set(data), {"schemaVersion", "namespace", "tokenAuthenticated", "namespaceQueryAccepted", "namespaceVerificationState", "checkedAt", "commitSha"})
        self.assertEqual(data["schemaVersion"], 2)
        self.assertIs(data["tokenAuthenticated"], True)
        self.assertIs(data["namespaceQueryAccepted"], True)
        self.assertEqual(data["namespaceVerificationState"], "NOT_ASSERTED")
        self.assertEqual(data["commitSha"], SHA)
        self.assertEqual(data["namespace"], C.NAMESPACE)
        self.assertRegex(data["checkedAt"], r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$")
        self.assertEqual(stat.S_IMODE(self.report.stat().st_mode), 0o600)

    def test_empty_and_nonempty_coherent_filtered_pages(self):
        for data in (page([]), dict(page([]), pageCount=1), page(total=7)):
            with self.subTest(data=data):
                self.assertEqual(self.invoke(Response(data))[0], 0)

    def test_http_errors_redirects_never_read_body_or_retry(self):
        for status in (401, 403, 404, 429, 500, 502, 503, 301, 302, 303, 307, 308):
            with self.subTest(status=status):
                self.stale()
                body = ErrorBody(PRIVATE.encode())
                error = urllib.error.HTTPError(C.URL, status, PRIVATE, {"Location": "https://evil.invalid"}, body)
                code, opener, _, _, errors = self.invoke(error)
                self.assertEqual(code, 1)
                self.assertIn("HTTP_" + str(status), errors)
                opener.open.assert_called_once()
                self.assertTrue(body.closed)
                self.assertFalse(self.report.exists())

    def test_non200_response_never_passes(self):
        for status in (201, 204, True, "200"):
            with self.subTest(status=status):
                self.assertEqual(self.invoke(Response(status=status))[0], 1)
                self.assertFalse(self.report.exists())

    def test_transport_and_unexpected_failures_emit_no_private_exception(self):
        for error in (urllib.error.URLError(PRIVATE), TimeoutError(PRIVATE), OSError(PRIVATE), RuntimeError(PRIVATE)):
            with self.subTest(error=type(error).__name__):
                self.stale()
                code, opener, _, _, _ = self.invoke(error)
                self.assertEqual(code, 1)
                opener.open.assert_called_once()
                self.assertFalse(self.report.exists())

    def test_bounded_malformed_duplicate_and_nonfinite_json(self):
        for raw in (b" " * (C.LIMIT + 1), PRIVATE.encode(), b"\xff", b"[" * 2000,
                    b'{"deployments":[],"deployments":[]}', b'{"value":NaN}'):
            with self.subTest(size=len(raw)):
                response = Response(raw=raw)
                self.assertEqual(self.invoke(response)[0], 1)
                self.assertTrue(response.closed)
                self.assertEqual(response.read_sizes, [C.LIMIT + 1])
                self.assertFalse(self.report.exists())

    def test_old_internal_verified_and_other_array_contracts_are_refused(self):
        for data in ([{"name": C.NAMESPACE, "state": "VERIFIED"}],
                     [{"name": C.NAMESPACE, "state": "VERIFYING"}],
                     [{"name": "io.github.p2pkit", "state": "VERIFIED"}], [], {}):
            self.assertEqual(self.invoke(Response(data))[0], 1)

    def test_strict_pagination(self):
        bad = []
        for key in ("page", "pageSize", "pageCount", "totalResultCount"):
            missing = page(); del missing[key]; bad.append(missing)
            for value in (True, None, "1", 1.0, -1, 2**63):
                bad.append(dict(page(), **{key: value}))
        bad.extend([dict(page(), page=1), dict(page(), pageSize=20), dict(page(), pageCount=2),
                    dict(page(), totalResultCount=0), dict(page([]), totalResultCount=1),
                    dict(page([]), pageCount=2), dict(page(), deployments=None),
                    dict(page(), deployments=page()["deployments"] * 2)])
        for data in bad:
            with self.subTest(data=data):
                self.assertEqual(self.invoke(Response(data))[0], 1)
                self.assertFalse(self.report.exists())

    def test_deployment_namespace_required_and_exact(self):
        for row in (None, [], {}, {"namespace": None}, {"namespace": "io.github.p2pkit"},
                    {"namespace": C.NAMESPACE + ".suffix"}, {"namespace": C.NAMESPACE.upper()}):
            with self.subTest(row=row):
                self.assertEqual(self.invoke(Response(page([row])))[0], 1)

    def test_unrelated_deployment_details_are_not_publication_validation(self):
        row = {"namespace": C.NAMESPACE, "deploymentState": "NEW_SERVER_STATE",
               "deploymentComponents": {"futureSchema": PRIVATE}, "deploymentName": PRIVATE}
        self.assertEqual(self.invoke(Response(page([row])))[0], 0)

    def test_missing_malformed_credentials_and_namespace_never_make_request(self):
        cases = []
        for key in ("MAVEN_CENTRAL_USERNAME", "MAVEN_CENTRAL_PASSWORD"):
            for value in (None, "", "a\nb", "a b", "é", "x" * 4097):
                cases.append({key: value})
        cases.extend([{"MAVEN_CENTRAL_USERNAME": "a:b"}, {"MAVEN_CENTRAL_NAMESPACE": None},
                      {"MAVEN_CENTRAL_NAMESPACE": "io.github.p2pkit"}])
        for env in cases:
            with self.subTest(keys=list(env)):
                self.stale()
                code, opener, factory, _, _ = self.invoke(env=env)
                self.assertEqual(code, 1)
                factory.assert_not_called()
                opener.open.assert_not_called()
                self.assertFalse(self.report.exists())

    def test_endpoint_overrides_and_arguments_refused(self):
        for env in ({"CURL_BIN": "evil"}, {"CENTRAL_NAMESPACE_API_URL": "https://evil.invalid"}):
            code, opener, _, _, _ = self.invoke(env=env)
            self.assertEqual(code, 1)
            opener.open.assert_not_called()
        code, opener, _, _, _ = self.invoke(argv=["https://evil.invalid"])
        self.assertEqual(code, 1)
        opener.open.assert_not_called()

    def test_environment_proxy_cannot_change_route(self):
        code, opener, factory, _, _ = self.invoke(env={"HTTPS_PROXY": "https://evil.invalid", "HTTP_PROXY": "https://evil.invalid"})
        self.assertEqual(code, 0)
        self.assertEqual(factory.call_args.args[0].proxies, {})
        self.assertEqual(opener.open.call_args.args[0].full_url, C.URL)

    def test_default_tls_handler_and_no_redirect(self):
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), C.NoRedirect())
        self.assertTrue(any(isinstance(h, urllib.request.HTTPSHandler) for h in opener.handlers))
        redirects = [h for h in opener.handlers if isinstance(h, urllib.request.HTTPRedirectHandler)]
        self.assertEqual(len(redirects), 1)
        self.assertIsInstance(redirects[0], C.NoRedirect)
        self.assertIsNone(redirects[0].redirect_request(None, None, 302, None, None, "https://evil.invalid"))

    def test_stale_report_replaced_without_old_fields(self):
        self.stale()
        self.assertEqual(self.invoke()[0], 0)
        self.assertNotIn("oldSuccess", self.report.read_text())

    def test_report_symlink_not_followed_and_old_target_untouched(self):
        self.directory.mkdir()
        target = Path(self.temp.name) / "protected"
        target.write_text("unchanged")
        self.report.symlink_to(target)
        code, opener, _, _, _ = self.invoke()
        self.assertEqual(code, 1)
        opener.open.assert_not_called()
        self.assertEqual(target.read_text(), "unchanged")
        self.assertFalse(self.report.is_symlink())

    def test_report_directory_symlink_not_followed(self):
        target = Path(self.temp.name) / "protected-dir"
        target.mkdir()
        self.directory.symlink_to(target, target_is_directory=True)
        code, opener, _, _, _ = self.invoke()
        self.assertEqual(code, 1)
        opener.open.assert_not_called()
        self.assertEqual(list(target.iterdir()), [])

    def test_partial_report_removed_after_write_failure(self):
        def fail_write(record, stream, **kwargs):
            stream.write('{"partial":true}')
            raise OSError(PRIVATE)
        with mock.patch.object(C.json, "dump", side_effect=fail_write):
            self.assertEqual(self.invoke()[0], 1)
        self.assertFalse(self.report.exists())

    def test_final_directory_close_failure_is_finite_and_never_prints_pass(self):
        self.directory.mkdir()
        original_directory = C.report_directory
        original_close = os.close
        final_fd = []

        def open_directory(path):
            fd = original_directory(path)
            final_fd.append(fd)
            return fd

        def close(fd):
            original_close(fd)
            if final_fd and fd == final_fd[0]:
                raise OSError(PRIVATE)

        with mock.patch.object(C, "report_directory", side_effect=open_directory), \
                mock.patch.object(C.os, "close", side_effect=close):
            code, _, _, output, errors = self.invoke()
        self.assertEqual(code, 1)
        self.assertNotIn("RESULT: PASS", output)
        self.assertIn("REPORT_CLEANUP_FAILURE", errors)
        # close was actually performed; no unsafe pathname fallback or retry.
        with self.assertRaises(OSError):
            os.fstat(final_fd[0])

    def test_source_is_actual_head_and_github_sha_must_match(self):
        result = types.SimpleNamespace(returncode=0, stdout=(SHA + "\n").encode())
        with mock.patch.object(C.subprocess, "run", return_value=result) as git:
            with mock.patch.dict(os.environ, {}, clear=True):
                self.assertEqual(C.source_commit(), SHA)
            with mock.patch.dict(os.environ, {"GITHUB_SHA": SHA}, clear=True):
                self.assertEqual(C.source_commit(), SHA)
            for value in ("b" * 40, "local", "", SHA.upper()):
                with mock.patch.dict(os.environ, {"GITHUB_SHA": value}, clear=True):
                    with self.assertRaises(C.Refusal):
                        C.source_commit()
            self.assertEqual(git.call_args.args[0], ["git", "rev-parse", "HEAD"])
            self.assertEqual(git.call_args.kwargs["cwd"], ROOT)
        for result in (types.SimpleNamespace(returncode=1, stdout=SHA.encode()),
                       types.SimpleNamespace(returncode=0, stdout=b"local")):
            with mock.patch.object(C.subprocess, "run", return_value=result), self.assertRaises(C.Refusal):
                C.source_commit()

    def test_maintained_wrappers_and_secret_free_controls_workflow(self):
        wrapper = (ROOT / "scripts/check-maven-namespace-access.sh").read_text()
        test = (ROOT / "scripts/tests/check-maven-namespace-access-test.sh").read_text()
        workflow = (ROOT / ".github/workflows/verify-maven-namespace.yml").read_text()
        self.assertIn('exec python3 -I -B -S "$ROOT/scripts/check-maven-namespace-access.py" "$@"', wrapper)
        self.assertIn('scripts/tests/check-maven-namespace-access-test.py" -v', test)
        self.assertIn("default: verify", workflow)
        controls = workflow.split("  namespace-controls:\n", 1)[1].split("  verify-namespace:\n", 1)[0]
        verify = workflow.split("  verify-namespace:\n", 1)[1]
        self.assertIn("inputs.operation == 'controls'", controls)
        self.assertNotIn("secrets.", controls)
        self.assertNotIn("environment:", controls)
        self.assertIn("run: bash scripts/tests/check-maven-namespace-access-test.sh", controls)
        self.assertNotIn("run: scripts/check-maven-namespace-access.sh", controls)
        self.assertIn("inputs.operation == 'verify'", verify)
        self.assertIn("name: maven-central", verify)
        self.assertIn("run: scripts/check-maven-namespace-access.sh", verify)
        self.assertIn("persist-credentials: false", controls)


if __name__ == "__main__":
    unittest.main(failfast=True)
