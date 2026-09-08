#!/usr/bin/env python3
"""Exercise real audit leaf callers with fake, recordable tool boundaries.

These are POSIX host contract tests, not Gradle, Xcode, simulator, or device
acceptance. Only copied first-party entrypoints run. Every wrapper, executor,
and native executable in each disposable checkout is a synthetic fixture.
The actual ios-run-lock.py still owns and registers each mutating worker.
"""

import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
import unittest
import uuid


sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
PROCESS_SPEC = importlib.util.spec_from_file_location("audit_leaf_process_contract", ROOT / "scripts/audit_processes.py")
PROCESSES = importlib.util.module_from_spec(PROCESS_SPEC)
PROCESS_SPEC.loader.exec_module(PROCESSES)
BASH = os.environ.get("P2PKIT_TEST_BASH", "bash")
HEAD = "1234567890abcdef1234567890abcdef12345678"
UDID = "11111111-1111-1111-1111-111111111111"
SLICES = ("ios-arm64", "ios-arm64_x86_64-simulator")
PROJECTS = ("p2p-core", "p2p-transport-lan", "p2p-network-provisioning-android")
EDGES = ("compileAndroidMain", "buildAndroidAbi", "checkAndroidAbi")
PROVENANCE_TASK = ":p2p-transport-lan:verifyP2pKitSharedReleaseXCFrameworkProvenance"
TAIL = ["--no-daemon", "--max-workers=2", "--console=plain"]
INPUTS = (
    "settings.gradle.kts",
    "build.gradle.kts",
    ".github/workflows/ci.yml",
    "scripts/run-release-gate.sh",
    "scripts/tests/check-kotlin-toolchain-policy-test.sh",
    "scripts/tests/check-lock-write-policy-test.sh",
    "scripts/check-android-abi-guard.sh",
    "scripts/check-audit-receipt.py",
    "scripts/run-ios-app.sh",
    "scripts/run-ios-ui-tests.sh",
    "scripts/ios-run-lock.py",
    "samples/iosApp/scripts/check-xcframework.sh",
) + tuple(
    name
    for project in PROJECTS
    for name in (
        f"library/{project}/build.gradle.kts",
        f"library/{project}/api/android/{project}.api",
    )
)


