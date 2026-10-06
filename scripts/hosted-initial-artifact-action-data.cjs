'use strict';

// Closed U/A DATA only. No process, file, clock, credential or network owner.
// Original returned objects/bytes and same-invocation custody belong to the
// fixed Action controller. Equal DATA cannot construct or renew that owner.
const {createHash} = require('node:crypto');

const NS = 1000000000n, UINT64 = (1n << 64n) - 1n, INT64 = (1n << 63n) - 1n;
const RECORD = 16384, BODY = 1048576, INPUT = 2097152, ZIP_LIMIT = 512 * 1024 * 1024, BLOCK = 8 * 1024 * 1024;
const REPOSITORY = 'p2pKit/P2pKit', REF = 'refs/heads/work/release-foundation-20260926-1WzHcOIr';
const WORKFLOW = '.github/workflows/dependency-cache-bootstrap.yml';
const POLICY_SHA256 = 'a1e4cc4862d46d7887b9cf41e73127939f41342042afe0aee00c3b603b38953b';
const MEMBERS = Object.freeze(['evidence.tar.gz.gpg', 'manifest.json', 'custody-tail.tar.gz.gpg', 'custody-tail-manifest.json']);
const SEED = Object.freeze(['initialSealSha256', 'initialSealEndNs', 'initialSealClockRole',
    'initialSealClockDomain', 'initialSealClockTicksPerSecond', 'initialSealBootSha256']);
const SEED_ENV = Object.freeze(['P2PKIT_INITIAL_SEAL_SHA256', 'P2PKIT_INITIAL_SEAL_END_NS',
    'P2PKIT_INITIAL_SEAL_CLOCK_ROLE', 'P2PKIT_INITIAL_SEAL_CLOCK_DOMAIN',
    'P2PKIT_INITIAL_SEAL_CLOCK_TICKS_PER_SECOND', 'P2PKIT_INITIAL_SEAL_BOOT_SHA256']);
const UTC_FIELDS = Object.freeze(['policyNotBefore', 'policyExpiresAt', 'authorityNotBefore', 'authorityExpiresAt']);
const DOMAINS = Object.freeze({'linux-x64': 'linux.clock_gettime_ns(CLOCK_MONOTONIC_RAW)',
    'windows-x64': 'windows.QueryPerformanceCounter/QueryPerformanceFrequency.floor_ns',
    'macos-arm64': 'darwin.clock_gettime_ns(CLOCK_MONOTONIC_RAW)',
    'macos-x64': 'darwin.clock_gettime_ns(CLOCK_MONOTONIC_RAW)'});
const HOSTS = Object.freeze({'linux-x64': Object.freeze(['Linux', 'X64', 'ubuntu-latest']),
    'windows-x64': Object.freeze(['Windows', 'X64', 'windows-latest']),
    'macos-arm64': Object.freeze(['macOS', 'ARM64', 'macos-26']),
    'macos-x64': Object.freeze(['macOS', 'X64', 'macos-15-intel'])});
const SELECTIONS = Object.freeze(['desktop-linux-x64', 'desktop-windows-x64', 'desktop-macos-arm64',
    'desktop-macos-x64', 'full-macos-arm64', 'full-macos-x64']);
const STEPS = Object.freeze([['export', 'P2pKit initial custody export'], ['collect', 'P2pKit initial post-export custody'],
    ['seal', 'P2pKit initial custody seal'], ['before', 'P2pKit initial before-upload custody'],
    ['upload', 'P2pKit initial custody upload'], ['after', 'P2pKit initial after-upload custody']].map(Object.freeze));
const SCOPES = Object.freeze({ready: 'INITIAL_ARTIFACT_NATIVE_READY_PENDING_SERVICE_AND_STREAM_V1',
    final: 'INITIAL_ARTIFACT_NATIVE_STREAM_CLOSED_FILES_PENDING_PROCESS_V1',
    finishInput: 'INITIAL_ARTIFACT_FINISH_ORIGINALS_INPUT_V1', afterInput: 'INITIAL_ARTIFACT_AFTER_ORIGINALS_INPUT_V1',
    afterReady: 'INITIAL_ARTIFACT_AFTER_READY_PENDING_PUBLIC_OBSERVATION_V1',
    finishResult: 'INITIAL_ARTIFACT_FINISH_CLOSED_PENDING_PROCESS_V1',
    afterResult: 'INITIAL_ARTIFACT_AFTER_CLOSED_PENDING_PROCESS_V1'});

