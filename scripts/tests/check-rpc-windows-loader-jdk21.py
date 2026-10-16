#!/usr/bin/env python3
"""JVM refusal/models plus a conditional Windows system-bootstrap investigation, not installed authority."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
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
    for name in ("java21", "java17", "jar", "output", "application-classpath"):
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
                        "VmAcquisitionInvocationTests" in name or
                        "LibraryLoadInvocationTests" in name or
                        "ExportLookupInvocationTests" in name or
                        "ImageReadInvocationTests" in name or
                        "SystemBootstrapCandidateTests" in name or
                        "SystemImportResolutionTests" in name or
                        "InstallationSecurityTests" in name or
                        "AncestorRetirementTests" in name or
                        "ByteReadInvocationTests" in name or
                        "PackagedVerifierTests" in name or
                        "LoadedRegistrationTests" in name or "InstalledProviderTests" in name or
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

    # Real development application classes enter only the new connection JVMs, never the existing
    # isolated refusal/native-mechanics controls. This manifest is test provenance, not installed authority.
    classpath_file = args.application_classpath.resolve(strict=True)
    require(classpath_file.stat().st_size <= 65536, "Unbounded development application classpath")
    application = json.loads(classpath_file.read_text(encoding="utf-8"))
    require(isinstance(application, dict) and set(application) == {"schema", "mainClassDirectories", "classpath"} and
            type(application["schema"]) is int and application["schema"] == 1,
            "Unexpected development classpath descriptor")

    def paths(values, limit):
        require(isinstance(values, list) and 1 <= len(values) <= limit and
                all(isinstance(item, str) and 0 < len(item) <= 4096 and Path(item).is_absolute() and
                    not any(char in item for char in "\x00\r\n") for item in values), "Invalid application classpath entries")
        result = [Path(item).resolve(strict=True) for item in values]
        require(len(result) == len(set(result)), "Duplicate application classpath entries")
        return result

    main_directories = paths(application["mainClassDirectories"], 16)
    application_paths = paths(application["classpath"], 256)
    require(all(path.is_dir() and path in application_paths for path in main_directories),
            "Actual main class outputs are missing from the development classpath")
    resources = ["dev/p2pkit/sample/rpc/profile/" + name + ".class" for name in
                 ("WindowsProfilePackagedVerifier", "WindowsProfileCustodyJni", "WindowsProfileInstalledProvider",
                  "WindowsProfileFiles", "WindowsProfileInstalledProvider$Unavailable")]
    candidates = [path for path in main_directories if all((path / resource).is_file() for resource in resources)]
    require(len(candidates) == 1, "Original compiled helper/JNI class output is ambiguous or absent")
    main_directory = candidates[0]
    bindings = []
    for resource in resources:
        with (main_directory / resource).open("rb") as source:
            value = source.read(1024 * 1024 + 1)
        require(8 <= len(value) <= 1024 * 1024 and value[:8] == bytes.fromhex("cafebabe0000003d"),
                "Connection requires actual Java-17 helper/JNI class bytes")
        bindings.append({"resource": resource, "bytes": len(value), "sha256": hashlib.sha256(value).hexdigest()})
    (output / "application-bindings.json").write_text(json.dumps({
        "scope": "DEVELOPMENT_MAIN_CLASS_BINDING_NOT_INSTALLED_AUTHORITY", "mainClassDirectory": str(main_directory),
        "classpath": [str(path) for path in application_paths], "classes": bindings,
    }, indent=2) + "\n", encoding="utf-8")

    def run(name, command, expected, stdout=None, stderr=None, timeout=60):
        # Fixed compiler/controls, including Windows system-only investigation. Not installed-app supervision.
        with (output / (name + "-stdout.log")).open("xb") as out, \
                (output / (name + "-stderr.log")).open("xb") as err:
            try:
                result = subprocess.run([str(item) for item in command], cwd=ROOT, stdin=subprocess.DEVNULL,
                                        stdout=out, stderr=err, timeout=timeout, check=False)
            except subprocess.TimeoutExpired:
                # Do not lose the attempted command or read possibly unfinished descendant output.
                # The existing outer component supervisor still owns final descendant retirement.
                records.append({"case": name, "exit": None, "expectedExit": expected, "timedOut": True})
                (output / "commands.json").write_text(json.dumps(records, indent=2) + "\n", encoding="utf-8")
                raise ValueError(name + " exceeded its fixed command deadline") from None
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
    packaged_cases = ["success", "missing-helper", "invalid-pin", "manifest-pin", "header-byte", "code-byte",
                      "iat-byte", "export-address", "page-count"]
    empty_classpath = output / "empty-application-classpath"
    empty_classpath.mkdir()
    def connected_run(name, test_class, arguments, expected, missing_helper=False, flags=()):
        connected = base[1:] + list(flags) + access + ["--patch-module", MODULE + "=" + str(classes)]
        connected += ["--class-path", str(empty_classpath) if missing_helper else
                      os.pathsep.join(str(path) for path in application_paths)]
        connected += ["--module", MODULE + "/" + PACKAGE + "." + test_class, *arguments]
        # Java argument files avoid Windows' process-command limit. Quote every token, including backslashes;
        # do not use a shell or an ambient/current-directory classpath fallback.
        require(all(not any(char in str(item) for char in "\x00\r\n") for item in connected), "Invalid Java argument")
        arguments = "\n".join('"' + str(item).replace("\\", "\\\\").replace('"', '\\"') + '"' for item in connected) + "\n"
        require(len(arguments.encode("utf-8")) <= 256 * 1024, "Unbounded connected Java command")
        argument_file = output / (name + ".args")
        with argument_file.open("x", encoding="utf-8", newline="\n") as target:
            target.write(arguments)
        run(name, [java21, "@" + str(argument_file)], 0, expected, "")

    for case in packaged_cases:
        connected_run("packaged-verifier-" + case, "PackagedVerifierTests", [case, str(main_directory),
                      bindings[0]["sha256"], bindings[1]["sha256"]],
            "WINDOWS_PACKAGED_VERIFIER_PASS case=" + re.escape(case) +
            r" scope=REAL_JDK21_TO_JDK17_BYTE_COMPARISON_NOT_LOAD_OR_AUTHORITY\n", case == "missing-helper")
    connected_run("installed-provider-unavailable", "InstalledProviderTests", [str(main_directory),
                  bindings[2]["sha256"], bindings[3]["sha256"], bindings[1]["sha256"], bindings[4]["sha256"]],
        r"WINDOWS_INSTALLED_PROVIDER_REFUSAL_PASS scope=REAL_JDK21_TO_JDK17_TYPED_REFUSAL_NOT_INSTALLED_OR_NATIVE\n")
    run("loaded-registration-diagnostics", base + ["--patch-module", MODULE + "=" + str(classes),
        "--module", MODULE + "/" + PACKAGE + ".LoadedRegistrationTests", "diagnostics"], 0,
        r"WINDOWS_LOADED_REGISTRATION_DIAGNOSTICS_PASS scope=INERT_FORMATTING_NOT_DLL_OR_AUTHORITY\n", "")
    models, _ = run("models", base + access + ["--patch-module", MODULE + "=" + str(classes),
                         "--module", MODULE + "/" + PACKAGE + ".ModelTests"], 0,
                   r"WINDOWS_LOADER_JDK21_MODELS_PASS tests=14 "
                   r"scope=PORTABLE_FFM_DATA_NOT_WINDOWS_NATIVE_OR_PROFILE\n", "")
    run("installation-security-policy", base + ["--patch-module", MODULE + "=" + str(classes),
        "--module", MODULE + "/" + PACKAGE + ".InstallationSecurityTests"], 0,
        r"WINDOWS_INSTALLATION_SECURITY_PASS tests=259 "
        r"scope=INERT_DESCRIPTOR_POLICY_NOT_NATIVE_READBACK_OR_AUTHORITY\n", "")
    run("ancestor-frame-retirement", base + access + ["--patch-module", MODULE + "=" + str(classes),
        "--module", MODULE + "/" + PACKAGE + ".AncestorRetirementTests"], 0,
        r"WINDOWS_ANCESTOR_RETIREMENT_PASS tests=2 "
        r"scope=INERT_FRAME_QUARANTINE_NOT_PENDING_OS_IO_OR_AUTHORITY\n", "")
    import_cases = ["valid", "bounds", "unsupported", "names", "duplicate", "snapshot", "owner-refusal",
                    "retirement-known", "retirement-unknown"]
    for case in import_cases:
        run("system-import-resolution-" + case, base + access + ["--patch-module", MODULE + "=" + str(classes),
            "--module", MODULE + "/" + PACKAGE + ".SystemImportResolutionTests", case], 0,
            "WINDOWS_SYSTEM_IMPORT_RESOLUTION_PASS case=" + re.escape(case) +
            r" scope=INERT_INVENTORY_AND_OWNERSHIP_NOT_NATIVE_OR_AUTHORITY\n", "")
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
    vm_cases = ["success", "arguments", "virtual", "thread", "reentrant", "close-after-result", "retired-frame",
                "status", "zero-count", "multiple-count", "negative-count", "null-vm", "unaligned-vm",
                "high-vm", "frame-alias", "partial-frame-alias", "clear-failure", "count-clear-failure",
                "readback-cleanup", "closed-entry"]
    for case in vm_cases:
        run("vm-acquisition-invocation-" + case, base + access + ["--patch-module", MODULE + "=" + str(classes),
            "--module", MODULE + "/" + PACKAGE + ".VmAcquisitionInvocationTests", case], 0,
            "WINDOWS_JVM_FFM_ACQUISITION_PASS case=" + re.escape(case) +
            r" scope=JDK_UPCALL_MARSHALING_NOT_VM_LOOKUP_OR_AUTHORITY\n", "")
    load_cases = ["success", "arguments", "virtual", "thread", "reentrant", "duplicate", "close-after-result",
                  "retired-frame", "null-module", "unaligned-module", "high-module", "readback-failure",
                  "clear-failure", "closed-entry", "late-scope-close", "return-failure"]
    capture_scope = "WINDOWS_GET_LAST_ERROR" if os.name == "nt" else "NOT_EXECUTED"
    byte_cases = ["full", "short", "eof", "false", "pending", "throw-after-return", "excess-count",
                  "unsigned-count", "thread", "bounds", "limit"]
    for case in byte_cases:
        run("file-byte-read-" + case, base + access + ["--patch-module", MODULE + "=" + str(classes),
            "--module", MODULE + "/" + PACKAGE + ".ByteReadInvocationTests", case], 0,
            "WINDOWS_FILE_BYTE_READ_PASS case=" + re.escape(case) +
            " scope=INERT_READ_AND_RETIREMENT_NOT_FILE_CUSTODY_OR_AUTHORITY capture=" + capture_scope + r"\n", "")
    for case in load_cases:
        run("library-load-invocation-" + case, base + access + ["--patch-module", MODULE + "=" + str(classes),
            "--module", MODULE + "/" + PACKAGE + ".LibraryLoadInvocationTests", case], 0,
            "WINDOWS_LIBRARY_FFM_LOAD_PASS case=" + re.escape(case) +
            " scope=JDK_UPCALL_MARSHALING_NOT_DLL_LOADING_OR_AUTHORITY capture=" + capture_scope + r"\n", "")
    export_cases = ["success", "long-name", "arguments", "forwarder", "wrong-address", "null-address",
                    "high-address", "private-alias", "partial-frame-alias", "ordinal-buffer", "thread",
                    "virtual", "closed-bootstrap", "closed-module", "close-after-result", "reentrant",
                    "retired-frame", "clear-failure", "invocation-failure", "late-module-close"]
    export_host = "WINDOWS_X64_LINKER" if os.name == "nt" else "INERT_FRAME_ONLY"
    for case in export_cases:
        run("export-lookup-invocation-" + case, base + access + ["--patch-module", MODULE + "=" + str(classes),
            "--module", MODULE + "/" + PACKAGE + ".ExportLookupInvocationTests", case], 0,
            "WINDOWS_EXPORT_FFM_LOOKUP_PASS case=" + re.escape(case) +
            " scope=JDK_UPCALL_MARSHALING_NOT_EXPORT_LOOKUP_OR_AUTHORITY host=" + export_host + r"\n", "")
    image_cases = ["success", "data", "data-copy", "readonly", "readonly-writable", "readonly-copy",
                   "readonly-executable", "maximum", "arguments", "virtual", "thread", "reentrant",
                   "padding-change", "close-after-result", "source-frame-alias", "count-frame-alias", "retired-frame",
                   "closed-bootstrap", "closed-module", "invocation-error", "query-failed", "query-short",
                   "allocation-mismatch", "not-committed", "not-image", "code-writable", "data-executable", "guard",
                   "region-gap", "region-short", "region-overflow", "read-failed", "partial-read", "excess-read",
                   "late-query-failed", "mapping-change", "clear-failure", "late-module-close", "readback-failure"]
    for case in image_cases:
        run("image-read-invocation-" + case, base + access + ["--patch-module", MODULE + "=" + str(classes),
            "--module", MODULE + "/" + PACKAGE + ".ImageReadInvocationTests", case], 0,
            "WINDOWS_IMAGE_FFM_READ_PASS case=" + re.escape(case) +
            " scope=JDK_UPCALL_MARSHALING_NOT_OS_MEMORY_READ_OR_AUTHORITY capture=" + capture_scope + r"\n", "")
    bootstrap_entry = ["--patch-module", MODULE + "=" + str(classes), "--module",
                       MODULE + "/" + PACKAGE + ".SystemBootstrapCandidateTests"]
    run("system-bootstrap-runtime", base + bootstrap_entry + ["runtime"], 0,
        r"WINDOWS_SYSTEM_BOOTSTRAP_CANDIDATE_PASS case=runtime scope=RUNTIME_REFUSAL_NO_SYSTEM_BOOTSTRAP\n", "")
    run("system-bootstrap-virtual", base + access + bootstrap_entry + ["virtual"], 0,
        r"WINDOWS_SYSTEM_BOOTSTRAP_CANDIDATE_PASS case=virtual scope=THREAD_REFUSAL_NO_SYSTEM_BOOTSTRAP\n", "")
    bootstrap_case = "inspect" if os.name == "nt" else "unsupported"
    bootstrap_scope = ("DEVELOPMENT_JVM_SYSTEM_CALLS_NOT_INSTALLED_AUTHORITY_OR_PROFILE" if os.name == "nt"
                       else "RUNTIME_REFUSAL_NO_SYSTEM_BOOTSTRAP")
    run("system-bootstrap-" + bootstrap_case, base + access + bootstrap_entry + [bootstrap_case], 0,
        "WINDOWS_SYSTEM_BOOTSTRAP_CANDIDATE_PASS case=" + bootstrap_case + " scope=" + bootstrap_scope + r"\n", "")
    original_jvm_scope = "UNSUPPORTED_HOST_NOT_EXECUTED"
    original_file_scope = "UNSUPPORTED_HOST_NOT_EXECUTED"
    original_security_scope = "UNSUPPORTED_HOST_NOT_EXECUTED"
    original_security_policy = "NOT_EXECUTED"
    original_ancestor_scope = "UNSUPPORTED_HOST_NOT_EXECUTED"
    original_ancestor_policies = "NOT_EXECUTED"
    original_bytes_scope = "UNSUPPORTED_HOST_NOT_EXECUTED"
    if os.name == "nt":
        original_jvm_scope = "DEVELOPMENT_JVM_ONE_VM_NOT_INSTALLED_AUTHORITY_REGISTRATION_OR_PROFILE"
        run("system-bootstrap-jvm", base + access + bootstrap_entry + ["jvm"], 0,
            "WINDOWS_SYSTEM_BOOTSTRAP_CANDIDATE_PASS case=jvm scope=" + original_jvm_scope + r"\n", "")
        original_file_scope = "DEVELOPMENT_JVM_FILE_LEASE_NOT_INSTALLED_ACL_ANCESTOR_MAPPING_OR_PROFILE"
        run("system-bootstrap-file", base + access + bootstrap_entry + ["file"], 0,
            "WINDOWS_SYSTEM_BOOTSTRAP_CANDIDATE_PASS case=file scope=" + original_file_scope + r"\n", "")
        original_security_scope = "DEVELOPMENT_JVM_HANDLE_SECURITY_NOT_INSTALLED_ANCESTOR_MAPPING_OR_PROFILE"
        security, _ = run("system-bootstrap-security", base + access + bootstrap_entry + ["security"], 0,
            "WINDOWS_SYSTEM_BOOTSTRAP_CANDIDATE_PASS case=security scope=" + original_security_scope +
            r" descriptorPolicy=(ACCEPTED|REFUSED)\n", "")
        original_security_policy = security.strip().rsplit("=", 1)[1]
        original_ancestor_scope = "DEVELOPMENT_JVM_ANCESTOR_HANDLES_NOT_APPROVED_INSTALLATION_MAPPING_OR_PROFILE"
        ancestors, _ = run("system-bootstrap-ancestors", base + access + bootstrap_entry + ["ancestors"], 0,
            "WINDOWS_SYSTEM_BOOTSTRAP_CANDIDATE_PASS case=ancestors scope=" + original_ancestor_scope +
            r" descriptorPolicies=(ACCEPTED|REFUSED)\n", "")
        original_ancestor_policies = ancestors.strip().rsplit("=", 1)[1]
        original_bytes_scope = "DEVELOPMENT_JVM_HANDLE_BYTES_NOT_INSTALLED_IDENTITY_MAPPING_OR_PROFILE"
        run("system-bootstrap-bytes", base + access + bootstrap_entry + ["bytes"], 0,
            "WINDOWS_SYSTEM_BOOTSTRAP_CANDIDATE_PASS case=bytes scope=" + original_bytes_scope + r"\n", "")
    run("test-dll-compiler-budget", [sys.executable, "-I", "-B",
        ROOT / "samples/p2p-sample-rpc/native/windows-profile/tests/jvm/test-build-test-dll.py"], 0,
        r"WINDOWS_TEST_DLL_BUDGET_CONTROLS_PASS tests=30 scope=INERT_CLOCK_NO_COMPILER_OR_NATIVE_EXECUTION\n", "")
    loaded_registration_scope = "UNSUPPORTED_HOST_NOT_EXECUTED"
    if os.name == "nt":
        # A distinct development fixture, never the productive DLL or profile backend. Finish the existing
        # controls first so a new compiler/runtime failure preserves their original results.
        # The producer has a separate cumulative 150-second compilation budget. Its caller must allow
        # that budget plus receipt/retirement, not kill it at an individual tool's 60-second phase cap.
        # Every existing control and every actual DLL/JNI case retains its original 60-second bound.
        native = output / "test-native"
        run("compile-deny-storage-dll", [sys.executable, "-I", "-B",
            ROOT / "samples/p2p-sample-rpc/native/windows-profile/tests/jvm/build-test-dll.py",
            "--jdk17", args.java17.resolve(strict=True), "--output", native], 0,
            r"WINDOWS_TEST_DLL_COMPILE_PASS scope=TEST_ONLY_DENY_STORAGE_NOT_PACKAGED\n", "", timeout=180)
        receipt_path = native / "compiler-receipt.json"
        require(receipt_path.stat().st_size <= 256 * 1024, "Unbounded fixture compiler receipt")
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        require(isinstance(receipt, dict) and type(receipt.get("schema")) is int and receipt["schema"] == 1 and
                receipt.get("result") == "PASS" and
                receipt.get("scope") == "TEST_ONLY_DENY_STORAGE_NOT_PACKAGED" and
                receipt.get("nativeExecution") == receipt.get("packaging") == "NOT_PERFORMED" and
                receipt.get("profileBackend") == "NOT_LINKED" and receipt.get("sourceDirty") is False and
                type(receipt.get("statusBytes")) is int and receipt["statusBytes"] == 0 and
                receipt.get("statusSha256") == hashlib.sha256(b"").hexdigest(),
                "Fixture compilation is not clean-source, test-only, unexecuted evidence")
        for key, revision in (("source", "HEAD"), ("tree", "HEAD^{tree}")):
            require(isinstance(receipt.get(key), str) and re.fullmatch("[0-9a-f]{40}", receipt[key]),
                    "Invalid compiler source binding")
            observed = subprocess.run(["git", "rev-parse", revision], cwd=ROOT, stdin=subprocess.DEVNULL,
                                      stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=15, check=False)
            require(observed.returncode == 0 and observed.stdout.strip() == receipt[key].encode("ascii") and
                    not observed.stderr, "Compiler source no longer matches the original checkout")
        dll = native / "p2pkit-windows-profile.dll"
        bound = receipt.get("dll")
        require(isinstance(bound, dict) and set(bound) == {"path", "name", "bytes", "sha256"} and
                bound["path"] == str(dll) and bound["name"] == dll.name and
                type(bound["bytes"]) is int and 512 <= bound["bytes"] <= 4 * 1024 * 1024 and
                isinstance(bound["sha256"], str) and re.fullmatch("[0-9a-f]{64}", bound["sha256"]),
                "Invalid separately produced fixture identity")
        with dll.open("rb") as source:
            compiled = source.read(4 * 1024 * 1024 + 1)
        require(len(compiled) == bound["bytes"] and hashlib.sha256(compiled).hexdigest() == bound["sha256"],
                "Compiler DLL changed before its first test execution")
        def require_clean_source():
            state = subprocess.run(["git", "status", "--porcelain=v1", "--untracked-files=all"], cwd=ROOT,
                                   stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   timeout=15, check=False)
            require(state.returncode == 0 and not state.stdout and not state.stderr,
                    "Loaded native fixture requires the original clean source")

        require_clean_source()
        loaded_registration_scope = "DEV_TEST_DLL_DENY_STORAGE_NOT_INSTALLED_AUTHORITY_OR_PROVIDER"
        for case in ("pin", "success", "address"):
            connected_run("loaded-registration-" + case, "LoadedRegistrationTests",
                [case, str(dll), bound["sha256"], str(bound["bytes"]), receipt["source"], receipt["tree"],
                 str(main_directory), bindings[0]["sha256"], bindings[1]["sha256"]],
                "WINDOWS_LOADED_REGISTRATION_PASS case=" + case + " scope=" + loaded_registration_scope + r"\n",
                flags=("-Xcheck:jni", "--add-modules=jdk.unsupported"))
        require_clean_source()
        with dll.open("rb") as source:
            require(source.read(4 * 1024 * 1024 + 1) == compiled, "Compiler DLL changed during fixture execution")
    require(jar.read_bytes() == data, "Adapter changed during controls")
    for binding in bindings:
        with (main_directory / binding["resource"]).open("rb") as source:
            value = source.read(1024 * 1024 + 1)
        require(len(value) == binding["bytes"] and hashlib.sha256(value).hexdigest() == binding["sha256"],
                "Actual main helper/JNI class bytes changed during controls")
    result = {"scope": "JDK21_CONTROLS_AND_CONDITIONAL_SYSTEM_BOOTSTRAP_NOT_INSTALLED_OR_PROFILE", "result": "PASS",
              "jar": {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()},
              "observation": actual, "modelResult": models.strip(),
              "systemBootstrapScope": bootstrap_scope, "originalJvmScope": original_jvm_scope,
              "originalJvmFileScope": original_file_scope, "originalJvmSecurityScope": original_security_scope,
              "originalJvmDescriptorPolicy": original_security_policy, "originalJvmAncestorScope": original_ancestor_scope,
              "originalJvmAncestorPolicies": original_ancestor_policies,
              "originalJvmBytesScope": original_bytes_scope,
              "loadedRegistrationScope": loaded_registration_scope, "commands": records}
    (output / "result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
