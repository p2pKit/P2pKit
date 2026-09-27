'use strict';

// Two fixed controller launchers, not the service-only provider Node entry.
// Actual successful child return/EOF/close precedes every safe Action output.
// Python owns the real native source/provider episodes; this transport cannot
// infer descendant retirement from killing a lost controller. HOLD on failure.
const fs = require('node:fs');
const paths = require('node:path');
const {spawn, ChildProcess} = require('node:child_process');
const {Readable} = require('node:stream');
const windows = process.platform === 'win32', path = windows ? paths.win32 : paths.posix;
const root = path.resolve(__dirname, '../../..');
const helper = path.join(root, 'scripts', 'run-hosted-test-custody.py');
const NS = 1000000000n, LIMIT = 16384;
const IDENTITY = Object.freeze(['GITHUB_ACTIONS', 'GITHUB_REPOSITORY', 'GITHUB_SHA', 'GITHUB_REF', 'GITHUB_RUN_ID',
    'GITHUB_RUN_ATTEMPT', 'GITHUB_EVENT_NAME', 'GITHUB_WORKFLOW_REF', 'GITHUB_WORKFLOW_SHA', 'GITHUB_WORKSPACE',
    'GITHUB_EVENT_PATH', 'GITHUB_SERVER_URL', 'GITHUB_API_URL', 'GITHUB_JOB', 'RUNNER_OS', 'RUNNER_ARCH', 'RUNNER_NAME',
    'RUNNER_ENVIRONMENT', 'RUNNER_TEMP', 'ImageOS', 'ImageVersion']);
const NATIVE = Object.freeze(['HOME', 'USERPROFILE', 'SYSTEMROOT', 'WINDIR', 'COMSPEC', 'PATHEXT', 'APPDATA',
    'LOCALAPPDATA', 'NUMBER_OF_PROCESSORS', 'PROCESSOR_ARCHITECTURE', 'DEVELOPER_DIR', 'JAVA_HOME', 'P2PKIT_AUDIT_JDK21',
    'ANDROID_HOME', 'LANG', 'LC_ALL', 'P2PKIT_AUDIT_JOB_ID', 'P2PKIT_AUDIT_OWNERSHIP_CHAIN',
    'P2PKIT_AUDIT_OWNERSHIP_DOMAINS', 'P2PKIT_AUDIT_STATE_DIR', 'GRADLE_USER_HOME']);
const SERVICE = Object.freeze(['ACTIONS_RUNTIME_TOKEN', 'ACTIONS_RESULTS_URL', 'ACTIONS_CACHE_SERVICE_V2']);
const API_TOKEN = 'P2PKIT_ACTIONS_READ_TOKEN';
const SECRETS = Object.freeze([...SERVICE, API_TOKEN]);
const OUTPUTS = Object.freeze(['dependency_seed_ready', 'dependency_cache_ready', 'native_provider_ready',
    'dependency_seed_home', 'dependency_seed_staging_sha256', 'preparation_sha256', 'restoration_sha256', 'cache_key', 'cache_path']);
const BLOCKED = new Set(['JAVA_OPTS', 'GRADLE_OPTS', 'JAVA_TOOL_OPTIONS', 'JDK_JAVA_OPTIONS', '_JAVA_OPTIONS',
    'BASH_ENV', 'ENV', 'ZDOTDIR', 'PYTHONPATH', 'PYTHONHOME', 'PYTHONSTARTUP', 'PYTHONINSPECT', 'NODE_OPTIONS', 'NODE_PATH',
    'KONAN_HOME', 'KOTLIN_HOME', 'KOTLIN_OPTS', 'KONAN_OPTS', 'KONAN_JVM_ARGS', 'KOTLIN_NATIVE_HOME', 'SDKROOT',
    'TOOLCHAINS', 'XCODE_XCCONFIG_FILE']);
