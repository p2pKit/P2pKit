'use strict';

// Focused pure DATA controls, not transport/native/provider/hosted qualification.
// Only the driver reads four bounded Action source/metadata files. Candidate
// filesystem, process, clock, timer and console effects are denied and counted.
// The initial sibling is TEXT ONLY: loading it would call the real controller.
// The VM is a finite reviewed model, not an OS security sandbox.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const paths = require('node:path');
const vm = require('node:vm');

const cases = [], test = (name, body) => cases.push({name, body});
const FILES = Object.freeze({
    ordinary: '.github/actions/ordinary-cache-provider/index.cjs',
    ordinaryMetadata: '.github/actions/ordinary-cache-provider/action.yml',
    initial: '.github/actions/initial-ordinary-cache-provider/index.cjs',
    initialMetadata: '.github/actions/initial-ordinary-cache-provider/action.yml',
});
const OUTPUTS = Object.freeze(['dependency_seed_ready', 'dependency_cache_ready', 'native_provider_ready',
    'dependency_seed_home', 'dependency_seed_staging_sha256', 'preparation_sha256', 'restoration_sha256',
    'cache_key', 'cache_path']);
const COHORTS = Object.freeze([['desktop', 'linux-x64'], ['desktop', 'windows-x64'],
    ['desktop', 'macos-x64'], ['desktop', 'macos-arm64'], ['full', 'macos-x64'], ['full', 'macos-arm64']]);
const IDENTITIES = Object.freeze({repository: 'GITHUB_REPOSITORY', event: 'GITHUB_EVENT_NAME', ref: 'GITHUB_REF',
    workflowSha: 'GITHUB_WORKFLOW_SHA', job: 'GITHUB_JOB', runId: 'GITHUB_RUN_ID', runAttempt: 'GITHUB_RUN_ATTEMPT'});
let sources;

function readSources() {
    const result = {}, limit = 65536;
    for (const [name, relative] of Object.entries(FILES)) {
        const fd = fs.openSync(paths.join(__dirname, '../..', relative), 'r');
        try {
            assert(fs.fstatSync(fd).isFile(), 'subject must be a regular source file');
            const raw = Buffer.alloc(limit + 1);
            let size = 0;
            while (size < raw.length) {
                const count = fs.readSync(fd, raw, size, raw.length - size, size);
                if (count === 0) break;
                size += count;
            }
            assert(size > 0 && size <= limit, 'subject exceeds the fixed source-read bound');
            result[name] = raw.subarray(0, size).toString('utf8');
        } finally { fs.closeSync(fd); }
    }
    return result;
}

const namesFor = origin => [...OUTPUTS, ...(origin === 'initial' ? ['initial_current_history_sha256'] : [])];
const copy = value => JSON.parse(JSON.stringify(value));
// Independent model encoder: sort the fixture structure, use the host JSON
// serializer, then escape non-ASCII UTF-16 units. Fixture member names are ASCII.
function frame(value) {
    function ordered(item) {
        if (Array.isArray(item)) return item.map(ordered);
        if (item !== null && typeof item === 'object') return Object.fromEntries(
            Object.keys(item).sort().map(name => [name, ordered(item[name])]));
        return item;
    }
    return Buffer.from(JSON.stringify(ordered(value)).replace(/[\u007f-\uffff]/g,
        unit => '\\u' + unit.charCodeAt(0).toString(16).padStart(4, '0')) + '\n', 'ascii');
}

