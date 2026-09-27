'use strict';

// One secret-free DATA peer for seven joint controls. No HTTP/native helper,
// process creation, private fixture, real hosted identity or previous suite.
const assert = require('node:assert/strict');
const Module = require('node:module');
const D = require('../hosted-initial-artifact-action-data.cjs');
const input = process.stdin, output = process.stdout, diagnostic = process.stderr;
const BOUND = 512 * 1024, BODY = 1048576, SCOPE = 'OFFLINE_FINITE_PYTHON_NODE_MODEL_NOT_AUTHORITY_V1';
Module._load = () => { throw new Error('FINITE_CONTRACT_UNEXPECTED_IMPORT'); };

function same(actual, expected) { assert.ok(D.equal(actual, expected), 'FINITE_CONTRACT_EXACT_VALUE'); }
function sameBytes(actual, expected) { assert.ok(actual.equals(expected), 'FINITE_CONTRACT_EXACT_BYTES'); }
function originals(rows) {
    return rows.map(row => ({kind: row.kind, id: row.id, body: D.base64(row.bodyBase64, BODY),
        rawHeaderVector: row.rawHeaderVector}));
}
function changedInput(raw, mode) {
    const value = D.record(raw, BOUND), before = mode === 'finish', rowsName = before ? 'beforeOriginals' : 'afterOriginals',
        closedName = before ? 'beforeClosed' : 'afterClosed', index = before ? 0 : 1;
    const rows = [...value[rowsName]], original = rows[index], body = Buffer.concat([D.base64(original.bodyBase64, BODY),
        Buffer.from(' ', 'ascii')]), headers = [...original.rawHeaderVector];
    // Same HTTP JSON semantics, different authentic-body bytes. Rebind all I's
    // shallow transport hashes so the retained F originals are decisive.
    const contentLength = headers.findIndex((name, position) => position % 2 === 0 && name.toLowerCase() === 'content-length');
    assert.ok(contentLength >= 0, 'FINITE_CONTRACT_CONTENT_LENGTH');
    headers[contentLength + 1] = String(body.length);
    rows[index] = {...original, bodyBase64: body.toString('base64'), rawHeaderVector: headers};
    const closed = value[closedName], requests = [...closed.requests];
    requests[index] = {...requests[index], bodyBytes: body.length, bodySha256: D.sha(body),
        rawHeaderVectorSha256: D.sha(Buffer.from(JSON.stringify(headers), 'utf8'))};
    return D.encode({...value, [rowsName]: rows, [closedName]: {...closed, requests}}, BOUND);
}
function rejectReplacement(resultRaw, context, mode) {
    const changed = changedInput(context.inputRaw, mode);
    assert.ok(!changed.equals(context.inputRaw), 'FINITE_CONTRACT_NEGATIVE_NOOP');
    assert.throws(() => D.finiteResult(resultRaw, {...context, inputRaw: changed}), D.DataError);
    const rebound = D.encode({...D.record(resultRaw), inputSha256: D.sha(changed)});
    assert.throws(() => D.finiteResult(rebound, {...context, inputRaw: changed}), D.DataError);
    return changed;
}
function peer(raw) {
    const request = D.record(raw, BOUND);
    D.fields(request, ['schema', 'scope', 'nowMs', 'environment', 'readyBase64', 'finalBase64', 'finishInputBase64',
        'afterReadyBase64', 'afterInputBase64', 'finishResultBase64', 'afterResultBase64', 'codecBase64',
        'invalidCanonicalBase64']);
    assert.ok(request.schema === 1 && request.scope === SCOPE, 'FINITE_CONTRACT_MODEL_SCOPE');
    const environment = request.environment, nowMs = request.nowMs,
        readyRaw = D.base64(request.readyBase64, 16384), finalRaw = D.base64(request.finalBase64, 16384),
        readyValue = D.ready(readyRaw, environment, nowMs), suppliedFinish = D.base64(request.finishInputBase64, BOUND),
        finish = D.record(suppliedFinish, BOUND), bounds = D.localBounds(readyValue, BigInt(finish.readerClosed.preSpawnLocalNs));
    sameBytes(D.encode(readyValue), readyRaw);
    const finishInput = D.finishInput({readyRaw, finalRaw, readerValue: finish.readerClosed, transportValue: finish.transportClosed,
        beforeValue: finish.beforeClosed, originals: originals(finish.beforeOriginals)}, readyValue, bounds, nowMs);
    sameBytes(finishInput, suppliedFinish);
    const afterReadyRaw = D.base64(request.afterReadyBase64, 16384), afterReadyValue = D.afterReady(afterReadyRaw, environment, nowMs),
        afterBounds = D.afterBounds(afterReadyValue, 200000000000n), suppliedAfter = D.base64(request.afterInputBase64, BOUND),
        after = D.record(suppliedAfter, BOUND);
    sameBytes(D.encode(afterReadyValue), afterReadyRaw);
    const afterInput = D.afterInput({afterValue: after.afterClosed, originals: originals(after.afterOriginals)},
        afterReadyRaw, afterReadyValue, afterBounds, nowMs);
    sameBytes(afterInput, suppliedAfter);
    const finishResultRaw = D.base64(request.finishResultBase64, 16384), afterResultRaw = D.base64(request.afterResultBase64, 16384),
        finishContext = {mode: 'upload', readyRaw, readyValue, bounds, inputRaw: finishInput,
            artifactId: '9010', environment, nowMs},
        afterContext = {mode: 'after', readyRaw: afterReadyRaw, readyValue: afterReadyValue, bounds: afterBounds,
            inputRaw: afterInput, artifactId: '9010', environment, nowMs};
    const finishResult = D.finiteResult(finishResultRaw, finishContext), afterResult = D.finiteResult(afterResultRaw, afterContext),
        uploadOutputs = D.outputs(finishResult), afterOutputs = D.outputs(afterResult);
    sameBytes(D.encode(finishResult), finishResultRaw);
    sameBytes(D.encode(afterResult), afterResultRaw);
    same(afterResult.pending.uploadCarrier, {directoryIdentitySha256: finishResult.directoryIdentitySha256,
        fileMetadataSha256: finishResult.fileMetadataSha256, fileOwnerCloseSha256: finishResult.fileOwnerCloseSha256});
    assert.ok(afterResult.pending.uploadSha256 === finishResult.pendingSha256, 'FINITE_CONTRACT_ORIGINAL_U');
    const changedFinish = rejectReplacement(finishResultRaw, finishContext, 'finish'),
        changedAfter = rejectReplacement(afterResultRaw, afterContext, 'after');
    const codecRaw = D.base64(request.codecBase64, 16384), codec = D.record(codecRaw);
    sameBytes(D.encode(codec), codecRaw);
    assert.ok(D.integer(codec.uint64) === (1n << 64n) - 1n && D.integer(codec.largeId) === (1n << 63n) - 1n &&
        D.integer(codec.safeBoundary) === (1n << 53n) + 1n, 'FINITE_CONTRACT_INTEGER_PRECISION');
    const invalidRefused = D.array(request.invalidCanonicalBase64, 3, 3).map(encoded => {
        const value = D.base64(encoded, 16384);
        assert.throws(() => D.record(value), D.DataError);
        assert.throws(() => D.integer(D.parse(value, 16384).n), D.DataError);
        return true;
    });
    return D.encode({schema: 1, scope: SCOPE, readyBase64: D.encode(readyValue).toString('base64'),
        afterReadyBase64: D.encode(afterReadyValue).toString('base64'), finishInputBase64: finishInput.toString('base64'),
        afterInputBase64: afterInput.toString('base64'), finishResultBase64: D.encode(finishResult).toString('base64'),
        afterResultBase64: D.encode(afterResult).toString('base64'), uploadOutputs, afterOutputs,
        changedFinishInputBase64: changedFinish.toString('base64'), changedAfterInputBase64: changedAfter.toString('base64'),
        originalInputRefused: {finish: true, after: true}, reboundInputRefused: {finish: true, after: true},
        codecBase64: D.encode(codec).toString('base64'), invalidRefused}, BOUND);
}

let size = 0, failed = false;
const chunks = [];
function refuse() {
    if (failed) return;
    failed = true;
    input.destroy();
    diagnostic.write('FINITE_CONTRACT_PEER_REFUSED\n');
    process.exitCode = 1;
}
input.on('data', chunk => {
    if (failed) return;
    size += chunk.length;
    if (size > BOUND) { refuse(); return; }
    chunks.push(Buffer.from(chunk));
});
input.on('error', refuse);
output.on('error', refuse);
input.on('end', () => {
    if (failed) return;
    try { output.end(peer(Buffer.concat(chunks, size))); }
    catch (_error) { refuse(); }
});
