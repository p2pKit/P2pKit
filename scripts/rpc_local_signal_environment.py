"""Prepare signal inheritance in one fresh, unprivileged, single-threaded process.

GUI authorization helpers need not inherit a Terminal's signal mask. A blocked
SIGTERM can be accepted by the kernel without reaching a cancellation handler.
Record the incoming state before restoring ordinary child-process semantics.
This changes no other process, audit policy, ownership rule or test deadline.
"""
from __future__ import annotations

import os
import signal
import threading

SCOPE = 'FRESH_PROCESS_SIGNAL_ENVIRONMENT_NOT_NATIVE_ADMISSION'


def need(condition, message):
    if not condition:
        raise RuntimeError(message)


def disposition(number):
    value = signal.getsignal(number)
    if value == signal.SIG_DFL:
        return 'DEFAULT'
    if value == signal.SIG_IGN:
        return 'IGNORE'
    if number == signal.SIGINT and value is signal.default_int_handler:
        return 'PYTHON_DEFAULT_INTERRUPT'
    return 'CUSTOM'


def observe():
    return dict(blockedSignals=sorted(map(int, signal.pthread_sigmask(signal.SIG_BLOCK, []))),
        pendingSignals=sorted(map(int, signal.sigpending())),
        dispositions={name: disposition(getattr(signal, name)) for name in ('SIGINT', 'SIGTERM')})


def normalize(retain_before):
    need(os.getuid() == os.geteuid() and os.getuid() > 0, 'Signal preparation must run after privilege drop')
    need(threading.current_thread() is threading.main_thread() and threading.active_count() == 1,
         'Signal preparation requires a fresh single main thread, before native workers')
    before = observe()
    retain_before(before)  # Create-only evidence first; failure must not alter even this process.
    need(not before['pendingSignals'], 'Pending signals cannot be discarded or repurposed as fresh admission')
    need('CUSTOM' not in before['dispositions'].values(), 'Existing custom cancellation handler cannot be replaced')
    signal.signal(signal.SIGINT, signal.default_int_handler)
    signal.signal(signal.SIGTERM, signal.SIG_DFL)
    previous = signal.pthread_sigmask(signal.SIG_SETMASK, [])
    need(sorted(map(int, previous)) == before['blockedSignals'], 'Signal mask changed during fresh-process preparation')
    after = observe()
    need(not after['blockedSignals'] and not after['pendingSignals'] and
         after['dispositions'] == dict(SIGINT='PYTHON_DEFAULT_INTERRUPT', SIGTERM='DEFAULT'),
         'Ordinary process-local signal environment was not restored')
    return dict(schema=1, scope=SCOPE, before=before, after=after,
        maskChanged=bool(before['blockedSignals']), processLocalOnly=True, nativeAdmission=False)
