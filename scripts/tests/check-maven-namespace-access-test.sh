#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
bash -n "$ROOT/scripts/check-maven-namespace-access.sh"
exec python3 -I -B -S -W error::ResourceWarning "$ROOT/scripts/tests/check-maven-namespace-access-test.py" -v
