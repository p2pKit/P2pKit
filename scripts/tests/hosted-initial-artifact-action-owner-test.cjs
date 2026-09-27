'use strict';

// New finite-owner models only. Actual Node Readable/Writable, fake child and
// clocks; never Python/HTTP/native/key execution or replay of accepted suites.
// The private function is exposed ONLY inside this test's isolated wrapper;
// the checked-in Action exports only fixed named entries and accepts no
// injectable backend.
const assert = require('node:assert/strict');
const {EventEmitter} = require('node:events');
const {Readable, Writable} = require('node:stream');
const fs = require('node:fs'), path = require('node:path'), vm = require('node:vm');
const D = require('../hosted-initial-artifact-action-data.cjs');
const ProductiveData = require('../hosted-initial-artifact-productive-action-data.cjs');
const {NS} = require('./hosted-initial-artifact-action-fixtures.cjs');
const source = fs.readFileSync(path.join(__dirname, '../hosted-initial-artifact-action.cjs'), 'utf8');
const cases = [], test = (name, body) => cases.push({name, body});
const tick = () => new Promise(resolve => setImmediate(resolve));
function packet(tag, raw) {
    const header = Buffer.alloc(5); header[0] = tag.charCodeAt(0); header.writeUInt32BE(raw.length, 1);
    return Buffer.concat([header, raw]);
}
function model(config = {}) {
    const module = {exports: {}}, calls = [], writes = [], timers = new Map(), errors = [], checkpoints = [];
    const signalOwner = new AbortController(), heldWrites = [], heldFinal = [];
    const raw = D.encode({scope: 'OFFLINE_FINITE_OWNER_BYTES_NOT_AUTHORITY'});
    let now = 100n * NS, timerId = 0, endCalls = 0, child = null, handle = null;
    class Child extends EventEmitter {
        constructor() {
            super();
            this.stdin = new Writable({write(chunk, _encoding, done) {
                writes.push(Buffer.from(chunk));
                if (config.writeThrows) throw new Error('PRIVATE_FINITE_WRITE_FAILURE');
                if (config.holdWrite) heldWrites.push(done); else queueMicrotask(done);
            }, final(done) {
                endCalls++;
                if (config.holdFinal) heldFinal.push(done); else queueMicrotask(done);
            }});
            this.stdout = new Readable({read() {}}); this.stderr = new Readable({read() {}});
            if (config.aliasPipe) this.stderr = this.stdout;
        }
        kill() { assert.fail('no signal/PID termination substitute for original cooperative EOF'); }
    }
    const imports = {'node:child_process': {ChildProcess: Child, spawn(python, args, options) {
        child = new Child(); calls.push({python, args, options});
        if (config.listenerThrows) {
            const original = child.on;
            child.on = function (name, listener) {
                if (name === 'spawn') throw new Error('PRIVATE_FINITE_LISTENER_FAILURE');
                return original.call(this, name, listener);
            };
        }
        if (!config.noSpawn) queueMicrotask(() => child.emit('spawn'));
        return child;
    }}, 'node:stream': {Readable, Writable}, 'node:fs': {appendFileSync() { assert.fail('owner-only model cannot output'); }},
    'node:path': path, 'node:timers': {setTimeout(callback, ms) {
        const id = ++timerId; timers.set(id, {callback, ms}); return id;
    }, clearTimeout(id) { timers.delete(id); }}, './hosted-initial-artifact-action-data.cjs': D,
    './hosted-initial-artifact-productive-action-data.cjs': ProductiveData,
    './hosted-initial-artifact-reader.cjs': {}, './hosted-initial-artifact-observer.cjs': {},
    './hosted-initial-artifact-transport.cjs': {}};
    // Same realm preserves exact descriptor/prototype DATA checks. Every
    // authority-bearing import is replaced by this closed OFFLINE model.
    const factory = vm.runInThisContext('(function(require,module,__dirname,process){\n' + source +
        '\nmodule.exports = Object.freeze({openFinite: options => openFinite(options, LEGACY_ROUTE)});\n})',
        {filename: 'offline-new-finite-owner.cjs', timeout: 1000});
    factory(name => { assert(Object.hasOwn(imports, name)); return imports[name]; }, module, '/model/p2pkit/scripts',
        {platform: config.windows ? 'win32' : 'linux', hrtime: {bigint: () => now}});
    const options = {mode: config.after ? 'after' : 'finish', python: config.windows ? 'C:\\model\\python.exe' : '/usr/bin/python3',
        kind: 'gate', environment: Object.freeze({MODEL_ONLY: 'NOT_AUTHORITY'}), signal: signalOwner.signal,
        originalEndNs: config.after ? null : 160n * NS,
        checkpoint(end) { checkpoints.push(end); assert(now < end); if (config.guardThrows) throw new Error('PRIVATE_GUARD_FAILURE'); },
        poison(error) { errors.push(error); if (!signalOwner.signal.aborted) signalOwner.abort(); }};
    async function start() { handle = module.exports.openFinite(options); await tick(); return handle; }
    async function ready() {
        await start(); child.stdout.push(packet('R', raw)); await handle.ready;
        handle.bindAfter(114n * NS); return handle;
    }
    async function input(inputRaw = raw) { if (config.after) await ready(); else await start(); handle.input(inputRaw); await tick(); }
    async function final(chunk = raw) { child.stdout.push(packet('F', chunk)); await tick(); }
    async function close(flags = {}) {
        if (flags.stdout !== false) child.stdout.push(null);
        if (flags.stderr !== false) child.stderr.push(null);
        if (flags.exit !== false) child.emit('exit', flags.code === undefined ? 0 : flags.code, flags.signal || null);
        await tick();
        if (flags.childClose !== false) child.emit('close', flags.code === undefined ? 0 : flags.code, flags.signal || null);
        await tick();
    }
    async function expire() {
        now = config.after ? 115n * NS : 160n * NS;
        for (const {callback} of [...timers.values()]) callback();
        await tick(); return handle.completion;
    }
    return {raw, options, calls, writes, timers, errors, checkpoints, signalOwner, heldWrites, heldFinal,
        start, ready, input, final, close, expire, setNow(value) { now = value; },
        get handle() { return handle; }, get child() { return child; }, get endCalls() { return endCalls; }};
}
async function failed(m) {
    const result = await m.expire(); assert.equal(result.transport, 'incomplete');
    assert.equal(typeof result.code, 'string'); assert(m.errors.length > 0);
    assert.match(result.code, /^INITIAL_ARTIFACT_ACTION_FINITE_[A-Z_]+$/);
    const serialized = JSON.stringify(result, (_, value) => typeof value === 'bigint' ? String(value) : value);
    // A static FINITE_PRIVATE_DIAGNOSTIC code is not the raw diagnostic.
    // Reject every exact private model original, not a shared English prefix.
    for (const original of ['PRIVATE_FINITE_DIAGNOSTIC', 'PRIVATE_FINITE_WRITE_FAILURE',
        'PRIVATE_FINITE_LISTENER_FAILURE', 'PRIVATE_GUARD_FAILURE']) assert(!serialized.includes(original));
    assert.throws(() => m.handle.finalFrame()); return result;
}

