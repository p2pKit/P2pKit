"""Synthetic external suppliers for the actual ordinary FULL controller.

These files, receipts, Git replies and xcresulttool replies are model inputs,
NOT native/build/signature/hosted evidence. No command is executed. The real
closed roster, canonical validators, artifact readers, Central preparation and
removal, Swift case assessor, both copy maps and separate seal consume them.
"""
from contextlib import redirect_stdout
import base64
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import patch
import zipfile


class Suppliers:
    def __init__(self, case, controller):
        self.t, self.c, self.f = case, controller, controller.supplements
        self.enabled = True
        self.codes, self.omit, self.children = {}, set(), []
        self.nested_counter = 1
        self.swift_boots = True
        self.swift_cases = {
            "p2pkit-sample-tests": [("ModelUnitTests/testOrdinary()", "Success")],
            "p2pkit-sample-uitests": [("ModelUITests/testOrdinary()", "Success")],
        }
        self.swift_refs = ["synthetic-tests-ref"]
        self.swift_object_override = None
        self.swift_modules, self.swift_poll_calls = [], []
        self.swift_spawn_output = self.swift_poll = None
        self.swift_code = 0
        self.helper_errors, self.git_calls, self.swift_calls = [], [], []
        self.central, self.central_context = None, None
        self.central_secret = (b"-----BEGIN PGP PRIVATE KEY BLOCK-----\n"
            b"SYNTHETIC-NOT-AN-ACTUAL-PRIVATE-KEY-0123456789abcdef0123456789abcdef\n"
            b"-----END PGP PRIVATE KEY BLOCK-----\n")
        self.central_fingerprint = "0123456789ABCDEF0123456789ABCDEF01234567"
        self.central_injections = {}
        self.central_git_seconds = 0
        self.central_registry_extra = None
        self.before_helper = self.after_helper = self.after_canonical = None
        self.t.save(case.root / "gradle.properties", b"GROUP=dev.p2pkit\nVERSION_NAME=0.7.0-SNAPSHOT\n")
        self.central_sources = ("gradle.properties", "scripts/prepare-audit-central-bundle-metadata.py",
                                "scripts/check-audit-receipt.py", "scripts/audit_processes.py")
        self.source_bytes = {name: (case.root / name).read_bytes() for name in self.central_sources}
        self.derived_diff = b"MODEL VERSION-ONLY DIFF; NOT A REAL GIT DIFF\n"

    def spec(self, name):
        run = self.c.parse((self.session / "run-context.json").read_bytes())
        return next(row for row in run["fullSupplementIntent"] if row["name"] == name)

    @property
    def session(self):
        return self.c.session_path("full", "macos-arm64")

    @property
    def state(self):
        return self.session / "state"

    def mkdir(self, path):
        path.mkdir(mode=0o700, parents=True, exist_ok=True)
        return path

    def file(self, path, value):
        self.mkdir(path.parent)
        return self.t.save(path, value)

    def canonical(self, identifier, purpose, kind, argv, ancestors, *, code=0, pid=None, finish=True):
        """Real-shaped supplier receipt, not a replacement canonical validator."""
        t, c = self.t, self.c
        folder = self.mkdir(self.state / "evidence" / identifier)
        pid = pid if pid is not None else 200000 + self.nested_counter
        start = {"schema": 1, "id": identifier, "purpose": purpose, "kind": kind, "requestedArgv": argv,
            "cwd": str(t.root), "wrapper": str(t.root / "gradlew"), "host": "macos-arm64", "jobId": t.job,
            "gradleHome": str(self.state / "gradle-home"), "startedUtc": "2026-09-16T00:00:00Z",
            "controllerPid": pid, "ancestorInvocationIds": ancestors, "evidenceDirectory": str(folder),
            "sourceBefore": None, "sourceAfter": None, "productExitCode": None, "stopExitCode": None,
            "finalExitCode": 125, "sourceUnchanged": False, "errors": [], "ownedSurvivors": []}
        self.file(folder / "start.json", start)
        executed = argv if kind == "command" else [str(t.root / "gradlew"), *c.audit.gradle_arguments(argv)]
        child_pid = pid + 100000
        identity = {"pid": child_pid, "uniqueId": child_pid + 10000, "startSeconds": 100,
                    "startMicroseconds": 0, "pidVersion": 1}
        result = {**start, "executedArgv": executed, "productPid": child_pid, "productLaunchIndex": 0,
            "sourceBefore": t.clean_source, "sourceAfter": t.clean_source, "sourceUnchanged": True,
            "productExitCode": code, "stopExitCode": 0, "finalExitCode": code,
            "ownership": {"backend": "darwin-libproc-audit-token", "scope": "controlled-marker-inheriting-descendants",
                "job": t.job, "invocation": identifier, "discoveryErrors": [], "startedIdentities": [identity],
                "launches": [{"api": "subprocess.Popen", "requestedArgv": executed, "cwd": str(t.root),
                              "shell": False, "created": True, "pid": child_pid}]}}
        for name in ("product.stdout.log", "product.stderr.log", "stop.stdout.log", "stop.stderr.log"):
            self.file(folder / name, b"MODEL EXTERNAL SUPPLIER, NOT AN EXECUTED PRODUCT\n")
        if finish:
            self.file(folder / "receipt.json", result)
        return folder, start, result

    def nested(self, spec, environment, purpose, argv, code=0):
        identifier = "b2" + format(self.nested_counter, "030x")
        self.nested_counter += 1
        parents = [*environment[self.c.processes.CHAIN_ENV].split(":"), spec["id"]]
        folder, _start, value = self.canonical(identifier, purpose, "gradle", argv, parents, code=code)
        self.children.append(value)
        return folder, value

    def canonical_child(self, args, environment):
        identifier = args[args.index("--id") + 1]
        specs = self.c.parse((self.session / "run-context.json").read_bytes())["fullSupplementIntent"]
        spec = next(row for row in specs if row["id"] == identifier)
        name, command = spec["name"], args[args.index("--") + 1:]
        self.t.assertEqual(command, spec["argv"])
        self.t.assertEqual(args[args.index("--kind") + 1], spec["kind"])
        self.t.assertEqual(args[args.index("--purpose") + 1], spec["purpose"])
        self.t.assertEqual(environment[self.c.processes.STATE_ENV], str(self.state))
        self.t.assertEqual(environment[self.c.processes.JOB_ENV], self.t.job)
        self.t.assertEqual(environment["GRADLE_USER_HOME"], str(self.state / "gradle-home"))
        code = self.codes.get(name, 0)
        if not self.enabled or name in self.omit:
            self.t.exit_code = code
            return
        folder, _start, result = self.canonical(spec["id"], spec["purpose"], spec["kind"], command,
            environment[self.c.processes.CHAIN_ENV].split(":"), code=code, pid=self.t.calls[-1]["pid"], finish=False)
        self.products(name, spec, environment, result)
        self.file(folder / "receipt.json", result)
        if "--receipt" in args:
            self.file(Path(args[args.index("--receipt") + 1]), (folder / "receipt.json").read_bytes())
        if self.after_canonical:
            self.after_canonical(name, folder, result)
        self.t.exit_code = code

    def products(self, name, spec, environment, result):
        t, c, state = self.t, self.c, self.state
        if name == "lock-policy":
            work = self.mkdir(state / "work/lock-policy.synthetic")
            self.file(work / "ownership.json", {"workDirectory": str(work), "stateDirectory": str(state),
                "jobId": t.job, "contextSha256": c.digest((state / "context.json").read_bytes())})
            for suffix in ("before", "after"):
                self.file(work / ("locks-" + suffix + ".txt"), b"SYNTHETIC IDENTICAL LOCK INVENTORY\n")
            selections = {"abbreviated": ["rALl", "--dry-run"],
                "indirect": ["indirectLockRefresh", "--dry-run", "--init-script", str(work / "indirect.init.gradle.kts")],
                "ordinary-write": ["help", "--write-locks", "--dry-run"],
                "configure-on-demand-write": ["rALl", "--write-locks", "--dry-run", "--configure-on-demand"],
                "authorized": ["rALl", "--write-locks", "--dry-run"]}
            for label, argv in selections.items():
                folder, _value = self.nested(spec, environment, "lock-policy-" + label,
                    [*argv, "--no-daemon", "--max-workers=2", "--console=plain"], 0 if label == "authorized" else 1)
                self.file(work / (label + ".log.receipt.json"), (folder / "receipt.json").read_bytes())
        elif name == "android-abi-graph":
            self.nested(spec, environment, name, [":p2p-core:check", ":p2p-transport-lan:check",
                ":p2p-network-provisioning-android:check", "--dependency-verification=strict", "--dry-run", "--console=plain"])
        elif name == "dokka-sbom":
            for module in self.f.MODULES:
                self.file(t.root / "library" / module / "build/dokka/html/index.html", b"<p>MODEL DOKKA OUTPUT</p>\n")
            self.file(t.root / "build/reports/cyclonedx/bom.json", {"bomFormat": "CycloneDX", "model": True})
            self.file(t.root / "build/reports/cyclonedx/bom.xml", b"<bom model='true'/>\n")
        elif name == "published-consumers":
            self.consumer(spec, environment)
        elif name == "xcframework-build":
            for suffix in self.f.SIDECARS:
                self.file(t.root / "library/p2p-transport-lan/build/XCFrameworks/release" / suffix,
                          ("SYNTHETIC " + suffix + "\n").encode())
        elif name == "swift-ui":
            self.file(state / "work/swift-ui/DerivedData/Logs/Test/Synthetic.xcresult/Data/data.bin",
                      b"MODEL XCRESULT BYTES; NOT A NATIVE TEST EXECUTION\n")
            if self.swift_boots:
                t.simulator_state("Booted")
        elif name == "central-bundle":
            self.central_product(spec, environment, result)

    def consumer(self, spec, environment):
        c, state = self.c, self.state
        work = state / "work/consumer"
        repo = self.mkdir(work / "repository")
        for suffix in ("pom", "module", "jar"):
            self.file(repo / "dev/p2pkit/model/0.7.0-SNAPSHOT" / ("model." + suffix), ("MODEL " + suffix + "\n").encode())
        publish_dir, publish = self.nested(spec, environment, "consumer-publish", ["--no-daemon", "--console=plain",
            "publishToMavenLocal", "-Dmaven.repo.local=" + str(repo)])
        helper = self.f.load_helper(Path(__file__).parents[1] / "prepare-audit-consumer-metadata.py", "model_consumer_contract")
        build_dir, build = self.nested(spec, environment, "consumer-build", ["--no-daemon", "--console=plain", "-p",
            str(work / "consumer"), "-PconsumerRepo=" + str(repo), *helper.CONSUMER_TASKS])
        receipts = self.mkdir(state / "consumer-receipts.synthetic")
        admission = self.file(receipts / "consumer-admission.json", {"contextId": self.t.job,
            "contextSha256": c.digest((state / "context.json").read_bytes()), "source": self.t.clean_source,
            "workDir": str(work), "repository": str(repo), "repositoryInitiallyAbsent": True})
        files = {str(path.relative_to(repo)): {"sha256": c.digest(path.read_bytes()), "bytes": path.stat().st_size}
                 for path in repo.rglob("*") if path.is_file()}
        publication = self.file(receipts / "consumer-publication-manifest.json", {"source": self.t.clean_source,
            "admissionSha256": c.digest(admission), "publicationId": publish["id"], "publicationCount": 15,
            "publicationReceiptSha256": c.digest((publish_dir / "receipt.json").read_bytes()), "repositoryFiles": files})
        self.file(receipts / "consumer-metadata-verification.json", {"source": self.t.clean_source, "result": "PASS",
            "publicationManifestSha256": c.digest(publication), "consumerBuildId": build["id"], "publicationCount": 15,
            "consumerBuildReceiptSha256": c.digest((build_dir / "receipt.json").read_bytes())})
        self.file(work / "consumer/kmpConsumer/build/bin/iosSimulatorArm64/debugFramework/P2pKitConsumer.framework/P2pKitConsumer",
                  b"MODEL NATIVE FRAMEWORK; NOT A COMPILED BINARY\n")

    def helper_child(self, argv, environment):
        script = Path(argv[4]).name
        if script not in ("inspect-ordinary-swift-results.py", "prepare-audit-central-bundle-metadata.py"):
            return False
        if self.before_helper:
            self.before_helper(script, argv, environment)
        module = self.f.load_helper(Path(__file__).parents[1] / script, "model_" + script.replace("-", "_"))
        swift = script.startswith("inspect-")
        if swift:
            self.swift_modules.append(module)
        try:
            with patch.dict(os.environ, environment, clear=True), patch.object(sys, "argv", argv[4:]), \
                    patch.object(module.subprocess, "Popen" if swift else "run",
                                 side_effect=self.swift_popen if swift else self.central_run), redirect_stdout(io.StringIO()):
                self.t.exit_code = module.main() or 0
        except BaseException as error:
            self.helper_errors.append((script, error))
            self.t.exit_code = 125
        if self.after_helper:
            self.after_helper(script, argv, environment)
        return True

    def swift_popen(self, argv, *, stdout, stderr, stdin, close_fds, env):
        self.t.assertEqual(stdin, subprocess.DEVNULL)
        self.t.assertTrue(close_fds)
        self.t.assertEqual(env[self.c.processes.JOB_ENV], self.t.job)
        # An external process writes the fd, not the caller's bounded .write().
        # Direct fd writes let the actual live verify() catch modeled floods.
        class Writer:
            def __init__(self, sink):
                self.sink = sink
            def write(self, raw):
                return os.write(self.sink.fileno(), raw)
        self.swift_run(argv, stdout=Writer(stdout), stderr=Writer(stderr), timeout=90, check=False)
        if self.swift_spawn_output:
            self.swift_spawn_output(argv, stdout, stderr)
        def poll():
            self.swift_poll_calls.append(list(argv))
            return self.swift_poll(argv, stdout, stderr) if self.swift_poll else self.swift_code
        return SimpleNamespace(pid=70000 + len(self.swift_calls), poll=poll)

    def swift_run(self, argv, *, stdout, stderr, timeout, check):
        self.t.assertGreater(timeout, 0)
        self.t.assertLessEqual(timeout, 90)
        prefix = ["/usr/bin/xcrun", "xcresulttool", "get", "object", "--legacy", "--format", "json", "--path"]
        self.t.assertEqual(argv[:8], prefix)
        self.swift_calls.append({"argv": list(argv), "timeout": timeout})
        if len(argv) == 9:
            value = {"actions": {"_values": [{"actionResult": {"testsRef": {"id": {"_value": item}}}}
                                              for item in self.swift_refs]}}
        else:
            self.t.assertEqual(argv[9], "--id")
            self.t.assertIn(argv[10], self.swift_refs)
            value = self.swift_object_override
            if value is None:
                value = {"summaries": {"_values": [{"_type": {"_name": "ActionTestableSummary"},
                    "targetName": {"_value": target}, "tests": {"_values": [
                        {"_type": {"_name": "ActionTestMetadata"}, "identifier": {"_value": name},
                         "testStatus": {"_value": status}} for name, status in cases]}}
                    for target, cases in self.swift_cases.items()]}}
        stdout.write(self.c.encoded(value))
        stderr.write(b"")
        return SimpleNamespace(returncode=0)

    def central_run(self, argv, **options):
        """Only modeled Git/GPG observations: never subprocess/native execution."""
        self.t.assertGreater(options.get("timeout", 60), 0)
        self.t.assertLessEqual(options.get("timeout", 60), 60)
        if argv[0] == "gpgconf":
            self.t.assertEqual(argv[-2:], ["--kill", "all"])
            options["stdout"].write(b"MODEL STOP OBSERVATION\n")
            return SimpleNamespace(returncode=0)
        self.t.assertEqual(argv[:2], ["git", "-C"])
        self.git_calls.append({"argv": list(argv), "timeout": options.get("timeout")})
        self.t.clock.now += self.central_git_seconds
        root, args = Path(argv[2]), argv[3:]
        fixture = self.state / "work/central-bundle/release-source"
        if args[:2] == ["worktree", "add"]:
            self.mkdir(fixture)
            for name, raw in self.source_bytes.items():
                self.file(fixture / name, raw)
            self.file(fixture / ".git", b"gitdir: MODEL-NOT-A-REAL-GIT-WORKTREE\n")
            raw = b"MODEL WORKTREE ADDED\n"
        elif args[:2] == ["worktree", "remove"]:
            self.t.assertEqual(args, ["worktree", "remove", "--force", str(fixture)])
            self.t.assertTrue(fixture.is_relative_to(self.t.path))
            shutil.rmtree(fixture)
            raw = self.central_injections.get("worktree-remove.stdout.log", b"MODEL WORKTREE REMOVED\n")
        elif args == ["worktree", "list", "--porcelain", "-z"]:
            raw = b"worktree " + os.fsencode(self.t.root) + b"\0"
            if self.central_registry_extra:
                raw += b"worktree " + os.fsencode(self.central_registry_extra) + b"\0"
            raw += self.central_injections.get("worktree-registry.stdout.log", b"")
        elif args == ["rev-parse", "--show-toplevel"]:
            raw = (str(root) + "\n").encode()
        elif args == ["rev-parse", "HEAD"]:
            raw = (self.t.source["commit"] + "\n").encode()
        elif args == ["rev-parse", "HEAD^{tree}"]:
            raw = (self.t.source["tree"] + "\n").encode()
        elif args == ["status", "--porcelain=v1", "--untracked-files=all"]:
            raw = b" M gradle.properties\n" if root == fixture else b""
        elif args == ["diff", "--binary", "--no-ext-diff", "--no-textconv", "HEAD"]:
            raw = self.derived_diff if root == fixture else b""
        elif args == ["ls-tree", "-r", "-z", "--full-tree", "HEAD"]:
            raw = b"".join(("100644 blob " + self.c.abi.blob(value) + "\t" + name + "\0").encode()
                           for name, value in self.source_bytes.items())
        else:
            raise AssertionError("UNMODELED_CENTRAL_GIT " + repr(argv))
        destination = options.get("stdout")
        if destination is not None and destination != subprocess.PIPE:
            destination.write(raw)
            error = self.central_injections.get("worktree-registry.stderr.log" if args[:2] == ["worktree", "list"]
                                                else "worktree-remove.stderr.log", b"")
            options["stderr"].write(error)
        return SimpleNamespace(returncode=0, stdout=raw, stderr=b"")

    def central_product(self, spec, environment, result):
        module = self.f.load_helper(self.t.root / "scripts/prepare-audit-central-bundle-metadata.py", "model_central_product")
        self.central = module
        c = self.c
        domains = c.processes.ownership_domains(environment[c.processes.CHAIN_ENV], environment[c.processes.DOMAINS_ENV])
        domains.append({"id": spec["id"], "job": self.t.job, "state": str(self.state), "home": str(self.state / "gradle-home")})
        env = {**environment, c.processes.CHAIN_ENV: ":".join(row["id"] for row in domains),
            c.processes.DOMAINS_ENV: json.dumps(domains), "P2PKIT_GPG_TMPDIR": str(self.t.path),
            "P2PKIT_GRADLE_EXECUTOR": str(self.t.root / "scripts/run-audit-command.py")}
        with patch.dict(os.environ, env, clear=True), patch.object(module.subprocess, "run", side_effect=self.central_run), \
                redirect_stdout(io.StringIO()):
            context = module.context()
            self.central_context = context
            module.admit(context, str(self.t.root))
            module.fixture(context)
            module.allocate_home(context, "signer")
            self.file(context["work"] / "key.asc", self.central_secret)
            with patch.dict(os.environ, {"ORG_GRADLE_PROJECT_signingInMemoryKeyBase64": base64.b64encode(self.central_secret).decode(),
                    "ORG_GRADLE_PROJECT_signingInMemoryKeyPassword": module.PASSWORD,
                    "MAVEN_SIGNING_KEY_FINGERPRINT": self.central_fingerprint}):
                module.builder(context, str(context["fixture"]), str(context["work"] / "p2pkit-test-central-bundle.zip"))
            self.file(context["repository"] / "release-key.asc", self.central_secret)
            module.allocate_home(context, "verifier")
            self.central_publication(context, spec, environment)
            module.stop_home(context, "signer")
            module.stop_home(context, "verifier")
            module.finish_builder(context, result["productExitCode"])
            self.t.assertEqual(module.finish(context, result["productExitCode"], "model-finished"), result["productExitCode"])

    def central_publication(self, context, spec, environment):
        module, c = self.central, self.c
        repo, work = context["repository"], context["work"]
        path = repo / "dev/p2pkit/model/9.8.7-rc6/model-9.8.7-rc6.pom"
        self.file(path, b"<project>MODEL NONPUBLISHING ARTIFACT</project>\n")
        self.file(Path(str(path) + ".asc"), b"MODEL SIGNATURE, NOT CRYPTOGRAPHIC PROOF\n")
        for algorithm in ("md5", "sha1", "sha256", "sha512"):
            self.file(Path(str(path) + "." + algorithm), (hashlib.new(algorithm, path.read_bytes()).hexdigest() + "\n").encode())
        folder, receipt = self.nested(spec, environment, module.PURPOSE, module.publish_arguments(context))
        self.file(context["evidence"] / "publish.json", (folder / "receipt.json").read_bytes())
        self.file(context["evidence"] / "publish-validation.json", {"finalExitCode": 0})
        members = {str(item.relative_to(repo)): item.read_bytes() for item in (repo / "dev").rglob("*") if item.is_file()}
        archive = work / "p2pkit-test-central-bundle.zip"
        with zipfile.ZipFile(archive, "w") as output:
            for name, raw in members.items():
                output.writestr(name, raw)
        self.file(archive.with_suffix(".manifest.sha256"), b"".join(
            (c.digest(raw) + "  " + name + "\n").encode() for name, raw in members.items()))
        self.file(archive.with_suffix(".summary.json"), {"schemaVersion": 1, "group": "dev.p2pkit", "version": "9.8.7-rc6",
            "signingKeyFingerprint": self.central_fingerprint, "bundleFile": archive.name,
            "bundleSha256": c.digest(archive.read_bytes()), "bundleSizeBytes": archive.stat().st_size, "signedFiles": 1})
        self.file(work / "signatures/1.status", b"MODEL GNUPG STATUS; NO REAL VERIFICATION\n")
        module.signature(context, SimpleNamespace(artifact=str(path.relative_to(repo)),
            status_file=str(work / "signatures/1.status"), fingerprint=self.central_fingerprint, status=0))
