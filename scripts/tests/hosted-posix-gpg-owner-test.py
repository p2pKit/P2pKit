#!/usr/bin/env python3
"""Pure actual-launch models; no native owner, real child, GPG or cryptography.

All file/archive bytes are synthetic. Reaching an exported-file shape in a model
is NOT encryption, authenticated decryption or hosted evidence. Run -I -B -S.
"""
from __future__ import annotations

import ctypes
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import audit_processes as P
import hosted_evidence as H
import hosted_test_evidence as E
import hosted_test_identity as I


JOB, INVOCATION = "1" * 32, "2" * 32
STATE, HOME = "/synthetic/enclosing-owner", "/synthetic/enclosing-owner/gradle-home"
MARKERS = (P.JOB_ENV, P.CHAIN_ENV, P.DOMAINS_ENV, P.STATE_ENV, "GRADLE_USER_HOME")
STATUS = b"[GNUPG:] BEGIN_ENCRYPTION 2 9\n[GNUPG:] END_ENCRYPTION\n"


def parent_environment():
    return P.ownership_environment({}, JOB, INVOCATION, STATE, HOME)


def owns(environment, state=STATE, home=HOME):
    # Only the production pure predicate is exercised; no native constructor.
    scope = object.__new__(P.PosixScope)
    scope.job, scope.invocation, scope.state, scope.home = JOB, INVOCATION, state, home
    return scope._ours({key.encode("ascii"): os.fsencode(value) for key, value in environment.items()})


class ModelChild:
    returncode = 0

    def poll(self):
        return 0

    def wait(self, timeout=None):
        return 0


