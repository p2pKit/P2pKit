'use strict';

// Fixed PUBLIC terminal HTTP originals only. No source/recipient admission,
// semantic Step acceptance, native authority, artifact upload or qualification.
// The caller binds these exact returns to actual K/U/A before using their DATA.
const https = require('node:https');
const {ClientRequest, IncomingMessage} = require('node:http');
const {TLSSocket} = require('node:tls');
const {createHash} = require('node:crypto');
const {setTimeout, clearTimeout} = require('node:timers');

const NS = 1000000000n, BODY_LIMIT = 1024 * 1024, HEADER_LIMIT = 16 * 1024;
const HOST = 'api.github.com', API = '/repos/p2pKit/P2pKit/actions/';
const aborted = Object.getOwnPropertyDescriptor(AbortSignal.prototype, 'aborted').get;
const addAbort = EventTarget.prototype.addEventListener, removeAbort = EventTarget.prototype.removeEventListener;
let used = false, reentered = false, originalFailure = null;
// Unknown original objects stay reachable. Never export handles or raw errors.
const quarantine = [];

class ObserverError extends Error {}
function need(value, code) {
    if (!value) throw new ObserverError('INITIAL_ARTIFACT_OBSERVER_' + code);
}
function fields(value, names) {
    need(value !== null && Object.getPrototypeOf(value) === Object.prototype, 'PLAIN_FIELDS');
    const descriptors = Object.getOwnPropertyDescriptors(value);
    need(Reflect.ownKeys(value).length === names.length && names.every(name =>
        Object.hasOwn(descriptors, name) && Object.hasOwn(descriptors[name], 'value') && descriptors[name].enumerable),
    'CLOSED_DATA_FIELDS');
    return Object.freeze(Object.fromEntries(names.map(name => [name, descriptors[name].value])));
}
function uint64(value) { return typeof value === 'bigint' && value >= 0n && value <= 18446744073709551615n; }
function id(value) {
    return typeof value === 'string' && /^[1-9][0-9]{0,18}$/.test(value) && BigInt(value) <= 9223372036854775807n;
}
function sha(raw) { return createHash('sha256').update(raw).digest('hex'); }
function minimum(left, right) { return left < right ? left : right; }

