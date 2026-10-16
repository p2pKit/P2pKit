"""Native Mac generator prerequisites, never phone telemetry or physical LAN proof.

No Linux counters are fabricated on Darwin. Use a real kqueue periodic timer,
native sysctl hardware observations and bounded vm_stat page counts. The same
125-second / <100ms-gap / >=6GiB thresholds apply; virtual/unknown hosts are refused.
"""
from __future__ import annotations

import argparse
import ctypes
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import select
import stat
import sys
import time

import rpc_mobile_capacity as protocol
import rpc_mobile_usb as usb

need = protocol.need
ROOT = Path(__file__).resolve().parents[1]
SCOPE = 'DARWIN_KQUEUE_GENERATOR_CLOCK_PREFLIGHT_NOT_MOBILE_OR_CAPACITY'
PERIOD = 10_000_000
DURATION = 125_000_000_000
MIN_MEMORY = 6 * 1024 ** 3


def sysctl(name):
    need(name in ('hw.memsize', 'hw.pagesize', 'hw.logicalcpu', 'hw.model', 'kern.hv_vmm_present'))
    system = ctypes.CDLL('/usr/lib/libSystem.B.dylib', use_errno=True)
    function = system.sysctlbyname
    function.argtypes = [ctypes.c_char_p, ctypes.c_void_p, ctypes.POINTER(ctypes.c_size_t), ctypes.c_void_p, ctypes.c_size_t]
    function.restype = ctypes.c_int
    data, size = ctypes.create_string_buffer(128), ctypes.c_size_t(128)
    need(function(name.encode('ascii'), data, ctypes.byref(size), None, 0) == 0 and 0 < size.value <= 128,
         'Missing/invalid native hardware observation is not a physical-host admission')
    raw = data.raw[:size.value]
    if name == 'hw.model':
        need(raw.endswith(b'\0'))
        return raw[:-1].decode('ascii')
    need(size.value in (4, 8))
    return int.from_bytes(raw, 'little')


def native_hardware(query=sysctl):
    values = {key: query(key) for key in ('hw.memsize', 'hw.pagesize', 'hw.logicalcpu', 'hw.model', 'kern.hv_vmm_present')}
    need(type(values['hw.model']) is str and re.fullmatch('Mac[0-9]+,[0-9]+', values['hw.model']) and
         type(values['kern.hv_vmm_present']) is int and values['kern.hv_vmm_present'] == 0,
         'Only the observed nonvirtual native Mac is admitted; no assumed zero balloon counter')
    need(all(type(values[k]) is int for k in ('hw.memsize', 'hw.pagesize', 'hw.logicalcpu')) and
         values['hw.memsize'] > 0 and values['hw.pagesize'] in (4096, 16384) and 1 <= values['hw.logicalcpu'] <= 4096)
    return dict(memoryBytes=values['hw.memsize'], pageBytes=values['hw.pagesize'], logicalCpus=values['hw.logicalcpu'],
                nativeMacModelObserved=True, hypervisorPresent=False)


def snapshot(commands):
    hardware = native_hardware()
    tool = Path('/usr/bin/vm_stat')
    info = tool.lstat()
    need(stat.S_ISREG(info.st_mode) and info.st_uid == 0 and not info.st_mode & (stat.S_ISUID | stat.S_ISGID) and
         not stat.S_IMODE(info.st_mode) & 0o022, 'Only the nonprivileged installed page observer is admitted')
    _, raw = commands.run('mac-generator-pages', [str(tool)], timeout=2)
    text = raw.decode('ascii')
    need(re.findall(r'page size of ([0-9]+) bytes', text) == [str(hardware['pageBytes'])])
    available = protocol.parse_vm_stat(text, hardware['memoryBytes'])
    return hardware | dict(availableBytes=available, memorySource='vm-stat-free-inactive-speculative')


