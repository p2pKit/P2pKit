#!/usr/bin/env bash
# Isolated receiver-capacity experiment only. Never run on the owner's device.
# A separately reviewed exact-source push/run authorization is required.
set -euo pipefail
set -C
umask 077
test "$#" -eq 8
test "$EUID" -eq 0
readonly SOURCE="$1" TEMP="$2" SHA="$3" REF="$4" RUN="$5" ATTEMPT="$6" IMAGE_OS="$7" IMAGE_VERSION="$8"
readonly BRANCH=work/receiver-hosted-capacity-20260922-362aa96c
readonly BASE=/tmp/p2pkit-initial-graph-hosted
test "$SOURCE" = /home/runner/work/P2pKit/P2pKit
test "$TEMP" = /home/runner/work/_temp
test "$REF" = "refs/heads/$BRANCH"
test "$ATTEMPT" = 1
test "$IMAGE_OS" = ubuntu24
[[ "$SHA" =~ ^[0-9a-f]{40}$ && "$RUN" =~ ^[1-9][0-9]{0,19}$ ]]
[[ "$IMAGE_VERSION" =~ ^[0-9]{8}\.[0-9]+\.[0-9]+$ ]]
test "$(readlink -f -- "$SOURCE")" = "$SOURCE"
test "$(readlink -f -- "$TEMP")" = "$TEMP"
readonly CASE="$TEMP/p2pkit-receiver-capacity-$RUN-$ATTEMPT"
readonly RESULTS="$CASE/results/body"
readonly RESULT_OWNER=$(stat -c '%u:%g' -- "$SOURCE")
# The enclosing workflow owns fresh capture directories and observes our actual
# return. The test UID cannot access either those captures or this body output.
test -d "$CASE/results"
test "$(readlink -f -- "$CASE/results")" = "$CASE/results"
mkdir -m 0700 -- "$RESULTS"
finish() {
    local body_status=$? finalization_status=0
    trap - EXIT
    set +e
    printf '%s\n' "$body_status" > "$RESULTS/body.exit" || finalization_status=1
    date -u '+%Y-%m-%dT%H:%M:%SZ' > "$RESULTS/body-finished-at.txt" || finalization_status=1
    # Only public model transcripts/metadata. The synthetic fixture is excluded.
    # Errors go to the caller's launcher.stderr. Do not discard a failed capture
    # finalization or replace an earlier nonzero body result with success.
    chown -R -- "$RESULT_OWNER" "$RESULTS" || finalization_status=1
    printf 'RECEIVER_CAPACITY_BODY_EXIT=%s; MODEL_ONLY; NO_RELEASE_AUTHORITY\n' \
        "$body_status" || finalization_status=1
    if test "$body_status" -ne 0; then exit "$body_status"; fi
    exit "$finalization_status"
}
trap finish EXIT
date -u '+%Y-%m-%dT%H:%M:%SZ' > "$RESULTS/started-at.txt"
printf 'repository=p2pKit/P2pKit\nref=%s\ncommit=%s\nrun=%s\nattempt=%s\nimage_os=%s\nimage_version=%s\n' \
    "$REF" "$SHA" "$RUN" "$ATTEMPT" "$IMAGE_OS" "$IMAGE_VERSION" > "$RESULTS/host.txt"

# No installations, alternate interpreters or fallback to an unconfined launch.
TOOLS=(/usr/bin/python3.12 /usr/bin/unshare /usr/bin/setpriv /usr/bin/env
    /usr/bin/timeout /usr/bin/prlimit /usr/bin/bash /usr/bin/git /usr/bin/sha256sum)
for tool in "${TOOLS[@]}"; do test -x "$tool"; done
sha256sum "${TOOLS[@]}" > "$RESULTS/tools.sha256"
/usr/bin/dpkg-query -W python3.12-minimal python3.12 libpython3.12-stdlib util-linux coreutils \
    > "$RESULTS/runtime-packages.txt"
/usr/bin/lscpu > "$RESULTS/cpu.txt"
grep '^MemAvailable:' /proc/meminfo > "$RESULTS/memory.txt"
test "$(awk '/^MemAvailable:/ {print $2}' /proc/meminfo)" -ge 1048576
/usr/bin/df -k -- "$TEMP" > "$RESULTS/disk.txt"
test "$(df -k --output=avail "$TEMP" | tail -n 1)" -ge 1048576
git_view() {
    /usr/bin/git --no-optional-locks -c safe.directory="$SOURCE" -c core.fsmonitor=false \
        -c core.hooksPath=/dev/null -C "$SOURCE" "$@"
}
test "$(git_view rev-parse HEAD)" = "$SHA"
test -z "$(git_view status --porcelain=v1 --untracked-files=all)"
git_view rev-parse HEAD 'HEAD^{tree}' > "$RESULTS/source-identity.txt"
git_view ls-files -z -- 'scripts/*.py' 'scripts/tests/*.py' .github/test-evidence-recipient.json \
    > "$RESULTS/source-paths.nul"