class DataError extends Error {}
function need(value, code) {
    if (!value) throw new DataError('INITIAL_ARTIFACT_ACTION_DATA_' + code);
}
function fields(value, names) {
    need(value !== null && Object.getPrototypeOf(value) === Object.prototype, 'PLAIN_OBJECT');
    const descriptors = Object.getOwnPropertyDescriptors(value), keys = Reflect.ownKeys(descriptors);
    need(keys.length === names.length && names.every(name => Object.hasOwn(descriptors, name) &&
        Object.hasOwn(descriptors[name], 'value') && descriptors[name].enumerable), 'EXACT_FIELDS');
    return Object.freeze(Object.fromEntries(names.map(name => [name, descriptors[name].value])));
}
function array(value, minimum, maximum) {
    need(Array.isArray(value) && value.length >= minimum && value.length <= maximum, 'ARRAY_BOUND');
    const names = ['length', ...Array.from({length: value.length}, (_, index) => String(index))];
    const descriptors = Object.getOwnPropertyDescriptors(value);
    need(Reflect.ownKeys(descriptors).length === names.length && names.every(name =>
        Object.hasOwn(descriptors, name) && Object.hasOwn(descriptors[name], 'value')), 'DENSE_ARRAY');
    return Object.freeze(Array.from({length: value.length}, (_, index) => descriptors[String(index)].value));
}
function integer(value, minimum = 0n, maximum = UINT64) {
    need(typeof value === 'bigint' || Number.isSafeInteger(value) && !Object.is(value, -0), 'INTEGER');
    const number = BigInt(value);
    need(number >= minimum && number <= maximum, 'INTEGER_BOUND');
    return number;
}
function count(value, minimum, maximum) { return Number(integer(value, BigInt(minimum), BigInt(maximum))); }
function decimal(value, minimum = 0n, maximum = UINT64) {
    need(typeof value === 'string' && /^(0|[1-9][0-9]{0,19})$/.test(value), 'DECIMAL');
    return integer(BigInt(value), minimum, maximum);
}
function digest(value) { need(typeof value === 'string' && /^[0-9a-f]{64}$/.test(value), 'DIGEST'); return value; }
function bytes(raw, maximum) {
    need(Buffer.isBuffer(raw) && !(raw.buffer instanceof SharedArrayBuffer) && raw.length > 0 && raw.length <= maximum,
        'ORIGINAL_BYTES_BOUND');
    return raw;
}
function sha(raw) { return createHash('sha256').update(bytes(raw, INPUT)).digest('hex'); }
function minimum(left, right) { return left < right ? left : right; }
function asciiString(value) {
    return JSON.stringify(value).replace(/[\u007f-\uffff]/g, character =>
        '\\u' + character.charCodeAt(0).toString(16).padStart(4, '0'));
}
function keyOrder(left, right) {
    const a = Array.from(left, value => value.codePointAt(0)), b = Array.from(right, value => value.codePointAt(0));
    for (let index = 0; index < Math.min(a.length, b.length); index++) if (a[index] !== b[index]) return a[index] - b[index];
    return a.length - b.length;
}
function encode(value, maximum = RECORD) {
    const active = new Set(), parts = [];
    let size = 0;
    function emit(text) {
        size += Buffer.byteLength(text, 'ascii');
        need(size <= maximum, 'ENCODED_BOUND'); parts.push(text);
    }
    function write(item) {
        if (item === null || typeof item === 'boolean') { emit(String(item)); return; }
        if (typeof item === 'string') { emit(asciiString(item)); return; }
        if (typeof item === 'number' || typeof item === 'bigint') {
            need(typeof item === 'bigint' || Number.isSafeInteger(item) && !Object.is(item, -0), 'CANONICAL_INTEGER');
            emit(String(item)); return;
        }
        need(item !== null && typeof item === 'object' && !active.has(item), 'CANONICAL_VALUE');
        active.add(item);
        if (Array.isArray(item)) {
            const values = array(item, 0, maximum); emit('[');
            values.forEach((part, index) => { if (index) emit(','); write(part); }); emit(']');
        } else {
            need(Object.getPrototypeOf(item) === Object.prototype, 'CANONICAL_OBJECT');
            const descriptors = Object.getOwnPropertyDescriptors(item), keys = Reflect.ownKeys(descriptors);
            need(keys.every(key => typeof key === 'string' && descriptors[key].enumerable &&
                Object.hasOwn(descriptors[key], 'value')), 'CANONICAL_DATA_PROPERTIES');
            emit('{');
            keys.sort(keyOrder).forEach((key, index) => {
                if (index) emit(','); emit(asciiString(key)); emit(':'); write(descriptors[key].value);
            });
            emit('}');
        }
        active.delete(item);
    }
    try { write(value); emit('\n'); return Buffer.from(parts.join(''), 'ascii'); }
    catch (error) { throw error instanceof DataError ? error : new DataError('INITIAL_ARTIFACT_ACTION_DATA_ENCODING'); }
}
function parse(raw, maximum, canonical = false) {
    // Exact integer tokens survive JavaScript's Number boundary. Duplicate keys
    // are rejected while reading, not after JSON.parse has overwritten them.
    bytes(raw, maximum);
    let text, position = 0;
    try {
        text = new TextDecoder('utf-8', {fatal: true}).decode(raw);
        function space() { while (/[\x20\t\r\n]/.test(text[position] || '\0')) position++; }
        function string() {
            const start = position++;
            need(text[start] === '"', 'JSON_STRING');
            while (position < text.length) {
                const character = text[position++];
                if (character === '\\') { position++; continue; }
                if (character === '"') return JSON.parse(text.slice(start, position));
                need(character.charCodeAt(0) >= 32, 'JSON_STRING_CONTROL');
            }
            throw new DataError('INITIAL_ARTIFACT_ACTION_DATA_JSON_STRING_END');
        }
        function value() {
            space(); const first = text[position];
            if (first === '"') return string();
            if (first === '{') {
                position++; space(); const result = {}, names = new Set();
                if (text[position] === '}') { position++; return Object.freeze(result); }
                while (true) {
                    space(); const key = string(); need(!names.has(key), 'JSON_DUPLICATE'); names.add(key);
                    space(); need(text[position++] === ':', 'JSON_COLON');
                    Object.defineProperty(result, key, {value: value(), enumerable: true});
                    space(); const end = text[position++];
                    if (end === '}') return Object.freeze(result);
                    need(end === ',', 'JSON_OBJECT_DELIMITER');
                }
            }
            if (first === '[') {
                position++; space(); const result = [];
                if (text[position] === ']') { position++; return Object.freeze(result); }
                while (true) {
                    result.push(value()); space(); const end = text[position++];
                    if (end === ']') return Object.freeze(result);
                    need(end === ',', 'JSON_ARRAY_DELIMITER');
                }
            }
            for (const [token, result] of [['true', true], ['false', false], ['null', null]]) {
                if (text.startsWith(token, position)) { position += token.length; return result; }
            }
            const matched = /^-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?/.exec(text.slice(position));
            need(matched !== null, 'JSON_TOKEN'); const token = matched[0]; position += token.length;
            if (!/[.eE]/.test(token)) {
                need(token.length <= 4300, 'JSON_INTEGER_BOUND');
                const number = BigInt(token);
                if (token === '-0') return -0;
                return number >= BigInt(Number.MIN_SAFE_INTEGER) && number <= BigInt(Number.MAX_SAFE_INTEGER) ?
                    Number(number) : number;
            }
            const number = Number(token); need(Number.isFinite(number), 'JSON_FINITE');
            // A lexical 1.0/1e0 is a JSON float, not a typed integer. Preserve
            // that distinction even when JavaScript could round it to1. The
            // original body remains untouched; unused service extras need not
            // become canonical evidence or integer identity fields.
            return Object.freeze(new Number(number));
        }
        const result = value(); space(); need(position === text.length, 'JSON_TRAILING');
        need(result !== null && Object.getPrototypeOf(result) === Object.prototype, 'JSON_OBJECT');
        if (canonical) need(encode(result, maximum).equals(raw), 'CANONICAL_BYTES');
        return result;
    } catch (error) { throw error instanceof DataError ? error : new DataError('INITIAL_ARTIFACT_ACTION_DATA_JSON'); }
}
function record(raw, maximum = RECORD) { return parse(raw, maximum, true); }
function equal(left, right, maximum = INPUT) { return encode(left, maximum).equals(encode(right, maximum)); }
function base64Size(value, maximum) {
    need(typeof value === 'string' && value.length > 0 && value.length <= 4 * Math.ceil(maximum / 3) &&
        value.length % 4 === 0 && /^(?:[A-Za-z0-9+/]{4})*(?:[A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?$/.test(value),
    'BASE64_ENCODED_BOUND');
    const padding = value.endsWith('==') ? 2 : value.endsWith('=') ? 1 : 0;
    need(value.length / 4 * 3 - padding <= maximum, 'BASE64_DECODED_BOUND');
    return value.length / 4 * 3 - padding;
}
function base64(value, maximum) {
    base64Size(value, maximum);
    const raw = Buffer.from(value, 'base64');
    need(raw.length > 0 && raw.toString('base64') === value, 'BASE64_CANONICAL'); return raw;
}
function utc(value, milliseconds = false) {
    need(typeof value === 'string' && (milliseconds ? /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$/ :
        /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$/).test(value), 'UTC');
    const epoch = Date.parse(value);
    need(Number.isSafeInteger(epoch) && epoch > 0 && epoch <= 253402300799000 &&
        new Date(epoch).toISOString() === (milliseconds ? value : value.replace('Z', '.000Z')), 'UTC_DATE');
    return milliseconds ? epoch : epoch / 1000;
}
function currentUtc(value, nowMs) {
    count(nowMs, 1, 253402300799000);
    const [start, end, authorityStart, authorityEnd] = UTC_FIELDS.map(name => count(value[name], 1, 253402300799));
    need(start <= authorityStart && authorityStart < authorityEnd && authorityEnd <= end &&
        authorityEnd - authorityStart <= 14 * 86400 &&
        authorityStart * 1000 <= nowMs && nowMs < authorityEnd * 1000, 'ORIGINAL_CURRENT_UTC');
    return Object.freeze({start, end, authorityStart, authorityEnd});
}
function source(value, environment) {
    const result = fields(value, ['commit', 'tree']);
    need([result.commit, result.tree].every(item => typeof item === 'string' && /^[0-9a-f]{40}$/.test(item)) &&
        result.commit !== '3bc76f956f8f47447b51a62474fc878b9c43173c' &&
        result.tree !== '2a1105fde1d1ac299448489501e29d7a0d4a407a' && result.commit === environment.GITHUB_SHA,
    'SOURCE_BINDING');
}
function identity(value, environment, kind) {
    need(kind === 'gate' || kind === 'worker', 'KIND');
    source(value.source, environment);
    const github = fields(value.github, ['repository', 'runId', 'runAttempt', 'job', 'jobId', 'role']);
    need(SELECTIONS.includes(value.selection), 'SELECTION');
    const selected = value.selection.replace(/^(?:desktop|full)-/, ''), role = kind === 'gate' ? 'linux-x64' : selected;
    const host = HOSTS[role];
    need(host !== undefined && github.role === role && github.job === (kind === 'gate' ? 'initial-recipient-gate' : 'populate') &&
        github.repository === REPOSITORY && environment.GITHUB_ACTIONS === 'true' &&
        environment.RUNNER_ENVIRONMENT === 'github-hosted' && environment.GITHUB_REPOSITORY === REPOSITORY &&
        environment.GITHUB_EVENT_NAME === 'workflow_dispatch' && environment.GITHUB_JOB === github.job &&
        environment.GITHUB_REF === REF && environment.GITHUB_WORKFLOW_SHA === value.source.commit &&
        environment.GITHUB_WORKFLOW_REF === REPOSITORY + '/' + WORKFLOW + '@' + REF &&
        environment.GITHUB_SERVER_URL === 'https://github.com' && environment.GITHUB_API_URL === 'https://api.github.com' &&
        environment.RUNNER_OS === host[0] && environment.RUNNER_ARCH === host[1], 'ORIGINAL_HOSTED_CONTEXT');
    for (const [name, env] of [['runId', 'GITHUB_RUN_ID'], ['runAttempt', 'GITHUB_RUN_ATTEMPT']]) {
        decimal(github[name], 1n); need(github[name] === environment[env], 'RUN_BINDING');
    }
    integer(github.jobId, 1n, INT64);
    need(environment.P2PKIT_INITIAL_BEFORE_OUTCOME === 'success' && environment.P2PKIT_INITIAL_SEAL_OUTCOME === 'success' &&
        digest(value.beforeSha256) === environment.P2PKIT_INITIAL_BEFORE_SHA256, 'ORIGINAL_BEFORE_STEP');
    const seed = fields(value.deadline, SEED);
    SEED.forEach((name, index) => need(seed[name] === environment[SEED_ENV[index]], 'ORIGINAL_SEED_ENV'));
    return window(value.originalWindow, kind, role, seed);
}
function window(value, kind, role, seed) {
    fields(value, ['schema', 'scope', 'clock', 'originalBootDigest', 'kind', 'originalJobBasisNs', 'jobEndNs',
        'startNs', 'workEndNs', 'nativeFinalEndNs', 'readEndNs', 'sealEndNs', 'uploadEndNs', 'afterEndNs']);
    fields(seed, SEED); digest(seed.initialSealSha256); digest(seed.initialSealBootSha256);
    const clock = fields(value.clock, ['role', 'domain', 'ticksPerSecond']);
    const frequency = integer(clock.ticksPerSecond, 1n, INT64);
    need(clock.role === role && clock.domain === DOMAINS[role] && (role === 'windows-x64' || frequency === NS) &&
        seed.initialSealClockRole === role && seed.initialSealClockDomain === clock.domain &&
        decimal(seed.initialSealClockTicksPerSecond, 1n, INT64) === frequency, 'CLOCK_IDENTITY');
    need(value.schema === 1 && value.scope === 'INITIAL_RECIPIENT_CUSTODY_ABSOLUTE_WINDOW_V1' &&
        value.kind === kind && value.originalBootDigest === seed.initialSealBootSha256, 'WINDOW_SCOPE');
    const basis = integer(value.originalJobBasisNs, -UINT64), start = integer(value.startNs),
        jobEnd = basis + (kind === 'gate' ? 360n : 5400n) * NS,
        work = minimum(start + 240n * NS, jobEnd - 180n * NS);
    need(basis <= start && start < work && jobEnd <= UINT64 && integer(value.jobEndNs) === jobEnd, 'WINDOW_BASIS');
    const names = ['workEndNs', 'nativeFinalEndNs', 'readEndNs', 'sealEndNs', 'uploadEndNs', 'afterEndNs'];
    [0n, 45n, 75n, 105n, 165n, 180n].forEach((seconds, index) =>
        need(integer(value[names[index]]) === work + seconds * NS, 'ORIGINAL_WINDOW_ARITHMETIC'));
    need(integer(value.afterEndNs) <= jobEnd && integer(value.sealEndNs) === decimal(seed.initialSealEndNs), 'WINDOW_SEED');
    return Object.freeze({seal: integer(value.sealEndNs), upload: integer(value.uploadEndNs), after: integer(value.afterEndNs)});
}
function members(value, zipBytes) {
    const rows = array(value, 4, 4); let total = 0, framing = 22;
    rows.forEach((supplied, index) => {
        const row = fields(supplied, ['name', 'bytes', 'sha256']);
        need(row.name === MEMBERS[index], 'MEMBER_ORDER'); digest(row.sha256);
        total += count(row.bytes, 1, index === 1 || index === 3 ? 65536 : 576 * 1024 * 1024);
        framing += 30 + 16 + 46 + 2 * MEMBERS[index].length;
    });
    need(total <= 576 * 1024 * 1024 && count(zipBytes, 1, ZIP_LIMIT) === total + framing, 'COMPLETE_ZIP_BOUND');
    return total;
}
function ready(raw, environment, nowMs) {
    const value = record(raw);
    fields(value, ['schema', 'scope', 'kind', 'selection', 'source', 'github', 'beforeSha256', 'carrierCloseSha256',
        'firstRawNs', 'deadline', 'originalWindow', 'workEndNs', 'closeEndNs', 'members', 'zipBytes', 'originals',
        'jobOriginal', 'observedAt', 'nativeFileRetirement', 'originalStepOutcome', 'qualification', ...UTC_FIELDS]);
    need(value.schema === 1 && value.scope === SCOPES.ready && value.nativeFileRetirement === 'PENDING_ORIGINAL_READERS' &&
        value.originalStepOutcome === 'NOT_OBSERVED' && value.qualification === 'NOT_ESTABLISHED', 'READY_SCOPE');
    const ends = identity(value, environment, value.kind), first = decimal(value.firstRawNs),
        close = minimum(first + 60n * NS, ends.upload), work = close - 5n * NS;
    need(first < ends.seal && ends.seal < work && work < close && close <= UINT64 &&
        decimal(value.workEndNs) === work && decimal(value.closeEndNs) === close, 'READY_CAPS');
    digest(value.carrierCloseSha256); members(value.members, value.zipBytes);
    const originals = fields(value.originals, ['eventSha256', 'policySha256', 'matchSha256']);
    Object.values(originals).forEach(digest); need(originals.policySha256 === POLICY_SHA256, 'ORIGINAL_POLICY_HASH');
    const job = array(value.jobOriginal, 4, 4);
    need(integer(job[0], 1n, INT64) === integer(value.github.jobId) && typeof job[2] === 'string' &&
        job[2] === environment.RUNNER_NAME && job[2].length > 0, 'READY_ORIGINAL_RUNNER');
    utc(job[1]); integer(job[3], 1n, INT64);
    const validity = currentUtc(value, nowMs), observed = count(value.observedAt, 1, 253402300799);
    need(validity.authorityStart <= observed && observed < validity.authorityEnd && observed <= Math.floor(nowMs / 1000),
        'READY_ORIGINAL_UTC');
    return value;
}
function headerVector(supplied, bodyBytes, nowMs) {
    const vector = array(supplied, 2, 128); need(vector.length % 2 === 0, 'HEADER_PAIRS');
    const values = Object.create(null); let size = 0;
    for (let index = 0; index < vector.length; index += 2) {
        const name = vector[index], value = vector[index + 1];
        need(typeof name === 'string' && /^[!#$%&'*+.^_`|~0-9A-Za-z-]+$/.test(name) &&
            typeof value === 'string' && /^[\t\x20-\x7e]*$/.test(value) && name.length + value.length + 2 <= 2048 &&
            !Object.hasOwn(values, name.toLowerCase()), 'HEADER_FIELDS');
        values[name.toLowerCase()] = value.trim(); size += name.length + value.length + 4;
    }
    need(size <= 16384 && ['application/json', 'application/json; charset=utf-8'].includes((values['content-type'] || '').toLowerCase()) &&
        (values['content-encoding'] || 'identity').toLowerCase() === 'identity' &&
        values['x-github-api-version-selected'] === '2022-11-28' && /^[A-Za-z0-9:-]{8,128}$/.test(values['x-github-request-id'] || ''),
    'HEADER_TYPE');
    need((!Object.hasOwn(values, 'age') || values.age === '0') &&
        ['warning', 'via', 'location', 'content-range', 'retry-after'].every(name => !Object.hasOwn(values, name)) &&
        ['MISS', 'BYPASS'].includes((Object.hasOwn(values, 'x-cache') ? values['x-cache'] : 'MISS').toUpperCase()),
    'HEADER_FRESHNESS');
    const cache = Object.create(null);
    for (const component of (values['cache-control'] || '').toLowerCase().split(',')) {
        const part = component.trim(), at = part.indexOf('='), name = at < 0 ? part : part.slice(0, at), item = part.slice(at + 1);
        need(!Object.hasOwn(cache, name) && ['public', 'max-age', 's-maxage'].includes(name) &&
            (name === 'public' ? at === -1 : at !== -1 && item === '60'), 'HEADER_CACHE'); cache[name] = true;
    }
    need(Object.keys(cache).length === 3 && typeof values.date === 'string' && values.date.length === 29, 'HEADER_CACHE_DATE');
    const dateMs = Date.parse(values.date);
    need(Number.isSafeInteger(dateMs) && dateMs > 0 && dateMs <= 253402300799000 &&
        new Date(dateMs).toUTCString() === values.date && dateMs <= nowMs && nowMs < dateMs + 61000,
    'HEADER_DATE');
    // The maintained Python contract uses integer seconds, inclusive Date+60.
    need(Math.floor(nowMs / 1000) <= dateMs / 1000 + 60, 'HEADER_CURRENT_DATE');
    if (Object.hasOwn(values, 'content-length')) need(/^[0-9]{1,7}$/.test(values['content-length']) &&
        Number(values['content-length']) === bodyBytes && !Object.hasOwn(values, 'transfer-encoding'), 'HEADER_LENGTH');
    if (Object.hasOwn(values, 'transfer-encoding')) need(values['transfer-encoding'].toLowerCase() === 'chunked', 'HEADER_TRANSFER');
    return Object.freeze({date: values.date, epoch: dateMs / 1000,
        sha256: sha(Buffer.from(JSON.stringify(vector), 'utf8'))});
}
function serviceSteps(job, date, stage) {
    need(stage === 'upload' || stage === 'after', 'STEP_STAGE');
    const began = utc(job.started_at), rows = array(job.steps, 1, 256), selected = {}, names = new Set();
    const expected = stage === 'upload' ? STEPS.slice(0, 5) : STEPS; let previous = 0;
    need(began <= date, 'JOB_STARTED');
    for (const supplied of rows) {
        const row = fields(supplied, ['name', 'status', 'conclusion', 'number', 'started_at', 'completed_at']);
        need(typeof row.name === 'string' && row.name.length > 0 && row.name.length <= 256 &&
            !/[\x00-\x1f\x7f]/.test(row.name) && !names.has(row.name), 'STEP_NAME'); names.add(row.name);
        previous = count(row.number, previous + 1, 2147483647);
        if (row.status === 'queued') need(row.conclusion === null && row.started_at === null && row.completed_at === null, 'STEP_QUEUED');
        else if (row.status === 'in_progress') need(row.conclusion === null && row.completed_at === null &&
            began <= utc(row.started_at) && utc(row.started_at) <= date, 'STEP_CURRENT');
        else {
            need(row.status === 'completed' && ['success', 'failure', 'neutral', 'cancelled', 'skipped', 'timed_out', 'action_required']
                .includes(row.conclusion), 'STEP_COMPLETED');
            if (row.started_at === null || row.completed_at === null) need(row.conclusion === 'skipped' &&
                row.started_at === null && row.completed_at === null, 'STEP_SKIPPED_TIMES');
            else need(began <= utc(row.started_at) && utc(row.started_at) <= utc(row.completed_at) &&
                utc(row.completed_at) <= date, 'STEP_TIMES');
        }
        for (const [role, name] of expected) if (row.name === name) selected[role] = row;
    }
    need(Object.keys(selected).length === expected.length, 'STEP_MISSING');
    const ordered = expected.map(([role]) => selected[role]);
    for (let index = 0; index < ordered.length; index++) {
        const row = ordered[index];
        need(index === ordered.length - 1 ? row.status === 'in_progress' :
            row.status === 'completed' && row.conclusion === 'success' && typeof row.started_at === 'string' &&
                typeof row.completed_at === 'string', 'STEP_REQUIRED_SUCCESS');
        if (index) need(integer(row.number) > integer(ordered[index - 1].number) &&
            utc(ordered[index - 1].completed_at) <= utc(row.started_at), 'STEP_ORIGINAL_ORDER');
    }
    need(integer(selected.upload.number) === integer(selected.before.number) + 1n &&
        (stage === 'upload' || integer(selected.after.number) === integer(selected.upload.number) + 1n), 'STEP_ADJACENCY');
    const current = integer(ordered[ordered.length - 1].number);
    need(rows.every(row => integer(row.number) === current || row.status ===
        (integer(row.number) < current ? 'completed' : 'queued')), 'STEP_UNIQUE_FRONTIER');
    return Object.freeze(selected);
}
function serviceJob(readyValue, body, vector, environment, stage, nowMs) {
    const raw = bytes(body, BODY), job = parse(raw, BODY), header = headerVector(vector, raw.length, nowMs),
        github = readyValue.github, original = readyValue.jobOriginal;
    need(integer(job.id, 1n, INT64) === integer(github.jobId) &&
        integer(job.run_id, 1n) === decimal(github.runId, 1n) && integer(job.run_attempt, 1n) === decimal(github.runAttempt, 1n),
    'JOB_IDENTITY');
    need(job.name === github.job && job.head_sha === readyValue.source.commit && job.head_branch === REF.slice(11) &&
        job.url === 'https://api.github.com/repos/' + REPOSITORY + '/actions/jobs/' + String(github.jobId) &&
        job.run_url === 'https://api.github.com/repos/' + REPOSITORY + '/actions/runs/' + github.runId &&
        job.status === 'in_progress' && job.conclusion === null && job.completed_at === null, 'JOB_SOURCE_OR_CURRENT');
    need(Array.isArray(original) && original.length === 4 && integer(job.id) === integer(original[0]) &&
        job.started_at === original[1] && job.runner_name === original[2] && job.runner_name === environment.RUNNER_NAME &&
        integer(job.runner_id, 1n, INT64) === integer(original[3], 1n, INT64), 'ORIGINAL_RUNNER_CONTINUITY');
    const expected = readyValue.kind === 'gate' ? 'ubuntu-24.04' : HOSTS[github.role][2];
    need(array(job.labels, 1, 1)[0] === expected && integer(job.runner_group_id) === 0n &&
        job.runner_group_name === 'GitHub Actions', 'ORIGINAL_HOSTED_SELECTOR');
    const selected = serviceSteps(job, header.epoch, stage);
    return Object.freeze({jobId: github.jobId, bodySha256: sha(raw), rawHeaderVectorSha256: header.sha256,
        serviceDate: header.date, serviceEpoch: header.epoch, steps: selected});
}
function artifactName(value) {
    return 'initial-recipient-custody-' + value.github.runId + '-' + value.github.runAttempt + '-' + value.kind + '-' + value.selection;
}

const READER_FIELDS = Object.freeze(['scope', 'transport', 'code', 'preSpawnLocalNs', 'returnedLocalNs',
    'originalChildCloseObserved', 'originalExitZeroObserved', 'stdinFinishObserved', 'stdinEndCallbackObserved',
    'stdoutEndObserved', 'stderrEndObserved', 'originalPipeCloses', 'stderrBytes', 'readySha256', 'finalSha256',
    'zipBytes', 'zipSha256', 'nativeFileRetirement', 'originalStepOutcome', 'qualification']);
const OBSERVER_FIELDS = Object.freeze(['scope', 'stage', 'transport', 'code', 'requestSha256', 'jobId', 'artifactId',
    'enteredNs', 'lastObservationNs', 'agentDestroyReturned', 'originalResourceCount', 'requests',
    'originalStepOutcome', 'qualification']);
const OBSERVER_ROW_FIELDS = Object.freeze(['kind', 'id', 'startedNs', 'endNs', 'closedNs', 'status', 'bodyBytes',
    'bodySha256', 'rawHeaderVectorSha256', 'date', 'dateEpochSeconds', 'requestFinishObserved',
    'requestEndCallbackObserved', 'tlsSecureConnectObserved', 'tlsAuthorizedObserved', 'responseEndObserved',
    'requestCloseObserved', 'responseCloseObserved', 'socketCloseObserved']);
const TRANSPORT_FIELDS = Object.freeze(['scope', 'transport', 'code', 'requestSha256', 'artifactName', 'inputBytes',
    'sentBytes', 'observedZipSha256', 'submittedFinalizeHash', 'artifactId', 'createInvokedAt', 'requestedExpiresAt',
    'requestedRetentionDays', 'enteredNs', 'returnedObservationNs', 'inputEndObserved', 'inputCloseObserved',
    'requests', 'serviceDigest', 'actualServiceExpiry', 'nativeFileRetirement', 'originalRunnerOutcome', 'qualification']);
const TRANSPORT_ROW_FIELDS = Object.freeze(['kind', 'startNs', 'status', 'bodyBytes', 'responseBytes',
    'requestFinished', 'requestEndCallback', 'responseEndObserved', 'requestCloseObserved',
    'responseCloseObserved', 'socketCloseObserved']);

function localBounds(readyValue, preSpawnLocalNs) {
    const pre = integer(preSpawnLocalNs), first = decimal(readyValue.firstRawNs),
        seal = integer(readyValue.originalWindow.sealEndNs), upload = integer(readyValue.originalWindow.uploadEndNs),
        start = integer(pre + seal - first), close = minimum(integer(pre + 60n * NS), integer(pre + upload - first)),
        work = close - 5n * NS;
    need(pre < start && start < work && work < close &&
        decimal(readyValue.workEndNs) === first + work - pre &&
        decimal(readyValue.closeEndNs) === first + close - pre, 'DIRECTED_LOCAL_BOUNDS');
    return Object.freeze({preSpawnLocalNs: pre, startByNs: start, workEndNs: work, closeEndNs: close});
}
function readerClosed(supplied, readyRaw, finalRaw, readyValue, bounds) {
    const row = fields(supplied, READER_FIELDS), final = record(finalRaw);
    fields(final, ['schema', 'scope', 'beforeSha256', 'readySha256', 'zipBytes', 'zipSha256',
        'nativeCloseSha256', 'closedNs', 'nativeFileRetirement', 'originalReaderOutcome', 'qualification']);
    const closes = fields(row.originalPipeCloses, ['stdin', 'stdout', 'stderr']);
    need(row.scope === 'INITIAL_ARTIFACT_FIXED_READER_TRANSPORT_ONLY' && row.transport === 'closed' && row.code === null &&
        row.nativeFileRetirement === 'FIXED_HELPER_RETURN_REQUIRES_CALLER_VALIDATION' &&
        row.originalStepOutcome === 'NOT_OBSERVED' && row.qualification === 'NOT_ESTABLISHED' &&
        ['originalChildCloseObserved', 'originalExitZeroObserved', 'stdinFinishObserved', 'stdinEndCallbackObserved',
            'stdoutEndObserved', 'stderrEndObserved'].every(name => row[name] === true) &&
        Object.values(closes).every(value => value === true) && row.stderrBytes === 0, 'READER_COMPLETE_CLOSE');
    const returned = decimal(row.returnedLocalNs);
    need(decimal(row.preSpawnLocalNs) === bounds.preSpawnLocalNs && returned >= bounds.preSpawnLocalNs &&
        returned < bounds.workEndNs && row.readySha256 === sha(readyRaw) && row.finalSha256 === sha(finalRaw),
    'READER_ORIGINAL_BOUNDS');
    need(final.schema === 1 && final.scope === SCOPES.final && final.beforeSha256 === readyValue.beforeSha256 &&
        final.readySha256 === row.readySha256 && final.zipBytes === readyValue.zipBytes && row.zipBytes === final.zipBytes &&
        digest(final.zipSha256) === row.zipSha256 && final.nativeFileRetirement === 'KNOWN_NATIVE_CLOSE' &&
        final.originalReaderOutcome === 'PENDING_ENCLOSING_PROCESS_CLOSE' && final.qualification === 'NOT_ESTABLISHED',
    'READER_FINAL_BINDING');
    digest(final.nativeCloseSha256);
    need(decimal(final.closedNs) >= decimal(readyValue.firstRawNs) &&
        decimal(final.closedNs) < decimal(readyValue.workEndNs), 'READER_FINAL_ORIGINAL_RAW');
    return final;
}
function originalRows(supplied, stage, jobId, artifactId, nowMs) {
    need(stage === 'before' || stage === 'after', 'ORIGINALS_STAGE');
    const expected = stage === 'before' ? [['job', jobId]] : [['job', jobId], ['artifact', artifactId]];
    return Object.freeze(array(supplied, expected.length, expected.length).map((raw, index) => {
        const row = fields(raw, ['kind', 'id', 'body', 'rawHeaderVector']), [kind, id] = expected[index];
        need(row.kind === kind && row.id === id && decimal(row.id, 1n, INT64) > 0n, 'ORIGINALS_ORDER');
        bytes(row.body, BODY); headerVector(row.rawHeaderVector, row.body.length, nowMs);
        return row;
    }));
}
function observerClosed(supplied, originals, readyValue, bounds, stage, requestSha256, nowMs) {
    const row = fields(supplied, OBSERVER_FIELDS), jobId = String(readyValue.github.jobId),
        artifactId = stage === 'after' ? readyValue.artifactId : null,
        actual = originalRows(originals, stage, jobId, artifactId, nowMs),
        requests = array(row.requests, actual.length, actual.length),
        phaseEnd = stage === 'before' ? bounds.startByNs : bounds.endNs;
    need(row.scope === 'INITIAL_ARTIFACT_PUBLIC_TERMINAL_TRANSPORT_ONLY_V1' && row.stage === stage &&
        row.transport === 'closed' && row.code === null && row.requestSha256 === digest(requestSha256) &&
        row.jobId === jobId && row.artifactId === artifactId && row.agentDestroyReturned === true &&
        row.originalResourceCount === 3 * actual.length && row.originalStepOutcome === 'NOT_OBSERVED' &&
        row.qualification === 'NOT_ESTABLISHED', 'OBSERVER_COMPLETE_CLOSE');
    const entered = decimal(row.enteredNs), returned = decimal(row.lastObservationNs);
    need(bounds.preSpawnLocalNs <= entered && entered <= returned && returned < phaseEnd, 'OBSERVER_ORIGINAL_BOUNDS');
    let previous = entered;
    requests.forEach((suppliedRequest, index) => {
        const request = fields(suppliedRequest, OBSERVER_ROW_FIELDS), original = actual[index],
            header = headerVector(original.rawHeaderVector, original.body.length, nowMs),
            start = decimal(request.startedNs), end = decimal(request.endNs), close = decimal(request.closedNs);
        need(request.kind === original.kind && request.id === original.id && request.status === 200 &&
            request.bodyBytes === original.body.length && request.bodySha256 === sha(original.body) &&
            request.rawHeaderVectorSha256 === header.sha256 && request.date === header.date &&
            request.dateEpochSeconds === header.epoch, 'OBSERVER_ORIGINAL_HTTP');
        need(OBSERVER_ROW_FIELDS.slice(11).every(name => request[name] === true), 'OBSERVER_ALL_ORIGINAL_CLOSES');
        need(previous <= start && start <= close && end === minimum(phaseEnd, integer(start + 15n * NS)) &&
            close < end && close <= returned, 'OBSERVER_REQUEST_CHRONOLOGY');
        previous = close;
    });
    return row;
}
function transportClosed(supplied, readyValue, bounds, readerValue, beforeValue, nowMs) {
    const row = fields(supplied, TRANSPORT_FIELDS), name = artifactName(readyValue), zipBytes = readyValue.zipBytes;
    need(row.scope === 'INITIAL_ARTIFACT_STREAM_TRANSPORT_ONLY' && row.transport === 'closed' && row.code === null &&
        row.requestSha256 === readerValue.readySha256 && row.artifactName === name && row.inputBytes === zipBytes &&
        row.sentBytes === zipBytes && row.observedZipSha256 === digest(readerValue.zipSha256) &&
        row.submittedFinalizeHash === 'sha256:' + row.observedZipSha256 && row.requestedRetentionDays === 14 &&
        row.inputEndObserved === true && row.inputCloseObserved === true &&
        row.serviceDigest === 'NOT_OBSERVED' && row.actualServiceExpiry === 'NOT_OBSERVED' &&
        row.nativeFileRetirement === 'NOT_ESTABLISHED' && row.originalRunnerOutcome === 'NOT_OBSERVED' &&
        row.qualification === 'NOT_ESTABLISHED', 'TRANSPORT_COMPLETE_CLOSE');
    decimal(row.artifactId, 1n, INT64);
    const entered = decimal(row.enteredNs), returned = decimal(row.returnedObservationNs),
        created = utc(row.createInvokedAt, true), expiry = utc(row.requestedExpiresAt, true);
    need(decimal(beforeValue.lastObservationNs) <= entered && entered < bounds.startByNs && entered <= returned &&
        entered <= decimal(readerValue.returnedLocalNs) && decimal(readerValue.returnedLocalNs) <= returned && returned < bounds.closeEndNs &&
        created <= count(nowMs, 1, 253402300799000) && expiry - created === 14 * 86400000, 'TRANSPORT_ORIGINAL_BOUNDS');
    const blocks = Math.ceil(count(zipBytes, 1, ZIP_LIMIT) / BLOCK), requests = array(row.requests, blocks + 3, blocks + 3);
    const list = '<?xml version="1.0" encoding="utf-8"?><BlockList>' + Array.from({length: blocks}, (_, index) =>
        '<Uncommitted>' + Buffer.from(String(index).padStart(6, '0'), 'ascii').toString('base64') + '</Uncommitted>')
        .join('') + '</BlockList>';
    // Both real service backend GUID strings have exactly36 ASCII bytes. These
    // are byte-count formulas only; no reconstructed request is evidence.
    const createBytes = Buffer.byteLength(JSON.stringify({workflow_run_backend_id: '', workflow_job_run_backend_id: '',
        name, version: 7, mime_type: 'application/zip', expires_at: row.requestedExpiresAt}), 'utf8') + 72;
    const finalizeBytes = Buffer.byteLength(JSON.stringify({workflow_run_backend_id: '', workflow_job_run_backend_id: '',
        name, size: String(zipBytes), hash: row.submittedFinalizeHash}), 'utf8') + 72;
    let previous = entered;
    requests.forEach((suppliedRequest, index) => {
        const request = fields(suppliedRequest, TRANSPORT_ROW_FIELDS), start = decimal(request.startNs),
            kind = index === 0 ? 'create' : index <= blocks ? 'block' : index === blocks + 1 ? 'blocklist' : 'finalize',
            service = kind === 'create' || kind === 'finalize',
            bodyBytes = kind === 'create' ? createBytes : kind === 'finalize' ? finalizeBytes :
                kind === 'blocklist' ? Buffer.byteLength(list, 'ascii') : Math.min(BLOCK, zipBytes - (index - 1) * BLOCK);
        need(request.kind === kind && request.status === (service ? 200 : 201) && request.bodyBytes === bodyBytes &&
            TRANSPORT_ROW_FIELDS.slice(5).every(field => request[field] === true), 'TRANSPORT_REQUEST_ROSTER');
        count(request.responseBytes, service ? 1 : 0, service ? 65536 : 0);
        need(previous <= start && start < bounds.workEndNs && start <= returned &&
            (index !== 0 || start < bounds.startByNs), 'TRANSPORT_REQUEST_CHRONOLOGY');
        previous = start;
    });
    return row;
}
function finishInput({readyRaw, finalRaw, readerValue, transportValue, beforeValue, originals}, readyValue, bounds, nowMs) {
    const final = readerClosed(readerValue, readyRaw, finalRaw, readyValue, bounds);
    observerClosed(beforeValue, originals, readyValue, bounds, 'before', sha(readyRaw), nowMs);
    transportClosed(transportValue, readyValue, bounds, readerValue, beforeValue, nowMs);
    need(final.zipSha256 === transportValue.observedZipSha256, 'FINAL_TRANSPORT_ZIP');
    const rows = originalRows(originals, 'before', String(readyValue.github.jobId), null, nowMs);
    return encode({schema: 1, scope: SCOPES.finishInput, readerReadyBase64: bytes(readyRaw, RECORD).toString('base64'),
        readerFinalBase64: bytes(finalRaw, RECORD).toString('base64'), readerClosed: readerValue,
        transportClosed: transportValue, beforeClosed: beforeValue, beforeOriginals: rows.map(row => ({kind: row.kind,
            id: row.id, bodyBase64: row.body.toString('base64'), rawHeaderVector: row.rawHeaderVector}))}, INPUT - 5);
}
function afterReady(raw, environment, nowMs) {
    const value = record(raw);
    fields(value, ['schema', 'scope', 'kind', 'selection', 'source', 'github', 'beforeSha256', 'uploadSha256',
        'deadline', 'originalWindow', 'firstRawNs', 'endNs', 'artifactId', ...UTC_FIELDS,
        'observedAt', 'originalStepOutcome', 'qualification']);
    need(value.schema === 1 && value.scope === SCOPES.afterReady && value.originalStepOutcome === 'NOT_OBSERVED' &&
        value.qualification === 'NOT_ESTABLISHED', 'AFTER_READY_SCOPE');
    const ends = identity(value, environment, value.kind), first = decimal(value.firstRawNs), end = decimal(value.endNs);
    need(first < ends.upload && first < end && end === minimum(integer(first + 15n * NS), ends.after), 'AFTER_RAW_CAP');
    decimal(value.artifactId, 1n, INT64);
    need(digest(value.uploadSha256) === environment.P2PKIT_INITIAL_UPLOAD_SHA256 &&
        environment.P2PKIT_INITIAL_UPLOAD_OUTCOME === 'success', 'AFTER_ORIGINAL_UPLOAD');
    for (const name of ['P2PKIT_INITIAL_UPLOAD_DIRECTORY_SHA256', 'P2PKIT_INITIAL_UPLOAD_FILE_METADATA_SHA256',
        'P2PKIT_INITIAL_UPLOAD_OWNER_CLOSE_SHA256']) digest(environment[name]);
    const validity = currentUtc(value, nowMs), observed = count(value.observedAt, 1, 253402300799);
    need(validity.authorityStart <= observed && observed < validity.authorityEnd && observed <= Math.floor(nowMs / 1000),
        'AFTER_READY_ORIGINAL_UTC');
    return value;
}
function afterBounds(readyValue, preSpawnLocalNs) {
    const pre = integer(preSpawnLocalNs), first = decimal(readyValue.firstRawNs), end = decimal(readyValue.endNs),
        localEnd = integer(pre + end - first);
    need(pre < localEnd && localEnd <= integer(pre + 15n * NS), 'AFTER_DIRECTED_LOCAL_BOUNDS');
    return Object.freeze({preSpawnLocalNs: pre, endNs: localEnd});
}
function afterInput({afterValue, originals}, readyRaw, readyValue, bounds, nowMs) {
    observerClosed(afterValue, originals, readyValue, bounds, 'after', sha(readyRaw), nowMs);
    const rows = originalRows(originals, 'after', String(readyValue.github.jobId), readyValue.artifactId, nowMs);
    // The SAME native after helper retains R and rechecks complete service
    // job/runner/Step/artifact semantics against actual independently read K/U.
    // R intentionally does not export the private original runner tuple.
    return encode({schema: 1, scope: SCOPES.afterInput, afterClosed: afterValue,
        afterOriginals: rows.map(row => ({kind: row.kind, id: row.id, bodyBase64: row.body.toString('base64'),
            rawHeaderVector: row.rawHeaderVector}))}, INPUT - 5);
}

const PENDING_FIELDS = Object.freeze(['schema', 'scope', 'kind', 'selection', 'source', 'github', 'beforeSha256', 'readySha256',
    'originalWindow', 'deadline', 'originals', 'members', ...UTC_FIELDS, 'observedAt', 'artifact', 'times', 'observations',
    'writerReturn', 'originalHelperOutcome', 'originalStepOutcome', 'qualification', 'privateOriginals']);
const ARTIFACT_FIELDS = Object.freeze(['id', 'name', 'zipBytes', 'zipSha256', 'createInvokedAt', 'requestedExpiresAt',
    'requestedRetentionDays']);
const U_TIMES = Object.freeze(['firstRawNs', 'streamClosedNs', 'finishFirstRawNs', 'pendingPreparedNs', 'workEndNs', 'closeEndNs',
    'readerPreSpawnLocalNs', 'readerReturnedLocalNs', 'beforeEnteredLocalNs', 'beforeReturnedLocalNs',
    'transportEnteredLocalNs', 'transportReturnedLocalNs']);
const A_TIMES = Object.freeze(['firstRawNs', 'endNs', 'pendingPreparedNs', 'observerEnteredLocalNs', 'observerReturnedLocalNs']);
const U_HASHES = Object.freeze(['streamFinalSha256', 'readerClosedSha256', 'transportClosedSha256', 'beforeClosedSha256',
    'beforeBodySha256', 'beforeHeaderVectorSha256']);
const A_HASHES = Object.freeze(['afterClosedSha256', 'jobBodySha256', 'jobHeaderVectorSha256',
    'artifactBodySha256', 'artifactHeaderVectorSha256']);
const U_OBSERVATIONS = Object.freeze([...U_HASHES, 'beforeServiceEpoch', 'beforeStepNumber', 'uploadStepNumber', 'transportRequestCount']);
const A_OBSERVATIONS = Object.freeze([...A_HASHES, 'jobServiceEpoch', 'artifactServiceEpoch',
    'beforeStepNumber', 'uploadStepNumber', 'afterStepNumber', 'observerRequestCount']);
const CARRIER_FIELDS = Object.freeze(['directoryIdentitySha256', 'fileMetadataSha256', 'fileOwnerCloseSha256']);
const RESULT_FIELDS = Object.freeze(['schema', 'scope', 'kind', 'selection', 'source', 'github', 'beforeSha256', 'readySha256',
    'inputSha256', 'pending', 'pendingSha256', ...CARRIER_FIELDS, 'closedNs', 'artifactId',
    'originalHelperOutcome', 'originalStepOutcome', 'qualification']);

function pendingShape(value, mode) {
    need(mode === 'upload' || mode === 'after', 'PENDING_MODE');
    const upload = mode === 'upload';
    fields(value, [...PENDING_FIELDS, ...(upload ? ['carrierCloseSha256'] : ['uploadSha256', 'uploadCarrier'])]);
    need(value.schema === 1 && value.scope === (upload ? 'INITIAL_ARTIFACT_UPLOAD_PENDING_ORIGINAL_STEP_RETURN_V1' :
        'INITIAL_ARTIFACT_DELIVERY_PENDING_ORIGINAL_STEP_RETURN_V1') &&
        (value.kind === 'gate' || value.kind === 'worker') && SELECTIONS.includes(value.selection) &&
        value.writerReturn === 'PENDING_OWNER_CLOSE' && value.originalHelperOutcome === 'PENDING_ENCLOSING_PROCESS_CLOSE' &&
        value.originalStepOutcome === 'NOT_OBSERVED' && value.qualification === 'NOT_ESTABLISHED' &&
        value.privateOriginals === 'TERMINAL_SELF_TAIL_NOT_DELIVERED', 'PENDING_SAFE_SCOPE');
    const src = fields(value.source, ['commit', 'tree']);
    need(Object.values(src).every(item => typeof item === 'string' && /^[0-9a-f]{40}$/.test(item)), 'PENDING_SAFE_SOURCE');
    const github = fields(value.github, ['repository', 'runId', 'runAttempt', 'job', 'jobId', 'role']),
        role = value.kind === 'gate' ? 'linux-x64' : value.selection.replace(/^(?:desktop|full)-/, '');
    need(github.repository === REPOSITORY && github.role === role &&
        github.job === (value.kind === 'gate' ? 'initial-recipient-gate' : 'populate'), 'PENDING_SAFE_GITHUB');
    decimal(github.runId, 1n); decimal(github.runAttempt, 1n); integer(github.jobId, 1n, INT64);
    digest(value.beforeSha256); digest(value.readySha256);
    window(value.originalWindow, value.kind, role, value.deadline);
    const originals = fields(value.originals, ['eventSha256', 'policySha256', 'matchSha256']);
    Object.values(originals).forEach(digest); need(originals.policySha256 === POLICY_SHA256, 'PENDING_POLICY');
    const observedAt = count(value.observedAt, 1, 253402300799); currentUtc(value, observedAt * 1000);
    const artifact = fields(value.artifact, [...ARTIFACT_FIELDS, ...(upload ? [] : ['createdAt', 'expiresAt', 'serviceDigest'])]);
    decimal(artifact.id, 1n, INT64); digest(artifact.zipSha256);
    need(artifact.name === artifactName(value) && artifact.requestedRetentionDays === 14, 'PENDING_ARTIFACT_IDENTITY');
    members(value.members, artifact.zipBytes);
    const created = utc(artifact.createInvokedAt, true), requested = utc(artifact.requestedExpiresAt, true);
    need(requested - created === 14 * 86400000 && Math.floor(created / 1000) <= observedAt, 'PENDING_ORIGINAL_RETENTION');
    const times = fields(value.times, upload ? U_TIMES : A_TIMES); Object.values(times).forEach(item => decimal(item));
    const observations = fields(value.observations, upload ? U_OBSERVATIONS : A_OBSERVATIONS);
    (upload ? U_HASHES : A_HASHES).forEach(name => digest(observations[name]));
    for (const name of upload ? ['beforeServiceEpoch'] : ['jobServiceEpoch', 'artifactServiceEpoch']) {
        const serviceAt = count(observations[name], 1, 253402300799);
        need(serviceAt <= observedAt && observedAt <= serviceAt + 60, 'PENDING_SERVICE_CURRENT');
    }
    for (const name of upload ? ['beforeStepNumber', 'uploadStepNumber'] : ['beforeStepNumber', 'uploadStepNumber', 'afterStepNumber'])
        count(observations[name], 1, 2147483647);
    need(observations.uploadStepNumber === observations.beforeStepNumber + 1 &&
        (upload || observations.afterStepNumber === observations.uploadStepNumber + 1), 'PENDING_ADJACENCY');
    if (upload) {
        digest(value.carrierCloseSha256);
        need(observations.transportRequestCount === 3 + Math.ceil(artifact.zipBytes / BLOCK) &&
            observations.transportRequestCount <= 67, 'PENDING_COMPLETE_REQUEST_COUNT');
        const first = decimal(times.firstRawNs), seal = integer(value.originalWindow.sealEndNs),
            close = minimum(integer(first + 60n * NS), integer(value.originalWindow.uploadEndNs)), work = close - 5n * NS;
        need(first < seal && seal < work && decimal(times.workEndNs) === work && decimal(times.closeEndNs) === close &&
            first <= decimal(times.streamClosedNs) && decimal(times.streamClosedNs) <= decimal(times.finishFirstRawNs) &&
            decimal(times.finishFirstRawNs) <= decimal(times.pendingPreparedNs) && decimal(times.pendingPreparedNs) < work,
        'PENDING_U_ORIGINAL_RAW');
        const pre = decimal(times.readerPreSpawnLocalNs), beforeEnter = decimal(times.beforeEnteredLocalNs),
            beforeReturn = decimal(times.beforeReturnedLocalNs), transportEnter = decimal(times.transportEnteredLocalNs),
            readerReturn = decimal(times.readerReturnedLocalNs), transportReturn = decimal(times.transportReturnedLocalNs);
        need(pre <= beforeEnter && beforeEnter <= beforeReturn && beforeReturn <= transportEnter &&
            transportEnter <= readerReturn && readerReturn <= transportReturn && beforeReturn < pre + seal - first &&
            readerReturn < pre + work - first && transportReturn < pre + close - first, 'PENDING_U_ORIGINAL_LOCAL');
    } else {
        digest(value.uploadSha256);
        Object.values(fields(value.uploadCarrier, CARRIER_FIELDS)).forEach(digest);
        need(observations.observerRequestCount === 2, 'PENDING_AFTER_REQUEST_COUNT');
        const first = decimal(times.firstRawNs), end = decimal(times.endNs), enter = decimal(times.observerEnteredLocalNs),
            returned = decimal(times.observerReturnedLocalNs);
        need(first < integer(value.originalWindow.uploadEndNs) &&
            end === minimum(integer(first + 15n * NS), integer(value.originalWindow.afterEndNs)) &&
            first <= decimal(times.pendingPreparedNs) && decimal(times.pendingPreparedNs) < end &&
            enter <= returned && returned - enter < 15n * NS, 'PENDING_A_ORIGINAL_BOUNDS');
        const serviceCreated = utc(artifact.createdAt), serviceExpires = utc(artifact.expiresAt);
        need(serviceCreated >= Math.floor(created / 1000) && serviceCreated <= observedAt && observedAt < serviceExpires &&
            serviceExpires <= serviceCreated + 14 * 86400 && serviceExpires * 1000 <= requested &&
            artifact.serviceDigest === 'sha256:' + artifact.zipSha256, 'PENDING_SERVICE_RETENTION');
    }
    return value;
}
function decodedOriginals(supplied, stage, jobId, artifactId, nowMs) {
    const expected = stage === 'before' ? [['job', jobId]] : [['job', jobId], ['artifact', artifactId]];
    const rows = array(supplied, expected.length, expected.length).map((value, index) => {
        const row = fields(value, ['kind', 'id', 'bodyBase64', 'rawHeaderVector']), [kind, id] = expected[index];
        need(row.kind === kind && row.id === id, 'INPUT_ORIGINAL_ORDER');
        headerVector(row.rawHeaderVector, base64Size(row.bodyBase64, BODY), nowMs); return row;
    });
    // Every roster/encoded bound is checked BEFORE either original decode.
    return Object.freeze(rows.map(row => Object.freeze({kind: row.kind, id: row.id,
        body: base64(row.bodyBase64, BODY), rawHeaderVector: row.rawHeaderVector})));
}
function afterServiceJob(readyValue, original, environment, nowMs) {
    const job = parse(original.body, BODY), header = headerVector(original.rawHeaderVector, original.body.length, nowMs),
        github = readyValue.github;
    need(integer(job.id, 1n, INT64) === integer(github.jobId) && integer(job.run_id, 1n) === decimal(github.runId, 1n) &&
        integer(job.run_attempt, 1n) === decimal(github.runAttempt, 1n) && job.name === github.job &&
        job.head_sha === readyValue.source.commit && job.head_branch === REF.slice(11) &&
        job.url === 'https://api.github.com/repos/' + REPOSITORY + '/actions/jobs/' + String(github.jobId) &&
        job.run_url === 'https://api.github.com/repos/' + REPOSITORY + '/actions/runs/' + github.runId &&
        job.status === 'in_progress' && job.conclusion === null && job.completed_at === null, 'AFTER_JOB_IDENTITY');
    need(job.runner_name === environment.RUNNER_NAME && integer(job.runner_id, 1n, INT64) > 0n &&
        array(job.labels, 1, 1)[0] === (readyValue.kind === 'gate' ? 'ubuntu-24.04' : HOSTS[github.role][2]) &&
        integer(job.runner_group_id) === 0n && job.runner_group_name === 'GitHub Actions', 'AFTER_CURRENT_RUNNER');
    // The original historical runner/start tuple is deliberately absent from
    // after-R. ONLY the same native A helper checks it against actual K; do not
    // manufacture a tuple from this response and call that continuity.
    return Object.freeze({steps: serviceSteps(job, header.epoch, 'after'), serviceEpoch: header.epoch,
        bodySha256: sha(original.body), rawHeaderVectorSha256: header.sha256});
}
function serviceArtifact(pending, original, nowMs) {
    const item = parse(original.body, BODY), artifact = pending.artifact,
        header = headerVector(original.rawHeaderVector, original.body.length, nowMs),
        location = 'https://api.github.com/repos/' + REPOSITORY + '/actions/artifacts/' + artifact.id;
    need(integer(item.id, 1n, INT64) === decimal(artifact.id, 1n, INT64) && item.name === artifact.name &&
        item.size_in_bytes === artifact.zipBytes && item.digest === artifact.serviceDigest && item.expired === false &&
        item.url === location && item.archive_download_url === location + '/zip', 'AFTER_ARTIFACT_IDENTITY');
    const workflow = item.workflow_run;
    need(workflow !== null && typeof workflow === 'object' && integer(workflow.id, 1n) === decimal(pending.github.runId, 1n) &&
        workflow.head_sha === pending.source.commit && workflow.head_branch === REF.slice(11), 'AFTER_ARTIFACT_SOURCE');
    const created = utc(item.created_at), expires = utc(item.expires_at), observed = Math.floor(nowMs / 1000);
    need(item.created_at === artifact.createdAt && item.expires_at === artifact.expiresAt &&
        created >= Math.floor(utc(artifact.createInvokedAt, true) / 1000) && created <= observed && observed < expires &&
        expires <= created + 14 * 86400 && expires * 1000 <= utc(artifact.requestedExpiresAt, true), 'AFTER_ARTIFACT_EXPIRY');
    return Object.freeze({serviceEpoch: header.epoch, bodySha256: sha(original.body), rawHeaderVectorSha256: header.sha256});
}
function finiteResult(raw, context) {
    const {mode, readyRaw, readyValue, bounds, inputRaw, artifactId, environment, nowMs} = fields(context,
        ['mode', 'readyRaw', 'readyValue', 'bounds', 'inputRaw', 'artifactId', 'environment', 'nowMs']);
    need(mode === 'upload' || mode === 'after', 'RESULT_MODE');
    const upload = mode === 'upload', result = record(raw), pending = result.pending, input = record(inputRaw, INPUT - 5);
    fields(result, RESULT_FIELDS); pendingShape(pending, mode);
    need(result.schema === 1 && result.scope === (upload ? SCOPES.finishResult : SCOPES.afterResult) &&
        result.originalHelperOutcome === 'PENDING_ENCLOSING_PROCESS_CLOSE' && result.originalStepOutcome === 'NOT_OBSERVED' &&
        result.qualification === 'NOT_ESTABLISHED' && result.readySha256 === sha(readyRaw) &&
        result.inputSha256 === sha(inputRaw) && result.pendingSha256 === sha(encode(pending)) &&
        result.artifactId === artifactId && pending.artifact.id === artifactId && pending.readySha256 === result.readySha256,
    'RESULT_ORIGINAL_BINDINGS');
    CARRIER_FIELDS.forEach(name => digest(result[name]));
    const checkedReady = upload ? ready(readyRaw, environment, nowMs) : afterReady(readyRaw, environment, nowMs);
    need(equal(checkedReady, readyValue), 'RESULT_ORIGINAL_READY');
    for (const name of ['kind', 'selection', 'source', 'github', 'beforeSha256'])
        need(equal(result[name], readyValue[name]) && equal(pending[name], readyValue[name]), 'RESULT_SOURCE_CONTEXT');
    for (const name of ['originalWindow', 'deadline', ...UTC_FIELDS]) need(equal(pending[name], readyValue[name]), 'RESULT_PINNED_CONTEXT');
    identity(pending, environment, pending.kind); currentUtc(pending, nowMs);
    need(pending.observedAt >= readyValue.observedAt && pending.observedAt <= Math.floor(nowMs / 1000) &&
        decimal(result.closedNs) >= decimal(pending.times.pendingPreparedNs) &&
        decimal(result.closedNs) < decimal(upload ? readyValue.workEndNs : readyValue.endNs), 'RESULT_ORIGINAL_CLOSE');
    if (upload) {
        fields(input, ['schema', 'scope', 'readerReadyBase64', 'readerFinalBase64', 'readerClosed', 'transportClosed',
            'beforeClosed', 'beforeOriginals']);
        need(input.schema === 1 && input.scope === SCOPES.finishInput, 'RESULT_FINISH_INPUT');
        base64Size(input.readerReadyBase64, RECORD); base64Size(input.readerFinalBase64, RECORD);
        const originals = decodedOriginals(input.beforeOriginals, 'before', String(readyValue.github.jobId), null, nowMs),
            originalReady = base64(input.readerReadyBase64, RECORD), finalRaw = base64(input.readerFinalBase64, RECORD);
        need(originalReady.equals(readyRaw), 'RESULT_READY_BYTES');
        const final = readerClosed(input.readerClosed, readyRaw, finalRaw, readyValue, bounds);
        observerClosed(input.beforeClosed, originals, readyValue, bounds, 'before', sha(readyRaw), nowMs);
        transportClosed(input.transportClosed, readyValue, bounds, input.readerClosed, input.beforeClosed, nowMs);
        const job = serviceJob(readyValue, originals[0].body, originals[0].rawHeaderVector, environment, 'upload', nowMs),
            transport = input.transportClosed, times = pending.times;
        need(pending.carrierCloseSha256 === readyValue.carrierCloseSha256 && equal(pending.members, readyValue.members) &&
            equal(pending.originals, readyValue.originals) && equal(pending.artifact, {id: transport.artifactId,
                name: transport.artifactName, zipBytes: transport.sentBytes, zipSha256: transport.observedZipSha256,
                createInvokedAt: transport.createInvokedAt, requestedExpiresAt: transport.requestedExpiresAt,
                requestedRetentionDays: transport.requestedRetentionDays}), 'RESULT_U_ARTIFACT_ORIGINALS');
        const actualTimes = {firstRawNs: readyValue.firstRawNs, streamClosedNs: final.closedNs, workEndNs: readyValue.workEndNs,
            closeEndNs: readyValue.closeEndNs, readerPreSpawnLocalNs: input.readerClosed.preSpawnLocalNs,
            readerReturnedLocalNs: input.readerClosed.returnedLocalNs, beforeEnteredLocalNs: input.beforeClosed.enteredNs,
            beforeReturnedLocalNs: input.beforeClosed.lastObservationNs, transportEnteredLocalNs: transport.enteredNs,
            transportReturnedLocalNs: transport.returnedObservationNs};
        for (const [name, value] of Object.entries(actualTimes)) need(times[name] === value, 'RESULT_U_ORIGINAL_TIMES');
        need(equal(pending.observations, {streamFinalSha256: sha(finalRaw), readerClosedSha256: sha(encode(input.readerClosed, INPUT)),
            transportClosedSha256: sha(encode(transport, INPUT)), beforeClosedSha256: sha(encode(input.beforeClosed, INPUT)),
            beforeBodySha256: job.bodySha256, beforeHeaderVectorSha256: job.rawHeaderVectorSha256,
            beforeServiceEpoch: job.serviceEpoch, beforeStepNumber: job.steps.before.number, uploadStepNumber: job.steps.upload.number,
            transportRequestCount: transport.requests.length}), 'RESULT_U_ACTUAL_OBSERVATIONS');
    } else {
        fields(input, ['schema', 'scope', 'afterClosed', 'afterOriginals']);
        need(input.schema === 1 && input.scope === SCOPES.afterInput && pending.uploadSha256 === readyValue.uploadSha256 &&
            equal(pending.uploadCarrier, {directoryIdentitySha256: environment.P2PKIT_INITIAL_UPLOAD_DIRECTORY_SHA256,
                fileMetadataSha256: environment.P2PKIT_INITIAL_UPLOAD_FILE_METADATA_SHA256,
                fileOwnerCloseSha256: environment.P2PKIT_INITIAL_UPLOAD_OWNER_CLOSE_SHA256}), 'RESULT_AFTER_ORIGINAL_U');
        const originals = decodedOriginals(input.afterOriginals, 'after', String(readyValue.github.jobId), artifactId, nowMs);
        observerClosed(input.afterClosed, originals, readyValue, bounds, 'after', sha(readyRaw), nowMs);
        const job = afterServiceJob(readyValue, originals[0], environment, nowMs), artifact = serviceArtifact(pending, originals[1], nowMs);
        need(pending.times.firstRawNs === readyValue.firstRawNs && pending.times.endNs === readyValue.endNs &&
            pending.times.observerEnteredLocalNs === input.afterClosed.enteredNs &&
            pending.times.observerReturnedLocalNs === input.afterClosed.lastObservationNs, 'RESULT_A_ORIGINAL_TIMES');
        need(equal(pending.observations, {afterClosedSha256: sha(encode(input.afterClosed, INPUT)), jobBodySha256: job.bodySha256,
            jobHeaderVectorSha256: job.rawHeaderVectorSha256, artifactBodySha256: artifact.bodySha256,
            artifactHeaderVectorSha256: artifact.rawHeaderVectorSha256, jobServiceEpoch: job.serviceEpoch,
            artifactServiceEpoch: artifact.serviceEpoch, beforeStepNumber: job.steps.before.number,
            uploadStepNumber: job.steps.upload.number, afterStepNumber: job.steps.after.number,
            observerRequestCount: input.afterClosed.requests.length}), 'RESULT_A_ACTUAL_OBSERVATIONS');
    }
    return result;
}
function outputs(result) {
    fields(result, RESULT_FIELDS);
    need(result.schema === 1 && [SCOPES.finishResult, SCOPES.afterResult].includes(result.scope), 'OUTPUT_RESULT_SCOPE');
    pendingShape(result.pending, result.scope === SCOPES.finishResult ? 'upload' : 'after');
    const raw = encode(result.pending);
    need(sha(raw) === digest(result.pendingSha256) && decimal(result.artifactId, 1n, INT64) > 0n &&
        result.artifactId === result.pending.artifact.id, 'OUTPUT_SAFE_PENDING');
    CARRIER_FIELDS.forEach(name => digest(result[name]));
    return Object.freeze({'artifact-id': result.artifactId, 'receipt-base64': raw.toString('base64'),
        'receipt-sha256': result.pendingSha256, 'directory-identity-sha256': result.directoryIdentitySha256,
        'file-metadata-sha256': result.fileMetadataSha256, 'file-owner-close-sha256': result.fileOwnerCloseSha256});
}

module.exports = Object.freeze({DataError, fields, array, integer, count, decimal, digest, bytes, sha, encode, parse, record,
    equal, base64, currentUtc, members, ready, localBounds, serviceSteps, serviceJob, headerVector, artifactName,
    readerClosed, observerClosed, transportClosed, finishInput, afterReady, afterBounds, afterInput,
    pendingShape, finiteResult, outputs});
