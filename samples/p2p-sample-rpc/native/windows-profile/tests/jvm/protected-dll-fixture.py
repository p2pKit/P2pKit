#!/usr/bin/env python3
"""Create-only protected development DLL reader fixture; not installation or loading authority.

Compile through the existing checker's run() and selected compiler receipt. begin() owns only the
helper, not a second Java launcher. The caller may finish_after_reader_run() ONLY after its existing
reader run has returned with process and captures retired; every exception must abandon() instead.
No destructor, EOF, timeout or failure can issue cleanup. The outer maintained supervisor still owns
uncertain descendants. No privilege, token, ACL repair, path deletion or candidate loading is here.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path, PureWindowsPath
import re
import subprocess
import sys
import threading
import time

HERE = Path(__file__).resolve().parent
SCOPE = "DEVELOPMENT_PROTECTED_DLL_READ_FIXTURE_NOT_INSTALLED_AUTHORITY"
COMPILE_SCOPE = "DEVELOPMENT_PROTECTED_READER_HELPER_NOT_INSTALLED_AUTHORITY"
DLL = "p2pkit-windows-profile.dll"
HELPER = "protected-dll-fixture.exe"
MAXIMUM_DLL = 32 * 1024 * 1024
MAXIMUM_CAPTURE = 16384
PIN = r"[0-9a-f]{64}"
REVISION = r"[0-9a-f]{40}"
NONCE = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
FIELDS = {"schema", "scope", "phase", "stage", "error", "nonce", "path", "source", "tree", "sha256",
          "bytes", "created", "owner", "volume", "directoryId", "fileId"}
_OWNERS = []  # Keep original processes/captures reachable on any unconfirmed return, never auto-delete.
FAILURE_SCOPE = "CLOSED_FIXTURE_FAILURE_DIAGNOSTIC_NOT_CLEANUP_OR_AUTHORITY"


def require(value, message):
    if not value:
        raise ValueError(message)


def matches(pattern, value):
    return isinstance(value, str) and re.fullmatch(pattern, value) is not None


def object_pairs(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "Duplicate fixture receipt field")
        result[key] = value
    return result


def parse(data, maximum):
    require(isinstance(data, bytes) and 0 < len(data) <= maximum, "Unbounded fixture receipt")
    value = json.loads(data.decode("ascii"), object_pairs_hook=object_pairs)
    require(isinstance(value, dict), "Fixture receipt is not an object")
    return value


def path_valid(value):
    if not isinstance(value, str) or not 4 <= len(value) < 260 or not re.fullmatch(r"[A-Za-z]:\\[A-Za-z0-9 ._\\-]+", value):
        return False
    for component in value[3:].split("\\"):
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9 ._-]*", component) or component.endswith((".", " ")):
            return False
        stem = component.split(".", 1)[0].rstrip(" ").upper()
        if stem in ("CON", "PRN", "AUX", "NUL") or re.fullmatch(r"(?:COM|LPT)[1-9]", stem):
            return False
    return True


def validate_ready(row, compiler):
    require(isinstance(row, dict) and set(row) == FIELDS and type(row["schema"]) is int and row["schema"] == 1 and
            row["scope"] == SCOPE and row["phase"] == row["stage"] == "READY" and
            type(row["error"]) is int and row["error"] == 0 and row["created"] is True and
            row["owner"] == "BUILTIN_ADMINISTRATORS", "Invalid protected fixture READY")
    require(matches(NONCE, row["nonce"]) and path_valid(row["path"]), "Invalid fixture locator/nonce")
    parts = PureWindowsPath(row["path"]).parts
    require(len(parts) >= 4 and parts[-2] == "P2pKit-Rpc-ReadFixture-" + row["nonce"] and parts[-1] == DLL,
            "Fixture locator does not match its original nonce")
    for key, pattern in (("volume", r"[0-9a-f]{16}"), ("directoryId", r"[0-9a-f]{32}"), ("fileId", r"[0-9a-f]{32}")):
        require(matches(pattern, row[key]) and int(row[key], 16) != 0, "Invalid original NTFS identity")
    require(row["fileId"] != row["directoryId"], "File and directory identity must be distinct")
    require(type(row["bytes"]) is int and 512 <= row["bytes"] <= MAXIMUM_DLL and
            row["bytes"] == compiler["dll"]["bytes"] and matches(PIN, row["sha256"]) and
            row["sha256"] == compiler["dll"]["sha256"] and row["source"] == compiler["source"] and
            row["tree"] == compiler["tree"] and matches(REVISION, row["source"]) and matches(REVISION, row["tree"]),
            "Fixture differs from original maintained compiler observation")
    require(row["path"] != compiler["dll"]["path"], "Protected fixture cannot replace compiler output")
    return dict(row)


def validate_cleaned(row, original):
    require(isinstance(row, dict) and set(row) == FIELDS and row["phase"] == row["stage"] == "CLEANED" and
            type(row["error"]) is int and row["error"] == 0 and
            all(row[key] == original[key] and type(row[key]) is type(original[key])
                for key in FIELDS - {"phase", "stage", "error"}), "Cleanup is not the original fixture receipt")
    return dict(row)


def failed_cleanup_projection(lines, original, compiler, code):
    """Only terminal, fully bound LEFT records may contribute closed stage/error labels."""
    require(type(code) is int and code in (1, 3), "Expected failed terminal helper")
    require(len(lines) == 2 and all(line.endswith(b"\n") for line in lines), "Incomplete terminal records")
    require(validate_ready(parse(lines[0], MAXIMUM_CAPTURE), compiler) == original, "Original READY changed")
    row = parse(lines[1], MAXIMUM_CAPTURE)
    require(set(row) == FIELDS and row["phase"] == "LEFT" and
            type(row["error"]) is int and 0 <= row["error"] <= 65535 and
            all(row[key] == original[key] and type(row[key]) is type(original[key])
                for key in FIELDS - {"phase", "stage", "error"}), "Unbound terminal LEFT record")
    require((code == 1 and row["stage"] in ("READY", "DELETE_FILE", "DELETE_DIRECTORY", "QUERY_DIRECTORY_ID",
                                           "OPEN_DIRECTORY_ID", "DISPOSE_DIRECTORY", "QUERY_DIRECTORY_PATH",
                                           "OPEN_DIRECTORY_PATH", "VERIFY_DIRECTORY_PATH")) or
            (code == 3 and row["stage"] == "PRESERVED" and row["error"] == 0), "Unexpected terminal outcome")
    return row["stage"], row["error"]


def toolkit():
    # One maintained source-relative module, not a caller-supplied module or retired runner import.
    spec = importlib.util.spec_from_file_location("protected_fixture_compiler", HERE / "build-test-dll.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def progress():
    started = time.monotonic()
    return {"started": started, "deadline": started + 150, "stage": "PREFLIGHT", "timeout": "NONE"}


def read_compiler(path, tools, clock):
    tools.regular(path)
    require(path.name == "compiler-receipt.json" and path.is_absolute() and path.stat().st_size <= 256 * 1024,
            "Expected original bounded maintained compiler receipt")
    with path.open("rb") as source:
        row = parse(source.read(256 * 1024 + 1), 256 * 1024)
    require(row.get("schema") == 1 and type(row["schema"]) is int and row.get("scope") == tools.SCOPE and
            row.get("result") == "PASS" and row.get("nativeExecution") == row.get("packaging") == "NOT_PERFORMED" and
            row.get("profileBackend") == "NOT_LINKED" and row.get("sourceDirty") is False and
            type(row.get("statusBytes")) is int and row["statusBytes"] == 0 and
            row.get("statusSha256") == hashlib.sha256(b"").hexdigest(), "Compiler receipt is not clean test-only evidence")
    observed = tools.source_state(clock)
    require(all(row.get(key) == value for key, value in observed.items()), "Compiler source observation changed")
    dll = row.get("dll")
    require(isinstance(dll, dict) and set(dll) == {"path", "name", "bytes", "sha256"} and dll["name"] == DLL and
            dll["path"] == str(path.parent / DLL) and type(dll["bytes"]) is int and 512 <= dll["bytes"] <= MAXIMUM_DLL and
            matches(PIN, dll["sha256"]) and tools.digest(Path(dll["path"]), clock, MAXIMUM_DLL) ==
            {"bytes": dll["bytes"], "sha256": dll["sha256"]}, "Original compiler DLL changed")
    for group in ("sources", "tools"):
        require(isinstance(row.get(group), dict) and 1 <= len(row[group]) <= 64, "Unbounded selected compiler inputs")
        for name, metadata in row[group].items():
            require(isinstance(metadata, dict) and set(metadata) == {"bytes", "sha256"} and
                    type(metadata["bytes"]) is int and matches(PIN, metadata["sha256"]), "Invalid compiler input binding")
            tools.command_path(Path(name))
            require(tools.digest(Path(name), clock) == metadata, "Selected direct compiler input changed")
    return row



def selected_headers(roots, tools):
    # Search only the three original selected SDK include roots, never scan a namespace or PATH.
    require(isinstance(roots, list) and len(roots) == 3, "Expected exact selected SDK include roots")
    selected = []
    for name in ("aclapi.h", "bcrypt.h", "shlobj.h"):
        found = []
        for root in roots:
            candidate = root / name
            try:
                tools.regular(candidate)
            except FileNotFoundError:
                continue
            found.append(candidate)  # Present but reparsed/invalid is refused by regular(), not skipped.
        require(len(found) == 1, "Required direct SDK header is absent or ambiguous")
        selected.append(found[0])
    return selected


def compile_helper(compiler_path, output):
    require(sys.platform == "win32", "The protected fixture compiler requires actual Windows")
    tools, clock = toolkit(), progress()
    compiler = read_compiler(compiler_path, tools, clock)
    require(output.is_absolute() and ".." not in output.parts and not output.exists() and output.parent.is_dir(),
            "Protected helper output must be create-only")
    reports = tools.ROOT / "build/reports/rpc-windows-loader-jdk21"
    require(not output.is_relative_to(tools.ROOT) or output.is_relative_to(reports), "Helper output is not a test report")
    tools.command_path(output)
    selection = compiler["toolchain"]
    vc, sdk = Path(selection["vcTools"]), Path(selection["sdk"])
    version = selection["sdkVersion"]
    tools.version(selection["vcVersion"], 3)
    tools.version(version, 4)
    selected_sdk = {"bin": sdk / "bin" / version / "x64",
                    "include": [sdk / "Include" / version / kind for kind in ("ucrt", "shared", "um")],
                    "lib": [sdk / "Lib" / version / kind / "x64" for kind in ("ucrt", "um")]}
    system = Path(selection["environment"]["SystemRoot"])
    require(selection["environment"] == tools.child_environment(system, compiler_path.parent, vc, selected_sdk),
            "Unexpected compiler environment")
    cl = vc / "bin/Hostx64/x64/cl.exe"
    require(compiler["compilerArguments"][0] == str(cl) and str(cl) in compiler["tools"] and
            str(vc / "bin/Hostx64/x64/link.exe") in compiler["tools"], "Compiler executable is not the selected original")
    libraries = ("kernel32.lib", "advapi32.lib", "shell32.lib", "ole32.lib", "uuid.lib", "bcrypt.lib")
    inputs = [HERE / "protected-dll-fixture.c", Path(__file__).resolve(), HERE / "build-test-dll.py"]
    inputs += [sdk / "Lib" / version / "um/x64" / name for name in libraries]
    inputs += selected_headers(selected_sdk["include"], tools)
    bindings = {str(path): tools.digest(path, clock) for path in inputs}
    output.mkdir(mode=0o700)
    (output / "tmp").mkdir()
    environment = tools.child_environment(system, output, vc, selected_sdk)
    command = [str(cl), "/nologo", "/std:c11", "/W4", "/WX", "/O2", "/MT", "/GS", "/sdl", "/guard:cf",
               "/D_WIN32_WINNT=0x0A00", str(inputs[0]), "/link", "/OUT:" + HELPER, "/MACHINE:X64", "/DYNAMICBASE",
               "/HIGHENTROPYVA", "/NXCOMPAT", "/GUARD:CF", "/INCREMENTAL:NO", "/MANIFEST:EMBED", "/OPT:REF",
               "/OPT:ICF", *libraries]
    receipt = {"schema": 1, "scope": COMPILE_SCOPE, "result": "FAIL", "source": compiler["source"],
               "tree": compiler["tree"], "compilerReceipt": tools.digest(compiler_path, clock, 256 * 1024),
               "inputs": bindings, "command": command, "nativeExecution": "NOT_PERFORMED",
               "stage": "COMPILE", "failureKind": "NONE"}
    try:
        with (output / "compile-stdout.log").open("xb") as out, (output / "compile-stderr.log").open("xb") as err:
            result = subprocess.run(command, cwd=output, env=environment, stdin=subprocess.DEVNULL, stdout=out,
                                    stderr=err, timeout=tools.remaining(clock, 60), check=False, shell=False)
        receipt["stage"] = "COMPILE_VERIFY"
        require(result.returncode == 0, "Fixed protected-fixture compiler failed")
        require((output / "compile-stdout.log").stat().st_size <= 1024 * 1024 and
                (output / "compile-stderr.log").stat().st_size <= 65536, "Unbounded compiler capture")
        receipt["stage"] = "INPUT_RECHECK"
        require(read_compiler(compiler_path, tools, clock) == compiler and
                all(tools.digest(Path(path), clock) == value for path, value in bindings.items()),
                "Original fixture compiler inputs changed")
        receipt["stage"] = "OUTPUT_VERIFY"
        receipt["helper"] = {"name": HELPER, **tools.digest(output / HELPER, clock, MAXIMUM_DLL)}
        receipt["result"] = "PASS"
        receipt["stage"] = "COMPLETE"
    except BaseException as error:
        receipt["failureKind"] = ("TIMEOUT" if isinstance(error, (TimeoutError, subprocess.TimeoutExpired)) else
                                  "INPUT_MISSING" if isinstance(error, FileNotFoundError) else
                                  "REFUSED" if isinstance(error, ValueError) else
                                  "OS_ERROR" if isinstance(error, OSError) else "UNEXPECTED")
        raise
    finally:
        with (output / "helper-receipt.json").open("x", encoding="ascii") as target:
            target.write(json.dumps(receipt, sort_keys=True, indent=2) + "\n")


class ProtectedDllFixture:
    """Original helper owner. A successful existing reader run, not a boolean flag, precedes finish."""
    def __init__(self, output, compiler):
        self._thread = threading.get_ident()
        self._state = "STARTING"
        self._output, self._compiler = output, compiler
        self._process = self._out = self._err = None
        self._ready = None
        self._failure = self._diagnostic_failure = None
        _OWNERS.append(self)  # Root before Popen/capture effects, including uncertain Popen failure.

    def _guard(self):
        require(threading.get_ident() == self._thread, "Protected fixture owner is thread-confined")

    @property
    def receipt(self):
        self._guard()
        require(self._ready is not None, "Protected fixture has no READY observation")
        return dict(self._ready)

    @property
    def path(self):
        self._guard()
        require(self._state == "READY", "Protected fixture is not available for its original reader")
        return self._ready["path"]

    def _lines(self):
        values = []
        for name in ("helper-stdout.log", "helper-stderr.log"):
            with (self._output / name).open("rb") as source:
                value = source.read(MAXIMUM_CAPTURE + 1)
            require(len(value) <= MAXIMUM_CAPTURE, "Unbounded protected fixture capture")
            values.append(value)
        require(not values[1], "Protected fixture emitted unexpected stderr")
        require(values[0].count(b"\n") <= 2, "Extra protected fixture record")
        return values[0].splitlines(keepends=True)

    def _retire_captures(self):
        require(self._process is not None and self._process.poll() is not None, "Helper retirement is unconfirmed")
        self._out.close()
        self._err.close()

    def _record_failure(self):
        # Report paths are public commitments: use only this finite stage set and bounded Win32 number.
        # Unknown/native-ongoing captures are NEVER read; UNKNOWN/0 means no trusted error observation.
        stage, error = "UNKNOWN", 0
        code = self._process.poll() if self._process is not None else None
        if code is not None and self._out is not None and self._err is not None and self._out.closed and self._err.closed:
            try:
                stage, error = failed_cleanup_projection(self._lines(), self._ready, self._compiler, code)
            except Exception:
                pass  # Invalid protocol cannot export arbitrary strings, identities or exception text.
        name = "protected-fixture-failure-" + stage + "-" + str(error) + ".json"
        row = {"schema": 1, "scope": FAILURE_SCOPE, "stage": stage, "error": error}
        with (self._output / name).open("x", encoding="ascii") as target:
            target.write(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n")

    def finish_after_reader_run(self):
        """Call only after existing run() confirms original Java exit AND closes its original captures."""
        self._guard()
        require(self._state == "READY", "Cleanup is one-shot and cannot follow uncertainty")
        self._state = "CLEANUP_REQUESTED"  # Before any write; no retries after partial/unknown write.
        try:
            require(self._process.poll() is None, "Original helper exited before reader retirement")
            command = ("CLEANUP " + self._ready["nonce"] + "\n").encode("ascii")
            require(len(command) == 45, "Invalid original cleanup nonce")
            require(self._process.stdin.write(command) == len(command), "Incomplete cleanup handshake")
            self._process.stdin.flush()
            self._process.stdin.close()
            code = self._process.wait(timeout=10)
            self._retire_captures()
            lines = self._lines()
            require(code == 0 and len(lines) == 2 and all(line.endswith(b"\n") for line in lines), "Original cleanup failed")
            require(validate_ready(parse(lines[0], MAXIMUM_CAPTURE), self._compiler) == self._ready, "READY record changed")
            cleaned = validate_cleaned(parse(lines[1], MAXIMUM_CAPTURE), self._ready)
            self._state = "COMPLETE"
            return cleaned
        except BaseException as failure:
            self._failure = failure  # Retain and rethrow the original; diagnostics cannot replace it.
            try:
                self._record_failure()
            except BaseException as diagnostic_failure:
                self._diagnostic_failure = diagnostic_failure
            raise

    def abandon(self):
        """Preserve on any reader failure/timeout/unknown return. EOF is never a cleanup request."""
        self._guard()
        if self._state == "COMPLETE":
            return
        self._state = "ABANDONED"
        if self._process is not None:
            if self._process.stdin is not None and not self._process.stdin.closed:
                self._process.stdin.close()
            if self._process.poll() is not None:
                self._retire_captures()


def begin(compiler_path, output):
    require(sys.platform == "win32", "Protected read fixture requires actual Windows")
    tools, clock = toolkit(), progress()
    compiler = read_compiler(compiler_path, tools, clock)
    tools.directory(output)
    path = output / "helper-receipt.json"
    tools.regular(path)
    with path.open("rb") as source:
        helper = parse(source.read(256 * 1024 + 1), 256 * 1024)
    require(helper.get("schema") == 1 and type(helper["schema"]) is int and helper.get("scope") == COMPILE_SCOPE and
            helper.get("result") == "PASS" and helper.get("stage") == "COMPLETE" and helper.get("failureKind") == "NONE" and
            helper.get("nativeExecution") == "NOT_PERFORMED" and
            helper.get("source") == compiler["source"] and helper.get("tree") == compiler["tree"] and
            helper.get("compilerReceipt") == tools.digest(compiler_path, clock, 256 * 1024), "Helper compiler binding changed")
    require(isinstance(helper.get("inputs"), dict) and len(helper["inputs"]) == 12 and
            str(HERE / "protected-dll-fixture.c") in helper["inputs"] and str(Path(__file__).resolve()) in helper["inputs"] and
            all(tools.digest(Path(name), clock) == metadata for name, metadata in helper["inputs"].items()),
            "Original helper direct inputs changed")
    bound = helper.get("helper")
    require(isinstance(bound, dict) and set(bound) == {"name", "bytes", "sha256"} and bound["name"] == HELPER and
            tools.digest(output / HELPER, clock, MAXIMUM_DLL) == {"bytes": bound["bytes"], "sha256": bound["sha256"]},
            "Original compiled helper changed")
    owner = ProtectedDllFixture(output, compiler)
    try:
        owner._out = (output / "helper-stdout.log").open("xb")
        owner._err = (output / "helper-stderr.log").open("xb")
        environment = tools.child_environment(Path(compiler["toolchain"]["environment"]["SystemRoot"]), output)
        owner._process = subprocess.Popen([str(output / HELPER), compiler["dll"]["path"], str(compiler["dll"]["bytes"]),
                                           compiler["dll"]["sha256"], compiler["source"], compiler["tree"]],
                                          cwd=output, env=environment, stdin=subprocess.PIPE, stdout=owner._out,
                                          stderr=owner._err, close_fds=True, shell=False)
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            lines = owner._lines()
            if lines and lines[0].endswith(b"\n"):
                require(len(lines) == 1 and owner._process.poll() is None, "Helper did not retain original fixture")
                owner._ready = validate_ready(parse(lines[0], MAXIMUM_CAPTURE), compiler)
                owner._state = "READY"
                return owner
            require(owner._process.poll() is None, "Helper exited without a READY fixture")
            time.sleep(0.01)
        raise TimeoutError("Protected fixture READY deadline exhausted")
    except BaseException:
        try:
            owner.abandon()
        except Exception:
            pass  # Preserve original failure and original owner, never infer retirement or delete.
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("compile",))
    parser.add_argument("--compiler-receipt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    try:
        compile_helper(arguments.compiler_receipt, arguments.output)
        print("WINDOWS_PROTECTED_DLL_HELPER_COMPILE_PASS scope=" + COMPILE_SCOPE)
        return 0
    except Exception:
        print("WINDOWS_PROTECTED_DLL_HELPER_COMPILE_REFUSED", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
