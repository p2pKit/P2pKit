'use strict';

// Fixed one-shot U/A composition. DATA does not create a native/HTTP owner.
// No caller-selected helper, endpoint, clock, process or acceptance fallback.
// Existing activation HOLDs and independent hosted qualification still apply.
const {spawn, ChildProcess} = require('node:child_process');
const {Readable, Writable} = require('node:stream');
const fs = require('node:fs');
const paths = require('node:path');
const {setTimeout, clearTimeout} = require('node:timers');
const D = require('./hosted-initial-artifact-action-data.cjs');
const ProductiveData = require('./hosted-initial-artifact-productive-action-data.cjs');
const Reader = require('./hosted-initial-artifact-reader.cjs');
const Observer = require('./hosted-initial-artifact-observer.cjs');
const Transport = require('./hosted-initial-artifact-transport.cjs');

const NS = 1000000000n, RECORD = 16384, INPUT = 2097152;
const windows = process.platform === 'win32', path = windows ? paths.win32 : paths.posix;
const workspace = path.dirname(__dirname), helper = path.join(__dirname, 'run-hosted-initial-recipient-upload.py');
const aborted = Object.getOwnPropertyDescriptor(AbortSignal.prototype, 'aborted').get;
const addAbort = EventTarget.prototype.addEventListener, removeAbort = EventTarget.prototype.removeEventListener;
const IDENTITY = Object.freeze(['GITHUB_ACTIONS', 'GITHUB_REPOSITORY', 'GITHUB_SHA', 'GITHUB_REF', 'GITHUB_RUN_ID',
    'GITHUB_RUN_ATTEMPT', 'GITHUB_EVENT_NAME', 'GITHUB_WORKFLOW_REF', 'GITHUB_WORKFLOW_SHA',
    'GITHUB_WORKSPACE', 'GITHUB_EVENT_PATH', 'GITHUB_SERVER_URL', 'GITHUB_API_URL', 'GITHUB_JOB',
    'RUNNER_OS', 'RUNNER_ARCH', 'RUNNER_NAME', 'RUNNER_ENVIRONMENT', 'RUNNER_TEMP', 'ImageOS', 'ImageVersion']);
const SEED = Object.freeze(['P2PKIT_INITIAL_SEAL_SHA256', 'P2PKIT_INITIAL_SEAL_END_NS', 'P2PKIT_INITIAL_SEAL_CLOCK_ROLE',
    'P2PKIT_INITIAL_SEAL_CLOCK_DOMAIN', 'P2PKIT_INITIAL_SEAL_CLOCK_TICKS_PER_SECOND',
    'P2PKIT_INITIAL_SEAL_BOOT_SHA256', 'P2PKIT_INITIAL_SEAL_OUTCOME',
    'P2PKIT_INITIAL_BEFORE_SHA256', 'P2PKIT_INITIAL_BEFORE_OUTCOME']);
const UPLOAD = Object.freeze(['P2PKIT_INITIAL_UPLOAD_SHA256', 'P2PKIT_INITIAL_UPLOAD_DIRECTORY_SHA256',
    'P2PKIT_INITIAL_UPLOAD_FILE_METADATA_SHA256', 'P2PKIT_INITIAL_UPLOAD_OWNER_CLOSE_SHA256', 'P2PKIT_INITIAL_UPLOAD_OUTCOME']);
const LEGACY_ROUTE = Object.freeze({data: D, helper, productive: false, seed: SEED, upload: UPLOAD,
    openReader: Reader.openReader, startField: 'sealEndNs', boundsField: 'originalWindow'});
const PRODUCTIVE_ROUTE = Object.freeze({data: ProductiveData,
    helper: path.join(__dirname, 'run-hosted-initial-recipient-productive-upload.py'), productive: true,
    seed: Object.freeze(['P2PKIT_INITIAL_PRODUCTIVE_BEFORE_SHA256', 'P2PKIT_INITIAL_PRODUCTIVE_BEFORE_OUTCOME',
        'P2PKIT_INITIAL_PRODUCTIVE_DEADLINE_SHA256', 'P2PKIT_INITIAL_PRODUCTIVE_DEADLINE_BASE64',
        'P2PKIT_INITIAL_PRODUCTIVE_SEAL_OUTCOME']),
    upload: Object.freeze(['P2PKIT_INITIAL_PRODUCTIVE_UPLOAD_SHA256','P2PKIT_INITIAL_PRODUCTIVE_UPLOAD_DIRECTORY_SHA256',
        'P2PKIT_INITIAL_PRODUCTIVE_UPLOAD_FILE_METADATA_SHA256','P2PKIT_INITIAL_PRODUCTIVE_UPLOAD_OWNER_CLOSE_SHA256',
        'P2PKIT_INITIAL_PRODUCTIVE_UPLOAD_OUTCOME']), openReader: Reader.openProductiveReader,
    startField: 'uploadStartByNs', boundsField: 'deadline'});
