"""Read the fixed ACK-bound provider originals under an existing native Owner.

This is a success-only readback, not runner/source admission or cache acceptance.
The caller must first observe the original supervisor's successful exit/close,
then supply a NEW Owner whose RAW/local fences still end at the original end.
No failed, incomplete or cancelled bridge result permits this read. The borrowed
owner still needs its own known close and the enclosing Action/runner return.
No provider output or path-bearing original is suitable for public logs.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import os

import hosted_cache_provider_launch as launch
import hosted_cache_provider_supervisor_return as outer


@dataclass(frozen=True, repr=False)
class ProviderReadback:
    provider: launch.transport.TransportedProvider = field(repr=False)
    acknowledgement: outer.Acknowledgement = field(repr=False)
    worker_request: bytes = field(repr=False)
    originals: tuple = field(repr=False)
    checked_ns: int
    scope: str = "PROVIDER_ORIGINAL_READBACK_PENDING_OWNER_CLOSE_V1"
    enclosing_owner_close: str = "NOT_OBSERVED"
    original_action_outcome: str = "NOT_OBSERVED"
    provider_acceptance: str = "NOT_ESTABLISHED"


def _worker_request(native, request, ack, python, bindings):
    """Recover the actual retained argv token; never reconstruct a worker frame."""
    context, _ = outer._context(request)
    role = context["role"]
    value = launch.transport._parse(native, outer.NATIVE_BYTES)
    backend, api, mode = (("windows-job-list-suspended", "CreateProcessW", "caller-owned-native-files")
        if role == "windows-x64" else
        ("linux-proc-pidfd" if role == "linux-x64" else "darwin-libproc-audit-token",
         "subprocess.Popen", "caller-owned-files"))
    launch.require(value.get("backend") == backend and value.get("job") == context["job"] and
        value.get("invocation") == context["outerId"] and value.get("discoveryErrors") == [] and
        type(value.get("launches")) is list and len(value["launches"]) == 1, "PROVIDER_READBACK_NATIVE_RECORD")
    record = value["launches"][0]
    argv = record.get("requestedArgv") if type(record) is dict else None
    launch.require(type(argv) is list and len(argv) == 7 and all(type(arg) is str for arg in argv) and
        argv[:5] == [python, "-I", "-B", "-S", str(launch.SCRIPTS / "hosted_cache_provider_worker.py")] and
        record.get("resolvedArgv") == argv and record.get("api") == api and record.get("created") is True and
        type(record.get("pid")) is int and record["pid"] > 0 and
        record.get("cwd") == str(launch.SCRIPTS.parent) and record.get("outputMode") == mode,
        "PROVIDER_READBACK_NATIVE_LAUNCH")
    launch._path(python, role)
    if role == "windows-x64":
        launch.require(record.get("resumed") is True and record.get("batch") is False and
            record.get("applicationName") == python and
            record.get("commandLine") == launch.subprocess.list2cmdline(argv), "PROVIDER_READBACK_NATIVE_FRAMING")
    else:
        launch.require(record.get("shell") is False and record.get("executable") == python,
                       "PROVIDER_READBACK_NATIVE_FRAMING")
    roster = launch.worker_source.names(role)
    launch.require(type(bindings) is dict and set(bindings) == set(launch.worker_source.outer_names(role)),
                   "PROVIDER_READBACK_SOURCE_ROSTER")
    sources = {name: bindings[name] for name in roster}
    launch.require(all(type(value) is str and launch.re.fullmatch(r"[0-9a-f]{64}", value)
                       for value in bindings.values()) and argv[5] == launch._json(sources),
                   "PROVIDER_READBACK_SOURCE_BINDING")
    raw = argv[6].encode("ascii")
    frame, digest = launch.transport._context(raw)
    launch._frame(frame)
    launch.require(digest == ack.worker_request_sha256 and all(frame.get(name) == value
        for name, value in context.items() if name not in ("schema", "firstNs")), "PROVIDER_READBACK_WORKER_REQUEST")
    return raw


def read_success(owner, directory, request, acknowledgement, supervisor_exit, *, python, bindings):
    """Read actual fixed files, binding their native identities AND exact bytes.

    Owner is the maintained bootstrap Owner, supplied by its fixed caller. This
    function does not authenticate that caller or the supplied original ACK.
    No new deadline, owner, process, source loader, cache classifier or writer is
    created. Failed transport remains private for separate failure custody.
    """
    context, _ = outer._context(request)
    ack = outer.read_ack(acknowledgement, request, supervisor_exit)
    launch.require(ack.kind == ack.provider_kind == "success" and ack.worker_exit_code == 0,
                   "PROVIDER_READBACK_SUCCESS_REQUIRED")
    first, fence, ledger, callback = owner.first, owner.fence, owner.resources, owner.cancelled
    limits = owner.local_end, owner.work_limit, owner.final_limit
    binding_raw = launch._json(bindings)
    launch.clocks.validate_reading(first)
    launch.require(first.clock == launch.clocks.ClockIdentity(context["role"],
        launch.clocks.DOMAINS[context["role"]], context["frequency"]) and
        ack.observed_ns <= first.nanoseconds < int(context["hardEndNs"]) and
        any(row["owner"] is directory for row in ledger), "PROVIDER_READBACK_ORIGINAL_OWNER")
    directory_type = launch.files.windows_files.PrivateDirectory if context["role"] == "windows-x64" else launch.files._PosixDirectory
    launch.require(type(directory) is directory_type, "PROVIDER_READBACK_NATIVE_DIRECTORY")
    directory_identity = tuple(context["directoryIdentity"])

    def same():
        launch.require(owner.first is first and owner.fence is fence and owner.resources is ledger and
            owner.cancelled is callback and owner.original is None and not owner.unknown and not owner.closed,
            "PROVIDER_READBACK_OWNER_CHANGED")
        launch.require((owner.local_end, owner.work_limit, owner.final_limit) == limits and
                       launch._json(bindings) == binding_raw, "PROVIDER_READBACK_INPUT_CHANGED")

    def checked():
        same()
        callback()
        same()
        end = owner.end()
        same()
        directory.verify()
        launch.require(str(directory.path) == context["directory"] and
                       tuple(directory.identity) == directory_identity, "PROVIDER_READBACK_DIRECTORY_CHANGED")
        now = launch.clocks.checked_now(first.clock, minimum_ns=checked.last)
        launch.require(now < int(context["hardEndNs"]), "PROVIDER_READBACK_ORIGINAL_END")
        checked.last = now
        callback()
        same()
        owner.end()
        same()
        return end

    checked.last = first.nanoseconds
    originals = []
    references = dict(ack.files)
    for slot, name in (("native", outer.NATIVE_NAME), ("stdout", "provider-stdout.log"),
                       ("stderr", "provider-stderr.log"), ("packet", launch.transport.PACKET_NAME)):
        end = checked()
        reference = references[slot]
        launch.require(type(reference) is outer.FileReference, "PROVIDER_READBACK_FILE_REFERENCE")
        maximum, reader = outer._LIMITS[slot], None
        try:
            reader = owner.acquire("provider-" + slot + "-reader", lambda: (
                directory.open_file(name, max_bytes=maximum, deadline=end) if context["role"] == "windows-x64" else
                launch.files._posix_stream(directory.path / name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, "rb")))
            checked()
            def info():
                return (reader.verify() if context["role"] == "windows-x64" else
                        launch.files._file_info(directory.path / name, reader, maximum))
            before = info()
            launch.require(before.size == reference.size and
                launch.transport.file_identity(before, context["role"]) == reference.identity,
                "PROVIDER_READBACK_FILE_REPLACED")
            checked()
            raw = reader.read(maximum + 1)
            checked()
            launch.require(info() == before and type(raw) is bytes and len(raw) == reference.size and
                hashlib.sha256(raw).hexdigest() == reference.sha256, "PROVIDER_READBACK_FILE_CHANGED")
            originals.append((slot, raw))
            checked()
        except BaseException as error:
            owner.error("provider-readback", error)
            raise
        finally:
            if reader is not None:
                owner.close_one(reader)
        checked()  # Known original reader close is required before interpretation.
    raw_files = dict(originals)
    worker_request = _worker_request(raw_files["native"], request, ack, python, bindings)
    checked()
    worker_ack = launch.transport.read_ack(raw_files["stdout"], worker_request)
    packet_ref = references["packet"]
    launch.require((worker_ack.packet_bytes, worker_ack.packet_sha256, worker_ack.packet_identity) ==
                   (packet_ref.size, packet_ref.sha256, packet_ref.identity), "PROVIDER_READBACK_PACKET_BINDING")
    provider = launch.transport.decode(raw_files["packet"], worker_ack, worker_request, ack.worker_exit_code)
    launch.require(provider.kind == "success" and provider.observed_ns <= ack.observed_ns,
                   "PROVIDER_READBACK_PROVIDER_RETURN")
    checked()
    return ProviderReadback(provider, ack, worker_request, tuple(originals), checked.last)
