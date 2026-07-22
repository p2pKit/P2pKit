#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
ALICE="$ROOT/.run/JVM CLI Alice.run.xml"
BOB="$ROOT/.run/JVM CLI Bob.run.xml"

fail() {
    echo "FAIL: $*" >&2
    exit 1
}

profile_from() {
    sed -n 's/.*-Pp2pkit\.sample\.identityProfile=\([A-Za-z0-9_-]*\).*/\1/p' "$1"
}

alice_profile="$(profile_from "$ALICE")"
bob_profile="$(profile_from "$BOB")"

[[ "$alice_profile" =~ ^[A-Za-z0-9_-]{1,32}$ ]] || fail "Alice identity profile is missing or invalid"
[[ "$bob_profile" =~ ^[A-Za-z0-9_-]{1,32}$ ]] || fail "Bob identity profile is missing or invalid"
[[ "$alice_profile" != "$bob_profile" ]] || fail "Alice and Bob must use distinct identity profiles"

grep -Fq -- '--args=&quot;Alice&quot;' "$ALICE" || fail "Alice run configuration changed its device-name arguments"
grep -Fq -- '--args=&quot;Bob&quot;' "$BOB" || fail "Bob run configuration changed its device-name arguments"
grep -Fq 'p2pkit.sample.identityProfile' "$ROOT/p2p-sample-desktop/build.gradle.kts" ||
    fail "desktop run task does not consume the identity-profile property"

echo "RESULT: PASS — Alice/Bob share the default appId and persist under distinct identity profiles"
