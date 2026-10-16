"""Inactive ordinary-CI facade pipe: loss observations, never process authority.

The facade alone retains the writer. It sends NO bytes. Empty/open means only
UNDECIDED: the keeper still needs an independently checked exact facade lifetime,
immutable deadlines and the canonical cancellation interface. EOF, data, invalid
descriptor state or read uncertainty permanently requests cancellation.

Transfer contract: prepare the reader's spawn_plan(), use an exec-based spawn
with exactly its close_fds/pass_fds, then call keeper_started(plan) ONLY after
confirmed spawn. A failed spawn leaves the parent reader owned and available for
explicit cleanup. The keeper immediately adopt_inherited(fd)s its received copy
before any descendants; adoption sets CLOEXEC again. Never duplicate/pass the
writer or use a fork-only child. This module does not spawn or authenticate that
contract. Exclusive serialized FD ownership is a CALLER PREREQUISITE, not a
guarantee supplied by this helper: no external close, duplication, dup2 or
replacement beyond the explicit reader-transfer contract. Borrowed reader
numbers are for pass_fds only. Keeping _fd private does not enforce exclusion.

The fingerprint detects some accidental mismatches only. It is not a lifetime
or generation token: Darwin pipe st_ino hashes a recyclable pipe address, so
pipe-to-pipe ABA can match. External replacement can also race fstat and the
following read/close. Neither a matching fingerprint nor an open pipe proves
the exact facade lifetime. The caller's outer watchdog remains mandatory:
CPython PEP475 may retry EINTR internally even without an application retry loop.
"""
from __future__ import annotations

from dataclasses import dataclass
import errno
import os
import stat

try:
    import fcntl
except ImportError:
    fcntl = None


SCOPE = "ORDINARY_CI_PIPE_OBSERVATIONS_NOT_NATIVE_OR_RELEASE_QUALIFICATION"
_CREATE = object()


def _fingerprint(fd: int, access: int) -> tuple[int, int, int, int]:
    if fcntl is None or os.name != "posix" or type(fd) is not int or fd < 3:
        raise ValueError("Private POSIX pipe descriptor required")
    info = os.fstat(fd)
    mode = fcntl.fcntl(fd, fcntl.F_GETFL) & os.O_ACCMODE
    if not stat.S_ISFIFO(info.st_mode) or mode != access:
        raise ValueError("Wrong pipe endpoint")
    return info.st_dev, info.st_ino, stat.S_IFMT(info.st_mode), mode


@dataclass(frozen=True)
class PipeObservation:
    state: str
    reason: str | None = None


@dataclass(frozen=True)
class KeeperSpawnPlan:
    """Private borrowed descriptors, not evidence that a keeper was launched."""
    pass_fds: tuple[int, ...]
    close_fds: bool = True


class _DescriptorOwner:
    def __init__(self, fd: int, access: int, token: object):
        if token is not _CREATE:
            raise ValueError("Use the pipe factory or inherited-reader adoption")
        self._fingerprint = _fingerprint(fd, access)
        self._access = access
        self._fd = fd
        self._close_result = None

    def _owned_fd(self) -> int | None:
        if self._fd is None:
            return None
        try:
            matches = _fingerprint(self._fd, self._access) == self._fingerprint
        except (OSError, ValueError):
            matches = False
        if not matches:
            # A mismatch/unknown observation relinquishes this local number.
            # A match is only a heuristic under exclusive ownership, not a
            # generation token or protection from ABA/check-use races.
            self._fd = None
            self._close_result = False
        return self._fd

    def close(self) -> bool:
        """Under exclusive ownership, consume local state before one os.close call.

        True means os.close returned successfully, not that another process
        retired or external descriptor replacement was excluded. False remains
        false after an error, including EINTR. Once this owner consumes _fd, its
        later calls cannot retry that cached number. This does not protect a
        first close from external replacement before/during its check-use gap.
        """
        fd = self._owned_fd()
        if fd is None:
            return self._close_result is True
        self._fd = None
        try:
            os.close(fd)
        except OSError:
            self._close_result = False
        else:
            self._close_result = True
        return self._close_result


class FacadeWriteEnd(_DescriptorOwner):
    """Sole retained writer; intentionally no write, duplicate or transfer API."""


