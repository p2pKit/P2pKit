'use strict';

// Authored UNRUN controls. Real new DATA and original Node stream events over
// explicit in-memory child/time/env models; no subprocess/native/API/provider.
// Private finite exposure below is TEST-LOCAL only, with the literal productive
// route. It checks transport, never semantic U/A acceptance or a valid receipt.
const assert = require('node:assert/strict');
const {EventEmitter} = require('node:events');
const {Readable, Writable} = require('node:stream');
const fs = require('node:fs'), path = require('node:path'), vm = require('node:vm');
const crypto = require('node:crypto');
const D = require('../hosted-initial-artifact-productive-action-data.cjs');
const LegacyData = require('../hosted-initial-artifact-action-data.cjs');
const readerSource = fs.readFileSync(path.join(__dirname, '../hosted-initial-artifact-reader.cjs'), 'utf8');
const actionSource = fs.readFileSync(path.join(__dirname, '../hosted-initial-artifact-action.cjs'), 'utf8');
const NS = 1000000000n, cases = [], test = (name, run) => cases.push({name, run});
const tick = () => new Promise(resolve => setImmediate(resolve));
const sha = raw => crypto.createHash('sha256').update(raw).digest('hex');
const IDENTITY = ['GITHUB_ACTIONS', 'GITHUB_REPOSITORY', 'GITHUB_SHA', 'GITHUB_REF', 'GITHUB_RUN_ID',
    'GITHUB_RUN_ATTEMPT', 'GITHUB_EVENT_NAME', 'GITHUB_WORKFLOW_REF', 'GITHUB_WORKFLOW_SHA', 'GITHUB_WORKSPACE',
    'GITHUB_EVENT_PATH', 'GITHUB_SERVER_URL', 'GITHUB_API_URL', 'GITHUB_JOB', 'RUNNER_OS', 'RUNNER_ARCH',
    'RUNNER_NAME', 'RUNNER_ENVIRONMENT', 'RUNNER_TEMP', 'ImageOS', 'ImageVersion'];
const SEED = ['P2PKIT_INITIAL_PRODUCTIVE_BEFORE_SHA256', 'P2PKIT_INITIAL_PRODUCTIVE_BEFORE_OUTCOME',
    'P2PKIT_INITIAL_PRODUCTIVE_DEADLINE_SHA256', 'P2PKIT_INITIAL_PRODUCTIVE_DEADLINE_BASE64',
    'P2PKIT_INITIAL_PRODUCTIVE_SEAL_OUTCOME'];
const UPLOAD = ['P2PKIT_INITIAL_PRODUCTIVE_UPLOAD_SHA256', 'P2PKIT_INITIAL_PRODUCTIVE_UPLOAD_DIRECTORY_SHA256',
    'P2PKIT_INITIAL_PRODUCTIVE_UPLOAD_FILE_METADATA_SHA256', 'P2PKIT_INITIAL_PRODUCTIVE_UPLOAD_OWNER_CLOSE_SHA256',
    'P2PKIT_INITIAL_PRODUCTIVE_UPLOAD_OUTCOME'];