mkdir -m 0755 -- "$BASE" "$BASE/source" "$BASE/harness"
mkdir -m 0700 -- "$BASE/work"
chown 65534:65534 -- "$BASE/work"
while IFS= read -r -d '' name; do
    [[ "$name" = scripts/*.py || "$name" = .github/test-evidence-recipient.json ]]
    [[ "$name" != *$'\n'* && "$name" != *$'\r'* && "$name" != *'/../'* ]]
    test -f "$SOURCE/$name"
    test ! -L "$SOURCE/$name"
    install -D -o 0 -g 0 -m 0444 -- "$SOURCE/$name" "$BASE/source/$name"
done < "$RESULTS/source-paths.nul"
install -o 0 -g 0 -m 0444 -- "$SOURCE/scripts/tests/initial-recipient-graph-probe.py" \
    "$BASE/harness/guarded-author.py"
install -o 0 -g 0 -m 0444 -- "$SOURCE/scripts/tests/initial-recipient-graph-fixture.py" \
    "$BASE/harness/retained-fixture.py"
(cd "$BASE/source" && xargs -0 sha256sum < "$RESULTS/source-paths.nul") > "$RESULTS/source-inputs.sha256"
(cd "$BASE/harness" && sha256sum guarded-author.py retained-fixture.py) > "$RESULTS/harness-inputs.sha256"
# The held receiver and full test body are unchanged; this is not an optimization.
sha256sum "$SOURCE/scripts/run-hosted-initial-recipient.py" \
    "$SOURCE/scripts/tests/hosted-initial-recipient-original-graph-test.py" > "$RESULTS/receiver-inputs.sha256"

check_inputs() {
    sha256sum -c "$RESULTS/tools.sha256"
    (cd "$BASE/source" && sha256sum -c "$RESULTS/source-inputs.sha256")
    (cd "$SOURCE" && sha256sum -c "$RESULTS/source-inputs.sha256")
    (cd "$BASE/harness" && sha256sum -c "$RESULTS/harness-inputs.sha256")
    test "$(git_view rev-parse HEAD)" = "$SHA"
    test -z "$(git_view status --porcelain=v1 --untracked-files=all)"
}
run_case() {
    local phase="$1" status
    check_inputs > "$RESULTS/$phase.pre-integrity.txt" 2> "$RESULTS/$phase.pre-integrity.stderr"
    date -u '+%Y-%m-%dT%H:%M:%SZ' > "$RESULTS/$phase.started-at.txt"
    # Same envelope as the retained R9 receiver-only attempt. Preparation has
    # its own invocation, as it already did in R9; it is not reclassified away.
    local -a command=(/usr/bin/setpriv --clear-groups --no-new-privs /usr/bin/env -i
        PATH=/usr/bin:/bin HOME=/nonexistent LANG=C.UTF-8 LC_ALL=C.UTF-8
        /usr/bin/timeout --signal=TERM --kill-after=2s 30s /usr/bin/prlimit
        --cpu=20:20 --as=536870912:536870912 --fsize=33554432:33554432 --nofile=128:128 --core=0:0
        /usr/bin/unshare --mount --net --pid --ipc --uts --fork --kill-child=KILL --mount-proc
        /usr/bin/setpriv --reuid=65534 --regid=65534 --clear-groups --no-new-privs
        --bounding-set=-all --inh-caps=-all --ambient-caps=-all
        /usr/bin/env -i PATH=/usr/bin:/bin HOME="$BASE/work" TMPDIR="$BASE/work"
        LANG=C.UTF-8 LC_ALL=C.UTF-8 /usr/bin/python3.12 -I -B -S "$BASE/harness/guarded-author.py" "$phase")
    printf '%q ' "${command[@]}" > "$RESULTS/$phase.command"
    printf '\n' >> "$RESULTS/$phase.command"
    TIMEFORMAT='wall=%3R user=%3U system=%3S'
    set +e
    { time "${command[@]}" </dev/null > "$RESULTS/$phase.stdout" 2> "$RESULTS/$phase.stderr"; } \
        2> "$RESULTS/$phase.time"
    status=$?
    set -e
    printf '%s\n' "$status" > "$RESULTS/$phase.exit"
    date -u '+%Y-%m-%dT%H:%M:%SZ' > "$RESULTS/$phase.finished-at.txt"
    check_inputs > "$RESULTS/$phase.post-integrity.txt" 2> "$RESULTS/$phase.post-integrity.stderr"
    cat "$RESULTS/$phase.time"
    printf 'RECEIVER_CAPACITY_PHASE=%s COMMAND_EXIT=%s\n' "$phase" "$status"
    test "$status" -eq 0
    grep -Fx 'AUTHOR_GUARD_SYNTHETIC_CONTROLS=4 UNEXPECTED_DENIALS=0' "$RESULTS/$phase.stdout" >/dev/null
    grep -Fx 'AUTHOR_RESOURCE_WARNINGS=0' "$RESULTS/$phase.stdout" >/dev/null
}
run_case prepare
# Only a declaration hash is exported; no synthetic payload/key or live owner.
sha256sum "$BASE/work/retained-synthetic-graph.json" > "$RESULTS/synthetic-declaration.sha256"
run_case read
grep -E '^SYNTHETIC_READER_ONLY_COMPLETE CPU_SECONDS=[0-9]+\.[0-9]+ ORIGINALS=1066 AUTHORITY=NONE$' \
    "$RESULTS/read.stdout" > "$RESULTS/complete-marker.txt"
printf '%s\n' 'EXACT_HOSTED_LINUX_OFFLINE_MODEL_CAPACITY_ONLY; NOT_NATIVE_PROVIDER_OR_RELEASE_QUALIFICATION' \
    > "$RESULTS/result.txt"
cat "$RESULTS/complete-marker.txt" "$RESULTS/result.txt"
