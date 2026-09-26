'use strict';
// Focused OFFLINE models only. Real byte Readables; fake original HTTP/socket
// objects and monotonic/UTC clocks. No host/credential/runner identity is spoofed
// into a production caller, and no network/native helper/old reader is run.
const assert = require('node:assert/strict');
const {EventEmitter} = require('node:events');
const {Readable} = require('node:stream');
const crypto = require('node:crypto');
const {readFileSync} = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const source = readFileSync(path.join(__dirname, '../hosted-initial-artifact-transport.cjs'), 'utf8');
const NS = 1000000000n, BLOCK = 8 * 1024 * 1024;
const cases = [], test = (name, run) => cases.push({name, run});
const tick = () => new Promise(resolve => setImmediate(resolve));
const sha = raw => crypto.createHash('sha256').update(raw).digest('hex');
const md5 = raw => crypto.createHash('md5').update(raw).digest('base64');
const SAS = 'https://p2pkitmodel.blob.core.windows.net/model/archive.zip?sv=2026-04-06&sp=cw&sig=MODEL%2bNOT%2fA%3dCREDENTIAL';
const payload = Buffer.alloc(1024, 0x51);

function model(raw = payload, config = {}) {
    const calls = [], timers = new Map(), mutations = [], module = {exports: {}};
    let now = 100n * NS, timerId = 0, resolved = false, result, started = false, producerReads = 0, offset = 0;
    class Socket extends EventEmitter {
        constructor() { super(); this.destroyed = false; this.neverClose = false; }
        destroy() {
            if (this.destroyed) return;
            this.destroyed = true;
            queueMicrotask(() => { if (!this.neverClose) this.emit('close', false); });
        }
    }
    class Incoming extends EventEmitter {
        constructor() { super(); this.complete = true; this.destroyed = false; this.neverClose = false; }
        destroy() {
            if (this.destroyed) return;
            this.destroyed = true;
            queueMicrotask(() => { if (!this.neverClose) this.emit('close'); });
        }
    }
    class Request extends EventEmitter {
        constructor(url, options) {
            super(); this.url = url; this.options = options; this.destroyed = false; this.reusedSocket = false;
            this.socket = new Socket(); this.incoming = null; this.neverClose = false; this.driven = false;
            this.kind = url.pathname.endsWith('CreateArtifact') ? 'create' :
                url.pathname.endsWith('FinalizeArtifact') ? 'finalize' : url.searchParams.get('comp');
        }
        end(body, callback) { this.body = body; this.callback = callback; }
        destroy() {
            if (this.destroyed) return;
            this.destroyed = true; this.socket.destroy();
            if (this.incoming) this.incoming.destroy();
            queueMicrotask(() => { if (!this.neverClose) this.emit('close'); });
        }
    }
    const imports = {
        'node:https': {request: (url, options) => {
            if (config.requestThrows) throw new Error('PRIVATE_MODEL_REQUEST_URL_MUST_NOT_ESCAPE');
            const request = new Request(url, options); calls.push(request);
            if (config.onRequest) config.onRequest(request, api);
            return request;
        }},
        'node:http': {ClientRequest: Request, IncomingMessage: Incoming},
        'node:tls': {TLSSocket: Socket}, 'node:stream': {Readable}, 'node:crypto': crypto,
        'node:timers': {setTimeout: (callback, ms) => {
            const id = ++timerId; timers.set(id, {callback, ms}); return id;
        }, clearTimeout: id => timers.delete(id)},
    };
    const utc = Date.parse('2026-09-26T12:34:56.789Z');
    class ClockDate extends Date {
        constructor(...args) { super(...(args.length ? args : [utc])); }
        static now() { return utc; }
    }
    const processModel = {versions: {node: '24.20.0'}, hrtime: {bigint: () => now}};
    Object.defineProperty(processModel, 'env', {get() { throw new Error('AMBIENT_ENVIRONMENT_FORBIDDEN'); }});
    vm.runInNewContext(source, {module, require: name => {
        assert(Object.hasOwn(imports, name), 'closed offline import: ' + name); return imports[name];
    }, process: processModel, Object, Reflect, JSON, Buffer, SharedArrayBuffer, AbortSignal, EventTarget,
    TextDecoder, URL, Error, Date: ClockDate}, {timeout: 1000});
    const control = new AbortController();
    const stream = config.stream || new Readable({highWaterMark: 0, read() {
        producerReads++;
        if (offset === raw.length) { this.push(null); return; }
        const end = Math.min(raw.length, offset + (config.chunkSize || BLOCK));
        const chunk = raw.subarray(offset, end); offset = end;
        if (config.asyncInput) setImmediate(() => this.push(chunk));
        else this.push(chunk);
    }});
    const jwt = {scp: 'Actions.Other Actions.Results:11111111-1111-1111-1111-111111111111:22222222-2222-2222-2222-222222222222'};
    const token = [Buffer.from('{"alg":"MODEL_ONLY"}').toString('base64url'),
        Buffer.from(JSON.stringify(jwt)).toString('base64url'), 'MODEL_NOT_A_SIGNATURE'].join('.');
    const options = {stream, artifactName: 'stage1-gate-evidence-MODEL-1-1', expectedZipBytes: raw.length,
        requestSha256: 'd'.repeat(64), startByNs: 101n * NS, workEndNs: 155n * NS, closeEndNs: 160n * NS,
        signal: control.signal, service: {ACTIONS_RUNTIME_TOKEN: token, ACTIONS_RESULTS_URL: 'https://example.invalid/'},
        maxRetentionDays: 90};
    function complete(request, change = {}) {
        request.driven = true;
        request.socket.neverClose = change.socketClose === false;
        request.neverClose = change.requestClose === false;
        request.emit('socket', request.socket);
        if (request.destroyed) return;
        if (change.endCallback !== false) request.callback(change.writeError || null);
        if (change.finish !== false) request.emit('finish');
        if (request.destroyed) return;
        const incoming = new Incoming(); request.incoming = incoming;
        incoming.neverClose = change.responseClose === false;
        incoming.statusCode = change.status === undefined ? (['create', 'finalize'].includes(request.kind) ? 200 : 201) : change.status;
        incoming.headers = {'content-md5': request.options.headers['Content-MD5'], ...change.headers};
        incoming.complete = change.complete !== false;
        request.emit('response', incoming);
        if (request.destroyed) return;
        let body = change.body;
        if (body === undefined) body = request.kind === 'create' ?
            Buffer.from(JSON.stringify({ok: true, signed_upload_url: SAS})) : request.kind === 'finalize' ?
                Buffer.from('{"ok":true,"artifact_id":"9007199254740993"}') : Buffer.alloc(0);
        if (body.length) incoming.emit('data', body);
        if (change.end !== false) incoming.emit('end');
        if (change.responseClose !== false) incoming.emit('close');
        if (change.requestClose !== false) request.emit('close');
        if (change.socketClose !== false) request.socket.emit('close', change.socketError || false);
    }
    async function drive(transform = () => ({})) {
        for (let count = 0; count < 150 && !resolved; count++) {
            await tick();
            const next = calls.find(call => !call.driven && !call.destroyed);
            if (next) complete(next, transform(next));
        }
        assert(resolved, 'model did not complete; use explicit fence/close tests for incomplete originals');
        return result;
    }
    async function until(kind) {
        for (let count = 0; count < 150; count++) {
            await tick();
            const next = calls.find(call => !call.driven && !call.destroyed);
            if (next && next.kind === kind) return next;
            if (next) complete(next);
            assert(!resolved, 'model completed before selected operation');
        }
        assert.fail('model did not reach operation');
    }
    function expire(which = 'close') {
        now = which === 'work' ? options.workEndNs : options.closeEndNs;
        const selected = [...timers.values()][which === 'work' ? 0 : 1];
        assert(selected, 'original timer exists'); selected.callback();
    }
    const api = {calls, timers, mutations, options, stream, control, complete, drive, until, expire,
        get producerReads() { return producerReads; },
        setNow: value => { now = value; }, get result() { return result; }, get resolved() { return resolved; },
        start: () => {
            assert(!started); started = true;
            const pending = module.exports.uploadOnce(options);
            pending.then(value => { result = value; resolved = true; });
            return pending;
        }, uploadOnce: module.exports.uploadOnce};
    return api;
}