function environment() {
    // Deliberately NOT hosted identity. Only the low-level pipe environment
    // grammar accepts this map; the unchanged semantic DATA/helper must refuse.
    return {...Object.fromEntries([...IDENTITY, ...SEED].map(name => [name, 'SYNTHETIC_NOT_AUTHORITY'])),
        GITHUB_WORKSPACE: '/model/p2pkit', GITHUB_JOB: 'populate', RUNNER_TEMP: '/model/temporary',
        PATH: '/usr/bin:/bin', LANG: 'C', LC_ALL: 'C', PYTHONDONTWRITEBYTECODE: '1', PYTHONUNBUFFERED: '1'};
}
function frame(tag, raw) {
    const header = Buffer.alloc(5); header[0] = tag.charCodeAt(0); header.writeUInt32BE(raw.length, 1);
    return Buffer.concat([header, raw]);
}
function shellModel() {
    let now = 100n * NS, serial = 0, child;
    const calls = [], writes = [], timers = new Map(), signals = new EventEmitter(), errors = [];
    class ModelChild extends EventEmitter {
        constructor() {
            super();
            this.stdin = new Writable({write(raw, _encoding, done) {
                writes.push(Buffer.from(raw)); queueMicrotask(done);
            }, final(done) { queueMicrotask(done); }});
            this.stdout = new Readable({read() {}}); this.stderr = new Readable({read() {}});
        }
        kill() { assert.fail('No signal/PID/replacement close proof'); }
    }
    const imports = {'node:child_process': {ChildProcess: ModelChild, spawn(python, argv, settings) {
        calls.push({python, argv, settings}); // Observe the attempted effect even if its duplicate is caught.
        assert.equal(child, undefined, 'one original model child only');
        child = new ModelChild();
        queueMicrotask(() => child.emit('spawn')); return child;
    }}, 'node:stream': {Readable, Writable}, 'node:path': path, 'node:crypto': crypto,
    'node:timers': {setTimeout(callback, milliseconds) {
        const id = ++serial; timers.set(id, {callback, end: now + BigInt(milliseconds) * 1000000n}); return id;
    }, clearTimeout(id) { timers.delete(id); }}};
    const processModel = {platform: 'linux', versions: {node: '24.20.0'}, execPath: '/model/node',
        hrtime: {bigint: () => now}, env: {}, stderr: {write(text) { errors.push(text); }},
        on: signals.on.bind(signals), removeListener: signals.removeListener.bind(signals)};
    return {imports, calls, writes, timers, errors, processModel, get child() { return child; },
        async close({processClose = true, exit = true, code = 0} = {}) {
            child.stdout.push(null); child.stderr.push(null);
            if (exit) child.emit('exit', code, null);
            await tick(); if (processClose) child.emit('close', code, null); await tick();
        }, async expire(value) {
            now = value;
            for (const timer of [...timers.values()]) if (timer.end <= now) timer.callback();
            await tick();
        }};
}
function readerModel() {
    const s = shellModel(), module = {exports: {}}, control = new AbortController();
    const factory = vm.runInThisContext('(function(require,module,__dirname,process){\n' + readerSource + '\n})',
        {filename: 'productive-reader-explicit-model.cjs', timeout: 1000});
    factory(name => { assert(Object.hasOwn(s.imports, name)); return s.imports[name]; }, module,
        '/model/p2pkit/scripts', s.processModel);
    const options = {python: '/usr/bin/python3', kind: 'worker', environment: environment(), signal: control.signal};
    const readyRaw = D.encode({scope: 'SYNTHETIC_READY_NOT_K_AUTHORITY'}), bytes = Buffer.from('MODEL_CIPHERTEXT_NOT_ACTUAL');
    const bounds = {readySha256: sha(readyRaw), beforeSha256: 'b'.repeat(64), firstRawNs: 900n * NS,
        uploadStartByNs: 901n * NS, uploadEndNs: 960n * NS, zipBytes: bytes.length};
    let handle;
    return {s, module, options, bounds, bytes, readyRaw, get handle() { return handle; },
        async start() { handle = module.exports.openProductiveReader(options); handle.ready.catch(() => {}); await tick(); },
        async ready() { await this.start(); s.child.stdout.push(frame('R', readyRaw)); await handle.ready; },
        async bind() { await this.ready(); return handle.bind(bounds); },
        async demand(tag, raw) {
            assert.equal(handle.stream.read(), null); await tick();
            s.child.stdout.push(frame(tag, raw)); await tick();
            return tag === 'D' ? handle.stream.read() : null;
        }, terminal(scope = 'INITIAL_PRODUCTIVE_ARTIFACT_NATIVE_STREAM_CLOSED_FILES_PENDING_PROCESS_V1') {
            return D.encode({schema: 1, scope, beforeSha256: bounds.beforeSha256, readySha256: sha(readyRaw),
                zipBytes: bytes.length, zipSha256: sha(bytes), nativeCloseSha256: 'c'.repeat(64),
                closedNs: (bounds.firstRawNs + NS).toString(), nativeFileRetirement: 'KNOWN_NATIVE_CLOSE',
                originalReaderOutcome: 'PENDING_ENCLOSING_PROCESS_CLOSE', qualification: 'NOT_ESTABLISHED'});
        }, async failed() {
            await s.expire(160n * NS);
            const result = await handle.completion;
            assert.equal(result.transport, 'incomplete'); assert.equal(result.originalStepOutcome, 'NOT_OBSERVED');
            assert.equal(result.qualification, 'NOT_ESTABLISHED');
            assert(!JSON.stringify(result).includes('SYNTHETIC_NOT_AUTHORITY')); return result;
        }};
}
function actionModel() {
    const s = shellModel(), module = {exports: {}}, outputs = [], readerCalls = [], legacyReaderCalls = [],
        observerCalls = [], transportCalls = [];
    const env = {...environment(), ...Object.fromEntries(UPLOAD.map(name => [name, 'SYNTHETIC_NOT_AUTHORITY'])),
        INPUT_MODE: 'after', INPUT_PYTHON: '/usr/bin/python3', 'INPUT_TOOL-PATH': '/usr/bin:/bin',
        GITHUB_OUTPUT: '/model/output', GITHUB_RETENTION_DAYS: '14',
        ACTIONS_RUNTIME_TOKEN: 'SYNTHETIC_NOT_A_CREDENTIAL', ACTIONS_RESULTS_URL: 'SYNTHETIC_NOT_A_SERVICE'};
    s.processModel.env = env;
    function reader(supplied) {
        readerCalls.push(supplied);
        return {ready: Promise.resolve({raw: D.encode({scope: 'SYNTHETIC_NOT_READY'}), preSpawnLocalNs: 100n * NS}),
            stream: new Readable({read() { assert.fail('No demand before genuine semantic READY'); }}),
            bind() { assert.fail('Invalid semantic READY cannot bind'); }, completion: Promise.resolve({transport: 'incomplete'}),
            cancel() {}, finalFrame() { assert.fail('No original close'); }};
    }
    Object.assign(s.imports, {'node:fs': {appendFileSync(...args) { outputs.push(args); }},
        './hosted-initial-artifact-action-data.cjs': LegacyData,
        './hosted-initial-artifact-productive-action-data.cjs': D,
        './hosted-initial-artifact-reader.cjs': {openReader(...args) {
            legacyReaderCalls.push(args); assert.fail('No legacy route fallback'); }, openProductiveReader: reader},
        './hosted-initial-artifact-observer.cjs': {beforeOnce(...args) { observerCalls.push(args); assert.fail('No real original job'); },
            afterOnce(...args) { observerCalls.push(args); assert.fail('No real original job'); }},
        './hosted-initial-artifact-transport.cjs': {uploadOnce(...args) { transportCalls.push(args); assert.fail('No Create'); }}});
    // Test-local access to the ORIGINAL lexical finite owner with the fixed
    // productive route; production module.exports remains exactly two entries.
    const factory = vm.runInThisContext('(function(require,module,__dirname,process,Date){\n' + actionSource +
        '\nreturn {entry:module.exports, finite:parameters=>openFinite(parameters,PRODUCTIVE_ROUTE)};\n})',
        {filename: 'productive-finite-explicit-model.cjs', timeout: 1000});
    const bound = factory(name => { assert(Object.hasOwn(s.imports, name)); return s.imports[name]; }, module,
        '/model/p2pkit/scripts', s.processModel, {now: () => 1790000000000});
    const control = new AbortController(), observed = [], poisoned = [];
    return {s, env, outputs, readerCalls, legacyReaderCalls, observerCalls, transportCalls, entry: bound.entry, poisoned, observed,
        finite(mode) { return bound.finite({mode, python: '/usr/bin/python3', kind: 'worker', environment: environment(),
            signal: control.signal, originalEndNs: mode === 'finish' ? 160n * NS : null,
            checkpoint(end) { observed.push(end); assert(100n * NS < end); }, poison(error) { poisoned.push(error); }}); }};
}

