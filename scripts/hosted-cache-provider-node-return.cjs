'use strict';

// Dormant bounded supplied-event reducer, NOT an original child/runner observer.
// No spawn, kill, environment, clock, filesystem, callback registration or CLI.
// The future fixed caller must feed its actual child events and separately bind
// prestart authority, original RAW deadlines, cancellation and enclosing return.
const {createHash} = require('node:crypto');

const ACK_LIMIT = 4096;
const STDERR_LIMIT = 1024 * 1024;
const REQUEST_LIMIT = 16 * 1024;
const PENDING = Object.freeze({
    enclosingNodeReturn: 'NOT_OBSERVED',
    originalRunnerOutcome: 'NOT_OBSERVED',
    providerAcceptance: 'NOT_ESTABLISHED',
});
const LIMITS = Object.freeze({native: 2 * 1024 * 1024, stdout: 1024 * 1024,
    stderr: 1024 * 1024, packet: 6 * 1024 * 1024});
const NS = 1000000000n;
const UINT64 = (1n << 64n) - 1n;
const INT64 = (1n << 63n) - 1n;
const SAFE = BigInt(Number.MAX_SAFE_INTEGER);
const SOURCE_ERRORS = new WeakSet();
const typedArray = Object.getPrototypeOf(Uint8Array.prototype);
const typedLength = Object.getOwnPropertyDescriptor(typedArray, 'length').get;
const typedBuffer = Object.getOwnPropertyDescriptor(typedArray, 'buffer').get;
const arrayBufferLength = Object.getOwnPropertyDescriptor(ArrayBuffer.prototype, 'byteLength').get;
const typedSet = Uint8Array.prototype.set;
const apply = Reflect.apply;

