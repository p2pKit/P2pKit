'use strict';

// Dormant fixed Node24 Action connection, NOT prestart/Stage1/provider admission.
// Trusted workflow/source/tool/runtime-service provenance must exist BEFORE this
// process starts. Checks here cannot authenticate its earlier Node environment.
// The ordinary helper uses trusted-main admission, with no policy fallback.
// A SEPARATE fixed initial entry uses its two fresh public authority episodes;
// no Action API-token input or environment-selected exception route exists.
// No workflow calls this source; all existing HOLDs and qualifications remain.
const {spawn, ChildProcess} = require('node:child_process');
const {createHash} = require('node:crypto');
const fs = require('node:fs');
const https = require('node:https');
const paths = require('node:path');
const {setTimeout, clearTimeout} = require('node:timers');
const {launchSupervisor} = require('./hosted-cache-provider-node-bridge.cjs');

const NS = 1000000000n;
const windows = process.platform === 'win32';
const path = windows ? paths.win32 : paths.posix;
const workspace = path.dirname(__dirname);
const helper = path.join(__dirname, 'hosted_cache_provider_native.py');
const clockHelper = path.join(__dirname, 'hosted_cache_provider_clock.py');
const SERVICE = ['ACTIONS_RUNTIME_TOKEN', 'ACTIONS_RESULTS_URL', 'ACTIONS_CACHE_SERVICE_V2'];
const MARKERS = ['P2PKIT_AUDIT_JOB_ID', 'P2PKIT_AUDIT_OWNERSHIP_CHAIN', 'P2PKIT_AUDIT_OWNERSHIP_DOMAINS',
    'P2PKIT_AUDIT_STATE_DIR', 'GRADLE_USER_HOME'];
const IDENTITY = ['GITHUB_ACTIONS', 'GITHUB_REPOSITORY', 'GITHUB_SHA', 'GITHUB_REF', 'GITHUB_RUN_ID',
    'GITHUB_RUN_ATTEMPT', 'GITHUB_EVENT_NAME', 'GITHUB_WORKFLOW_REF', 'GITHUB_WORKFLOW_SHA',
    'GITHUB_WORKSPACE', 'GITHUB_EVENT_PATH', 'GITHUB_SERVER_URL', 'GITHUB_API_URL', 'GITHUB_JOB',
    'RUNNER_OS', 'RUNNER_ARCH', 'RUNNER_NAME', 'RUNNER_ENVIRONMENT', 'RUNNER_TEMP', 'ImageOS', 'ImageVersion'];
const BASE_CLAIMS = ['PRODUCER_OUTCOME', 'HANDOFF_SHA256', 'PRODUCER_RETURN_SHA256',
    'SAVE_PREPARE_OUTCOME', 'SAVE_PREPARATION_SHA256'];
const LOOKUP_CLAIMS = ['SAVE_OUTCOME', 'SAVE_READBACK_SHA256', 'AFTER_SAVE_OUTCOME', 'AFTER_SAVE_SHA256',
    'PROBE_PREPARE_OUTCOME', 'PROBE_PREPARATION_SHA256'];
const PIN = 'caa296126883cff596d87d8935842f9db880ef25';
const BUNDLES = Object.freeze({
    save: Object.freeze({entry: 'save-only', bytes: 3202441n,
        sha256: '7fb63f90f06ce6a10f39d40a113f99791bffdedad5394cdad5b4dfaa644559cb'}),
    lookup: Object.freeze({entry: 'restore-only', bytes: 3202022n,
        sha256: '6255afaa3956351b8cfefc1e82f026b4db418a10678a8eaddf3d6c55f81744de'}),
});
// Retain original failed/incomplete handles and private errors in memory only.
// This is NOT retirement, failure custody, permission to clean up, or a retry.
const pending = [];
let used = false;
// Keep the original transport alive across run() and main() output finalization.
// This is private ownership, never a serialized public result or acceptance.
let providerReturn = null;

function need(value, reason) {
    if (!value) throw new Error(reason);
}
function absolute(value) {
    return typeof value === 'string' && value.length > 0 && value.length <= 4096 &&
        !/[\x00-\x1f\x7f]/.test(value) && path.isAbsolute(value) && path.normalize(value) === value;
}
function hash(raw) { return createHash('sha256').update(raw).digest('hex'); }
function scalar(value) {
    need(typeof value === 'string' && /^(0|[1-9][0-9]{0,19})$/.test(value), 'PROVIDER_ACTION_RAW');
    const result = BigInt(value);
    need(result < 1n << 64n, 'PROVIDER_ACTION_RAW');
    return result;
}
function canonical(value) {
    const escaped = item => JSON.stringify(item).replace(/[\x7f-\uffff]/g,
        char => '\\u' + char.charCodeAt(0).toString(16).padStart(4, '0'));
    if (value === null || typeof value === 'string' || typeof value === 'boolean') return escaped(value);
    if (typeof value === 'bigint') return value.toString();
    if (Array.isArray(value)) return '[' + value.map(canonical).join(',') + ']';
    need(value && Object.getPrototypeOf(value) === Object.prototype, 'PROVIDER_ACTION_JSON_VALUE');
    return '{' + Object.keys(value).sort().map(key => escaped(key) + ':' + canonical(value[key])).join(',') + '}';
}
function parse(raw) {
    need(Buffer.isBuffer(raw) && raw.length > 0 && raw.length <= 16384 && !raw.some(byte => byte > 127),
        'PROVIDER_ACTION_PRIVATE_BYTES');
    const text = raw.toString('ascii');
    const result = JSON.parse(text, (_key, value, original) => {
        if (typeof value !== 'number') return value;
        need(original && /^-?(0|[1-9][0-9]*)$/.test(original.source), 'PROVIDER_ACTION_INTEGER');
        return BigInt(original.source); // No QPC/file-identity Number truncation.
    });
    need(canonical(result) === text, 'PROVIDER_ACTION_CANONICAL');
    return result;
}
function check(end, signal) {
    need(!signal.aborted && process.hrtime.bigint() < end, 'PROVIDER_ACTION_ORIGINAL_END');
}