const ANCESTORS = Object.freeze(['P2PKIT_AUDIT_JOB_ID', 'P2PKIT_AUDIT_OWNERSHIP_CHAIN', 'P2PKIT_AUDIT_OWNERSHIP_DOMAINS',
    'P2PKIT_AUDIT_STATE_DIR', 'GRADLE_USER_HOME']);
const NATIVE = Object.freeze(['SYSTEMROOT', 'WINDIR', 'COMSPEC', 'PATHEXT']);
const FORBIDDEN = Object.freeze(['GH_TOKEN', 'GITHUB_TOKEN', 'P2PKIT_ACTIONS_READ_TOKEN']);
let used = false, reentered = false, originalFailure = null;
// UNKNOWN original resources/errors stay privately reachable. Never replace,
// reopen, remove or print them merely because a finite command has failed.
const quarantine = [];

class ActionError extends Error {}
function need(value, code) { if (!value) throw new ActionError('INITIAL_ARTIFACT_ACTION_' + code); }
function absolute(value) {
    return typeof value === 'string' && value.length > 0 && value.length <= 4096 &&
        !/[\x00-\x1f\x7f]/.test(value) && path.isAbsolute(value) && path.normalize(value) === value;
}
function safeString(value) {
    return typeof value === 'string' && value.length > 0 && value.length <= 16384 && !/[\x00\r\n]/.test(value);
}
function min(left, right) { return left < right ? left : right; }
function frame(kind, raw) {
    D.bytes(raw, kind === 'I' ? INPUT - 5 : RECORD);
    const header = Buffer.alloc(5); header[0] = kind.charCodeAt(0); header.writeUInt32BE(raw.length, 1);
    return Buffer.concat([header, raw]);
}

