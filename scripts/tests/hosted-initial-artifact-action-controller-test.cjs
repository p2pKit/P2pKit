'use strict';

// New fixed-controller wiring models ONLY. Actual new DATA plus original
// Node stream events, synthetic supplier returns/child/clock/fs. No native,
// credential, HTTP, hosted identity or accepted reader/observer/transport run.
const assert = require('node:assert/strict');
const {EventEmitter} = require('node:events');
const {Readable, Writable} = require('node:stream');
const fs = require('node:fs'), path = require('node:path'), vm = require('node:vm');
const D = require('../hosted-initial-artifact-action-data.cjs');
const ProductiveData = require('../hosted-initial-artifact-productive-action-data.cjs');
const {finiteFixture, headers, sha, NS, NOW} = require('./hosted-initial-artifact-action-fixtures.cjs');
const source = fs.readFileSync(path.join(__dirname, '../hosted-initial-artifact-action.cjs'), 'utf8');
const cases = [], test = (name, body) => cases.push({name, body});
const tick = () => new Promise(resolve => setImmediate(resolve));
function packet(tag, raw) {
    const header = Buffer.alloc(5); header[0] = tag.charCodeAt(0); header.writeUInt32BE(raw.length, 1);
    return Buffer.concat([header, raw]);
}
function replaceBody(original, request, value) {
    original.body = Buffer.isBuffer(value) ? value : Buffer.from(JSON.stringify(value));
    original.rawHeaderVector = headers(original.body.length);
    Object.assign(request, {bodyBytes: original.body.length, bodySha256: sha(original.body),
        rawHeaderVectorSha256: sha(Buffer.from(JSON.stringify(original.rawHeaderVector)))});
}
function model(mode = 'upload', config = {}) {
    const m = finiteFixture(mode), f = m.f, upload = mode === 'upload';
    const calls = [], outputs = [], errors = [], writes = [], timers = new Map(), options = {};
    const module = {exports: {}}, signals = new EventEmitter(), env = {...f.environment,
        INPUT_MODE: mode, INPUT_PYTHON: '/usr/bin/python3', 'INPUT_TOOL-PATH': '/usr/bin:/bin',
        GITHUB_OUTPUT: '/model/output', GITHUB_RETENTION_DAYS: '14',
        ACTIONS_RUNTIME_TOKEN: 'MODEL_RESULTS_CREDENTIAL_NOT_REAL', ACTIONS_RESULTS_URL: 'MODEL_RESULTS_URL_NOT_REAL'};
    let now = (upload ? 100n : 200n) * NS, nowMs = NOW, timerId = 0, child = null, mainPromise = null;
    let created = false, demand = 0, readerReturned = false, acceptReader, childCloseRequested = false;
    const readerReady = {raw: f.readyRaw, preSpawnLocalNs: f.bounds.preSpawnLocalNs};
    const readerCompletion = new Promise(resolve => { acceptReader = resolve; });
    const stream = new Readable({highWaterMark: 0, read() {
        demand++; assert(created, 'only actual transport Create model may precede demand'); this.push(null);
    }});
    const processModel = {platform: 'linux', versions: {node: '24.0.0'}, execPath: '/model/node', env, exitCode: undefined,
        hrtime: {bigint: () => now}, stderr: {write(text) { errors.push(text); }},
        on: signals.on.bind(signals), removeListener: signals.removeListener.bind(signals)};
    function hook(name, ...args) { if (typeof config[name] === 'function') config[name](api, ...args); }
    function settleReader() {
        if (readerReturned) return;
        readerReturned = true; calls.push('reader-close'); acceptReader(f.readerClosed);
    }
    const reader = {ready: Promise.resolve(readerReady), stream,
        bind(value) {
            calls.push('bind'); options.bind = value;
            assert.equal(demand, 0); assert.equal(stream.readableDidRead, false);
            assert.equal(value.readySha256, sha(readerReady.raw));
            hook('bind', value);
            return {startByNs: f.bounds.startByNs + (config.wrongBind ? 1n : 0n),
                workEndNs: f.bounds.workEndNs, closeEndNs: f.bounds.closeEndNs};
        }, completion: readerCompletion, cancel() { calls.push('reader-cancel'); settleReader(); },
        finalFrame() { assert(readerReturned); calls.push('reader-F'); return f.finalRaw; }};
    function observer(stage, supplied) {
        calls.push(stage); options[stage] = supplied;
        assert.equal(stage, upload ? 'before' : 'after'); assert.equal(supplied.jobId, '123');
        assert.equal(supplied.requestSha256, sha(upload ? f.readyRaw : f.afterReadyRaw));
        const originals = upload ? f.beforeOriginals : f.afterOriginals,
            closed = upload ? f.beforeClosed : f.afterClosed;
        let accept;
        const completion = new Promise(resolve => { accept = resolve; });
        queueMicrotask(() => {
            now = upload ? 100n * NS + 210000000n : 200n * NS + 600000000n;
            hook('observerReturn', closed, originals);
            calls.push(stage + '-close'); accept(closed);
        });
        return {completion, cancel() { calls.push(stage + '-cancel'); accept(closed); }, originals() {
            calls.push(stage + '-originals'); hook('originals', originals); return originals;
        }};
    }
    function transport(supplied) {
        calls.push('Create'); options.transport = supplied;
        assert.equal(supplied.stream, stream); assert.equal(demand, 0);
        assert.equal(stream.readableDidRead, false); assert.equal(stream.listenerCount('data'), 0);
        assert.equal(stream.listenerCount('readable'), 0);
        created = true; stream.read(0); // Synthetic Create precedes the FIRST demand.
        return new Promise(resolve => queueMicrotask(() => {
            now = 104n * NS + 300000000n;
            hook('transportReturn', supplied);
            if (!config.holdReader) settleReader();
            calls.push('transport-close'); resolve(f.transportClosed);
        }));
    }
    function childClose() {
        assert(child !== null); assert(!childCloseRequested);
        childCloseRequested = true; calls.push('finite-child-close'); child.emit('close', writes.length ? 0 : 1, null);
    }
    class Child extends EventEmitter {
        constructor() {
            super();
            this.stdin = new Writable({write(chunk, _encoding, done) {
                calls.push('I-write'); writes.push(Buffer.from(chunk)); queueMicrotask(done);
            }, final(done) {
                calls.push('stdin-end'); queueMicrotask(done);
                queueMicrotask(() => {
                    if (writes.length) {
                        assert.equal(writes.length, 1); assert.deepEqual(writes[0], packet('I', m.inputRaw));
                        now = (upload ? 107n : 205n) * NS;
                        hook('finiteReturn', m.result);
                        calls.push('finite-F'); child.stdout.push(packet('F', D.encode(m.result)));
                    }
                    child.stdout.push(null); child.stderr.push(null); child.emit('exit', writes.length ? 0 : 1, null);
                    setImmediate(() => { if (!config.holdChildClose) childClose(); });
                });
            }});
            this.stdout = new Readable({read() {}}); this.stderr = new Readable({read() {}});
        }
        kill() { assert.fail('EOF only, not signal-as-known-close'); }
    }
    const imports = {'node:child_process': {ChildProcess: Child, spawn(python, argv, settings) {
        calls.push('finite-spawn'); options.finite = {python, argv, settings}; child = new Child();
        queueMicrotask(() => {
            child.emit('spawn');
            if (!upload) { calls.push('after-R'); child.stdout.push(packet('R', f.afterReadyRaw)); }
        });
        return child;
    }}, 'node:stream': {Readable, Writable}, 'node:path': path,
    'node:fs': {appendFileSync(output, text, settings) {
        calls.push('outputs'); assert.equal(output, '/model/output'); assert.equal(settings.encoding, 'utf8');
        assert(calls.includes('finite-child-close')); outputs.push(text); hook('append', text);
    }}, 'node:timers': {setTimeout(callback, ms) {
        const id = ++timerId; timers.set(id, {callback, end: now + BigInt(ms) * 1000000n}); return id;
    }, clearTimeout(id) { timers.delete(id); }}, './hosted-initial-artifact-action-data.cjs': D,
    './hosted-initial-artifact-productive-action-data.cjs': ProductiveData,
    './hosted-initial-artifact-reader.cjs': {openReader(supplied) {
        calls.push('reader-open'); options.reader = supplied;
        supplied.signal.addEventListener('abort', settleReader, {once: true}); return reader;
    }}, './hosted-initial-artifact-observer.cjs': {beforeOnce: supplied => observer('before', supplied),
        afterOnce: supplied => observer('after', supplied)},
    './hosted-initial-artifact-transport.cjs': {uploadOnce: transport}};
    // Same realm avoids bypassing DATA prototype rules. No arbitrary import,
    // real process/fs/network backend or test seam enters the production module.
    const factory = vm.runInThisContext('(function(require,module,__dirname,process,Date){\n' + source + '\n})',
        {filename: 'offline-new-artifact-controller.cjs', timeout: 1000});
    factory(name => { assert(Object.hasOwn(imports, name)); return imports[name]; }, module,
        '/model/p2pkit/scripts', processModel, {now: () => nowMs});
    const api = {m, f, calls, outputs, errors, writes, timers, options, env, signals, readerReady, reader, module,
        get child() { return child; }, get demand() { return demand; }, get exitCode() { return processModel.exitCode; },
        get result() { return mainPromise; }, setNow(value) { now = value; }, setUtc(value) { nowMs = value; },
        settleReader, childClose,
        async start() { assert(mainPromise === null); hook('setup'); mainPromise = module.exports.main(); await tick(); await tick(); },
        async run() { await api.start(); await mainPromise; return api; },
        async expire() {
            now = upload ? f.bounds.closeEndNs : f.afterBounds.endNs;
            for (const row of [...timers.values()]) if (now >= row.end) row.callback();
            await tick(); await mainPromise;
        }};
    return api;
}
function notAccepted(m, emitted = 0) {
    assert.equal(m.exitCode, 125); assert.equal(m.outputs.length, emitted);
    assert(m.errors.length > 0);
    assert(m.errors.every(text => text === 'INITIAL_ARTIFACT_ACTION_NOT_ACCEPTED\n'));
    assert(m.calls.filter(name => name === 'Create').length <= 1);
    assert(m.calls.filter(name => name === 'finite-spawn').length <= 1);
}

