"""NEW collect-only supplied boundaries; no old suite imported or replayed.

This module is a test fixture, NOT an original producer. Prior Step/carrier
bytes are a complete minimal downstream grammar. No old Window is restored and
no old PRIMARY/crypto return is registered or represented as successful. The new entry, metadata,
source/acquirer, child/parent phase, close and outputs remain production code.
Only clock/host/Step observations, Git query returns, HTTP transport and the
native process scope are supplied. Files are tiny real private POSIX files.
Public checked-in policy is grammar only; no GPG, native library, Git command,
process, network, SDK, private original, provider or hosted identity is used.
Host-shaped mappings live ONLY in module-local supplier namespaces, never in
the process environment. Tests must be reviewed before any interpreter use.
"""
from __future__ import annotations

import base64
from contextlib import ExitStack, contextmanager
import ctypes  # Finish stdlib initialization before forbidding native loading.
from datetime import datetime, timezone
from email.utils import format_datetime
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import signal
import sys
import tempfile
from types import SimpleNamespace
from unittest.mock import patch


def offline(event, _args):
    if event.startswith(("subprocess.", "socket.")) or event in (
            "os.system", "os.exec", "os.posix_spawn", "os.fork", "os.forkpty", "pty.spawn", "ctypes.dlopen"):
        raise RuntimeError("COLLECT_MODEL_PROCESS_NETWORK_NATIVE_FORBIDDEN")


sys.addaudithook(offline)
sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
_spec = importlib.util.spec_from_file_location("collect_only_source_under_review",
    ROOT / "scripts/run-hosted-initial-recipient-custody.py")
D = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = D
_spec.loader.exec_module(D)
NS, BOOT = 1_000_000_000, "7" * 64
TOKEN = "SUPPLIED_OFFLINE_COLLECT_NOT_A_CREDENTIAL"


