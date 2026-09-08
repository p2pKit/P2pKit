#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
WORK="$(mktemp -d "${TMPDIR:-/tmp}/p2pkit-dependency-policy-test.XXXXXX")"
trap 'rm -rf "$WORK"' EXIT
PYTHON3="${P2PKIT_PYTHON3:-/usr/bin/python3}"
if [[ ! -x "$PYTHON3" ]] || ! "$PYTHON3" -c 'import json, xml.etree.ElementTree' 2>/dev/null; then
    PYTHON3="$(command -v python3 || true)"
fi
if [[ -z "$PYTHON3" ]] || ! "$PYTHON3" -c 'import json, xml.etree.ElementTree' 2>/dev/null; then
    echo "FATAL: a working Python 3 with JSON and XML support is required" >&2
    exit 1
fi

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
    cp "$ROOT/scripts/check-archive-whitespace.sh" "$fixture/scripts/"
    cp "$ROOT/.gitattributes" "$fixture/"
    for path in \
        docs/archive/evidence/v0.3/jvm-cli.log \
        docs/archive/remediation/2026-06/PROBLEMS_P2PKIT.md \
        docs/archive/remediation/2026-07/OPEN_DECISIONS_2026-07.md; do
        mkdir -p "$(dirname "$fixture/$path")"
        cp "$ROOT/$path" "$fixture/$path"
    done
    cp "$ROOT/scripts/review-dependency-verification.sh" "$fixture/scripts/"
    cp "$ROOT/scripts/validate-gradle-plugin-marker.sh" "$fixture/scripts/"
    cp "$ROOT/scripts/validate-gradle-plugin-metadata.py" "$fixture/scripts/"
    cp "$ROOT/scripts/resolve-gradle-variant-artifact.py" "$fixture/scripts/"
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
    printf '%s\n' '# group|module|version|repository|workflow|source ref|source digest' \
        >"$fixture/gradle/plugin-provenance-policy.txt"
    printf 'example:library:1.0=runtimeClasspath\n' >"$fixture/gradle.lockfile"
    cat >"$fixture/build.gradle.kts" <<'KOTLIN'
buildscript {
    configurations.configureEach {
        resolutionStrategy.activateDependencyLocking()
    }
}
KOTLIN
    printf 'example:plugin:1.0=classpath\n' >"$fixture/buildscript-gradle.lockfile"
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

whitespace_fixture="$(new_fixture whitespace-range)"
whitespace_base="$(git -C "$whitespace_fixture" rev-parse HEAD)"
printf 'bad earlier dependency-update whitespace \n' >"$whitespace_fixture/earlier.txt"
git -C "$whitespace_fixture" add earlier.txt
git -C "$whitespace_fixture" commit -qm "bad earlier range"
sed -i.bak 's/fixture = "1.0"/fixture = "1.1"/' \
    "$whitespace_fixture/gradle/libs.versions.toml"
sed -i.bak '/<\/components>/i\
      <component group="example" name="library" version="1.1">\
         <artifact name="library-1.1.jar">\
            <sha256 value="bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb" origin="Reviewed fixture"/>\
         </artifact>\
      </component>' "$whitespace_fixture/gradle/verification-metadata.xml"
git -C "$whitespace_fixture" add gradle
git -C "$whitespace_fixture" commit -qm "complete dependency update"
whitespace_head="$(git -C "$whitespace_fixture" rev-parse HEAD)"
expect_failure "earlier update-range whitespace" "trailing whitespace" \
    bash -c "cd '$whitespace_fixture' && scripts/check-dependency-update.sh '$whitespace_base' '$whitespace_head'"

