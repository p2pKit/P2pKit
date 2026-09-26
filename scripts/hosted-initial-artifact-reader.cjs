'use strict';

// One FIXED credential-free native helper and one demand-driven ZIP stream.
// This is a child/pipe owner, not K authority, service admission or an Action.
// The caller must validate the actual READY/K/BEFORE bindings before bind().
// No helper path, native backend, process factory or clock can be supplied.
const {spawn, ChildProcess} = require('node:child_process');
const {Readable, Writable} = require('node:stream');
const paths = require('node:path');
const {createHash} = require('node:crypto');
const {setTimeout, clearTimeout} = require('node:timers');

const NS = 1000000000n, FRAME = 64 * 1024, RECORD = 16 * 1024, ZIP_LIMIT = 512 * 1024 * 1024;
const path = process.platform === 'win32' ? paths.win32 : paths.posix;
const workspace = path.dirname(__dirname);
const helper = path.join(__dirname, 'run-hosted-initial-recipient-upload.py');
const aborted = Object.getOwnPropertyDescriptor(AbortSignal.prototype, 'aborted').get;
const addAbort = EventTarget.prototype.addEventListener, removeAbort = EventTarget.prototype.removeEventListener;
const IDENTITY = ['GITHUB_ACTIONS', 'GITHUB_REPOSITORY', 'GITHUB_SHA', 'GITHUB_REF', 'GITHUB_RUN_ID',
    'GITHUB_RUN_ATTEMPT', 'GITHUB_EVENT_NAME', 'GITHUB_WORKFLOW_REF', 'GITHUB_WORKFLOW_SHA',
    'GITHUB_WORKSPACE', 'GITHUB_EVENT_PATH', 'GITHUB_SERVER_URL', 'GITHUB_API_URL', 'GITHUB_JOB',
    'RUNNER_OS', 'RUNNER_ARCH', 'RUNNER_NAME', 'RUNNER_ENVIRONMENT', 'RUNNER_TEMP', 'ImageOS', 'ImageVersion'];
const SEED = ['P2PKIT_INITIAL_SEAL_SHA256', 'P2PKIT_INITIAL_SEAL_END_NS', 'P2PKIT_INITIAL_SEAL_CLOCK_ROLE',
    'P2PKIT_INITIAL_SEAL_CLOCK_DOMAIN', 'P2PKIT_INITIAL_SEAL_CLOCK_TICKS_PER_SECOND',
    'P2PKIT_INITIAL_SEAL_BOOT_SHA256', 'P2PKIT_INITIAL_SEAL_OUTCOME',
    'P2PKIT_INITIAL_BEFORE_SHA256', 'P2PKIT_INITIAL_BEFORE_OUTCOME'];
const ANCESTORS = ['P2PKIT_AUDIT_JOB_ID', 'P2PKIT_AUDIT_OWNERSHIP_CHAIN', 'P2PKIT_AUDIT_OWNERSHIP_DOMAINS',
    'P2PKIT_AUDIT_STATE_DIR', 'GRADLE_USER_HOME'];
let used = false, reentered = false, originalFailure = null;
// Failed original children/pipes remain referenced; no delete/reopen/PID retry.
const quarantine = [];

