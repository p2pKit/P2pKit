'use strict';

// One original byte stream to the Actions Artifact service. NOT a native owner,
// runner admission, four-member ZIP validator, Action, or qualification result.
// The separately reviewed caller must supply genuine current authority, owned
// four-file ZIP input and conservatively mapped ORIGINAL absolute deadlines.
const https = require('node:https');
const {ClientRequest, IncomingMessage} = require('node:http');
const {TLSSocket} = require('node:tls');
const {Readable} = require('node:stream');
const {createHash} = require('node:crypto');
const {setTimeout, clearTimeout} = require('node:timers');

const NS = 1000000000n, BLOCK = 8 * 1024 * 1024, BODY_LIMIT = 64 * 1024;
const MEMBERS = ['evidence.tar.gz.gpg', 'manifest.json', 'custody-tail.tar.gz.gpg', 'custody-tail-manifest.json'];
// Classic stored ZIP, four ASCII names, data descriptors; no comments/extras.
// K separately limits EACH manifest to64KiB and ALL member bytes to576MiB.
const ZIP_OVERHEAD = 22 + MEMBERS.reduce((sum, name) => sum + 30 + 46 + 16 + 2 * name.length, 0);
const ZIP_LIMIT = 576 * 1024 * 1024 + ZIP_OVERHEAD;
const MAX_REQUESTS = Math.ceil(ZIP_LIMIT / BLOCK) + 3;
const SERVICE_PATH = '/twirp/github.actions.results.api.v1.ArtifactService/';
// Microsoft Learn Put Block / Put Block List: SAS Create(c) requires2026-04-06+.
const AZURE_VERSION = '2026-04-06';
const aborted = Object.getOwnPropertyDescriptor(AbortSignal.prototype, 'aborted').get;
const addAbort = EventTarget.prototype.addEventListener, removeAbort = EventTarget.prototype.removeEventListener;
let used = false;
// Unknown originals stay private and reachable. No accessor exports raw errors,
// credentials, URLs, request/response objects or potentially live input handles.
const quarantine = [];

