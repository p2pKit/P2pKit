#!/usr/bin/env bash
# Read-only supported-API authentication and exact namespace-query preflight.
# This does not claim namespace VERIFIED state or prove publication capability.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
exec python3 -I -B -S "$ROOT/scripts/check-maven-namespace-access.py" "$@"