def check_snapshot(value):
    need(type(value) is dict and set(value) == {'memoryBytes', 'pageBytes', 'logicalCpus', 'nativeMacModelObserved',
                                               'hypervisorPresent', 'availableBytes', 'memorySource'})
    need(value['nativeMacModelObserved'] is True and value['hypervisorPresent'] is False and
         value['memorySource'] == 'vm-stat-free-inactive-speculative' and
         all(type(value[k]) is int for k in ('memoryBytes', 'pageBytes', 'logicalCpus', 'availableBytes')) and
         0 <= value['availableBytes'] <= value['memoryBytes'] and value['memoryBytes'] > 0 and
         value['pageBytes'] in (4096, 16384) and 1 <= value['logicalCpus'] <= 4096)


class Timer:
    def __enter__(self):
        self.queue = select.kqueue()
        try:
            self.queue.control([select.kevent(1, filter=select.KQ_FILTER_TIMER,
                flags=select.KQ_EV_ADD | select.KQ_EV_ENABLE, data=10)], 0, 0)
        except BaseException:
            self.queue.close()
            raise
        return self

    def read(self, timeout):
        events = self.queue.control(None, 1, timeout)
        if not events:
            return None
        need(len(events) == 1 and events[0].ident == 1 and events[0].filter == select.KQ_FILTER_TIMER and
             not events[0].flags & (select.KQ_EV_ERROR | select.KQ_EV_EOF) and
             type(events[0].data) is int and 0 < events[0].data <= 1_000_000, 'Unproven kernel timer expiration')
        return events[0].data

    def __exit__(self, *_args):
        self.queue.close()


def clock(commands, *, now=time.monotonic_ns, timer=Timer, observe=snapshot):
    first = observe(commands)
    check_snapshot(first)
    samples = [dict(elapsedNanos=0, snapshot=first)]
    reads = expirations = maximum_gap = 0
    with timer() as source:
        started = previous = now()
        while True:
            count = source.read(.5)
            current = now()
            need(current >= previous, 'Monotonic clock regressed')
            maximum_gap = max(maximum_gap, current - previous)
            if count is not None:
                need(type(count) is int and count > 0)
                reads += 1
                expirations += count
                previous = current
            elapsed = current - started
            if elapsed >= samples[-1]['elapsedNanos'] + 1_000_000_000 or elapsed >= DURATION:
                samples.append(dict(elapsedNanos=elapsed, snapshot=observe(commands)))
                # The final observation has no following timer read to expose
                # its cost. Include it explicitly; a slow last vm_stat must not
                # disappear from the original <100ms scheduling-gap requirement.
                observed_at = now()
                need(observed_at >= current, 'Monotonic observer clock regressed')
                maximum_gap = max(maximum_gap, observed_at - previous)
            need(len(samples) <= 127, 'Unbounded clock observer')
            if elapsed >= DURATION:
                break
    value = dict(schema=1, scope=SCOPE, periodNanos=PERIOD, durationNanos=elapsed,
        kernelExpirations=expirations, userspaceReads=reads, coalescedExpirations=expirations - reads,
        maximumGapNanos=maximum_gap, minimumAvailableBytes=min(r['snapshot']['availableBytes'] for r in samples),
        samples=samples, healthyForAttempt=maximum_gap < 100_000_000 and
        min(r['snapshot']['availableBytes'] for r in samples) >= MIN_MEMORY, capacityQualified=False)
    return assess_clock(value)


