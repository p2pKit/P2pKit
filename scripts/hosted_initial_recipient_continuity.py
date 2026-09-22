"""Fixed native boot observation and digest-only runner output, not admission.

Nothing is observed or loaded natively at import. Boot equality is meaningful
only with the reviewed same-job Steps caller and original execution evidence.
No timestamp/hostname/runner-label fallback can stand in for a kernel boot ID.
"""
from __future__ import annotations

import ctypes
import hashlib
import os
from pathlib import Path
import re
import stat
import sys
import uuid

import hosted_job_clock as clocks

STEP_SCOPE = "INITIAL_RECIPIENT_STEP_PENDING_GUARDED_OUTPUT_AND_RETURN_V1"
STEP_HASH_ENV = "P2PKIT_INITIAL_RECIPIENT_STEP_SHA256"
STEP_FILE = "step-pending.json"
STEP_LIMIT = 16384
QUARANTINE = []


class ContinuityError(RuntimeError):
    """Finite public-safe refusal; native identifiers are never exception text."""


def require(value, code):
    if not value:
        raise ContinuityError(code)


def _uuid_bytes(raw, ending):
    require(type(raw) is bytes and len(raw) == 36 + len(ending) and raw.endswith(ending), "BOOT_UUID_SIZE")
    text = raw[:36]
    require(re.fullmatch(rb"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}", text),
            "BOOT_UUID_GRAMMAR")
    value = uuid.UUID(text.decode("ascii")).bytes
    require(value != bytes(16), "BOOT_UUID_ZERO")
    return value


def _linux_boot():
    require(sys.platform == "linux", "BOOT_PLATFORM")
    path = Path("/proc/sys/kernel/random/boot_id")
    before = path.lstat()
    require(stat.S_ISREG(before.st_mode) and before.st_uid == 0 and not before.st_mode & 0o022,
            "BOOT_KERNEL_FILE")
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC)
    failure, raw = None, None
    try:
        require(os.path.samestat(before, os.fstat(descriptor)), "BOOT_KERNEL_FILE_CHANGED")
        raw = os.read(descriptor, 64)
        require(os.read(descriptor, 1) == b"", "BOOT_KERNEL_FILE_LIMIT")
        require(os.path.samestat(before, path.lstat()), "BOOT_KERNEL_FILE_CHANGED")
    except BaseException as error:
        failure = error
    try:
        os.close(descriptor)
    except BaseException as error:
        QUARANTINE.append(descriptor)  # No retry or lost close responsibility.
        if failure is not None:
            raise failure from error
        raise ContinuityError("BOOT_KERNEL_CLOSE_UNKNOWN") from error
    if failure is not None:
        raise failure
    return _uuid_bytes(raw, b"\n")


def _darwin_boot():
    require(sys.platform == "darwin", "BOOT_PLATFORM")
    library = ctypes.CDLL("/usr/lib/libSystem.B.dylib", use_errno=True)
    function = library.sysctlbyname
    function.argtypes = [ctypes.c_char_p, ctypes.c_void_p, ctypes.POINTER(ctypes.c_size_t),
                         ctypes.c_void_p, ctypes.c_size_t]
    function.restype = ctypes.c_int
    data, size = ctypes.create_string_buffer(37), ctypes.c_size_t(37)
    require(function(b"kern.bootsessionuuid", data, ctypes.byref(size), None, 0) == 0 and size.value == 37,
            "BOOT_DARWIN_QUERY")
    return _uuid_bytes(data.raw, b"\0")


class _BootEnvironment(ctypes.Structure):
    _fields_ = [("identifier", ctypes.c_ubyte * 16), ("firmware", ctypes.c_uint32), ("flags", ctypes.c_uint64)]


def _windows_boot():
    require(sys.platform == "win32" and callable(getattr(ctypes, "WinDLL", None)), "BOOT_PLATFORM")
    library = ctypes.WinDLL("ntdll.dll", use_last_error=True, winmode=0x00000800)
    function = library.NtQuerySystemInformation
    function.argtypes = [ctypes.c_uint32, ctypes.c_void_p, ctypes.c_uint32, ctypes.POINTER(ctypes.c_uint32)]
    function.restype = ctypes.c_int32
    data, size = _BootEnvironment(), ctypes.c_uint32()
    require(ctypes.sizeof(data) == 32, "BOOT_WINDOWS_ABI")
    # SystemBootEnvironmentInformation (90), fixed current supported NT ABI.
    require(function(90, ctypes.byref(data), ctypes.sizeof(data), ctypes.byref(size)) == 0 and
            size.value == ctypes.sizeof(data) and data.firmware in (0, 1, 2), "BOOT_WINDOWS_QUERY")
    raw = bytes(data.identifier)
    require(raw != bytes(16), "BOOT_UUID_ZERO")
    return uuid.UUID(bytes_le=raw).bytes