function publicHeaders(incoming) {
    // rawHeaders is Node's original parsed vector, NOT the HTTP wire bytes.
    const original = incoming.rawHeaders;
    need(Array.isArray(original) && original.length > 0 && original.length <= 128 &&
        original.length % 2 === 0 && original.every(value => typeof value === 'string'), 'HEADER_VECTOR');
    const vector = Object.freeze([...original]), values = Object.create(null);
    let bytes = 0;
    for (let index = 0; index < vector.length; index += 2) {
        const name = vector[index], value = vector[index + 1], key = name.toLowerCase();
        need(/^[!#$%&'*+.^_`|~0-9A-Za-z-]+$/.test(name) && /^[\t\x20-\x7e]*$/.test(value) &&
            name.length + value.length + 2 <= 2048, 'HEADER_FIELDS');
        need(!Object.hasOwn(values, key), 'DUPLICATE_HEADER');
        values[key] = value.trim(); bytes += name.length + value.length + 4;
    }
    need(bytes <= HEADER_LIMIT, 'HEADER_BOUND');
    need(['application/json', 'application/json; charset=utf-8'].includes((values['content-type'] || '').toLowerCase()) &&
        (Object.hasOwn(values, 'content-encoding') ? values['content-encoding'] : 'identity').toLowerCase() === 'identity' &&
        values['x-github-api-version-selected'] === '2022-11-28', 'PUBLIC_TYPE');
    need(/^[A-Za-z0-9:-]{8,128}$/.test(values['x-github-request-id'] || ''), 'REQUEST_ID');
    need((!Object.hasOwn(values, 'age') || values.age === '0') &&
        ['warning', 'via', 'location', 'content-range', 'retry-after'].every(key => !Object.hasOwn(values, key)) &&
        ['MISS', 'BYPASS'].includes((Object.hasOwn(values, 'x-cache') ? values['x-cache'] : 'MISS').toUpperCase()),
    'STALE_OR_INTERMEDIARY');
    const cache = Object.create(null);
    for (const part of (values['cache-control'] || '').toLowerCase().split(',')) {
        const item = part.trim(), equal = item.indexOf('=');
        const name = equal < 0 ? item : item.slice(0, equal), value = equal < 0 ? '' : item.slice(equal + 1);
        need(!Object.hasOwn(cache, name) && ['public', 'max-age', 's-maxage'].includes(name) &&
            (name === 'public' ? equal === -1 : equal !== -1 && value === '60'), 'PUBLIC_CACHE_POLICY');
        cache[name] = value;
    }
    need(Object.keys(cache).length === 3, 'PUBLIC_CACHE_POLICY');
    const date = values.date;
    need(typeof date === 'string' && date.length === 29 &&
        /^(Mon|Tue|Wed|Thu|Fri|Sat|Sun), [0-9]{2} (Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec) [0-9]{4} [0-9]{2}:[0-9]{2}:[0-9]{2} GMT$/.test(date),
    'HTTP_DATE');
    const epoch = Date.parse(date);
    need(Number.isSafeInteger(epoch) && epoch > 0 && epoch <= 253402300799000 &&
        new Date(epoch).toUTCString() === date, 'HTTP_DATE');
    let length = null;
    if (Object.hasOwn(values, 'content-length')) {
        need(/^[0-9]{1,7}$/.test(values['content-length']) && !Object.hasOwn(values, 'transfer-encoding'), 'HTTP_LENGTH');
        length = Number(values['content-length']);
        need(length > 0 && length <= BODY_LIMIT, 'HTTP_LENGTH');
    }
    if (Object.hasOwn(values, 'transfer-encoding')) {
        need(values['transfer-encoding'].toLowerCase() === 'chunked', 'HTTP_TRANSFER');
    }
    return Object.freeze({vector, vectorSha256: sha(Buffer.from(JSON.stringify(vector), 'utf8')),
        date, dateEpochSeconds: epoch / 1000, length});
}

function observeOnce(stage, supplied) {
    let options, enteredNs, phaseEndNs, closeEndNs;
    try {
        if (used) {
            reentered = true;
            const error = new ObserverError('INITIAL_ARTIFACT_OBSERVER_ONE_INVOCATION');
            if (originalFailure !== null) originalFailure(error);
            throw error;
        }
        used = true;
        enteredNs = process.hrtime.bigint();
        need(uint64(enteredNs) && /^24\./.test(process.versions.node), 'NODE24_LOCAL_CLOCK');
        options = fields(supplied, stage === 'before' ?
            ['jobId', 'requestSha256', 'preSpawnLocalNs', 'startByNs', 'workEndNs', 'closeEndNs', 'signal'] :
            ['jobId', 'artifactId', 'requestSha256', 'preSpawnLocalNs', 'endNs', 'signal']);
        need(id(options.jobId) && (stage === 'before' || id(options.artifactId)) &&
            typeof options.requestSha256 === 'string' && /^[0-9a-f]{64}$/.test(options.requestSha256), 'IDENTIFIERS');
        need(!Reflect.apply(aborted, options.signal, []), 'CANCELLED');
        need(uint64(options.preSpawnLocalNs) && options.preSpawnLocalNs <= enteredNs, 'ORIGINAL_BASIS');
        if (stage === 'before') {
            need([options.startByNs, options.workEndNs, options.closeEndNs].every(uint64) &&
                enteredNs < options.startByNs && options.startByNs < options.workEndNs &&
                options.workEndNs === options.closeEndNs - 5n * NS &&
                options.closeEndNs <= options.preSpawnLocalNs + 60n * NS, 'BEFORE_ORIGINAL_FENCES');
            phaseEndNs = options.startByNs; closeEndNs = options.closeEndNs;
        } else {
            need(uint64(options.endNs) && enteredNs < options.endNs &&
                options.endNs <= options.preSpawnLocalNs + 15n * NS, 'AFTER_ORIGINAL_FENCES');
            phaseEndNs = closeEndNs = options.endNs;
        }
        need(!reentered, 'ONE_INVOCATION');
    } catch (error) {
        throw error instanceof ObserverError ? error : new ObserverError('INITIAL_ARTIFACT_OBSERVER_INVALID_INPUT');
    }

    const specs = stage === 'before' ? [['job', options.jobId]] : [['job', options.jobId], ['artifact', options.artifactId]];
    const rows = [], resources = [], owned = new WeakMap(), destroyed = new WeakSet();
    const retained = {agent: null, rows, resources, errors: []};
    let agent = null, agentDestroyRequested = false, agentDestroyReturned = false, closeTimer = null;
    let failed = null, settled = false, lastNs = enteredNs, acceptCompletion;
    const completion = new Promise(resolve => { acceptCompletion = resolve; });

    function remember(error) { if (retained.errors.length < 8) retained.errors.push(error); }
    function clock(end) {
        const now = process.hrtime.bigint();
        need(uint64(now) && now >= lastNs && now < end, 'ORIGINAL_DEADLINE');
        lastNs = now;
        need(failed === null && !settled && !reentered && !Reflect.apply(aborted, options.signal, []), 'FAILED_OR_CANCELLED');
        return now;
    }
    function knownClosed() { return resources.every(row => row.closed); }
    function stopAgent() {
        if (agent === null || agentDestroyRequested) return;
        agentDestroyRequested = true;
        try { agent.destroy(); agentDestroyReturned = true; }
        catch (error) {
            remember(error);
            if (failed === null) failed = 'INITIAL_ARTIFACT_OBSERVER_AGENT_CLOSE_FAILED';
        }
    }
    function summary(success) {
        return Object.freeze({scope: 'INITIAL_ARTIFACT_PUBLIC_TERMINAL_TRANSPORT_ONLY_V1', stage,
            transport: success ? 'closed' : 'incomplete', code: failed,
            requestSha256: options.requestSha256, jobId: options.jobId,
            artifactId: stage === 'after' ? options.artifactId : null,
            enteredNs: enteredNs.toString(), lastObservationNs: lastNs.toString(),
            agentDestroyReturned, originalResourceCount: resources.length,
            requests: Object.freeze(rows.map(row => Object.freeze({kind: row.kind, id: row.id,
                startedNs: row.startedNs.toString(), endNs: row.endNs.toString(),
                closedNs: row.closedNs === null ? null : row.closedNs.toString(),
                status: row.status, bodyBytes: row.bytes, bodySha256: row.bodySha256,
                rawHeaderVectorSha256: row.headers === null ? null : row.headers.vectorSha256,
                date: row.headers === null ? null : row.headers.date,
                dateEpochSeconds: row.headers === null ? null : row.headers.dateEpochSeconds,
                requestFinishObserved: row.finished, requestEndCallbackObserved: row.sent,
                tlsSecureConnectObserved: row.secure, tlsAuthorizedObserved: row.authorized,
                responseEndObserved: row.ended, requestCloseObserved: row.request !== null && row.request.closed,
                responseCloseObserved: row.response !== null && row.response.closed,
                socketCloseObserved: row.socket !== null && row.socket.closed}))),
            originalStepOutcome: 'NOT_OBSERVED', qualification: 'NOT_ESTABLISHED'});
    }
    function settle(success) {
        if (settled) return;
        settled = true;
        clearTimeout(closeTimer);
        for (const row of rows) clearTimeout(row.timer);
        Reflect.apply(removeAbort, options.signal, ['abort', cancel]);
        if (!knownClosed() || agent !== null && !agentDestroyReturned) quarantine.push(retained);
        acceptCompletion(summary(success));
    }
    function destroy(record) {
        if (destroyed.has(record.handle)) return;
        destroyed.add(record.handle);
        try { if (!record.handle.destroyed) record.handle.destroy(); }
        catch (error) { remember(error); }
    }
    function fail(error) {
        if (settled) return;
        if (failed === null) failed = error instanceof ObserverError ? error.message :
            'INITIAL_ARTIFACT_OBSERVER_OPERATION_FAILED';
        remember(error);
        for (const record of resources) destroy(record);
        stopAgent();
        if (knownClosed() && (agent === null || agentDestroyReturned)) settle(false);
    }
    function guarded(action) {
        if (settled) return;
        try { action(); } catch (error) { fail(error); }
    }
    function cancel() { fail(new ObserverError('INITIAL_ARTIFACT_OBSERVER_CANCELLED')); }
    function at(end, callback) {
        const now = clock(end);
        return setTimeout(callback, Math.max(1, Number((end - now + 999999n) / 1000000n)));
    }
    function track(row, role, handle) {
        need(handle !== null && (typeof handle === 'object' || typeof handle === 'function'), 'ORIGINAL_HANDLE');
        const previous = owned.get(handle);
        if (previous) return previous;
        const record = {role, handle, closed: false};
        resources.push(record); owned.set(handle, record); // Before any fallible listener/brand work.
        handle.on('error', fail);
        handle.on('close', hadError => {
            const duplicate = record.closed; record.closed = true;
            if (failed === null) guarded(() => {
                clock(row.endNs);
                need(!duplicate && (role !== 'socket' || hadError === false), 'ORIGINAL_ERROR_OR_DUPLICATE_CLOSE');
            });
            progress(row);
        });
        if (failed !== null || settled) destroy(record);
        return record;
    }
    function finish() {
        guarded(() => {
            const end = rows[rows.length - 1].endNs;
            clock(end);
            need(rows.length === specs.length && rows.every(row => row.done) &&
                resources.length === 3 * rows.length && knownClosed(), 'COMPLETE_ORIGINALS_REQUIRED');
            stopAgent();
            clock(end); need(agentDestroyReturned, 'AGENT_CLOSE_REQUIRED');
            settle(true);
        });
    }
    function progress(row) {
        if (failed !== null) {
            if (knownClosed() && (agent === null || agentDestroyReturned)) settle(false);
            return;
        }
        if (settled || row.done || row.request === null || row.response === null || row.socket === null) return;
        // Join independent original callbacks. No EOF/close flag alone grants a return.
        if (!(row.request.closed && row.response.closed && row.socket.closed && row.finished && row.sent &&
            row.secure && row.authorized && row.ended && row.valid)) return;
        guarded(() => {
            clock(row.endNs); row.done = true; row.closedNs = lastNs; clearTimeout(row.timer);
            if (rows.length === specs.length) finish();
            else launch();
        });
    }
    function socket(row, value) {
        try {
            const record = track(row, 'socket', value), first = row.socket === null;
            if (first) row.socket = record;
            if (failed !== null || settled) { destroy(record); return; }
            guarded(() => {
                clock(row.endNs);
                need(first && record.role === 'socket' && value instanceof TLSSocket &&
                    row.request.handle.reusedSocket === false, 'ORIGINAL_FRESH_TLS_SOCKET');
                value.on('secureConnect', () => guarded(() => {
                    clock(row.endNs);
                    need(!row.secure && !record.closed && !row.request.closed && value.encrypted === true &&
                        value.authorized === true && (value.authorizationError === null || value.authorizationError === undefined) &&
                        value.servername === HOST, 'ORIGINAL_TLS_VERIFICATION');
                    row.secure = row.authorized = true; progress(row);
                }));
            });
        } catch (error) { fail(error); }
    }
    function response(row, incoming) {
        try {
            const record = track(row, 'response', incoming), first = row.response === null;
            if (first) row.response = record;
            if (incoming.socket !== null && incoming.socket !== undefined) track(row, 'socket', incoming.socket);
            if (failed !== null || settled) { destroy(record); return; }
            guarded(() => {
                clock(row.endNs);
                need(first && record.role === 'response' && incoming instanceof IncomingMessage &&
                    row.socket !== null && incoming.socket === row.socket.handle && incoming.req === row.request.handle &&
                    row.secure && row.authorized && !row.socket.closed && !row.request.closed &&
                    incoming.readableObjectMode === false && incoming.readableEncoding === null, 'ORIGINAL_RESPONSE');
                need(incoming.httpVersion === '1.1' || incoming.httpVersion === '1.0', 'HTTP_VERSION');
                row.status = incoming.statusCode;
                need(row.status === 200, 'HTTP_STATUS');
                row.headers = publicHeaders(incoming);
                incoming.on('aborted', () => fail(new ObserverError('INITIAL_ARTIFACT_OBSERVER_RESPONSE_ABORTED')));
                incoming.on('data', raw => guarded(() => {
                    clock(row.endNs);
                    need(!row.ended && !record.closed && Buffer.isBuffer(raw) && raw.length > 0 &&
                        !(raw.buffer instanceof SharedArrayBuffer) && row.bytes + raw.length <= BODY_LIMIT &&
                        (row.headers.length === null || row.bytes + raw.length <= row.headers.length), 'BODY_BOUND');
                    row.bytes += raw.length; row.parts.push(Buffer.from(raw));
                }));
                incoming.on('end', () => guarded(() => {
                    clock(row.endNs);
                    need(!row.ended && !record.closed && incoming.complete === true && row.bytes > 0 &&
                        (row.headers.length === null || row.bytes === row.headers.length) &&
                        Array.isArray(incoming.rawTrailers) && incoming.rawTrailers.length === 0 &&
                        incoming.trailers !== null && typeof incoming.trailers === 'object' &&
                        Reflect.ownKeys(incoming.trailers).length === 0, 'BODY_EOF_OR_TRAILERS');
                    row.body = Buffer.concat(row.parts); row.parts = []; row.bodySha256 = sha(row.body);
                    clock(row.endNs); row.ended = row.valid = true; progress(row);
                }));
            });
        } catch (error) { fail(error); }
    }
    function unexpected(row, incoming, value) {
        try {
            if (incoming) track(row, 'response', incoming);
            if (value) track(row, 'socket', value);
            fail(new ObserverError('INITIAL_ARTIFACT_OBSERVER_UNEXPECTED_HTTP_PROTOCOL'));
        } catch (error) { fail(error); }
    }
    function launch() {
        guarded(() => {
            const start = clock(phaseEndNs), index = rows.length;
            need(index < specs.length && rows.every(row => row.done), 'FIXED_REQUEST_ORDER');
            const [kind, requestId] = specs[index], end = minimum(phaseEndNs, start + 15n * NS);
            const row = {kind, id: requestId, startedNs: start, endNs: end, closedNs: null, timer: null,
                request: null, response: null, socket: null, sent: false, finished: false,
                secure: false, authorized: false, ended: false, valid: false, done: false,
                status: null, headers: null, bytes: 0, parts: [], body: null, bodySha256: null};
            rows.push(row);
            row.timer = at(end, () => fail(new ObserverError('INITIAL_ARTIFACT_OBSERVER_REQUEST_DEADLINE')));
            const request = https.request({protocol: 'https:', hostname: HOST, port: 443, servername: HOST,
                path: API + (kind === 'job' ? 'jobs/' : 'artifacts/') + requestId, method: 'GET', agent,
                rejectUnauthorized: true, insecureHTTPParser: false, maxHeaderSize: HEADER_LIMIT,
                headers: {Accept: 'application/vnd.github+json', 'X-GitHub-Api-Version': '2022-11-28',
                    'User-Agent': 'P2pKit-initial-artifact-observer', 'Cache-Control': 'no-cache, max-age=0',
                    Pragma: 'no-cache', 'Accept-Encoding': 'identity', Connection: 'close'}});
            row.request = track(row, 'request', request);
            need(request instanceof ClientRequest && row.request.role === 'request', 'ORIGINAL_HTTP_REQUEST');
            request.on('socket', value => socket(row, value));
            request.on('response', value => response(row, value));
            request.on('upgrade', (incoming, value) => unexpected(row, incoming, value));
            request.on('connect', (incoming, value) => unexpected(row, incoming, value));
            request.on('information', () => fail(new ObserverError('INITIAL_ARTIFACT_OBSERVER_UNEXPECTED_HTTP_PROTOCOL')));
            request.on('finish', () => guarded(() => {
                clock(row.endNs); need(!row.finished, 'REQUEST_FINISH_ONCE'); row.finished = true; progress(row);
            }));
            request.on('timeout', () => fail(new ObserverError('INITIAL_ARTIFACT_OBSERVER_SOCKET_TIMEOUT')));
            const remaining = row.endNs - clock(row.endNs);
            request.setTimeout(Math.min(5000, Math.max(1, Number((remaining + 999999n) / 1000000n))));
            clock(row.endNs);
            request.end(error => guarded(() => {
                if (error) throw error;
                clock(row.endNs); need(!row.sent, 'REQUEST_END_CALLBACK_ONCE'); row.sent = true; progress(row);
            }));
        });
    }

    originalFailure = fail;
    Reflect.apply(addAbort, options.signal, ['abort', cancel, {once: true}]);
    guarded(() => {
        closeTimer = at(closeEndNs, () => {
            fail(new ObserverError('INITIAL_ARTIFACT_OBSERVER_CLOSE_DEADLINE')); settle(false);
        });
        clock(phaseEndNs);
        agent = new https.Agent({keepAlive: false, proxyEnv: {}, maxSockets: 1, maxTotalSockets: 1});
        retained.agent = agent;
        need(agent instanceof https.Agent, 'ORIGINAL_AGENT');
        clock(phaseEndNs); launch();
    });
    return Object.freeze({completion, cancel, originals: () => {
        need(settled && failed === null && !reentered && knownClosed() && agentDestroyReturned &&
            rows.length === specs.length && rows.every(row => row.done), 'NO_CLOSED_ORIGINALS');
        // Passive copied historical DATA; root still checks its original live
        // phase/policy before Create/output. These copies do not renew authority.
        return Object.freeze(rows.map(row => Object.freeze({kind: row.kind, id: row.id,
            body: Buffer.from(row.body), rawHeaderVector: Object.freeze([...row.headers.vector])})));
    }});
}

module.exports = Object.freeze({beforeOnce: supplied => observeOnce('before', supplied),
    afterOnce: supplied => observeOnce('after', supplied)});