class PosixGpgOwnerTests(unittest.TestCase):
    def setUp(self):
        self.base = Path(tempfile.mkdtemp(prefix="p2pkit-gpg-owner-model-")).resolve(strict=True)
        self.addCleanup(shutil.rmtree, self.base)  # Wholly synthetic, no native/crypto worker ever starts.
        self.work = self.base / "work"
        self.work.mkdir(mode=0o700)
        self.home = self.work / "gnupg"
        self.recipient = H.Recipient(self.work, self.home, self.base / "not-executed-gpg", "A" * 40,
                                     "B" * 40, 0, "c" * 64, (1, 2))
        self.calls = []
        self.launch_error = None
        self.environment = parent_environment()
        for target, name in ((subprocess, "run"), (P, "make_scope"), (ctypes, "CDLL")):
            guard = patch.object(target, name, side_effect=AssertionError("No native or child call in models"))
            guard.start()
            self.addCleanup(guard.stop)
        launch = patch.object(subprocess, "Popen", side_effect=self.model_launch)
        launch.start()
        self.addCleanup(launch.stop)

    def model_launch(self, argv, **kwargs):
        self.calls.append({"argv": list(argv), "environment": dict(kwargs["env"]),
                           "kwargs": {key: kwargs[key] for key in ("close_fds", "pass_fds")}})
        if self.launch_error is not None:
            raise self.launch_error
        kwargs["stdout"].write(b"synthetic-gpg-output\n")
        kwargs["stderr"].write(b"synthetic-private-diagnostic\n")
        if "--status-fd" in argv:
            descriptor = int(argv[argv.index("--status-fd") + 1])
            os.write(descriptor, STATUS)
        return ModelChild()

    def run_gpg(self, *, status=False, output=None):
        with patch.dict(os.environ, self.environment, clear=True):
            return H._gpg(self.recipient, ["--list-keys"], time.monotonic() + 30,
                          status=status, output=output)

    def rejected_before_allocation_or_launch(self):
        with patch.object(H.tempfile, "mkdtemp", side_effect=AssertionError("Invalid owner allocated GPG work")):
            with self.assertRaisesRegex(H.EvidenceError, "^Incomplete or mismatched enclosing evidence owner$"):
                self.run_gpg()
        self.assertEqual(self.calls, [])

    def test_actual_launch_preserves_exact_complete_parent_domain(self):
        self.assertEqual(self.run_gpg(), (b"synthetic-gpg-output\n", b""))
        actual = self.calls[0]["environment"]
        self.assertTrue(owns(actual))
        self.assertEqual({name: actual[name] for name in MARKERS}, parent_environment())

    def test_nested_original_domains_remain_byte_exact_not_recreated(self):
        self.environment = P.ownership_environment(self.environment, "3" * 32, "4" * 32,
                                                  "/synthetic/new-owner", "/synthetic/new-owner/home",
                                                  allow_new_context=True)
        self.run_gpg()
        actual = self.calls[0]["environment"]
        self.assertTrue(owns(actual))
        for name in MARKERS:
            self.assertEqual(actual[name], self.environment[name])
        self.assertEqual(len(P.ownership_domains(actual[P.CHAIN_ENV], actual[P.DOMAINS_ENV])), 2)

    def test_preserves_credential_and_hook_noninheritance(self):
        self.environment.update(GITHUB_TOKEN="synthetic-token", SSH_AUTH_SOCK="synthetic-socket",
                                GPG_AGENT_INFO="synthetic-agent", LD_PRELOAD="synthetic-hook",
                                PYTHONPATH="synthetic-python", GIT_CONFIG_GLOBAL="synthetic-config")
        self.run_gpg()
        expected = {"PATH", "HOME", "GNUPGHOME", "LANG", "LC_ALL", "TMPDIR", *MARKERS}
        self.assertEqual(set(self.calls[0]["environment"]), expected)

    def test_direct_unowned_call_keeps_original_six_key_contract(self):
        self.environment = {"GRADLE_USER_HOME": "/synthetic/unowned-home", "GITHUB_TOKEN": "synthetic-token"}
        self.run_gpg()
        actual = self.calls[0]["environment"]
        self.assertEqual(set(actual), {"PATH", "HOME", "GNUPGHOME", "LANG", "LC_ALL", "TMPDIR"})
        self.assertFalse(owns(actual))

    def test_missing_each_marker_is_rejected_before_private_allocation(self):
        for name in MARKERS:
            with self.subTest(missing=name):
                self.environment = parent_environment()
                del self.environment[name]
                self.rejected_before_allocation_or_launch()

    def test_any_lone_owner_marker_is_not_a_direct_caller_fallback(self):
        for name in MARKERS[:-1]:
            with self.subTest(lone=name):
                self.environment = {name: parent_environment()[name]}
                self.rejected_before_allocation_or_launch()

    def test_empty_context_does_not_fall_back_to_unowned_launch(self):
        for name in MARKERS:
            with self.subTest(empty=name):
                self.environment = parent_environment()
                self.environment[name] = ""
                self.rejected_before_allocation_or_launch()

    def test_current_job_state_and_home_must_match_last_original_domain(self):
        for name, value in ((P.JOB_ENV, "5" * 32), (P.STATE_ENV, "/synthetic/other-state"),
                            ("GRADLE_USER_HOME", "/synthetic/other-home")):
            with self.subTest(changed=name):
                self.environment = dict(parent_environment(), **{name: value})
                self.rejected_before_allocation_or_launch()

    def test_chain_and_domain_encoding_are_validated_by_existing_supplier(self):
        good = parent_environment()
        domains = json.loads(good[P.DOMAINS_ENV])
        invalid = ["not-json", "{}", "[]", json.dumps(domains + domains),
                   good[P.DOMAINS_ENV].replace('"job":', '"job":"' + JOB + '","job":')]
        for encoded in invalid:
            with self.subTest(encoded=encoded):
                self.environment = dict(good, **{P.DOMAINS_ENV: encoded})
                self.rejected_before_allocation_or_launch()

    def test_duplicate_or_inconsistent_chain_ids_cannot_enter(self):
        for chain in (INVOCATION + ":" + INVOCATION, "3" * 32, "3" * 31):
            with self.subTest(chain=chain):
                self.environment = dict(parent_environment(), **{P.CHAIN_ENV: chain})
                self.rejected_before_allocation_or_launch()

    def test_existing_domain_size_bound_is_not_expanded(self):
        self.environment[P.DOMAINS_ENV] = " " * (512 * 1024 + 1)
        self.rejected_before_allocation_or_launch()

    def test_raw_nonascii_domain_rejected_before_allocation_or_launch(self):
        state = "/synthetic/caf\u00e9-owner"
        self.environment = P.ownership_environment({}, JOB, INVOCATION, state, state + "/gradle-home")
        self.environment[P.DOMAINS_ENV] = json.dumps(json.loads(self.environment[P.DOMAINS_ENV]),
                                                    ensure_ascii=False, separators=(",", ":"))
        self.assertFalse(self.environment[P.DOMAINS_ENV].isascii())
        with self.assertRaisesRegex(H.EvidenceError, "^Incomplete or mismatched enclosing evidence owner$"):
            self.run_gpg()
        self.assertEqual(self.calls, [])
        self.assertEqual(list(self.work.iterdir()), [])

    def test_original_ascii_escaped_unicode_domain_remains_exact_and_recognizable(self):
        state, home = "/synthetic/caf\u00e9-owner", "/synthetic/caf\u00e9-owner/gradle-home"
        self.environment = P.ownership_environment({}, JOB, INVOCATION, state, home)
        original = dict(self.environment)
        self.assertTrue(original[P.DOMAINS_ENV].isascii())
        self.run_gpg()
        actual = self.calls[0]["environment"]
        self.assertTrue(owns(actual, state=state, home=home))
        for name in MARKERS:
            self.assertEqual(actual[name], original[name])

    def test_original_launch_cancellation_preserved_with_domain_already_supplied(self):
        original = KeyboardInterrupt("synthetic-launch-cancellation")
        self.launch_error = original
        with self.assertRaises(KeyboardInterrupt) as raised:
            self.run_gpg()
        self.assertIs(raised.exception, original)
        self.assertTrue(owns(self.calls[0]["environment"]))
        records = list(self.work.glob("gpg-*/process.json"))
        self.assertEqual(len(records), 1)
        self.assertEqual(json.loads(records[0].read_bytes())["interruption"], "operation-interrupted")

    def test_original_no_agent_network_and_status_sink_contracts_remain(self):
        self.assertEqual(self.run_gpg(status=True, output=self.work / "ciphertext"), (b"", STATUS))
        command = self.calls[0]
        for value in ("--no-options", "--no-autostart", "--no-auto-key-retrieve", "--no-auto-key-import",
                      "--disable-dirmngr", "--no-random-seed-file", "--no-default-keyring"):
            self.assertIn(value, command["argv"])
        self.assertTrue(command["kwargs"]["close_fds"])
        self.assertEqual(len(command["kwargs"]["pass_fds"]), 1)
        self.assertTrue(owns(command["environment"]))

    def test_actual_recipient_and_ordinary_export_callers_share_preserved_context(self):
        # Public key parsing, native GPG semantics and ciphertext shape are
        # deliberately replaced. Archive/file/control flow is real and bounded.
        key = self.base / "synthetic.asc"
        key.write_bytes(b"synthetic-not-a-real-key")
        key.chmod(0o600)
        executable = self.base / "not-executed-gpg"
        executable.write_bytes(b"not executable content; never launched\n")
        executable.chmod(0o700)
        evidence = self.base / "evidence"
        evidence.mkdir(mode=0o700)
        (evidence / "fixture.log").write_bytes(b"synthetic-original\x00\xff")
        identity = {"profile": "desktop", "suites": ["cli"],
                    "source": {"commit": "1" * 40, "tree": "2" * 40},
                    "github": {"model": "NOT_GITHUB"}, "policy": {"model": "NOT_TRUSTED_POLICY"}}
        admission = I.Admission(I.encoded(identity), b"synthetic-event", b"synthetic-policy", key.read_bytes(),
                                 "A" * 40, hashlib.sha256(key.read_bytes()).hexdigest(), int(time.time()) + 1000)
        with patch.dict(os.environ, self.environment, clear=True), \
                patch.object(H.shutil, "which", return_value=str(executable)), \
                patch.object(H, "_public_armor", return_value=b"synthetic-packets"), \
                patch.object(H, "_key_identity", return_value=("B" * 40, 0)), \
                patch.object(H, "_ciphertext_shape"), \
                patch.object(I, "admit", return_value=admission), \
                patch.object(H, "_manifest_identity", side_effect=AssertionError("Never impersonate manual identity")):
            recipient = H.validate_recipient(key, admission.fingerprint, self.work)
            manifest = E.export_encrypted(evidence, self.base / "output", recipient, profile="desktop", root=ROOT,
                                           admission=admission, query_runner=lambda **_: self.fail("No Git query"))
        self.assertEqual(len(self.calls), 4)  # show-only + list + refresh + encryption
        self.assertTrue(all(owns(call["environment"]) for call in self.calls))
        self.assertEqual(manifest["schema"], 2)
        self.assertEqual((evidence / "fixture.log").read_bytes(), b"synthetic-original\x00\xff")


if __name__ == "__main__":
    unittest.main(verbosity=2)
