#!/usr/bin/env python3
"""Native Windows private-file custody primitives, not an executor or uploader.

Only local fixed NTFS volumes and native 64-bit Python are admitted. Root and
explicit child creation use NtCreateFile(FILE_CREATE), an explicit protected
DACL, and a pinned parent: there is no create-then-secure/create-then-open window.
The only allowed access ACEs are this process's user and SYSTEM, both FILE_ALL_ACCESS.
The expected owner is the token's default owner (user or Builtin Administrators).
SYSTEM, administrators/privileged OS components, and malicious same-user code
are NOT sandboxed. This does not resolve the separate hostile-source #120 policy.

Ordinary handles deny write/delete sharing and pin every ancestor until the last
dependent object closes. The separate fixed provider command-file capability
permits pathname writes until an overlapping deny-write reader locks the file;
it does not prove append-only history, a kernel byte quota or writer retirement.
The two fixed provider logs have a byte-only overlapping readback: their original
deny-write/delete writer stays pinned until the temporary reader has closed.
That reader never escapes the operation, and ordinary sharing is unchanged.
An inherited descendant ACL is accepted only below a verified
private root and only when it is the exact recognized user+SYSTEM inheritance.
No operation deletes evidence. Callers must stop writers before snapshotting.
Deadlines are checked between bounded synchronous native calls; an OS/disk hang
still needs the outer invocation owner's watchdog. This is not secure erasure.

Import and pure validation/model tests are portable. Native entry points fail on
non-Windows hosts; they do not silently substitute POSIX or claim qualification.
"""
from __future__ import annotations

import ctypes
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from functools import wraps
import io
import os
from pathlib import Path
import re
import struct
import threading
import time
from types import MappingProxyType


MAX_FILE_BYTES = 576 * 1024 * 1024
MAX_MEMBERS = 10_000
MAX_DEPTH = 64
MAX_SECONDS = 900
CHUNK = 64 * 1024
MAX_READ_BYTES = 16 * 1024 * 1024
PROVIDER_COMMAND_NAME = "provider-output.txt"
MAX_PROVIDER_COMMAND_BYTES = 4 * 1024
PROVIDER_LOG_NAMES = ("provider-stdout.log", "provider-stderr.log")
MAX_PROVIDER_LOG_BYTES = 1024 * 1024
SYSTEM_SID = "S-1-5-18"
ADMINISTRATORS_SID = "S-1-5-32-544"
FILE_ALL_ACCESS = 0x001F01FF
DIRECTORY = 0x10
REPARSE_POINT = 0x400
SE_DACL_PRESENT = 0x0004
SE_DACL_PROTECTED = 0x1000
INHERITED_ACE = 0x10
INVALID_HANDLE = ctypes.c_void_p(-1).value
U16, U32, U64, I64, PTR = ctypes.c_uint16, ctypes.c_uint32, ctypes.c_uint64, ctypes.c_int64, ctypes.c_void_p


class FilesystemError(RuntimeError):
    """Bounded, public-safe error. Original evidence must remain private."""


def _locked(method):
    @wraps(method)
    def locked(self, *args, **kwargs):
        with self._operation_lock:
            return method(self, *args, **kwargs)
    return locked


def require(value, message):
    if not value:
        raise FilesystemError(message)


def _note(error, message):
    # The maintained Mac's system Python can predate BaseException.add_note.
    # Keep the same inspectable detail without replacing the original failure.
    if hasattr(error, "add_note"):
        error.add_note(message)
    else:
        if not hasattr(error, "__notes__"):
            error.__notes__ = []
        error.__notes__.append(message)


def _cleanup(operations, original=None):
    """Attempt every owned cleanup and never overwrite the operation's failure."""
    errors = []
    for operation in operations:
        try:
            operation()
        except BaseException as error:
            errors.append(error)
    if errors:
        failure = original if original is not None else FilesystemError("Native custody cleanup failed")
        for error in errors:
            _note(failure, "Cleanup: " + type(error).__name__ + ": " + str(error)[:512])
            for detail in getattr(error, "__notes__", ()):
                _note(failure, detail)
        if original is None:
            raise failure from errors[0]


@contextmanager
def _on_exit(*operations):
    original = None
    try:
        yield
    except BaseException as error:
        original = error
        raise
    finally:
        _cleanup(operations, original)


def _close_native(api, handle):
    value = handle.value if isinstance(handle, PTR) else handle
    if value not in (None, 0, INVALID_HANDLE):
        try:
            api.close(handle)
        except BaseException as error:
            _note(error, f"Native handle retirement UNKNOWN: {handle}")
            raise


def _bound(value, maximum, label, *, zero=False):
    require(type(value) is int and (0 if zero else 1) <= value <= maximum, "Invalid " + label + " bound")
    return value


def _end(deadline=None):
    now = time.monotonic()
    if deadline is None:
        return now + MAX_SECONDS
    require(type(deadline) in (int, float) and now < deadline <= now + MAX_SECONDS,
            "Invalid native filesystem deadline")
    return deadline


def _check_time(deadline):
    require(time.monotonic() < deadline, "Native filesystem deadline exceeded")


def component(value):
    require(isinstance(value, str) and value and value not in (".", "..") and
            value[-1] not in " ." and not any(ord(c) < 32 or ord(c) == 127 or c in '<>:"/\\|?*' for c in value),
            "Unsafe Windows path component")
    try:
        size = len(value.encode("utf-16-le"))
    except UnicodeError:
        raise FilesystemError("Invalid Windows path encoding") from None
    require(size <= 510, "Windows path component exceeds bound")
    stem = value.split(".", 1)[0].upper()
    require(stem not in {"CON", "PRN", "AUX", "NUL", "CONIN$", "CONOUT$", "CLOCK$"} and
            re.fullmatch(r"(?:COM|LPT)[1-9¹²³]", stem) is None, "Windows device name is not a custody path")
    return value


def absolute_parts(value):
    value = os.fspath(value)
    require(isinstance(value, str) and re.match(r"^[A-Za-z]:\\", value) is not None and
            "/" not in value and not value.endswith("\\") and len(value.encode("utf-16-le", errors="surrogatepass")) < 65500,
            "Use a normalized local absolute Windows path, not UNC/device/drive-relative paths")
    parts = value[3:].split("\\")
    require(0 < len(parts) <= MAX_DEPTH, "Windows path depth exceeds bound")
    return value[0].upper() + ":\\", tuple(component(part) for part in parts)


def relative_parts(value):
    require(isinstance(value, str) and value and "\\" not in value, "Use a relative slash-separated custody path")
    parts = value.split("/")
    require(len(parts) <= MAX_DEPTH, "Relative custody depth exceeds bound")
    return tuple(component(part) for part in parts)


def final_path_matches(actual, requested):
    require(isinstance(actual, str) and actual.startswith("\\\\?\\") and not actual.startswith("\\\\?\\UNC\\"),
            "Native file resolved outside a local DOS volume")
    native = actual[4:]
    # A different case is not an authority change; short names, mount/device paths,
    # SUBST drives and other aliases must still resolve to exactly this path.
    def folded(value):
        return value.translate(str.maketrans("ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz"))
    require(folded(native) == folded(requested), "Native final path differs from its pinned path")
    return native


@dataclass(frozen=True)
class AccessPolicy:
    user_sid: str
    owner_sid: str

    def __post_init__(self):
        require(re.fullmatch(r"S-1-(?:[0-9]+-){1,14}[0-9]+", self.user_sid or "") is not None and
                self.user_sid not in (SYSTEM_SID, ADMINISTRATORS_SID) and
                self.owner_sid in (self.user_sid, ADMINISTRATORS_SID), "Unsupported current token user/default owner")

    def sddl(self, directory):
        flags = "OICI" if directory else ""
        return (f"O:{self.owner_sid}D:P(A;{flags};FA;;;{self.user_sid})"
                f"(A;{flags};FA;;;{SYSTEM_SID})")


