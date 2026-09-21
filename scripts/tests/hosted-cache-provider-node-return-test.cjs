'use strict';
// Entirely supplied synthetic events/bytes. No child, signal, clock or authority.
const assert = require('node:assert/strict');
const {createHash} = require('node:crypto');
const {inspect} = require('node:util');
const {ReceiptReducer, ReceiptError} = require('../hosted-cache-provider-node-return.cjs');

const cases = [];
const test = (name, run) => cases.push({name, run});
const sha = raw => createHash('sha256').update(raw).digest('hex');
const wire = value => {
    if (typeof value === 'bigint') return value.toString();
    if (Array.isArray(value)) return '[' + value.map(wire).join(',') + ']';
    if (value !== null && typeof value === 'object') return '{' + Object.keys(value).sort().map(
        key => JSON.stringify(key) + ':' + wire(value[key])).join(',') + '}';
    return JSON.stringify(value).replace(/[\x7f-\uffff]/g,
        char => '\\u' + char.charCodeAt(0).toString(16).padStart(4, '0'));
};
function fixture(role = 'windows-x64', failed = false, packet = true) {
    const windows = role === 'windows-x64';
    const id = number => [1, windows ? number.toString(16).padStart(32, '0') : number];
    const request = {schema: 'P2PKIT_PROVIDER_SUPERVISOR_REQUEST_V1', role, frequency: 1000000000,
        firstNs: '100000000000', issuedNs: '100000000000', hardEndNs: '280000000000',
        workerCutoffNs: '250000000000', phase: 'save', job: '1'.repeat(32), outerId: '2'.repeat(32),
        innerId: '3'.repeat(32), directory: windows ? 'C:\\model' : '/model', directoryIdentity: id(1),
        home: windows ? 'C:\\home' : '/home', homeIdentity: id(2),
        node: windows ? 'C:\\tools\\node.exe' : '/tools/node', toolPath: windows ? 'C:\\tools' : '/tools',
        plan: {role, model: 'NOT_AN_EXECUTABLE_PLAN'}};
    const rawRequest = Buffer.from(wire(request));
    const file = (number, size) => ({bytes: size, sha256: sha(Buffer.from('MODEL_FILE_' + number)), identity: id(number)});
    const closes = ['scope', 'retirement-writer'];
    if (!windows) closes.push('stdout-reader', 'stderr-reader');
    if (packet) closes.push('packet-reader');
    closes.push('stderr', 'stdout', 'bundle', 'capture_directory', 'home', 'directory');
    const ack = {schema: 'P2PKIT_PROVIDER_SUPERVISOR_ACK_V1', invocationSha256: sha(rawRequest),
        workerRequestSha256: 'e'.repeat(64), kind: failed ? 'failed' : 'success',
        workerExitCode: packet ? (failed ? 65 : 0) : 7, providerKind: packet ? (failed ? 'failed' : 'success') : null,
        observedNs: '210000000000', closedResources: closes,
        files: {native: file(3, 100), stdout: file(4, 0), stderr: file(5, 0), packet: packet ? file(6, 100) : null},
        enclosingNodeReturn: 'NOT_OBSERVED', originalRunnerOutcome: 'NOT_OBSERVED', providerAcceptance: 'NOT_ESTABLISHED'};
    return {request, rawRequest, ack, rawAck: Buffer.from(wire(ack) + '\n'), code: failed ? 65 : 0};
}
function feed(reducer, f, {beforeClose = () => {}} = {}) {
    reducer.onSpawn();
    reducer.onData('stdout', f.rawAck);
    reducer.onEnd('stdout');
    reducer.onEnd('stderr');
    reducer.onExit(f.code, null);
    beforeClose(reducer);
    reducer.onClose(f.code, null);
}
function rejected(f, mutate) {
    const reducer = new ReceiptReducer(f.rawRequest);
    mutate(reducer);
    assert.throws(() => reducer.finish(), ReceiptError);
    return reducer;
}
function alteredAck(change) {
    const f = fixture();
    change(f.ack, f);
    f.rawAck = Buffer.from(wire(f.ack) + '\n');
    rejected(f, reducer => feed(reducer, f));
}
for (const role of ['linux-x64', 'windows-x64', 'macos-arm64', 'macos-x64']) {
    test('supplied ' + role + ' packet remains unqualified', () => {
        const f = fixture(role), reducer = new ReceiptReducer(f.rawRequest);
        feed(reducer, f);
        const result = reducer.finish();
        assert.equal(result.scope, 'SUPPLIED_NODE_EVENT_CONSISTENCY_ONLY');
        assert.equal(result.originalChildIdentity, 'NOT_AUTHENTICATED');
        assert.equal(result.originalRawDeadline, 'NOT_OBSERVED');
        assert.equal(result.originalCancellation, 'NOT_OBSERVED');
        assert.equal(result.enclosingNodeReturn, 'NOT_OBSERVED');
        assert.equal(result.originalRunnerOutcome, 'NOT_OBSERVED');
        assert.equal(result.providerAcceptance, 'NOT_ESTABLISHED');
        assert.equal(result.acknowledgementSha256, sha(f.rawAck));
        assert.equal(result.invocationSha256, sha(f.rawRequest));
        assert(Object.isFrozen(result));
    });
}
test('failed packet transport stays failed', () => {
    const f = fixture('windows-x64', true), reducer = new ReceiptReducer(f.rawRequest);
    feed(reducer, f);
    assert.equal(reducer.finish().kind, 'failed');
});
test('opaque failed worker can have no packet', () => {
    const f = fixture('linux-x64', true, false), reducer = new ReceiptReducer(f.rawRequest);
    feed(reducer, f);
    assert.equal(reducer.finish().suppliedExitCode, 65);
});
test('stdout may end after exit but before close', () => {
    const f = fixture(), reducer = new ReceiptReducer(f.rawRequest);
    reducer.onSpawn();
    reducer.onExit(0, null);
    for (const byte of f.rawAck) reducer.onData('stdout', Buffer.from([byte]));
    reducer.onEnd('stdout'); reducer.onEnd('stderr'); reducer.onClose(0, null);
    assert.equal(reducer.finish().acknowledgementSha256, sha(f.rawAck));
});
test('copied request and event chunks cannot be rewritten by caller', () => {
    const f = fixture(), reducer = new ReceiptReducer(f.rawRequest), hash = sha(f.rawAck);
    f.rawRequest.fill(120);
    reducer.onSpawn(); reducer.onData('stdout', f.rawAck); f.rawAck.fill(120);
    reducer.onEnd('stdout'); reducer.onEnd('stderr'); reducer.onExit(0, null); reducer.onClose(0, null);
    const copy = reducer.retainedBytes(); copy.stdout.fill(121);
    assert.equal(reducer.finish().acknowledgementSha256, hash);
    assert.equal(sha(reducer.retainedBytes().stdout), hash);
});
test('bounded stderr remains private opaque data, not action commands', () => {
    const f = fixture();
    const raw = Buffer.from('MODEL_PRIVATE::error::NOT_A_RUNNER_COMMAND');
    const r = new ReceiptReducer(f.rawRequest);
    r.onSpawn(); r.onData('stderr', raw); r.onData('stdout', f.rawAck);
    r.onEnd('stdout'); r.onEnd('stderr'); r.onExit(0, null); r.onClose(0, null);
    const result = r.finish();
    assert.equal(result.stderrBytes, raw.length); assert.equal(result.stderrSha256, sha(raw));
    assert(!JSON.stringify(result).includes('MODEL_PRIVATE'));
    assert(!JSON.stringify(r).includes('MODEL_PRIVATE'));
    assert(!inspect(r).includes('MODEL_PRIVATE'));
});
test('exit without close cannot complete', () => rejected(fixture(), r => {
    const f = fixture(); r.onSpawn(); r.onData('stdout', f.rawAck);
    r.onEnd('stdout'); r.onEnd('stderr'); r.onExit(0, null);
}));
test('close without exit cannot complete', () => rejected(fixture(), r => {
    const f = fixture(); r.onSpawn(); r.onData('stdout', f.rawAck);
    r.onEnd('stdout'); r.onEnd('stderr'); r.onClose(0, null);
}));
test('close with mismatched exit cannot complete', () => rejected(fixture(), r => {
    const f = fixture(); r.onSpawn(); r.onData('stdout', f.rawAck);
    r.onEnd('stdout'); r.onEnd('stderr'); r.onExit(0, null); r.onClose(65, null);
}));
test('missing original stream EOF cannot complete', () => rejected(fixture(), r => {
    const f = fixture(); r.onSpawn(); r.onData('stdout', f.rawAck); r.onEnd('stdout');
    r.onExit(0, null); r.onClose(0, null);
}));
for (const event of ['spawn', 'exit', 'end', 'close']) {
    test('duplicate ' + event + ' is sticky failure', () => rejected(fixture(), r => {
        const f = fixture(); r.onSpawn(); if (event === 'spawn') r.onSpawn();
        r.onData('stdout', f.rawAck); r.onEnd('stdout'); r.onEnd('stderr');
        if (event === 'end') r.onEnd('stderr');
        r.onExit(0, null); if (event === 'exit') r.onExit(0, null);
        r.onClose(0, null); if (event === 'close') r.onClose(0, null);
    }));
}
for (const code of [66, 1, null, true, false, '0', undefined, -0]) {
    test('incomplete/invalid exit ' + String(code) + ' never rehabilitates ACK', () => rejected(fixture(), r => {
        const f = fixture(); r.onSpawn(); r.onData('stdout', f.rawAck);
        r.onEnd('stdout'); r.onEnd('stderr'); r.onExit(code, null); r.onClose(code, null);
    }));
}
test('signal exit cannot imply cooperative retirement', () => rejected(fixture(), r => {
    const f = fixture(); r.onSpawn(); r.onData('stdout', f.rawAck);
    r.onEnd('stdout'); r.onEnd('stderr'); r.onExit(null, 'SIGTERM'); r.onClose(null, 'SIGTERM');
}));
test('error event remains first failure through otherwise valid finish', () => {
    const f = fixture(), r = new ReceiptReducer(f.rawRequest);
    r.onError(); feed(r, f);
    let first;
    try { r.finish(); } catch (error) { first = error; }
    assert(first instanceof ReceiptError);
    assert.equal(first.message, 'NODE_RECEIPT_CHILD_ERROR');
    assert.throws(() => r.finish(), error => error === first);
});
test('finish is one use and cannot be retried after an early attempt', () => {
    const f = fixture(), r = new ReceiptReducer(f.rawRequest);
    let first;
    try { r.finish(); } catch (error) { first = error; }
    feed(r, f);
    assert.throws(() => r.finish(), error => error === first);
});
test('data before spawn fails even if later normal events arrive', () => rejected(fixture(), r => {
    r.onData('stdout', Buffer.alloc(0)); feed(r, fixture());
}));
test('data after EOF cannot be ignored', () => rejected(fixture(), r => {
    feed(r, fixture(), {beforeClose: owner => owner.onData('stdout', Buffer.from('x'))});
}));
test('truncated ACK rejects after apparently matching exit/close', () => {
    const f = fixture(); f.rawAck = f.rawAck.subarray(0, -2);
    rejected(f, r => feed(r, f));
});
test('oversized stdout rejects without retaining oversized bytes', () => {
    const f = fixture(), r = rejected(f, r => {
        r.onSpawn(); r.onData('stdout', Buffer.alloc(4097));
        r.onEnd('stdout'); r.onEnd('stderr'); r.onExit(0, null); r.onClose(0, null);
    });
    assert.equal(r.retainedBytes().stdout.length, 0);
});
test('chunk total cap is cumulative', () => {
    const f = fixture();
    const r = rejected(f, r => {
        r.onSpawn(); r.onData('stderr', Buffer.alloc(1024 * 1024)); r.onData('stderr', Buffer.from('x'));
        r.onData('stdout', f.rawAck); r.onEnd('stdout'); r.onEnd('stderr'); r.onExit(0, null); r.onClose(0, null);
    });
    assert.equal(r.retainedBytes().stderr.length, 1024 * 1024);
});
test('wrong invocation hash fails', () => alteredAck(ack => { ack.invocationSha256 = 'a'.repeat(64); }));
test('matching success-shaped ACK cannot promote failed exit', () => {
    const f = fixture(); f.code = 65; rejected(f, r => feed(r, f));
});
test('late observed RAW field fails shape, not live clock acceptance', () => alteredAck((ack, f) => {
    ack.observedNs = f.request.hardEndNs;
}));
test('early observed RAW field fails shape', () => alteredAck(ack => { ack.observedNs = '99999999999'; }));
test('forged provider acceptance is refused', () => alteredAck(ack => { ack.providerAcceptance = 'PASS'; }));
test('success packet cannot be omitted', () => alteredAck(ack => { ack.files.packet = null; }));
test('aliased file identities are rejected', () => alteredAck(ack => { ack.files.stderr.identity = ack.files.stdout.identity; }));
test('wrong native close roster is rejected', () => alteredAck(ack => { ack.closedResources.pop(); }));
test('oversized native reference is rejected', () => alteredAck(ack => { ack.files.native.bytes = 2 * 1024 * 1024 + 1; }));
test('unknown ACK field is rejected', () => alteredAck(ack => { ack.extra = true; }));
test('duplicate JSON fields cannot hide behind JSON.parse', () => {
    const f = fixture(); f.rawAck = Buffer.from(f.rawAck.toString().replace('{', '{"kind":"failed",'));
    rejected(f, r => feed(r, f));
});
test('ACK whitespace and extra newline are not canonical', () => {
    for (const prefix of [' ', '\n']) {
        const f = fixture(); f.rawAck = Buffer.concat([Buffer.from(prefix), f.rawAck]);
        rejected(f, r => feed(r, f));
    }
});
test('non-ASCII bytes never decode by silent masking', () => {
    const f = fixture(); f.rawAck[1] = 0xff; rejected(f, r => feed(r, f));
});
test('unsafe JSON integer cannot be silently rounded', () => {
    const f = fixture(); f.rawAck = Buffer.from(f.rawAck.toString().replace('"bytes":100', '"bytes":9007199254740993'));
    rejected(f, r => feed(r, f));
});
test('original request malformed/oversized/wrong-role/expired-shape refuses construction', () => {
    for (const raw of [Buffer.from('{}'), Buffer.alloc(16385), Buffer.from('{"a":1,"a":1}')]) {
        assert.throws(() => new ReceiptReducer(raw), ReceiptError);
    }
    for (const change of [request => { request.role = 'linux-arm64'; },
        request => { request.firstNs = request.hardEndNs; }, request => { request.frequency = true; }]) {
        const f = fixture(); change(f.request);
        assert.throws(() => new ReceiptReducer(Buffer.from(wire(f.request))), ReceiptError);
    }
});
test('literal model unicode path retains exact canonical ASCII spelling', () => {
    const f = fixture(); f.request.directory = 'C:\\model-\u00e9';
    f.rawRequest = Buffer.from(wire(f.request)); f.ack.invocationSha256 = sha(f.rawRequest);
    f.rawAck = Buffer.from(wire(f.ack) + '\n');
    const r = new ReceiptReducer(f.rawRequest); feed(r, f);
    assert.equal(r.finish().invocationSha256, sha(f.rawRequest));
});
test('numeric-looking nested keys retain lexical rather than JS enumeration order', () => {
    const f = fixture(); f.request.plan = {'2': 2, '10': 10};
    f.rawRequest = Buffer.from(wire(f.request)); f.ack.invocationSha256 = sha(f.rawRequest);
    f.rawAck = Buffer.from(wire(f.ack) + '\n');
    const r = new ReceiptReducer(f.rawRequest); feed(r, f);
    assert.equal(r.finish().invocationSha256, sha(f.rawRequest));
});
test('deep or negative-zero JSON cannot exhaust recursion or alias canonical integers', () => {
    const f = fixture();
    f.request.plan = {nested: JSON.parse('['.repeat(40) + '0' + ']'.repeat(40))};
    assert.throws(() => new ReceiptReducer(Buffer.from(wire(f.request))), ReceiptError);
    const other = fixture(); other.rawAck = Buffer.from(other.rawAck.toString().replace('"workerExitCode":0', '"workerExitCode":-0'));
    rejected(other, r => feed(r, other));
});
test('text or typed-array chunks are not original unencoded Buffer bytes', () => {
    for (const value of ['text', new Uint8Array([1, 2])]) {
        rejected(fixture(), r => { r.onSpawn(); r.onData('stdout', value); });
    }
});
test('empty events leave only exact private byte prefixes', () => {
    const f = fixture(), r = new ReceiptReducer(f.rawRequest);
    r.onSpawn();
    for (let index = 0; index < 1000; index++) {
        r.onData('stdout', Buffer.alloc(0)); r.onData('stderr', Buffer.alloc(0));
    }
    r.onData('stdout', f.rawAck); r.onEnd('stdout'); r.onEnd('stderr');
    r.onExit(0, null); r.onClose(0, null);
    assert.equal(r.finish().acknowledgementBytes, f.rawAck.length);
    assert.deepEqual(r.retainedBytes(), {stdout: f.rawAck, stderr: Buffer.alloc(0)});
});
test('bounded stderr fragmentation preserves all bytes without caller views', () => {
    const f = fixture(), r = new ReceiptReducer(f.rawRequest);
    const raw = Buffer.from('MODEL_OPAQUE_STDERR');
    r.onSpawn();
    for (let index = 0; index < 2048; index++) r.onData('stderr', raw);
    const expected = Buffer.concat(Array(2048).fill(raw));
    raw.fill(0);
    r.onData('stdout', f.rawAck); r.onEnd('stdout'); r.onEnd('stderr');
    r.onExit(0, null); r.onClose(0, null);
    assert.equal(r.finish().stderrSha256, sha(expected));
    assert.deepEqual(r.retainedBytes().stderr, expected);
});
test('successful finish cannot be replayed as a second completed return', () => {
    const f = fixture(), r = new ReceiptReducer(f.rawRequest);
    feed(r, f); r.finish();
    assert.throws(() => r.finish(), error => error.message === 'NODE_RECEIPT_ALREADY_FINISHED');
});
test('error after supplied close still prevents a later completed return', () => rejected(fixture(), r => {
    feed(r, fixture()); r.onError();
}));
test('unknown stream names cannot select private reducer fields', () => {
    for (const name of ['stdin', '__proto__', 'constructor']) {
        rejected(fixture(), r => { r.onSpawn(); r.onData(name, Buffer.alloc(0)); });
    }
});
test('full uint64 POSIX identities preserve adjacent values above IEEE safe range', () => {
    const f = fixture('linux-x64'), maximum = (1n << 64n) - 1n;
    f.request.directoryIdentity = [maximum, maximum];
    f.request.homeIdentity = [maximum, maximum - 1n];
    f.request.plan.exact = 9007199254740993n;
    let inode = maximum;
    for (const file of Object.values(f.ack.files)) file.identity = [maximum, inode--];
    f.rawRequest = Buffer.from(wire(f.request)); f.ack.invocationSha256 = sha(f.rawRequest);
    f.rawAck = Buffer.from(wire(f.ack) + '\n');
    const r = new ReceiptReducer(f.rawRequest); feed(r, f);
    const result = r.finish();
    assert.equal(result.invocationSha256, sha(f.rawRequest));
    assert.equal(result.acknowledgementSha256, sha(f.rawAck));
});
test('Windows wire accepts uint64 volume and positive int64 frequency without rounding', () => {
    const f = fixture();
    f.request.frequency = (1n << 63n) - 1n;
    f.request.directoryIdentity[0] = f.request.homeIdentity[0] = (1n << 64n) - 1n;
    for (const file of Object.values(f.ack.files)) file.identity[0] = (1n << 64n) - 1n;
    f.rawRequest = Buffer.from(wire(f.request)); f.ack.invocationSha256 = sha(f.rawRequest);
    f.rawAck = Buffer.from(wire(f.ack) + '\n');
    const r = new ReceiptReducer(f.rawRequest); feed(r, f);
    assert.equal(r.finish().acknowledgementSha256, sha(f.rawAck));
});
test('lossless integers still refuse unsigned overflow and invalid native frequency', () => {
    for (const change of [request => { request.directoryIdentity[0] = 1n << 64n; },
        request => { request.directoryIdentity[0] = -1; }, request => { request.frequency = 1n << 63n; }]) {
        const f = fixture(); change(f.request);
        assert.throws(() => new ReceiptReducer(Buffer.from(wire(f.request))), ReceiptError);
    }
    alteredAck(ack => { ack.files.native.identity[0] = 1n << 64n; });
});
test('missing reviver source context cannot silently choose rounded numbers', () => {
    const f = fixture(), original = JSON.parse;
    try {
        JSON.parse = (raw, revive) => original(raw, (key, value) => revive(key, value));
        assert.throws(() => new ReceiptReducer(f.rawRequest), ReceiptError);
    } finally { JSON.parse = original; }
});
test('caller Buffer getters cannot complete receipt while data is being retained', () => {
    const f = fixture(), r = new ReceiptReducer(f.rawRequest);
    const chunk = Buffer.from('MODEL_PRIVATE_BYTES');
    let calls = 0, nested;
    Object.defineProperty(chunk, 'length', {get() {
        calls++; r.onEnd('stderr'); r.onExit(0, null); r.onClose(0, null);
        nested = r.finish(); return 1;
    }});
    Object.defineProperty(chunk, 'buffer', {get() { throw new ReceiptError('MODEL_PRIVATE_GETTER'); }});
    r.onSpawn(); r.onData('stdout', f.rawAck); r.onEnd('stdout'); r.onData('stderr', chunk);
    assert.equal(calls, 0); assert.equal(nested, undefined);
    r.onEnd('stderr'); r.onExit(0, null); r.onClose(0, null);
    assert.equal(r.finish().stderrBytes, Buffer.byteLength('MODEL_PRIVATE_BYTES'));
    assert.equal(r.retainedBytes().stderr.toString(), 'MODEL_PRIVATE_BYTES');
});
test('forged Buffer length cannot hide the actual internal byte bound', () => {
    const f = fixture(), chunk = Buffer.alloc(4097);
    Object.defineProperty(chunk, 'length', {get() { return 0; }});
    const r = rejected(f, owner => { owner.onSpawn(); owner.onData('stdout', chunk); });
    assert.equal(r.retainedBytes().stdout.length, 0);
});
test('shared or proxy Buffer wrappers cannot claim original stable input bytes', () => {
    const shared = Buffer.from(new SharedArrayBuffer(1));
    const proxied = new Proxy(Buffer.from('x'), {get() { throw new ReceiptError('MODEL_PRIVATE_PROXY'); }});
    for (const chunk of [shared, proxied]) {
        const r = rejected(fixture(), owner => { owner.onSpawn(); owner.onData('stderr', chunk); });
        assert.throws(() => r.finish(), error => !error.message.includes('MODEL_PRIVATE'));
    }
});
test('foreign ReceiptError from modeled allocation is sanitized rather than class-trusted', () => {
    const f = fixture(), r = new ReceiptReducer(f.rawRequest), chunk = Buffer.from('x');
    const original = Buffer.alloc;
    r.onSpawn();
    try {
        Buffer.alloc = () => { throw new ReceiptError('MODEL_PRIVATE_FOREIGN_ERROR'); };
        r.onData('stderr', chunk);
    } finally { Buffer.alloc = original; }
    let first;
    assert.throws(() => r.finish(), error => {
        first = error;
        return error instanceof ReceiptError && error.message === 'NODE_RECEIPT_BYTE_BOUND';
    });
    assert(Object.isFrozen(first));
    assert.throws(() => { first.message = 'MODEL_PRIVATE_REWRITE'; }, TypeError);
    assert.throws(() => r.finish(), error => error === first && !error.message.includes('MODEL_PRIVATE'));
});
test('reentry during modeled allocation cannot publish a nested completed return', () => {
    const f = fixture(), r = new ReceiptReducer(f.rawRequest), chunk = Buffer.from('x');
    const original = Buffer.alloc;
    let nested, first;
    r.onSpawn(); r.onData('stdout', f.rawAck); r.onEnd('stdout');
    try {
        Buffer.alloc = size => {
            r.onEnd('stderr'); r.onExit(0, null); r.onClose(0, null);
            try { nested = r.finish(); } catch (error) { first = error; }
            return original(size);
        };
        r.onData('stderr', chunk);
    } finally { Buffer.alloc = original; }
    assert.equal(nested, undefined);
    assert(first instanceof ReceiptError);
    assert.equal(first.message, 'NODE_RECEIPT_REENTRY');
    assert.throws(() => r.finish(), error => error === first);
});

let failed = 0;
for (const item of cases) {
    try { item.run(); console.log('PASS ' + item.name); }
    catch (error) { failed++; console.error('FAIL ' + item.name + ': ' + error.message); }
}
console.log('SUPPLIED_EVENT_CONTROLS=' + cases.length + ' PASS=' + (cases.length - failed) + ' FAIL=' + failed);
if (failed) process.exitCode = 1;