function openFinite({mode, python, kind, environment, signal, originalEndNs, checkpoint, poison}, route) {
    const D = route.data, helper = route.helper;
    // Private fixed finish/after process owner. The public Action exports no
    // handle factory; these arguments come only from its one original chain.
    need(mode === 'finish' || mode === 'after', 'FINITE_MODE');
    const preSpawnLocalNs = D.integer(process.hrtime.bigint());
    let endNs = mode === 'after' ? D.integer(preSpawnLocalNs + 15n * NS) : D.integer(originalEndNs);
    need(preSpawnLocalNs < endNs && (mode === 'after' || originalEndNs === endNs), 'FINITE_ORIGINAL_END');
    const retained = {child: null, pipes: null, errors: [], input: null, ready: null, final: null};
    let child = null, pipes = null, lastNs = preSpawnLocalNs, timer = null, failed = null, settled = false;
    let bound = mode === 'finish', readyRaw = null, finalRaw = null, buffer = Buffer.alloc(0), readySettled = false;
    let spawned = false, exited = false, childClosed = false, inputRequested = false, inputWritten = false;
    let inputEndRequested = false, inputEndCallback = false, stdinFinished = false, stdoutEnded = false, stderrEnded = false;
    let stderrBytes = 0, acceptReady, rejectReady, acceptCompletion;
    const closed = {stdin: false, stdout: false, stderr: false};
    const ready = new Promise((resolve, reject) => { acceptReady = resolve; rejectReady = reject; });
    const completion = new Promise(resolve => { acceptCompletion = resolve; });
    ready.catch(() => {}); // A failed finish has no READY consumer.

    function observe() {
        const now = D.integer(process.hrtime.bigint());
        need(now >= lastNs && now < endNs, 'FINITE_ORIGINAL_DEADLINE'); lastNs = now;
        need(failed === null && !settled && !Reflect.apply(aborted, signal, []), 'FINITE_FAILED_OR_CANCELLED');
        checkpoint(endNs); return now;
    }
    function knownClosed() { return childClosed && pipes !== null && Object.values(closed).every(value => value); }
    function settle(success) {
        if (settled) return;
        settled = true; clearTimeout(timer);
        Reflect.apply(removeAbort, signal, ['abort', cancel]);
        if (!knownClosed()) quarantine.push(retained);
        if (!readySettled) {
            readySettled = true;
            rejectReady(new ActionError(failed || 'INITIAL_ARTIFACT_ACTION_FINITE_NO_READY'));
        }
        acceptCompletion(Object.freeze({transport: success ? 'closed' : 'incomplete', code: failed,
            preSpawnLocalNs, returnedLocalNs: lastNs, inputWriteCallbackObserved: inputWritten,
            stdinEndCallbackObserved: inputEndCallback, stdinFinishObserved: stdinFinished,
            stdoutEndObserved: stdoutEnded, stderrEndObserved: stderrEnded, stderrBytes,
            originalExitZeroObserved: exited, originalChildCloseObserved: childClosed,
            originalPipeCloses: Object.freeze({...closed})}));
    }
    function endInput() {
        if (inputEndRequested || pipes === null || pipes.stdin === null) return;
        inputEndRequested = true; // Mark original effect before fallible call.
        try {
            pipes.stdin.end(error => {
                if (error) fail(error);
                else guarded(() => {
                    observe(); need(!inputEndCallback, 'FINITE_END_CALLBACK_ONCE'); inputEndCallback = true; progress();
                });
            });
        } catch (error) { fail(error); }
    }
    function fail(error) {
        if (retained.errors.length < 8) retained.errors.push(error);
        if (failed === null) {
            failed = error instanceof ActionError ? error.message : 'INITIAL_ARTIFACT_ACTION_FINITE_OPERATION_FAILED';
            poison(error); // Restoration or an apparently good later F cannot clear the original failure.
        }
        if (!readySettled) { readySettled = true; rejectReady(new ActionError(failed)); }
        endInput(); // Cooperative EOF on every host, not Windows kill(SIGTERM).
        if (!settled && knownClosed()) settle(false);
    }
    function guarded(operation) {
        if (settled || failed !== null) return;
        try { operation(); } catch (error) { fail(error); }
    }
    function cancel() { fail(new ActionError('INITIAL_ARTIFACT_ACTION_FINITE_CANCELLED')); }
    function arm() {
        clearTimeout(timer);
        const remaining = endNs - D.integer(process.hrtime.bigint());
        timer = setTimeout(() => {
            fail(new ActionError('INITIAL_ARTIFACT_ACTION_FINITE_ORIGINAL_DEADLINE')); settle(false);
        }, Math.max(1, Number((remaining + 999999n) / 1000000n)));
    }
    function progress() {
        if (settled) return;
        if (failed !== null) { if (knownClosed()) settle(false); return; }
        if (!knownClosed()) return;
        // Complete frame and real pipe EOF may precede the corresponding
        // writable callbacks. Join the original events, never synthesize one.
        if (!inputWritten || !inputEndCallback || !stdinFinished) return;
        guarded(() => {
            observe();
            need(spawned && exited && inputRequested && inputEndRequested && stdoutEnded && stderrEnded &&
                stderrBytes === 0 && buffer.length === 0 && finalRaw !== null && bound &&
                (mode === 'finish' ? readyRaw === null : readyRaw !== null), 'FINITE_COMPLETE_ORIGINAL_CLOSE');
            settle(true);
        });
    }
    function acceptFrame(tag, raw) {
        observe(); need(spawned && !stdoutEnded && !childClosed, 'FINITE_FRAME_LIFETIME');
        if (tag === 'R') {
            need(mode === 'after' && readyRaw === null && finalRaw === null && !bound && !inputRequested,
                'FINITE_READY_ONCE_FIRST');
            readyRaw = raw; retained.ready = raw; readySettled = true;
            acceptReady(Object.freeze({raw: Buffer.from(raw), preSpawnLocalNs}));
        } else {
            need(tag === 'F' && finalRaw === null && bound && inputRequested && inputEndRequested &&
                (mode === 'finish' || readyRaw !== null), 'FINITE_FINAL_AFTER_INPUT');
            finalRaw = raw; retained.final = raw;
        }
        progress();
    }
    function stdout(raw) {
        guarded(() => {
            observe();
            need(Buffer.isBuffer(raw) && raw.length > 0 && !(raw.buffer instanceof SharedArrayBuffer) &&
                buffer.length + raw.length <= RECORD + 5 && finalRaw === null, 'FINITE_FRAME_BOUND');
            buffer = Buffer.concat([buffer, Buffer.from(raw)]);
            if (buffer.length < 5) return;
            const tag = String.fromCharCode(buffer[0]), size = buffer.readUInt32BE(1);
            need((tag === 'R' && mode === 'after' || tag === 'F') && size > 0 && size <= RECORD &&
                buffer.length <= size + 5, 'FINITE_FRAME_HEADER');
            if (buffer.length < size + 5) return;
            const complete = Buffer.from(buffer.subarray(5)); buffer = Buffer.alloc(0);
            acceptFrame(tag, complete);
        });
    }
    Reflect.apply(addAbort, signal, ['abort', cancel, {once: true}]);
    arm();
    try {
        observe();
        child = spawn(python, ['-I', '-B', '-S', helper, mode, '--kind', kind],
            {cwd: workspace, env: environment, shell: false, detached: false, windowsHide: false,
                stdio: ['pipe', 'pipe', 'pipe']});
        retained.child = child;
        // Pin child and EACH returned pipe before any fallible listener/brand
        // operation. A partial setup failure retains all originals received.
        pipes = {stdin: null, stdout: null, stderr: null}; retained.pipes = pipes;
        for (const name of ['stdin', 'stdout', 'stderr']) pipes[name] = child[name];
        child.on('error', fail);
        child.on('spawn', () => guarded(() => {
            observe(); need(!spawned && !exited && !childClosed, 'FINITE_SPAWN_ORDER'); spawned = true;
        }));
        child.on('exit', (code, signalName) => guarded(() => {
            observe(); need(spawned && !exited && !childClosed && code === 0 && !Object.is(code, -0) &&
                signalName === null, 'FINITE_ORIGINAL_EXIT'); exited = true;
        }));
        child.on('close', (code, signalName) => {
            const duplicate = childClosed; childClosed = true;
            guarded(() => {
                observe(); need(!duplicate && exited && code === 0 && !Object.is(code, -0) && signalName === null,
                    'FINITE_ORIGINAL_CHILD_CLOSE');
            });
            progress();
        });
        for (const [name, pipe] of Object.entries(pipes)) {
            pipe.on('error', fail);
            pipe.on('close', () => {
                const duplicate = closed[name]; closed[name] = true;
                guarded(() => { observe(); need(!duplicate, 'FINITE_DUPLICATE_PIPE_CLOSE'); }); progress();
            });
        }
        need(child instanceof ChildProcess && pipes.stdin instanceof Writable && pipes.stdout instanceof Readable &&
            pipes.stderr instanceof Readable && new Set(Object.values(pipes)).size === 3 &&
            !pipes.stdout.readableObjectMode && !pipes.stderr.readableObjectMode &&
            pipes.stdout.readableEncoding === null && pipes.stderr.readableEncoding === null, 'FINITE_ORIGINAL_PIPES');
        pipes.stdin.on('finish', () => guarded(() => {
            observe(); need(inputEndRequested && !stdinFinished, 'FINITE_STDIN_FINISH'); stdinFinished = true; progress();
        }));
        pipes.stdout.on('data', stdout);
        pipes.stdout.on('end', () => guarded(() => {
            observe(); need(!stdoutEnded && finalRaw !== null && buffer.length === 0, 'FINITE_STDOUT_EOF');
            stdoutEnded = true; progress();
        }));
        pipes.stderr.on('data', raw => guarded(() => {
            observe(); need(Buffer.isBuffer(raw) && !(raw.buffer instanceof SharedArrayBuffer) &&
                stderrBytes + raw.length <= RECORD, 'FINITE_STDERR_BOUND');
            stderrBytes += raw.length; need(stderrBytes === 0, 'FINITE_PRIVATE_DIAGNOSTIC');
        }));
        pipes.stderr.on('end', () => guarded(() => {
            observe(); need(!stderrEnded, 'FINITE_STDERR_END_ONCE'); stderrEnded = true; progress();
        }));
    } catch (error) { fail(error); }

    return Object.freeze({ready, completion, preSpawnLocalNs, cancel,
        bindAfter(proposed) {
            try {
                observe(); need(mode === 'after' && readyRaw !== null && !bound && !inputRequested, 'FINITE_BIND_ONCE');
                bound = true;
                const next = D.integer(proposed);
                need(lastNs < next && next <= endNs, 'FINITE_NO_EXTENSION'); endNs = next;
                arm(); observe();
            } catch (error) { fail(error); throw new ActionError(failed); }
        },
        input(raw) {
            try {
                observe(); need(bound && !inputRequested && !inputEndRequested && pipes !== null, 'FINITE_INPUT_ONCE');
                // Full canonical I preflight precedes the FIRST write; never
                // stream a prefix then discover that the second original overflows.
                const wire = frame('I', D.bytes(raw, INPUT - 5)); retained.input = wire;
                inputRequested = true;
                pipes.stdin.write(wire, error => {
                    if (error) fail(error);
                    else guarded(() => {
                        observe(); need(!inputWritten, 'FINITE_WRITE_CALLBACK_ONCE'); inputWritten = true; progress();
                    });
                });
                endInput(); observe();
            } catch (error) { fail(error); throw new ActionError(failed); }
        },
        finalFrame() {
            need(settled && failed === null && knownClosed() && finalRaw !== null, 'FINITE_NO_KNOWN_RETURN');
            return Buffer.from(finalRaw);
        }});
}