class ReaderError extends Error {}
function need(value, code) {
    if (!value) throw new ReaderError('INITIAL_ARTIFACT_READER_' + code);
}
function data(value, names) {
    need(value !== null && Object.getPrototypeOf(value) === Object.prototype, 'PLAIN_FIELDS');
    const descriptors = Object.getOwnPropertyDescriptors(value);
    need(Reflect.ownKeys(value).length === names.length && names.every(name =>
        Object.hasOwn(descriptors, name) && Object.hasOwn(descriptors[name], 'value') && descriptors[name].enumerable),
    'CLOSED_DATA_FIELDS');
    return Object.freeze(Object.fromEntries(names.map(name => [name, descriptors[name].value])));
}
function absolute(value) {
    return typeof value === 'string' && value.length > 0 && value.length <= 4096 &&
        !/[\x00-\x1f\x7f]/.test(value) && path.isAbsolute(value) && path.normalize(value) === value;
}
function sha(raw) { return createHash('sha256').update(raw).digest('hex'); }
function digest(value) { return typeof value === 'string' && /^[0-9a-f]{64}$/.test(value); }
function uint64(value) {
    return typeof value === 'bigint' && value >= 0n && value <= 18446744073709551615n;
}
function environment(supplied) {
    need(supplied !== null && Object.getPrototypeOf(supplied) === Object.prototype, 'ENVIRONMENT');
    const allowed = ['PATH', 'LANG', 'LC_ALL', 'HOME', 'USERPROFILE', 'TMPDIR', 'TMP', 'TEMP',
        'SYSTEMROOT', 'WINDIR', 'COMSPEC', 'PATHEXT', 'PYTHONDONTWRITEBYTECODE', 'PYTHONUNBUFFERED',
        ...IDENTITY, ...SEED, ...ANCESTORS];
    const names = Reflect.ownKeys(supplied);
    need(names.every(name => typeof name === 'string' && allowed.includes(name)), 'TOKEN_FREE_ENVIRONMENT');
    const env = data(supplied, names);
    need(Object.values(env).every(value => typeof value === 'string' && value.length > 0 &&
        value.length <= 16 * 1024 && !/[\x00\r\n]/.test(value)) &&
        [...IDENTITY, ...SEED, 'PATH', 'LANG', 'LC_ALL', 'PYTHONDONTWRITEBYTECODE', 'PYTHONUNBUFFERED']
            .every(name => Object.hasOwn(env, name)), 'ENVIRONMENT_FIELDS');
    const inherited = ANCESTORS.filter(name => Object.hasOwn(env, name));
    need(inherited.length === 0 || inherited.length === 1 && inherited[0] === 'GRADLE_USER_HOME' ||
        inherited.length === ANCESTORS.length, 'PARTIAL_ANCESTOR_CONTEXT');
    need(env.GITHUB_WORKSPACE === workspace && env.LANG === 'C' && env.LC_ALL === 'C' &&
        env.PYTHONDONTWRITEBYTECODE === '1' && env.PYTHONUNBUFFERED === '1', 'ENVIRONMENT_CONTEXT');
    // Actual hosted/source/boot/recipient claims are independently checked by
    // the fixed helper. A supplied environment map alone authenticates nothing.
    return Object.assign({}, env);
}

