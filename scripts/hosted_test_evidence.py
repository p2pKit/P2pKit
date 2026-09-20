#!/usr/bin/env python3
"""Closed ordinary-CI and bootstrap adapters; never identity impersonation.

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


def _bootstrap_bounds(max_bytes, max_members, timeout_seconds):
    # The existing bootstrap proposal reserves 240s for custody-encrypt. This
    # relative mechanism cap is NOT an original phase/job fence or its admission.
    for value, maximum in ((max_bytes, hosted_evidence.MAX_BYTES),
                           (max_members, hosted_evidence.MAX_MEMBERS), (timeout_seconds, 240)):
        if type(value) is not int or not 0 < value <= maximum:
            raise hosted_evidence.EvidenceError("Bootstrap evidence bounds cannot be disabled or expanded")


def _bound_bootstrap_manifest(recipient, *, root, admission, query_runner) -> dict:
    """Closed bootstrap identity, never ordinary suites or a caller manifest."""
    import hosted_cache_bootstrap_identity as bootstrap

    if type(admission) is not hosted_test_identity.Admission:
        raise hosted_evidence.EvidenceError("Bootstrap evidence requires its original admission")
    checked = bootstrap.admit(root, query_runner=query_runner, expected=admission)
    if bootstrap.cache_cohort(checked.record) is None:
        raise hosted_evidence.EvidenceError("Ordinary admission cannot authorize bootstrap evidence")
    if recipient.fingerprint != checked.fingerprint or recipient.key_sha256 != checked.key_sha256:
        raise hosted_evidence.EvidenceError("Bootstrap evidence recipient differs from the approved source policy")
    if recipient.expires_at and checked.expires_at > recipient.expires_at:
        raise hosted_evidence.EvidenceError("Bootstrap policy validity exceeds its validated recipient lifetime")
    identity = json.loads(checked.record)
    return {"schema": 3, "scope": "ENCRYPTED_PRIVATE_CACHE_BOOTSTRAP_EVIDENCE",
            "source": identity["source"], "github": identity["github"], "policy": identity["policy"],
            "custody": {name: identity[name] for name in
                        ("profile", "selection", "cacheCohort", "producerCommand", "producerScope", "testAcceptance")}}


def export_bootstrap_encrypted(evidence_dir: str | Path, output_dir: str | Path,
                               recipient: hosted_evidence.Recipient, *, root: Path,
                               admission: hosted_test_identity.Admission, query_runner,
                               timeout_seconds: int,
                               max_bytes: int = hosted_evidence.MAX_BYTES,
                               max_members: int = hosted_evidence.MAX_MEMBERS) -> dict:
    """Dormant bootstrap-only entry to the unchanged POSIX encryption mechanism.

    The future owner must supply a NEW frozen evidence-only tree, known complete
    writer retirement and the original absolute custody/return fences. H/S and
    dependency bytes are not evidence. This function supplies none of those
    premises, provider success, failed-owner authority, a seal or upload authority.
    Its explicit relative timeout can only shorten the proposed 240s mechanism
    cap; it cannot renew the enclosing phase or include uncharged re-admission.
    """
    if os.name != "posix":
        raise hosted_evidence.EvidenceError("Bootstrap encrypted export needs an admitted native filesystem backend")
    _bootstrap_bounds(max_bytes, max_members, timeout_seconds)
    manifest = _bound_bootstrap_manifest(recipient, root=root, admission=admission, query_runner=query_runner)
    return hosted_evidence._export_bound_manifest(evidence_dir, output_dir, recipient, manifest=manifest,
                                                  max_bytes=max_bytes, max_members=max_members,
                                                  timeout_seconds=timeout_seconds)