async function mainFixed(route) {
    const D = route.data, SEED = route.seed, UPLOAD = route.upload;
    process.exitCode = 125; // A pending/rejected chain never silently succeeds.
    if (used) {
        reentered = true;
        if (originalFailure !== null) originalFailure(new ActionError('INITIAL_ARTIFACT_ACTION_ONE_INVOCATION'));
        process.stderr.write('INITIAL_ARTIFACT_ACTION_NOT_ACCEPTED\n'); return;
    }
    used = true;
    const retained = {reader: null, observer: null, transport: null, finite: null, originals: [], errors: []};
    const control = new AbortController(), signal = control.signal, pins = [], bytePins = [], completions = [];
    let failed = null, quarantined = false, lastNs = null, endNs = null, timer = null, validity = null, utcFence = null;
    let originalEnvironment = null, signalsInstalled = false;
    const signals = ['SIGINT', 'SIGTERM', ...(windows ? ['SIGBREAK'] : [])];
    function fail(error) {
        process.exitCode = 125;
        if (retained.errors.length < 8) retained.errors.push(error);
        if (failed === null) failed = 'INITIAL_ARTIFACT_ACTION_NOT_ACCEPTED';
        if (!quarantined) { quarantined = true; quarantine.push(retained); }
        if (!Reflect.apply(aborted, signal, [])) control.abort();
    }
    originalFailure = fail;
    function cancel() { fail(new ActionError('INITIAL_ARTIFACT_ACTION_CANCELLED')); }
    function pin(value, maximum = INPUT) {
        retained.originals.push(value); // Original object BEFORE fallible DATA traversal.
        const raw = D.encode(value, maximum); pins.push({value, raw, maximum}); return value;
    }
    function pinBytes(raw, maximum) {
        retained.originals.push(raw);
        D.bytes(raw, maximum); bytePins.push({raw, copy: Buffer.from(raw), maximum}); return raw;
    }
    function pinHandle(owner, names) {
        retained.originals.push(owner);
        const original = D.fields(owner, names);
        pins.push({verify: () => {
            const current = D.fields(owner, names);
            need(names.every(name => current[name] === original[name]), 'ORIGINAL_RETURN_HANDLE_CHANGED');
        }});
        return original;
    }
    function pinRows(rows) {
        retained.originals.push(rows);
        for (const original of D.array(rows, 1, 2)) {
            retained.originals.push(original);
            const row = D.fields(original, ['kind', 'id', 'body', 'rawHeaderVector']);
            pinBytes(row.body, 1048576); pin(row.rawHeaderVector);
            // Bind the original row references too; a copied/equal later DTO
            // never substitutes the body/vector returned by this observer.
            const originalBody = row.body, originalVector = row.rawHeaderVector;
            pins.push({verify: () => {
                const current = D.fields(original, ['kind', 'id', 'body', 'rawHeaderVector']);
                need(current.body === originalBody && current.rawHeaderVector === originalVector &&
                    current.kind === row.kind && current.id === row.id, 'ORIGINAL_HTTP_ROW_REPLACED');
            }});
        }
        const originals = Array.from(rows);
        pins.push({verify: () => need(rows.length === originals.length &&
            originals.every((row, index) => rows[index] === row), 'ORIGINAL_HTTP_ROWS_REPLACED')});
        return rows;
    }
    function checkpoint(limit = endNs) {
        const now = D.integer(process.hrtime.bigint());
        need(lastNs === null || now >= lastNs, 'ORIGINAL_LOCAL_REGRESSION'); lastNs = now;
        need(failed === null && !reentered && !Reflect.apply(aborted, signal, []) &&
            (limit === null || now < limit) && (endNs === null || now < endNs) &&
            (utcFence === null || now < utcFence), 'ORIGINAL_PHASE_FENCE');
        need(!FORBIDDEN.some(name => Object.hasOwn(process.env, name)), 'API_CREDENTIAL_BOUNDARY');
        if (originalEnvironment !== null) for (const [name, value] of Object.entries(originalEnvironment))
            need(process.env[name] === value, 'ORIGINAL_ENVIRONMENT_CHANGED');
        if (validity !== null) D.currentUtc(validity, Date.now());
        for (const row of pins) {
            if (row.verify) row.verify();
            else need(D.encode(row.value, row.maximum).equals(row.raw), 'ORIGINAL_RETURN_CHANGED');
        }
        for (const row of bytePins) need(D.bytes(row.raw, row.maximum).equals(row.copy), 'ORIGINAL_BYTES_CHANGED');
        return now;
    }
    function arm() {
        checkpoint(); clearTimeout(timer);
        if (validity !== null) {
            const utc = Date.now(); D.currentUtc(validity, utc);
            const mapped = lastNs + BigInt(validity.authorityExpiresAt * 1000 - utc) * 1000000n;
            utcFence = utcFence === null ? mapped : min(utcFence, mapped); // Only tighten.
        }
        const end = utcFence === null ? endNs : min(endNs, utcFence);
        need(end !== null && lastNs < end, 'ORIGINAL_TIMER');
        timer = setTimeout(cancel, Math.max(1, Number((end - lastNs + 999999n) / 1000000n)));
    }
    try {
        const mode = process.env.INPUT_MODE, python = process.env.INPUT_PYTHON,
            toolPath = process.env['INPUT_TOOL-PATH'], output = process.env.GITHUB_OUTPUT;
        need((mode === 'upload' || mode === 'after') && /^24\./.test(process.versions.node) && absolute(process.execPath) &&
            absolute(python) && /^python(?:3(?:\.\d+)?)?(?:\.exe)?$/.test(path.basename(python)) &&
            typeof toolPath === 'string' && toolPath.length <= 16384 && toolPath.split(windows ? ';' : ':').every(absolute) &&
            absolute(output), 'FIXED_TOOLS_AND_OUTPUT');
        const kind = process.env.GITHUB_JOB === 'initial-recipient-gate' ? 'gate' :
            process.env.GITHUB_JOB === 'populate' ? 'worker' : null;
        need(kind !== null && (!route.productive || kind === 'worker') && process.env.GITHUB_WORKSPACE === workspace, 'ORIGINAL_JOB_WORKSPACE');
        const names = [...IDENTITY, ...SEED, ...ANCESTORS, ...NATIVE, ...(mode === 'after' ? UPLOAD : []),
            'INPUT_MODE', 'INPUT_PYTHON', 'INPUT_TOOL-PATH', 'GITHUB_OUTPUT', 'GITHUB_RETENTION_DAYS',
            ...(mode === 'upload' ? ['ACTIONS_RUNTIME_TOKEN', 'ACTIONS_RESULTS_URL'] : [])];
        originalEnvironment = Object.freeze(Object.fromEntries(names.map(name => [name, process.env[name]])));
        const required = [...IDENTITY, ...SEED, ...(mode === 'after' ? UPLOAD : [])];
        need(required.every(name => safeString(originalEnvironment[name])), 'ORIGINAL_ENVIRONMENT');
        need(absolute(originalEnvironment.RUNNER_TEMP), 'ORIGINAL_PRIVATE_PARENT');
        const inherited = ANCESTORS.filter(name => originalEnvironment[name] !== undefined);
        need(inherited.length === 0 || inherited.length === 1 && inherited[0] === 'GRADLE_USER_HOME' ||
            inherited.length === ANCESTORS.length, 'PARTIAL_ANCESTORS');
        const env = Object.fromEntries([...required, ...ANCESTORS, ...NATIVE]
            .filter(name => originalEnvironment[name] !== undefined).map(name => [name, originalEnvironment[name]]));
        need(Object.values(env).every(safeString), 'HELPER_ENVIRONMENT');
        Object.assign(env, {PATH: toolPath, LANG: 'C', LC_ALL: 'C', PYTHONDONTWRITEBYTECODE: '1', PYTHONUNBUFFERED: '1',
            ...(windows ? {USERPROFILE: env.RUNNER_TEMP, TMP: env.RUNNER_TEMP, TEMP: env.RUNNER_TEMP} :
                {HOME: env.RUNNER_TEMP, TMPDIR: env.RUNNER_TEMP})});
        Object.freeze(env); pin(env);
        for (const signalName of signals) process.on(signalName, cancel);
        signalsInstalled = true; checkpoint();
        let readyRaw, readyValue, bounds, inputRaw, expectedArtifactId;
        if (mode === 'upload') {
            need(/^[1-9][0-9]{0,2}$/.test(originalEnvironment.GITHUB_RETENTION_DAYS || ''), 'ORIGINAL_RETENTION_SETTING');
            const maxRetentionDays = Number(originalEnvironment.GITHUB_RETENTION_DAYS);
            need(maxRetentionDays >= 14 && maxRetentionDays <= 400, 'RETENTION_REQUIRES_14_DAYS');
            const service = Object.freeze({ACTIONS_RUNTIME_TOKEN: originalEnvironment.ACTIONS_RUNTIME_TOKEN,
                ACTIONS_RESULTS_URL: originalEnvironment.ACTIONS_RESULTS_URL});
            need(Object.values(service).every(safeString), 'ORIGINAL_RESULTS_CREDENTIALS');
            retained.reader = route.openReader({python, kind, environment: env, signal});
            const reader = retained.reader;
            pinHandle(reader, ['ready', 'stream', 'bind', 'completion', 'cancel', 'finalFrame']);
            completions.push(reader.completion);
            const returned = await reader.ready; retained.originals.push(returned);
            const readyReturn = pinHandle(returned, ['raw', 'preSpawnLocalNs']);
            readyRaw = pinBytes(readyReturn.raw, RECORD);
            readyValue = pin(D.ready(readyRaw, env, Date.now()), RECORD); validity = readyValue;
            bounds = D.localBounds(readyValue, readyReturn.preSpawnLocalNs);
            endNs = bounds.closeEndNs; arm(); checkpoint(bounds.startByNs);
            const bound = pin(reader.bind({readySha256: D.sha(readyRaw), beforeSha256: readyValue.beforeSha256,
                firstRawNs: D.decimal(readyValue.firstRawNs), [route.startField]: D.integer(readyValue[route.boundsField][route.startField]),
                uploadEndNs: D.integer(readyValue[route.boundsField].uploadEndNs), zipBytes: readyValue.zipBytes}));
            D.fields(bound, ['startByNs', 'workEndNs', 'closeEndNs']);
            need(bound.startByNs === bounds.startByNs && bound.workEndNs === bounds.workEndNs &&
                bound.closeEndNs === bounds.closeEndNs, 'ORIGINAL_READER_MAPPING');
            checkpoint(bounds.startByNs);
            retained.observer = Observer.beforeOnce({jobId: String(readyValue.github.jobId), requestSha256: D.sha(readyRaw),
                preSpawnLocalNs: bounds.preSpawnLocalNs, ...bound, signal});
            const before = retained.observer; pinHandle(before, ['completion', 'cancel', 'originals']);
            completions.push(before.completion);
            const beforeValue = pin(await before.completion), originals = pinRows(before.originals());
            D.observerClosed(beforeValue, originals, readyValue, bounds, 'before', D.sha(readyRaw), Date.now());
            D.serviceJob(readyValue, originals[0].body, originals[0].rawHeaderVector, env, 'upload', Date.now());
            checkpoint(bounds.startByNs); // COMPLETE original job/Step semantics BEFORE Create.
            retained.transport = Transport.uploadOnce({stream: reader.stream, artifactName: D.artifactName(readyValue),
                expectedZipBytes: readyValue.zipBytes, requestSha256: D.sha(readyRaw), ...bound, signal, service,
                maxRetentionDays});
            completions.push(retained.transport);
            const transportValue = pin(await retained.transport), readerValue = pin(await reader.completion),
                finalRaw = pinBytes(reader.finalFrame(), RECORD);
            checkpoint(bounds.workEndNs);
            inputRaw = pinBytes(D.finishInput({readyRaw, finalRaw, readerValue, transportValue, beforeValue, originals},
                readyValue, bounds, Date.now()), INPUT - 5);
            expectedArtifactId = transportValue.artifactId;
            checkpoint(bounds.workEndNs);
            retained.finite = openFinite({mode: 'finish', python, kind, environment: env, signal,
                originalEndNs: bounds.closeEndNs, checkpoint, poison: fail}, route);
        } else {
            retained.finite = openFinite({mode: 'after', python, kind, environment: env, signal,
                originalEndNs: null, checkpoint, poison: fail}, route);
            const finite = retained.finite;
            completions.push(finite.completion);
            endNs = finite.preSpawnLocalNs + 15n * NS; arm();
            const returned = await finite.ready; retained.originals.push(returned);
            const readyReturn = pinHandle(returned, ['raw', 'preSpawnLocalNs']);
            need(readyReturn.preSpawnLocalNs === finite.preSpawnLocalNs, 'AFTER_ORIGINAL_PRESPAWN');
            readyRaw = pinBytes(readyReturn.raw, RECORD);
            readyValue = pin(D.afterReady(readyRaw, env, Date.now()), RECORD); validity = readyValue;
            bounds = D.afterBounds(readyValue, readyReturn.preSpawnLocalNs);
            endNs = bounds.endNs; finite.bindAfter(endNs); arm(); checkpoint();
            retained.observer = Observer.afterOnce({jobId: String(readyValue.github.jobId), artifactId: readyValue.artifactId,
                requestSha256: D.sha(readyRaw), preSpawnLocalNs: bounds.preSpawnLocalNs, endNs, signal});
            const after = retained.observer; pinHandle(after, ['completion', 'cancel', 'originals']);
            completions.push(after.completion);
            const afterValue = pin(await after.completion), originals = pinRows(after.originals());
            checkpoint();
            inputRaw = pinBytes(D.afterInput({afterValue, originals}, readyRaw, readyValue, bounds, Date.now()), INPUT - 5);
            expectedArtifactId = readyValue.artifactId;
        }
        const finite = retained.finite;
        if (mode === 'upload') completions.push(finite.completion);
        checkpoint(); finite.input(inputRaw);
        const finiteClosed = pin(await finite.completion);
        need(finiteClosed.transport === 'closed' && finiteClosed.code === null, 'FINITE_KNOWN_ORIGINAL_CLOSE');
        const finalRaw = pinBytes(finite.finalFrame(), RECORD);
        checkpoint();
        const result = pin(D.finiteResult(finalRaw, {mode, readyRaw, readyValue, bounds, inputRaw, artifactId: expectedArtifactId,
            environment: env, nowMs: Date.now()}), RECORD);
        const outputs = D.outputs(result), text = Object.entries(outputs).map(([name, value]) => name + '=' + value + '\n').join('');
        checkpoint();
        fs.appendFileSync(output, text, {encoding: 'utf8'}); // Six bounded SAFE values only, exactly once.
        checkpoint(); process.exitCode = 0;
    } catch (error) {
        fail(error);
        // Existing owners use their ORIGINAL absolute fences, including when
        // incomplete. Waiting here neither creates a new deadline nor calls a
        // retry/replacement helper. UNKNOWN handles remain in quarantine.
        await Promise.allSettled(completions);
        process.stderr.write('INITIAL_ARTIFACT_ACTION_NOT_ACCEPTED\n');
    } finally {
        clearTimeout(timer);
        if (signalsInstalled) for (const signalName of signals) process.removeListener(signalName, cancel);
    }
}

// Named entries only. Switching names cannot retry a failed original owner.
async function main() { return mainFixed(LEGACY_ROUTE); }
async function mainProductive() { return mainFixed(PRODUCTIVE_ROUTE); }
module.exports = Object.freeze({main, mainProductive});