function native(python, args, env, end, signal) {
    // Fixed script only. Stdout/stderr are PRIVATE pipes, never runner output.
    // Tighten to the helper's own initial45; never wait for a fresh provider180.
    const helperEnd = process.hrtime.bigint() + 45n * NS;
    if (helperEnd < end) end = helperEnd;
    check(end, signal);
    return new Promise((resolve, reject) => {
        let child = null, timer = null, started = false, exited = false, closed = false, settled = false;
        const chunks = {stdout: [], stderr: []}, sizes = {stdout: 0, stderr: 0}, eof = {stdout: false, stderr: false};
        const errors = [];
        const remember = error => { if (errors.length < 16) errors.push(error); };
        function fail(error) {
            remember(error);
            if (settled) return;
            settled = true;
            if (timer !== null) clearTimeout(timer);
            signal.removeEventListener('abort', cancel);
            pending.push({child, chunks, errors});
            reject(new Error('PROVIDER_ACTION_NATIVE_INCOMPLETE'));
        }
        function cancel() {
            // Never use Windows kill(SIGTERM) as cooperative retirement.
            // Native helpers have no stdin control protocol. Their own original
            // fences remain; cancellation here cannot claim their known close.
            if (child && !closed && !windows) {
                try { child.kill('SIGTERM'); } catch (error) { remember(error); }
            }
            fail(new Error('PROVIDER_ACTION_CANCELLED'));
        }
        function guarded(operation) {
            if (settled) return;
            try { check(end, signal); operation(); } catch (error) { fail(error); }
        }
        function deadline() {
            if (settled) return;
            const remaining = end - process.hrtime.bigint();
            if (remaining <= 0n) { cancel(); return; }
            timer = setTimeout(deadline, Math.max(1, Number(remaining / 1000000n)));
        }
        try {
            signal.addEventListener('abort', cancel, {once: true});
            check(end, signal);
            child = spawn(python, ['-I', '-B', '-S', helper, ...args], {cwd: workspace, env,
                shell: false, detached: false, windowsHide: false, stdio: ['ignore', 'pipe', 'pipe']});
            need(child instanceof ChildProcess, 'PROVIDER_ACTION_ORIGINAL_CHILD');
            // Attach original failure/close handlers before fallible pipe checks.
            child.on('error', fail);
            child.on('spawn', () => guarded(() => {
                need(!started && !exited && !closed, 'PROVIDER_ACTION_NATIVE_SPAWN'); started = true;
            }));
            child.on('exit', (code, nativeSignal) => guarded(() => {
                need(started && !exited && !closed && code === 0 && !Object.is(code, -0) && nativeSignal === null,
                    'PROVIDER_ACTION_NATIVE_EXIT'); exited = true;
            }));
            child.on('close', (code, nativeSignal) => {
                closed = true;
                guarded(() => {
                    need(started && exited && code === 0 && !Object.is(code, -0) && nativeSignal === null &&
                        eof.stdout && eof.stderr && sizes.stderr === 0 && errors.length === 0,
                    'PROVIDER_ACTION_NATIVE_CLOSE');
                    const raw = Buffer.concat(chunks.stdout, sizes.stdout), value = parse(raw);
                    need(value.ownerClose === 'KNOWN_RESOURCE_CLOSE_ONLY' && value.originalHelperReturn === 'PENDING',
                        'PROVIDER_ACTION_NATIVE_RETURN');
                    check(end, signal);
                    settled = true;
                    if (timer !== null) clearTimeout(timer);
                    signal.removeEventListener('abort', cancel);
                    resolve({value, raw});
                });
            });
            for (const name of ['stdout', 'stderr']) if (child[name]) child[name].on('error', fail);
            need(child.stdout && child.stderr, 'PROVIDER_ACTION_NATIVE_PIPES');
            for (const name of ['stdout', 'stderr']) {
                child[name].on('data', chunk => guarded(() => {
                    const limit = name === 'stdout' ? 16384 : 65536;
                    need(started && !closed && !eof[name] && Buffer.isBuffer(chunk) && chunk.length <= limit - sizes[name],
                        'PROVIDER_ACTION_NATIVE_STREAM');
                    if (chunk.length) chunks[name].push(Buffer.from(chunk));
                    sizes[name] += chunk.length;
                }));
                child[name].on('end', () => guarded(() => {
                    need(started && !closed && !eof[name], 'PROVIDER_ACTION_NATIVE_EOF'); eof[name] = true;
                }));
            }
            deadline();
        } catch (error) { fail(error); }
    });
}