def validate_acl(policy, owner, control, revision, aces, *, directory, inherited_allowed=False):
    """Pure closed ACL policy. Unknown ACEs/rights/inheritance never become safe."""
    require(owner == policy.owner_sid and revision == 1 and control & SE_DACL_PRESENT,
            "Native owner/security descriptor differs from the admitted token")
    protected = bool(control & SE_DACL_PROTECTED)
    require(protected or inherited_allowed, "A standalone custody root needs a protected DACL")
    expected_flags = (3 if directory else 0) | (0 if protected else INHERITED_ACE)
    require(isinstance(aces, (tuple, list)) and len(aces) == 2 and
            all(isinstance(ace, tuple) and len(ace) == 4 and ace[:3] == (0, expected_flags, FILE_ALL_ACCESS)
                for ace in aces) and {ace[3] for ace in aces} == {policy.user_sid, SYSTEM_SID},
            "DACL is null, broad, duplicated, inherited from an unknown policy, or otherwise unsupported")
    return protected


def decode_streams(raw, *, directory, size, live_output_max_bytes=None, live_output_min_bytes=0):
    """Decode streams strictly, or bounded monotonic growth for a live writer."""
    if live_output_max_bytes is not None:
        require(not directory, "Live output observation requires a private regular file")
        _bound(live_output_max_bytes, MAX_FILE_BYTES, "file bytes", zero=True)
        _bound(live_output_min_bytes, live_output_max_bytes, "file bytes", zero=True)
    if raw is None:
        require(directory, "Regular file lacks native stream information")
        return ()
    require(isinstance(raw, bytes) and 24 <= len(raw) <= 1024 * 1024, "Invalid native stream information")
    position, rows = 0, []
    while True:
        require(position + 24 <= len(raw) and len(rows) < 1024, "Truncated/excessive stream information")
        following, length, stream_size, allocation = struct.unpack_from("<IIqq", raw, position)
        require(0 < length <= 1024 and length % 2 == 0 and position + 24 + length <= len(raw) and
                stream_size >= 0 and allocation >= 0, "Invalid native stream record")
        try:
            name = raw[position + 24:position + 24 + length].decode("utf-16-le")
        except UnicodeError:
            raise FilesystemError("Invalid native stream name") from None
        rows.append((name, stream_size))
        if following == 0:
            break
        require(following % 8 == 0 and following >= 24 + length and position + following < len(raw),
                "Invalid native stream offset")
        position += following
    if live_output_max_bytes is None:
        require(rows == [("::$DATA", size)] and (not directory or size == 0), "Alternate data streams are not admitted")
    else:
        require(len(rows) == 1 and rows[0][0] == "::$DATA", "Alternate data streams are not admitted")
        require(type(size) is int and live_output_min_bytes <= size <= rows[0][1] <= live_output_max_bytes,
                "Live output stream shrank or exceeded its byte bound")
    return tuple(rows)


def decode_directory(raw):
    """Decode bounded FILE_ID_BOTH_DIR_INFO records; never use their short aliases."""
    require(isinstance(raw, bytes) and 104 <= len(raw) <= CHUNK, "Invalid native directory information")
    position, names = 0, []
    while True:
        require(position + 104 <= len(raw) and len(names) < MAX_MEMBERS, "Truncated/excessive directory information")
        following = struct.unpack_from("<I", raw, position)[0]
        length = struct.unpack_from("<I", raw, position + 60)[0]
        require(0 < length <= 510 and length % 2 == 0 and position + 104 + length <= len(raw),
                "Invalid native directory name size")
        try:
            name = raw[position + 104:position + 104 + length].decode("utf-16-le")
        except UnicodeError:
            raise FilesystemError("Invalid native directory name encoding") from None
        if name not in (".", ".."):
            names.append(component(name))
        if following == 0:
            break
        require(following % 8 == 0 and following >= 104 + length and position + following < len(raw),
                "Invalid native directory offset")
        position += following
    return names


@dataclass(frozen=True)
class FileInfo:
    identity: tuple[int, str]
    is_directory: bool
    size: int
    links: int
    attributes: int
    creation_100ns: int
    modified_100ns: int
    change_100ns: int
    owner_sid: str | None = None
    protected_dacl: bool | None = None

    def as_dict(self):
        return asdict(self)


class _UnicodeString(ctypes.Structure):
    _fields_ = [("length", U16), ("maximum", U16), ("buffer", PTR)]


class _ObjectAttributes(ctypes.Structure):
    _fields_ = [("length", U32), ("root", PTR), ("name", ctypes.POINTER(_UnicodeString)),
                ("attributes", U32), ("security", PTR), ("qos", PTR)]


class _IoStatus(ctypes.Structure):
    _fields_ = [("status", PTR), ("information", ctypes.c_size_t)]


class _FileId(ctypes.Structure):
    _fields_ = [("volume", U64), ("identifier", ctypes.c_ubyte * 16)]


class _Basic(ctypes.Structure):
    _fields_ = [("created", I64), ("accessed", I64), ("modified", I64), ("changed", I64), ("attributes", U32)]


class _Standard(ctypes.Structure):
    _fields_ = [("allocated", I64), ("size", I64), ("links", U32),
                ("delete_pending", ctypes.c_ubyte), ("directory", ctypes.c_ubyte)]


class _AclSize(ctypes.Structure):
    _fields_ = [("count", U32), ("in_use", U32), ("free", U32)]