test('fixed finish helper uses exactly private pipes/cwd/isolated argv and one complete I', async () => {
    const m = model(); await m.input();
    assert.equal(m.calls.length, 1); assert.equal(m.calls[0].python, '/usr/bin/python3');
    assert.equal(m.calls[0].args.join('|'), '-I|-B|-S|/model/p2pkit/scripts/run-hosted-initial-recipient-upload.py|finish|--kind|gate');
    assert.equal(m.calls[0].options.cwd, '/model/p2pkit'); assert.equal(m.calls[0].options.shell, false);
    assert.equal(m.calls[0].options.detached, false); assert.equal(m.calls[0].options.stdio.join('|'), 'pipe|pipe|pipe');
    assert.equal(m.writes.length, 1); assert.deepEqual(m.writes[0], packet('I', m.raw)); assert.equal(m.endCalls, 1);
    await m.final(); await m.close(); assert.equal((await m.handle.completion).transport, 'closed');
});
test('F is not a helper return before actual exit0 and all three pipe/process closes', async () => {
    const m = model(); await m.input(); await m.final(); await m.close({childClose: false});
    assert.throws(() => m.handle.finalFrame()); m.child.emit('close', 0, null); await tick();
    const result = await m.handle.completion; assert.equal(result.transport, 'closed');
    assert(Object.values(result.originalPipeCloses).every(Boolean)); assert.deepEqual(m.handle.finalFrame(), m.raw);
});
test('original exit may precede already-written final stdout bytes without fabricating close', async () => {
    const m = model(); await m.input(); m.child.emit('exit', 0, null); await m.final(); await m.close({exit: false});
    assert.equal((await m.handle.completion).transport, 'closed');
});
test('withheld original write/final callbacks cannot be replaced by observed F/EOF', async () => {
    const m = model({holdWrite: true}); await m.input(); await m.final();
    m.child.stdout.push(null); m.child.stderr.push(null); m.child.emit('exit', 0, null); await tick();
    assert.throws(() => m.handle.finalFrame()); assert.equal(m.endCalls, 0);
    m.heldWrites.shift()(); await tick(); m.child.emit('close', 0, null); await tick();
    const result = await m.handle.completion;
    assert.equal(result.transport, 'closed'); assert.equal(result.inputWriteCallbackObserved, true);
    assert.equal(result.stdinEndCallbackObserved, true); assert.equal(result.stdinFinishObserved, true);
});
test('withheld stdin finish/end callback remains incomplete at original deadline', async () => {
    const m = model({holdFinal: true}); await m.input(); await m.final(); await m.close();
    const result = await failed(m); assert.equal(result.stdinFinishObserved, false);
    m.heldFinal.shift()(); await tick(); assert.throws(() => m.handle.finalFrame());
});
test('after owns R then exactly one I/EOF then F within the SAME original15s', async () => {
    const m = model({after: true}); await m.input();
    assert.equal(m.calls[0].args[4], 'after'); assert.equal(m.writes.length, 1);
    m.setNow(113n * NS); await m.final(); await m.close();
    assert.equal((await m.handle.completion).transport, 'closed');
});
test('after cannot extend its original cap or bind twice', async () => {
    const m = model({after: true}); await m.start(); m.child.stdout.push(packet('R', m.raw)); await m.handle.ready;
    assert.throws(() => m.handle.bindAfter(116n * NS)); await failed(m);
    const twice = model({after: true}); await twice.ready();
    assert.throws(() => twice.handle.bindAfter(113n * NS)); await failed(twice);
});
test('finish cannot accept R and after cannot accept F without R/input', async () => {
    const finish = model(); await finish.start(); finish.child.stdout.push(packet('R', finish.raw)); await failed(finish);
    const after = model({after: true}); await after.start(); after.child.stdout.push(packet('F', after.raw)); await failed(after);
});
test('complete I frame has an inclusive2MiB bound before FIRST write', async () => {
    const m = model(); await m.start();
    assert.throws(() => m.handle.input(Buffer.alloc(2097152 - 4, 0x20)));
    assert.equal(m.writes.length, 0); await failed(m);
});
test('maximum permitted complete I is written once without truncation', async () => {
    const m = model(); await m.input(Buffer.alloc(2097152 - 5, 0x20));
    assert.equal(m.writes[0].length, 2097152); await m.final(); await m.close();
    assert.equal((await m.handle.completion).transport, 'closed');
});
test('duplicate I remains sticky even if a valid original F follows', async () => {
    const m = model(); await m.input(); assert.throws(() => m.handle.input(m.raw));
    await m.final(); await m.close(); await failed(m); assert.equal(m.writes.length, 1);
});
test('fragmented header and payload produce one complete F, not a prefix return', async () => {
    const m = model(); await m.input(); const wire = packet('F', m.raw);
    for (const part of [wire.subarray(0, 1), wire.subarray(1, 4), wire.subarray(4, 6), wire.subarray(6)]) {
        m.child.stdout.push(part); await tick(); assert.throws(() => m.handle.finalFrame());
    }
    await m.close(); assert.deepEqual(m.handle.finalFrame(), m.raw);
});
test('oversized F declaration refuses immediately without waiting for payload', async () => {
    const m = model(); await m.input(); const header = Buffer.alloc(5); header[0] = 70; header.writeUInt32BE(16385, 1);
    m.child.stdout.push(header); await failed(m);
});
test('trailing/duplicate F and N/D finite frames cannot become success', async () => {
    for (const tag of ['F', 'D', 'N']) {
        const m = model(); await m.input();
        m.child.stdout.push(Buffer.concat([packet('F', m.raw), packet(tag, m.raw)])); await failed(m);
    }
});
test('premature stdout EOF or missing stderr EOF stays incomplete', async () => {
    const early = model(); await early.input(); await early.close(); await failed(early);
    const missing = model(); await missing.input(); await missing.final(); await missing.close({stderr: false}); await failed(missing);
});
test('nonzero exit, exit signal and negative zero cannot be called exit0', async () => {
    for (const flags of [{code: 1}, {signal: 'SIGTERM'}, {code: -0}]) {
        const m = model(); await m.input(); await m.final(); await m.close(flags); await failed(m);
    }
});
test('private stderr is never printed or admitted on success', async () => {
    const m = model(); await m.input(); m.child.stderr.push(Buffer.from('PRIVATE_FINITE_DIAGNOSTIC'));
    await m.final(); await m.close(); const result = await failed(m);
    assert.equal(result.code, 'INITIAL_ARTIFACT_ACTION_FINITE_PRIVATE_DIAGNOSTIC');
    assert.equal(result.stderrBytes, Buffer.byteLength('PRIVATE_FINITE_DIAGNOSTIC'));
});
test('partial constructor/listener and alias-pipe failures retain originals and cannot relaunch', async () => {
    const m = model({listenerThrows: true}); await m.start(); await failed(m); assert.equal(m.calls.length, 1);
    const alias = model({aliasPipe: true}); await alias.start(); await failed(alias); assert.equal(alias.calls.length, 1);
});
test('absolute finish end is not refreshed at child launch or F return', async () => {
    const m = model(); m.setNow(159n * NS); await m.input();
    assert([...m.timers.values()].every(row => row.ms <= 1000));
    m.setNow(160n * NS); await m.final(); await m.close(); await failed(m);
});
test('local regression fails sticky despite restoring the previous timestamp', async () => {
    const m = model(); await m.input(); m.setNow(99n * NS); await m.final(); m.setNow(100n * NS);
    await m.close(); await failed(m);
});
test('external cancellation uses EOF on Windows without any kill/known-close substitution', async () => {
    const m = model({windows: true}); await m.input(); m.signalOwner.abort(); await failed(m);
    assert.equal(m.calls.length, 1); assert.equal(m.endCalls, 1);
});
test('returned F copy cannot mutate the original retained final frame', async () => {
    const m = model(); await m.input(); await m.final(); await m.close();
    const copy = m.handle.finalFrame(); copy.fill(0); assert.deepEqual(m.handle.finalFrame(), m.raw);
});

(async () => {
    const args = process.argv.slice(2);
    assert(args.length === 0 || args.length === 1 && args[0] === '--r1-remaining');
    assert.equal(cases.length, 22);
    // Explicit historical suffix only; no arbitrary skip/filter input.
    const remaining = args.length === 1, selected = remaining ? cases.slice(16) : cases;
    assert.equal(selected.length, remaining ? 6 : 22);
    let passed = 0;
    for (const {name, body} of selected) {
        try { await body(); passed++; }
        catch (error) { process.stderr.write('FAIL new finite-owner model: ' + name + '\n'); process.exitCode = 1; return; }
    }
    process.stdout.write('PASS ' + passed + '/' + selected.length + ' new finite-owner models only' +
        (remaining ? ' (R1 remaining 17-22)' : '') + '\n');
})().catch(() => { process.stderr.write('FAIL new finite-owner model harness\n'); process.exitCode = 1; });