function acquire(bundle, phase, end, signal) {
    // Fixed public source GET only. Never runtime credentials, API tokens,
    // redirects, a configurable endpoint, a retry or an npm/tool installation.
    const expected = BUNDLES[phase];
    const url = 'https://raw.githubusercontent.com/actions/cache/' + PIN + '/dist/' + expected.entry + '/index.js';
    need(bundle.url === url && bundle.bytes === expected.bytes && bundle.sha256 === expected.sha256 &&
        bundle.basename === 'provider.cjs', 'PROVIDER_ACTION_PINNED_BUNDLE');
    const acquisitionEnd = process.hrtime.bigint() + 45n * NS;
    if (acquisitionEnd < end) end = acquisitionEnd;
    check(end, signal);
    return new Promise((resolve, reject) => {
        let request = null, response = null, timer = null, size = 0, requestClosed = false, responseClosed = false;
        let ended = false, settled = false, requestDestroyAttempted = false, responseDestroyAttempted = false;
        const chunks = [], errors = [];
        const remember = error => { if (errors.length < 16) errors.push(error); };
        // Keep the actual late response in the same retained failure record;
        // copying a null response at timeout would lose its later ownership.
        const original = {request: null, response: null, chunks, errors};
        function destroyOwned() {
            if (response !== null && !responseDestroyAttempted) {
                responseDestroyAttempted = true;
                try { response.destroy(); } catch (error) { remember(error); }
            }
            if (request !== null && !requestDestroyAttempted) {
                requestDestroyAttempted = true;
                try { request.destroy(); } catch (error) { remember(error); }
            }
        }
        function fail(error) {
            remember(error);
            if (settled) return;
            settled = true;
            if (timer !== null) clearTimeout(timer);
            signal.removeEventListener('abort', cancel);
            // Destroy only these original request/response objects, not a PID
            // or an unrelated connection. Failure is not a known-close result.
            pending.push(original);
            destroyOwned();
            reject(new Error('PROVIDER_ACTION_PUBLIC_ACQUISITION_FAILED'));
        }
        function cancel() { fail(new Error('PROVIDER_ACTION_CANCELLED')); }
        function guarded(operation) {
            if (settled) return;
            try { check(end, signal); operation(); } catch (error) { fail(error); }
        }
        function complete() {
            if (!requestClosed || !responseClosed || settled) return;
            guarded(() => {
                need(ended && response.complete === true && errors.length === 0 && BigInt(size) === expected.bytes,
                    'PROVIDER_ACTION_PUBLIC_SOURCE_INCOMPLETE');
                const raw = Buffer.concat(chunks, size);
                need(hash(raw) === expected.sha256, 'PROVIDER_ACTION_PUBLIC_SOURCE_HASH');
                check(end, signal);
                settled = true;
                clearTimeout(timer);
                signal.removeEventListener('abort', cancel);
                resolve(raw);
            });
        }
        function deadline() {
            if (settled) return;
            const remaining = end - process.hrtime.bigint();
            if (remaining <= 0n) { cancel(); return; }
            timer = setTimeout(deadline, Math.max(1, Number(remaining / 1000000n)));
        }
        try {
            signal.addEventListener('abort', cancel, {once: true});
            check(end, signal);
            // Attach original observers before sending. There is exactly one
            // response callback, including a response arriving after refusal.
            request = https.request(url, {agent: false, method: 'GET', headers: {'accept': 'application/octet-stream'}});
            original.request = request;
            request.on('error', fail);
            request.on('close', () => { requestClosed = true; complete(); });
            request.once('response', value => {
                response = value;
                original.response = response;
                response.on('error', fail);
                response.on('aborted', cancel);
                response.on('close', () => { responseClosed = true; complete(); });
                if (settled) { destroyOwned(); return; }
                guarded(() => {
                    need(response.statusCode === 200 && !response.headers.location &&
                        (!response.headers['content-encoding'] || response.headers['content-encoding'] === 'identity'),
                    'PROVIDER_ACTION_PUBLIC_SOURCE_RESPONSE');
                    if (response.headers['content-length'] !== undefined) {
                        need(response.headers['content-length'] === expected.bytes.toString(),
                            'PROVIDER_ACTION_PUBLIC_SOURCE_SIZE');
                    }
                });
                if (settled) return;
                response.on('data', chunk => guarded(() => {
                    need(!ended && !responseClosed && Buffer.isBuffer(chunk) &&
                        BigInt(chunk.length) <= expected.bytes - BigInt(size), 'PROVIDER_ACTION_PUBLIC_SOURCE_BOUND');
                    if (chunk.length) chunks.push(Buffer.from(chunk));
                    size += chunk.length;
                }));
                response.on('end', () => guarded(() => {
                    need(!ended && !responseClosed, 'PROVIDER_ACTION_PUBLIC_SOURCE_EOF'); ended = true;
                }));
            });
            check(end, signal);
            request.end();
            deadline();
        } catch (error) { fail(error); }
    });
}

function retainSource(directory, raw, end, signal) {
    check(end, signal);
    let descriptor = null, original = null;
    try {
        // Never replace a prior acquisition. Native preparation independently
        // reopens this fixed file under its native private-directory checks.
        descriptor = fs.openSync(path.join(directory, 'provider-source.cjs'),
            fs.constants.O_WRONLY | fs.constants.O_CREAT | fs.constants.O_EXCL | (fs.constants.O_NOFOLLOW || 0), 0o600);
        check(end, signal);
        need(fs.writeSync(descriptor, raw) === raw.length, 'PROVIDER_ACTION_PUBLIC_SOURCE_WRITE');
        fs.fsyncSync(descriptor);
        check(end, signal);
    } catch (error) { original = error; }
    finally {
        if (descriptor !== null) {
            try { fs.closeSync(descriptor); } catch (error) { original = original || error; pending.push({descriptor, error}); }
        }
    }
    if (original) throw original;
    check(end, signal);
}