class _WinApi:
    """Delayed native binding. Only the private model tests inject a substitute."""

    def __init__(self):
        require(os.name == "nt" and ctypes.sizeof(PTR) == 8 and ctypes.sizeof(ctypes.c_wchar) == 2,
                "Native 64-bit Windows Python is required; no emulated filesystem qualification")
        require(tuple(ctypes.sizeof(t) for t in (_UnicodeString, _ObjectAttributes, _IoStatus, _FileId,
                                                _Basic, _Standard, _AclSize)) == (16, 48, 16, 24, 40, 24, 12),
                "Unsupported Windows filesystem ABI")
        self.kernel = ctypes.WinDLL("kernel32.dll", use_last_error=True, winmode=0x800)
        self.advapi = ctypes.WinDLL("advapi32.dll", use_last_error=True, winmode=0x800)
        self.ntdll = ctypes.WinDLL("ntdll.dll", use_last_error=True, winmode=0x800)
        self._bind(self.kernel, "CloseHandle", [PTR], ctypes.c_int32)
        self._bind(self.kernel, "GetCurrentProcess", [], PTR)
        self._bind(self.kernel, "GetCurrentThread", [], PTR)
        self._bind(self.kernel, "IsWow64Process2", [PTR, ctypes.POINTER(U16), ctypes.POINTER(U16)], ctypes.c_int32)
        self._bind(self.kernel, "GetHandleInformation", [PTR, ctypes.POINTER(U32)], ctypes.c_int32)
        self._bind(self.kernel, "LocalFree", [PTR], PTR)
        self._bind(self.kernel, "GetDriveTypeW", [ctypes.c_wchar_p], U32)
        self._bind(self.kernel, "GetVolumeInformationW", [ctypes.c_wchar_p, PTR, U32, ctypes.POINTER(U32),
                   ctypes.POINTER(U32), ctypes.POINTER(U32), ctypes.c_wchar_p, U32], ctypes.c_int32)
        self._bind(self.kernel, "CreateFileW", [ctypes.c_wchar_p, U32, U32, PTR, U32, U32, PTR], PTR)
        self._bind(self.kernel, "GetFileType", [PTR], U32)
        self._bind(self.kernel, "GetFileInformationByHandleEx", [PTR, ctypes.c_int32, PTR, U32], ctypes.c_int32)
        self._bind(self.kernel, "GetFinalPathNameByHandleW", [PTR, ctypes.c_wchar_p, U32, U32], U32)
        self._bind(self.kernel, "ReadFile", [PTR, PTR, U32, ctypes.POINTER(U32), PTR], ctypes.c_int32)
        self._bind(self.kernel, "WriteFile", [PTR, PTR, U32, ctypes.POINTER(U32), PTR], ctypes.c_int32)
        self._bind(self.kernel, "SetFilePointerEx", [PTR, I64, ctypes.POINTER(I64), U32], ctypes.c_int32)
        self._bind(self.kernel, "FlushFileBuffers", [PTR], ctypes.c_int32)
        self._bind(self.advapi, "OpenProcessToken", [PTR, U32, ctypes.POINTER(PTR)], ctypes.c_int32)
        self._bind(self.advapi, "OpenThreadToken", [PTR, U32, ctypes.c_int32, ctypes.POINTER(PTR)], ctypes.c_int32)
        self._bind(self.advapi, "GetTokenInformation", [PTR, ctypes.c_int32, PTR, U32, ctypes.POINTER(U32)], ctypes.c_int32)
        self._bind(self.advapi, "ConvertSidToStringSidW", [PTR, ctypes.POINTER(PTR)], ctypes.c_int32)
        self._bind(self.advapi, "IsValidSid", [PTR], ctypes.c_int32)
        self._bind(self.advapi, "GetLengthSid", [PTR], U32)
        self._bind(self.advapi, "ConvertStringSecurityDescriptorToSecurityDescriptorW",
                   [ctypes.c_wchar_p, U32, ctypes.POINTER(PTR), ctypes.POINTER(U32)], ctypes.c_int32)
        self._bind(self.advapi, "GetSecurityInfo", [PTR, U32, U32, ctypes.POINTER(PTR), PTR,
                   ctypes.POINTER(PTR), PTR, ctypes.POINTER(PTR)], U32)
        self._bind(self.advapi, "GetSecurityDescriptorControl", [PTR, ctypes.POINTER(U16), ctypes.POINTER(U32)], ctypes.c_int32)
        self._bind(self.advapi, "GetAclInformation", [PTR, PTR, U32, U32], ctypes.c_int32)
        self._bind(self.advapi, "GetAce", [PTR, U32, ctypes.POINTER(PTR)], ctypes.c_int32)
        self._bind(self.ntdll, "NtCreateFile", [ctypes.POINTER(PTR), U32, ctypes.POINTER(_ObjectAttributes),
                   ctypes.POINTER(_IoStatus), PTR, U32, U32, U32, U32, PTR, U32], ctypes.c_int32)
        self._bind(self.ntdll, "RtlNtStatusToDosError", [ctypes.c_int32], U32)
        self._native_architecture()
        self.policy = self._token_policy()

    def _bind(self, library, name, arguments, result):
        function = getattr(library, name)
        function.argtypes, function.restype = arguments, result
        setattr(self, name, function)

    def checked(self, result, operation):
        require(result, f"Windows {operation} failed (error {ctypes.get_last_error()})")
        return result

    def close(self, handle):
        self.checked(self.CloseHandle(handle), "CloseHandle")

    def _native_architecture(self):
        process_machine, native_machine = U16(), U16()
        self.checked(self.IsWow64Process2(self.GetCurrentProcess(), ctypes.byref(process_machine),
                                         ctypes.byref(native_machine)), "IsWow64Process2")
        require(process_machine.value == 0 and native_machine.value in (0x8664, 0xAA64),
                "Custody requires native AMD64/ARM64 Windows Python, not a translated process")

    def _free(self, pointer):
        if pointer:
            require(not self.LocalFree(pointer), "Windows LocalFree failed")

    def _sid(self, pointer):
        require(pointer and self.IsValidSid(pointer) and 8 <= self.GetLengthSid(pointer) <= 68, "Invalid native SID")
        output = PTR()
        with _on_exit(lambda: self._free(output)):
            self.checked(self.ConvertSidToStringSidW(pointer, ctypes.byref(output)), "ConvertSidToStringSidW")
            # The OS allocates a NUL-terminated SID string. Do not read an
            # arbitrary 256 wchar range beyond that actual allocation.
            value = ctypes.wstring_at(output.value)
            require(0 < len(value) < 256, "Native SID string exceeds bound")
            return value

    def _token_policy(self):
        thread = PTR()
        if self.OpenThreadToken(self.GetCurrentThread(), 0x8, 1, ctypes.byref(thread)):
            error = FilesystemError("Thread impersonation is not admitted")
            _cleanup((lambda: _close_native(self, thread),), error)
            raise error
        require(ctypes.get_last_error() == 1008, "Cannot establish absence of thread impersonation")
        token = PTR()
        with _on_exit(lambda: _close_native(self, token)):
            self.checked(self.OpenProcessToken(self.GetCurrentProcess(), 0x8, ctypes.byref(token)), "OpenProcessToken")
            def sid(information):
                count = U32()
                self.GetTokenInformation(token, information, None, 0, ctypes.byref(count))
                require(ctypes.get_last_error() == 122 and 8 <= count.value <= 65536, "Invalid native token information size")
                data = ctypes.create_string_buffer(count.value)
                self.checked(self.GetTokenInformation(token, information, data, len(data), ctypes.byref(count)),
                             "GetTokenInformation")
                return self._sid(PTR.from_buffer(data).value)
            return AccessPolicy(sid(1), sid(4))  # TokenUser and TokenOwner, not arbitrary caller-supplied SIDs.

    def drive(self, drive):
        require(self.GetDriveTypeW(drive) == 3, "Custody requires a local fixed volume")
        name, serial, maximum, flags = ctypes.create_unicode_buffer(32), U32(), U32(), U32()
        self.checked(self.GetVolumeInformationW(drive, None, 0, ctypes.byref(serial), ctypes.byref(maximum),
                                               ctypes.byref(flags), name, len(name)), "GetVolumeInformationW")
        require(name.value == "NTFS" and flags.value & 0x8 and flags.value & 0x40000,
                "Only NTFS with persistent ACLs and named-stream inspection is admitted")
        handle = self.CreateFileW("\\\\?\\" + drive, 0x001200A1, 1, None, 3, 0x02200000, None)
        require(handle not in (None, INVALID_HANDLE), "Cannot pin native volume root")
        return handle

    def child(self, parent, name, *, directory, create=False, writable=False):
        return self._child(parent, name, directory=directory, create=create, writable=writable, sharing=1)

    def provider_command_file(self, parent):
        # A READ-access original can overlap the later ordinary read/share1 pin.
        # A WRITE-access original could not; closing it first would create a gap.
        return self._child(parent, PROVIDER_COMMAND_NAME, directory=False, create=True, writable=False, sharing=3)

    def provider_log_reader(self, parent, name):
        # The caller must KEEP the original WRITE/shareREAD pin throughout this
        # temporary READ/shareREAD|WRITE handle's life, including its close.
        require(type(name) is str and name in PROVIDER_LOG_NAMES, "Unsupported provider log name")
        return self._child(parent, name, directory=False, create=False, writable=False, sharing=3)

    def _child(self, parent, name, *, directory, create, writable, sharing):
        component(name)
        require(not writable or create and not directory, "Only exclusive newly created files are writable")
        require(type(sharing) is int and (sharing == 1 or sharing == 3 and type(name) is str and
                directory is False and writable is False and
                (name == PROVIDER_COMMAND_NAME and create is True or name in PROVIDER_LOG_NAMES and create is False)),
                "Unsupported native sharing policy")
        security = PTR()
        handle = PTR()
        try:
            with _on_exit(lambda: self._free(security)):
                if create:
                    self.checked(self.ConvertStringSecurityDescriptorToSecurityDescriptorW(
                        self.policy.sddl(directory), 1, ctypes.byref(security), None),
                        "Create protected security descriptor")
                text = ctypes.create_unicode_buffer(name)
                length = len(name.encode("utf-16-le"))
                string = _UnicodeString(length, length + 2, ctypes.cast(text, PTR))
                attributes = _ObjectAttributes(ctypes.sizeof(_ObjectAttributes), parent, ctypes.pointer(string),
                                               0x40, security, None)  # OBJ_CASE_INSENSITIVE, never OBJ_INHERIT.
                status = _IoStatus()
                access = 0x00120080 | (0 if directory is None else 0x21 if directory else 0x2 if writable else 0x1)
                result = self.NtCreateFile(ctypes.byref(handle), access, ctypes.byref(attributes), ctypes.byref(status),
                                           None, 0x80, sharing, 2 if create else 1,
                                           0x00200020 | (0 if directory is None else 0x1 if directory else 0x40), None, 0)
                require(result == 0, f"Windows NtCreateFile failed (error {self.RtlNtStatusToDosError(result)})")
                require(handle.value not in (None, INVALID_HANDLE) and status.information == (2 if create else 1),
                        "Native exclusive creation/open result differs")
        except BaseException as error:
            _cleanup((lambda: _close_native(self, handle),), error)
            raise
        # Transfer only after security-descriptor retirement also succeeded.
        return handle.value

    def _information(self, handle, kind, structure):
        value = structure()
        self.checked(self.GetFileInformationByHandleEx(handle, kind, ctypes.byref(value), ctypes.sizeof(value)),
                     "GetFileInformationByHandleEx")
        return value

    def _security(self, handle, *, directory, inherited_allowed):
        owner, dacl, descriptor = PTR(), PTR(), PTR()
        with _on_exit(lambda: self._free(descriptor)):
            code = self.GetSecurityInfo(handle, 1, 0x5, ctypes.byref(owner), None, ctypes.byref(dacl), None,
                                        ctypes.byref(descriptor))
            require(code == 0, f"Windows GetSecurityInfo failed (error {code})")
            control, revision = U16(), U32()
            self.checked(self.GetSecurityDescriptorControl(descriptor, ctypes.byref(control), ctypes.byref(revision)),
                         "GetSecurityDescriptorControl")
            require(bool(dacl), "Null DACL is not private custody")
            size = _AclSize()
            self.checked(self.GetAclInformation(dacl, ctypes.byref(size), ctypes.sizeof(size), 2), "GetAclInformation")
            require(size.count == 2 and 8 <= size.in_use <= 1024, "Unsupported native DACL size/count")
            records = []
            for index in range(size.count):
                ace = PTR()
                self.checked(self.GetAce(dacl, index, ctypes.byref(ace)), "GetAce")
                header = ctypes.string_at(ace.value, 8)
                kind, flags, ace_size, mask = struct.unpack("<BBHI", header)
                require(kind == 0 and 16 <= ace_size <= 1024 and self.IsValidSid(ace.value + 8),
                        "Unsupported native ACE")
                require(self.GetLengthSid(ace.value + 8) + 8 == ace_size, "Native ACE SID size differs")
                records.append((kind, flags, mask, self._sid(ace.value + 8)))
            owner_sid = self._sid(owner.value)
            protected = validate_acl(self.policy, owner_sid, control.value, revision.value, records,
                                     directory=directory, inherited_allowed=inherited_allowed)
            return owner_sid, protected

    def inspect(self, handle, path, *, directory, private=False, inherited_allowed=False,
                live_output_max_bytes=None, live_output_min_bytes=0, strict_streams=False):
        if live_output_max_bytes is not None:
            require(private and not directory, "Live output observation requires a private regular file")
            _bound(live_output_max_bytes, MAX_FILE_BYTES, "file bytes", zero=True)
            _bound(live_output_min_bytes, live_output_max_bytes, "file bytes", zero=True)
        require(self.GetFileType(handle) == 1, "Only native disk files are admitted")
        flags = U32()
        self.checked(self.GetHandleInformation(handle, ctypes.byref(flags)), "GetHandleInformation")
        require(not flags.value & 1, "Custody handles must not be inheritable")
        identifier = self._information(handle, 18, _FileId)
        basic = self._information(handle, 0, _Basic)
        standard = self._information(handle, 1, _Standard)
        require(identifier.volume != 0 and any(identifier.identifier) and not standard.delete_pending and
                bool(standard.directory) == directory and bool(basic.attributes & DIRECTORY) == directory and
                not basic.attributes & REPARSE_POINT and standard.size >= 0 and standard.links >= 1 and
                (directory or standard.links == 1), "Linked/reparse/deleting/wrong-kind file is not admitted")
        final = ctypes.create_unicode_buffer(32768)
        length = self.GetFinalPathNameByHandleW(handle, final, len(final), 0)
        require(0 < length < len(final), "Native final path is unavailable or exceeds bound")
        final_path_matches(final.value, path)
        owner, protected = (self._security(handle, directory=directory, inherited_allowed=inherited_allowed)
                            if private else (None, None))
        observed_size = standard.size
        if private or strict_streams:
            capacity = 4096
            while True:
                streams = ctypes.create_string_buffer(capacity)
                if self.GetFileInformationByHandleEx(handle, 7, streams, len(streams)):
                    rows = decode_streams(streams.raw, directory=directory, size=standard.size,
                                          live_output_max_bytes=live_output_max_bytes,
                                          live_output_min_bytes=live_output_min_bytes)
                    if live_output_max_bytes is not None:
                        # The child may append between these separate native
                        # queries. Never return the stale, smaller first size.
                        observed_size = rows[0][1]
                    break
                error = ctypes.get_last_error()
                if error == 38 and directory:  # ERROR_HANDLE_EOF: directory has no data streams.
                    decode_streams(None, directory=True, size=standard.size)
                    break
                require(error in (122, 234) and capacity < 1024 * 1024, "Cannot inspect bounded native data streams")
                capacity *= 2
        return FileInfo((identifier.volume, bytes(identifier.identifier).hex()), directory, observed_size,
                        standard.links, basic.attributes, basic.created, basic.modified, basic.changed, owner, protected)

    def names(self, handle, maximum, deadline):
        names, seen, restart = [], set(), True
        while True:
            _check_time(deadline)
            buffer = ctypes.create_string_buffer(CHUNK)
            if not self.GetFileInformationByHandleEx(handle, 11 if restart else 10, buffer, len(buffer)):
                require(ctypes.get_last_error() == 18, "Cannot enumerate native directory")
                return names
            restart = False
            for name in decode_directory(buffer.raw):
                require(name.casefold() not in seen and len(names) < maximum,
                        "Directory has duplicate aliases or exceeds member bound")
                seen.add(name.casefold())
                names.append(name)

    def kind(self, parent, name):
        # Do not infer a directory from a failed regular-file open (permission,
        # sharing, I/O and reparse failures must remain failures).
        handle = self.child(parent, name, directory=None)
        with _on_exit(lambda: _close_native(self, handle)):
            basic = self._information(handle, 0, _Basic)
            standard = self._information(handle, 1, _Standard)
            require(not basic.attributes & REPARSE_POINT and not standard.delete_pending and
                    bool(standard.directory) == bool(basic.attributes & DIRECTORY), "Unknown/reparse native member kind")
            return bool(standard.directory)

    def read(self, handle, count):
        data, actual = ctypes.create_string_buffer(count), U32()
        self.checked(self.ReadFile(handle, data, count, ctypes.byref(actual), None), "ReadFile")
        require(actual.value <= count, "Native read exceeds request")
        return data.raw[:actual.value]

    def write(self, handle, data):
        actual = U32()
        self.checked(self.WriteFile(handle, data, len(data), ctypes.byref(actual), None), "WriteFile")
        require(0 < actual.value <= len(data), "Native write made no progress or exceeded request")
        return actual.value

    def seek(self, handle, position, whence):
        output = I64()
        self.checked(self.SetFilePointerEx(handle, position, ctypes.byref(output), whence), "SetFilePointerEx")
        return output.value

    def flush(self, handle):
        self.checked(self.FlushFileBuffers(handle), "FlushFileBuffers")


