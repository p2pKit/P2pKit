'use strict';

// Authored UNRUN controls. Real new DATA and original Node stream events over
// explicit in-memory child/time/env models; no subprocess/native/API/provider.
// Private finite exposure below is TEST-LOCAL only, with the literal productive
// route. Pipe models check transport only. The separate synthetic DATA fixtures
// below check public validators, never original U/A authority or a real receipt.
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

// Invented public DATA, not service responses, personal approval, owner/native
// returns or qualification. Expected phase offsets are literal reviewed values,
// not generated by production allocation helpers or new test-only exports.
const DATA_NOW = Date.parse('2026-09-26T12:00:00Z'), DATA_JOB = '2026-09-26T10:00:00Z';
const DATA_POLICY = 'a1e4cc4862d46d7887b9cf41e73127939f41342042afe0aee00c3b603b38953b';
const DATA_PHASES = [
    ['productive-entry',120,870], ['recipient-validation',240,1110], ['recipient-final',45,1155], ['recipient-read',30,1185],
    ['canonical-init',120,1305], ['canonical-init-final',45,1350], ['canonical-init-read',30,1380],
    ['dependency-stage',120,1500], ['empty-seed',120,1620], ['custody-prepare',120,1740],
    ['custody-prepare-final',45,1785], ['custody-prepare-read',30,1815], ['producer-work',600,2415],
    ['producer-return',225,2640], ['producer-final',45,2685], ['producer-read',30,2715], ['custody-collect',120,2835],
    ['custody-collect-final',45,2880], ['custody-collect-read',30,2910], ['custody-uninstall',90,3000],
    ['custody-uninstall-final',45,3045], ['custody-uninstall-read',30,3075], ['dependency-export',120,3195],
    ['save-set-before',120,3315], ['producer-owner-return',45,3360], ['save-transition',30,3390],
    ['provider-save',180,3570], ['save-readmission',120,3690], ['save-set-after',120,3810], ['save-observation',30,3840],
    ['save-owner-return',45,3885], ['probe-transition',30,3915], ['provider-probe',180,4095],
    ['custody-readmission',120,4215], ['provider-observation',30,4245], ['custody-freeze',180,4425],
    ['custody-encrypt',240,4665], ['custody-encrypt-final',45,4710], ['custody-encrypt-read',30,4740],
    ['ciphertext-open',90,4830], ['ciphertext-verify',90,4920], ['custody-owner-return',45,4965],
    ['seal-transition',30,4995], ['separate-seal',120,5115], ['upload-transition',30,5145],
    ['evidence-upload',180,5325], ['upload-after-guard',30,5355], ['delivery-return',45,5400]
];
function dataCopy(value) {
    if (Array.isArray(value)) return value.map(dataCopy);
    if (value !== null && typeof value === 'object')
        return Object.fromEntries(Object.entries(value).map(([name, item]) => [name, dataCopy(item)]));
    return value;
}
function dataAllocationPolicy() {
    return {scope: 'CLOSED_SOURCE_PROPOSAL_NOT_ADMITTED_OR_MEASURED_FIT', proposedJobSeconds: 5400,
        phases: DATA_PHASES.map(([name, maximumSeconds]) => ({name, maximumSeconds})), allocatedSeconds: 4650,
        unallocatedSetupHeadroomSeconds: 750,
        headroomScope: 'ARITHMETIC_ONLY_ALREADY_ELAPSED_SETUP_AND_SERVICE_CHARGES_STILL_APPLY',
        nativeCaptureSpans: [
            ['recipient', ['recipient-validation', 'recipient-final'], 285],
            ['initializer', ['canonical-init', 'canonical-init-final'], 165],
            ['custody-prepare', ['custody-prepare', 'custody-prepare-final'], 165],
            ['producer', ['producer-work', 'producer-return', 'producer-final'], 870],
            ['custody-collect', ['custody-collect', 'custody-collect-final'], 165],
            ['custody-uninstall', ['custody-uninstall', 'custody-uninstall-final'], 135],
            ['custody-encrypt', ['custody-encrypt', 'custody-encrypt-final'], 285]
        ].map(([name, phases, maximumSeconds]) => ({name, phases, maximumSeconds})),
        nativeCaptureScope: 'ORIGINAL_FIRST_WORK_ANCHOR_INCLUDING_IDLE_GAPS_NOT_PER_CALL_RENEWAL', windowsNativeFileSeconds: 900,
        producerReturn: {seconds: 225, sameHomeStopSeconds: 120, sameHomeStopIncluded: true,
            scope: 'STOP_AND_CANONICAL_TAIL_SHARE_ORIGINAL_RETURN_CAP'},
        dependencyObservations: {phases: ['empty-seed', 'dependency-export', 'save-set-before', 'save-set-after'],
            hardSeconds: 120, newWorkSeconds: 90, fileBytes: 512 * 1024 * 1024, aggregateBytes: 2 * 1024 * 1024 * 1024,
            strategy: 'STREAM_PER_FILE_NOT_WINDOWS_AGGREGATE_SNAPSHOT'},
        originalEntry: 'SEPARATE_UNCHANGED_ORIGINAL75_LOCAL45_ORIGINAL120_NOT_EXTENDED',
        failureCustody: 'RESERVED_CUSTODY_CAPS_NOT_A_FAILED_OR_UNKNOWN_OWNER_EXECUTOR',
        providerScope: 'PROPOSED_CAPS_NOT_STORAGE_CONTENTS_OR_RESOLVER_QUALIFICATION'};
}
function bindProductiveData(f) {
    const proposal = f.ready.originalProposal;
    proposal.serviceTimeBasisSha256 = sha(D.encode(proposal.serviceTimeBasis));
    f.ready.deadline.originalProposalSha256 = sha(D.encode(proposal));
    f.after.originalProposal = dataCopy(proposal); f.after.deadline = dataCopy(f.ready.deadline);
    const deadlineRaw = D.encode(f.ready.deadline);
    f.env.P2PKIT_INITIAL_PRODUCTIVE_DEADLINE_BASE64 = deadlineRaw.toString('base64');
    f.env.P2PKIT_INITIAL_PRODUCTIVE_DEADLINE_SHA256 = sha(deadlineRaw);
    f.readyRaw = D.encode(f.ready); f.afterRaw = D.encode(f.after);
    return f;
}
function productiveDataFixture({request = 65n * NS, age = 0n} = {}) {
    const source = {commit: 'a'.repeat(40), tree: 'b'.repeat(40)}, selection = 'desktop-linux-x64',
        clock = {role: 'linux-x64', domain: 'linux.clock_gettime_ns(CLOCK_MONOTONIC_RAW)', ticksPerSecond: NS},
        env = {GITHUB_ACTIONS: 'true', GITHUB_REPOSITORY: 'p2pKit/P2pKit', GITHUB_SHA: source.commit,
            GITHUB_REF: 'refs/heads/work/release-foundation-20260926-1WzHcOIr', GITHUB_RUN_ID: '123456', GITHUB_RUN_ATTEMPT: '1',
            GITHUB_EVENT_NAME: 'workflow_dispatch', GITHUB_WORKFLOW_SHA: source.commit, GITHUB_JOB: 'populate',
            GITHUB_SERVER_URL: 'https://github.com', GITHUB_API_URL: 'https://api.github.com',
            RUNNER_ENVIRONMENT: 'github-hosted', RUNNER_OS: 'Linux', RUNNER_ARCH: 'X64', RUNNER_NAME: 'SYNTHETIC-DATA-NOT-RUNNER',
            P2PKIT_INITIAL_PRODUCTIVE_BEFORE_SHA256: '1'.repeat(64), P2PKIT_INITIAL_PRODUCTIVE_BEFORE_OUTCOME: 'success',
            P2PKIT_INITIAL_PRODUCTIVE_SEAL_OUTCOME: 'success', P2PKIT_INITIAL_PRODUCTIVE_UPLOAD_SHA256: '2'.repeat(64),
            P2PKIT_INITIAL_PRODUCTIVE_UPLOAD_OUTCOME: 'success', P2PKIT_INITIAL_PRODUCTIVE_UPLOAD_DIRECTORY_SHA256: '3'.repeat(64),
            P2PKIT_INITIAL_PRODUCTIVE_UPLOAD_FILE_METADATA_SHA256: '4'.repeat(64),
            P2PKIT_INITIAL_PRODUCTIVE_UPLOAD_OWNER_CLOSE_SHA256: '5'.repeat(64)};
    env.GITHUB_WORKFLOW_REF = env.GITHUB_REPOSITORY + '/.github/workflows/dependency-cache-bootstrap.yml@' + env.GITHUB_REF;
    const github = {repository: env.GITHUB_REPOSITORY, eventSha256: '6'.repeat(64), event: 'workflow_dispatch',
        runId: env.GITHUB_RUN_ID, runAttempt: env.GITHUB_RUN_ATTEMPT, workflow: '.github/workflows/dependency-cache-bootstrap.yml',
        workflowSha: source.commit, job: 'populate', ref: env.GITHUB_REF, profile: 'cache-bootstrap', selection,
        runnerOS: 'Linux', runnerArch: 'X64'},
        workerGithub = Object.fromEntries(Object.entries(github).filter(([name]) => !['profile', 'selection'].includes(name)));
    workerGithub.eventBinding = {originalMain: '3bc76f956f8f47447b51a62474fc878b9c43173c', policyHead: source.commit,
        selection, expectedCommit: source.commit, expectedTree: source.tree};
    const shared = {schema: 1, profile: 'cache-bootstrap', selection, cacheCohort: {profile: 'desktop', role: 'linux-x64'},
        source, github: workerGithub, workerIdentitySha256: '7'.repeat(64), clock, firstUseAt: DATA_NOW / 1000 - 3600,
        budgetAcceptance: 'NOT_ADMITTED', testAcceptance: 'NOT_PERFORMED', exportSaveAuthority: false},
        job = BigInt(Date.parse(DATA_JOB) / 1000), charged = (age + 66n) * NS, virtual = request - charged,
        service = {numericJobId: 789, runnerName: env.RUNNER_NAME, selector: 'ubuntu-latest', jobStartedAt: DATA_JOB,
            originDateEpochSeconds: job + age, firstNs: 0n, lastNs: request + NS, jobsRequestStartedNs: request,
            originalsSha256: Object.fromEntries(['attempt', 'jobs', 'approvals', 'comment', 'environment', 'branches', 'main',
                'reviewed_ref'].map(name => [name, sha(Buffer.from('SYNTHETIC-NOT-ORIGINAL-' + name))])),
            budgetAcceptance: 'NOT_ADMITTED', exportSaveAuthority: false},
        basis = {...dataCopy(shared), scope: 'INITIAL_RECIPIENT_BOOTSTRAP_SERVICE_TIME_BASIS_V1', invocation: 'c'.repeat(32),
            service, policy: {scope: 'SERVICE_DATE_TRANSLATION_NOT_NATIVE_START_OR_JOB_ALLOCATION',
                anchor: 'ORIGINAL_JOBS_REQUEST_STARTED_NS', dateQuantizationSeconds: 1, maximumServiceCacheSeconds: 60,
                clockMarginSeconds: 5}, jobsRequestStartedNs: request, jobStartedEpochSeconds: job,
            serviceAgeSeconds: age, chargedAgeNs: charged, jobStartBasisNs: virtual},
        proposal = {...dataCopy(shared), scope: 'INITIAL_RECIPIENT_BOOTSTRAP_ALLOCATION_PROPOSAL_V1', serviceTimeBasis: basis,
            serviceTimeBasisSha256: '0'.repeat(64), policy: dataAllocationPolicy(), allocationStartBasisNs: virtual + 750n * NS,
            proposedJobEndNs: virtual + 5400n * NS,
            phaseFencesNs: Object.fromEntries(DATA_PHASES.map(([name, _seconds, offset]) => [name, virtual + BigInt(offset) * NS])),
            productiveOwner: 'NOT_CREATED'},
        deadline = {schema: 1, scope: 'INITIAL_RECIPIENT_PRODUCTIVE_RECEIVER_DEADLINES_V1', kind: 'worker', selection,
            source, github, policySha256: DATA_POLICY, originalProposalSha256: '0'.repeat(64), originalJobBasisNs: virtual, clock,
            originalBootDigest: '8'.repeat(64), sealFirstNs: virtual + 4995n * NS, sealEndNs: virtual + 5115n * NS,
            uploadStartByNs: virtual + 5145n * NS, uploadEndNs: virtual + 5325n * NS,
            afterEndNs: virtual + 5355n * NS, returnEndNs: virtual + 5400n * NS,
            collectCloseSha256: '9'.repeat(64), manifestSha256: 'a'.repeat(64), sealSha256: 'b'.repeat(64),
            budgetAcceptance: 'NOT_ADMITTED', exportSaveAuthority: false},
        names = ['evidence.tar.gz.gpg', 'manifest.json', 'custody-tail.tar.gz.gpg', 'custody-tail-manifest.json'],
        members = names.map((name, index) => ({name, bytes: (index + 1) * 10, sha256: 'd'.repeat(64)})),
        first = virtual + 5144n * NS,
        ready = {schema: 1, scope: 'INITIAL_PRODUCTIVE_ARTIFACT_NATIVE_READY_PENDING_SERVICE_AND_STREAM_V1', kind: 'worker',
            selection, source, github: {repository: env.GITHUB_REPOSITORY, runId: env.GITHUB_RUN_ID,
                runAttempt: env.GITHUB_RUN_ATTEMPT, job: 'populate', jobId: 789, role: 'linux-x64'},
            beforeSha256: env.P2PKIT_INITIAL_PRODUCTIVE_BEFORE_SHA256, carrierCloseSha256: 'e'.repeat(64),
            firstRawNs: String(first), deadline, originalProposal: proposal,
            workEndNs: String(first + 55n * NS), closeEndNs: String(first + 60n * NS), members,
            zipBytes: 100 + 22 + names.reduce((total, name) => total + 30 + 16 + 46 + 2 * name.length, 0),
            originals: {eventSha256: github.eventSha256, policySha256: DATA_POLICY, matchSha256: 'f'.repeat(64)},
            jobOriginal: [789, DATA_JOB, env.RUNNER_NAME, 456], observedAt: DATA_NOW / 1000,
            nativeFileRetirement: 'PENDING_ORIGINAL_READERS', originalStepOutcome: 'NOT_OBSERVED', qualification: 'NOT_ESTABLISHED',
            policyNotBefore: DATA_NOW / 1000 - 86400, policyExpiresAt: DATA_NOW / 1000 + 86400,
            authorityNotBefore: DATA_NOW / 1000 - 7200, authorityExpiresAt: DATA_NOW / 1000 + 3600},
        after = {...Object.fromEntries(['schema', 'kind', 'selection', 'source', 'github', 'beforeSha256', 'observedAt',
            'originalStepOutcome', 'qualification', 'policyNotBefore', 'policyExpiresAt', 'authorityNotBefore', 'authorityExpiresAt']
            .map(name => [name, dataCopy(ready[name])])),
            scope: 'INITIAL_PRODUCTIVE_ARTIFACT_AFTER_READY_PENDING_PUBLIC_OBSERVATION_V1',
            uploadSha256: env.P2PKIT_INITIAL_PRODUCTIVE_UPLOAD_SHA256,
            firstRawNs: String(virtual + 5323n * NS), endNs: String(virtual + 5338n * NS), artifactId: '9010'};
    return bindProductiveData({env, ready, after});
}
function validateProductiveData(f) {
    return [D.ready(f.readyRaw, f.env, DATA_NOW), D.afterReady(f.afterRaw, f.env, DATA_NOW)];
}
function rejectsProductiveChange(change) {
    const f = productiveDataFixture(); validateProductiveData(f);
    const original = Buffer.from(f.readyRaw);
    change(f.ready); bindProductiveData(f); // Rebind every shallow hash; original arithmetic must still refuse.
    assert(!original.equals(f.readyRaw), 'negative must change its actual baseline');
    assert.throws(() => D.ready(f.readyRaw, f.env, DATA_NOW), D.DataError);
    assert.throws(() => D.afterReady(f.afterRaw, f.env, DATA_NOW), D.DataError);
}
test('synthetic productive DATA keeps exact66 and unsigned5400/4650 ends for negative zero and positive V', () => {
    const cases = [[65n * NS, 0n, -NS, 66n * NS, 749n * NS, 5399n * NS],
        [66n * NS, 0n, 0n, 66n * NS, 750n * NS, 5400n * NS],
        [67n * NS, 0n, NS, 66n * NS, 751n * NS, 5401n * NS],
        [75n * NS, 10n, -NS, 76n * NS, 749n * NS, 5399n * NS],
        [0n, 0n, -66n * NS, 66n * NS, 684n * NS, 5334n * NS],
        [0n, 684n, -750n * NS, 750n * NS, 0n, 4650n * NS]];
    for (const [request, age, virtual, charged, start, end] of cases) {
        const f = productiveDataFixture({request, age}), [ready, after] = validateProductiveData(f),
            proposal = ready.originalProposal, basis = proposal.serviceTimeBasis;
        assert.equal(BigInt(basis.jobStartBasisNs), virtual); assert.equal(BigInt(ready.deadline.originalJobBasisNs), virtual);
        assert.equal(BigInt(basis.chargedAgeNs), charged); assert.equal(BigInt(proposal.allocationStartBasisNs), start);
        assert.equal(BigInt(proposal.proposedJobEndNs), end); assert.equal(BigInt(after.deadline.returnEndNs), end);
        assert.equal(end, request + (BigInt(basis.jobStartedEpochSeconds) + 5400n -
            BigInt(basis.service.originDateEpochSeconds) - 66n) * NS);
        assert.equal(Object.keys(proposal.phaseFencesNs).length, 48);
        assert.equal(BigInt(proposal.phaseFencesNs['separate-seal']), virtual + 5115n * NS);
        assert.deepEqual(D.encode(ready), f.readyRaw); assert.deepEqual(D.encode(after), f.afterRaw);
        assert.equal(ready.qualification, 'NOT_ESTABLISHED'); assert.equal(proposal.budgetAcceptance, 'NOT_ADMITTED');
    }
});
test('synthetic productive DATA signed coordinates retain exact BigInt tokens without changing native defaults', () => {
    const raw = D.encode({originalJobBasisNs: -9007199254740993n, jobStartBasisNs: -18446744073709551615n}), value = D.record(raw);
    assert.equal(value.originalJobBasisNs, -9007199254740993n); assert.equal(value.jobStartBasisNs, -18446744073709551615n);
    assert.deepEqual(D.encode(value), raw); assert.throws(() => D.integer(-1n), D.DataError);
    for (const key of ['originalJobBasisNs', 'jobStartBasisNs']) {
        for (const bad of [true, '-1000000000', -(1n << 64n), 1n << 64n]) rejectsProductiveChange(row => {
            if (key === 'originalJobBasisNs') row.deadline[key] = bad;
            else row.originalProposal.serviceTimeBasis[key] = bad;
        });
        const f = productiveDataFixture(), text = f.readyRaw.toString('ascii'), token = '"' + key + '":-1000000000';
        assert(text.includes(token));
        for (const alias of ['-1000000000.0', '-1000000000e0', '-0']) {
            const changed = text.replace(token, '"' + key + '":' + alias);
            assert.notEqual(changed, text);
            assert.throws(() => D.ready(Buffer.from(changed, 'ascii'), f.env, DATA_NOW), D.DataError);
        }
    }
});
test('synthetic productive negative V cannot be clamped rebased or derived from a later original request or Date', () => {
    for (const virtual of [0n, -NS + 1n, -NS - 1n]) rejectsProductiveChange(row => {
        row.originalProposal.serviceTimeBasis.jobStartBasisNs = row.deadline.originalJobBasisNs = virtual;
    });
    for (const change of [
        basis => { basis.service.jobsRequestStartedNs = basis.service.lastNs; },
        basis => { basis.service.originDateEpochSeconds++; },
        basis => { basis.service.jobStartedAt = '2026-09-26T10:00:01Z'; },
        basis => { basis.chargedAgeNs--; },
        basis => { basis.policy.maximumServiceCacheSeconds = 59; }
    ]) rejectsProductiveChange(row => change(row.originalProposal.serviceTimeBasis));
});
test('synthetic productive negative V does not make raw timestamps charges or phase fences signed', () => {
    for (const name of ['sealFirstNs', 'sealEndNs', 'uploadStartByNs', 'uploadEndNs', 'afterEndNs', 'returnEndNs'])
        rejectsProductiveChange(row => { row.deadline[name] = -1n; });
    for (const name of ['allocationStartBasisNs', 'proposedJobEndNs'])
        rejectsProductiveChange(row => { row.originalProposal[name] = -1n; });
    for (const [name] of DATA_PHASES)
        rejectsProductiveChange(row => { row.originalProposal.phaseFencesNs[name] = -1n; });
    for (const name of ['jobsRequestStartedNs', 'jobStartedEpochSeconds', 'serviceAgeSeconds', 'chargedAgeNs'])
        rejectsProductiveChange(row => { row.originalProposal.serviceTimeBasis[name] = -1n; });
    for (const name of ['firstNs', 'lastNs', 'jobsRequestStartedNs', 'originDateEpochSeconds'])
        rejectsProductiveChange(row => { row.originalProposal.serviceTimeBasis.service[name] = -1n; });
    rejectsProductiveChange(row => { row.originalProposal.serviceTimeBasis.chargedAgeNs = 1n << 64n; });
});
test('synthetic productive unsigned end and allocation-start boundaries still refuse underflow or overflow', () => {
    const maximum = (1n << 64n) - 1n, good = productiveDataFixture({request: maximum - 5334n * NS}),
        [ready] = validateProductiveData(good);
    assert.equal(BigInt(ready.originalProposal.proposedJobEndNs), maximum);
    const underflow = productiveDataFixture({request: 0n, age: 685n});
    assert.equal(underflow.ready.originalProposal.allocationStartBasisNs, -NS);
    const expired = productiveDataFixture({request: NS - 1n, age: 5335n});
    assert.equal(expired.ready.originalProposal.proposedJobEndNs, -1n);
    for (const f of [underflow, expired, productiveDataFixture({request: maximum - 5334n * NS + 1n})]) {
        assert.throws(() => D.ready(f.readyRaw, f.env, DATA_NOW), D.DataError);
        assert.throws(() => D.afterReady(f.afterRaw, f.env, DATA_NOW), D.DataError);
    }
    const chargedOverflow = productiveDataFixture({request: 0n, age: maximum / NS + 1n});
    assert(chargedOverflow.ready.originalProposal.serviceTimeBasis.chargedAgeNs > maximum);
    assert.throws(() => D.ready(chargedOverflow.readyRaw, chargedOverflow.env, DATA_NOW), D.DataError);
});
test('synthetic productive negative V preserves external original bindings and strict upload UTC fences', () => {
    const f = productiveDataFixture(), [ready, after] = validateProductiveData(f);
    assert.deepEqual(D.localBounds(ready, 100n * NS), {preSpawnLocalNs: 100n * NS, startByNs: 101n * NS,
        workEndNs: 155n * NS, closeEndNs: 160n * NS});
    assert.deepEqual(D.afterBounds(after, 200n * NS), {preSpawnLocalNs: 200n * NS, endNs: 215n * NS});
    for (const change of [row => { row.deadline.originalBootDigest = 'c'.repeat(64); },
        row => { row.deadline.clock.ticksPerSecond++; }, row => { row.source.commit = 'd'.repeat(40); },
        row => { row.originalProposal.serviceTimeBasisSha256 = 'e'.repeat(64); },
        row => { row.firstRawNs = String(row.deadline.uploadStartByNs); },
        row => { row.closeEndNs = String(BigInt(row.closeEndNs) + 1n); }]) {
        const changed = dataCopy(f.ready); change(changed);
        assert.throws(() => D.ready(D.encode(changed), f.env, DATA_NOW), D.DataError);
    }
    const late = dataCopy(f.after); late.firstRawNs = String(late.deadline.uploadEndNs);
    assert.throws(() => D.afterReady(D.encode(late), f.env, DATA_NOW), D.DataError);
    for (const now of [ready.authorityExpiresAt * 1000, ready.authorityNotBefore * 1000 - 1]) {
        assert.throws(() => D.ready(f.readyRaw, f.env, now), D.DataError);
        assert.throws(() => D.afterReady(f.afterRaw, f.env, now), D.DataError);
    }
});

(async () => {
    for (const item of cases) { await item.run(); process.stdout.write('PASS ' + item.name + '\n'); }
    process.stdout.write(String(cases.length) + ' productive DATA/pipe/model controls passed; not hosted acceptance\n');
})().catch(error => { process.stderr.write(String(error.stack || error) + '\n'); process.exitCode = 1; });
