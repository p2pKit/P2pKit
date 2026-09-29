"""Inert exact filename/diagnostic/clock inverses for historical source pins only.

Each inverse transforms the supplied CURRENT source, checks every reviewed hunk
and substitution count, then requires the independently retained original hash.
It never reads files, returns an embedded source substitute, or executes source.
Behavioral controls must import the current runtime, never these preimages.
"""
import hashlib

BASE_RUNTIME_SHA256 = "a3904f34c48f85d1e0b93b8a6f24f61423e9533030c9328c61916862c46b623d"
BASE_WORKFLOW_SHA256 = "c88c6e69c00c0a150e0eacefbfb54e7611ec9511112dbd02c303f8ad19d7aa40"
BASE_EXPERIMENT_TEST_SHA256 = "484c4ebdd20bf5500ad9ba340f552cc15088e0c02e74759805cf693cfe290768"

# The filename-only increment must recover the complete accepted 372bf615
# runtime before either historical runtime entrypoint applies its older inverse.
PLIST_NAME_BASE_RUNTIME_SHA256 = "c2726e3b3e43544f813f567f674473f52636fa165f70766a1f0f7cd1e18dc1bf"
PLIST_NAME_PATCH = (
    ('            exact.append(["/usr/bin/mktemp", self.root + "/job.XXXXXXXXXX"])\n',
     '            exact.append(["/usr/bin/mktemp", self.root + "/job.plist"])\n'),
    ('        raw = self._run(["/usr/bin/mktemp", self.root + "/job.XXXXXXXXXX"], "ADMIN_CREATE")["stdout"]\n',
     '        raw = self._run(["/usr/bin/mktemp", self.root + "/job.plist"], "ADMIN_CREATE")["stdout"]\n'),
    ('        require(re.fullmatch(re.escape(self.root.encode("ascii")) + rb"/job\\.[A-Za-z0-9]{10}\\n", raw),\n'
     '                "ADMIN_CREATE", "UNSUPPORTED")\n',
     '        require(raw == self.root.encode("ascii") + b"/job.plist\\n", "ADMIN_CREATE", "UNSUPPORTED")\n'),
)

