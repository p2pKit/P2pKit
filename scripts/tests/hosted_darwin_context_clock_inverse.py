"""Inert exact clock-delta inverses for historical source pins only.

Each inverse transforms the supplied CURRENT source, checks every reviewed hunk
and substitution count, then requires the independently retained original hash.
It never reads files, returns an embedded source substitute, or executes source.
Behavioral controls must import the current runtime, never these preimages.
"""
import hashlib

BASE_RUNTIME_SHA256 = "a3904f34c48f85d1e0b93b8a6f24f61423e9533030c9328c61916862c46b623d"
BASE_WORKFLOW_SHA256 = "c88c6e69c00c0a150e0eacefbfb54e7611ec9511112dbd02c303f8ad19d7aa40"
BASE_EXPERIMENT_TEST_SHA256 = "484c4ebdd20bf5500ad9ba340f552cc15088e0c02e74759805cf693cfe290768"

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


def restore_runtime(source):
    return _restore(source, RUNTIME_PATCH, 33, "time.monotonic_ns()", "shared_raw_ns()", BASE_RUNTIME_SHA256)


def restore_workflow(source):
    return _restore(source, WORKFLOW_PATCH, 3, "time.monotonic_ns()", "shared_raw_ns()", BASE_WORKFLOW_SHA256)


def restore_experiment_test(source):
    return _restore(source, EXPERIMENT_TEST_PATCH, 6, 'patch.object(M.time, "monotonic_ns"',
                    'patch.object(M, "shared_raw_ns"', BASE_EXPERIMENT_TEST_SHA256)
