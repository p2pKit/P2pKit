'use strict';
// Authored offline models, not an executed result or hosted/provider admission.
// Real source reads and JSON/Buffer operations; spawn, HTTP, files, clocks,
// signals, provider returns and the pinned bundle's digest are explicit models.
// No real child_process/https import, native helper, bundle or credential access.
const assert = require('node:assert/strict');
const {createHash} = require('node:crypto');
const {EventEmitter} = require('node:events');
const {readFileSync} = require('node:fs');
const paths = require('node:path');
const vm = require('node:vm');

const source = readFileSync(paths.join(__dirname, '../hosted-cache-provider-action.cjs'), 'utf8');
const action = readFileSync(paths.join(__dirname, '../../.github/actions/dependency-cache-provider/action.yml'), 'utf8');
const entry = readFileSync(paths.join(__dirname, '../../.github/actions/dependency-cache-provider/index.cjs'), 'utf8');
const NS = 1000000000n;
const PIN = 'caa296126883cff596d87d8935842f9db880ef25';
const META = {
    save: {entry: 'save-only', bytes: 3202441n, sha256: '7fb63f90f06ce6a10f39d40a113f99791bffdedad5394cdad5b4dfaa644559cb'},
    lookup: {entry: 'restore-only', bytes: 3202022n, sha256: '6255afaa3956351b8cfefc1e82f026b4db418a10678a8eaddf3d6c55f81744de'},
};
const cases = [];
const test = (name, run) => cases.push({name, run});
const sha = raw => createHash('sha256').update(raw).digest('hex');
function wire(value) {
    if (typeof value === 'bigint') return value.toString();
    if (Array.isArray(value)) return '[' + value.map(wire).join(',') + ']';
    if (value !== null && typeof value === 'object') return '{' + Object.keys(value).sort().map(
        key => JSON.stringify(key) + ':' + wire(value[key])).join(',') + '}';
    return JSON.stringify(value);
}
const settle = promise => promise.then(value => ({value}), error => ({error}));
async function turn() { await Promise.resolve(); await Promise.resolve(); }
function refused(outcome, reason) {
    assert(outcome.error instanceof Error, 'a modeled refusal must reject, not return success');
    assert.equal(outcome.error.message, reason);
}
function fixture(role = 'linux-x64', phase = 'save') {
    const windows = role === 'windows-x64', path = windows ? paths.win32 : paths.posix;
    const root = windows ? 'C:\\model\\repo' : '/model/repo';
    const temp = windows ? 'C:\\model\\private' : '/model/private';
    const tools = windows ? 'C:\\model\\tools' : '/model/tools';
    const directory = path.join(temp, 'original' + (phase === 'save' ? '-save' : '-probe'));
    const python = path.join(tools, windows ? 'python.exe' : 'python3');
    const node = path.join(tools, windows ? 'node.exe' : 'node');
    const preparationHash = 'a'.repeat(64), preparedHash = 'b'.repeat(64), readbackHash = 'c'.repeat(64);
    const meta = META[phase];
    const bundle = {url: 'https://raw.githubusercontent.com/actions/cache/' + PIN + '/dist/' + meta.entry + '/index.js',
        bytes: meta.bytes, sha256: meta.sha256, basename: 'provider.cjs'};
    const window = {scope: 'PROVIDER_ORIGINAL_WINDOW_PENDING_HELPER_RETURN_V1', phase,
        preparationSha256: preparationHash, providerAdmission: 'NOT_ESTABLISHED', directory,
        bundle, issuedNs: String(100n * NS), firstNs: String(101n * NS), observedNs: String(102n * NS),
        hardEndNs: String(280n * NS), ownerClose: 'KNOWN_RESOURCE_CLOSE_ONLY', originalHelperReturn: 'PENDING'};
    const context = {phase, role, issuedNs: window.issuedNs, firstNs: String(110n * NS), hardEndNs: window.hardEndNs,
        directory: path.join(directory, 'provider'), home: path.join(directory, 'provider-home'), node, toolPath: tools,
        frequency: windows ? 9223372036854775807n : NS};
    const prepared = {scope: 'PROVIDER_NATIVE_PREPARATION_PENDING_HELPER_RETURN_V1', phase,
        preparationSha256: preparationHash, preparedSha256: preparedHash, providerExecution: 'NOT_PERFORMED',
        enclosingActionReturn: 'NOT_OBSERVED', request: wire(context), observedNs: String(111n * NS),
        bindings: {hosted_cache_provider_worker: 'd'.repeat(64)},
        clockBindings: {hosted_cache_provider_clock: 'e'.repeat(64)},
        ownerClose: 'KNOWN_RESOURCE_CLOSE_ONLY', originalHelperReturn: 'PENDING'};
    const outputs = phase === 'save' ? {} : {'cache-primary-key': 'MODEL_KEY', 'cache-matched-key': 'MODEL_KEY', 'cache-hit': 'true'};
    const readback = {scope: 'PROVIDER_NATIVE_READBACK_PENDING_HELPER_RETURN_V1', phase,
        readbackSha256: readbackHash, providerAcceptance: 'NOT_ESTABLISHED', outputs,
        observedNs: String(270n * NS), ownerClose: 'KNOWN_RESOURCE_CLOSE_ONLY', originalHelperReturn: 'PENDING'};
    return {role, phase, windows, path, root, temp, tools, directory, python, node, bundle, context,
        preparationHash, preparedHash, readbackHash, window, prepared, readback};
}