# The diagnostic-only increment must first recover the complete accepted
# c61acffd runtime. The original clock hunks/counts/hashes below stay unchanged.
ADMIN_RETURN_BASE_RUNTIME_SHA256 = "5224a331a6570a913aa3c34ac1785d2ae744688fbfe9e4329ba587e36586ba1b"
ADMIN_RETURN_PATCH = (
    ('ADMIN_ITEMS = frozenset((*SOURCE_OS_ITEMS.values(), "PRIVATE_DIRECTORY", "PRIVATE_FILE"))\n',
     'ADMIN_ITEMS = frozenset((*SOURCE_OS_ITEMS.values(), "PRIVATE_DIRECTORY", "PRIVATE_FILE"))\n'
     'ADMIN_RETURN_SITES = frozenset(("BOOTSTRAP_PRECHECK_PRINT", "BOOTSTRAP_COMMAND",\n'
     '                                "INSPECT_RUNNING_PRINT", "INSPECT_STOPPED_PRINT"))\n'
     'ADMIN_RETURN_GUARDS = frozenset(("LEDGER_WRITE", "RETURN_CODE", "STDERR"))\n'),
    ('@contextlib.contextmanager\ndef at_stage(stage):\n',
     'def annotate_admin_return(error, return_site, case, result, *, ledger=False):\n'
     '    """Describe an already-failed guard using only held, bounded primitives."""\n'
     '    site = return_site if type(return_site) is str and return_site in ADMIN_RETURN_SITES else "UNKNOWN"\n'
     '    case = case if type(case) is str and case in CASES else "UNKNOWN"\n'
     '    code = result.get("code") if type(result) is dict else None\n'
     '    stderr = result.get("stderr") if type(result) is dict else None\n'
     '    code = code if type(code) is int and -127 <= code <= 255 else "UNKNOWN"\n'
     '    stderr = ("EMPTY" if len(stderr) == 0 else "NONEMPTY") if type(stderr) is bytes else "UNKNOWN"\n'
     '    guard = "UNKNOWN"\n'
     '    if ledger is True:\n'
     '        guard = "LEDGER_WRITE"\n'
     '    elif type(code) is int and code != 0:\n'
     '        guard = "RETURN_CODE"\n'
     '    elif type(code) is int and code == 0 and stderr == "NONEMPTY":\n'
     '        guard = "STDERR"\n'
     '    error.admin_return = (site, case, guard, code, stderr)\n'
     '\n\n'
     'def public_admin_return(error):\n'
     '    """Fixed failing-return facts only; neither an OS cause nor acceptance."""\n'
     '    if (not isinstance(error, ExperimentError) or type(error.stage) is not str or type(error.reason) is not str or\n'
     '            error.stage != "BOOTSTRAP" or error.reason != "RETURN_FAILED"):\n'
     '        return None\n'
     '    fields = getattr(error, "admin_return", None)\n'
     '    if type(fields) is not tuple or len(fields) != 5:\n'
     '        return None\n'
     '    site, case, guard, code, stderr = fields\n'
     '    site = site if type(site) is str and site in ADMIN_RETURN_SITES else "UNKNOWN"\n'
     '    case = case if type(case) is str and case in CASES else "UNKNOWN"\n'
     '    guard = guard if type(guard) is str and guard in ADMIN_RETURN_GUARDS else "UNKNOWN"\n'
     '    code = str(code) if type(code) is int and -127 <= code <= 255 else "UNKNOWN"\n'
     '    stderr = stderr if type(stderr) is str and stderr in ("EMPTY", "NONEMPTY", "UNKNOWN") else "UNKNOWN"\n'
     '    return "P2PKIT_CONTEXT_ADMIN_RETURN|" + "|".join((site, case, guard, code, stderr))\n'
     '\n\n'
     '@contextlib.contextmanager\ndef at_stage(stage):\n'),
    ('    def _run(self, argv, stage, *, input_raw=b"", success=True):\n',
     '    def _run(self, argv, stage, *, input_raw=b"", success=True, return_site=None):\n'),
    ('        require(self.record.write(raw) == len(raw), stage, "RETURN_FAILED")\n',
     '        try:\n'
     '            require(self.record.write(raw) == len(raw), stage, "RETURN_FAILED")\n'
     '        except ExperimentError as error:\n'
     '            annotate_admin_return(error, return_site, self.directory.name, result, ledger=True)\n'
     '            raise\n'),
    ('        if success:\n'
     '            require(result["code"] == 0 and result["stderr"] == b"", stage, "RETURN_FAILED")\n'
     '        return result\n',
     '        if success:\n'
     '            try:\n'
     '                require(result["code"] == 0 and result["stderr"] == b"", stage, "RETURN_FAILED")\n'
     '            except ExperimentError as error:\n'
     '                annotate_admin_return(error, return_site, self.directory.name, result)\n'
     '                raise\n'
     '        return result\n'),
    ('        service_absent(self._run(["/bin/launchctl", "print", "system/" + self.label], "BOOTSTRAP", success=False), self.label)\n'
     '        self._run(["/bin/launchctl", "bootstrap", "system", self.path], "BOOTSTRAP")\n',
     '        service_absent(self._run(["/bin/launchctl", "print", "system/" + self.label], "BOOTSTRAP", success=False,\n'
     '                                 return_site="BOOTSTRAP_PRECHECK_PRINT"), self.label)\n'
     '        self._run(["/bin/launchctl", "bootstrap", "system", self.path], "BOOTSTRAP", return_site="BOOTSTRAP_COMMAND")\n'),
    ('        raw = self._run(["/bin/launchctl", "print", "system/" + self.label], "BOOTSTRAP")["stdout"]\n',
     '        raw = self._run(["/bin/launchctl", "print", "system/" + self.label], "BOOTSTRAP",\n'
     '                        return_site="INSPECT_RUNNING_PRINT" if running else "INSPECT_STOPPED_PRINT")["stdout"]\n'),
    ('        if admin_diagnostic is not None:\n'
     '            print(admin_diagnostic)\n'
     '        return 2  # No qualifying exclusive outcome/seal tuple on this route.\n',
     '        if admin_diagnostic is not None:\n'
     '            print(admin_diagnostic)\n'
     '        return_diagnostic = public_admin_return(error)\n'
     '        if return_diagnostic is not None:\n'
     '            print(return_diagnostic)\n'
     '        return 2  # No qualifying exclusive outcome/seal tuple on this route.\n'),
)

