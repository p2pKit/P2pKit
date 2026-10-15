"""Exact native Apple lane binding for disposable test-environment preparation.

This is not product ownership admission. The unchanged native executor, original
platform inventories and architecture-specific cleanup gates still have to run.
"""
from __future__ import annotations

import platform

from audit_processes import host_role

HOSTS = {
    'apple-x64': ('x86_64', 'macos-x64'),
    'apple-arm64': ('arm64', 'macos-arm64'),
}


def selected_lane(env):
    lane = env.get('RPC_APPLE_LANE')
    if type(lane) is not str or lane not in HOSTS:
        raise RuntimeError('Explicit supported Apple lane required')
    return lane


def native_lane(env):
    lane = selected_lane(env)
    machine, role = HOSTS[lane]
    if platform.system() != 'Darwin' or platform.machine() != machine or host_role() != role:
        raise RuntimeError('Selected Apple lane does not match the actual native process')
    return lane


def proof_lane(value, expected=None):
    if type(value) is not str or value not in HOSTS or expected is not None and value != expected:
        raise RuntimeError('Apple environment proof belongs to a different native lane')
    return value