archive_fixture="$(new_fixture archive-integrity)"
archive_base="$(git -C "$archive_fixture" hash-object -t tree /dev/null)"
archive_head="$(git -C "$archive_fixture" rev-parse HEAD)"
(cd "$archive_fixture" && scripts/check-dependency-update.sh "$archive_base" "$archive_head" >/dev/null)
archive_path='docs/archive/evidence/v0.3/jvm-cli.log'
printf 'whitespace-clean replacement\n' >"$archive_fixture/$archive_path"
git -C "$archive_fixture" add -- "$archive_path"
git -C "$archive_fixture" commit -qm 'changed archive'
archive_head="$(git -C "$archive_fixture" rev-parse HEAD)"
git -C "$archive_fixture" checkout HEAD^ -- "$archive_path"
expect_failure "changed archived head despite clean index/worktree" "bytes changed in range head" \
    bash -c "cd '$archive_fixture' && scripts/check-dependency-update.sh '$archive_base' '$archive_head'"

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

unlocked_buildscript_fixture="$(new_fixture unlocked-buildscript)"
sed -i.bak '/activateDependencyLocking/d' "$unlocked_buildscript_fixture/build.gradle.kts"
expect_failure "unlocked buildscript" "dependency locking is not activated" \
    bash -c "cd '$unlocked_buildscript_fixture' && scripts/check-dependency-verification.sh"

empty_buildscript_lock_fixture="$(new_fixture empty-buildscript-lock)"
printf 'empty=classpath\n' >"$empty_buildscript_lock_fixture/buildscript-gradle.lockfile"
expect_failure "empty buildscript lock" "contains no classpath components" \
    bash -c "cd '$empty_buildscript_lock_fixture' && scripts/check-dependency-verification.sh"

stale_lock_fixture="$(new_fixture stale-lock)"
printf 'example:old-utp:1.0=_internal-unified-test-platform-core\n' \
    >>"$stale_lock_fixture/gradle.lockfile"
expect_failure "stale AGP lock" "removed AGP internal UTP configuration" \
    bash -c "cd '$stale_lock_fixture' && scripts/check-dependency-verification.sh"

marker_fixture="$WORK/marker"
mkdir -p "$marker_fixture"
cat >"$marker_fixture/marker.pom" <<'XML'
<project xmlns="http://maven.apache.org/POM/4.0.0">
  <modelVersion>4.0.0</modelVersion>
  <groupId>example.plugin</groupId>
  <artifactId>example.plugin.gradle.plugin</artifactId>
  <version>1.2.3</version>
  <packaging>pom</packaging>
  <dependencies>
    <dependency>
      <groupId>example.implementation</groupId>
      <artifactId>plugin</artifactId>
      <version>4.5.6</version>
    </dependency>
  </dependencies>
</project>
XML
printf '%s\n' \
    'example.implementation|plugin|4.5.6|plugin-4.5.6.jar|aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa' \
    >"$marker_fixture/entries"
printf '%s\n' 'example.implementation:plugin:4.5.6=classpath' >"$marker_fixture/buildscript.lock"
marker_implementation="$("$ROOT/scripts/validate-gradle-plugin-marker.sh" \
    "$marker_fixture/marker.pom" example.plugin example.plugin.gradle.plugin 1.2.3 \
    "$marker_fixture/entries" "$marker_fixture/buildscript.lock")"
[[ "$marker_implementation" == 'example.implementation|plugin|4.5.6' ]] ||
    fail "valid plugin marker did not resolve to its implementation"

cp "$marker_fixture/marker.pom" "$marker_fixture/unsafe.pom"
sed -i.bak '/<dependencies>/i\
  <repositories><repository><url>https://attacker.invalid</url></repository></repositories>' \
    "$marker_fixture/unsafe.pom"
expect_failure "marker with unsupported elements" "unsupported elements" \
    "$ROOT/scripts/validate-gradle-plugin-marker.sh" \
    "$marker_fixture/unsafe.pom" example.plugin example.plugin.gradle.plugin 1.2.3 \
    "$marker_fixture/entries" "$marker_fixture/buildscript.lock"

cp "$marker_fixture/marker.pom" "$marker_fixture/multiple.pom"
sed -i.bak '/<\/dependencies>/i\
    <dependency><groupId>other</groupId><artifactId>plugin</artifactId><version>1</version></dependency>' \
    "$marker_fixture/multiple.pom"