function fixture(origin = 'ordinary', profile = 'desktop', role = 'linux-x64', temp) {
    const windows = role === 'windows-x64', path = windows ? paths.win32 : paths.posix;
    const workflow = profile === 'full' ? '.github/workflows/ci.yml' : '.github/workflows/desktop-cross-host.yml';
    const expected = {
        GITHUB_SHA: '1'.repeat(40), GITHUB_REPOSITORY: 'p2pKit/P2pKit',
        GITHUB_EVENT_NAME: origin === 'initial' ? 'pull_request' : 'push',
        GITHUB_REF: origin === 'initial' ? 'refs/pull/12/merge' : 'refs/heads/main',
        GITHUB_WORKFLOW_SHA: '2'.repeat(40), GITHUB_JOB: 'model_job', GITHUB_RUN_ID: '42', GITHUB_RUN_ATTEMPT: '3',
        RUNNER_TEMP: temp === undefined ? (windows ? 'C:\\model\\runner-temp' : '/model/runner-temp') : temp,
    };
    expected.GITHUB_WORKFLOW_REF = expected.GITHUB_REPOSITORY + '/' + workflow + '@' + expected.GITHUB_REF;
    const home = path.join(expected.RUNNER_TEMP, 'p2pkit-dependency-seed-' + profile + '-' + role, 'restore-home');
    const outputs = {
        dependency_seed_ready: 'true', dependency_cache_ready: 'true', native_provider_ready: 'true',
        dependency_seed_home: home, dependency_seed_staging_sha256: '4'.repeat(64),
        preparation_sha256: '5'.repeat(64), restoration_sha256: '6'.repeat(64),
        cache_key: 'p2pkit-dependency-files-v1-' + profile + '-' + role + '-' + '7'.repeat(64) + '-' + '8'.repeat(64),
        cache_path: path.join(home, 'caches', 'modules-2', 'files-2.1'),
    };
    if (origin === 'initial') outputs.initial_current_history_sha256 = '9'.repeat(64);
    const github = Object.fromEntries(Object.entries(IDENTITIES).map(([field, name]) => [field, expected[name]]));
    github.workflow = workflow;
    const value = {
        schema: 1, scope: (origin === 'initial' ? 'INITIAL_ORDINARY_' : 'ORDINARY_') +
            'CACHE_PROVIDER_CONTROLLER_PENDING_ACTION_CLOSE_V1', profile, role, controllerPid: 321,
        source: {commit: expected.GITHUB_SHA, tree: '3'.repeat(40)}, github, outputs,
        retirement: 'KNOWN', errors: [], enclosingActionReturn: 'NOT_OBSERVED', resolverAcceptance: 'NOT_PERFORMED',
    };
    // These are explicit model values, never producer, runner or custody evidence.
    return {origin, profile, role, childPid: 321, expected, value};
}

function model(f) {
    const effects = [], imports = [];
    const denied = name => () => {
        effects.push(name);
        throw new Error('MODEL_EFFECT_DENIED:' + name);
    };
    function object(name, allowed = {}) {
        return new Proxy(Object.freeze(allowed), {
            get(target, key) {
                if (Object.hasOwn(target, key)) return target[key];
                return denied(name + '.' + String(key))();
            },
            set: denied(name + '.set'), deleteProperty: denied(name + '.delete'),
            defineProperty: denied(name + '.define'), setPrototypeOf: denied(name + '.prototype'),
        });
    }
    const modules = {
        'node:fs': object('fs'), 'node:path': paths,
        'node:child_process': object('child_process', {spawn: denied('spawn'),
            ChildProcess: function ChildProcess() { denied('ChildProcess')(); }}),
        'node:stream': object('stream', {Readable: function Readable() { denied('Readable')(); }}),
    };
    const localRequire = name => {
        imports.push(name);
        if (!Object.hasOwn(modules, name)) return denied('require:' + name)();
        return modules[name];
    };
    const module = {exports: {}};
    localRequire.main = Object.freeze({}); // Deliberately NOT the candidate module.
    const windows = f.role === 'windows-x64', path = windows ? paths.win32 : paths.posix;
    const dirname = path.join(windows ? 'C:\\model\\repo' : '/model/repo', '.github', 'actions', 'ordinary-cache-provider');
    const sandbox = {
        module, exports: module.exports, require: localRequire, Buffer,
        __dirname: dirname, __filename: path.join(dirname, 'index.cjs'),
        process: object('process', {platform: windows ? 'win32' : (f.role.startsWith('macos-') ? 'darwin' : 'linux'),
            arch: f.role.endsWith('arm64') ? 'arm64' : 'x64'}),
        console: object('console'), performance: object('performance'),
        Date: new Proxy(function ModelDate() {}, {apply: denied('Date.call'), construct: denied('Date.construct'),
            get: denied('Date.property')}), setTimeout: denied('setTimeout'), clearTimeout: denied('clearTimeout'),
        setInterval: denied('setInterval'), clearInterval: denied('clearInterval'),
        setImmediate: denied('setImmediate'), clearImmediate: denied('clearImmediate'),
        queueMicrotask: denied('queueMicrotask'), fetch: denied('fetch'),
    };
    vm.runInNewContext(sources.ordinary, sandbox, {filename: FILES.ordinary, timeout: 1000});
    assert.deepEqual(imports, ['node:fs', 'node:path', 'node:child_process', 'node:stream']);
    assert.deepEqual(effects, [], 'passive module load must not attempt an effect');
    assert.deepEqual(Object.keys(module.exports).sort(), ['mainInitial', 'mainOrdinary', 'resultData']);
    for (const name of ['mainInitial', 'mainOrdinary', 'resultData']) assert.equal(typeof module.exports[name], 'function');
    return {
        effects,
        read(raw, input = f) {
            try {
                return module.exports.resultData(raw, input.origin, input.profile, input.role, input.childPid, input.expected);
            } finally { assert.deepEqual(effects, [], 'DATA parse must not attempt an effect'); }
        },
    };
}

