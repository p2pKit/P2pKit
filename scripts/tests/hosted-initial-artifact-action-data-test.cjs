'use strict';

// New DATA controls only. No reader/observer/transport replay, native process,
// HTTP, credential, key, file ownership or hosted qualification is performed.
const assert = require('node:assert/strict');
const D = require('../hosted-initial-artifact-action-data.cjs');
const {fixture, finiteFixture, copy, headers, sha, NS, NOW} = require('./hosted-initial-artifact-action-fixtures.cjs');
const cases = [], test = (name, body) => cases.push({name, body});
function rejectsChanged(original, mutate, validate) {
    validate(original); const changed = copy(original); mutate(changed);
    assert.notDeepEqual(changed, original, 'negative must change its actual baseline');
    assert.throws(() => validate(changed));
}

test('canonical Python-compatible Unicode/key order and exact uint64 round trip', () => {
    const value = {z: 18446744073709551615n, originalJobBasisNs: -18446744073709551615n,
        '😀': 'line\n\t\u007f😀', '\uffff': '\udfff', a: [true, false, null, 0]};
    const raw = D.encode(value);
    assert(raw.every(byte => byte < 128)); assert(raw.toString('ascii').endsWith('\n'));
    assert.equal(D.record(raw).z, 18446744073709551615n); assert.deepEqual(D.encode(D.record(raw)), raw);
    assert.equal(D.record(raw).originalJobBasisNs, -18446744073709551615n);
    assert(raw.toString('ascii').indexOf('"\\uffff"') < raw.toString('ascii').indexOf('"\\ud83d\\ude00"'));
});
test('duplicate keys, alternate encodings, fractional integers and negative zero are refused', () => {
    for (const raw of ['{"n":1,"n":2}\n', '{"n":1.0}\n', '{"n":1e0}\n', '{"n":-0}\n',
        '{ "n":1}\n', '{"n":1}', '{"n":1}\n{}', '{"__proto__":1,"__proto__":2}\n'])
        assert.throws(() => D.record(Buffer.from(raw, 'ascii')));
    assert.throws(() => D.record(Buffer.from([0xff])));
    assert.throws(() => D.integer(D.parse(Buffer.from('{"id":123.0}'), 1024).id));
});
test('closed DATA rejects getters, symbols, sparse arrays and canonical cycles', () => {
    let calls = 0; const getter = {};
    Object.defineProperty(getter, 'x', {enumerable: true, get() { calls++; return 1; }});
    assert.throws(() => D.fields(getter, ['x'])); assert.equal(calls, 0);
    assert.throws(() => D.fields({x: 1, [Symbol('extra')]: 2}, ['x']));
    assert.throws(() => D.array(new Array(2), 1, 2));
    const cycle = {}; cycle.self = cycle; assert.throws(() => D.encode(cycle));
});
test('base64 validates encoded and decoded limits without accepting aliases', () => {
    assert.deepEqual(D.base64('YQ==', 1), Buffer.from('a'));
    for (const text of ['YR==', 'YQ', 'YQ==\n', 'YWI=', '====']) assert.throws(() => D.base64(text, 1));
    assert.throws(() => D.base64('A'.repeat(4 * Math.ceil(16384 / 3) + 4), 16384));
});
test('complete gate READY maps different RAW/LOCAL epochs without restarting60s', () => {
    const f = fixture(), value = D.ready(f.readyRaw, f.environment, NOW);
    const bounds = D.localBounds(value, 100n * NS);
    assert.equal(bounds.startByNs, 101n * NS); assert.equal(bounds.workEndNs, 155n * NS);
    assert.equal(bounds.closeEndNs, 160n * NS);
});
test('required four UTC bounds cannot be omitted, coerced or substituted', () => {
    const f = fixture(), validate = value => D.ready(D.encode(value), f.environment, NOW);
    for (const name of ['policyNotBefore', 'policyExpiresAt', 'authorityNotBefore', 'authorityExpiresAt']) {
        rejectsChanged(f.ready, value => { delete value[name]; }, validate);
        rejectsChanged(f.ready, value => { value[name] = true; }, validate);
        rejectsChanged(f.ready, value => { value[name] = String(value[name]); }, validate);
    }
    rejectsChanged(f.ready, value => { value.authorityExpiresAt = value.policyExpiresAt + 1; }, validate);
});
test('current authority expiration rejects equality and earlier/future original observations', () => {
    const f = fixture(); D.currentUtc(f.ready, NOW);
    assert.throws(() => D.currentUtc(f.ready, f.ready.authorityExpiresAt * 1000));
    assert.throws(() => D.currentUtc(f.ready, f.ready.authorityNotBefore * 1000 - 1));
    rejectsChanged(f.ready, value => { value.observedAt = NOW / 1000 + 1; },
        value => D.ready(D.encode(value), f.environment, NOW));
});
test('real source/ref/job/runner/seed bindings must agree before Create', () => {
    const f = fixture(); D.ready(f.readyRaw, f.environment, NOW);
    for (const name of ['GITHUB_SHA', 'GITHUB_REF', 'GITHUB_WORKFLOW_SHA', 'GITHUB_RUN_ID', 'GITHUB_RUN_ATTEMPT',
        'GITHUB_JOB', 'RUNNER_NAME', 'RUNNER_OS', 'RUNNER_ARCH', 'P2PKIT_INITIAL_SEAL_BOOT_SHA256',
        'P2PKIT_INITIAL_BEFORE_SHA256', 'P2PKIT_INITIAL_BEFORE_OUTCOME'])
        rejectsChanged(f.environment, value => { value[name] += 'changed'; }, value => D.ready(f.readyRaw, value, NOW));
});
test('complete original window arithmetic and strict original upload interval remain required', () => {
    const f = fixture(), validate = value => D.ready(D.encode(value), f.environment, NOW);
    for (const name of ['jobEndNs', 'workEndNs', 'nativeFinalEndNs', 'readEndNs', 'sealEndNs', 'uploadEndNs', 'afterEndNs'])
        rejectsChanged(f.ready, value => { value.originalWindow[name]++; }, validate);
    rejectsChanged(f.ready, value => { value.firstRawNs = value.deadline.initialSealEndNs; }, validate);
    rejectsChanged(f.ready, value => { value.closeEndNs = String(BigInt(value.closeEndNs) + NS); }, validate);
});
test('complete ZIP cap remains512MiB including four-member framing', () => {
    const f = fixture(); D.members(f.ready.members, f.ready.zipBytes);
    rejectsChanged(f.ready.members, value => { value.reverse(); }, value => D.members(value, f.ready.zipBytes));
    assert.throws(() => D.members(f.ready.members, f.ready.zipBytes + 1));
    const oversized = copy(f.ready.members); oversized[0].bytes = 512 * 1024 * 1024;
    assert.throws(() => D.members(oversized, 512 * 1024 * 1024 + f.ready.zipBytes - 10));
});
test('full pre-Create public job preserves original runner tuple and exact selected steps', () => {
    const f = fixture();
    const value = D.serviceJob(f.ready, f.beforeOriginals[0].body, f.beforeOriginals[0].rawHeaderVector,
        f.environment, 'upload', NOW);
    assert.equal(value.jobId, 123); assert.equal(value.steps.upload.number, value.steps.before.number + 1);
    assert.equal(value.bodySha256, sha(f.beforeOriginals[0].body));
});
test('identity float, changed runner, incomplete Step success and terminal interposition fail before Create', () => {
    const f = fixture(), validate = value => {
        const body = Buffer.from(JSON.stringify(value));
        return D.serviceJob(f.ready, body, headers(body.length), f.environment, 'upload', NOW);
    };
    for (const mutate of [value => { value.runner_id++; }, value => { value.runner_name += 'new'; },
        value => { value.run_attempt++; }, value => { value.labels[0] = 'ubuntu-latest'; },
        value => { value.steps[3].conclusion = 'failure'; }, value => { value.steps[4].number++; value.steps[5].number++; },
        value => { value.steps[5].status = 'in_progress'; value.steps[5].started_at = '2026-09-26T11:59:20Z'; }])
        rejectsChanged(f.job(), mutate, validate);
    const raw = Buffer.from(JSON.stringify(f.job()).replace('"id":123,', '"id":123.0,'));
    assert.throws(() => D.serviceJob(f.ready, raw, headers(raw.length), f.environment, 'upload', NOW));
});
test('after grammar requires U success, A adjacency and a unique current frontier', () => {
    const f = fixture(), validate = value => D.serviceSteps(value, NOW / 1000, 'after');
    validate(f.job('after'));
    for (const mutate of [value => { value.steps[4].conclusion = 'cancelled'; }, value => { value.steps[5].number++; },
        value => { value.steps[4].completed_at = '2026-09-26T11:59:21Z'; }])
        rejectsChanged(f.job('after'), mutate, validate);
});
test('original public header vector hash uses UTF8 JSON without canonical LF', () => {
    const f = fixture(), row = f.beforeOriginals[0], header = D.headerVector(row.rawHeaderVector, row.body.length, NOW);
    assert.equal(header.sha256, sha(Buffer.from(JSON.stringify(row.rawHeaderVector), 'utf8')));
    assert.notEqual(header.sha256, sha(D.encode(row.rawHeaderVector)));
    assert.throws(() => D.headerVector([...row.rawHeaderVector, 'date', 'Sat, 26 Sep 2026 12:00:00 GMT'], row.body.length, NOW));
    assert.throws(() => D.headerVector(row.rawHeaderVector, row.body.length, NOW + 61000));
});
test('complete observer projection binds each original body/vector/id and all eight close facts', () => {
    const f = fixture(), validate = value => D.observerClosed(value, f.beforeOriginals, f.ready, f.bounds, 'before', sha(f.readyRaw), NOW);
    validate(f.beforeClosed);
    for (const name of ['requestFinishObserved', 'requestEndCallbackObserved', 'tlsSecureConnectObserved',
        'tlsAuthorizedObserved', 'responseEndObserved', 'requestCloseObserved', 'responseCloseObserved', 'socketCloseObserved'])
        rejectsChanged(f.beforeClosed, value => { value.requests[0][name] = false; }, validate);
    rejectsChanged(f.beforeClosed, value => { value.requests[0].bodySha256 = '0'.repeat(64); }, validate);
    rejectsChanged(f.beforeClosed, value => { value.originalResourceCount = 2; }, validate);
});
test('observer chronology cannot be replaced by later returned time or a fresh15s', () => {
    const f = fixture(), validate = value => D.observerClosed(value, f.afterOriginals, f.afterReady, f.afterBounds,
        'after', sha(f.afterReadyRaw), NOW);
    validate(f.afterClosed);
    for (const mutate of [value => { value.requests[1].endNs = String(f.afterBounds.endNs + NS); },
        value => { value.requests[1].startedNs = value.requests[0].startedNs; },
        value => { value.requests[1].closedNs = String(f.afterBounds.endNs); },
        value => { value.lastObservationNs = value.enteredNs; }]) rejectsChanged(f.afterClosed, mutate, validate);
});
test('complete reader return and exact native final bind all three original pipe closes', () => {
    const f = fixture(), validate = value => D.readerClosed(value, f.readyRaw, f.finalRaw, f.ready, f.bounds);
    validate(f.readerClosed);
    for (const name of ['stdin', 'stdout', 'stderr']) rejectsChanged(f.readerClosed,
        value => { value.originalPipeCloses[name] = false; }, validate);
    rejectsChanged(f.readerClosed, value => { value.stdinEndCallbackObserved = false; }, validate);
    rejectsChanged(f.readerClosed, value => { value.returnedLocalNs = String(f.bounds.workEndNs); }, validate);
    rejectsChanged(f.readerClosed, value => { value.finalSha256 = '0'.repeat(64); }, validate);
});
test('complete transport retains Create/block/blocklist/Finalize and exact bytes/closes', () => {
    const f = fixture(), validate = value => D.transportClosed(value, f.ready, f.bounds, f.readerClosed, f.beforeClosed, NOW);
    validate(f.transportClosed);
    for (const mutate of [value => { value.requests.splice(1, 1); }, value => { value.requests.reverse(); },
        value => { value.requests[1].bodyBytes++; }, value => { value.requests[2].responseBytes++; },
        value => { value.requests[3].requestEndCallback = false; }, value => { value.inputCloseObserved = false; },
        value => { value.submittedFinalizeHash = 'sha256:' + '0'.repeat(64); }])
        rejectsChanged(f.transportClosed, mutate, validate);
});
test('retention is exactly14 days from original Create; return cannot exceed original close fence', () => {
    const f = fixture(), validate = value => D.transportClosed(value, f.ready, f.bounds, f.readerClosed, f.beforeClosed, NOW);
    for (const mutate of [value => { value.requestedRetentionDays = 15; },
        value => { value.requestedExpiresAt = new Date(NOW + 15 * 86400000).toISOString(); },
        value => { value.returnedObservationNs = String(f.bounds.closeEndNs); },
        value => { value.enteredNs = String(f.bounds.startByNs); }]) rejectsChanged(f.transportClosed, mutate, validate);
});
test('finish I retains exact original READY/final bytes and complete observer/transport projections', () => {
    const f = fixture(), raw = D.finishInput(f.input(), f.ready, f.bounds, NOW), value = D.record(raw, 2097152 - 5);
    assert.deepEqual(D.base64(value.readerReadyBase64, 16384), f.readyRaw);
    assert.deepEqual(D.base64(value.readerFinalBase64, 16384), f.finalRaw);
    assert.equal(value.transportClosed.requests.length, 4);
    assert.deepEqual(D.base64(value.beforeOriginals[0].bodyBase64, 1048576), f.beforeOriginals[0].body);
    assert(raw.length + 5 <= 2097152);
});
test('AFTER required original U hash/outcome/three custody carriers cannot be invented', () => {
    const f = fixture(); D.afterReady(f.afterReadyRaw, f.environment, NOW);
    for (const name of ['P2PKIT_INITIAL_UPLOAD_SHA256', 'P2PKIT_INITIAL_UPLOAD_DIRECTORY_SHA256',
        'P2PKIT_INITIAL_UPLOAD_FILE_METADATA_SHA256', 'P2PKIT_INITIAL_UPLOAD_OWNER_CLOSE_SHA256', 'P2PKIT_INITIAL_UPLOAD_OUTCOME'])
        rejectsChanged(f.environment, value => { delete value[name]; }, value => D.afterReady(f.afterReadyRaw, value, NOW));
    assert.throws(() => D.afterReady(D.encode({...f.afterReady, jobOriginal: f.ready.jobOriginal}), f.environment, NOW));
});
test('AFTER FIRST and directed local end keep the one original15s', () => {
    const f = fixture(), value = D.afterReady(f.afterReadyRaw, f.environment, NOW);
    assert.equal(D.afterBounds(value, 200n * NS).endNs, 215n * NS);
    const validate = ready => D.afterReady(D.encode(ready), f.environment, NOW);
    rejectsChanged(f.afterReady, ready => { ready.endNs = String(BigInt(ready.endNs) + NS); }, validate);
    rejectsChanged(f.afterReady, ready => { ready.firstRawNs = String(ready.originalWindow.uploadEndNs); }, validate);
});
test('AFTER I preserves both actual ordered originals and the same R request hash', () => {
    const f = fixture(), input = {afterValue: f.afterClosed, originals: f.afterOriginals};
    const raw = D.afterInput(input, f.afterReadyRaw, f.afterReady, f.afterBounds, NOW), value = D.record(raw, 2097152 - 5);
    assert.equal(value.afterClosed.requestSha256, sha(f.afterReadyRaw));
    assert.deepEqual(value.afterOriginals.map(row => row.kind), ['job', 'artifact']);
    assert.deepEqual(D.base64(value.afterOriginals[1].bodyBase64, 1048576), f.afterOriginals[1].body);
    assert.throws(() => D.afterInput({...input, originals: [...f.afterOriginals].reverse()}, f.afterReadyRaw,
        f.afterReady, f.afterBounds, NOW));
});
test('two individually valid1MiB originals overflow the SAME complete2MiB I and must fail as a pair', () => {
    const f = fixture();
    D.afterInput({afterValue: f.afterClosed, originals: f.afterOriginals}, f.afterReadyRaw, f.afterReady, f.afterBounds, NOW);
    const originals = copy(f.afterOriginals), value = copy(f.afterClosed);
    originals.forEach((row, index) => {
        row.body = Buffer.alloc(1048576, 0x20); row.rawHeaderVector = headers(row.body.length);
        Object.assign(value.requests[index], {bodyBytes: row.body.length, bodySha256: sha(row.body),
            rawHeaderVectorSha256: sha(Buffer.from(JSON.stringify(row.rawHeaderVector), 'utf8'))});
    });
    D.observerClosed(value, originals, f.afterReady, f.afterBounds, 'after', sha(f.afterReadyRaw), NOW);
    assert.throws(() => D.afterInput({afterValue: value, originals}, f.afterReadyRaw, f.afterReady, f.afterBounds, NOW));
});
test('both complete F envelopes independently validate SAFE pending and emit exactly six outputs', () => {
    for (const mode of ['upload', 'after']) {
        const m = finiteFixture(mode), result = D.finiteResult(m.raw, m.context), output = D.outputs(result);
        assert.deepEqual(Object.keys(output), ['artifact-id', 'receipt-base64', 'receipt-sha256',
            'directory-identity-sha256', 'file-metadata-sha256', 'file-owner-close-sha256']);
        assert.equal(output['artifact-id'], '789');
        const pendingRaw = D.base64(output['receipt-base64'], 16384);
        assert.equal(sha(pendingRaw), output['receipt-sha256']); assert.deepEqual(pendingRaw, D.encode(m.pending));
        for (const value of ['MODEL_RUNNER_NOT_AUTHORITY', 'MODEL_HEADER_NOT_PUBLIC_OUTPUT', 'bodyBase64',
            '/model/', 'ACTIONS_RUNTIME_TOKEN', 'rawHeaderVector']) assert(!pendingRaw.toString('ascii').includes(value));
        assert(m.raw.length <= 16384 && pendingRaw.length <= 16384);
    }
});
test('safe pending closed rosters exclude arbitrary private fields at every projected map', () => {
    for (const mode of ['upload', 'after']) {
        const m = finiteFixture(mode), validate = value => D.pendingShape(value, mode);
        for (const select of [value => value, value => value.source, value => value.github, value => value.originals,
            value => value.deadline, value => value.originalWindow, value => value.originalWindow.clock,
            value => value.members[0], value => value.artifact, value => value.times, value => value.observations])
            rejectsChanged(m.pending, value => { select(value).privateLeak = 'MODEL_PRIVATE'; }, validate);
    }
});
test('F exact R/I/pending/hash/source/artifact metadata cannot be substituted', () => {
    const m = finiteFixture(), validate = value => D.finiteResult(D.encode(value), m.context);
    for (const mutate of [value => { value.readySha256 = '0'.repeat(64); }, value => { value.inputSha256 = '0'.repeat(64); },
        value => { value.pendingSha256 = '0'.repeat(64); }, value => { value.artifactId = '790'; },
        value => { value.source.tree = '0'.repeat(40); }, value => { value.fileMetadataSha256 = 'NOT_A_HASH'; },
        value => { value.originalHelperOutcome = 'RETURNED'; }, value => { value.qualification = 'PASS'; }])
        rejectsChanged(m.result, mutate, validate);
});
test('rehashing altered U pending cannot hide incomplete projection/original/timing bindings', () => {
    const m = finiteFixture(), validate = value => {
        const changed = copy(m.result); changed.pending = value; changed.pendingSha256 = sha(D.encode(value));
        return D.finiteResult(D.encode(changed), m.context);
    };
    for (const mutate of [value => { value.observations.readerClosedSha256 = '0'.repeat(64); },
        value => { value.observations.transportClosedSha256 = '0'.repeat(64); },
        value => { value.observations.beforeBodySha256 = '0'.repeat(64); },
        value => { value.times.transportReturnedLocalNs = String(105n * NS); },
        value => { value.artifact.createInvokedAt = '2026-09-26T11:59:59.000Z'; },
        value => { value.members[0].sha256 = '0'.repeat(64); }, value => { value.originals.matchSha256 = '0'.repeat(64); }])
        rejectsChanged(m.pending, mutate, validate);
});
test('F actual file-owner close is after prepared pending but before original work/end', () => {
    for (const mode of ['upload', 'after']) {
        const m = finiteFixture(mode), validate = value => D.finiteResult(D.encode(value), m.context);
        rejectsChanged(m.result, value => { value.closedNs = String(BigInt(m.pending.times.pendingPreparedNs) - 1n); }, validate);
        rejectsChanged(m.result, value => { value.closedNs = mode === 'upload' ? m.f.ready.workEndNs : m.f.afterReady.endNs; }, validate);
    }
});
test('A preserves historical U carrier rather than substituting its new owner close', () => {
    const m = finiteFixture('after'), validate = value => {
        const changed = copy(m.result); changed.pending = value; changed.pendingSha256 = sha(D.encode(value));
        return D.finiteResult(D.encode(changed), m.context);
    };
    for (const mutate of [value => { value.uploadSha256 = '0'.repeat(64); },
        value => { value.uploadCarrier.fileOwnerCloseSha256 = m.result.fileOwnerCloseSha256; },
        value => { value.uploadCarrier.directoryIdentitySha256 = m.result.directoryIdentitySha256; },
        value => { value.observations.artifactBodySha256 = '0'.repeat(64); },
        value => { value.observations.afterStepNumber++; }]) rejectsChanged(m.pending, mutate, validate);
});
test('A actual shorter service expiry is retained, never renewed to a later requested expiry', () => {
    const m = finiteFixture('after'); D.finiteResult(m.raw, m.context);
    assert(m.pending.artifact.expiresAt < m.pending.artifact.requestedExpiresAt);
    const validate = value => {
        const changed = copy(m.result); changed.pending = value; changed.pendingSha256 = sha(D.encode(value));
        return D.finiteResult(D.encode(changed), m.context);
    };
    rejectsChanged(m.pending, value => { value.artifact.expiresAt = '2026-10-10T12:00:00Z'; }, validate);
    rejectsChanged(m.pending, value => { value.artifact.createdAt = '2026-09-26T11:59:59Z'; }, validate);
});
test('whole F and pending file each retain their independent16KiB limit', () => {
    const m = finiteFixture(); D.finiteResult(m.raw, m.context);
    assert.throws(() => D.finiteResult(Buffer.concat([m.raw, Buffer.alloc(16385, 0x20)]), m.context));
    const changed = copy(m.result); changed.pending.privateOriginals = 'x'.repeat(16384);
    assert.throws(() => D.outputs(changed));
});

