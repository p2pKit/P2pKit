#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
WORK="$(mktemp -d "${TMPDIR:-/tmp}/p2pkit-dependency-policy-test.XXXXXX")"
trap 'rm -rf "$WORK"' EXIT

fail() {
    echo "FATAL: $*" >&2
    exit 1
}

expect_failure() {
    local label="$1" expected="$2"
    shift 2
    if "$@" >"$WORK/stdout" 2>"$WORK/stderr"; then
        fail "$label unexpectedly passed"
    fi
    grep -Fq -- "$expected" "$WORK/stdout" "$WORK/stderr" ||
        fail "$label did not report '$expected'"
}

new_fixture() {
    local fixture="$WORK/$1"
    mkdir -p "$fixture/gradle/wrapper" "$fixture/scripts/tests"
    cp "$ROOT/scripts/check-dependency-verification.sh" "$fixture/scripts/"
    cp "$ROOT/scripts/check-dependency-update.sh" "$fixture/scripts/"
    cat >"$fixture/gradle/verification-metadata.xml" <<'XML'
<?xml version="1.0" encoding="UTF-8"?>
<verification-metadata xmlns="https://schema.gradle.org/dependency-verification" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="https://schema.gradle.org/dependency-verification https://schema.gradle.org/dependency-verification/dependency-verification-1.4.xsd">
   <configuration>
      <verify-metadata>true</verify-metadata>
      <verify-signatures>false</verify-signatures>
   </configuration>
   <components>
      <component group="example" name="library" version="1.0">
         <artifact name="library-1.0.jar">
            <sha256 value="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa" origin="Reviewed fixture"/>
         </artifact>
      </component>
   </components>
</verification-metadata>
XML
    printf '[versions]\nfixture = "1.0"\n' >"$fixture/gradle/libs.versions.toml"
    printf 'example:library:1.0=runtimeClasspath\n' >"$fixture/gradle.lockfile"
    for path in gradle/wrapper/gradle-wrapper.properties gradle/wrapper/gradle-wrapper.jar gradlew gradlew.bat; do
        printf 'wrapper-v1\n' >"$fixture/$path"
    done
    cat >"$fixture/scripts/check-gradle-wrapper.sh" <<'SCRIPT'
#!/usr/bin/env bash
exit 0
SCRIPT
    cat >"$fixture/scripts/tests/check-gradle-wrapper-test.sh" <<'SCRIPT'
#!/usr/bin/env bash
exit 0
SCRIPT
    chmod +x "$fixture/scripts/"*.sh "$fixture/scripts/tests/"*.sh
    git -C "$fixture" init -q
    git -C "$fixture" config user.name "P2pKit Test"
    git -C "$fixture" config user.email "test@p2pkit.invalid"
    git -C "$fixture" add .
    git -C "$fixture" commit -qm baseline
    printf '%s\n' "$fixture"
}

catalog_fixture="$(new_fixture catalog)"
catalog_base="$(git -C "$catalog_fixture" rev-parse HEAD)"
sed -i.bak 's/fixture = "1.0"/fixture = "1.1"/' "$catalog_fixture/gradle/libs.versions.toml"
git -C "$catalog_fixture" add gradle/libs.versions.toml
git -C "$catalog_fixture" commit -qm update
catalog_head="$(git -C "$catalog_fixture" rev-parse HEAD)"
expect_failure "catalog-only update" "without reviewed verification metadata" \
    bash -c "cd '$catalog_fixture' && scripts/check-dependency-update.sh '$catalog_base' '$catalog_head'"

cat >>"$catalog_fixture/gradle/verification-metadata.xml" <<'XML'
<!-- candidate metadata change -->
XML
git -C "$catalog_fixture" add gradle/verification-metadata.xml
git -C "$catalog_fixture" commit -qm metadata
catalog_head="$(git -C "$catalog_fixture" rev-parse HEAD)"
expect_failure "metadata without component" "added no explicitly checksummed component version" \
    bash -c "cd '$catalog_fixture' && scripts/check-dependency-update.sh '$catalog_base' '$catalog_head'"