async function run() {
    return runFixed('trusted-main');
}

async function runInitialRecipient() {
    return runFixed('initial-recipient');
}

async function runFixed(origin) {
    need(origin === 'trusted-main' || origin === 'initial-recipient', 'PROVIDER_ACTION_FIXED_ORIGIN');
    const operations = origin === 'trusted-main' ? ['window', 'prepare', 'readback'] :
        ['initial-window', 'initial-prepare', 'initial-readback'];
    const scopePrefix = origin === 'trusted-main' ? '' : 'INITIAL_RECIPIENT_';
    need(!used, 'PROVIDER_ACTION_ONE_INVOCATION'); used = true;
    const phase = process.env.INPUT_PHASE, python = process.env.INPUT_PYTHON, toolPath = process.env['INPUT_TOOL-PATH'];
    need(Object.hasOwn(BUNDLES, phase) && /^24\./.test(process.versions.node) && absolute(process.execPath) &&
        absolute(python) && /^python(?:3(?:\.\d+)?)?(?:\.exe)?$/.test(path.basename(python)) &&
        typeof toolPath === 'string' && toolPath.split(windows ? ';' : ':').every(absolute), 'PROVIDER_ACTION_TOOLS');
    need(process.env.GITHUB_ACTIONS === 'true' && process.env.RUNNER_ENVIRONMENT === 'github-hosted' &&
        process.env.GITHUB_REPOSITORY === 'p2pKit/P2pKit' && process.env.GITHUB_WORKSPACE === workspace &&
        process.env.GITHUB_EVENT_NAME === 'workflow_dispatch' && process.env.GITHUB_JOB === 'populate' &&
        process.env.GITHUB_SERVER_URL === 'https://github.com' && process.env.GITHUB_API_URL === 'https://api.github.com',
    'PROVIDER_ACTION_HOSTED_CONTEXT');
    need(!['GH_TOKEN', 'GITHUB_TOKEN', 'P2PKIT_ACTIONS_READ_TOKEN'].some(name => Object.hasOwn(process.env, name)),
        'PROVIDER_ACTION_API_CREDENTIALS');
    const claimNames = [...BASE_CLAIMS, ...(phase === 'lookup' ? LOOKUP_CLAIMS : [])];
    const helperEnv = Object.fromEntries([...IDENTITY, ...MARKERS, 'SYSTEMROOT', 'WINDIR', 'COMSPEC', 'PATHEXT',
        ...claimNames.map(name => 'P2PKIT_BOOTSTRAP_' + name)]
        .filter(name => Object.hasOwn(process.env, name)).map(name => [name, process.env[name]]));
    need(absolute(helperEnv.RUNNER_TEMP), 'PROVIDER_ACTION_PRIVATE_PARENT');
    Object.assign(helperEnv, {PATH: toolPath, LANG: 'C', LC_ALL: 'C', GIT_TERMINAL_PROMPT: '0',
        ...(windows ? {USERPROFILE: helperEnv.RUNNER_TEMP, TEMP: helperEnv.RUNNER_TEMP, TMP: helperEnv.RUNNER_TEMP} :
            {HOME: helperEnv.RUNNER_TEMP, TMPDIR: helperEnv.RUNNER_TEMP})});
    const preparationHash = helperEnv['P2PKIT_BOOTSTRAP_' + (phase === 'save' ? 'SAVE' : 'PROBE') + '_PREPARATION_SHA256'];
    need(typeof preparationHash === 'string' && /^[0-9a-f]{64}$/.test(preparationHash), 'PROVIDER_ACTION_ORIGINAL_HASH');
    const controller = new AbortController(), signal = controller.signal;
    const abort = () => controller.abort();
    const signals = ['SIGINT', 'SIGTERM', ...(windows ? ['SIGBREAK'] : [])];
    for (const number of signals) process.on(number, abort);
    try {
        // Pair LOCAL with the NEW helper RAW observation, never descriptor firstNs.
        const anchor = process.hrtime.bigint();
        const window = (await native(python, [operations[0], phase], helperEnv, anchor + 45n * NS, signal)).value;
        need(window.scope === scopePrefix + 'PROVIDER_ORIGINAL_WINDOW_PENDING_HELPER_RETURN_V1' && window.phase === phase &&
            window.preparationSha256 === preparationHash && window.providerAdmission === 'NOT_ESTABLISHED' &&
            absolute(window.directory), 'PROVIDER_ACTION_ORIGINAL_WINDOW');
        const issued = scalar(window.issuedNs), first = scalar(window.firstNs), end = scalar(window.hardEndNs);
        const observed = scalar(window.observedNs), localEnd = anchor + end - first, workEnd = localEnd - 45n * NS;
        need(issued <= first && first <= observed && observed < end - 45n * NS && end <= issued + 180n * NS,
            'PROVIDER_ACTION_ORIGINAL_INTERVAL');
        check(workEnd, signal);
        const raw = await acquire(window.bundle, phase, workEnd, signal);
        retainSource(window.directory, raw, workEnd, signal);
        const preparation = (await native(python, [operations[1], phase, '--node', process.execPath, '--tool-path', toolPath],
            helperEnv, workEnd, signal)).value;
        need(preparation.scope === scopePrefix + 'PROVIDER_NATIVE_PREPARATION_PENDING_HELPER_RETURN_V1' && preparation.phase === phase &&
            preparation.preparationSha256 === preparationHash && preparation.providerExecution === 'NOT_PERFORMED' &&
            preparation.enclosingActionReturn === 'NOT_OBSERVED' && /^[0-9a-f]{64}$/.test(preparation.preparedSha256),
        'PROVIDER_ACTION_PREPARED_RETURN');
        const request = Buffer.from(preparation.request, 'ascii'), context = parse(request);
        need(context.phase === phase && context.issuedNs === window.issuedNs && context.hardEndNs === window.hardEndNs &&
            context.directory === path.join(window.directory, 'provider') && context.home === path.join(window.directory, 'provider-home') &&
            scalar(context.firstNs) >= observed && scalar(preparation.observedNs) >= scalar(context.firstNs),
        'PROVIDER_ACTION_PREPARED_CONTEXT');
        const providerEnv = {PATH: toolPath, GITHUB_WORKSPACE: workspace, LANG: 'C', LC_ALL: 'C',
            ...(windows ? {SYSTEMROOT: helperEnv.SYSTEMROOT, USERPROFILE: context.home, TEMP: context.home,
                TMP: context.home, PATHEXT: '.EXE'} : {HOME: context.home, TMPDIR: context.home})};
        for (const name of MARKERS) if (Object.hasOwn(helperEnv, name)) providerEnv[name] = helperEnv[name];
        // Runner-injected values stay private and go ONLY to the provider chain.
        for (const name of SERVICE) providerEnv[name] = process.env[name];
        check(workEnd, signal);
        providerReturn = await launchSupervisor({python, request, bindings: preparation.bindings,
            clockBindings: preparation.clockBindings, environment: providerEnv, localEndNs: localEnd,
            minimumRawNs: scalar(preparation.observedNs), signal});
        const returned = providerReturn;
        need(returned.transport === 'closed' && returned.childCloseObserved && returned.clockChildCloseObserved &&
            returned.originalRawDeadline === 'OBSERVED_AFTER_PROVIDER_CLOSE' && returned.summary.kind === 'success' &&
            returned.summary.suppliedExitCode === 0, 'PROVIDER_ACTION_PROVIDER_INCOMPLETE');
        check(localEnd, signal);
        const acknowledgement = returned.retainedBytes().stdout;
        const clock = parse(Buffer.from(returned.retainedClockBytes().stdout.toString('ascii').trimEnd(), 'ascii'));
        need(clock.invocationSha256 === returned.summary.invocationSha256 &&
            scalar(clock.observedNs) >= scalar(preparation.observedNs), 'PROVIDER_ACTION_POST_PROVIDER_CLOCK');
        const result = (await native(python, [operations[2], phase, '--prepared-sha256', preparation.preparedSha256,
            '--acknowledgement', acknowledgement.toString('base64'), '--minimum-ns', clock.observedNs],
        helperEnv, localEnd, signal)).value;
        need(result.scope === scopePrefix + 'PROVIDER_NATIVE_READBACK_PENDING_HELPER_RETURN_V1' && result.phase === phase &&
            result.providerAcceptance === 'NOT_ESTABLISHED' && /^[0-9a-f]{64}$/.test(result.readbackSha256) &&
            scalar(result.observedNs) >= scalar(clock.observedNs), 'PROVIDER_ACTION_READBACK_RETURN');
        const names = phase === 'save' ? [] : ['cache-primary-key', 'cache-matched-key', 'cache-hit'];
        need(result.outputs && Object.keys(result.outputs).sort().join('\0') === names.sort().join('\0') &&
            Object.values(result.outputs).every(value => typeof value === 'string' && value.length <= 512 &&
                /^[\x20-\x7e]*$/.test(value)), 'PROVIDER_ACTION_READBACK_OUTPUTS');
        check(localEnd, signal);
        return {outputs: {'readback-sha256': result.readbackSha256, ...result.outputs}, localEnd,
            scope: 'PROVIDER_ACTION_PENDING_ORIGINAL_RUNNER_RETURN', providerAcceptance: 'NOT_ESTABLISHED'};
    } catch (error) {
        // Retain returned live/unknown children and their original private
        // captures even when validation or a later readback refuses them.
        if (providerReturn !== null) pending.push({supervisor: providerReturn});
        throw error;
    } finally {
        for (const number of signals) process.removeListener(number, abort);
    }
}