class _Pin:
    def __init__(self, api, handle, path, info, *, private, inherited_allowed=False, writable=False,
                 strict_streams=False, immutable=False):
        self.api, self.handle, self.path, self.info = api, handle, path, info
        self.private, self.inherited_allowed, self.writable = private, inherited_allowed, writable
        self.strict_streams = strict_streams
        self.immutable = immutable
        self.references, self.lock = 1, threading.RLock()

    def acquire(self):
        with self.lock:
            require(self.references > 0, "Custody parent handle is already closed")
            self.references += 1
        return self

    def release(self):
        with self.lock:
            require(self.references > 0, "Custody handle released twice")
            self.references -= 1
            if self.references == 0:
                handle = self.handle
                _close_native(self.api, handle)
                self.handle = None

    def observe(self, *, live_output_max_bytes=None, live_output_min_bytes=0):
        with self.lock:
            require(self.references > 0, "Custody handle is closed")
            options = {}
            if self.strict_streams:
                # Public dependency inputs may have readable ACLs, but EVERY
                # observation still checks their strict unnamed-stream shape.
                options["strict_streams"] = True
            if live_output_max_bytes is not None:
                require(self.writable and self.private and not self.info.is_directory,
                        "Live output observation requires an exclusive private writer pin")
                options.update(live_output_max_bytes=live_output_max_bytes, live_output_min_bytes=live_output_min_bytes)
            info = self.api.inspect(self.handle, self.path, directory=self.info.is_directory,
                                    private=self.private, inherited_allowed=self.inherited_allowed, **options)
            require(info.identity == self.info.identity, "Pinned native identity changed")
            require(not self.immutable or info == self.info, "Pinned dependency source changed")
            return info

    def names(self, maximum, deadline):
        # Directory enumeration has a per-handle cursor. Cloned directory views
        # share this pin, so serialize the complete restart/continuation loop.
        with self.lock:
            require(self.references > 0 and self.info.is_directory, "Directory pin is closed or wrong-kind")
            return self.api.names(self.handle, maximum, deadline)