valid_fixture="$(new_fixture valid)"
valid_base="$(git -C "$valid_fixture" rev-parse HEAD)"
sed -i.bak 's/fixture = "1.0"/fixture = "1.1"/' "$valid_fixture/gradle/libs.versions.toml"
sed -i.bak '/<\/components>/i\
      <component group="example" name="library" version="1.1">\
         <artifact name="library-1.1.jar">\
            <sha256 value="bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb" origin="Reviewed fixture"/>\
         </artifact>\
      </component>' "$valid_fixture/gradle/verification-metadata.xml"
git -C "$valid_fixture" add gradle
git -C "$valid_fixture" commit -qm valid
valid_head="$(git -C "$valid_fixture" rev-parse HEAD)"
(cd "$valid_fixture" && scripts/check-dependency-update.sh "$valid_base" "$valid_head" >/dev/null)

trust_fixture="$(new_fixture trust)"
sed -i.bak '/<components>/i\
      <trusted-artifacts><trust group="*"/></trusted-artifacts>' "$trust_fixture/gradle/verification-metadata.xml"
expect_failure "broad trust" "broad trust" \
    bash -c "cd '$trust_fixture' && scripts/check-dependency-verification.sh"

hash_fixture="$(new_fixture hash)"
sed -i.bak 's/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa/deadbeef/' \
    "$hash_fixture/gradle/verification-metadata.xml"
expect_failure "weak checksum" "invalid SHA-256" \
    bash -c "cd '$hash_fixture' && scripts/check-dependency-verification.sh"

stale_lock_fixture="$(new_fixture stale-lock)"
printf 'example:old-utp:1.0=_internal-unified-test-platform-core\n' \
    >>"$stale_lock_fixture/gradle.lockfile"
expect_failure "stale AGP lock" "removed AGP internal UTP configuration" \
    bash -c "cd '$stale_lock_fixture' && scripts/check-dependency-verification.sh"

wrapper_fixture="$(new_fixture wrapper)"
wrapper_base="$(git -C "$wrapper_fixture" rev-parse HEAD)"
for path in gradle/wrapper/gradle-wrapper.properties gradle/wrapper/gradle-wrapper.jar gradlew gradlew.bat; do
    printf 'wrapper-v2\n' >"$wrapper_fixture/$path"
done
git -C "$wrapper_fixture" add gradle/wrapper gradlew gradlew.bat
git -C "$wrapper_fixture" commit -qm wrapper
wrapper_head="$(git -C "$wrapper_fixture" rev-parse HEAD)"
expect_failure "wrapper without policy" "omitted required reviewed file" \
    bash -c "cd '$wrapper_fixture' && scripts/check-dependency-update.sh '$wrapper_base' '$wrapper_head'"

# The workflow must contain the literal shell variable references.
# shellcheck disable=SC2016
grep -Fq 'scripts/check-dependency-update.sh "$BASE_SHA" "$HEAD_SHA"' \
    "$ROOT/.github/workflows/ci.yml" ||
    fail "CI does not fail fast on incomplete dependency updates"
grep -Fq 'scripts/check-dependency-verification.sh' "$ROOT/scripts/run-release-gate.sh" ||
    fail "release gate does not validate dependency-verification state"
grep -Fq 'android-gradle-toolchain:' "$ROOT/.github/dependabot.yml" ||
    fail "Dependabot does not coordinate the Android Gradle toolchain"
grep -Fq -- '- "agp"' "$ROOT/.github/dependabot.yml" ||
    fail "Dependabot toolchain group omits AGP"
grep -Fq -- '- "gradle-wrapper"' "$ROOT/.github/dependabot.yml" ||
    fail "Dependabot toolchain group omits the Gradle wrapper"

echo "RESULT: PASS — incomplete updates, stale locks, broad trust, and malformed checksums fail before Gradle execution"