def boot_digest(role):
    """Actual closed native role; return a domain-separated digest, never raw ID."""
    require(not QUARANTINE and role in clocks.DOMAINS and clocks.processes.host_role() == role, "BOOT_NATIVE_ROLE")
    try:
        raw = (_linux_boot() if role == "linux-x64" else _windows_boot() if role == "windows-x64" else _darwin_boot())
        return hashlib.sha256(b"P2pKit hosted boot v1\0" + role.encode("ascii") + b"\0" + raw).hexdigest()
    except ContinuityError:
        raise
    except Exception:
        raise ContinuityError("BOOT_NATIVE_OBSERVATION_FAILED") from None


def append_outputs(values, check):
    """Actual runner file command, not evidence storage or a self-signed result.

    Only fixed lowercase hashes leave private custody. A failed/partial append
    cannot authorize the next step: the fixed caller also requires SUCCESS.
    """
    require(type(values) is dict and set(values) in (
        {"recipientSenderSha256", "recipientStepSha256"}, {"initializationSha256"}) and
        all(type(value) is str and re.fullmatch(r"[0-9a-f]{64}", value) for value in values.values()) and
        callable(check) and not QUARANTINE, "STEP_OUTPUT_FIELDS")
    raw = "".join(name + "=" + values[name] + "\n" for name in sorted(values)).encode("ascii")
    check()
    target = Path(os.environ.get("GITHUB_OUTPUT", ""))
    parent = Path(os.environ.get("RUNNER_TEMP", ""))
    require(target.is_absolute() and parent.is_absolute() and ".." not in target.parts and
        target.parent == parent / "_runner_file_commands" and
        re.fullmatch(r"set_output_[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}",
                     target.name), "STEP_OUTPUT_PATH")
    parents = tuple((path, path.lstat()) for path in target.parents)
    for path, info in parents:
        require(stat.S_ISDIR(info.st_mode) and not getattr(info, "st_file_attributes", 0) & 0x400,
                "STEP_OUTPUT_PARENT")
    before = target.lstat()
    require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and before.st_size == 0 and
        not getattr(before, "st_file_attributes", 0) & 0x400 and
        (os.name == "nt" or before.st_uid == os.geteuid()), "STEP_OUTPUT_FILE")
    attributes = ("st_dev", "st_ino", "st_mode", "st_uid", "st_gid", "st_nlink", "st_file_attributes")
    identity = tuple(getattr(before, name, None) for name in attributes)
    def same_file(current, size):
        return tuple(getattr(current, name, None) for name in attributes) == identity and current.st_size == size
    check()
    descriptor = os.open(target, os.O_RDWR | os.O_APPEND | getattr(os, "O_NOFOLLOW", 0) |
                         getattr(os, "O_BINARY", 0) | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_CLOEXEC", 0))
    failure = None
    try:
        require(same_file(os.fstat(descriptor), 0), "STEP_OUTPUT_CHANGED")
        check()
        require(os.write(descriptor, raw) == len(raw), "STEP_OUTPUT_SHORT_WRITE")
        os.fsync(descriptor)
        check()
        require(os.lseek(descriptor, 0, os.SEEK_SET) == 0 and os.read(descriptor, len(raw) + 1) == raw,
                "STEP_OUTPUT_READBACK")
        require(same_file(target.lstat(), len(raw)) and same_file(os.fstat(descriptor), len(raw)),
                "STEP_OUTPUT_CHANGED")
        for path, info in parents:
            after = path.lstat()
            require(os.path.samestat(info, after) and stat.S_ISDIR(after.st_mode) and
                    not getattr(after, "st_file_attributes", 0) & 0x400, "STEP_OUTPUT_PARENT_CHANGED")
    except BaseException as error:
        failure = error
    try:
        os.close(descriptor)
    except BaseException as error:
        QUARANTINE.append(descriptor)
        if failure is not None:
            raise failure from error
        raise ContinuityError("STEP_OUTPUT_CLOSE_UNKNOWN") from error
    if failure is not None:
        raise failure
    check()  # Actual fsync/readback/close return remains inside the original cap.
