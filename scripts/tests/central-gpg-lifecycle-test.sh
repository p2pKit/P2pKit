#!/usr/bin/env bash
# Synthetic shell controls: fake GPG tools only; no keys, Gradle or signing.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
WORK="$(mktemp -d "${TMPDIR:-/tmp}/p2pkit-gpg-lifecycle-controls.XXXXXX")"
trap '/bin/rm -rf -- "$WORK"' EXIT
mkdir "$WORK/bin" "$WORK/ambient"
printf 'untouched\n' > "$WORK/ambient/sentinel"
cat > "$WORK/bin/gpgconf" <<'EOF'
#!/usr/bin/env bash
set -eu
[[ $# == 4 && $1 == --homedir && $3 == --kill && $4 == all ]]
[[ $2 == "$EXPECTED_HOME" && -d $2 && $2 != "$GNUPGHOME_AMBIENT" ]]
printf 'stop\n' >> "$TRACE"
exit "$FAKE_STOP_EXIT"
EOF
cat > "$WORK/bin/rm" <<'EOF'
#!/usr/bin/env bash
set -eu
printf 'remove\n' >> "$TRACE"
if [[ ${FAKE_REMOVE_FAIL:-0} == 1 ]]; then exit 8; fi
exec /bin/rm "$@"
EOF
cat > "$WORK/bin/gpg" <<'EOF'
#!/usr/bin/env bash
set -eu
[[ $# == 6 && $1 == --batch && $2 == --homedir && $4 == --show-keys && $5 == --with-colons ]]
[[ $3 == "$EXPECTED_HOME" && $3 != "$GNUPGHOME_AMBIENT" && -d $3 ]]
printf 'show\n' >> "$TRACE"
exit 23
EOF
cat > "$WORK/bin/git" <<'EOF'
#!/usr/bin/env bash
set -eu
case "$*" in
  *' status --porcelain --untracked-files=all') ;;
  *' rev-parse --verify HEAD^{commit}') printf '%040d\n' 1 ;;
  *' rev-parse --verify HEAD^{tree}') printf '%040d\n' 2 ;;
  *) exit 97 ;;
esac
EOF
for name in jq openssl unzip zip; do
    printf '#!/usr/bin/env bash\nexit 98\n' > "$WORK/bin/$name"
done
chmod 700 "$WORK/bin/"*
count=0
for name in builder fixture; do
    if [[ $name == builder ]]; then
        source="$ROOT/scripts/build-central-portal-bundle.sh"
        function=cleanup_bundle
    else
        source="$ROOT/scripts/tests/build-central-portal-bundle-test.sh"
        function=cleanup
    fi
    body="$(awk -v start="$function() {" '$0 == start { capture = 1 } capture { print } capture && /^}/ { exit }' "$source")"
    [[ -n $body ]]
    # Run the actual function and actual source-installed signal/EXIT handlers.
    traps="$(grep '^trap ' "$source")"
    for case in success original-failure stop-failure both-failures absent-home remove-failure signal; do
        dir="$WORK/$name-$case"
        mkdir -p "$dir/owned"
        ready=true; stop=0; original=0; remove=0; expected=0; retained=false
        case "$case" in
          original-failure) original=7; expected=7 ;;
          stop-failure) stop=9; expected=1; retained=true ;;
          both-failures) stop=9; original=7; expected=7; retained=true ;;
          absent-home) ready=false ;;
          remove-failure) remove=1; expected=1; retained=true ;;
          signal) expected=143 ;;
        esac
        if [[ $ready == true ]]; then mkdir -m 700 "$dir/owned/gnupg"; fi
        printf '%s\n%s\n%s\n' "$body" "$traps" \
          'if [[ $CASE == signal ]]; then kill -TERM "$$"; else exit "$ORIGINAL"; fi' > "$dir/driver.sh"
        if env PATH="$WORK/bin:$PATH" ROOT="$ROOT" WORK_DIR="$dir/owned" REPOSITORY="$dir/owned" \
            GNUPGHOME="$dir/owned/gnupg" gnupg_ready="$ready" PHASE=synthetic RELEASE_WORKTREE='' \
            EXPECTED_HOME="$dir/owned/gnupg" GNUPGHOME_AMBIENT="$WORK/ambient" TRACE="$dir/trace" \
            FAKE_STOP_EXIT="$stop" FAKE_REMOVE_FAIL="$remove" ORIGINAL="$original" CASE="$case" \
            bash "$dir/driver.sh" > "$dir/output" 2>&1; then actual=0; else actual=$?; fi
        [[ $actual == "$expected" ]]
        if [[ $retained == true ]]; then [[ -d "$dir/owned" ]]; else [[ ! -e "$dir/owned" ]]; fi
        if [[ $ready == false ]]; then expected_trace=remove
        elif [[ $stop != 0 ]]; then expected_trace=stop
        else expected_trace=$'stop\nremove'; fi
        [[ $(cat "$dir/trace") == "$expected_trace" ]]
        [[ $(cat "$WORK/ambient/sentinel") == untouched ]]
        count=$((count + 1))
    done
