#!/usr/bin/env bash
# Shared Central request budgets. Source after defining fail(); never retries.
# Each phase owns an absolute monotonic deadline. curl's connect and transfer
# limits include DNS/TLS/redirects and are clipped to that phase's remaining time.
central_phase_start() {
    CENTRAL_HTTP_DEADLINE="$(python3 - "$1" <<'PY'
import math, os, sys, time
seconds = float(sys.argv[1])
if os.environ.get('P2PKIT_CENTRAL_TEST_MODE') == '1':
    override = float(os.environ.get('P2PKIT_CENTRAL_PHASE_SECONDS', seconds))
    if not math.isfinite(override) or not 0 < override <= seconds:
        raise SystemExit('invalid Central phase budget')
    seconds = override
print(time.monotonic() + seconds)
PY
    )" || fail "invalid Central phase budget"
}

central_phase_active() {
    python3 - "$CENTRAL_HTTP_DEADLINE" <<'PY'
import sys, time
raise SystemExit(0 if time.monotonic() < float(sys.argv[1]) else 1)
PY
}

central_http() {
    local maximum="$1" limits connect total
    shift
    limits="$(python3 - "$CENTRAL_HTTP_DEADLINE" "$maximum" <<'PY'
import math, os, sys, time
remaining = float(sys.argv[1]) - time.monotonic()
maximum = float(sys.argv[2])
if os.environ.get('P2PKIT_CENTRAL_TEST_MODE') == '1':
    override = float(os.environ.get('P2PKIT_CENTRAL_REQUEST_SECONDS', maximum))
    if not math.isfinite(override) or not 0 < override <= maximum:
        raise SystemExit(2)
    maximum = override
# curl interprets zero as unlimited; never round an exhausted budget to zero.
if remaining < 0.001:
    raise SystemExit(28)
total = min(maximum, remaining)
print(f'{min(10, total):.6f} {total:.6f}')
PY
    )" || return "$?"
    read -r connect total <<<"$limits"
    # Ignore per-user curlrc retry settings: upload is strictly one request.
    curl --disable --connect-timeout "$connect" --max-time "$total" "$@"
}

central_phase_sleep() {
    python3 - "$CENTRAL_HTTP_DEADLINE" "$1" <<'PY'
import sys, time
time.sleep(max(0, min(float(sys.argv[2]), float(sys.argv[1]) - time.monotonic())))
PY
}
