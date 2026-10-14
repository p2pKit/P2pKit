/* Native controls for the actual read-only Terminal shell-retirement helper.
 * No Terminal/GUI launch. The current-host native executor owns this executable
 * and its one forked child. No numeric PID is ever used to send a signal.
 */
#define main terminal_application_main_not_invoked_by_fixture
#include "../../diagnostics/apple-terminal-context.m"
#undef main
#include <stdio.h>
#include <sys/select.h>
#include <sys/wait.h>

static int decisions(void) {
    uid_t uid = getuid();
    NSDictionary *shell = @{@"pid":@17, @"uid":@(uid), @"uniqueId":@101, @"startSeconds":@123, @"startMicroseconds":@45};
    if (!validShell(shell, uid) || validShell(shell, 0)) return 1;
    for (NSDictionary *change in @[@{@"pid":@YES}, @{@"uid":@0}, @{@"uniqueId":@0},
            @{@"uniqueId":@1.5}, @{@"startSeconds":@(-1)}, @{@"startMicroseconds":@1000000}, @{@"unknown":@1}]) {
        NSMutableDictionary *invalid = [shell mutableCopy];
        [invalid addEntriesFromDictionary:change];
        if (validShell(invalid, uid)) return 2;
    }
    RpcShellIdentity value = {0};
    value.bsd.pbi_pid = 17; value.bsd.pbi_uid = uid; value.bsd.pbi_ruid = uid; value.bsd.pbi_status = 3;
    value.bsd.pbi_start_tvsec = 123; value.bsd.pbi_start_tvusec = 45; value.unique.uniqueId = 101;
    if (shellRetirementObservation(shell, uid, &value, sizeof(value), 0) != 0) return 3;
    value.unique.pidVersion++; /* Exec is the SAME lifetime, not retirement. */
    if (shellRetirementObservation(shell, uid, &value, sizeof(value), 0) != 0) return 4;
    value.bsd.pbi_status = 5; /* A zombie still needs retirement/reaping. */
    if (shellRetirementObservation(shell, uid, &value, sizeof(value), 0) != 0) return 5;
    value.bsd.pbi_status = 3;
    value.bsd.pbi_ruid++;
    if (shellRetirementObservation(shell, uid, &value, sizeof(value), 0) != -1) return 6;
    value.bsd.pbi_ruid = uid;
    value.unique.uniqueId++;
    if (shellRetirementObservation(shell, uid, &value, sizeof(value), 0) != 1) return 7;
    value.unique.uniqueId = 101;
    for (NSNumber *error in @[@0, @(EPERM), @(EACCES), @(EINVAL), @(EIO)]) {
        if (shellRetirementObservation(shell, uid, &value, 0, error.intValue) != -1) return 8;
    }
    for (NSNumber *error in @[@(ESRCH), @(ENOENT)]) {
        if (shellRetirementObservation(shell, uid, &value, 0, error.intValue) != 1) return 9;
    }
    if (shellRetirementObservation(shell, uid, &value, sizeof(value) - 1, 0) != -1) return 10;
    value.unique.uniqueId = 0;
    if (shellRetirementObservation(shell, uid, &value, sizeof(value), 0) != -1) return 11;
    return 0;
}

/* Actual shared finalizer with deterministic read/clock/action dependencies.
 * This is refusal/control evidence, not a Terminal launch or cancellation run. */