function safeResult(result) {
    const raw = JSON.stringify(result);
    for (const forbidden of ['MODEL_NOT_A_SIGNATURE', 'MODEL%2b', 'example.invalid', 'PRIVATE_MODEL_', 'Authorization', 'signed_upload_url']) {
        assert(!raw.includes(forbidden), 'safe result excludes private inputs');
    }
    assert.equal(result.scope, 'INITIAL_ARTIFACT_STREAM_TRANSPORT_ONLY');
    assert.equal(result.serviceDigest, 'NOT_OBSERVED');
    assert.equal(result.actualServiceExpiry, 'NOT_OBSERVED');
    assert.equal(result.nativeFileRetirement, 'NOT_ESTABLISHED');
    assert.equal(result.originalRunnerOutcome, 'NOT_OBSERVED');
    assert.equal(result.qualification, 'NOT_ESTABLISHED');
}
function failed(m, result) {
    assert.equal(result.transport, 'incomplete'); assert(result.code.startsWith('INITIAL_ARTIFACT_'));
    assert.equal(m.timers.size, 0); safeResult(result);
}

test('exact create/block/list/finalize, wire fields, UTC14, original hash and int64 ID', async () => {
    const m = model(); m.start(); const result = await m.drive();
    assert.equal(result.transport, 'closed'); assert.equal(result.code, null);
    assert.deepEqual(m.calls.map(row => row.kind), ['create', 'block', 'blocklist', 'finalize']);
    const [create, block, list, finalize] = m.calls;
    assert.deepEqual(JSON.parse(create.body), {workflow_run_backend_id: '11111111-1111-1111-1111-111111111111',
        workflow_job_run_backend_id: '22222222-2222-2222-2222-222222222222', name: m.options.artifactName,
        version: 7, mime_type: 'application/zip', expires_at: '2026-10-10T12:34:56.789Z'});
    assert.equal(block.url.href, SAS + '&comp=block&blockid=MDAwMDAw');
    assert.equal(list.url.href, SAS + '&comp=blocklist');
    assert.equal(list.body.toString(), '<?xml version="1.0" encoding="utf-8"?><BlockList>' +
        '<Uncommitted>MDAwMDAw</Uncommitted></BlockList>');
    assert.equal(list.options.headers['If-None-Match'], '*');
    assert(!Object.hasOwn(block.options.headers, 'If-None-Match'));
    for (const row of m.calls) {
        assert.equal(row.options.agent, false); assert.equal(row.options.maxHeaderSize, 16 * 1024);
        assert.equal(row.options.rejectUnauthorized, true); assert.equal(row.options.insecureHTTPParser, false);
        assert.equal(row.options.headers.Connection, 'close');
        assert.equal(row.options.headers['Content-Length'], String(row.body.length));
        if (['create', 'finalize'].includes(row.kind)) {
            assert.equal(row.url.origin, 'https://example.invalid');
            assert.equal(row.options.headers.Authorization, 'Bearer ' + m.options.service.ACTIONS_RUNTIME_TOKEN);
        } else {
            assert(!Object.hasOwn(row.options.headers, 'Authorization'));
            assert.equal(row.options.headers['Content-MD5'], md5(row.body));
            assert.equal(row.options.headers['x-ms-version'], '2026-04-06');
            assert.equal(row.options.headers['x-ms-date'], 'Sat, 26 Sep 2026 12:34:56 GMT');
        }
    }
    assert.equal(JSON.parse(finalize.body).size, '1024');
    assert.equal(JSON.parse(finalize.body).hash, 'sha256:' + sha(payload));
    assert.equal(result.observedZipSha256, sha(payload));
    assert.equal(result.submittedFinalizeHash, 'sha256:' + sha(payload));
    assert.equal(result.artifactId, '9007199254740993');
    assert.equal(result.createInvokedAt, '2026-09-26T12:34:56.789Z');
    assert.equal(result.requestedExpiresAt, '2026-10-10T12:34:56.789Z');
    assert.equal(result.inputBytes, payload.length); assert.equal(result.sentBytes, payload.length);
    assert(result.inputEndObserved && result.inputCloseObserved);
    assert(result.requests.every(row => row.requestFinished && row.requestEndCallback && row.responseEndObserved &&
        row.requestCloseObserved && row.responseCloseObserved && row.socketCloseObserved));
    assert.equal(m.timers.size, 0); safeResult(result);
});

