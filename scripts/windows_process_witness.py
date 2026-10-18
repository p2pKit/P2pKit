#!/usr/bin/env python3
"""Retained original-process witnesses for an existing canonical WindowsScope.

This module never launches, discovers by PID, or signals a process. The one
scope supplies already membership-validated original handles to its identity
hook. Image paths and identities are private evidence, never launch authority.
"""
from __future__ import annotations

import ctypes
import ntpath

MAX_WITNESSES = 64
MAX_IMAGE_CHARS = 32768


def require(value):
    if not value:
        raise ValueError("WINDOWS_PROCESS_WITNESS_REFUSED")


def normalized_image(path):
    require(type(path) is str and path and "\0" not in path)
    require(len(path.encode("utf-16-le")) // 2 < MAX_IMAGE_CHARS)
    require(ntpath.isabs(path) and bool(ntpath.splitdrive(path)[0]))
    return ntpath.normcase(ntpath.normpath(path))


class Witnesses:
    """Duplicate only originals admitted by this ONE canonical WindowsScope."""
    def __init__(self, scope, deadline):
        self.scope, self.api, self.deadline = scope, scope.api, deadline
        self.original_identity = self.api.identity
        self.rows = {}
        self.frozen = False
        self.api._bind("QueryFullProcessImageNameW",
                       [ctypes.c_void_p, ctypes.c_uint32, ctypes.POINTER(ctypes.c_wchar),
                        ctypes.POINTER(ctypes.c_uint32)], ctypes.c_int)
        # Instance-only hook: no global backend replacement and no PID reopen.
        self.api.identity = self.admit

    def image(self, original):
        buffer = ctypes.create_unicode_buffer(MAX_IMAGE_CHARS)
        length = ctypes.c_uint32(MAX_IMAGE_CHARS)
        self.api.check(self.api.QueryFullProcessImageNameW(original, 0, buffer, ctypes.byref(length)),
                       "QueryFullProcessImageNameW original death witness")
        require(0 < length.value < MAX_IMAGE_CHARS)
        path = buffer.value
        require(len(path.encode("utf-16-le")) // 2 == length.value)
        normalized_image(path)
        return path

    def admit(self, original, pid):
        identity = self.original_identity(original, pid)
        key = (identity["pid"], identity["creationFileTime"])
        if key in self.rows:
            return identity
        require(not self.frozen and len(self.rows) < MAX_WITNESSES)
        state = self.api.WaitForSingleObject(original, 0)
        require(state in (0, 258))
        if state == 0:
            return identity
        duplicate = ctypes.c_void_p()
        self.api.check(self.api.DuplicateHandle(ctypes.c_void_p(-1), original, ctypes.c_void_p(-1),
            ctypes.byref(duplicate), 0x1000 | 0x100000, 0, 0), "DuplicateHandle original death witness")
        row = {**identity, "handle": duplicate.value, "firstSeenCounter": None, "imagePath": None,
               "exitObservedCounter": None, "exitCode": None, "closed": False}
        self.rows[key] = row  # Register the duplicate before any fallible follow-up.
        row["firstSeenCounter"] = self.deadline.now()
        require(self.original_identity(duplicate.value, pid) == identity)
        member, flags = ctypes.c_int(), ctypes.c_uint32()
        self.api.check(self.api.IsProcessInJob(duplicate.value, self.scope.job, ctypes.byref(member)),
                       "IsProcessInJob original death witness")
        self.api.check(self.api.GetHandleInformation(duplicate.value, ctypes.byref(flags)),
                       "GetHandleInformation original death witness")
        require(member.value and flags.value & 1 == 0)
        row["imagePath"] = self.image(duplicate.value)
        self.deadline.check()
        return identity

    def poll(self):
        for row in self.rows.values():
            if row["exitObservedCounter"] is not None:
                continue
            state = self.api.WaitForSingleObject(row["handle"], 0)
            require(state in (0, 258))
            if state == 0:
                code = ctypes.c_uint32()
                self.api.check(self.api.GetExitCodeProcess(row["handle"], ctypes.byref(code)),
                               "GetExitCodeProcess original death witness")
                row["exitCode"] = code.value
                row["exitObservedCounter"] = self.deadline.now()

    def all_exited(self):
        return bool(self.rows) and all(row["exitObservedCounter"] is not None for row in self.rows.values())

    def freeze(self):
        # Evidence ends BEFORE any enclosing drain/signal/job closure.
        self.frozen = True
        self.api.identity = self.original_identity

    def close(self):
        failed = False
        for row in self.rows.values():
            original, row["handle"] = row["handle"], None
            if original is not None:
                try:
                    self.api.close(original)
                    row["closed"] = True
                except BaseException:
                    failed = True
        require(not failed)

    def evidence(self):
        return [{key: value for key, value in row.items() if key != "handle"}
                for row in sorted(self.rows.values(), key=lambda item: (item["creationFileTime"], item["pid"]))]
