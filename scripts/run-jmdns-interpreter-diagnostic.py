#!/usr/bin/env python3
"""Optional hosted JmDNS control, not RPC qualification or multicast delivery proof.

Reuse the retained controller's pinned dependency, compiler argv, canonical Python
argument and unchanged real-resource control. Post-failure primitives run only if
the fixture's existing native context gate admits them; their output cannot turn
a failed control into success. The modular CI wrapper owns source/host evidence.
"""
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import platform
import re
import signal
import sys
import tempfile
import threading
import time

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import ci_evidence as evidence

spec = importlib.util.spec_from_file_location('jmdns_rpc_controller', ROOT / 'scripts/run-rpc-qualification.py')
rpc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rpc)

SCOPE = 'JMDNS_CANONICAL_INTERPRETER_DIAGNOSTIC_NOT_QUALIFICATION'
DEADLINE = 'P2PKIT_CI_COMMAND_DEADLINE_NS'
MAX_LOG = 1024 * 1024
COMMANDS = ('multicast-reviewed-dependency', 'multicast-vendor-compile',
            'multicast-fixture-compile', 'multicast-readiness-control')
# No Java/Python option injection, proxy, signing, repository or GitHub tokens.
# Preserve inherited ownership carriers; this is not a new root process domain.
ENVIRONMENT = frozenset(('PATH', 'LANG', 'LC_ALL', 'TMPDIR', 'JAVA_HOME', 'GRADLE_USER_HOME',
    'CI', 'GITHUB_ACTIONS', 'RUNNER_ENVIRONMENT', 'RUNNER_OS', 'RUNNER_ARCH', 'RUNNER_TEMP',
    'RUNNER_TRACKING_ID', DEADLINE, evidence.audit_processes.JOB_ENV,
    evidence.audit_processes.CHAIN_ENV, evidence.audit_processes.DOMAINS_ENV,
    evidence.audit_processes.STATE_ENV, evidence.audit_processes.PIPE_ENV))


def admit():
    rpc.need(platform.system() == 'Darwin' and os.environ.get('GITHUB_ACTIONS') == 'true' and
             os.environ.get('RUNNER_ENVIRONMENT') == 'github-hosted', 'Hosted macOS required')
    rpc.need('P2PKIT_JMDNS_FIXTURE_IPV4' not in os.environ, 'No multicast/interface override')
    rpc.multicast_interpreter()  # Refuse bad launchers before allocation or acquisition.
    home = Path(os.environ.get('JAVA_HOME', ''))
    rpc.need(home.is_absolute(), 'JDK 17 required')
    home = home.resolve(strict=True)
    release = rpc.bounded(home / 'release', 16384).decode('utf-8')
    rpc.need(len(re.findall(r'^JAVA_VERSION="17(?:\.[0-9A-Za-z.+_-]+)?"$', release, re.M)) == 1 and
             all((home / 'bin' / name).is_file() and os.access(home / 'bin' / name, os.X_OK)
                 for name in ('java', 'javac')), 'JDK 17 required')
    # One cumulative budget; never renew a Terminal parent's command clock.
    end = time.monotonic() + 420
    if DEADLINE in os.environ:
        value = os.environ[DEADLINE]
        rpc.need(re.fullmatch(r'[1-9][0-9]{0,19}', value), 'Invalid enclosing deadline')
        end = min(end, int(value) / 1_000_000_000)
    rpc.need(end - time.monotonic() > 15, 'Enclosing deadline exhausted')
    return end