test('lowerCamel protobuf response spellings remain exact alternatives', async () => {
    const m = model(); m.start(); const result = await m.drive(row => row.kind === 'create' ?
        {body: Buffer.from(JSON.stringify({ok: true, signedUploadUrl: SAS}))} : row.kind === 'finalize' ?
            {body: Buffer.from('{"ok":true,"artifactId":"17"}')} : {});
    assert.equal(result.transport, 'closed'); assert.equal(result.artifactId, '17');
});

for (const asyncInput of [false, true]) test('producer backpressure, full blocks and ordered IDs; async=' + asyncInput, async () => {
    const raw = Buffer.alloc(2 * BLOCK + 1024, 0x4d), m = model(raw, {asyncInput}); m.start();
    for (let i = 0; i < 3; i++) await tick();
    assert.equal(m.producerReads, 0); assert.equal(m.stream.readableLength, 0);
    const first = await m.until('block');
    assert.equal(first.body.length, BLOCK);
    for (let i = 0; i < 3; i++) await tick();
    assert.equal(m.calls.filter(row => row.kind === 'block').length, 1);
    assert.equal(m.producerReads, 1); assert.equal(m.stream.readableLength, 0);
    assert.equal(m.stream.readableHighWaterMark, 0); assert.equal(m.stream.listenerCount('readable'), 0);
    m.complete(first); const second = await m.until('block');
    for (let i = 0; i < 3; i++) await tick();
    assert.equal(m.producerReads, 2); assert.equal(m.stream.readableLength, 0);
    m.complete(second); const result = await m.drive();
    const blocks = m.calls.filter(row => row.kind === 'block');
    assert.deepEqual(blocks.map(row => row.body.length), [BLOCK, BLOCK, 1024]);
    assert.deepEqual(blocks.map(row => row.url.searchParams.get('blockid')), ['MDAwMDAw', 'MDAwMDAx', 'MDAwMDAy']);
    assert.equal(m.producerReads, 4);
    assert.equal(result.observedZipSha256, sha(raw)); assert.equal(result.transport, 'closed');
});

