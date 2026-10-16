#!/usr/bin/env python3
"""Finalize a NEW development-ad-hoc Desktop app copy; never publish, install, or replace vendor signatures."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import plistlib
import re
import shutil
import stat
import struct
import subprocess
import selectors
import time
import zipfile

POLICY = 'development-adhoc-v1'
PROPERTY = 'dev.p2pkit.lan.macos.installedPolicy'
RESOURCE = 'META-INF/p2pkit/macos-tcp.properties'
NATIVE = 'Contents/app/resources/p2pkit-native/macos-arm64'
LIBRARY = 'libp2pkit_lan_socket.dylib'
MAX_TOOL_OUTPUT = 65536


def require(value, message):
    if not value:
        raise ValueError(message)


def tool(arguments, check=True):
    # Fixed tools, nonblocking owned pipe, bounded output and deadline; never signal unrelated descendants.
    require(arguments[0] in ('/usr/bin/codesign', '/usr/bin/git', '/bin/ls'), 'Unapproved tool')
    process = subprocess.Popen(arguments, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, bufsize=0,
                               stderr=subprocess.STDOUT, env={'PATH': '/usr/bin:/bin', 'LC_ALL': 'C'})
    return collect_tool(process, check=check)


def collect_tool(process, check=True, timeout=30):
    # A descendant-held pipe cannot keep a blocking reader or close operation alive: there is no reader thread.
    selector = None
    primary = None
    cleanup_errors = []
    try:
        os.set_blocking(process.stdout.fileno(), False)
        selector = selectors.DefaultSelector()
        selector.register(process.stdout, selectors.EVENT_READ)
        deadline, data, eof = time.monotonic() + timeout, bytearray(), False
        while not eof or process.poll() is None:
            left = deadline - time.monotonic()
            require(left > 0, 'Tool timed out or output EOF remains unproven')
            for key, _mask in selector.select(min(left, 0.1)):
                chunk = os.read(key.fd, min(4096, MAX_TOOL_OUTPUT + 1 - len(data)))
                if chunk:
                    data.extend(chunk)
                    require(len(data) <= MAX_TOOL_OUTPUT, 'Tool output exceeds bound')
                else:
                    eof = True
                    selector.unregister(process.stdout)
        code = process.wait(timeout=max(0.001, deadline - time.monotonic()))
        text = data.decode('utf-8', errors='strict')
        require(not check or code == 0, 'Tool rejected with exit code ' + str(code))
        return code, text
    except BaseException as error:
        primary = error
        raise
    finally:
        def cleanup(action):
            try:
                action()
            except BaseException as error:
                cleanup_errors.append(error)
        cleanup(lambda: process.kill() if process.poll() is None else None)
        cleanup(lambda: process.wait(timeout=5))
        if selector is not None:
            cleanup(selector.close)
        cleanup(process.stdout.close)
        if cleanup_errors:
            if primary is not None:
                for error in cleanup_errors:
                    if hasattr(primary, 'add_note'):
                        primary.add_note('Owned tool cleanup failed: ' + type(error).__name__)
                    else:
                        primary.__context__ = error
            else:
                raise RuntimeError('Owned tool cleanup failed') from cleanup_errors[0]


def ad_hoc(metadata):
    fields = [line.split('=', 1) for line in metadata.splitlines() if '=' in line]
    require([value for key, value in fields if key == 'Signature'] == ['adhoc'], 'Not an ad-hoc signature')
    require([value for key, value in fields if key == 'TeamIdentifier'] == ['not set'], 'Unexpected signing team')
    flags = re.findall(r'^CodeDirectory .* flags=0x([0-9a-fA-F]+)(?:\([^\r\n]*\))? ', metadata, re.MULTILINE)
    require(len(flags) == 1 and int(flags[0], 16) & 2, 'Missing ad-hoc CodeDirectory flag')


def signature(path, allow_unsigned=False, require_adhoc=False):
    code, display = tool(['/usr/bin/codesign', '--display', '--verbose=4', str(path)], check=False)
    if code != 0:
        require(allow_unsigned and code == 1 and display.rstrip().endswith('code object is not signed at all'),
                'Missing/invalid/unknown signature')
        return 'unsigned'
    tool(['/usr/bin/codesign', '--verify', '--strict', '--deep', '--all-architectures', str(path)])
    if require_adhoc:
        ad_hoc(display)
    return 'verified'


def canonical(path):
    require(path.is_absolute() and path == Path(os.path.normpath(path)) and
            path == path.resolve(strict=True) and not any(ord(c) < 32 or ord(c) == 127 for c in str(path)),
            'Path must be absolute, canonical and free of control characters')
    return path


def regular(path):
    mode = path.lstat()
    require(stat.S_ISREG(mode.st_mode) and mode.st_nlink == 1 and mode.st_uid in (0, os.getuid()) and
            mode.st_mode & 0o7022 == 0, 'Unsafe file: ' + path.name)


def bounded_read(path, maximum):
    regular(path)
    before = path.lstat()
    require(0 < before.st_size <= maximum, 'File exceeds size bound: ' + path.name)
    with path.open('rb') as file:
        opened = os.fstat(file.fileno())
        require((before.st_dev, before.st_ino, before.st_size) ==
                (opened.st_dev, opened.st_ino, opened.st_size), 'File changed before read')
        data = file.read(maximum + 1)
        after = os.fstat(file.fileno())
        require((opened.st_dev, opened.st_ino, opened.st_size, opened.st_mtime_ns) ==
                (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns) and len(data) == before.st_size,
                'File changed during read')
    require(len(data) <= maximum, 'Read exceeds size bound')
    return data


def manifest(stage, source, tree):
    for name in ('macos-tcp.properties', LIBRARY, 'p2pkit-macos-tcp-manifest.jar'):
        regular(stage / name)
    raw = bounded_read(stage / 'macos-tcp.properties', 4096)
    require(0 < len(raw) <= 4096 and raw.endswith(b'\n'), 'Invalid manifest size/termination')
    entries = [line.split('=') for line in raw.decode('ascii')[:-1].split('\n')]
    require(all(len(row) == 2 for row in entries) and len({row[0] for row in entries}) == len(entries),
            'Invalid/duplicate manifest entries')
    values = dict(entries)
    require(set(values) == {'abi', 'platform', 'arch', 'source', 'tree', 'file', 'bytes', 'sha256'},
            'Unexpected manifest keys')
    require(values['abi'] == '1' and values['platform'] == 'macos' and values['arch'] == 'arm64' and
            values['source'] == source and values['tree'] == tree and values['file'] == LIBRARY and
            re.fullmatch('[a-f0-9]{40}', source) and re.fullmatch('[a-f0-9]{40}', tree), 'Wrong source/platform')
    data = bounded_read(stage / LIBRARY, 4194304)
    require(32 <= len(data) <= 4194304 and str(len(data)) == values['bytes'] and
            hashlib.sha256(data).hexdigest() == values['sha256'], 'Native bytes do not match manifest')
    magic, cpu, _subtype, kind = struct.unpack('<IIII', data[:16])
    require(magic == 0xfeedfacf and cpu == 0x0100000c and kind == 6, 'Not an ARM64 Mach-O dylib')
    with zipfile.ZipFile(stage / 'p2pkit-macos-tcp-manifest.jar') as jar:
        require(jar.namelist() == [RESOURCE] and jar.getinfo(RESOURCE).file_size <= 4096 and jar.read(RESOURCE) == raw, 'Producer JAR differs from manifest')
    signature(stage / LIBRARY, require_adhoc=True)
    return raw, values


def launcher_classpath(app):
    info = plistlib.loads(bounded_read(app / 'Contents/Info.plist', 65536))
    executable = info.get('CFBundleExecutable')
    require(isinstance(executable, str) and re.fullmatch(r'[A-Za-z0-9_. -]+', executable) and
            executable not in ('.', '..'), 'Invalid launcher name')
    regular(app / 'Contents/MacOS' / executable)
    cfg = app / 'Contents/app' / (executable + '.cfg')
    regular(cfg)
    require(cfg.stat().st_size <= 65536, 'Launcher configuration exceeds limit')
    section, fields = None, []
    for line in bounded_read(cfg, 65536).decode('utf-8').splitlines():
        if line.startswith('[') and line.endswith(']'):
            section = line[1:-1]
        elif line and not line.startswith('#'):
            key, sep, value = line.partition('=')
            require(bool(sep), 'Malformed launcher configuration')
            fields.append((section, key, value))
    options = [value for section, key, value in fields if section == 'JavaOptions' and key == 'java-options']
    policy_options = [value for value in options if value.startswith('-D' + PROPERTY)]
    require(policy_options == ['-D' + PROPERTY + '=' + POLICY], 'Launcher must select the one installed policy')
    require(not any(value.startswith('-Ddev.p2pkit.lan.macos.nativeDir') for value in options),
            'Private native location must not be packaged')
    require(not any(value.startswith(('-javaagent', '-agentlib', '-agentpath', '-Djava.system.class.loader',
                                      '-Xbootclasspath', '--patch-module')) for value in options),
            'Unsupported alternate code authority')
    classpath = [value for section, key, value in fields if section == 'Application' and key == 'app.classpath']
    require(bool(classpath), 'Expected explicit launcher classpath')
    jars = []
    for item in [part for value in classpath for part in value.split(':')]:
        require(item.startswith('$APPDIR/') and '/' not in item[len('$APPDIR/'):] and item.endswith('.jar'),
                'Launcher classpath must contain explicit in-bundle JARs')
        jar = app / 'Contents/app' / item[len('$APPDIR/'):]
        regular(jar)
        require(jar not in jars, 'Duplicate classpath JAR')
        jars.append(jar)
    require(bool(jars), 'Empty launcher classpath')
    return executable, jars


def classpath_authority(app, expected):
    executable, jars = launcher_classpath(app)
    authorities, implementations = [], []
    for path in jars:
        with zipfile.ZipFile(path) as jar:
            names = jar.namelist()
            if RESOURCE in names:
                require(names.count(RESOURCE) == 1 and jar.getinfo(RESOURCE).file_size <= 4096 and
                        jar.read(RESOURCE) == expected, 'Classpath native authority mismatch')
                authorities.append(path.name)
            if 'dev/p2pkit/transport/lan/MacLanNativeLoader.class' in names:
                implementations.append(path.name)
    require(len(authorities) == 1 and len(implementations) == 1, 'Expected one manifest and one transport implementation')
    return executable, authorities[0], implementations[0]


def inventory(app):
    result = {}
    for path in sorted(app.rglob('*')):
        relative = path.relative_to(app).as_posix()
        if path.is_symlink():
            target = os.readlink(path)
            require(path.resolve(strict=True).is_relative_to(app), 'External bundle symlink')
            result[relative] = {'link': target}
        elif path.is_file():
            result[relative] = {'bytes': path.stat().st_size, 'sha256': sha256(path)}
        elif path.is_dir():
            result[relative] = {'directory': True}
        else:
            raise ValueError('Unsupported bundle object')
    return result


def sha256(path):
    digest = hashlib.sha256()
    with path.open('rb') as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def finalize(input_app, output_app, stage, source, tree):
    require(platform.system() == 'Darwin' and platform.machine() == 'arm64', 'Mac ARM64 required')
    canonical(input_app)
    canonical(stage)
    require(input_app.suffix == '.app' and output_app.name == input_app.name, 'Preserve application name')
    require(not output_app.exists() and not output_app.is_symlink() and output_app.parent.is_dir() and
            output_app.parent.resolve(strict=True) == output_app.parent and
            not output_app.is_relative_to(input_app), 'Output must be a new sibling-owned app image')
    require(output_app.parent.stat().st_uid == os.getuid() and output_app.parent.stat().st_mode & 0o022 == 0,
            'Output parent must be privately writable by this user only')
    raw, values = manifest(stage, source, tree)
    before = inventory(input_app)
    executable, authority_jar, implementation_jar = classpath_authority(input_app, raw)
    input_signature = signature(input_app, allow_unsigned=True, require_adhoc=True)
    # Verify all existing nested native bytes without replacing vendor signatures. Only the app launcher is signed.
    for path in sorted(input_app.rglob('*')):
        if not path.is_file() or path.is_symlink() or path == input_app / 'Contents/MacOS' / executable:
            continue
        with path.open('rb') as file:
            magic = file.read(4)
        if magic in (b'\xcf\xfa\xed\xfe', b'\xce\xfa\xed\xfe', b'\xfe\xed\xfa\xcf',
                     b'\xfe\xed\xfa\xce', b'\xca\xfe\xba\xbe', b'\xbe\xba\xfe\xca'):
            signature(path)
    shutil.copytree(input_app, output_app, symlinks=True, copy_function=shutil.copy2)
    native = output_app / NATIVE
    require(not native.exists(), 'Input already contains native stage; refusing replacement')
    native.mkdir(parents=True, mode=0o755)
    for name in ('macos-tcp.properties', LIBRARY):
        shutil.copyfile(stage / name, native / name)
        os.chmod(native / name, 0o644)
    # Producer signed the inner dylib BEFORE its pinned manifest. Never change those signed bytes here.
    signature(native / LIBRARY, require_adhoc=True)
    tool(['/usr/bin/codesign', '--force', '--sign', '-', '--timestamp=none', str(output_app)])
    signature(output_app, require_adhoc=True)
    signature(native / LIBRARY, require_adhoc=True)
    require((native / LIBRARY).stat().st_size == int(values['bytes']) and sha256(native / LIBRARY) == values['sha256'],
            'Outer signing changed pinned native bytes')
    require((native / 'macos-tcp.properties').read_bytes() == raw, 'Outer signing changed manifest')
    require(classpath_authority(output_app, raw) == (executable, authority_jar, implementation_jar),
            'Final classpath authority changed')
    require(inventory(input_app) == before, 'Original app was changed')
    after = inventory(output_app)
    allowed = {'Contents/MacOS/' + executable}
    for name, entry in before.items():
        if name in allowed or name.startswith('Contents/_CodeSignature/'):
            continue
        require(after.get(name) == entry, 'Unrelated packaged input changed: ' + name)
    return {'schema': 1, 'scope': 'DEVELOPMENT_ADHOC_APP_IMAGE_NOT_PUBLICATION_NOT_NOTARIZATION',
            'policy': POLICY, 'nativeSource': source, 'nativeTree': tree, 'inputSignature': input_signature,
            'applicationSourceBinding': 'MUST_BE_VERIFIED_BY_EXISTING_APPLICATION_IDENTITY_PIPELINE',
            'inputUnchanged': True, 'pinnedNativeSha256': values['sha256'], 'manifestJar': authority_jar,
            'transportJar': implementation_jar, 'nativeLoaded': False, 'applicationLaunched': False,
            'appName': output_app.name, 'files': after}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--input-app', type=Path, required=True)
    parser.add_argument('--output-app', type=Path, required=True)
    parser.add_argument('--native-stage', type=Path, required=True)
    parser.add_argument('--receipt', type=Path, required=True)
    parser.add_argument('--policy', choices=[POLICY], required=True)
    args = parser.parse_args()
    root = canonical(args.root)
    require(not args.receipt.exists() and args.receipt.parent.is_dir(), 'Receipt must be new')
    source = tool(['/usr/bin/git', '-C', str(root), 'rev-parse', 'HEAD'])[1].strip()
    tree = tool(['/usr/bin/git', '-C', str(root), 'rev-parse', 'HEAD^{tree}'])[1].strip()
    require(not tool(['/usr/bin/git', '-C', str(root), 'status', '--porcelain', '--untracked-files=all'])[1],
            'Clean source required')
    result = finalize(args.input_app, args.output_app, args.native_stage, source, tree)
    require(tool(['/usr/bin/git', '-C', str(root), 'rev-parse', 'HEAD'])[1].strip() == source and
            not tool(['/usr/bin/git', '-C', str(root), 'status', '--porcelain', '--untracked-files=all'])[1],
            'Source changed during staging')
    with args.receipt.open('x') as file:
        json.dump(result, file, indent=2, sort_keys=True)
        file.write('\n')
    print(json.dumps({key: value for key, value in result.items() if key != 'files'}, sort_keys=True))


if __name__ == '__main__':
    main()
