"""POSIX file primitives with explicit fake Android tools; never Android/runtime qualification."""
import os
from pathlib import Path
import shlex
import shutil
import sys


def install(root, *, supports_dereference=False):
    """Model API24's missing stat -L, while all metadata comes from actual fixture inodes."""
    if type(supports_dereference) is not bool:
        raise TypeError('The offline stat capability must be explicit')
    root = Path(root)
    native_stat = shutil.which('stat')
    if native_stat is None or sys.platform not in ('darwin', 'linux'):
        raise RuntimeError('The fixture requires the host BSD or GNU stat')
    tools = root / 'fixture-tools'
    tools.mkdir(mode=0o700)
    # Keep the original five-second shell bound. Starting a Python interpreter
    # for every pathname query can itself consume that budget on macOS. Only
    # the modeled Android FD helper needs Python; pathname metadata uses the
    # installed host stat with an explicit BSD/GNU format translation.
    formats = {'%u': '%u', '%a': '%Lp', '%h': '%l', '%s': '%z', '%f': '%Xp',
               '%d:%i': '%d:%i', '%d:%i:%s:%Y:%a:%u:%h': '%d:%i:%z:%m:%Lp:%u:%l'}
    cases = '\n'.join(f'    {shlex.quote(key)}) format={shlex.quote(value if sys.platform == "darwin" else key)};;'
                      for key, value in formats.items())
    stat_option = '-f' if sys.platform == 'darwin' else '-c'
    programs = {
        'stat': f'''#!/bin/sh
set -eu
test "$#" -eq 3 || exit 2
case "$1" in
    -Lc)
        if {str(not supports_dereference).lower()}; then
            printf 'usage: stat [-f] [-c FORMAT] FILE...\\n\\nDisplay status of files or filesystems.\\n\\nstat: Unknown option Lc\\n' >&2
            exit 1
        fi;;
    -c) ;;
    *) exit 2;;
esac
# The positive capability control uses the actual inherited /dev/null FD on
# both kernels; Darwin has no Linux /proc path. No pathname is reopened here.
if test "$1" = -Lc && test "$2" = %f && test "$3" = /proc/self/fd/5; then
    exec {shlex.quote(sys.executable)} -I -S -c 'import os; print(format(os.fstat(5).st_mode, "x"))'
fi
case "$2" in
{cases}
    *) exit 2;;
esac
if test "$1" = -Lc; then
    exec {shlex.quote(native_stat)} -L {stat_option} "$format" "$3"
fi
exec {shlex.quote(native_stat)} {stat_option} "$format" "$3"
''',
        'app_process': f'''#!{sys.executable} -S
import os, stat, sys
if len(sys.argv) != 4 or sys.argv[1:3] != ['/system/bin', 'dev.p2pkit.sample.android.rpclab.RpcLabFdStat']:
    raise SystemExit(2)
if sys.argv[3] not in ('identity', 'record'):
    raise SystemExit(2)
s = os.fstat(5)
if not stat.S_ISREG(s.st_mode):
    raise SystemExit(1)
fields = [str(s.st_dev), str(s.st_ino)]
if sys.argv[3] == 'record':
    fields += [str(s.st_size), str(int(s.st_mtime)), format(stat.S_IMODE(s.st_mode), 'o'), str(s.st_uid), str(s.st_nlink)]
print(':'.join(fields))
''',
    }
    for name, text in programs.items():
        path = tools / name
        with path.open('x') as stream:
            stream.write(text)
        path.chmod(0o700)
    apk = root / 'fixture.apk'
    with apk.open('xb') as stream:
        stream.write(b'NOT_AN_APK_OR_RUNTIME')
    return dict(os.environ, PATH=str(tools) + os.pathsep + os.environ.get('PATH', ''), CLASSPATH=str(apk))


def script(raw, environment):
    """Only the fixed native metadata tool is simulated, not its inode data or shell security checks."""
    executable = Path(environment['CLASSPATH']).parent / 'fixture-tools/app_process'
    return raw.replace('/system/bin/app_process', shlex.quote(str(executable)))
