#!/usr/bin/env bash
# Produce lock/checksum candidates, verify them strictly, then perform the
# independent remote checksum/signature review. Nothing is committed or pushed.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BASE_REF="${1:-origin/main}"

cd "$ROOT"
scripts/check-gradle-wrapper.sh
./gradlew resolveAndLockAll --write-locks --write-verification-metadata sha256 --no-daemon --console=plain
scripts/check-dependency-verification.sh
./gradlew help --dependency-verification=strict --no-daemon --console=plain
scripts/review-dependency-verification.sh "$BASE_REF"
git diff --check

echo "RESULT: PASS — dependency lock/checksum candidates are generated and independently reviewed; inspect the complete diff before committing"
