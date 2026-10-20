#!/usr/bin/env python3
"""One read-only Intel inventory observation. Never platform-test qualification.

The 600-second ceiling belongs ONLY to this diagnostic. Production inventory
keeps its 120-second deadline. Streams/context/stack samples remain encrypted by
the enclosing ci_evidence invocation; only a fixed status is printed publicly.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import platform
import re
import selectors
import signal
import subprocess
import sys
import threading
import time

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('intel_platform_owner', ROOT / 'scripts/run-platform-tests.py')
owner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(owner)
OUTPUT = ROOT / 'build/reports/intel-simulator-diagnostic'
SCOPE = 'READ_ONLY_INTEL_INVENTORY_DIAGNOSTIC_NOT_QUALIFICATION'
INVENTORY = ['/usr/bin/xcrun', 'simctl', 'list', '--json', 'runtimes']
INVENTORY_SECONDS = 600
SAMPLE_AT = (90, 180)
STREAM_LIMITS = {'stdout': 2 * 1024 * 1024, 'stderr': 256 * 1024}
DEVELOPER = '/Applications/Xcode_26.3.app/Contents/Developer'
CANCELLED = threading.Event()
OUTER_DEADLINE = None


def require(condition, code):
    if not condition:
        raise RuntimeError(code)


def write(path, value):
    with path.open('xb') as stream:
        stream.write((json.dumps(value, sort_keys=True, indent=2) + '\n').encode())
    path.chmod(0o600)


class Capture:
    """Retained direct child/group plus concurrent bounded stream readers."""
    def __init__(self, label, argv, seconds, directory=OUTPUT):
        self.label, self.argv = label, argv
        self.directory = directory / 'commands' / label
        self.directory.mkdir(parents=True, mode=0o700)
        self.began = time.monotonic()
        self.started_utc = owner.datetime.now(owner.timezone.utc).isoformat()
        self.deadline = self.began + seconds
        self.buffers = {name: bytearray() for name in STREAM_LIMITS}
        self.done = {name: threading.Event() for name in STREAM_LIMITS}
        self.eof = {name: threading.Event() for name in STREAM_LIMITS}
        self.stop = threading.Event()
        self.overflow = threading.Event()
        self.read_error = threading.Event()
        self.threads = []
        self.process = None
        self.row = None
        try:
            self.process = subprocess.Popen(argv, cwd=ROOT, start_new_session=True,
                                            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                            stderr=subprocess.PIPE)
            for name in STREAM_LIMITS:
                thread = threading.Thread(target=self.drain, args=(name,), daemon=True)
                thread.start()
                self.threads.append(thread)
        except BaseException:
            self.close('SPAWN_OR_CAPTURE_FAILED')
            raise

    def drain(self, name):
        stream = getattr(self.process, name)
        try:
            os.set_blocking(stream.fileno(), False)
            with selectors.DefaultSelector() as selector:
                selector.register(stream, selectors.EVENT_READ)
                while not self.stop.is_set():
                    if not selector.select(0.05):
                        continue
                    try:
                        chunk = os.read(stream.fileno(), 65536)
                    except BlockingIOError:
                        continue
                    if not chunk:
                        self.eof[name].set()
                        break
                    room = STREAM_LIMITS[name] - len(self.buffers[name])
                    self.buffers[name].extend(chunk[:room])
                    if len(chunk) > room:
                        self.overflow.set()  # Continue draining until original child retires.
        except (OSError, ValueError):
            self.read_error.set()
        finally:
            self.done[name].set()

    def reason(self, *, allow_reap=True):
        if CANCELLED.is_set():
            return 'CANCELLED'
        if self.overflow.is_set():
            return 'OUTPUT_LIMIT'
        if self.read_error.is_set():
            return 'CAPTURE_ERROR'
        if time.monotonic() >= self.deadline:
            return 'TIMEOUT'
        # Never reap the inventory while a PID-targeted observer is active.
        if allow_reap and self.process.poll() is not None and all(x.is_set() for x in self.done.values()):
            return 'EXITED'
        return None

    def close(self, reason):
        if self.row is not None:
            return self.row
        drained = False
        work_seconds = time.monotonic() - self.began
        try:
            # Existing source-owned TERM(15s)/KILL(5s) original-group retirement.
            drained = owner.terminate_process(self.process)
        finally:
            # Drain buffered kernel output through EOF before stopping readers.
            for thread in self.threads:
                thread.join(timeout=0.25)
            self.stop.set()
            for thread in self.threads:
                thread.join(timeout=1)
            closed = not any(thread.is_alive() for thread in self.threads)
            if self.process is not None and closed:
                self.process.stdout.close()
                self.process.stderr.close()
            self.row = {'label': self.label, 'argv': self.argv, 'startedUtc': self.started_utc,
                        'elapsedSeconds': time.monotonic() - self.began, 'workElapsedSeconds': work_seconds,
                        'reason': reason,
                        'exitCode': None if self.process is None else self.process.returncode,
                        'timedOut': reason == 'TIMEOUT', 'outputLimitExceeded': self.overflow.is_set(),
                        'captureError': self.read_error.is_set(), 'capturesClosed': closed,
                        'streamsReachedEof': all(event.is_set() for event in self.eof.values()),
                        'ownedGroupDrained': drained}
            for name, buf in self.buffers.items():
                raw = bytes(buf)
                with (self.directory / (name + '.bin')).open('xb') as stream:
                    stream.write(raw)
                (self.directory / (name + '.bin')).chmod(0o600)
                self.row[name] = {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}
            write(self.directory / 'result.json', self.row)
        return self.row


def probe(label, argv, stage_deadline):
    require(not CANCELLED.is_set() and stage_deadline > time.monotonic(), 'OBSERVATION_BUDGET')
    capture = Capture(label, argv, min(10, stage_deadline - time.monotonic()))
    try:
        while (reason := capture.reason()) is None:
            time.sleep(0.02)
        return capture.close(reason), bytes(capture.buffers['stdout'])
    finally:
        if capture.row is None:
            capture.close('INTERRUPTED')


def source_snapshot(prefix, deadline):
    result = {}
    for key, args in (('status', ['status', '--porcelain=v1']),
                      ('commit', ['rev-parse', 'HEAD']), ('tree', ['rev-parse', 'HEAD^{tree}'])):
        row, raw = probe(prefix + '-' + key, ['/usr/bin/git', '--no-optional-locks', *args], deadline)
        require(observed(row), 'SOURCE_QUERY_FAILED')
        result[key] = raw.decode('ascii').strip()
    require(result.pop('status') == '', 'SOURCE_DIRTY')
    require(all(re.fullmatch('[0-9a-f]{40}', v) for v in result.values()), 'SOURCE_IDENTITY')
    return result


def observed(row):
    return (row['reason'] == 'EXITED' and type(row['exitCode']) is int and row['exitCode'] == 0
            and row['ownedGroupDrained'] is True and row['capturesClosed'] is True
            and row['streamsReachedEof'] is True
            and not row['outputLimitExceeded'] and not row['captureError'])


def sample_commands(pid):
    require(type(pid) is int and pid > 1, 'ORIGINAL_PID')
    return [('sample', ['/usr/bin/sample', str(pid), '1', '1', '-mayDie', '-file', '/dev/stdout']),
            ('process', ['/bin/ps', '-p', str(pid), '-o', 'pid=,ppid=,pgid=,sess=,stat=,comm='])]



def observer_exit_confirmed(sample):
    """The fixed sample/ps PID lookup must end before releasing its target hold.

    Group/capture uncertainty remains a diagnostic failure even if the direct
    trusted observer exited. An unconfirmed direct exit is handed to the outer
    owner with the inventory still unreaped; it is never treated as retirement.
    """
    if hasattr(sample, 'direct_exit_confirmed'):
        return sample.direct_exit_confirmed
    process = sample.process
    recovered = process.returncode is None
    if recovered:
        try:
            process.kill()  # Retained unreaped Popen only, not a discovered PID.
            process.wait(timeout=5)
        except (OSError, subprocess.TimeoutExpired):
            pass
    sample.direct_exit_confirmed = process.returncode is not None
    if recovered:
        write(sample.directory / 'direct-exit-recovery.json', {
            'attempted': True, 'waitSeconds': 5, 'exitCode': process.returncode,
            'confirmed': sample.direct_exit_confirmed, 'originalGroupResultUnchanged': True})
    return sample.direct_exit_confirmed



def retain_original_until_outer_handoff(inventory):
    """Keep the original reference until existing outer cancellation or its bound.

    This exceptional FAILED path does not promise a PID hold after interpreter
    exit, nor claim the outer scope retired anything. No new process or retry.
    """
    require(OUTER_DEADLINE is not None, 'OUTER_DEADLINE_MISSING')
    marker = {'directObserverExitUnknown': True, 'inventoryLocallyReaped': False,
              'cleanupKnown': False, 'qualification': 'NOT_PERFORMED'}
    try:
        write(OUTPUT / 'original-guard-handoff.json', marker)
    finally:
        # The collector supplies this monotonic deadline. A signal already seen
        # means its cancellation/retirement path has already started.
        triggered = CANCELLED.wait(max(0, OUTER_DEADLINE - time.monotonic()) + 20)
        # Keep the reference live through the wait, without polling/reaping it.
        require(inventory.process is not None, 'ORIGINAL_REFERENCE_MISSING')
    write(OUTPUT / 'original-guard-handoff-end.json', {
        **marker, 'outerCancellationObserved': triggered,
        'pidHoldAfterInterpreterExitClaimed': False})


def inventory_observation():
    inventory = Capture('inventory', INVENTORY, INVENTORY_SECONDS)
    samplers, rows, thresholds = [], [], iter(SAMPLE_AT)
    next_sample = next(thresholds, None)
    primary_error = None
    try:
        while True:
            for sample in list(samplers):
                sample_reason = sample.reason()
                if sample_reason:
                    closed = sample.close(sample_reason)
                    rows.append(closed)
                    require(observer_exit_confirmed(sample), 'OBSERVER_DIRECT_EXIT_UNKNOWN')
                    require(closed['ownedGroupDrained'] and closed['capturesClosed'], 'OBSERVER_RETIREMENT_UNKNOWN')
                    samplers.remove(sample)
            reason = inventory.reason(allow_reap=not samplers)
            if reason:
                break
            if next_sample is not None and time.monotonic() - inventory.began >= next_sample:
                # Holding this unreaped direct child prevents PID reuse until all
                # PID-targeted observers close. Do not poll it again meanwhile.
                if not samplers and inventory.process.poll() is None:
                    for label, argv in sample_commands(inventory.process.pid):
                        samplers.append(Capture(f'{label}-{next_sample}', argv, 8))
                next_sample = next(thresholds, None)
            time.sleep(0.02)
    except BaseException as error:
        primary_error = error
        raise
    finally:
        retirement_errors = []
        for sample in samplers:
            try:
                rows.append(sample.close('INVENTORY_RETIRING'))
            except BaseException as error:
                # Finish every observer before the original, preserving first failure.
                retirement_errors.append(error)
        holds_released = True
        for sample in samplers:
            try:
                holds_released = observer_exit_confirmed(sample) and holds_released
            except BaseException as error:
                retirement_errors.append(error)
                holds_released = False
        try:
            if holds_released:
                row = inventory.close(locals().get('reason') or 'INTERRUPTED')
            else:
                # Do not poll/kill/reap the target while a direct PID observer's
                # exit is unconfirmed. The existing outer ownership scope must
                # retire this failed command domain; no local cleanup claim.
                retain_original_until_outer_handoff(inventory)
                retirement_errors.append(RuntimeError('OBSERVER_DIRECT_EXIT_UNKNOWN'))
        except BaseException as error:
            retirement_errors.append(error)
        if retirement_errors:
            if primary_error is not None:
                primary_error.add_note('DIAGNOSTIC_RETIREMENT_FAILED')
            else:
                raise RuntimeError('DIAGNOSTIC_RETIREMENT_FAILED') from retirement_errors[0]
    return row, rows


def admit(env):
    global OUTER_DEADLINE
    deadline = env.get('P2PKIT_CI_COMMAND_DEADLINE_NS', '')
    require(re.fullmatch('[0-9]{1,20}', deadline) is not None, 'OUTER_DEADLINE_MISSING')
    OUTER_DEADLINE = int(deadline) / 1_000_000_000
    require(0 < OUTER_DEADLINE - time.monotonic() <= 900, 'OUTER_DEADLINE_BOUND')
    expected = {'GITHUB_ACTIONS': 'true', 'RUNNER_ENVIRONMENT': 'github-hosted',
                'GITHUB_REPOSITORY': 'p2pKit/P2pKit', 'GITHUB_EVENT_NAME': 'push',
                'GITHUB_WORKFLOW': 'Intel simulator diagnostic', 'GITHUB_JOB': 'diagnose',
                'GITHUB_REF': 'refs/heads/work/issues-intel-inventory-diagnostic-20261020',
                'RUNNER_OS': 'macOS', 'RUNNER_ARCH': 'X64', 'DEVELOPER_DIR': DEVELOPER}
    require(all(env.get(k) == v for k, v in expected.items()), 'ADMISSION')
    require(platform.system() == 'Darwin' and platform.machine() == 'x86_64', 'NATIVE_HOST')
    require(os.getuid() == os.geteuid() != 0 and os.getgid() == os.getegid() != 0, 'ORDINARY_UID')
    require(re.fullmatch('[0-9a-f]{40}', env.get('GITHUB_SHA', '')) is not None, 'SOURCE_ADMISSION')
    require(env.get('GITHUB_WORKFLOW_SHA') == env['GITHUB_SHA'], 'WORKFLOW_SOURCE')
    require(env.get('GITHUB_WORKFLOW_REF') == 'p2pKit/P2pKit/.github/workflows/intel-simulator-diagnostic.yml@' + expected['GITHUB_REF'], 'WORKFLOW_IDENTITY')
    require(Path(env.get('GITHUB_WORKSPACE', '')).resolve() == ROOT, 'WORKSPACE')


def main():
    require(len(sys.argv) == 1, 'NO_ARGUMENTS')
    admit(os.environ)
    OUTPUT.mkdir(parents=True, mode=0o700, exist_ok=False)
    handlers = {sig: signal.signal(sig, lambda *_: CANCELLED.set()) for sig in (signal.SIGTERM, signal.SIGINT)}
    summary = {'schema': 1, 'scope': SCOPE, 'qualification': 'NOT_PERFORMED', 'testsExecuted': 0,
               'configurationChanged': False, 'productionInventorySeconds': 120,
               'diagnosticInventorySeconds': INVENTORY_SECONDS, 'sourceBefore': None, 'sourceAfter': None,
               'inventory': None, 'observers': [], 'error': None, 'result': 'REFUSED',
               'preconditionDifferences': ['No Bonjour preference preparation or restore',
                                          'No Gradle/cache/Java setup or platform tests']}
    code = 1
    try:
        before_deadline = time.monotonic() + 120
        summary['sourceBefore'] = source_snapshot('before', before_deadline)
        require(summary['sourceBefore']['commit'] == os.environ['GITHUB_SHA'], 'SOURCE_MISMATCH')
        context = {'developerDir': os.environ['DEVELOPER_DIR'], 'uid': os.getuid(), 'gid': os.getgid(),
                   'pid': os.getpid(), 'session': os.getsid(0), 'processGroup': os.getpgrp(),
                   'runId': os.environ.get('GITHUB_RUN_ID'), 'runAttempt': os.environ.get('GITHUB_RUN_ATTEMPT'),
                   'consoleUserMatches': Path('/dev/console').stat().st_uid == os.getuid(), 'probes': {}}
        for label, argv in [('macos', ['/usr/bin/sw_vers', '-productVersion']),
                            ('xcode', ['/usr/bin/xcodebuild', '-version']),
                            ('first-launch', ['/usr/bin/xcodebuild', '-checkFirstLaunchStatus']),
                            ('coresimulator-service', ['/bin/launchctl', 'print',
                             f'gui/{os.getuid()}/com.apple.CoreSimulator.CoreSimulatorService']),
                            ('bonjour-preference', ['/usr/bin/defaults', 'read', '/Library/Preferences/com.apple.mDNSResponder', 'NoMulticastAdvertisements'])]:
            row, raw = probe(label, argv, before_deadline)
            context['probes'][label] = row
            if label == 'macos':
                require(observed(row) and re.fullmatch(rb'15\.[0-9.]+\s*', raw), 'MACOS_VERSION')
            if label == 'xcode':
                require(observed(row) and raw.startswith(b'Xcode 26.3\n'), 'XCODE_VERSION')
        write(OUTPUT / 'context.json', context)
        require(time.monotonic() <= before_deadline, 'PRELUDE_BUDGET')
        summary['inventory'], summary['observers'] = inventory_observation()
        row = summary['inventory']
        summary['completedWithinProduction120'] = observed(row) and row['workElapsedSeconds'] <= 120
        summary['result'] = 'INVENTORY_OBSERVED' if observed(row) else 'INVENTORY_NOT_OBSERVED'
        after_deadline = time.monotonic() + 60
        # Fixed service-only log predicate, no arbitrary system log/environment dump.
        log_row, _ = probe('coresimulator-log', ['/usr/bin/log', 'show', '--last', '10m', '--style', 'ndjson',
                          '--predicate', 'process == "CoreSimulatorService" AND (messageType == error OR messageType == fault)'], after_deadline)
        summary['observers'].append(log_row)
        summary['unavailableReadOnlyObservations'] = [
            r['label'] for r in [*context['probes'].values(), *summary['observers']] if not observed(r)]
        summary['sourceAfter'] = source_snapshot('after', after_deadline)
        require(summary['sourceAfter'] == summary['sourceBefore'], 'SOURCE_CHANGED')
        rows = [*context['probes'].values(), *summary['observers'], row]
        require(all(r['ownedGroupDrained'] and r['capturesClosed'] for r in rows), 'RETIREMENT_UNKNOWN')
        code = 0 if observed(row) else 1
    except Exception as error:
        # No arbitrary exception/argv/stream or private path in public output.
        summary['error'] = (str(error) if type(error) is RuntimeError and
                            re.fullmatch('[A-Z_]{1,64}', str(error)) else type(error).__name__)
    finally:
        try:
            write(OUTPUT / 'summary.json', summary)
        finally:
            for sig, handler in handlers.items():
                signal.signal(sig, handler)
    print('INTEL_INVENTORY_DIAGNOSTIC ' + ('OBSERVED' if code == 0 else 'NOT_OBSERVED') + ' NOT_QUALIFICATION')
    return code


if __name__ == '__main__':
    raise SystemExit(main())