function openReader(supplied) {
    let options, env, preSpawnNs;
    try {
        if (used) {
            reentered = true;
            const error = new ReaderError('INITIAL_ARTIFACT_READER_ONE_INVOCATION');
            if (originalFailure !== null) originalFailure(error);
            throw error;
        }
        used = true;
        options = data(supplied, ['python', 'kind', 'environment', 'signal']);
        need(/^24\./.test(process.versions.node), 'NODE24_REQUIRED');
        need(options.kind === 'gate' || options.kind === 'worker', 'KIND');
        need(absolute(options.python) && /^python(?:3(?:\.\d+)?)?(?:\.exe)?$/.test(path.basename(options.python)),
            'FIXED_PYTHON');
        need(!Reflect.apply(aborted, options.signal, []), 'CANCELLED');
        env = environment(options.environment);
        preSpawnNs = process.hrtime.bigint();
        need(!reentered, 'ONE_INVOCATION');
        need(uint64(preSpawnNs), 'LOCAL_CLOCK');
    } catch (error) {
        throw error instanceof ReaderError ? error : new ReaderError('INITIAL_ARTIFACT_READER_INVALID_INPUT');
    }

    let child = null, pipes = null, timer = null, failed = null, settled = false, released = false;
    let readyRaw = null, finalRaw = null, buffer = Buffer.alloc(0), pending = null, finalData = null;
    let inputEndRequested = false, inputEndCallback = false, spawned = false, exited = false, childClosed = false;
    let stdinFinished = false, stdoutEnded = false, stderrEnded = false, stderrBytes = 0;
    const pipeClosed = {stdin: false, stdout: false, stderr: false};
    let lastNs = preSpawnNs, closeEndNs = preSpawnNs + 60n * NS, workEndNs = null, bounds = null;
    let receivedBytes = 0, observedZipSha256 = null, closeNs = null, readySettled = false;
    const zipHash = createHash('sha256');
    const retained = {child: null, pipes: null, errors: []};
    let acceptReady, rejectReady, acceptCompletion;
    const ready = new Promise((resolve, reject) => { acceptReady = resolve; rejectReady = reject; });
    const completion = new Promise(resolve => { acceptCompletion = resolve; });

    function observe(work = false) {
        const now = process.hrtime.bigint();
        need(uint64(now) && now >= lastNs && now < (work && workEndNs !== null ? workEndNs : closeEndNs),
            'ORIGINAL_DEADLINE');
        lastNs = now;
        need(failed === null && !reentered && !settled && !Reflect.apply(aborted, options.signal, []),
            'FAILED_OR_CANCELLED');
        return now;
    }
    function knownClosed() {
        return childClosed && pipes !== null && Object.values(pipeClosed).every(value => value);
    }
    function summary(success) {
        return Object.freeze({scope: 'INITIAL_ARTIFACT_FIXED_READER_TRANSPORT_ONLY',
            transport: success ? 'closed' : 'incomplete', code: failed,
            preSpawnLocalNs: preSpawnNs.toString(), returnedLocalNs: lastNs.toString(),
            originalChildCloseObserved: childClosed, originalExitZeroObserved: exited,
            stdinFinishObserved: stdinFinished, stdinEndCallbackObserved: inputEndCallback,
            stdoutEndObserved: stdoutEnded, stderrEndObserved: stderrEnded,
            originalPipeCloses: Object.freeze({...pipeClosed}), stderrBytes,
            readySha256: readyRaw === null ? null : sha(readyRaw),
            finalSha256: finalRaw === null ? null : sha(finalRaw),
            zipBytes: receivedBytes, zipSha256: observedZipSha256,
            nativeFileRetirement: 'FIXED_HELPER_RETURN_REQUIRES_CALLER_VALIDATION',
            originalStepOutcome: 'NOT_OBSERVED', qualification: 'NOT_ESTABLISHED'});
    }
    function settle(success) {
        if (settled) return;
        settled = true;
        clearTimeout(timer);
        Reflect.apply(removeAbort, options.signal, ['abort', cancel]);
        if (!knownClosed()) quarantine.push(retained);
        if (!readySettled) {
            readySettled = true;
            rejectReady(new ReaderError(failed || 'INITIAL_ARTIFACT_READER_NO_READY'));
        }
        acceptCompletion(summary(success));
    }
    function endInput() {
        if (inputEndRequested || pipes === null) return;
        inputEndRequested = true; // Original handle, once, before fallible .end().
        try {
            pipes.stdin.end(error => {
                if (error) fail(error);
                else event(() => { observe(); inputEndCallback = true; progress(); });
            });
        } catch (error) { fail(error); }
    }
    function fail(error) {
        if (settled) return;
        if (failed === null) failed = error instanceof ReaderError ? error.message :
            'INITIAL_ARTIFACT_READER_OPERATION_FAILED';
        if (retained.errors.length < 8) retained.errors.push(error);
        if (!readySettled) { readySettled = true; rejectReady(new ReaderError(failed)); }
        endInput(); // EOF is cooperative cancellation on ALL hosts; no Windows kill(SIGTERM).
        if (!stream.destroyed) stream.destroy(new ReaderError(failed));
        if (knownClosed()) settle(false);
    }
    function event(action) {
        if (settled) return;
        try { action(); } catch (error) { fail(error); }
    }
    function cancel() { fail(new ReaderError('INITIAL_ARTIFACT_READER_CANCELLED')); }
    function armTimer() {
        clearTimeout(timer);
        const remaining = closeEndNs - process.hrtime.bigint();
        timer = setTimeout(() => {
            fail(new ReaderError('INITIAL_ARTIFACT_READER_ORIGINAL_DEADLINE'));
            settle(false);
        }, Math.max(1, Number((remaining + 999999n) / 1000000n)));
    }
    function finalRecord(raw) {
        need(!raw.some(value => value > 127), 'FINAL_ASCII');
        const value = JSON.parse(raw.toString('ascii'));
        const names = ['schema', 'scope', 'beforeSha256', 'readySha256', 'zipBytes', 'zipSha256',
            'nativeCloseSha256', 'closedNs', 'nativeFileRetirement', 'originalReaderOutcome', 'qualification'];
        const row = data(value, names);
        const canonical = JSON.stringify(Object.fromEntries([...names].sort().map(name => [name, row[name]]))) + '\n';
        need(Buffer.from(canonical, 'ascii').equals(raw), 'FINAL_CANONICAL');
        need(row.schema === 1 && row.scope === 'INITIAL_ARTIFACT_NATIVE_STREAM_CLOSED_FILES_PENDING_PROCESS_V1' &&
            row.beforeSha256 === bounds.beforeSha256 && row.readySha256 === sha(readyRaw) &&
            Number.isSafeInteger(row.zipBytes) && row.zipBytes === bounds.zipBytes && receivedBytes === row.zipBytes &&
            digest(row.zipSha256) && digest(row.nativeCloseSha256) &&
            row.nativeFileRetirement === 'KNOWN_NATIVE_CLOSE' &&
            row.originalReaderOutcome === 'PENDING_ENCLOSING_PROCESS_CLOSE' &&
            row.qualification === 'NOT_ESTABLISHED', 'FINAL_BINDING');
        need(typeof row.closedNs === 'string' && /^(0|[1-9][0-9]{0,19})$/.test(row.closedNs) &&
            uint64(BigInt(row.closedNs)) && BigInt(row.closedNs) >= bounds.firstRawNs &&
            BigInt(row.closedNs) < bounds.firstRawNs + workEndNs - preSpawnNs, 'FINAL_RAW_FENCE');
        observedZipSha256 = zipHash.digest('hex');
        need(row.zipSha256 === observedZipSha256, 'FINAL_OBSERVED_ZIP');
        return row;
    }
    function progress() {
        if (failed !== null) { if (knownClosed()) settle(false); return; }
        if (!knownClosed()) return;
        // Independent pipe events may precede the original N callback. Only a
        // COMPLETE retained final frame may wait here; EOF alone grants nothing.
        if (pending !== null && !pending.written && pending.frame !== null && pending.frame.kind === 'F') return;
        event(() => {
            observe(true);
            need(spawned && exited && stdinFinished && inputEndCallback && stdoutEnded && stderrEnded &&
                stderrBytes === 0 && finalData !== null && finalRaw !== null && pending === null &&
                buffer.length === 0 && released, 'INCOMPLETE_ORIGINAL_CLOSE');
            closeNs = lastNs;
            settle(true);
            // Native return alone did NOT expose EOF. Actual original process
            // exit/close and all three pipe closes are now known before EOF.
            stream.push(null);
        });
    }
    function deliver() {
        if (pending === null || !pending.written || pending.frame === null) return;
        event(() => {
            observe(true);
            const {kind, raw} = pending.frame;
            pending = null; // No reentrant demand can consume the old command.
            if (kind === 'D') {
                need(receivedBytes + raw.length <= bounds.zipBytes, 'ZIP_OVERRUN');
                receivedBytes += raw.length; zipHash.update(raw);
                stream.push(raw);
            } else {
                need(kind === 'F' && finalRaw === null, 'FINAL_ONCE');
                finalData = finalRecord(raw); finalRaw = raw;
                endInput();
            }
            progress();
        });
    }
    function frame(kind, raw) {
        observe(true);
        // Node may report child exit before it drains that child's final pipe
        // bytes. ChildProcess close, not exit, is the terminal I/O boundary.
        need(spawned && !stdoutEnded && !childClosed, 'FRAME_LIFETIME');
        if (readyRaw === null) {
            need(kind === 'R' && pending === null && !released, 'READY_FIRST');
            readyRaw = raw; readySettled = true;
            acceptReady(Object.freeze({raw: Buffer.from(raw), preSpawnLocalNs: preSpawnNs}));
            return;
        }
        need(released && pending !== null && pending.frame === null && finalRaw === null &&
            (kind === 'D' || kind === 'F'), 'FRAME_WITHOUT_DEMAND');
        pending.frame = {kind, raw};
        deliver();
    }
    function stdout(raw) {
        event(() => {
            observe(true);
            need(Buffer.isBuffer(raw) && raw.length > 0 && !(raw.buffer instanceof SharedArrayBuffer) &&
                buffer.length + raw.length <= FRAME + 5, 'PIPE_FRAME_BOUND');
            buffer = Buffer.concat([buffer, Buffer.from(raw)]);
            if (buffer.length < 5) return;
            const kind = String.fromCharCode(buffer[0]), count = buffer.readUInt32BE(1);
            need(['R', 'D', 'F'].includes(kind) && count > 0 && count <= (kind === 'D' ? FRAME : RECORD),
                'FRAME_HEADER');
            need(buffer.length <= count + 5, 'PREFETCH_OR_TRAILING_FRAME');
            if (buffer.length < count + 5) return;
            const complete = Buffer.from(buffer.subarray(5));
            buffer = Buffer.alloc(0);
            frame(kind, complete);
        });
    }
    const stream = new Readable({highWaterMark: 0, autoDestroy: true, emitClose: true,
        read() {
            event(() => {
                observe(true);
                need(released && readyRaw !== null && pending === null && finalRaw === null &&
                    pipes !== null && !inputEndRequested, 'DEMAND_STATE');
                const command = {written: false, frame: null};
                pending = command; // Register demand before any pipe callback.
                pipes.stdin.write(Buffer.from('N', 'ascii'), error => event(() => {
                    if (error) throw error;
                    observe(true);
                    need(pending === command && !command.written, 'DEMAND_WRITE_ONCE');
                    command.written = true; deliver();
                }));
            });
        },
        destroy(error, done) {
            if (!settled && failed === null) fail(error || new ReaderError('INITIAL_ARTIFACT_READER_INPUT_CANCELLED'));
            done(error);
        }});
    // Passive only: never data/readable listeners or any input read/prefetch.
    originalFailure = fail;
    stream.on('error', () => {});
    Reflect.apply(addAbort, options.signal, ['abort', cancel, {once: true}]);
    armTimer();
    try {
        observe();
        child = spawn(options.python, ['-I', '-B', '-S', helper, 'stream', '--kind', options.kind],
            {cwd: workspace, env, shell: false, detached: false, windowsHide: false, stdio: ['pipe', 'pipe', 'pipe']});
        retained.child = child; // Original returned handle precedes callbacks.
        child.on('error', fail);
        child.on('spawn', () => event(() => {
            observe(); need(!spawned && !exited && !childClosed, 'SPAWN_ORDER'); spawned = true;
        }));
        child.on('exit', (code, signal) => event(() => {
            observe(); need(spawned && !exited && !childClosed && code === 0 && !Object.is(code, -0) &&
                signal === null, 'ORIGINAL_EXIT'); exited = true;
        }));
        child.on('close', (code, signal) => {
            const duplicate = childClosed; childClosed = true;
            if (failed === null) event(() => {
                observe(); need(!duplicate && exited && code === 0 && !Object.is(code, -0) &&
                    signal === null, 'ORIGINAL_CHILD_CLOSE');
            });
            progress();
        });
        pipes = {stdin: child.stdin, stdout: child.stdout, stderr: child.stderr};
        retained.pipes = pipes; // Retain the exact three returned pipe handles.
        for (const [name, pipe] of Object.entries(pipes)) {
            pipe.on('error', fail);
            pipe.on('close', () => {
                const duplicate = pipeClosed[name]; pipeClosed[name] = true;
                if (failed === null) event(() => { observe(); need(!duplicate, 'DUPLICATE_PIPE_CLOSE'); });
                progress();
            });
        }
        need(child instanceof ChildProcess && pipes.stdin instanceof Writable && pipes.stdout instanceof Readable &&
            pipes.stderr instanceof Readable && new Set(Object.values(pipes)).size === 3 &&
            !pipes.stdout.readableObjectMode && !pipes.stderr.readableObjectMode &&
            pipes.stdout.readableEncoding === null && pipes.stderr.readableEncoding === null, 'ORIGINAL_CHILD_PIPES');
        pipes.stdin.on('finish', () => event(() => {
            observe(); need(inputEndRequested && !stdinFinished, 'STDIN_FINISH'); stdinFinished = true; progress();
        }));
        pipes.stdout.on('data', stdout);
        pipes.stdout.on('end', () => event(() => {
            const waitingFinal = pending !== null && !pending.written && pending.frame !== null &&
                pending.frame.kind === 'F';
            observe(); need(!stdoutEnded && buffer.length === 0 &&
                (finalRaw !== null && pending === null || waitingFinal),
                'STDOUT_PREMATURE_EOF'); stdoutEnded = true; progress();
        }));
        pipes.stderr.on('data', raw => event(() => {
            observe(); need(Buffer.isBuffer(raw) && !(raw.buffer instanceof SharedArrayBuffer) &&
                stderrBytes + raw.length <= RECORD, 'STDERR_BOUND');
            stderrBytes += raw.length;
            need(stderrBytes === 0, 'HELPER_DIAGNOSTIC'); // Never print raw stderr.
        }));
        pipes.stderr.on('end', () => event(() => {
            observe(); need(!stderrEnded, 'STDERR_END_ONCE'); stderrEnded = true; progress();
        }));
    } catch (error) { fail(error); }

    function bind(suppliedBounds) {
        try {
            observe();
            need(!released && readyRaw !== null && finalRaw === null && pending === null &&
                stream.readableLength === 0 && !stream.readableDidRead && !stream.destroyed, 'BIND_ONCE_BEFORE_DEMAND');
            const row = data(suppliedBounds, ['readySha256', 'beforeSha256', 'firstRawNs', 'sealEndNs',
                'uploadEndNs', 'zipBytes']);
            need(row.readySha256 === sha(readyRaw) && digest(row.beforeSha256) &&
                [row.firstRawNs, row.sealEndNs, row.uploadEndNs].every(uint64) &&
                row.firstRawNs < row.sealEndNs && row.sealEndNs < row.uploadEndNs &&
                Number.isSafeInteger(row.zipBytes) && row.zipBytes > 0 && row.zipBytes <= ZIP_LIMIT, 'BIND_FIELDS');
            const startByNs = preSpawnNs + row.sealEndNs - row.firstRawNs;
            const mappedEnd = preSpawnNs + row.uploadEndNs - row.firstRawNs;
            closeEndNs = mappedEnd < closeEndNs ? mappedEnd : closeEndNs;
            workEndNs = closeEndNs - 5n * NS;
            need(lastNs < startByNs && startByNs < workEndNs && workEndNs < closeEndNs &&
                closeEndNs <= preSpawnNs + 60n * NS, 'ORIGINAL_DIRECTED_MAPPING');
            bounds = row; released = true;
            armTimer(); observe(true);
            return Object.freeze({startByNs, workEndNs, closeEndNs});
        } catch (error) {
            fail(error);
            throw new ReaderError(failed || 'INITIAL_ARTIFACT_READER_BIND_FAILED');
        }
    }
    return Object.freeze({ready, stream, bind, completion, cancel,
        finalFrame: () => {
            need(settled && failed === null && knownClosed() && closeNs !== null && finalRaw !== null,
                'NO_KNOWN_RETURN');
            return Buffer.from(finalRaw);
        }});
}

module.exports = Object.freeze({openReader});
