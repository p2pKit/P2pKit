#!/usr/bin/env python3
"""Compile a fresh deny-storage DLL fixture; never execute, package or authorize it."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import time
import traceback

SCOPE = "TEST_ONLY_DENY_STORAGE_NOT_PACKAGED"
MAXIMUM_DLL = 32 * 1024 * 1024
SOURCE = Path(__file__).resolve().parents[2]
ROOT = SOURCE.parents[3]
INPUT_NAMES = ("profile_policy.c", "profile_jni.c", "profile_jni_registration.c", "tests/jvm/deny_storage.c")
HEADER_NAMES = ("profile_policy.h", "profile_win32.h", "profile_jni_registration.h")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def regular(path):
    info = path.lstat()
    require(stat.S_ISREG(info.st_mode) and not path.is_symlink() and
            not (getattr(info, "st_file_attributes", 0) & 0x400), "Expected an original regular input/output file")
    return info


def remaining(progress, phase_limit):
    available = progress["deadline"] - time.monotonic()
    if available <= 0:
        progress["timeout"] = "CUMULATIVE"
        raise TimeoutError("Fixture compiler cumulative budget exhausted")
    return min(phase_limit, available)


def observation(progress):
    return {"stage": progress["stage"], "timeout": progress["timeout"], "budgetSeconds": 150,
            "elapsedSeconds": round(time.monotonic() - progress["started"], 6)}


def digest(path, progress, maximum=64 * 1024 * 1024):
    remaining(progress, 150)
    info = regular(path)
    require(0 < info.st_size <= maximum, "Compiler input/output exceeds its bound")
    value = hashlib.sha256()
    count = 0
    with path.open("rb") as source:
        while True:
            remaining(progress, 150)
            block = source.read(65536)
            if not block:
                break
            remaining(progress, 150)
            count += len(block)
            require(count <= maximum, "Compiler input/output grew beyond its bound")
            value.update(block)
    remaining(progress, 150)
    require(count == info.st_size, "Compiler input/output length changed")
    return {"bytes": count, "sha256": value.hexdigest()}


def command_path(path):
    text = str(path)
    require(path.is_absolute() and text and len(text) < 1024 and
            all(32 <= ord(char) < 127 and char not in '\"%!^&|<>' for char in text),
            "Unsupported fixed Windows compiler path")
    return text


def quoted(value):
    require(value and all(32 <= ord(char) < 127 and char not in '\"%!^&|<>' for char in value),
            "Unsupported fixed compiler argument")
    # Quote every argument, including paths containing parentheses but no spaces. No caller flags are accepted.
    require(not value.endswith("\\"), "Unsupported trailing separator in compiler argument")
    return '"' + value + '"'


def git(progress, *arguments):
    limit = remaining(progress, 15)
    try:
        result = subprocess.run(["git", *arguments], cwd=ROOT, stdin=subprocess.DEVNULL,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=limit, check=False)
    except subprocess.TimeoutExpired:
        progress["timeout"] = "CUMULATIVE" if limit < 15 else "PHASE"
        raise
    remaining(progress, 150)
    require(result.returncode == 0 and len(result.stdout) <= 1024 * 1024 and len(result.stderr) <= 65536,
            "Bounded source observation failed")
    return result.stdout


def source_state(progress):
    source = git(progress, "rev-parse", "HEAD").decode("ascii").strip()
    tree = git(progress, "rev-parse", "HEAD^{tree}").decode("ascii").strip()
    status = git(progress, "status", "--porcelain=v1", "--untracked-files=all")
    require(re.fullmatch("[0-9a-f]{40}", source) and re.fullmatch("[0-9a-f]{40}", tree),
            "Invalid original Git source/tree")
    return {"source": source, "tree": tree, "sourceDirty": bool(status),
            "statusBytes": len(status), "statusSha256": hashlib.sha256(status).hexdigest()}


def compile_fixture(progress):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--jdk17", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    require(sys.platform == "win32", "This fixed compiler fixture requires actual Windows")
    require(args.jdk17.is_absolute() and args.output.is_absolute() and ".." not in args.output.parts,
            "Compiler fixture paths must be explicit and absolute")
    jdk = args.jdk17.resolve(strict=True)
    output = args.output.resolve()
    require(not output.exists() and output.parent.is_dir(), "Fixture output must be a new directory")
    # The maintained checker uses a fresh report attempt. Never permit a fixture to replace resources,
    # the packaged native artifact, a source directory or an installer input in this checkout.
    reports = ROOT / "build/reports/rpc-windows-loader-jdk21"
    require(not output.is_relative_to(ROOT) or output.is_relative_to(reports),
            "In-checkout fixture output must remain in adapter test reports")
    for path in (jdk, output, ROOT, SOURCE):
        command_path(path)
    release = jdk / "release"
    regular(release)
    require(release.stat().st_size <= 65536 and
            any(line.startswith('JAVA_VERSION="17.') for line in release.read_text(encoding="utf-8").splitlines()),
            "The fixed fixture producer requires the selected JDK17 headers")
    source_files = [SOURCE / name for name in INPUT_NAMES + HEADER_NAMES]
    source_files += [Path(__file__).resolve(), jdk / "include/jni.h", jdk / "include/win32/jni_md.h", release]
    source_inputs = {str(path): digest(path, progress) for path in source_files}
    original = source_state(progress)

    # Normal compiler/tool selection only, not OS-bootstrap or installed-runtime authority.
    system = Path(os.environ["SystemRoot"]).resolve(strict=True)
    system32 = system / "System32"
    command_processor = system32 / "cmd.exe"
    locator = Path(os.environ["ProgramFiles(x86)"]) / "Microsoft Visual Studio/Installer/vswhere.exe"
    locator = locator.resolve(strict=True)
    for path in (system, command_processor, locator):
        command_path(path)
    selected_tools = {str(path): digest(path, progress) for path in (command_processor, locator)}
    environment = {"PATH": ";".join(str(path) for path in (system32,
                       system32 / "WindowsPowerShell/v1.0", system32 / "Wbem")),
                   "SystemRoot": str(system), "WINDIR": str(system),
                   "ComSpec": str(command_processor), "SystemDrive": system.drive, "VSLANG": "1033",
                   # Microsoft STL CI uses this supported optional setup-telemetry opt-out. Apply it
                   # only to our reconstructed child environment, never machine/user configuration.
                   "VSCMD_SKIP_SENDTELEMETRY": "1"}
    # VS setup may query these fixed installed-tool locations; no credentials, Java overrides or compiler
    # response flags are inherited. Actual compiler flags are cleared again inside each batch child.
    for name in ("ProgramFiles", "ProgramFiles(x86)", "ProgramW6432"):
        value = Path(os.environ[name]).resolve(strict=True)
        environment[name] = command_path(value)
    remaining(progress, 150)
    output.mkdir(mode=0o700)
    progress["output"] = output
    temporary = output / "tmp"
    temporary.mkdir()
    environment.update({"TEMP": str(temporary), "TMP": str(temporary), "USERPROFILE": str(output),
                        "APPDATA": str(output), "LOCALAPPDATA": str(output)})
    records = []
    receipt = {"schema": 1, "scope": SCOPE, **original, "result": "FAIL",
               "inputScope": "SELECTED_DIRECT_INPUTS_NOT_TRANSITIVE_SDK_PROVENANCE",
               "vsDevCmdEnvironment": {"VSCMD_SKIP_SENDTELEMETRY": environment["VSCMD_SKIP_SENDTELEMETRY"]},
               "sources": source_inputs, "tools": selected_tools, "commands": records,
               "nativeExecution": "NOT_PERFORMED", "profileBackend": "NOT_LINKED", "packaging": "NOT_PERFORMED"}

    def run(label, command, timeout=60):
        # The canonical CI component's existing outer supervisor owns descendants and aggregate output.
        # These are fixed trusted-tool invocations, not an installed-app/process-retirement qualification.
        # Raw compiler output stays in this new private test directory; bounded reads never expose it publicly.
        stdout = output / (label + "-stdout.log")
        stderr = output / (label + "-stderr.log")
        record = {"name": label, "command": command, "exit": None, "timedOut": False,
                  "timeoutSeconds": None}
        records.append(record)
        with stdout.open("xb") as out, stderr.open("xb") as err:
            try:
                limit = remaining(progress, timeout)
                record["timeoutSeconds"] = limit
                result = subprocess.run(command, cwd=output, env=environment, stdin=subprocess.DEVNULL,
                                        stdout=out, stderr=err, timeout=limit, check=False)
                record["exit"] = result.returncode
            except subprocess.TimeoutExpired:
                record["timedOut"] = True
                progress["timeout"] = "CUMULATIVE" if limit < timeout else "PHASE"
                raise
            except TimeoutError:
                record["timedOut"] = True
                raise
        remaining(progress, 150)
        require(stdout.stat().st_size <= 1024 * 1024 and stderr.stat().st_size <= 65536,
                "Fixed compiler output exceeded its expected bound")
        require(record["exit"] == 0, "Fixed compiler command failed")
        return stdout.read_text(encoding="utf-8", errors="strict").replace("\r\n", "\n")

    def batch(label, lines):
        path = output / (label + ".cmd")
        with path.open("x", encoding="ascii", newline="\r\n") as target:
            target.write("\n".join(lines) + "\n")
        command_path(path)
        # Fixed batch-file pathname only; the command language receives no caller-selected switches/body.
        command = quoted(str(command_processor)) + ' /d /s /c "' + quoted(str(path)) + '"'
        return run(label, command)

    try:
        progress["stage"] = "LOCATE"
        installation = run("locate-msvc", [str(locator), "-latest", "-products", "*", "-requires",
                                           "Microsoft.VisualStudio.Component.VC.Tools.x86.x64",
                                           "-property", "installationPath"], 15).strip()
        require(installation and "\n" not in installation, "Installed MSVC selection was ambiguous")
        developer = Path(installation) / "Common7/Tools/VsDevCmd.bat"
        command_path(developer)
        selected_tools[str(developer)] = digest(developer, progress)
        setup = ["@echo off", "setlocal DisableDelayedExpansion", 'set "INCLUDE="', 'set "LIB="',
                 'set "LIBPATH="', 'set "CL="', 'set "_CL_="', 'set "LINK="', 'set "_LINK_="',
                 'set "ERRORLEVEL="', 'call ' + quoted(str(developer)) + " -arch=x64 -host_arch=x64",
                 "if errorlevel 1 exit /b 2", 'if /i not "%VSCMD_ARG_TGT_ARCH%"=="x64" exit /b 2',
                 'set "CL="', 'set "_CL_="', 'set "LINK="', 'set "_LINK_="', 'set "ERRORLEVEL="',
                 'cd /d ' + quoted(str(output)), 'if errorlevel 1 exit /b 2']
        progress["stage"] = "INVENTORY"
        inventory = batch("compiler-inventory", setup + [
            "echo P2PKIT_VCTOOLS=%VCToolsInstallDir%", "echo P2PKIT_VCVERSION=%VCToolsVersion%",
            "echo P2PKIT_SDK=%WindowsSdkDir%", "echo P2PKIT_SDKVERSION=%WindowsSDKVersion%", "exit /b 0"])
        fields = {}
        for line in inventory.splitlines():
            if line.startswith("P2PKIT_"):
                name, value = line.split("=", 1)
                require(name not in fields and value, "Compiler inventory is incomplete or duplicated")
                fields[name] = value
        require(set(fields) == {"P2PKIT_VCTOOLS", "P2PKIT_VCVERSION", "P2PKIT_SDK", "P2PKIT_SDKVERSION"},
                "Compiler inventory differs from the fixed contract")
        tools = Path(fields["P2PKIT_VCTOOLS"]).resolve(strict=True)
        sdk = Path(fields["P2PKIT_SDK"]).resolve(strict=True)
        require(re.fullmatch(r"[0-9.]+", fields["P2PKIT_VCVERSION"]) and
                re.fullmatch(r"[0-9.]+\\?", fields["P2PKIT_SDKVERSION"]), "Invalid selected toolchain version")
        compiler = tools / "bin/Hostx64/x64/cl.exe"
        linker = tools / "bin/Hostx64/x64/link.exe"
        for path in (tools, sdk, compiler, linker):
            command_path(path)
        for path in (compiler, linker):
            selected_tools[str(path)] = digest(path, progress)
        receipt["toolchain"] = {"vcTools": str(tools), "vcVersion": fields["P2PKIT_VCVERSION"],
                                 "sdk": str(sdk), "sdkVersion": fields["P2PKIT_SDKVERSION"]}
        recipe = [str(compiler), "/nologo", "/Bv", "/std:c11", "/W4", "/WX", "/O2", "/MT", "/GS", "/sdl",
                  "/guard:cf", "/D_WIN32_WINNT=0x0A00", "/I" + str(jdk / "include"),
                  "/I" + str(jdk / "include/win32"), "/LD", *[str(SOURCE / name) for name in INPUT_NAMES],
                  "/link", "/OUT:p2pkit-windows-profile.dll", "/MACHINE:X64", "/DYNAMICBASE", "/HIGHENTROPYVA",
                  "/NXCOMPAT", "/GUARD:CF", "/INCREMENTAL:NO", "/MANIFEST:EMBED", "/OPT:REF", "/OPT:ICF",
                  "kernel32.lib"]
        receipt["compilerArguments"] = recipe
        # Pin the selected version in the second setup too; don't silently compile using another VC/SDK.
        compile_setup = setup + [
            'if not "%VCToolsVersion%"=="' + fields["P2PKIT_VCVERSION"] + '" exit /b 2',
            'if not "%WindowsSDKVersion%"=="' + fields["P2PKIT_SDKVERSION"] + '" exit /b 2',
            'if /i not "%VCToolsInstallDir%"=="' + fields["P2PKIT_VCTOOLS"] + '" exit /b 2',
            'if /i not "%WindowsSdkDir%"=="' + fields["P2PKIT_SDK"] + '" exit /b 2',
            'set "PATH=' + str(compiler.parent) + ';%PATH%"']
        progress["stage"] = "COMPILE"
        batch("compile-dll", compile_setup + [" ".join(quoted(item) for item in recipe), "exit /b %ERRORLEVEL%"])
        progress["stage"] = "VERIFY"
        current = source_state(progress)
        require(current == original, "Source state changed while compiling the fixture")
        require(all(digest(Path(path), progress) == value for path, value in source_inputs.items()),
                "Original direct source/header bytes changed while compiling")
        require(all(digest(Path(path), progress) == value for path, value in selected_tools.items()),
                "Selected compiler/tool bytes changed while compiling")
        dll = output / "p2pkit-windows-profile.dll"
        metadata = digest(dll, progress, MAXIMUM_DLL)
        require(metadata["bytes"] >= 512, "Compiled fixture DLL is too short")
        receipt["dll"] = {"path": str(dll), "name": dll.name, **metadata}
        remaining(progress, 150)
        progress["stage"] = "COMPLETE"
        receipt["result"] = "PASS"
        print("WINDOWS_TEST_DLL_COMPILE_PASS scope=" + SCOPE)
    finally:
        receipt["diagnostics"] = observation(progress)
        with (output / "compiler-receipt.json").open("x", encoding="utf-8") as target:
            target.write(json.dumps(receipt, indent=2, sort_keys=True) + "\n")


def main():
    # One compiler-only total deadline includes preflight, setup, Git and hash observations. The
    # caller's separate retirement allowance does not extend compiler work or any native test budget.
    started = time.monotonic()
    progress = {"started": started, "deadline": started + 150, "stage": "PREFLIGHT",
                "timeout": "NONE", "output": None}
    try:
        compile_fixture(progress)
        return 0
    except Exception:
        detail = traceback.format_exc()
        output = progress["output"]
        if output is not None:
            # Only our successfully create-only output may receive diagnostics. Preserve any existing
            # producer receipt; a reporting failure must not replace the original compiler failure.
            try:
                with (output / "compiler-failure-detail.log").open("x", encoding="utf-8") as target:
                    target.write(detail)
                path = output / "compiler-receipt.json"
                if not path.exists():
                    receipt = {"schema": 1, "scope": SCOPE, "result": "FAIL",
                               "diagnostics": observation(progress), "nativeExecution": "NOT_PERFORMED",
                               "profileBackend": "NOT_LINKED", "packaging": "NOT_PERFORMED"}
                    with path.open("x", encoding="utf-8") as target:
                        target.write(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
            except Exception:
                pass
        # These values are fixed internal labels, never an exception message, command, path or identifier.
        print("WINDOWS_TEST_DLL_COMPILE_REFUSED stage=" + progress["stage"] +
              " timeout=" + progress["timeout"], file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