test('fragmented demand assembles full blocks without reading during upload', async () => {
    const raw = Buffer.alloc(2 * BLOCK + 1024, 0x37), m = model(raw, {chunkSize: 3 * BLOCK / 4}); m.start();
    const first = await m.until('block');
    assert.equal(m.producerReads, 2); assert.equal(first.body.length, BLOCK);
    for (let i = 0; i < 3; i++) await tick();
    assert.equal(m.producerReads, 2); assert.equal(m.stream.readableLength, 0);
    m.complete(first); const result = await m.drive();
    assert.deepEqual(m.calls.filter(row => row.kind === 'block').map(row => row.body.length), [BLOCK, BLOCK, 1024]);
    assert.equal(result.transport, 'closed'); assert.equal(result.observedZipSha256, sha(raw));
});

for (const excess of ['one large chunk', 'multiple synchronous chunks', 'changed HWM']) {
    test('post-demand buffer/chunk bound refuses ' + excess + ' before any block upload', async () => {
        let reads = 0;
        const stream = new Readable({highWaterMark: 0, read() {
            reads++;
            if (excess === 'changed HWM') { this._readableState.highWaterMark = BLOCK; this.push(payload); }
            else if (excess === 'one large chunk') this.push(Buffer.alloc(BLOCK + 1));
            else { this.push(Buffer.alloc(BLOCK)); this.push(Buffer.alloc(1)); }
        }});
        const m = model(payload, {stream}); m.start(); const result = await m.drive();
        failed(m, result); assert.equal(reads, 1); assert.equal(m.calls.length, 1);
        assert.equal(result.inputBytes, 0); assert.equal(result.sentBytes, 0);
    });
}