# This backend deliberately cannot start Gradle or native Apple tools. The shell
# front ends exec it so even `sh ./gradlew` preserves the lock worker PID.
BACKEND = r'''
import json
import os
from pathlib import Path
import re
import sys

root = Path(os.environ["LEAF_FAKE_REPO"])
events = Path(os.environ["LEAF_FAKE_EVENTS"])
kind, arguments = sys.argv[1], sys.argv[2:]
event = {"kind": kind, "actualCwd": os.getcwd(), "pid": os.getpid()}

def record():
    with events.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(event, ensure_ascii=False) + "\n")

def assert_mutation_lock():
    lock = Path(os.environ["LEAF_FAKE_EXPECT_LOCK"])
    owner = int((lock / "pid").read_text(encoding="ascii"))
    worker = int((lock / "worker").read_text(encoding="ascii"))
    expected_owner = int(os.environ["LEAF_FAKE_EXPECT_OWNER"])
    assert owner == expected_owner, (owner, expected_owner)
    assert worker == os.getpid(), (worker, os.getpid())
    os.kill(owner, 0)
    event["lock"] = {"owner": owner, "worker": worker, "path": str(lock)}

if kind == "native":
    tool, arguments = arguments[0], arguments[1:]
    event.update(tool=tool, argv=arguments)
    if tool == "git":
        assert arguments == ["rev-parse", "HEAD"], arguments
        record()
        print(os.environ["LEAF_FAKE_HEAD"])
        raise SystemExit(int(os.environ.get("LEAF_FAKE_GIT_STATUS", "0")))
    if tool == "xcrun":
        assert arguments[0] == "simctl", arguments
        if arguments[1:] == ["list", "devices", "available"]:
            record()
            print("    iPhone 17 (11111111-1111-1111-1111-111111111111) (Shutdown)")
            raise SystemExit(0)
        assert arguments == ["simctl", "bootstatus",
                             "11111111-1111-1111-1111-111111111111", "-b"], arguments
    else:
        assert tool in ("xcodegen", "xcodebuild"), tool
    assert_mutation_lock()
    record()
    if tool == "xcodebuild":
        raise SystemExit(int(os.environ.get("LEAF_FAKE_PRODUCT_STATUS", "0")))
    print("synthetic native boundary, not an Apple execution")
    raise SystemExit(0)

options = {}
if kind == "executor":
    assert "--" in arguments, arguments
    boundary = arguments.index("--")
    prefix, arguments = arguments[:boundary], arguments[boundary + 1:]
    assert len(prefix) % 2 == 0, prefix
    for index in range(0, len(prefix), 2):
        key, value = prefix[index:index + 2]
        assert key in ("--cwd", "--wrapper", "--purpose", "--receipt"), key
        assert key not in options, key
        options[key] = value
    assert set(options) >= {"--cwd", "--wrapper", "--purpose"}, options
    assert Path(options["--cwd"]).resolve() == root.resolve(), options
    assert Path(options["--wrapper"]).resolve() == (root / "gradlew").resolve(), options
    event.update(options=options, purpose=options["--purpose"])
else:
    assert kind == "wrapper", kind
event["argv"] = arguments

if kind == "wrapper" and arguments == ["--stop"]:
    event["stop"] = True
    record()
    print("SYNTHETIC WRAPPER STOP OUTPUT MUST NEVER BE A TASK GRAPH")
    raise SystemExit(0)

entrypoint = os.environ["LEAF_FAKE_ENTRYPOINT"]
status, output = 0, ""
if entrypoint == "lock":
    assert arguments[-3:] == ["--no-daemon", "--max-workers=2", "--console=plain"], arguments
    selector = arguments[:-3]
    if selector == ["rALl", "--dry-run"]:
        label = "abbreviated"
    elif selector[:3] == ["indirectLockRefresh", "--dry-run", "--init-script"]:
        assert len(selector) == 4, selector
        event["initScript"] = Path(selector[3]).read_text(encoding="utf-8")
        assert 'dependsOn("resolveAndLockAll")' in event["initScript"]
        label = "indirect"
    elif selector == ["help", "--write-locks", "--dry-run"]:
        label = "ordinary-write"
    elif selector == ["rALl", "--write-locks", "--dry-run", "--configure-on-demand"]:
        label = "configure-on-demand-write"
    else:
        assert selector == ["rALl", "--write-locks", "--dry-run"], selector
        label = "authorized"
    event["label"] = label
    if kind == "executor":
        assert options["--purpose"] == "lock-policy-" + label, options
    diagnostics = {
        "abbreviated": "resolveAndLockAll must be invoked with --write-locks",
        "indirect": "resolveAndLockAll must be invoked with --write-locks",
        "ordinary-write": "--write-locks may only be used with resolveAndLockAll",
        "configure-on-demand-write": "--write-locks requires --no-configure-on-demand",
    }
    mutation = os.environ.get("LEAF_FAKE_POLICY_MUTATION", "")
    if label != "authorized":
        status = 1
        diagnostic = diagnostics[label]
        if mutation == "wrong-diagnostic-" + label:
            diagnostic = "synthetic unrelated product failure"
        output = "> Task :buildSrc:compileJava\n" + diagnostic + "\n"
        if mutation == "project-task-" + label:
            output += "> Task :p2p-core:check\n"
    else:
        modules = re.findall(r'^include\(":([^"\n]+)"\)$',
                             (root / "settings.gradle.kts").read_text(encoding="utf-8"), re.M)
        assert len(modules) > 3 and "iosApp" in modules, modules
        output = ":resolveAndLockAll SKIPPED\n"
        output += "".join(":" + module + ":check SKIPPED\n"
                          for module in modules if module != "iosApp")
        if mutation == "missing-authorized-task":
            output = output.replace(":resolveAndLockAll SKIPPED\n", "")
        if mutation == "missing-module-check":
            output = output.replace(":p2p-core:check SKIPPED\n", "")
        if mutation == "changed-lockfile":
            (root / "fixture.gradle.lockfile").write_text("unexpected mutation\n", encoding="utf-8")
elif entrypoint == "abi":
    expected = [":p2p-core:check", ":p2p-transport-lan:check",
                ":p2p-network-provisioning-android:check", "--dependency-verification=strict",
                "--dry-run", "--console=plain"]
    assert arguments == expected, arguments
    if kind == "executor":
        assert options["--purpose"] == "android-abi-graph", options
    for module in ("p2p-core", "p2p-transport-lan", "p2p-network-provisioning-android"):
        for task in ("compileAndroidMain", "buildAndroidAbi", "checkAndroidAbi"):
            line = ":" + module + ":" + task + " SKIPPED\n"
            if line.rstrip("\n") != os.environ.get("LEAF_FAKE_MISSING_EDGE"):
                output += line
    status = int(os.environ.get("LEAF_FAKE_PRODUCT_STATUS", "0"))
else:
    assert entrypoint in ("provenance", "bootstrap"), entrypoint
    expected = [":p2p-transport-lan:verifyP2pKitSharedReleaseXCFrameworkProvenance"]
    if entrypoint == "provenance":
        expected.append("-q")
    expected.append("--console=plain")
    assert arguments == expected, arguments
    if kind == "executor":
        assert options["--purpose"] == ("xcode-provenance" if entrypoint == "provenance"
                                         else "ios-bootstrap"), options
    if entrypoint == "bootstrap":
        assert_mutation_lock()
        selected = os.environ.get("LEAF_FAKE_SLICES", "ios-arm64,ios-arm64_x86_64-simulator")
        for slice_name in filter(None, selected.split(",")):
            binary = (root / "library/p2p-transport-lan/build/XCFrameworks/release/"
                      "P2pKitShared.xcframework" / slice_name / "P2pKitShared.framework/P2pKitShared")
            binary.parent.mkdir(parents=True, exist_ok=True)
            binary.write_bytes(b"synthetic slice, never a native artifact")
    output = "synthetic verification boundary, not a Gradle execution\n"
    status = int(os.environ.get("LEAF_FAKE_PRODUCT_STATUS", "0"))

event.update(productExitCode=status, productStdout=output)
final_status = status
if kind == "executor" and "--receipt" in options:
    path = Path(options["--receipt"])
    assert not path.exists() and not path.is_symlink(), path
    if entrypoint == "lock":
        event["workDirectory"] = str(path.parent)
        sentinel = path.parent / "adapter-owned-sentinel.txt"
        sentinel_bytes = os.environ["LEAF_FAKE_WORK_SENTINEL"].encode("utf-8")
        if sentinel.exists():
            assert sentinel.read_bytes() == sentinel_bytes, sentinel
        else:
            with sentinel.open("xb") as stream:
                stream.write(sentinel_bytes)
    source = {"commit": "1" * 40, "tree": "2" * 40,
              "status": "", "diffSha256": "3" * 64}
    receipt = {"schema": 1, "id": "synthetic-call-" + str(os.getpid()),
               "purpose": options["--purpose"], "requestedArgv": arguments,
               "cwd": str(root.resolve()), "wrapper": str((root / "gradlew").resolve()),
               "sourceBefore": dict(source), "sourceAfter": dict(source),
               "productExitCode": status, "stopExitCode": 0, "finalExitCode": status,
               "sourceUnchanged": True, "ownedSurvivors": [], "errors": []}
    mode = os.environ.get("LEAF_FAKE_RECEIPT_MODE", "valid")
    target = os.environ.get("LEAF_FAKE_RECEIPT_LABEL")
    if target and event.get("label") != target:
        mode = "valid"
    if mode == "infrastructure-125":
        final_status = receipt["finalExitCode"] = 125
    elif mode == "stop-failed":
        receipt["stopExitCode"] = 9
    elif mode == "stop-missing":
        receipt.pop("stopExitCode")
    elif mode == "stop-unknown":
        receipt["stopExitCode"] = None
    elif mode == "cancelled-no-receipt":
        # Synthetic controller result only; no real worker/signal acceptance.
        final_status = receipt["finalExitCode"] = 130
    elif mode == "stale-purpose":
        receipt["purpose"] = "lock-policy-another-invocation"
    elif mode == "source-changed":
        receipt["sourceAfter"]["tree"] = "4" * 40
        receipt["sourceUnchanged"] = False
    elif mode == "owned-survivor":
        receipt["ownedSurvivors"] = [{"pid": 42}]
    elif mode == "cleanup-error":
        receipt["errors"] = ["synthetic cleanup failure"]
    elif mode == "argv-changed":
        receipt["requestedArgv"] = ["help"]
    elif mode == "product-code-changed":
        receipt["productExitCode"] = 0
    elif mode == "final-code-changed":
        receipt["finalExitCode"] = 0
    else:
        assert mode in ("valid", "missing", "malformed"), mode
    if mode == "malformed":
        path.write_text("{not a JSON receipt", encoding="utf-8")
    elif mode not in ("missing", "cancelled-no-receipt"):
        path.write_text(json.dumps(receipt), encoding="utf-8")
    event["receipt"] = receipt
    event["receiptMode"] = mode

event["finalExitCode"] = final_status
record()
sys.stdout.write(output)
if kind == "executor":
    print("synthetic executor finalization (not task-graph stdout)", file=sys.stderr)
raise SystemExit(final_status)
'''


