"""Synthetic Android binary XML, never an installable/qualified application."""

import struct


def manifest(version="0.8.0-rc1", code=320202, utf8=True):
    strings = ["manifest", "package", "dev.p2pkit.sample.android", "http://schemas.android.com/apk/res/android",
               "versionCode", "versionName", version]
    offsets, body = [], b""
    for value in strings:
        offsets.append(len(body))
        if utf8:
            data = value.encode("utf-8")
            body += bytes([len(value), len(data)]) + data + b"\0"
        else:
            body += struct.pack("<H", len(value)) + value.encode("utf-16-le") + b"\0\0"
    body += b"\0" * (-len(body) % 4)
    start = 28 + 4 * len(strings)
    pool = struct.pack("<HHIIIIII", 1, 28, start + len(body), len(strings), 0, 0x100 if utf8 else 0, start, 0)
    pool += struct.pack("<" + "I" * len(offsets), *offsets) + body
    resources = struct.pack("<HHI6I", 0x180, 8, 32, 0, 0, 0, 0, 0x0101021b, 0x0101021c)
    attrs = b"".join(struct.pack("<IIIHBBI", *values) for values in (
        (0xffffffff, 1, 2, 8, 0, 3, 2), (3, 4, 0xffffffff, 8, 0, 0x10, code), (3, 5, 6, 8, 0, 3, 6)))
    element = struct.pack("<HHIIIIIHHHHHH", 0x102, 16, 36 + len(attrs), 1, 0xffffffff, 0xffffffff, 0, 20, 20, 3, 0, 0, 0) + attrs
    close = struct.pack("<HHIIIII", 0x103, 16, 24, 1, 0xffffffff, 0xffffffff, 0)
    data = pool + resources + element + close
    return struct.pack("<HHI", 3, 8, 8 + len(data)) + data
