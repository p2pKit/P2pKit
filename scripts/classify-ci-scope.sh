#!/usr/bin/env bash
set -euo pipefail

# Read a NUL-delimited list of changed repository paths from stdin. Callers must
# disable rename detection so both the removed and added paths are classified.
# Only Markdown-only changes are eligible for the lightweight required check.
# An empty list and every other file type fail closed to the complete gate.
scope="lightweight"
saw_path=0

while IFS= read -r -d '' path; do
    saw_path=1
    case "$path" in
        *.md) ;;
        *)
            scope="full"
            break
            ;;
    esac
done

if [[ "$saw_path" -eq 0 ]]; then
    scope="full"
fi

printf '%s\n' "$scope"