test('decoded16KiB permits only21848 encoded receipt bytes, no decoded cap extension', () => {
    const raw = Buffer.alloc(16384, 120), encoded = raw.toString('base64');
    assert.equal(encoded.length, 21848); assert.deepEqual(D.base64(encoded, 16384), raw);
    assert.throws(() => D.base64(Buffer.alloc(16385, 120).toString('base64'), 16384), /BASE64_DECODED_BOUND/);
    const item = {model: ''}; item.model = 'x'.repeat(16384 - D.encode(item).length);
    assert.equal(D.encode(item).length, 16384);
    assert.throws(() => D.encode({model: item.model + 'x'}), /ENCODED_BOUND/);
});
test('productive DATA canonical parse preserves integers and rejects duplicate originals', () => {
    const raw = D.encode({job: 9007199254740993n});
    assert.equal(D.record(raw).job, 9007199254740993n);
    assert.throws(() => D.record(Buffer.from('{"job":1,"job":2}\n')), /JSON_DUPLICATE/);
});
test('productive reader literal helper, original mapping and all closes precede exposed EOF', async () => {
    const m = readerModel(), bounds = await m.bind(), call = m.s.calls[0];
    assert.equal(call.argv.join('|'), '-I|-B|-S|/model/p2pkit/scripts/run-hosted-initial-recipient-productive-upload.py|stream|--kind|worker');
    assert.equal(call.settings.cwd, '/model/p2pkit'); assert.equal(call.settings.shell, false);
    assert.equal(call.settings.detached, false); assert.equal(call.settings.stdio.join('|'), 'pipe|pipe|pipe');
    assert(!Object.hasOwn(call.settings.env, 'ACTIONS_RUNTIME_TOKEN'));
    assert.deepEqual(bounds, {startByNs: 101n * NS, workEndNs: 155n * NS, closeEndNs: 160n * NS});
    assert.deepEqual(await m.demand('D', m.bytes), m.bytes);
    await m.demand('F', m.terminal());
    let ended = false; m.handle.stream.on('end', () => { ended = true; });
    await m.s.close({processClose: false}); assert.equal(ended, false);
    m.s.child.emit('close', 0, null); await tick();
    const result = await m.handle.completion;
    assert.equal(result.scope, 'INITIAL_PRODUCTIVE_ARTIFACT_FIXED_READER_TRANSPORT_ONLY');
    assert.equal(result.transport, 'closed'); assert(Object.values(result.originalPipeCloses).every(Boolean));
    assert.equal(result.originalStepOutcome, 'NOT_OBSERVED'); assert.equal(result.qualification, 'NOT_ESTABLISHED');
    m.handle.stream.read(); await tick(); assert.equal(ended, true);
});
test('productive reader cannot rename old seal end as upload transition', async () => {
    const m = readerModel(); await m.ready();
    const {uploadStartByNs, ...rest} = m.bounds;
    assert.throws(() => m.handle.bind({...rest, sealEndNs: uploadStartByNs}), /CLOSED_DATA_FIELDS/);
    assert.equal(m.s.writes.length, 0); await m.failed();
});
test('productive reader rejects legacy final scope after actual demanded bytes', async () => {
    const m = readerModel(); await m.bind(); await m.demand('D', m.bytes);
    await m.demand('F', m.terminal('INITIAL_ARTIFACT_NATIVE_STREAM_CLOSED_FILES_PENDING_PROCESS_V1'));
    assert.equal((await m.failed()).code, 'INITIAL_ARTIFACT_READER_FINAL_BINDING');
});
test('changed original READY hash fails before first productive demand', async () => {
    const m = readerModel(); await m.ready();
    assert.throws(() => m.handle.bind({...m.bounds, readySha256: '0'.repeat(64)}), /BIND_FIELDS/);
    assert.equal(m.s.writes.length, 0); await m.failed();
});
test('one-shot reader latch is shared with legacy even when nested refusal is swallowed', async () => {
    const m = readerModel(); await m.ready();
    assert.throws(() => m.module.exports.openReader(m.options), /ONE_INVOCATION/);
    assert.equal(m.s.calls.length, 1); await m.failed();
});
test('productive worker-only and credential-free input failures spend the same latch', () => {
    for (const kind of ['gate', 'credential']) {
        const m = readerModel();
        if (kind === 'gate') m.options.kind = 'gate';
        else m.options.environment.GITHUB_TOKEN = 'SYNTHETIC_NONCREDENTIAL';
        assert.throws(() => m.module.exports.openProductiveReader(m.options),
            kind === 'gate' ? /KIND/ : /TOKEN_FREE_ENVIRONMENT/);
        assert.throws(() => m.module.exports.openReader(m.options), /ONE_INVOCATION/);
        assert.equal(m.s.calls.length, 0);
    }
});
test('21848 output encoding does not enlarge productive helper environment cap', () => {
    const m = readerModel(); m.options.environment.P2PKIT_INITIAL_PRODUCTIVE_DEADLINE_BASE64 = 'x'.repeat(21848);
    assert.throws(() => m.module.exports.openProductiveReader(m.options), /ENVIRONMENT_FIELDS/);
    assert.equal(m.s.calls.length, 0);
});
test('actual productive finite finish retains original frame and all original closes', async () => {
    const m = actionModel(), finite = m.finite('finish'); await tick();
    const input = D.encode({scope: 'SYNTHETIC_INPUT_NOT_SEMANTIC_ACCEPTANCE'}), final = D.encode({scope: 'SYNTHETIC_F_TRANSPORT_ONLY'});
    finite.input(input); await tick();
    assert.deepEqual(m.s.writes, [frame('I', input)]);
    m.s.child.stdout.push(frame('F', final)); await tick();
    let complete = false; finite.completion.then(() => { complete = true; });
    await m.s.close({processClose: false}); assert.equal(complete, false);
    assert.throws(() => finite.finalFrame(), /FINITE_NO_KNOWN_RETURN/);
    m.s.child.emit('close', 0, null); await tick();
    const result = await finite.completion;
    assert.equal(result.transport, 'closed'); assert.equal(result.code, null);
    assert.equal(result.inputWriteCallbackObserved, true); assert.equal(result.stdinEndCallbackObserved, true);
    assert(Object.values(result.originalPipeCloses).every(Boolean)); assert.deepEqual(finite.finalFrame(), final);
    assert(m.s.calls[0].argv.includes('/model/p2pkit/scripts/run-hosted-initial-recipient-productive-upload.py'));
    assert.equal(m.poisoned.length, 0); assert.equal(m.outputs.length, 0);
});
test('actual productive finite after refuses renewal beyond original15second end', async () => {
    const m = actionModel(), finite = m.finite('after'); await tick();
    m.s.child.stdout.push(frame('R', D.encode({scope: 'SYNTHETIC_R_TRANSPORT_ONLY'}))); await finite.ready;
    assert.throws(() => finite.bindAfter(116n * NS), /FINITE_NO_EXTENSION/);
    assert.equal(m.poisoned.length, 1); assert.equal(m.s.writes.length, 0);
    await m.s.expire(115n * NS);
    assert.equal((await finite.completion).transport, 'incomplete');
    assert.throws(() => finite.finalFrame(), /FINITE_NO_KNOWN_RETURN/);
});
test('finite premature EOF or oversized frame never proves known productive return', async () => {
    for (const oversized of [false, true]) {
        const m = actionModel(), finite = m.finite('after'); await tick();
        if (oversized) {
            const header = Buffer.alloc(5); header[0] = 82; header.writeUInt32BE(16385, 1);
            m.s.child.stdout.push(header); await tick();
        }
        await m.s.close();
        const result = await finite.completion;
        assert.equal(result.transport, 'incomplete'); assert.equal(m.s.writes.length, 0);
        assert.throws(() => finite.finalFrame(), /FINITE_NO_KNOWN_RETURN/);
        assert.equal(m.poisoned.length, 1);
    }
});
test('public productive upload chooses only productive reader then rejects unqualified READY before Create', async () => {
    const m = actionModel(); m.env.INPUT_MODE = 'upload'; await m.entry.mainProductive();
    assert.equal(m.readerCalls.length, 1); assert.equal(m.readerCalls[0].kind, 'worker');
    assert(Object.hasOwn(m.readerCalls[0].environment, SEED[0]));
    assert(!Object.hasOwn(m.readerCalls[0].environment, 'P2PKIT_INITIAL_BEFORE_SHA256'));
    assert(!Object.hasOwn(m.readerCalls[0].environment, 'ACTIONS_RUNTIME_TOKEN'));
    assert.equal(m.s.processModel.exitCode, 125); assert.equal(m.observerCalls.length, 0);
    assert.equal(m.transportCalls.length, 0); assert.equal(m.s.calls.length, 0); assert.equal(m.outputs.length, 0);
    await m.entry.main(); assert.equal(m.readerCalls.length, 1); assert.equal(m.legacyReaderCalls.length, 0);
});
test('public productive after has fixed worker helper but no acceptance from transport-only READY', async () => {
    const m = actionModel(), pending = m.entry.mainProductive(); await tick();
    assert.equal(m.s.calls.length, 1);
    const call = m.s.calls[0];
    assert.equal(call.argv.join('|'), '-I|-B|-S|/model/p2pkit/scripts/run-hosted-initial-recipient-productive-upload.py|after|--kind|worker');
    assert(!Object.hasOwn(call.settings.env, 'ACTIONS_RUNTIME_TOKEN'));
    m.s.child.stdout.push(frame('R', D.encode({scope: 'SYNTHETIC_NOT_READY'}))); await tick();
    await m.s.close(); await pending;
    assert.equal(m.s.processModel.exitCode, 125); assert.equal(m.observerCalls.length, 0);
    assert.equal(m.outputs.length, 0); assert.equal(m.transportCalls.length, 0);
    assert(m.s.errors.every(text => text === 'INITIAL_ARTIFACT_ACTION_NOT_ACCEPTED\n'));
});
test('public productive gate or API credential refusal cannot fall back to legacy', async () => {
    for (const failure of ['gate', 'token']) {
        const m = actionModel();
        if (failure === 'gate') m.env.GITHUB_JOB = 'initial-recipient-gate';
        else m.env.GH_TOKEN = 'SYNTHETIC_NONCREDENTIAL';
        await m.entry.mainProductive();
        m.env.GITHUB_JOB = 'populate'; delete m.env.GH_TOKEN;
        await m.entry.main();
        assert.equal(m.s.calls.length, 0); assert.equal(m.readerCalls.length, 0); assert.equal(m.outputs.length, 0);
        assert.equal(m.legacyReaderCalls.length, 0);
        assert.equal(m.s.processModel.exitCode, 125);
        assert(m.s.errors.every(text => text === 'INITIAL_ARTIFACT_ACTION_NOT_ACCEPTED\n'));
    }
});

(async () => {
    for (const item of cases) { await item.run(); process.stdout.write('PASS ' + item.name + '\n'); }
    process.stdout.write(String(cases.length) + ' productive DATA/pipe/model controls passed; not hosted acceptance\n');
})().catch(error => { process.stderr.write(String(error.stack || error) + '\n'); process.exitCode = 1; });
