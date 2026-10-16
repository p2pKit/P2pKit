#!/usr/bin/env python3
"""Real development-JDK21 JNI/FFM component controls; NOT profile/installed/bootstrap qualification."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
import threading


def digest(path):
    result = hashlib.sha256()
    with path.open("rb") as value:
        for block in iter(lambda: value.read(1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def run_command(command, directory, environment, index, timeout=60):
    """Bounded direct child/output only; not Foundation descendant or atomic-job supervision."""
    start = time.monotonic()
    outcome = {"command": command, "exitCode": None, "timedOut": False, "outputExceeded": False,
               "captureFailed": False, "finalizationCompleted": False}
    process = subprocess.Popen(command, cwd=directory, env=environment, stdin=subprocess.DEVNULL,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=0)
    def capture(stream, kind):
        try:
            with (directory / f"{index}-{kind}.log").open("xb") as log:
                count = 0
                while block := stream.read(4096):
                    log.write(block[:max(0, 65536 - count)])
                    count += len(block)
                    if count > 65536:
                        outcome["outputExceeded"] = True
                        process.kill()
                        break
        except Exception:
            outcome["captureFailed"] = True
            try:
                process.kill()
            except OSError:
                pass
        finally:
            stream.close()
    readers = [threading.Thread(target=capture, args=(stream, kind), daemon=True)
               for stream, kind in ((process.stdout, "stdout"), (process.stderr, "stderr"))]
    started = []
    try:
        for reader in readers:
            reader.start()
            started.append(reader)
        try:
            outcome["exitCode"] = process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            outcome["timedOut"] = True
            process.kill()
            try:
                outcome["exitCode"] = process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                pass
    finally:
        if process.poll() is None:
            try:
                process.kill()
                process.wait(timeout=5)
            except (OSError, subprocess.TimeoutExpired):
                outcome["captureFailed"] = True
        # Do not wait forever on inherited pipes; incomplete capture fails, never counts as cleanup proof.
        end = time.monotonic() + 5
        for reader in started:
            reader.join(timeout=max(0, end - time.monotonic()))
        outcome["finalizationCompleted"] = process.poll() is not None and all(not r.is_alive() for r in readers)
        outcome["elapsedSeconds"] = round(time.monotonic() - start, 3)
    return outcome


def command_path(path):
    value = str(path)
    if not path.is_absolute() or any(ord(c) > 127 or c in '\r\n"%!^&|<>' for c in value):
        raise ValueError("Unsupported fixed Windows test command path")
    return value


def hosted_windows_binding(repository, args):
    required = {"GITHUB_ACTIONS": "true", "GITHUB_EVENT_NAME": "workflow_dispatch",
                "GITHUB_REPOSITORY": "p2pKit/P2pKit", "GITHUB_JOB": "rpc-windows",
                "GITHUB_REF": "refs/heads/work/rpc-windows-validation-20261012",
                "RUNNER_ENVIRONMENT": "github-hosted", "RUNNER_OS": "Windows", "RUNNER_ARCH": "X64",
                "ImageOS": "win22"}
    if any(os.environ.get(key) != value for key, value in required.items()) or not args.ffm:
        raise ValueError("Windows execution requires the exact hosted component job and all seven controls")
    if os.environ.get("RPC_WINDOWS_VALIDATION_MODE") not in ("full", "build-only"):
        raise ValueError("Unknown scoped Windows validation mode")
    if args.jdk.resolve(strict=True) != Path(os.environ["RPC_WINDOWS_JDK21"]).resolve(strict=True):
        raise ValueError("Only the existing job-selected development JDK21 is allowed")
    expected_output = Path(os.environ["RUNNER_TEMP"]) / "p2pkit-windows-validation/real-jni-ffm-controls"
    if args.output.resolve() != expected_output.resolve():
        raise ValueError("Only the fixed new hosted component output is allowed")
    def git(*arguments):
        return subprocess.check_output(["git", *arguments], cwd=repository, text=True, timeout=10).strip()
    head = git("rev-parse", "HEAD")
    if head != os.environ.get("GITHUB_SHA") or git("status", "--porcelain"):
        raise ValueError("Expected clean exact-source hosted checkout")
    return {"source": head, "tree": git("rev-parse", "HEAD^{tree}"),
            "run": os.environ["GITHUB_RUN_ID"], "attempt": os.environ["GITHUB_RUN_ATTEMPT"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path, help="New private absolute directory outside checkout")
    parser.add_argument("--clang", type=Path, help="Existing trusted absolute Apple Clang")
    parser.add_argument("--sdk", type=Path, help="Existing trusted absolute macOS SDK")
    parser.add_argument("--vsdevcmd", type=Path, help="Existing selected x64 MSVC VsDevCmd.bat; hosted Windows only")
    parser.add_argument("--jdk", required=True, type=Path, help="Existing trusted absolute development JDK21 home")
    parser.add_argument("--classes", required=True, type=Path, help="This checkout's existing Gradle JVM main classes")
    parser.add_argument("--ffm", action="store_true",
                        help="Also connect the actual dormant named-module FFM invocation to this test-owned VM")
    args = parser.parse_args()
    source = Path(__file__).resolve().parent
    repository = source.parents[3]
    expected_classes = repository / "samples/p2p-sample-rpc/build/classes/kotlin/jvm/main"
    windows = sys.platform == "win32"
    if sys.platform not in ("darwin", "win32"):
        parser.error("Only macOS development or the scoped Windows hosted component is supported")
    if windows and (args.clang or args.sdk or not args.vsdevcmd):
        parser.error("Windows requires only --vsdevcmd for its existing compiler")
    if not windows and (not args.clang or not args.sdk or args.vsdevcmd):
        parser.error("macOS requires the existing --clang and --sdk")
    for name in ("output", "jdk", "classes") + (("vsdevcmd",) if windows else ("clang", "sdk")):
        if not getattr(args, name).is_absolute():
            parser.error(f"--{name} must be absolute")
    if args.output.resolve().is_relative_to(repository) or args.output.exists():
        parser.error("Output must be new and outside checkout")
    if args.classes.resolve() != expected_classes.resolve():
        parser.error("Classes must be this checkout's actual existing Gradle JVM main output")
    binding = hosted_windows_binding(repository, args) if windows else None
    args.jdk = args.jdk.resolve(strict=True)
    args.classes = args.classes.resolve(strict=True)
    args.output = args.output.resolve()
    jvm = args.jdk / ("bin/server/jvm.dll" if windows else "lib/server/libjvm.dylib")
    javac = args.jdk / ("bin/javac.exe" if windows else "bin/javac")
    required = [args.jdk / "release", jvm, args.jdk / "include/jni.h",
                args.jdk / ("include/win32/jni_md.h" if windows else "include/darwin/jni_md.h")]
    if windows:
        args.vsdevcmd = args.vsdevcmd.resolve(strict=True)
        required += [args.vsdevcmd]
    else:
        required += [args.clang, args.sdk / "SDKSettings.json"]
    module = "dev.p2pkit.rpc.windows.loader"
    java_sources = []
    if args.ffm:
        required.append(javac)
        java_sources = sorted((source.parent / "windows-loader-jdk21/src/main/java").rglob("*.java"))
        java_sources.append(source / "tests/jvm/RealRegistrationInvocationTest.java")
        if len(java_sources) < 2 or not all(path.is_file() for path in java_sources):
            parser.error("Missing original named-module sources or test-only FFM adapter")
    names = ("WindowsProfileCustodyCalls", "WindowsProfileCustodyJni")
    package = Path("dev/p2pkit/sample/rpc/profile")
    class_inputs = [args.classes / package / (name + ".class") for name in names]
    if not all(path.is_file() for path in required + class_inputs):
        parser.error("Missing selected tool/SDK/runtime or actual compiled classes; no download/build fallback")
    if not any(line.startswith('JAVA_VERSION="21.') for line in (args.jdk / "release").read_text().splitlines()):
        parser.error("Existing JDK21 required, not JDK17 fallback")
    for path in class_inputs:
        header = path.read_bytes()[:8]
        if header != b"\xca\xfe\xba\xbe\x00\x00\x00\x3d":
            parser.error("Actual custody classes must retain Java17 non-preview bytecode")

    os.umask(0o077)
    args.output.mkdir(mode=0o700)
    copied_classes = args.output / "actual-gradle-classes"
    (copied_classes / package).mkdir(parents=True)
    empty_classes = args.output / "empty-classes"
    empty_classes.mkdir()
    temporary = args.output / "tmp"
    temporary.mkdir()
    c_inputs = [source / "profile_policy.c", source / "profile_jni.c", source / "profile_jni_registration.c",
                source / "tests/jvm/deny_storage.c", source / "tests/jvm/registration_jvm_test.c"]
    inputs = c_inputs + [source / name for name in ("profile_policy.h", "profile_win32.h", "profile_jni_registration.h")]
    inputs += [Path(__file__).resolve()] + required + class_inputs + java_sources
    inputs += [repository / "samples/p2p-sample-rpc/src/jvmMain/kotlin" / package / (name + ".kt") for name in names]
    # Include Windows bin DLLs as well: actual selected development-runtime bytes, not installed authority.
    image_directories = ("lib", "include", "bin") if windows else ("lib", "include")
    inputs += [path for name in image_directories for path in (args.jdk / name).rglob("*") if path.is_file()]
    inputs = sorted(set(inputs))
    before = {str(path): digest(path) for path in inputs}
    for path in class_inputs:
        target = copied_classes / package / path.name
        shutil.copyfile(path, target)
        if digest(target) != before[str(path)]:
            raise RuntimeError("Actual class bytes changed while copying")
    if windows:
        system = Path(os.environ["SystemRoot"]).resolve(strict=True)
        system32 = system / "System32"
        command_processor = system32 / "cmd.exe"
        environment = {"PATH": str(system32), "SystemRoot": str(system), "WINDIR": str(system),
                       "TEMP": str(temporary), "TMP": str(temporary), "USERPROFILE": str(args.output),
                       "APPDATA": str(args.output), "LOCALAPPDATA": str(args.output), "VSLANG": "1033",
                       "ComSpec": str(command_processor), "SystemDrive": system.drive}
        compiler_environment = dict(environment)
        compiler_environment["PATH"] = ";".join(str(path) for path in (
            system32, system32 / "WindowsPowerShell/v1.0", system32 / "Wbem"))
        for name in ("ProgramFiles", "ProgramFiles(x86)", "ProgramW6432"):
            path = Path(os.environ[name]).resolve(strict=True)
            compiler_environment[name] = command_path(path)
        executable = args.output / "registration-jvm-test.exe"
        for path in [repository, args.output, args.vsdevcmd, args.jdk, args.classes, executable, command_processor]:
            command_path(path)
        # The selected development toolchain initializes only this compiler child. No compiler flags or
        # arbitrary PATH values enter the JVM children, and no profile_win32.c or jvm.lib is linked.
        command = ["cl.exe", "/nologo", "/Bv", "/std:c11", "/W4", "/WX", "/O2", "/MT", "/GS", "/sdl",
                   "/guard:cf", "/D_WIN32_WINNT=0x0A00", "/I" + str(args.jdk / "include"),
                   "/I" + str(args.jdk / "include/win32")] + [str(path) for path in c_inputs]
        command += ["/Fe:" + str(executable), "/link", "/MACHINE:X64", "/DYNAMICBASE", "/HIGHENTROPYVA",
                    "/NXCOMPAT", "/GUARD:CF", "/INCREMENTAL:NO", "/MANIFEST:EMBED", "kernel32.lib"]
        recipe = args.output / "compile.cmd"
        lines = ["@echo off", "setlocal DisableDelayedExpansion", 'set "INCLUDE="', 'set "LIB="',
                 'set "LIBPATH="', 'set "ERRORLEVEL="', f'call "{args.vsdevcmd}" -arch=x64 -host_arch=x64',
                 "if errorlevel 1 exit /b 2", 'if /i not "%VSCMD_ARG_TGT_ARCH%"=="x64" exit /b 2',
                 'set "CL="', 'set "_CL_="', 'set "LINK="', 'set "_LINK_="', 'set "ERRORLEVEL="',
                 subprocess.list2cmdline(command), "exit /b %ERRORLEVEL%"]
        recipe.write_text("\n".join(lines) + "\n", encoding="ascii")
        commands = [("compile-native", f'"{command_processor}" /d /s /c ""{recipe}""', None, None)]
    else:
        environment = {"PATH": "/usr/bin:/bin", "HOME": str(args.output), "TMPDIR": str(temporary),
                       "LANG": "C", "LC_ALL": "C", "SDKROOT": str(args.sdk)}
        compiler_environment = environment
        executable = args.output / "registration-jvm-test"
        command = [str(args.clang), "-std=c11", "-Wall", "-Wextra", "-Werror", "-pedantic", "-isysroot", str(args.sdk),
                   "-I" + str(args.jdk / "include"), "-I" + str(args.jdk / "include/darwin")]
        commands = [("compile-native", command + [str(path) for path in c_inputs] + ["-o", str(executable)], b"", b"")]
    modes = ("success", "pending", "address", "missing-class")
    for mode in modes:
        commands.append((mode, [str(executable), str(jvm),
                               str(empty_classes if mode == "missing-class" else copied_classes), mode],
                         f"PASS real-development-JDK21-registration {mode}; no Windows storage or loader\n".encode(), b""))
    module_classes = args.output / "test-module-classes"
    if args.ffm:
        module_classes.mkdir()
        commands.append(("compile-ffm", [str(javac), "-J-Xmx256m", "--release", "21",
                         "--enable-preview", "-proc:none", "-encoding", "UTF-8", "-Xlint:all,-preview", "-Werror",
                         "-d", str(module_classes)] + [str(path) for path in java_sources], b"",
                         b"Note: Some input files use preview features of Java SE 21.\n"
                         b"Note: Recompile with -Xlint:preview for details.\n"))
        for mode in ("ffm-success", "ffm-address", "ffm-missing-class"):
            commands.append((mode, [str(executable), str(jvm),
                             str(empty_classes if mode == "ffm-missing-class" else copied_classes),
                             mode, str(module_classes)],
                             f"PASS real-development-JDK21-registration {mode}; no Windows storage or loader\n".encode(), b""))
    module_before = None
    executable_before = None
    results = []
    for index, (case, command, expected_out, expected_err) in enumerate(commands):
        outcome = run_command(command, args.output,
                              compiler_environment if case == "compile-native" else environment, index)
        outcome["case"] = case
        # -Xcheck:jni warnings are failures, including those the JVM writes to stdout.
        logs = [(args.output / f"{index}-{stream}.log").read_bytes() for stream in ("stdout", "stderr")]
        # Windows tools use CRLF; preserve raw logs and normalize only those exact line endings.
        compared = [log.replace(b"\r\n", b"\n") for log in logs] if windows else logs
        outcome["cleanOutput"] = (expected_out is None or compared[0] == expected_out) and (
            expected_err is None or compared[1] == expected_err) and not (
            outcome["outputExceeded"] or outcome["captureFailed"] or outcome["timedOut"]
        ) and outcome["finalizationCompleted"]
        if case == "compile-native" and outcome["exitCode"] == 0 and outcome["cleanOutput"]:
            executable_before = digest(executable)
        if case == "compile-ffm" and outcome["exitCode"] == 0 and outcome["cleanOutput"]:
            module_before = {str(path): digest(path) for path in sorted(module_classes.rglob("*.class"))}
        results.append(outcome)
        if outcome["exitCode"] != 0 or not outcome["cleanOutput"]:
            break
    after = {str(path): digest(path) for path in inputs}
    unchanged = before == after
    executable_unchanged = executable_before is not None and executable.is_file() and digest(executable) == executable_before
    if windows:
        unchanged = unchanged and hosted_windows_binding(repository, args) == binding
    module_after = {str(path): digest(path) for path in sorted(module_classes.rglob("*.class"))} if args.ffm else None
    module_unchanged = not args.ffm or bool(module_before) and module_before == module_after
    receipt = {
        "scope": "REAL_WINDOWS_X64_DEVELOPMENT_JDK21_FFM_JNI_NOT_PROFILE_OR_INSTALLED_RUNTIME" if windows else
                 "REAL_MAC_DEVELOPMENT_JDK21_JNI_REGISTRATION_NOT_WINDOWS_STORAGE_OR_INSTALLED_RUNTIME",
        "hostedBinding": binding,
        "executableUnchanged": executable_unchanged,
        "compileRecipeSha256": digest(recipe) if windows else None,
        "runtimePath": str(jvm), "runtimeInputSha256": before[str(jvm)],
        "runtimeResolution": "Exact supplied JDK DLL path; SYSTEM32 plus selected JDK bin; no preloaded jvm"
                             if windows else "Explicit selected development JDK dylib",
        "nativeStorage": "NOT_PERFORMED", "productionAvailable": False,
        "ffmConnection": args.ffm, "ffmModule": module if args.ffm else None,
        "ffmScope": "TEST_OWNED_VM_AND_STATIC_SYMBOLS_NOT_LOAD_AUTHORITY" if args.ffm else "NOT_PERFORMED",
        "moduleClasses": module_before, "moduleClassesUnchanged": module_unchanged,
        "inputs": before, "inputsUnchanged": unchanged, "environment": environment,
        "compilerEnvironment": compiler_environment,
        "classBinding": "Copied actual existing Gradle outputs; source hashes are observations, not a rebuild receipt",
        "toolBinding": "Selected image/input hashes, not full compiler dependency provenance or production authority",
        "processScope": "Bounded same-user test child; not Foundation whole-invocation supervisor acceptance",
        "results": results,
        "passed": unchanged and executable_unchanged and module_unchanged and len(results) == len(commands) and
                  all(result["exitCode"] == 0 and result["cleanOutput"] for result in results),
    }
    if executable.is_file():
        receipt["executableSha256"] = digest(executable)
    with (args.output / "result.json").open("x") as target:
        json.dump(receipt, target, indent=2)
        target.write("\n")
    print(json.dumps({"passed": receipt["passed"], "evidence": str(args.output / "result.json")}))
    return 0 if receipt["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