function model(f = fixture(), settings = {}) {
    let now = 100n * NS, serial = 0;
    const timers = new Map(), calls = {spawn: [], http: [], files: [], supervisor: [], logs: []};
    const env = {INPUT_PHASE: f.phase, INPUT_PYTHON: f.python, 'INPUT_TOOL-PATH': f.tools,
        GITHUB_ACTIONS: 'true', RUNNER_ENVIRONMENT: 'github-hosted', GITHUB_REPOSITORY: 'p2pKit/P2pKit',
        GITHUB_WORKSPACE: f.root, RUNNER_TEMP: f.temp, RUNNER_NAME: 'MODEL_RUNNER', GITHUB_JOB: 'populate',
        GITHUB_EVENT_NAME: 'workflow_dispatch', GITHUB_SERVER_URL: 'https://github.com', GITHUB_API_URL: 'https://api.github.com',
        SYSTEMROOT: 'C:\\Windows', GITHUB_OUTPUT: f.path.join(f.temp, 'action-output.txt'),
        ACTIONS_RUNTIME_TOKEN: 'MODEL_NOT_A_CREDENTIAL', ACTIONS_RESULTS_URL: 'https://example.invalid/',
        ACTIONS_CACHE_SERVICE_V2: 'True'};
    for (const name of ['PRODUCER_OUTCOME', 'SAVE_PREPARE_OUTCOME', 'SAVE_OUTCOME', 'AFTER_SAVE_OUTCOME', 'PROBE_PREPARE_OUTCOME']) {
        env['P2PKIT_BOOTSTRAP_' + name] = 'success';
    }
    for (const name of ['HANDOFF_SHA256', 'PRODUCER_RETURN_SHA256', 'SAVE_PREPARATION_SHA256', 'AFTER_SAVE_SHA256',
        'PROBE_PREPARATION_SHA256']) env['P2PKIT_BOOTSTRAP_' + name] = f.preparationHash;
    Object.assign(env, settings.env || {});
    const processModel = Object.assign(new EventEmitter(), {env, platform: f.windows ? 'win32' :
        f.role.startsWith('macos-') ? 'darwin' : 'linux', arch: f.role.endsWith('arm64') ? 'arm64' : 'x64',
        execPath: f.node, versions: {node: '24.MODEL'}, hrtime: {bigint: () => now},
        stderr: {write: raw => { calls.logs.push(String(raw)); return true; }}});
    class Child extends EventEmitter {
        constructor() {
            super(); this.stdout = new EventEmitter(); this.stderr = new EventEmitter(); this.kills = [];
        }
        kill(signal) { this.kills.push(signal); return true; }
    }
    class Request extends EventEmitter {
        constructor() { super(); this.ends = 0; this.destroys = 0; }
        end() {
            this.ends++;
            assert.equal(this.listenerCount('response'), 1, 'attach the single response listener before sending');
            assert(this.listenerCount('error') > 0 && this.listenerCount('close') > 0);
            if (settings.requestEndThrows) throw new Error('MODEL_PRIVATE_REQUEST_END');
        }
        destroy() {
            this.destroys++;
            if (settings.requestDestroyThrows) throw new Error('MODEL_PRIVATE_REQUEST_DESTROY');
        }
    }
    class Response extends EventEmitter {
        constructor() {
            super(); this.statusCode = 200; this.headers = {'content-length': f.bundle.bytes.toString()};
            this.complete = true; this.destroys = 0;
        }
        destroy() {
            this.destroys++;
            if (settings.responseDestroyThrows) throw new Error('MODEL_PRIVATE_RESPONSE_DESTROY');
        }
    }
    // This fixed synthetic nonexecutable body is NOT the pinned supplier bytes.
    // Only its digest is modeled, explicitly; other hashes use the real SHA-256.
    const body = () => Buffer.alloc(Number(f.bundle.bytes), 0x53);
    const cryptography = {createHash: algorithm => {
        const real = createHash(algorithm), chunks = [];
        return {update(raw) { chunks.push(Buffer.from(raw)); real.update(raw); return this; },
            digest(encoding) {
                const raw = Buffer.concat(chunks);
                if (!settings.realBundleDigest && raw.length === Number(f.bundle.bytes) && raw.equals(body())) {
                    assert.equal(algorithm, 'sha256'); assert.equal(encoding, 'hex'); return f.bundle.sha256;
                }
                return real.digest(encoding);
            }};
    }};
    const outputError = new Error('MODEL_PRIVATE_ACTION_OUTPUT');
    const filesystem = {
        constants: {O_WRONLY: 1, O_CREAT: 2, O_EXCL: 4, O_NOFOLLOW: 8},
        openSync: (...args) => { calls.files.push(['open', ...args]); return 42; },
        writeSync: (fd, raw) => {
            calls.files.push(['write', fd, raw.length]);
            return raw.length - (settings.shortWrite ? 1 : 0);
        },
        fsyncSync: fd => { calls.files.push(['sync', fd]); },
        closeSync: fd => {
            calls.files.push(['close', fd]);
            if (settings.closeThrows) throw new Error('MODEL_PRIVATE_FILE_CLOSE');
        },
        appendFileSync: (path, value) => {
            calls.files.push(['output', path, value]);
            if (settings.outputThrows) throw outputError;
            if (settings.outputCrossesEnd) now = 280n * NS;
        },
    };
    const acknowledgement = Buffer.from('MODEL_PRIVATE_SUPERVISOR_ACK\n');
    const supervisorResult = {transport: 'closed', childCloseObserved: true, clockChildCloseObserved: true,
        originalRawDeadline: 'OBSERVED_AFTER_PROVIDER_CLOSE',
        summary: {kind: 'success', suppliedExitCode: 0, invocationSha256: sha(Buffer.from(f.prepared.request))},
        retainedBytes: () => ({stdout: acknowledgement, stderr: Buffer.alloc(0)}),
        retainedClockBytes: () => ({stdout: Buffer.from(wire({invocationSha256: sha(Buffer.from(f.prepared.request)),
            observedNs: String(260n * NS)}) + '\n'), stderr: Buffer.alloc(0)}),
        originalChild: () => 'MODEL_LIVE_OR_CLOSED_CHILD', originalClockChild: () => 'MODEL_CLOCK_CHILD'};
    const modules = {
        'node:child_process': {ChildProcess: Child, spawn: (python, argv, options) => {
            const child = new Child();
            calls.spawn.push({python, argv, options, child});
            if (settings.partialStdio) child.stdout = null;
            if (settings.spawnThrows) throw new Error('MODEL_PRIVATE_SPAWN');
            return child;
        }},
        'node:crypto': cryptography, 'node:fs': filesystem, 'node:path': paths,
        'node:https': {request: (url, options) => {
            const request = new Request(); calls.http.push({url, options, request}); return request;
        }},
        'node:timers': {setTimeout: (callback, ms) => {
            const id = ++serial; timers.set(id, {callback, ms}); return id;
        }, clearTimeout: id => timers.delete(id)},
        './hosted-cache-provider-node-bridge.cjs': {launchSupervisor: async options => {
            calls.supervisor.push(options); return supervisorResult;
        }},
    };
    const module = {exports: {}};
    const context = vm.createContext({module, __dirname: f.path.join(f.root, 'scripts'),
        require: name => { assert(Object.hasOwn(modules, name), 'closed modeled Action import roster'); return modules[name]; },
        process: processModel, Object, Reflect, JSON, Buffer, AbortController, Error});
    vm.runInContext(source, context, {timeout: 1000});
    // Fixed test-only lexical inspection; no production inspection/export API.
    const internals = vm.runInContext('({native, acquire, retainSource, parse, canonical, pending})', context, {timeout: 1000});
    function completeNative(index, {value = [f.window, f.prepared, f.readback][index], raw = null,
        code = 0, signal = null, spawn = true, eof = true, close = true, stderr = null} = {}) {
        const child = calls.spawn[index].child;
        if (spawn) child.emit('spawn');
        if (raw !== false) child.stdout.emit('data', raw || Buffer.from(wire(value)));
        if (stderr) child.stderr.emit('data', stderr);
        if (eof) { child.stdout.emit('end'); child.stderr.emit('end'); }
        child.emit('exit', code, signal);
        if (close) child.emit('close', code, signal);
    }
    function respond(changes = {}) {
        const response = Object.assign(new Response(), changes);
        calls.http[0].request.emit('response', response);
        return response;
    }
    function completeHttp({raw = body(), requestClose = true, responseClose = true, changes = {}} = {}) {
        const response = respond(changes);
        response.emit('data', raw); response.emit('end');
        if (responseClose) response.emit('close');
        if (requestClose) calls.http[0].request.emit('close');
        return response;
    }
    function expire(value) {
        now = value;
        const current = [...timers.values()];
        assert.equal(current.length, 1, 'exactly one original local timer');
        current[0].callback();
    }
    return {f, api: module.exports, internals, calls, timers, env, process: processModel, supervisorResult, outputError,
        body, respond, completeHttp, completeNative, expire, setNow: value => { now = value; }};
}

