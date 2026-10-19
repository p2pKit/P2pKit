"""Fixed native smoke selection and original-file custody, not source/account authorization.

The operator must independently review the exact build and supply its expected
digest. No manifest, filename or matching digest authorizes its own execution.
The canonical installed supervisor owns all processes and the original 30s limit.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import re

OPERATIONS = {
    "native-custody": "--disposable-custody-smoke",
    "native-restart": "--disposable-custody-restart-smoke",
}
FILE_NAME = "p2pkit-windows-profile-smoke.exe"
MAXIMUM_BYTES = 4 * 1024 * 1024
LOG_LIMIT = 65536
SCOPE = "NATIVE_SMOKE_SUPERVISION_NOT_JNI_OR_HOST_CLIENT_QUALIFICATION"


def require(value):
    if not value:
        raise ValueError("WINDOWS_NATIVE_SMOKE_BINDING_REFUSED")


def validate_arguments(args):
    directory = getattr(args, "native_directory", None)
    digest = getattr(args, "native_sha256", None)
    if args.operation in OPERATIONS:
        require(type(directory) is str and Path(directory).is_absolute())
        require(type(digest) is str and re.fullmatch(r"[0-9a-f]{64}", digest) is not None)
    else:
        require(directory is None and digest is None)


def extra_arguments(args):
    validate_arguments(args)
    return (["--native-directory", args.native_directory, "--native-sha256", args.native_sha256]
            if args.operation in OPERATIONS else [])


def executable(args):
    validate_arguments(args)
    require(args.operation in OPERATIONS)
    return Path(args.native_directory) / FILE_NAME


def matches(raw, operation):
    require(operation in OPERATIONS)
    scope = (b"SCOPE real-native-custody-smoke-only; NOT transactions/JNI/loader/MSI qualification"
             if operation == "native-custody" else
             b"SCOPE cold-composite-write-session-reopen-only; NOT crash/encrypted-profile/JNI/loader/MSI qualification")
    if type(raw) is not bytes or not 0 < len(raw) <= LOG_LIMIT:
        return False
    lines = raw.splitlines()
    return (len(lines) > 2 and lines[0] == scope and
            lines[-1] == b"RESULT code=0; canonical-fixtures-retained; exit-zero-required" and
            all(re.fullmatch(rb"PASS [A-Za-z0-9_.-]+|CASE (stage|candidate|write-record)-size-index=[0-2]", line)
                for line in lines[1:-1]))


def run(args, deadline, E, F, private):
    """Retain original executable plus ancestors until E observed exit/descendant cleanup."""
    validate_arguments(args)
    root = file = None
    try:
        root = F.open_private_directory(args.native_directory)
        file = root.open_file(FILE_NAME, max_bytes=MAXIMUM_BYTES, deadline=deadline.monotonic_end(5))
        data = file.read()
        require(512 <= len(data) <= MAXIMUM_BYTES and hashlib.sha256(data).hexdigest() == args.native_sha256)
        pe = int.from_bytes(data[60:64], "little")
        require(data[:2] == b"MZ" and 64 <= pe <= len(data) - 26 and data[pe:pe + 4] == b"PE\0\0")
        require(int.from_bytes(data[pe + 4:pe + 6], "little") == 0x8664)
        require(int.from_bytes(data[pe + 24:pe + 26], "little") == 0x20b)
        require(int.from_bytes(data[pe + 22:pe + 24], "little") & 0x2002 == 0x0002)
        before = file.verify()
        work, cleanup = deadline.worker_budgets()
        # No command/argument/environment-path override. F denies write/delete sharing, rejects
        # reparse/hard-link/ADS/ACL ambiguity, and retains all original ancestor handles.
        outcome = E.run_command([str(file.path), OPERATIONS[args.operation]], cwd=root.path,
            environment=dict(os.environ), private=private, timeout=work,
            cleanup_seconds=cleanup, log_limit=LOG_LIMIT)
        deadline.check(2)
        require(file.verify() == before)
        root.verify()
        return outcome
    finally:
        # Each original close attempted once. A failed close cannot yield an accepted worker result.
        failure = None
        for owner in (file, root):
            if owner is not None:
                try:
                    owner.close()
                    deadline.check(1)
                except BaseException as error:
                    if failure is None:
                        failure = error
        if failure is not None:
            raise failure
