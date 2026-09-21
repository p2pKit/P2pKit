"""Fixed dormant outer entry, NOT source/service admission or a Node caller.

Only the literal --supervisor mode of the isolated fixed loader constructs this
entry. Its two roots already exist; it neither acquires a bundle nor selects a
provider. An incomplete entry exits66 without public exception/file contents.
Fences reject late native returns; they cannot preempt a blocked root opener or
prove retirement if this original supervisor itself is lost.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import signal
import threading

import hosted_cache_provider_supervisor as supervisor


L = supervisor.launch
T = supervisor.outer_return
QUARANTINE = []


@dataclass(frozen=True, repr=False)
class _EntryReturn:
    result: object = field(repr=False)
    error: BaseException | None = field(repr=False)
    check: object = field(repr=False)


class _SupervisorEntry:
    """One actual pre-root window, two actual roots and a finite signal owner."""
    def __init__(self, request):
        context, _ = T._context(request)
        role = context["role"]
        self.first = L.clocks.validate_reading(L.clocks.Reading(L.clocks.ClockIdentity(
            role, L.clocks.DOMAINS[role], context["frequency"]), int(context["firstNs"])))
        for name in ("directory", "home", "node"):
            L._path(context[name], role)
        L.require(L._path(context["node"], role).name == ("node.exe" if role == "windows-x64" else "node") and
                  context["directory"] != context["home"], "PROVIDER_ENTRY_PATHS")
        for path in context["toolPath"].split(";" if role == "windows-x64" else ":"):
            L._path(path, role)
        L.cache.bootstrap_provider_contract(context["plan"], context["phase"])
        L.require(context["plan"]["role"] == role, "PROVIDER_ENTRY_PLAN_ROLE")
        self.request, self.context = request, context
        self.owner = supervisor.ProviderSupervisor()
        self.window = None
        self.roots = {"directory": None, "home": None}
        self._started = self._finished = self._exit_started = self._unknown = False
        self._primary = self._completed = None
        self._errors = []
        self._signalled = False
        self._cancellation = KeyboardInterrupt("PROVIDER_ENTRY_CANCELLED")

    def _failed(self, stage, error, *, unknown=False):
        if self._primary is None:
            self._primary = error
        self._errors.append((stage, error))
        self._unknown |= unknown
        if not any(value is self for value in QUARANTINE):
            QUARANTINE.append(self)

    def run(self):
        try:
            L.require(not self._started and threading.current_thread() is threading.main_thread(),
                      "PROVIDER_ENTRY_ONCE_MAIN_THREAD")
            self._started = True
        except BaseException as error:
            self._failed("entry", error)
            raise self._primary
        owner, first, context, request = self.owner, self.first, self.context, self.request
        roots, originals = self.roots, {"directory": None, "home": None}
        errors, cancellation = self._errors, self._cancellation
        thread = threading.get_ident()
        handlers, installed, restored, closed = [], set(), [], []
        window = result = run_error = completion = None
        called = transferred = False

        def same():
            L.require(threading.get_ident() == thread and self.owner is owner and self.first is first and
                self.context is context and self.request is request and L._json(context).encode("ascii") == request and
                self.roots is roots and tuple(roots) == ("directory", "home") and
                all(roots[name] is value for name, value in originals.items()) and
                self.window is window and self._errors is errors and self._cancellation is cancellation,
                "PROVIDER_ENTRY_ORIGINALS_CHANGED")
            if window is not None:
                L.require(owner.launch.window is owner.launch._window_original is window,
                          "PROVIDER_ENTRY_WINDOW_CHANGED")

        def checked(*, final=False):
            same()
            if not final:
                if self._primary is not None:
                    raise self._primary
                if self._signalled:
                    raise cancellation
            observed = window.check(work=not final)
            same()
            if not final:
                if self._primary is not None:
                    raise self._primary
                if self._signalled:
                    raise cancellation
            return observed

        def cancelled():
            # The supervisor's wait/retirement own their shorter work/final
            # fences. Do not turn cancellation into a second finalization limit.
            checked(final=True)
            if self._primary is not None:
                raise self._primary
            if self._signalled:
                raise cancellation

        def received(_number, _frame):
            self._signalled = True  # No async raise, native I/O or cleanup.

        try:
            if self._primary is not None:
                raise self._primary
            # This is the sole LOCAL-before-RAW conversion in this process.
            # Supplied original RAW fields grant no admission; current native
            # observations must match them before any root acquisition.
            window = L._Window(first, int(context["issuedNs"]), int(context["hardEndNs"]),
                               int(context["hardEndNs"]))
            self.window = window
            owner.take_window(window)
            checked()
            numbers = (signal.SIGINT, signal.SIGTERM, *([signal.SIGBREAK] if hasattr(signal, "SIGBREAK") else []))
            for number in numbers:
                checked()
                previous = signal.getsignal(number)
                handlers.append((number, previous))  # Before the fallible setter.
                actual = signal.signal(number, received)
                installed.add(number)  # The setter actually returned, before another callback.
                L.require(actual is previous and signal.getsignal(number) is received, "PROVIDER_ENTRY_SIGNAL_INSTALL")
                checked()
            for name in roots:
                checked()
                try:
                    value = L._open_directory(context[name], first.clock.role)
                except BaseException:
                    self._unknown = True  # A native acquisition may not have returned.
                    raise
                originals[name] = value
                roots[name] = value  # Actual return before callbacks/verification.
                if value is None:
                    self._unknown = True
                L.require(value is not None, "PROVIDER_ENTRY_ROOT_NOT_RETURNED")
                checked()
                value.verify()
                L.require(tuple(value.identity) == tuple(context[name + "Identity"]) and
                          str(value.path) == context[name], "PROVIDER_ENTRY_ROOT_CHANGED")
                checked()
            owner.take_directories(roots["directory"], roots["home"])
            transferred = True
            checked()
            called = True
            try:
                result = owner.run_and_send(first, issued_ns=int(context["issuedNs"]),
                    hard_end_ns=int(context["hardEndNs"]), worker_cutoff_ns=int(context["workerCutoffNs"]),
                    phase=context["phase"], job=context["job"], invocation=context["outerId"],
                    inner_invocation=context["innerId"], plan=context["plan"], node=context["node"],
                    tool_path=context["toolPath"], cancelled=cancelled)
            except BaseException as error:
                run_error = error  # Original local return, not a later diagnostic selection.
                raise
        except BaseException as error:
            self._failed("run", error)
        finally:
            # Before actual invocation, only these two returned roots belong to
            # this wrapper. After invocation it must not repeat supervisor close.
            if not called and not self._unknown and window is not None:
                for name in ("home", "directory"):
                    value = originals[name]
                    if value is not None:
                        try:
                            checked(final=True)
                            closed.append(name)  # Never retry an ambiguous close.
                            value.close()
                            checked(final=True)
                        except BaseException as error:
                            self._failed("root-close", error, unknown=True)
                            break
            # Restore every attempted installation, including a setter that may
            # have changed its handler before raising. No handler is a file owner.
            for number, previous in reversed(handlers):
                try:
                    current = signal.getsignal(number)
                    if current is not received and (number in installed or current is not previous):
                        self._failed("signal-changed", L.ProviderLaunchError("PROVIDER_ENTRY_SIGNAL_CHANGED"), unknown=True)
                    displaced = signal.signal(number, previous)
                    restored.append(number)
                    L.require(displaced is current and signal.getsignal(number) is previous,
                              "PROVIDER_ENTRY_SIGNAL_RESTORE")
                except BaseException as error:
                    self._failed("signal-restore", error, unknown=True)
            self._finished = True
        try:
            L.require(called and transferred and not self._unknown and self._primary is run_error and
                      restored == [number for number, _ in reversed(handlers)], "PROVIDER_ENTRY_INCOMPLETE")
            L.require(not self._signalled or run_error is cancellation, "PROVIDER_ENTRY_LATE_CANCELLATION")
            checked(final=True)
            prefix, signal_state = tuple(errors), self._signalled
            def completed():
                L.require(self._finished and self._completed is completion and not self._unknown and
                    self._primary is run_error and self._signalled is signal_state and
                    len(errors) == len(prefix) and all(a is b for a, b in zip(errors, prefix)),
                    "PROVIDER_ENTRY_COMPLETION_CHANGED")
                for number, previous in handlers:
                    L.require(signal.getsignal(number) is previous, "PROVIDER_ENTRY_SIGNAL_RESTORE_CHANGED")
                checked(final=True)
                L.require(self._completed is completion and self._signalled is signal_state and
                    len(errors) == len(prefix) and all(a is b for a, b in zip(errors, prefix)),
                    "PROVIDER_ENTRY_COMPLETION_CHANGED")
                for number, previous in handlers:
                    L.require(signal.getsignal(number) is previous, "PROVIDER_ENTRY_SIGNAL_RESTORE_CHANGED")
                # Even the final handler getter can spend time or deliver a
                # pending cancellation. No callback-bearing read follows this
                # final fence and direct completion-state check.
                checked(final=True)
                L.require(self._finished and self._completed is completion and not self._unknown and
                    self._primary is run_error and self._signalled is signal_state and
                    len(errors) == len(prefix) and all(a is b for a, b in zip(errors, prefix)),
                    "PROVIDER_ENTRY_COMPLETION_CHANGED")
            completed()
            pending = _EntryReturn(result, run_error, completed)
            completed()
            completion = pending
            self._completed = completion  # No following callback before actual return.
        except BaseException as error:
            self._failed("completion", error)
        if self._primary is not None:
            raise self._primary
        return result

    def exit_code(self, result, error):
        """Actual loader passes its own run return/raise here once, never a replay."""
        try:
            L.require(not self._exit_started, "PROVIDER_ENTRY_EXIT_ONCE")
            self._exit_started = True
            completion = self._completed
            L.require(type(completion) is _EntryReturn and result is completion.result and error is completion.error,
                      "PROVIDER_ENTRY_EXIT_INCOMPLETE")
            completion.check()
            code = self.owner.exit_code(result, error)
            completion.check()
            L.require(type(code) is int and code == (0 if error is None else T.FAILED_EXIT), "PROVIDER_ENTRY_EXIT_CODE")
            return code
        except BaseException as failure:
            self._failed("exit", failure)
            raise self._primary