expect_failure "marker with multiple dependencies" "exactly one dependency" \
    "$ROOT/scripts/validate-gradle-plugin-marker.sh" \
    "$marker_fixture/multiple.pom" example.plugin example.plugin.gradle.plugin 1.2.3 \
    "$marker_fixture/entries" "$marker_fixture/buildscript.lock"

printf '%s\n' 'other:plugin:1=classpath' >"$marker_fixture/wrong.lock"
expect_failure "marker implementation missing from lock" "absent from the buildscript classpath lock" \
    "$ROOT/scripts/validate-gradle-plugin-marker.sh" \
    "$marker_fixture/marker.pom" example.plugin example.plugin.gradle.plugin 1.2.3 \
    "$marker_fixture/entries" "$marker_fixture/wrong.lock"

expect_failure "noncanonical unsigned marker" "not a canonical Gradle plugin marker" \
    "$ROOT/scripts/validate-gradle-plugin-marker.sh" \
    "$marker_fixture/marker.pom" example.plugin arbitrary-module 1.2.3 \
    "$marker_fixture/entries" "$marker_fixture/buildscript.lock"

module_sha="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
cat >"$marker_fixture/plugin.module" <<JSON
{
  "formatVersion": "1.1",
  "component": {
    "group": "example.implementation",
    "module": "plugin",
    "version": "4.5.6",
    "attributes": {"org.gradle.status": "release"}
  },
  "createdBy": {"gradle": {"version": "9.7.0"}},
  "variants": [
    {
      "name": "apiElements",
      "attributes": {
        "org.gradle.category": "library",
        "org.gradle.jvm.version": 17,
        "org.gradle.usage": "java-api"
      },
      "files": [{
        "name": "plugin-4.5.6.jar",
        "url": "plugin-4.5.6.jar",
        "size": 1,
        "sha512": "$(printf 'a%.0s' {1..128})",
        "sha256": "$module_sha",
        "sha1": "$(printf 'a%.0s' {1..40})",
        "md5": "$(printf 'a%.0s' {1..32})"
      }]
    },
    {
      "name": "runtimeElements",
      "attributes": {
        "org.gradle.category": "library",
        "org.gradle.jvm.version": 17,
        "org.gradle.usage": "java-runtime"
      },
      "files": [{
        "name": "plugin-4.5.6.jar",
        "url": "plugin-4.5.6.jar",
        "size": 1,
        "sha512": "$(printf 'a%.0s' {1..128})",
        "sha256": "$module_sha",
        "sha1": "$(printf 'a%.0s' {1..40})",
        "md5": "$(printf 'a%.0s' {1..32})"
      }]
    }
  ]
}
JSON
module_implementation="$("$PYTHON3" "$ROOT/scripts/validate-gradle-plugin-metadata.py" module \
    "$marker_fixture/plugin.module" example.implementation plugin 4.5.6 "$module_sha" \
    "$marker_fixture/entries" "$marker_fixture/buildscript.lock")"
[[ "$module_implementation" == 'example.implementation|plugin|4.5.6' ]] ||
    fail "valid plugin module metadata did not bind to its implementation"

sed 's#"url": "plugin-4.5.6.jar"#"url": "https://attacker.invalid/plugin.jar"#' \
    "$marker_fixture/plugin.module" >"$marker_fixture/remote.module"
expect_failure "module with remote file" "non-local artifact URL" \
    "$PYTHON3" "$ROOT/scripts/validate-gradle-plugin-metadata.py" module \
    "$marker_fixture/remote.module" example.implementation plugin 4.5.6 "$module_sha" \
    "$marker_fixture/entries" "$marker_fixture/buildscript.lock"

