#!/usr/bin/env python3
"""Private Darwin exec handshake; never run a product before lifetime admission.

Invoked with the controller's native interpreter, -I and -S. Both descriptors
are anonymous pipes passed explicitly by Popen, not files or inherited globals.
Controller exit/failed admission closes the release pipe: EOF refuses execution.
This is not a substitute for native ownership or a standalone public launcher.
"""
import os
import select
import sys


def main():
    if len(sys.argv) < 4:
        return 125
    ready, release = int(sys.argv[1]), int(sys.argv[2])
    argv = sys.argv[3:]
    if not os.path.isabs(argv[0]) or ready == release or min(ready, release) < 3:
        return 125
    try:
        if os.write(ready, b"R") != 1 or not select.select([release], [], [], 10)[0] or \
                os.read(release, 1) != b"G":
            return 125
    finally:
        os.close(ready)
        os.close(release)
    os.execv(argv[0], argv)
    return 125


if __name__ == "__main__":
    raise SystemExit(main())