class LeafHooksTest(unittest.TestCase):
    def setUp(self):
        temporary_root = Path(tempfile.gettempdir()).resolve()
        if temporary_root == ROOT or ROOT in temporary_root.parents:
            self.fail("fixture TMPDIR must be outside the source checkout")
        self.temporary = tempfile.TemporaryDirectory(prefix="p2pkit-leaf-hooks-", dir=temporary_root)
        self.addCleanup(self.temporary.cleanup)
        self.work = Path(self.temporary.name)
        self.repo = self.work / "checkout with spaces Ω"
        self.repo.mkdir()
        for name in INPUTS:
            destination = self.repo / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / name, destination)
        self.project = self.repo / "samples/iosApp"
        self.lock = self.project / "build/.ios-launch.lock"
        self.release = self.repo / "library/p2p-transport-lan/build/XCFrameworks/release"
        self.events_file = self.work / "calls.jsonl"
        backend = self.work / "recordable boundary Ω.py"
        backend.write_text(BACKEND, encoding="utf-8")
        fake_bin = self.work / "fake tools Ω"
        fake_bin.mkdir()
        self.executor = fake_bin / "leaf executor Ω"
        self.shell_boundary(self.executor, "executor")
        self.shell_boundary(self.repo / "gradlew", "wrapper")
        for tool in ("git", "xcrun", "xcodegen", "xcodebuild"):
            self.shell_boundary(fake_bin / tool, "native " + tool)
        self.env = dict(os.environ)
        for name in ("P2PKIT_GRADLE_EXECUTOR", "P2PKIT_XCODE_JOBS", "IOS_RUN_DIR",
                     "KEEP_IOS_RUN_ARTIFACTS", "SIM_NAME", "SIM_UDID", "BASH_ENV"):
            self.env.pop(name, None)
        tmp = self.work / "temporary work Ω"
        tmp.mkdir()
        self.env.update(
            LEAF_FAKE_BACKEND=str(backend), LEAF_FAKE_REPO=str(self.repo),
            LEAF_FAKE_EVENTS=str(self.events_file), LEAF_FAKE_HEAD=HEAD,
            LEAF_FAKE_WORK_SENTINEL="synthetic worker inputs must survive until outer finalization\n",
            PATH=str(fake_bin) + os.pathsep + os.environ["PATH"], TMPDIR=str(tmp),
            SIM_UDID=UDID,
        )
        self.audit_state = self.work / "initialized audit state Ω"
        for child in ("work", "evidence", "gradle-home"):
            (self.audit_state / child).mkdir(parents=True)
        self.audit_context = {
            "schema": 1, "id": uuid.uuid4().hex, "root": str(self.repo.resolve()), "host": "linux-x64",
            "gradleHome": str(self.audit_state / "gradle-home"), "expectedCommit": "1" * 40,
            "tree": "2" * 40, "source": {"commit": "1" * 40, "tree": "2" * 40,
                                         "status": "", "diffSha256": hashlib.sha256(b"").hexdigest()},
        }
        (self.audit_state / "context.json").write_text(json.dumps(self.audit_context), encoding="utf-8")
        # Preserve every real ancestor domain. An independent raw STATE/HOME
        # overwrite would make hosted POSIX discovery reject our own children.
        # This is a fixture namespace, not native executor admission evidence.
        self.ancestor_domains = PROCESSES.ownership_domains(
            self.env.get(PROCESSES.CHAIN_ENV, ""), self.env.get(PROCESSES.DOMAINS_ENV, ""))
        self.env = PROCESSES.ownership_environment(
            self.env, self.audit_context["id"], uuid.uuid4().hex, str(self.audit_state),
            self.audit_context["gradleHome"], allow_new_context=True)
        self.lockfiles = [self.repo / "fixture.gradle.lockfile",
                          self.repo / "library/fixture/gradle.lockfile"]
        for path in self.lockfiles:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"synthetic lock baseline\n")

    def shell_boundary(self, path, kind):
        path.write_text(
            "#!/bin/sh\nexec " + shlex.quote(sys.executable)
            + ' "$LEAF_FAKE_BACKEND" ' + kind + ' "$@"\n', encoding="utf-8")
        path.chmod(0o755)

    def invoke(self, arguments, entrypoint="", adapter=False, input_text=None, **overrides):
        env = dict(self.env, LEAF_FAKE_ENTRYPOINT=entrypoint)
        if adapter:
            env["P2PKIT_GRADLE_EXECUTOR"] = str(self.executor)
        env.update(overrides)
        domains = PROCESSES.ownership_domains(env[PROCESSES.CHAIN_ENV], env[PROCESSES.DOMAINS_ENV])
        self.assertEqual(self.ancestor_domains, domains[:-1], "Do not strip or rewrite actual parent ownership")
        self.assertEqual(domains[-1]["job"], env[PROCESSES.JOB_ENV])
        self.assertEqual(domains[-1]["state"], env[PROCESSES.STATE_ENV])
        self.assertEqual(domains[-1]["home"], env["GRADLE_USER_HOME"])
        process = subprocess.Popen(
            arguments, cwd=self.repo, env=env, stdin=subprocess.PIPE if input_text is not None else None,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True, encoding="utf-8", start_new_session=True)
        try:
            stdout, stderr = process.communicate(input=input_text, timeout=30)
        except subprocess.TimeoutExpired:
            # Only this invocation's synthetic process group is owned here.
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            stdout, stderr = process.communicate(timeout=5)
            self.fail("synthetic entrypoint timed out:\n" + stdout + stderr)
        return subprocess.CompletedProcess(arguments, process.returncode, stdout, stderr)

    def assert_status(self, result, expected=0):
        self.assertEqual(expected, result.returncode, result.stdout + result.stderr)
        self.assertNotIn("unbound variable", result.stdout + result.stderr)

    def events(self):
        if not self.events_file.exists():
            return []
        return [json.loads(line) for line in self.events_file.read_text(encoding="utf-8").splitlines()]

    def reset_events(self):
        self.events_file.unlink(missing_ok=True)

    def leaves(self):
        return [event for event in self.events()
                if event["kind"] in ("wrapper", "executor") and not event.get("stop")]

    def lock_policy(self, adapter=False, **overrides):
        return self.invoke([BASH, "scripts/tests/check-lock-write-policy-test.sh"],
                           entrypoint="lock", adapter=adapter, **overrides)

    def retained_lock_work(self, result):
        matches = re.findall(r"^AUDIT_LOCK_POLICY_WORK=(.+)$", result.stderr, re.M)
        self.assertEqual(1, len(matches), result.stdout + result.stderr)
        work = Path(matches[0])
        self.assertEqual(self.audit_state / "work", work.parent)
        self.assertTrue(work.name.startswith("lock-policy."))
        self.assertTrue(work.is_dir(), "Inspect actual retained WORK, not just a fake event snapshot")
        self.assertFalse(work.is_symlink())
        owner = json.loads((work / "ownership.json").read_text(encoding="utf-8"))
        self.assertEqual(1, owner["schema"])
        self.assertEqual("lock-policy-work", owner["purpose"])
        self.assertEqual(self.audit_context["id"], owner["jobId"])
        self.assertEqual(self.audit_context["host"], owner["host"])
        self.assertEqual(str(self.repo.resolve()), owner["root"])
        self.assertEqual(str(self.audit_state), owner["stateDirectory"])
        self.assertEqual(str(work), owner["workDirectory"])
        self.assertEqual(hashlib.sha256((self.audit_state / "context.json").read_bytes()).hexdigest(),
                         owner["contextSha256"])
        for path, key in ((self.audit_state, "stateIdentity"), (work.parent, "workParentIdentity")):
            info = path.stat()
            self.assertEqual({"device": info.st_dev, "inode": info.st_ino}, owner[key])
        self.assertEqual("run-audit-host.py", owner["cleanupOwner"])
        self.assertIs(owner["preserveUntilOuterFinalization"], True)
        self.assertEqual("NOT_ASSESSED", owner["leafFinalization"])
        return work

    def assert_lock_snapshot(self, path):
        expected = "".join(hashlib.sha256(lock.read_bytes()).hexdigest() + "  " + str(lock) + "\n"
                           for lock in sorted(self.lockfiles))
        self.assertEqual(expected.encode("utf-8"), path.read_bytes())

    def audit_allocator(self, state):
        # Helper-only rejection control: execute the maintained here-doc bytes,
        # passing the rejected state as its real positional input. Do not put an
        # empty/invalid STATE value into a spawned process's ownership domain.
        script = self.repo / "scripts/tests/check-lock-write-policy-test.sh"
        raw = script.read_bytes()
        source = raw.decode("utf-8")
        marker = "<<'PYTHON'\n"
        self.assertEqual(1, source.count(marker), "The actual allocator extraction boundary changed")
        prefix, _, rest = source.partition(marker)
        body, delimiter, _ = rest.partition("\nPYTHON\n")
        self.assertEqual("\nPYTHON\n", delimiter)
        body += "\n"
        evidence = self.audit_state / "evidence"
        source_copy = evidence / "allocator-source.txt"
        metadata = {"sourceFile": "scripts/tests/check-lock-write-policy-test.sh",
                    "sourceSha256": hashlib.sha256(raw).hexdigest(), "firstLine": prefix.count("\n") + 2,
                    "lineCount": body.count("\n"), "sliceSha256": hashlib.sha256(body.encode("utf-8")).hexdigest(),
                    "scope": "exact helper positional-input rejection, not full shell/native execution"}
        if source_copy.exists():
            self.assertEqual(body.encode("utf-8"), source_copy.read_bytes())
        else:
            source_copy.write_bytes(body.encode("utf-8"))
            (evidence / "allocator-source.json").write_text(json.dumps(metadata) + "\n", encoding="utf-8")
            # The source-bound test log retains the exact slice/hash reference
            # after assertions finish and this fixture's temporary tree is retired.
            print("AUDIT_LOCK_ALLOCATOR_FIXTURE=" + json.dumps(metadata), file=sys.stderr)
        return self.invoke([sys.executable, "-", str(self.repo), state], input_text=body)

    def abi(self, adapter=False, **overrides):
        return self.invoke([BASH, "scripts/check-android-abi-guard.sh"],
                           entrypoint="abi", adapter=adapter, **overrides)

    def seed_framework(self, state="clean"):
        for slice_name in SLICES:
            binary = self.binary(slice_name)
            binary.parent.mkdir(parents=True, exist_ok=True)
            binary.write_bytes(b"synthetic fixture, not an XCFramework binary")
        for name, value in (("BUILD_COMMIT.txt", HEAD), ("BUILD_SOURCE_STATE.txt", state),
                            ("BUILD_INPUTS_SHA256.txt", "a" * 64)):
            (self.release / name).write_text(value + "\n", encoding="ascii")

    def binary(self, slice_name):
        return self.release / "P2pKitShared.xcframework" / slice_name / "P2pKitShared.framework/P2pKitShared"

    def provenance(self, adapter=False, **overrides):
        return self.invoke(["sh", "samples/iosApp/scripts/check-xcframework.sh"],
                           entrypoint="provenance", adapter=adapter,
                           SRCROOT=str(self.project), **overrides)

    def locked_call(self, body, arguments=(), entrypoint="", adapter=False, **overrides):
        script = '''source "$1"
shift
initialize_ios_run_cleanup "$LEAF_FAKE_REPO/samples/iosApp" ios-run
acquire_ios_run_lock "$IOS_LAUNCH_LOCK"
IOS_LAUNCH_OWNS_LOCK=1
export LEAF_FAKE_EXPECT_LOCK="$IOS_LAUNCH_LOCK" LEAF_FAKE_EXPECT_OWNER="$$"
''' + body
        result = self.invoke([BASH, "-c", script, "audit-leaf-fixture",
                              str(self.repo / "scripts/run-ios-app.sh"), *arguments],
                             entrypoint=entrypoint, adapter=adapter, **overrides)
        self.assertFalse(self.lock.exists(), result.stdout + result.stderr)
        self.assertTrue(Path(str(self.lock) + ".guard").is_file(), result.stdout + result.stderr)
        return result

    def bootstrap(self, adapter=False, repeat=False, **overrides):
        body = 'ensure_ios_xcframework_present "$LEAF_FAKE_REPO"\n'
        if repeat:
            body += 'ensure_ios_xcframework_present "$LEAF_FAKE_REPO"\n'
        body += 'echo "BOOTSTRAP-RETURNED-SUCCESS"\n'
        return self.locked_call(body, entrypoint="bootstrap", adapter=adapter, **overrides)

    def assert_worker_lock(self, event):
        self.assertIn("lock", event)
        self.assertEqual(str(self.lock), event["lock"]["path"])
        self.assertGreater(event["lock"]["owner"], 1)
        self.assertEqual(event["pid"], event["lock"]["worker"])
        self.assertNotEqual(event["lock"]["owner"], event["pid"])

    def test_lock_policy_default_and_adapter_preserve_all_five_leaves(self):
        expected_labels = ["abbreviated", "indirect", "ordinary-write",
                           "configure-on-demand-write", "authorized"]
        baseline = {path: path.read_bytes() for path in self.lockfiles}
        vectors = []
        for adapter in (False, True):
            with self.subTest(adapter=adapter):
                self.reset_events()
                result = self.lock_policy(adapter=adapter)
                self.assert_status(result)
                self.assertIn("RESULT: PASS", result.stdout)
                leaves = self.leaves()
                self.assertEqual(expected_labels, [leaf["label"] for leaf in leaves])
                self.assertEqual([1, 1, 1, 1, 0], [leaf["productExitCode"] for leaf in leaves])
                self.assertEqual(["executor" if adapter else "wrapper"] * 5,
                                 [leaf["kind"] for leaf in leaves])
                self.assertEqual(0 if adapter else 5,
                                 sum(bool(event.get("stop")) for event in self.events()))
                normalized = []
                for leaf in leaves:
                    self.assertEqual(str(self.repo), leaf["actualCwd"])
                    self.assertEqual(TAIL, leaf["argv"][-3:])
                    argv = list(leaf["argv"])
                    if leaf["label"] == "indirect":
                        init = Path(argv[argv.index("--init-script") + 1])
                        self.assertIn(" ", str(init))
                        self.assertIn("Ω", str(init))
                        self.assertIn('tasks.register("indirectLockRefresh")', leaf["initScript"])
                        argv[argv.index("--init-script") + 1] = "<owned-init-script>"
                    normalized.append(argv)
                    if adapter:
                        receipt = leaf["receipt"]
                        self.assertEqual("lock-policy-" + leaf["label"], receipt["purpose"])
                        self.assertEqual(leaf["argv"], receipt["requestedArgv"])
                        self.assertEqual(0, receipt["stopExitCode"])
                vectors.append(normalized)
                self.assertIn("--configure-on-demand", leaves[3]["argv"])
                self.assertNotIn("--no-configure-on-demand", leaves[3]["argv"])
                self.assertNotIn(":iosApp:check SKIPPED", leaves[-1]["productStdout"])
                modules = re.findall(r'^include\(":([^"\n]+)"\)$',
                                     (self.repo / "settings.gradle.kts").read_text(), re.M)
                for module in modules:
                    if module != "iosApp":
                        self.assertIn(f":{module}:check SKIPPED", leaves[-1]["productStdout"])
                self.assertEqual(baseline, {path: path.read_bytes() for path in self.lockfiles})
        self.assertEqual(vectors[0], vectors[1])

    def test_all_four_policy_diagnostics_and_preexecution_rejections_remain_required(self):
        labels = ["abbreviated", "indirect", "ordinary-write", "configure-on-demand-write"]
        for index, label in enumerate(labels):
            for mutation, expected in (("wrong-diagnostic-", "did not report"),
                                       ("project-task-", "executed a project task")):
                with self.subTest(label=label, mutation=mutation):
                    self.reset_events()
                    result = self.lock_policy(adapter=True, LEAF_FAKE_POLICY_MUTATION=mutation + label)
                    self.assert_status(result, 1)
                    self.assertIn(expected, result.stderr)
                    self.assertNotIn("RESULT: PASS", result.stdout)
                    self.assertEqual(index + 1, len(self.leaves()))

    def test_authorized_graph_and_unchanged_locks_remain_required(self):
        for mutation, expected in (
            ("missing-authorized-task", "did not select resolveAndLockAll"),
            ("missing-module-check", "lock refresh omitted :p2p-core:check"),
            ("changed-lockfile", "modified a dependency lockfile"),
        ):
            with self.subTest(mutation=mutation):
                self.reset_events()
                result = self.lock_policy(adapter=True, LEAF_FAKE_POLICY_MUTATION=mutation)
                self.assert_status(result, 1)
                self.assertIn(expected, result.stderr)
                self.assertEqual(5, len(self.leaves()))
                self.assertNotIn("RESULT: PASS", result.stdout)

    def test_expected_red_never_hides_failed_or_unbound_executor_receipts(self):
        for mode in ("infrastructure-125", "stop-failed", "stop-missing", "stop-unknown", "missing", "malformed",
                     "cancelled-no-receipt", "stale-purpose",
                     "source-changed", "owned-survivor", "cleanup-error", "argv-changed",
                     "product-code-changed", "final-code-changed"):
            with self.subTest(mode=mode):
                self.reset_events()
                result = self.lock_policy(adapter=True, LEAF_FAKE_RECEIPT_MODE=mode)
                self.assert_status(result, 1)
                self.assertIn("audit leaf finalization failed", result.stderr)
                self.assertIn("resolveAndLockAll must be invoked with --write-locks", result.stderr)
                self.assertNotIn("RESULT: PASS", result.stdout)
                self.assertEqual(1, len(self.leaves()), self.events())
                self.assertTrue(all(event["kind"] == "executor" for event in self.events()))

    def test_audited_success_retains_inputs_logs_receipts_and_snapshots_for_outer_finalizer(self):
        context_before = (self.audit_state / "context.json").read_bytes()
        # A usable ambient TMPDIR is not part of opt-in workspace admission.
        # Deliberately make it a regular foreign file, not an allocation root.
        unrelated = self.work / "foreign tmp setting Ω"
        unrelated.write_bytes(b"not an owned disposable output")
        result = self.lock_policy(adapter=True, TMPDIR=str(unrelated))
        self.assert_status(result)
        self.assertIn("RESULT: PASS", result.stdout)
        work = self.retained_lock_work(result)
        self.assert_lock_snapshot(work / "locks-before.txt")
        self.assert_lock_snapshot(work / "locks-after.txt")
        self.assertFalse((work / "locks-before").exists())
        self.assertFalse((work / "locks-after").exists())
        leaves = self.leaves()
        self.assertEqual(5, len(leaves))
        self.assertEqual([1, 1, 1, 1, 0], [leaf["productExitCode"] for leaf in leaves])
        for leaf in leaves:
            self.assertEqual(str(work), leaf["workDirectory"])
            log = work / (leaf["label"] + ".log")
            self.assertIn(leaf["productStdout"].encode("utf-8"), log.read_bytes())
            self.assertIn(b"synthetic executor finalization", log.read_bytes())
            receipt = work / (leaf["label"] + ".log.receipt.json")
            self.assertEqual(json.dumps(leaf["receipt"]).encode("utf-8"), receipt.read_bytes())
        self.assertEqual(leaves[1]["initScript"].encode("utf-8"), (work / "indirect.init.gradle.kts").read_bytes())
        self.assertEqual(self.env["LEAF_FAKE_WORK_SENTINEL"].encode("utf-8"),
                         (work / "adapter-owned-sentinel.txt").read_bytes())
        self.assertFalse((work / "gradle-stop.log").exists(), "Only the real adapter may stop its owned leaf")
        self.assertTrue(all(event["kind"] == "executor" for event in self.events()))
        self.assertEqual(context_before, (self.audit_state / "context.json").read_bytes())
        self.assertEqual(b"not an owned disposable output", unrelated.read_bytes())

    def test_unknown_finalization_keeps_actual_init_log_optional_receipt_and_sentinel(self):
        context_before = (self.audit_state / "context.json").read_bytes()
        unrelated = self.audit_state / "work/unrelated-fixture/sentinel.txt"
        unrelated.parent.mkdir()
        unrelated.write_bytes(b"outside this leaf's work directory")
        retained = []
        for mode in ("stop-failed", "stop-missing", "stop-unknown", "missing", "malformed", "owned-survivor",
                     "infrastructure-125", "cancelled-no-receipt"):
            with self.subTest(mode=mode):
                self.reset_events()
                result = self.lock_policy(adapter=True, LEAF_FAKE_RECEIPT_MODE=mode,
                                          LEAF_FAKE_RECEIPT_LABEL="indirect")
                self.assert_status(result, 1)
                self.assertIn("audit leaf finalization failed for lock-policy-indirect", result.stderr)
                self.assertNotIn("RESULT: PASS", result.stdout)
                leaves = self.leaves()
                self.assertEqual(["abbreviated", "indirect"], [leaf["label"] for leaf in leaves])
                self.assertEqual([1, 1], [leaf["productExitCode"] for leaf in leaves])
                expected = 125 if mode == "infrastructure-125" else 130 if mode == "cancelled-no-receipt" else 1
                self.assertEqual(expected, leaves[1]["finalExitCode"])
                observed_work = Path(leaves[1]["options"]["--receipt"]).parent
                # This checks the defect itself before the new metadata/output
                # contract: an unconditional EXIT cleanup has already erased
                # these real fixture files, even if fake event snapshots exist.
                for name in ("adapter-owned-sentinel.txt", "indirect.init.gradle.kts", "abbreviated.log",
                             "indirect.log", "abbreviated.log.receipt.json"):
                    self.assertTrue((observed_work / name).is_file(),
                                    "Unknown leaf finalization must not erase actual WORK file: " + name)
                work = self.retained_lock_work(result)
                self.assertEqual(observed_work, work)
                self.assertNotIn(work, retained, "A later leaf test must not reuse prior failed WORK")
                retained.append(work)
                self.assertEqual(str(work), leaves[1]["workDirectory"])
                self.assertEqual(leaves[1]["initScript"].encode("utf-8"),
                                 (work / "indirect.init.gradle.kts").read_bytes())
                for leaf in leaves:
                    log = work / (leaf["label"] + ".log")
                    self.assertIn(leaf["productStdout"].encode("utf-8"), log.read_bytes())
                    self.assertIn(b"synthetic executor finalization", log.read_bytes())
                first = work / "abbreviated.log.receipt.json"
                self.assertEqual(json.dumps(leaves[0]["receipt"]).encode("utf-8"), first.read_bytes())
                failed = work / "indirect.log.receipt.json"
                if mode in ("missing", "cancelled-no-receipt"):
                    self.assertFalse(failed.exists(), "Missing evidence must remain missing, not be invented")
                elif mode == "malformed":
                    self.assertEqual(b"{not a JSON receipt", failed.read_bytes())
                else:
                    self.assertEqual(json.dumps(leaves[1]["receipt"]).encode("utf-8"), failed.read_bytes())
                self.assertEqual(self.env["LEAF_FAKE_WORK_SENTINEL"].encode("utf-8"),
                                 (work / "adapter-owned-sentinel.txt").read_bytes())
                self.assert_lock_snapshot(work / "locks-before.txt")
                self.assertFalse((work / "locks-after.txt").exists())
                self.assertFalse((work / "gradle-stop.log").exists())
                self.assertTrue(all(event["kind"] == "executor" for event in self.events()))
                self.assertTrue(all(path.is_dir() for path in retained))
                self.assertEqual(context_before, (self.audit_state / "context.json").read_bytes())
                self.assertEqual(b"outside this leaf's work directory", unrelated.read_bytes())

    def test_default_lock_policy_keeps_original_temp_cleanup_on_success_and_failure(self):
        for mutation in ("", "wrong-diagnostic-indirect"):
            with self.subTest(mutation=mutation):
                self.reset_events()
                result = self.lock_policy(LEAF_FAKE_POLICY_MUTATION=mutation)
                self.assert_status(result, 1 if mutation else 0)
                self.assertNotIn("AUDIT_LOCK_POLICY_WORK=", result.stderr)
                leaves = self.leaves()
                indirect = next(leaf for leaf in leaves if leaf["label"] == "indirect")
                init = Path(indirect["argv"][indirect["argv"].index("--init-script") + 1])
                self.assertEqual(Path(self.env["TMPDIR"]), init.parent.parent)
                self.assertTrue(init.parent.name.startswith("p2pkit-lock-policy-test."))
                self.assertFalse(init.exists())
                self.assertFalse(init.parent.exists(), "Unopted EXIT cleanup must remain unchanged")
                self.assertEqual([], list((self.audit_state / "work").iterdir()))
                self.assertEqual(len(leaves), sum(bool(event.get("stop")) for event in self.events()))

    def test_actual_allocator_rejects_missing_relative_or_source_local_state_without_tmp_fallback(self):
        for state in ("", "relative-state", str(self.work / "missing-state"), str(self.repo),
                      str(self.repo / "state")):
            with self.subTest(state=state):
                self.reset_events()
                result = self.audit_allocator(state)
                self.assert_status(result, 1)
                self.assertIn("cannot allocate retained audit lock-policy work", result.stderr)
                self.assertNotIn("AUDIT_LOCK_POLICY_WORK=", result.stderr)
                self.assertEqual([], self.events())
                self.assertEqual([], list((self.audit_state / "work").iterdir()))
                self.assertEqual([], list(Path(self.env["TMPDIR"]).glob("p2pkit-lock-policy-test.*")))

    def test_audit_work_context_is_bounded_strict_and_bound_without_rewriting_inputs(self):
        context = self.audit_state / "context.json"
        shapes = [b"{malformed", b"[]", b'{"schema":1,"schema":1}', b'{"value":NaN}', b"x" * (4 * 1024 * 1024 + 1)]
        for key, value in (("schema", True), ("id", "a" * 31), ("root", str(self.work)),
                           ("gradleHome", str(self.work / "foreign-home")), ("host", None)):
            record = copy.deepcopy(self.audit_context)
            record[key] = value
            shapes.append(json.dumps(record).encode("utf-8"))
        for raw in shapes:
            with self.subTest(shape=raw[:80]):
                self.reset_events()
                context.write_bytes(raw)
                result = self.lock_policy(adapter=True)
                self.assert_status(result, 1)
                self.assertIn("audit lock-policy work allocation failed", result.stderr)
                self.assertNotIn("AUDIT_LOCK_POLICY_WORK=", result.stderr)
                self.assertEqual([], self.events())
                self.assertEqual(raw, context.read_bytes())
                self.assertEqual([], list((self.audit_state / "work").iterdir()))

    def test_audit_work_never_creates_missing_roots_or_follows_symlinked_owners(self):
        work = self.audit_state / "work"
        preserved = self.audit_state / "preserved-work"
        work.rename(preserved)
        result = self.lock_policy(adapter=True)
        self.assert_status(result, 1)
        self.assertEqual([], self.events())
        self.assertFalse(work.exists(), "An uninitialized work root must not be created by this leaf")
        foreign = self.work / "foreign work Ω"
        foreign.mkdir()
        sentinel = foreign / "sentinel.txt"
        sentinel.write_bytes(b"not an admitted work root")
        work.symlink_to(foreign, target_is_directory=True)
        result = self.lock_policy(adapter=True)
        self.assert_status(result, 1)
        self.assertIn("Symlink/reparse audit work path", result.stderr)
        self.assertEqual([], self.events())
        self.assertTrue(work.is_symlink())
        self.assertEqual([sentinel], list(foreign.iterdir()))
        self.assertEqual(b"not an admitted work root", sentinel.read_bytes())
        work.unlink()
        preserved.rename(work)
        alias = self.work / "symlinked audit state Ω"
        alias.symlink_to(self.audit_state, target_is_directory=True)
        result = self.audit_allocator(str(alias))
        self.assert_status(result, 1)
        self.assertIn("Symlink/reparse audit work path", result.stderr)
        self.assertEqual([], self.events())
        self.assertEqual([], list(work.iterdir()))
        self.assertTrue(alias.is_symlink())

    def test_all_gradle_hooks_reject_invalid_opt_in_without_wrapper_fallback(self):
        missing = self.work / "missing adapter Ω"
        nonexec = self.work / "not executable Ω"
        nonexec.write_text("this must not be executed", encoding="utf-8")
        nonexec.chmod(0o644)
        for hook in (self.lock_policy, self.abi, self.provenance, self.bootstrap):
            for invalid in (str(missing), str(nonexec), "relative adapter Ω"):
                with self.subTest(hook=hook.__name__, adapter=invalid):
                    self.reset_events()
                    result = hook(P2PKIT_GRADLE_EXECUTOR=invalid)
                    self.assert_status(result, 1)
                    self.assertIn("P2PKIT_GRADLE_EXECUTOR", result.stdout + result.stderr)
                    self.assertEqual([], self.events(), "invalid opt-in fell back to a wrapper")

    def test_abi_default_and_adapter_preserve_exact_complete_graph_request(self):
        vectors = []
        for adapter in (False, True):
            with self.subTest(adapter=adapter):
                self.reset_events()
                result = self.abi(adapter=adapter)
                self.assert_status(result)
                self.assertIn("RESULT: PASS", result.stdout)
                self.assertEqual(1, len(self.leaves()))
                leaf = self.leaves()[0]
                vectors.append(leaf["argv"])
                self.assertEqual("executor" if adapter else "wrapper", leaf["kind"])
                self.assertEqual({f":{project}:{task} SKIPPED" for project in PROJECTS for task in EDGES},
                                 set(leaf["productStdout"].splitlines()))
                self.assertEqual(1, len(self.events()), "the caller must not issue adapter-owned stops")
                self.assertNotIn("SYNTHETIC WRAPPER STOP", result.stdout + result.stderr)
                if adapter:
                    self.assertIn("synthetic executor finalization", result.stderr)
                    self.assertNotIn("synthetic executor finalization", result.stdout)
        self.assertEqual(vectors[0], vectors[1])

    def test_abi_rejects_each_missing_producer_extractor_and_comparison_edge(self):
        messages = {"compileAndroidMain": "does not own the Android compiler producer",
                    "buildAndroidAbi": "omits Android ABI extraction",
                    "checkAndroidAbi": "omits Android ABI comparison"}
        for project in PROJECTS:
            for task in EDGES:
                with self.subTest(project=project, task=task):
                    self.reset_events()
                    result = self.abi(adapter=True, LEAF_FAKE_MISSING_EDGE=f":{project}:{task} SKIPPED")
                    self.assert_status(result, 1)
                    self.assertIn(f":{project} check {messages[task]}", result.stderr)
                    self.assertNotIn("RESULT: PASS", result.stdout)

    def test_abi_nonzero_product_cannot_pass_even_with_complete_graph(self):
        for adapter in (False, True):
            with self.subTest(adapter=adapter):
                self.reset_events()
                result = self.abi(adapter=adapter, LEAF_FAKE_PRODUCT_STATUS="42")
                self.assert_status(result, 1)
                self.assertIn("task graph dry-run failed", result.stderr)
                self.assertEqual(9, len(self.leaves()[0]["productStdout"].splitlines()))
                self.assertNotIn("RESULT: PASS", result.stdout)

    def test_posix_provenance_default_and_adapter_preserve_verification_and_head(self):
        vectors = []
        for adapter in (False, True):
            for state in ("clean", "dirty"):
                with self.subTest(adapter=adapter, state=state):
                    self.reset_events()
                    self.seed_framework(state)
                    result = self.provenance(adapter=adapter)
                    self.assert_status(result)
                    self.assertIn("XCFramework is fresh", result.stdout)
                    self.assertIn("source state: " + state, result.stdout)
                    self.assertEqual(state == "dirty", "not reproducible from" in result.stdout)
                    self.assertEqual(1, len(self.leaves()))
                    leaf = self.leaves()[0]
                    self.assertEqual("executor" if adapter else "wrapper", leaf["kind"])
                    vectors.append(leaf["argv"])
                    native = [event for event in self.events() if event["kind"] == "native"]
                    self.assertEqual([("git", ["rev-parse", "HEAD"])],
                                     [(event["tool"], event["argv"]) for event in native])
        self.assertTrue(all(vector == [PROVENANCE_TASK, "-q", "--console=plain"] for vector in vectors))

    def test_posix_provenance_requires_each_slice_and_all_three_sidecars(self):
        paths = [self.binary(name) for name in SLICES]
        paths += [self.release / name for name in
                  ("BUILD_COMMIT.txt", "BUILD_SOURCE_STATE.txt", "BUILD_INPUTS_SHA256.txt")]
        for path in paths:
            with self.subTest(missing=path.relative_to(self.repo)):
                self.seed_framework()
                path.unlink()
                result = self.provenance(adapter=True)
                self.assert_status(result, 1)
                self.assertIn("binary missing" if path.name == "P2pKitShared" else "sidecar missing",
                              result.stdout)
                self.assertNotIn("XCFramework is fresh", result.stdout)

    def test_posix_provenance_still_rejects_stale_head_state_and_nonlowercase_sha256(self):
        for filename, value, expected in (
            ("BUILD_COMMIT.txt", "f" * 40, "identity mismatch"),
            ("BUILD_SOURCE_STATE.txt", "unknown", "invalid XCFramework source-state"),
            ("BUILD_SOURCE_STATE.txt", "", "invalid XCFramework source-state"),
            ("BUILD_INPUTS_SHA256.txt", "A" * 64, "invalid XCFramework input fingerprint"),
            ("BUILD_INPUTS_SHA256.txt", "g" * 64, "invalid XCFramework input fingerprint"),
            ("BUILD_INPUTS_SHA256.txt", "a" * 63, "must be a SHA-256 value"),
            ("BUILD_INPUTS_SHA256.txt", "a" * 65, "must be a SHA-256 value"),
            ("BUILD_INPUTS_SHA256.txt", "", "invalid XCFramework input fingerprint"),
        ):
            with self.subTest(filename=filename, value=value):
                self.seed_framework()
                (self.release / filename).write_text(value + "\n", encoding="ascii")
                result = self.provenance(adapter=True)
                self.assert_status(result, 1)
                self.assertIn(expected, result.stdout)
                self.assertNotIn("XCFramework is fresh", result.stdout)

    def test_posix_provenance_propagates_executor_and_git_failures(self):
        self.seed_framework()
        for overrides in ({"LEAF_FAKE_PRODUCT_STATUS": "42"}, {"LEAF_FAKE_GIT_STATUS": "42"}):
            with self.subTest(overrides=overrides):
                result = self.provenance(adapter=True, **overrides)
                self.assert_status(result, 42)
                self.assertNotIn("XCFramework is fresh", result.stdout)

    def test_bootstrap_default_and_adapter_execute_inside_real_mutation_lock_once(self):
        vectors = []
        for adapter in (False, True):
            with self.subTest(adapter=adapter):
                if self.release.exists():
                    shutil.rmtree(self.release)  # Only this test's synthetic temporary products.
                self.reset_events()
                result = self.bootstrap(adapter=adapter, repeat=True)
                self.assert_status(result)
                self.assertEqual(1, len(self.leaves()))
                leaf = self.leaves()[0]
                self.assertEqual("executor" if adapter else "wrapper", leaf["kind"])
                self.assert_worker_lock(leaf)
                vectors.append(leaf["argv"])
                for slice_name in SLICES:
                    self.assertTrue(self.binary(slice_name).is_file())
        self.assertEqual([[PROVENANCE_TASK, "--console=plain"]] * 2, vectors)

    def test_bootstrap_still_requires_both_slices_after_successful_leaf(self):
        for selected in (*SLICES, ""):
            with self.subTest(selected=selected):
                if self.release.exists():
                    shutil.rmtree(self.release)
                self.reset_events()
                result = self.bootstrap(adapter=True, LEAF_FAKE_SLICES=selected)
                self.assert_status(result, 1)
                self.assertIn("without both required slices", result.stderr)
                self.assertNotIn("BOOTSTRAP-RETURNED-SUCCESS", result.stdout)
                self.assert_worker_lock(self.leaves()[0])

    def test_bootstrap_nonzero_executor_cannot_be_hidden_by_created_slices(self):
        result = self.bootstrap(adapter=True, LEAF_FAKE_PRODUCT_STATUS="42")
        self.assert_status(result, 42)
        self.assertNotIn("BOOTSTRAP-RETURNED-SUCCESS", result.stdout)
        for slice_name in SLICES:
            self.assertTrue(self.binary(slice_name).is_file())
        self.assert_worker_lock(self.leaves()[0])

    def test_xcode_jobs_unset_keeps_original_argv_and_opt_in_is_bounded_and_locked(self):
        arguments = ["-project", str(self.project / "project with spaces Ω.xcodeproj"),
                     "-destination", f"platform=iOS Simulator,id={UDID}", "build"]
        for jobs in (None, "1", "2"):
            with self.subTest(jobs=jobs):
                self.reset_events()
                overrides = {} if jobs is None else {"P2PKIT_XCODE_JOBS": jobs}
                result = self.locked_call('run_ios_xcodebuild "$@"\n', arguments, **overrides)
                self.assert_status(result)
                self.assertEqual(1, len(self.events()))
                event = self.events()[0]
                self.assertEqual("xcodebuild", event["tool"])
                self.assertEqual(([] if jobs is None else ["-jobs", jobs]) + arguments, event["argv"])
                self.assert_worker_lock(event)

    def test_xcode_jobs_invalid_values_reject_before_mutation_and_nonzero_is_propagated(self):
        for jobs in ("0", "3", "-1", "all", "1 2", "01"):
            with self.subTest(jobs=jobs):
                self.reset_events()
                result = self.locked_call('run_ios_xcodebuild build\n', P2PKIT_XCODE_JOBS=jobs)
                self.assert_status(result, 2)
                self.assertIn("P2PKIT_XCODE_JOBS must be 1 or 2", result.stderr)
                self.assertEqual([], self.events())
        result = self.locked_call('run_ios_xcodebuild build\n', P2PKIT_XCODE_JOBS="2",
                                  LEAF_FAKE_PRODUCT_STATUS="42")
        self.assert_status(result, 42)
        self.assert_worker_lock(self.events()[0])

    def test_actual_ui_caller_keeps_nonparallel_testing_with_default_and_bounded_jobs(self):
        self.seed_framework()
        # Export the real launcher's owner PID, then exec the real UI entrypoint;
        # exec preserves that PID and no mutation helper is replaced.
        script = '''export LEAF_FAKE_EXPECT_OWNER="$$"
export LEAF_FAKE_EXPECT_LOCK="$LEAF_FAKE_REPO/samples/iosApp/build/.ios-launch.lock"
exec "$1" "$2"
'''
        for jobs in (None, "1", "2"):
            with self.subTest(jobs=jobs):
                self.reset_events()
                overrides = {} if jobs is None else {"P2PKIT_XCODE_JOBS": jobs}
                result = self.invoke([BASH, "-c", script, "audit-ui-fixture", BASH,
                                      str(self.repo / "scripts/run-ios-ui-tests.sh")], **overrides)
                self.assert_status(result)
                self.assertIn("RESULT: PASS", result.stdout)
                self.assertFalse(self.lock.exists())
                xcode = [event for event in self.events() if event.get("tool") == "xcodebuild"]
                self.assertEqual(1, len(xcode))
                actual = xcode[0]["argv"]
                derived = Path(actual[actual.index("-derivedDataPath") + 1])
                self.assertEqual(self.project / "build", derived.parent.parent)
                self.assertTrue(derived.parent.name.startswith("ios-ui-run."))
                self.assertEqual("DerivedData", derived.name)
                expected = ([] if jobs is None else ["-jobs", jobs]) + [
                    "-project", str(self.project / "p2pkit-sample.xcodeproj"),
                    "-scheme", "p2pkit-sample-ui", "-configuration", "Debug",
                    "-sdk", "iphonesimulator", "-destination", f"platform=iOS Simulator,id={UDID}",
                    "-derivedDataPath", str(derived), "-parallel-testing-enabled", "NO", "test",
                ]
                self.assertEqual(expected, actual)
                self.assert_worker_lock(xcode[0])
                for event in self.events():
                    if event.get("tool") in ("xcodegen", "xcodebuild") or "bootstatus" in event.get("argv", []):
                        self.assert_worker_lock(event)

    def good_receipt(self, status=1):
        source = {"commit": "1" * 40, "tree": "2" * 40,
                  "status": "", "diffSha256": "3" * 64}
        return {"schema": 1, "id": "synthetic-receipt-oracle", "purpose": "fixture-purpose",
                "requestedArgv": ["rALl", "--dry-run", "argument with spaces Ω"],
                "cwd": str(self.repo.resolve()), "wrapper": str((self.repo / "gradlew").resolve()),
                "sourceBefore": dict(source), "sourceAfter": dict(source),
                "productExitCode": status, "stopExitCode": 0, "finalExitCode": status,
                "sourceUnchanged": True, "ownedSurvivors": [], "errors": []}

    def check_receipt(self, path, status=1):
        # Options precede the two positional arguments because the remaining
        # original argv is intentionally parsed with argparse.REMAINDER.
        return self.invoke([sys.executable, str(self.repo / "scripts/check-audit-receipt.py"),
                            "--purpose", "fixture-purpose", "--cwd", str(self.repo),
                            "--wrapper", str(self.repo / "gradlew"), str(path), str(status),
                            "--", "rALl", "--dry-run", "argument with spaces Ω"])

    def test_receipt_cli_accepts_only_exact_product_status_with_finalized_source_binding(self):
        path = self.work / "receipt with spaces Ω.json"
        for status in (0, 1, 42):
            with self.subTest(status=status):
                path.write_text(json.dumps(self.good_receipt(status)), encoding="utf-8")
                self.assert_status(self.check_receipt(path, status))
        for field, value in (("schema", True), ("schema", 2), ("id", ""),
                             ("purpose", "previous-purpose"), ("cwd", str(self.work)),
                             ("wrapper", str(self.executor)), ("requestedArgv", ["help"]),
                             ("productExitCode", True), ("productExitCode", 0),
                             ("finalExitCode", 0), ("stopExitCode", 9), ("stopExitCode", False),
                             ("sourceUnchanged", False), ("ownedSurvivors", [{"pid": 42}]),
                             ("ownedSurvivors", None), ("ownedSurvivors", {}), ("errors", ["cleanup failed"]),
                             ("sourceBefore", None), ("sourceAfter", {})):
            with self.subTest(field=field, value=value):
                receipt = self.good_receipt()
                receipt[field] = value
                path.write_text(json.dumps(receipt), encoding="utf-8")
                result = self.check_receipt(path)
                self.assert_status(result, 125)
                self.assertIn("FATAL: invalid audit leaf receipt", result.stderr)
        path.write_text(json.dumps(self.good_receipt(125)), encoding="utf-8")
        self.assert_status(self.check_receipt(path, 125), 125)

    def test_receipt_cli_rejects_missing_malformed_duplicate_oversized_and_symlink_inputs(self):
        path = self.work / "invalid receipt Ω.json"
        self.assert_status(self.check_receipt(path), 125)
        for raw in ("{invalid", "[]", '{"schema":1,"schema":1}', " " * (1024 * 1024 + 1)):
            with self.subTest(shape=raw[:40]):
                path.write_text(raw, encoding="utf-8")
                self.assert_status(self.check_receipt(path), 125)
        target = self.work / "valid receipt.json"
        target.write_text(json.dumps(self.good_receipt()), encoding="utf-8")
        path.unlink()
        path.symlink_to(target)
        self.assert_status(self.check_receipt(path), 125)

    def test_receipt_cli_requires_exact_source_pair_and_well_formed_commit_tree_diff(self):
        path = self.work / "source receipt.json"
        for field, value in (("commit", "A" * 40), ("commit", "1" * 39),
                             ("tree", "2" * 41), ("status", None),
                             ("diffSha256", "A" * 64), ("diffSha256", "3" * 63)):
            with self.subTest(field=field, value=value):
                receipt = self.good_receipt()
                receipt["sourceBefore"][field] = value
                receipt["sourceAfter"] = copy.deepcopy(receipt["sourceBefore"])
                path.write_text(json.dumps(receipt), encoding="utf-8")
                self.assert_status(self.check_receipt(path), 125)
        receipt = self.good_receipt()
        receipt["sourceAfter"]["status"] = " M settings.gradle.kts\n"
        path.write_text(json.dumps(receipt), encoding="utf-8")
        self.assert_status(self.check_receipt(path), 125)


if __name__ == "__main__":
    unittest.main(verbosity=2)