cat >"$marker_fixture/attestation.json" <<JSON
[
  {
    "verificationResult": {
      "verifiedTimestamps": [{"type": "Tlog"}],
      "statement": {
        "predicateType": "https://slsa.dev/provenance/v1",
        "subject": [{"name": "plugin.jar", "digest": {"sha256": "$module_sha"}}]
      },
      "signature": {"certificate": {
        "subjectAlternativeName": "https://github.com/example/upstream/.github/workflows/release.yml@refs/tags/v4.5.6",
        "issuer": "https://token.actions.githubusercontent.com",
        "githubWorkflowRepository": "example/upstream",
        "githubWorkflowRef": "refs/tags/v4.5.6",
        "githubWorkflowSHA": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        "sourceRepositoryDigest": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        "sourceRepositoryRef": "refs/tags/v4.5.6",
        "runnerEnvironment": "github-hosted"
      }}
    }
  }
]
JSON
"$PYTHON3" "$ROOT/scripts/validate-gradle-plugin-metadata.py" attestation \
    "$marker_fixture/attestation.json" "$module_sha" example/upstream \
    example/upstream/.github/workflows/release.yml refs/tags/v4.5.6 \
    aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
expect_failure "attestation with wrong source" "trusted build identity" \
    "$PYTHON3" "$ROOT/scripts/validate-gradle-plugin-metadata.py" attestation \
    "$marker_fixture/attestation.json" "$module_sha" example/upstream \
    example/upstream/.github/workflows/release.yml refs/tags/v4.5.6 \
    bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb

review_fixture="$(new_fixture provenance-review)"
review_base="$(git -C "$review_fixture" rev-parse HEAD)"
mkdir -p "$review_fixture/mock-bin" "$review_fixture/mock-repository"
cp "$marker_fixture/marker.pom" "$review_fixture/mock-repository/example.plugin.gradle.plugin-1.2.3.pom"
cp "$marker_fixture/plugin.module" "$review_fixture/mock-repository/plugin-4.5.6.module"
printf 'attested plugin bytes' >"$review_fixture/mock-repository/plugin-4.5.6.jar"
printf 'signed library bytes' >"$review_fixture/mock-repository/signed-1.0.jar"
printf 'issuer-key-id-only signature fixture' >"$review_fixture/mock-repository/signed-1.0.jar.asc"
printf 'public key fixture' >"$review_fixture/mock-repository/signing-key.asc"
review_jar_sha="$(shasum -a 256 "$review_fixture/mock-repository/plugin-4.5.6.jar" | awk '{print $1}')"
signed_jar_sha="$(shasum -a 256 "$review_fixture/mock-repository/signed-1.0.jar" | awk '{print $1}')"
"$PYTHON3" - "$review_fixture/mock-repository/plugin-4.5.6.module" "$module_sha" "$review_jar_sha" <<'PY'
import sys
path, old, new = sys.argv[1:]
data = open(path, encoding="utf-8").read().replace(old, new)
open(path, "w", encoding="utf-8").write(data)
PY
review_module_sha="$(shasum -a 256 "$review_fixture/mock-repository/plugin-4.5.6.module" | awk '{print $1}')"
review_marker_sha="$(shasum -a 256 \
    "$review_fixture/mock-repository/example.plugin.gradle.plugin-1.2.3.pom" | awk '{print $1}')"
sed -i.bak '/<\/components>/i\
      <component group="example.implementation" name="plugin" version="4.5.6">\
         <artifact name="plugin-4.5.6.jar">\
            <sha256 value="'"$review_jar_sha"'" origin="Fixture"/>\
         </artifact>\
         <artifact name="plugin-4.5.6.module">\
            <sha256 value="'"$review_module_sha"'" origin="Fixture"/>\
         </artifact>\
      </component>\
      <component group="example.plugin" name="example.plugin.gradle.plugin" version="1.2.3">\
         <artifact name="example.plugin.gradle.plugin-1.2.3.pom">\
            <sha256 value="'"$review_marker_sha"'" origin="Fixture"/>\
         </artifact>\
      </component>\
      <component group="example.signed" name="signed" version="1.0">\
         <artifact name="signed-1.0.jar">\
            <sha256 value="'"$signed_jar_sha"'" origin="Fixture"/>\
         </artifact>\
      </component>' "$review_fixture/gradle/verification-metadata.xml"
printf '%s\n' 'example.implementation:plugin:4.5.6=classpath' \
    >>"$review_fixture/buildscript-gradle.lockfile"
