# Initial-provider public transport: source-only increment

Status: dormant source, pending independent implementation review and execution.
This does not activate a workflow or qualify provider, cache, custody or Release.

The distinct contract in
[`hosted_initial_recipient_public_origin.py`](../../scripts/hosted_initial_recipient_public_origin.py)
allows only the eight fixed public GitHub endpoint kinds used by initial
recipient acquisition. It requires the exact public cache directive set
`public,max-age=60,s-maxage=60`, each once, with no extra directives. Directive
order and normal outer whitespace may differ. All other original header,
status, length, Date, request-ID, age/intermediary and conservative 60-second
service-time conditions remain. Public cacheability does not prove an
instantaneous or uncached origin response.

The bootstrap origin module shares its existing bounded HTTP/reader/connection
lifecycle behind closed private/public wrappers. Private entry signatures and
`hosted_full_job_budget.freshness` are unchanged; private still refuses public.
Both envelope readers reject the other scope. The new public wrapper sends no
Authorization header and refuses actual API/runtime credential environment
fields; no token fallback, redirect, retry or cachebuster is added.

The initial recipient acquisition sibling preserves complete source-before,
eight GETs, source-after and original payload matching. It returns a
`BootstrapMatch`, never ordinary `Admission`. The retained public envelopes
have their own scope; body/header bytes are not normalized or relabelled.
An actual process-context entry exists, but has **no native/provider caller**.
The four fixed site spellings are begin/final for provider-save/provider-probe.
The enclosing owner must still authenticate original site/order and matching
authority: a string or returned JSON record cannot supply that capability.

This increment supplies only the inner 24 Git-query acquisition composition.
The original per-use owner, outer 12+12 queries, native child routing, known
close/one-use return, productive provider bridge and complete evidence custody
remain separate unfinished integration work. No B/N/C registry or accepted
initializer/reader implementation changes here.

Known anonymous quota must cover the remaining requests: begin owes its own
eight plus final's eight; final owes eight. Missing quota is not invented,
known insufficiency fails, and sufficient quota is not a reservation against
shared-egress callers. The 32 public GETs per save+probe runner, two acquisitions
inside helper45/provider180, transition30 and Windows900 remain real hosted
fit/qualification risks, not new allowances or passed measurements.

[`hosted-initial-recipient-public-origin-test.py`](../../scripts/tests/hosted-initial-recipient-public-origin-test.py)
authors 34 focused offline model methods. They cover the observed header shape,
cross-scope refusal, unchanged private composition, fixed paths, source24,
credential boundaries, quota loss, original payload checks, parent/drift bounds
and close/failure preservation. Models use explicitly synthetic identities and
fake HTTP/Git I/O. These methods are **authored but unexecuted** in this source
increment; they cannot establish original service/native/provider acceptance.
All original HOLDs, approvals, required checks and Release gates remain.
