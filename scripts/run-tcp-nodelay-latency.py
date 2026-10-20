#!/usr/bin/env python3
"""Bounded source-bound TCP option microbenchmark; never full interoperability acceptance."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import statistics
import subprocess

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = 'scripts/diagnostics/TcpNoDelayLatency.java'
SOURCES = [FIXTURE, 'scripts/run-tcp-nodelay-latency.py',
    'library/p2p-transport-lan/src/jvmMain/kotlin/dev/p2pkit/transport/lan/JvmLanDataTransport.kt',
    'library/p2p-transport-lan/src/androidMain/kotlin/dev/p2pkit/transport/lan/AndroidLanDataTransport.kt',
    'library/p2p-transport-lan/src/nativeInterop/cinterop/p2pkit_nw.h']


def summary(value):
    if type(value) is not dict or set(value) != {'schema', 'scope', 'warmup', 'samplesPerBlock', 'blocks'} or \
            value['schema'] != 1 or value['scope'] not in ('loopback-transport-only', 'explicit-peer-transport-only') or \
            value['warmup'] != 8 or value['samplesPerBlock'] != 32 or len(value['blocks']) != 8:
        raise ValueError('Incomplete measurement envelope')
    groups = {}
    for index, block in enumerate(value['blocks']):
        option = (False, True, True, False)[index % 4]
        shape = 'coalesced-40' if index < 4 else 'split-4-36'
        if set(block) != {'block', 'noDelay', 'acceptedNoDelay', 'writeShape', 'nanoseconds'} or \
                block['block'] != index or block['noDelay'] is not option or block['acceptedNoDelay'] is not option or \
                block['writeShape'] != shape or len(block['nanoseconds']) != 32 or \
                any(type(n) is not int or not 0 < n < 2_000_000_000 for n in block['nanoseconds']):
            raise ValueError('Invalid sample or socket option observation')
        groups.setdefault((shape, option), []).extend(block['nanoseconds'])
    rows = []
    for (shape, option), samples in groups.items():
        ordered = sorted(samples)
        rows.append({'writeShape': shape, 'noDelay': option, 'count': len(samples),
            'medianNanoseconds': statistics.median(samples), 'p95Nanoseconds': ordered[(95 * len(ordered) + 99) // 100 - 1],
            'minNanoseconds': min(samples), 'maxNanoseconds': max(samples)})
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--java', required=True, type=Path, help='Explicit JDK17 java executable')
    parser.add_argument('--output', required=True, type=Path, help='New private evidence directory outside source')
    parser.add_argument('--peer', help='Explicit authorized peer host, otherwise loopback diagnostics only')
    parser.add_argument('--port', type=int)
    args = parser.parse_args()
    if bool(args.peer) != (args.port is not None):
        parser.error('--peer and --port are required together')
    java = args.java.resolve(strict=True)
    output = args.output.absolute()
    if output == ROOT or ROOT in output.parents:
        parser.error('Evidence must be outside the source tree')
    output.mkdir(mode=0o700, parents=False, exist_ok=False)
    os.chmod(output, 0o700)
    sources = {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in SOURCES}
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    dirty = subprocess.check_output(['git', 'status', '--porcelain=v1', '--untracked-files=all'], cwd=ROOT, text=True)
    command = [str(java), str(ROOT / FIXTURE)] + (['measure', args.peer, str(args.port)] if args.peer else ['loopback'])
    report = {'schema': 1, 'sourceCommit': commit, 'sourceDirty': bool(dirty), 'sourceSha256': sources,
        'host': {'system': platform.system(), 'machine': platform.machine()},
        'javaExecutableSha256': hashlib.sha256(java.read_bytes()).hexdigest(),
        'scope': 'TCP socket-option synthetic PING/PONG microbenchmark; not authenticated P2pKit or independent interop',
        'baseline': 'Real sockets with TCP_NODELAY=false; option-only historical-policy control, not a historical product build',
        'limits': 'Loopback is not real LAN; explicit peer mode requires separately retained server/source/network evidence',
        'acceptance': 'NOT_ESTABLISHED', 'commandMode': 'explicit-peer' if args.peer else 'loopback'}
    try:
        version = subprocess.run([str(java), '-version'], stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            timeout=10, check=True)
        with (output / 'java-version.txt').open('xb') as stream:
            stream.write(version.stdout)
        report['javaVersionSha256'] = hashlib.sha256(version.stdout).hexdigest()
        with (output / 'stdout.json').open('xb') as stdout, (output / 'stderr.log').open('xb') as stderr:
            completed = subprocess.run(command, cwd=ROOT, stdout=stdout, stderr=stderr, timeout=120, check=False)
        report['exitCode'] = completed.returncode
        if completed.returncode:
            raise RuntimeError('Native measurement failed; originals retained')
        if (output / 'stderr.log').stat().st_size:
            raise RuntimeError('Unexpected measurement stderr')
        raw = (output / 'stdout.json').read_bytes()
        if len(raw) > 65536:
            raise ValueError('Oversized result')
        result = json.loads(raw)
        report['summary'] = summary(result)
        if any(hashlib.sha256((ROOT / n).read_bytes()).hexdigest() != h for n, h in sources.items()):
            raise RuntimeError('Bound source changed during measurement')
        report.update(status='MEASURED_TRANSPORT_ONLY', originalSha256=hashlib.sha256(raw).hexdigest())
    except BaseException as error:
        report.update(status='FAILED', error=type(error).__name__)
        raise
    finally:
        for name in ('stdout.json', 'stderr.log', 'java-version.txt'):
            if (output / name).exists():
                os.chmod(output / name, 0o600)
        with (output / 'report.json').open('x') as stream:
            json.dump(report, stream, indent=2); stream.write('\n')
        os.chmod(output / 'report.json', 0o600)
    print(json.dumps({'status': report['status'], 'summary': report['summary']}))


if __name__ == '__main__':
    main()
