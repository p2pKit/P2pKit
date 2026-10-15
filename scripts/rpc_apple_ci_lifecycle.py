"""Production-inactive decision core for the ordinary-CI Apple keeper.

No process, Terminal, GitHub, file, native observer or cancellation record is
created here. One serialized keeper owner supplies independently verified
observations and consumes the decisions; these inputs are not runtime evidence.
The original feature-context helper and its admission remain unchanged.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import re
from typing import Callable


SCOPE = "ORDINARY_CI_APPLE_KEEPER_DECISIONS_NOT_NATIVE_OR_RELEASE_QUALIFICATION"
BINDING_KEYS = {"source", "runId", "runAttempt", "jobId", "invocationId", "bootSession",
                "boundAtMonotonic", "productCutoffMonotonic", "finalizationCutoffMonotonic",
                "jobCutoffMonotonic", "cancellationAllowanceSeconds", "terminalAndVerificationReserveSeconds"}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def finite(value: object) -> float:
    require(type(value) in (int, float), "Numeric monotonic observation required")
    try:
        number = float(value)
    except (ValueError, OverflowError):
        raise ValueError("Unrepresentable monotonic observation") from None
    require(math.isfinite(number) and number >= 0, "Finite nonnegative monotonic observation required")
    return number


def boot_uuid(value: object) -> str:
    require(type(value) is str and re.fullmatch(
        r"[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}", value) is not None and
        set(value.replace("-", "")) != {"0"}, "Exact kernel boot-session UUID required")
    return value.lower()


@dataclass(frozen=True)
class KeeperBinding:
    """Immutable caller binding, not authentication or a reviewed budget approval.

    The caller supplies both cancellation allowance and complete Terminal/outer
    verification reserve. The 300-second ceiling and 30-second minimum only
    reject impossible inputs; they do not establish a sufficient runtime budget.
    """
    commit: str
    tree: str
    run_id: int
    run_attempt: int
    job_id: str
    invocation_id: str
    boot_session: str
    bound_at: float
    product_cutoff: float
    finalization_cutoff: float
    job_cutoff: float
    cancellation_allowance: float
    terminal_and_verification_reserve: float

    def __post_init__(self) -> None:
        for value in (self.commit, self.tree):
            require(type(value) is str and re.fullmatch(r"(?:[0-9a-f]{40}|[0-9a-f]{64})", value) is not None and
                    set(value) != {"0"}, "Exact source object identity required")
        require(len(self.commit) == len(self.tree), "Source hash algorithms differ")
        for value, maximum in ((self.run_id, 2**63 - 1), (self.run_attempt, 2**31 - 1)):
            require(type(value) is int and 0 < value <= maximum, "Exact run/attempt identity required")
        for value in (self.job_id, self.invocation_id):
            require(type(value) is str and re.fullmatch(r"[0-9a-f]{32}", value) is not None and
                    set(value) != {"0"}, "Exact preallocated audit identity required")
        object.__setattr__(self, "boot_session", boot_uuid(self.boot_session))
        for name in ("bound_at", "product_cutoff", "finalization_cutoff", "job_cutoff",
                     "cancellation_allowance", "terminal_and_verification_reserve"):
            object.__setattr__(self, name, finite(getattr(self, name)))
        require(self.bound_at < self.product_cutoff < self.finalization_cutoff <= self.job_cutoff and
                self.job_cutoff - self.bound_at <= 3600 and
                self.finalization_cutoff - self.product_cutoff >= self.terminal_and_verification_reserve,
                "Original job/product cutoffs and complete finalization reserve required")
        require(30 <= self.terminal_and_verification_reserve < self.cancellation_allowance <= 300,
                "Caller-reviewed cancellation allowance and Terminal/verification reserve required")

    @classmethod
    def from_record(cls, record: dict) -> KeeperBinding:
        require(type(record) is dict and set(record) == BINDING_KEYS, "Closed keeper binding required")
        source = record["source"]
        require(type(source) is dict and set(source) == {"commit", "tree"}, "Closed exact source required")
        return cls(source["commit"], source["tree"], record["runId"], record["runAttempt"],
                   record["jobId"], record["invocationId"], record["bootSession"], record["boundAtMonotonic"],
                   record["productCutoffMonotonic"], record["finalizationCutoffMonotonic"], record["jobCutoffMonotonic"],
                   record["cancellationAllowanceSeconds"], record["terminalAndVerificationReserveSeconds"])


class KeeperDecision:
    """Single-owner, serialized decisions; not a spawn API or signal handler.

    The runtime must validate the actual façade lifetime before reporting SAME.
    EOF/UNCERTAIN never authorize PID-based control. A successful begin_product
    only consumes one launch decision: the maintained executor must still check
    the exact invocation's cancellation fence before actually spawning a child.
    """

    def __init__(self, binding: KeeperBinding):
        require(type(binding) is KeeperBinding, "Immutable keeper binding required")
        self._binding = binding
        self._last_now = binding.bound_at
        self._clock_usable = True
        self._start_decided = False
        self._launch_requested = False
        self._product_exit = None
        self._cancel_reason = None
        self._cancel_cutoff = None
        self._cancel_attempted = False
        self._cancel_delivery = "NOT_REQUESTED"
        self._closed = False

    @property
    def binding(self) -> KeeperBinding:
        return self._binding

    @property
    def cancellation_reason(self) -> str | None:
        return self._cancel_reason

    @property
    def cancellation_delivery(self) -> str:
        return self._cancel_delivery

    @property
    def cancellation_cutoff(self) -> float | None:
        return self._cancel_cutoff

    @property
    def cancellation_request_cutoff(self) -> float | None:
        if self._cancel_cutoff is None:
            return None
        return math.nextafter(self._cancel_cutoff - self.binding.terminal_and_verification_reserve, -math.inf)

    def _latch(self, reason: str) -> None:
        if self._cancel_reason is None:
            self._cancel_reason = reason
            if self._clock_usable:
                # Supplied by the reviewed contract, never a new default lease.
                # Reserve the original Terminal phase plus caller verification.
                self._cancel_cutoff = min(self.binding.finalization_cutoff, math.nextafter(
                    self._last_now + self.binding.cancellation_allowance, -math.inf))

    def _observe_clock(self, now: object, boot_session: object) -> None:
        try:
            boot = boot_uuid(boot_session)
        except ValueError:
            self._clock_usable = False
            self._latch("BOOT_SESSION_UNKNOWN")
            return
        if boot != self.binding.boot_session:
            self._clock_usable = False
            self._latch("BOOT_SESSION_CHANGED")
            return  # Never compare clocks from different boot sessions.
        try:
            observed = finite(now)
        except ValueError:
            self._clock_usable = False
            self._latch("CLOCK_UNKNOWN")
            return
        if observed < self._last_now:
            self._clock_usable = False
            self._latch("CLOCK_REVERSED")
            return
        if not self._clock_usable:
            return  # A later plausible reading cannot repair lost continuity.
        self._last_now = observed
        if self._cancel_cutoff is not None and observed >= self._cancel_cutoff:
            self._latch("CANCELLATION_DEADLINE")
        elif observed >= self.binding.finalization_cutoff:
            self._latch("FINALIZATION_DEADLINE")
        elif self._product_exit is None and observed >= self.binding.product_cutoff:
            self._latch("PRODUCT_DEADLINE")

    def observe(self, *, now: object, boot_session: object, facade: str,
                explicit_cancel: bool = False) -> bool:
        require(not self._closed, "Finalized keeper cannot accept new work or observations")
        self._observe_clock(now, boot_session)
        if type(explicit_cancel) is not bool:
            self._latch("CANCEL_OBSERVATION_UNKNOWN")
        elif explicit_cancel:
            self._latch("EXPLICIT_CANCEL")
        if type(facade) is str and facade == "EOF":
            self._latch("FACADE_EOF")
        elif type(facade) is not str or facade != "SAME":
            self._latch("FACADE_IDENTITY_UNKNOWN")
        return self._cancel_reason is None

    def begin_product(self, **observation) -> bool:
        require(not self._start_decided, "Product launch decision is single-use")
        self._start_decided = True
        self._launch_requested = self.observe(**observation)
        return self._launch_requested

    def product_exited(self, exit_code: int, **observation) -> None:
        require(self._launch_requested and self._product_exit is None, "One previously requested product exit required")
        require(type(exit_code) is int and -255 <= exit_code <= 255, "Exact observed product exit required")
        self.observe(**observation)  # Charge the product deadline before accepting its completion.
        self._product_exit = exit_code

    def request_cancellation(self, callback: Callable, clock: Callable[[], tuple[float, str]]) -> str:
        """Deliver once through the future canonical Foundation callable.

        callback binds the independently admitted physical state and accepts
        expected_job_id, invocation_id, deadline_monotonic. It must return None
        after completing the canonical request. No product PID is needed: the
        preallocated invocation fences cancellation between decision and spawn.
        clock returns a fresh (monotonic, kernel_boot_uuid) observation. Sampling
        after callback detects a late return; it CANNOT interrupt blocked I/O.
        The callback gets the earlier latched cancellation cutoff minus the
        caller-reviewed Terminal/verification reserve, not the whole job lease.
        The enclosing reviewed runtime watchdog remains mandatory.
        """
        require(not self._closed, "Finalized keeper cannot request cancellation")
        if self._cancel_reason is None or not self._launch_requested:
            return self._cancel_delivery
        if self._cancel_attempted:
            return self._cancel_delivery
        self._cancel_attempted = True

        def sample() -> None:
            try:
                now, boot = clock()
            except Exception:
                self._clock_usable = False
                self._latch("CLOCK_UNKNOWN")
                return
            self._observe_clock(now, boot)

        sample()
        if not self._clock_usable:
            self._cancel_delivery = "REFUSED_CLOCK"
            return self._cancel_delivery
        deadline = self.cancellation_request_cutoff
        if deadline is None or self._last_now >= deadline:
            self._cancel_delivery = "REFUSED_DEADLINE"
            return self._cancel_delivery
        try:
            result = callback(expected_job_id=self.binding.job_id, invocation_id=self.binding.invocation_id,
                              deadline_monotonic=deadline)
            self._cancel_delivery = "ACKNOWLEDGED_BY_CALLBACK" if result is None else "FAILED_CALLBACK"
        except Exception:
            self._cancel_delivery = "FAILED_CALLBACK"  # Never retain exception text or credentials.
        sample()
        if not self._clock_usable:
            self._cancel_delivery = "UNKNOWN_CALLBACK_COMPLETION"
        elif self._last_now >= deadline:
            self._cancel_delivery = "LATE_CALLBACK_COMPLETION"
        return self._cancel_delivery

    def finish(self, *, cleanup_verified: bool, **observation) -> dict:
        """Record caller-verified cleanup separately; never manufacture proof.

        A true input means the future runtime verified its exact supervisor,
        shell and application receipts. This pure module cannot establish that.
        Cancellation remains failure even when that cleanup observation is true.
        """
        require(type(cleanup_verified) is bool, "Explicit cleanup observation required")
        self.observe(**observation)
        self._closed = True
        cutoff = self.binding.finalization_cutoff if self._cancel_cutoff is None else self._cancel_cutoff
        cleanup_accepted = cleanup_verified and self._clock_usable and self._last_now < cutoff
        code = (self._product_exit if self._cancel_reason is None and cleanup_accepted and
                type(self._product_exit) is int and 0 <= self._product_exit <= 255 else 125)
        return {"scope": SCOPE, "source": {"commit": self.binding.commit, "tree": self.binding.tree},
                "runId": self.binding.run_id, "runAttempt": self.binding.run_attempt,
                "jobId": self.binding.job_id, "invocationId": self.binding.invocation_id,
                "productExitCode": self._product_exit, "exitCodeDecision": code,
                "cancellationReason": self._cancel_reason, "cancellationDelivery": self._cancel_delivery,
                "cancellationCutoffMonotonic": self._cancel_cutoff,
                "cancellationRequestCutoffMonotonic": self.cancellation_request_cutoff,
                "cleanupObservation": "VERIFIED_BY_CALLER" if cleanup_accepted else "UNKNOWN",
                "nativeExecutionAuthorized": False, "runtimeEvidenceRequired": True}