// Synthetic worker DATA only. Keep the shared gate fixture and every original
// control unchanged. Explicit work values below are expectations, not a copy of
// the production min() calculation or any original/native admission facility.
function workerDataFixture({basis = 100n * NS, start = 1000n * NS, work = 1240n * NS} = {}) {
    const gate = fixture(), environment = copy(gate.environment), ready = copy(gate.ready), after = copy(gate.afterReady);
    environment.GITHUB_JOB = 'populate';
    ready.kind = 'worker'; ready.github.job = 'populate';
    ready.originalWindow = {...ready.originalWindow, kind: 'worker', originalJobBasisNs: basis,
        jobEndNs: basis + 5400n * NS, startNs: start, workEndNs: work, nativeFinalEndNs: work + 45n * NS,
        readEndNs: work + 75n * NS, sealEndNs: work + 105n * NS, uploadEndNs: work + 165n * NS,
        afterEndNs: work + 180n * NS};
    ready.deadline.initialSealEndNs = String(work + 105n * NS);
    environment.P2PKIT_INITIAL_SEAL_END_NS = ready.deadline.initialSealEndNs;
    ready.firstRawNs = String(work + 104n * NS);
    ready.closeEndNs = String(work + 164n * NS); ready.workEndNs = String(work + 159n * NS);
    Object.assign(after, {kind: 'worker', github: copy(ready.github), originalWindow: copy(ready.originalWindow),
        deadline: copy(ready.deadline), firstRawNs: String(work + 162n * NS), endNs: String(work + 177n * NS)});
    return {environment, ready, readyRaw: D.encode(ready), after, afterRaw: D.encode(after)};
}