def _release(pins):
    errors = []
    for pin in reversed(pins):
        try:
            pin.release()
        except BaseException as error:
            errors.append(error)
    if errors:
        failure = FilesystemError("Native handle closure failed")
        for error in errors:
            _note(failure, type(error).__name__ + ": " + str(error)[:512])
            for detail in getattr(error, "__notes__", ()):
                _note(failure, detail)
        raise failure from errors[0]


def _acquire(pins):
    acquired = []
    try:
        for pin in pins:
            acquired.append(pin.acquire())
        return acquired
    except BaseException as error:
        _cleanup((lambda: _release(acquired),), error)
        raise


def _exit_close(owner, original):
    try:
        owner.close()
    except BaseException as error:
        if original is None:
            raise
        _note(original, "Native custody finalization also failed: " + str(error)[:512])
        for detail in getattr(error, "__notes__", ()):
            _note(original, detail)
    return False


class PrivateDirectory:
    def __init__(self, api, pins):
        self._operation_lock = threading.RLock()
        self._api, self._pins = api, pins
        self.path = Path(pins[-1].path)
        self.identity = pins[-1].info.identity
        self._closed = False

    def __enter__(self):
        self._live()
        return self

    def __exit__(self, kind, value, trace):
        return _exit_close(self, value)

    def _live(self):
        require(not self._closed, "Private directory is closed")

    @_locked
    def _clone(self):
        self._live()
        return PrivateDirectory(self._api, _acquire(self._pins))

    @_locked
    def verify(self):
        self._live()
        for pin in self._pins:
            pin.observe()
        return self._pins[-1].observe()

    @_locked
    def names(self, *, max_names, deadline=None):
        """One complete pinned listing, not a recursive snapshot or absence API."""
        return _directory_names(self, max_names, deadline)

    @_locked
    def _child(self, name, *, directory, create=False, writable=False, max_bytes=MAX_FILE_BYTES, deadline=None):
        self._live()
        component(name)
        end = _end(deadline)
        self.verify()
        parent = self._pins[-1]
        path = parent.path + "\\" + name
        require(len(self._pins) <= MAX_DEPTH and len(path.encode("utf-16-le")) < 65500,
                "Custody child path exceeds its depth/length bound")
        handle = self._api.child(parent.handle, name, directory=directory, create=create, writable=writable)
        pins = []
        with _on_exit(lambda: _close_native(self._api, handle), lambda: _release(pins)):
            info = self._api.inspect(handle, path, directory=directory, private=True, inherited_allowed=not create)
            require(info.identity[0] == self.identity[0], "Custody child crossed its pinned volume")
            require(directory or info.size <= max_bytes, "Native file exceeds its byte bound")
            pins = _acquire(self._pins)
            pins.append(_Pin(self._api, handle, path, info, private=True, inherited_allowed=not create, writable=writable))
            handle = None
            owner = (PrivateDirectory(self._api, pins) if directory else
                     NativeFile(self._api, pins, max_bytes=max_bytes, writable=writable, deadline=end))
            pins = []
            return owner

    def _walk_parent(self, relative, deadline):
        parts = relative_parts(relative)
        current = self._clone()
        try:
            for name in parts[:-1]:
                child = current._child(name, directory=True, deadline=deadline)
                try:
                    current.close()
                finally:
                    current = child
            return current, parts[-1]
        except BaseException as error:
            _exit_close(current, error)
            raise

    def create_directory(self, relative, *, deadline=None):
        return self._relative(relative, directory=True, create=True, deadline=deadline)

    def open_directory(self, relative, *, deadline=None):
        return self._relative(relative, directory=True, deadline=deadline)

    @_locked
    def _relative(self, relative, *, deadline=None, **options):
        end = _end(deadline)
        parent, name = self._walk_parent(relative, end)
        try:
            child = parent._child(name, deadline=end, **options)
        except BaseException as error:
            _exit_close(parent, error)
            raise
        try:
            parent.close()
        except BaseException as error:
            _exit_close(child, error)
            raise
        return child

    def create_file(self, relative, *, max_bytes, deadline=None):
        return self._file(relative, max_bytes=max_bytes, deadline=deadline, create=True)

    def open_file(self, relative, *, max_bytes, deadline=None):
        return self._file(relative, max_bytes=max_bytes, deadline=deadline, create=False)

    def _file(self, relative, *, max_bytes, deadline, create):
        _bound(max_bytes, MAX_FILE_BYTES, "file bytes", zero=True)
        return self._relative(relative, directory=False, create=create, writable=create,
                              max_bytes=max_bytes, deadline=deadline)

    @_locked
    def create_provider_command_file(self, *, max_bytes, deadline):
        """Create one externally mutable command file, never adopt an old output.

        This separate capability is not a NativeFile writer or snapshot. The
        caller must register it before any fallible post-return operation and
        retain it until actual native writer retirement and final reader close.
        """
        self._live()
        _bound(max_bytes, MAX_PROVIDER_COMMAND_BYTES, "provider command bytes", zero=True)
        require(deadline is not None, "Provider command file requires its original deadline")
        end = _end(deadline)
        self.verify()
        _check_time(end)
        parent = self._pins[-1]
        path = parent.path + "\\" + PROVIDER_COMMAND_NAME
        require(len(self._pins) <= MAX_DEPTH and len(path.encode("utf-16-le")) < 65500,
                "Provider command path exceeds its depth/length bound")
        handle = self._api.provider_command_file(parent.handle)
        pins = []
        with _on_exit(lambda: _close_native(self._api, handle), lambda: _release(pins)):
            _check_time(end)
            info = self._api.inspect(handle, path, directory=False, private=True)
            _check_time(end)
            require(info.identity[0] == self.identity[0] and info.size == 0,
                    "Provider command creation crossed a volume or was not empty")
            pins = _acquire(self._pins)
            pins.append(_Pin(self._api, handle, path, info, private=True))
            handle = None
            owner = _ProviderCommandFile(self._api, pins, max_bytes=max_bytes, deadline=end)
            _check_time(end)
            pins = []
            return owner

    def read_bytes(self, relative, *, max_bytes, deadline=None):
        _bound(max_bytes, MAX_READ_BYTES, "in-memory read", zero=True)
        with self.open_file(relative, max_bytes=max_bytes, deadline=deadline) as stream:
            return stream.read()

    def snapshot(self, *, max_bytes, max_members, deadline=None):
        return Snapshot(self, max_bytes=max_bytes, max_members=max_members, deadline=deadline)

    @_locked
    def close(self):
        if self._closed:
            return
        self._closed = True
        pins, self._pins = self._pins, []
        _release(pins)


