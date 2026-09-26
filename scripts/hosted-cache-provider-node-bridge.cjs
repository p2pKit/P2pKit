'use strict';

// Actual asynchronous child/pipe adapter; NOT hosted admission or an Action.
// The caller must already own source/tool/service authority and the ORIGINAL
// Node-local deadline, conservatively derived before its native RAW observation.
// This module never creates a new180, reads credentials from ambient env, seals
// files, or turns a matching ACK into provider/runner acceptance.
const {spawn, ChildProcess} = require('node:child_process');
const paths = require('node:path');
const {setTimeout, clearTimeout} = require('node:timers');
const {ReceiptReducer} = require('./hosted-cache-provider-node-return.cjs');

const NS = 1000000000n;
const SERVICE = ['ACTIONS_RUNTIME_TOKEN', 'ACTIONS_RESULTS_URL', 'ACTIONS_CACHE_SERVICE_V2'];
const MARKERS = ['P2PKIT_AUDIT_JOB_ID', 'P2PKIT_AUDIT_OWNERSHIP_CHAIN', 'P2PKIT_AUDIT_OWNERSHIP_DOMAINS',
    'P2PKIT_AUDIT_STATE_DIR', 'GRADLE_USER_HOME'];
const path = process.platform === 'win32' ? paths.win32 : paths.posix;
const workspace = path.dirname(__dirname);
const worker = path.join(__dirname, 'hosted_cache_provider_worker.py');
const clockWorker = path.join(__dirname, 'hosted_cache_provider_clock.py');
const aborted = Object.getOwnPropertyDescriptor(AbortSignal.prototype, 'aborted').get;
let used = false;

function need(value, reason) {
    if (!value) throw new Error(reason); // Only fixed source-owned reasons.
}
function fields(value) {
    need(value !== null && Object.getPrototypeOf(value) === Object.prototype,
        'PROVIDER_BRIDGE_PLAIN_FIELDS_REQUIRED');
    const descriptors = Object.getOwnPropertyDescriptors(value);
    need(Reflect.ownKeys(value).length === Object.keys(descriptors).length &&
        Object.values(descriptors).every(item => Object.hasOwn(item, 'value') && item.enumerable),
    'PROVIDER_BRIDGE_DATA_FIELDS_REQUIRED');
    return Object.fromEntries(Object.entries(descriptors).map(([name, item]) => [name, item.value]));
}
function absolute(value) {
    return typeof value === 'string' && value.length > 0 && value.length <= 4096 &&
        !/[\x00-\x1f\x7f]/.test(value) && path.isAbsolute(value) && path.normalize(value) === value;
}
function environmentFor(context, supplied) {
    const env = fields(supplied), windows = context.role === 'windows-x64';
    const base = ['PATH', 'GITHUB_WORKSPACE', 'LANG', 'LC_ALL', ...SERVICE,
        ...(windows ? ['SYSTEMROOT', 'USERPROFILE', 'TEMP', 'TMP', 'PATHEXT'] : ['HOME', 'TMPDIR'])];
    const markers = MARKERS.filter(name => Object.hasOwn(env, name));
    need(markers.length === 0 || (markers.length === 1 && markers[0] === 'GRADLE_USER_HOME') ||
        markers.length === MARKERS.length, 'PROVIDER_BRIDGE_PARTIAL_OWNERSHIP');
    need(Object.keys(env).sort().join('\0') === [...base, ...markers].sort().join('\0') &&
        Object.values(env).every(value => typeof value === 'string' && value.length > 0 &&
            value.length <= 4096 && !/[\x00-\x1f\x7f]/.test(value)), 'PROVIDER_BRIDGE_ENVIRONMENT');
    need(env.PATH === context.toolPath && env.GITHUB_WORKSPACE === workspace &&
        env.LANG === 'C' && env.LC_ALL === 'C' && env.ACTIONS_CACHE_SERVICE_V2 === 'True',
    'PROVIDER_BRIDGE_ENVIRONMENT_CONTEXT');
    need(windows ? absolute(env.SYSTEMROOT) && env.USERPROFILE === context.home &&
        env.TEMP === context.home && env.TMP === context.home && env.PATHEXT === '.EXE' :
        env.HOME === context.home && env.TMPDIR === context.home, 'PROVIDER_BRIDGE_PRIVATE_HOME');
    // This is a closed handoff, not service-origin authentication. The existing
    // native entry validates the service fragment again. Never serialize env.
    return env;
}

