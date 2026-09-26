'use strict';
// New OFFLINE child/pipe/demand models only. Real Node Readable/Writable, fake
// ChildProcess and clocks. No Python, native file, network, CI or old suite.
const assert = require('node:assert/strict');
const {EventEmitter} = require('node:events');
const {Readable, Writable} = require('node:stream');
const crypto = require('node:crypto');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const source = fs.readFileSync(path.join(__dirname, '../hosted-initial-artifact-reader.cjs'), 'utf8');
const NS = 1000000000n, cases = [];
const test = (name, run) => cases.push({name, run});
const tick = () => new Promise(resolve => setImmediate(resolve));
const sha = raw => crypto.createHash('sha256').update(raw).digest('hex');
const canonical = value => Buffer.from(JSON.stringify(Object.fromEntries(
    Object.keys(value).sort().map(name => [name, value[name]]))) + '\n', 'ascii');
function packet(kind, body) {
    const header = Buffer.alloc(5); header[0] = kind.charCodeAt(0); header.writeUInt32BE(body.length, 1);
    return Buffer.concat([header, body]);
}

function model(config = {}) {
    const timers = new Map(), calls = [], writes = [], raw = Buffer.from('offline-encrypted-byte-model');
    const readyRaw = canonical({scope: 'OFFLINE_READY_NOT_AUTHORITY'});
    const module = {exports: {}}, control = new AbortController();
    let now = 100n * NS, timerId = 0, endedInput = 0, child, handle;
    const callbacks = [];
    class Child extends EventEmitter {
        constructor() {
            super();
            this.stdin = new Writable({write(chunk, _encoding, done) {
                writes.push(Buffer.from(chunk));
                if (config.holdWriteCallback) callbacks.push(done); else queueMicrotask(done);
            }, final(done) { endedInput++; queueMicrotask(done); }});
            this.stdout = new Readable({read() {}});
            this.stderr = new Readable({read() {}});
        }
        kill() { assert.fail('no signal/PID/Windows termination fallback in this bridge'); }
    }
    const imports = {'node:child_process': {ChildProcess: Child, spawn: (python, args, options) => {
        child = new Child(); calls.push({python, args, options});
        queueMicrotask(() => child.emit('spawn'));
        return child;
    }}, 'node:stream': {Readable, Writable}, 'node:path': path, 'node:crypto': crypto,
    'node:timers': {setTimeout: (callback, ms) => {
        const id = ++timerId; timers.set(id, {callback, ms}); return id;
    }, clearTimeout: id => timers.delete(id)}};
    vm.runInNewContext(source, {module, require: name => {
        assert(Object.hasOwn(imports, name), 'closed offline import ' + name); return imports[name];
    }, __dirname: '/model/p2pkit/scripts', process: {platform: 'linux', versions: {node: '24.20.0'},
        hrtime: {bigint: () => now}}, Object, Reflect, JSON, Buffer, SharedArrayBuffer,
    AbortSignal, EventTarget, Error, Set}, {timeout: 1000});
    const names = ['GITHUB_ACTIONS', 'GITHUB_REPOSITORY', 'GITHUB_SHA', 'GITHUB_REF', 'GITHUB_RUN_ID',
        'GITHUB_RUN_ATTEMPT', 'GITHUB_EVENT_NAME', 'GITHUB_WORKFLOW_REF', 'GITHUB_WORKFLOW_SHA',
        'GITHUB_WORKSPACE', 'GITHUB_EVENT_PATH', 'GITHUB_SERVER_URL', 'GITHUB_API_URL', 'GITHUB_JOB',
        'RUNNER_OS', 'RUNNER_ARCH', 'RUNNER_NAME', 'RUNNER_ENVIRONMENT', 'RUNNER_TEMP', 'ImageOS', 'ImageVersion',
        'P2PKIT_INITIAL_SEAL_SHA256', 'P2PKIT_INITIAL_SEAL_END_NS', 'P2PKIT_INITIAL_SEAL_CLOCK_ROLE',
        'P2PKIT_INITIAL_SEAL_CLOCK_DOMAIN', 'P2PKIT_INITIAL_SEAL_CLOCK_TICKS_PER_SECOND',
        'P2PKIT_INITIAL_SEAL_BOOT_SHA256', 'P2PKIT_INITIAL_SEAL_OUTCOME',
        'P2PKIT_INITIAL_BEFORE_SHA256', 'P2PKIT_INITIAL_BEFORE_OUTCOME'];
    // The low-level transport checks a closed credential-free map, NOT hosted
    // admission. These deliberately unqualified model strings reach no native
    // process and cannot be used as production runner/source authority.
    const environment = Object.fromEntries(names.map(name => [name, 'MODEL_NOT_AUTHORITY']));
    Object.assign(environment, {GITHUB_WORKSPACE: '/model/p2pkit', PATH: '/usr/bin:/bin', LANG: 'C', LC_ALL: 'C',
        PYTHONDONTWRITEBYTECODE: '1', PYTHONUNBUFFERED: '1'});
    const options = {python: '/usr/bin/python3', kind: 'gate', environment, signal: control.signal};
    const bounds = {readySha256: sha(readyRaw), beforeSha256: 'b'.repeat(64), firstRawNs: 900n * NS,
        sealEndNs: 901n * NS, uploadEndNs: 960n * NS, zipBytes: raw.length};
    function terminal(changes = {}) {
        return canonical({schema: 1, scope: 'INITIAL_ARTIFACT_NATIVE_STREAM_CLOSED_FILES_PENDING_PROCESS_V1',
            beforeSha256: bounds.beforeSha256, readySha256: sha(readyRaw), zipBytes: raw.length, zipSha256: sha(raw),
            nativeCloseSha256: 'c'.repeat(64), closedNs: (bounds.firstRawNs + NS).toString(),
            nativeFileRetirement: 'KNOWN_NATIVE_CLOSE', originalReaderOutcome: 'PENDING_ENCLOSING_PROCESS_CLOSE',
            qualification: 'NOT_ESTABLISHED', ...changes});
    }
    async function start() {
        handle = module.exports.openReader(options);
        // Tests deliberately inspect failures; always consume the ready
        // rejection rather than introducing an unrelated unhandled rejection.
        handle.ready.catch(() => {});
        await tick(); return handle;
    }
    async function ready() {
        await start(); child.stdout.push(packet('R', readyRaw)); await handle.ready; return handle;
    }
    async function bind() { await ready(); return handle.bind(bounds); }
    async function demand(body, kind = 'D') {
        assert.equal(handle.stream.read(), null);
        await tick();
        child.stdout.push(packet(kind, body));
        await tick();
        return kind === 'D' ? handle.stream.read() : null;
    }
    async function close({exit = true, stdout = true, stderr = true, processClose = true} = {}) {
        if (stdout) child.stdout.push(null);
        if (stderr) child.stderr.push(null);
        if (exit) child.emit('exit', 0, null);
        await tick();
        if (processClose) child.emit('close', 0, null);
        await tick();
    }
    async function expire() {
        now = 160n * NS;
        const current = [...timers.values()];
        assert.equal(current.length, 1); current[0].callback();
        await tick(); return handle.completion;
    }
    return {raw, readyRaw, module, options, bounds, timers, calls, writes, control, callbacks,
        start, ready, bind, demand, close, expire, terminal, setNow: value => { now = value; },
        get child() { return child; }, get handle() { return handle; }, get endedInput() { return endedInput; }};
}
function safe(result) {
    assert.equal(result.qualification, 'NOT_ESTABLISHED');
    assert.equal(result.originalStepOutcome, 'NOT_OBSERVED');
    for (const forbidden of ['MODEL_NOT_AUTHORITY', 'PRIVATE_DIAGNOSTIC', 'MODEL_SECRET', '/model/', '/usr/bin/']) {
        assert(!JSON.stringify(result).includes(forbidden), 'no private model values in safe result');
    }
}
async function failed(m) {
    const result = await m.expire();
    assert.equal(result.transport, 'incomplete');
    assert(result.code.startsWith('INITIAL_ARTIFACT_READER_')); safe(result);
    assert.equal(m.endedInput, 1);
    return result;
}
async function dataThenFinal(m, changes = {}) {
    assert.deepEqual(await m.demand(m.raw), m.raw);
    await m.demand(m.terminal(changes), 'F');
}

