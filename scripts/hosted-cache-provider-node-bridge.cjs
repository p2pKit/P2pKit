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
        ['bindings', 'environment', 'localEndNs', 'python', 'request', 'signal'].sort().join('\0'),
    'PROVIDER_BRIDGE_ARGUMENTS');
    const {python, localEndNs, signal} = values;
    // Native AbortSignal brand check; no caller-provided cancellation callback.
    need(!Reflect.apply(aborted, signal, []), 'PROVIDER_BRIDGE_ALREADY_CANCELLED');
    need(Buffer.isBuffer(values.request) && values.request.length <= 16 * 1024 &&
        !(values.request.buffer instanceof SharedArrayBuffer), 'PROVIDER_BRIDGE_REQUEST_BYTES');
    const request = Buffer.from(values.request);
    const reducer = new ReceiptReducer(request);
    // Canonical/width checks belong to the unchanged reducer. Only string
    // fields below are selected from JSON; numeric file identities stay there.
    const context = JSON.parse(request.toString('ascii'));
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
    const env = environmentFor(context, values.environment);
    const bindingText = JSON.stringify(Object.fromEntries(Object.keys(bindings).sort().map(name => [name, bindings[name]])));
    need(bindingText.length <= 16 * 1024, 'PROVIDER_BRIDGE_BINDINGS_BOUND');
    const now = process.hrtime.bigint();
    need(typeof localEndNs === 'bigint' && now < localEndNs && localEndNs - now <=
        BigInt(context.hardEndNs) - BigInt(context.firstNs) && localEndNs - now <= 180n * NS,
    'PROVIDER_BRIDGE_ORIGINAL_LOCAL_END_REQUIRED');

    return new Promise(resolve => {
        let child = null, timer = null, settled = false, closed = false, stopped = false, cancelled = false;
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
        function finish(knownClose) {
            if (settled) return;
            let summary = null;
            try {
                need(knownClose && process.hrtime.bigint() < localEndNs && !cancelled &&
                    !currentCancellation() && errors.length === 0, 'PROVIDER_BRIDGE_INCOMPLETE');
                summary = reducer.finish();
                need(process.hrtime.bigint() < localEndNs && !currentCancellation(),
                    'PROVIDER_BRIDGE_LATE_CLOSE');
            } catch (error) { summary = null; remember(error); }
            settled = true;
            if (timer !== null) clearTimeout(timer);
            signal.removeEventListener('abort', stop);
            resolve(Object.freeze({scope: 'ORIGINAL_NODE_CHILD_TRANSPORT_ONLY',
                transport: summary === null ? 'incomplete' : 'closed', childCloseObserved: closed,
                cancellationRequested: cancelled, summary,
                originalRawDeadline: 'NOT_OBSERVED', enclosingNodeReturn: 'NOT_OBSERVED',
                originalRunnerOutcome: 'NOT_OBSERVED', providerAcceptance: 'NOT_ESTABLISHED',
                // Private capabilities/bytes, not JSON/log fields. On timeout
                // this retains a LIVE/UNKNOWN child, NOT permission to read,
                // delete, reuse or seal its still-owned native files.
                originalChild: () => child, retainedBytes: () => reducer.retainedBytes(),
                originalErrors: () => errors.slice()}));
        }
        function deadline() {
            const remaining = localEndNs - process.hrtime.bigint();
            if (remaining <= 0n) { finish(false); return; }
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
                if (!settled) { reducer.onClose(code, nativeSignal); finish(true); }
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
            finish(false); // An ambiguous launch never mints a completed return.
        }
    });
}

module.exports = Object.freeze({launchSupervisor});
