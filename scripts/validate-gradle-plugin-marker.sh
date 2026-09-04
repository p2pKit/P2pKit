#!/usr/bin/env bash
# Compatibility entry point for strict marker-POM validation.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
PYTHON3="${P2PKIT_PYTHON3:-/usr/bin/python3}"
if [[ ! -x "$PYTHON3" ]] || ! "$PYTHON3" -c 'import json, xml.etree.ElementTree' 2>/dev/null; then
    PYTHON3="$(command -v python3 || true)"
fi
[[ -n "$PYTHON3" ]] && "$PYTHON3" -c 'import json, xml.etree.ElementTree' 2>/dev/null || {
    echo "FATAL: a working Python 3 with JSON and XML support is required" >&2
    exit 1
}
exec "$PYTHON3" "$ROOT/validate-gradle-plugin-metadata.py" marker "$@"