class _ProviderCommandFile:
    """Fixed private path, mutable until freeze; no read/write/handle interface.

    Compatible pathname writers can overwrite or temporarily exceed the bound.
    Observations reject witnessed shrink/overflow, not unobserved history. The
    caller must establish whole-domain writer retirement before freeze(); a
    successful write-denying open alone does not prove that process fact or
    absence of writable mappings. No flush/durability claim is made by this
    read-access original. Failure is terminal; close never deletes/retries.
    """
    def __init__(self, api, pins, *, max_bytes, deadline):
        self._operation_lock = threading.RLock()
        self._api, self._pins = api, pins
        self.path, self.identity = Path(pins[-1].path), pins[-1].info.identity
        self.max_bytes, self._deadline = max_bytes, deadline
        self._size = 0
        self._closed = self._failed = False
        self._failed_pins = ()

    def _live(self):
        require(not self._closed and not self._failed, "Provider command owner is closed or failed")
        _check_time(self._deadline)

    def _ancestors(self):
        for pin in self._pins[:-1]:
            _check_time(self._deadline)
            pin.observe()
            _check_time(self._deadline)

    @_locked
    def observe(self):
        try:
            self._live()
            self._ancestors()
            pin = self._pins[-1]
            info = self._api.inspect(pin.handle, pin.path, directory=False, private=True,
                live_output_max_bytes=self.max_bytes, live_output_min_bytes=self._size)
            _check_time(self._deadline)
            require(info.identity == self.identity, "Provider command original identity changed")
            require(self._size <= info.size <= self.max_bytes, "Provider command size shrank or exceeded bound")
            self._size = info.size
            return info
        except BaseException:
            self._failed = True
            raise

    @_locked
    def freeze(self):
        """One overlapping strict-reader handoff, not native retirement evidence.

        The returned ordinary NativeFile keeps its original deadline and
        postchecks release of its own pins. The caller must still register it,
        read/verify/close it and postcheck after every other original owner
        closes; the reader cannot attest later directory/enclosing returns.
        """
        handle, pins, reader = None, [], None
        try:
            self._live()
            self._ancestors()
            parent, original = self._pins[-2:]
            handle = self._api.child(parent.handle, PROVIDER_COMMAND_NAME, directory=False)
            _check_time(self._deadline)
            info = self._api.inspect(handle, original.path, directory=False, private=True)
            _check_time(self._deadline)
            current = self._api.inspect(original.handle, original.path, directory=False, private=True)
            _check_time(self._deadline)
            require(info == current and info.identity == self.identity and self._size <= info.size <= self.max_bytes,
                    "Provider command final identity/info/size changed")
            self._ancestors()
            pins = _acquire(self._pins[:-1])
            pins.append(_Pin(self._api, handle, original.path, info, private=True))
            handle = None
            reader = NativeFile(self._api, pins, max_bytes=self.max_bytes, writable=False, deadline=self._deadline)
            pins = []
            _check_time(self._deadline)
            self.close()  # The new strict pin and all its ancestors are already held.
            _check_time(self._deadline)
            return reader
        except BaseException as error:
            self._failed = True
            # Keep failed ownership references for the outer owner's quarantine;
            # a failed close is never permission to retry a possibly reused handle.
            self._failed_pins += tuple(pins) + tuple(reader._pins if reader is not None else ())
            _cleanup((lambda: _close_native(self._api, handle), lambda: _release(pins),
                      lambda: reader.close() if reader is not None else None), error)
            raise

    @_locked
    def close(self):
        if self._closed:
            return
        self._closed = True
        pins, self._pins = self._pins, []
        failure = None
        try:
            _check_time(self._deadline)
        except BaseException as error:
            failure = error
        try:
            if failure is not None:
                _cleanup((lambda: _release(pins),), failure)
                raise failure
            _release(pins)
            _check_time(self._deadline)
        except BaseException:
            self._failed = True
            self._failed_pins += tuple(pins)
            raise