done
# Exercise the actual builder through key inspection with fake metadata/tools.
# Inspection intentionally fails; cleanup must preserve 23 and scope every call.
for stop in 0 9; do
    dir="$WORK/integration-$stop"
    mkdir -p "$dir/repo/scripts" "$dir/temp"
    cp "$ROOT/scripts/build-central-portal-bundle.sh" "$dir/repo/scripts/"
    printf 'VERSION_NAME=0.8.0-rc1\nGROUP=example.invalid\n' > "$dir/repo/gradle.properties"
    # Resolve the builder's fresh mktemp directory, not any inherited home.
    cat > "$WORK/bin/mktemp" <<'EOF'
#!/usr/bin/env bash
set -eu
[[ $# == 2 && $1 == -d && $2 == "$P2PKIT_RELEASE_TMPDIR/p2pkit-central-bundle.XXXXXX" ]]
mkdir -m 700 "$EXPECTED_PARENT"
printf '%s\n' "$EXPECTED_PARENT"
EOF
    chmod 700 "$WORK/bin/mktemp"
    if env PATH="$WORK/bin:$PATH" HOME="$WORK/ambient" GNUPGHOME="$WORK/ambient" \
        GNUPGHOME_AMBIENT="$WORK/ambient" P2PKIT_RELEASE_TMPDIR="$dir/temp" \
        EXPECTED_PARENT="$dir/temp/created" EXPECTED_HOME="$dir/temp/created/gnupg" \
        TRACE="$dir/trace" FAKE_STOP_EXIT="$stop" FAKE_REMOVE_FAIL=0 \
        ORG_GRADLE_PROJECT_signingInMemoryKey=NOT_A_REAL_KEY \
        ORG_GRADLE_PROJECT_signingInMemoryKeyBase64='' \
        ORG_GRADLE_PROJECT_signingInMemoryKeyPassword=NOT_A_REAL_PASSWORD \
        MAVEN_SIGNING_KEY_FINGERPRINT=AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA \
        bash "$dir/repo/scripts/build-central-portal-bundle.sh" "$dir/result.zip" > "$dir/output" 2>&1; then actual=0; else actual=$?; fi
    [[ $actual == 23 ]]
    if [[ $stop == 0 ]]; then
        [[ $(cat "$dir/trace") == $'show\nstop\nremove' && ! -e "$dir/temp/created" ]]
    else
        [[ $(cat "$dir/trace") == $'show\nstop' && -d "$dir/temp/created/gnupg" ]]
    fi
    [[ $(cat "$WORK/ambient/sentinel") == untouched ]]
    [[ ! -e "$dir/result.zip" ]]
    count=$((count + 1))
done
printf 'PASS: %s synthetic GPG lifecycle cases; no real key, signing or Gradle execution\n' "$count"