test('mutable source chunk is owned before await and hash equals bytes actually sent', async () => {
    const raw = Buffer.alloc(1024, 0x23), expected = Buffer.from(raw), m = model(raw); m.start();
    const block = await m.until('block'); raw.fill(0x7e);
    assert.deepEqual(block.body, expected);
    m.complete(block); const result = await m.drive();
    assert.equal(result.observedZipSha256, sha(expected)); assert.notEqual(result.observedZipSha256, sha(raw));
    assert.equal(result.transport, 'closed');
});

for (const [name, change] of [
    ['extra input', o => { o.extra = true; }],
    ['accessor input', o => { Object.defineProperty(o, 'artifactName', {get() { throw new Error('NO_GETTER'); }}); }],
    ['symbol input', o => { o[Symbol('extra')] = true; }],
    ['absent retention', o => { delete o.maxRetentionDays; }],
    ['short retention', o => { o.maxRetentionDays = 13; }],
    ['retention coercion', o => { o.maxRetentionDays = '14'; }],
    ['boolean length', o => { o.expectedZipBytes = true; }],
    ['nonzero Readable HWM', o => { o.stream = new Readable({highWaterMark: 1, read() {}}); }],
    ['prebuffered stream', o => { o.stream.push(payload); }],
    ['oversize ZIP', o => { o.expectedZipBytes = 577 * 1024 * 1024; }],
    ['start equality', o => { o.startByNs = 100n * NS; }],
    ['new sixty-one', o => { o.closeEndNs += NS; o.workEndNs += NS; }],
    ['missing closing reserve', o => { o.workEndNs += 1n; }],
    ['relative numeric deadline', o => { o.closeEndNs = 60; }],
    ['fake AbortSignal', o => { o.signal = {aborted: false}; }],
    ['credentials extra', o => { o.service.GH_TOKEN = 'MODEL_FORBIDDEN'; }],
    ['URL userinfo', o => { o.service.ACTIONS_RESULTS_URL = 'https://secret@example.invalid/'; }],
    ['URL query', o => { o.service.ACTIONS_RESULTS_URL = 'https://example.invalid/?secret=MODEL'; }],
    ['URL prefix', o => { o.service.ACTIONS_RESULTS_URL = 'https://example.invalid/other/'; }],
    ['invalid token', o => { o.service.ACTIONS_RUNTIME_TOKEN = 'PRIVATE_MODEL_TOKEN'; }],
]) {
    test('refuse ' + name + ' before network/input read', () => {
        const m = model(); change(m.options);
        assert.throws(() => m.start(), /^Error: INITIAL_ARTIFACT_/);
        assert.equal(m.calls.length, 0); assert.equal(m.stream.readableDidRead, false); assert.equal(m.producerReads, 0);
    });
}

test('one module invocation has no retry entry, even after successful close', async () => {
    const m = model(); m.start(); await m.drive();
    assert.throws(() => m.uploadOnce(m.options), /ONE_INVOCATION/); assert.equal(m.calls.length, 4);
});

for (const [name, body] of [
    ['duplicate ok', '{"ok":false,"ok":true,"signed_upload_url":' + JSON.stringify(SAS) + '}'],
    ['mixed alias', JSON.stringify({ok: true, signed_upload_url: SAS, signedUploadUrl: SAS})],
    ['wrong status value', JSON.stringify({ok: 1, signed_upload_url: SAS})],
    ['extra field', JSON.stringify({ok: true, signed_upload_url: SAS, extra: true})],
    ['relative signed URL', JSON.stringify({ok: true, signed_upload_url: '/storage'})],
    ['custom signed origin', JSON.stringify({ok: true, signed_upload_url: 'https://example.invalid/blob?sig=MODEL'})],
    ['duplicate SAS key', JSON.stringify({ok: true, signed_upload_url: SAS + '&sig=OTHER'})],
    ['preselected blob operation', JSON.stringify({ok: true, signed_upload_url: SAS + '&comp=block'})],
    ['malformed JSON', '{PRIVATE_MODEL_INVALID_JSON'],
    ['oversize body', 'x'.repeat(64 * 1024 + 1)],
]) {
    test('fail closed on ' + name + ' without input/finalize', async () => {
        const m = model(); m.start(); const result = await m.drive(() => ({body: Buffer.from(body)}));
        failed(m, result); assert.equal(m.calls.length, 1); assert.equal(result.sentBytes, 0);
        assert.equal(m.producerReads, 0); assert.equal(m.stream.readableDidRead, false);
    });
}