test('worker JOB5400 READY preserves its original basis,240 work and complete tail', () => {
    const f = workerDataFixture(), value = D.ready(f.readyRaw, f.environment, NOW), w = value.originalWindow;
    assert.equal(value.kind, 'worker'); assert.equal(value.github.job, 'populate');
    assert.equal(BigInt(w.jobEndNs), 5500n * NS);
    assert.equal(BigInt(w.jobEndNs) - BigInt(w.originalJobBasisNs), 5400n * NS);
    assert.equal(BigInt(w.workEndNs) - BigInt(w.startNs), 240n * NS);
    assert.deepEqual(['workEndNs', 'nativeFinalEndNs', 'readEndNs', 'sealEndNs', 'uploadEndNs', 'afterEndNs']
        .map(name => BigInt(w[name])), [1240n, 1285n, 1315n, 1345n, 1405n, 1420n].map(seconds => seconds * NS));
});
test('worker JOB5400 AFTER retains one15s and the original upload cutoff', () => {
    const f = workerDataFixture(), validate = value => D.afterReady(D.encode(value), f.environment, NOW);
    const value = validate(f.after);
    assert.equal(BigInt(value.endNs) - BigInt(value.firstRawNs), 15n * NS);
    assert.equal(D.afterBounds(value, 200n * NS).endNs, 215n * NS);
    rejectsChanged(f.after, row => { row.endNs = String(BigInt(row.endNs) + 1n); }, validate);
    rejectsChanged(f.after, row => { row.firstRawNs = String(row.originalWindow.uploadEndNs); }, validate);
});
test('worker JOB5400 parity does not widen the independent gate600', () => {
    const f = fixture(), validate = value => D.ready(D.encode(value), f.environment, NOW), value = validate(f.ready);
    assert.equal(BigInt(value.originalWindow.jobEndNs) - BigInt(value.originalWindow.originalJobBasisNs), 600n * NS);
    rejectsChanged(f.ready, row => { row.originalWindow.jobEndNs = row.originalWindow.originalJobBasisNs + 5400n * NS; }, validate);
});
test('worker old1200 expanded job or rebased values cannot replace the original window', () => {
    const f = workerDataFixture(), validate = value => D.ready(D.encode(value), f.environment, NOW);
    for (const seconds of [1200n, 5399n, 5401n]) rejectsChanged(f.ready,
        row => { row.originalWindow.jobEndNs = row.originalWindow.originalJobBasisNs + seconds * NS; }, validate);
    rejectsChanged(f.ready, row => { row.originalWindow.originalJobBasisNs += NS; }, validate);
    rejectsChanged(f.ready, row => { row.originalWindow.startNs = row.originalWindow.originalJobBasisNs - 1n; }, validate);
});
test('late worker original residual clips work before its180s tail with strict equality refusal', () => {
    const f = workerDataFixture({start: 5320n * NS - 1n, work: 5320n * NS});
    const validate = value => D.ready(D.encode(value), f.environment, NOW), value = validate(f.ready), w = value.originalWindow;
    assert.equal(BigInt(w.workEndNs) - BigInt(w.startNs), 1n);
    assert.equal(BigInt(w.afterEndNs), BigInt(w.jobEndNs));
    for (const late of [5320n * NS, 5320n * NS + 1n]) rejectsChanged(f.ready,
        row => { row.originalWindow.startNs = late; }, validate);
});
test('worker JOB5400 exact uint64 endpoint is valid but one-nanosecond overflow is not', () => {
    const maximum = (1n << 64n) - 1n, basis = maximum - 5400n * NS;
    const f = workerDataFixture({basis, start: basis + 900n * NS, work: basis + 1140n * NS});
    assert.equal(BigInt(D.ready(f.readyRaw, f.environment, NOW).originalWindow.jobEndNs), maximum);
    const overflow = workerDataFixture({basis: basis + 1n, start: basis + 900n * NS, work: basis + 1140n * NS});
    assert.throws(() => D.ready(overflow.readyRaw, overflow.environment, NOW));
});
test('worker native window fields remain strict unsigned integers without lexical float aliases', () => {
    const f = workerDataFixture(), validate = value => D.ready(D.encode(value), f.environment, NOW);
    for (const name of ['jobEndNs', 'startNs', 'workEndNs', 'nativeFinalEndNs',
        'readEndNs', 'sealEndNs', 'uploadEndNs', 'afterEndNs']) {
        for (const bad of [true, -1n, String(f.ready.originalWindow[name]), 1.5, -0, (1n << 64n)])
            rejectsChanged(f.ready, row => { row.originalWindow[name] = bad; }, validate);
    }
    for (const bad of [true, String(f.ready.originalWindow.originalJobBasisNs), 1.5, -0, -(1n << 64n), (1n << 64n)])
        rejectsChanged(f.ready, row => { row.originalWindow.originalJobBasisNs = bad; }, validate);
    // An in-range negative coordinate still cannot replace a different window's basis alone.
    rejectsChanged(f.ready, row => { row.originalWindow.originalJobBasisNs = -1n; }, validate);
    const raw = f.readyRaw.toString('ascii'), token = '"originalJobBasisNs":' + f.ready.originalWindow.originalJobBasisNs;
    const floating = raw.replace(token + ',', token + '.0,');
    assert.notEqual(floating, raw);
    assert.throws(() => D.ready(Buffer.from(floating, 'ascii'), f.environment, NOW));
});
test('worker JOB5400 preserves exact240 and each45/75/105/165/180 tail offset', () => {
    for (const work of [1240n * NS - 1n, 1240n * NS + 1n]) {
        const changed = workerDataFixture({work});
        assert.throws(() => D.ready(changed.readyRaw, changed.environment, NOW));
    }
    const f = workerDataFixture(), validate = value => D.ready(D.encode(value), f.environment, NOW);
    for (const name of ['nativeFinalEndNs', 'readEndNs', 'sealEndNs', 'uploadEndNs', 'afterEndNs'])
        rejectsChanged(f.ready, row => { row.originalWindow[name]++; }, validate);
});
test('worker JOB5400 does not restart or enlarge the original60s upload and5s close', () => {
    const f = workerDataFixture(), validate = value => D.ready(D.encode(value), f.environment, NOW);
    const bounds = D.localBounds(validate(f.ready), 100n * NS);
    assert.deepEqual(bounds, {preSpawnLocalNs: 100n * NS, startByNs: 101n * NS, workEndNs: 155n * NS, closeEndNs: 160n * NS});
    rejectsChanged(f.ready, row => {
        row.closeEndNs = String(BigInt(row.firstRawNs) + 61n * NS);
        row.workEndNs = String(BigInt(row.closeEndNs) - 5n * NS);
    }, validate);
    rejectsChanged(f.ready, row => { row.workEndNs = String(BigInt(row.closeEndNs) - 4n * NS); }, validate);
    rejectsChanged(f.ready, row => { row.firstRawNs = row.deadline.initialSealEndNs; }, validate);
});
test('worker arithmetic stays unqualified DATA with original seed and context bindings', () => {
    const f = workerDataFixture(), validate = value => D.ready(D.encode(value), f.environment, NOW), value = validate(f.ready);
    assert.equal(value.qualification, 'NOT_ESTABLISHED'); assert.equal(value.originalStepOutcome, 'NOT_OBSERVED');
    assert.equal(value.nativeFileRetirement, 'PENDING_ORIGINAL_READERS');
    for (const [name, bad] of [['qualification', 'PASS'], ['originalStepOutcome', 'success'],
        ['nativeFileRetirement', 'KNOWN_NATIVE_CLOSE'], ['jobAdmission', 'SELF_ASSERTED_NOT_AUTHORITY']])
        rejectsChanged(f.ready, row => { row[name] = bad; }, validate);
    for (const name of ['GITHUB_JOB', 'RUNNER_ENVIRONMENT', 'P2PKIT_INITIAL_SEAL_END_NS', 'P2PKIT_INITIAL_SEAL_CLOCK_ROLE',
        'P2PKIT_INITIAL_SEAL_CLOCK_DOMAIN', 'P2PKIT_INITIAL_SEAL_CLOCK_TICKS_PER_SECOND', 'P2PKIT_INITIAL_SEAL_BOOT_SHA256'])
        rejectsChanged(f.environment, env => { env[name] += 'changed'; }, env => D.ready(f.readyRaw, env, NOW));
});