class ReceiptError extends Error {
    constructor(reason) {
        super(reason); // Fixed source-owned code only; never raw bytes/errors.
        this.name = 'ProviderNodeReceiptError';
    }
}
function need(value, reason) {
    if (!value) throw sourceError(reason);
}
function sourceError(reason) {
    const error = Object.freeze(new ReceiptError(reason));
    SOURCE_ERRORS.add(error);
    return error;
}
function normalized(error, reason) {
    // A caller may construct ReceiptError with private text. Its class alone
    // supplies no source provenance, and it must not become our public error.
    return SOURCE_ERRORS.has(error) ? error : sourceError(reason);
}
function plain(value) {
    return value !== null && typeof value === 'object' && Object.getPrototypeOf(value) === Object.prototype;
}
function keys(value, expected) {
    return plain(value) && Object.keys(value).sort().join('\0') === [...expected].sort().join('\0');
}
function integer(value, low, high) {
    return (Number.isSafeInteger(value) || typeof value === 'bigint') && value >= low && value <= high;
}
function hex(value, length) {
    return typeof value === 'string' && value.length === length && /^[0-9a-f]+$/.test(value);
}
function digest(raw) {
    return createHash('sha256').update(raw).digest('hex');
}
function bytes(value, maximum) {
    try {
        // Internal slots first: no caller length/buffer/valueOf/copy/iterator
        // property is read. Proxies and shared backing cannot supply originals.
        const length = apply(typedLength, value, []);
        const backing = apply(typedBuffer, value, []);
        apply(arrayBufferLength, backing, []); // Refuses SharedArrayBuffer.
        need(Object.getPrototypeOf(value) === Buffer.prototype && Buffer.isBuffer(value) && length <= maximum,
            'NODE_RECEIPT_BYTE_BOUND');
        const owned = Buffer.alloc(length);
        apply(typedSet, owned, [value]);
        return owned;
    } catch (error) { throw normalized(error, 'NODE_RECEIPT_BYTE_BOUND'); }
}
function canonical(value) {
    const escaped = part => JSON.stringify(part).replace(/[\x7f-\uffff]/g,
        char => '\\u' + char.charCodeAt(0).toString(16).padStart(4, '0'));
    function ordered(part, depth) {
        need(depth <= 32, 'NODE_RECEIPT_JSON_DEPTH');
        if (part === null || typeof part === 'string' || typeof part === 'boolean') return escaped(part);
        if (typeof part === 'bigint') return part.toString();
        if (typeof part === 'number') {
            need(Number.isSafeInteger(part), 'NODE_RECEIPT_JSON_INTEGER');
            return escaped(part);
        }
        if (Array.isArray(part)) return '[' + part.map(item => ordered(item, depth + 1)).join(',') + ']';
        need(plain(part), 'NODE_RECEIPT_JSON_OBJECT');
        return '{' + Object.keys(part).sort().map(key => {
            need(/^[\x20-\x7e]+$/.test(key), 'NODE_RECEIPT_JSON_KEY');
            return escaped(key) + ':' + ordered(part[key], depth + 1);
        }).join(',') + '}';
    }
    return ordered(value, 0);
}
function parse(raw, maximum, newline) {
    const owned = bytes(raw, maximum);
    need(owned.length > 0 && !owned.some(value => value > 127), 'NODE_RECEIPT_ASCII');
    let value;
    try {
        value = JSON.parse(owned.toString('ascii'), (_key, part, context) => {
            if (typeof part !== 'number') return part;
            need(context && typeof context.source === 'string' && /^-?(0|[1-9][0-9]*)$/.test(context.source),
                'NODE_RECEIPT_JSON_INTEGER_SOURCE');
            const exact = BigInt(context.source);
            return -SAFE <= exact && exact <= SAFE ? Number(exact) : exact;
        });
    } catch (error) { throw normalized(error, 'NODE_RECEIPT_JSON'); }
    need(plain(value) && canonical(value) + (newline ? '\n' : '') === owned.toString('ascii'),
        'NODE_RECEIPT_CANONICAL');
    return value; // Exact re-encoding rejects duplicate keys and numeric aliases.
}
function nanoseconds(value) {
    need(typeof value === 'string' && /^(0|[1-9][0-9]{0,19})$/.test(value), 'NODE_RECEIPT_RAW_SHAPE');
    const number = BigInt(value);
    need(number < (1n << 64n), 'NODE_RECEIPT_RAW_SHAPE');
    return number;
}
function identity(value, role) {
    need(Array.isArray(value) && value.length === 2 && integer(value[0], 0, UINT64) &&
        (role === 'windows-x64' ? hex(value[1], 32) : integer(value[1], 1, UINT64)),
    'NODE_RECEIPT_FILE_IDENTITY');
    return canonical(value);
}
function requestContext(raw) {
    const value = parse(raw, REQUEST_LIMIT, false);
    need(keys(value, ['schema', 'role', 'frequency', 'firstNs', 'issuedNs', 'hardEndNs', 'workerCutoffNs',
        'phase', 'job', 'outerId', 'innerId', 'directory', 'directoryIdentity', 'home', 'homeIdentity',
        'node', 'toolPath', 'plan']) && value.schema === 'P2PKIT_PROVIDER_SUPERVISOR_REQUEST_V1',
    'NODE_RECEIPT_REQUEST');
    need(['linux-x64', 'windows-x64', 'macos-arm64', 'macos-x64'].includes(value.role) &&
        integer(value.frequency, 1, INT64) &&
        (value.role === 'windows-x64' || value.frequency === Number(NS)), 'NODE_RECEIPT_CLOCK_SHAPE');
    const issued = nanoseconds(value.issuedNs), first = nanoseconds(value.firstNs);
    const cut = nanoseconds(value.workerCutoffNs), end = nanoseconds(value.hardEndNs);
    need(issued <= first && first < cut && cut < end && end <= issued + 180n * NS && issued + 45n * NS < cut,
        'NODE_RECEIPT_WINDOW_SHAPE');
    need(['save', 'lookup'].includes(value.phase) && ['job', 'outerId', 'innerId'].every(key => hex(value[key], 32)) &&
        value.outerId !== value.innerId && plain(value.plan) &&
        ['directory', 'home', 'node', 'toolPath'].every(key => typeof value[key] === 'string' && value[key].length > 0),
    'NODE_RECEIPT_REQUEST');
    need(identity(value.directoryIdentity, value.role) !== identity(value.homeIdentity, value.role),
        'NODE_RECEIPT_ROOT_ALIAS');
    return value; // Not native path/plan/clock admission or freshness.
}
function acknowledgement(raw, request, code) {
    const value = parse(raw, ACK_LIMIT, true);
    need(keys(value, ['schema', 'invocationSha256', 'workerRequestSha256', 'kind', 'workerExitCode', 'providerKind',
        'observedNs', 'closedResources', 'files', ...Object.keys(PENDING)]) &&
        value.schema === 'P2PKIT_PROVIDER_SUPERVISOR_ACK_V1', 'NODE_RECEIPT_ACK');
    need(value.invocationSha256 === request.hash && hex(value.workerRequestSha256, 64) &&
        Object.entries(PENDING).every(([key, expected]) => value[key] === expected), 'NODE_RECEIPT_ACK_BINDING');
    need((value.kind === 'success' && code === 0) || (value.kind === 'failed' && code === 65), 'NODE_RECEIPT_ACK_EXIT');
    need(value.workerExitCode === null || integer(value.workerExitCode, -(2 ** 31), 2 ** 32 - 1),
        'NODE_RECEIPT_WORKER_EXIT');
    need([null, 'success', 'failed'].includes(value.providerKind) &&
        (value.providerKind === null || value.workerExitCode === (value.providerKind === 'success' ? 0 : 65)) &&
        (value.kind === 'failed' || (value.workerExitCode === 0 && value.providerKind === 'success')),
    'NODE_RECEIPT_PROVIDER_KIND');
    const observed = nanoseconds(value.observedNs);
    need(nanoseconds(request.value.firstNs) <= observed && observed < nanoseconds(request.value.hardEndNs),
        'NODE_RECEIPT_ACK_TIME_SHAPE');
    need(keys(value.files, Object.keys(LIMITS)), 'NODE_RECEIPT_FILES');
    const identities = [];
    for (const [name, limit] of Object.entries(LIMITS)) {
        const file = value.files[name];
        if (name === 'packet' && file === null) continue;
        need(keys(file, ['bytes', 'sha256', 'identity']) &&
            integer(file.bytes, ['stdout', 'stderr'].includes(name) ? 0 : 1, limit) && hex(file.sha256, 64),
        'NODE_RECEIPT_FILE');
        identities.push(identity(file.identity, request.value.role));
    }
    need(new Set(identities).size === identities.length &&
        (value.providerKind === null || value.files.packet !== null), 'NODE_RECEIPT_FILE_ALIAS_OR_PACKET');
    const closes = ['scope', 'retirement-writer'];
    if (request.value.role !== 'windows-x64') closes.push('stdout-reader', 'stderr-reader');
    if (value.files.packet !== null) closes.push('packet-reader');
    closes.push('stderr', 'stdout', 'bundle', 'capture_directory', 'home', 'directory');
    need(Array.isArray(value.closedResources) && JSON.stringify(value.closedResources) === JSON.stringify(closes),
        'NODE_RECEIPT_CLOSE_ROSTER');
    return value;
}

