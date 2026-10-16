"""Pure canonical Python argv assembly, NOT admission or an execution entrypoint.

Both callers load this fixed sibling from captured, independently hash-bound
source bytes. Do not import a controller, open files, observe clocks, create
owners or consult ambient modules here. The canonical child still admits only
its original two suppliers; this helper is not a third child input.
"""

CANONICAL_NAMES = ("audit_processes.py", "run-audit-command.py")
CANONICAL_SOURCE_LIMIT = 512 * 1024
CANONICAL_BOOTSTRAP = '''import hashlib, json, os, stat, sys, types
from pathlib import Path
def require(value):
    if not value:
        raise RuntimeError("CANONICAL_BOOTSTRAP_REFUSED")
require(sys.flags.isolated == 1 and sys.flags.no_site == 1 and sys.dont_write_bytecode)
require(len(sys.argv) >= 4 and "audit_processes" not in sys.modules)
directory = Path(sys.argv[1])
require(directory.is_absolute() and ".." not in directory.parts and directory.name == "scripts")
for path in (directory, *directory.parents):
    info = path.lstat()
    require(not stat.S_ISLNK(info.st_mode) and not getattr(info, "st_file_attributes", 0) & 0x400)
bindings = json.loads(sys.argv[2])
names = ("audit_processes.py", "run-audit-command.py")
require(type(bindings) is dict and set(bindings) == set(names))
source = {}
for name in names:
    path = directory / name
    before = path.lstat()
    require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and
            not getattr(before, "st_file_attributes", 0) & 0x400 and 0 < before.st_size <= 512 * 1024)
    with path.open("rb") as stream:
        opened = os.fstat(stream.fileno())
        require(os.path.samestat(before, opened))
        raw = stream.read(512 * 1024 + 1)
        after = os.fstat(stream.fileno())
    current = path.lstat()
    require(os.path.samestat(before, after) and os.path.samestat(before, current) and
            before.st_mtime_ns == after.st_mtime_ns == current.st_mtime_ns and
            before.st_size == after.st_size == current.st_size == len(raw) and
            type(bindings[name]) is str and hashlib.sha256(raw).hexdigest() == bindings[name])
    source[name] = compile(raw, str(path), "exec", dont_inherit=True)
# Execute precisely the admitted bytes, not a second path read after hashing.
# Preloading this closed sibling preserves -I without changing sys.path.
module = types.ModuleType("audit_processes")
module.__file__, module.__package__, module.__spec__ = str(directory / names[0]), None, None
sys.modules["audit_processes"] = module
exec(source[names[0]], module.__dict__)
sys.argv = [str(directory / names[1]), *sys.argv[3:]]
main = types.ModuleType("__main__")
main.__file__, main.__package__, main.__spec__, main.__cached__ = sys.argv[0], None, None, None
sys.modules["__main__"] = main
exec(source[names[1]], main.__dict__)
'''


def assemble(executable, directory, bindings_json, *args):
    """Assemble already-validated caller data; no authority or command execution."""
    return [executable, "-I", "-B", "-S", "-c", CANONICAL_BOOTSTRAP, directory,
            bindings_json, *map(str, args)]
