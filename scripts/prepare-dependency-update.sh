#!/usr/bin/env bash
# Produce lock/checksum candidates, verify them strictly, then perform the
# remote checksum/signature review, or narrowly reuse an unchanged reviewed
# base's provenance. Nothing is committed or pushed.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BASE_REF="${1:-origin/main}"

cd "$ROOT"
BASE_SHA="$(git rev-parse --verify --end-of-options "$BASE_REF^{commit}")" || {
    echo "FATAL: dependency-update base is not an available commit" >&2
    exit 1
}
SOURCE_SHA="$(git rev-parse --verify 'HEAD^{commit}')"
git merge-base --is-ancestor "$BASE_SHA" "$SOURCE_SHA" || {
    echo "FATAL: dependency-update base must be an ancestor of the current source" >&2
    exit 1
}
PYTHON3="${P2PKIT_PYTHON3:-/usr/bin/python3}"
if [[ ! -x "$PYTHON3" ]] || ! "$PYTHON3" -c 'import json, xml.etree.ElementTree' 2>/dev/null; then
    PYTHON3="$(command -v python3 || true)"
fi
if [[ -z "$PYTHON3" ]] || ! "$PYTHON3" -c 'import json, xml.etree.ElementTree' 2>/dev/null; then
    echo "FATAL: a working Python 3 with JSON and XML support is required" >&2
    exit 1
fi
printf 'DEPENDENCY-UPDATE base=%s source=%s\n' "$BASE_SHA" "$SOURCE_SHA"
scripts/check-gradle-wrapper.sh
./gradlew resolveAndLockAll --write-locks --write-verification-metadata sha256 \
    --no-configure-on-demand --no-daemon --console=plain
scripts/check-dependency-verification.sh
./gradlew verifyBuildPluginSecurityFloors help --dependency-verification=strict --no-daemon --console=plain
provenance="$("$PYTHON3" scripts/classify-dependency-provenance.py "$BASE_SHA" "$SOURCE_SHA")"
case "$provenance" in
    REUSE)
        # The classifier proves exact input equality, not the base's review.
        # The operator must supply an independently accepted base and retain it.
        echo "PROVENANCE: unchanged reviewed-base inputs reused; no fresh remote artifact review"
        ;;
    REVIEW)
        scripts/review-dependency-verification.sh "$BASE_SHA"
        ;;
    *)
        echo "FATAL: unexpected dependency provenance classification" >&2
        exit 1
        ;;
esac
[[ "$(git rev-parse --verify 'HEAD^{commit}')" == "$SOURCE_SHA" ]] || {
    echo "FATAL: source changed during dependency update" >&2
    exit 1
}
git diff --check

echo "RESULT: PASS — complete dependency candidate procedure; provenance=$provenance; inspect the complete diff before committing"
