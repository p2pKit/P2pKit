'use strict';

// New synthetic DATA ONLY. These invented model identifiers/hashes are not
// public originals, runner identity, owner approval or execution evidence.
// No files, processes, network, keys, native APIs or historical tests are used.
const crypto = require('node:crypto');
const D = require('../hosted-initial-artifact-action-data.cjs');
const NS = 1000000000n, NOW = Date.parse('2026-09-26T12:00:00.000Z');
const sha = raw => crypto.createHash('sha256').update(raw).digest('hex');
function copy(value) {
    if (Buffer.isBuffer(value)) return Buffer.from(value);
    if (Array.isArray(value)) return value.map(copy);
    if (value !== null && typeof value === 'object') return Object.fromEntries(Object.entries(value).map(([k, v]) => [k, copy(v)]));
    return value;
}
function headers(length) {
    return ['Date', 'Sat, 26 Sep 2026 12:00:00 GMT', 'Content-Type', 'application/json; charset=utf-8',
        'X-GitHub-Api-Version-Selected', '2022-11-28', 'X-GitHub-Request-Id', 'MODELREQ:1234',
        'Cache-Control', 'public, max-age=60, s-maxage=60', 'Content-Length', String(length),
        'X-Model-Private', 'MODEL_HEADER_NOT_PUBLIC_OUTPUT'];
}
function fixture() {
    const environment = {GITHUB_ACTIONS: 'true', GITHUB_REPOSITORY: 'p2pKit/P2pKit', GITHUB_SHA: 'a'.repeat(40),
        GITHUB_REF: 'refs/heads/work/release-foundation-20260926-1WzHcOIr', GITHUB_RUN_ID: '123456', GITHUB_RUN_ATTEMPT: '1',
        GITHUB_EVENT_NAME: 'workflow_dispatch', GITHUB_WORKFLOW_SHA: 'a'.repeat(40), GITHUB_WORKSPACE: '/model/p2pkit',
        GITHUB_EVENT_PATH: '/model/event.json', GITHUB_SERVER_URL: 'https://github.com', GITHUB_API_URL: 'https://api.github.com',
        GITHUB_JOB: 'initial-recipient-gate', RUNNER_OS: 'Linux', RUNNER_ARCH: 'X64', RUNNER_NAME: 'MODEL_RUNNER_NOT_AUTHORITY',
        RUNNER_ENVIRONMENT: 'github-hosted', RUNNER_TEMP: '/model/tmp', ImageOS: 'ubuntu24', ImageVersion: 'MODEL_IMAGE',
        P2PKIT_INITIAL_SEAL_SHA256: '9'.repeat(64), P2PKIT_INITIAL_SEAL_END_NS: String(385n * NS),
        P2PKIT_INITIAL_SEAL_CLOCK_ROLE: 'linux-x64', P2PKIT_INITIAL_SEAL_CLOCK_DOMAIN: 'linux.clock_gettime_ns(CLOCK_MONOTONIC_RAW)',
        P2PKIT_INITIAL_SEAL_CLOCK_TICKS_PER_SECOND: String(NS), P2PKIT_INITIAL_SEAL_BOOT_SHA256: '8'.repeat(64),
        P2PKIT_INITIAL_SEAL_OUTCOME: 'success', P2PKIT_INITIAL_BEFORE_SHA256: 'b'.repeat(64),
        P2PKIT_INITIAL_BEFORE_OUTCOME: 'success', P2PKIT_INITIAL_UPLOAD_SHA256: '1'.repeat(64),
        P2PKIT_INITIAL_UPLOAD_DIRECTORY_SHA256: '2'.repeat(64), P2PKIT_INITIAL_UPLOAD_FILE_METADATA_SHA256: '3'.repeat(64),
        P2PKIT_INITIAL_UPLOAD_OWNER_CLOSE_SHA256: '4'.repeat(64), P2PKIT_INITIAL_UPLOAD_OUTCOME: 'success'};
    environment.GITHUB_WORKFLOW_REF = environment.GITHUB_REPOSITORY + '/.github/workflows/dependency-cache-bootstrap.yml@' +
        environment.GITHUB_REF;
    const names = ['evidence.tar.gz.gpg', 'manifest.json', 'custody-tail.tar.gz.gpg', 'custody-tail-manifest.json'];
    const members = names.map((name, index) => ({name, bytes: (index + 1) * 10, sha256: 'd'.repeat(64)}));
    const zipBytes = 100 + 22 + names.reduce((total, name) => total + 30 + 16 + 46 + 2 * name.length, 0);
    const ready = {schema: 1, scope: 'INITIAL_ARTIFACT_NATIVE_READY_PENDING_SERVICE_AND_STREAM_V1', kind: 'gate',
        selection: 'desktop-linux-x64', source: {commit: 'a'.repeat(40), tree: 'b'.repeat(40)},
        github: {repository: environment.GITHUB_REPOSITORY, runId: environment.GITHUB_RUN_ID,
            runAttempt: environment.GITHUB_RUN_ATTEMPT, job: environment.GITHUB_JOB, jobId: 123, role: 'linux-x64'},
        beforeSha256: environment.P2PKIT_INITIAL_BEFORE_SHA256, carrierCloseSha256: 'c'.repeat(64), firstRawNs: String(384n * NS),
        deadline: {initialSealSha256: environment.P2PKIT_INITIAL_SEAL_SHA256, initialSealEndNs: environment.P2PKIT_INITIAL_SEAL_END_NS,
            initialSealClockRole: environment.P2PKIT_INITIAL_SEAL_CLOCK_ROLE,
            initialSealClockDomain: environment.P2PKIT_INITIAL_SEAL_CLOCK_DOMAIN,
            initialSealClockTicksPerSecond: environment.P2PKIT_INITIAL_SEAL_CLOCK_TICKS_PER_SECOND,
            initialSealBootSha256: environment.P2PKIT_INITIAL_SEAL_BOOT_SHA256},
        originalWindow: {schema: 1, scope: 'INITIAL_RECIPIENT_CUSTODY_ABSOLUTE_WINDOW_V1',
            clock: {role: 'linux-x64', domain: environment.P2PKIT_INITIAL_SEAL_CLOCK_DOMAIN, ticksPerSecond: NS},
            // Supplied late residual: JOB600 retains the existing work280/end460 DATA below.
            originalBootDigest: environment.P2PKIT_INITIAL_SEAL_BOOT_SHA256, kind: 'gate', originalJobBasisNs: -140n * NS,
            jobEndNs: 460n * NS, startNs: 110n * NS, workEndNs: 280n * NS, nativeFinalEndNs: 325n * NS,
            readEndNs: 355n * NS, sealEndNs: 385n * NS, uploadEndNs: 445n * NS, afterEndNs: 460n * NS},
        workEndNs: String(439n * NS), closeEndNs: String(444n * NS), members, zipBytes,
        originals: {eventSha256: 'e'.repeat(64), policySha256: 'a1e4cc4862d46d7887b9cf41e73127939f41342042afe0aee00c3b603b38953b',
            matchSha256: 'f'.repeat(64)},
        jobOriginal: [123, '2026-09-26T11:59:00Z', environment.RUNNER_NAME, 456], observedAt: NOW / 1000,
        nativeFileRetirement: 'PENDING_ORIGINAL_READERS', originalStepOutcome: 'NOT_OBSERVED', qualification: 'NOT_ESTABLISHED',
        policyNotBefore: NOW / 1000 - 6 * 86400, policyExpiresAt: NOW / 1000 + 8 * 86400,
        authorityNotBefore: NOW / 1000 - 3600, authorityExpiresAt: NOW / 1000 + 7 * 86400};
    const readyRaw = D.encode(ready), bounds = D.localBounds(ready, 100n * NS);
    function job(stage = 'upload') {
        const steps = ['P2pKit initial custody export', 'P2pKit initial post-export custody', 'P2pKit initial custody seal',
            'P2pKit initial before-upload custody', 'P2pKit initial custody upload', 'P2pKit initial after-upload custody'];
        const current = stage === 'upload' ? 4 : 5;
        return {id: 123, run_id: 123456, run_attempt: 1, name: environment.GITHUB_JOB, head_sha: ready.source.commit,
            head_branch: environment.GITHUB_REF.slice(11), url: 'https://api.github.com/repos/p2pKit/P2pKit/actions/jobs/123',
            run_url: 'https://api.github.com/repos/p2pKit/P2pKit/actions/runs/123456', status: 'in_progress', conclusion: null,
            completed_at: null, started_at: ready.jobOriginal[1], runner_name: environment.RUNNER_NAME, runner_id: 456,
            labels: ['ubuntu-24.04'], runner_group_id: 0, runner_group_name: 'GitHub Actions',
            steps: steps.map((name, index) => ({name, number: index + 1, status: index < current ? 'completed' :
                index === current ? 'in_progress' : 'queued', conclusion: index < current ? 'success' : null,
            started_at: index <= current ? '2026-09-26T11:59:' + String(10 + 2 * index) + 'Z' : null,
            completed_at: index < current ? '2026-09-26T11:59:' + String(11 + 2 * index) + 'Z' : null}))};
    }
    const beforeBody = Buffer.from(JSON.stringify(job()), 'utf8');
    const beforeOriginals = [{kind: 'job', id: '123', body: beforeBody, rawHeaderVector: headers(beforeBody.length)}];
    function observerRow(original, start, close, end) {
        return {kind: original.kind, id: original.id, startedNs: String(start), closedNs: String(close), endNs: String(end),
            status: 200, bodyBytes: original.body.length, bodySha256: sha(original.body),
            rawHeaderVectorSha256: sha(Buffer.from(JSON.stringify(original.rawHeaderVector), 'utf8')),
            date: 'Sat, 26 Sep 2026 12:00:00 GMT', dateEpochSeconds: NOW / 1000,
            requestFinishObserved: true, requestEndCallbackObserved: true, tlsSecureConnectObserved: true,
            tlsAuthorizedObserved: true, responseEndObserved: true, requestCloseObserved: true,
            responseCloseObserved: true, socketCloseObserved: true};
    }
    const beforeClosed = {scope: 'INITIAL_ARTIFACT_PUBLIC_TERMINAL_TRANSPORT_ONLY_V1', stage: 'before', transport: 'closed',
        code: null, requestSha256: sha(readyRaw), jobId: '123', artifactId: null,
        enteredNs: String(100n * NS + 50000000n), lastObservationNs: String(100n * NS + 210000000n),
        agentDestroyReturned: true, originalResourceCount: 3,
        requests: [observerRow(beforeOriginals[0], 100n * NS + 100000000n, 100n * NS + 200000000n, bounds.startByNs)],
        originalStepOutcome: 'NOT_OBSERVED', qualification: 'NOT_ESTABLISHED'};
    const final = {schema: 1, scope: 'INITIAL_ARTIFACT_NATIVE_STREAM_CLOSED_FILES_PENDING_PROCESS_V1',
        beforeSha256: ready.beforeSha256, readySha256: sha(readyRaw), zipBytes, zipSha256: 'a'.repeat(64),
        nativeCloseSha256: '5'.repeat(64), closedNs: String(388n * NS), nativeFileRetirement: 'KNOWN_NATIVE_CLOSE',
        originalReaderOutcome: 'PENDING_ENCLOSING_PROCESS_CLOSE', qualification: 'NOT_ESTABLISHED'};
    const finalRaw = D.encode(final);
    const readerClosed = {scope: 'INITIAL_ARTIFACT_FIXED_READER_TRANSPORT_ONLY', transport: 'closed', code: null,
        preSpawnLocalNs: String(100n * NS), returnedLocalNs: String(104n * NS), originalChildCloseObserved: true,
        originalExitZeroObserved: true, stdinFinishObserved: true, stdinEndCallbackObserved: true,
        stdoutEndObserved: true, stderrEndObserved: true, originalPipeCloses: {stdin: true, stdout: true, stderr: true}, stderrBytes: 0,
        readySha256: sha(readyRaw), finalSha256: sha(finalRaw), zipBytes, zipSha256: final.zipSha256,
        nativeFileRetirement: 'FIXED_HELPER_RETURN_REQUIRES_CALLER_VALIDATION', originalStepOutcome: 'NOT_OBSERVED',
        qualification: 'NOT_ESTABLISHED'};
    const artifactName = D.artifactName(ready), createInvokedAt = new Date(NOW).toISOString(),
        requestedExpiresAt = new Date(NOW + 14 * 86400000).toISOString(), submittedFinalizeHash = 'sha256:' + final.zipSha256;
    const createBytes = Buffer.byteLength(JSON.stringify({workflow_run_backend_id: '', workflow_job_run_backend_id: '',
        name: artifactName, version: 7, mime_type: 'application/zip', expires_at: requestedExpiresAt}), 'utf8') + 72;
    const finalizeBytes = Buffer.byteLength(JSON.stringify({workflow_run_backend_id: '', workflow_job_run_backend_id: '',
        name: artifactName, size: String(zipBytes), hash: submittedFinalizeHash}), 'utf8') + 72;
    const listBytes = Buffer.byteLength('<?xml version="1.0" encoding="utf-8"?><BlockList><Uncommitted>' +
        Buffer.from('000000', 'ascii').toString('base64') + '</Uncommitted></BlockList>', 'ascii');
    const request = (kind, start, bodyBytes, responseBytes) => ({kind, startNs: String(start),
        status: kind === 'create' || kind === 'finalize' ? 200 : 201, bodyBytes, responseBytes,
        requestFinished: true, requestEndCallback: true, responseEndObserved: true,
        requestCloseObserved: true, responseCloseObserved: true, socketCloseObserved: true});
    const transportClosed = {scope: 'INITIAL_ARTIFACT_STREAM_TRANSPORT_ONLY', transport: 'closed', code: null,
        requestSha256: sha(readyRaw), artifactName, inputBytes: zipBytes, sentBytes: zipBytes, observedZipSha256: final.zipSha256,
        submittedFinalizeHash, artifactId: '789', createInvokedAt, requestedExpiresAt, requestedRetentionDays: 14,
        enteredNs: String(100n * NS + 300000000n), returnedObservationNs: String(104n * NS + 300000000n),
        inputEndObserved: true, inputCloseObserved: true,
        requests: [request('create', 100n * NS + 310000000n, createBytes, 40), request('block', 101n * NS, zipBytes, 0),
            request('blocklist', 104n * NS + 100000000n, listBytes, 0),
            request('finalize', 104n * NS + 200000000n, finalizeBytes, 40)],
        serviceDigest: 'NOT_OBSERVED', actualServiceExpiry: 'NOT_OBSERVED', nativeFileRetirement: 'NOT_ESTABLISHED',
        originalRunnerOutcome: 'NOT_OBSERVED', qualification: 'NOT_ESTABLISHED'};
    const afterReady = {schema: 1, scope: 'INITIAL_ARTIFACT_AFTER_READY_PENDING_PUBLIC_OBSERVATION_V1', kind: ready.kind,
        selection: ready.selection, source: copy(ready.source), github: copy(ready.github), beforeSha256: ready.beforeSha256,
        uploadSha256: environment.P2PKIT_INITIAL_UPLOAD_SHA256, deadline: copy(ready.deadline),
        originalWindow: copy(ready.originalWindow), firstRawNs: String(442n * NS), endNs: String(457n * NS), artifactId: '789',
        policyNotBefore: ready.policyNotBefore, policyExpiresAt: ready.policyExpiresAt, authorityNotBefore: ready.authorityNotBefore,
        authorityExpiresAt: ready.authorityExpiresAt, observedAt: NOW / 1000, originalStepOutcome: 'NOT_OBSERVED',
        qualification: 'NOT_ESTABLISHED'};
    const afterReadyRaw = D.encode(afterReady), afterBounds = D.afterBounds(afterReady, 200n * NS),
        afterJobBody = Buffer.from(JSON.stringify(job('after')), 'utf8'), artifactBody = Buffer.from('{"id":789}', 'utf8');
    const afterOriginals = [{kind: 'job', id: '123', body: afterJobBody, rawHeaderVector: headers(afterJobBody.length)},
        {kind: 'artifact', id: '789', body: artifactBody, rawHeaderVector: headers(artifactBody.length)}];
    const afterClosed = {scope: 'INITIAL_ARTIFACT_PUBLIC_TERMINAL_TRANSPORT_ONLY_V1', stage: 'after', transport: 'closed', code: null,
        requestSha256: sha(afterReadyRaw), jobId: '123', artifactId: '789', enteredNs: String(200n * NS + 100000000n),
        lastObservationNs: String(200n * NS + 600000000n), agentDestroyReturned: true, originalResourceCount: 6,
        requests: [observerRow(afterOriginals[0], 200n * NS + 200000000n, 200n * NS + 300000000n, afterBounds.endNs),
            observerRow(afterOriginals[1], 200n * NS + 400000000n, 200n * NS + 500000000n, afterBounds.endNs)],
        originalStepOutcome: 'NOT_OBSERVED', qualification: 'NOT_ESTABLISHED'};
    function input() { return {readyRaw, finalRaw, readerValue: readerClosed, transportValue: transportClosed,
        beforeValue: beforeClosed, originals: beforeOriginals}; }
    return {environment, ready, readyRaw, bounds, final, finalRaw, readerClosed, beforeOriginals, beforeClosed,
        transportClosed, afterReady, afterReadyRaw, afterBounds, afterClosed, afterOriginals, job, input, observerRow};
}
function finiteFixture(mode = 'upload') {
    const f = fixture(), upload = mode === 'upload', r = upload ? f.ready : f.afterReady,
        readyRaw = upload ? f.readyRaw : f.afterReadyRaw, transport = f.transportClosed;
    const artifact = {id: transport.artifactId, name: transport.artifactName, zipBytes: transport.sentBytes,
        zipSha256: transport.observedZipSha256, createInvokedAt: transport.createInvokedAt,
        requestedExpiresAt: transport.requestedExpiresAt, requestedRetentionDays: 14};
    if (!upload) {
        Object.assign(artifact, {createdAt: '2026-09-26T12:00:00Z', expiresAt: '2026-10-09T12:00:00Z',
            serviceDigest: transport.submittedFinalizeHash});
        const value = {id: 789, name: artifact.name, size_in_bytes: artifact.zipBytes, digest: artifact.serviceDigest,
            expired: false, url: 'https://api.github.com/repos/p2pKit/P2pKit/actions/artifacts/789',
            archive_download_url: 'https://api.github.com/repos/p2pKit/P2pKit/actions/artifacts/789/zip',
            workflow_run: {id: 123456, head_sha: r.source.commit, head_branch: f.environment.GITHUB_REF.slice(11)},
            created_at: artifact.createdAt, expires_at: artifact.expiresAt};
        const row = f.afterOriginals[1]; row.body = Buffer.from(JSON.stringify(value)); row.rawHeaderVector = headers(row.body.length);
        Object.assign(f.afterClosed.requests[1], {bodyBytes: row.body.length, bodySha256: sha(row.body),
            rawHeaderVectorSha256: sha(Buffer.from(JSON.stringify(row.rawHeaderVector), 'utf8'))});
    }
    const times = upload ? {firstRawNs: r.firstRawNs, streamClosedNs: f.final.closedNs, finishFirstRawNs: String(389n * NS),
        pendingPreparedNs: String(390n * NS), workEndNs: r.workEndNs, closeEndNs: r.closeEndNs,
        readerPreSpawnLocalNs: f.readerClosed.preSpawnLocalNs, readerReturnedLocalNs: f.readerClosed.returnedLocalNs,
        beforeEnteredLocalNs: f.beforeClosed.enteredNs, beforeReturnedLocalNs: f.beforeClosed.lastObservationNs,
        transportEnteredLocalNs: transport.enteredNs, transportReturnedLocalNs: transport.returnedObservationNs} :
        {firstRawNs: r.firstRawNs, endNs: r.endNs, pendingPreparedNs: String(446n * NS),
            observerEnteredLocalNs: f.afterClosed.enteredNs, observerReturnedLocalNs: f.afterClosed.lastObservationNs};
    const observations = upload ? {streamFinalSha256: sha(f.finalRaw), readerClosedSha256: sha(D.encode(f.readerClosed, 2097152)),
        transportClosedSha256: sha(D.encode(transport, 2097152)), beforeClosedSha256: sha(D.encode(f.beforeClosed, 2097152)),
        beforeBodySha256: sha(f.beforeOriginals[0].body), beforeHeaderVectorSha256: f.beforeClosed.requests[0].rawHeaderVectorSha256,
        beforeServiceEpoch: NOW / 1000, beforeStepNumber: 4, uploadStepNumber: 5, transportRequestCount: 4} :
        {afterClosedSha256: sha(D.encode(f.afterClosed, 2097152)), jobBodySha256: sha(f.afterOriginals[0].body),
            jobHeaderVectorSha256: f.afterClosed.requests[0].rawHeaderVectorSha256, artifactBodySha256: sha(f.afterOriginals[1].body),
            artifactHeaderVectorSha256: f.afterClosed.requests[1].rawHeaderVectorSha256, jobServiceEpoch: NOW / 1000,
            artifactServiceEpoch: NOW / 1000, beforeStepNumber: 4, uploadStepNumber: 5, afterStepNumber: 6, observerRequestCount: 2};
    const pending = {schema: 1, scope: upload ? 'INITIAL_ARTIFACT_UPLOAD_PENDING_ORIGINAL_STEP_RETURN_V1' :
        'INITIAL_ARTIFACT_DELIVERY_PENDING_ORIGINAL_STEP_RETURN_V1', kind: r.kind, selection: r.selection,
        source: copy(r.source), github: copy(r.github), beforeSha256: r.beforeSha256, readySha256: sha(readyRaw),
        originalWindow: copy(r.originalWindow), deadline: copy(r.deadline), originals: copy(f.ready.originals), members: copy(f.ready.members),
        policyNotBefore: r.policyNotBefore, policyExpiresAt: r.policyExpiresAt, authorityNotBefore: r.authorityNotBefore,
        authorityExpiresAt: r.authorityExpiresAt, observedAt: NOW / 1000, artifact, times, observations,
        writerReturn: 'PENDING_OWNER_CLOSE', originalHelperOutcome: 'PENDING_ENCLOSING_PROCESS_CLOSE',
        originalStepOutcome: 'NOT_OBSERVED', qualification: 'NOT_ESTABLISHED', privateOriginals: 'TERMINAL_SELF_TAIL_NOT_DELIVERED'};
    if (upload) pending.carrierCloseSha256 = r.carrierCloseSha256;
    else Object.assign(pending, {uploadSha256: r.uploadSha256, uploadCarrier: {
        directoryIdentitySha256: f.environment.P2PKIT_INITIAL_UPLOAD_DIRECTORY_SHA256,
        fileMetadataSha256: f.environment.P2PKIT_INITIAL_UPLOAD_FILE_METADATA_SHA256,
        fileOwnerCloseSha256: f.environment.P2PKIT_INITIAL_UPLOAD_OWNER_CLOSE_SHA256}});
    const inputRaw = upload ? D.finishInput(f.input(), r, f.bounds, NOW) :
        D.afterInput({afterValue: f.afterClosed, originals: f.afterOriginals}, readyRaw, r, f.afterBounds, NOW);
    const result = {schema: 1, scope: upload ? 'INITIAL_ARTIFACT_FINISH_CLOSED_PENDING_PROCESS_V1' :
        'INITIAL_ARTIFACT_AFTER_CLOSED_PENDING_PROCESS_V1', kind: r.kind, selection: r.selection, source: copy(r.source),
        github: copy(r.github), beforeSha256: r.beforeSha256, readySha256: sha(readyRaw), inputSha256: sha(inputRaw), pending,
        pendingSha256: sha(D.encode(pending)), directoryIdentitySha256: '6'.repeat(64), fileMetadataSha256: '7'.repeat(64),
        fileOwnerCloseSha256: '8'.repeat(64), closedNs: String((upload ? 391n : 447n) * NS), artifactId: artifact.id,
        originalHelperOutcome: 'PENDING_ENCLOSING_PROCESS_CLOSE', originalStepOutcome: 'NOT_OBSERVED', qualification: 'NOT_ESTABLISHED'};
    return {f, pending, result, raw: D.encode(result), inputRaw,
        context: {mode, readyRaw, readyValue: r, bounds: upload ? f.bounds : f.afterBounds, inputRaw,
            artifactId: artifact.id, environment: f.environment, nowMs: NOW}};
}
module.exports = Object.freeze({fixture, finiteFixture, copy, headers, sha, NS, NOW});
