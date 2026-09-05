#!/usr/bin/env python3
"""Serialize launcher-lock metadata on macOS without the nonstandard flock CLI.

The empty .guard inode must remain in place while launchers may be running.
Its kernel lock covers short metadata transactions, not an entire Xcode build.
The directory records the launcher and its current foreground mutating worker.
"""

import argparse
import contextlib
import fcntl
import os
import pathlib
import re
import stat
import sys


def read_pid(path):
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK), "rb") as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
            raise ValueError("owner record is not a regular file")
        raw = stream.read(65)
    if len(raw) > 64:
        raise ValueError("oversized owner record")
    value = raw.decode("ascii").strip()
    if not re.fullmatch(r"[1-9][0-9]{0,9}", value) or int(value) > 2**31 - 1:
        raise ValueError("invalid owner PID")
    return int(value)


def alive(pid):
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True  # An inaccessible process is not proof of a stale owner.


def owners(lock):
    try:
        if not stat.S_ISDIR(lock.lstat().st_mode):
            raise ValueError("lock is not a directory")
        entries = {entry.name for entry in lock.iterdir()}
        if entries not in ({"pid"}, {"pid", "worker"}):
            raise ValueError("missing owner or unexpected lock contents")
        return read_pid(lock / "pid"), read_pid(lock / "worker") if "worker" in entries else None
    except (OSError, ValueError) as error:
        raise ValueError(
            f"cannot establish launcher ownership at {lock}: {error}. "
            "Do not remove it until all launchers and their build workers have stopped; "
            "then inspect and remove only its pid/worker records and the empty lock directory."
        ) from error


def remove_lock(lock, worker):
    if worker is not None:
        (lock / "worker").unlink()
    (lock / "pid").unlink()
    lock.rmdir()  # Never recursively delete unexpected or caller-owned contents.


@contextlib.contextmanager
def metadata_guard(lock):
    # Never unlink this file: doing so would let contenders lock different inodes.
    fd = os.open(str(lock) + ".guard", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "r+") as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise ValueError("launcher metadata guard must be a regular, unshared file")
        fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
        yield


def operate(action, lock, owner_pid, command):
    if action == "acquire":
        try:
            lock.parent.mkdir(parents=True, exist_ok=True)
        except OSError as error:
            raise ValueError(f"cannot prepare launcher lock parent {lock.parent}: {error}") from error
    elif action == "cleanup" and not lock.parent.exists():
        return
    with metadata_guard(lock):
        if action == "cleanup" and not lock.exists() and not lock.is_symlink():
            return
        if action == "acquire":
            if lock.exists() or lock.is_symlink():
                owner, worker = owners(lock)
                if alive(owner) or (worker is not None and alive(worker)):
                    raise ValueError(
                        f"another launcher owns {lock} (pid {owner}, worker {worker or 'none'}). "
                        "Wait for that launcher and its foreground build worker to finish."
                    )
                remove_lock(lock, worker)
                print(f"[ios-run] Reclaimed stale launcher lock at {lock} (dead pid {owner}).")
            lock.mkdir()
            try:
                with (lock / "pid").open("x") as stream:
                    try:
                        stream.write(f"{owner_pid}\n")
                        stream.flush()
                    except OSError:
                        (lock / "pid").unlink()
                        raise
            except OSError:
                lock.rmdir()
                raise
            return

        owner, worker = owners(lock)
        if action == "cleanup" and owner != owner_pid:
            return
        if owner != owner_pid or not alive(owner_pid):
            raise ValueError(f"launcher does not own {lock}; refusing {action}")
        if worker is not None and alive(worker):
            raise ValueError(f"foreground worker {worker} still owns {lock}; refusing {action}")
        if action in ("release", "cleanup"):
            remove_lock(lock, worker)
            return

        # Register before exec, under the same guard as stale recovery. If Bash
        # is killed first, either this transaction refuses the dead owner or a
        # subsequent launcher sees this live worker and cannot reclaim its lock.
        with (lock / "worker").open("w") as stream:
            stream.write(f"{os.getpid()}\n")
    os.execvp(command[0], command)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("acquire", "release", "cleanup", "run"))
    parser.add_argument("lock", type=pathlib.Path)
    parser.add_argument("owner", type=int)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if args.owner <= 1 or (args.action == "run") != bool(args.command):
        parser.error("a valid launcher PID is required; only run accepts a command")
    try:
        operate(args.action, args.lock, args.owner, args.command)
    except (OSError, ValueError) as error:
        print(f"[ios-run] FATAL: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