function accepts(f, candidate = model(f), raw = frame(f.value)) {
    const before = copy(f);
    const output = candidate.read(raw, f);
    assert.equal(output, namesFor(f.origin).map(name => name + '=' + f.value.outputs[name] + '\n').join(''));
    assert.deepEqual(f, before, 'helper must not mutate its model inputs');
    return candidate;
}
const holds = body => assert.throws(body, error => error && error.name === 'Error' &&
    error.message === 'NATIVE_CACHE_CONTROLLER_HOLD');
function changed(f, mutate) {
    const candidate = accepts(f), next = copy(f);
    mutate(next);
    assert.notDeepEqual(next, f, 'negative must change its accepted baseline');
    holds(() => candidate.read(frame(next.value), next));
}
function changedRaw(f, mutate, syntax = false) {
    const candidate = accepts(f), raw = frame(f.value), next = mutate(raw);
    assert.notDeepEqual(next, raw, 'negative must change the accepted frame');
    if (syntax) assert.throws(() => candidate.read(next, f), error => error && error.name === 'SyntaxError');
    else holds(() => candidate.read(next, f));
}
function editRaw(f, before, after) {
    changedRaw(f, raw => Buffer.from(raw.toString('ascii').replace(before, after), 'ascii'));
}

test('Action metadata declares exact profile, output order and node24 fixed entries', () => {
    for (const origin of ['ordinary', 'initial']) {
        const metadata = sources[origin + 'Metadata'];
        const sections = metadata.split('\noutputs:\n');
        assert.equal(sections.length, 2);
        const [output, runs, extra] = sections[1].split('\nruns:\n');
        assert.equal(extra, undefined);
        assert.equal(runs, '  using: node24\n  main: index.cjs\n');
        assert.deepEqual([...output.matchAll(/^  ([a-z][a-z0-9_]*):$/gm)].map(match => match[1]), namesFor(origin));
        assert.equal(sections[0].split('\ninputs:\n').length, 2);
        assert.equal(sections[0].split('\ninputs:\n')[1].split('\n')[0], '  profile:');
        assert.equal((sections[0].match(/^  [a-z][a-z0-9_]*:$/gm) || []).length, 1);
        assert.match(sections[0], /^    required: true$/m);
    }
});
test('initial entry is fixed routing TEXT only and ordinary retains a passive import guard', () => {
    const lines = sources.initial.split('\n').filter(line => line.trim() && !/^\s*\/\//.test(line));
    assert.deepEqual(lines, ["'use strict';", "require('../ordinary-cache-provider/index.cjs').mainInitial();"]);
    assert(sources.ordinary.includes('if (require.main === module) exports.mainOrdinary();'));
});
test('shared DATA module loads passively without candidate filesystem, process or timer effects', () => {
    for (const [profile, role] of COHORTS) assert.deepEqual(model(fixture('ordinary', profile, role)).effects, []);
});
test('ordinary DATA returns the exact nine outputs for all six supported cohorts', () => {
    for (const [profile, role] of COHORTS) accepts(fixture('ordinary', profile, role));
});
test('initial DATA returns its exact ten outputs for all six supported cohorts', () => {
    for (const [profile, role] of COHORTS) accepts(fixture('initial', profile, role));
});
test('ASCII escaped Unicode including surrogate pairs round trips POSIX and Windows paths', () => {
    for (const origin of ['ordinary', 'initial']) for (const role of ['linux-x64', 'windows-x64']) {
        const temp = role === 'windows-x64' ? 'C:\\model\\caf\u00e9-\ud83d\ude00' : '/model/caf\u00e9-\ud83d\ude00';
        const f = fixture(origin, 'desktop', role, temp), raw = frame(f.value);
        assert(raw.every(byte => byte < 128));
        assert(raw.toString('ascii').includes('caf\\u00e9-\\ud83d\\ude00'));
        accepts(f, model(f), raw);
    }
});
test('ordinary pull-request DATA remains ordinary and rejects an initial-only history field', () => {
    const f = fixture();
    f.expected.GITHUB_EVENT_NAME = f.value.github.event = 'pull_request';
    f.expected.GITHUB_REF = f.value.github.ref = 'refs/pull/12/merge';
    f.expected.GITHUB_WORKFLOW_REF = f.value.github.repository + '/' + f.value.github.workflow + '@' + f.value.github.ref;
    accepts(f);
    changed(f, next => { next.value.outputs.initial_current_history_sha256 = '9'.repeat(64); });
});
test('tree and digest values are shape-only DATA here, not a new external authority', () => {
    for (const origin of ['ordinary', 'initial']) {
        const f = fixture(origin);
        f.value.source.tree = 'a'.repeat(40);
        for (const name of namesFor(origin).filter(name => name.endsWith('_sha256'))) f.value.outputs[name] = 'b'.repeat(64);
        f.value.outputs.cache_key = f.value.outputs.cache_key.replace('7'.repeat(64), 'c'.repeat(64)).replace('8'.repeat(64), 'd'.repeat(64));
        accepts(f);
    }
});
test('one exact 16384-byte canonical frame fits but its 16385-byte successor does not', () => {
    const f = fixture(), padding = 16384 - frame(f.value).length;
    assert(padding > 0);
    f.value.github.job += 'j'.repeat(padding);
    f.expected.GITHUB_JOB = f.value.github.job; // Explicit model, not a service job record.
    assert.equal(frame(f.value).length, 16384);
    accepts(f);
    changed(f, next => { next.expected.GITHUB_JOB = next.value.github.job += 'j'; });
});
test('the 4096-character output bound admits an exact literal model cache path', () => {
    const seed = fixture(), suffix = seed.value.outputs.cache_path.slice(seed.expected.RUNNER_TEMP.length);
    const f = fixture('ordinary', 'desktop', 'linux-x64', '/' + 't'.repeat(4096 - suffix.length - 1));
    assert.equal(f.value.outputs.cache_path.length, 4096);
    accepts(f);
    changed(f, next => { next.value.outputs.cache_path += 'x'; });
});
test('unknown or mixed caller origin, profile and role selections fail closed', () => {
    for (const [field, values] of Object.entries({origin: ['bootstrap', 'ORDINARY', '', null],
        profile: ['FULL', 'bootstrap-desktop', '', null], role: ['linux-arm64', 'windows-arm64', 'macos', '', null]}))
        for (const value of values) changed(fixture(), next => { next[field] = value; });
    changed(fixture(), next => { next.origin = 'initial'; });
    changed(fixture(), next => { next.profile = 'full'; });
    changed(fixture(), next => { next.role = 'macos-x64'; });
    for (const role of ['linux-x64', 'windows-x64']) {
        const f = fixture('ordinary', 'full', role);
        holds(() => model(f).read(frame(f.value), f));
    }
});
test('scope, record profile and record role must match the selected caller exactly', () => {
    for (const origin of ['ordinary', 'initial']) {
        const f = fixture(origin);
        for (const scope of ['ORDINARY_CACHE_PROVIDER_CONTROLLER_CLOSED_V1',
            fixture(origin === 'ordinary' ? 'initial' : 'ordinary').value.scope, '', null])
            changed(f, next => { next.value.scope = scope; });
        changed(f, next => { next.value.profile = 'full'; });
        changed(f, next => { next.value.role = 'macos-x64'; });
    }
});
test('schema is integer one and actual controller PID is positive, safe and exact', () => {
    for (const value of [true, false, '1', 0, 2, null, 1.5, Number.MAX_SAFE_INTEGER + 1])
        changed(fixture(), next => { next.value.schema = value; });
    for (const value of [true, '321', 0, -1, 322, null, 321.5, Number.MAX_SAFE_INTEGER + 1])
        changed(fixture(), next => { next.value.controllerPid = value; });
    for (const value of [true, '321', 0, 322, null]) changed(fixture(), next => { next.childPid = value; });
});
test('pending Action, known retirement, empty errors and no resolver acceptance are mandatory', () => {
    for (const [field, values] of Object.entries({retirement: ['UNKNOWN', true, null],
        errors: [['failure'], {}, '', null], enclosingActionReturn: ['OBSERVED', 'SUCCESS', true],
        resolverAcceptance: ['PASS', 'PERFORMED', true]}))
        for (const value of values) changed(fixture(), next => { next.value[field] = value; });
});
test('top-level members are exact and cannot carry extra result or authority fields', () => {
    for (const origin of ['ordinary', 'initial']) {
        const f = fixture(origin);
        for (const name of Object.keys(f.value)) changed(f, next => { delete next.value[name]; });
        for (const name of ['extra', 'currentAuthority', '__proto__'])
            changed(f, next => { Object.defineProperty(next.value, name, {value: true, enumerable: true}); });
    }
});
test('source, GitHub and output member sets are exact for both origins', () => {
    for (const origin of ['ordinary', 'initial']) for (const field of ['source', 'github', 'outputs']) {
        const f = fixture(origin);
        for (const name of Object.keys(f.value[field])) changed(f, next => { delete next.value[field][name]; });
        changed(f, next => { next.value[field].extra = 'not-admitted'; });
        for (const value of [null, [], '', true]) changed(f, next => { next.value[field] = value; });
    }
});
test('source commit matches the supplied identity and tree requires lowercase full SHA shape', () => {
    const f = fixture();
    for (const commit of ['a'.repeat(40), '', null, true]) changed(f, next => { next.value.source.commit = commit; });
    changed(f, next => { next.expected.GITHUB_SHA = 'a'.repeat(40); });
    changed(f, next => { delete next.expected.GITHUB_SHA; });
    for (const tree of ['A'.repeat(40), 'g'.repeat(40), '3'.repeat(39), '3'.repeat(41), '', null, true])
        changed(f, next => { next.value.source.tree = tree; });
});
test('each GitHub field must equal its exact expected source, job and attempt identity', () => {
    for (const origin of ['ordinary', 'initial']) for (const [field, name] of Object.entries(IDENTITIES)) {
        const f = fixture(origin);
        changed(f, next => { next.value.github[field] += '-stale'; });
        changed(f, next => { next.expected[name] += '-stale'; });
        changed(f, next => { delete next.expected[name]; });
    }
});
test('workflow file and complete expected workflow ref cannot switch profile or source ref', () => {
    for (const profile of ['desktop', 'full']) {
        const f = fixture('ordinary', profile, 'macos-arm64');
        for (const workflow of ['.github/workflows/dependency-cache-bootstrap.yml',
            profile === 'full' ? '.github/workflows/desktop-cross-host.yml' : '.github/workflows/ci.yml', 'ci.yml'])
            changed(f, next => { next.value.github.workflow = workflow; });
        changed(f, next => { next.expected.GITHUB_WORKFLOW_REF += '-stale'; });
        changed(f, next => { delete next.expected.GITHUB_WORKFLOW_REF; });
    }
});
test('initial event must remain pull_request even when a different event agrees with expected', () => {
    for (const event of ['push', 'workflow_dispatch', 'schedule', 'pull_request_target'])
        changed(fixture('initial'), next => { next.expected.GITHUB_EVENT_NAME = next.value.github.event = event; });
});
test('only actual nonempty ASCII Buffers are result frames', () => {
    const f = fixture();
    for (const value of [undefined, null, true, frame(f.value).toString('ascii'), new Uint8Array(frame(f.value)), {}, []])
        changedRaw(f, () => value);
    changedRaw(f, () => Buffer.alloc(0));
    changedRaw(f, raw => Buffer.concat([raw, Buffer.from([0x80])]));
    changedRaw(f, raw => Buffer.concat([raw, Buffer.from([0xff])]));
});
test('malformed JSON fails as syntax, not as a successful or empty result', () => {
    const f = fixture();
    for (const text of ['{', '{"schema":', 'undefined', frame(f.value).toString('ascii') + '{}', '{"bad":"\\x41"}\n'])
        changedRaw(f, () => Buffer.from(text, 'ascii'), true);
});
test('valid JSON primitives and arrays are not controller records', () => {
    for (const value of [null, true, false, 0, 'record', [], [1]]) changedRaw(fixture(), () => frame(value));
});
test('exactly one LF and no leading, trailing, CRLF or pretty-print whitespace is accepted', () => {
    const f = fixture();
    for (const mutate of [raw => raw.subarray(0, raw.length - 1), raw => Buffer.concat([raw, Buffer.from('\n')]),
        raw => Buffer.from(raw.toString('ascii').replace(/\n$/, '\r\n'), 'ascii'),
        raw => Buffer.concat([Buffer.from(' '), raw]), raw => Buffer.concat([raw, Buffer.from(' ')]),
        raw => Buffer.from(raw.toString('ascii').replace('{', '{ '), 'ascii')]) changedRaw(f, mutate);
});
test('duplicate keys and unsorted object members cannot substitute equal parsed DATA', () => {
    const f = fixture();
    changedRaw(f, () => Buffer.from(JSON.stringify(f.value) + '\n', 'ascii'));
    editRaw(f, '"schema":1', '"schema":1,"schema":1');
    editRaw(f, '"commit":"' + f.value.source.commit + '"',
        '"commit":"' + f.value.source.commit + '","commit":"' + f.value.source.commit + '"');
    const source = f.value.source;
    editRaw(f, '"source":{"commit":"' + source.commit + '","tree":"' + source.tree + '"}',
        '"source":{"tree":"' + source.tree + '","commit":"' + source.commit + '"}');
});
test('fractional, exponent, negative-zero and unsafe integer encodings fail closed', () => {
    const f = fixture();
    for (const spelling of ['1.0', '1e0', '-0']) editRaw(f, '"schema":1', '"schema":' + spelling);
    for (const spelling of ['321.0', '3.21e2', '-0', '9007199254740992'])
        editRaw(f, '"controllerPid":321', '"controllerPid":' + spelling);
});
test('equivalent slash, ASCII and uppercase Unicode escape aliases are rejected', () => {
    const f = fixture();
    editRaw(f, 'p2pKit/P2pKit', 'p2pKit\\/P2pKit');
    editRaw(f, '"schema":1', '"\\u0073chema":1');
    const unicode = fixture('ordinary', 'desktop', 'linux-x64', '/model/caf\u00e9');
    editRaw(unicode, '\\u00e9', '\\u00E9');
    changedRaw(unicode, raw => Buffer.from(raw.toString('ascii').replace('\\u00e9', '\u00e9'), 'utf8'));
});
test('all three readiness outputs require the literal lowercase string true', () => {
    for (const name of ['dependency_seed_ready', 'dependency_cache_ready', 'native_provider_ready'])
        for (const value of [true, false, 1, 'True', 'false', '1', '', null])
            changed(fixture(), next => { next.value.outputs[name] = value; });
});
test('every output digest including initial history requires exactly lowercase SHA256 shape', () => {
    for (const origin of ['ordinary', 'initial']) for (const name of namesFor(origin).filter(name => name.endsWith('_sha256')))
        for (const value of ['A'.repeat(64), 'g'.repeat(64), 'a'.repeat(63), 'a'.repeat(65), true, null])
            changed(fixture(origin), next => { next.value.outputs[name] = value; });
});
test('output values reject nonstrings, emptiness, oversize and control-character injection', () => {
    for (const name of namesFor('initial')) for (const value of ['', [], {}, true, null, 'x'.repeat(4097),
        'x\nforged=true', 'x\rforged=true', 'x\0y', 'x\ty', 'x\u007fy'])
        changed(fixture('initial'), next => { next.value.outputs[name] = value; });
});
test('POSIX and Windows seed homes must equal the fixed literal current model home', () => {
    for (const role of ['linux-x64', 'windows-x64']) {
        const f = fixture('ordinary', 'desktop', role), home = f.value.outputs.dependency_seed_home;
        for (const value of ['relative/home', home + '/', home + '/..', home + '-other', home.toUpperCase()])
            changed(f, next => { next.value.outputs.dependency_seed_home = value; });
        changed(f, next => { next.expected.RUNNER_TEMP += '-other'; });
        changed(f, next => { next.expected.RUNNER_TEMP = 'relative-temp'; });
    }
});
test('cache path cannot change directory, omit the cohort suffix or use an alternate spelling', () => {
    for (const role of ['linux-x64', 'windows-x64']) {
        const f = fixture('ordinary', 'desktop', role), path = f.value.outputs.cache_path;
        for (const value of [f.value.outputs.dependency_seed_home, path + '/', path + '/..', path + '-other',
            path.replace('files-2.1', 'files-2.0')]) changed(f, next => { next.value.outputs.cache_path = value; });
    }
});
test('cache key keeps exact namespace, profile, role and both lowercase full digest components', () => {
    const f = fixture(), key = f.value.outputs.cache_key;
    for (const value of [key.replace('-v1-', '-v2-'), key.replace('-desktop-', '-full-'),
        key.replace('-linux-x64-', '-macos-x64-'), key.replace('7'.repeat(64), 'a'.repeat(63)),
        key.replace('8'.repeat(64), 'B'.repeat(64)), key + '-extra', 'prefix-' + key])
        changed(f, next => { next.value.outputs.cache_key = value; });
});

function main() {
    sources = readSources();
    for (const [index, item] of cases.entries()) {
        try { item.body(); }
        catch (error) {
            console.error('FAIL ' + (index + 1) + ' - ' + item.name + '\n' + String(error && error.stack || error));
            process.exitCode = 1;
            return; // Exact first failure; no retries or later controls.
        }
        console.log('ok ' + (index + 1) + ' - ' + item.name);
    }
    console.log(cases.length + '/' + cases.length + ' pure Action DATA controls passed; transport/native/provider qualification NOT_RUN');
}
if (require.main === module) {
    try { main(); }
    catch (error) {
        console.error('FAIL source setup: ' + String(error && error.stack || error));
        process.exitCode = 1;
    }
}