async function main() {
    return mainFixed('trusted-main');
}

async function mainInitialRecipient() {
    return mainFixed('initial-recipient');
}

async function mainFixed(origin) {
    process.exitCode = 125; // An unresolved Promise must not silently succeed.
    try {
        const result = origin === 'trusted-main' ? await run() : await runInitialRecipient();
        const output = process.env.GITHUB_OUTPUT;
        need(absolute(output) && process.hrtime.bigint() < result.localEnd, 'PROVIDER_ACTION_OUTPUT_FENCE');
        // Only bounded output values/hashes, never private helper/provider bytes.
        fs.appendFileSync(output, Object.entries(result.outputs).map(([name, value]) => name + '=' + value + '\n').join(''));
        need(process.hrtime.bigint() < result.localEnd, 'PROVIDER_ACTION_OUTPUT_RETURN');
        process.exitCode = 0;
    } catch (error) {
        pending.push({supervisor: providerReturn, error});
        // Original errors/requests can carry private paths/service fields.
        process.stderr.write('CACHE_PROVIDER_ACTION_NOT_ACCEPTED\n');
    }
}

// These are service-only children of the genuine current-owning controller,
// never a replacement for that controller or for the bootstrap Action above.
// One private frame; no public GITHUB_OUTPUT, Git/API acquisition, configuration
// callback or caller-selected script/operation. The controller observes THIS
// process's eventual original exit/EOF/close before reading the native raw4.
function serviceFrame(end, signal) {
    return new Promise((resolve, reject) => {
        const input = process.stdin, chunks = [];
        let size = 0, ended = false, settled = false, timer = null;
        const finish = error => {
            if (settled) return;
            settled = true;
            if (timer !== null) clearTimeout(timer);
            signal.removeEventListener('abort', cancel);
            try { input.pause(); } catch (failure) { if (!error) error = failure; }
            if (error) {
                pending.push({input, chunks, error}); reject(new Error('PROVIDER_SERVICE_FRAME_INCOMPLETE'));
                return false;
            }
            return true;
        };
        const cancel = () => finish(new Error('PROVIDER_SERVICE_CANCELLED'));
        function deadline() {
            if (settled) return;
            const remaining = end - process.hrtime.bigint();
            if (remaining <= 0n) { cancel(); return; }
            timer = setTimeout(deadline, Math.max(1, Number(remaining / 1000000n)));
        }
        input.on('error', finish);
        input.on('data', chunk => {
            if (settled) return;
            try {
                check(end, signal);
                need(!ended && Buffer.isBuffer(chunk) && chunk.length <= 16384 - size,
                    'PROVIDER_SERVICE_FRAME_BOUND');
                if (chunk.length) chunks.push(Buffer.from(chunk));
                size += chunk.length;
            } catch (error) { finish(error); }
        });
        input.on('end', () => {
            if (settled) return;
            try {
                check(end, signal);
                need(!ended, 'PROVIDER_SERVICE_FRAME_EOF'); ended = true;
                const raw = Buffer.concat(chunks, size);
                need(raw.length > 1 && raw[raw.length - 1] === 10, 'PROVIDER_SERVICE_FRAME_LF');
                const value = parse(raw.subarray(0, -1));
                if (finish(null)) resolve({raw, value});
            } catch (error) { finish(error); }
        });
        signal.addEventListener('abort', cancel, {once: true});
        try { check(end, signal); input.resume(); deadline(); } catch (error) { finish(error); }
    });
}

