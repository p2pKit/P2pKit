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
            all(32 <= ord(char) < 127 and char not in '\"%!^&|<>;' for char in text),
            "Unsupported fixed Windows compiler path")
    return text


def directory(path):
    info = path.lstat()
    require(stat.S_ISDIR(info.st_mode) and not path.is_symlink() and
            not (getattr(info, "st_file_attributes", 0) & 0x400), "Expected an original installed-tool directory")
    return path


def version(value, components):
    require(isinstance(value, str) and len(value) <= 32 and
            re.fullmatch(r"(?:0|[1-9][0-9]{0,4})(?:\.(?:0|[1-9][0-9]{0,4})){" +
                         str(components - 1) + r"}", value), "Invalid installed toolchain version")
    parts = tuple(int(part) for part in value.split("."))
    require(all(part <= 65535 for part in parts), "Installed toolchain version exceeds its bound")
    return parts


def selected_vc(installation, progress):
    directory(installation)
    selection = installation / "VC/Auxiliary/Build/Microsoft.VCToolsVersion.default.txt"
    metadata = digest(selection, progress, 128)
    with selection.open("rb") as source:
        snapshot = source.read(129)
    require(0 < len(snapshot) <= 128, "Default MSVC version exceeds its bound")
    require(len(snapshot) == metadata["bytes"] and hashlib.sha256(snapshot).hexdigest() == metadata["sha256"],
            "Default MSVC version bytes changed before selection")
    text = snapshot.decode("ascii").strip(" \t\r\n")
    version(text, 3)
    tools = directory(installation / "VC/Tools/MSVC" / text)
    required_directories = [tools / "bin/Hostx64/x64", tools / "include", tools / "lib/x64"]
    for path in required_directories:
        directory(path)
    inputs = [selection, tools / "bin/Hostx64/x64/cl.exe", tools / "bin/Hostx64/x64/link.exe",
              tools / "include/vcruntime.h", tools / "lib/x64/libcmt.lib",
              tools / "lib/x64/libvcruntime.lib", tools / "lib/x64/oldnames.lib"]
    require(digest(selection, progress, 128) == metadata, "Default MSVC selection changed during observation")
    for path in inputs:
        regular(path)
        command_path(path)
    return {"root": tools, "version": text, "inputs": inputs}


def reconcile_sdk_roots(values):
    require(isinstance(values, list) and 1 <= len(values) <= 2, "No registered Windows SDK root")
    roots = []
    for value in values:
        require(isinstance(value, str) and value and "\x00" not in value,
                "Malformed registered Windows SDK root")
        root = Path(value)
        command_path(root)
        directory(root)  # Do not resolve away an explicitly refused registry-root reparse entry.
        root = directory(root.resolve(strict=True))
        if roots:
            require(root == roots[0], "Registered Windows SDK roots disagree")
        roots.append(root)
    return roots[0]


def registered_sdk_root():
    # Only fixed read-only registered developer-tool locations. This is not runtime/bootstrap authority.
    import winreg
    values = []
    for view in (winreg.KEY_WOW64_64KEY, winreg.KEY_WOW64_32KEY):
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows Kits\Installed Roots",
                                0, winreg.KEY_QUERY_VALUE | view) as key:
                value, kind = winreg.QueryValueEx(key, "KitsRoot10")
        except FileNotFoundError:
            continue
        require(kind == winreg.REG_SZ, "Registered Windows SDK root is not an exact string")
        values.append(value)
    return reconcile_sdk_roots(values)


def selected_sdk(root, progress):
    include = directory(root / "Include")
    available = []
    with os.scandir(include) as entries:
        for index, entry in enumerate(entries):
            remaining(progress, 150)
            require(index < 64, "Installed Windows SDK inventory exceeds its bound")
            path = directory(Path(entry.path))
            parsed = version(path.name, 4)
            require(parsed[:2] == (10, 0), "Unsupported registered Windows SDK family")
            include_parts = [path / kind for kind in ("ucrt", "shared", "um")]
            lib_parts = [root / "Lib" / path.name / kind / "x64" for kind in ("ucrt", "um")]
            binary = root / "bin" / path.name / "x64"
            inputs = [include_parts[0] / "stdio.h", include_parts[1] / "ntdef.h",
                      include_parts[2] / "Windows.h", lib_parts[0] / "libucrt.lib",
                      lib_parts[1] / "kernel32.lib"]
            required = include_parts + lib_parts + [binary] + inputs
            # Incomplete installed versions are not selected; malformed/reparsed present entries refuse.
            complete = True
            for item in required:
                if not item.exists():
                    require(not item.is_symlink(), "Reparsed incomplete Windows SDK input")
                    complete = False
                elif item in inputs:
                    regular(item)
                else:
                    directory(item)
            available.append((parsed, path.name, complete, include_parts, lib_parts, binary, inputs))
    candidates = [item for item in available if item[2]]
    require(candidates, "No complete installed Windows SDK version")
    require(len({item[0] for item in available}) == len(available), "Ambiguous installed Windows SDK versions")
    chosen = max(candidates, key=lambda item: item[0])
    return {"root": root, "version": chosen[1], "include": chosen[3], "lib": chosen[4],
            "bin": chosen[5], "inputs": chosen[6],
            "inventory": [{"version": item[1], "complete": item[2]} for item in sorted(available)]}