test('UPLOAD original chain validates BEFORE before Create and waits for all closes before six safe outputs', async () => {
    const m = await model().run(); assert.equal(m.exitCode, 0); assert.equal(m.errors.length, 0);
    assert.deepEqual(m.calls.filter(name => ['reader-open', 'bind', 'before', 'before-close', 'before-originals', 'Create',
        'reader-close', 'transport-close', 'reader-F', 'finite-spawn', 'I-write', 'finite-F', 'finite-child-close', 'outputs'].includes(name)),
    ['reader-open', 'bind', 'before', 'before-close', 'before-originals', 'Create', 'reader-close', 'transport-close', 'reader-F',
        'finite-spawn', 'I-write', 'finite-F', 'finite-child-close', 'outputs']);
    assert.equal(m.demand, 1); assert.equal(m.outputs.length, 1);
    const lines = m.outputs[0].trimEnd().split('\n'); assert.equal(lines.length, 6);
    assert.deepEqual(lines, Object.entries(D.outputs(m.m.result)).map(([name, value]) => name + '=' + value));
    assert.equal(m.options.finite.argv[4], 'finish'); assert.equal(m.options.finite.python, '/usr/bin/python3');
    assert.equal(m.timers.size, 0);
});
test('AFTER opens exactly one new R/I/F process and public observer, never reader/Create', async () => {
    const m = await model('after').run(); assert.equal(m.exitCode, 0); assert.equal(m.errors.length, 0);
    assert.deepEqual(m.calls.filter(name => ['finite-spawn', 'after-R', 'after', 'after-close', 'after-originals',
        'I-write', 'finite-F', 'finite-child-close', 'outputs'].includes(name)),
    ['finite-spawn', 'after-R', 'after', 'after-close', 'after-originals', 'I-write', 'finite-F', 'finite-child-close', 'outputs']);
    assert(!m.calls.includes('Create')); assert(!m.calls.includes('reader-open')); assert.equal(m.outputs.length, 1);
    assert.equal(m.options.after.endNs, m.f.afterBounds.endNs);
    assert.equal(m.options.finite.settings.env.P2PKIT_INITIAL_UPLOAD_OWNER_CLOSE_SHA256,
        m.env.P2PKIT_INITIAL_UPLOAD_OWNER_CLOSE_SHA256);
});
test('complete invalid BEFORE Step semantics stop before Create, not merely in later native finish', async () => {
    const m = await model('upload', {setup(m) {
        const job = m.f.job(); job.steps[3].conclusion = 'failure';
        replaceBody(m.f.beforeOriginals[0], m.f.beforeClosed.requests[0], job);
    }}).run(); notAccepted(m); assert(m.calls.includes('before-originals'));
    assert(!m.calls.includes('Create')); assert(!m.calls.includes('finite-spawn')); assert.equal(m.demand, 0);
});
test('current original UTC expiry reached by BEFORE blocks Create without renewal', async () => {
    const m = await model('upload', {setup(m) {
        // Keep public Date fresh and bind every intervening original to a
        // genuinely short model interval, so the current-UTC guard is decisive.
        m.f.ready.authorityExpiresAt = NOW / 1000 + 1;
        m.f.readyRaw = D.encode(m.f.ready); m.readerReady.raw = m.f.readyRaw;
        const hash = sha(m.f.readyRaw);
        m.f.beforeClosed.requestSha256 = hash; m.f.final.readySha256 = hash;
        m.f.finalRaw = D.encode(m.f.final); m.f.readerClosed.readySha256 = hash;
        m.f.readerClosed.finalSha256 = sha(m.f.finalRaw); m.f.transportClosed.requestSha256 = hash;
    }, observerReturn(m) { m.setUtc(NOW + 1000); }}).run();
    notAccepted(m); assert(!m.calls.includes('Create')); assert.equal(m.demand, 0);
});
test('original mapped startBy equality blocks Create instead of extending its pre-upload allowance', async () => {
    const m = await model('upload', {observerReturn(m) { m.setNow(m.f.bounds.startByNs); }}).run();
    notAccepted(m); assert(!m.calls.includes('Create'));
});
test('only exact original source/ref/runner context is admitted before binding any public operation', async () => {
    const m = await model('upload', {setup(m) { m.env.GITHUB_REF = 'refs/heads/main'; }}).run();
    notAccepted(m); assert(!m.calls.includes('bind')); assert(!m.calls.includes('before')); assert(!m.calls.includes('Create'));
});
test('bind cannot replace the actual original reader mapping with a later allowance', async () => {
    const m = await model('upload', {wrongBind: true}).run(); notAccepted(m);
    assert(m.calls.includes('bind')); assert(!m.calls.includes('before')); assert(!m.calls.includes('Create'));
});
test('retained original READY bytes cannot change across the BEFORE callback', async () => {
    const m = await model('upload', {observerReturn(m) { m.readerReady.raw[0] = 0x20; }}).run();
    notAccepted(m); assert(!m.calls.includes('Create'));
});
test('an equal body replacement after actual return does not replace the original HTTP body handle', async () => {
    const m = await model('upload', {transportReturn(m) {
        m.f.beforeOriginals[0].body = Buffer.from(m.f.beforeOriginals[0].body);
    }}).run(); notAccepted(m); assert(m.calls.includes('Create')); assert(!m.calls.includes('finite-spawn'));
});
test('returned complete observer projection stays pinned through the transport callback', async () => {
    const m = await model('upload', {transportReturn(m) { m.f.beforeClosed.requests[0].requestCloseObserved = false; }}).run();
    notAccepted(m); assert(!m.calls.includes('finite-spawn'));
});
test('transport return cannot replace a missing original reader close or authorize finish early', async () => {
    const m = model('upload', {holdReader: true}); await m.start();
    assert(m.calls.includes('transport-close')); assert(!m.calls.includes('finite-spawn')); assert.equal(m.outputs.length, 0);
    m.settleReader(); await m.result; assert.equal(m.exitCode, 0);
});
test('two individually bounded AFTER originals exceeding complete2MiB are refused before FIRST I write', async () => {
    const m = await model('after', {setup(m) {
        m.f.afterOriginals.forEach((row, index) => replaceBody(row, m.f.afterClosed.requests[index], Buffer.alloc(1048576, 0x20)));
    }}).run(); notAccepted(m); assert(m.calls.includes('after-originals')); assert.equal(m.writes.length, 0);
    assert.equal(m.calls.filter(name => name === 'finite-spawn').length, 1);
});
test('rehashing a pending private field cannot authorize its public output', async () => {
    const m = await model('upload', {finiteReturn(_m, result) {
        result.pending.privateLeak = 'MODEL_PRIVATE_NOT_PUBLIC'; result.pendingSha256 = sha(D.encode(result.pending));
    }}).run(); notAccepted(m); assert(m.calls.includes('finite-child-close'));
});
test('a finite F cannot substitute its actual original I hash before safe output', async () => {
    const m = await model('after', {finiteReturn(_m, result) { result.inputSha256 = '0'.repeat(64); }}).run();
    notAccepted(m); assert(m.calls.includes('finite-child-close'));
});
test('complete F and all pipe EOFs do not authorize outputs until the actual child close', async () => {
    const m = model('upload', {holdChildClose: true}); await m.start();
    assert(m.calls.includes('finite-F')); assert.equal(m.outputs.length, 0); assert.equal(m.exitCode, 125);
    m.childClose(); await m.result; assert.equal(m.exitCode, 0); assert.equal(m.outputs.length, 1);
});
test('missing original child close remains NOT_ACCEPTED at the same original end with no retry', async () => {
    const m = model('after', {holdChildClose: true}); await m.start(); await m.expire(); notAccepted(m);
    assert.equal(m.calls.filter(name => name === 'finite-spawn').length, 1);
    m.childClose(); await tick(); assert.equal(m.outputs.length, 0); assert.equal(m.exitCode, 125);
});
test('UTC expiry during the one safe output append leaves the enclosing Step nonzero', async () => {
    const m = await model('upload', {append(m) { m.setUtc(m.f.ready.authorityExpiresAt * 1000); }}).run();
    notAccepted(m, 1); assert.equal(m.calls.filter(name => name === 'outputs').length, 1);
});
test('original LOCAL expiry during output leaves failure, not a renewed after allowance', async () => {
    const m = await model('after', {append(m) { m.setNow(m.f.afterBounds.endNs); }}).run(); notAccepted(m, 1);
});
test('output filesystem error is terminal and prints only static safe diagnostic', async () => {
    const m = await model('upload', {append() { throw new Error('MODEL_PRIVATE_OUTPUT_FAILURE'); }}).run();
    notAccepted(m, 1); assert.equal(m.calls.filter(name => name === 'outputs').length, 1);
});
test('controller reentry poisons the original chain even if its supplier later returns success', async () => {
    const m = await model('upload', {transportReturn(m) { void m.module.exports.main(); }}).run(); notAccepted(m);
    assert.equal(m.calls.filter(name => name === 'reader-open').length, 1); assert(!m.calls.includes('finite-spawn'));
});
test('helper environments exclude Results credentials, API tokens and output paths; six outputs exclude private originals', async () => {
    const m = await model().run(); assert.equal(m.exitCode, 0);
    for (const env of [m.options.reader.environment, m.options.finite.settings.env]) {
        for (const name of ['ACTIONS_RUNTIME_TOKEN', 'ACTIONS_RESULTS_URL', 'GH_TOKEN', 'GITHUB_TOKEN',
            'P2PKIT_ACTIONS_READ_TOKEN', 'GITHUB_OUTPUT']) assert(!Object.hasOwn(env, name));
        assert.equal(env.HOME, '/model/tmp'); assert.equal(env.PATH, '/usr/bin:/bin');
    }
    assert.equal(m.options.transport.service.ACTIONS_RUNTIME_TOKEN, m.env.ACTIONS_RUNTIME_TOKEN);
    const lines = Object.fromEntries(m.outputs[0].trimEnd().split('\n').map(line => {
        const at = line.indexOf('='); return [line.slice(0, at), line.slice(at + 1)];
    })), receipt = D.base64(lines['receipt-base64'], 16384).toString('ascii');
    for (const marker of ['MODEL_RUNNER', 'MODEL_HEADER', 'MODEL_RESULTS', '/model/', 'bodyBase64', 'rawHeaderVector'])
        assert(!receipt.includes(marker));
});
test('API credential contamination and insufficient14-day repository retention fail before opening any owner', async () => {
    for (const change of [m => { m.env.GITHUB_TOKEN = 'MODEL_FORBIDDEN'; }, m => { m.env.GITHUB_RETENTION_DAYS = '13'; }]) {
        const m = await model('upload', {setup: change}).run(); notAccepted(m);
        assert(!m.calls.includes('reader-open')); assert(!m.calls.includes('finite-spawn'));
    }
});
test('AFTER requires original U Step outcome and every historical output carrier before its observer', async () => {
    const m = await model('after', {setup(m) { delete m.env.P2PKIT_INITIAL_UPLOAD_OWNER_CLOSE_SHA256; }}).run();
    notAccepted(m); assert(!m.calls.includes('finite-spawn')); assert(!m.calls.includes('after'));
});
test('signal cancellation and original environment substitution never become later successful output', async () => {
    for (const change of [m => { m.signals.emit('SIGTERM'); }, m => { m.env.RUNNER_NAME += '-changed'; }]) {
        const m = await model('upload', {observerReturn: change}).run(); notAccepted(m);
        assert(!m.calls.includes('Create')); assert.equal(m.demand, 0);
    }
});

(async () => {
    let passed = 0;
    for (const {name, body} of cases) {
        try { await body(); passed++; }
        catch (error) { process.stderr.write('FAIL new Action controller model: ' + name + '\n'); process.exitCode = 1; return; }
    }
    process.stdout.write('PASS ' + passed + '/' + cases.length + ' new Action controller models only\n');
})().catch(() => { process.stderr.write('FAIL new Action controller model harness\n'); process.exitCode = 1; });