class Diagnostic:
    def __init__(self, state, end, cancelled):
        self.state, self.end, self.cancelled = state, end, cancelled
        self.environment = {key: value for key, value in os.environ.items() if key in ENVIRONMENT}
        self.policy = rpc.module('jmdns_fixture_marker_policy', 'run-rpc-hosted-validation.py')
        self.result = {'scope': SCOPE, 'status': 'FAIL', 'commands': [], 'multicastMarkers': []}
        (state / 'work').mkdir(mode=0o700)

    def invoke(self, purpose, argv, timeout, allow_failure=False):
        index = len(self.result['commands'])
        rpc.need(index < len(COMMANDS) and purpose == COMMANDS[index] and
                 timeout == (45 if index == 3 else 90) and allow_failure == (index == 3),
                 'Unexpected diagnostic command')
        rpc.need(not self.cancelled.is_set(), 'Diagnostic cancelled')
        remaining = self.end - time.monotonic() - 15  # Keep the existing cleanup budget.
        rpc.need(remaining > 0, 'Diagnostic deadline exhausted')
        private = self.state / purpose
        outcome = evidence.run_command(argv, cwd=ROOT, environment=self.environment,
            private=private, timeout=min(timeout, remaining), cancelled=self.cancelled.is_set,
            log_limit=MAX_LOG, cleanup_seconds=15, create_gradle_home=False)
        # Keep the full finite ownership outcome privately, even when unsafe to read logs.
        evidence.write_private(private / 'outcome.json', (json.dumps(outcome) + '\n').encode())
        self.result['commands'].append({'purpose': purpose, **outcome})
        rpc.need(outcome.get('cleanupKnown') is True and outcome.get('capturesClosed') is True,
                 'Diagnostic finalization unproven', 'OWNERSHIP_UNPROVEN')
        rpc.need(not self.cancelled.is_set() and outcome.get('timedOut') is False and
                 outcome.get('code') in ('PASS', 'COMMAND_FAILED') and
                 type(outcome.get('exitCode')) is int and
                 (outcome['code'] == 'PASS') == (outcome['exitCode'] == 0),
                 'Diagnostic command did not complete', 'PRODUCT_FAILED')
        rpc.need(outcome['exitCode'] == 0 or allow_failure, 'Diagnostic command failed', 'PRODUCT_FAILED')
        return {'id': purpose, 'productExitCode': outcome['exitCode']}

    def output(self, proof, maximum=MAX_LOG, stream='stdout'):
        rpc.need(proof['id'] in COMMANDS and stream in ('stdout', 'stderr'), 'Invalid capture')
        return rpc.bounded(self.state / proof['id'] / (stream + '.log'), min(maximum, MAX_LOG))

    def run(self):
        # Deliberately reuse only this diagnostic method, not full RPC admission.
        rpc.Qualification.multicast_admission(self)
        rpc.need(not self.cancelled.is_set() and time.monotonic() < self.end,
                 'Diagnostic interrupted or expired')
        self.result['status'] = 'PASS'


def main(argv=None):
    previous, diagnostic, state = {}, None, None
    cancelled = threading.Event()
    code = 1
    try:
        rpc.need(not (sys.argv[1:] if argv is None else argv), 'No diagnostic arguments supported')
        for sig in (signal.SIGINT, signal.SIGTERM):
            previous[sig] = signal.signal(sig, lambda _sig, _frame: cancelled.set())
        end = admit()
        reports = ROOT / 'build/reports/jmdns-interpreter-diagnostic'
        rpc.need(reports.resolve() == reports, 'Linked diagnostic reports refused')
        reports.mkdir(parents=True, exist_ok=True, mode=0o700)
        state = Path(tempfile.mkdtemp(prefix='run-', dir=reports))
        diagnostic = Diagnostic(state, end, cancelled)
        diagnostic.run()
        rpc.need(diagnostic.result['status'] == 'PASS' and not cancelled.is_set(),
                 'Diagnostic did not pass')
        code = 0
    except Exception:
        # Private command outcomes/captures retain detail. Never publish exception text.
        pass
    finally:
        if cancelled.is_set():
            code = 1
        if diagnostic is not None:
            if code != 0:
                diagnostic.result['status'] = 'FAIL'
            try:
                evidence.write_private(state / 'result.json', (json.dumps(diagnostic.result) + '\n').encode())
            except Exception:
                code = 1
        for sig, handler in previous.items():
            signal.signal(sig, handler)
    print(('PASS' if code == 0 else 'FAIL') + ' ' + SCOPE)
    return code


if __name__ == '__main__':
    sys.exit(main())