class NativeFile(io.RawIOBase):
    """Bounded binary stream retaining parent pins; never transfer its borrowed handle.

    A native process owner may DuplicateHandle(native_handle) into an explicit
    child handle list, keeping this object alive until the child/duplicate retires.
    Such writes bypass write(): the owner MUST observe_live_output() while the
    child may write, then strictly verify/sync only after its duplicates retire.
    fileno() is intentionally unsupported: Win32 handles are not CRT descriptors.
    readall() shares read()'s aggregate materialization limit; line-reading and
    implicit iteration are unsupported. Archive callers use bounded binary reads.
    """

    def __init__(self, api, pins, *, max_bytes, writable, deadline):
        self._operation_lock = threading.RLock()
        super().__init__()
        self._api, self._pins, self.max_bytes = api, pins, max_bytes
        self._writable, self._deadline = writable, deadline
        self.path, self.identity = Path(pins[-1].path), pins[-1].info.identity
        self.initial_info = pins[-1].info
        self._live_output_size = self.initial_info.size
        self.final_info = None
        self._retired = False
        self._provider_log_started = self._provider_log_active = self._provider_log_unknown = False
        self._provider_log_failure = self._provider_log_reader = None
        self._provider_log_secondary = ()

    @property
    @_locked
    def native_handle(self):
        require(not self.closed and not self._retired and not self._provider_log_unknown, "Native file is closed or UNKNOWN")
        return self._pins[-1].handle

    @_locked
    def readable(self):
        return not self.closed and not self._retired and not self._provider_log_unknown and not self._writable

    @_locked
    def writable(self):
        return not self.closed and not self._retired and not self._provider_log_unknown and self._writable

    @_locked
    def seekable(self):
        return not self.closed and not self._retired and not self._provider_log_unknown

    @_locked
    def tell(self):
        position = self._api.seek(self.native_handle, 0, 1)
        require(0 <= position <= self.max_bytes, "Native file position exceeds its byte bound")
        return position

    @_locked
    def seek(self, offset, whence=0):
        require(type(offset) is int and type(whence) is int and whence in (0, 1, 2), "Invalid native file seek")
        origin = 0 if whence == 0 else self.tell() if whence == 1 else self.verify().size
        require(0 <= origin + offset <= self.max_bytes, "Native seek exceeds its byte bound")
        return self._api.seek(self.native_handle, origin + offset, 0)

    @_locked
    def read(self, size=-1):
        require(self.readable() and type(size) is int and size >= -1, "Native file is not an admitted reader")
        _check_time(self._deadline)
        remaining = self.initial_info.size - self.tell()
        require(remaining >= 0, "Reader position exceeds the original file size")
        count = remaining if size == -1 else min(size, remaining)
        require(count <= MAX_READ_BYTES, "Use bounded streaming reads instead of materializing a large native file")
        output = bytearray()
        while len(output) < count:
            _check_time(self._deadline)
            part = self._api.read(self.native_handle, min(CHUNK, count - len(output)))
            require(part, "Native file was truncated during its bounded read")
            output.extend(part)
        return bytes(output)

    def readall(self):
        # RawIOBase.readall() repeatedly calls read() and materializes the whole
        # result, bypassing a per-call cap. Keep the aggregate read bound here.
        return self.read()

    def readline(self, size=-1):
        raise io.UnsupportedOperation("Native custody streams require bounded binary reads, not line materialization")

    def readlines(self, hint=-1):
        raise io.UnsupportedOperation("Native custody streams require bounded binary reads, not line materialization")

    def __iter__(self):
        raise io.UnsupportedOperation("Native custody streams require explicit bounded binary reads")

    def __next__(self):
        raise io.UnsupportedOperation("Native custody streams require explicit bounded binary reads")

    @_locked
    def readinto(self, buffer):
        data = self.read(min(len(buffer), CHUNK))
        buffer[:len(data)] = data
        return len(data)

    @_locked
    def write(self, data):
        require(self.writable(), "Native file is not an exclusive writer")
        _check_time(self._deadline)
        view = memoryview(data).cast("B")
        require(self.tell() + len(view) <= self.max_bytes, "Native output exceeds its byte bound")
        total = 0
        while total < len(view):
            _check_time(self._deadline)
            total += self._api.write(self.native_handle, bytes(view[total:total + CHUNK]))
        return total

    @_locked
    def observe_live_output(self):
        """Bound a live child writer, not an immutable snapshot or retirement proof.

        Ancestors stay strict. Only this exclusive private file pin permits
        monotonic growth across the separate size queries; both sizes are bounded.
        No final_info is published: post-drain verification/readback remains
        mandatory. Ordinary readers still require close/reopen; the two provider
        logs may use their separate original-writer-pinned byte-only readback.
        """
        _check_time(self._deadline)
        require(self.writable(), "Native file is not an exclusive writer")
        for pin in self._pins[:-1]:
            pin.observe()
        current = self._pins[-1].observe(live_output_max_bytes=self.max_bytes,
                                         live_output_min_bytes=self._live_output_size)
        require(current.size <= self.max_bytes, "Native output exceeds its byte bound")
        require(current.size >= self._live_output_size, "Native live output shrank between observations")
        self._live_output_size = current.size
        return current

    @_locked
    def read_provider_log(self):
        """One bounded byte-only read while the ORIGINAL writer denies sharing.

        The caller must first establish whole-domain writer retirement; this
        method cannot prove it. No permissive reader/handle is returned.
        Any failed supplier/check episode is conservatively UNKNOWN, even when
        the temporary reader's close is known. Retain the original owner and any
        unresolved private reader reference; never retry.
        """
        if self._provider_log_failure is not None:
            raise self._provider_log_failure
        try:
            require(not self._provider_log_started, "Provider log readback is one-use only")
        except BaseException as error:
            self._provider_log_failure = error
            raise
        self._provider_log_started = self._provider_log_active = True
        api, pins, end, maximum = self._api, self._pins, self._deadline, self.max_bytes
        originals, raw, admitted = tuple(pins), None, False

        def failed(error, *, unknown=False):
            # An opener may fail before returning its acquired handle; notes or
            # causes cannot establish that every provisional obligation retired.
            self._provider_log_unknown |= admitted or unknown
            if self._provider_log_failure is None:
                self._provider_log_failure = error
            elif error is not self._provider_log_failure:
                self._provider_log_secondary += (error,)

        def checked():
            if self._provider_log_failure is not None:
                raise self._provider_log_failure
            require(self._api is api and self._pins is pins and len(pins) == len(originals) and
                    all(pin is original for pin, original in zip(pins, originals)) and
                    self._deadline == end and type(self._deadline) is type(end) and
                    type(self.max_bytes) is int and self.max_bytes == maximum and self.writable(),
                    "Provider log original writer changed")
            _check_time(end)

        try:
            require(type(self) is NativeFile and len(pins) >= 2 and pins[-1].private and pins[-1].writable and
                    not pins[-1].info.is_directory, "Provider log requires its original private writer")
            _bound(maximum, MAX_PROVIDER_LOG_BYTES, "provider log bytes", zero=True)
            name = pins[-1].path.rsplit("\\", 1)[-1]
            require(name in PROVIDER_LOG_NAMES and str(self.path) == pins[-1].path and
                    self.identity == pins[-1].info.identity, "Provider log original path differs")
            admitted = True  # Pure shape rejection above performs no native work.
            checked()
            self.sync()
            checked()
            before = self.verify()
            checked()
            # Save the actual handle before any post-return callback/check.
            self._provider_log_reader = api.provider_log_reader(pins[-2].handle, name)
            checked()
            require(api.inspect(self._provider_log_reader, pins[-1].path, directory=False, private=True) == before,
                    "Provider log readback identity or metadata differs")
            checked()
            require(api.seek(self._provider_log_reader, 0, 0) == 0, "Provider log readback position differs")
            checked()
            output = bytearray()
            while len(output) < before.size:
                checked()
                count = min(CHUNK, before.size - len(output))
                part = api.read(self._provider_log_reader, count)
                checked()
                require(type(part) is bytes and 0 < len(part) <= count, "Provider log readback was truncated or oversized")
                output.extend(part)
            checked()  # Last growth (or empty allocation) precedes the next native inspect.
            require(api.inspect(self._provider_log_reader, pins[-1].path, directory=False, private=True) == before,
                    "Provider log changed during readback")
            checked()
            require(self.verify() == before, "Provider log original changed during readback")
            checked()
            raw = bytes(output)
            checked()
        except BaseException as error:
            failed(error)
        finally:
            if self._provider_log_reader is not None:
                try:
                    # This is the successfully returned original handle. Keep
                    # its first close failure even if attaching a note fails.
                    api.close(self._provider_log_reader)
                except BaseException as error:
                    failed(error, unknown=True)
                else:
                    self._provider_log_reader = None
            try:
                _check_time(end)  # The temporary reader close spends the ORIGINAL end too.
                checked()
                require(self.verify() == before, "Provider log original changed before reader retirement")
                checked()
            except BaseException as error:
                failed(error)
            self._provider_log_active = False
        if self._provider_log_unknown:
            try:
                _note(self._provider_log_failure, "Native provider log readback retirement UNKNOWN; retain original writer")
            except BaseException as detail:
                failed(detail, unknown=True)
        if self._provider_log_failure is not None:
            raise self._provider_log_failure
        return raw

    @_locked
    def verify(self):
        _check_time(self._deadline)
        require(not self.closed and not self._retired and not self._provider_log_unknown, "Native file is closed or UNKNOWN")
        for pin in self._pins:
            current = pin.observe()
        require(current.size <= self.max_bytes and (self._writable or current == self.initial_info),
                "Native input changed or output exceeded its byte bound")
        self.final_info = current
        return current

    @_locked
    def flush(self):
        if self._writable and not self.closed and not self._retired:
            self._api.flush(self.native_handle)

    sync = flush

    @_locked
    def close(self):
        if self._provider_log_active:
            if self._provider_log_failure is None:
                self._provider_log_failure = FilesystemError("Provider log readback is active")
            raise self._provider_log_failure
        if self._provider_log_unknown:
            raise self._provider_log_failure
        if self.closed or self._retired:
            return
        errors = []
        try:
            self.flush()
            self.verify()
        except BaseException as error:
            errors.append(error)
        finally:
            try:
                super().close()
            except BaseException as error:
                errors.append(error)
            pins, self._pins = self._pins, []
            try:
                _release(pins)
            except BaseException as error:
                errors.append(error)
            self._retired = True
            try:
                # Charge final flush/verification and every owned pin release
                # to the same deadline; cleanup and the first failure survive.
                _check_time(self._deadline)
            except BaseException as error:
                errors.append(error)
        if errors:
            failure = FilesystemError("Native file finalization failed")
            for error in errors:
                _note(failure, type(error).__name__ + ": " + str(error)[:512])
                for detail in getattr(error, "__notes__", ()):
                    _note(failure, detail)
            raise failure from errors[0]

    def __exit__(self, kind, value, trace):
        return _exit_close(self, value)


def _root(path, api, *, create):
    drive, parts = absolute_parts(path)
    pins, handle = [], None
    with _on_exit(lambda: _close_native(api, handle), lambda: _release(pins)):
        handle = api.drive(drive)
        info = api.inspect(handle, drive, directory=True)
        pins.append(_Pin(api, handle, drive, info, private=False))
        handle = None
        for index, name in enumerate(parts):
            parent = pins[-1]
            last = index == len(parts) - 1
            native_path = parent.path + ("" if parent.path.endswith("\\") else "\\") + name
            handle = api.child(parent.handle, name, directory=True, create=create and last)
            info = api.inspect(handle, native_path, directory=True, private=last)
            require(info.identity[0] == pins[0].info.identity[0], "Root path crossed its pinned local volume")
            pins.append(_Pin(api, handle, native_path, info, private=last))
            handle = None
        root = PrivateDirectory(api, pins)
        pins = []
        return root


def create_private_directory(path):
    """Create exactly one new protected directory below existing physical parents."""
    return _root(path, _WinApi(), create=True)