def wire(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
        allow_nan=False) + "\n").encode("ascii")


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def timestamp(value):
    return datetime.fromtimestamp(value, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def ensure(value, label):
    if not value:
        raise AssertionError("COLLECT_SUPPLIED_MODEL_" + label)


def put(path, raw):
    ensure(type(raw) is bytes, "BYTE_FILE")
    with path.open("xb") as stream:
        stream.write(raw)
    path.chmod(0o600)


def close_record(labels):
    return {"schema": 1, "scope": "INITIAL_CUSTODY_PRIMARY_NATIVE_CLOSE_V1",
        "resources": [{"ordinal": index, "label": label, "closeAttempted": True, "closed": True}
            for index, label in enumerate(labels)], "retirement": "KNOWN_RESOURCE_CLOSE_ONLY", "exportSaveAuthority": False}


class FalseyFailure(RuntimeError):
    def __bool__(self):
        return False


class Clock:
    def __init__(self):
        self.identity = D.O.clocks.ClockIdentity("linux-x64", D.O.clocks.DOMAINS["linux-x64"], NS)
        self.raw, self.local = 1180 * NS, 100.0
        self.events, self.callback, self.observe_hook = [], lambda: None, lambda: None
        self.boot = BOOT

    def advance(self, seconds):
        self.raw += round(seconds * NS)
        self.local += seconds

    def monotonic(self):
        self.events.append("LOCAL")
        return self.local

    def reading(self):
        self.events.append("FIRST_RAW")
        return D.O.clocks.Reading(self.identity, self.raw)

    def checked(self, expected, *, minimum_ns=0):
        self.events.append("RAW")
        self.observe_hook()
        ensure(expected == self.identity and self.raw >= minimum_ns, "NONDECREASING_ORIGINAL_RAW")
        return self.raw

    def cancelled(self):
        self.events.append("CANCEL")
        self.callback()


class Packets:
    """Complete new downstream grammar, explicitly NOT prior Step evidence."""
    def __init__(self, kind):
        self.kind, self.source = kind, {"commit": "1" * 40, "tree": "2" * 40}
        self.policy_raw = (ROOT / ".github/test-evidence-recipient.json").read_bytes()
        self.policy = json.loads(self.policy_raw)
        ensure(sha(self.policy_raw) == D.A.stages.POLICY_SHA256, "CHECKED_IN_PUBLIC_POLICY_BYTES")
        self.use = self.policy["notBefore"] + 180
        self.selection, self.run, self.attempt = "desktop-linux-x64", "7301", "1"
        self.event = wire({"repository": {"full_name": D.I.REPOSITORY, "default_branch": "main"},
            "ref": D.A.stages.SOURCE_REF, "inputs": {"selection": self.selection,
                "expected_sha": self.source["commit"], "expected_tree": self.source["tree"]}})
        self.env = {"GITHUB_ACTIONS": "true", "GITHUB_REPOSITORY": D.I.REPOSITORY,
            "GITHUB_SERVER_URL": "https://github.com", "GITHUB_API_URL": "https://api.github.com",
            "RUNNER_ENVIRONMENT": "github-hosted", "GITHUB_EVENT_NAME": "workflow_dispatch",
            "GITHUB_REF": D.A.stages.SOURCE_REF, "GITHUB_SHA": self.source["commit"],
            "GITHUB_WORKFLOW_SHA": self.source["commit"], "GITHUB_WORKFLOW_REF": D.I.REPOSITORY + "/" +
                D.A.stages.bootstrap.WORKFLOW + "@" + D.A.stages.SOURCE_REF,
            "GITHUB_RUN_ID": self.run, "GITHUB_RUN_ATTEMPT": self.attempt, "RUNNER_OS": "Linux", "RUNNER_ARCH": "X64",
            "RUNNER_NAME": "SUPPLIED-COLLECT-ONLY", "GITHUB_JOB": D.A.gate.JOB if kind == "gate" else D.A.stages.bootstrap.JOB}
        self.observed = D.A._context(self.env, self.event, kind, self.use)  # Pure supplied context, not env installation.
        author = {"login": D.A.stages.joint.OWNER_LOGIN, "id": D.A.stages.joint.OWNER_ID, "type": "User"}
        environment = {"name": D.A.stages.ENVIRONMENT, "id": 9100, "branchPolicies": [
            {"id": 9101 + index, "name": name, "type": "branch"} for index, name in enumerate(D.A.stages.BRANCHES)]}
        declaration = {"schema": 1, "scope": D.A.stages.STAGE1, "repository": D.I.REPOSITORY,
            "base": D.A.stages.BASE, "reviewed": self.source, "sourceRef": D.A.stages.SOURCE_REF,
            "policySha256": D.A.stages.POLICY_SHA256, "notBefore": self.policy["notBefore"],
            "expiresAt": self.policy["expiresAt"], "environment": environment,
            "bootstrap": [{"selection": self.selection, "runId": self.run, "runAttempt": self.attempt}]}
        body = D.A.stages.COMMANDS[D.A.stages.STAGE1] + wire(declaration).decode("ascii").removesuffix("\n")
        api, web = D.O.wire.ORIGIN + D.A.API, "https://github.com/" + D.I.REPOSITORY
        comment = wire({"id": 9200, "url": api + "/issues/comments/9200", "issue_url": api + "/issues/437",
            "html_url": web + "/issues/437#issuecomment-9200", "user": author, "performed_via_github_app": None,
            "created_at": timestamp(self.use - 30), "updated_at": timestamp(self.use - 30), "body": body})
        approvals = wire([{"state": "approved", "user": author, "environments": [{"name": environment["name"], "id": 9100}],
            "comment": "AUTHORIZE_INITIAL_RECIPIENT stage1 " + self.run + "/1 9200 " + sha(body.encode("ascii"))}])
        environment_raw = wire({"id": 9100, "name": environment["name"], "can_admins_bypass": False,
            "deployment_branch_policy": {"protected_branches": False, "custom_branch_policies": True},
            "protection_rules": [{"type": "branch_policy"}, {"type": "required_reviewers", "prevent_self_review": False,
                "reviewers": [{"type": "User", "reviewer": author}]}]})
        branches_raw = wire({"total_count": 2, "branch_policies": environment["branchPolicies"]})
        self.blob = hashlib.sha1(b"blob " + str(len(self.policy_raw)).encode("ascii") + b"\0" + self.policy_raw).hexdigest()
        self.source_raws = {"base_policy_entry": b"", "ancestry_raw": D.A.stages.BASE["commit"].encode("ascii") + b"\n",
            "candidate_policy_entry": b"100644 blob " + self.blob.encode("ascii") + b"\t" + D.I.POLICY_PATH.encode("ascii") + b"\0",
            "candidate_policy_raw": self.policy_raw}
        observation = {"repository": D.I.REPOSITORY, "base": D.A.stages.BASE, "reviewed": self.source,
            "source": self.source, "firstUseAt": self.use, "github": dict(self.observed["github"])}
        if kind == "gate":
            observation["inputs"] = self.observed["inputs"]
            self.match = D.A.gate.eligible(stage="stage1", approvals_raw=approvals, comment_raw=comment,
                environment_raw=environment_raw, branches_raw=branches_raw, observation_raw=wire(observation),
                now=self.use, **self.source_raws)
        else:
            observation["github"].update(profile=D.A.stages.bootstrap.PROFILE, selection=self.selection)
            self.match = D.A.stages.match_bootstrap(comment_raw=comment, comment_id=9200, body_sha256=sha(body.encode("ascii")),
                observation_raw=wire(observation), now=self.use, **self.source_raws)
        branch = D.A.stages.SOURCE_REF.removeprefix("refs/heads/")
        run = {"id": int(self.run), "run_attempt": 1, "repository": {"full_name": D.I.REPOSITORY},
            "head_repository": {"full_name": D.I.REPOSITORY}, "path": D.A.stages.bootstrap.WORKFLOW,
            "event": "workflow_dispatch", "head_sha": self.source["commit"], "head_branch": branch,
            "status": "in_progress", "conclusion": None, "pull_requests": [],
            "created_at": timestamp(self.use - 5), "run_started_at": timestamp(self.use - 4)}
        self.job = {"id": 9300, "name": self.env["GITHUB_JOB"], "run_id": int(self.run), "run_attempt": 1,
            "head_sha": self.source["commit"], "head_branch": branch, "url": api + "/actions/jobs/9300",
            "run_url": api + "/actions/runs/" + self.run, "status": "in_progress", "conclusion": None,
            "completed_at": None, "started_at": timestamp(self.use - 1), "runner_name": self.env["RUNNER_NAME"],
            "runner_id": 9400, "labels": [D.A.GATE_SELECTOR if kind == "gate" else D.O.SERVICE_SELECTORS["linux-x64"]],
            "runner_group_id": 0, "runner_group_name": "GitHub Actions"}
        jobs = [self.job]
        if kind == "worker":
            jobs.append({**self.job, "id": 9299, "name": D.A.gate.JOB, "url": api + "/actions/jobs/9299",
                "status": "completed", "conclusion": "success", "labels": [D.A.GATE_SELECTOR],
                "started_at": timestamp(self.use - 3), "completed_at": timestamp(self.use - 2)})
        def ref(name, commit):
            return wire({"ref": "refs/heads/" + name, "url": api + "/git/refs/heads/" + name,
                "object": {"type": "commit", "sha": commit, "url": api + "/git/commits/" + commit}})
        run_path, env_path = D.A.API + "/actions/runs/" + self.run, D.A.API + "/environments/" + environment["name"]
        self.bodies = (("attempt", run_path + "/attempts/1", wire(run)),
            ("jobs", run_path + "/attempts/1/jobs?per_page=100&page=1", wire({"total_count": len(jobs), "jobs": jobs})),
            ("approvals", run_path + "/approvals", approvals), ("comment", D.A.API + "/issues/comments/9200", comment),
            ("environment", env_path, environment_raw),
            ("branches", env_path + "/deployment-branch-policies?per_page=100&page=1", branches_raw),
            ("main", D.A.API + "/git/ref/heads/main", ref("main", D.A.stages.BASE["commit"])),
            ("reviewed_ref", D.A.API + "/git/ref/heads/" + branch, ref(branch, self.source["commit"])))

    def commands(self):
        commit = self.source["commit"]
        return (("rev-parse", "--show-toplevel"), ("status", "--porcelain=v1", "--untracked-files=all"),
            ("rev-parse", "--verify", "HEAD^{commit}"), ("rev-parse", "--verify", commit + "^{tree}"),
            ("rev-parse", "--is-shallow-repository"), ("rev-parse", "--verify", "refs/remotes/origin/main^{commit}"),
            ("rev-parse", "--verify", D.A.stages.BASE["commit"] + "^{tree}"),
            ("ls-tree", "-z", D.A.stages.BASE["commit"], "--", D.I.POLICY_PATH),
            ("merge-base", D.A.stages.BASE["commit"], commit), ("ls-tree", "-z", commit, "--", D.I.POLICY_PATH),
            ("cat-file", "-s", self.blob), ("cat-file", "blob", self.blob))

    def query_outputs(self):
        return (str(ROOT).encode("utf-8") + b"\n", b"", self.source["commit"].encode("ascii") + b"\n",
            self.source["tree"].encode("ascii") + b"\n", b"false\n", D.A.stages.BASE["commit"].encode("ascii") + b"\n",
            D.A.stages.BASE["tree"].encode("ascii") + b"\n", b"", self.source_raws["ancestry_raw"],
            self.source_raws["candidate_policy_entry"], str(len(self.policy_raw)).encode("ascii") + b"\n", self.policy_raw)

    def prior(self, custody, clock):
        for name in ("", "returned", "returned/control-home", "returned/temporary", "returned/crypto-service",
                "authority-1", "copied-evidence", "public-crypto", "export-output"):
            (custody / name).mkdir(mode=0o700)
        def pin(path):
            info = path.stat()
            return [info.st_dev, info.st_ino]
        paths = {"custody": custody, "returned": custody / "returned", "control-home": custody / "returned/control-home",
            "temporary": custody / "returned/temporary", "crypto-service": custody / "returned/crypto-service",
            "copied-evidence": custody / "copied-evidence", "public-crypto": custody / "public-crypto", "export-output": custody / "export-output"}
        frame = {"schema": 1, "scope": D.WINDOW_SCOPE, "clock": D.O.clock_value(clock.identity), "originalBootDigest": BOOT,
            **D.schedule(self.kind, 950 * NS, 1000 * NS)}
        # Worker has more READ residue; the new parent's preliminary30 still wins.
        self.primary = {"step": "initial-originals" if self.kind == "gate" else "canonical-initialization", "outcome": "success",
            "resultSha256": sha(b"SUPPLIED-PRIMARY-RESULT"), "handoffSha256": sha(b"SUPPLIED-PRIMARY-HANDOFF"),
            "inventorySha256": sha(b"SUPPLIED-PRIMARY-INVENTORY")}
        maps = {name: wire({"scope": "SUPPLIED_PRIOR_STEP_DATA_ONLY", "name": name})
            for name in ("primary-map.json", "authority-map.json", "authority-return.json")}
        key = self.policy["recipient"]["publicKey"].encode("ascii")
        files = {**maps, "original-match.json": self.match.record, "fresh-match.json": self.match.record,
            "event.json": self.event, "candidate-policy.json": self.policy_raw, "recipient-public.asc": key}
        context = {"schema": 1, "scope": D._CRYPTO_CONTEXT_SCOPE, "kind": self.kind, "root": str(ROOT),
            "session": str(paths["returned"]), "job": "4" * 32, "observed": self.observed, "window": frame,
            "primary": self.primary, "authority": {"returnSha256": sha(maps["authority-return.json"]),
                "matchSha256": sha(self.match.record), "copySha256": sha(maps["authority-map.json"])},
            "filesSha256": {name: sha(raw) for name, raw in files.items()},
            "directories": {name: None if name == "export-output" else pin(path) for name, path in paths.items()},
            "inheritedContext": {}, "budgetAcceptance": "NOT_ADMITTED", "exportSaveAuthority": False}
        match = json.loads(self.match.record)
        github = dict(self.observed["github"])
        if self.kind == "worker":
            github.update(profile=D.A.stages.bootstrap.PROFILE, selection=self.selection)
        copied = {"mapSha256": sha(b"SUPPLIED-FROZEN-MAP"), "memberCount": 3, "totalBytes": 9,
            "origins": {name: sha(name.encode("ascii")) for name in D.ORIGINS}}
        manifest = {"schema": 4, "scope": D.E.SCOPE, "kind": self.kind, "selection": self.selection, "source": self.source,
            "github": {**github, "repository": D.I.REPOSITORY, "eventSha256": sha(self.event)},
            "policy": {**match["policy"], "fingerprint": self.policy["recipient"]["fingerprint"],
                "keySha256": self.policy["recipient"]["sha256"], "expiresAt": self.policy["expiresAt"], "retentionDays": 14},
            "initialRecipient": {**{name: match[name] for name in
                ("authority", "environment", "originalBase", "reviewed", "firstUseAt", "notBefore", "expiresAt")},
                "matchSha256": sha(self.match.record), "freshReturnSha256": sha(maps["authority-return.json"])},
            "primary": self.primary, "copy": copied, "recipient": {"fingerprint": self.policy["recipient"]["fingerprint"],
                "encryptionFingerprint": "F" * 40, "keySha256": sha(key), "expiresAt": self.policy["expiresAt"] + 60},
            "testAcceptance": "NOT_PERFORMED", "productiveAuthority": False, "cacheAuthority": False,
            "exportSaveAuthority": False, "budgetAcceptance": "NOT_ADMITTED",
            "artifact": {"name": D.native.posix.ARTIFACT, "size": 3, "sha256": sha(b"XYZ")}}
        context_raw, manifest_raw = wire(context), wire(manifest)
        phases = {name: sha(("SUPPLIED-NATIVE-" + name).encode("ascii")) for name in D.native.PHASE_FILES}
        parent = {"schema": 1, "scope": "INITIAL_CUSTODY_CRYPTO_PARENT_KNOWN_CLOSE_V1", "contextSha256": sha(context_raw),
            "childSha256": sha(b"SUPPLIED-CHILD"), "authorityCopyCloseSha256": sha(b"SUPPLIED-COPY-CLOSE"),
            "phaseSha256": phases, "closedNs": 1174 * NS,
            "resources": [{"ordinal": 0, "label": "directory", "closeAttempted": True, "closed": True}],
            "retirement": "KNOWN_RESOURCE_CLOSE_ONLY", "exportSaveAuthority": False}
        carrier = {"schema": 1, "scope": "INITIAL_RECIPIENT_CUSTODY_CLOSED_RETURN_V1",
            **{name: manifest[name] for name in ("kind", "selection", "source", "github", "policy", "primary", "recipient")},
            "authority": manifest["initialRecipient"], "window": {**{name: frame[name] for name in
                ("clock", "originalBootDigest", "originalJobBasisNs", "jobEndNs", "startNs", *D.WINDOW_NAMES)},
                "lastNs": 1176 * NS, "lastLocal": 98.0},
            "copy": {**copied, "path": str(paths["copied-evidence"]), "directoryIdentity": pin(paths["copied-evidence"]),
                "sourceMetadataSha256": {name: sha((name + "-METADATA").encode("ascii")) for name in D.ORIGINS},
                "destinationMetadataSha256": sha(b"SUPPLIED-FREEZE-METADATA")},
            "exporter": {"manifestBase64": base64.b64encode(manifest_raw).decode("ascii"), "manifestBytes": len(manifest_raw),
                "manifestSha256": sha(manifest_raw), "childSha256": parent["childSha256"], "ackSha256": phases["stdout.log"],
                "phaseSha256": phases, "nativeResources": parent["resources"]}, "parentClose": parent,
            "writerReturn": "PENDING_OWNER_CLOSE", "originalStepOutcome": "NOT_OBSERVED", "testAcceptance": "NOT_PERFORMED",
            "productiveAuthority": False, "cacheAuthority": False, "exportSaveAuthority": False, "budgetAcceptance": "NOT_ADMITTED"}
        carrier_raw = wire(carrier)
        self.transfer = {"schema": 1, "scope": D._EXPORT_STEP_SCOPE, "kind": self.kind, "step": "initial-custody-export",
            "primary": self.primary, "originalServiceJob": [self.job[name] for name in ("id", "started_at", "runner_name", "runner_id")],
            "directory": str(paths["returned"]), "directoryIdentity": pin(paths["returned"]),
            "cryptoCarrier": {"sha256": sha(carrier_raw), "bytes": len(carrier_raw), "exporterReturnSha256": sha(manifest_raw),
                "metadataClose": close_record(("directory", "writer"))}, "originalWindow": frame,
            "originalContextSha256": sha(context_raw), "observed": self.observed, "lowerNs": 1178 * NS, "lowerLocal": 99.0,
            "sample": "AFTER_CRYPTO_CARRIER_FUNCTION_BEFORE_GUARDED_OUTPUT_AND_STEP_RETURN", "writerReturn": "PENDING_OWNER_CLOSE",
            "originalStepOutcome": "NOT_OBSERVED", "testAcceptance": "NOT_PERFORMED", "productiveAuthority": False,
            "cacheAuthority": False, "budgetAcceptance": "NOT_ADMITTED", "exportSaveAuthority": False}
        self.raws = {"step": wire(self.transfer), "carrier": carrier_raw, "context": context_raw, "manifest": manifest_raw,
            "original-match": self.match.record, "fresh-match": self.match.record, "event": self.event,
            "policy": self.policy_raw, "public": key}
        for name, raw in {**files, "context.json": context_raw, "custody-return.json": carrier_raw,
                D._EXPORT_STEP_FILE: self.raws["step"]}.items():
            put(paths["returned"] / name, raw)
        put(paths["export-output"] / D.native.posix.MANIFEST, manifest_raw)
        put(paths["export-output"] / D.native.posix.ARTIFACT, b"XYZ")


class QuerySupplier:
    """Low-level Git return model; actual GitView/_source/acquirer are not patched."""
    def __init__(self, rig, owner, fence, path):
        self.rig, self.owner, self.fence, self.path = rig, owner, fence, path
        self.executable, self.job = str(rig.git), format(len(rig.queries) + 1, "032x")
        self.queries, self.declarations = [], []
        self.closed, self.unknown, self.first_error = False, False, None
        self.close_calls, self.finalizers = 0, []
        path.mkdir(mode=0o700)
        (path / "query-home").mkdir(mode=0o700)
        self.private = D.Q._PosixDirectory(path)
        self._write(self.private, "owner.json", wire({"scope": "SUPPLIED_QUERY_OWNER_NO_NATIVE_PROOF"}))

    def native_host_matches_actions(self):
        self.rig.events.append(("supplied-query-host", self.path.name))

    def __call__(self, *, argv, cwd, environment, stdout_limit, stderr_limit, timeout_seconds):
        ensure(not self.closed and self.first_error is None and not self.unknown, "QUERY_LIVE")
        ensure(not any(name in environment for name in D._CREDENTIAL_NAMES), "TOKEN_NOT_IN_GIT")
        index = len(self.queries)
        expected = (str(self.rig.git), "--no-replace-objects", "--no-pager", "-c", "core.fsmonitor=false",
            "-C", str(ROOT), *self.rig.packets.commands()[index % 12])
        ensure(tuple(argv) == expected and cwd == ROOT and stderr_limit == 4096 and timeout_seconds == 15, "EXACT_QUERY")
        self.owner.end()
        raw = self.rig.packets.query_outputs()[index % 12]
        if self.rig.query_hook is not None:
            raw = self.rig.query_hook(self, index, raw)
        self.rig.clock.advance(.002)
        self.owner.end()
        identifier = format(index + 1, "032x")
        directory = self.path / ("query-" + identifier)
        directory.mkdir(mode=0o700)
        row = {"id": identifier, "argv": list(argv), "stdoutLimit": stdout_limit, "stderrLimit": stderr_limit,
            "job": self.job, "state": str(self.path), "home": str(self.path / "query-home"), "cwd": str(ROOT),
            "launchAttempted": True, "scopeAttempted": True, "waitExitCode": 0, "retirement": "KNOWN",
            "result": "READY_FOR_CALLER_SEAL", "errors": [], "ownedSurvivors": []}
        self.queries.append(row)
        for name in ("start.json", "baseline.json", "stdout.log", "stderr.log", "result.json"):
            data = raw if name == "stdout.log" else b"" if name == "stderr.log" else wire({"scope": "SUPPLIED_QUERY_RECORD", "id": identifier})
            put(directory / name, data)
            limit = row[name[:-4] + "Limit"] if name.endswith(".log") else None
            self.declarations.append((directory, name, limit))
        return raw

    def _write(self, parent, name, raw):
        ensure(parent is self.private, "QUERY_PRIVATE")
        raw = raw if type(raw) is bytes else wire(raw)
        put(self.path / name, raw)
        self.declarations.append((self.path, name, None))
        return raw

    def record_admission_failure(self, error):
        if self.first_error is None:
            self.first_error = error

    def _error(self, _row, _stage, error):
        self.record_admission_failure(error)

    def close(self):
        ensure(not self.closed, "QUERY_CLOSE_ONCE")
        self.closed, self.close_calls = True, self.close_calls + 1
        if self.rig.query_close_error is not None:
            self.unknown = True
            raise self.rig.query_close_error
        if self.first_error is not None:
            self.private.close()
            return
        reads = []
        for parent, name, maximum in self.declarations:
            raw = (parent / name).read_bytes()
            reads.append({"parent": str(parent), "name": name, "maximum": max(1, len(raw)) if maximum is None else maximum,
                "retirement": "KNOWN", "result": "RETAINED", "bytes": len(raw), "sha256": sha(raw)})
        value = {"schema": 1, "scope": "ORDINARY_GIT_QUERIES_ONLY", "job": self.job, "queries": self.queries,
            "result": "READY_FOR_CALLER_SEAL", "retirement": "KNOWN", "firstError": None, "errors": [], "readbacks": reads}
        if self.rig.session_hook is not None:
            self.rig.session_hook(self, value)
        put(self.path / "session-result.json", wire(value))
        self.private.close()

    def _finalize(self, failure):
        self.finalizers.append(failure)
        D.Q.NativeGitQueries._finalize(self, failure)


class Scope:
    """Native process-supplier model; actual native.phase still owns its lifecycle."""
    def __init__(self, rig, job, invocation, state, home):
        self.rig, self.job, self.invocation, self.state, self.home = rig, job, invocation, state, home
        self.name, self.baseline = D.native.BACKENDS["linux-x64"], set()
        self.launches, self.identities = [], []
        self.close_calls, self.drains, self.closed = 0, [], False
        # Deterministically distinct from native.preparer_identity's PID; this
        # remains only a supplied child identity, never a process lookup/spawn.
        self.leader = {"pid": 19001 if D.native.os.getpid() != 19001 else 19002, "startTicks": 26001}

    def _identity(self, pid):
        return {"pid": pid, "startTicks": 26002, "live": True}

    def spawn(self, argv, cwd, environment, *, stdout, stderr):
        ensure(cwd == str(ROOT) and environment.get(D.O.wire.TOKEN_ENV) == TOKEN and
            not any(name in environment for name in D._CREDENTIAL_NAMES if name != D.O.wire.TOKEN_ENV), "FIXED_CHILD_TOKEN")
        ensure(argv[5] == "_post-export-authority" and argv[-2] == "--minimum-ns", "FIXED_CHILD_ROUTE")
        self.launches.append({"created": True, "requestedArgv": list(argv), "resolvedArgv": list(argv), "cwd": cwd,
            "pid": self.leader["pid"], "api": "subprocess.Popen", "shell": False,
            "executable": argv[0], "outputMode": "caller-owned-files"})
        self.identities.append(dict(self.leader))
        self.rig.events.append(("supplied-spawn", environment[D.O.wire.TOKEN_ENV]))
        if self.rig.spawn_hook is not None:
            self.rig.spawn_hook(self)
        child_env = dict(environment)
        with self.rig.environment(child_env), patch.object(D.native, "sys", SimpleNamespace(
                **{**vars(sys), "stdout": SimpleNamespace(buffer=stdout.stream)})):
            D.native.guarded(lambda _signals: D._collect_authority_child(argv[7], int(argv[-1]), self.rig.clock.cancelled))
        ensure(D.O.wire.TOKEN_ENV not in child_env, "CHILD_TOKEN_POPPED")
        return SimpleNamespace(pid=self.leader["pid"], stdout=None, stderr=None, poll=lambda: 0)

    def description(self):
        return {"backend": self.name, "job": self.job, "invocation": self.invocation,
            "scope": "controlled-marker-inheriting-descendants", "discoveryErrors": [], "discoveryReconciliations": [],
            "launches": json.loads(wire(self.launches)), "startedIdentities": json.loads(wire(self.identities))}

    def discover(self):
        return []

    def drain(self, *, grace, kill_wait, deadline):
        ensure(deadline <= self.rig.original_local_end and 0 <= grace <= 5 and 0 <= kill_wait <= 5, "ORIGINAL_DRAIN_CEILING")
        self.drains.append((grace, kill_wait, deadline))
        if self.rig.drain_error is not None:
            raise self.rig.drain_error
        return []

    def close(self):
        self.close_calls += 1
        ensure(self.close_calls == 1, "SCOPE_CLOSE_ONCE")
        if self.rig.scope_close_error is not None:
            raise self.rig.scope_close_error
        self.closed = True


class Rig:
    """Fresh collect-only test scope. Never populates old successful registries."""
    def __init__(self, kind="gate"):
        self.kind, self.stack, self.clock = kind, ExitStack(), Clock()
        self.events, self.queries, self.scopes, self.requests = [], [], [], []
        self.query_hook = self.session_hook = self.http_hook = self.spawn_hook = None
        self.query_close_error = self.scope_close_error = self.drain_error = None
        self.original_local_end = 130.0
        self.host_hook = lambda: None
        self.signal_hook = lambda _number, _handler: None

    def __enter__(self):
        self.base = Path(self.stack.enter_context(tempfile.TemporaryDirectory(prefix="collect-only-model-"))).resolve(strict=True)
        self.packets = Packets(self.kind)
        self.custody, self.primary = self.base / "primary-custody", self.base / "primary"
        self.packets.prior(self.custody, self.clock)
        self.git = self.base / "git-tools/git"
        self.git.parent.mkdir(mode=0o700)
        put(self.git, b"SUPPLIED_GIT_PATH_NOT_AN_EXECUTABLE\n")
        event = self.base / "event.json"
        put(event, self.packets.event)
        outputs = self.base / "_runner_file_commands"
        outputs.mkdir(mode=0o700)
        self.output = outputs / "set_output_aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
        put(self.output, b"")
        self.env = {**self.packets.env, "RUNNER_TEMP": str(self.base), "GITHUB_WORKSPACE": str(ROOT),
            "GITHUB_EVENT_PATH": str(event), "GITHUB_OUTPUT": str(self.output),
            D.PRIMARY_OUTCOME: "success", D.PRIMARY_RESULT: self.packets.primary["resultSha256"],
            D.PRIMARY_HANDOFF: self.packets.primary["handoffSha256"], D._COLLECT_OUTCOME: "success",
            D._COLLECT_STEP_HASH: sha(self.packets.raws["step"]), D._COLLECT_EXPORT_HASH: sha(self.packets.raws["manifest"])}
        for name in ("_PRIMARY_OWNERS", "_CUSTODY_OWNERS", "_COLLECT_CLOCKS", "_COLLECT_INPUTS", "_COLLECT_ATTEMPTS",
                "_COLLECT_AUTHORITY_RETURNS", "_COLLECT_RETURNS", "_COLLECT_OUTPUTS", "_EXPORT_STEPS"):
            self.stack.enter_context(patch.object(D, name, {}))
        for module, name in ((D, "_PRIMARY_QUARANTINE"), (D.native, "QUARANTINE"), (D.Q, "QUARANTINE"),
                (D.C, "QUARANTINE"), (D.native.diagnostics, "_QUARANTINE")):
            self.stack.enter_context(patch.object(module, name, []))
        self.stack.enter_context(self.environment(self.env))
        self.stack.enter_context(patch.object(D.time, "monotonic", self.clock.monotonic))
        self.stack.enter_context(patch.object(D.time, "time", lambda: self.packets.use))
        self.stack.enter_context(patch.object(D.O.clocks, "observe", self.clock.reading))
        self.stack.enter_context(patch.object(D.O.clocks, "checked_now", self.clock.checked))
        self.stack.enter_context(patch.object(D.C, "boot_digest", lambda _role: self.clock.boot))
        self.stack.enter_context(patch.object(D.native.processes, "host_role", lambda: "linux-x64"))
        self.stack.enter_context(patch.object(D.N, "location", lambda: (self.kind, self.primary)))
        self.stack.enter_context(patch.object(D, "_paths", self.paths))
        self.stack.enter_context(patch.object(D.N, "host_context", self.host))
        self.stack.enter_context(patch.object(D.I.shutil, "which", lambda _name: str(self.git)))
        self.stack.enter_context(patch.object(D.N, "query_owner", self.query_owner))
        self.stack.enter_context(patch.object(D.O, "_request", self.request))
        self.stack.enter_context(patch.object(D.native.processes, "make_scope", self.scope))
        self.stack.enter_context(patch.object(D.native, "signal", SimpleNamespace(SIGINT=signal.SIGINT, SIGTERM=signal.SIGTERM,
            getsignal=lambda _number: "SUPPLIED_PREVIOUS_HANDLER", signal=lambda number, handler: self.signal_hook(number, handler))))
        return self

    def __exit__(self, *args):
        return self.stack.__exit__(*args)

    @contextmanager
    def environment(self, value):
        # Only supplier-module variables change. The real process environment
        # never receives GITHUB_ACTIONS, hosted runner identity or test tokens.
        with ExitStack() as stack:
            for module in (D, D.N, D.A, D.native, D.Q, D.C):
                stack.enter_context(patch.object(module, "os", SimpleNamespace(**{**vars(os), "environ": value})))
            yield

    def paths(self, kind):
        ensure(kind == self.kind, "FIXED_KIND")
        return {"P": self.primary}, self.base / "primary-handoff", self.custody

    def host(self, first_use):
        ensure(first_use == self.packets.use, "ORIGINAL_FIRST_USE")
        self.host_hook()
        return self.packets.observed, self.primary, self.packets.event

    def query_owner(self, owner, fence, path):
        ensure(type(owner) is D._CustodyOwner and owner.fence is fence, "ORIGINAL_QUERY_PARENT")
        owner.end()
        supplier = QuerySupplier(self, owner, fence, path)
        self.queries.append(supplier)
        return supplier

    def request(self, path, token, invocation, fence, end):
        index = len(self.requests)
        ensure(index < 8 and token == TOKEN, "SINGLE_TOKEN_HTTP_EPISODE")
        name, expected, body = self.packets.bodies[index]
        ensure(path == expected and type(fence) is D._CollectClock and fence.side == "child" and end <= fence.work,
            "FIXED_HTTP_ROUTE_AND_ORIGINAL_CLIP")
        started = fence.now(limit=end)
        self.clock.advance(.002)
        finished = fence.now(limit=end)
        if self.http_hook is not None:
            body = self.http_hook(name, body)
        date = format_datetime(datetime.fromtimestamp(self.packets.use, timezone.utc), usegmt=True)
        headers = ("HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nCache-Control: private, no-store\r\n"
            "X-GitHub-Api-Version-Selected: 2022-11-28\r\nX-GitHub-Request-Id: SUPPLIED-COLLECT\r\nDate: " + date +
            "\r\nContent-Length: " + str(len(body)) + "\r\n\r\n").encode("ascii")
        raw = wire({"schema": 1, "scope": D.O.RESPONSE_SCOPE, "origin": D.O.wire.ORIGIN, "method": "GET", "path": path,
            "invocation": invocation, "clock": D.O.clock_value(self.clock.identity), "startedNs": started, "finishedNs": finished,
            "status": 200, "headersBase64": base64.b64encode(headers).decode("ascii"),
            "bodyBase64": base64.b64encode(body).decode("ascii"), "complete": True, "retirement": "KNOWN", "error": None})
        self.requests.append((name, raw))
        return raw, None

    def scope(self, job, invocation, state, home):
        result = Scope(self, job, invocation, state, home)
        self.scopes.append(result)
        return result

    def input(self):
        first = self.clock.reading()
        clock = D._CollectClock(first, self.clock.local, BOOT, self.clock.cancelled, side="parent")
        actual = D._collect_actual()
        result = D._read_collect_input(clock, self.kind, actual)
        expected = clock.bind_parent(result)
        return clock, result, expected

    def authority(self):
        self.env[D.O.wire.TOKEN_ENV] = TOKEN
        return D._collect_pre_metadata(self.kind, self.clock.cancelled)

    def closed(self):
        return D._collect_closed(self.authority())

    def export_currency_boundary(self):
        """Supply only the four old return-check boundaries, NOT currency itself.

        Actual new collect acquisition supplies the complete15 retained records
        below. They exercise the real retained-match/current-policy predicates,
        not a claim that authority-1 or crypto ran. Marker objects stand only at
        the explicitly patched prior-return APIs; no old registry row is added.
        The new original clock still makes the actual last callback observation.
        """
        episode = self.authority()
        clock, _inputs, _raw, _originals, match, captured = D._checked_collect_authority(episode)
        window = SimpleNamespace(clock=clock.clock)
        primary, authority = object(), object()
        original = type(match)(match.record)
        carrier = D.CustodyCryptoCarrier(object(), self.packets.raws["carrier"], wire(close_record(("directory", "writer"))))
        prior_close = wire(json.loads(self.packets.raws["carrier"])["parentClose"])
        history = wire({"serviceJob": self.packets.transfer["originalServiceJob"]})
        historical = (("P/acquisition-queries/candidate_policy_raw.bin", self.packets.policy_raw),)
        state = SimpleNamespace(carrier=carrier, window=window, clock=clock, original=original,
            primary=primary, authority=authority, primary_window=window, inputs=(primary, authority), checks=[])
        def checked_carrier(value):
            ensure(value is carrier, "EXPLICIT_PRIOR_CARRIER_ARGUMENT")
            state.checks.append("carrier")
            return window, clock, self.packets.raws["context"], self.packets.raws["manifest"], prior_close
        def crypto_inputs(value):
            ensure(value is carrier, "EXPLICIT_PRIOR_INPUT_ARGUMENT")
            state.checks.append("inputs")
            return state.inputs
        def checked_primary(value):
            ensure(value is primary, "EXPLICIT_PRIOR_PRIMARY_ARGUMENT")
            state.checks.append("primary")
            return state.primary_window, SimpleNamespace(kind=self.kind), history, object(), historical
        def checked_authority(value, first):
            ensure(value is authority and first is primary, "EXPLICIT_PRIOR_AUTHORITY_ARGUMENT")
            state.checks.append("authority")
            return window, original, captured, b"SUPPLIED_PRIOR_RETURN", (), ()
        for name, supplier in (("_checked_crypto_carrier", checked_carrier), ("_collect_crypto_inputs", crypto_inputs),
                ("checked_primary", checked_primary), ("checked_custody_authority", checked_authority)):
            self.stack.enter_context(patch.object(D, name, supplier))
        return state

    def export_step(self):
        """Supplied prior crypto-return boundary; NEW transfer writer stays real.

        The old carrier below is intentionally NOT entered in any old registry.
        Direct real _checked_crypto_carrier must refuse it. Only this one modeled
        caller boundary lets new transfer/output controls avoid the old crypto
        producer, original Window restoration or replay of its accepted tests.
        """
        (self.custody / "returned" / D._EXPORT_STEP_FILE).unlink()
        first = self.clock.reading()
        facade = D._CollectClock(first, self.clock.local, BOOT, self.clock.cancelled, side="parent")
        binding = (first, self.clock.local, BOOT, b"SUPPLIED_OLD_LIMITS", (), (), self.clock.cancelled)
        class WindowData:
            clock = first.clock
            def _view(inner):
                return SimpleNamespace(binding=binding, local_last=self.clock.local)
        window = WindowData()
        carrier = D.CustodyCryptoCarrier(object(), self.packets.raws["carrier"], wire(close_record(("directory", "writer"))))
        original_dictionary = carrier.__dict__
        def currency(value):
            ensure(value is carrier and value.__dict__ is original_dictionary and value.raw == self.packets.raws["carrier"],
                "SUPPLIED_ORIGINAL_CRYPTO_RETURN_BOUNDARY")
            facade.now()
            return window, facade, self.packets.raws["context"], self.packets.raws["manifest"], \
                wire(json.loads(self.packets.raws["carrier"])["parentClose"]), {"serviceJob": self.packets.transfer["originalServiceJob"]}
        self.stack.enter_context(patch.object(D, "_collect_export_currency", currency))
        result = D._retain_crypto_step(carrier)
        return result, facade