function prelaunchClock(python, bindings, request, environment, end, signal) {
    // Original LOCAL anchor is owned by the caller. This child has exactly the
    // existing credential-free clock roster/backend; POST_CLOSE is a separate
    // mandatory launchSupervisor operation, not satisfied by these bytes.
    return new Promise((resolve, reject) => {
        let child = null, timer = null, started = false, exited = false, closed = false, settled = false;
        const chunks = {stdout: [], stderr: []}, sizes = {stdout: 0, stderr: 0}, eof = {stdout: false, stderr: false};
        const errors = [];
        function fail(error) {
            if (errors.length < 16) errors.push(error);
            if (settled) return;
            settled = true;
            if (timer !== null) clearTimeout(timer);
            signal.removeEventListener('abort', cancel);
            pending.push({child, chunks, errors});
            reject(new Error('PROVIDER_SERVICE_PRELAUNCH_INCOMPLETE'));
        }
        function cancel() {
            if (child !== null && !closed && !windows) {
                try { child.kill('SIGTERM'); } catch (error) { if (errors.length < 16) errors.push(error); }
            }
            // No Windows kill-as-retirement. Original native controller owns
            // remaining descendants and the same external RAW/LOCAL interval.
            fail(new Error('PROVIDER_SERVICE_PRELAUNCH_CANCELLED'));
        }
        function event(operation) {
            if (settled) return;
            try { check(end, signal); operation(); } catch (error) { fail(error); }
        }
        function deadline() {
            if (settled) return;
            const remaining = end - process.hrtime.bigint();
            if (remaining <= 0n) { cancel(); return; }
            timer = setTimeout(deadline, Math.max(1, Number(remaining / 1000000n)));
        }
        try {
            signal.addEventListener('abort', cancel, {once: true});
            check(end, signal);
            child = spawn(python, ['-I', '-B', '-S', clockHelper, '--prelaunch', canonical(bindings), canonical(request)],
                {cwd: workspace, env: environment, shell: false, detached: false, windowsHide: false,
                    stdio: ['ignore', 'pipe', 'pipe']});
            need(child instanceof ChildProcess, 'PROVIDER_SERVICE_CLOCK_CHILD');
            child.on('error', fail);
            child.on('spawn', () => event(() => {
                need(!started && !exited && !closed, 'PROVIDER_SERVICE_CLOCK_SPAWN'); started = true;
            }));
            child.on('exit', (code, nativeSignal) => event(() => {
                need(started && !exited && !closed && code === 0 && !Object.is(code, -0) && nativeSignal === null,
                    'PROVIDER_SERVICE_CLOCK_EXIT'); exited = true;
            }));
            child.on('close', (code, nativeSignal) => {
                closed = true;
                event(() => {
                    need(started && exited && code === 0 && !Object.is(code, -0) && nativeSignal === null &&
                        eof.stdout && eof.stderr && sizes.stderr === 0 && errors.length === 0,
                    'PROVIDER_SERVICE_CLOCK_CLOSE');
                    const raw = Buffer.concat(chunks.stdout, sizes.stdout);
                    need(raw.length > 1 && raw[raw.length - 1] === 10, 'PROVIDER_SERVICE_CLOCK_LF');
                    const value = parse(raw.subarray(0, -1)), observed = scalar(value.observedNs);
                    const domain = request.role === 'windows-x64' ?
                        'windows.QueryPerformanceCounter/QueryPerformanceFrequency.floor_ns' :
                        (request.role.startsWith('macos-') ? 'darwin' : 'linux') + '.clock_gettime_ns(CLOCK_MONOTONIC_RAW)';
                    need(raw.toString('ascii') === canonical({...request,
                        schema: 'P2PKIT_PROVIDER_PRELAUNCH_CLOCK_OBSERVATION_V1', domain, observedNs: value.observedNs}) + '\n' &&
                        observed >= scalar(request.minimumNs) && observed < scalar(request.hardEndNs),
                    'PROVIDER_SERVICE_CLOCK_BINDING');
                    check(end, signal);
                    settled = true;
                    if (timer !== null) clearTimeout(timer);
                    signal.removeEventListener('abort', cancel);
                    resolve({raw, observed});
                });
            });
            for (const name of ['stdout', 'stderr']) if (child[name]) child[name].on('error', fail);
            need(child.stdout && child.stderr, 'PROVIDER_SERVICE_CLOCK_PIPES');
            for (const name of ['stdout', 'stderr']) {
                child[name].on('data', chunk => event(() => {
                    const limit = name === 'stdout' ? 1024 : 4096;
                    need(started && !closed && !eof[name] && Buffer.isBuffer(chunk) && chunk.length <= limit - sizes[name],
                        'PROVIDER_SERVICE_CLOCK_BOUND');
                    if (chunk.length) chunks[name].push(Buffer.from(chunk));
                    sizes[name] += chunk.length;
                }));
                child[name].on('end', () => event(() => {
                    need(started && !closed && !eof[name], 'PROVIDER_SERVICE_CLOCK_EOF'); eof[name] = true;
                }));
            }
            deadline();
        } catch (error) { fail(error); }
    });
}

