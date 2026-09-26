'use strict';
// New offline original-HTTP/clock models only. No real HTTPS, Node Agent,
// native process/file ownership, credentials, service Step proof or old suite.
const assert = require('node:assert/strict');
const {EventEmitter} = require('node:events');
const crypto = require('node:crypto');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const source = fs.readFileSync(path.join(__dirname, '../hosted-initial-artifact-observer.cjs'), 'utf8');
const NS = 1000000000n, DATE = 'Sat, 26 Sep 2026 12:00:00 GMT', cases = [];
const test = (name, run) => cases.push({name, run});
const tick = () => new Promise(resolve => setImmediate(resolve));
const sha = raw => crypto.createHash('sha256').update(raw).digest('hex');
function headers(bytes) {
    return ['Date', DATE, 'Content-Type', 'application/json; charset=utf-8',
        'X-GitHub-Api-Version-Selected', '2022-11-28', 'X-GitHub-Request-Id', 'MODELREQ:1234',
        'Cache-Control', 'public, max-age=60, s-maxage=60', 'Content-Length', String(bytes),
        'X-Model-Private', 'MODEL_PRIVATE_HEADER'];
}
function header(vector, name, value) {
    const result = [];
    for (let index = 0; index < vector.length; index += 2) {
        if (vector[index].toLowerCase() !== name.toLowerCase()) result.push(vector[index], vector[index + 1]);
    }
    if (value !== null) result.push(name, value);
    return result;
}
function model(config = {}) {
    const requests = [], agents = [], timers = new Map(), module = {exports: {}}, control = new AbortController();
    const raw = Buffer.from('{"scope":"MODEL_PRIVATE_BODY_NOT_STEP_AUTHORITY"}', 'utf8');
    let now = 100n * NS, timerId = 0, handle;
    class Agent {
        constructor(options) { this.options = options; this.destroyCalls = 0; agents.push(this); }
        destroy() {
            this.destroyCalls++;
            if (config.agentDestroyError) throw new Error('MODEL_PRIVATE_AGENT_ERROR');
            if (config.agentDestroyNow !== undefined) now = config.agentDestroyNow;
        }
    }
    class Socket extends EventEmitter {
        constructor() {
            super(); this.destroyed = false; this.destroyCalls = 0; this.encrypted = true;
            this.authorized = true; this.authorizationError = null; this.servername = 'api.github.com';
            Object.assign(this, config.socket || {});
        }
        destroy() { this.destroyCalls++; this.destroyed = true; }
    }
    class Incoming extends EventEmitter {
        constructor(request) {
            super(); this.req = request; this.socket = request.socket; this.statusCode = 200; this.httpVersion = '1.1';
            this.rawHeaders = headers(raw.length); this.rawTrailers = []; this.trailers = {};
            this.readableObjectMode = false; this.readableEncoding = null; this.complete = false;
            this.destroyed = false; this.destroyCalls = 0;
        }
        destroy() { this.destroyCalls++; this.destroyed = true; }
    }
    class Request extends EventEmitter {
        constructor(options) {
            super(); this.options = options; this.reusedSocket = config.reusedSocket === true;
            this.destroyed = false; this.destroyCalls = 0; this.endCalls = 0; this.endCallback = null;
            this.socket = null; this.incoming = null; this.timeoutMs = null;
        }
        setTimeout(ms) { this.timeoutMs = ms; }
        end(callback) {
            assert.equal(typeof callback, 'function'); this.endCalls++; this.endCallback = callback;
            if (!config.holdFinish) queueMicrotask(() => this.emit('finish'));
            if (!config.holdEndCallback) queueMicrotask(() => callback());
        }
        destroy() { this.destroyCalls++; this.destroyed = true; }
    }
    const imports = {'node:https': {Agent, request(options) {
        const request = new Request(options); requests.push(request);
        queueMicrotask(() => {
            if (config.noSocket) return;
            request.socket = new Socket(); request.emit('socket', request.socket);
            if (!config.noSecureConnect) request.socket.emit('secureConnect');
        });
        return request;
    }}, 'node:http': {ClientRequest: Request, IncomingMessage: Incoming}, 'node:tls': {TLSSocket: Socket},
    'node:crypto': crypto, 'node:timers': {setTimeout(callback, ms) {
        const id = ++timerId; timers.set(id, {callback, ms, at: now + BigInt(ms) * 1000000n}); return id;
    }, clearTimeout(id) { timers.delete(id); }}};
    vm.runInNewContext(source, {module, require: name => {
        assert(Object.hasOwn(imports, name), 'closed offline import ' + name); return imports[name];
    }, process: {versions: {node: config.node || '24.20.0'}, hrtime: {bigint: () => now}},
    Object, Reflect, JSON, Number, Date, Buffer, SharedArrayBuffer, AbortSignal, EventTarget, Error, WeakMap, WeakSet},
    {timeout: 1000});
    const stage = config.stage || 'before';
    const options = stage === 'before' ? {jobId: '123', requestSha256: 'a'.repeat(64),
        preSpawnLocalNs: 100n * NS, startByNs: 130n * NS, workEndNs: 155n * NS, closeEndNs: 160n * NS,
        signal: control.signal} : {jobId: '123', artifactId: '456', requestSha256: 'a'.repeat(64),
        preSpawnLocalNs: 100n * NS, endNs: 115n * NS, signal: control.signal};
    function call(supplied = options) { return module.exports[stage + 'Once'](supplied); }
    async function start() { handle = call(); await tick(); return handle; }
    function incoming(index = 0, props = {}) {
        const request = requests[index], value = new Incoming(request);
        Object.assign(value, props); request.incoming = value; request.emit('response', value); return value;
    }
    async function respond(index = 0, options = {}) {
        const body = options.body === undefined ? raw : options.body;
        const value = incoming(index, {rawHeaders: options.headers || headers(body.length), ...(options.props || {})});
        for (const chunk of options.chunks || (body.length ? [body] : [])) value.emit('data', chunk);
        value.complete = options.complete !== false; value.emit('end'); await tick(); return value;
    }
    async function close(index = 0, flags = {}) {
        const request = requests[index];
        if (flags.response !== false && request.incoming) request.incoming.emit('close');
        if (flags.request !== false) request.emit('close');
        if (flags.socket !== false && request.socket) request.socket.emit('close', flags.socketError === true);
        await tick();
    }
    async function expire() {
        now = stage === 'before' ? options.closeEndNs : options.endNs;
        for (const entry of [...timers.values()].sort((left, right) => Number(left.at - right.at))) entry.callback();
        await tick(); return handle.completion;
    }
    return {module, options, requests, agents, timers, control, raw, Socket, Incoming,
        call, start, incoming, respond, close, expire, setNow: value => { now = value; },
        get handle() { return handle; }};
}
function safe(result) {
    assert.equal(result.qualification, 'NOT_ESTABLISHED');
    assert.equal(result.originalStepOutcome, 'NOT_OBSERVED');
    for (const text of ['MODEL_PRIVATE_BODY', 'MODEL_PRIVATE_HEADER', 'MODEL_PRIVATE_ERROR',
        'MODEL_PRIVATE_AGENT_ERROR', 'Authorization', 'Bearer ', 'https://']) {
        assert(!JSON.stringify(result).includes(text), 'safe summary excludes ' + text);
    }
}
async function failed(m) {
    const result = await m.expire();
    assert.equal(result.transport, 'incomplete');
    assert(result.code.startsWith('INITIAL_ARTIFACT_OBSERVER_')); safe(result);
    assert.throws(() => m.handle.originals()); return result;
}
async function positive(m) {
    await m.respond(); await m.close();
    if (m.options.artifactId !== undefined) { await m.respond(1); await m.close(1); }
    const result = await m.handle.completion;
    assert.equal(result.transport, 'closed'); assert.equal(result.code, null); safe(result); return result;
}