const quarantine = [];
let used = false;
let lostController = false;
function need(value) { if (!value) throw new Error('NATIVE_CACHE_CONTROLLER_HOLD'); }
function absolute(value) {
    return typeof value === 'string' && value.length > 0 && value.length <= 4096 &&
        !/[\x00-\x1f\x7f]/.test(value) && path.isAbsolute(value) && path.normalize(value) === value;
}
function keys(value, names) {
    need(value && Object.getPrototypeOf(value) === Object.prototype &&
        Object.keys(value).sort().join('\0') === [...names].sort().join('\0'));
}
function canonical(value) {
    if (value === null || typeof value === 'boolean' || typeof value === 'string') return JSON.stringify(value);
    if (typeof value === 'number') { need(Number.isSafeInteger(value) && !Object.is(value, -0)); return String(value); }
    if (Array.isArray(value)) return '[' + value.map(canonical).join(',') + ']';
    need(value && Object.getPrototypeOf(value) === Object.prototype);
    return '{' + Object.keys(value).sort().map(key => JSON.stringify(key) + ':' + canonical(value[key])).join(',') + '}';
}
function asciiCanonical(value) {
    // Python's fixed ensure_ascii form, including non-ASCII runner path units.
    return (canonical(value) + '\n').replace(/[\u007f-\uffff]/g,
        char => '\\u' + char.charCodeAt(0).toString(16).padStart(4, '0'));
}
function installedPython(toolPath) {
    const names = windows ? ['python.exe', 'python3.exe'] : ['python3'];
    for (const directory of toolPath.split(windows ? ';' : ':')) {
        need(absolute(directory));
        for (const name of names) {
            const candidate = path.join(directory, name);
            try {
                const actual = fs.realpathSync.native(candidate);
                need(absolute(actual) && /^python(?:3(?:\.\d+)?)?(?:\.exe)?$/.test(path.basename(actual)) &&
                    fs.statSync(actual).isFile());
                fs.accessSync(actual, windows ? fs.constants.F_OK : fs.constants.X_OK);
                return actual;
            } catch (error) {
                if (error.code !== 'ENOENT' && error.code !== 'ENOTDIR') throw error;
            }
        }
    }
    need(false);
}
function environment() {
    need(!['GH_TOKEN', 'GITHUB_TOKEN', 'ACTIONS_CACHE_URL', 'ACTIONS_ID_TOKEN_REQUEST_TOKEN',
        'ACTIONS_ID_TOKEN_REQUEST_URL'].some(name => Object.hasOwn(process.env, name)));
    for (const [name, value] of Object.entries(process.env)) {
        need(!(value && (BLOCKED.has(name) || /^(?:DYLD_|LD_|BASH_FUNC_|ORG_GRADLE_PROJECT_)/.test(name))));
        need(!name.startsWith('GIT_') || name === 'GIT_TERMINAL_PROMPT');
    }
    need(/^24\./.test(process.versions.node) && absolute(process.execPath) &&
        fs.realpathSync.native(process.execPath) === process.execPath && fs.statSync(process.execPath).isFile());
    need(typeof process.env.PATH === 'string' && process.env.PATH.length <= 16384);
    const nodeDirectory = path.dirname(process.execPath);
    const toolPath = [nodeDirectory, ...process.env.PATH.split(windows ? ';' : ':')].join(windows ? ';' : ':');
    need(toolPath.length <= 16384 && toolPath.split(windows ? ';' : ':').every(absolute));
    const env = {};
    for (const name of [...IDENTITY, ...NATIVE]) if (Object.hasOwn(process.env, name)) env[name] = process.env[name];
    for (const name of SECRETS) {
        const value = process.env[name];
        need(typeof value === 'string' && value.length > 0 && value.length <= 4096 && !/[\x00-\x20\x7f-\uffff]/.test(value));
        env[name] = value;
        delete process.env[name];
    }
    // B's maintained environment validator authenticates no endpoint by shape;
    // actual runner/source/native qualification remains independently required.
    need(env.ACTIONS_CACHE_SERVICE_V2 === 'True');
    Object.assign(env, {PATH: toolPath, CI: 'true', GIT_TERMINAL_PROMPT: '0', PYTHONDONTWRITEBYTECODE: '1', PYTHONUNBUFFERED: '1'});
    return env;
}
function resultData(raw, origin, profile, role, childPid, expected) {
    need((origin === 'ordinary' || origin === 'initial') && (profile === 'full' || profile === 'desktop') &&
        ['linux-x64', 'windows-x64', 'macos-x64', 'macos-arm64'].includes(role) &&
        (profile !== 'full' || role.startsWith('macos-')));
    need(Buffer.isBuffer(raw) && raw.length > 0 && raw.length <= LIMIT && raw.every(byte => byte < 128));
    const value = JSON.parse(raw.toString('ascii'));
    need(Buffer.from(asciiCanonical(value), 'ascii').equals(raw));
    keys(value, ['schema', 'scope', 'profile', 'role', 'controllerPid', 'source', 'github', 'outputs', 'retirement',
        'errors', 'enclosingActionReturn', 'resolverAcceptance']);
    need(value.schema === 1 && value.scope === (origin === 'initial' ? 'INITIAL_ORDINARY_' : 'ORDINARY_') +
        'CACHE_PROVIDER_CONTROLLER_PENDING_ACTION_CLOSE_V1' && value.profile === profile && value.role === role &&
        Number.isSafeInteger(value.controllerPid) && value.controllerPid > 0 && value.controllerPid === childPid &&
        value.retirement === 'KNOWN' && Array.isArray(value.errors) && value.errors.length === 0 &&
        value.enclosingActionReturn === 'NOT_OBSERVED' && value.resolverAcceptance === 'NOT_PERFORMED');
    keys(value.source, ['commit', 'tree']);
    need(value.source.commit === expected.GITHUB_SHA && /^[0-9a-f]{40}$/.test(value.source.tree));
    const fields = {repository: 'GITHUB_REPOSITORY', event: 'GITHUB_EVENT_NAME', ref: 'GITHUB_REF',
        workflowSha: 'GITHUB_WORKFLOW_SHA', job: 'GITHUB_JOB', runId: 'GITHUB_RUN_ID', runAttempt: 'GITHUB_RUN_ATTEMPT'};
    keys(value.github, [...Object.keys(fields), 'workflow']);
    for (const [field, name] of Object.entries(fields)) need(value.github[field] === expected[name]);
    need(value.github.workflow === (profile === 'full' ? '.github/workflows/ci.yml' : '.github/workflows/desktop-cross-host.yml') &&
        expected.GITHUB_WORKFLOW_REF === value.github.repository + '/' + value.github.workflow + '@' + value.github.ref &&
        (origin !== 'initial' || value.github.event === 'pull_request'));
    const names = [...OUTPUTS, ...(origin === 'initial' ? ['initial_current_history_sha256'] : [])];
    keys(value.outputs, names);
    for (const [name, item] of Object.entries(value.outputs)) {
        need(typeof item === 'string' && item.length > 0 && item.length <= 4096 && !/[\x00-\x1f\x7f]/.test(item));
        if (name.endsWith('_sha256')) need(/^[0-9a-f]{64}$/.test(item));
        if (name.endsWith('_ready')) need(item === 'true');
    }
    const home = path.join(expected.RUNNER_TEMP, 'p2pkit-dependency-seed-' + profile + '-' + role, 'restore-home');
    need(absolute(home) && value.outputs.dependency_seed_home === home &&
        value.outputs.cache_path === path.join(home, 'caches', 'modules-2', 'files-2.1') &&
        new RegExp('^p2pkit-dependency-files-v1-' + profile + '-' + role + '-[0-9a-f]{64}-[0-9a-f]{64}$').test(value.outputs.cache_key));
    return names.map(name => name + '=' + value.outputs[name] + '\n').join('');
}
function transport(python, argv, env, end) {
    return new Promise((resolve, reject) => {
        let child, spawned = false, exited = false, closed = false, stdoutEnded = false, stderrEnded = false;
        let stdoutClosed = false, stderrClosed = false, stdout = Buffer.alloc(0), stderrBytes = 0, original = null;
        let timer, killTimer, lostTimer, settled = false;
        const signals = ['SIGINT', 'SIGTERM', ...(windows ? ['SIGBREAK'] : [])];
        const record = {child: null, errors: [], stdout: null};
        function check() { need(!original && process.hrtime.bigint() < end); }
        function finish(success) {
            if (settled) return;
            settled = true;
            clearTimeout(timer); clearTimeout(killTimer); clearTimeout(lostTimer);
            for (const number of signals) process.removeListener(number, cancelled);
            for (const name of SECRETS) delete env[name];
            if (success) resolve({raw: stdout, pid: child.pid});
            else { record.stdout = stdout; quarantine.push(record); reject(original || new Error('NATIVE_CACHE_CONTROLLER_HOLD')); }
        }
        function fail(error) {
            if (settled) return;
            if (original === null) original = error;
            record.errors.push(error); // Private only, never written to logs or output.
            clearTimeout(timer);
            if (closed || child === undefined) { finish(false); return; }
            if (killTimer !== undefined) return;
            try { child.kill('SIGTERM'); } catch (secondary) { record.errors.push(secondary); }
            killTimer = setTimeout(() => {
                try { child.kill('SIGKILL'); } catch (secondary) { record.errors.push(secondary); }
                lostTimer = setTimeout(() => { lostController = true; finish(false); }, 5000);
            }, 5000);
        }
        function cancelled() { fail(new Error('NATIVE_CACHE_CONTROLLER_CANCELLED')); }
        function guard(body) { try { check(); body(); } catch (error) { fail(error); } }
        try {
            check();
            child = spawn(python, argv, {cwd: root, env, shell: false, windowsHide: true, stdio: ['ignore', 'pipe', 'pipe']});
            record.child = child;
            need(child instanceof ChildProcess && child.stdout instanceof Readable && child.stderr instanceof Readable &&
                !child.stdout.readableObjectMode && !child.stderr.readableObjectMode &&
                child.stdout.readableEncoding === null && child.stderr.readableEncoding === null);
            child.on('error', fail);
            child.once('spawn', () => guard(() => { need(!spawned && !exited && !closed); spawned = true; }));
            child.once('exit', (code, signal) => guard(() => {
                need(spawned && !exited && !closed && code === 0 && signal === null); exited = true;
            }));
            child.stdout.on('data', chunk => guard(() => {
                need(spawned && !stdoutEnded && Buffer.isBuffer(chunk) && stdout.length + chunk.length <= LIMIT);
                stdout = Buffer.concat([stdout, chunk]);
            }));
            child.stderr.on('data', chunk => guard(() => {
                need(spawned && !stderrEnded && Buffer.isBuffer(chunk)); stderrBytes += chunk.length;
                need(stderrBytes <= LIMIT);
            }));
            child.stdout.once('end', () => guard(() => { need(!stdoutEnded); stdoutEnded = true; }));
            child.stderr.once('end', () => guard(() => { need(!stderrEnded); stderrEnded = true; }));
            child.stdout.once('close', () => { stdoutClosed = true; });
            child.stderr.once('close', () => { stderrClosed = true; });
            child.stdout.on('error', fail); child.stderr.on('error', fail);
            child.once('close', (code, signal) => {
                closed = true;
                if (original !== null) { finish(false); return; }
                guard(() => {
                    need(spawned && exited && stdoutEnded && stderrEnded && stdoutClosed && stderrClosed &&
                        code === 0 && signal === null && stderrBytes === 0 && stdout.length > 0);
                    finish(true);
                });
            });
            for (const number of signals) process.on(number, cancelled);
            timer = setTimeout(cancelled, Math.max(1, Number((end - process.hrtime.bigint()) / 1000000n)));
        } catch (error) { fail(error); }
    });
}
function appendOutput(target, text, end) {
    need(absolute(target) && fs.realpathSync.native(target) === target && process.hrtime.bigint() < end);
    const before = fs.lstatSync(target, {bigint: true});
    need(before.isFile() && before.nlink === 1n);
    const fd = fs.openSync(target, fs.constants.O_WRONLY | fs.constants.O_APPEND | (fs.constants.O_NOFOLLOW || 0));
    let failure = null;
    try {
        const current = fs.fstatSync(fd, {bigint: true});
        need(current.isFile() && current.dev === before.dev && current.ino === before.ino && current.nlink === 1n);
        fs.writeFileSync(fd, text, {encoding: 'utf8'}); fs.fsyncSync(fd);
        need(process.hrtime.bigint() < end);
    } catch (error) { failure = error; }
    try { fs.closeSync(fd); } catch (error) { failure = failure || error; }
    if (failure) throw failure;
    need(process.hrtime.bigint() < end);
}
async function run(origin) {
    process.exitCode = 125; // An unresolved promise is never a successful Action.
    let env;
    try {
        need(!used && (origin === 'ordinary' || origin === 'initial')); used = true;
        const profile = process.env.INPUT_PROFILE, output = process.env.GITHUB_OUTPUT;
        const role = ({linux: 'linux-', darwin: 'macos-', win32: 'windows-'})[process.platform] + process.arch;
        need((profile === 'full' || profile === 'desktop') && ['linux-x64', 'windows-x64', 'macos-x64', 'macos-arm64'].includes(role) &&
            (profile !== 'full' || role.startsWith('macos-')) && process.env.GITHUB_ACTIONS === 'true' &&
            process.env.GITHUB_REPOSITORY === 'p2pKit/P2pKit' && process.env.RUNNER_ENVIRONMENT === 'github-hosted' &&
            process.env.GITHUB_WORKSPACE === root && fs.realpathSync.native(root) === root && fs.statSync(helper).isFile());
        const end = process.hrtime.bigint() + BigInt(profile === 'full' ? 8400 : 1500) * NS;
        // Existing controller ceiling only; service-derived job/stage fences
        // are stricter and remain enforced by the real Python owner.
        const expected = Object.fromEntries(IDENTITY.map(name => [name, process.env[name]]));
        env = environment();
        const python = installedPython(env.PATH);
        const argv = ['-I', '-B', '-S', helper, origin === 'initial' ? 'initial-prepare-restore' : 'ordinary-prepare-restore',
            '--profile', profile];
        const returned = await transport(python, argv, env, end);
        const text = resultData(returned.raw, origin, profile, role, returned.pid, expected);
        appendOutput(output, text, end);
        process.exitCode = 0;
    } catch (_) {
        process.stderr.write('Native cache controller HOLD; no resolver/product acceptance; preserve private records.\n');
        process.exitCode = 125;
    } finally {
        for (const name of SECRETS) { delete process.env[name]; if (env) delete env[name]; }
    }
    // A lost controller has no known retirement claim. Bound the failed
    // transport's own lifetime; the hosted job must fail and quarantine it.
    // This does not certify or conceal descendant cleanup and cannot emit PASS.
    if (lostController) process.exit(125);
}
exports.mainOrdinary = () => run('ordinary');
exports.mainInitial = () => run('initial');
// Pure DATA helpers only for focused controls; no alternate executor injection.
exports.resultData = resultData;
if (require.main === module) exports.mainOrdinary();
