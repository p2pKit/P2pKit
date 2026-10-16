#!/usr/bin/env python3
"""Offline Central-auth transport/output and isolated-workflow controls."""
import base64
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import re
import unittest
from unittest.mock import Mock, patch
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("central_auth_diagnostic", ROOT / "scripts/diagnose-maven-central-auth.py")
C = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(C)
USER = "synthetic-token-user"
PASSWORD = "synthetic-private-token-password"
PAIR = USER + ":" + PASSWORD
ENCODED = base64.b64encode(PAIR.encode()).decode()
PRIVATE = "private-response-content-not-for-output"


class Response:
    def __init__(self, data, status=200, raw=False):
        self.raw = data if raw else json.dumps(data).encode()
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


class UnreadErrorBody(io.BytesIO):
    def read(self, *args):
        raise AssertionError("Error bodies must never be read")


def public_response(**changes):
    value = {"deployments": [], "page": 0, "pageSize": 1, "private": PRIVATE}
    value.update(changes)
    return Response(value)


def namespace_response(data=None):
    if data is None:
        data = [{"name": C.NAMESPACE, "state": "VERIFIED", "private": PRIVATE}]
    return Response(data)


class DiagnosticTests(unittest.TestCase):
    def invoke(self, responses, env=None):
        opener = Mock()
        opener.open.side_effect = responses
        stdout, stderr = io.StringIO(), io.StringIO()
        values = {"MAVEN_CENTRAL_USERNAME": USER, "MAVEN_CENTRAL_PASSWORD": PASSWORD} if env is None else env
        with patch.dict(C.os.environ, values, clear=True), \
                patch.object(C.urllib.request, "build_opener", return_value=opener) as factory, \
                patch.object(C.urllib.request, "urlopen", side_effect=AssertionError("No live network")), \
                contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = C.main()
        output = stdout.getvalue()
        self.assertEqual(stderr.getvalue(), "")
        for secret in (USER, PASSWORD, PAIR, ENCODED, PRIVATE):
            self.assertNotIn(secret, output)
        return code, json.loads(output), opener, factory

    def test_success_is_two_fixed_gets_with_bearer_and_bounded_closed_responses(self):
        responses = [public_response(), namespace_response()]
        code, result, opener, factory = self.invoke(responses)
        self.assertEqual(code, 0)
        self.assertEqual(result["scope"], C.SCOPE)
        self.assertFalse(result["uploadPerformed"])
        self.assertFalse(result["credentialsAndBodiesRetained"])
        self.assertTrue(result["currentInternalGate"]["exactVerifiedNamespaceVisible"])
        self.assertEqual(opener.open.call_count, 2)
        for call, route in zip(opener.open.call_args_list, C.ROUTES):
            request = call.args[0]
            self.assertEqual(request.full_url, C.HOST + route)
            self.assertEqual(request.get_method(), "GET")
            self.assertIsNone(request.data)
            self.assertEqual(request.get_header("Authorization"), "Bearer " + ENCODED)
            self.assertEqual(call.kwargs, {"timeout": 20})
        self.assertEqual(C.ROUTES, (
            "/api/v1/publisher/deployments?namespace=io.github.apdelrahman1911&page=0&size=1",
            "/api/internal/publisher/namespace"))
        handlers = factory.call_args.args
        self.assertIsInstance(handlers[0], urllib.request.ProxyHandler)
        self.assertEqual(handlers[0].proxies, {})
        self.assertIsInstance(handlers[1], C.NoRedirect)
        self.assertTrue(all(r.closed and r.read_sizes == [C.LIMIT + 1] for r in responses))

    def test_http_401_404_and_redirects_do_not_read_error_bodies_or_retry(self):
        for status in (401, 404, 301, 302, 307, 308):
            with self.subTest(status=status):
                body = UnreadErrorBody(PRIVATE.encode())
                error = urllib.error.HTTPError(C.HOST + C.ROUTES[0], status, PRIVATE,
                                               {"Location": "https://untrusted.invalid/" + PRIVATE}, body)
                code, result, opener, _ = self.invoke([error, namespace_response()])
                self.assertEqual(code, 1)
                self.assertEqual(result["documentedPublicApi"]["httpStatus"], status)
                self.assertFalse(result["documentedPublicApi"]["expectedResponseShape"])
                self.assertTrue(result["currentInternalGate"]["exactVerifiedNamespaceVisible"])
                self.assertEqual(opener.open.call_count, 2)
                self.assertTrue(body.closed)

    def test_internal_refusal_does_not_promote_public_authentication_to_gate_success(self):
        body = UnreadErrorBody(PRIVATE.encode())
        error = urllib.error.HTTPError(C.HOST + C.ROUTES[1], 401, PRIVATE, {}, body)
        code, result, opener, _ = self.invoke([public_response(), error])
        self.assertEqual(code, 1)
        self.assertTrue(result["documentedPublicApi"]["expectedResponseShape"])
        self.assertEqual(result["currentInternalGate"]["httpStatus"], 401)
        self.assertFalse(result["currentInternalGate"]["exactVerifiedNamespaceVisible"])
        self.assertEqual(opener.open.call_count, 2)
        self.assertTrue(body.closed)

    def test_transport_failures_keep_both_routes_and_never_echo_exception_text(self):
        for error in (urllib.error.URLError(PRIVATE), TimeoutError(PRIVATE),
                      C.http.client.IncompleteRead(PRIVATE.encode(), 10), ValueError(PRIVATE)):
            with self.subTest(kind=type(error).__name__):
                code, result, opener, _ = self.invoke([error, OSError(PRIVATE)])
                self.assertEqual(code, 1)
                self.assertEqual(opener.open.call_count, 2)
                for key in ("documentedPublicApi", "currentInternalGate"):
                    self.assertTrue(result[key]["transportError"])
                    self.assertIsNone(result[key]["httpStatus"])

    def test_oversize_and_malformed_json_are_bounded_closed_and_private(self):
        for raw in (b"x" * (C.LIMIT + 1), PRIVATE.encode(), b"\xff", b"[" * 1500):
            with self.subTest(length=len(raw)):
                response = Response(raw, raw=True)
                code, result, opener, _ = self.invoke([response, namespace_response()])
                self.assertEqual(code, 1)
                self.assertFalse(result["documentedPublicApi"]["boundedJson"])
                self.assertEqual(response.read_sizes, [C.LIMIT + 1])
                self.assertTrue(response.closed)
                self.assertEqual(opener.open.call_count, 2)

    def test_public_json_shape_is_not_an_authentication_pass(self):
        responses = [Response([]), public_response(deployments=[{}, {}]),
                     public_response(deployments=PRIVATE), public_response(page=True),
                     public_response(page=1), public_response(pageSize=True), public_response(pageSize=20)]
        for response in responses:
            with self.subTest(raw=response.raw):
                code, result, opener, _ = self.invoke([response, namespace_response()])
                self.assertEqual(code, 1)
                self.assertFalse(result["documentedPublicApi"]["expectedResponseShape"])
                self.assertEqual(opener.open.call_count, 2)

    def test_namespace_match_must_be_unique_exact_and_verified(self):
        for data in ([], {}, [PRIVATE], [{"name": C.NAMESPACE, "state": "UNVERIFIED"}],
                     [{"name": C.NAMESPACE + ".other", "state": "VERIFIED"}],
                     [{"name": C.NAMESPACE, "state": "VERIFIED"}] * 2):
            with self.subTest(data=data):
                code, result, opener, _ = self.invoke([public_response(), namespace_response(data)])
                self.assertEqual(code, 1)
                self.assertFalse(result["currentInternalGate"]["exactVerifiedNamespaceVisible"])
                self.assertEqual(opener.open.call_count, 2)

    def test_missing_or_malformed_credential_input_makes_no_requests(self):
        cases = [{}, {"MAVEN_CENTRAL_USERNAME": USER}, {"MAVEN_CENTRAL_PASSWORD": PASSWORD}]
        for username, password in (("", PASSWORD), (USER, ""), ("a:b", PASSWORD),
                                   (USER + "\n", PASSWORD), (USER, PASSWORD + "\r"),
                                   (USER, " " + PASSWORD), (USER, "\u00e9"),
                                   ("x" * 4097, PASSWORD), (USER, "x" * 4097)):
            cases.append({"MAVEN_CENTRAL_USERNAME": username, "MAVEN_CENTRAL_PASSWORD": password})
        for env in cases:
            with self.subTest(keys=sorted(env)):
                code, result, opener, factory = self.invoke([], env)
                self.assertEqual(code, 1)
                self.assertFalse(result["validCredentialInput"])
                factory.assert_not_called()
                opener.open.assert_not_called()

    def test_url_and_proxy_environment_cannot_redirect_credentials(self):
        env = {"MAVEN_CENTRAL_USERNAME": USER, "MAVEN_CENTRAL_PASSWORD": PASSWORD,
               "CENTRAL_NAMESPACE_API_URL": "https://untrusted.invalid/", "HTTPS_PROXY": "http://untrusted.invalid/",
               "HTTP_PROXY": "http://untrusted.invalid/", "ALL_PROXY": "http://untrusted.invalid/"}
        code, _, opener, factory = self.invoke([public_response(), namespace_response()], env)
        self.assertEqual(code, 0)
        self.assertEqual([c.args[0].full_url for c in opener.open.call_args_list], [C.HOST + r for r in C.ROUTES])
        self.assertEqual(factory.call_args.args[0].proxies, {})

    def test_opener_retains_default_tls_and_refuses_redirect_request(self):
        # Construct handlers only; no opener.open/network call is made.
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), C.NoRedirect())
        self.assertTrue(any(isinstance(h, urllib.request.HTTPSHandler) for h in opener.handlers))
        redirectors = [h for h in opener.handlers if isinstance(h, urllib.request.HTTPRedirectHandler)]
        self.assertEqual(len(redirectors), 1)
        self.assertIsInstance(redirectors[0], C.NoRedirect)
        self.assertIsNone(redirectors[0].redirect_request(
            urllib.request.Request(C.HOST + C.ROUTES[0]), None, 302, PRIVATE,
            {"Location": "http://untrusted.invalid/"}, "http://untrusted.invalid/"))

    def test_workflow_is_explicit_protected_and_has_only_the_two_token_secrets(self):
        workflow = (ROOT / ".github/workflows/verify-maven-namespace.yml").read_text()
        self.assertIn("options: [verify, auth-diagnostic]", workflow)
        self.assertIn("default: verify", workflow)
        legacy, diagnostic = workflow.split("  auth-diagnostic:\n")
        self.assertIn("if: ${{ inputs.operation == 'verify' }}", legacy)
        self.assertIn("runs-on: macos-15", legacy)
        self.assertIn("run: scripts/check-maven-namespace-access.sh", legacy)
        self.assertIn("name: maven-central-namespace-access", legacy)
        self.assertIn("if: ${{ inputs.operation == 'auth-diagnostic' }}", diagnostic)
        self.assertIn("runs-on: ubuntu-24.04", diagnostic)
        self.assertIn("timeout-minutes: 5", diagnostic)
        self.assertIn("name: maven-central", diagnostic)
        self.assertEqual(re.findall(r"secrets\.([A-Z_]+)", diagnostic),
                         ["MAVEN_CENTRAL_USERNAME", "MAVEN_CENTRAL_PASSWORD"])
        self.assertIn("uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1", diagnostic)
        self.assertIn("ref: ${{ github.sha }}", diagnostic)
        self.assertIn("persist-credentials: false", diagnostic)
        self.assertIn('test "$(git rev-parse HEAD)" = "$EXPECTED_SHA"', diagnostic)
        self.assertIn('git status --porcelain=v1 --untracked-files=all --ignore-submodules=none', diagnostic)
        self.assertIn("run: python3 -I -B -S scripts/diagnose-maven-central-auth.py", diagnostic)
        self.assertNotIn("upload-artifact", diagnostic)
        self.assertNotIn("SIGNING", diagnostic)
        self.assertNotIn("contents: write", workflow)


if __name__ == "__main__":
    unittest.main(failfast=True)
