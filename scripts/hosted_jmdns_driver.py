"""Two fixed children of the existing manual maintenance command owner.

This is neither a new executor nor a permission checker. The controller alone
admits sources, invokes/receives the canonical command, retains candidate
reports, and exports after known native/stream closure. Child metadata cannot
stand in for that return. No command, environment, path or timeout menu exists.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import time

NS = 1_000_000_000
PRODUCT_NS, OBSERVATION_NS = 1200 * NS, 120 * NS
RESERVED_CLOSE_NS = (120 + 180) * NS
TARGET_KEYS = {"schema", "scope", "requestSha256", "invocationId", "jobId", "beforeJava",
               "requestedGradleArgv", "executedGradleArgv", "testExitCode", "beforeObservationElapsedNs",
               "startedTestMonotonicNs", "endTestMonotonicNs"}
RETURN_KEYS = {"schema", "scope", "requestSha256", "targetReceipt", "targetReceiptSha256",
               "targetRecordSha256", "returnedMonotonicNs"}
CONTROL_REPORT = re.compile(
    r"library/p2p-transport-lan/build/reports/jmdns-close/run-[A-Za-z0-9_-]+/control-[A-Za-z0-9_-]+\.log\Z")
HASH = re.compile(r"[0-9a-f]{64}\Z")
PURPOSES = {"target": "dependency-maintenance-jmdns-target", "observer": "dependency-maintenance-jmdns-observer"}
CHILD_ENVIRONMENT_FIXED_CODES = (
    ("HOME", "JMDNS_ENV_MISSING_HOME", "JMDNS_ENV_VALUE_HOME"),
    ("TMPDIR", "JMDNS_ENV_MISSING_TMPDIR", "JMDNS_ENV_VALUE_TMPDIR"),
    ("XDG_CONFIG_HOME", "JMDNS_ENV_MISSING_XDG_CONFIG_HOME", "JMDNS_ENV_VALUE_XDG_CONFIG_HOME"),
    ("XDG_CACHE_HOME", "JMDNS_ENV_MISSING_XDG_CACHE_HOME", "JMDNS_ENV_VALUE_XDG_CACHE_HOME"),
    ("GNUPGHOME", "JMDNS_ENV_MISSING_GNUPGHOME", "JMDNS_ENV_VALUE_GNUPGHOME"),
    ("GH_CONFIG_DIR", "JMDNS_ENV_MISSING_GH_CONFIG_DIR", "JMDNS_ENV_VALUE_GH_CONFIG_DIR"),
    ("KONAN_DATA_DIR", "JMDNS_ENV_MISSING_KONAN_DATA_DIR", "JMDNS_ENV_VALUE_KONAN_DATA_DIR"),
    ("ANDROID_USER_HOME", "JMDNS_ENV_MISSING_ANDROID_USER_HOME", "JMDNS_ENV_VALUE_ANDROID_USER_HOME"),
    ("PYTHONDONTWRITEBYTECODE", "JMDNS_ENV_MISSING_PYTHONDONTWRITEBYTECODE",
     "JMDNS_ENV_VALUE_PYTHONDONTWRITEBYTECODE"),
    ("PYTHONUNBUFFERED", "JMDNS_ENV_MISSING_PYTHONUNBUFFERED", "JMDNS_ENV_VALUE_PYTHONUNBUFFERED"),
    ("GIT_CONFIG_NOSYSTEM", "JMDNS_ENV_MISSING_GIT_CONFIG_NOSYSTEM", "JMDNS_ENV_VALUE_GIT_CONFIG_NOSYSTEM"),
    ("GIT_CONFIG_GLOBAL", "JMDNS_ENV_MISSING_GIT_CONFIG_GLOBAL", "JMDNS_ENV_VALUE_GIT_CONFIG_GLOBAL"),
    ("GIT_TERMINAL_PROMPT", "JMDNS_ENV_MISSING_GIT_TERMINAL_PROMPT", "JMDNS_ENV_VALUE_GIT_TERMINAL_PROMPT"),
    ("LC_ALL", "JMDNS_ENV_MISSING_LC_ALL", "JMDNS_ENV_VALUE_LC_ALL"),
    ("TZ", "JMDNS_ENV_MISSING_TZ", "JMDNS_ENV_VALUE_TZ"),
)
CHILD_ENVIRONMENT_EXTRA_CODES = (
    ("__CF_USER_TEXT_ENCODING", "JMDNS_ENV_EXTRA_CF_USER_TEXT_ENCODING"),
    ("__PYVENV_LAUNCHER__", "JMDNS_ENV_EXTRA_PYVENV_LAUNCHER"),
    ("LC_CTYPE", "JMDNS_ENV_EXTRA_LC_CTYPE"),
    ("PYTHONEXECUTABLE", "JMDNS_ENV_EXTRA_PYTHONEXECUTABLE"),
    ("SDKROOT", "JMDNS_ENV_EXTRA_SDKROOT"),
    ("DYLD_FRAMEWORK_PATH", "JMDNS_ENV_EXTRA_DYLD_FRAMEWORK_PATH"),
    ("DYLD_LIBRARY_PATH", "JMDNS_ENV_EXTRA_DYLD_LIBRARY_PATH"),
)


class DriverError(RuntimeError):
    """Fixed reason only; the existing controller renders infrastructure failure."""


def require(value, reason):
    if not value:
        raise DriverError(reason)


def child_environment_failure_code(actual, expected):
    """NONEXHAUSTIVE first recognized discrepancy, never input text or cause proof.

    This pure diagnostic runs only after full environment equality has failed.
    Its fixed names are not an environment allowance; even OTHER still refuses.
    """
    if type(actual) is not dict or type(expected) is not dict:
        return "JMDNS_ENV_OTHER"
    if not all(type(key) is str and type(value) is str
               for environment in (actual, expected) for key, value in environment.items()):
        return "JMDNS_ENV_OTHER"
    for key, missing_code, value_code in CHILD_ENVIRONMENT_FIXED_CODES:
        if key not in expected:
            continue
        if key not in actual:
            return missing_code
        if actual[key] != expected[key]:
            return value_code
    for key, code in CHILD_ENVIRONMENT_EXTRA_CODES:
        if key in actual and key not in expected:
            return code
    return "JMDNS_ENV_OTHER"


def ordinary_exit(code):
    require(type(code) is int and 0 <= code <= 123, "JMDNS_COMMAND_NOT_KNOWN_ORDINARY")
    return code


def request_data(value, scope):
    require(type(value) is dict and set(value) == {"schema", "scope", "request", "github", "startedMonotonicNs",
            "deadlineMonotonicNs", "observationBudgetNs"} and type(value["schema"]) is int and
            value["schema"] == 1 and value["scope"] == scope and type(value["request"]) is dict and
            value["request"].get("operation") == "diagnose-jmdns", "JMDNS_REQUEST")
    require(all(type(value[key]) is int and value[key] > 0 for key in
                ("startedMonotonicNs", "deadlineMonotonicNs", "observationBudgetNs")) and
            value["deadlineMonotonicNs"] - value["startedMonotonicNs"] == PRODUCT_NS and
            value["observationBudgetNs"] == OBSERVATION_NS, "JMDNS_FIXED_BUDGET")
    return value


def target_data(value, request, request_hash, scope):
    require(type(value) is dict and set(value) == TARGET_KEYS and type(value["schema"]) is int and
            value["schema"] == 1 and value["scope"] == scope and value["requestSha256"] == request_hash and
            all(type(value[key]) is str and re.fullmatch(r"[0-9a-f]{32}", value[key])
                for key in ("invocationId", "jobId")), "JMDNS_TARGET_BINDING")
    ordinary_exit(value["testExitCode"])
    require(all(type(value[key]) is int for key in
                ("startedTestMonotonicNs", "endTestMonotonicNs", "beforeObservationElapsedNs")) and
            request["startedMonotonicNs"] <= value["startedTestMonotonicNs"] <= value["endTestMonotonicNs"] <
            request["deadlineMonotonicNs"] and value["beforeObservationElapsedNs"] ==
            value["startedTestMonotonicNs"] - request["startedMonotonicNs"], "JMDNS_TARGET_CLOCKS")
    return value


def observation_deadline(request, target=None):
    """Do not charge the actual test twice; do charge all dispatch/close overhead."""
    test_ns = 0 if target is None else target["endTestMonotonicNs"] - target["startedTestMonotonicNs"]
    return request["startedMonotonicNs"] + request["observationBudgetNs"] + test_ns


def can_start(now, deadline, seconds):
    require(type(now) is int and type(deadline) is int and type(seconds) is int and seconds > 0,
            "JMDNS_ACTION_CLOCK")
    return now + seconds * NS <= deadline


def inconclusive(reason):
    return {"status": "INCONCLUSIVE", "reason": reason}


class Driver:
    def __init__(self, controller, phase):
        self.c = controller
        require(phase in PURPOSES and sys.flags.isolated == 1 and sys.flags.no_site == 1 and
                sys.dont_write_bytecode and os.name == "posix", "JMDNS_FIXED_CHILD")
        self.phase = phase
        self.runner = controller.module("jmdns_driver_executor", "scripts/run-audit-command.py")
        self.data = controller.module("jmdns_driver_data", "scripts/hosted_jmdns_diagnostic.py")
        require((self.data.PRODUCT_SECONDS, self.data.OBSERVATION_SECONDS) == (1200, 120) and
                (controller.STOP_SECONDS, controller.NATIVE_HEADROOM) == (120, 180), "JMDNS_RESOURCE_POLICY")
        self.state, self.context = self.runner.context_at(os.environ.get("P2PKIT_AUDIT_STATE_DIR", ""))
        processes = sys.modules["audit_processes"]
        domains = processes.ownership_domains(os.environ.get(processes.CHAIN_ENV, ""),
                                             os.environ.get(processes.DOMAINS_ENV, ""))
        require(len(domains) == 1 and self.context["host"] == "macos-arm64" and
                domains[-1]["job"] == self.context["id"] == os.environ.get(processes.JOB_ENV) and
                domains[-1]["state"] == str(self.state) and
                domains[-1]["home"] == self.context["gradleHome"] == os.environ.get("GRADLE_USER_HOME"),
                "JMDNS_ORIGINAL_OWNER")
        self.invocation = domains[-1]["id"]
        self.records = self.state / "evidence/maintenance"
        self.root = controller.ROOT
        require(Path(self.context["root"]) == self.root == Path.cwd() and
                self.runner.source_snapshot(self.root) == self.context["source"], "JMDNS_CONTROLLER_SOURCE")
        self.candidate = controller.physical(self.root.parent / "candidate")
        expected_env = controller.child_environment(os.environ, self.state.parent)
        expected_env.update({key: os.environ[key] for key in controller.NATIVE_OWNER_ENV})
        if not (dict(os.environ) == expected_env):
            raise DriverError(child_environment_failure_code(dict(os.environ), expected_env))
        self.env = dict(os.environ)  # Preserve the actual complete domain; never reset or replace it.
        raw = controller.read_file(self.records / "jmdns-request.json", 16384)[0]
        self.request_hash = controller.digest(raw)
        self.request = request_data(controller.parsed(raw), controller.DIAGNOSTIC_SCOPE)
        request = self.request["request"]
        require(controller.request_data(request, os.environ) == self.request["github"] and
                self.context["source"]["commit"] == request["controller_sha"] and
                self.context["source"]["tree"] == request["controller_tree"], "JMDNS_REQUEST_SOURCE")
        controller.clean_source(self.runner, self.candidate, request["candidate_sha"], request["candidate_tree"])
        for name in ("gradlew", "gradle/wrapper/gradle-wrapper.jar", "gradle/wrapper/gradle-wrapper.properties",
                     "gradle.properties", "scripts/run-audit-command.py", "scripts/audit_processes.py"):
            require(controller.read_file(self.root / name)[0] == controller.read_file(self.candidate / name)[0],
                    "JMDNS_WRAPPER_OR_RESOURCE_CHANGED")
        argv = [str(Path(sys.executable).resolve()), "-I", "-B", "-S",
                str(self.root / "scripts/run-hosted-dependency-update.py"), "_diagnostic-" + phase]
        start = controller.parsed(controller.read_file(self.state / "evidence" / self.invocation / "start.json")[0])
        require(start.get("id") == self.invocation and start.get("jobId") == self.context["id"] and
                start.get("kind") == "command" and start.get("purpose") == PURPOSES[phase] and
                start.get("requestedArgv") == argv and start.get("cwd") == str(self.root) and
                start.get("wrapper") == str(self.root / "gradlew") and
                start.get("controllerPid") == os.getppid() and
                not os.path.lexists(self.state / "evidence" / self.invocation / "receipt.json"),
                "JMDNS_ORIGINAL_START")
        self.product_deadline = self.request["deadlineMonotonicNs"] - RESERVED_CLOSE_NS
        self.observation_deadline = observation_deadline(self.request)
        require(self.request["startedMonotonicNs"] <= time.monotonic_ns() < self.product_deadline,
                "JMDNS_TOTAL_DEADLINE")
        self.directory = self.records / ("jmdns-" + phase)
        self.directory.mkdir(mode=0o700)

    def observation_window(self, seconds):
        started = time.monotonic_ns()
        if not can_start(started, min(self.product_deadline, self.observation_deadline), seconds):
            return None
        return started, started + seconds * NS

    def hash_java(self, path):
        window = self.observation_window(self.data.HASH_SECONDS)
        if window is None:
            return inconclusive("OBSERVATION_BUDGET_NOT_ADMITTED")
        started, deadline = window
        try:
            fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        except (FileNotFoundError, PermissionError):
            return inconclusive("JAVA_CODE_UNAVAILABLE")
        with os.fdopen(fd, "rb") as stream:
            before = os.fstat(stream.fileno())
            require(stat.S_ISREG(before.st_mode) and 0 < before.st_size <= self.c.FILE_LIMIT,
                    "JMDNS_JAVA_CODE_BOUND")
            checksum, size = hashlib.sha256(), 0
            while True:
                require(time.monotonic_ns() < deadline, "JMDNS_HASH_TIMEOUT")
                block = stream.read(1024 * 1024)
                require(time.monotonic_ns() < deadline, "JMDNS_HASH_TIMEOUT")
                if not block:
                    break
                size += len(block)
                require(size <= self.c.FILE_LIMIT, "JMDNS_JAVA_CODE_BOUND")
                checksum.update(block)
            after = os.fstat(stream.fileno())
            fields = lambda info: (info.st_dev, info.st_ino, info.st_mode, info.st_uid, info.st_nlink,
                                   info.st_size, info.st_mtime_ns, info.st_ctime_ns)
            require(size == before.st_size and fields(before) == fields(after) == fields(path.lstat()),
                    "JMDNS_JAVA_CODE_CHANGED")
        ended = time.monotonic_ns()
        require(ended <= deadline, "JMDNS_HASH_TIMEOUT")
        return {"status": "OBSERVED", "sha256": checksum.hexdigest(), "bytes": size,
                "identity": [before.st_dev, before.st_ino], "mode": stat.S_IMODE(before.st_mode),
                "uid": before.st_uid, "nlink": before.st_nlink, "mtimeNs": before.st_mtime_ns,
                "ctimeNs": before.st_ctime_ns, "startedMonotonicNs": started, "endedMonotonicNs": ended}

    def observe_command(self, name, argv, seconds, interpretation_limit):
        window = self.observation_window(seconds)
        if window is None:
            return inconclusive("OBSERVATION_BUDGET_NOT_ADMITTED"), None, None
        started, deadline = window
        try:
            child = subprocess.Popen(argv, cwd=self.root, env=self.env, stdin=subprocess.DEVNULL,
                                     stdout=subprocess.PIPE, stderr=subprocess.PIPE, close_fds=True, bufsize=0)
        except (FileNotFoundError, PermissionError):
            return inconclusive("NATIVE_COMMAND_UNAVAILABLE"), None, None
        errors, streams = [], []
        try:
            for pipe, suffix in ((child.stdout, "stdout"), (child.stderr, "stderr")):
                stream = self.runner.Tee(pipe, self.directory / (name + "." + suffix + ".log"),
                                         None, errors, False)
                streams.append(stream)  # Own the reader before a potentially partial thread start.
                stream.start()
            remaining = (deadline - time.monotonic_ns()) / NS
            require(remaining > 0, "JMDNS_OBSERVER_TIMEOUT")
            code = ordinary_exit(child.wait(timeout=remaining))
        finally:
            # No PID kill, private owner, new session or ownership-marker rewrite.
            # On timeout/UNKNOWN the existing parent performs its canonical drain;
            # this child returns reserved infrastructure failure, never export credit.
            for stream in streams:
                try:
                    stream.finish()
                except BaseException:
                    errors.append("STREAM_RETIREMENT_FAILED")
            for pipe in (child.stdout, child.stderr):
                if pipe is not None and not any(stream.source is pipe for stream in streams):
                    try:
                        pipe.close()
                    except BaseException:
                        errors.append("UNCLAIMED_STREAM_CLOSE_FAILED")
        ended = time.monotonic_ns()
        require(not errors and ended <= deadline, "JMDNS_OBSERVER_STREAM_OR_TIMEOUT")
        outputs = {}
        raw = []
        for suffix in ("stdout", "stderr"):
            path = self.directory / (name + "." + suffix + ".log")
            data, info = self.c.read_file(path, self.runner.MAX_STREAM_BYTES)
            outputs[suffix] = {"file": path.relative_to(self.records).as_posix(), **info}
            raw.append(data)
        require(time.monotonic_ns() <= deadline, "JMDNS_OBSERVER_TIMEOUT")
        result = {"status": "RETURNED", "argv": argv, "exitCode": code,
                  "startedMonotonicNs": started, "endedMonotonicNs": time.monotonic_ns(), **outputs,
                  "interpretation": "INCONCLUSIVE" if code or sum(map(len, raw)) > interpretation_limit else
                                    "NATIVE_ORIGINAL_REVIEW_REQUIRED"}
        return result, raw[0], raw[1]

    def java_metadata(self):
        try:
            java = (Path(self.env["JAVA_HOME"]) / "bin/java").resolve(strict=True)
        except (FileNotFoundError, PermissionError):
            return {"executablePathSha256": "UNKNOWN", "executable": inconclusive("JAVA_CODE_UNAVAILABLE"),
                    "signature": inconclusive("JAVA_CODE_UNAVAILABLE"), "uuid": inconclusive("JAVA_CODE_UNAVAILABLE")}
        path_hash = self.data.path_identity(str(java))
        result = {"executablePathSha256": path_hash, "executable": self.hash_java(java)}
        for name, argv in self.data.code_argv(str(java)).items():
            result[name] = self.observe_command(name, argv, self.data.CODE_SECONDS, self.data.CODE_LIMIT)[0]
        return result

    def record(self, name, value):
        self.c.write_new(self.records / name, self.c.encoded(value))


def target(controller):
    driver = Driver(controller, "target")
    before = driver.java_metadata()
    original = driver.data.diagnostic_gradle_arguments(str(Path(sys.executable).resolve(strict=True)))
    argv = [str(driver.candidate / "gradlew"), *driver.runner.gradle_arguments(original)]
    started = time.monotonic_ns()
    require(started < driver.product_deadline, "JMDNS_TEST_NOT_ADMITTED")
    child = subprocess.Popen(argv, cwd=driver.candidate, env=driver.env, stdin=subprocess.DEVNULL, close_fds=True)
    # The existing canonical parent's bounded product streams capture these exact
    # inherited stdout/stderr. No direct Java launch or substitute test assessor.
    remaining = (driver.product_deadline - time.monotonic_ns()) / NS
    require(remaining > 0, "JMDNS_TEST_TIMEOUT")
    code = ordinary_exit(child.wait(timeout=remaining))
    ended = time.monotonic_ns()
    require(ended < driver.product_deadline, "JMDNS_TEST_TIMEOUT")
    record = {"schema": 1, "scope": controller.DIAGNOSTIC_SCOPE, "requestSha256": driver.request_hash,
              "invocationId": driver.invocation, "jobId": driver.context["id"], "beforeJava": before,
              "requestedGradleArgv": original, "executedGradleArgv": argv, "testExitCode": code,
              "beforeObservationElapsedNs": started - driver.request["startedMonotonicNs"],
              "startedTestMonotonicNs": started, "endTestMonotonicNs": ended}
    target_data(record, driver.request, driver.request_hash, controller.DIAGNOSTIC_SCOPE)
    driver.record("jmdns-target.json", record)
    return code  # Before-code nonzero metadata never replaces the actual test result.


def original_target(driver):
    c = driver.c
    raw = c.read_file(driver.records / "jmdns-target-return.json", 8 * c.MIB)[0]
    returned = c.parsed(raw)
    require(type(returned) is dict and set(returned) == RETURN_KEYS and type(returned["schema"]) is int and
            returned["schema"] == 1 and returned["scope"] == c.DIAGNOSTIC_SCOPE and
            returned["requestSha256"] == driver.request_hash and type(returned["returnedMonotonicNs"]) is int and
            all(type(returned[name]) is str and HASH.fullmatch(returned[name]) for name in
                ("targetReceiptSha256", "targetRecordSha256")), "JMDNS_ORIGINAL_RETURN")
    target_raw = c.read_file(driver.records / "jmdns-target.json")[0]
    require(c.digest(target_raw) == returned["targetRecordSha256"], "JMDNS_TARGET_RECORD_CHANGED")
    result = target_data(c.parsed(target_raw), driver.request, driver.request_hash, c.DIAGNOSTIC_SCOPE)
    expected_gradle = driver.data.diagnostic_gradle_arguments(str(Path(sys.executable).resolve(strict=True)))
    require(result["jobId"] == driver.context["id"] and result["invocationId"] != driver.invocation and
            result["endTestMonotonicNs"] <= returned["returnedMonotonicNs"] <= time.monotonic_ns() <
            driver.request["deadlineMonotonicNs"] and result["requestedGradleArgv"] == expected_gradle and
            result["executedGradleArgv"] == [str(driver.candidate / "gradlew"),
                *driver.runner.gradle_arguments(expected_gradle)], "JMDNS_TARGET_IDENTITY")
    receipt_raw = c.read_file(driver.state / "evidence" / result["invocationId"] / "receipt.json", 4 * c.MIB)[0]
    receipt = c.parsed(receipt_raw)
    require(c.digest(receipt_raw) == returned["targetReceiptSha256"] and receipt == returned["targetReceipt"],
            "JMDNS_TARGET_RECEIPT_CHANGED")
    expected = [str(Path(sys.executable).resolve()), "-I", "-B", "-S",
                str(driver.root / "scripts/run-hosted-dependency-update.py"), "_diagnostic-target"]
    c.command_return_data(result["testExitCode"], receipt, driver.context, result["invocationId"], PURPOSES["target"], expected)
    return returned, result, receipt, c.digest(raw)


def retained_control(driver, returned, receipt):
    """Read only the original admitted candidate copy, never a fresh live report."""
    c = driver.c
    anchor = driver.records / "candidate-reports"
    binding = c.parsed(c.read_file(anchor / "binding.json")[0])
    manifest_raw = c.read_file(anchor / "report-manifest.json")[0]
    baseline_raw = c.read_file(driver.records / "candidate-report-baseline.json")[0]
    require(type(binding) is dict and type(binding.get("schema")) is int and binding["schema"] == 1 and
            binding.get("scope") == "MANUAL_JMDNS_REPORT_CUSTODY_V1" and
            binding.get("request") == driver.request["request"] and
            binding.get("invocationId") == receipt["id"] and binding.get("purpose") == PURPOSES["target"] and
            binding.get("productExitCode") == receipt["productExitCode"] and
            binding.get("receiptSha256") == returned["targetReceiptSha256"] and
            binding.get("beforeManifestSha256") == c.digest(baseline_raw) and
            binding.get("afterManifestSha256") == c.digest(manifest_raw) and
            binding.get("candidateBefore") == binding.get("candidateAfter") ==
            {"commit": driver.request["request"]["candidate_sha"], "tree": driver.request["request"]["candidate_tree"],
             "status": "", "diffSha256": c.digest(b"")}, "JMDNS_REPORT_BINDING")
    manifest = c.parsed(manifest_raw)
    require(type(manifest) is dict and set(manifest) == {"schema", "records", "limitation"} and
            type(manifest["schema"]) is int and manifest["schema"] == 1 and type(manifest["records"]) is list and
            len(manifest["records"]) <= c.FILE_COUNT and all(type(row) is dict for row in manifest["records"]),
            "JMDNS_REPORT_MANIFEST")
    rows = [row for row in manifest["records"] if type(row) is dict and
            type(row.get("source")) is str and CONTROL_REPORT.fullmatch(row["source"])]
    if len(rows) != 1:
        return inconclusive("ORIGINAL_CONTROL_REPORT_UNAVAILABLE")
    row = rows[0]
    require(set(row) == {"source", "sha256", "bytes", "classification", "retained"} and
            row["classification"] == "changed-since-admission" and row["retained"] == "reports/" + row["source"] and
            type(row["sha256"]) is str and HASH.fullmatch(row["sha256"]) and type(row["bytes"]) is int and
            row["bytes"] >= 0, "JMDNS_ORIGINAL_CONTROL_REPORT")
    if row["bytes"] > driver.data.FIXTURE_LIMIT:
        return inconclusive("ORIGINAL_CONTROL_REPORT_OVERSIZED")
    raw = c.read_file(anchor / row["retained"], driver.data.FIXTURE_LIMIT)[0]
    require(len(raw) == row["bytes"] and c.digest(raw) == row["sha256"], "JMDNS_CONTROL_REPORT_CHANGED")
    return driver.data.parse_fixture_trace(raw)


def observe(controller):
    driver = Driver(controller, "observer")
    returned, result, receipt, return_hash = original_target(driver)
    driver.observation_deadline = observation_deadline(driver.request, result)
    after = driver.java_metadata()
    before = result["beforeJava"]
    require(type(before) is dict and set(before) == {"executablePathSha256", "executable", "signature", "uuid"},
            "JMDNS_ORIGINAL_JAVA_METADATA")
    old_file, new_file = before["executable"], after["executable"]
    stable = old_file.get("status") == new_file.get("status") == "OBSERVED"
    if stable:
        require(old_file["sha256"] == new_file["sha256"] and
                before["executablePathSha256"] == after["executablePathSha256"], "JMDNS_JAVA_CODE_CHANGED")
    if not stable:
        binding = inconclusive("JAVA_CODE_IDENTITY_UNAVAILABLE")
    elif result["testExitCode"] == 0:
        binding = inconclusive("FAILURE_NOT_REPRODUCED")
    elif time.monotonic_ns() >= driver.observation_deadline:
        binding = inconclusive("OBSERVATION_BUDGET_NOT_ADMITTED")
    else:
        trace = retained_control(driver, returned, receipt)
        binding = driver.data.bind_native_process(trace, receipt, invocation_id=result["invocationId"],
            job_id=result["jobId"], executable_path_sha256=after["executablePathSha256"])
    log = inconclusive("ORIGINAL_FIRST_SEND_NOT_BOUND")
    interpretation = log
    if binding.get("status") == "BOUND":
        log, stdout, stderr = driver.observe_command("native-log", driver.data.log_argv(binding),
                                                    driver.data.LOG_SECONDS, driver.data.LOG_LIMIT)
        interpretation = driver.data.log_data(stdout, stderr, log["exitCode"], binding) if stdout is not None else log
    codes = [item["exitCode"] for item in (before["signature"], before["uuid"], after["signature"], after["uuid"], log)
             if item.get("status") == "RETURNED"]
    code = next((ordinary_exit(value) for value in codes if value), 0)
    ended = time.monotonic_ns()
    require(ended < driver.product_deadline, "JMDNS_TOTAL_DEADLINE")
    driver.record("jmdns-observer.json", {"schema": 1, "scope": controller.DIAGNOSTIC_SCOPE,
        "requestSha256": driver.request_hash, "invocationId": driver.invocation, "jobId": driver.context["id"],
        "targetReturnSha256": return_hash, "targetRecordSha256": returned["targetRecordSha256"],
        "afterJava": after, "binding": binding, "logObservation": log, "logInterpretation": interpretation,
        "observationDeadlineMonotonicNs": driver.observation_deadline,
        "observationElapsedNs": ended - driver.request["startedMonotonicNs"] -
                                (result["endTestMonotonicNs"] - result["startedTestMonotonicNs"]),
        "endedMonotonicNs": ended, "observerExitCode": code})
    return code