async function reachProvider(m) {
    assert.equal(m.calls.spawn.length, 1);
    m.completeNative(0); await turn();
    assert.equal(m.calls.http.length, 1);
    m.completeHttp(); await turn();
    assert.equal(m.calls.spawn.length, 2);
    m.completeNative(1); await turn();
    assert.equal(m.calls.supervisor.length, 1);
}
async function completeRun(m) {
    await reachProvider(m);
    assert.equal(m.calls.spawn.length, 3);
    m.completeNative(2); await turn();
}

test('Action uses fixed Node24 entry and has no post/save hook or token input', () => {
    assert.match(action, /runs:\n  using: node24\n  main: index\.cjs\n$/);
    assert(!/^\s*(post|pre|token|endpoint|command):/m.test(action));
    assert.match(entry, /require\('\.\.\/\.\.\/\.\.\/scripts\/hosted-cache-provider-action\.cjs'\)\.main\(\);/);
});
for (const role of ['linux-x64', 'windows-x64', 'macos-arm64']) {
    test(role + ' complete modeled Action remains transport-only and credential-separated', async () => {
        const m = model(fixture(role)), pending = settle(m.api.run());
        await completeRun(m);
        const result = await pending;
        assert(!result.error);
        assert.equal(result.value.scope, 'PROVIDER_ACTION_PENDING_ORIGINAL_RUNNER_RETURN');
        assert.equal(result.value.providerAcceptance, 'NOT_ESTABLISHED');
        assert.equal(result.value.localEnd, 279n * NS, 'LOCAL-before-new-first-RAW, not old issuance or renewed180');
        assert.deepEqual({...result.value.outputs}, {'readback-sha256': m.f.readbackHash});
        for (const call of m.calls.spawn) {
            assert.equal(call.python, m.f.python);
            assert.deepEqual([...call.argv.slice(0, 4)], ['-I', '-B', '-S', m.f.path.join(m.f.root, 'scripts/hosted_cache_provider_native.py')]);
            assert.equal(call.options.cwd, m.f.root);
            assert.equal(call.options.shell, false);
            assert.deepEqual([...call.options.stdio], ['ignore', 'pipe', 'pipe']);
            assert(!Object.keys(call.options.env).some(name => name.startsWith('ACTIONS_') || name === 'GH_TOKEN'));
        }
        const provider = m.calls.supervisor[0];
        assert.equal(provider.environment.ACTIONS_RUNTIME_TOKEN, 'MODEL_NOT_A_CREDENTIAL');
        assert.equal(provider.environment.ACTIONS_RESULTS_URL, 'https://example.invalid/');
        assert.equal(provider.localEndNs, 279n * NS);
        assert.equal(provider.minimumRawNs, 111n * NS);
        assert(!Object.keys(provider.environment).some(name => name.startsWith('P2PKIT_BOOTSTRAP_') || name === 'GITHUB_OUTPUT'));
        assert.equal(m.calls.spawn[2].argv.at(-1), String(260n * NS));
        assert.equal(m.timers.size, 0);
        assert.equal(m.process.listenerCount('SIGTERM'), 0);
        assert.equal(m.calls.logs.length, 0);
    });
}
test('lookup carries only original bounded three-field outputs', async () => {
    const m = model(fixture('linux-x64', 'lookup')), pending = settle(m.api.run());
    await completeRun(m);
    assert.deepEqual({...((await pending).value.outputs)}, {'readback-sha256': m.f.readbackHash, ...m.f.readback.outputs});
    assert.equal(m.calls.http[0].url, m.f.bundle.url);
});
test('private JSON preserves full-width native integers', () => {
    const m = model(fixture('windows-x64'));
    const result = m.internals.parse(Buffer.from(wire(m.f.context)));
    assert.equal(result.frequency, 9223372036854775807n);
});
test('private JSON refuses normalized noncanonical and fractional aliases', () => {
    const m = model();
    for (const raw of ['{"x":1}\n', '{"x":1.0}', '{"x":1e0}', '{"x":1,"x":1}', '{"x":-0}', '{"z":1,"a":2}']) {
        assert.throws(() => m.internals.parse(Buffer.from(raw)));
    }
});
test('native needs original spawn before success bytes', async () => {
    const m = model(), c = new AbortController();
    const result = settle(m.internals.native(m.f.python, ['window', 'save'], {}, 200n * NS, c.signal));
    m.completeNative(0, {spawn: false});
    refused(await result, 'PROVIDER_ACTION_NATIVE_INCOMPLETE');
});
test('native nonzero exit is not helper acceptance', async () => {
    const m = model(), c = new AbortController();
    const result = settle(m.internals.native(m.f.python, ['window', 'save'], {}, 200n * NS, c.signal));
    m.completeNative(0, {code: 125});
    refused(await result, 'PROVIDER_ACTION_NATIVE_INCOMPLETE');
});
test('native missing EOF is not a known-close helper result', async () => {
    const m = model(), c = new AbortController();
    const result = settle(m.internals.native(m.f.python, ['window', 'save'], {}, 200n * NS, c.signal));
    m.completeNative(0, {eof: false});
    refused(await result, 'PROVIDER_ACTION_NATIVE_INCOMPLETE');
});
test('native stderr is retained privately and refuses success', async () => {
    const m = model(), c = new AbortController(), raw = Buffer.from('MODEL_PRIVATE_HELPER_DIAGNOSTIC');
    const result = settle(m.internals.native(m.f.python, ['window', 'save'], {}, 200n * NS, c.signal));
    m.completeNative(0, {stderr: raw});
    refused(await result, 'PROVIDER_ACTION_NATIVE_INCOMPLETE');
    assert(Buffer.concat(m.internals.pending[0].chunks.stderr).equals(raw));
    assert.equal(m.calls.logs.length, 0);
});
test('native refuses stdout beyond the existing16KiB private protocol bound', async () => {
    const m = model(), c = new AbortController();
    const result = settle(m.internals.native(m.f.python, ['window', 'save'], {}, 200n * NS, c.signal));
    m.completeNative(0, {raw: Buffer.alloc(16385, 0x20)});
    refused(await result, 'PROVIDER_ACTION_NATIVE_INCOMPLETE');
    assert.equal(m.internals.pending[0].chunks.stdout.length, 0);
});
test('native45 clamp retains original child on timeout without claiming retirement', async () => {
    const m = model(), c = new AbortController();
    const result = settle(m.internals.native(m.f.python, ['prepare', 'save'], {}, 279n * NS, c.signal));
    const child = m.calls.spawn[0].child;
    m.expire(145n * NS);
    refused(await result, 'PROVIDER_ACTION_NATIVE_INCOMPLETE');
    assert.equal(m.internals.pending[0].child, child);
    assert.deepEqual(child.kills, ['SIGTERM']);
    assert.equal(m.timers.size, 0);
});
test('native keeps a smaller original end instead of renewing45', async () => {
    const m = model(), c = new AbortController();
    const result = settle(m.internals.native(m.f.python, ['readback', 'save'], {}, 112n * NS, c.signal));
    m.expire(112n * NS);
    refused(await result, 'PROVIDER_ACTION_NATIVE_INCOMPLETE');
});
test('Windows helper cancellation retains unknown child and never kill(SIGTERM)', async () => {
    const m = model(fixture('windows-x64')), c = new AbortController();
    const result = settle(m.internals.native(m.f.python, ['window', 'save'], {}, 200n * NS, c.signal));
    c.abort();
    refused(await result, 'PROVIDER_ACTION_NATIVE_INCOMPLETE');
    assert.deepEqual(m.calls.spawn[0].child.kills, []);
    assert.equal(m.internals.pending[0].child, m.calls.spawn[0].child);
});
test('native failure and late errors retain at most16 original errors', async () => {
    const m = model(), c = new AbortController();
    const result = settle(m.internals.native(m.f.python, ['window', 'save'], {}, 200n * NS, c.signal));
    const original = new Error('MODEL_FIRST_ERROR'), child = m.calls.spawn[0].child;
    child.emit('error', original);
    for (let i = 0; i < 40; i++) child.stderr.emit('error', new Error('MODEL_LATE_ERROR'));
    refused(await result, 'PROVIDER_ACTION_NATIVE_INCOMPLETE');
    assert.equal(m.internals.pending[0].errors.length, 16);
    assert.equal(m.internals.pending[0].errors[0], original);
    assert.equal(m.internals.pending.length, 1);
});
test('native partial pipes install original error listeners before refusal', async () => {
    const m = model(fixture(), {partialStdio: true}), c = new AbortController();
    const result = settle(m.internals.native(m.f.python, ['window', 'save'], {}, 200n * NS, c.signal));
    m.calls.spawn[0].child.stderr.emit('error', new Error('MODEL_LATE_PIPE_ERROR'));
    refused(await result, 'PROVIDER_ACTION_NATIVE_INCOMPLETE');
    assert.equal(m.internals.pending[0].child, m.calls.spawn[0].child);
});
test('native refuses a claimed accepted return in place of the private pending protocol', async () => {
    const m = model(), c = new AbortController();
    const result = settle(m.internals.native(m.f.python, ['window', 'save'], {}, 200n * NS, c.signal));
    m.completeNative(0, {value: {...m.f.window, originalHelperReturn: 'ACCEPTED'}});
    refused(await result, 'PROVIDER_ACTION_NATIVE_INCOMPLETE');
});
test('native late actual close cannot accept earlier valid bytes', async () => {
    const m = model(), c = new AbortController();
    const result = settle(m.internals.native(m.f.python, ['window', 'save'], {}, 112n * NS, c.signal));
    m.completeNative(0, {close: false});
    m.setNow(112n * NS); m.calls.spawn[0].child.emit('close', 0, null);
    refused(await result, 'PROVIDER_ACTION_NATIVE_INCOMPLETE');
});
test('already cancelled native operation never spawns', () => {
    const m = model(), c = new AbortController(); c.abort();
    assert.throws(() => m.internals.native(m.f.python, ['window', 'save'], {}, 200n * NS, c.signal),
        {message: 'PROVIDER_ACTION_ORIGINAL_END'});
    assert.equal(m.calls.spawn.length, 0);
});
test('acquisition is one fixed credential-free GET and requires both original closes', async () => {
    const m = model(), c = new AbortController();
    let done = false;
    const result = settle(m.internals.acquire(m.f.bundle, 'save', 235n * NS, c.signal)).then(value => { done = true; return value; });
    const call = m.calls.http[0];
    assert.equal(call.url, m.f.bundle.url);
    assert.equal(call.options.method, 'GET'); assert.equal(call.options.agent, false);
    assert.deepEqual({...call.options.headers}, {accept: 'application/octet-stream'});
    const response = m.completeHttp({requestClose: false});
    await turn(); assert.equal(done, false);
    call.request.emit('close');
    assert((await result).value.equals(m.body()));
    assert.equal(response.destroys, 0); assert.equal(call.request.ends, 1);
    assert.equal(m.timers.size, 0);
});
test('late HTTP response after abort remains original retained ownership and is destroyed once', async () => {
    const m = model(), c = new AbortController();
    const result = settle(m.internals.acquire(m.f.bundle, 'save', 235n * NS, c.signal));
    c.abort(); refused(await result, 'PROVIDER_ACTION_PUBLIC_ACQUISITION_FAILED');
    const row = m.internals.pending[0], request = m.calls.http[0].request;
    assert.equal(row.request, request); assert.equal(row.response, null);
    const response = m.respond();
    assert.equal(row.response, response);
    assert.equal(response.destroys, 1); assert.equal(request.destroys, 1);
    response.emit('error', new Error('MODEL_LATE_HTTP_ERROR'));
    assert.equal(row.response, response); assert.equal(response.destroys, 1);
    assert.equal(m.internals.pending.length, 1);
});
test('HTTP errors after settlement remain bounded and preserve the first cause', async () => {
    const m = model(), c = new AbortController();
    const result = settle(m.internals.acquire(m.f.bundle, 'save', 235n * NS, c.signal));
    const original = new Error('MODEL_FIRST_HTTP_ERROR'), request = m.calls.http[0].request;
    request.emit('error', original);
    for (let i = 0; i < 40; i++) request.emit('error', new Error('MODEL_LATE_HTTP_ERROR'));
    refused(await result, 'PROVIDER_ACTION_PUBLIC_ACQUISITION_FAILED');
    assert.equal(m.internals.pending[0].errors.length, 16);
    assert.equal(m.internals.pending[0].errors[0], original);
    assert.equal(request.destroys, 1);
});
for (const [name, changes] of [
    ['redirect', {statusCode: 302, headers: {location: 'https://example.invalid/'}}],
    ['content encoding', {headers: {'content-encoding': 'gzip'}}],
    ['changed declared length', {headers: {'content-length': '12'}}],
]) {
    test('acquisition rejects ' + name + ' without following or retrying', async () => {
        const m = model(), c = new AbortController();
        const result = settle(m.internals.acquire(m.f.bundle, 'save', 235n * NS, c.signal));
        const response = m.respond(changes);
        refused(await result, 'PROVIDER_ACTION_PUBLIC_ACQUISITION_FAILED');
        assert.equal(response.destroys, 1); assert.equal(m.calls.http.length, 1);
    });
}
test('acquisition rejects short complete body', async () => {
    const m = model(), c = new AbortController();
    const result = settle(m.internals.acquire(m.f.bundle, 'save', 235n * NS, c.signal));
    m.completeHttp({raw: Buffer.from('MODEL_SHORT_BODY')});
    refused(await result, 'PROVIDER_ACTION_PUBLIC_ACQUISITION_FAILED');
});
test('real SHA-256 rejects synthetic full-length bytes without digest model', async () => {
    const m = model(fixture(), {realBundleDigest: true}), c = new AbortController();
    const result = settle(m.internals.acquire(m.f.bundle, 'save', 235n * NS, c.signal));
    m.completeHttp();
    refused(await result, 'PROVIDER_ACTION_PUBLIC_ACQUISITION_FAILED');
});
test('acquisition45 is bounded by its original remaining interval', async () => {
    for (const end of [112n * NS, 235n * NS]) {
        const m = model(), c = new AbortController();
        const result = settle(m.internals.acquire(m.f.bundle, 'save', end, c.signal));
        m.expire(end < 145n * NS ? end : 145n * NS);
        refused(await result, 'PROVIDER_ACTION_PUBLIC_ACQUISITION_FAILED');
        assert.equal(m.calls.http[0].request.destroys, 1);
    }
});
test('acquisition refuses a chunk exceeding the pinned byte ceiling', async () => {
    const m = model(), c = new AbortController();
    const result = settle(m.internals.acquire(m.f.bundle, 'save', 235n * NS, c.signal));
    const response = m.respond(); response.emit('data', Buffer.alloc(Number(m.f.bundle.bytes) + 1));
    refused(await result, 'PROVIDER_ACTION_PUBLIC_ACQUISITION_FAILED');
    assert.equal(m.internals.pending[0].chunks.length, 0);
});
test('request-send failure retains its original request and no retry', async () => {
    const m = model(fixture(), {requestEndThrows: true, requestDestroyThrows: true}), c = new AbortController();
    const result = await settle(m.internals.acquire(m.f.bundle, 'save', 235n * NS, c.signal));
    refused(result, 'PROVIDER_ACTION_PUBLIC_ACQUISITION_FAILED');
    assert.equal(m.internals.pending[0].request, m.calls.http[0].request);
    assert.equal(m.internals.pending[0].errors[0].message, 'MODEL_PRIVATE_REQUEST_END');
    assert.equal(m.calls.http[0].request.destroys, 1);
});
test('changed bundle pin refuses before any HTTP operation', () => {
    const m = model(), c = new AbortController();
    assert.throws(() => m.internals.acquire({...m.f.bundle, sha256: 'f'.repeat(64)}, 'save', 235n * NS, c.signal),
        {message: 'PROVIDER_ACTION_PINNED_BUNDLE'});
    assert.equal(m.calls.http.length, 0);
});
test('public source retention exclusively creates600 then writes syncs and closes', () => {
    const m = model(), c = new AbortController();
    m.internals.retainSource(m.f.directory, Buffer.from('MODEL_SOURCE'), 235n * NS, c.signal);
    assert.deepEqual(m.calls.files, [['open', m.f.path.join(m.f.directory, 'provider-source.cjs'), 15, 0o600],
        ['write', 42, 12], ['sync', 42], ['close', 42]]);
});
test('partial source write still closes and preserves primary failure over unknown close', () => {
    const m = model(fixture(), {shortWrite: true, closeThrows: true}), c = new AbortController();
    assert.throws(() => m.internals.retainSource(m.f.directory, Buffer.from('MODEL_SOURCE'), 235n * NS, c.signal),
        {message: 'PROVIDER_ACTION_PUBLIC_SOURCE_WRITE'});
    assert.equal(m.calls.files.filter(row => row[0] === 'close').length, 1);
    assert.equal(m.internals.pending[0].descriptor, 42);
});
test('ambient API credential refuses before helper or network', async () => {
    const m = model(fixture(), {env: {GH_TOKEN: 'MODEL_FORBIDDEN_NOT_A_CREDENTIAL'}});
    refused(await settle(m.api.run()), 'PROVIDER_ACTION_API_CREDENTIALS');
    assert.equal(m.calls.spawn.length, 0); assert.equal(m.calls.http.length, 0);
});
test('changed preparation hash refuses before helper allocation', async () => {
    const m = model(fixture(), {env: {P2PKIT_BOOTSTRAP_SAVE_PREPARATION_SHA256: 'bad'}});
    refused(await settle(m.api.run()), 'PROVIDER_ACTION_ORIGINAL_HASH');
    assert.equal(m.calls.spawn.length, 0);
});
test('window cannot widen the original180', async () => {
    const m = model(), pending = settle(m.api.run());
    m.completeNative(0, {value: {...m.f.window, hardEndNs: String(281n * NS)}});
    refused(await pending, 'PROVIDER_ACTION_ORIGINAL_INTERVAL');
    assert.equal(m.calls.http.length, 0);
});
test('window cannot return RAW below its new initial reading', async () => {
    const m = model(), pending = settle(m.api.run());
    m.completeNative(0, {value: {...m.f.window, observedNs: String(100n * NS)}});
    refused(await pending, 'PROVIDER_ACTION_ORIGINAL_INTERVAL');
    assert.equal(m.calls.http.length, 0);
});
test('changed prepared context never starts the provider', async () => {
    const m = model(), pending = settle(m.api.run());
    m.completeNative(0); await turn(); m.completeHttp(); await turn();
    m.completeNative(1, {value: {...m.f.prepared, request: wire({...m.f.context, issuedNs: '1'})}});
    refused(await pending, 'PROVIDER_ACTION_PREPARED_CONTEXT');
    assert.equal(m.calls.supervisor.length, 0);
});
test('incomplete bridge result retains original live capabilities and never starts readback', async () => {
    const m = model(); m.supervisorResult.transport = 'incomplete'; m.supervisorResult.summary = null;
    const pending = settle(m.api.run()); await reachProvider(m);
    refused(await pending, 'PROVIDER_ACTION_PROVIDER_INCOMPLETE');
    assert.equal(m.calls.spawn.length, 2);
    assert.equal(m.internals.pending[0].supervisor, m.supervisorResult);
    assert.equal(m.internals.pending[0].supervisor.originalChild(), 'MODEL_LIVE_OR_CLOSED_CHILD');
});
test('post-provider clock mismatch retains original result without readback', async () => {
    const m = model();
    m.supervisorResult.retainedClockBytes = () => ({stdout: Buffer.from(wire({
        invocationSha256: 'f'.repeat(64), observedNs: String(260n * NS)}))});
    const pending = settle(m.api.run()); await reachProvider(m);
    refused(await pending, 'PROVIDER_ACTION_POST_PROVIDER_CLOCK');
    assert.equal(m.calls.spawn.length, 2); assert.equal(m.internals.pending[0].supervisor, m.supervisorResult);
});
test('readback refusal keeps the already returned supervisor originals', async () => {
    const m = model(), pending = settle(m.api.run()); await reachProvider(m);
    m.completeNative(2, {value: {...m.f.readback, readbackSha256: 'bad'}});
    refused(await pending, 'PROVIDER_ACTION_READBACK_RETURN');
    assert.equal(m.internals.pending[0].supervisor, m.supervisorResult);
    assert(!m.calls.files.some(row => row[0] === 'output'));
});
test('lookup missing original output never becomes an exact-hit success', async () => {
    const m = model(fixture('linux-x64', 'lookup')), pending = settle(m.api.run()); await reachProvider(m);
    m.completeNative(2, {value: {...m.f.readback, outputs: {'cache-hit': 'true'}}});
    refused(await pending, 'PROVIDER_ACTION_READBACK_OUTPUTS');
});
test('main only writes bounded public fields after the whole modeled sequence', async () => {
    const m = model(), pending = m.api.main();
    assert.equal(m.process.exitCode, 125);
    await completeRun(m); await pending;
    assert.equal(m.process.exitCode, 0);
    assert.deepEqual(m.calls.files.filter(row => row[0] === 'output'),
        [['output', m.env.GITHUB_OUTPUT, 'readback-sha256=' + m.f.readbackHash + '\n']]);
    assert.equal(m.calls.logs.length, 0);
});
test('main failure logs only fixed refusal and stays125 with no private output', async () => {
    const m = model(fixture(), {spawnThrows: true});
    await m.api.main();
    assert.equal(m.process.exitCode, 125);
    assert.deepEqual(m.calls.logs, ['CACHE_PROVIDER_ACTION_NOT_ACCEPTED\n']);
    assert(!m.calls.files.some(row => row[0] === 'output'));
});
test('main output returning after the original end cannot report success', async () => {
    const m = model(fixture(), {outputCrossesEnd: true}), pending = m.api.main();
    await completeRun(m); await pending;
    assert.equal(m.process.exitCode, 125);
    assert.deepEqual(m.calls.logs, ['CACHE_PROVIDER_ACTION_NOT_ACCEPTED\n']);
    assert.equal(m.internals.pending[0].supervisor, m.supervisorResult);
    assert.equal(m.internals.pending[0].error.message, 'PROVIDER_ACTION_OUTPUT_RETURN');
});
test('main output exception retains exact error and original supervisor privately', async () => {
    const m = model(fixture(), {outputThrows: true}), pending = m.api.main();
    await completeRun(m); await pending;
    assert.equal(m.process.exitCode, 125);
    assert.deepEqual(m.calls.logs, ['CACHE_PROVIDER_ACTION_NOT_ACCEPTED\n']);
    assert.equal(m.internals.pending[0].supervisor, m.supervisorResult);
    assert.equal(m.internals.pending[0].error, m.outputError);
});
test('one Action invocation cannot retry after refusal', async () => {
    const m = model(fixture(), {spawnThrows: true});
    refused(await settle(m.api.run()), 'PROVIDER_ACTION_NATIVE_INCOMPLETE');
    refused(await settle(m.api.run()), 'PROVIDER_ACTION_ONE_INVOCATION');
    assert.equal(m.calls.spawn.length, 1);
});

// An unresolved model Promise must not exit0 without the complete aggregate.
process.exitCode = 1;
module.exports = (async () => {
    for (const item of cases) {
        await item.run();
        process.stdout.write('PASS ' + item.name + '\n');
    }
    process.stdout.write('RESULT: ' + cases.length + '/' + cases.length + ' offline Action model controls passed\n');
    process.exitCode = 0;
    return {passed: cases.length, total: cases.length};
})().catch(error => {
    process.stderr.write(String(error.stack || error) + '\n');
    process.exitCode = 1;
    throw error;
});
