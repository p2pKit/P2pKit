#!/usr/bin/env python3
"""Synthetic service-field controls; no environment acquisition or provider."""
from __future__ import annotations

import contextlib
import io
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
from urllib.parse import SplitResult


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import hosted_cache_provider_environment as E


class RuntimeServiceFragment(unittest.TestCase):
    def setUp(self):
        self.fields = {
            "ACTIONS_RUNTIME_TOKEN": "SYNTHETIC_TOKEN_NOT_A_CREDENTIAL",
            "ACTIONS_RESULTS_URL": "https://synthetic-results.example.invalid/base/",
            "ACTIONS_CACHE_SERVICE_V2": "True",
        }

    def fragment(self, fields=None):
        return E.runtime_service_fragment(self.fields if fields is None else fields)

    def test_exact_roster_and_fresh_unchanged_values(self):
        original = dict(self.fields)
        result = self.fragment()
        self.assertEqual(result, original)
        self.assertEqual(set(result), {
            "ACTIONS_RUNTIME_TOKEN", "ACTIONS_RESULTS_URL", "ACTIONS_CACHE_SERVICE_V2"})
        self.assertIsNot(result, self.fields)
        result["ACTIONS_RUNTIME_TOKEN"] = "different-synthetic-value"
        self.assertEqual(self.fields, original)
        self.assertEqual(self.fragment(), original)

    def test_no_mapping_or_string_subclasses_are_admitted(self):
        class Mapping(dict):
            pass
        class String(str):
            pass
        for value in (None, True, [], tuple(self.fields.items()), Mapping(self.fields)):
            with self.subTest(kind=type(value).__name__), self.assertRaises(E.ProviderEnvironmentError):
                E.runtime_service_fragment(value)
        for name in self.fields:
            with self.subTest(name=name), self.assertRaises(E.ProviderEnvironmentError):
                self.fragment({**self.fields, name: String(self.fields[name])})
        value = {String(name): data for name, data in self.fields.items()}
        with self.assertRaisesRegex(E.ProviderEnvironmentError, "RUNTIME_FIELDS"):
            self.fragment(value)

    def test_all_fields_required_and_no_extras_even_empty(self):
        for name in self.fields:
            value = dict(self.fields)
            del value[name]
            with self.subTest(missing=name), self.assertRaisesRegex(E.ProviderEnvironmentError, "RUNTIME_FIELDS"):
                self.fragment(value)
        for value in ("", "synthetic"):
            with self.assertRaisesRegex(E.ProviderEnvironmentError, "RUNTIME_FIELDS"):
                self.fragment({**self.fields, "extra": value})

    def test_windows_case_aliases_and_duplicate_spellings_refuse(self):
        for name in self.fields:
            for alias in (name.lower(), name.title()):
                with self.subTest(alias=alias), self.assertRaisesRegex(E.ProviderEnvironmentError, "RUNTIME_FIELDS"):
                    self.fragment({**self.fields, alias: self.fields[name]})
                value = dict(self.fields)
                value[alias] = value.pop(name)
                with self.assertRaisesRegex(E.ProviderEnvironmentError, "RUNTIME_FIELDS"):
                    self.fragment(value)

    def test_only_inspected_runner_true_spelling_without_coercion(self):
        for value in ("true", "TRUE", "false", "False", "1", "0", "yes", " True", "True ", "True\n", True, 1):
            with self.subTest(kind=type(value).__name__), self.assertRaises(E.ProviderEnvironmentError):
                self.fragment({**self.fields, "ACTIONS_CACHE_SERVICE_V2": value})

    def test_all_values_are_nonempty_bounded_plain_strings(self):
        for name in self.fields:
            for value in ("", None, False, 1, [], b"synthetic", "x" * 4097):
                with self.subTest(name=name, kind=type(value).__name__), self.assertRaises(E.ProviderEnvironmentError):
                    self.fragment({**self.fields, name: value})

    def test_token_boundary_is_not_token_authentication(self):
        for value in ("x", "x" * 4096, "synthetic._~+/=value"):
            self.assertEqual(self.fragment({**self.fields, "ACTIONS_RUNTIME_TOKEN": value})["ACTIONS_RUNTIME_TOKEN"], value)
        # Accepted strings are still only synthetic supplied data, not credentials.

    def test_no_whitespace_control_nonascii_or_silent_trimming(self):
        for name in self.fields:
            for char in (" ", "\t", "\r", "\n", "\0", "\x1f", "\x7f", "é"):
                with self.subTest(name=name, code=ord(char)), self.assertRaises(E.ProviderEnvironmentError):
                    self.fragment({**self.fields, name: self.fields[name] + char})

    def test_https_original_spelling_is_retained_not_normalized(self):
        for value in ("https://SYNTHETIC-RESULTS.example.invalid/Path/", "https://synthetic.example.invalid:443/",
                      "https://synthetic.example.invalid:8443/base", "https://synthetic.example.invalid"):
            self.assertEqual(self.fragment({**self.fields, "ACTIONS_RESULTS_URL": value})["ACTIONS_RESULTS_URL"], value)

    def test_endpoint_scheme_authority_userinfo_and_port_refusals(self):
        for value in ("http://synthetic.example.invalid/", "HTTPS://synthetic.example.invalid/",
                      "//synthetic.example.invalid/", "https:synthetic.example.invalid", "https:///base/",
                      "https://", "https://:443/", "https://synthetic.example.invalid:/",
                      "https://synthetic.example.invalid:0/", "https://synthetic.example.invalid:65536/",
                      "https://synthetic.example.invalid:word/", "https://synthetic.example.invalid:-1/",
                      "https://user@synthetic.example.invalid/", "https://user:pass@synthetic.example.invalid/",
                      "https://[not-an-ip]/", "https://[broken/", "https://@synthetic.example.invalid/"):
            with self.subTest(value=value), self.assertRaisesRegex(E.ProviderEnvironmentError, "RUNTIME_URL"):
                self.fragment({**self.fields, "ACTIONS_RESULTS_URL": value})

    def test_query_fragment_escape_and_non_uri_characters_refuse(self):
        for suffix in ("?", "?query=value", "#", "#fragment", "%2f", "\\other", '"', "<", ">", "`", "{", "}", "|", "^"):
            with self.subTest(suffix=suffix), self.assertRaisesRegex(E.ProviderEnvironmentError, "RUNTIME_URL"):
                self.fragment({**self.fields, "ACTIONS_RESULTS_URL": self.fields["ACTIONS_RESULTS_URL"] + suffix})

    def test_bracketed_hosts_require_real_ipv6_not_ipvfuture_or_loose_brackets(self):
        for value in ("https://[2001:DB8::1]/", "https://[2001:db8::1]:443/",
                      "https://[::ffff:192.0.2.1]/"):
            self.assertEqual(self.fragment({**self.fields, "ACTIONS_RESULTS_URL": value})["ACTIONS_RESULTS_URL"], value)
        for value in ("https://[v1.invalid[body]/", "https://[v1.future-address]/", "https://[1:2:3]/",
                      "https://[2001:db8::1]suffix:443/", "https://prefix[2001:db8::1]:443/"):
            with self.subTest(value=value), self.assertRaisesRegex(E.ProviderEnvironmentError, "RUNTIME_URL"):
                self.fragment({**self.fields, "ACTIONS_RESULTS_URL": value})

    def test_explicit_authority_checks_do_not_depend_on_later_urlsplit_bracket_patch(self):
        # Explicit model of permissive parsing; not a run on an older Python or Node.
        authority = "[2001:db8::1]suffix:443"
        parsed = SplitResult("https", authority, "/", "", "")
        self.assertEqual(parsed.hostname, "2001:db8::1")
        self.assertEqual(parsed.port, 443)
        with patch.object(E, "urlsplit", return_value=parsed), \
                self.assertRaisesRegex(E.ProviderEnvironmentError, "RUNTIME_URL"):
            self.fragment({**self.fields, "ACTIONS_RESULTS_URL": "https://" + authority + "/"})
        with patch.object(E, "urlsplit", return_value=SplitResult("https", "different.example.invalid", "/", "", "")), \
                self.assertRaisesRegex(E.ProviderEnvironmentError, "RUNTIME_URL"):
            self.fragment()

    def test_port_spelling_is_exact_not_normalized_to_a_different_original(self):
        for port in ("0443", "+443", "-443", "00001", "000000443", "443tail", "443:443"):
            with self.subTest(port=port), self.assertRaisesRegex(E.ProviderEnvironmentError, "RUNTIME_URL"):
                self.fragment({**self.fields, "ACTIONS_RESULTS_URL": "https://synthetic.example.invalid:" + port + "/"})

    def test_url_bound_accepts_exact_4096_but_not_4097(self):
        base = self.fields["ACTIONS_RESULTS_URL"]
        exact = base + "x" * (4096 - len(base))
        self.assertEqual(self.fragment({**self.fields, "ACTIONS_RESULTS_URL": exact})["ACTIONS_RESULTS_URL"], exact)
        with self.assertRaises(E.ProviderEnvironmentError):
            self.fragment({**self.fields, "ACTIONS_RESULTS_URL": exact + "x"})

    def test_v1_api_oidc_command_inputs_and_loader_fields_never_enter_fragment(self):
        for name in ("ACTIONS_CACHE_URL", "ACTIONS_RUNTIME_URL", "ACTIONS_CACHE_MODE", "GH_TOKEN", "GITHUB_TOKEN",
                     "P2PKIT_ACTIONS_READ_TOKEN", "ACTIONS_ID_TOKEN_REQUEST_TOKEN", "ACTIONS_ID_TOKEN_REQUEST_URL",
                     "GITHUB_OUTPUT", "GITHUB_ENV", "GITHUB_PATH", "GITHUB_STATE", "GITHUB_STEP_SUMMARY",
                     "NODE_OPTIONS", "NODE_PATH", "HTTP_PROXY", "https_proxy", "LD_PRELOAD", "DYLD_INSERT_LIBRARIES",
                     "SSL_CERT_FILE", "NODE_EXTRA_CA_CERTS", "RUNNER_DEBUG", "CACHE_UPLOAD_CONCURRENCY", "INPUT_KEY"):
            with self.subTest(name=name), self.assertRaisesRegex(E.ProviderEnvironmentError, "RUNTIME_FIELDS"):
                self.fragment({**self.fields, name: "SYNTHETIC_DO_NOT_FORWARD"})

    def test_alternative_credential_field_cannot_replace_missing_runtime_field(self):
        for name in ("GH_TOKEN", "GITHUB_TOKEN", "P2PKIT_ACTIONS_READ_TOKEN", "ACTIONS_ID_TOKEN_REQUEST_TOKEN"):
            value = {key: data for key, data in self.fields.items() if key != "ACTIONS_RUNTIME_TOKEN"}
            value[name] = "SYNTHETIC_NOT_RUNTIME"
            with self.subTest(name=name), self.assertRaisesRegex(E.ProviderEnvironmentError, "RUNTIME_FIELDS"):
                self.fragment(value)

    def test_errors_and_output_do_not_replay_supplied_values(self):
        values = ({**self.fields, "extra": "PRIVATE_SYNTHETIC_MARKER"},
                  {**self.fields, "ACTIONS_RESULTS_URL": "https://[PRIVATE_SYNTHETIC_MARKER]/"},
                  {**self.fields, "ACTIONS_RUNTIME_TOKEN": "PRIVATE_SYNTHETIC_MARKER\n"})
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            self.fragment()
            for value in values:
                with self.assertRaises(E.ProviderEnvironmentError) as raised:
                    self.fragment(value)
                self.assertRegex(str(raised.exception), r"^CACHE_PROVIDER_RUNTIME_(FIELDS|VALUE|V2|URL)$")
                self.assertNotIn("PRIVATE_SYNTHETIC_MARKER", repr(raised.exception))
                self.assertIsNone(raised.exception.__cause__)
        self.assertEqual(stdout.getvalue(), "")
        self.assertEqual(stderr.getvalue(), "")

    def test_ambient_environment_is_not_read_copied_or_changed(self):
        hostile = {"ACTIONS_RUNTIME_TOKEN": "SYNTHETIC_AMBIENT_NOT_ORIGINAL", "NODE_OPTIONS": "synthetic"}
        with patch.dict(os.environ, hostile, clear=True):
            self.assertEqual(self.fragment(), self.fields)
            self.assertEqual(dict(os.environ), hostile)
        with self.assertRaises(TypeError):
            E.runtime_service_fragment(self.fields, environment=hostile)

    def test_no_files_or_io_are_needed(self):
        with patch("builtins.open", side_effect=AssertionError("no file reads")), \
                patch.object(Path, "open", side_effect=AssertionError("no path reads")):
            self.assertEqual(self.fragment(), self.fields)


if __name__ == "__main__":
    unittest.main()