def open_private_directory(path):
    """Open a protected private root; arbitrary inherited roots are not admitted."""
    return _root(path, _WinApi(), create=False)


def _directory_names(directory, maximum, deadline):
    _bound(maximum, MAX_MEMBERS, "directory names")
    end = _end(deadline)
    before = directory.verify()
    names = directory._pins[-1].names(maximum, end)
    require(len(names) <= maximum and len(set(name.casefold() for name in names)) == len(names),
            "Directory has duplicate aliases or exceeds member bound")
    for name in names:
        component(name)
    require(directory.verify() == before, "Directory changed during its complete listing")
    _check_time(end)
    return tuple(sorted(names))


class DependencySourceDirectory:
    """Read-only public dependency bytes; never private evidence or a writer.

    It shares the existing native supplier and pins, not PrivateDirectory's
    writable API or ACL policy. Source roots/selected ancestors always retain
    strict ADS checks, including later NativeFile verification observations.
    """

    def __init__(self, api, pins):
        self._operation_lock = threading.RLock()
        self._api, self._pins, self._closed = api, pins, False
        self.path, self.identity = Path(pins[-1].path), pins[-1].info.identity

    @_locked
    def verify(self):
        require(not self._closed, "Dependency source directory is closed")
        for pin in self._pins:
            current = pin.observe()
        require(current == self._pins[-1].info, "Dependency source directory changed")
        return current

    @_locked
    def names(self, *, max_names, deadline=None):
        return _directory_names(self, max_names, deadline)

    @_locked
    def _child(self, name, *, directory, max_bytes=MAX_FILE_BYTES, deadline=None):
        component(name)
        end = _end(deadline)
        self.verify()
        parent = self._pins[-1]
        path = parent.path + "\\" + name
        require(len(self._pins) <= MAX_DEPTH and len(path.encode("utf-16-le")) < 65500,
                "Dependency source path exceeds its depth/length bound")
        handle = self._api.child(parent.handle, name, directory=directory)
        pins = []
        with _on_exit(lambda: _close_native(self._api, handle), lambda: _release(pins)):
            info = self._api.inspect(handle, path, directory=directory, strict_streams=True)
            require(info.identity[0] == self.identity[0], "Dependency source crossed its pinned volume")
            require(directory or info.size <= max_bytes, "Dependency source exceeds its byte bound")
            self.verify()
            pins = _acquire(self._pins)
            pins.append(_Pin(self._api, handle, path, info, private=False, strict_streams=True, immutable=True))
            handle = None
            result = (DependencySourceDirectory(self._api, pins) if directory else
                      NativeFile(self._api, pins, max_bytes=max_bytes, writable=False, deadline=end))
            pins = []
            return result

    def open_directory(self, name, *, deadline=None):
        return self._child(name, directory=True, deadline=deadline)

    def open_file(self, name, *, max_bytes, deadline=None):
        _bound(max_bytes, MAX_FILE_BYTES, "file bytes", zero=True)
        return self._child(name, directory=False, max_bytes=max_bytes, deadline=deadline)

    @_locked
    def close(self):
        if self._closed:
            return
        pins = self._pins
        try:
            with _on_exit(lambda: _release(pins)):
                self.verify()
        finally:
            self._closed, self._pins = True, []


def _dependency_source_root(path, api):
    drive, parts = absolute_parts(path)
    pins, handle = [], None
    with _on_exit(lambda: _close_native(api, handle), lambda: _release(pins)):
        handle = api.drive(drive)
        info = api.inspect(handle, drive, directory=True, strict_streams=True)
        pins.append(_Pin(api, handle, drive, info, private=False, strict_streams=True))
        handle = None
        for index, name in enumerate(parts):
            parent = pins[-1]
            native_path = parent.path + ("" if parent.path.endswith("\\") else "\\") + name
            handle = api.child(parent.handle, name, directory=True)
            info = api.inspect(handle, native_path, directory=True, strict_streams=True)
            require(info.identity[0] == pins[0].info.identity[0], "Dependency source crossed its pinned volume")
            pins.append(_Pin(api, handle, native_path, info, private=False, strict_streams=True,
                             immutable=index == len(parts) - 1))
            handle = None
        result = DependencySourceDirectory(api, pins)
        pins = []
        return result


def open_dependency_source(path):
    """Open only existing public input; never create, rewrite ACLs, save or delete."""
    return _dependency_source_root(path, _WinApi())


class Snapshot:
    """Pinned immutable byte inventory; close it before any owned evidence cleanup."""

    def __init__(self, root, *, max_bytes, max_members, deadline=None):
        self._operation_lock = threading.RLock()
        _bound(max_bytes, MAX_FILE_BYTES, "snapshot bytes", zero=True)
        _bound(max_members, MAX_MEMBERS, "snapshot members")
        self._deadline = _end(deadline)
        self._root, self._directories, self._files, self._names = root._clone(), {}, {}, {}
        self._closed = False
        entries, total = {}, 0
        self._directories[""] = self._root
        try:
            pending = [("", self._root, 0)]
            while pending:
                _check_time(self._deadline)
                name, directory, depth = pending.pop()
                require(depth <= MAX_DEPTH, "Snapshot directory depth exceeds bound")
                if name == "":
                    entries[name] = directory.verify()
                names = directory._pins[-1].names(max_members, self._deadline)
                self._names[name] = tuple(sorted(names))
                for child_name in names:
                    require(len(entries) < max_members, "Snapshot member count exceeds bound")
                    child_path = name + "/" + child_name if name else child_name
                    # Native opens use FILE_NON_DIRECTORY_FILE / FILE_DIRECTORY_FILE.
                    # Query the kind with an attribute-only open, never infer it
                    # from filename extensions or from a failed file open.
                    kind = directory._api.kind(directory._pins[-1].handle, child_name)
                    if kind:
                        child = directory._child(child_name, directory=True, deadline=self._deadline)
                        self._directories[child_path] = child
                        entries[child_path] = child.verify()
                        pending.append((child_path, child, depth + 1))
                    else:
                        child = directory._child(child_name, directory=False, max_bytes=max_bytes - total,
                                                 deadline=self._deadline)
                        self._files[child_path] = child
                        entries[child_path] = child.initial_info
                        total += child.initial_info.size
                        require(total <= max_bytes, "Snapshot byte count exceeds bound")
            self.entries = MappingProxyType(entries)
            self.total_bytes = total
            self.verify()
        except BaseException as error:
            _exit_close(self, error)
            raise

    def __enter__(self):
        require(not self._closed, "Snapshot is closed")
        return self

    def __exit__(self, kind, value, trace):
        return _exit_close(self, value)

    @_locked
    def open_file(self, relative):
        require(not self._closed and relative in self._files, "File is not a pinned snapshot member")
        self._files[relative].verify()
        stream = self._root.open_file(relative, max_bytes=self.entries[relative].size, deadline=self._deadline)
        try:
            require(stream.initial_info == self.entries[relative], "Snapshot file identity changed")
            return stream
        except BaseException as error:
            _exit_close(stream, error)
            raise

    @_locked
    def verify(self):
        require(not self._closed, "Snapshot is closed")
        _check_time(self._deadline)
        for name, directory in self._directories.items():
            require(directory.verify() == self.entries[name], "Snapshot directory metadata changed")
            names = directory._pins[-1].names(MAX_MEMBERS, self._deadline)
            require(tuple(sorted(names)) == self._names[name], "Snapshot membership changed")
        for name, stream in self._files.items():
            require(stream.verify() == self.entries[name], "Snapshot file changed")
        return self.entries

    @_locked
    def close(self):
        if self._closed:
            return
        self._closed = True
        errors = []
        for owner in [*self._files.values(), *reversed(list(self._directories.values()))]:
            try:
                owner.close()
            except BaseException as error:
                errors.append(error)
        if errors:
            failure = FilesystemError("Native snapshot finalization failed")
            for error in errors:
                _note(failure, type(error).__name__ + ": " + str(error)[:512])
                for detail in getattr(error, "__notes__", ()):
                    _note(failure, detail)
            raise failure from errors[0]