class ReceiptReducer {
    #request;
    #phase = 'new';
    #failure = null;
    #stdout;
    #stderr;
    #sizes = {stdout: 0, stderr: 0};
    #ended = {stdout: false, stderr: false};
    #exit = null;
    #finished = false;
    #busy = false;
    constructor(request) {
        try {
            const raw = bytes(request, REQUEST_LIMIT);
            this.#request = {value: requestContext(raw), hash: digest(raw)};
            // Fixed storage also bounds allocation when events arrive one byte
            // at a time. Empty events cannot accumulate retained objects.
            this.#stdout = Buffer.alloc(ACK_LIMIT);
            this.#stderr = Buffer.alloc(STDERR_LIMIT);
        } catch (error) { throw normalized(error, 'NODE_RECEIPT_REQUEST_FAILURE'); }
    }
    #accept(operation) {
        if (this.#busy) {
            if (this.#failure === null) this.#failure = sourceError('NODE_RECEIPT_REENTRY');
            return;
        }
        this.#busy = true;
        try {
            need(!this.#finished, 'NODE_RECEIPT_ALREADY_FINISHED');
            operation();
        } catch (error) {
            if (this.#failure === null) this.#failure = normalized(error, 'NODE_RECEIPT_EVENT_FAILURE');
        } finally { this.#busy = false; }
        // Event handlers must not throw and thereby kill the original supervisor.
        // A fixed first failure is surfaced only by finish(), never cleared.
    }
    onSpawn() {
        this.#accept(() => { need(this.#phase === 'new', 'NODE_RECEIPT_SPAWN_ORDER'); this.#phase = 'started'; });
    }
    onData(stream, chunk) {
        this.#accept(() => {
            need(['stdout', 'stderr'].includes(stream) && ['started', 'exited'].includes(this.#phase) &&
                !this.#ended[stream], 'NODE_RECEIPT_STREAM_ORDER');
            const limit = stream === 'stdout' ? ACK_LIMIT : STDERR_LIMIT;
            const raw = bytes(chunk, limit - this.#sizes[stream]);
            raw.copy(stream === 'stdout' ? this.#stdout : this.#stderr, this.#sizes[stream]);
            this.#sizes[stream] += raw.length;
        });
    }
    onEnd(stream) {
        this.#accept(() => {
            need(['stdout', 'stderr'].includes(stream) && ['started', 'exited'].includes(this.#phase) &&
                !this.#ended[stream], 'NODE_RECEIPT_END_ORDER');
            this.#ended[stream] = true;
        });
    }
    onError() {
        this.#accept(() => { throw sourceError('NODE_RECEIPT_CHILD_ERROR'); });
    }
    onExit(code, signal) {
        this.#accept(() => {
            need(this.#phase === 'started' && signal === null && (code === 0 || code === 65) && !Object.is(code, -0),
                'NODE_RECEIPT_EXIT');
            this.#exit = code;
            this.#phase = 'exited';
        });
    }
    onClose(code, signal) {
        this.#accept(() => {
            need(this.#phase === 'exited' && Object.is(code, this.#exit) && signal === null &&
                this.#ended.stdout && this.#ended.stderr, 'NODE_RECEIPT_CLOSE');
            this.#phase = 'closed';
        });
    }
    finish() {
        let result;
        this.#accept(() => {
            need(this.#phase === 'closed', 'NODE_RECEIPT_INCOMPLETE');
            this.#finished = true;
            if (this.#failure !== null) throw this.#failure;
            const stdout = this.#stdout.subarray(0, this.#sizes.stdout);
            const stderr = this.#stderr.subarray(0, this.#sizes.stderr);
            const ack = acknowledgement(stdout, this.#request, this.#exit);
            result = Object.freeze({scope: 'SUPPLIED_NODE_EVENT_CONSISTENCY_ONLY',
                invocationSha256: this.#request.hash, acknowledgementSha256: digest(stdout),
                acknowledgementBytes: this.#sizes.stdout, stderrSha256: digest(stderr),
                stderrBytes: this.#sizes.stderr, suppliedExitCode: this.#exit, kind: ack.kind,
                originalChildIdentity: 'NOT_AUTHENTICATED', originalRawDeadline: 'NOT_OBSERVED',
                originalCancellation: 'NOT_OBSERVED', ...PENDING});
        });
        this.#finished = true; // Early or reentrant attempts also consume finish.
        if (this.#failure !== null) throw this.#failure;
        return result;
    }
    retainedBytes() {
        // Private custody data only. Copies cannot mutate the reducer's originals.
        return {stdout: Buffer.from(this.#stdout.subarray(0, this.#sizes.stdout)),
            stderr: Buffer.from(this.#stderr.subarray(0, this.#sizes.stderr))};
    }
}

module.exports = Object.freeze({ReceiptReducer, ReceiptError});