test('BEFORE owns one fixed GET, fresh explicitly no-proxy Agent and private original copies', async () => {
    const m = model(); await m.start(); assert.throws(() => m.handle.originals());
    assert.equal(m.agents.length, 1); const agent = m.agents[0], request = m.requests[0];
    assert.equal(agent.options.keepAlive, false); assert.equal(agent.options.maxSockets, 1);
    assert.equal(agent.options.maxTotalSockets, 1); assert.deepEqual(Object.keys(agent.options.proxyEnv), []);
    assert.equal(request.options.agent, agent); assert.equal(request.options.hostname, 'api.github.com');
    assert.equal(request.options.servername, 'api.github.com'); assert.equal(request.options.port, 443);
    assert.equal(request.options.path, '/repos/p2pKit/P2pKit/actions/jobs/123');
    assert.equal(request.options.protocol, 'https:'); assert.equal(request.options.method, 'GET');
    assert.equal(request.options.rejectUnauthorized, true); assert.equal(request.options.insecureHTTPParser, false);
    assert.equal(request.options.maxHeaderSize, 16384); assert.equal(request.endCalls, 1);
    assert(!Object.hasOwn(request.options, 'auth')); assert(!Object.hasOwn(request.options, 'lookup'));
    assert(!Object.hasOwn(request.options, 'checkServerIdentity'));
    assert.deepEqual(Object.keys(request.options.headers).sort(),
        ['Accept', 'Accept-Encoding', 'Cache-Control', 'Connection', 'Pragma', 'User-Agent', 'X-GitHub-Api-Version'].sort());
    const result = await positive(m);
    assert.equal(m.requests.length, 1); assert.equal(agent.destroyCalls, 1); assert.equal(result.originalResourceCount, 3);
    assert.equal(result.requests[0].bodySha256, sha(m.raw)); assert.equal(result.requests[0].date, DATE);
    const originals = m.handle.originals(); assert.equal(originals[0].kind, 'job'); assert.equal(originals[0].id, '123');
    assert.deepEqual(originals[0].body, m.raw);
    assert.equal(result.requests[0].rawHeaderVectorSha256,
        sha(Buffer.from(JSON.stringify(originals[0].rawHeaderVector), 'utf8')));
    originals[0].body.fill(0); assert.deepEqual(m.handle.originals()[0].body, m.raw);
    assert.throws(() => { originals[0].rawHeaderVector[0] = 'Changed'; });
});
test('AFTER is jobs then exact artifact, only after all original first-request closes', async () => {
    const m = model({stage: 'after'}); await m.start(); await m.respond(); await m.close(0, {socket: false});
    assert.equal(m.requests.length, 1); assert.throws(() => m.handle.originals());
    m.requests[0].socket.emit('close', false); await tick();
    assert.equal(m.requests.length, 2);
    assert.equal(m.requests[1].options.path, '/repos/p2pKit/P2pKit/actions/artifacts/456');
    assert.notEqual(m.requests[0].socket, m.requests[1].socket);
    await m.respond(1); await m.close(1);
    const result = await m.handle.completion;
    assert.equal(result.transport, 'closed'); assert.equal(result.originalResourceCount, 6);
    assert.equal(m.agents.length, 1); assert.equal(m.agents[0].destroyCalls, 1);
    assert.equal(result.requests.map(row => row.kind).join(','), 'job,artifact'); safe(result);
});
test('captured ids, hashes and absolute bounds do not follow caller mutation', async () => {
    const m = model(); await m.start(); m.options.jobId = '999'; m.options.requestSha256 = 'b'.repeat(64);
    m.options.closeEndNs += 100n * NS; const result = await positive(m);
    assert.equal(result.jobId, '123'); assert.equal(result.requestSha256, 'a'.repeat(64));
    assert.equal(result.requests[0].endNs, (115n * NS).toString());
});
test('canonical positive64 ids, binding hashes and mode-specific exact DATA are mandatory', async () => {
    for (const change of [{jobId: 123}, {jobId: '0'}, {jobId: '01'}, {jobId: '../123'},
        {jobId: '9223372036854775808'}, {requestSha256: 'x'.repeat(64)}, {artifactId: '456'},
        {url: 'https://not.example/'}, {token: 'MODEL_PRIVATE_ERROR'}, {backend: () => {}}]) {
        const m = model(); assert.throws(() => m.call({...m.options, ...change}));
        assert.equal(m.agents.length, 0); assert.equal(m.requests.length, 0);
    }
    for (const value of [456, '0', '01', '9223372036854775808']) {
        const m = model({stage: 'after'}); assert.throws(() => m.call({...m.options, artifactId: value}));
        assert.equal(m.agents.length, 0);
    }
});
test('accessors, nonplain inputs, non-Node24 and unbranded or already-aborted signals refuse', async () => {
    const m = model(); let read = false;
    const options = {...m.options}; Object.defineProperty(options, 'jobId', {enumerable: true, get() { read = true; return '123'; }});
    assert.throws(() => m.call(options)); assert.equal(read, false); assert.equal(m.agents.length, 0);
    for (const config of [{node: '22.20.0'}, {}]) {
        const n = model(config); assert.throws(() => n.call({...n.options, signal: {aborted: false}}));
        assert.equal(n.agents.length, 0);
    }
    const n = model(); n.control.abort(); assert.throws(() => n.call()); assert.equal(n.agents.length, 0);
    const p = model(); assert.throws(() => p.call(Object.assign(Object.create(null), p.options)));
});
test('BEFORE keeps original U60, strict startBy/work and unchanged five-second tail', async () => {
    for (const change of [{preSpawnLocalNs: 101n * NS}, {preSpawnLocalNs: 99n * NS},
        {startByNs: 100n * NS}, {startByNs: 155n * NS}, {workEndNs: 154n * NS},
        {closeEndNs: 161n * NS, workEndNs: 156n * NS}, {startByNs: 100000000001}, {closeEndNs: -1n}]) {
        const m = model(); assert.throws(() => m.call({...m.options, ...change})); assert.equal(m.requests.length, 0);
    }
});
test('AFTER uses the original pre-spawn15 cap, not a renewed observer allowance', async () => {
    for (const change of [{preSpawnLocalNs: 99n * NS}, {preSpawnLocalNs: 101n * NS},
        {endNs: 116n * NS}, {endNs: 100n * NS}, {endNs: 115000000000}]) {
        const m = model({stage: 'after'}); assert.throws(() => m.call({...m.options, ...change}));
        assert.equal(m.requests.length, 0);
    }
});
test('each request has HTTP15 clipped by BEFORE startBy and socket inactivity5', async () => {
    const m = model(); await m.start(); assert.equal(m.requests[0].timeoutMs, 5000);
    assert([...m.timers.values()].some(row => row.at === 115n * NS));
    m.handle.cancel(); await failed(m);
    const n = model(); n.options.startByNs = 102n * NS; await n.start();
    assert.equal(n.requests[0].timeoutMs, 2000); assert([...n.timers.values()].some(row => row.at === 102n * NS));
    n.handle.cancel(); await failed(n);
});
test('BEFORE full original close at startBy is too late even when body completed earlier', async () => {
    const m = model(); m.options.startByNs = 102n * NS; await m.start(); await m.respond();
    m.setNow(102n * NS); await m.close(); await failed(m); assert.equal(m.requests.length, 1);
});
test('AFTER second request still ends at the first original15, not request2 plus15', async () => {
    const m = model({stage: 'after'}); await m.start(); m.setNow(114n * NS); await m.respond(); await m.close();
    assert.equal(m.requests.length, 2); assert.equal(m.requests[1].timeoutMs, 1000);
    await m.respond(1); m.setNow(115n * NS); await m.close(1);
    const result = await failed(m); assert.equal(result.requests[1].endNs, (115n * NS).toString());
});
test('backward and expired LOCAL observations irreversibly fail', async () => {
    for (const now of [99n * NS, 115n * NS, -1n]) {
        const m = model(); await m.start(); m.setNow(now); await m.respond(); m.setNow(100n * NS);
        await failed(m);
    }
});
test('complete original HTTP close joins a delayed successful request end callback', async () => {
    const m = model({holdEndCallback: true}); await m.start(); await m.respond(); await m.close();
    assert.throws(() => m.handle.originals()); assert.equal(m.agents[0].destroyCalls, 0);
    m.requests[0].endCallback(); await tick();
    const result = await m.handle.completion; assert.equal(result.transport, 'closed');
    assert.equal(result.requests[0].requestEndCallbackObserved, true); safe(result);
});
test('complete original HTTP close also requires original request finish, not just its callback', async () => {
    const m = model({holdFinish: true}); await m.start(); await m.respond(); await m.close();
    assert.throws(() => m.handle.originals()); m.requests[0].emit('finish'); await tick();
    assert.equal((await m.handle.completion).transport, 'closed');
});
test('failed delayed request callback cannot be repaired by complete body and every close', async () => {
    const m = model({holdEndCallback: true}); await m.start(); await m.respond(); await m.close();
    m.requests[0].endCallback(new Error('MODEL_PRIVATE_ERROR')); await tick(); await failed(m);
});
test('missing request, response or TLS close never provides private originals or a second request', async () => {
    for (const kind of ['request', 'response', 'socket']) {
        const m = model({stage: 'after'}); await m.start(); await m.respond(); await m.close(0, {[kind]: false});
        assert.equal(m.requests.length, 1); assert.throws(() => m.handle.originals()); await failed(m);
    }
});
test('wrong TLS host, authorization, encryption and reused sockets fail without fallback', async () => {
    for (const config of [{socket: {servername: 'not.example'}}, {socket: {authorized: false}},
        {socket: {encrypted: false}}, {socket: {authorizationError: 'MODEL_PRIVATE_ERROR'}}, {reusedSocket: true}]) {
        const m = model(config); await m.start(); await failed(m); assert.equal(m.requests.length, 1);
    }
});
test('missing or duplicate original secureConnect is not a verified TLS response', async () => {
    const m = model({noSecureConnect: true}); await m.start(); await m.respond(); await failed(m);
    const n = model(); await n.start(); n.requests[0].socket.emit('secureConnect'); await failed(n);
});
test('response must belong to the original request and TLS socket and remain a byte stream', async () => {
    for (const props of [{req: {}}, {readableObjectMode: true}, {readableEncoding: 'utf8'}, {httpVersion: '2.0'}]) {
        const m = model(); await m.start(); await m.respond(0, {props}); await failed(m);
    }
    const m = model(); await m.start(); const foreign = new m.Socket();
    await m.respond(0, {props: {socket: foreign}}); await failed(m); assert.equal(foreign.destroyCalls, 1);
});
test('HTTP status errors are terminal: no redirect,304,partial,quota or server retry', async () => {
    for (const statusCode of [301, 302, 304, 401, 403, 404, 206, 429, 500]) {
        const m = model({stage: 'after'}); await m.start(); await m.respond(0, {props: {statusCode}});
        await failed(m); assert.equal(m.requests.length, 1);
    }
});
test('public JSON/API/request-ID and identity encoding are strict, including empty present headers', async () => {
    for (const [key, value] of [['Content-Type', null], ['Content-Type', 'text/html'],
        ['Content-Encoding', 'gzip'], ['Content-Encoding', ''], ['X-GitHub-Api-Version-Selected', 'wrong'],
        ['X-GitHub-Request-Id', null], ['X-GitHub-Request-Id', 'short'], ['X-Cache', '']]) {
        const m = model(); await m.start(); await m.respond(0, {headers: header(headers(m.raw.length), key, value)});
        await failed(m);
    }
});
test('public cache policy is distinct, exact and never a private-response fallback', async () => {
    for (const value of [null, 'private, max-age=60, s-maxage=60', 'public, max-age=60',
        'public, max-age=61, s-maxage=60', 'public, max-age=60, s-maxage=60, public',
        'public, max-age=60, s-maxage=60, no-cache', 'public=1,max-age=60,s-maxage=60']) {
        const m = model(); await m.start();
        await m.respond(0, {headers: header(headers(m.raw.length), 'Cache-Control', value)}); await failed(m);
    }
});
test('public cache order/normal whitespace and absent optional identity/cache indicators are supported', async () => {
    const m = model(); await m.start();
    await m.respond(0, {headers: header(headers(m.raw.length), 'Cache-Control', ' s-maxage=60, public , max-age=60 ')});
    await m.close(); assert.equal((await m.handle.completion).transport, 'closed');
});
test('aged, hit and intermediary fields cannot turn a stale response into an original', async () => {
    for (const [key, value] of [['Age', '1'], ['Age', '00'], ['Warning', '110 stale'], ['Via', 'proxy'],
        ['Location', 'https://not.example'], ['Content-Range', 'bytes 0-1/2'], ['Retry-After', '0'], ['X-Cache', 'HIT']]) {
        const m = model(); await m.start(); await m.respond(0, {headers: header(headers(m.raw.length), key, value)});
        await failed(m);
    }
});
test('canonical positive IMF Date must round-trip, including the actual weekday', async () => {
    for (const value of [null, '', 'Sat, 26 Sep 2026 12:00:00 UTC', 'Fri, 26 Sep 2026 12:00:00 GMT',
        'Sat, 26 Sep 2026 24:00:00 GMT', 'Sun, 31 Feb 2026 12:00:00 GMT', 'Thu, 01 Jan 1970 00:00:00 GMT']) {
        const m = model(); await m.start(); await m.respond(0, {headers: header(headers(m.raw.length), 'Date', value)});
        await failed(m);
    }
});
test('duplicate, malformed, non-ASCII and over-bound original header vectors refuse', async () => {
    const variants = [value => [...value, 'date', DATE], value => [...value, 'bad name', 'x'],
        value => [...value, 'X-Bad', '\n'], value => [...value, 'X-Bad', '\u0080'],
        value => [...value, 'X-Large', 'x'.repeat(2048)], value => [...value, 'odd'],
        value => [...value, ...Array.from({length: 65}, (_, i) => ['X-' + i, 'v']).flat()],
        value => [...value, ...Array.from({length: 9}, (_, i) => ['X-' + i, 'x'.repeat(2000)]).flat()]];
    for (const alter of variants) {
        const m = model(); await m.start(); await m.respond(0, {headers: alter(headers(m.raw.length))}); await failed(m);
    }
});
test('Content-Length and transfer encoding preserve exact bounded body completeness', async () => {
    for (const [key, value] of [['Content-Length', '0'], ['Content-Length', '-1'], ['Content-Length', '1048577'],
        ['Content-Length', 'wrong'], ['Transfer-Encoding', 'chunked'], ['Transfer-Encoding', 'gzip']]) {
        const m = model(); await m.start(); await m.respond(0, {headers: header(headers(m.raw.length), key, value)});
        await failed(m);
    }
    const n = model(); await n.start();
    await n.respond(0, {headers: header(header(headers(n.raw.length), 'Content-Length', null), 'Transfer-Encoding', 'gzip')});
    await failed(n); // Independently reject bad transfer coding without a Content-Length conflict.
    const m = model(); await m.start();
    await m.respond(0, {headers: header(header(headers(m.raw.length), 'Content-Length', null), 'Transfer-Encoding', 'chunked')});
    await m.close(); assert.equal((await m.handle.completion).transport, 'closed');
});
test('empty, short, oversized and incomplete bodies cannot satisfy original EOF', async () => {
    for (const options of [{body: Buffer.alloc(0)}, {complete: false},
        {chunks: [Buffer.from('x')]}, {chunks: [Buffer.alloc(1024 * 1024 + 1)]}]) {
        const m = model(); await m.start(); await m.respond(0, options); await failed(m);
    }
    const m = model(); await m.start();
    await m.respond(0, {headers: header(headers(m.raw.length), 'Content-Length', null),
        chunks: [Buffer.alloc(1024 * 1024 + 1)]});
    await failed(m); // The global cap applies without any declared length.
});
test('exact one-MiB body is allowed and actual copied chunk bytes determine its hash', async () => {
    const m = model(); await m.start(); const body = Buffer.alloc(1024 * 1024, 120);
    await m.respond(0, {body, chunks: [body.subarray(0, 65536), body.subarray(65536)]}); await m.close();
    const result = await m.handle.completion;
    assert.equal(result.transport, 'closed'); assert.equal(result.requests[0].bodyBytes, body.length);
    assert.equal(result.requests[0].bodySha256, sha(body));
});
test('non-byte/shared/empty chunks and response trailers refuse without semantic parsing', async () => {
    for (const options of [{chunks: ['not bytes']}, {chunks: [Buffer.alloc(0)]},
        {chunks: [Buffer.from(new SharedArrayBuffer(4))]}, {props: {rawTrailers: ['X-Tail', 'x']}},
        {props: {trailers: {'x-tail': ''}}}]) {
        const m = model(); await m.start(); await m.respond(0, options); await failed(m);
    }
});
test('retained body and header originals do not alias mutable incoming DATA', async () => {
    const m = model(); await m.start(); const incoming = m.incoming(), body = Buffer.from(m.raw);
    incoming.emit('data', body); body.fill(0); incoming.rawHeaders[1] = 'changed after observation';
    incoming.complete = true; incoming.emit('end'); await m.close();
    const result = await m.handle.completion; assert.equal(result.transport, 'closed');
    assert.equal(result.requests[0].bodySha256, sha(m.raw)); assert.equal(result.requests[0].date, DATE);
    assert.deepEqual(m.handle.originals()[0].body, m.raw);
});
test('original response aborted or native error stays failed and never exposes private diagnostics', async () => {
    const m = model(); await m.start(); const incoming = m.incoming(); incoming.emit('aborted'); await failed(m);
    const n = model(); await n.start(); n.requests[0].emit('error', new Error('MODEL_PRIVATE_ERROR')); await failed(n);
});
test('socket error-close and duplicate request callback/finish/close cannot be repaired later', async () => {
    const m = model(); await m.start(); await m.respond(); await m.close(0, {socketError: true}); await failed(m);
    for (const action of [request => request.endCallback(), request => request.emit('finish'),
        request => { request.emit('close'); request.emit('close'); }]) {
        const n = model(); await n.start(); action(n.requests[0]); await failed(n);
    }
});
test('duplicate socket/response retains every returned original for bounded failure', async () => {
    const m = model(); await m.start(); const extra = new m.Socket(); m.requests[0].emit('socket', extra);
    const result = await failed(m); assert.equal(result.originalResourceCount, 3); assert.equal(extra.destroyCalls, 1);
    const n = model(); await n.start(); n.incoming(); const incoming = n.incoming();
    const other = await failed(n); assert.equal(other.originalResourceCount, 4); assert.equal(incoming.destroyCalls, 1);
});
test('unexpected informational/upgrade protocol cannot silently become the fixed GET', async () => {
    const m = model(); await m.start(); m.requests[0].emit('information', {statusCode: 103}); await failed(m);
    const n = model(); await n.start(); const incoming = new n.Incoming(n.requests[0]);
    n.requests[0].emit('upgrade', incoming, n.requests[0].socket, Buffer.from('MODEL_PRIVATE_ERROR'));
    const result = await failed(n); assert.equal(result.originalResourceCount, 3); assert.equal(incoming.destroyCalls, 1);
});
test('abort before first close forbids AFTER request2 and only cancels retained originals once', async () => {
    const m = model({stage: 'after'}); await m.start(); await m.respond(); m.control.abort(); m.handle.cancel();
    await m.close(); const result = await failed(m); assert.equal(m.requests.length, 1);
    assert.equal(m.agents[0].destroyCalls, 1); assert(m.requests[0].destroyCalls <= 1);
    assert(m.requests[0].socket.destroyCalls <= 1); assert(m.requests[0].incoming.destroyCalls <= 1); safe(result);
});
test('socket inactivity and missing original handles remain bounded failure, not synthetic close', async () => {
    const m = model(); await m.start(); m.requests[0].emit('timeout'); await failed(m);
    const n = model({noSocket: true}); await n.start();
    const result = await failed(n); assert.equal(result.requests[0].socketCloseObserved, false);
});
test('Agent destroy failure or late return cannot replace original bounded completion', async () => {
    for (const config of [{agentDestroyError: true}, {agentDestroyNow: 115n * NS}]) {
        const m = model(config); await m.start(); await m.respond(); await m.close(); await failed(m);
        assert.equal(m.agents[0].destroyCalls, 1);
    }
});
test('caught active same-mode or cross-mode reentry poisons the original without new requests', async () => {
    for (const method of ['beforeOnce', 'afterOnce']) {
        const m = model(); await m.start(); assert.throws(() => m.module.exports[method](m.options));
        const result = await failed(m); assert.equal(m.requests.length, 1); assert.equal(m.agents.length, 1);
        assert.equal(result.code, 'INITIAL_ARTIFACT_OBSERVER_ONE_INVOCATION');
    }
});
test('caught early input-inspection reentry refuses before allocating an Agent or request', async () => {
    const m = model(); let caught = false;
    const options = new Proxy(m.options, {getPrototypeOf(target) {
        try { m.call(); } catch (_) { caught = true; } return Object.getPrototypeOf(target);
    }});
    assert.throws(() => m.call(options)); assert.equal(caught, true);
    assert.equal(m.agents.length, 0); assert.equal(m.requests.length, 0);
});

let currentName = 'before first model';
(async () => {
    for (const item of cases) {
        currentName = item.name; await item.run(); process.stdout.write('PASS ' + item.name + '\n');
    }
    process.stdout.write('OFFLINE_PUBLIC_OBSERVER_MODELS ' + cases.length + '/' + cases.length +
        '; no real HTTP/native/hosted/Step qualification\n');
})().catch(error => {
    // All diagnostic values here are explicit offline fixtures, never original
    // native/service data. The production observer has no output/logging path.
    process.stderr.write('FAIL OFFLINE_PUBLIC_OBSERVER_MODEL ' + currentName + '; stop on first failure\n' +
        String(error.stack || error).slice(0, 4000) + '\n');
    process.exitCode = 1;
});