def assess_clock(value):
    expected = {'schema', 'scope', 'periodNanos', 'durationNanos', 'kernelExpirations', 'userspaceReads',
                'coalescedExpirations', 'maximumGapNanos', 'minimumAvailableBytes', 'samples', 'healthyForAttempt', 'capacityQualified'}
    need(type(value) is dict and set(value) == expected and type(value['schema']) is int and value['schema'] == 1 and
         value['scope'] == SCOPE and value['capacityQualified'] is False)
    for key in expected - {'scope', 'samples', 'healthyForAttempt', 'capacityQualified'}:
        need(type(value[key]) is int and 0 <= value[key] < 2 ** 63)
    need(value['periodNanos'] == PERIOD and value['durationNanos'] >= DURATION and
         value['kernelExpirations'] >= 12500 and value['userspaceReads'] > 0 and
         value['kernelExpirations'] == value['userspaceReads'] + value['coalescedExpirations'])
    rows = value['samples']
    need(type(rows) is list and 2 <= len(rows) <= 127)
    for row in rows:
        need(type(row) is dict and set(row) == {'elapsedNanos', 'snapshot'} and
             type(row['elapsedNanos']) is int and 0 <= row['elapsedNanos'] <= value['durationNanos'])
        check_snapshot(row['snapshot'])
    need(rows[0]['elapsedNanos'] == 0 and rows[-1]['elapsedNanos'] == value['durationNanos'] and
         all(a['elapsedNanos'] < b['elapsedNanos'] for a, b in zip(rows, rows[1:])) and
         all({k: r['snapshot'][k] for k in ('memoryBytes', 'pageBytes', 'logicalCpus')} ==
             {k: rows[0]['snapshot'][k] for k in ('memoryBytes', 'pageBytes', 'logicalCpus')} for r in rows))
    minimum = min(r['snapshot']['availableBytes'] for r in rows)
    need(value['minimumAvailableBytes'] == minimum and value['healthyForAttempt'] is
         (value['maximumGapNanos'] < 100_000_000 and minimum >= MIN_MEMORY))
    return value


def direct_route(raw, interface_raw, config):
    need(type(raw) is bytes and type(interface_raw) is bytes and max(len(raw), len(interface_raw)) <= 65536)
    text, device = raw.decode('ascii'), interface_raw.decode('ascii')
    def field(name):
        rows = re.findall(r'(?m)^\s*' + re.escape(name) + r':\s*(\S+)\s*$', text)
        need(len(rows) == 1, 'Ambiguous/missing selected route field')
        return rows[0]
    need(re.fullmatch('en[0-9]{1,3}', config['interface']) and field('route to') == config['endpointAddress'] and
         field('interface') == config['interface'], 'Exact selected direct Mac interface and endpoint required')
    flags = field('flags')
    need(flags.startswith('<') and flags.endswith('>'))
    flags = set(flags[1:-1].split(','))
    need({'UP', 'DONE'} <= flags and not flags & {'GATEWAY', 'REJECT', 'BLACKHOLE', 'LOCAL', 'BROADCAST', 'MULTICAST'},
         'No gateway/tunnel/local substitute for the selected LAN path')
    headers = re.findall(r'(?m)^(en[0-9]+): flags=[0-9]+<([^>]+)>', device)
    need(len(headers) == 1 and headers[0][0] == config['interface'] and {'UP', 'RUNNING'} <= set(headers[0][1].split(',')))
    addresses = re.findall(r'(?m)^\s*inet ([0-9.]+)\s', device)
    need(addresses.count(config['localAddress']) == 1, 'Configured source address is not on the selected interface')
    return dict(selectedDirectRouteObserved=True, physicalLanProven=False,
                rawSha256=hashlib.sha256(raw).hexdigest(), interfaceSha256=hashlib.sha256(interface_raw).hexdigest())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, required=True)
    args = parser.parse_args()
    from audit_processes import host_role
    need(host_role() == 'macos-arm64' and os.environ.get('P2PKIT_AUDIT_OWNERSHIP_CHAIN'), 'Admitted native ARM command required')
    spec = importlib.util.spec_from_file_location('darwin_clock_files', ROOT / 'scripts/run-rpc-capacity-lab.py')
    files = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(files)
    state, _ = files.owned_context()
    need(args.directory.parent == state / 'work' and re.fullmatch('mobile-clock-[a-z0-9-]{1,48}', args.directory.name))
    args.directory.mkdir(mode=0o700)
    commands = usb.Commands(args.directory, os.environ, files)
    print(json.dumps(clock(commands), sort_keys=True))


if __name__ == '__main__':
    main()
