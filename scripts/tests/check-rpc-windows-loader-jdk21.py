#!/usr/bin/env python3
"""Real JVM preview/module refusal controls and portable FFM models; no OS DLL/JNI/profile operations."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[2]
MODULE = "dev.p2pkit.rpc.windows.loader"
PACKAGE = "dev.p2pkit.rpc.windows.loader"
SCOPE = "JDK21_PREVIEW_MODULE_DIAGNOSTIC_NOT_DLL_OR_PROFILE"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def observation(text):
    require(len(text) <= 2048 and text.endswith("\n") and text.count("\n") == 1, "Unbounded probe result")
    value = json.loads(text)
    expected = {
        "schema", "scope", "javaFeature", "javaVersion", "module", "previewEnabled", "namedNativeAccess",
        "unnamedNativeAccess", "ffmFromJavaBase", "windowsX64Hint", "productionAvailable", "nativeLoad",
        "profileAccess", "javaVendor", "javaRuntimeVersion", "javaVmVersion",
    }
    require(set(value) == expected, "Unexpected adapter result keys")
    require(type(value["schema"]) is int and value["schema"] == 1 and value["scope"] == SCOPE and
            type(value["javaFeature"]) is int and value["javaFeature"] == 21 and
            value["module"] == MODULE and value["previewEnabled"] is True and
            value["namedNativeAccess"] is True and value["unnamedNativeAccess"] is False and
            value["ffmFromJavaBase"] is True and value["productionAvailable"] is False and
            value["nativeLoad"] == value["profileAccess"] == "NOT_PERFORMED", "Invalid adapter observation")
    require(type(value["windowsX64Hint"]) is bool and
            re.fullmatch(r"21[0-9A-Za-z.+_-]*", value["javaVersion"]), "Unexpected runtime observation")
    for key in ("javaVendor", "javaRuntimeVersion", "javaVmVersion"):
        require(isinstance(value[key], str) and 0 < len(value[key]) <= 128 and
                all(32 <= ord(char) < 127 for char in value[key]), "Invalid runtime metadata")
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("java21", "java17", "jar", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    require(not any(os.environ.get(name) for name in (
        "JAVA_TOOL_OPTIONS", "_JAVA_OPTIONS", "JDK_JAVA_OPTIONS",
    )), "Ambient Java overrides are not admitted")
    jar = args.jar.resolve(strict=True)
    data = jar.read_bytes()
    require(0 < len(data) <= 1024 * 1024, "Unexpected adapter JAR size")
    with zipfile.ZipFile(jar) as archive:
        entries = archive.namelist()
        require(len(entries) == len(set(entries)) and "module-info.class" in entries and
                not any("ModelTests" in name or "RegistrationOwnerTests" in name or "RegistrationInvocationTests" in name or
                        name.startswith("META-INF/versions/") for name in entries),
                "Noncanonical production adapter inventory")
        probe = archive.read(PACKAGE.replace(".", "/") + "/Probe.class")
        require(probe[:8] == bytes.fromhex("cafebabeffff0041"), "Probe must require JDK21 preview class format")
    output = args.output.resolve()
    output.mkdir(mode=0o700, parents=False)
    suffix = ".exe" if os.name == "nt" else ""
    java21 = args.java21.resolve(strict=True) / "bin" / ("java" + suffix)
    java17 = args.java17.resolve(strict=True) / "bin" / ("java" + suffix)
    javac = args.java21.resolve(strict=True) / "bin" / ("javac" + suffix)
    records = []

    def run(name, command, expected, stdout=None, stderr=None):
        # Ordinary, fixed Java compiler/model commands. This is not Foundation's installed-app supervisor.
        with (output / (name + "-stdout.log")).open("xb") as out, \
                (output / (name + "-stderr.log")).open("xb") as err:
            result = subprocess.run([str(item) for item in command], cwd=ROOT, stdin=subprocess.DEVNULL,
                                    stdout=out, stderr=err, timeout=60, check=False)
        streams = []
        for kind in ("stdout", "stderr"):
            path = output / (name + "-" + kind + ".log")
            require(path.stat().st_size <= 65536, "Compiler/model output exceeded bound")
            streams.append(path.read_text(encoding="utf-8"))
        records.append({"case": name, "exit": result.returncode, "expectedExit": expected})
        (output / "commands.json").write_text(json.dumps(records, indent=2) + "\n", encoding="utf-8")
        require(result.returncode == expected, name + " returned an unexpected exit")
        require(stdout is None or re.fullmatch(stdout, streams[0]), name + " unexpected stdout")
        require(stderr is None or re.fullmatch(stderr, streams[1]), name + " unexpected stderr")
        return streams

    base = [java21, "-Xmx128m", "--enable-preview", "--module-path", jar]
    access = ["--enable-native-access=" + MODULE]
    entry = ["--module", MODULE + "/" + PACKAGE + ".Probe"]
    positive, _ = run("named-preview", base + access + entry, 0, stderr="")
    actual = observation(positive)
    refusal = r"JDK21_LOADER_PROBE_REFUSED_RUNTIME_POLICY\n"
    run("no-native-access", base + entry, 2, "", refusal)
    run("wrong-native-module", base + ["--enable-native-access=dev.p2pkit.missing"] + entry, 2, "",
        r"WARNING: Unknown module: dev.p2pkit.missing specified to --enable-native-access\n" + refusal)
    run("unnamed-only", base + ["--enable-native-access=ALL-UNNAMED"] + entry, 2, "", refusal)
    run("named-and-unnamed", base + ["--enable-native-access=" + MODULE + ",ALL-UNNAMED"] + entry, 2,
        "", refusal)
    run("classpath-refused", [java21, "-Xmx128m", "--enable-preview", "--enable-native-access=ALL-UNNAMED",
                              "-cp", jar, PACKAGE + ".Probe"], 2, "", refusal)
    run("arguments-refused", base + access + entry + ["--enable-provider"], 2, "",
        r"JDK21_LOADER_PROBE_REFUSED_ARGUMENTS\n")
    run("preview-disabled", [java21, "-Xmx128m", "--module-path", jar] + access + entry, 1, "",
        r"(?s).*UnsupportedClassVersionError.*Preview features are not enabled.*")
    run("jdk17-refused", [java17, "-Xmx128m", "-cp", jar, PACKAGE + ".Probe"], 1, "",
        r"(?s).*UnsupportedClassVersionError.*65\.65535.*up to 61\.0.*")
    test_sources = ROOT / "samples/p2p-sample-rpc/native/windows-loader-jdk21/src/test/java"
    classes = output / "test-classes"
    classes.mkdir()
    sources = sorted(test_sources.rglob("*.java"))
    require(bool(sources), "Missing adapter model controls")
    run("compile-models", [javac, "-J-Xmx256m", "--release", "21", "--enable-preview", "-proc:none",
                           "-encoding", "UTF-8", "-Xlint:all,-preview", "-Werror", "--module-path", jar,
                           "--patch-module", MODULE + "=" + str(test_sources), "-d", classes, *sources], 0)
    models, _ = run("models", base + access + ["--patch-module", MODULE + "=" + str(classes),
                         "--module", MODULE + "/" + PACKAGE + ".ModelTests"], 0,
                   r"WINDOWS_LOADER_JDK21_MODELS_PASS tests=14 "
                   r"scope=PORTABLE_FFM_DATA_NOT_WINDOWS_NATIVE_OR_PROFILE\n", "")
    # Real boot-module singleton, fresh process for each terminal outcome: no test-only reset hook.
    owner_cases = ["success", "reentrant", "concurrent", "invocation", "report", "cleanup",
                   "invocation-cleanup", "report-cleanup", "null-report", "virtual", "null-input", "copied-owner"]
    owner_cases += ["malformed-" + str(i) for i in range(24)] + ["refusal-" + str(i) for i in range(1, 11)]
    for case in owner_cases:
        run("registration-owner-" + case, base + access + ["--patch-module", MODULE + "=" + str(classes),
            "--module", MODULE + "/" + PACKAGE + ".RegistrationOwnerTests", case], 0,
            "WINDOWS_JNI_OWNER_PASS case=" + re.escape(case) +
            r" scope=PORTABLE_LIFETIME_NOT_NATIVE_REGISTRATION_OR_AUTHORITY\n", "")
    invocation_cases = ["success", "snapshot", "arguments", "virtual", "thread", "reentrant", "refusal",
                        "zero-report", "mismatched-result", "report-clear-failure", "closed-entry", "closed-vm",
                        "other-invocation"]
    for case in invocation_cases:
        run("registration-invocation-" + case, base + access + ["--patch-module", MODULE + "=" + str(classes),
            "--module", MODULE + "/" + PACKAGE + ".RegistrationInvocationTests", case], 0,
            "WINDOWS_JNI_FFM_INVOCATION_PASS case=" + re.escape(case) +
            r" scope=JDK_UPCALL_MARSHALING_NOT_WINDOWS_JNI_OR_AUTHORITY\n", "")
    require(jar.read_bytes() == data, "Adapter changed during controls")
    result = {"scope": "JDK21_PREVIEW_REFUSALS_AND_PORTABLE_MODELS_NOT_OS_JNI_OR_RELEASE", "result": "PASS",
              "jar": {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()},
              "observation": actual, "modelResult": models.strip(), "commands": records}
    (output / "result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
