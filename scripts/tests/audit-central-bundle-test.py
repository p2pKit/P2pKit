#!/usr/bin/env python3
"""Offline caller controls: synthetic Git/files; fake Gradle/GPG, never native proof."""

import hashlib
from contextlib import contextmanager
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import unittest
import uuid


ROOT = Path(__file__).resolve().parents[2]
FINGERPRINT = "0123456789ABCDEF0123456789ABCDEF01234567"
SECRET = "-----BEGIN PGP PRIVATE KEY BLOCK-----\nsynthetic-not-a-private-key-0123456789\n-----END PGP PRIVATE KEY BLOCK-----\n"

BOUNDARY = r'''
import hashlib, json, os, pathlib, signal, subprocess, sys, uuid, zipfile
name = pathlib.Path(sys.argv[0]).name
args = sys.argv[1:]
root = pathlib.Path(os.environ["FAKE_ROOT"])
trace = pathlib.Path(os.environ["FAKE_TRACE"])
fingerprint = "0123456789ABCDEF0123456789ABCDEF01234567"
secret = "-----BEGIN PGP PRIVATE KEY BLOCK-----\nsynthetic-not-a-private-key-0123456789\n-----END PGP PRIVATE KEY BLOCK-----\n"
def record(kind, **values):
    with trace.open("a") as stream:
        stream.write(json.dumps({"kind": kind, "argv": args, "cwd": os.getcwd(),
                                 "gradleHome": os.environ.get("GRADLE_USER_HOME"), **values}) + "\n")
def home():
    value = args[args.index("--homedir") + 1] if "--homedir" in args else os.environ.get("GNUPGHOME", str(root / "ambient"))
    return pathlib.Path(value)
if name in ("gpg", "gpgconf"):
    directory = home()
    record(name, home=str(directory), homeExists=directory.is_dir())
    if name == "gpgconf":
        code = int(os.environ.get("FAKE_GPG_STOP_EXIT", "0"))
        if code == 0:
            (directory / "synthetic-worker").unlink(missing_ok=True)
        sys.exit(code)
    if "--quick-generate-key" in args:
        directory.mkdir(exist_ok=True)
        (directory / "synthetic-worker").write_text("not a real process\n")
        if os.environ.get("FAKE_SIGNAL_KEYGEN"):
            os.kill(os.getppid(), signal.SIGTERM)
        sys.exit(int(os.environ.get("FAKE_KEYGEN_EXIT", "0")))
    if "--show-keys" in args or "--list-secret-keys" in args:
        print("pub:-:2048:1:FAKE:0:0::-:::scSC:")
        print("fpr:::::::::" + fingerprint + ":")
    elif "--export-secret-keys" in args:
        if os.environ.get("FAKE_PREPUBLICATION_INPUT"):
            path = pathlib.Path(os.environ["P2PKIT_CENTRAL_BUNDLE_WORK_DIR"]) / "release-source" / os.environ["FAKE_PREPUBLICATION_INPUT"]
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("not produced by this publication\n")
        sys.stdout.write(secret)
    elif "--import" in args:
        (directory / "synthetic-worker").write_text("not a real process\n")
    elif "--verify" in args:
        selected = "A" * 40 if os.environ.get("FAKE_BAD_SIGNATURE") else fingerprint
        print("[GNUPG:] VALIDSIG " + selected + " 20260916 0 4 0 1 10 00")
        sys.exit(int(os.environ.get("FAKE_VERIFY_EXIT", "0")))
    sys.exit(0)
if name == "gradlew":
    record("gradle-stop" if "--stop" in args else "gradle")
    if "--stop" in args:
        sys.exit(int(os.environ.get("FAKE_GRADLE_STOP_EXIT", "0")))
    project = pathlib.Path(args[args.index("-p") + 1]) if "-p" in args else pathlib.Path.cwd()
    props = dict(line.split("=", 1) for line in (project / "gradle.properties").read_text().splitlines() if "=" in line)
    repo = pathlib.Path(next(value.split("=", 1)[1] for value in args if value.startswith("-Dmaven.repo.local=")))
    folder = repo / props["GROUP"].replace(".", "/") / "synthetic" / props["VERSION_NAME"]
    folder.mkdir(parents=True, exist_ok=True)
    suffixes = ("jar", "pom", "module") if os.environ.get("FAKE_MODULE_METADATA") else ("jar", "pom")
    for suffix in suffixes:
        artifact = folder / ("synthetic-" + props["VERSION_NAME"] + "." + suffix)
        artifact.write_bytes(("synthetic " + suffix + "\n").encode())
        artifact.with_name(artifact.name + ".asc").write_text("synthetic signature\n")
    output = project / "library/example/build/reports/model"
    output.mkdir(parents=True, exist_ok=True)
    (output / "publication.txt").write_text("synthetic compilation, not a build result\n")
    if os.environ.get("FAKE_MUTATE_FIXTURE"):
        (project / "source.txt").write_text("unexpected source mutation\n")
    if os.environ.get("FAKE_EXTRA_FIXTURE"):
        (project / os.environ["FAKE_EXTRA_FIXTURE"]).write_text("unexpected input\n")
    if os.environ.get("FAKE_LOG_SECRET"):
        print(os.environ.get("ORG_GRADLE_PROJECT_signingInMemoryKeyBase64", ""))
    print("SYNTHETIC PUBLICATION ONLY")
    sys.exit(int(os.environ.get("FAKE_PUBLISH_EXIT", "0")))
if name == "run-audit-command.py":
    options, requested = args[:args.index("--")], args[args.index("--") + 1:]
    get = lambda flag: options[options.index(flag) + 1]
    cwd, wrapper, purpose = get("--cwd"), get("--wrapper"), get("--purpose")
    destination = pathlib.Path(get("--receipt"))
    state = pathlib.Path(os.environ["P2PKIT_AUDIT_STATE_DIR"])
    context = json.loads((state / "context.json").read_text())
    identifier = uuid.uuid4().hex
    directory = state / "evidence" / identifier
    directory.mkdir()
    start = {"schema": 1, "id": identifier, "purpose": purpose, "kind": "gradle", "cwd": cwd,
             "wrapper": wrapper, "requestedArgv": requested, "jobId": context["id"],
             "gradleHome": context["gradleHome"],
             "ancestorInvocationIds": os.environ["P2PKIT_AUDIT_OWNERSHIP_CHAIN"].split(":")}
    (directory / "start.json").write_text(json.dumps(start))
    record("executor", requested=requested, purpose=purpose)
    product = subprocess.run([wrapper, *requested], cwd=cwd, capture_output=True, timeout=15)
    stop = subprocess.run([wrapper, "--stop", "--console=plain"], cwd=cwd, capture_output=True, timeout=5)
    for kind, value in (("product.stdout.log", product.stdout), ("product.stderr.log", product.stderr),
                        ("stop.stdout.log", stop.stdout), ("stop.stderr.log", stop.stderr)):
        (directory / kind).write_bytes(value)
    sys.stdout.buffer.write(product.stdout)
    sys.stderr.buffer.write(product.stderr)
    code = product.returncode if stop.returncode == 0 else 125
    receipt = {"schema": 1, "id": identifier, "purpose": purpose, "kind": "gradle", "cwd": cwd,
               "wrapper": wrapper, "requestedArgv": requested, "jobId": context["id"],
               "gradleHome": context["gradleHome"], "host": context["host"],
               "sourceBefore": context["source"], "sourceAfter": context["source"], "sourceUnchanged": True,
               "productExitCode": product.returncode, "stopExitCode": stop.returncode, "finalExitCode": code,
               "errors": [] if stop.returncode == 0 else ["synthetic stop failure"], "ownedSurvivors": [],
               "ancestorInvocationIds": os.environ["P2PKIT_AUDIT_OWNERSHIP_CHAIN"].split(":"),
               "evidenceDirectory": str(directory),
               "ownership": {"backend": "darwin-libproc-audit-token", "discoveryErrors": [],
                             "job": context["id"], "invocation": identifier}}
    receipt.update(json.loads(os.environ.get("FAKE_RECEIPT_MUTATION", "{}")))
    raw = json.dumps(receipt, sort_keys=True).encode() + b"\n"
    (directory / "receipt.json").write_bytes(raw)
    if not os.environ.get("FAKE_MISSING_RECEIPT"):
        destination.write_bytes(raw + (b" " if os.environ.get("FAKE_RECEIPT_COPY_TAMPER") else b""))
    sys.exit(code)
if name == "check-publish-artifacts.sh":
    record("publication-inspector")
    print("SYNTHETIC PUBLICATION INSPECTOR ONLY")
    sys.exit(int(os.environ.get("FAKE_INSPECT_EXIT", "0")))
if name == "openssl":
    data = pathlib.Path(args[-1]).read_bytes()
    print("0" * 40 if os.environ.get("FAKE_BAD_CHECKSUM") and args[1] == "-sha1" else
          hashlib.new(args[1].lstrip("-"), data).hexdigest())
    sys.exit(0)
if name == "zip":
    destination = next(arg for arg in args if arg.endswith(".zip"))
    source = pathlib.Path(args[-1])
    with zipfile.ZipFile(destination, "w") as archive:
        for path in sorted(source.rglob("*")):
            if path.is_file(): archive.write(path, str(path))
    sys.exit(0)
if name == "unzip":
    with zipfile.ZipFile(args[-1]) as archive:
        sys.exit(1 if archive.testzip() else 0)
if name == "jq":
    values = {}; index = 0
    while index < len(args):
        if args[index] in ("--arg", "--argjson"):
            values[args[index + 1]] = json.loads(args[index + 2]) if args[index] == "--argjson" else args[index + 2]
            index += 3
        else: index += 1
    if "-n" in args:
        if os.environ.get("FAKE_CORRUPT_SUMMARY"):
            values["bundleSha256"] = "0" * 64
        print(json.dumps({"schemaVersion": 1, **values}))
        sys.exit(0)
    value = json.loads(pathlib.Path(args[-1]).read_text())
    sys.exit(0 if value.get("schemaVersion") == 1 and value.get("group") == values["group"] and
             value.get("version") == values["version"] and value.get("signingKeyFingerprint") == values["fingerprint"] and
             value.get("signedFiles", 0) > 0 else 1)
raise SystemExit("unexpected offline tool: " + name)
'''