class KeeperReadEnd(_DescriptorOwner):
    def __init__(self, fd: int, token: object):
        super().__init__(fd, os.O_RDONLY, token)
        self._observation = PipeObservation("UNDECIDED")
        self._plan = None

    @classmethod
    def adopt_inherited(cls, fd: int) -> KeeperReadEnd:
        """Consume a separately received reader, not an existing local owner's fd.

        Under the exclusive-ownership prerequisite, invalid input remains
        caller-owned: a detected writer or unrelated descriptor is not closed
        or reconfigured by refused adoption. Validation is not an atomic
        descriptor-generation check and cannot exclude external replacement.
        """
        _fingerprint(fd, os.O_RDONLY)
        if not (fcntl.fcntl(fd, fcntl.F_GETFL) & os.O_NONBLOCK):
            raise ValueError("Nonblocking pipe reader required")
        os.set_inheritable(fd, False)
        if os.get_inheritable(fd):
            raise ValueError("Non-inheritable pipe reader required")
        return cls(fd, _CREATE)

    def _cancel(self, reason: str) -> PipeObservation:
        if self._observation.state != "CANCEL":
            self._observation = PipeObservation("CANCEL", reason)
        return self._observation

    def _readable_fd(self) -> int | None:
        fd = self._owned_fd()
        if fd is None:
            self._cancel("DESCRIPTOR_UNCERTAIN")
            return None
        try:
            safe = (fcntl.fcntl(fd, fcntl.F_GETFL) & os.O_NONBLOCK) and not os.get_inheritable(fd)
        except OSError:
            safe = False
        if not safe:
            self._cancel("DESCRIPTOR_FLAGS")
            return None
        return fd

    def observe(self) -> PipeObservation:
        if self._observation.state == "CANCEL":
            return self._observation
        fd = self._readable_fd()
        if fd is None:
            return self._observation
        try:
            # One-byte request, no byte protocol or application-level retry.
            # CPython PEP475 may retry EINTR; this is not a whole-call watchdog.
            data = os.read(fd, 1)
        except BlockingIOError as error:
            if error.errno in (errno.EAGAIN, errno.EWOULDBLOCK):
                return self._observation
            return self._cancel("READ_ERROR")
        except OSError as error:
            if error.errno == errno.EBADF:
                self._fd = None  # Relinquish the number; this owner will not retry its close.
                self._close_result = False
            return self._cancel("READ_ERROR")
        if type(data) is not bytes:
            return self._cancel("READ_RESULT_INVALID")
        return self._cancel("UNEXPECTED_DATA" if data else "EOF")

    def spawn_plan(self) -> KeeperSpawnPlan:
        """Borrow only the reader; retain it until confirmed spawn or cleanup."""
        if self._observation.state == "CANCEL":
            raise ValueError("Cancelled reader cannot prepare a keeper")
        fd = self._readable_fd()
        if fd is None:
            raise ValueError("Reader transfer unavailable")
        if self._plan is None:
            self._plan = KeeperSpawnPlan((fd,))
        return self._plan

    def keeper_started(self, plan: KeeperSpawnPlan) -> bool:
        """Caller confirms actual spawn; this is not a process/native admission."""
        if plan is not self._plan or self._plan is None:
            raise ValueError("Exact outstanding reader transfer required")
        self._plan = None
        return self.close()

    def close(self) -> bool:
        self._plan = None
        self._cancel("CLOSED")
        return super().close()


def open_facade_pipe() -> tuple[FacadeWriteEnd, KeeperReadEnd]:
    """Allocate only this process's pipe; callers explicitly close both owners."""
    if fcntl is None or os.name != "posix":
        raise ValueError("POSIX liveness pipe required")
    reader_fd, writer_fd = os.pipe()  # CPython creates both descriptors non-inheritable.
    reader = writer = None
    complete = False
    try:
        os.set_inheritable(reader_fd, False)
        os.set_inheritable(writer_fd, False)
        os.set_blocking(reader_fd, False)
        reader = KeeperReadEnd.adopt_inherited(reader_fd)
        reader_fd = None
        writer = FacadeWriteEnd(writer_fd, os.O_WRONLY, _CREATE)
        writer_fd = None
        complete = True
        return writer, reader
    finally:
        if not complete:
            cleanup_ok = True
            for owner in (reader, writer):
                if owner is not None:
                    cleanup_ok = owner.close() and cleanup_ok
            for fd in (reader_fd, writer_fd):
                if fd is not None:
                    try:
                        os.close(fd)
                    except OSError:
                        cleanup_ok = False
            if not cleanup_ok:
                raise OSError("Pipe allocation cleanup uncertain") from None
