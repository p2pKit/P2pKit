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

module.exports = Object.freeze({run, main, runInitialRecipient, mainInitialRecipient});
