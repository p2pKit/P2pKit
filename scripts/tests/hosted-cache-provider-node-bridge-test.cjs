'use strict';
// Authored offline controls; NOT an executed result or native/runner test.
// The actual adapter is evaluated with fixed fake spawn/timers/process seams.
// No real child_process import, child, native clock, credential or network use.
const assert = require('node:assert/strict');
const {createHash} = require('node:crypto');
const {EventEmitter} = require('node:events');
const {readFileSync} = require('node:fs');
const paths = require('node:path');
const vm = require('node:vm');
const receipt = require('../hosted-cache-provider-node-return.cjs');
const source = readFileSync(paths.join(__dirname, '../hosted-cache-provider-node-bridge.cjs'), 'utf8');
const cases = [];
const test = (name, run) => cases.push({name, run});
const sha = raw => createHash('sha256').update(raw).digest('hex');
function wire(value) {
    if (Array.isArray(value)) return '[' + value.map(wire).join(',') + ']';
    if (value !== null && typeof value === 'object') return '{' + Object.keys(value).sort().map(
        key => JSON.stringify(key) + ':' + wire(value[key])).join(',') + '}';
    return JSON.stringify(value);
}
function fixture(role = 'linux-x64', failed = false) {
    const windows = role === 'windows-x64', path = windows ? paths.win32 : paths.posix;
    const root = windows ? 'C:\\model\\repo' : '/model/repo';
    const directory = windows ? 'C:\\model\\capture' : '/model/capture';
    const home = windows ? 'C:\\model\\home' : '/model/home';
    const tools = windows ? 'C:\\model\\tools' : '/model/tools';
    const id = n => [1, windows ? n.toString(16).padStart(32, '0') : n];
    const request = {schema: 'P2PKIT_PROVIDER_SUPERVISOR_REQUEST_V1', role, frequency: 1000000000,
        firstNs: '100000000000', issuedNs: '100000000000', hardEndNs: '280000000000', workerCutoffNs: '250000000000',
        phase: 'save', job: '1'.repeat(32), outerId: '2'.repeat(32), innerId: '3'.repeat(32),
        directory, directoryIdentity: id(1), home, homeIdentity: id(2),
        node: path.join(tools, windows ? 'node.exe' : 'node'), toolPath: tools,
        plan: {role, scope: 'SUPPLIED_MODEL_NOT_AN_EXECUTABLE_PLAN'}};
    const rawRequest = Buffer.from(wire(request));
    const file = n => ({bytes: 100, sha256: sha(Buffer.from('MODEL_FILE_' + n)), identity: id(n)});
    const closes = ['scope', 'retirement-writer'];
    if (!windows) closes.push('stdout-reader', 'stderr-reader');
    closes.push('packet-reader', 'stderr', 'stdout', 'bundle', 'capture_directory', 'home', 'directory');
    const ack = {schema: 'P2PKIT_PROVIDER_SUPERVISOR_ACK_V1', invocationSha256: sha(rawRequest),
        workerRequestSha256: 'e'.repeat(64), kind: failed ? 'failed' : 'success',
        workerExitCode: failed ? 65 : 0, providerKind: failed ? 'failed' : 'success', observedNs: '210000000000',
        closedResources: closes, files: {native: file(3), stdout: file(4), stderr: file(5), packet: file(6)},
        enclosingNodeReturn: 'NOT_OBSERVED', originalRunnerOutcome: 'NOT_OBSERVED', providerAcceptance: 'NOT_ESTABLISHED'};
    return {windows, path, root, home, tools, request, rawRequest, rawAck: Buffer.from(wire(ack) + '\n'), code: failed ? 65 : 0};
}
function model(f = fixture(), {spawnThrows = false, partialStdio = false} = {}) {
    const calls = [], timers = new Map(), kills = [], writes = [];
    let now = 100000000000n, sequence = 0;
    class Child extends EventEmitter {
        constructor() {
            super(); this.pid = 12345;
            this.stdin = new EventEmitter(); this.stdout = new EventEmitter(); this.stderr = new EventEmitter();
            this.stdin.write = (raw, callback) => { writes.push(Buffer.from(raw)); callback(null); return true; };
        }
        kill(signal) { kills.push(signal); return true; }
    }
    const child = new Child(), module = {exports: {}};
    if (partialStdio) child.stdout = null;
    const modules = {
        'node:child_process': {ChildProcess: Child, spawn: (...args) => {
            calls.push(args); if (spawnThrows) throw new Error('MODEL_PRIVATE_SPAWN_ERROR'); return child;
        }},
        'node:path': paths,
        'node:timers': {setTimeout: (callback, ms) => { const id = ++sequence; timers.set(id, {callback, ms}); return id; },
            clearTimeout: id => timers.delete(id)},
        './hosted-cache-provider-node-return.cjs': receipt,
    };
    vm.runInNewContext(source, {module, __dirname: f.path.join(f.root, 'scripts'),
        require: name => { assert(Object.hasOwn(modules, name), 'closed model import'); return modules[name]; },
        process: {platform: f.windows ? 'win32' : f.request.role.startsWith('macos-') ? 'darwin' : 'linux',
            arch: f.request.role.endsWith('arm64') ? 'arm64' : 'x64', execPath: f.request.node,
            versions: {node: '24.20.0'}, hrtime: {bigint: () => now}},
        Object, Reflect, JSON, Buffer, SharedArrayBuffer, AbortSignal, Error}, {timeout: 1000});
    const controller = new AbortController();
    const environment = {PATH: f.tools, GITHUB_WORKSPACE: f.root, LANG: 'C', LC_ALL: 'C',
        ACTIONS_RUNTIME_TOKEN: 'MODEL_TOKEN_NOT_A_CREDENTIAL', ACTIONS_RESULTS_URL: 'https://example.invalid/',
        ACTIONS_CACHE_SERVICE_V2: 'True', ...(f.windows ? {SYSTEMROOT: 'C:\\Windows', USERPROFILE: f.home,
            TEMP: f.home, TMP: f.home, PATHEXT: '.EXE'} : {HOME: f.home, TMPDIR: f.home})};
    const options = {python: f.path.join(f.tools, f.windows ? 'python.exe' : 'python3'), request: f.rawRequest,
        bindings: {hosted_cache_provider_worker: 'a'.repeat(64), hosted_cache_provider_entry: 'b'.repeat(64),
            hosted_cache_provider_supervisor: 'c'.repeat(64)}, environment,
        localEndNs: now + 180000000000n, signal: controller.signal};
    function complete({end = true, code = f.code, signal = null} = {}) {
        child.emit('spawn'); child.stdout.emit('data', f.rawAck);
        if (end) { child.stdout.emit('end'); child.stderr.emit('end'); }
        child.emit('exit', code, signal); child.emit('close', code, signal);
    }
    return {api: module.exports, child, options, calls, kills, writes, timers, controller, complete,
        setNow: value => { now = value; }, expire: () => {
            now = options.localEndNs;
            const pending = [...timers.values()]; assert.equal(pending.length, 1); pending[0].callback();
        }};
}
for (const role of ['linux-x64', 'macos-arm64', 'macos-x64']) {
    test(role + ' fixed launch and original close remain transport-only', async () => {
        const f = fixture(role), m = model(f), pending = m.api.launchSupervisor(m.options);
        const [python, argv, options] = m.calls[0];
        assert.equal(python, m.options.python);
        assert.deepEqual([...argv.slice(0, 5)], ['-I', '-B', '-S', f.path.join(f.root, 'scripts/hosted_cache_provider_worker.py'), '--supervisor']);
        assert.equal(argv[6], f.rawRequest.toString('ascii'));
        assert.equal(options.shell, false); assert.equal(options.detached, false);
        assert.equal(options.env.ACTIONS_RUNTIME_TOKEN, 'MODEL_TOKEN_NOT_A_CREDENTIAL');
        assert(!Object.hasOwn(options.env, 'GH_TOKEN'));
        m.complete(); const result = await pending;
        assert.equal(result.transport, 'closed'); assert.equal(result.childCloseObserved, true);
        assert.equal(result.originalChild(), m.child); assert.equal(result.summary.kind, 'success');
        assert.equal(result.originalRawDeadline, 'NOT_OBSERVED');
        assert.equal(result.originalRunnerOutcome, 'NOT_OBSERVED'); assert.equal(result.providerAcceptance, 'NOT_ESTABLISHED');
        assert.equal(m.timers.size, 0);
    });
}
test('original known-failed exit stays failed', async () => {
    const m = model(fixture('linux-x64', true)), pending = m.api.launchSupervisor(m.options);
    m.complete(); const result = await pending;
    assert.equal(result.transport, 'closed'); assert.equal(result.summary.kind, 'failed');
});
test('Windows refuses the committed no-stdin roster before spawning', () => {
    const m = model(fixture('windows-x64'));
    assert.throws(() => m.api.launchSupervisor(m.options), /WINDOWS_COOPERATIVE_CONTROL_REQUIRED/);
    assert.equal(m.calls.length, 0);
});
test('future Windows stdin transport sends one C and never kill(SIGTERM)', async () => {
    const m = model(fixture('windows-x64'));
    m.options.bindings.hosted_cache_provider_cancel = 'd'.repeat(64);
    const pending = m.api.launchSupervisor(m.options);
    m.controller.abort(); m.controller.abort(); m.complete();
    const result = await pending;
    assert.deepEqual(m.writes, [Buffer.from('C')]); assert.deepEqual(m.kills, []);
    assert.equal(result.transport, 'incomplete'); assert.equal(result.cancellationRequested, true);
});
test('POSIX cancellation requests the original child once and cannot pass', async () => {
    const m = model(), pending = m.api.launchSupervisor(m.options);
    m.controller.abort(); m.controller.abort(); m.complete();
    assert.equal((await pending).transport, 'incomplete'); assert.deepEqual(m.kills, ['SIGTERM']);
});
test('exit without close cannot be completed or retired by timeout', async () => {
    const m = model(), pending = m.api.launchSupervisor(m.options);
    m.child.emit('spawn'); m.child.emit('exit', 0, null); m.expire();
    const result = await pending;
    assert.equal(result.transport, 'incomplete'); assert.equal(result.childCloseObserved, false);
    assert.equal(result.originalChild(), m.child); assert.deepEqual(m.kills, []);
    m.child.emit('close', 0, null); assert.equal(result.childCloseObserved, false);
});
test('a late close does not renew the original deadline', async () => {
    const m = model(), pending = m.api.launchSupervisor(m.options);
    m.setNow(m.options.localEndNs); m.complete();
    assert.equal((await pending).transport, 'incomplete');
});
test('missing EOF refuses even when exit and close both say zero', async () => {
    const m = model(), pending = m.api.launchSupervisor(m.options);
    m.complete({end: false}); assert.equal((await pending).transport, 'incomplete');
});
test('incomplete native exit cannot rehabilitate an earlier good ACK', async () => {
    const m = model(), pending = m.api.launchSupervisor(m.options);
    m.complete({code: 66}); assert.equal((await pending).transport, 'incomplete');
});
test('spawn error and private child errors never become public text', async () => {
    const m = model(fixture(), {spawnThrows: true});
    const result = await m.api.launchSupervisor(m.options);
    assert.equal(result.transport, 'incomplete'); assert.equal(result.originalChild(), null);
    assert(!JSON.stringify(result).includes('MODEL_PRIVATE'));
});
test('returned child with partial stdio retains later errors without throwing', async () => {
    const m = model(fixture(), {partialStdio: true});
    const result = await m.api.launchSupervisor(m.options);
    const error = new Error('MODEL_PRIVATE_RETURNED_CHILD_ERROR');
    const pipeError = new Error('MODEL_PRIVATE_RETURNED_PIPE_ERROR');
    assert.doesNotThrow(() => m.child.emit('error', error));
    assert.doesNotThrow(() => m.child.stderr.emit('error', pipeError));
    m.child.emit('close', 66, null);
    assert.equal(result.originalChild(), m.child); assert.equal(result.transport, 'incomplete');
    assert.equal(result.childCloseObserved, false); assert(result.originalErrors().includes(error));
    assert(result.originalErrors().includes(pipeError)); assert(!JSON.stringify(result).includes('MODEL_PRIVATE'));
});
test('opaque stderr is retained privately, never forwarded or serialized', async () => {
    const m = model(), pending = m.api.launchSupervisor(m.options);
    const raw = Buffer.from('MODEL_PRIVATE::error::NOT_AN_ACTION_COMMAND');
    m.child.emit('spawn'); m.child.stderr.emit('data', raw); m.child.stdout.emit('data', fixture().rawAck);
    m.child.stdout.emit('end'); m.child.stderr.emit('end'); m.child.emit('exit', 0, null); m.child.emit('close', 0, null);
    const result = await pending;
    assert.equal(result.transport, 'closed'); assert(result.retainedBytes().stderr.equals(raw));
    assert(!JSON.stringify(result).includes('MODEL_PRIVATE'));
    result.retainedBytes().stderr.fill(0); assert(result.retainedBytes().stderr.equals(raw));
});
test('API credentials and loader overrides cannot enter the child environment', () => {
    for (const name of ['GH_TOKEN', 'GITHUB_TOKEN', 'NODE_OPTIONS', 'PYTHONPATH', 'LD_PRELOAD']) {
        const m = model(); m.options.environment[name] = 'MODEL_FORBIDDEN';
        assert.throws(() => m.api.launchSupervisor(m.options), /PROVIDER_BRIDGE_ENVIRONMENT/);
        assert.equal(m.calls.length, 0);
    }
});
test('already cancelled and expired requests start no child', () => {
    for (const cancel of [true, false]) {
        const m = model();
        if (cancel) m.controller.abort(); else m.setNow(m.options.localEndNs);
        assert.throws(() => m.api.launchSupervisor(m.options)); assert.equal(m.calls.length, 0);
    }
});
test('one module invocation cannot silently retry a provider', async () => {
    const m = model(), pending = m.api.launchSupervisor(m.options); m.complete(); await pending;
    assert.throws(() => m.api.launchSupervisor(m.options), /ONE_INVOCATION/); assert.equal(m.calls.length, 1);
});

// An unresolved modeled Promise has no native event-loop handle. Default to
// failure so Node cannot exit0 before the final aggregate is actually reached.
process.exitCode = 1;
module.exports = (async () => {
    let passed = 0;
    for (const {name, run} of cases) {
        try { await run(); passed++; }
        catch { process.stderr.write('FAIL ' + name + '\n'); process.exitCode = 1; }
    }
    process.stdout.write(`${passed}/${cases.length} offline bridge model controls passed; no native/provider execution\n`);
    if (passed === cases.length) process.exitCode = 0;
    return {passed, total: cases.length};
})();