// Derived coordinates only: these public DATA fixtures contain no original
// service/Step/native return and cannot grant a job, upload or qualification.
function gateVirtualDataFixture({basis, start = NS, work}) {
    const f = workerDataFixture({basis, start, work});
    f.environment.GITHUB_JOB = 'initial-recipient-gate';
    for (const value of [f.ready, f.after]) {
        value.kind = value.originalWindow.kind = 'gate';
        value.github.job = f.environment.GITHUB_JOB;
        value.originalWindow.jobEndNs = basis + 600n * NS;
    }
    f.readyRaw = D.encode(f.ready); f.afterRaw = D.encode(f.after);
    return f;
}
test('gate JOB600 preserves full240 at zero and180second prelude with exact fixed tail', () => {
    for (const [start, work] of [[100n * NS, 340n * NS], [280n * NS, 520n * NS]]) {
        const f = gateVirtualDataFixture({basis: 100n * NS, start, work}),
            ready = D.ready(f.readyRaw, f.environment, NOW), after = D.afterReady(f.afterRaw, f.environment, NOW),
            w = ready.originalWindow;
        assert.equal(BigInt(w.originalJobBasisNs), 100n * NS);
        assert.equal(BigInt(w.startNs), start);
        assert.equal(BigInt(w.jobEndNs), 700n * NS);
        assert.equal(BigInt(w.workEndNs), work);
        assert.equal(BigInt(w.workEndNs) - BigInt(w.startNs), 240n * NS);
        assert.deepEqual(['workEndNs', 'nativeFinalEndNs', 'readEndNs', 'sealEndNs', 'uploadEndNs', 'afterEndNs']
            .map(name => BigInt(w[name]) - work), [0n, 45n, 75n, 105n, 165n, 180n].map(seconds => seconds * NS));
        assert(BigInt(w.afterEndNs) <= BigInt(w.jobEndNs));
        assert.equal(BigInt(after.endNs) - BigInt(after.firstRawNs), 15n * NS);
        assert.equal(ready.qualification, 'NOT_ESTABLISHED');
    }
});
test('gate JOB600 one-nanosecond residual rejects exact expiry and later entry', () => {
    const f = gateVirtualDataFixture({basis: 100n * NS, start: 520n * NS - 1n, work: 520n * NS}),
        validate = value => D.ready(D.encode(value), f.environment, NOW), ready = validate(f.ready);
    assert.equal(BigInt(ready.originalWindow.workEndNs) - BigInt(ready.originalWindow.startNs), 1n);
    assert.equal(BigInt(ready.originalWindow.afterEndNs), BigInt(ready.originalWindow.jobEndNs));
    for (const late of [520n * NS, 520n * NS + 1n])
        rejectsChanged(f.ready, row => { row.originalWindow.startNs = late; }, validate);
});
test('gate JOB600 refuses old360 adjacent worker and rebased original envelopes', () => {
    const f = gateVirtualDataFixture({basis: 100n * NS, start: 280n * NS, work: 520n * NS}),
        validate = value => D.ready(D.encode(value), f.environment, NOW);
    for (const seconds of [360n, 599n, 601n, 5400n])
        rejectsChanged(f.ready, row => { row.originalWindow.jobEndNs = row.originalWindow.originalJobBasisNs + seconds * NS; }, validate);
    rejectsChanged(f.ready, row => { row.originalWindow.originalJobBasisNs += NS; }, validate);
    rejectsChanged(f.ready, row => { row.originalWindow.startNs = row.originalWindow.originalJobBasisNs - 1n; }, validate);
    // Restoring the shared fixture's former basis reconstructs its complete old360 window,
    // not just an inconsistent jobEnd mutation. The new decoder must still refuse it.
    const old = fixture(), oldValidate = value => D.ready(D.encode(value), old.environment, NOW);
    rejectsChanged(old.ready, row => { row.originalWindow.originalJobBasisNs = 100n * NS; }, oldValidate);
});
test('gate JOB600 exact uint64 job end is valid but one-nanosecond overflow is refused', () => {
    const maximum = (1n << 64n) - 1n, basis = maximum - 600n * NS,
        f = gateVirtualDataFixture({basis, start: basis + 180n * NS, work: basis + 420n * NS});
    assert.equal(BigInt(D.ready(f.readyRaw, f.environment, NOW).originalWindow.jobEndNs), maximum);
    const overflow = gateVirtualDataFixture({basis: basis + 1n, start: basis + 180n * NS, work: basis + 420n * NS});
    assert.throws(() => D.ready(overflow.readyRaw, overflow.environment, NOW), D.DataError);
});
test('gate JOB600 refuses altered240 work and every fixed tail offset', () => {
    for (const work of [520n * NS - 1n, 520n * NS + 1n]) {
        const changed = gateVirtualDataFixture({basis: 100n * NS, start: 280n * NS, work});
        assert.throws(() => D.ready(changed.readyRaw, changed.environment, NOW), D.DataError);
    }
    const f = gateVirtualDataFixture({basis: 100n * NS, start: 280n * NS, work: 520n * NS}),
        validate = value => D.ready(D.encode(value), f.environment, NOW);
    for (const name of ['nativeFinalEndNs', 'readEndNs', 'sealEndNs', 'uploadEndNs', 'afterEndNs'])
        rejectsChanged(f.ready, row => { row.originalWindow[name]++; }, validate);
});
test('negative and zero virtual worker bases retain unsigned JOB5400 READY and AFTER ends', () => {
    for (const [basis, end] of [[-66n * NS, 5334n * NS], [-1n, 5400n * NS - 1n], [0n, 5400n * NS]]) {
        const f = workerDataFixture({basis}), ready = D.ready(f.readyRaw, f.environment, NOW),
            after = D.afterReady(f.afterRaw, f.environment, NOW);
        assert.equal(BigInt(ready.originalWindow.originalJobBasisNs), basis);
        assert.equal(BigInt(ready.originalWindow.jobEndNs), end);
        assert.equal(BigInt(ready.originalWindow.workEndNs), 1240n * NS);
        assert.equal(BigInt(after.originalWindow.originalJobBasisNs), basis);
        assert.equal(BigInt(after.endNs) - BigInt(after.firstRawNs), 15n * NS);
        assert.equal(ready.qualification, 'NOT_ESTABLISHED');
        assert.deepEqual(D.encode(ready), f.readyRaw);
    }
});
test('negative and zero gate virtual bases retain600 and the complete180second tail', () => {
    for (const [basis, work, end] of [[-66n * NS, 241n * NS, 534n * NS],
        [-1n, 241n * NS, 600n * NS - 1n], [0n, 241n * NS, 600n * NS]]) {
        const f = gateVirtualDataFixture({basis, work}), ready = D.ready(f.readyRaw, f.environment, NOW),
            after = D.afterReady(f.afterRaw, f.environment, NOW);
        assert.equal(BigInt(ready.originalWindow.originalJobBasisNs), basis);
        assert.equal(BigInt(ready.originalWindow.jobEndNs), end);
        assert.equal(BigInt(ready.originalWindow.workEndNs), work);
        assert.equal(BigInt(ready.originalWindow.afterEndNs), work + 180n * NS);
        assert(BigInt(ready.originalWindow.afterEndNs) <= end);
        assert.equal(BigInt(after.originalWindow.originalJobBasisNs), basis);
        assert.equal(after.qualification, 'NOT_ESTABLISHED');
    }
});
test('negative virtual bases do not forgive expired gate or worker residual windows', () => {
    for (const [make, work] of [[gateVirtualDataFixture, 354n * NS], [workerDataFixture, 5154n * NS]]) {
        const f = make({basis: -66n * NS, start: work - 1n, work}),
            validate = value => D.ready(D.encode(value), f.environment, NOW);
        const ready = validate(f.ready);
        assert.equal(BigInt(ready.originalWindow.workEndNs) - BigInt(ready.originalWindow.startNs), 1n);
        assert.equal(BigInt(ready.originalWindow.afterEndNs), BigInt(ready.originalWindow.jobEndNs));
        for (const late of [work, work + 1n])
            rejectsChanged(f.ready, row => { row.originalWindow.startNs = late; }, validate);
    }
    for (const basis of [-5400n * NS - 1n, -((1n << 64n) - 1n)]) {
        const f = workerDataFixture({basis});
        assert.throws(() => D.ready(f.readyRaw, f.environment, NOW), D.DataError);
    }
});
test('negative virtual basis cannot be clamped rebased or spelled as a float', () => {
    const f = workerDataFixture({basis: -66n * NS}), validate = value => D.ready(D.encode(value), f.environment, NOW);
    for (const basis of [0n, -66n * NS + 1n, -(1n << 64n), 1n << 64n])
        rejectsChanged(f.ready, value => { value.originalWindow.originalJobBasisNs = basis; }, validate);
    const token = '"originalJobBasisNs":-66000000000', raw = f.readyRaw.toString('ascii');
    assert(raw.includes(token));
    for (const alias of ['-66000000000.0', '-66000000000e0', '-0']) {
        const changed = raw.replace(token, '"originalJobBasisNs":' + alias);
        assert.notEqual(changed, raw);
        assert.throws(() => D.ready(Buffer.from(changed, 'ascii'), f.environment, NOW), D.DataError);
    }
    assert.throws(() => D.ready(f.readyRaw, f.environment, f.ready.authorityExpiresAt * 1000), D.DataError);
    rejectsChanged(f.ready, value => { value.firstRawNs = value.deadline.initialSealEndNs; }, validate);
    assert.throws(() => D.integer(-1n), D.DataError); // Native/default integer remains unsigned.
});

let passed = 0;
for (const {name, body} of cases) {
    try { body(); passed++; }
    catch (error) {
        process.stderr.write('FAIL new Action DATA control: ' + name + '\n');
        process.exitCode = 1; break; // Stop on first failure, never automatic retry.
    }
}
if (passed === cases.length) process.stdout.write('PASS ' + passed + '/' + cases.length + ' new Action DATA controls only\n');