async function runRestoreService(origin) {
    need(origin === 'ordinary' || origin === 'initial-ordinary', 'PROVIDER_SERVICE_FIXED_ORIGIN');
    need(!used, 'PROVIDER_ACTION_ONE_INVOCATION'); used = true;
    const controller = new AbortController(), signal = controller.signal;
    const abort = () => controller.abort();
    const signals = ['SIGINT', 'SIGTERM', ...(windows ? ['SIGBREAK'] : [])];
    for (const number of signals) process.on(number, abort);
    try {
        const incoming = await serviceFrame(process.hrtime.bigint() + 45n * NS, signal);
        const frame = incoming.value, prefix = origin === 'ordinary' ? 'P2PKIT_ORDINARY_' : 'P2PKIT_INITIAL_ORDINARY_';
        need(Object.keys(frame).sort().join('\0') === ['bindings', 'clockBindings', 'python', 'request', 'schema', 'scope'].join('\0') &&
            frame.schema === 1n && frame.scope === prefix + 'RESTORE_SERVICE_REQUEST_V1' &&
            typeof frame.request === 'string' && frame.request.length <= 16384 && !/[^\x00-\x7f]/.test(frame.request),
        'PROVIDER_SERVICE_FRAME_FIELDS');
        const request = Buffer.from(frame.request, 'ascii'), context = parse(request);
        need(context.schema === 'P2PKIT_PROVIDER_SUPERVISOR_REQUEST_V1' && context.phase === 'restore' &&
            context.plan && context.plan.mode === 'consume' && context.node === process.execPath &&
            /^24\./.test(process.versions.node) && absolute(frame.python) &&
            /^python(?:3(?:\.\d+)?)?(?:\.exe)?$/.test(path.basename(frame.python)), 'PROVIDER_SERVICE_RESTORE_ONLY');
        const role = {linux: 'linux-', darwin: 'macos-', win32: 'windows-'}[process.platform] + process.arch;
        need(context.role === role && absolute(context.home) && absolute(context.node) &&
            typeof context.toolPath === 'string' && context.toolPath.split(windows ? ';' : ':').every(absolute),
        'PROVIDER_SERVICE_NATIVE_CONTEXT');
        const first = scalar(context.firstNs), issued = scalar(context.issuedNs), end = scalar(context.hardEndNs);
        const cut = scalar(context.workerCutoffNs);
        need(issued <= first && first < cut && cut === end - 30n * NS && end <= issued + 180n * NS &&
            issued + 45n * NS < cut, 'PROVIDER_SERVICE_ORIGINAL_WINDOW');
        const bindingNames = ['audit_processes', 'hosted_primary_abi', 'hosted_test_identity',
            'hosted_cache_bootstrap_identity', 'hosted_dependency_seed', 'hosted_initial_recipient_exception',
            'hosted_initial_recipient_stages', 'hosted_initial_recipient_bootstrap_identity', 'hosted_initial_ordinary_identity',
            'hosted_windows_files', 'hosted_dependency_seed_files', 'hosted_dependency_cache',
            ...(role.startsWith('macos-') ? ['hosted_lock_resources'] : []), 'hosted_job_clock', 'hosted_evidence_primitives',
            'hosted_test_query', 'hosted_cache_provider_environment',
            'hosted_cache_provider_tools', 'hosted_cache_provider_lifecycle', 'hosted_cache_provider_return',
            'hosted_cache_provider_worker', 'hosted_cache_provider_launch', 'hosted_cache_provider_supervisor_return',
            'hosted_cache_provider_supervisor', 'hosted_cache_provider_cancel', 'hosted_cache_provider_entry'];
        const clockNames = ['audit_processes', 'hosted_job_clock', 'hosted_cache_provider_clock',
            ...(role.startsWith('macos-') ? ['hosted_lock_resources'] : [])];
        for (const [bindings, names] of [[frame.bindings, bindingNames], [frame.clockBindings, clockNames]]) {
            need(bindings && Object.getPrototypeOf(bindings) === Object.prototype &&
                Object.keys(bindings).sort().join('\0') === names.sort().join('\0') &&
                Object.values(bindings).every(value => typeof value === 'string' && /^[0-9a-f]{64}$/.test(value)),
            'PROVIDER_SERVICE_SOURCE_BINDINGS');
        }
        need(clockNames.every(name => name === 'hosted_cache_provider_clock' || frame.clockBindings[name] === frame.bindings[name]),
            'PROVIDER_SERVICE_CLOCK_SOURCES');
        // Build a fresh exact service map. No ambient API/Git/evidence token is
        // accepted even if a caller tried to make it harmless by omission later.
        need(!['GH_TOKEN', 'GITHUB_TOKEN', 'P2PKIT_ACTIONS_READ_TOKEN', 'GITHUB_OUTPUT'].some(name =>
            Object.hasOwn(process.env, name)), 'PROVIDER_SERVICE_CREDENTIAL_BOUNDARY');
        const base = {PATH: context.toolPath, GITHUB_WORKSPACE: workspace, LANG: 'C', LC_ALL: 'C',
            ...(windows ? {SYSTEMROOT: process.env.SYSTEMROOT, USERPROFILE: context.home, TEMP: context.home,
                TMP: context.home, PATHEXT: '.EXE'} : {HOME: context.home, TMPDIR: context.home})};
        need(!windows || absolute(base.SYSTEMROOT), 'PROVIDER_SERVICE_SYSTEMROOT');
        for (const name of MARKERS) if (Object.hasOwn(process.env, name)) base[name] = process.env[name];
        const clockRequest = {schema: 'P2PKIT_PROVIDER_PRELAUNCH_CLOCK_REQUEST_V1', invocationSha256: hash(request),
            role, frequency: context.frequency.toString(), minimumNs: context.firstNs, hardEndNs: context.hardEndNs};
        const anchor = process.hrtime.bigint();
        const prelaunch = await prelaunchClock(frame.python, frame.clockBindings, clockRequest, base, anchor + 45n * NS, signal);
        // Earlier NODE LOCAL plus freshly sampled RAW remaining time. Never
        // Python's epoch or now+(end-oldPreparationFirst), which renews time.
        const localEnd = anchor + end - prelaunch.observed;
        check(localEnd - 45n * NS, signal);
        const env = {...base};
        for (const name of SERVICE) env[name] = process.env[name];
        providerReturn = await launchSupervisor({python: frame.python, request, bindings: frame.bindings,
            clockBindings: frame.clockBindings, environment: env, localEndNs: localEnd,
            minimumRawNs: prelaunch.observed, signal});
        const returned = providerReturn;
        need(returned.transport === 'closed' && returned.childCloseObserved && returned.clockChildCloseObserved &&
            returned.originalRawDeadline === 'OBSERVED_AFTER_PROVIDER_CLOSE' && returned.summary.kind === 'success' &&
            returned.summary.suppliedExitCode === 0, 'PROVIDER_SERVICE_PROVIDER_INCOMPLETE');
        check(localEnd, signal);
        const ack = returned.retainedBytes().stdout, post = returned.retainedClockBytes().stdout;
        need(ack.length <= 4096 && post.length <= 1024, 'PROVIDER_SERVICE_RETURN_BOUND');
        const raw = Buffer.from(canonical({schema: 1n, scope: prefix + 'RESTORE_SERVICE_RETURN_V1',
            controllerRequestSha256: hash(incoming.raw), supervisorRequestSha256: hash(request),
            acknowledgement: ack.toString('ascii'), prelaunchClock: prelaunch.raw.toString('ascii'),
            postCloseClock: post.toString('ascii'), enclosingNodeReturn: 'NOT_OBSERVED',
            providerAcceptance: 'NOT_ESTABLISHED'}) + '\n', 'ascii');
        need(raw.length <= 16384, 'PROVIDER_SERVICE_RETURN_BOUND');
        check(localEnd, signal);
        return {raw, localEnd};
    } catch (error) {
        if (providerReturn !== null) pending.push({supervisor: providerReturn});
        throw error;
    } finally {
        for (const number of signals) process.removeListener(number, abort);
    }
}

async function runOrdinaryRestoreService() { return runRestoreService('ordinary'); }
async function runInitialOrdinaryRestoreService() { return runRestoreService('initial-ordinary'); }

async function serviceMain(initial) {
    process.exitCode = 66;
    try {
        const result = await (initial ? runInitialOrdinaryRestoreService() : runOrdinaryRestoreService());
        need(process.hrtime.bigint() < result.localEnd, 'PROVIDER_SERVICE_OUTPUT_FENCE');
        await new Promise((resolve, reject) => process.stdout.write(result.raw, error => error ? reject(error) : resolve()));
        need(process.hrtime.bigint() < result.localEnd, 'PROVIDER_SERVICE_OUTPUT_RETURN');
        process.exitCode = 0;
    } catch (error) { pending.push({supervisor: providerReturn, error}); }
}

module.exports = Object.freeze({run, main, runInitialRecipient, mainInitialRecipient,
    runOrdinaryRestoreService, runInitialOrdinaryRestoreService});
if (require.main === module) {
    process.exitCode = 66;
    if (process.argv.length === 3 && process.argv[2] === '--ordinary-restore-service') void serviceMain(false);
    else if (process.argv.length === 3 && process.argv[2] === '--initial-ordinary-restore-service') void serviceMain(true);
}