for (const status of [301, 307, 409, 429, 500]) {
    test('HTTP' + status + ' has no redirect, retry, delete or finalize', async () => {
        const m = model(); m.start(); const result = await m.drive(() => ({status}));
        failed(m, result); assert.equal(m.calls.length, 1); assert.equal(result.artifactId, null);
        assert.equal(m.producerReads, 0); assert.equal(m.stream.readableDidRead, false);
    });
}

for (const [name, change] of [
    ['wrong MD5', {headers: {'content-md5': 'MODEL_WRONG'}}],
    ['missing MD5', {headers: {'content-md5': undefined}}],
    ['unexpected body', {body: Buffer.from('PRIVATE_MODEL_RESPONSE')}],
    ['incomplete HTTP body', {complete: false}],
    ['missing finish', {finish: false}],
    ['missing end callback', {endCallback: false}],
    ['missing response end', {end: false}],
    ['write callback error', {writeError: new Error('PRIVATE_MODEL_WRITE_ERROR')}],
    ['socket error close', {socketError: true}],
]) {
    test('failed block ' + name + ' cannot commit/finalize', async () => {
        const m = model(); m.start(); const result = await m.drive(row => row.kind === 'block' ? change : {});
        failed(m, result); assert.equal(m.calls.filter(row => row.kind === 'blocklist' || row.kind === 'finalize').length, 0);
    });
}

test('existing committed blob412 never triggers overwrite/retry/finalize', async () => {
    const m = model(); m.start(); const result = await m.drive(row => row.kind === 'blocklist' ? {status: 412} : {});
    failed(m, result); assert.equal(m.calls.length, 3);
});

for (const id of ['0', '-1', '01', '9223372036854775808', 17, true]) {
    test('refuse noncanonical artifact ID ' + JSON.stringify(id), async () => {
        const m = model(); m.start(); const result = await m.drive(row => row.kind === 'finalize' ?
            {body: Buffer.from(JSON.stringify({ok: true, artifact_id: id}))} : {});
        failed(m, result); assert.equal(result.artifactId, null); assert.equal(m.calls.length, 4);
    });
}

test('short declared input cannot commit its otherwise successful block', async () => {
    const m = model(); m.options.expectedZipBytes += 1; m.start(); const result = await m.drive();
    failed(m, result); assert(!m.calls.some(row => row.kind === 'blocklist'));
});
test('input overrun stops before sending the excessive original block', async () => {
    const m = model(); m.options.expectedZipBytes -= 1; m.start(); const result = await m.drive();
    failed(m, result); assert.equal(m.calls.length, 1);
});
test('source stream failure never becomes empty/successful EOF', async () => {
    const stream = new Readable({highWaterMark: 0, read() { this.destroy(new Error('PRIVATE_MODEL_INPUT_ERROR')); }});
    const m = model(payload, {stream}); m.start(); const result = await m.drive();
    failed(m, result); assert.equal(m.calls.length, 1);
});
test('shared-memory input is never borrowed for hashing or transfer', async () => {
    const raw = Buffer.from(new SharedArrayBuffer(1024)), m = model(raw); m.start(); const result = await m.drive();
    failed(m, result); assert.equal(m.calls.length, 1);
});
test('already consumed stream is refused before service creation', () => {
    const m = model(); m.stream.read(1);
    assert.throws(() => m.start(), /ORIGINAL_BYTE_STREAM/); assert.equal(m.calls.length, 0);
    m.stream.destroy();
});
test('object-mode stream cannot impersonate bytes', () => {
    const m = model(payload, {stream: new Readable({objectMode: true, read() {}})});
    assert.throws(() => m.start(), /ORIGINAL_BYTE_STREAM/); assert.equal(m.calls.length, 0);
});