test('fixed isolated helper, cwd, no shell, no inherited credential, no control before READY', async () => {
    const m = model(); await m.ready();
    assert.equal(m.calls.length, 1);
    const call = m.calls[0];
    assert.equal(call.python, '/usr/bin/python3');
    assert.equal(call.args.join('|'), '-I|-B|-S|/model/p2pkit/scripts/run-hosted-initial-recipient-upload.py|stream|--kind|gate');
    assert.equal(call.options.cwd, '/model/p2pkit'); assert.equal(call.options.shell, false);
    assert.equal(call.options.detached, false); assert.equal(call.options.stdio.join('|'), 'pipe|pipe|pipe');
    assert(!Object.hasOwn(call.options.env, 'ACTIONS_RUNTIME_TOKEN')); assert.equal(m.writes.length, 0);
    assert.equal(m.handle.stream.readableHighWaterMark, 0); assert.equal(m.handle.stream.readableLength, 0);
    assert.equal(m.handle.stream.listenerCount('data'), 0); assert.equal(m.handle.stream.listenerCount('readable'), 0);
    m.handle.cancel(); await failed(m);
});
test('directed RAW to pre-spawn LOCAL mapping never equates distinct epochs', async () => {
    const m = model(); const ends = await m.bind();
    assert.equal(ends.startByNs, 101n * NS); assert.equal(ends.workEndNs, 155n * NS);
    assert.equal(ends.closeEndNs, 160n * NS); assert.equal(m.writes.length, 0);
    m.handle.cancel(); await failed(m);
});
test('one N one chunk, no demand while the downstream consumer is paused', async () => {
    const m = model(); await m.bind();
    assert.deepEqual(await m.demand(m.raw), m.raw);
    assert.equal(m.writes.length, 1); assert.equal(m.writes[0].toString('ascii'), 'N');
    await tick(); await tick();
    assert.equal(m.writes.length, 1); assert.equal(m.handle.stream.readableLength, 0);
    m.handle.cancel(); await failed(m);
});
test('genuine original exit and every pipe/process close precede exposed stream EOF', async () => {
    const m = model(); await m.bind(); await dataThenFinal(m);
    let ended = false; m.handle.stream.on('end', () => { ended = true; });
    await m.close({processClose: false});
    assert.equal(ended, false); assert.equal(m.handle.stream.readableEnded, false);
    m.child.emit('close', 0, null); await tick();
    const result = await m.handle.completion;
    assert.equal(result.transport, 'closed'); assert.equal(result.originalChildCloseObserved, true);
    assert(Object.values(result.originalPipeCloses).every(Boolean));
    m.handle.stream.read(); await tick(); assert.equal(ended, true);
    assert.equal(result.zipBytes, m.raw.length); assert.equal(result.zipSha256, sha(m.raw)); safe(result);
    assert.deepEqual(m.handle.finalFrame(), m.terminal());
});
test('Node exit may precede delivery of already-written final stdout bytes', async () => {
    const m = model(); await m.bind(); await m.demand(m.raw);
    assert.equal(m.handle.stream.read(), null); await tick();
    m.child.emit('exit', 0, null);
    m.child.stdout.push(packet('F', m.terminal())); await tick();
    await m.close({exit: false});
    assert.equal((await m.handle.completion).transport, 'closed');
});
test('READY and bound values are captured, caller mutation cannot change the stream contract', async () => {
    const m = model(); await m.ready(); const copy = await m.handle.ready;
    copy.raw.fill(0); m.handle.bind(m.bounds); m.bounds.zipBytes++;
    await dataThenFinal(m); await m.close();
    assert.equal((await m.handle.completion).transport, 'closed');
});
test('fragmented five-byte header and payload are one frame, not extra demand', async () => {
    const m = model(); await m.bind(); m.handle.stream.read(); await tick();
    const whole = packet('D', m.raw);
    for (const piece of [whole.subarray(0, 1), whole.subarray(1, 4), whole.subarray(4, 8), whole.subarray(8)]) {
        m.child.stdout.push(piece); await tick();
    }
    assert.deepEqual(m.handle.stream.read(), m.raw); assert.equal(m.writes.length, 1);
    m.handle.cancel(); await failed(m);
});
test('frame cannot release bytes before the original N write callback', async () => {
    const m = model({holdWriteCallback: true}); await m.bind(); m.handle.stream.read(); await tick();
    m.child.stdout.push(packet('D', m.raw)); await tick();
    assert.equal(m.handle.stream.readableLength, 0);
    m.callbacks.shift()(); await tick(); assert.deepEqual(m.handle.stream.read(), m.raw);
    m.handle.cancel(); await failed(m);
});
test('complete F and stdout EOF join the delayed original N callback before any successful close', async () => {
    const m = model({holdWriteCallback: true}); await m.bind(); m.handle.stream.read(); await tick();
    m.child.stdout.push(packet('D', m.raw)); m.callbacks.shift()(); await tick();
    assert.deepEqual(m.handle.stream.read(), m.raw);
    m.handle.stream.read(); await tick();
    m.child.stdout.push(packet('F', m.terminal())); m.child.stdout.push(null); m.child.stderr.push(null);
    await tick();
    assert.equal(m.handle.stream.destroyed, false); assert.equal(m.handle.stream.readableEnded, false);
    assert.throws(() => m.handle.finalFrame()); assert.equal(m.endedInput, 0);
    m.callbacks.shift()(); await tick();
    assert.equal(m.endedInput, 1); assert.equal(m.handle.stream.readableEnded, false);
    await m.close({stdout: false, stderr: false});
    const result = await m.handle.completion;
    assert.equal(result.transport, 'closed'); assert.equal(result.stdinEndCallbackObserved, true);
    assert.equal(result.zipSha256, sha(m.raw)); assert.deepEqual(m.handle.finalFrame(), m.terminal());
    safe(result);
});
test('EOF while a D or truncated F waits for N callback is still a failure', async () => {
    for (const body of [packet('D', Buffer.from('x')), packet('F', Buffer.from('{}')).subarray(0, 6)]) {
        const m = model({holdWriteCallback: true}); await m.bind(); m.handle.stream.read(); await tick();
        m.child.stdout.push(body); m.child.stdout.push(null); await tick();
        assert.equal(m.handle.stream.destroyed, true);
        m.callbacks.shift()(); await tick(); await failed(m);
    }
});
test('complete F and EOF cannot mask failure of the delayed original N callback', async () => {
    const m = model({holdWriteCallback: true}); await m.bind(); m.handle.stream.read(); await tick();
    m.child.stdout.push(packet('F', m.terminal())); m.child.stdout.push(null); await tick();
    assert.equal(m.handle.stream.destroyed, false);
    m.callbacks.shift()(new Error('MODEL_PRIVATE_WRITE_ERROR')); await tick();
    const result = await m.expire();
    assert.equal(result.transport, 'incomplete'); assert.equal(result.originalStepOutcome, 'NOT_OBSERVED');
    assert(!JSON.stringify(result).includes('MODEL_PRIVATE_WRITE_ERROR')); assert.throws(() => m.handle.finalFrame());
});
test('changed READY binding refuses before any N', async () => {
    const m = model(); await m.ready();
    assert.throws(() => m.handle.bind({...m.bounds, readySha256: '0'.repeat(64)}));
    assert.equal(m.writes.length, 0); await failed(m);
});
test('early source end, overdue seal and enlarged source interval cannot invent time', async () => {
    for (const change of [{sealEndNs: 900n * NS}, {sealEndNs: 955n * NS},
        {sealEndNs: 961n * NS}, {uploadEndNs: 900n * NS}, {firstRawNs: -1n}, {firstRawNs: 900000000000}]) {
        const m = model(); await m.ready();
        assert.throws(() => m.handle.bind({...m.bounds, ...change}));
        assert.equal(m.writes.length, 0); await failed(m);
    }
});
test('second bind is sticky failure and cannot reset the budget', async () => {
    const m = model(); await m.bind(); assert.throws(() => m.handle.bind(m.bounds)); await failed(m);
});
test('read before bind fails closed without a control write', async () => {
    const m = model(); await m.ready(); m.handle.stream.read(); await tick();
    assert.equal(m.writes.length, 0); await failed(m);
});
test('unsolicited payload without N is a refusal', async () => {
    const m = model(); await m.bind(); m.child.stdout.push(packet('D', m.raw)); await tick(); await failed(m);
});
test('two concatenated frames cannot become payload prefetch', async () => {
    const m = model(); await m.bind(); m.handle.stream.read(); await tick();
    m.child.stdout.push(Buffer.concat([packet('D', m.raw), packet('D', m.raw)])); await tick(); await failed(m);
});
test('empty, oversized and unknown frame headers refuse without a payload allocation', async () => {
    for (const [kind, count] of [['D', 0], ['D', 65537], ['R', 16385], ['F', 16385], ['X', 1]]) {
        const m = model(); await m.bind(); m.handle.stream.read(); await tick();
        const header = Buffer.alloc(5); header[0] = kind.charCodeAt(0); header.writeUInt32BE(count, 1);
        m.child.stdout.push(header); await tick(); await failed(m);
    }
});
test('actual observed payload overrun prevents a successful native terminal record', async () => {
    const m = model(); await m.bind(); m.handle.stream.read(); await tick();
    m.child.stdout.push(packet('D', Buffer.concat([m.raw, Buffer.from('x')]))); await tick(); await failed(m);
});
test('short byte stream cannot pass on a matching declaration alone', async () => {
    const m = model(); await m.bind(); await m.demand(m.raw.subarray(1)); await m.demand(m.terminal(), 'F');
    await failed(m);
});
test('terminal source/ready/native/hash/size/close-time and nonacceptance fields are all bound', async () => {
    for (const changes of [{beforeSha256: '0'.repeat(64)}, {readySha256: '0'.repeat(64)},
        {nativeCloseSha256: 'bad'}, {zipSha256: '0'.repeat(64)}, {zipBytes: true},
        {closedNs: (955n * NS).toString()}, {closedNs: '0900000000000'}, {qualification: 'ACCEPTED'},
        {nativeFileRetirement: 'UNKNOWN'}, {originalReaderOutcome: 'SUCCESS'}]) {
        const m = model(); await m.bind(); await dataThenFinal(m, changes); await failed(m);
    }
});
test('noncanonical or duplicate terminal keys are rejected, not silently overwritten', async () => {
    for (const changed of [raw => Buffer.from(raw.toString('ascii').replace('"schema":1', '"schema":1,"schema":1')),
        raw => Buffer.from(' ' + raw.toString('ascii')), raw => Buffer.from(raw.toString('ascii').trimEnd())]) {
        const m = model(); await m.bind(); await m.demand(m.raw);
        await m.demand(changed(m.terminal()), 'F'); await failed(m);
    }
});
test('EOF alone cannot stand in for a successful terminal record', async () => {
    const m = model(); await m.bind(); m.child.stdout.push(null); await tick(); await failed(m);
});
test('missing stderr EOF/close cannot expose Readable EOF even with child close', async () => {
    const m = model(); await m.bind(); await dataThenFinal(m); await m.close({stderr: false});
    assert.equal(m.handle.stream.readableEnded, false);
    const result = await failed(m); assert.equal(result.originalPipeCloses.stderr, false);
});
test('missing process close retains incomplete status after pipe EOF/close and zero exit', async () => {
    const m = model(); await m.bind(); await dataThenFinal(m); await m.close({processClose: false});
    const result = await failed(m); assert.equal(result.originalExitZeroObserved, true);
    assert.equal(result.originalChildCloseObserved, false); assert.throws(() => m.handle.finalFrame());
});
test('nonzero native exit cannot be repaired by a later zero close event', async () => {
    const m = model(); await m.bind(); m.child.emit('exit', 125, null); await tick();
    m.child.emit('close', 0, null); await failed(m);
});
test('private helper stderr never enters the public result and permanently fails', async () => {
    const m = model(); await m.bind(); m.child.stderr.push(Buffer.from('PRIVATE_DIAGNOSTIC')); await tick();
    const result = await failed(m); assert.equal(result.stderrBytes, 18);
});
test('abort requests original stdin EOF once; no PID signal or retry', async () => {
    const m = model(); await m.bind(); m.control.abort(); m.handle.cancel(); await tick();
    await failed(m); assert.equal(m.endedInput, 1);
});
test('original local deadline is not restarted after a delayed READY', async () => {
    const m = model(); await m.ready(); m.setNow(101n * NS);
    assert.throws(() => m.handle.bind(m.bounds)); await failed(m);
});
test('service tokens, loader overrides and arbitrary env keys are refused before spawn', async () => {
    for (const key of ['ACTIONS_RUNTIME_TOKEN', 'GITHUB_TOKEN', 'GH_TOKEN', 'LD_PRELOAD', 'PYTHONPATH', 'JAVA_OPTS']) {
        const m = model(); m.options.environment[key] = 'MODEL_SECRET';
        assert.throws(() => m.module.exports.openReader(m.options));
        assert.equal(m.calls.length, 0);
    }
});
test('no caller-selected helper/backend or shell expression may be added', async () => {
    for (const change of [{helper: '/tmp/anything.py'}, {python: '/bin/sh'}, {kind: 'ordinary'}]) {
        const m = model(); assert.throws(() => m.module.exports.openReader({...m.options, ...change}));
        assert.equal(m.calls.length, 0);
    }
});
test('caught second invocation poisons the original without independent cancel or renewed allowance', async () => {
    const m = model(); await m.ready();
    assert.throws(() => m.module.exports.openReader(m.options)); assert.equal(m.calls.length, 1);
    assert.throws(() => m.handle.bind(m.bounds));
    assert.equal(m.writes.length, 0); await failed(m);
});
test('caught reentry during first input inspection also refuses before any child exists', async () => {
    const m = model(); let caught = false;
    const options = new Proxy(m.options, {getPrototypeOf(target) {
        try { m.module.exports.openReader(m.options); } catch (_) { caught = true; }
        return Object.getPrototypeOf(target);
    }});
    assert.throws(() => m.module.exports.openReader(options));
    assert.equal(caught, true); assert.equal(m.calls.length, 0);
});

let currentName = 'before first model';
(async () => {
    for (const item of cases) {
        currentName = item.name;
        await item.run();
        process.stdout.write('PASS ' + item.name + '\n');
    }
    process.stdout.write('OFFLINE_READER_PIPE_MODELS ' + cases.length + '/' + cases.length +
        '; no native/hosted/provider/service qualification\n');
})().catch(error => {
    // All inputs and child/clock objects are explicit offline fixtures. This
    // bounded test failure is not a channel for production/native diagnostics.
    process.stderr.write('FAIL OFFLINE_READER_PIPE_MODEL ' + currentName + '; stop on first failure\n' +
        String(error.stack || error).slice(0, 4000) + '\n');
    process.exitCode = 1;
});
