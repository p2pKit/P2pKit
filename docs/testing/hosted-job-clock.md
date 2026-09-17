# Ordinary job-clock prerequisite

[`hosted_job_clock.py`](../../scripts/hosted_job_clock.py) is **dormant**. No
workflow, existing FULL timing, native owner, operation maximum or activation
HOLD uses or changes because of this helper. It grants no extra execution time
and does not fix the remaining job-budget/cache integration by itself.

## Why the same host needs a shared clock

A workflow's acquisition, controller, sealing and delivery processes must consume
one original job deadline. Creating a fresh local allowance in each process can
silently overrun it. Python's local `monotonic()` epoch is not the maintained
cross-process contract, notably on the admitted macOS Python 3.9 combination.

The closed roles are:

| Role | Elapsed observation | Identity/units |
| --- | --- | --- |
| macOS ARM64 or x64 | The unchanged `hosted_lock_resources.shared_raw_ns()` | Its exact existing Darwin RAW domain; nanoseconds |
| Linux x64 | Explicit `clock_gettime_ns(CLOCK_MONOTONIC_RAW)` | Separate Linux RAW domain; nanoseconds |
| Windows x64 | Explicit `QueryPerformanceCounter` and `QueryPerformanceFrequency` | Separate QPC domain; observed positive frequency and integer-floor nanoseconds |

No wall clock, process-local epoch, alternative clock ID, environment-selected
role, DLL path or caller-supplied reader is substituted when a source is absent.
The Windows API uses the fixed system library search and explicit signed-64-bit
counter/frequency pointers. Its lazy module reference lasts for the process;
clock queries do not allocate an owned native HANDLE. Imports do not read clocks,
load that library or the Darwin-only resource observer, create children or make
network requests. Only the selected Darwin reader imports that unchanged
observer, then checks its exact pinned RAW domain before delegation. Linux and
Windows need neither Unix-only defaults nor the Darwin module to import.

Each immutable `Reading` includes its `ClockIdentity`. The pure validators check
the supplied type/domain/role/frequency/value only. `observe()` reuses the existing
`host_role()` native architecture/translation checks. It is **not complete native
host/clock qualification**; existing owner/toolchain admission remains required.

`elapsed_ns` refuses a changed identity/frequency or backward reading.
`checked_now` obtains a new reading against the original identity and lower bound.
Neither proves that two arbitrary records came from the same machine or boot:
the caller must bind the genuine original job, runner, native owner and source.
Do not reuse these records across machines or reboot. Linux/Darwin RAW clocks
exclude suspended time; Windows QPC retains its own OS-defined suspend behavior.
This helper does not normalize suspend semantics or establish a service-wall-clock
deadline across suspension. Future budgeting must preserve its admitted host/
service-clock assumptions and must not compare these different domains.

`local_deadline` samples local time **before** the new shared reading, clamps to
the supplied original fence and operation maximum, and rounds downward. The
result is a per-process convenience: never serialize it or use it instead of
the original shared fence. The caller must recheck that fence at return and
resource-retirement boundaries. A deadline is not cancellation of an unbounded
system call, proof of retirement, or permission to renew an exhausted job.

## Verification and unfinished integration

Focused offline command (a recipe, not an execution claim):

```bash
python3 -I -B -S scripts/tests/hosted-job-clock-test.py
```

It models native clock suppliers and checks explicit API signatures/selection,
integer precision, invalid values/frequency, cross-domain/backward refusal,
expired fences, conversion order/rounding and absent fallback. It starts no real
native query, child, build, emulator or download. Authoring/passing models does
not qualify real Linux/Windows cross-process clocks. Genuine source-bound
paired-process native admission remains necessary before a new role is used.

Still required: closed profile/mode budgeting from original service-job
observations, actual source/outcome binding, custody retention through separate
seal, provider and sample-delivery guards, and native/hosted qualification.
FULL's current 2,430-second reserve leaves at most 1,170 seconds before setup
and freshness charges. Desktop's current 1,500-second controller plus 120-second
seal and 180-second evidence upload already consume its whole 30-minute job,
before setup, packaging, sample uploads or cache operations. A clock cannot make
that accounting fit: reject overcommitment or independently review an equivalent
complete bounded allocation. Do not append new timeouts or widen the jobs.