def invoke(command, *, cwd, env, timeout=30):
    process = subprocess.Popen(command, cwd=cwd, env=env, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, text=True, start_new_session=True)
    try:
        stdout, stderr = process.communicate(timeout=timeout)
    except BaseException:
        if process.poll() is None:
            os.killpg(process.pid, signal.SIGKILL)
        process.communicate(timeout=5)
        raise
    return subprocess.CompletedProcess(command, process.returncode, stdout, stderr)


class AuditCentralBundleTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="central-offline-")
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name).resolve()
        self.root = self.base / "source with spaces"
        self.state = self.base / "state"
        self.work = self.state / "work" / "central bundle"
        self.evidence = self.state / "evidence" / "central-metadata"
        self.tools = self.base / "tools"
        self.short = Path(tempfile.mkdtemp(prefix="cb.", dir="/tmp")).resolve()
        self.addCleanup(shutil.rmtree, self.short)
        self.trace = self.base / "calls.jsonl"
        for directory in (self.root / "scripts/tests", self.root / "gradle/wrapper", self.tools,
                          self.state / "work", self.state / "evidence", self.state / "gradle-home",
                          self.base / "home", self.base / "temporary"):
            directory.mkdir(parents=True, exist_ok=True)
        for name in ("tests/build-central-portal-bundle-test.sh", "build-central-portal-bundle.sh",
                     "prepare-audit-central-bundle-metadata.py", "check-audit-receipt.py", "audit_processes.py"):
            if (ROOT / "scripts" / name).is_file():
                shutil.copy2(ROOT / "scripts" / name, self.root / "scripts" / name)
        (self.root / "gradle.properties").write_text("GROUP=example.audit\nVERSION_NAME=0.7.0-SNAPSHOT\n")
        (self.root / "source.txt").write_text("original source\n")
        (self.root / "library/example").mkdir(parents=True)
        (self.root / "library/example/build.gradle.kts").write_text("// synthetic input\n")
        (self.root / ".gitignore").write_text(".gradle/\n.kotlin/\nbuild/\nlocal.properties\n")
        for name in ("gradle-wrapper.properties", "gradle-wrapper.jar"):
            (self.root / "gradle/wrapper" / name).write_text("synthetic wrapper input\n")
        for path in (self.root / "gradlew", self.root / "scripts/run-audit-command.py",
                     self.root / "scripts/check-publish-artifacts.sh",
                     *(self.tools / name for name in ("gpg", "gpgconf", "zip", "unzip", "openssl", "jq"))):
            path.write_text("#!" + sys.executable + "\n" + BOUNDARY)
            path.chmod(0o755)
        self.env = dict(os.environ)
        for name in list(self.env):
            if name.startswith(("P2PKIT_", "FAKE_", "GIT_", "ORG_GRADLE_PROJECT_", "MAVEN_")) or name in (
                    "GNUPGHOME", "BASH_ENV", "ENV", "JAVA_OPTS", "GRADLE_OPTS", "JAVA_TOOL_OPTIONS", "JDK_JAVA_OPTIONS"):
                self.env.pop(name)
        self.env.update(PATH=str(self.tools) + os.pathsep + os.environ["PATH"], HOME=str(self.base / "home"),
                        TMPDIR=str(self.base / "temporary"), P2PKIT_RELEASE_TMPDIR=str(self.base / "temporary"),
                        P2PKIT_GPG_TMPDIR=str(self.short), GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull,
                        FAKE_ROOT=str(self.root), FAKE_TRACE=str(self.trace), PYTHONDONTWRITEBYTECODE="1")
        for args in (("init", "-q"), ("config", "user.name", "Synthetic audit"),
                     ("config", "user.email", "synthetic@example.invalid"), ("add", "."),
                     ("-c", "commit.gpgsign=false", "-c", "core.hooksPath=" + os.devnull,
                      "commit", "-qm", "Synthetic fixture; not product provenance")):
            self.git(*args)
        self.source = {"commit": self.git("rev-parse", "HEAD").strip(),
                       "tree": self.git("rev-parse", "HEAD^{tree}").strip(), "status": "",
                       "diffSha256": hashlib.sha256(b"").hexdigest()}
        self.job, self.outer = uuid.uuid4().hex, uuid.uuid4().hex
        policy = b"org.gradle.workers.max=2\norg.gradle.parallel=false\n"
        (self.state / "gradle-home/gradle.properties").write_bytes(policy)
        self.context = {"schema": 1, "id": self.job, "root": str(self.root),
                        "expectedCommit": self.source["commit"], "tree": self.source["tree"], "source": self.source,
                        "gradleHome": str(self.state / "gradle-home"), "host": "macos-arm64",
                        "gradlePropertiesSha256": hashlib.sha256(policy).hexdigest()}
        (self.state / "context.json").write_text(json.dumps(self.context))
        self.outer_directory = self.state / "evidence" / self.outer
        self.outer_directory.mkdir()
        self.outer_start = {"schema": 1, "id": self.outer, "jobId": self.job, "kind": "command",
                            "purpose": "central-bundle", "cwd": str(self.root), "wrapper": str(self.root / "gradlew"),
                            "requestedArgv": ["bash", "scripts/tests/build-central-portal-bundle-test.sh"],
                            "gradleHome": str(self.state / "gradle-home"), "ancestorInvocationIds": []}
        (self.outer_directory / "start.json").write_text(json.dumps(self.outer_start))
        self.options = {"P2PKIT_CENTRAL_BUNDLE_AUDIT": "1", "P2PKIT_AUDIT_STATE_DIR": str(self.state),
                        "P2PKIT_CENTRAL_BUNDLE_WORK_DIR": str(self.work),
                        "P2PKIT_CENTRAL_BUNDLE_EVIDENCE_DIR": str(self.evidence),
                        "P2PKIT_GRADLE_EXECUTOR": str(self.root / "scripts/run-audit-command.py"),
                        "GRADLE_USER_HOME": str(self.state / "gradle-home"), "P2PKIT_AUDIT_JOB_ID": self.job,
                        "P2PKIT_AUDIT_OWNERSHIP_CHAIN": self.outer,
                        "P2PKIT_AUDIT_OWNERSHIP_DOMAINS": json.dumps([
                            {"id": self.outer, "job": self.job, "state": str(self.state),
                             "home": str(self.state / "gradle-home")}])}

    def git(self, *args):
        result = invoke(["git", "-C", str(self.root), *args], cwd=self.base, env=self.env)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout

    def run_gate(self, overrides=None, *, audited=True):
        return invoke(["bash", "scripts/tests/build-central-portal-bundle-test.sh"], cwd=self.root,
                      env={**self.env, **(self.options if audited else {}), **(overrides or {})})

    def calls(self, kind=None):
        rows = [json.loads(line) for line in self.trace.read_text().splitlines()] if self.trace.exists() else []
        return [row for row in rows if kind is None or row["kind"] == kind]

    def helper(self, *arguments, overrides=None):
        return invoke([sys.executable, "-I", "-B", "-S", str(self.root / "scripts/prepare-audit-central-bundle-metadata.py"),
                       *arguments], cwd=self.root, env={**self.env, **self.options, **(overrides or {})})

    def result(self):
        return json.loads((self.evidence / "result.json").read_text())

    @contextmanager
    def scenario(self):
        case = type(self)("test_audit_refuses_nonempty_borrowed_work_before_any_tool")
        try:
            case.setUp()
            yield case
        finally:
            case.doCleanups()

    def rebind(self):
        self.git("add", ".")
        self.git("-c", "commit.gpgsign=false", "-c", "core.hooksPath=" + os.devnull, "commit", "-qm", "Synthetic variant")
        self.source.update(commit=self.git("rev-parse", "HEAD").strip(), tree=self.git("rev-parse", "HEAD^{tree}").strip())
        self.context.update(source=self.source, expectedCommit=self.source["commit"], tree=self.source["tree"])
        (self.state / "context.json").write_text(json.dumps(self.context))

    def admit_fixture(self):
        for arguments in (("admit", "--root", str(self.root)), ("fixture",)):
            result = self.helper(*arguments)
            self.assertEqual(result.returncode, 0, self.output(result))

    def outer_receipt(self, status=0, changes=None):
        # Synthetic model of an enclosing receipt, not a native retirement witness.
        value = {**self.outer_start, "host": self.context["host"], "sourceBefore": self.source,
                 "sourceAfter": self.source, "sourceUnchanged": True, "productExitCode": status,
                 "stopExitCode": 0, "finalExitCode": status, "errors": [], "ownedSurvivors": [],
                 "evidenceDirectory": str(self.outer_directory),
                 "ownership": {"backend": "darwin-libproc-audit-token", "job": self.job,
                               "invocation": self.outer, "discoveryErrors": []}, **(changes or {})}
        path = self.outer_directory / "receipt.json"
        path.write_text(json.dumps(value))
        return path

    @staticmethod
    def output(result):
        return f"exit={result.returncode}\n{result.stdout}\n{result.stderr}"

    def test_audit_refuses_nonempty_borrowed_work_before_any_tool(self):
        self.work.mkdir()
        sentinel = self.work / "caller-owned.txt"
        sentinel.write_text("preserve caller input\n")
        result = self.run_gate()
        self.assertNotEqual(result.returncode, 0, self.output(result))
        self.assertEqual(self.calls(), [])
        self.assertEqual(sentinel.read_text(), "preserve caller input\n")

    def test_exact_fixture_routes_root_wrapper_and_retains_pending_then_retires(self):
        result = self.run_gate({"FAKE_MODULE_METADATA": "1"})
        self.assertEqual(result.returncode, 0, self.output(result))
        metadata = self.result()
        self.assertEqual(metadata["nativeRetirement"], "REQUIRES_ENCLOSING_CANONICAL_RECEIPT")
        self.assertFalse(metadata["workRemoved"])
        self.assertEqual(metadata["gpgStopExitCodes"], {"signer": 0, "verifier": 0})
        self.assertFalse(metadata["bundle"]["zipBytesRetained"])
        home_paths = [Path(json.loads((self.evidence / (role + "-home.json")).read_text())["path"])
                      for role in ("signer", "verifier")]
        self.assertNotEqual(*home_paths)
        self.assertTrue(all(path.is_dir() for path in home_paths))
        self.assertTrue(self.work.is_dir())
        self.assertEqual(len(self.calls("executor")), 1)
        request = self.calls("executor")[0]["requested"]
        self.assertEqual(request, ["--no-daemon", "--no-build-cache", "--rerun-tasks", "--console=plain", "-p",
                                   str(self.work / "release-source"), "publishToMavenLocal", "-PsigningInMemoryKey=",
                                   "-PreleasePublication=true", "-Dmaven.repo.local=" + str(self.work / "repository")])
        self.assertTrue(all(row["cwd"] == str(self.root) and row["gradleHome"] == str(self.state / "gradle-home")
                            for row in self.calls("gradle") + self.calls("gradle-stop")))
        self.assertTrue(all("--homedir" in row["argv"] and row["homeExists"] for row in self.calls("gpg")))
        self.assertEqual({row["home"] for row in self.calls("gpgconf")}, {str(path) for path in home_paths})
        self.assertTrue((self.evidence / "originals/reports/library/example/build/reports/model/publication.txt").is_file())
        self.assertTrue((self.evidence / "originals/publication/receipt.json").is_file())
        for suffix in ("pom", "module"):
            name = "example/audit/synthetic/9.8.7-rc6/synthetic-9.8.7-rc6." + suffix
            self.assertTrue((self.evidence / "originals/metadata" / name).is_file(),
                            "selected publication metadata bytes must be retained")
            self.assertEqual((self.evidence / "originals/metadata" / name).read_bytes(),
                             (self.work / "repository" / name).read_bytes())
        self.assertFalse(any(path.suffix in ("jar", "zip", "asc") for path in (self.evidence / "originals").rglob("*")))
        self.assertIn("cannot use a SNAPSHOT version", (self.evidence / "originals/logs/snapshot.log").read_text())
        self.assertIn("an in-memory signing key is required", (self.evidence / "originals/logs/missing-key.log").read_text())
        self.assertEqual(self.git("-C", str(self.work / "release-source"), "rev-parse", "HEAD").strip(), self.source["commit"])
        self.assertIn("VERSION_NAME=9.8.7-rc6", (self.work / "release-source/gradle.properties").read_text())
        for mutation in ({"ownedSurvivors": [{"status": "UNKNOWN"}]}, {"stopExitCode": 8},
                         {"errors": ["native close uncertainty"]}, {"ancestorInvocationIds": [uuid.uuid4().hex]},
                         {"ownership": {"backend": "unqualified-model", "job": self.job, "invocation": self.outer,
                                        "discoveryErrors": []}}):
            with self.subTest(outer=mutation):
                rejected = self.helper("retire", "--outer-receipt", str(self.outer_receipt(changes=mutation)))
                self.assertEqual(rejected.returncode, 125, self.output(rejected))
                self.assertTrue(self.work.is_dir())
                self.assertTrue(all(path.is_dir() for path in home_paths))
        retained = self.evidence / "originals/logs/keygen.log"
        original = retained.read_bytes()
        retained.chmod(0o600)
        retained.write_text("replaced original\n")
        rejected = self.helper("retire", "--outer-receipt", str(self.outer_receipt()))
        self.assertEqual(rejected.returncode, 125, self.output(rejected))
        self.assertTrue(self.work.is_dir())
        retained.write_bytes(original)
        retained.chmod(0o444)
        retired = self.helper("retire", "--outer-receipt", str(self.outer_receipt()))
        self.assertEqual(retired.returncode, 0, self.output(retired))
        self.assertFalse(self.work.exists())
        self.assertTrue(all(not path.exists() for path in home_paths))
        self.assertTrue(json.loads((self.evidence / "retirement.json").read_text())["workRemoved"])

    def test_worktree_removal_failure_retains_exact_outcome_and_reachable_homes(self):
        result = self.run_gate()
        self.assertEqual(result.returncode, 0, self.output(result))
        real_git = shutil.which("git", path=self.env["PATH"])
        wrapper = self.tools / "git"
        wrapper.write_text("#!" + sys.executable + "\nimport os, sys\n"
                           "if sys.argv[3:5] == ['worktree', 'remove']:\n"
                           "    print('synthetic removal refusal', file=sys.stderr)\n"
                           "    raise SystemExit(23)\n"
                           "os.execv(" + repr(real_git) + ", [" + repr(real_git) + ", *sys.argv[1:]])\n")
        wrapper.chmod(0o755)
        retired = self.helper("retire", "--outer-receipt", str(self.outer_receipt()))
        self.assertEqual(retired.returncode, 125, self.output(retired))
        record = self.evidence / "worktree-removal.json"
        self.assertTrue(record.is_file(), "the failed removal's exact status must be retained")
        observation = json.loads(record.read_text())
        self.assertEqual(observation["argv"], ["git", "-C", str(self.root), "worktree", "remove", "--force",
                                               str(self.work / "release-source")])
        self.assertEqual(observation["exitCode"], 23)
        self.assertIsNone(observation["errorType"])
        self.assertFalse(observation["pathAbsent"])
        self.assertEqual(observation["registry"]["argv"],
                         ["git", "-C", str(self.root), "worktree", "list", "--porcelain", "-z"])
        self.assertEqual(observation["registry"]["exitCode"], 0)
        self.assertIsNone(observation["registry"]["errorType"])
        self.assertFalse(observation["registryAbsent"])
        self.assertEqual((self.evidence / "worktree-remove.stderr.log").read_text(), "synthetic removal refusal\n")
        self.assertFalse((self.evidence / "retirement.json").exists())
        self.assertTrue((self.work / "release-source").is_dir())
        for role in ("signer", "verifier"):
            self.assertTrue(Path(json.loads((self.evidence / (role + "-home.json")).read_text())["path"]).is_dir())

    def test_invalid_paths_are_refused_without_touching_callers(self):
        foreign = self.base / "foreign"
        foreign.mkdir()
        sentinel = foreign / "sentinel"
        sentinel.write_text("preserve\n")
        link = self.state / "work/link"
        link.symlink_to(foreign, target_is_directory=True)
        for key, value in (("P2PKIT_CENTRAL_BUNDLE_WORK_DIR", "relative"),
                           ("P2PKIT_CENTRAL_BUNDLE_WORK_DIR", str(link)),
                           ("P2PKIT_CENTRAL_BUNDLE_WORK_DIR", str(foreign)),
                           ("P2PKIT_CENTRAL_BUNDLE_EVIDENCE_DIR", str(self.work)),
                           ("P2PKIT_CENTRAL_BUNDLE_EVIDENCE_DIR", str(foreign))):
            with self.subTest(key=key, value=value):
                result = self.run_gate({key: value})
                self.assertEqual(result.returncode, 125, self.output(result))
                self.assertEqual(self.calls(), [])
                self.assertEqual(sentinel.read_text(), "preserve\n")
        self.evidence.mkdir()
        (self.evidence / "caller.json").write_text("{}")
        result = self.run_gate()
        self.assertEqual(result.returncode, 125, self.output(result))
        self.assertTrue((self.evidence / "caller.json").exists())

    def test_source_context_home_and_outer_admission_bindings(self):
        cases = ({"GRADLE_USER_HOME": str(self.base / "home")}, {"P2PKIT_AUDIT_JOB_ID": uuid.uuid4().hex},
                 {"P2PKIT_GRADLE_EXECUTOR": str(self.tools / "untrusted")},
                 {"P2PKIT_AUDIT_OWNERSHIP_CHAIN": ""}, {"ORG_GRADLE_PROJECT_signingInMemoryKey": "not a key"})
        for mutation in cases:
            with self.subTest(environment=mutation):
                result = self.run_gate(mutation)
                self.assertEqual(result.returncode, 125, self.output(result))
                self.assertEqual(self.calls(), [])
        for name in ("gradlew", "scripts/build-central-portal-bundle.sh"):
            with self.subTest(source=name):
                path = self.root / name
                old = path.read_bytes()
                path.write_bytes(old + b"\n# unreviewed overlay\n")
                result = self.run_gate()
                self.assertEqual(result.returncode, 125, self.output(result))
                self.assertEqual(self.calls(), [])
                path.write_bytes(old)
        self.context["tree"] = "0" * 40
        (self.state / "context.json").write_text(json.dumps(self.context))
        result = self.run_gate()
        self.assertEqual(result.returncode, 125, self.output(result))
        self.assertEqual(self.calls(), [])

    def test_manifest_cannot_authorize_second_source_change_or_extra_input(self):
        for name in ("source.txt", "gradlew", "scripts/build-central-portal-bundle.sh", "local.properties"):
            with self.subTest(name=name), self.scenario() as case:
                case.admit_fixture()
                path = case.work / "release-source" / name
                path.write_text("unexpected fixture input\n")
                result = case.helper("publish")
                self.assertEqual(result.returncode, 125, case.output(result))
                self.assertEqual(case.calls(), [])
        with self.scenario() as case:
            case.admit_fixture()
            manifest_path = case.evidence / "fixture.json"
            manifest = json.loads(manifest_path.read_text())
            altered = case.work / "release-source/source.txt"
            altered.write_bytes(b"manifest-forged source\n")
            manifest["tracked"]["source.txt"]["sha256"] = hashlib.sha256(altered.read_bytes()).hexdigest()
            manifest_path.chmod(0o600)
            manifest_path.write_text(json.dumps(manifest))
            result = case.helper("publish")
            self.assertEqual(result.returncode, 125, case.output(result))
            self.assertIn("exact version-only derivative", result.stderr)
            self.assertEqual(case.calls(), [])

    def test_audit_fixture_does_not_copy_ignored_local_settings(self):
        (self.root / "local.properties").write_text("sdk.dir=unrelated-caller-setting\n")
        self.admit_fixture()
        self.assertFalse((self.work / "release-source/local.properties").exists())
        self.assertTrue((self.root / "local.properties").exists())

    def test_prepublication_generated_inputs_are_rejected_before_launch(self):
        for name in (".gradle/injected.bin", "buildSrc/build/injected.bin", "library/example/build/injected.bin"):
            with self.subTest(name=name), self.scenario() as case:
                result = case.run_gate({"FAKE_PREPUBLICATION_INPUT": name})
                self.assertEqual(result.returncode, 125, case.output(result))
                self.assertIn("pre-publication generated path", (case.work / "bundle.log").read_text())
                self.assertEqual(case.calls("executor"), [])

    def test_non_snapshot_fixture_keeps_git_and_version_without_synthetic_commit(self):
        (self.root / "gradle.properties").write_text("GROUP=example.audit\nVERSION_NAME=1.2.3-rc9\n")
        self.rebind()
        self.admit_fixture()
        manifest = json.loads((self.evidence / "fixture.json").read_text())
        self.assertEqual(manifest["version"], "1.2.3-rc9")
        self.assertEqual(manifest["source"], self.source)
        self.assertEqual((self.evidence / "fixture-version.diff").read_bytes(), b"")

    def test_post_publication_mutation_stops_before_inspection(self):
        for mutation in ({"FAKE_MUTATE_FIXTURE": "1"}, {"FAKE_EXTRA_FIXTURE": "local.properties"}):
            with self.subTest(mutation=mutation), self.scenario() as case:
                result = case.run_gate(mutation)
                self.assertEqual(result.returncode, 125, case.output(result))
                self.assertEqual(case.calls("publication-inspector"), [])
                self.assertIn("post-publication fixture", (case.evidence / "publish-validation.json").read_text())
                self.assertTrue(case.work.exists())

    def test_bad_nested_receipts_and_same_home_stop_fail_closed(self):
        variants = ({"FAKE_MISSING_RECEIPT": "1"}, {"FAKE_RECEIPT_COPY_TAMPER": "1"},
                    {"FAKE_RECEIPT_MUTATION": json.dumps({"sourceAfter": {}})},
                    {"FAKE_RECEIPT_MUTATION": json.dumps({"requestedArgv": ["wrong-task"]})},
                    {"FAKE_RECEIPT_MUTATION": json.dumps({"ancestorInvocationIds": []})},
                    {"FAKE_RECEIPT_MUTATION": json.dumps({"ownedSurvivors": [{"status": "UNKNOWN"}]})},
                    {"FAKE_GRADLE_STOP_EXIT": "9"})
        for mutation in variants:
            with self.subTest(mutation=mutation), self.scenario() as case:
                result = case.run_gate(mutation)
                self.assertEqual(result.returncode, 125, case.output(result))
                self.assertEqual(case.calls("publication-inspector"), [])
                self.assertEqual(len(case.calls("gradle-stop")), 1)
                self.assertTrue(case.work.is_dir())
                self.assertNotEqual(case.result()["finalExitCode"], 0)

    def test_product_failure_preserves_original_exit_and_diagnostics(self):
        result = self.run_gate({"FAKE_PUBLISH_EXIT": "27"})
        self.assertEqual(result.returncode, 27, self.output(result))
        self.assertEqual(self.calls("publication-inspector"), [])
        self.assertEqual(self.result()["productExitCode"], 27)
        self.assertIn("SYNTHETIC PUBLICATION ONLY", (self.evidence / "originals/publication/product.stdout.log").read_text())
        self.assertTrue(self.work.is_dir())
        retired = self.helper("retire", "--outer-receipt", str(self.outer_receipt(27)))
        self.assertEqual(retired.returncode, 0, self.output(retired))
        self.assertFalse(json.loads((self.evidence / "retirement.json").read_text())["productPassed"])

    def test_gpg_stop_failure_retains_both_reachable_homes(self):
        result = self.run_gate({"FAKE_GPG_STOP_EXIT": "7"})
        self.assertEqual(result.returncode, 125, self.output(result))
        metadata = self.result()
        self.assertEqual(metadata["gpgStopExitCodes"], {"signer": 7, "verifier": 7})
        for role in ("signer", "verifier"):
            home = Path(json.loads((self.evidence / (role + "-home.json")).read_text())["path"])
            self.assertTrue(home.is_dir())
        self.assertEqual(json.loads((self.evidence / "builder-result.json").read_text())["productExitCode"], 0)
        retired = self.helper("retire", "--outer-receipt", str(self.outer_receipt(125)))
        self.assertEqual(retired.returncode, 125, self.output(retired))
        self.assertTrue(self.work.is_dir())

    def test_key_generation_failure_and_cancellation_keep_original_status(self):
        for mutation, status in (({"FAKE_KEYGEN_EXIT": "41"}, 41), ({"FAKE_SIGNAL_KEYGEN": "1"}, 143)):
            with self.subTest(mutation=mutation), self.scenario() as case:
                result = case.run_gate(mutation)
                self.assertEqual(result.returncode, status, case.output(result))
                self.assertEqual(case.calls("gradle"), [])
                self.assertEqual(case.result()["productExitCode"], status)
                self.assertEqual(case.result()["gpgStopExitCodes"], {"signer": 0})
                self.assertTrue((case.evidence / "originals/logs/keygen.log").exists())
                self.assertTrue(case.work.is_dir())

    def test_validsig_with_nonzero_exit_is_not_an_audit_signature_pass(self):
        result = self.run_gate({"FAKE_VERIFY_EXIT": "2"})
        self.assertEqual(result.returncode, 1, self.output(result))
        signatures = list((self.evidence / "originals/signatures").glob("*.json"))
        self.assertEqual(len(signatures), 2)
        self.assertTrue(all(json.loads(path.read_text())["exitCode"] == 2 and
                            json.loads(path.read_text())["valid"] is False for path in signatures))
        self.assertEqual(self.result()["productExitCode"], 1)

    def test_corrupt_summary_and_checksum_are_rejected_with_originals_retained(self):
        for mutation in ({"FAKE_CORRUPT_SUMMARY": "1"}, {"FAKE_BAD_CHECKSUM": "1"}):
            with self.subTest(mutation=mutation), self.scenario() as case:
                result = case.run_gate(mutation)
                self.assertEqual(result.returncode, 125, case.output(result))
                self.assertIn("bundle/fixture verification", str(case.result()["errors"]))
                self.assertEqual(case.result()["retentionStatus"], "RETAINED")
                self.assertTrue((case.evidence / "originals/p2pkit-test-central-bundle.summary.json").is_file())
                self.assertTrue(case.work.is_dir())

    def test_leaked_secret_is_quarantined_not_exported_as_sanitized_original(self):
        result = self.run_gate({"FAKE_LOG_SECRET": "1"})
        self.assertEqual(result.returncode, 125, self.output(result))
        self.assertEqual(self.result()["retentionStatus"], "HOLD_PRIVATE_QUARANTINE")
        self.assertFalse((self.evidence / "originals").exists())
        for path in self.evidence.rglob("*"):
            if path.is_file():
                self.assertNotIn(SECRET.encode(), path.read_bytes())
                self.assertNotIn(__import__("base64").b64encode(SECRET.encode()), path.read_bytes())
        # Original canonical leaf logs stay private and reachable; later controller
        # export MUST treat this marker as non-exportable, not copy all of STATE.
        raw = list((self.state / "evidence").glob("*/product.stdout.log"))
        self.assertTrue(any(__import__("base64").b64encode(SECRET.encode()) in path.read_bytes() for path in raw))
        self.assertTrue(self.work.is_dir())

    def test_overlong_gpg_home_rejected_before_key_generation(self):
        long_parent = self.base / ("long" * 30)
        long_parent.mkdir()
        result = self.run_gate({"P2PKIT_GPG_TMPDIR": str(long_parent)})
        self.assertEqual(result.returncode, 125, self.output(result))
        self.assertEqual(self.calls("gpg"), [])
        self.assertEqual(list(long_parent.iterdir()), [])

    def test_missing_key_negative_requires_specific_diagnostic(self):
        path = self.root / "scripts/build-central-portal-bundle.sh"
        path.write_text(path.read_text().replace("an in-memory signing key is required", "unrelated error"))
        self.rebind()
        result = self.run_gate()
        self.assertEqual(result.returncode, 1, self.output(result))
        self.assertIn("did not identify the missing-key rejection", result.stderr)
        self.assertEqual(self.calls("gpg"), [])
        self.assertIn("unrelated error", (self.evidence / "originals/logs/missing-key.log").read_text())

    def test_ordinary_caller_does_not_opt_in_from_ambient_executor(self):
        result = self.run_gate({"P2PKIT_GRADLE_EXECUTOR": self.options["P2PKIT_GRADLE_EXECUTOR"]}, audited=False)
        self.assertEqual(result.returncode, 0, self.output(result))
        self.assertEqual(self.calls("executor"), [])
        self.assertEqual(len(self.calls("gradle")), 1)
        self.assertEqual(len(self.calls("gpgconf")), 2)
        self.assertFalse(self.evidence.exists())
        self.assertTrue(all(not Path(row["home"]).exists() for row in self.calls("gpgconf")))

    def test_ordinary_non_snapshot_uses_original_source_without_version_change(self):
        path = self.root / "gradle.properties"
        path.write_text("GROUP=example.audit\nVERSION_NAME=1.2.3-rc9\n")
        result = self.run_gate(audited=False)
        self.assertEqual(result.returncode, 0, self.output(result))
        self.assertEqual(self.calls("gradle")[0]["cwd"], str(self.root))
        self.assertEqual(self.calls("executor"), [])
        self.assertIn("VERSION_NAME=1.2.3-rc9", path.read_text())


if __name__ == "__main__":
    unittest.main(verbosity=2)