cat >"$review_fixture/gradle/plugin-provenance-policy.txt" <<'POLICY'
# group|module|version|repository|workflow|source ref|source digest
example.implementation|plugin|4.5.6|example/upstream|example/upstream/.github/workflows/release.yml|refs/tags/v4.5.6|aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
POLICY
cat >"$review_fixture/mock-bin/curl" <<'SCRIPT'
#!/usr/bin/env bash
set -euo pipefail
output=""
url=""
while [[ $# -gt 0 ]]; do
    case "$1" in
        -o)
            output="$2"
            shift 2
            ;;
        http*)
            url="$1"
            shift
            ;;
        *)
            shift
            ;;
    esac
done
if [[ "$url" == *keyserver* || "$url" == *keys.openpgp.org* ]]; then
    source="$MOCK_REPOSITORY/signing-key.asc"
else
    source="$MOCK_REPOSITORY/${url##*/}"
fi
[[ -n "$output" && -f "$source" ]] || exit 22
cp "$source" "$output"
SCRIPT
cat >"$review_fixture/mock-bin/gh" <<'SCRIPT'
#!/usr/bin/env bash
set -euo pipefail
arguments=" $* "
for expected in \
    '--hostname github.com' \
    '--repo example/upstream' \
    '--signer-workflow example/upstream/.github/workflows/release.yml' \
    '--source-ref refs/tags/v4.5.6' \
    '--source-digest aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa' \
    '--deny-self-hosted-runners' \
    '--format json'; do
    [[ "$arguments" == *" $expected "* ]] || {
        echo "missing attestation constraint: $expected" >&2
        exit 1
    }
done
cat <<JSON
[{"verificationResult":{"verifiedTimestamps":[{"type":"Tlog"}],"statement":{"predicateType":"https://slsa.dev/provenance/v1","subject":[{"name":"plugin-4.5.6.jar","digest":{"sha256":"$MOCK_JAR_SHA"}}]},"signature":{"certificate":{"subjectAlternativeName":"https://github.com/example/upstream/.github/workflows/release.yml@refs/tags/v4.5.6","issuer":"https://token.actions.githubusercontent.com","githubWorkflowRepository":"example/upstream","githubWorkflowRef":"refs/tags/v4.5.6","githubWorkflowSHA":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","sourceRepositoryDigest":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","sourceRepositoryRef":"refs/tags/v4.5.6","runnerEnvironment":"github-hosted"}}}}]
JSON
SCRIPT
cat >"$review_fixture/mock-bin/gpg" <<'SCRIPT'
#!/usr/bin/env bash
set -euo pipefail
if [[ "${MOCK_REQUIRE_BYTE_LOCALE:-false}" == true && "${LC_ALL:-}" != C ]]; then
    echo 'gpg fixture: curation must use the byte locale' >&2
    exit 2
fi
fingerprint="${MOCK_KEY_FINGERPRINT:-41CD49B4EF5876F9E9F691DABAC30622339994C4}"
if [[ "${#fingerprint}" -eq 40 ]]; then
    key_id="${fingerprint: -16}"
else
    key_id="${fingerprint:0:16}"
fi
packet_key_id="${MOCK_PACKET_KEY_ID:-$key_id}"
arguments=" $* "
if [[ "$arguments" == *' --list-packets '* ]]; then
    case "${MOCK_PACKET_MODE:-keyid}" in
        keyid)
            printf ':signature packet: algo 1, keyid %s\n' "$packet_key_id"
            printf ' version 4, created 1785364858, md5len 0, sigclass 0x00\n'
            printf ' subpkt 16 len 8 (issuer key ID %s)\n' "$packet_key_id"
            ;;
        full)
            printf ':signature packet: algo 1, keyid %s\n' "$packet_key_id"
            printf ' hashed subpkt 33 len 21 (issuer fpr v%s %s)\n' \
                "$([[ "${#fingerprint}" -eq 40 ]] && echo 4 || echo 6)" "$fingerprint"
            printf ' subpkt 16 len 8 (issuer key ID %s)\n' "$packet_key_id"
            ;;
        multiple)
            printf ':signature packet: algo 1, keyid %s\n' "$packet_key_id"
            printf ':signature packet: algo 1, keyid %s\n' "$packet_key_id"
            ;;
        *)
            echo 'not a signature packet'
            ;;
    esac