# Independently transcribed from the reviewed aef82967 -> shared-clock delta.
# The 33 runtime call replacements are separately counted, not arbitrary AST
# erasure; existing diagnostic/directory inverses run only AFTER this inverse.
RUNTIME_PATCH = (
    ('NS = 1_000_000_000\n',
     'NS = 1_000_000_000\n'
     'UINT64 = (1 << 64) - 1\n'
     'CLOCK_SCHEMA = 2\n'
     'CLOCK_DOMAIN = "darwin.clock_gettime_ns(CLOCK_MONOTONIC_RAW)"\n'),
    ('def errno_name(value):\n',
     'def shared_raw_ns():\n'
     '    """Only this guarded same-boot kernel clock crosses interpreter boundaries."""\n'
     '    require(sys.platform == "darwin" and callable(getattr(time, "clock_gettime_ns", None)) and\n'
     '            type(getattr(time, "CLOCK_MONOTONIC_RAW", None)) is int, "PREPARE", "UNSUPPORTED")\n'
     '    value = time.clock_gettime_ns(time.CLOCK_MONOTONIC_RAW)\n'
     '    require(type(value) is int and 0 <= value <= UINT64, "PREPARE", "BOUND")\n'
     '    return value\n'
     '\n'
     '\n'
     'def errno_name(value):\n'),
    ('def validate_allocation(allocation, request, github, now_ns, wall_ns):\n'
     '    keys = {"schema", "source", "sourceTree", "runId", "runAttempt", "startedMonotonicNs", "startedEpochNs"}\n'
     '    require(type(allocation) is dict and set(allocation) == keys and type(allocation["schema"]) is int and\n'
     '            allocation["schema"] == 1 and allocation["source"] == request["source_sha"] and\n',
     'def validate_allocation_clock(allocation, stage):\n'
     '    keys = {"schema", "clockDomain", "source", "sourceTree", "runId", "runAttempt", "startedMonotonicNs", "startedEpochNs"}\n'
     '    require(type(allocation) is dict and set(allocation) == keys and type(allocation["schema"]) is int and\n'
     '            allocation["schema"] == CLOCK_SCHEMA and type(allocation["clockDomain"]) is str and\n'
     '            allocation["clockDomain"] == CLOCK_DOMAIN, stage, "IDENTITY_CHANGED")\n'
     '\n'
     '\n'
     'def validate_allocation(allocation, request, github, now_ns, wall_ns):\n'
     '    validate_allocation_clock(allocation, "PREPARE")\n'
     '    require(allocation["source"] == request["source_sha"] and\n'),
    ('def producer(fd):\n'
     '    """Only the original D-created inherited FD and fixed START can select work."""\n',
     'def producer(fd):\n'
     '    """Only the original D-created inherited FD and fixed START can select work."""\n'
     '    require(os.environ.get("P2PKIT_CONTEXT_CLOCK_SCHEMA") == str(CLOCK_SCHEMA) and\n'
     '            os.environ.get("P2PKIT_CONTEXT_CLOCK_DOMAIN") == CLOCK_DOMAIN, "START", "IDENTITY_CHANGED")\n'),
    ('            directory.name == value["case"] and directory.parent.name == "evidence", "IDENTITY", "REFUSED")\n'
     '    validate_account(account(), value["account"])\n',
     '            directory.name == value["case"] and directory.parent.name == "evidence", "IDENTITY", "REFUSED")\n'
     '    validate_allocation_clock(value["allocation"], "START")\n'
     '    validate_account(account(), value["account"])\n'),
    ('            require(type(prepared) is dict and type(prepared.get("caseEndNs")) is int, "START", "TIMEOUT")\n'
     '            end_ns = prepared["caseEndNs"]\n',
     '            require(type(prepared) is dict and type(prepared.get("caseEndNs")) is int, "START", "TIMEOUT")\n'
     '            validate_allocation_clock(prepared.get("allocation"), "START")\n'
     '            end_ns = prepared["caseEndNs"]\n'),
    ('                environment.update(P2PKIT_CONTEXT_BINDING=binding, P2PKIT_CONTEXT_CASE_END_NS=str(end_ns))\n',
     '                environment.update(P2PKIT_CONTEXT_BINDING=binding, P2PKIT_CONTEXT_CASE_END_NS=str(end_ns),\n'
     '                                   P2PKIT_CONTEXT_CLOCK_SCHEMA=str(CLOCK_SCHEMA), P2PKIT_CONTEXT_CLOCK_DOMAIN=CLOCK_DOMAIN)\n'),
    ('def validate_seal(seal, github, allocation, identity, now_ns):\n',
     'def validate_seal(seal, github, allocation, identity, now_ns):\n'
     '    validate_allocation_clock(allocation, "UPLOAD")\n'),
)

WORKFLOW_PATCH = (
    ('          import time\n\n',
     '          import time\n\n'
     '          UINT64 = (1 << 64) - 1\n'
     '          CLOCK_SCHEMA = 2\n'
     "          CLOCK_DOMAIN = 'darwin.clock_gettime_ns(CLOCK_MONOTONIC_RAW)'\n\n"),
    ('          def unique(pairs):\n',
     '          def shared_raw_ns():\n'
     "              require(sys.platform == 'darwin' and callable(getattr(time, 'clock_gettime_ns', None)) and\n"
     "                      type(getattr(time, 'CLOCK_MONOTONIC_RAW', None)) is int)\n"
     '              value = time.clock_gettime_ns(time.CLOCK_MONOTONIC_RAW)\n'
     '              require(type(value) is int and 0 <= value <= UINT64)\n'
     '              return value\n\n'
     '          def unique(pairs):\n'),
    ("              allocation = dict(schema=1, source=request['source_sha'], sourceTree=request['source_tree'],\n",
     '              allocation = dict(schema=CLOCK_SCHEMA, clockDomain=CLOCK_DOMAIN,\n'
     "                                source=request['source_sha'], sourceTree=request['source_tree'],\n"),
)

