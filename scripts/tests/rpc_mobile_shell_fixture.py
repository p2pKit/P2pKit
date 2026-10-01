"""POSIX file primitives with explicit fake Android tools; never Android/runtime qualification."""
import os
from pathlib import Path
import shlex
import shutil
import sys


def install(root):
    """Model API24's missing stat -L, while all metadata comes from actual fixture inodes."""
    root = Path(root)
    tools = root / 'fixture-tools'
    tools.mkdir(mode=0o700)
    stat = shutil.which('stat')
    if stat is None:
        raise RuntimeError('The offline POSIX stat fixture requires installed stat')
    programs = {
        'stat': f'''#!{sys.executable}
import os, sys
if any(value.startswith('-') and 'L' in value for value in sys.argv[1:]):
    print("stat: Unknown option 'L'", file=sys.stderr)
    raise SystemExit(1)
os.execv({stat!r}, [{stat!r}, *sys.argv[1:]])
''',
        'app_process': f'''#!{sys.executable}
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