def child_environment(system, output, tools=None, sdk=None):
    system32 = system / "System32"
    paths = [system32]
    if tools is not None:
        require(sdk is not None, "Complete installed compiler/SDK selection required")
        paths = [tools / "bin/Hostx64/x64", sdk["bin"], system32]
    environment = {"PATH": ";".join(command_path(path) for path in paths),
                   "SystemRoot": command_path(system), "WINDIR": str(system),
                   "SystemDrive": system.drive, "VSLANG": "1033",
                   "TEMP": str(output / "tmp"), "TMP": str(output / "tmp"), "USERPROFILE": str(output),
                   "APPDATA": str(output), "LOCALAPPDATA": str(output)}
    if tools is not None:
        environment["INCLUDE"] = ";".join(command_path(path) for path in [tools / "include", *sdk["include"]])
        environment["LIB"] = ";".join(command_path(path) for path in [tools / "lib/x64", *sdk["lib"]])
    return environment


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
    locator = Path(os.environ["ProgramFiles(x86)"]) / "Microsoft Visual Studio/Installer/vswhere.exe"
    locator = locator.resolve(strict=True)
    for path in (system, locator):
        command_path(path)
    selected_tools = {str(locator): digest(locator, progress)}
    environment = child_environment(system, output)
    remaining(progress, 150)
    output.mkdir(mode=0o700)
    progress["output"] = output
    temporary = output / "tmp"
    temporary.mkdir()
    records = []
    receipt = {"schema": 1, "scope": SCOPE, **original, "result": "FAIL",
               "inputScope": "SELECTED_DIRECT_INPUTS_NOT_TRANSITIVE_SDK_PROVENANCE",
               "toolSelection": "DIRECT_REGISTERED_MSVC_SDK_NO_SETUP_SCRIPT",
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
                                        stdout=out, stderr=err, timeout=limit, check=False, shell=False)
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

    try:
        progress["stage"] = "LOCATE"
        installation = run("locate-msvc", [str(locator), "-latest", "-products", "*", "-requires",
                                           "Microsoft.VisualStudio.Component.VC.Tools.x86.x64",
                                           "-property", "installationPath"], 15).strip()
        require(installation and "\n" not in installation, "Installed MSVC selection was ambiguous")
        progress["stage"] = "INVENTORY"
        installation_path = Path(installation)
        command_path(installation_path)
        vc = selected_vc(installation_path, progress)
        tools = vc["root"]
        remaining(progress, 150)
        sdk_root = registered_sdk_root()
        sdk = selected_sdk(sdk_root, progress)
        compiler = tools / "bin/Hostx64/x64/cl.exe"
        linker = tools / "bin/Hostx64/x64/link.exe"
        for path in (tools, sdk_root, compiler, linker):
            command_path(path)
        for path in vc["inputs"] + sdk["inputs"]:
            selected_tools[str(path)] = digest(path, progress)
        environment = child_environment(system, output, tools, sdk)
        receipt["toolchain"] = {"vcTools": str(tools), "vcVersion": vc["version"],
                                 "sdk": str(sdk_root), "sdkVersion": sdk["version"],
                                 "sdkInventory": sdk["inventory"], "environment": environment}
        recipe = [str(compiler), "/nologo", "/Bv", "/std:c11", "/W4", "/WX", "/O2", "/MT", "/GS", "/sdl",
                  "/guard:cf", "/D_WIN32_WINNT=0x0A00", "/I" + str(jdk / "include"),
                  "/I" + str(jdk / "include/win32"), "/LD", *[str(SOURCE / name) for name in INPUT_NAMES],
                  "/link", "/OUT:p2pkit-windows-profile.dll", "/MACHINE:X64", "/DYNAMICBASE", "/HIGHENTROPYVA",
                  "/NXCOMPAT", "/GUARD:CF", "/INCREMENTAL:NO", "/MANIFEST:EMBED", "/OPT:REF", "/OPT:ICF",
                  "kernel32.lib"]
        receipt["compilerArguments"] = recipe
        progress["stage"] = "COMPILE"
        # Absolute executable + argv, with no command processor, setup script, ambient flags or response file.
        run("compile-dll", recipe)
        progress["stage"] = "VERIFY"
        require(selected_vc(installation_path, progress) == vc and registered_sdk_root() == sdk_root and
                selected_sdk(sdk_root, progress) == sdk, "Installed compiler/SDK selection changed")
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
