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
        if (!result) result = realLifetime();
        if (result) { fprintf(stderr, "Native shell retirement control failed: %d\n", result); return 1; }
        puts("PASS: native shell result-before-exit, positive retirement and fail-closed observation controls");
        return 0;
    }
}
