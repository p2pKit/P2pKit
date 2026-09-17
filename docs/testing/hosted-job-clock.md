# Ordinary job-clock prerequisite

Ordinary consume/delivery source now connects one original job-budget chain
**behind unchanged FULL/Desktop activation HOLDs**. Desktop uses
[`hosted_job_clock.py`](../../scripts/hosted_job_clock.py); FULL retains its
existing Darwin RAW supplier and reservation. This is source integration, not
native clock, provider, product or hosted acceptance. It grants no extra time,
changes no job deadline and cannot lift either HOLD.

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
deadline across suspension. Connected budgeting must preserve its admitted host/
service-clock assumptions and must not compare these different domains.

`local_deadline` samples local time **before** the new shared reading, clamps to
the supplied original fence and operation maximum, and rounds downward. The
result is a per-process convenience: never serialize it or use it instead of
the original shared fence. The caller must recheck that fence at return and
resource-retirement boundaries. A deadline is not cancellation of an unbounded
system call, proof of retirement, or permission to renew an exhausted job.

## Original budget and delivery chain

`prepare-consume` retains original Actions service-job responses and their
native acquisition/return records. The budget binds source commit/tree, admitted
run/attempt/job/runner, original response hashes and clock identity/domain (and
QPC frequency). Service freshness, clock margin and elapsed setup are charged
against the original job, never replaced by a new per-process epoch.

Every later preparation, restore, controller, seal and delivery transition
re-admits the original record chain and carries forward the predecessor's
high-water observation before sampling the next clock. Changed source/job/clock
identity or frequency, backward observations and expired windows fail closed.
Local deadline conversion only clamps to that authority; it does not create a
new allowance. Cross-host and cross-boot record reuse remain invalid.

The source-owned allocation is:

- **FULL:** unchanged 3,600-second job and 2,430-second reserve. At most 1,170
  seconds remain before setup/freshness charges. Restore consumes the existing
  productive interval. No new cache save or post-Central-screen tail is added.
- **Desktop:** unchanged 1,800-second job; the 1,500-second controller ceiling
  is additionally clamped to original job-end minus 600 seconds. Product
  work/outer ceilings remain 600/825 seconds. The productive cutoff protects
  the existing 225-second return plus 45-second finalization interval.
  Custody, pre-export sample packaging (75 seconds work plus 45 finalization),
  freeze and export share that controller end; their maxima are not independently
  reserved or guaranteed to fit.
- **Desktop delivery:** ends at the earlier of original job-end or the original
  controller terminal observation plus 600 seconds. Seal is capped at 120
  seconds; evidence upload at 180. The post-seal `package-samples` guard is
  capped at 30 seconds and only verifies the pre-export packages, not a new
  application/package writer. Desktop and Linux-only Android sample uploads
  share **one** at-most-180-second window, including their guards; Android must
  follow successful Desktop completion. All remain inside that one delivery end.

Restore and Desktop upload action timeouts are the remaining complete 1–3
minutes, rounded down and checked again after original action return. FULL's
existing evidence upload remains three minutes and requires that original
allowance. Separate bounded windows are not additive extra job time. Exhaustion
fails the relevant gate; a timeout is not proof of cancellation or retirement.

## Verification and unfinished qualification

Focused offline commands (recipes, not execution claims):

```bash
python3 -I -B -S scripts/tests/hosted-job-clock-test.py
python3 -I -B -S scripts/tests/hosted-desktop-job-budget-test.py
python3 -I -B -S scripts/tests/hosted-consume-delivery-test.py
```

These model native clock/provider boundaries and check explicit API selection,
integer precision, invalid values/frequency, identity/backward refusal, original
budget fences and predecessor continuity, conversion rounding and absent
fallback. They start no real native query, build, emulator or download.
Authoring/passing models does
not qualify real Linux/Windows cross-process clocks. Genuine source-bound
paired-process native admission remains necessary before a new role is used.

Still required: independent review of the connected revision, genuine original
service/native timing admission, exact cache and changed-source product
acceptance, retained separate-seal/delivery evidence and measured budget fit.
The connected/budget models are registered in the unconditional ordinary CI
controls and release-workflow/release-gate checks. Their successful execution
does not establish any of that native/hosted acceptance.

Historical milestone: the initial clock helper was dormant. The earlier Desktop
1,500-second controller plus 120-second seal and 180-second evidence upload
already consumed the whole 30-minute job before setup, packaging and sample
uploads. The connected source now clamps shared envelopes rather than appending
independent allowances. That does not erase the earlier overcommitment finding
or prove the complete runtime fits. Do not widen jobs or resurrect fresh tails.