EXPERIMENT_TEST_PATCH = (
    ('class Focused(unittest.TestCase):\n',
     'class Focused(unittest.TestCase):\n'
     '    def setUp(self):\n'
     '        # Synthetic shared-clock readings only; these legacy models never\n'
     '        # qualify a host clock. The dedicated clock controls test its reader.\n'
     '        clock = patch.object(M, "shared_raw_ns", return_value=M.NS)\n'
     '        clock.start()\n'
     '        self.addCleanup(clock.stop)\n\n'),
    ('        context.allocation = dict(schema=1, source=SHA, sourceTree=TREE, runId="123", runAttempt="1",\n',
     '        context.allocation = dict(schema=2, clockDomain=M.CLOCK_DOMAIN, source=SHA, sourceTree=TREE,\n'
     '                                  runId="123", runAttempt="1",\n'),
    ('        allocation = dict(schema=1, source=SHA, sourceTree=TREE, runId="123", runAttempt="1",\n',
     '        allocation = dict(schema=2, clockDomain=M.CLOCK_DOMAIN, source=SHA, sourceTree=TREE,\n'
     '                          runId="123", runAttempt="1",\n'),
)


def _restore(source, patches, count, before_call, after_call, expected):
    if type(source) is not str:
        raise AssertionError("CLOCK_INVERSE_REQUIRES_CURRENT_SOURCE_TEXT")
    for before, after in reversed(patches):
        if source.count(after) != 1:
            raise AssertionError("EXACT_REVIEWED_CLOCK_HUNK_REQUIRED")
        source = source.replace(after, before, 1)
    if source.count(after_call) != count or before_call in source:
        raise AssertionError("EXACT_REVIEWED_CLOCK_SUBSTITUTIONS_REQUIRED")
    source = source.replace(after_call, before_call)
    if hashlib.sha256(source.encode("utf-8")).hexdigest() != expected:
        raise AssertionError("OUTSIDE_REVIEWED_CLOCK_DELTA_CHANGED")
    return source


def restore_plist_name_runtime(source):
    if type(source) is not str or len(PLIST_NAME_PATCH) != 3:
        raise AssertionError("EXACT_THREE_PLIST_NAME_HUNKS_REQUIRED")
    for before, after in reversed(PLIST_NAME_PATCH):
        if source.count(after) != 1:
            raise AssertionError("REVIEWED_PLIST_NAME_DELTA_CHANGED")
        source = source.replace(after, before, 1)
    if hashlib.sha256(source.encode("utf-8")).hexdigest() != PLIST_NAME_BASE_RUNTIME_SHA256:
        raise AssertionError("OUTSIDE_REVIEWED_PLIST_NAME_DELTA_CHANGED")
    return source


def restore_admin_return_runtime(source):
    source = restore_plist_name_runtime(source)
    if type(source) is not str or len(ADMIN_RETURN_PATCH) != 8:
        raise AssertionError("EXACT_EIGHT_ADMIN_RETURN_HUNKS_REQUIRED")
    for before, after in reversed(ADMIN_RETURN_PATCH):
        if source.count(after) != 1:
            raise AssertionError("REVIEWED_ADMIN_RETURN_DELTA_CHANGED")
        source = source.replace(after, before, 1)
    if hashlib.sha256(source.encode("utf-8")).hexdigest() != ADMIN_RETURN_BASE_RUNTIME_SHA256:
        raise AssertionError("OUTSIDE_REVIEWED_ADMIN_RETURN_DELTA_CHANGED")
    return source


def restore_runtime(source):
    source = restore_admin_return_runtime(source)
    return _restore(source, RUNTIME_PATCH, 33, "time.monotonic_ns()", "shared_raw_ns()", BASE_RUNTIME_SHA256)


def restore_workflow(source):
    return _restore(source, WORKFLOW_PATCH, 3, "time.monotonic_ns()", "shared_raw_ns()", BASE_WORKFLOW_SHA256)


def restore_experiment_test(source):
    return _restore(source, EXPERIMENT_TEST_PATCH, 6, 'patch.object(M.time, "monotonic_ns"',
                    'patch.object(M, "shared_raw_ns"', BASE_EXPERIMENT_TEST_SHA256)