elif [[ "$arguments" == *' --show-keys '* ]]; then
    printf 'pub:-:2048:1:%s:0:0::-:::scESC::::::23::0:\n' "$key_id"
    printf 'fpr:::::::::%s:\n' "$fingerprint"
elif [[ "$arguments" == *' --list-keys '* ]]; then
    exit 2
elif [[ "$arguments" == *' --import '* ]]; then
    if [[ "${MOCK_IMPORT_FAIL:-false}" == true ]]; then
        echo 'gpg: injected import failure' >&2
        exit 2
    fi
    echo 'gpg: key imported' >&2
elif [[ "$arguments" == *' --verify '* ]]; then
    if [[ "${MOCK_NON_UTF8_DIAGNOSTIC:-false}" == true ]]; then
        printf 'gpg: synthetic publisher diagnostic byte \351\n' >&2
    fi
    if [[ "${MOCK_VERIFY_FAIL:-false}" == true ]]; then
        echo '[GNUPG:] BADSIG injected' >&2
        exit 1
    fi
    valid_fingerprint="${MOCK_VALIDSIG_FINGERPRINT:-$fingerprint}"
    printf '[GNUPG:] VALIDSIG %s 2026-07-29 1785364858 0 4 0 1 10 00 %s\n' \
        "$valid_fingerprint" "$valid_fingerprint"
else
    echo "unexpected gpg invocation: $*" >&2
    exit 2
fi
SCRIPT
chmod +x "$review_fixture/mock-bin/curl" "$review_fixture/mock-bin/gh" \
    "$review_fixture/mock-bin/gpg"
(
    cd "$review_fixture"
    PATH="$review_fixture/mock-bin:$PATH" \
        MOCK_REPOSITORY="$review_fixture/mock-repository" \
        MOCK_JAR_SHA="$review_jar_sha" \
        scripts/review-dependency-verification.sh "$review_base" >/dev/null
)

# macOS sed rejects non-UTF-8 GPG diagnostic bytes under a UTF-8 caller
# locale. Assert the byte-locale contract too, including on hosts whose sed
# happens to tolerate those bytes, without replacing signature validation.
for caller_locale in C.UTF-8 en_US.UTF-8; do
    (
        cd "$review_fixture"
        LC_ALL="$caller_locale" PATH="$review_fixture/mock-bin:$PATH" \
            MOCK_REPOSITORY="$review_fixture/mock-repository" \
            MOCK_JAR_SHA="$review_jar_sha" MOCK_REQUIRE_BYTE_LOCALE=true \
            MOCK_NON_UTF8_DIAGNOSTIC=true \
            scripts/review-dependency-verification.sh "$review_base" >/dev/null
    )
done

v6_fingerprint="0123456789ABCDEF$(printf 'A%.0s' {1..48})"
(
    cd "$review_fixture"
    PATH="$review_fixture/mock-bin:$PATH" \
        MOCK_REPOSITORY="$review_fixture/mock-repository" \
        MOCK_JAR_SHA="$review_jar_sha" \
        MOCK_PACKET_MODE=full MOCK_KEY_FINGERPRINT="$v6_fingerprint" \
        scripts/review-dependency-verification.sh "$review_base" >/dev/null
)

expect_failure "issuer key ID resolving to the wrong key" "could not retrieve one exact signing key" \
    env PATH="$review_fixture/mock-bin:$PATH" \
    MOCK_REPOSITORY="$review_fixture/mock-repository" MOCK_JAR_SHA="$review_jar_sha" \
    MOCK_KEY_FINGERPRINT=BBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB \
    MOCK_PACKET_KEY_ID=BAC30622339994C4 \
    "$review_fixture/scripts/review-dependency-verification.sh" "$review_base"

