#!/usr/bin/env python3
"""Small hosted-job evidence runner; no cache admission or initial trust protocol.

Trust the reviewed workflow/host and the independent recipient pins supplied by
Actions configuration. Capture command output privately, retire its owned process
domain, bundle closed results, and encrypt with the pinned PUBLIC key only.
Successful uploads contain manifest.json and evidence.tar.gz.gpg. A failed
export may retain failure.json and encrypted closed captures instead; these are
diagnostic, never qualification.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import signal
import stat
import subprocess
import sys
import tarfile
import tempfile
import threading
import time
import uuid
import xml.etree.ElementTree as ET

sys.dont_write_bytecode = True
if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent))
import audit_processes
# Reuse only the existing public armor and GPG colon-listing validators. No
# recipient activation dates, historical custody, native authority, or exporter.
from hosted_evidence import _public_armor, _key_identity

SCHEMA = 1
MAX_LOG_BYTES = 64 * 1024 * 1024
MAX_BUNDLE_BYTES = 512 * 1024 * 1024
MAX_REPORTS = 10000
MAX_JSON_BYTES = 1024 * 1024
CODES = frozenset({"PASS", "INPUT", "SOURCE_CHANGED", "SPAWN", "COMMAND_FAILED", "TIMEOUT",
                   "CANCELLED", "OUTPUT_LIMIT", "OUTPUT_IO", "CLEANUP", "REPORTS", "RECIPIENT",
                   "ENCRYPTION", "MANIFEST"})
CLEANUP_REASONS = frozenset({"SCOPE_UNAVAILABLE", "DRAIN_ERROR", "DRAIN_DEADLINE",
    "DRAIN_UNCLASSIFIED", "DRAIN_NOT_QUIET", "DRAIN_SIGNAL_UNRESOLVED", "LIVE_PROCESSES",
    "DISCOVERY_ERRORS", "LEADER_WAIT", "SCOPE_CLOSE", "CAPTURE_ACTIVE", "PIPE_NO_EOF",
    "PIPE_NOT_CLOSED", "ORIGINAL_PIPE_CLOSE"})
PENDING_CONTEXT_SCOPE = "RECORDED_CONTEXT_NOT_OWNERSHIP_OR_EXIT"
PENDING_FAILURES = {
    "Darwin non-reaper original-parent lifetime was not observed": "PARENT_UNOBSERVED",
    "Darwin traced parentage is not an ownership proof": "TRACED_PARENT",
}
PENDING_OPERATIONS = {"environment": "ENVIRONMENT", "identity": "IDENTITY",
                      "task token": "TASK_TOKEN", "inherited pipe": "INHERITED_PIPE"}
PENDING_FAILURE_LABELS = frozenset((*PENDING_FAILURES.values(),
                                  *PENDING_OPERATIONS.values(), "OTHER"))

# Exact existing source-owned builder failures, never arbitrary log excerpts.
# These are diagnostic categories only; original command/cleanup failure remains.
BUNDLE_FATAL_MESSAGES = {
    "MAVEN signing key is not valid base64": "BUNDLE_KEY_ENCODING",
    "GROUP/VERSION_NAME is missing from gradle.properties": "BUNDLE_VERSION_MISSING",
    "Central release bundle cannot use a SNAPSHOT version": "BUNDLE_SNAPSHOT_REFUSED",
    "configure only one in-memory signing-key representation": "BUNDLE_KEY_REPRESENTATION",
    "an in-memory signing key is required": "BUNDLE_KEY_MISSING",
    "ORG_GRADLE_PROJECT_signingInMemoryKeyPassword is required": "BUNDLE_PASSWORD_MISSING",
    "MAVEN_SIGNING_KEY_FINGERPRINT must be a complete 40- or 64-hex fingerprint": "BUNDLE_FINGERPRINT_FORMAT",
    "signed original evidence requires clean committed source": "BUNDLE_SOURCE_DIRTY",
    "could not read a fingerprint from the signing key": "BUNDLE_KEY_READ",
    "signing key fingerprint does not match MAVEN_SIGNING_KEY_FINGERPRINT": "BUNDLE_FINGERPRINT_MISMATCH",
    "could not import the release key into the isolated verification keyring": "BUNDLE_KEY_IMPORT",
    "could not export the public signing certificate": "BUNDLE_PUBLIC_EXPORT",
    "public signing certificate export is empty": "BUNDLE_PUBLIC_EXPORT_EMPTY",
    "complete Central publication requires exactly 121 signed files across 21 coordinates": "BUNDLE_SIGNED_INVENTORY",
    "Central publication differs from the exact signed roster": "BUNDLE_SIGNED_ROSTER",
    "Central bundle exceeds the 1 GiB upload limit": "BUNDLE_UPLOAD_SIZE",
    "source changed while producing signed original evidence": "BUNDLE_SOURCE_CHANGED",
    "bundle builder leaked disposable credential material": "BUNDLE_TEST_SECRET_LEAK",
    "could not stop disposable GPG workers; private directory retained": "BUNDLE_TEST_GPG_RETIREMENT",
    "could not stop isolated bundle GPG workers; private directory retained": "BUNDLE_GPG_RETIREMENT",
}

# Existing curator/checker wrapper failures, with no dynamic coordinate or path.
DEPENDENCY_FATAL_MESSAGES = {
    "artifact checksum review failed": "DEPENDENCY_REVIEW_CHECKSUM",
    "artifact signature review failed": "DEPENDENCY_REVIEW_SIGNATURE",
    "variant metadata checksum review failed": "DEPENDENCY_REVIEW_VARIANT_CHECKSUM",
    "variant metadata signature review failed": "DEPENDENCY_REVIEW_VARIANT_SIGNATURE",
    "variant artifact location review failed": "DEPENDENCY_REVIEW_VARIANT_LOCATION",
    "KMP root checksum review failed": "DEPENDENCY_REVIEW_KMP_CHECKSUM",
    "KMP root signature review failed": "DEPENDENCY_REVIEW_KMP_SIGNATURE",
    "KMP artifact location review failed": "DEPENDENCY_REVIEW_KMP_LOCATION",
    "unchanged review requires exact complete original verification metadata": "DEPENDENCY_REVIEW_UNCHANGED_XML",
    "verification metadata structure is invalid": "DEPENDENCY_VERIFICATION_STRUCTURE",
}
DEPENDENCY_GENERATOR_PHASES = frozenset({"WRAPPER", "GENERATE", "INTEGRITY", "STRICT", "PROVENANCE", "DIFF"})

# Exact maintained adapter errors only; arbitrary exception text never leaves logs.
DEPENDENCY_UPDATE_ERRORS = frozenset({
    'CANDIDATE_ROSTER_CHANGED', 'CONTROLLER_CHANGED', 'DEPENDENCY_BASE_ALREADY_CHANGED',
    'DUPLICATE_OR_EMPTY_COMPONENT', 'DUPLICATE_VERIFICATION_ARTIFACT', 'DUPLICATE_VERIFICATION_ENTRY',
    'EMPTY_SOURCE', 'EMPTY_VERIFICATION', 'GENERATION_OR_GRADLE_STOP_FAILED',
    'GIT_METADATA_REFUSED', 'HOSTED_CONTROLLER_IDENTITY', 'LINKED_OR_TRAVERSAL_PATH',
    'LINKED_SOURCE', 'MAINTAINED_GENERATOR_CHANGED', 'NON_DEPENDENCY_SOURCE_CHANGED',
    'OUTPUT_MUST_BE_FRESH_EXTERNAL', 'PATCH_LIMIT_OR_DELTA_MISMATCH', 'REQUEST_IDENTITY',
    'SEPARATE_CANDIDATE_REQUIRED', 'SOURCE_DIRTY', 'SOURCE_FILE_CHANGED',
    'SOURCE_FILE_TYPE_OR_SIZE', 'SOURCE_IDENTITY', 'SOURCE_MODE_CHANGED',
    'SOURCE_ROSTER', 'SOURCE_ROSTER_LIMIT', 'UNCHANGED_VERIFICATION_BYTES_DIFFER',
    'VERIFICATION_ARTIFACT', 'VERIFICATION_CHECKSUM', 'VERIFICATION_COMPONENT',
    'VERIFICATION_HISTORY_REMOVED', 'VERIFICATION_STRUCTURE', 'VERIFICATION_TRUST_CHANGED',
    'VERIFICATION_XML',
})
DEPENDENCY_UPDATE_EXCEPTIONS = frozenset({
    "ValueError", "KeyError", "TypeError", "OSError", "FileNotFoundError", "PermissionError",
    "FileExistsError", "IsADirectoryError", "NotADirectoryError", "UnicodeDecodeError",
    "JSONDecodeError", "SubprocessError", "CalledProcessError", "TimeoutExpired",
})

TASK_NAMES = frozenset({
    "check-rpc-hosted-validation-test.py", "check-rpc-scalable-io-test.py", "central-http-test.py", "kotlin-toolchain-controls", "published-consumer-controls",
    'rpc-apple-bonjour-environment-test.py', 'intel-bonjour-advertising-test.py',
    'intel-advertising-prepare', 'intel-advertising-restore',
    "release-tag-controls", "release-identity-controls", "maven-environment-controls",
    "maven-namespace-controls", "maven-coordinate-controls", "maven-upload-controls",
    "wrapper", "layout", "links", "release-metadata", "ios-launcher-controls", "workflow-contract", "workflow-controls", "workflow-syntax",
    "platform-contract", "version-encoding", "signed-bundle-test",
    "ci-component-test.py", "ci-evidence-test.py", "ci-qualification-test.py", "dependency-update-test.py",
    "prepare-api-candidate-test.py",
    "apple-issue-validation-test.py", "run-android-ui-validation-test.py", "android-legacy-task-preview-test.py",
    "tcp-nodelay-latency-test.py", "protocol-ping-latency-test.py", "run-rpc-qualification-test.py",
    "run-jmdns-interpreter-diagnostic-test.py", "jmdns-interpreter-diagnostic",
    "run-android-permission-validation-test.py", "keyboard-readiness-diagnostic",
    "swift-jvm-transfer-test.py", "run-android-art-smoke-test.py",
    "embedded-jmdns-aar-test.py", "embedded-jmdns-archive-controls", "intel-bonjour-environment-test.py",
    "central-gpg-lifecycle-controls",
    "central-bundle-evidence-test.py", "maven-recovery-test.py",
    "application-release-version-test.py", "sample-artifact-identity-test.py",
    "package-sample-apps-test.py", "release-application-set-test.py", "publish-sample-release-test.py",
    "inspect-rpc-windows-package-test.py", "verify-rpc-windows-app-image-test.py",
    "verify-rpc-windows-msi-payload-test.py", "rpc-windows-package-inspection",
    "check-rpc-windows-image-runtime-test.py", "rpc-windows-runtime-readback",
    "rpc-capacity-evidence-test.py", "run-rpc-capacity-lab-test.py", "rpc-capacity-macos-stage-test.py",
    "prepare-rpc-capacity-copy-test.py",
    "rpc-mobile-capacity-test.py", "rpc-mobile-commands-test.py", "rpc-ios-usb-test.py",
    "run-rpc-mobile-capacity-test.py", "rpc-mobile-mac-control-test.py", "rpc-darwin-capacity-test.py",
    "run-rpc-mac-campaign-test.py",
    "run-rpc-phone-ios-controls-test.py", "run-rpc-ios-handoff-test.py",
    "prepare-macos-rpc-desktop-test.py", "package-rpc-preview-test.py",
    "run-platform-tests-test.py", "audit-process-drain-deadline-test.py", "verify-rpc-windows-jdk21-test.py", "check-rpc-windows-packaging-test.py", "integrity-policy",
    "lock-coverage", "lock-writer-policy", "check-freemarker-floor-test.py", "check-jackson-floor-test.py", "check-guava-floor-test.py",
    "build-plugin-floors", "jvm-tests", "jmdns-close-tests", "supervisor-controls", "android-tests-and-apk", "desktop-tests-and-installer",
    "native-platform-tests", "shared-platform-tests", "abi-graph", "api-abi", "documentation", "sbom", "publication-shape",
    "isolated-consumers", "published-pom-diagnostic", "published-consumers-diagnostic", "xcframework", "minimum-apple-os", "swift-ui", "osv-lock-coverage", "osv-scan",
    "prepare-android", "prepare-desktop", "inspect-android", "inspect-desktop", "gradle-stop", "component-setup"})


class EvidenceError(RuntimeError):
    def __init__(self, code):
        super().__init__(code if code in CODES else "INPUT")
        self.code = code if code in CODES else "INPUT"


def require(condition, code="INPUT"):
    if not condition:
        raise EvidenceError(code)


def encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n").encode()


def utc():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def digest_file(path):
    digest, size = hashlib.sha256(), 0
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
            size += len(block)
    return {"sha256": digest.hexdigest(), "bytes": size}


def write_private(path, raw):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "wb") as stream:
            fd = None
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
    finally:
        if fd is not None:
            os.close(fd)


def read_json(path, maximum=MAX_JSON_BYTES):
    with Path(path).open("rb") as stream:
        raw = stream.read(maximum + 1)
    require(len(raw) <= maximum)
    return json.loads(raw)


class Capture:
    """One bounded private sink and one original pipe owner, on every OS."""
    def __init__(self, pipe, path, limit):
        self.pipe, self.path, self.limit = pipe, path, limit
        self.count, self.eof, self.closed, self.error = 0, False, False, None
        self.thread = threading.Thread(target=self._copy, daemon=True)

    def _copy(self):
        try:
            with self.path.open("xb", buffering=0) as output:
                if os.name == "posix":
                    os.chmod(self.path, 0o600)
                while True:
                    block = self.pipe.read(65536)
                    if not block:
                        self.eof = True
                        break
                    permitted = max(0, self.limit - self.count)
                    if len(block) > permitted:
                        self.error = "OUTPUT_LIMIT"
                    kept = block[:permitted]
                    if kept:
                        view = memoryview(kept)
                        while view:
                            written = output.write(view)
                            if not written:
                                raise OSError("private sink did not advance")
                            self.count += written
                            view = view[written:]
                    # Continue draining until the controller retires the child;
                    # never grow memory/disk beyond this stream's bound.
                output.flush()
                os.fsync(output.fileno())
        except BaseException:
            self.error = self.error or "OUTPUT_IO"
        finally:
            try:
                self.pipe.close()
                self.closed = True
            except BaseException:
                self.error = self.error or "CLEANUP"


HOSTED_DARWIN_BOUNDARY = "GITHUB_HOSTED_DARWIN_MARKER_DOMAIN_V1"
MAX_OUTSIDE_DOMAIN_OBSERVATIONS = 1_000_000


class _HostedDarwinScope(audit_processes.DarwinScope):
    """Routine reviewed hosted tasks, not a whole-host nonownership proof.

    Keep every positive marker/pipe/original-parent proof and every known-child
    lifetime/opaque-token cleanup check. A new process with no such proof and
    only an unobserved non-reaper parent is outside the observed owned domain;
    it is NOT declared foreign, exited, or safe to signal. A later census still
    revisits it. Delegated host services belong to their explicit platform
    lifecycle and the disposable GitHub VM, not arbitrary process-name kills.
    """
    def __init__(self, *args):
        self.outside_domain_observations = 0
        super().__init__(*args)

    def _ownership_proof(self, identity, environment):
        try:
            return super()._ownership_proof(identity, environment)
        except audit_processes.DiscoveryUncertain as error:
            if (type(error) is not audit_processes.DiscoveryUncertain or
                    error.args != ("Darwin non-reaper original-parent lifetime was not observed",) or
                    getattr(error, "audit_session_exclusion", None) != "SAME_VALID_SESSION" or
                    audit_processes.retirement_details(error) or self._key(identity) in self.known):
                raise
            # The inherited implementation has already rejected owned markers,
            # inherited pipe capability and observed positive parentage. No
            # structural/traced/environment/known-owner failure reaches here.
            self.outside_domain_observations = min(MAX_OUTSIDE_DOMAIN_OBSERVATIONS,
                                                   self.outside_domain_observations + 1)
            return None


def _hosted_darwin_context(environment):
    # This is a source-owned scope selection, not an authorization token. The
    # artifact consumer independently checks the real Actions workflow/job/host.
    workflow, separator, ref = environment.get("GITHUB_WORKFLOW_REF", "").partition("@")
    return (platform.system() == "Darwin" and environment.get("GITHUB_ACTIONS") == "true" and
        environment.get("RUNNER_ENVIRONMENT") == "github-hosted" and
        environment.get("GITHUB_REPOSITORY") == "p2pKit/P2pKit" and separator == "@" and bool(ref) and
        workflow in {"p2pKit/P2pKit/.github/workflows/ci.yml",
                     "p2pKit/P2pKit/.github/workflows/dependency-update-candidate.yml",
                     "p2pKit/P2pKit/.github/workflows/prepare-api-candidate.yml",
                     "p2pKit/P2pKit/.github/workflows/publish-maven-central.yml",
                     "p2pKit/P2pKit/.github/workflows/recover-maven-central.yml"} and
        (not workflow.endswith("/prepare-api-candidate.yml") or environment.get("GITHUB_JOB") == "generate") and
        (not workflow.endswith("/publish-maven-central.yml") or environment.get("GITHUB_JOB") == "publish-release") and
        (not workflow.endswith("/recover-maven-central.yml") or environment.get("GITHUB_JOB") == "verify-recovery") and
        re.fullmatch(r"[0-9a-f]{40}", environment.get("GITHUB_SHA", "")) is not None and
        environment.get("GITHUB_WORKFLOW_SHA") == environment.get("GITHUB_SHA"))


def _command_scope(job, invocation, private, home, environment):
    return (_HostedDarwinScope(job, invocation, private, home) if _hosted_darwin_context(environment) else
            audit_processes.make_scope(job, invocation, private, home))


class _HostedLocalDarwinScope(audit_processes.LocalDarwinScope, _HostedDarwinScope):
    """Independent local marker, with the enclosing command's exact hosted boundary.

    The local marker must not rewrite the canonical evidence-bound audit domain.
    All native lifetime/pipe/signal operations and hosted exclusion conditions are
    inherited unchanged; this is not an additional ownership or host exemption.
    """


def local_command_scope(job, invocation, private, home, environment):
    return (_HostedLocalDarwinScope(job, invocation, private, home) if _hosted_darwin_context(environment) else
            audit_processes.make_local_scope(job, invocation, private, home))


def run_command(argv, *, cwd, environment, private, timeout, cancelled=None,
                log_limit=MAX_LOG_BYTES, cleanup_seconds=15.0, create_gradle_home=True):
    """Actual command + native ownership, with the explicit hosted Darwin domain.

    Ordinary hosted-runner trust: POSIX marker-inheriting descendants, Windows
    kernel Job Object. This is not containment of a malicious runner/child that
    erases its ownership markers. No process-name kill or shell interpolation.
    """
    require(type(timeout) in (int, float) and 0 < timeout <= 21600)
    require(type(log_limit) is int and 0 < log_limit <= MAX_LOG_BYTES)
    require(type(create_gradle_home) is bool)
    private = Path(private)
    private.mkdir(mode=0o700, parents=False, exist_ok=False)
    job, invocation = uuid.uuid4().hex, uuid.uuid4().hex
    home = Path(environment.get("GRADLE_USER_HOME", str(private / "gradle-home"))).absolute()
    if create_gradle_home:
        home.mkdir(parents=True, exist_ok=True)
    env = audit_processes.ownership_environment(dict(environment), job, invocation,
        str(private), str(home), allow_new_context=True)
    begin = time.monotonic()
    end = begin + timeout
    # Source-owned deadline for bounded nested operations; never trust a caller
    # override or reset the enclosing command's clock in a Terminal descendant.
    env["P2PKIT_CI_COMMAND_DEADLINE_NS"] = str(int(end * 1_000_000_000))
    scope, child, captures = None, None, []
    code, returncode, cleanup_known = "PASS", None, False
    native_error = None
    cleanup_reasons = set()
    pending_context = None
    ownership_fields = {}
    timed_out = False
    cancelled = cancelled or (lambda: False)
    try:
        scope = _command_scope(job, invocation, str(private), str(home), environment)
        child = scope.spawn(list(argv), str(cwd), env)
        captures = [Capture(child.stdout, private / "stdout.log", log_limit),
                    Capture(child.stderr, private / "stderr.log", log_limit)]
        for capture in captures:
            capture.thread.start()
        next_discovery = begin
        while True:
            if cancelled():
                code = "CANCELLED"
                break
            if any(item.error for item in captures):
                code = next(item.error for item in captures if item.error)
                break
            if time.monotonic() >= end:
                code, timed_out = "TIMEOUT", True
                break
            if time.monotonic() >= next_discovery:
                # The ownership backend retains live parent/descendant history.
                # Waiting until final drain loses intermediate parents of tools
                # that close inherited markers/pipes. Observe during work, at a
                # bounded cadence (no catch-up loop); drain still proves exit.
                scope.discover()
                next_discovery = time.monotonic() + 1.0
                if cancelled():
                    code = "CANCELLED"
                    break
                if any(item.error for item in captures):
                    code = next(item.error for item in captures if item.error)
                    break
            returncode = child.poll()
            if time.monotonic() >= end:
                code, timed_out = "TIMEOUT", True
                break
            if returncode is not None:
                code = "PASS" if returncode == 0 else "COMMAND_FAILED"
                break
            time.sleep(min(0.1, max(0.0, end - time.monotonic())))
    except BaseException as error:
        code = "SPAWN" if child is None else "CLEANUP"
        native_error = native_error_diagnostic(error)
    finally:
        cleanup_end = time.monotonic() + cleanup_seconds
        # spawn can register a real child before its discovery raises. Retain all
        # original leaders/pipes BEFORE close clears the POSIX leader registry.
        leaders = tuple(getattr(scope, "leaders", ())) if scope else ()
        pipes = tuple(stream for leader in leaders for stream in (leader.stdout, leader.stderr)
                      if stream is not None)
        try:
            if scope is not None:
                try:
                    live = scope.drain(grace=3.0, kill_wait=max(1.0, cleanup_seconds - 5.0), deadline=cleanup_end)
                except BaseException as error:
                    cleanup_reasons.add(cleanup_error_reason(error))
                    raise
                cleanup_known = not live and not scope.discovery_errors
                if live:
                    cleanup_reasons.add("LIVE_PROCESSES")
                if scope.discovery_errors:
                    cleanup_reasons.add("DISCOVERY_ERRORS")
                for leader in leaders:
                    remaining = max(0.01, cleanup_end - time.monotonic())
                    try:
                        leader.wait(timeout=remaining)
                    except BaseException:
                        cleanup_reasons.add("LEADER_WAIT")
                        raise
                if child is not None:
                    returncode = child.returncode
            else:
                cleanup_reasons.add("SCOPE_UNAVAILABLE")
        except BaseException:
            cleanup_known = False
        finally:
            if isinstance(scope, audit_processes.DarwinScope):
                pending_context = pending_context_diagnostic(scope)
            if isinstance(scope, _HostedDarwinScope):
                ownership_fields = {"ownershipBoundary": HOSTED_DARWIN_BOUNDARY,
                                    "outsideDomainObservations": scope.outside_domain_observations}
            try:
                if scope is not None:
                    scope.close()
            except BaseException:
                cleanup_known = False
                cleanup_reasons.add("SCOPE_CLOSE")
            for capture in captures:
                if capture.thread.ident is not None:
                    capture.thread.join(timeout=max(0.0, cleanup_end - time.monotonic()))
                for failed, reason in ((capture.thread.is_alive(), "CAPTURE_ACTIVE"),
                                       (not capture.eof, "PIPE_NO_EOF"),
                                       (not capture.closed, "PIPE_NOT_CLOSED")):
                    if failed:
                        cleanup_known = False
                        cleanup_reasons.add(reason)
                if capture.error and code == "PASS":
                    code = capture.error
            # Unadopted originals on an exceptional post-spawn path still close.
            captured = {id(item.pipe) for item in captures if item.thread.ident is not None}
            for pipe in pipes:
                if id(pipe) not in captured:
                    try:
                        pipe.close()
                    except BaseException:
                        cleanup_known = False
                        cleanup_reasons.add("ORIGINAL_PIPE_CLOSE")
        if not cleanup_known and code == "PASS":
            code = "CLEANUP"
    return {"exitCode": returncode, "timedOut": timed_out, "cleanupKnown": cleanup_known,
            "capturesClosed": len(captures) == 2 and all(
                item.thread.ident is not None and not item.thread.is_alive() and
                item.eof and item.closed and item.error is None for item in captures),
            "stage": "COMMAND", "code": code, "nativeError": native_error,
            "cleanupReasons": sorted(cleanup_reasons), "pendingContext": pending_context, **ownership_fields,
            "elapsedSeconds": round(time.monotonic() - begin, 6)}


def pending_failure_kind(message):
    """Reuse source-owned Darwin failure labels; never return message content."""
    if type(message) is not str or len(message) > 4096:
        return "OTHER"
    kind = PENDING_FAILURES.get(message, "OTHER")
    for operation, label in PENDING_OPERATIONS.items():
        if message.startswith("Darwin " + operation + " unresolved after bounded observation: "):
            return label
    return kind


def pending_context_diagnostic(scope):
    """Bounded recorded counts only; no native call or ownership/exit authority."""
    try:
        pending = scope.pending_discoveries
        if type(pending) is not dict or not 0 < len(pending) <= 1024:
            return None
        context = scope._pending_context()
        result = {**context, "pendingCount": len(pending), "sessionExclusions": {}, "failureKinds": {}}
        for record in pending.values():
            if type(record) is not dict:
                return None
            session = record.get("auditSessionExclusion")
            label = session if type(session) is str and session in audit_processes.DARWIN_SESSION_EXCLUSIONS else "NOT_RECORDED"
            result["sessionExclusions"][label] = result["sessionExclusions"].get(label, 0) + 1
            kind = pending_failure_kind(record.get("lastFailure"))
            result["failureKinds"][kind] = result["failureKinds"].get(kind, 0) + 1
        return public_pending_context(result)
    except BaseException:
        # A diagnostic failure must never replace the real cleanup failure or
        # prevent release of the original scope resources.
        return None


def public_pending_context(value):
    """Reject private labels, raw lifetime records, booleans and oversized counts."""
    fields = {"scope", "pendingCount", "roles", "parentage", "sessionExclusions", "failureKinds"}
    if (type(value) is not dict or set(value) != fields or value["scope"] != PENDING_CONTEXT_SCOPE
            or type(value["pendingCount"]) is not int or not 0 < value["pendingCount"] <= 1024):
        return None
    for field, labels in (("roles", audit_processes.DARWIN_DIAGNOSTIC_ROLES),
                          ("parentage", audit_processes.DARWIN_DIAGNOSTIC_PARENTAGE),
                          ("sessionExclusions", audit_processes.DARWIN_SESSION_EXCLUSIONS | {"NOT_RECORDED"}),
                          ("failureKinds", PENDING_FAILURE_LABELS)):
        counts = value[field]
        if (type(counts) is not dict or not set(counts) <= labels or
                not all(type(count) is int and 0 < count <= 1024 for count in counts.values()) or
                sum(counts.values()) != value["pendingCount"]):
            return None
    return {"scope": PENDING_CONTEXT_SCOPE, "pendingCount": value["pendingCount"],
            **{field: dict(value[field]) for field in fields - {"scope", "pendingCount"}}}


def cleanup_error_reason(error):
    """Map maintained backend failures, never their private text, to fixed labels."""
    if isinstance(error, audit_processes.DrainDeadlineExceeded):
        return "DRAIN_DEADLINE"
    exact = {
        "Unclassified Darwin lifetimes remain; cleanup is not proven": "DRAIN_UNCLASSIFIED",
        "Darwin drain did not establish three quiet censuses within its phase bounds": "DRAIN_NOT_QUIET",
        "Darwin known-token drain remains unresolved within its phase bounds": "DRAIN_SIGNAL_UNRESOLVED",
    }
    if (type(error) in (audit_processes.OwnershipError, audit_processes.DarwinObservationExhausted)
            and len(error.args) == 1 and type(error.args[0]) is str):
        return exact.get(error.args[0], "DRAIN_ERROR")
    return "DRAIN_ERROR"


def git_value(root, *arguments):
    # Fixed, small source-metadata queries only; the arbitrary actual task uses
    # run_command. Git output/error is never echoed to Actions.
    result = subprocess.run(["git", "-C", str(root), *arguments], stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30, check=False)
    require(result.returncode == 0 and len(result.stdout) <= MAX_JSON_BYTES, "SOURCE_CHANGED")
    return result.stdout.decode("utf-8").strip()


def source_identity(root):
    commit, tree = git_value(root, "rev-parse", "HEAD"), git_value(root, "rev-parse", "HEAD^{tree}")
    require(re.fullmatch(r"[0-9a-f]{40}", commit) and re.fullmatch(r"[0-9a-f]{40}", tree), "SOURCE_CHANGED")
    require(not git_value(root, "status", "--porcelain=v1", "--untracked-files=no"), "SOURCE_CHANGED")
    versions = re.findall(r"^VERSION_NAME=(\S+)$", (root / "gradle.properties").read_text(), re.M)
    require(len(versions) == 1 and re.fullmatch(r"[0-9A-Za-z][0-9A-Za-z.+_-]{0,79}", versions[0]), "SOURCE_CHANGED")
    return {"commit": commit, "tree": tree, "version": versions[0]}


def github_identity(environment, source):
    def value(name, pattern):
        result = environment.get(name, "")
        require(re.fullmatch(pattern, result))
        return result
    repository = value("GITHUB_REPOSITORY", r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+")
    require(value("GITHUB_SHA", r"[0-9a-f]{40}") == source["commit"], "SOURCE_CHANGED")
    workflow = value("GITHUB_WORKFLOW_REF", r"[^\r\n]{1,512}")
    prefix = repository + "/"
    require(workflow.startswith(prefix) and "@" in workflow)
    workflow_path = workflow[len(prefix):].rsplit("@", 1)[0]
    require(re.fullmatch(r"\.github/workflows/[A-Za-z0-9_.-]+\.ya?ml", workflow_path))
    return {"repository": repository, "runId": value("GITHUB_RUN_ID", r"[1-9][0-9]{0,19}"),
            "runAttempt": value("GITHUB_RUN_ATTEMPT", r"[1-9][0-9]{0,19}"),
            "workflowPath": workflow_path,
            "workflowSha": value("GITHUB_WORKFLOW_SHA", r"[0-9a-f]{40}"),
            "jobId": value("GITHUB_JOB", r"[A-Za-z_][A-Za-z0-9_-]{0,99}")}


def collect_reports(root, patterns, destination):
    destination.mkdir(mode=0o700)
    selected, total = set(), 0
    for pattern in patterns:
        require(not Path(pattern).is_absolute() and ".." not in Path(pattern).parts, "REPORTS")
        for path in root.glob(pattern):
            if path.is_dir() and not path.is_symlink():
                continue
            relative = path.relative_to(root)
            require(not any((root.joinpath(*relative.parts[:i])).is_symlink()
                            for i in range(1, len(relative.parts) + 1)), "REPORTS")
            info = path.lstat()
            require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1, "REPORTS")
            if relative in selected:
                continue
            selected.add(relative)
            total += info.st_size
            require(len(selected) <= MAX_REPORTS and total <= MAX_BUNDLE_BYTES, "REPORTS")
            target = destination / relative
            target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            shutil.copyfile(path, target)
            if os.name == "posix":
                os.chmod(target, 0o600)
            require(path.stat().st_size == info.st_size and target.stat().st_size == info.st_size, "REPORTS")


def archive_private(bundle, destination):
    files, total = [], 0
    for path in sorted(bundle.rglob("*")):
        info = path.lstat()
        require(not path.is_symlink() and (path.is_dir() or stat.S_ISREG(info.st_mode)), "REPORTS")
        if path.is_dir():
            continue
        total += info.st_size
        require(len(files) < MAX_REPORTS and total <= MAX_BUNDLE_BYTES, "REPORTS")
        files.append({"path": path.relative_to(bundle).as_posix(), **digest_file(path)})
    with tarfile.open(destination, "x:gz", format=tarfile.PAX_FORMAT) as archive:
        for record in files:
            path = bundle / record["path"]
            archive.add(path, arcname=record["path"], recursive=False)
            require(digest_file(path) == {key: record[key] for key in ("sha256", "bytes")}, "REPORTS")
    if os.name == "posix":
        os.chmod(destination, 0o600)
    return files


# Only these public, agent-free GPG operations may use direct Darwin ownership.
_PUBLIC_GPG_OPTIONS = ["--no-options", "--batch", "--no-tty", "--no-autostart", "--pinentry-mode", "error",
    "--homedir", "gnupg", "--no-auto-key-retrieve", "--no-auto-key-import", "--auto-key-locate", "clear",
    "--disable-dirmngr", "--no-random-seed-file", "--no-default-keyring", "--keyring", "./recipient.gpg"]


def _run_public_gpg(argv, *, cwd, environment, private, timeout, cancelled=None, log_limit=MAX_JSON_BYTES):
    """Fixed public GPG only, not a general command-supervisor opt-out.

    On Darwin trust the reviewed host GPG implementation plus the options that
    disable configuration, agents, key retrieval and network helpers. Observe
    the original child and both bounded pipes, NOT all new same-user processes
    on the host. This does not contain a malicious GPG that secretly detaches
    helpers and closes their pipes. Arbitrary test/build commands still use the
    unchanged descendant ownership backend; Windows retains its Job Object.
    """
    require(type(argv) is list and argv and all(type(arg) is str and arg and "\0" not in arg for arg in argv))
    require(os.path.isabs(argv[0]) and argv[1:1 + len(_PUBLIC_GPG_OPTIONS)] == _PUBLIC_GPG_OPTIONS)
    operation = argv[1 + len(_PUBLIC_GPG_OPTIONS):]
    listing = ["--with-colons", "--with-fingerprint", "--with-subkey-fingerprint"]
    public_listing = operation in (listing + ["--import-options", "show-only", "--import", "recipient.asc"],
                                   listing + ["--list-keys"])
    encryption = (len(operation) == 10 and operation[:5] ==
        ["--trust-model", "always", "--compress-algo", "none", "--recipient"] and
        re.fullmatch(r"[A-F0-9]{40}!", operation[5]) and operation[6] == "--output" and
        operation[8] == "--encrypt" and all(not value.startswith("-") and not os.path.isabs(value)
                                          for value in (operation[7], operation[9])))
    require((public_listing and timeout == 60) or (encryption and timeout == 300))
    require(type(log_limit) is int and 0 < log_limit <= MAX_JSON_BYTES)
    if platform.system() != "Darwin":
        return run_command(argv, cwd=cwd, environment=environment, private=private,
                           timeout=timeout, cancelled=cancelled, log_limit=log_limit)
    private = Path(private)
    private.mkdir(mode=0o700, parents=False, exist_ok=False)
    begin = time.monotonic()
    child, captures = None, []
    code, returncode, timed_out = "PASS", None, False
    cleanup_known, reasons = False, set()
    cancelled = cancelled or (lambda: False)
    try:
        if cancelled():
            code = "CANCELLED"
        else:
            child = subprocess.Popen(argv, cwd=cwd, env=environment, stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, close_fds=True, start_new_session=True)
            captures = [Capture(child.stdout, private / "stdout.log", log_limit),
                        Capture(child.stderr, private / "stderr.log", log_limit)]
            for capture in captures:
                capture.thread.start()
            while True:
                if cancelled():
                    code = "CANCELLED"
                    break
                if any(item.error for item in captures):
                    code = next(item.error for item in captures if item.error)
                    break
                if time.monotonic() >= begin + timeout:
                    code, timed_out = "TIMEOUT", True
                    break
                returncode = child.poll()
                if time.monotonic() >= begin + timeout:
                    code, timed_out = "TIMEOUT", True
                    break
                if returncode is not None:
                    code = "PASS" if returncode == 0 else "COMMAND_FAILED"
                    break
                time.sleep(min(0.1, max(0.0, begin + timeout - time.monotonic())))
    except BaseException:
        code = "SPAWN" if child is None else "CLEANUP"
    finally:
        cleanup_end = time.monotonic() + 15.0
        if child is not None:
            try:
                # Popen retains the original child; never signal a recycled
                # bare PID/group or anything after its terminal reaping.
                if child.poll() is None:
                    child.terminate()
                    try:
                        child.wait(timeout=min(3.0, max(0.01, cleanup_end - time.monotonic())))
                    except subprocess.TimeoutExpired:
                        if child.poll() is None:
                            child.kill()
                returncode = child.wait(timeout=max(0.01, cleanup_end - time.monotonic()))
                cleanup_known = returncode is not None
            except BaseException:
                reasons.add("LEADER_WAIT")
            captured = {id(item.pipe) for item in captures if item.thread.ident is not None}
            for pipe in (child.stdout, child.stderr):
                if pipe is not None and id(pipe) not in captured:
                    try:
                        pipe.close()
                    except BaseException:
                        reasons.add("ORIGINAL_PIPE_CLOSE")
        else:
            reasons.add("SCOPE_UNAVAILABLE")
        for capture in captures:
            if capture.thread.ident is not None:
                try:
                    capture.thread.join(timeout=max(0.0, cleanup_end - time.monotonic()))
                except BaseException:
                    reasons.add("CAPTURE_ACTIVE")
            for failed, reason in ((capture.thread.is_alive(), "CAPTURE_ACTIVE"),
                                   (not capture.eof, "PIPE_NO_EOF"), (not capture.closed, "PIPE_NOT_CLOSED")):
                if failed:
                    reasons.add(reason)
            if capture.error:
                cleanup_known = False
                if code == "PASS":
                    code = capture.error
        captures_closed = len(captures) == 2 and all(item.thread.ident is not None and
            not item.thread.is_alive() and item.eof and item.closed and item.error is None for item in captures)
        cleanup_known = cleanup_known and captures_closed and not reasons
        if not cleanup_known and code == "PASS":
            code = "CLEANUP"
        if code == "PASS" and cancelled():
            code = "CANCELLED"
    return {"exitCode": returncode, "timedOut": timed_out, "cleanupKnown": cleanup_known,
            "capturesClosed": captures_closed, "stage": "COMMAND", "code": code,
            "cleanupReasons": sorted(reasons), "pendingContext": None,
            "elapsedSeconds": round(time.monotonic() - begin, 6)}


def encrypt_archive(archive, output, key_raw, expected_sha, expected_fingerprint, work, environment, *, cancelled=None):
    require(re.fullmatch(r"[0-9a-f]{64}", expected_sha or "") and
            re.fullmatch(r"[A-Fa-f0-9]{40}", expected_fingerprint or ""), "RECIPIENT")
    require(hashlib.sha256(key_raw).hexdigest() == expected_sha, "RECIPIENT")
    packets = _public_armor(key_raw)  # Reject secret packets before a GPG invocation.
    key_file = work / "recipient.asc"
    write_private(key_file, key_raw)
    # Match the maintained public recipient validator: a real --import can
    # contact an agent even for public keys. Select only these validated packets.
    keyring = work / "recipient.gpg"
    write_private(keyring, packets)
    home = work / "gnupg"
    home.mkdir(mode=0o700)
    gpg = shutil.which("gpg", path=environment.get("PATH"))
    require(gpg is not None, "RECIPIENT")
    # The native supervisor sets cwd=work. Relative forward-slash arguments name
    # the same files for both native Windows GPG and Git/MSYS GPG; native drive
    # and backslash syntax is not a portable GPG homedir/filename contract.
    def filename(path):
        try:
            return os.path.relpath(path, work).replace(os.sep, "/")
        except ValueError:
            raise EvidenceError("ENCRYPTION") from None  # Different Windows drives.
    base = [gpg, *_PUBLIC_GPG_OPTIONS]
    environment = {key: value for key, value in environment.items() if key in {
        "PATH", "HOME", "USERPROFILE", "SYSTEMROOT", "SystemRoot", "WINDIR", "TEMP", "TMP", "TMPDIR",
        "LANG", "LC_ALL", "PATHEXT"}}
    # Public key only, no agent/keyserver/private-key lookup. GPG output remains
    # private. Only these fixed public operations use the Darwin direct-child boundary.
    def invoke(label, arguments, timeout=60):
        directory = work / label
        result = _run_public_gpg([*base, *arguments], cwd=work, environment=environment,
                             private=directory, timeout=timeout, log_limit=MAX_JSON_BYTES, cancelled=cancelled)
        if not (result["code"] == "PASS" and result["exitCode"] == 0 and result["cleanupKnown"]):
            error = EvidenceError("ENCRYPTION")
            # Only this source-owned exception carries a fixed public diagnostic.
            # Unknown writer retirement must also prevent erasing its private files.
            error.encryption_diagnostic = {
                "phase": label, "outcome": public_outcome(result),
                "categories": gpg_failure_categories(directory) if result["cleanupKnown"] else []}
            raise error
        return (directory / "stdout.log").read_bytes()
    listing = invoke("key-show", ["--with-colons", "--with-fingerprint", "--with-subkey-fingerprint",
                                   "--import-options", "show-only", "--import", filename(key_file)])
    fingerprint, expires_at = _key_identity(listing, expected_fingerprint.upper())
    selected = invoke("key-list", ["--with-colons", "--with-fingerprint", "--with-subkey-fingerprint", "--list-keys"])
    require(_key_identity(selected, expected_fingerprint.upper()) == (fingerprint, expires_at), "RECIPIENT")
    invoke("encrypt", ["--trust-model", "always", "--compress-algo", "none", "--recipient", fingerprint + "!",
                        "--output", filename(output), "--encrypt", filename(archive)], timeout=300)
    require(output.is_file() and 32 < output.stat().st_size <= MAX_BUNDLE_BYTES + 16 * 1024 * 1024, "ENCRYPTION")
    return {**digest_file(output), "recipientFingerprint": expected_fingerprint.upper()}


def encrypt_closed_failure_captures(root, private, output, environment, *, cancelled=None):
    """Protect exactly the two independently closed captures, never mutable reports.

    The caller has already retained a failed receipt. This archive does not
    prove source stability, task completion or process retirement.
    """
    work = private / "failure-encryption"
    work.mkdir(mode=0o700)
    bundle = work / "bundle"
    bundle.mkdir(mode=0o700)
    names = ("stderr.log", "stdout.log")
    for name in names:
        original = private / "command" / name
        info = original.lstat()
        require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and
                0 <= info.st_size <= MAX_LOG_BYTES, "REPORTS")
        target = bundle / name
        shutil.copyfile(original, target)
        if os.name == "posix":
            os.chmod(target, 0o600)
        require(digest_file(original) == digest_file(target), "REPORTS")
    archive = work / "evidence.tar.gz"
    records = archive_private(bundle, archive)
    require(tuple(row["path"] for row in records) == names, "REPORTS")
    with (root / ".github/ci-evidence-recipient.asc").open("rb") as public_key:
        key_raw = public_key.read(64 * 1024 + 1)
    require(0 < len(key_raw) <= 64 * 1024, "RECIPIENT")
    # Partial ciphertext stays private, including an unknown GPG retirement.
    cipher = work / "evidence.tar.gz.gpg"
    metadata = encrypt_archive(archive, cipher, key_raw,
        environment.get("CI_EVIDENCE_RECIPIENT_SHA256", ""),
        environment.get("CI_EVIDENCE_RECIPIENT_FINGERPRINT", ""), work, environment, cancelled=cancelled)
    target = output / "evidence.tar.gz.gpg"
    shutil.copyfile(cipher, target)
    if os.name == "posix":
        os.chmod(target, 0o600)
    require(digest_file(target) == {key: metadata[key] for key in ("bytes", "sha256")}, "ENCRYPTION")
    return {"kind": "CLOSED_CAPTURES_ONLY_NOT_QUALIFICATION", "sourceValidation": "INITIAL_ONLY",
            "members": list(names), "privateArchive": digest_file(archive), "ciphertext": metadata}


def tool_identity(tools_file):
    result = {"python": {"version": platform.python_version(),
                         "executableSha256": digest_file(Path(sys.executable).resolve())["sha256"]}}
    if tools_file.exists():
        supplied = read_json(tools_file)
        require(type(supplied) is dict and len(supplied) <= 12)
        for name, item in supplied.items():
            require(name in {"java", "gradle", "node", "xcode", "android-sdk", "gpg"} and type(item) is dict and
                    set(item) == {"version", "executableSha256"})
            require(type(item["version"]) is str and re.fullmatch(r"[A-Za-z0-9 ._+()/-]{1,120}", item["version"]) and
                    re.fullmatch(r"[0-9a-f]{64}", item["executableSha256"]))
            result[name] = item
    return result


def component_tasks(root, component):
    """Optional public diagnostic, never a replacement for actual task outcome.

    Only fixed source-owned task names and integral exit codes leave the private
    report. Missing/malformed reports remain unavailable, not invented success.
    """
    try:
        report = read_json(root / "build/reports/ci-component" / (component + ".json"), 64 * 1024)
        require(type(report) is dict and set(report) == {"component", "tasks", "exitCode"} and
                report["component"] == component and type(report["exitCode"]) is int)
        rows = report["tasks"]
        require(type(rows) is list and len(rows) <= 100)
        for row in rows:
            require(type(row) is dict and set(row) == {"task", "exitCode"} and
                    type(row["task"]) is str and row["task"] in TASK_NAMES and
                    type(row["exitCode"]) is int and -(2**31) <= row["exitCode"] < 2**32)
        return [{"task": row["task"], "exitCode": row["exitCode"]} for row in rows]
    except (OSError, ValueError, TypeError, KeyError, EvidenceError):
        return None


def junit_failures(root, source_commit="HEAD"):
    """Project failed JUnit cases onto public source names, never error text.

    Unmatched/dynamic names remain private. This diagnostic is not acceptance;
    malformed/oversized reports cannot create passing test evidence.
    """
    def bounded(path, limit):
        require(not any(p.is_symlink() for p in (path, *path.parents)))
        info = path.stat()
        require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and info.st_size <= limit)
        with path.open("rb") as stream:
            raw = stream.read(limit + 1)
        require(len(raw) == info.st_size)
        return raw

    try:
        blobs = {}
        for record in git_value(root, "--no-replace-objects", "ls-tree", "-r", "-z", source_commit).split("\0"):
            if record:
                identity, name = record.split("\t", 1)
                mode, kind, blob = identity.split()
                if mode in ("100644", "100755") and kind == "blob" and name.endswith((".kt", ".java")):
                    blobs[name] = blob
    except (OSError, ValueError, subprocess.SubprocessError, EvidenceError):
        return []

    def jmdns_details(failures, test_source):
        # Only this exact tracked fixture may define public labels. Never import
        # the RPC branch-specific runner or publish arbitrary assertion text.
        fixture = "library/p2p-transport-lan/src/jvmTest/java/dev/p2pkit/transport/lan/internal/jmdns/impl/JmdnsCloseLifecycleFixture.java"
        try:
            content = bounded(root / fixture, 1024 * 1024)
            blob = hashlib.sha1(b"blob " + str(len(content)).encode() + b"\0" + content).hexdigest()
            require(blob == blobs.get(fixture))
            labels = set(re.findall(r'"([a-z][A-Za-z0-9_]{4,100})"', content.decode("utf-8")))
            require(len(labels) <= 256)
            text = "\n".join(" ".join(node.itertext()) + " " + node.get("message", "") + " " + node.get("type", "") for node in failures)
            codes = {label for label in labels if re.search(r"(?<![A-Za-z0-9_])" + re.escape(label) +
                                                           r"(?![A-Za-z0-9_])", text)}
            jdk_message = "The real-resource close fixture requires JDK 17"
            if jdk_message in text and jdk_message in test_source and "jdk17_required" in labels:
                codes.add("jdk17_required")
            # Same fixed exception vocabulary as the maintained RPC diagnostic.
            classes = {"java.lang.AssertionError", "kotlin.AssertionError", "java.lang.IllegalStateException",
                       "org.opentest4j.AssertionFailedError", "java.net.NoRouteToHostException",
                       "java.net.SocketException", "java.net.BindException", "java.io.IOException",
                       "java.lang.InterruptedException", "java.util.concurrent.TimeoutException"}
            result = {"sourceDefinedCodes": sorted(codes), "exceptionClasses": sorted(cls for cls in classes
                      if re.search(r"(?<![A-Za-z0-9_.$])" + re.escape(cls) + r"(?![A-Za-z0-9_.$])", text))}
            # Only the source-bound original child's already emitted, finite
            # interface/route observations. No old runner import, native query,
            # route text, interface identity, permission or readiness inference.
            boolean, known = r"(?:true|false)", r"(?:true|false|UNKNOWN)"
            failure_class = "(?:" + "|".join(re.escape(cls) for cls in sorted(classes)) + ")"
            patterns = [
                "startup firstSendFailureClass=" + failure_class + " firstSendDestinationIpv4Mdns=" + known,
                "startup interfaceSnapshot=BEFORE_WAIT selectedKnown=" + boolean + " hostKnown=" + boolean
                + " socketKnown=" + boolean + " selectedHostMatch=" + known + " selectedSocketMatch=" + known
                + " hostSocketMatch=" + known,
                "startup route (?:queryStarted=false reason=(?:FIRST_SEND_DESTINATION_NOT_MATCHED|SELECTED_INTERFACE_UNKNOWN)"
                + "|observation=POST_FAILURE scope=SELECTED_IPV4_MDNS queryStarted=true queryCompleted=" + boolean
                + " exitZero=" + known + ")",
                "startup route outputWithinBound=" + boolean,
                "startup route processReaped=" + boolean,
                "startup route queryFailureClass=" + failure_class,
                "startup route interfaceParsed=" + boolean + " selectedInterfaceMatch=" + known
                + " flagsParsed=" + boolean,
                *("startup routeFlag=" + flag + " present=" + boolean
                  for flag in ("UP", "REJECT", "BLACKHOLE", "GATEWAY", "IFSCOPE")),
                "startup explicitAddress=" + boolean + " linkLocal=" + boolean
                + " virtualInterface=" + boolean + " pointToPoint=" + boolean,
            ]
            patterns = [re.compile(pattern) for pattern in patterns]
            markers, observations = {}, 0
            for failure in failures:
                # XML may repeat the transcript in body and message. Preserve
                # literal line boundaries; stripping arbitrary prefixes or using
                # Unicode splitlines could manufacture an apparently safe line.
                for value in (failure.text or "", failure.get("message", "")):
                    if len(value) > 128 * 1024:
                        return result
                    for line in value.split("\n"):
                        if line.endswith("\r"):
                            line = line[:-1]
                        if len(line) > 512:
                            continue
                        for index, pattern in enumerate(patterns):
                            if pattern.fullmatch(line):
                                observations += 1
                                # Conflicting values and excessive repetitions
                                # cannot select a favorable route observation.
                                if observations > 32 or (index in markers and markers[index] != line):
                                    return result
                                markers[index] = line
                                break
            if markers:
                result["startupMarkers"] = sorted(markers.values())
            return result
        except (OSError, ValueError, UnicodeError, EvidenceError):
            return None

    rows, consumed = [], 0
    for number, path in enumerate(root.glob("**/build/test-results/**/TEST-*.xml")):
        if number >= MAX_REPORTS or consumed >= 32 * 1024 * 1024 or len(rows) >= 32:
            break
        try:
            raw = bounded(path, 4 * 1024 * 1024)
            consumed += len(raw)
            if re.search(br"<!\s*(DOCTYPE|ENTITY)\b", raw, re.I):
                continue
            document = ET.fromstring(raw)
            for case in document.iter("testcase"):
                failures = [node for node in case if node.tag in ("failure", "error")]
                if not failures or len(rows) >= 32:
                    continue
                classname, method = case.get("classname", ""), case.get("name", "")
                if not re.fullmatch(r"(?:[A-Za-z_]\w*\.)+[A-Za-z_]\w*", classname):
                    continue
                # Gradle may append a target suffix; publish only the source identifier.
                match = re.fullmatch(r"([A-Za-z_]\w*)(?:\(\)|\[[A-Za-z0-9_-]{1,40}\])?", method)
                if not match:
                    continue
                method = match[1]
                package, cls = classname.rsplit(".", 1)
                for group in ("library", "samples"):
                    # KMP uses commonTest/jvmTest; ordinary JVM modules use exact test.
                    sources = (source for source_set in ("*Test", "test")
                               for source in (root / group).glob("*/src/" + source_set + "/**/" + cls + ".kt"))
                    for source in sources:
                        relative = source.relative_to(root).as_posix()
                        if relative not in blobs:
                            continue
                        content = bounded(source, 1024 * 1024)
                        blob = hashlib.sha1(b"blob " + str(len(content)).encode() + b"\0" + content).hexdigest()
                        if blob != blobs[relative]:
                            continue
                        text = content.decode("utf-8")
                        if (not re.search(r"(?m)^package " + re.escape(package) + r"\s*$", text) or
                            not re.search(r"\bclass\s+" + re.escape(cls) + r"\b", text) or
                            not re.search(r"\bfun\s+" + re.escape(method) + r"\s*\(", text)):
                            continue
                        kinds = {"java.lang.AssertionError": "ASSERTION", "org.opentest4j.AssertionFailedError": "ASSERTION",
                                 "kotlinx.coroutines.TimeoutCancellationException": "TIMEOUT",
                                 "java.net.NoRouteToHostException": "NETWORK_NO_ROUTE"}
                        row = {"source": source.relative_to(root).as_posix(), "test": method,
                               "kinds": sorted({kinds.get(node.get("type"), "OTHER") for node in failures})}
                        if relative == "library/p2p-transport-lan/src/jvmTest/kotlin/dev/p2pkit/transport/lan/JmdnsCloseLifecycleTest.kt" and method in (
                                "realResourceCloseRegressionsExitNaturally", "failedSendsCannotMultiplyTheSdkCleanupBudget"):
                            details = jmdns_details(failures, text)
                            if details is not None:
                                row["jmdnsFixture"] = details
                        if row not in rows:
                            rows.append(row)
        except (OSError, ValueError, UnicodeError, ET.ParseError, EvidenceError):
            continue
    return rows[:32]


# Fixed source-authored terminal errors only. These observations explain a
# refusal, never qualify an MSI or disclose arbitrary exception text/paths.
RPC_PACKAGE_ERRORS = {
    "Input exceeds its bound": "RPC_MSI_INPUT_BOUND",
    "Input changed during inspection": "RPC_MSI_INPUT_CHANGED",
    "Expected an ordinary file": "RPC_MSI_NONORDINARY_FILE",
    "Expected an ordinary directory": "RPC_MSI_NONORDINARY_DIRECTORY",
    "Unsafe logical component": "RPC_MSI_UNSAFE_COMPONENT",
    "Image has case-colliding paths": "RPC_MSI_IMAGE_CASE_COLLISION",
    "Extraction File inventory differs from MSI table": "RPC_MSI_EXTRACTION_INVENTORY",
    "MSI application path is outside INSTALLDIR or duplicated": "RPC_MSI_APPLICATION_PATH",
    "Decompiler Source escapes or differs from the owned extraction": "RPC_MSI_EXTRACTION_SOURCE",
    "Full image differs from earlier pinned components": "RPC_MSI_PINNED_IMAGE_CHANGED",
    "MSI and completed image application paths differ": "RPC_MSI_PAYLOAD_PATHS",
    "MSI application payload differs from completed image": "RPC_MSI_PAYLOAD_BYTES",
    "Application payload changed during full inspection": "RPC_MSI_PAYLOAD_CHANGED",
    "MSI package metadata differs from fixed package name": "RPC_MSI_PACKAGE_METADATA",
    "Original image package metadata conflicts with installer": "RPC_MSI_IMAGE_PACKAGE_METADATA",
}


def rpc_package_path_mismatch(value):
    """Closed finite metadata only; name digests are observations, never a passing inventory."""
    counts = ("imageFiles", "msiFiles", "missingFiles", "extraFiles")
    lists = ("missingNameSha256", "extraNameSha256")
    if (type(value) is not dict or set(value) != {*counts, *lists, "caseFoldEqual"} or
            any(type(value[key]) is not int or not 0 <= value[key] <= 50_000 for key in counts) or
            type(value["caseFoldEqual"]) is not bool):
        return None
    image, msi, missing, extra = (value[key] for key in counts)
    if (not image or not msi or not missing + extra or missing > image or extra > msi or
            image - missing != msi - extra or
            value["caseFoldEqual"] and (image != msi or missing != extra)):
        return None
    for key, count in zip(lists, (missing, extra)):
        items = value[key]
        if (type(items) is not list or len(items) != min(count, 16) or
                any(type(item) is not str or re.fullmatch(r"[0-9a-f]{64}", item) is None for item in items) or
                items != sorted(set(items))):
            return None
    if set(value[lists[0]]) & set(value[lists[1]]):
        return None
    return {**{key: value[key] for key in (*counts, "caseFoldEqual")},
            **{key: list(value[key]) for key in lists}}


def swift_sample_failure_observations(root, command_directory, source_commit="HEAD"):
    """Source-matched failure locations/names only; never a Swift success gate."""
    def bounded(path, limit):
        require(not any(p.is_symlink() for p in (path, *path.parents)))
        info = path.stat()
        require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and info.st_size <= limit)
        with path.open("rb") as stream:
            raw = stream.read(limit + 1)
        require(len(raw) == info.st_size)
        return raw

    try:
        files, methods = {}, {}
        prefix = "samples/iosApp/"
        for record in git_value(root, "--no-replace-objects", "ls-tree", "-r", "-z", source_commit, prefix).split("\0"):
            if not record:
                continue
            identity, name = record.split("\t", 1)
            mode, kind, blob = identity.split()
            if (mode != "100644" or kind != "blob" or re.fullmatch(re.escape(prefix) +
                    r"(?:[A-Za-z][A-Za-z0-9_]*/)*[A-Za-z][A-Za-z0-9_]*\.swift", name) is None):
                continue
            raw = bounded(root / name, 512 * 1024)
            require(hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest() == blob)
            text = raw.decode("utf-8")
            files[name] = len(text.splitlines())
            require(len(files) <= 64)
            owners = re.findall(r"\bclass (\w+): XCTestCase", text)
            if len(owners) == 1:
                for method in re.findall(r"\bfunc (test\w+)\(", text):
                    key = (owners[0], method)
                    require(key not in methods)
                    methods[key] = name
                    require(len(methods) <= 1024)
        locations, failures = [], []
        for name in ("stdout.log", "stderr.log"):
            path = Path(command_directory) / name
            if not path.exists():
                continue
            for line in bounded(path, MAX_LOG_BYTES).decode("utf-8", errors="replace").split("\n"):
                if len(line) > 4096:
                    continue
                location = re.match(re.escape(str(root) + "/") + r"([^:\n]+):(\d{1,5})(?::(\d{1,4}))?: (error|warning):", line)
                if location:
                    relative = Path(os.path.normpath(location[1])).as_posix()
                    if relative in files and 0 < int(location[2]) <= files[relative]:
                        row = {"source": relative, "line": int(location[2]), "kind": location[4].upper()}
                        if row not in locations and len(locations) < 32:
                            locations.append(row)
                case = re.match(r"Test Case '-\[(?:[A-Za-z_][A-Za-z0-9_]*\.)?([A-Za-z_]\w*) (test\w+)\]' (failed|skipped) \(", line)
                if case is None:
                    case = re.match(r"Test case '(?:[A-Za-z_][A-Za-z0-9_]*\.)?([A-Za-z_]\w*)\.(test\w+)\(\)' (failed|skipped) on ", line)
                if case and (case[1], case[2]) in methods:
                    row = {"source": methods[(case[1], case[2])], "test": case[2], "status": case[3].upper()}
                    if row not in failures and len(failures) < 32:
                        failures.append(row)
        return {"locations": locations, "failedSourceTests": failures} if locations or failures else None
    except (OSError, ValueError, UnicodeError, TypeError, EvidenceError, subprocess.SubprocessError):
        return None


def rpc_ios_phone_observations(root, source_commit="HEAD"):
    """Finite observations from closed original Xcode captures, not a new gate.

    Publish only fixed command labels/exits and source-blob-matched Swift
    locations/test identifiers. Compiler/assertion messages, device identities,
    command arguments and paths outside the tracked phone source stay private.
    Call only after the enclosing process domain is known retired.
    """
    report = root / "build/reports/rpc-io-phone"
    if not report.is_dir():
        return None

    def bounded(path, limit):
        require(not any(p.is_symlink() for p in (path, *path.parents)))
        info = path.stat()
        require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and info.st_size <= limit)
        with path.open("rb") as stream:
            raw = stream.read(limit + 1)
        require(len(raw) == info.st_size)
        return raw

    def walk(value):
        pending, visited = [value], 0
        while pending:
            item = pending.pop()
            visited += 1
            require(visited <= 50000)
            if type(item) is dict:
                yield item
                pending.extend(item.values())
            elif type(item) is list:
                pending.extend(item)

    def exit_code(value):
        return value is None or type(value) is int and -(2**31) <= value < 2**32

    try:
        commands = json.loads(bounded(report / "commands.json", 64 * 1024))
        labels = {"source-before", "tree-before", "status-before", "xcode-version", "runtimes", "framework",
                  "project", "project-inspection", "create-simulator", "boot", "boot-ready", "xctest", "test-actions",
                  "shutdown", "delete", "retired", "source-after", "status-after", "tree-after"}
        labels.update("test-summary-" + str(index) for index in range(8))
        require(type(commands) is list and 0 < len(commands) <= len(labels))
        require(all(type(row) is dict and row.get("label") in labels and "exitCode" in row and
                    exit_code(row["exitCode"]) and exit_code(row.get("observedExitCode")) for row in commands))
        require(len({row["label"] for row in commands}) == len(commands))
        observed = [{"label": row["label"], "exitCode": row["exitCode"],
                     "observedExitCode": row.get("observedExitCode")} for row in commands]
        files, expected = {}, {"p2pkit-rpc-phone-tests": {}, "p2pkit-rpc-phone-uitests": {}}
        prefix = "samples/p2p-sample-rpc/phone-ios/"
        for record in git_value(root, "--no-replace-objects", "ls-tree", "-r", "-z", source_commit, prefix).split("\0"):
            if not record:
                continue
            identity, name = record.split("\t", 1)
            mode, kind, blob = identity.split()
            if (mode != "100644" or kind != "blob" or
                    re.fullmatch(re.escape(prefix) + r"(?:Sources|Tests|UITests)/[A-Za-z][A-Za-z0-9_]*\.swift", name) is None):
                continue
            raw = bounded(root / name, 512 * 1024)
            require(hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest() == blob)
            text = raw.decode("utf-8")
            files[name] = len(text.splitlines())
            require(len(files) <= 64)
            target = ("p2pkit-rpc-phone-uitests" if name.startswith(prefix + "UITests/") else
                      "p2pkit-rpc-phone-tests" if name.startswith(prefix + "Tests/") else None)
            if target is not None:
                owners = re.findall(r"final class (\w+): XCTestCase", text)
                require(len(owners) == 1)
                for method in re.findall(r"\bfunc (test\w+)\(", text):
                    identifier = owners[0] + "/" + method + "()"
                    require(identifier not in expected[target])
                    expected[target][identifier] = {"source": name, "test": method}
        require(files and all(0 < len(methods) <= 256 for methods in expected.values()))
        locations, test_locations = [], []
        for name in ("xctest.stdout", "xctest.stderr"):
            path = report / name
            if not path.exists():
                continue
            for line in bounded(path, MAX_LOG_BYTES).decode("utf-8", errors="replace").split("\n"):
                if len(line) > 4096:
                    continue
                match = re.match(re.escape(str(root) + "/") + r"([^:\n]+):(\d{1,5}):(\d{1,4}): (error|warning):", line)
                if match and match[1] in files and 0 < int(match[2]) <= files[match[1]] and int(match[3]) > 0:
                    row = {"source": match[1], "line": int(match[2]), "column": int(match[3]), "kind": match[4].upper()}
                    if row not in locations and len(locations) < 32:
                        locations.append(row)
                # XCTest assertions omit the compiler's column. Crossbind the
                # actual source-known class/method to this exact tracked file;
                # discard the assertion message and its potentially private values.
                failure = re.match(re.escape(str(root) + "/") +
                    r"([^:\n]+):(\d{1,5}): error: -\[(?:[A-Za-z_]\w*\.)?([A-Za-z_]\w*) (test\w+)\] :", line)
                if failure and failure[1] in files and 0 < int(failure[2]) <= files[failure[1]]:
                    identifier = failure[3] + "/" + failure[4] + "()"
                    if any(methods.get(identifier) == {"source": failure[1], "test": failure[4]}
                           for methods in expected.values()):
                        row = {"source": failure[1], "line": int(failure[2]), "test": failure[4],
                               "kind": "XCTEST_FAILURE"}
                        if row not in test_locations and len(test_locations) < 32:
                            test_locations.append(row)
        cases, unexpected_targets = {target: [] for target in expected}, 0
        for command in commands:
            if not command["label"].startswith("test-summary-") or command["exitCode"] != 0:
                continue
            document = json.loads(bounded(report / (command["label"] + ".stdout"), MAX_JSON_BYTES))
            for entry in walk(document):
                if entry.get("_type", {}).get("_name") != "ActionTestableSummary":
                    continue
                target = entry.get("targetName", {}).get("_value")
                if target not in expected:
                    unexpected_targets += 1
                    continue
                for case in walk(entry.get("tests", {})):
                    if case.get("_type", {}).get("_name") == "ActionTestMetadata":
                        identifier, status = (case.get(key, {}).get("_value") for key in ("identifier", "testStatus"))
                        require(type(identifier) is str and type(status) is str)
                        cases[target].append((identifier, status))
                        require(sum(len(rows) for rows in cases.values()) <= 512)
        tests = []
        for target, methods in expected.items():
            actual = cases[target]
            matched = len(actual) == len(methods) and {name for name, _ in actual} == set(methods)
            source_cases = [{**methods[name], "status": status if status in {"Success", "Failure", "Skipped", "Expected Failure"}
                            else "UNKNOWN"} for name, status in actual if name in methods]
            tests.append({"target": target, "expected": len(methods), "observed": len(actual),
                          "inventoryMatched": matched, "allSuccessful": matched and all(status == "Success" for _, status in actual),
                          "sourceCases": sorted(source_cases, key=lambda row: (row["source"], row["test"], row["status"]))})
        return {"scope": "SOURCE_MATCHED_IOS_EXECUTION_OBSERVATIONS_NOT_PHYSICAL_QUALIFICATION",
                "commands": observed, "compilerLocations": locations, "testFailureLocations": test_locations, "tests": tests,
                "unexpectedTargets": unexpected_targets}
    except (OSError, ValueError, UnicodeError, TypeError, AttributeError, RecursionError, EvidenceError, subprocess.SubprocessError):
        return None


def failure_diagnostics(root, command_directory, source_commit="HEAD", *, include_reports=True):
    """Public error identifiers only; logs/payloads/paths remain encrypted.

    These observations help diagnose a failed command, never qualify it. Scan
    the already bounded closed captures; never copy arbitrary error messages.
    """
    categories, tasks, publication_lines, platform_lines = set(), set(), [], []
    rpc_package_lines = []
    rpc_path_observations = []
    dependency_exits, duplicate_dependency_steps = {}, set()
    generator_phases, duplicate_generator_phases = {}, set()
    phase_observations, duplicate_phases = {}, set()
    inventory_observations, signature_counts = [], []
    consumer_snapshots, duplicate_consumers = {}, set()
    modules = {"p2p-core", "p2p-transport-lan", "p2p-rpc", "p2p-network-provisioning-android",
               "p2p-network-provisioning-desktop", "p2p-sample-android", "p2p-sample-desktop",
               "p2p-sample-desktop-ui", "p2p-sample-diagnostics", "sample-kmp-shared", "p2p-sample-rpc", "buildSrc"}
    task_names = {"allTests", "check", "jvmTest", "test", "testDebugUnitTest", "testAndroidHostTest", "iosX64Test",
                  "iosSimulatorArm64Test", "dokkaGeneratePublicationHtml", "checkKotlinAbi", "checkAndroidAbi",
                  "publishToMavenLocal", "assembleDebug", "packageMsi", "packageDmg", "packageDeb", "compileJava"}
    task_names.update(prefix + target for prefix in ("compileKotlin", "compileTestKotlin", "linkDebugTest", "cinteropP2pkit_nw")
                      for target in ("Jvm", "IosArm64", "IosSimulatorArm64", "IosX64"))
    phase_labels = {"simulator-macos-version", "simulator-xcode-version", "simulator-first-launch",
                    "simulator-runtimes", "intel-bootstatus-help", "simulator-devices", "intel-boot",
                    "intel-bootstatus", "intel-prelaunch", "intel-retire-before", "intel-shutdown", "intel-retire-after"}
    bundle_phases = {
        "initialization": "BUNDLE_TEST_INITIALIZATION",
        "snapshot rejection": "BUNDLE_TEST_SNAPSHOT_REJECTION",
        "release fixture checkout": "BUNDLE_TEST_RELEASE_FIXTURE_CHECKOUT",
        "signature-status parser regression": "BUNDLE_TEST_SIGNATURE_STATUS_PARSER",
        "missing-key rejection": "BUNDLE_TEST_MISSING_KEY_REJECTION",
        "disposable key generation": "BUNDLE_TEST_DISPOSABLE_KEY_GENERATION",
        "disposable key export": "BUNDLE_TEST_DISPOSABLE_KEY_EXPORT",
        "signed bundle build": "BUNDLE_TEST_SIGNED_BUILD",
        "bundle verification": "BUNDLE_TEST_VERIFICATION",
    }
    known = {
        b"Dependency verification failed": "DEPENDENCY_INTEGRITY",
        b"Unresolved reference": "COMPILATION_UNRESOLVED_REFERENCE",
        b"unresolved link": "DOCUMENTATION_UNRESOLVED_LINK",
        b"NoRouteToHostException": "NETWORK_NO_ROUTE",
        b"host_not_announced": "LAN_HOST_NOT_ANNOUNCED",
        b"SIMULATOR_UNADMITTED_XCODE": "SIMULATOR_XCODE_MISMATCH",
        b"SIMULATOR_RUNTIME_UNAVAILABLE_OR_CHANGED": "SIMULATOR_RUNTIME_MISMATCH",
        b"INTEL_PHASE_FAILED": "SIMULATOR_COMMAND_FAILED",
        b"extraction failed on specified lockfile": "OSV_LOCKFILE_EXTRACTION_FAILED",
        b"cannot determine extractor": "OSV_UNSUPPORTED_LOCKFILE",
        b"FAIL embedded JmDNS": "PUBLICATION_EMBEDDED_JMDNS",
        b"publishing artifact set incomplete": "PUBLICATION_INCOMPLETE",
        b"Cannot convert the provided notation": "GRADLE_INVALID_NOTATION",
        b"Could not determine the dependencies of task": "GRADLE_TASK_DEPENDENCIES",
        b"Could not resolve all files": "GRADLE_DEPENDENCY_RESOLUTION",
        b"could not determine extractor": "OSV_UNSUPPORTED_LOCKFILE",
    }
    for name in ("stdout.log", "stderr.log"):
        try:
            stream = (Path(command_directory) / name).open("rb")
        except OSError:
            continue  # A refused spawn may have no original output pipes.
        with stream:
            for line in stream:
                # The captures themselves are bounded; cap each parsed line too.
                if len(line) > 4096:
                    continue
                if re.fullmatch(rb"RPC_WINDOWS_PACKAGE_REFUSAL_RECORD_FAILED\r?\n?", line):
                    categories.add("RPC_MSI_REFUSAL_RECORD_FAILED")
                package_error = re.fullmatch(rb"RPC_WINDOWS_PACKAGE_FAILURE ([A-Z_]{1,64})\r?\n?", line)
                if package_error and package_error[1].decode("ascii") in RPC_PACKAGE_ERRORS.values():
                    categories.add(package_error[1].decode("ascii"))
                location = re.fullmatch(rb"RPC_WINDOWS_PACKAGE_CHECK_LINES ([1-9][0-9]{0,4}(?:,[1-9][0-9]{0,4}){0,15})\r?\n?", line)
                if location and not rpc_package_lines:
                    rpc_package_lines = [int(value) for value in location[1].split(b",")]
                path_marker = re.fullmatch(rb"RPC_WINDOWS_PACKAGE_PATHS ([ -~]{1,3500})\r?\n?", line)
                if path_marker:
                    try:
                        decoded = json.loads(path_marker[1])
                        observation = rpc_package_path_mismatch(decoded)
                        if (observation is not None and json.dumps(decoded, sort_keys=True,
                                separators=(",", ":")).encode("ascii") == path_marker[1]):
                            if len(rpc_path_observations) < 2:
                                rpc_path_observations.append(observation)
                    except (ValueError, TypeError, UnicodeError):
                        pass
                consumer_keys = ("index", "listeners", "added", "resolved", "other_added", "other_resolved",
                                 "remote_srv", "remote_txt", "peers", "sees_other")
                consumer = re.fullmatch(rb"CONSUMER_DISCOVERY_SNAPSHOT " + b" ".join(
                    key.upper().encode() + rb" (0|[1-9][0-9]{0,3})" for key in consumer_keys) + rb"\r?\n?", line)
                if consumer:
                    values = dict(zip(consumer_keys, map(int, consumer.groups())))
                    index = values["index"]
                    if (index in (0, 1) and values["listeners"] <= 32 and
                            all(value <= 4096 for value in values.values()) and
                            values["other_resolved"] <= values["other_added"] <= values["added"] and
                            values["other_resolved"] <= values["resolved"] <= values["added"] and
                            all(values[key] in (0, 1) for key in ("remote_srv", "remote_txt", "sees_other"))):
                        if index in consumer_snapshots:
                            duplicate_consumers.add(index)
                        else:
                            consumer_snapshots[index] = values
                if line.removesuffix(b"\n").removesuffix(b"\r") == b"CONSUMER_DISCOVERY_SNAPSHOT_UNAVAILABLE":
                    categories.add("CONSUMER_DISCOVERY_SNAPSHOT_UNAVAILABLE")
                consumer_failure = re.fullmatch(
                    rb"consumer-lan failedPhase=(create-kits|advertise-[01]|discover-[01]|capture-owners|"
                    rb"metadata-[01]|await-peer-[01]) errorType=TimeoutCancellationException\r?\n?", line)
                if consumer_failure:
                    categories.add("CONSUMER_TIMEOUT_" + consumer_failure[1].decode("ascii").upper().replace("-", "_"))
                consumer_task = re.fullmatch(rb"> Task :lanJvm:(runEmbeddedJmdns(?:Coexistence(?:UpstreamFirst)?)?Smoke|"
                                             rb"runEmbeddedJmdnsPomSmoke) FAILED\r?\n?", line)
                if consumer_task:
                    tasks.add(":lanJvm:" + consumer_task[1].decode("ascii"))
                location = re.fullmatch(rb"PUBLICATION_EMBEDDED_CHECK_LINES ([0-9]{1,5}(?:,[0-9]{1,5}){0,15})\s*", line)
                if location:
                    publication_lines = [int(value) for value in location[1].split(b",")]
                location = re.fullmatch(rb"PLATFORM_CHECK_LINES ([0-9]{1,5}(?:,[0-9]{1,5}){0,15})\s*", line)
                if location:
                    platform_lines = [int(value) for value in location[1].split(b",")]
                signature = re.fullmatch(rb"CENTRAL_SIGNATURE_COUNTS CHECKED (0|[1-9][0-9]{0,3}) "
                                         rb"UNSIGNED (0|[1-9][0-9]{0,3}) INVALID (0|[1-9][0-9]{0,3})\r?\n?", line)
                if signature:
                    checked, unsigned, invalid = map(int, signature.groups())
                    if unsigned + invalid <= checked <= 4096:
                        signature_counts.append({"checked": checked, "unsigned": unsigned, "invalid": invalid})
                inventory_keys = ("expected", "observed", "missing", "extra", "jar", "aar", "klib", "pom",
                                  "module", "maven_metadata", "resolver_metadata", "other")
                inventory = re.fullmatch(
                    rb"CENTRAL_INVENTORY " + b" ".join(key.upper().encode() + rb" (0|[1-9][0-9]{0,3})"
                                                        for key in inventory_keys) + rb"\r?\n?", line)
                if inventory:
                    values = dict(zip(inventory_keys, map(int, inventory.groups())))
                    if (all(value <= 4096 for value in values.values()) and values["expected"] in (84, 117, 121) and
                            values["missing"] <= values["expected"] and
                            values["observed"] == values["expected"] - values["missing"] + values["extra"] and
                            sum(values[key] for key in inventory_keys[4:]) == values["extra"]):
                        inventory_observations.append(values)
                phase = re.fullmatch(
                    rb"INTEL_PHASE_RESULT ([a-z-]{1,40}) EXIT (null|0|-?[1-9][0-9]{0,2}) "
                    rb"TIMEOUT ([01]) OVERFLOW ([01]) DRAINED ([01])\r?\n?", line)
                if phase:
                    label = phase[1].decode("ascii")
                    value = None if phase[2] == b"null" else int(phase[2])
                    if label in phase_labels and (value is None or -255 <= value <= 255):
                        if label in phase_observations:
                            duplicate_phases.add(label)
                        else:
                            phase_observations[label] = {"label": label, "exitCode": value,
                                "timedOut": phase[3] == b"1", "outputLimitExceeded": phase[4] == b"1",
                                "ownedGroupDrained": phase[5] == b"1"}
                dependency_error = re.fullmatch(rb"DEPENDENCY_UPDATE_FAILED: ([A-Za-z_]{1,80})\r?\n?", line)
                if dependency_error:
                    label = dependency_error[1].decode("ascii")
                    if label in DEPENDENCY_UPDATE_ERRORS:
                        categories.add("DEPENDENCY_UPDATE_" + label)
                    elif label in DEPENDENCY_UPDATE_EXCEPTIONS:
                        categories.add("DEPENDENCY_UPDATE_EXCEPTION_" + label)
                dependency_step = re.fullmatch(
                    rb"DEPENDENCY_UPDATE_STEP (GENERATOR|GRADLE_STOP) EXIT (0|-?[1-9][0-9]{0,9})\r?\n?", line)
                if dependency_step:
                    label, value = dependency_step[1].decode("ascii"), int(dependency_step[2])
                    if label in dependency_exits or not -(2**31) <= value < 2**32:
                        duplicate_dependency_steps.add(label)
                    else:
                        dependency_exits[label] = value
                generator_phase = re.fullmatch(
                    rb"DEPENDENCY_GENERATOR_PHASE ([A-Z]{1,16}) EXIT (0|[1-9][0-9]{0,2})\r?\n?", line)
                if generator_phase:
                    label, value = generator_phase[1].decode("ascii"), int(generator_phase[2])
                    if label in DEPENDENCY_GENERATOR_PHASES:
                        if label in generator_phases or value > 255:
                            duplicate_generator_phases.add(label)
                        else:
                            generator_phases[label] = value
                if line.startswith(b"FATAL: "):
                    # Strip only the one actual line terminator; whitespace or
                    # appended private text cannot turn into an admitted label.
                    message = line.removesuffix(b"\n").removesuffix(b"\r")[7:]
                    text = message.decode("ascii", errors="replace")
                    category = BUNDLE_FATAL_MESSAGES.get(text) or DEPENDENCY_FATAL_MESSAGES.get(text)
                    if category is not None:
                        categories.add(category)
                bundle_phase = re.fullmatch(
                    rb"FATAL: disposable-key bundle test failed during: ([a-z -]{1,80})\r?\n?", line)
                if bundle_phase:
                    category = bundle_phases.get(bundle_phase[1].decode("ascii"))
                    if category is not None:
                        categories.add(category)
                for token, category in known.items():
                    if token.lower() in line.lower():
                        categories.add(category)
                root_task = re.fullmatch(
                    rb"> Task :(resolveAndLockAll|verifyBuildPluginSecurityFloors|help) FAILED\s*", line)
                if root_task:
                    tasks.add(":" + root_task[1].decode("ascii"))
                match = re.fullmatch(rb"> Task (:(?:p2p-[a-z0-9-]+|sample-kmp-shared|buildSrc):[A-Za-z0-9_:.-]{1,120}) FAILED\s*", line)
                if match:
                    task = match[1].decode("ascii")
                    pieces = task.split(":")
                    if len(pieces) == 3 and pieces[1] in modules and pieces[2] in task_names:
                        tasks.add(task)
    inventory_fields = {"centralInventory": inventory_observations[0]} if len(inventory_observations) == 1 else {}
    if rpc_package_lines:
        inventory_fields["rpcWindowsPackageCheckLines"] = rpc_package_lines
    if len(rpc_path_observations) == 1:
        inventory_fields["rpcWindowsPackagePathMismatch"] = rpc_path_observations[0]
    if consumer_snapshots:
        inventory_fields["consumerDiscoverySnapshots"] = [consumer_snapshots[key] for key in sorted(consumer_snapshots)
                                                         if key not in duplicate_consumers]
    if len(signature_counts) == 1:
        inventory_fields["centralSignatureCounts"] = signature_counts[0]
    observed_exits = {key: value for key, value in dependency_exits.items()
                      if key not in duplicate_dependency_steps}
    dependency_fields = {"dependencyUpdateExits": observed_exits} if observed_exits else {}
    observed_generator_phases = {key: value for key, value in generator_phases.items()
                                if key not in duplicate_generator_phases}
    if observed_generator_phases:
        dependency_fields["dependencyGeneratorPhases"] = observed_generator_phases
    observed_phases = [row for label, row in phase_observations.items() if label not in duplicate_phases]
    if not include_reports:
        # Original capture EOF/join/close is independent from descendant census.
        # After uncertain retirement read ONLY those closed private captures;
        # other reports may still have writers. These labels never qualify a run.
        return {"categories": sorted(categories), "failedGradleTasks": sorted(tasks), "simulatorPhases": observed_phases,
                "embeddedPublicationCheckLines": publication_lines, "platformCheckLines": platform_lines,
                "platformTests": [], "failedSourceTests": [], **dependency_fields, **inventory_fields}
    phases = list(observed_phases)
    # Prefer the closed command's observations; do not mix duplicated or
    # contradictory logs with a second report-derived phase history.
    phase_paths = [] if phase_observations else sorted(
        (root / "build/reports/platform-tests").glob("*/intel-simulator/*/result.json"))
    for path in phase_paths:
        try:
            row = read_json(path, 64 * 1024)
            if type(row) is not dict:
                continue
            label = row.get("label")
            if (type(label) is str and label in phase_labels
                    and "exitCode" in row and (row["exitCode"] is None or
                        type(row["exitCode"]) is int and -255 <= row["exitCode"] <= 255)
                    and all(type(row.get(k)) is bool for k in ("timedOut", "outputLimitExceeded", "ownedGroupDrained"))):
                phases.append({k: row[k] for k in ("label", "exitCode", "timedOut", "outputLimitExceeded", "ownedGroupDrained")})
        except (OSError, ValueError, TypeError):
            continue
    platform_reports = []
    for path in sorted((root / "build/reports/platform-tests").glob("*/execution.json")):
        try:
            report = read_json(path, MAX_JSON_BYTES)
            if type(report) is not dict or type(report.get("tests")) is not dict:
                continue
            tests = []
            for task, row in report["tests"].items():
                pieces = task.split(":")
                if (len(pieces) == 3 and pieces[1] in modules and pieces[2] in task_names and
                    type(row) is dict and type(row.get("outcome")) is str and row["outcome"] in
                    {"EXECUTED", "FAILED", "NO_SOURCE", "SKIPPED", "UP-TO-DATE", "FROM-CACHE", "NOT_COMPLETED", "NOT_REQUESTED"} and
                    all(type(row.get(k)) is int and 0 <= row[k] <= 1000000 for k in ("passed", "failed", "skipped"))):
                    tests.append({"task": task, **{k: row[k] for k in ("outcome", "passed", "failed", "skipped")}})
            platform_reports.append({"buildFailed": report.get("buildFailed") if type(report.get("buildFailed")) is bool else None,
                                     "tests": sorted(tests, key=lambda row: row["task"])[:64]})
        except (OSError, ValueError, TypeError):
            continue
    phone_observations = rpc_ios_phone_observations(root, source_commit)
    if phone_observations is not None:
        inventory_fields["rpcIosPhone"] = phone_observations
    swift_observations = swift_sample_failure_observations(root, command_directory, source_commit)
    if swift_observations is not None:
        inventory_fields["swiftSample"] = swift_observations
    return {"categories": sorted(categories), "failedGradleTasks": sorted(tasks), "simulatorPhases": phases[:32],
            "embeddedPublicationCheckLines": publication_lines, "platformCheckLines": platform_lines,
            "platformTests": platform_reports[:8], "failedSourceTests": junit_failures(root, source_commit), **dependency_fields, **inventory_fields}


def public_outcome(value):
    """Finite process metadata only; never copy a command or an exception."""
    if (type(value) is not dict or type(value.get("code")) is not str or value["code"] not in CODES or
            "exitCode" not in value or
            not (value.get("exitCode") is None or type(value.get("exitCode")) is int and
                 -(2**31) <= value["exitCode"] < 2**32) or
            any(type(value.get(key)) is not bool for key in ("timedOut", "cleanupKnown"))):
        return None
    result = {key: value[key] for key in ("code", "exitCode", "timedOut", "cleanupKnown")}
    if "nativeError" in value:
        result["nativeError"] = value["nativeError"]
    reasons = value.get("cleanupReasons")
    if (type(reasons) is list and len(reasons) <= len(CLEANUP_REASONS) and
            all(type(reason) is str and reason in CLEANUP_REASONS for reason in reasons)):
        result["cleanupReasons"] = sorted(set(reasons))
    if type(value.get("capturesClosed")) is bool:
        result["capturesClosed"] = value["capturesClosed"]
    count = value.get("outsideDomainObservations")
    if (value.get("ownershipBoundary") == HOSTED_DARWIN_BOUNDARY and type(count) is int and
            0 <= count <= MAX_OUTSIDE_DOMAIN_OBSERVATIONS):
        result.update(ownershipBoundary=HOSTED_DARWIN_BOUNDARY, outsideDomainObservations=count)
    pending_context = public_pending_context(value.get("pendingContext"))
    if pending_context is not None:
        result["pendingContext"] = pending_context
    return result


def native_error_diagnostic(error):
    """Only native numeric codes or exact source-owned operation names escape."""
    result = {"kind": "UNKNOWN", "operation": None, "errno": None, "winerror": None}
    if isinstance(error, OSError):
        result["kind"] = "OS"
        for key in ("errno", "winerror"):
            value = getattr(error, key, None)
            if type(value) is int and 0 <= value < 2**32:
                result[key] = value
    elif type(error) is audit_processes.OwnershipError and len(error.args) == 1 and type(error.args[0]) is str:
        message = error.args[0]
        operations = {"CreateJobObjectW", "SetInformationJobObject", "CreatePipe", "SetHandleInformation",
                      "GetHandleInformation", "CreateProcessW (atomic job assignment)", "Initialize attributes",
                      "HANDLE_LIST", "JOB_LIST", "pre-resume IsProcessInJob", "GetProcessTimes",
                      "GetExitCodeProcess", "CloseHandle", "QueryInformationJobObject", "IsProcessInJob",
                      "OpenProcess owned-job member", "TerminateJobObject", "TerminateJobObject failed launch",
                      "DuplicateHandle owned input", "DuplicateHandle owned output"}
        match = re.fullmatch(r"Windows (.{1,64}) failed: error ([0-9]{1,10})", message)
        if match and match[1] in operations and int(match[2]) < 2**32:
            result.update(kind="WIN32", operation=match[1], winerror=int(match[2]))
        else:
            fixed = {"Unsupported Windows Job Object ABI layout": "WINDOWS_ABI",
                     "Windows audit ownership requires native 64-bit Python": "WINDOWS_NATIVE_PYTHON",
                     "Native Windows command requires .exe/.com or explicit interpreter": "WINDOWS_EXECUTABLE_TYPE",
                     "Command executable does not resolve to an existing file": "EXECUTABLE_UNAVAILABLE"}
            if message in fixed:
                result.update(kind="OWNERSHIP", operation=fixed[message])
    # Finite source-owned type labels distinguish an ownership/shape/timeout
    # error without reading unclosed logs or exposing exception text/arguments.
    if result["kind"] == "UNKNOWN":
        labels = {audit_processes.OwnershipError: "OWNERSHIP_ERROR",
                  audit_processes.DiscoveryUncertain: "DISCOVERY_UNCERTAIN",
                  audit_processes.DarwinObservationExhausted: "DARWIN_OBSERVATION_EXHAUSTED",
                  audit_processes.DarwinObservationError: "DARWIN_OBSERVATION_ERROR",
                  subprocess.TimeoutExpired: "TIMEOUT_EXPIRED",
                  RuntimeError: "RUNTIME_ERROR", ValueError: "VALUE_ERROR", TypeError: "TYPE_ERROR",
                  KeyError: "KEY_ERROR", IndexError: "INDEX_ERROR", AttributeError: "ATTRIBUTE_ERROR",
                  AssertionError: "ASSERTION_ERROR", OverflowError: "OVERFLOW_ERROR",
                  MemoryError: "MEMORY_ERROR", RecursionError: "RECURSION_ERROR"}
        result["exceptionType"] = labels.get(type(error), "UNKNOWN")
        if type(error) in (audit_processes.DiscoveryUncertain, audit_processes.DarwinObservationExhausted):
            result["failureKind"] = pending_failure_kind(error.args[0] if len(error.args) == 1 else None)
        # Source-bound line numbers locate an otherwise opaque internal failure.
        # No function names, caller paths, frame locals, or exception text escape.
        scripts = Path(__file__).resolve().parent
        owned_files = {str(scripts / name): label for name, label in (
            ("ci_evidence.py", "EVIDENCE"), ("audit_processes.py", "OWNERSHIP"),
            ("audit_exec_gate.py", "EXEC_GATE"))}
        frames, cursor = [], error.__traceback__
        for _ in range(64):
            if cursor is None:
                break
            label = owned_files.get(cursor.tb_frame.f_code.co_filename)
            if label is not None and type(cursor.tb_lineno) is int and 0 < cursor.tb_lineno <= 1000000:
                frames.append({"source": label, "line": cursor.tb_lineno})
                frames = frames[-3:]
            cursor = cursor.tb_next
        if frames:
            result["sourceFrames"] = frames
    return result


def gpg_failure_categories(directory):
    """Classify closed GPG stderr without publishing any of its text."""
    tokens = {
        b"invalid option": "UNSUPPORTED_OPTION",
        b"permission denied": "ACCESS_DENIED",
        b"no such file or directory": "FILE_NOT_FOUND",
        b"can't connect to the keyboxd": "KEYBOXD_UNAVAILABLE",
        b"keyblock resource": "KEYRING_RESOURCE",
        b"can't connect to the agent": "AGENT_UNAVAILABLE",
        b"no gpg-agent running": "AGENT_UNAVAILABLE",
        b"error spawning": "HELPER_SPAWN",
        b"no valid openpgp data found": "RECIPIENT_PARSE",
        b"unusable public key": "RECIPIENT_UNUSABLE",
        b"encryption failed": "ENCRYPTION_FAILED",
    }
    try:
        with (directory / "stderr.log").open("rb") as stream:
            raw = stream.read(MAX_JSON_BYTES + 1)
        if len(raw) > MAX_JSON_BYTES:
            return []
        return sorted({category for token, category in tokens.items() if token in raw.lower()})
    except OSError:
        return []


def deferred_remote_consumer_home(component, environment):
    """Keep the original remote script's future home in its initial domain.

    The unchanged script first requires a new/empty borrowed work directory,
    then creates its own Gradle home. Do not populate that work ahead of it.
    """
    if component != "published-consumers-diagnostic":
        return False
    work = Path(environment.get("P2PKIT_CONSUMER_WORK_DIR", ""))
    home = Path(environment.get("GRADLE_USER_HOME", ""))
    parent = work.parent
    runner = Path(environment.get("RUNNER_TEMP", "")).resolve(strict=True)
    require(work.is_absolute() and work == work.resolve() and work.name == "consumer" and
            parent.parent == runner and parent.name.startswith("ci-terminal-") and
            home == work / "gradle-home" and not work.exists(), "INPUT")
    for path in (parent, parent / "home", parent / "tmp"):
        require(path == path.resolve(strict=True) and not path.is_symlink(), "INPUT")
        info = path.stat()
        require(stat.S_ISDIR(info.st_mode) and info.st_uid == os.getuid() and
                stat.S_IMODE(info.st_mode) == 0o700, "INPUT")
    require(environment.get("HOME") == str(parent / "home") and
            environment.get("TMPDIR") == str(parent / "tmp"), "INPUT")
    return True


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--component", required=True)
    parser.add_argument("--timeout-seconds", type=float, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, default=Path.cwd())
    parser.add_argument("--report-glob", action="append", default=[])
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    stage, private, output, previous = "INPUT", None, None, {}
    source, github, outcome, root = None, None, None, None
    cleanup_known = True
    cancelled = threading.Event()
    try:
        require(re.fullmatch(r"[a-z][a-z0-9-]{0,63}", args.component))
        command = args.command[1:] if args.command[:1] == ["--"] else args.command
        require(command and all(type(item) is str and item and "\0" not in item for item in command))
        root = args.source_root.resolve()
        output = args.output_dir.absolute()
        require(not output.exists() and root not in output.parents, "INPUT")
        output.mkdir(parents=True, mode=0o700)
        private = Path(tempfile.mkdtemp(prefix="ci-evidence-private-", dir=os.environ.get("RUNNER_TEMP")))
        for sig in (signal.SIGINT, signal.SIGTERM):
            previous[sig] = signal.signal(sig, lambda _s, _f: cancelled.set())
        started = utc()
        stage = "SOURCE"
        source = source_identity(root)
        github = github_identity(os.environ, source)
        environment = dict(os.environ)
        tools_file = private / "tools.json"
        environment["CI_EVIDENCE_TOOLS_FILE"] = str(tools_file)
        stage = "COMMAND"
        cleanup_known = False
        options = {"create_gradle_home": False} if deferred_remote_consumer_home(args.component, environment) else {}
        outcome = run_command(command, cwd=root, environment=environment, private=private / "command",
                              timeout=args.timeout_seconds, cancelled=cancelled.is_set, **options)
        cleanup_known = outcome["cleanupKnown"]
        require(cleanup_known, "CLEANUP")
        stage = "SOURCE"
        require(source_identity(root) == source, "SOURCE_CHANGED")
        stage = "REPORTS"
        bundle = private / "bundle"
        bundle.mkdir(mode=0o700)
        for name in ("stdout.log", "stderr.log"):
            shutil.copyfile(private / "command" / name, bundle / name)
        collect_reports(root, args.report_glob, bundle / "reports")
        write_private(bundle / "run.json", encoded({"source": source, "github": github, "command": command,
                                                     "outcome": outcome}))
        archive = private / "evidence.tar.gz"
        reports = archive_private(bundle, archive)
        stage = "RECIPIENT"
        with (root / ".github/ci-evidence-recipient.asc").open("rb") as public_key:
            key_raw = public_key.read(64 * 1024 + 1)
        require(0 < len(key_raw) <= 64 * 1024, "RECIPIENT")
        ciphertext = encrypt_archive(archive, output / "evidence.tar.gz.gpg", key_raw,
            os.environ.get("CI_EVIDENCE_RECIPIENT_SHA256", ""),
            os.environ.get("CI_EVIDENCE_RECIPIENT_FINGERPRINT", ""), private, environment, cancelled=cancelled.is_set)
        stage = "MANIFEST"
        manifest = {"schema": SCHEMA, "component": args.component, "source": source, "github": github,
            "host": {"platform": platform.system(), "arch": platform.machine(),
                     "runnerEnvironment": os.environ.get("RUNNER_ENVIRONMENT", "")},
            "timing": {"startedAt": started, "completedAt": utc()}, "tools": tool_identity(tools_file),
            "command": {"sha256": hashlib.sha256(encoded(command)).hexdigest()}, "outcome": outcome,
            "taskResults": component_tasks(root, args.component),
            "failureDiagnostics": failure_diagnostics(root, private / "command", source["commit"]) if outcome["code"] != "PASS" else None,
            "reports": reports, "privateArchive": digest_file(archive), "ciphertext": ciphertext}
        if args.component == "rpc-io-ios-phone" and outcome["code"] == "PASS":
            phone_observations = rpc_ios_phone_observations(root, source["commit"])
            if phone_observations is not None:
                manifest["rpcIosPhone"] = phone_observations
        write_private(output / "manifest.json", encoded(manifest))
        print("CI_EVIDENCE " + ("PASS" if outcome["code"] == "PASS" else "FAIL") + " " + outcome["code"])
        return 0 if outcome["code"] == "PASS" else 1
    except BaseException as error:
        code = error.code if type(error) is EvidenceError else "INPUT"
        encryption = getattr(error, "encryption_diagnostic", None) if type(error) is EvidenceError else None
        if encryption is not None and (encryption["outcome"] is None or
                                       not encryption["outcome"]["cleanupKnown"]):
            cleanup_known = False
        # Never render an exception, command, private path, GPG diagnostic or env.
        print("CI_EVIDENCE FAIL " + stage + " " + code, file=sys.stderr)
        try:
            if output is not None and output.is_dir():
                # No partial uploadable public receipt/ciphertext is a success.
                for name in ("manifest.json", "evidence.tar.gz.gpg"):
                    (output / name).unlink(missing_ok=True)
                # Explicitly NOT a qualification manifest. The job remains failed;
                # consumers still require manifest.json plus matching ciphertext.
                failure = {"schema": SCHEMA, "kind": "CI_EVIDENCE_FAILURE",
                    "component": args.component if re.fullmatch(r"[a-z][a-z0-9-]{0,63}", args.component) else None,
                    "source": source, "github": github, "stage": stage, "code": code,
                    "outcome": public_outcome(outcome), "encryptionDiagnostic": encryption,
                    "taskResults": component_tasks(root, args.component)
                        if source is not None and outcome is not None and outcome["cleanupKnown"] else None,
                    "failureDiagnostics": failure_diagnostics(root, private / "command", source["commit"],
                        include_reports=outcome["cleanupKnown"])
                        if source is not None and outcome is not None and
                        (outcome["cleanupKnown"] or outcome.get("capturesClosed") is True) else None}
                write_private(output / "failure.json", encoded(failure))
                if (stage == "COMMAND" and code == "CLEANUP" and source is not None and
                        outcome is not None and outcome["cleanupKnown"] is False and
                        outcome.get("capturesClosed") is True):
                    try:
                        failure["closedCaptureArchive"] = encrypt_closed_failure_captures(
                            root, private, output, environment, cancelled=cancelled.is_set)
                        # The original failure survives interruption/encryption
                        # failure. Replace it atomically only with a complete
                        # diagnostic attachment; never create a success manifest.
                        updated = output / "failure-update.json"
                        write_private(updated, encoded(failure))
                        os.replace(updated, output / "failure.json")
                    except BaseException as diagnostic_error:
                        for name in ("evidence.tar.gz.gpg", "failure-update.json"):
                            (output / name).unlink(missing_ok=True)
                        failure.pop("closedCaptureArchive", None)
                        # Reuse the encryptor's source-owned finite diagnostic;
                        # never render an exception or change the original failure.
                        failure["closedCaptureFailure"] = {
                            "code": diagnostic_error.code if type(diagnostic_error) is EvidenceError else "INPUT",
                            "exception": type(diagnostic_error).__name__ if type(diagnostic_error) in
                                (EvidenceError, OSError, FileNotFoundError, PermissionError, FileExistsError,
                                 IsADirectoryError, NotADirectoryError, ValueError, TypeError) else "UNKNOWN",
                            "encryptionDiagnostic": getattr(diagnostic_error, "encryption_diagnostic", None)
                                if type(diagnostic_error) is EvidenceError else None}
                        try:
                            updated = output / "failure-update.json"
                            write_private(updated, encoded(failure))
                            os.replace(updated, output / "failure.json")
                        except BaseException:
                            (output / "failure-update.json").unlink(missing_ok=True)
                            print("CI_EVIDENCE DIAGNOSTIC_RECEIPT_UPDATE_FAILED", file=sys.stderr)
                        print("CI_EVIDENCE DIAGNOSTIC_ENCRYPTION_FAILED", file=sys.stderr)
        except BaseException:
            # An OS cleanup error must not print a private filename/exception or
            # convert this failure to PASS. Job/API failure still denies intake.
            print("CI_EVIDENCE CLEANUP UNKNOWN", file=sys.stderr)
        return 1
    finally:
        for sig, handler in previous.items():
            signal.signal(sig, handler)
        if private is not None and cleanup_known:
            shutil.rmtree(private, ignore_errors=True)
        # Unknown writer retirement retains the private directory for runner
        # teardown; never erase evidence while a possible original writer lives.


if __name__ == "__main__":
    raise SystemExit(main())