class TransportError extends Error {}
function need(value, code) {
    if (!value) throw new TransportError('INITIAL_ARTIFACT_' + code);
}
function fields(value, names) {
    need(value !== null && Object.getPrototypeOf(value) === Object.prototype, 'PLAIN_FIELDS');
    const descriptors = Object.getOwnPropertyDescriptors(value);
    need(Reflect.ownKeys(value).length === names.length && names.every(name =>
        Object.hasOwn(descriptors, name) && Object.hasOwn(descriptors[name], 'value') && descriptors[name].enumerable),
    'CLOSED_DATA_FIELDS');
    return Object.freeze(Object.fromEntries(names.map(name => [name, descriptors[name].value])));
}
function text(value, limit) {
    return typeof value === 'string' && value.length > 0 && value.length <= limit && /^[\x21-\x7e]+$/.test(value);
}
function serviceUrl(value) {
    need(text(value, 4096) && /^https:\/\//.test(value) && !/[\\%?#]/.test(value), 'RESULTS_URL');
    const url = new URL(value);
    need(url.protocol === 'https:' && !url.username && !url.password && !url.port &&
        url.pathname === '/' && !url.search && !url.hash && value === url.href, 'RESULTS_URL');
    return url;
}
function backendIds(token) {
    need(text(token, 4096), 'RUNTIME_TOKEN_SHAPE');
    const parts = token.split('.');
    need(parts.length === 3 && parts.every(part => /^[A-Za-z0-9_-]+$/.test(part)), 'RUNTIME_TOKEN_SHAPE');
    const raw = Buffer.from(parts[1], 'base64url');
    need(raw.toString('base64url') === parts[1], 'RUNTIME_TOKEN_SHAPE');
    const claims = JSON.parse(new TextDecoder('utf-8', {fatal: true}).decode(raw));
    need(claims !== null && typeof claims === 'object' && typeof claims.scp === 'string' &&
        claims.scp.length <= 4096 && /^[\x20-\x7e]+$/.test(claims.scp), 'RESULTS_SCOPE');
    const scopes = claims.scp.split(' ').filter(scope => scope.startsWith('Actions.Results:'));
    const guid = '[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}';
    need(scopes.length === 1 && new RegExp('^Actions.Results:' + guid + ':' + guid + '$').test(scopes[0]),
        'RESULTS_SCOPE');
    const [, run, job] = scopes[0].split(':');
    // Decoding these IDs is not verification of the token or original runner.
    return {workflow_run_backend_id: run, workflow_job_run_backend_id: job};
}
function response(raw, kind) {
    const source = new TextDecoder('utf-8', {fatal: true}).decode(raw);
    const parsed = JSON.parse(source);
    const snake = kind === 'create' ? 'signed_upload_url' : 'artifact_id';
    const camel = kind === 'create' ? 'signedUploadUrl' : 'artifactId';
    const selected = parsed !== null && Object.hasOwn(parsed, snake) ? snake : camel;
    const value = fields(parsed, ['ok', selected]);
    need(value.ok === true && typeof value[selected] === 'string', 'SERVICE_RESPONSE');
    // This closed grammar has precisely TWO keys, ONE string value and true.
    // Every additional/duplicate JSON member adds a string token. Standard JSON
    // parsing validates escaping; counting lexical strings also rejects aliases
    // that JSON.parse alone would silently overwrite, without canonicalizing SAS.
    need((source.match(/"(?:[^"\\]|\\[\s\S])*"/g) || []).length === 3, 'SERVICE_RESPONSE_DUPLICATE');
    return value[selected];
}
function blobUrl(value) {
    need(text(value, 16 * 1024) && value.startsWith('https://') && !value.includes('\\'), 'BLOB_URL');
    const url = new URL(value);
    need(url.protocol === 'https:' && !url.username && !url.password && !url.port && !url.hash &&
        /^[a-z0-9]{3,24}\.blob\.core\.windows\.net$/.test(url.hostname) &&
        url.pathname.split('/').length >= 3 && url.pathname !== '/' && value === url.href, 'BLOB_URL');
    const names = [...url.searchParams.keys()];
    need(names.length > 0 && names.length <= 32 && new Set(names).size === names.length &&
        names.every(name => /^[a-z]+$/.test(name) && !['comp', 'blockid'].includes(name)) &&
        url.searchParams.has('sig') && url.searchParams.get('sig').length > 0, 'BLOB_QUERY');
    return url;
}

function uploadOnce(supplied) {
    let options, stream, signal, service, endpoint, ids, enteredNs;
    try {
        need(!used, 'ONE_INVOCATION'); used = true;
        enteredNs = process.hrtime.bigint();
        options = fields(supplied, ['stream', 'artifactName', 'expectedZipBytes', 'requestSha256',
            'startByNs', 'workEndNs', 'closeEndNs', 'signal', 'service', 'maxRetentionDays']);
        ({stream, signal} = options);
        need(/^24\./.test(process.versions.node), 'NODE24_REQUIRED');
        need(stream instanceof Readable && !stream.readableObjectMode && stream.readableEncoding === null &&
            !stream.destroyed && !stream.closed && !stream.readableEnded && !stream.readableDidRead &&
            stream.readableFlowing !== true && stream.listenerCount('data') === 0 &&
            stream.listenerCount('readable') === 0 && stream.readableHighWaterMark === 0 &&
            stream.readableLength === 0, 'ORIGINAL_BYTE_STREAM');
        need(!Reflect.apply(aborted, signal, []), 'CANCELLED');
        need(typeof options.artifactName === 'string' && /^[A-Za-z0-9][A-Za-z0-9._-]{0,199}$/.test(options.artifactName),
            'ARTIFACT_NAME');
        need(Number.isSafeInteger(options.expectedZipBytes) && options.expectedZipBytes > ZIP_OVERHEAD &&
            options.expectedZipBytes <= ZIP_LIMIT, 'ZIP_SIZE');
        need(typeof options.requestSha256 === 'string' && /^[0-9a-f]{64}$/.test(options.requestSha256), 'REQUEST_BINDING');
        need(Number.isInteger(options.maxRetentionDays) && options.maxRetentionDays >= 14 &&
            options.maxRetentionDays <= 400, 'RETENTION_REQUIRES_14_DAYS');
        need([options.startByNs, options.workEndNs, options.closeEndNs].every(value => typeof value === 'bigint') &&
            enteredNs < options.startByNs && options.startByNs < options.workEndNs &&
            options.workEndNs === options.closeEndNs - 5n * NS &&
            options.closeEndNs - enteredNs <= 60n * NS, 'ORIGINAL_ABSOLUTE_FENCES');
        service = fields(options.service, ['ACTIONS_RUNTIME_TOKEN', 'ACTIONS_RESULTS_URL']);
        endpoint = serviceUrl(service.ACTIONS_RESULTS_URL);
        ids = backendIds(service.ACTIONS_RUNTIME_TOKEN);
    } catch (error) {
        // URL/parser/native-brand exceptions may contain private inputs.
        throw error instanceof TransportError ? error : new TransportError('INITIAL_ARTIFACT_INVALID_INPUT');
    }

    return new Promise(resolve => {
        const rows = [], destroyed = new WeakSet(), waiters = new Set();
        const retained = {stream, rows, errors: []};
        let failed = null, settled = false, lastNs = enteredNs, workTimer, closeTimer;
        let inputEnded = false, inputClosed = false, waitingRead = null, reading = false;
        let parts = [], partBytes = 0, remainder = null;
        let inputBytes = 0, sentBytes = 0, observedZipSha256 = null, artifactId = null;
        let requestedExpiresAt = null, createInvokedAt = null, finishedWork = false;

        function observe(limit, code) {
            const now = process.hrtime.bigint();
            need(now >= lastNs && now < limit, code); lastNs = now;
            need(!Reflect.apply(aborted, signal, []), 'CANCELLED');
            need(failed === null && !settled, 'ALREADY_FAILED');
            return now;
        }
        const work = () => observe(options.workEndNs, 'WORK_DEADLINE');
        const close = () => observe(options.closeEndNs, 'CLOSE_DEADLINE');
        function knownClosed() {
            return inputClosed && rows.every(row => row.requestClosed &&
                (!row.response || row.responseClosed) && (!row.socket || row.socketClosed));
        }
        function finish(success) {
            if (settled) return;
            if (success) {
                try { close(); need(knownClosed() && finishedWork && artifactId !== null, 'INCOMPLETE'); }
                catch (error) { fail(error); return; }
            }
            settled = true;
            clearTimeout(workTimer); clearTimeout(closeTimer);
            Reflect.apply(removeAbort, signal, ['abort', cancel]);
            if (!knownClosed()) quarantine.push(retained);
            resolve(Object.freeze({scope: 'INITIAL_ARTIFACT_STREAM_TRANSPORT_ONLY',
                transport: success ? 'closed' : 'incomplete', code: failed,
                requestSha256: options.requestSha256, artifactName: options.artifactName,
                inputBytes, sentBytes, observedZipSha256,
                submittedFinalizeHash: rows.some(row => row.kind === 'finalize' && row.sent && row.finished) &&
                    observedZipSha256 !== null ?
                    'sha256:' + observedZipSha256 : null,
                artifactId, createInvokedAt, requestedExpiresAt, requestedRetentionDays: 14,
                enteredNs: enteredNs.toString(), returnedObservationNs: lastNs.toString(),
                inputEndObserved: inputEnded, inputCloseObserved: inputClosed,
                requests: Object.freeze(rows.map(row => Object.freeze({kind: row.kind,
                    startNs: row.startNs.toString(), status: row.status,
                    bodyBytes: row.bodyBytes, responseBytes: row.responseBytes,
                    requestFinished: row.finished, requestEndCallback: row.sent,
                    responseEndObserved: row.ended, requestCloseObserved: row.requestClosed,
                    responseCloseObserved: row.responseClosed, socketCloseObserved: row.socketClosed}))),
                serviceDigest: 'NOT_OBSERVED', actualServiceExpiry: 'NOT_OBSERVED',
                nativeFileRetirement: 'NOT_ESTABLISHED', originalRunnerOutcome: 'NOT_OBSERVED',
                qualification: 'NOT_ESTABLISHED'}));
        }
        function destroy(object) {
            if (!object || destroyed.has(object)) return;
            destroyed.add(object);
            try { if (!object.destroyed) object.destroy(); }
            catch (error) { if (retained.errors.length < 8) retained.errors.push(error); }
        }
        function fail(error) {
            if (settled) return;
            if (failed === null) failed = error instanceof TransportError ? error.message : 'INITIAL_ARTIFACT_OPERATION_FAILED';
            if (retained.errors.length < 8) retained.errors.push(error);
            stream.removeListener('readable', readReady);
            destroy(stream);
            for (const row of rows) { destroy(row.request); destroy(row.response); destroy(row.socket); }
            for (const reject of waiters) reject(new TransportError(failed));
            waiters.clear(); waitingRead = null;
            if (knownClosed()) finish(false);
        }
        const cancel = () => fail(new TransportError('INITIAL_ARTIFACT_CANCELLED'));
        function guarded(action) {
            if (settled) return;
            try { action(); } catch (error) { fail(error); }
        }
        function readReady() {
            if (!waitingRead || reading || failed !== null || settled) return;
            guarded(() => {
                reading = true;
                stream.removeListener('readable', readReady);
                try {
                    while (partBytes < BLOCK) {
                        work();
                        let owned = remainder; remainder = null;
                        if (owned === null) {
                            need(stream.readableHighWaterMark === 0 && stream.readableLength <= BLOCK,
                                'INPUT_BUFFER_BOUND');
                            // No positive size: read(n) can grow HWM and prefetch.
                            // With HWM0, no readable listener is registered while
                            // a synchronous producer returns or HTTP is pending.
                            const raw = Readable.prototype.read.call(stream);
                            need(stream.readableHighWaterMark === 0 && stream.readableLength === 0,
                                'INPUT_BUFFER_BOUND');
                            if (raw === null) {
                                if (inputEnded) break;
                                stream.once('readable', readReady);
                                return;
                            }
                            need(Buffer.isBuffer(raw) && raw.length > 0 && raw.length <= BLOCK &&
                                !(raw.buffer instanceof SharedArrayBuffer), 'INPUT_CHUNK');
                            // No await/callback between observation and owned copy.
                            owned = Buffer.from(raw);
                            inputBytes += owned.length;
                            need(inputBytes <= options.expectedZipBytes, 'INPUT_OVERRUN');
                        }
                        const take = Math.min(BLOCK - partBytes, owned.length);
                        parts.push(owned.subarray(0, take)); partBytes += take;
                        if (take < owned.length) remainder = owned.subarray(take);
                    }
                    // Assemble fragments before sending; a short input chunk is
                    // not a short Azure block. The fixed request cap stays valid.
                    const block = partBytes ? Buffer.concat(parts, partBytes) : null;
                    parts = []; partBytes = 0;
                    work();
                    const waiter = waitingRead; waitingRead = null;
                    waiters.delete(waiter.reject); waiter.resolve(block);
                } finally { reading = false; }
            });
        }
        function nextBlock() {
            return new Promise((accept, reject) => {
                waiters.add(reject); waitingRead = {resolve: accept, reject}; readReady();
            });
        }
        let resolveInputClose = null;
        function inputClose() {
            inputClosed = true;
            guarded(() => {
                close();
                if (!inputEnded) throw new TransportError('INITIAL_ARTIFACT_INPUT_PREMATURE_CLOSE');
                if (resolveInputClose) resolveInputClose();
            });
            if (failed !== null && knownClosed()) finish(false);
        }

        // Passive lifecycle listeners precede Create and cancellation effects.
        // A readable listener is demand: attach one only after an empty read,
        // after validated Create, and never leave it active during an upload.
        stream.on('error', error => fail(error));
        stream.on('end', () => guarded(() => { work(); inputEnded = true; readReady(); }));
        stream.on('close', inputClose);
        Reflect.apply(addAbort, signal, ['abort', cancel, {once: true}]);
        function timerAt(end, action) {
            const remaining = end - process.hrtime.bigint();
            return setTimeout(action, Math.max(1, Number((remaining + 999999n) / 1000000n)));
        }
        workTimer = timerAt(options.workEndNs, () => {
            if (!finishedWork) fail(new TransportError('INITIAL_ARTIFACT_WORK_DEADLINE'));
        });
        closeTimer = timerAt(options.closeEndNs, () => {
            fail(new TransportError('INITIAL_ARTIFACT_CLOSE_DEADLINE')); finish(false);
        });

        function exchange(kind, url, body, headers, expectedStatus, parse) {
            return new Promise((accept, reject) => {
                waiters.add(reject);
                guarded(() => {
                    const startNs = work();
                    if (kind === 'create') need(startNs < options.startByNs, 'START_DEADLINE');
                    need(rows.length < MAX_REQUESTS, 'REQUEST_COUNT');
                    const row = {kind, startNs, bodyBytes: body.length, responseBytes: 0, status: null,
                        request: null, response: null, socket: null, requestClosed: false,
                        responseClosed: false, socketClosed: false, finished: false, sent: false,
                        ended: false, valid: false, parsed: null, parts: []};
                    rows.push(row);
                    function progress() {
                        if (failed !== null) { if (knownClosed()) finish(false); return; }
                        guarded(() => {
                            if (kind === 'finalize' && row.finished && row.sent && row.ended && row.valid) finishedWork = true;
                            if (row.requestClosed && row.responseClosed && row.socketClosed) {
                                close();
                                need(row.finished && row.sent && row.ended && row.valid, 'HTTP_INCOMPLETE_CLOSE');
                                waiters.delete(reject); accept(row.parsed);
                            }
                        });
                    }
                    const request = https.request(url, {method: kind === 'create' || kind === 'finalize' ? 'POST' : 'PUT',
                        headers: {...headers, 'Content-Length': String(body.length), Connection: 'close',
                            ...(kind === 'block' || kind === 'blocklist' ? {'x-ms-date': new Date().toUTCString()} : {})},
                        agent: false, maxHeaderSize: 16 * 1024, insecureHTTPParser: false, rejectUnauthorized: true});
                    row.request = request;
                    need(request instanceof ClientRequest, 'ORIGINAL_HTTP_REQUEST');
                    request.on('error', error => fail(error));
                    request.on('finish', () => guarded(() => { work(); row.finished = true; progress(); }));
                    request.on('close', () => { row.requestClosed = true; progress(); });
                    request.on('socket', socket => guarded(() => {
                        need(row.socket === null, 'DUPLICATE_SOCKET'); row.socket = socket;
                        socket.on('error', error => fail(error));
                        socket.on('close', hadError => {
                            row.socketClosed = true;
                            if (hadError) fail(new TransportError('INITIAL_ARTIFACT_SOCKET_ERROR_CLOSE'));
                            progress();
                        });
                        need(socket instanceof TLSSocket && !request.reusedSocket, 'ORIGINAL_TLS_SOCKET');
                    }));
                    request.on('response', incoming => guarded(() => {
                        need(row.response === null, 'DUPLICATE_RESPONSE'); row.response = incoming;
                        incoming.on('error', error => fail(error));
                        incoming.on('aborted', () => fail(new TransportError('INITIAL_ARTIFACT_HTTP_ABORTED')));
                        incoming.on('close', () => { row.responseClosed = true; progress(); });
                        incoming.on('data', raw => guarded(() => {
                            work();
                            need(Buffer.isBuffer(raw) && !(raw.buffer instanceof SharedArrayBuffer) &&
                                row.responseBytes + raw.length <= (parse ? BODY_LIMIT : 0), 'RESPONSE_BODY_BOUND');
                            row.responseBytes += raw.length; row.parts.push(Buffer.from(raw));
                        }));
                        incoming.on('end', () => guarded(() => {
                            work(); need(incoming.complete === true, 'HTTP_TRUNCATED');
                            row.parsed = parse ? parse(Buffer.concat(row.parts)) : null;
                            row.parts = []; work(); row.valid = true; row.ended = true; progress();
                        }));
                        work(); need(incoming instanceof IncomingMessage, 'ORIGINAL_HTTP_RESPONSE');
                        row.status = incoming.statusCode;
                        need(row.status === expectedStatus, 'HTTP_STATUS');
                        if (headers['Content-MD5']) need(incoming.headers['content-md5'] === headers['Content-MD5'],
                            'TRANSACTIONAL_MD5');
                    }));
                    const sendNs = work();
                    if (kind === 'create') need(sendNs < options.startByNs, 'START_DEADLINE');
                    request.end(body, error => guarded(() => {
                        if (error) throw error;
                        work(); row.sent = true; progress();
                    }));
                });
            });
        }
        function serviceCall(kind, body) {
            // Credential is confined to the fixed methods on original Results origin.
            return exchange(kind, new URL(SERVICE_PATH + (kind === 'create' ? 'CreateArtifact' : 'FinalizeArtifact'), endpoint),
                Buffer.from(JSON.stringify(body), 'utf8'), {Authorization: 'Bearer ' + service.ACTIONS_RUNTIME_TOKEN,
                    'Content-Type': 'application/json', Accept: 'application/json'}, 200, raw => response(raw, kind));
        }
        async function run() {
            work();
            const utc = Date.now(); need(Number.isSafeInteger(utc) && utc > 0, 'UTC_CLOCK');
            createInvokedAt = new Date(utc).toISOString();
            requestedExpiresAt = new Date(utc + 14 * 86400000).toISOString();
            const signed = await serviceCall('create', {...ids, name: options.artifactName, version: 7,
                mime_type: 'application/zip', expires_at: requestedExpiresAt});
            work(); const blob = blobUrl(signed), blocks = [], hash = createHash('sha256');
            while (true) {
                const block = await nextBlock(); work();
                if (block === null) break;
                const id = Buffer.from(String(blocks.length).padStart(6, '0'), 'ascii').toString('base64');
                // Append only our operation parameters; URLSearchParams.append
                // would re-encode the ORIGINAL signed query as a side effect.
                const url = new URL(blob.href + '&comp=block&blockid=' + encodeURIComponent(id));
                hash.update(block);
                await exchange('block', url, block, {'x-ms-version': AZURE_VERSION,
                    'Content-Type': 'application/octet-stream', 'Content-MD5': createHash('md5').update(block).digest('base64')},
                201, null);
                work(); sentBytes += block.length; blocks.push(id);
            }
            need(inputEnded && inputBytes === options.expectedZipBytes && sentBytes === inputBytes, 'INPUT_SHORT');
            if (!inputClosed) await new Promise((accept, reject) => {
                waiters.add(reject); resolveInputClose = () => { waiters.delete(reject); accept(); };
            });
            work(); need(inputClosed, 'INPUT_CLOSE_REQUIRED');
            observedZipSha256 = hash.digest('hex');
            const list = Buffer.from('<?xml version="1.0" encoding="utf-8"?><BlockList>' +
                blocks.map(id => '<Uncommitted>' + id + '</Uncommitted>').join('') + '</BlockList>', 'ascii');
            const listUrl = new URL(blob.href + '&comp=blocklist');
            await exchange('blocklist', listUrl, list, {'x-ms-version': AZURE_VERSION, 'Content-Type': 'application/xml',
                'x-ms-blob-content-type': 'application/zip', 'If-None-Match': '*',
                'Content-MD5': createHash('md5').update(list).digest('base64')}, 201, null);
            work();
            const id = await serviceCall('finalize', {...ids, name: options.artifactName,
                size: String(sentBytes), hash: 'sha256:' + observedZipSha256});
            need(/^[1-9][0-9]{0,18}$/.test(id) && BigInt(id) <= 9223372036854775807n, 'ARTIFACT_ID');
            artifactId = id; finish(true);
        }
        run().catch(fail);
    });
}

module.exports = Object.freeze({uploadOnce});