expect_failure "VALIDSIG fingerprint mismatch" "signature fingerprint mismatch" \
    env PATH="$review_fixture/mock-bin:$PATH" \
    LC_ALL=en_US.UTF-8 MOCK_NON_UTF8_DIAGNOSTIC=true \
    MOCK_REPOSITORY="$review_fixture/mock-repository" MOCK_JAR_SHA="$review_jar_sha" \
    MOCK_VALIDSIG_FINGERPRINT=BBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB \
    "$review_fixture/scripts/review-dependency-verification.sh" "$review_base"

expect_failure "multiple detached signatures" "exactly one signature packet" \
    env PATH="$review_fixture/mock-bin:$PATH" \
    MOCK_REPOSITORY="$review_fixture/mock-repository" MOCK_JAR_SHA="$review_jar_sha" \
    MOCK_PACKET_MODE=multiple \
    "$review_fixture/scripts/review-dependency-verification.sh" "$review_base"

expect_failure "invalid detached signature" "invalid detached signature" \
    env PATH="$review_fixture/mock-bin:$PATH" \
    LC_ALL=en_US.UTF-8 MOCK_NON_UTF8_DIAGNOSTIC=true \
    MOCK_REPOSITORY="$review_fixture/mock-repository" MOCK_JAR_SHA="$review_jar_sha" \
    MOCK_VERIFY_FAIL=true \
    "$review_fixture/scripts/review-dependency-verification.sh" "$review_base"

expect_failure "signing key import failure" "could not import the exact signing key BAC30622339994C4" \
    env PATH="$review_fixture/mock-bin:$PATH" \
    MOCK_REPOSITORY="$review_fixture/mock-repository" MOCK_JAR_SHA="$review_jar_sha" \
    MOCK_IMPORT_FAIL=true \
    "$review_fixture/scripts/review-dependency-verification.sh" "$review_base"

bad_review_sha="$(printf 'b%.0s' {1..64})"
sed -i.bak "s/$review_jar_sha/$bad_review_sha/" \
    "$review_fixture/gradle/verification-metadata.xml"
expect_failure "review with mismatched downloaded checksum" "downloaded bytes disagree" \
    env PATH="$review_fixture/mock-bin:$PATH" \
    MOCK_REPOSITORY="$review_fixture/mock-repository" MOCK_JAR_SHA="$review_jar_sha" \
    "$review_fixture/scripts/review-dependency-verification.sh" "$review_base"
sed -i.bak "s/$bad_review_sha/$review_jar_sha/" \
    "$review_fixture/gradle/verification-metadata.xml"

printf 'unsigned executable' >"$review_fixture/mock-repository/other-1.0.jar"
other_sha="$(shasum -a 256 "$review_fixture/mock-repository/other-1.0.jar" | awk '{print $1}')"
sed -i.bak '/<\/components>/i\
      <component group="example" name="other" version="1.0">\
         <artifact name="other-1.0.jar">\
            <sha256 value="'"$other_sha"'" origin="Fixture"/>\
         </artifact>\
      </component>' "$review_fixture/gradle/verification-metadata.xml"
expect_failure "unsigned non-plugin artifact" "no detached signature or approved provenance" \
    env PATH="$review_fixture/mock-bin:$PATH" \
    MOCK_REPOSITORY="$review_fixture/mock-repository" MOCK_JAR_SHA="$review_jar_sha" \
    "$review_fixture/scripts/review-dependency-verification.sh" "$review_base"

grep -Fq 'validate-gradle-plugin-marker.sh' "$ROOT/scripts/review-dependency-verification.sh" ||
    fail "dependency reviewer does not invoke strict plugin-marker validation"
grep -Fq 'no detached signature or approved provenance' "$ROOT/scripts/review-dependency-verification.sh" ||
    fail "dependency reviewer no longer fails closed for unsigned non-marker artifacts"

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

"$PYTHON3" "$ROOT/scripts/tests/check-gradle-plugin-metadata-test.py"
"$PYTHON3" "$ROOT/scripts/tests/check-gradle-variant-artifact-test.py"
"$PYTHON3" "$ROOT/scripts/tests/review-dependency-temporary-directories-test.py"

echo "RESULT: PASS — incomplete updates, stale locks, broad trust, and malformed checksums fail before Gradle execution"
