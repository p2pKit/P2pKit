#!/usr/bin/env python3
"""Additive ordinary-CI encrypted custody; never a manual-identity impersonation.

The execution owner must first freeze the admitted public policy and retire ALL
evidence writers. This entry point rechecks the real event/source/policy and the
cryptographically validated recipient before sharing the POSIX export mechanism.
It does not initialize an execution owner, bootstrap policy, run tests, or upload.
Native Windows needs the separate private-handle exporter; mode bits are not a
Windows privacy contract. Workflow/controller wiring is a separate acceptance step.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import hosted_evidence
import hosted_test_identity


def export_encrypted(evidence_dir: str | Path, output_dir: str | Path,
                     recipient: hosted_evidence.Recipient, *, profile: str, root: Path,
                     admission: hosted_test_identity.Admission,
                     query_runner,
                     max_bytes: int = hosted_evidence.MAX_BYTES,
                     max_members: int = hosted_evidence.MAX_MEMBERS,
                     timeout_seconds: int = hosted_evidence.MAX_TIMEOUT_SECONDS) -> dict:
    """Return encrypted files only after closed re-admission and complete export.

    ``admission`` is the original immutable record from before test execution;
    it cannot authorize a different source, event, policy or encryption recipient.
    Successful return still needs the owner's post-return seal and independent
    private decryption/inspection; encrypted custody is not test acceptance.
    """
    if os.name != "posix":
        raise hosted_evidence.EvidenceError("Ordinary encrypted export needs an admitted native filesystem backend")
    manifest = _bound_manifest(recipient, profile=profile, root=root, admission=admission,
                               query_runner=query_runner)
    return hosted_evidence._export_bound_manifest(evidence_dir, output_dir, recipient, manifest=manifest,
                                                  max_bytes=max_bytes, max_members=max_members,
                                                  timeout_seconds=timeout_seconds)


def _bound_manifest(recipient, *, profile, root, admission, query_runner) -> dict:
    """Closed schema-2 identity shared by admitted native exporters, never raw input."""
    checked = hosted_test_identity.admit(profile, root, query_runner=query_runner, expected=admission)
    if recipient.fingerprint != checked.fingerprint or recipient.key_sha256 != checked.key_sha256:
        raise hosted_evidence.EvidenceError("Ordinary evidence recipient differs from the approved source policy")
    if recipient.expires_at and checked.expires_at > recipient.expires_at:
        raise hosted_evidence.EvidenceError("Ordinary policy validity exceeds its validated recipient lifetime")
    identity = json.loads(checked.record)
    return {"schema": 2, "scope": "ENCRYPTED_PRIVATE_TEST_EVIDENCE",
            "source": identity["source"], "github": identity["github"], "policy": identity["policy"],
            "custody": {"profile": identity["profile"], "suites": identity["suites"]}}