static int finalizationDecisions(void) {
    uid_t uid = getuid();
    NSDictionary *source = @{@"commit":@"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                             @"tree":@"bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"};
    NSDictionary *terminal = @{@"pid":@10, @"uid":@(uid), @"startSeconds":@100, @"startMicroseconds":@50};
    NSDictionary *shell = @{@"pid":@17, @"uid":@(uid), @"uniqueId":@101, @"startSeconds":@123, @"startMicroseconds":@45};
    NSArray *cases = @[
        @{@"case":@"success", @"code":@0, @"failure":@"NONE", @"quit":@YES, @"terminated":@YES},
        @{@"case":@"product-failure", @"code":@1, @"failure":@"NONE", @"quit":@YES, @"terminated":@YES},
        @{@"case":@"child-125", @"code":@125, @"failure":@"NONE", @"quit":@YES, @"terminated":@YES},
        @{@"case":@"child-source", @"code":@125, @"failure":@"CHILD_SOURCE", @"quit":@YES, @"terminated":@YES},
        @{@"case":@"child-source-unknown", @"code":@125, @"failure":@"CHILD_SOURCE"},
        @{@"case":@"no-app", @"code":@125, @"failure":@"APPLICATION_IDENTITY"},
        @{@"case":@"no-reap", @"code":@125, @"failure":@"CHILD_REAP"},
        @{@"case":@"no-registration", @"code":@125, @"failure":@"SHELL_REGISTRATION"},
        @{@"case":@"bad-source", @"code":@125, @"failure":@"SHELL_REGISTRATION"},
        @{@"case":@"source-mismatch", @"code":@125, @"failure":@"SHELL_REGISTRATION"},
        @{@"case":@"app-mismatch", @"code":@125, @"failure":@"SHELL_REGISTRATION"},
        @{@"case":@"extra-key", @"code":@125, @"failure":@"SHELL_REGISTRATION"},
        @{@"case":@"bad-schema", @"code":@125, @"failure":@"SHELL_REGISTRATION"},
        @{@"case":@"empty-shells", @"code":@125, @"failure":@"SHELL_REGISTRATION"},
        @{@"case":@"too-many-shells", @"code":@125, @"failure":@"SHELL_REGISTRATION"},
        @{@"case":@"duplicate-shell", @"code":@125, @"failure":@"SHELL_REGISTRATION"},
        @{@"case":@"app-as-shell", @"code":@125, @"failure":@"SHELL_REGISTRATION"},
        @{@"case":@"root-shell", @"code":@125, @"failure":@"SHELL_REGISTRATION"},
        @{@"case":@"unknown-retirement", @"code":@125, @"failure":@"SHELL_OBSERVATION"},
        @{@"case":@"live-shell", @"code":@125, @"failure":@"SHELL_RETIREMENT"},
        @{@"case":@"mixed-shells", @"code":@125, @"failure":@"SHELL_RETIREMENT"},
        @{@"case":@"retirement-deadline", @"code":@125, @"failure":@"SHELL_RETIREMENT"},
        @{@"case":@"identity-changed", @"code":@125, @"failure":@"APPLICATION_IDENTITY_CHANGED"},
        @{@"case":@"identity-deadline", @"code":@125, @"failure":@"QUIT_REQUEST"},
        @{@"case":@"quit-refused", @"code":@125, @"failure":@"QUIT_REQUEST", @"quit":@YES},
        @{@"case":@"quit-incomplete", @"code":@125, @"failure":@"QUIT_COMPLETION", @"quit":@YES},
        @{@"case":@"shared-deadline", @"code":@125, @"failure":@"QUIT_COMPLETION", @"quit":@YES},
        @{@"case":@"within-deadline", @"code":@0, @"failure":@"NONE", @"quit":@YES, @"terminated":@YES}
    ];
    for (NSDictionary *scenario in cases) {
        NSString *name = scenario[@"case"];
        BOOL (^is)(NSString *) = ^BOOL(NSString *value) { return [name isEqualToString:value]; };
        NSMutableDictionary *result = [@{@"applicationCreated":@(!is(@"no-app")),
            @"scriptChildReaped":@(!is(@"no-reap")), @"exitCode":@125,
            @"failureCheck":is(@"no-app") ? @"APPLICATION_IDENTITY" : is(@"no-reap") ? @"CHILD_REAP" : @"CHILD_SOURCE"} mutableCopy];
        NSNumber *childCode = is(@"product-failure") ? @1 : is(@"child-125") ? @125 : @0;
        if (is(@"child-source") || is(@"child-source-unknown") || is(@"no-app") || is(@"no-reap")) childCode = nil;
        NSDictionary *expectedSource = is(@"bad-source") ? @{} : source;
        NSMutableDictionary *registration = [@{@"schema":@1, @"source":source, @"terminal":terminal, @"shells":@[shell]} mutableCopy];
        if (is(@"no-registration")) registration = nil;
        if (is(@"source-mismatch")) registration[@"source"] = @{};
        if (is(@"app-mismatch")) registration[@"terminal"] = @{};
        if (is(@"extra-key")) registration[@"extra"] = @1;
        if (is(@"bad-schema")) registration[@"schema"] = @YES;
        if (is(@"empty-shells")) registration[@"shells"] = @[];
        if (is(@"too-many-shells")) {
            NSMutableArray *tooMany = [NSMutableArray array];
            for (int i = 0; i < 31; i++) [tooMany addObject:shell];
            registration[@"shells"] = tooMany;
        }
        if (is(@"duplicate-shell")) registration[@"shells"] = @[shell, shell];
        if (is(@"app-as-shell") || is(@"root-shell") || is(@"mixed-shells")) {
            NSMutableDictionary *changed = [shell mutableCopy];
            changed[is(@"root-shell") ? @"uid" : @"pid"] = is(@"root-shell") ? @0 : is(@"mixed-shells") ? @18 : @10;
            registration[@"shells"] = is(@"mixed-shells") ? @[shell, changed] : @[changed];
        }
        __block NSTimeInterval now = 100;
        __block int waits = 0, observations = 0, identities = 0, quits = 0;
        __block BOOL orderValid = YES, budgetValid = YES;
        RpcTerminalFinalization operations = {
            .now = ^NSTimeInterval{ return now; },
            .wait = ^BOOL(NSTimeInterval seconds, BOOL (^finished)(void)) {
                waits++;
                if (seconds != 130 - now) budgetValid = NO;
                BOOL done = finished();
                if (!done || (waits == 1 && is(@"retirement-deadline"))) now += seconds;
                else if (is(@"shared-deadline") || is(@"within-deadline"))
                    now += waits == 1 ? 22 : is(@"shared-deadline") ? 9 : 7;
                return done;
            },
            .retirement = ^int(NSDictionary *value) {
                observations++;
                if (identities || quits) orderValid = NO;
                return is(@"unknown-retirement") || is(@"child-source-unknown") ? -1 :
                    is(@"live-shell") || (is(@"mixed-shells") && [value[@"pid"] intValue] == 18) ? 0 : 1;
            },
            .originalIdentity = ^BOOL{
                identities++;
                if (![result[@"commandShellsRetired"] boolValue] || quits) orderValid = NO;
                if (is(@"identity-deadline")) now = 130;
                return !is(@"identity-changed");
            },
            .requestQuit = ^BOOL{
                quits++;
                if (identities != 1 || ![result[@"originalApplicationIdentity"] boolValue] || now >= 130) orderValid = NO;
                return !is(@"quit-refused");
            },
            .terminated = ^BOOL{ return !is(@"quit-incomplete"); }
        };
        int outcome = finalizeApplication(result, registration, expectedSource, terminal, uid, childCode, 130, operations);
        BOOL noAuthority = is(@"no-app") || is(@"no-reap") || [scenario[@"failure"] isEqual:@"SHELL_REGISTRATION"];
        if (outcome != [scenario[@"code"] intValue] || ![result[@"exitCode"] isEqual:scenario[@"code"]] ||
            ![result[@"failureCheck"] isEqual:scenario[@"failure"]] ||
            quits != [scenario[@"quit"] boolValue] ||
            [result[@"applicationQuitRequested"] boolValue] != ([scenario[@"quit"] boolValue] && !is(@"quit-refused")) ||
            [result[@"applicationTerminated"] boolValue] != [scenario[@"terminated"] boolValue] ||
            !orderValid || !budgetValid || (noAuthority && (waits || observations || identities || quits))) {
            fprintf(stderr, "Finalization decision failed: %s\n", name.UTF8String);
            return 30;
        }
    }
    return 0;
}

static int realLifetime(void) {
    int ready[2], release[2];
    if (pipe(ready)) return 20;
    if (pipe(release)) { close(ready[0]); close(ready[1]); return 21; }
    pid_t child = fork();
    if (child == 0) {
        close(ready[0]); close(release[1]);
        /* Like shell-result.txt, this byte exists BEFORE its writer exits. */
        if (write(ready[1], "R", 1) != 1) _exit(23);
        close(ready[1]);
        char byte;
        ssize_t size;
        do { size = read(release[0], &byte, 1); } while (size < 0 && errno == EINTR);
        close(release[0]);
        _exit(size == 0 ? 0 : 24); /* Exact parent closes its owned release pipe. */
    }
    close(ready[1]); close(release[0]);
    int result = child < 0 ? 22 : 0;
    if (!result) {
        fd_set set; FD_ZERO(&set); FD_SET(ready[0], &set);
        struct timeval bound = {.tv_sec = 3, .tv_usec = 0};
        char byte;
        if (select(ready[0] + 1, &set, NULL, NULL, &bound) != 1 || read(ready[0], &byte, 1) != 1 || byte != 'R') result = 25;
    }
    RpcShellIdentity value = {0};
    NSDictionary *shell = nil;
    if (!result) {
        if (proc_pidinfo(child, 18, 1, &value, sizeof(value)) != (int)sizeof(value) ||
            value.bsd.pbi_pid != (uint32_t)child || value.bsd.pbi_ppid != (uint32_t)getpid()) result = 26;
        else {
            shell = @{@"pid":@(child), @"uid":@(getuid()), @"uniqueId":@(value.unique.uniqueId),
                      @"startSeconds":@(value.bsd.pbi_start_tvsec), @"startMicroseconds":@(value.bsd.pbi_start_tvusec)};
            if (shellRetirement(shell, getuid()) != 0) result = 27;
        }
    }
    close(ready[0]); close(release[1]);
    int status = 0;
    if (child > 0) {
        pid_t reaped;
        do { reaped = waitpid(child, &status, 0); } while (reaped < 0 && errno == EINTR);
        if (reaped != child || !WIFEXITED(status) || WEXITSTATUS(status) != 0) result = 28;
    }
    if (!result && shellRetirement(shell, getuid()) != 1) result = 29;
    return result;
}

int main(void) {
    @autoreleasepool {
        if (!getuid() || getuid() != geteuid() || getgid() != getegid()) return 125;
        int result = decisions();
        if (!result) result = finalizationDecisions();
        if (!result) result = realLifetime();
        if (result) { fprintf(stderr, "Native shell retirement control failed: %d\n", result); return 1; }
        puts("PASS: native shell result-before-exit, positive retirement and fail-closed observation controls");
        return 0;
    }
}
