#!/usr/bin/env python3
"""Prerequisites and post-main inspection for the pinned submission action.

The action submits BEFORE this verifier runs. Its post action runs AFTER all
workflow steps. Neither a graph nor this receipt proves successful submission,
full resolver coverage, post-action completion, or native worker retirement.
No product tests, dependency writer, publisher, or token-free sandbox is added.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
from urllib.parse import unquote

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import audit_processes

MIB = 1024 * 1024
GRAPH_DIRECTORY = "dependency-graph-reports"
WORKFLOW = "p2pKit/P2pKit/.github/workflows/dependency-submission.yml@"
PROPERTIES = (
    "org.gradle.jvmargs=-Xmx2g -XX:MaxMetaspaceSize=768m -XX:+UseParallelGC -Dfile.encoding=UTF-8",
    "org.gradle.workers.max=2", "org.gradle.parallel=false", "org.gradle.caching=false",
    "org.gradle.configuration-cache=false", "org.gradle.daemon=false",
    "kotlin.compiler.execution.strategy=in-process", "org.gradle.java.installations.auto-download=false",
    "org.gradle.java.installations.auto-detect=false", "org.gradle.logging.level=info",
)
PLATFORMS = (("android-36", "36"), ("android-37.0", "37.0"))
OUTCOMES = {"success", "failure", "cancelled", "skipped"}


def require(value, message):
    if not value:
        raise ValueError(message)


def parse(raw):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, "duplicate JSON key")
            result[key] = value
        return result
    require(len(raw) <= 16 * MIB, "JSON input exceeds bound")
    return json.loads(raw, object_pairs_hook=unique,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite JSON value")))


def physical(path, directory=False):
    path = Path(path)
    require(path.is_absolute() and ".." not in path.parts and not re.search(r"[\x00-\x1f\x7f]", str(path)),
            "absolute single-line physical path required")
    for part in (path, *path.parents):
        require(not part.is_symlink(), "symlink is not an owned path")
    if directory:
        info = path.stat()
        require(stat.S_ISDIR(info.st_mode) and info.st_uid == os.getuid(), "owned directory required")
    return path


def read(path, limit=16 * MIB):
    path = physical(path)
    before = path.lstat()
    require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and before.st_size <= limit,
            "bounded single-link regular file required")
    with path.open("rb") as stream:
        raw = stream.read(limit + 1)
        after = os.fstat(stream.fileno())
    require(os.path.samestat(before, after) and os.path.samestat(after, path.lstat()) and
            before.st_size == after.st_size == len(raw) and before.st_mtime_ns == after.st_mtime_ns,
            "input changed while reading")
    return raw


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def write_new(path, raw):
    path = physical(path)
    with path.open("xb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())


def record(path, value):
    write_new(path, (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n").encode())


def reject_overrides(env):
    blocked = {"JAVA_OPTS", "GRADLE_OPTS", "JAVA_TOOL_OPTIONS", "JDK_JAVA_OPTIONS", "_JAVA_OPTIONS",
               "GRADLE_HOME", "GRADLE_USER_HOME", "KOTLIN_OPTS", "KONAN_OPTS", "KONAN_JVM_ARGS",
               "KOTLIN_HOME", "KONAN_HOME", "KOTLIN_NATIVE_HOME", "KONAN_DATA_DIR", "GRADLE_ENCRYPTION_KEY",
               "BASH_ENV", "ENV", "PYTHONHOME", "PYTHONPATH", "GIT_CONFIG_COUNT", "GIT_CONFIG_PARAMETERS",
               "GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "P2PKIT_GRADLE_EXECUTOR", "P2PKIT_ROOT_OVERRIDE"}
    prefixes = ("ORG_GRADLE_PROJECT_", "GITHUB_DEPENDENCY_GRAPH_", "DEPENDENCY_GRAPH_", "GRADLE_PLUGIN_",
                "GRADLE_BUILD_ACTION_", "GRADLE_ACTION_", "P2PKIT_AUDIT_", "BASH_FUNC_", "INPUT_", "DYLD_", "LD_")
    for key, value in env.items():
        require(not ((key in blocked and value) or key.startswith(prefixes)),
                "ambient execution/graph override must be resolved: " + key)
    # The action tests presence, not truthiness, and otherwise skips submission.
    require("ACT" not in env, "ACT cannot supply hosted dependency acceptance")


def hosted_identity(env):
    require(env.get("GITHUB_ACTIONS") == "true" and env.get("GITHUB_REPOSITORY") == "p2pKit/P2pKit" and
            env.get("RUNNER_ENVIRONMENT") == "github-hosted" and env.get("RUNNER_OS") == "macOS" and
            env.get("RUNNER_ARCH") in {"ARM64", "X64"}, "genuine hosted macOS context required")
    sha, ref = env.get("GITHUB_SHA", ""), env.get("GITHUB_REF", "")
    require(re.fullmatch(r"[0-9a-f]{40}", sha) and re.fullmatch(r"refs/heads/[^\s\x00]+", ref),
            "full source SHA and branch ref required")
    require(env.get("GITHUB_EVENT_NAME") in {"push", "workflow_dispatch"} and
            (env["GITHUB_EVENT_NAME"] != "push" or ref == "refs/heads/main"), "unsupported event/ref")
    require(env.get("GITHUB_WORKFLOW_REF") == WORKFLOW + ref and env.get("GITHUB_WORKFLOW_SHA") == sha and
            env.get("GITHUB_WORKFLOW") == "Dependency submission" and env.get("GITHUB_JOB") == "submit",
            "workflow identity differs")
    for key in ("GITHUB_RUN_ID", "GITHUB_RUN_ATTEMPT"):
        require(re.fullmatch(r"[1-9][0-9]*", env.get(key, "")), "run identity missing")
    return {"commit": sha, "ref": ref, "runId": env["GITHUB_RUN_ID"], "runAttempt": env["GITHUB_RUN_ATTEMPT"],
            "correlator": "dependency_submission-submit", "workflowRef": env["GITHUB_WORKFLOW_REF"]}


def java_homes(env):
    keys = ["JAVA_HOME_" + str(major) + "_" + env["RUNNER_ARCH"] for major in (17, 21)]
    require(all(env.get(key) and Path(env[key]).is_absolute() for key in ["JAVA_HOME", *keys]),
            "explicit setup-java homes required")
    homes = [str(Path(env[key]).resolve(strict=True)) for key in keys]
    require(len(set(homes)) == 2 and all(not re.search(r"[\s,\\=\x00]", p) for p in homes),
            "distinct supported setup-java paths required")
    require(Path(env.get("JAVA_HOME", "")).resolve(strict=True) == Path(homes[0]),
            "wrapper JAVA_HOME must be the installed native JDK17")
    for home in homes:
        require(all((Path(home) / "bin" / tool).is_file() for tool in ("java", "javac")), "full native JDK required")
    return homes


def java_settings(raw, major, home, arch):
    expected_arch = {"ARM64": {"aarch64", "arm64"}, "X64": {"amd64", "x86_64"}}[arch]
    values = {}
    for key in ("java.specification.version", "java.home", "os.arch"):
        matches = re.findall(r"^\s*" + re.escape(key) + r" = (.+)$", raw, re.M)
        require(len(matches) == 1, "ambiguous/missing Java identity")
        values[key] = matches[0]
    require(values["java.specification.version"] == str(major) and values["os.arch"] in expected_arch and
            Path(values["java.home"]).resolve(strict=True) == Path(home), "native Java identity differs")
    return values


def properties(homes):
    require(len(homes) == 2 and len(set(homes)) == 2 and
            all(Path(p).is_absolute() and not re.search(r"[\s,\\=\x00]", p) for p in homes), "invalid Java property paths")
    return ("\n".join((*PROPERTIES, "org.gradle.java.installations.paths=" + ",".join(homes))) + "\n").encode()


def sdk_directory(env, root):
    require(env.get("ANDROID_HOME"), "ANDROID_HOME is required")
    sdk = Path(env["ANDROID_HOME"]).resolve(strict=True)
    require(sdk.is_dir(), "installed Android SDK directory required")
    if env.get("ANDROID_SDK_ROOT"):
        require(Path(env["ANDROID_SDK_ROOT"]).resolve(strict=True) == sdk, "Android SDK aliases disagree")
    local = root / "local.properties"
    if local.exists() or local.is_symlink():
        # Fresh hosted checkout does not need exotic Java-properties escapes.
        # Reject ambiguity, rather than silently ignoring a second SDK alias.
        rows = [line.strip() for line in read(local, MIB).decode().splitlines()
                if line.strip() and not line.lstrip().startswith(("#", "!"))]
        require(all("\\" not in line and re.fullmatch(r"[A-Za-z0-9_.-]+\s*[=:].*", line) for line in rows),
                "ambiguous local.properties is not admitted")
        values = [re.split(r"\s*[=:]\s*", line, maxsplit=1) for line in rows]
        require(len({key for key, _ in values}) == len(values), "duplicate local.properties key")
        configured = dict(values).get("sdk.dir")
        if configured is not None:
            require(Path(configured).is_absolute() and Path(configured).resolve(strict=True) == sdk,
                    "local.properties sdk.dir disagrees")
    return sdk


def missing_platforms(sdk):
    missing = []
    for folder, level in PLATFORMS:
        directory = sdk / "platforms" / folder
        if not directory.exists() and not directory.is_symlink():
            missing.append("platforms;" + folder)
            continue
        raw = read(directory / "source.properties", MIB).decode()
        require(re.findall(r"^AndroidVersion.ApiLevel=(.*)$", raw, re.M) == [level],
                "literal Android platform metadata differs: " + folder)
    return missing


def query(argv, root, env, timeout=30):
    # Fixed Git/Java identity queries, not an arbitrary user command interface.
    result = subprocess.run(argv, cwd=root, env=env, stdin=subprocess.DEVNULL,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout, check=False)
    require(result.returncode == 0 and len(result.stdout) + len(result.stderr) <= MIB,
            "identity query failed or exceeded output bound")
    return result.stdout.decode(), result.stderr.decode()


def source_identity(root, env):
    out, _ = query(["git", "-c", "core.fsmonitor=false", "rev-parse", "HEAD", "HEAD^{tree}"], root, env)
    values = out.splitlines()
    require(len(values) == 2 and all(re.fullmatch(r"[0-9a-f]{40}", value) for value in values), "Git source identity missing")
    query(["git", "-c", "core.fsmonitor=false", "diff", "--exit-code", "HEAD", "--"], root, env)
    require(values[0] == env["GITHUB_SHA"], "checkout differs from hosted source")
    return values[1]


def expected_components(root):
    # Sanity representatives, NOT lock-count equality or a full graph/SBOM audit.
    checks = (("library/p2p-core/gradle.lockfile", "org.jetbrains.kotlin:kotlin-stdlib", "jvmRuntimeClasspath"),
              ("library/p2p-core/gradle.lockfile", "org.jetbrains.kotlinx:kotlinx-coroutines-core-jvm", "jvmRuntimeClasspath"),
              ("library/p2p-transport-lan/gradle.lockfile", "org.slf4j:slf4j-api", "embeddedJmdnsCompileClasspath"))
    coordinates = []
    for file, module, configuration in checks:
        matches = []
        for line in read(root / file, MIB).decode().splitlines():
            if line.startswith(module + ":"):
                coordinate, membership = line.split("=", 1)
                if configuration in membership.split(","):
                    matches.append(coordinate)
        require(len(matches) == 1, "current-lock representative is ambiguous")
        coordinates.append(matches[0])
    return coordinates


def coordinate(purl):
    require(isinstance(purl, str), "component package URL missing")
    match = re.fullmatch(r"pkg:maven/([^/]+)/([^/@]+)@([^?#]+)(?:\?[^#]*)?(?:#.*)?", purl)
    require(match, "non-Maven component requires reviewed admission")
    return ":".join(unquote(value) for value in match.groups())


def inspect_graphs(files, binding, expected):
    require(0 < len(files) <= 100, "nonempty bounded graph set required")
    components, rows, root_manifest, correlators = set(), [], False, set()
    for name, raw in files:
        graph = parse(raw)
        require(isinstance(graph, dict) and graph.get("sha") == binding["commit"] and graph.get("ref") == binding["ref"],
                "graph source/ref differs")
        job = graph.get("job", {})
        correlator = job.get("correlator", "") if isinstance(job, dict) else ""
        require(isinstance(job, dict) and job.get("id") == binding["runId"] and isinstance(correlator, str) and
                re.fullmatch(re.escape(binding["correlator"]) + r"(?:-[1-9][0-9]?)?", correlator) and
                name == correlator + ".json" and correlator not in correlators, "graph run/correlator differs")
        correlators.add(correlator)
        manifests = graph.get("manifests")
        require(isinstance(manifests, dict) and manifests, "nonempty graph manifests required")
        count = 0
        for manifest in manifests.values():
            require(isinstance(manifest, dict), "graph manifest object required")
            source = manifest.get("file")
            require(isinstance(source, dict), "graph manifest source file required")
            location = source.get("source_location")
            require(isinstance(location, str) and location and not Path(location).is_absolute() and
                    ".." not in Path(location).parts, "graph manifest source location differs")
            root_manifest |= location == "settings.gradle.kts"
            resolved = manifest.get("resolved")
            require(isinstance(resolved, dict) and resolved, "nonempty resolved manifest required")
            for identifier, value in resolved.items():
                require(isinstance(identifier, str) and isinstance(value, dict), "resolved component object required")
                current = coordinate(value.get("package_url"))
                require(not current.startswith("org.jmdns:") and not identifier.startswith("org.jmdns:"),
                        "stale external org.jmdns graph membership")
                components.add(current)
            count += len(resolved)
        rows.append({"file": name, "sha256": digest(raw), "bytes": len(raw), "resolvedEntries": count})
    require(root_manifest, "root settings manifest missing")
    require(set(expected) <= components, "current-lock representative missing from graph")
    return {"graphs": rows, "distinctCoordinates": len(components), "currentLockRepresentatives": expected}


def prepare(env, root):
    reject_overrides(env)
    binding = hosted_identity(env)
    require(sys.platform == "darwin" and os.getuid() != 0 and os.getuid() == os.geteuid(), "ordinary native Mac required")
    role = audit_processes.host_role()
    require(role == {"ARM64": "macos-arm64", "X64": "macos-x64"}[env["RUNNER_ARCH"]], "native Python/runner mismatch")
    require(Path(env["GITHUB_WORKSPACE"]).resolve(strict=True) == root, "workspace differs")
    binding["tree"] = source_identity(root, env)
    event = parse(read(Path(env["GITHUB_EVENT_PATH"])))
    require(event.get("repository", {}).get("full_name") == "p2pKit/P2pKit" and
            event.get("ref") in {binding["ref"], binding["ref"][11:]}, "original event identity differs")
    if env["GITHUB_EVENT_NAME"] == "push":
        require(event.get("after") == binding["commit"], "push event source differs")
    else:
        require(event.get("inputs") in (None, {}), "unexpected manual resolver inputs")
    require(not os.path.lexists(root / GRAPH_DIRECTORY), "old dependency graphs are not reusable")
    homes = java_homes(env)
    java = []
    for major, home in zip((17, 21), homes):
        out, err = query([home + "/bin/java", "-XshowSettings:properties", "-version"], root, env)
        java.append(java_settings(err, major, home, env["RUNNER_ARCH"]))
    sdk = sdk_directory(env, root)
    missing = missing_platforms(sdk)
    temporary = physical(Path(env["RUNNER_TEMP"]).resolve(strict=True), directory=True)
    state = temporary / ("p2pkit-dependency-submission-" + binding["runId"] + "-" + binding["runAttempt"])
    require(not os.path.lexists(state), "fresh exclusive submission state required")
    state.mkdir(mode=0o700)
    home = state / "gradle-home"
    home.mkdir(mode=0o700)
    evidence = state / "receipt"
    evidence.mkdir(mode=0o700)
    policy = properties(homes)
    write_new(home / "gradle.properties", policy)
    settings = read(root / "settings.gradle.kts", MIB).decode()
    projects = re.findall(r'^include\("(:[^"\s]+)"\)$', settings, re.M)
    require(len(projects) == len(set(projects)) == 10, "review changed default resolver project coverage")
    input_paths = ["gradlew", "gradle/wrapper/gradle-wrapper.jar", "gradle/wrapper/gradle-wrapper.properties",
                   ".github/workflows/dependency-submission.yml", "scripts/dependency-submission-prerequisites.py",
                   "scripts/audit_processes.py", "gradle.properties", "gradle/verification-metadata.xml",
                   "gradle/libs.versions.toml", "gradle/gradle-daemon-jvm.properties", "settings.gradle.kts"]
    input_paths.extend(str(path.relative_to(root)) for path in root.rglob("gradle.lockfile"))
    admission = {"schema": 1, "binding": binding, "runner": {"role": role, "image": env.get("ImageOS"),
                 "version": env.get("ImageVersion")}, "java": java, "gradleHome": str(home), "sdk": str(sdk),
                 "missingPlatforms": missing, "propertiesSha256": digest(policy), "properties": policy.decode(),
                 "expectedComponents": expected_components(root),
                 "sourceInputs": {path: digest(read(root / path)) for path in sorted(input_paths)},
                 "requiredResolverTasks": [project + ":ForceDependencyResolutionPlugin_resolveProjectDependencies"
                                           for project in ["", *projects]]}
    record(evidence / "admission.json", admission)
    with Path(env["GITHUB_ENV"]).open("a") as stream:
        stream.write("GRADLE_USER_HOME=" + str(home) + "\n")
    with Path(env["GITHUB_OUTPUT"]).open("a") as stream:
        stream.write("state=" + str(state) + "\ngradle-home=" + str(home) + "\nreceipt=" + str(evidence) + "\n")
    print("RESULT: hosted identity, native JDK17/21 and fresh bounded dependency home admitted")


def load_admission(env):
    binding = hosted_identity(env)
    state = physical(Path(env["P2PKIT_DEPENDENCY_STATE"]), directory=True)
    admission = parse(read(state / "receipt/admission.json"))
    expected = Path(env["RUNNER_TEMP"]).resolve(strict=True) / (
        "p2pkit-dependency-submission-" + binding["runId"] + "-" + binding["runAttempt"])
    require(state == expected and admission.get("schema") == 1 and
            {key: admission["binding"][key] for key in binding} == binding and
            env.get("GRADLE_USER_HOME") == admission["gradleHome"] == str(state / "gradle-home"),
            "source/run/owned-home binding changed")
    return state, admission, binding


def install_sdk(env, root):
    state, admission, _ = load_admission(env)
    sdk = sdk_directory(env, root)
    require(str(sdk) == admission["sdk"], "SDK changed after admission")
    missing = missing_platforms(sdk)
    row = {"schema": 1, "requestedMissingOnly": missing, "sdkManagerExitCode": None,
           "platformMetadata": dict(PLATFORMS), "sdk": str(sdk), "validation": "FAIL"}
    try:
        if missing:
            # Never --licenses, yes-pipe, package refresh, or emulator/system image.
            command = [str(sdk / "cmdline-tools/latest/bin/sdkmanager"), "--sdk_root=" + str(sdk), *missing]
            result = subprocess.run(command, cwd=root, env=env, stdin=subprocess.DEVNULL, timeout=720, check=False)
            row["sdkManagerExitCode"] = result.returncode
            require(result.returncode == 0, "missing compile SDK installation failed")
        require(not missing_platforms(sdk), "both literal compile platforms are required")
        row["validation"] = "PASS"
    finally:
        record(state / "receipt/sdk.json", row)
    print("RESULT: literal Android compile platforms 36 and 37.0 admitted; no runtime claim")


def verify(env, root):
    state, admission, binding = load_admission(env)
    evidence = state / "receipt"
    row = {"schema": 1, "binding": admission["binding"], "actionMainOutcome": env.get("P2PKIT_DEPENDENCY_ACTION_OUTCOME"),
           "stopOutcome": env.get("P2PKIT_DEPENDENCY_STOP_OUTCOME"), "verification": "FAIL",
           "scope": "POST_ACTION_MAIN_PRE_ACTION_POST",
           "actionMainAttempted": env.get("P2PKIT_DEPENDENCY_ACTION_OUTCOME") in {"success", "failure", "cancelled"},
           "apiSubmission": "NOT_INFERRED_FROM_THIS_RECEIPT",
           "postActionAndApiReadback": "POST_PENDING_EXTERNAL_READBACK", "fullResolverCoverage": "NOT_INSPECTED",
           "stopExitCode": env.get("P2PKIT_DEPENDENCY_STOP_EXIT_CODE", ""),
           "allWorkerRetirement": "NOT_ESTABLISHED_BY_THIS_RECEIPT"}
    try:
        require(all(row[key] in OUTCOMES for key in ("actionMainOutcome", "stopOutcome")), "action/stop outcomes missing")
        require({key: admission["binding"][key] for key in binding} == binding, "source/run binding changed")
        require(source_identity(root, env) == admission["binding"]["tree"], "source tree changed")
        require(all(digest(read(root / path)) == expected for path, expected in admission["sourceInputs"].items()),
                "source, locks, wrapper or metadata changed")
        require(env.get("GRADLE_USER_HOME") == admission["gradleHome"] == str(state / "gradle-home"), "owned home changed")
        actual = read(state / "gradle-home/gradle.properties", MIB)
        expected = admission["properties"].encode()
        # Exact pinned action may prepend only these two lines when runner debug is enabled.
        debug_prefix = b"org.gradle.logging.level=info\norg.gradle.logging.stacktrace=all\n\n"
        require(actual in (expected, debug_prefix + expected), "owned resource policy changed")
        row["propertiesAfterSha256"] = digest(actual)
        require(not missing_platforms(sdk_directory(env, root)), "compile SDK changed")
        directory = physical(root / GRAPH_DIRECTORY, directory=True)
        files = []
        for path in sorted(directory.iterdir()):
            if path.suffix == ".json":
                require(len(files) < 100, "too many dependency graphs")
                files.append((path.name, read(path)))
        row.update(inspect_graphs(files, binding, admission["expectedComponents"]))
        require(row["actionMainOutcome"] == row["stopOutcome"] == "success" and row["stopExitCode"] == "0",
                "action main or same-home stop did not succeed")
        row["verification"] = "PASS_POST_MAIN_SCOPE_ONLY"
    except (ValueError, OSError, KeyError, TypeError, subprocess.SubprocessError) as error:
        row["error"] = type(error).__name__ + ": " + str(error)[:1024]
        raise
    finally:
        record(evidence / "post-main.json", row)
    print("RESULT: nonempty source-bound dependency graph and successful action-main/stop outcomes; post readback still required")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("prepare", "install-sdk", "verify"))
    args = parser.parse_args()
    os.umask(0o077)
    root = Path(__file__).resolve().parents[1]
    try:
        {"prepare": prepare, "install-sdk": install_sdk, "verify": verify}[args.operation](dict(os.environ), root)
    except (ValueError, OSError, KeyError, TypeError, subprocess.SubprocessError) as error:
        print("FATAL: dependency prerequisite/inspection failed: " + type(error).__name__ + ": " + str(error)[:1024], file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