function launchSupervisor(options) {
    need(!used, 'PROVIDER_BRIDGE_ONE_INVOCATION');
    used = true;
    const values = fields(options);
    need(Object.keys(values).sort().join('\0') ===
        ['bindings', 'clockBindings', 'environment', 'localEndNs', 'minimumRawNs', 'python', 'request', 'signal'].sort().join('\0'),
    'PROVIDER_BRIDGE_ARGUMENTS');
    const {python, localEndNs, minimumRawNs, signal} = values;
    // Native AbortSignal brand check; no caller-provided cancellation callback.
    need(!Reflect.apply(aborted, signal, []), 'PROVIDER_BRIDGE_ALREADY_CANCELLED');
    need(Buffer.isBuffer(values.request) && values.request.length <= 16 * 1024 &&
        !(values.request.buffer instanceof SharedArrayBuffer), 'PROVIDER_BRIDGE_REQUEST_BYTES');
    const request = Buffer.from(values.request);
    const reducer = new ReceiptReducer(request);
    // Canonical/width checks belong to the unchanged reducer. Preserve integer
    // source tokens: an admitted INT64 QPC frequency need not be a safe Number.
    const context = JSON.parse(request.toString('ascii'), (_key, value, original) => {
        if (typeof value !== 'number') return value;
        need(original && /^-?(0|[1-9][0-9]*)$/.test(original.source), 'PROVIDER_BRIDGE_INTEGER_SOURCE');
        return BigInt(original.source);
    });
    const role = {linux: 'linux-', darwin: 'macos-', win32: 'windows-'}[process.platform] + process.arch;
    need(context.role === role && /^24\./.test(process.versions.node) && context.node === process.execPath,
        'PROVIDER_BRIDGE_NATIVE_NODE_CONTEXT');
    need(absolute(python) && /^python(?:3(?:\.\d+)?)?(?:\.exe)?$/.test(path.basename(python)),
        'PROVIDER_BRIDGE_FIXED_PYTHON');
    const bindings = fields(values.bindings);
    need(Object.keys(bindings).length <= 32 && Object.entries(bindings).every(([name, hash]) =>
        /^(?:audit_processes|hosted_[a-z0-9_]+)$/.test(name) && typeof hash === 'string' &&
        /^[0-9a-f]{64}$/.test(hash)) &&
        ['hosted_cache_provider_worker', 'hosted_cache_provider_entry', 'hosted_cache_provider_supervisor']
            .every(name => Object.hasOwn(bindings, name)), 'PROVIDER_BRIDGE_SOURCE_BINDINGS');
    // Windows kill(SIGTERM) terminates rather than cooperatively cancelling.
    // The old committed loader has no stdin reader: refuse before spawn unless
    // the admitted fixed source roster includes that separately reviewed leaf.
    need(context.role !== 'windows-x64' || Object.hasOwn(bindings, 'hosted_cache_provider_cancel'),
        'PROVIDER_BRIDGE_WINDOWS_COOPERATIVE_CONTROL_REQUIRED');
    const clockBindings = fields(values.clockBindings);
    const clockNames = ['audit_processes', 'hosted_job_clock', 'hosted_cache_provider_clock',
        ...(context.role.startsWith('macos-') ? ['hosted_lock_resources'] : [])];
    need(Object.keys(clockBindings).sort().join('\0') === clockNames.sort().join('\0') &&
        Object.entries(clockBindings).every(([name, hash]) => typeof hash === 'string' &&
            /^[0-9a-f]{64}$/.test(hash) && (name === 'hosted_cache_provider_clock' || hash === bindings[name])),
    'PROVIDER_BRIDGE_CLOCK_SOURCE_BINDINGS');
    need(typeof minimumRawNs === 'bigint' && minimumRawNs >= BigInt(context.firstNs) &&
        minimumRawNs < BigInt(context.hardEndNs), 'PROVIDER_BRIDGE_ORIGINAL_RAW_HIGH_WATER');
    const env = environmentFor(context, values.environment);
    const bindingText = JSON.stringify(Object.fromEntries(Object.keys(bindings).sort().map(name => [name, bindings[name]])));
    const clockBindingText = JSON.stringify(Object.fromEntries(Object.keys(clockBindings).sort().map(
        name => [name, clockBindings[name]])));
    need(bindingText.length <= 16 * 1024, 'PROVIDER_BRIDGE_BINDINGS_BOUND');
    const now = process.hrtime.bigint();
    need(typeof localEndNs === 'bigint' && now < localEndNs && localEndNs - now <=
        BigInt(context.hardEndNs) - BigInt(context.firstNs) && localEndNs - now <= 180n * NS,
    'PROVIDER_BRIDGE_ORIGINAL_LOCAL_END_REQUIRED');

    return new Promise(resolve => {
        let child = null, timer = null, settled = false, closed = false, stopped = false, cancelled = false;
        let clockChild = null, clockClosed = false, clockStarted = false, clockExit = false;
        let clockAttempted = false, clockObservation = null;
        const clockBytes = {stdout: Buffer.alloc(1024), stderr: Buffer.alloc(4096)};
        const clockSizes = {stdout: 0, stderr: 0}, clockEnded = {stdout: false, stderr: false};
        const errors = [];
        const remember = error => { if (errors.length < 16) errors.push(error); };
        const currentCancellation = () => Reflect.apply(aborted, signal, []);
        function stop() {
            cancelled = true;
            if (stopped || child === null || closed) return;
            stopped = true; // One original request, never a retry against a PID.
            try {
                if (context.role === 'windows-x64') {
                    child.stdin.write(Buffer.from('C'), error => { if (error) remember(error); });
                } else {
                    need(child.kill('SIGTERM'), 'PROVIDER_BRIDGE_CANCEL_NOT_SENT');
                }
            } catch (error) { remember(error); }
        }
        function finish(summary = null) {
            if (settled) return;
            try {
                need(summary !== null && closed && clockClosed && clockObservation !== null &&
                    process.hrtime.bigint() < localEndNs && !cancelled && !currentCancellation() &&
                    errors.length === 0, 'PROVIDER_BRIDGE_INCOMPLETE');
            } catch (error) { summary = null; remember(error); }
            settled = true;
            if (timer !== null) clearTimeout(timer);
            signal.removeEventListener('abort', stop);
            resolve(Object.freeze({scope: 'ORIGINAL_NODE_CHILD_TRANSPORT_ONLY',
                transport: summary === null ? 'incomplete' : 'closed', childCloseObserved: closed,
                cancellationRequested: cancelled, summary,
                clockChildCloseObserved: clockClosed,
                originalRawDeadline: summary === null ? 'NOT_ESTABLISHED' : 'OBSERVED_AFTER_PROVIDER_CLOSE',
                postLastOwnerCloseRaw: 'NOT_OBSERVED', enclosingNodeReturn: 'NOT_OBSERVED',
                originalRunnerOutcome: 'NOT_OBSERVED', providerAcceptance: 'NOT_ESTABLISHED',
                // Private capabilities/bytes, not JSON/log fields. On timeout
                // this retains a LIVE/UNKNOWN child, NOT permission to read,
                // delete, reuse or seal its still-owned native files.
                originalChild: () => child, retainedBytes: () => reducer.retainedBytes(),
                originalClockChild: () => clockChild,
                retainedClockBytes: () => Object.fromEntries(['stdout', 'stderr'].map(name =>
                    [name, Buffer.from(clockBytes[name].subarray(0, clockSizes[name]))])),
                originalErrors: () => errors.slice()}));
        }
        function observeAfterClose() {
            try {
                need(closed && !clockAttempted && !settled && !cancelled && !currentCancellation() &&
                    errors.length === 0 && process.hrtime.bigint() < localEndNs, 'PROVIDER_BRIDGE_CLOCK_PRECONDITION');
                clockAttempted = true;
                const summary = reducer.finish();
                const ack = JSON.parse(reducer.retainedBytes().stdout.toString('ascii'));
                const minimum = BigInt(ack.observedNs);
                need(minimum >= minimumRawNs && process.hrtime.bigint() < localEndNs,
                    'PROVIDER_BRIDGE_RAW_BACKWARDS');
                const clockRequest = {frequency: context.frequency.toString(), hardEndNs: context.hardEndNs,
                    invocationSha256: summary.invocationSha256, minimumNs: minimum.toString(), role: context.role,
                    schema: 'P2PKIT_PROVIDER_POST_CLOSE_CLOCK_REQUEST_V1'};
                // A fresh explicit map, never ambient env. The clock helper has
                // NO runtime/API credentials, provider inputs, or provider code.
                const clockEnv = Object.fromEntries(Object.entries(env).filter(([name]) => !SERVICE.includes(name)));
                need(!cancelled && !currentCancellation() && process.hrtime.bigint() < localEndNs,
                    'PROVIDER_BRIDGE_CLOCK_CANCELLED');
                clockChild = spawn(python, ['-I', '-B', '-S', clockWorker, clockBindingText, JSON.stringify(clockRequest)],
                    {cwd: workspace, env: clockEnv, shell: false, detached: false, windowsHide: false,
                        stdio: ['ignore', 'pipe', 'pipe']});
                need(clockChild instanceof ChildProcess, 'PROVIDER_BRIDGE_ORIGINAL_CLOCK_CHILD');
                const fail = error => { remember(error); };
                function event(operation) {
                    if (settled) return;
                    try { operation(); } catch (error) { fail(error); }
                }
                // Own original errors before any fallible pipe validation.
                clockChild.on('error', fail);
                clockChild.on('spawn', () => event(() => {
                    need(!clockStarted && !clockExit && !clockClosed, 'PROVIDER_BRIDGE_CLOCK_SPAWN_ORDER');
                    clockStarted = true;
                }));
                clockChild.on('exit', (code, nativeSignal) => event(() => {
                    need(clockStarted && !clockExit && !clockClosed && code === 0 && !Object.is(code, -0) &&
                        nativeSignal === null, 'PROVIDER_BRIDGE_CLOCK_EXIT');
                    clockExit = true;
                }));
                clockChild.on('close', (code, nativeSignal) => {
                    event(() => {
                        need(clockExit && !clockClosed && code === 0 && !Object.is(code, -0) && nativeSignal === null &&
                            clockEnded.stdout && clockEnded.stderr && clockSizes.stderr === 0 && errors.length === 0,
                        'PROVIDER_BRIDGE_CLOCK_CLOSE');
                        const raw = clockBytes.stdout.subarray(0, clockSizes.stdout);
                        need(raw.length > 0 && !raw.some(value => value > 127), 'PROVIDER_BRIDGE_CLOCK_BYTES');
                        const value = JSON.parse(raw.toString('ascii'));
                        need(typeof value.observedNs === 'string' && /^(0|[1-9][0-9]{0,19})$/.test(value.observedNs),
                            'PROVIDER_BRIDGE_CLOCK_RAW');
                        const observed = BigInt(value.observedNs);
                        const domain = context.role === 'windows-x64' ?
                            'windows.QueryPerformanceCounter/QueryPerformanceFrequency.floor_ns' :
                            (context.role.startsWith('macos-') ? 'darwin' : 'linux') + '.clock_gettime_ns(CLOCK_MONOTONIC_RAW)';
                        const expected = {...clockRequest, schema: 'P2PKIT_PROVIDER_POST_CLOSE_CLOCK_OBSERVATION_V1',
                            domain, observedNs: value.observedNs};
                        const canonical = JSON.stringify(Object.fromEntries(Object.keys(expected).sort().map(
                            name => [name, expected[name]]))) + '\n';
                        need(raw.toString('ascii') === canonical && observed >= minimum &&
                            observed < BigInt(context.hardEndNs), 'PROVIDER_BRIDGE_CLOCK_BINDING');
                        clockObservation = value;
                    });
                    clockClosed = true; // Actual close even if its receipt/return failed.
                    finish(summary);
                });
                for (const name of ['stdout', 'stderr']) {
                    if (clockChild[name]) clockChild[name].on('error', fail);
                }
                need(clockChild.stdout && clockChild.stderr, 'PROVIDER_BRIDGE_CLOCK_PIPES');
                for (const name of ['stdout', 'stderr']) {
                    clockChild[name].on('data', chunk => event(() => {
                        need(clockStarted && !clockClosed && !clockEnded[name] && Buffer.isBuffer(chunk) &&
                            chunk.length <= clockBytes[name].length - clockSizes[name], 'PROVIDER_BRIDGE_CLOCK_STREAM');
                        chunk.copy(clockBytes[name], clockSizes[name]);
                        clockSizes[name] += chunk.length;
                    }));
                    clockChild[name].on('end', () => event(() => {
                        need(clockStarted && !clockClosed && !clockEnded[name], 'PROVIDER_BRIDGE_CLOCK_EOF');
                        clockEnded[name] = true;
                    }));
                }
            } catch (error) { remember(error); finish(); }
        }
        function deadline() {
            const remaining = localEndNs - process.hrtime.bigint();
            if (remaining <= 0n) { finish(); return; }
            // Timer is only a local liveness fence, never a RAW-clock receipt.
            timer = setTimeout(deadline, Math.max(1, Number(remaining / 1000000n)));
        }
        try {
            signal.addEventListener('abort', stop, {once: true});
            need(!currentCancellation() && process.hrtime.bigint() < localEndNs,
                'PROVIDER_BRIDGE_CANCELLED_BEFORE_SPAWN');
            child = spawn(python, ['-I', '-B', '-S', worker, '--supervisor', bindingText, request.toString('ascii')],
                {cwd: workspace, env, shell: false, detached: false, windowsHide: false, stdio: ['pipe', 'pipe', 'pipe']});
            need(child instanceof ChildProcess, 'PROVIDER_BRIDGE_ORIGINAL_CHILD');
            // A failed spawn can RETURN a ChildProcess with missing stdio and
            // queue an error. Own that error/close before any pipe assertion;
            // otherwise Node can throw/log the original private error later.
            child.on('error', error => { remember(error); if (!settled) reducer.onError(); });
            child.on('exit', (code, nativeSignal) => { if (!settled) reducer.onExit(code, nativeSignal); });
            child.on('close', (code, nativeSignal) => {
                closed = true;
                if (!settled) { reducer.onClose(code, nativeSignal); observeAfterClose(); }
            });
            child.on('spawn', () => { if (!settled) reducer.onSpawn(); });
            for (const stream of ['stdin', 'stdout', 'stderr']) {
                if (child[stream]) child[stream].on('error', error => {
                    remember(error); if (!settled) reducer.onError();
                });
            }
            need(child.stdin && child.stdout && child.stderr, 'PROVIDER_BRIDGE_ORIGINAL_PIPES');
            for (const stream of ['stdout', 'stderr']) {
                child[stream].on('data', chunk => { if (!settled) reducer.onData(stream, chunk); });
                child[stream].on('end', () => { if (!settled) reducer.onEnd(stream); });
            }
            if (currentCancellation()) stop();
            deadline();
        } catch (error) {
            remember(error);
            finish(); // An ambiguous launch never mints a completed return.
        }
    });
}

module.exports = Object.freeze({launchSupervisor});