test('cancelled before entry has no network or owned input effects', () => {
    const m = model(); m.control.abort();
    assert.throws(() => m.start(), /CANCELLED/); assert.equal(m.calls.length, 0);
});
test('cancellation during an original block destroys only original objects once', async () => {
    const m = model(); m.start(); const block = await m.until('block');
    // No response has been received; associate the actual original socket first.
    block.driven = true; block.emit('socket', block.socket);
    m.control.abort(); m.control.abort();
    for (let i = 0; i < 10 && !m.resolved; i++) await tick();
    assert(m.resolved); failed(m, m.result); assert.equal(m.calls.length, 2);
});
test('request creation crossing exact start fence is retained failure before send', async () => {
    const m = model(payload, {onRequest: (_row, api) => api.setNow(api.options.startByNs)});
    m.start(); const result = await m.drive();
    failed(m, result); assert.equal(result.code, 'INITIAL_ARTIFACT_START_DEADLINE');
    assert.equal(m.calls.length, 1); assert.equal(m.calls[0].body, undefined);
});
test('private request-construction exception never escapes result', async () => {
    const m = model(payload, {requestThrows: true}); m.start(); await tick();
    // A throwing factory gave no original request handle: do not invent close.
    assert(!m.resolved); m.expire('close'); await tick();
    failed(m, m.result); assert.equal(m.result.code, 'INITIAL_ARTIFACT_OPERATION_FAILED');
});

for (const missing of ['requestClose', 'responseClose', 'socketClose']) {
    test('missing ' + missing + ' stays incomplete/unknown at original close fence', async () => {
        const m = model(); m.start(); const row = await m.until('block');
        m.complete(row, {[missing]: false}); await tick();
        m.expire('close'); await tick();
        assert(m.resolved); failed(m, m.result);
        assert.equal(m.result.requests.at(-1)[missing === 'socketClose' ? 'socketCloseObserved' :
            missing === 'responseClose' ? 'responseCloseObserved' : 'requestCloseObserved'], false);
        assert(!m.calls.some(call => call.kind === 'blocklist' || call.kind === 'finalize'));
    });
}
test('EOF without original stream close cannot commit the block list', async () => {
    const stream = new Readable({highWaterMark: 0, autoDestroy: false, emitClose: false,
        read() { this.push(payload); this.push(null); }});
    const m = model(payload, {stream}); m.start();
    const block = await m.until('block'); m.complete(block); await tick();
    assert(!m.resolved); m.expire('close'); await tick();
    failed(m, m.result); assert.equal(m.result.inputCloseObserved, false); assert.equal(m.calls.length, 2);
});
test('work equality stops body completion and cannot finalize', async () => {
    const m = model(); m.start(); const block = await m.until('block');
    m.setNow(m.options.workEndNs); m.complete(block); await tick();
    failed(m, m.result); assert(!m.calls.some(row => row.kind === 'finalize'));
});
test('last five seconds permit only known final close after all body work', async () => {
    const m = model(); m.start(); const final = await m.until('finalize');
    m.complete(final, {requestClose: false, responseClose: false, socketClose: false});
    m.expire('work'); assert(!m.resolved);
    m.setNow(m.options.workEndNs + NS);
    final.incoming.emit('close'); final.emit('close'); final.socket.emit('close', false);
    await tick(); assert.equal(m.result.transport, 'closed'); safeResult(m.result);
});
test('close equality after successful finalize response still cannot turn green', async () => {
    const m = model(); m.start(); const final = await m.until('finalize');
    m.complete(final, {requestClose: false, responseClose: false, socketClose: false});
    m.setNow(m.options.closeEndNs);
    final.incoming.emit('close'); final.emit('close'); final.socket.emit('close', false);
    await tick(); failed(m, m.result);
});

(async () => {
    let passed = 0;
    for (const {name, run} of cases) {
        try { await run(); passed++; process.stdout.write('PASS ' + name + '\n'); }
        catch (error) {
            // Only model inputs exist; still keep failure output to fixed names.
            process.stderr.write('FAIL ' + name + ': ' + error.name + '\n');
            process.stderr.write('completed=' + passed + ' total=' + cases.length + '\n');
            process.exitCode = 1; return;
        }
    }
    process.stdout.write('PASS ' + passed + '/' + cases.length + ' offline transport models; NOT provider/native qualification\n');
})().catch(() => { process.stderr.write('MODEL_RUNNER_FAILED\n'); process.exitCode = 1; });
