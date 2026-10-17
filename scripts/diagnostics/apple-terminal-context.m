/* Disposable Terminal application lease, not a product/ownership admission.
 * LaunchServices opens ONE fresh, fixed .command as the existing console user.
 * No AppleScript, clicks, permission edits, forced termination or PID signaling.
 * Retain the exact NSRunningApplication object and verify its original native
 * start identity before requesting its ordinary Quit, only after child result
 * AND the .command shell's positively observed retirement, within the SAME
 * original 30-second finalization bound. Never change Terminal preferences.
 */
#import <AppKit/AppKit.h>
#include <errno.h>
#include <libproc.h>
#include <stdint.h>
#include <sys/stat.h>
#include <unistd.h>
#ifdef P2PKIT_APPLE_CI_CANDIDATE
#include <mach/mach_time.h>
#include <math.h>
#include <sys/sysctl.h>
#include <time.h>
#endif

static BOOL waitUntil(NSTimeInterval seconds, BOOL (^finished)(void)) {
    NSTimeInterval end = NSProcessInfo.processInfo.systemUptime + seconds;
    while (!finished() && NSProcessInfo.processInfo.systemUptime < end) {
        [NSRunLoop.currentRunLoop runMode:NSDefaultRunLoopMode beforeDate:[NSDate dateWithTimeIntervalSinceNow:0.05]];
        [NSThread sleepForTimeInterval:0.01];
    }
    return finished();
}

static BOOL save(NSURL *url, NSDictionary *value) {
    NSError *error = nil;
    NSData *bytes = [NSJSONSerialization dataWithJSONObject:value options:NSJSONWritingSortedKeys error:&error];
    return bytes && !error && [bytes writeToURL:url options:NSDataWritingWithoutOverwriting error:&error] && !error;
}

static NSDictionary *readPrivate(NSURL *url, uid_t uid) {
    struct stat info;
    if (lstat(url.fileSystemRepresentation, &info) || !S_ISREG(info.st_mode) || info.st_uid != uid ||
        (info.st_mode & 0777) != 0600 || info.st_size <= 0 || info.st_size > 131072) return nil;
    NSData *bytes = [NSData dataWithContentsOfURL:url options:0 error:NULL];
    id value = bytes ? [NSJSONSerialization JSONObjectWithData:bytes options:0 error:NULL] : nil;
    return [value isKindOfClass:NSDictionary.class] ? value : nil;
}

static BOOL identity(pid_t pid, uid_t uid, struct proc_bsdinfo *value) {
    return proc_pidinfo(pid, PROC_PIDTBSDINFO, 0, value, sizeof(*value)) == (int)sizeof(*value) &&
        value->pbi_pid == (uint32_t)pid && value->pbi_uid == uid && value->pbi_ruid == uid;
}

/* The same fixed-width flavor-18 ABI used by audit_processes.py. These are
 * read-only birth observations, NOT an opaque signaling token or permission
 * to control a process. In particular, never inspect/adopt the root login. */
typedef struct {
    uint8_t uuid[16];
    uint64_t uniqueId, parentUniqueId;
    int32_t pidVersion, parentPidVersion;
    uint64_t reserved[2];
} RpcShellUnique;
typedef struct { struct proc_bsdinfo bsd; RpcShellUnique unique; } RpcShellIdentity;
_Static_assert(sizeof(RpcShellUnique) == 56 && sizeof(RpcShellIdentity) == 192, "Unsupported native shell ABI");

static BOOL integer(NSNumber *value, uint64_t minimum, uint64_t maximum) {
    if (![value isKindOfClass:NSNumber.class] || CFGetTypeID((__bridge CFTypeRef)value) == CFBooleanGetTypeID() ||
        CFNumberIsFloatType((__bridge CFNumberRef)value)) return NO;
    /* JSON integers only. No float truncation or negative-to-unsigned wrap. */
    NSString *text = value.stringValue;
    if (!text.length || [text rangeOfCharacterFromSet:NSCharacterSet.decimalDigitCharacterSet.invertedSet].location != NSNotFound) return NO;
    return value.unsignedLongLongValue >= minimum && value.unsignedLongLongValue <= maximum;
}

static BOOL validShell(NSDictionary *shell, uid_t uid) {
    return uid != 0 && [shell isKindOfClass:NSDictionary.class] && shell.count == 5 &&
        integer(shell[@"pid"], 2, INT32_MAX) && integer(shell[@"uid"], uid, uid) &&
        integer(shell[@"uniqueId"], 1, UINT64_MAX) && integer(shell[@"startSeconds"], 1, INT64_MAX) &&
        integer(shell[@"startMicroseconds"], 0, 999999);
}

/* -1 unknown/denied (fatal), 0 same lifetime (including a zombie), 1 positive
 * absence/replacement. Exec, PID-only census and result-file existence cannot
 * establish retirement. A replacement is never adopted or signaled. */
static int shellRetirementObservation(NSDictionary *shell, uid_t uid, const RpcShellIdentity *value, int count, int error) {
    if (!validShell(shell, uid)) return -1;
    if (count == 0 && (error == ESRCH || error == ENOENT)) return 1;
    if (count != (int)sizeof(*value) || value->bsd.pbi_pid != [shell[@"pid"] unsignedIntValue] ||
        !value->unique.uniqueId || !value->bsd.pbi_start_tvsec || value->bsd.pbi_start_tvusec >= 1000000) return -1;
    if (value->unique.uniqueId != [shell[@"uniqueId"] unsignedLongLongValue] ||
        value->bsd.pbi_start_tvsec != [shell[@"startSeconds"] unsignedLongLongValue] ||
        value->bsd.pbi_start_tvusec != [shell[@"startMicroseconds"] unsignedLongLongValue]) return 1;
    if (value->bsd.pbi_uid != uid || value->bsd.pbi_ruid != uid || value->bsd.pbi_status < 1 || value->bsd.pbi_status > 5) return -1;
    return 0;
}

static int shellRetirement(NSDictionary *shell, uid_t uid) {
    if (!validShell(shell, uid)) return -1;
    RpcShellIdentity value = {0};
    errno = 0;
    int count = proc_pidinfo([shell[@"pid"] intValue], 18, 1, &value, sizeof(value));
    return shellRetirementObservation(shell, uid, &value, count, errno);
}

/* These are the actual finalizer operations. The controller binds them to
 * read-only native observations and its retained application; fixtures bind
 * deterministic observations without opening an application or signaling. */
typedef struct {
    NSTimeInterval (^now)(void);
    BOOL (^wait)(NSTimeInterval, BOOL (^)(void));
    int (^retirement)(NSDictionary *);
    BOOL (^originalIdentity)(void);
    BOOL (^requestQuit)(void);
    BOOL (^terminated)(void);
} RpcTerminalFinalization;

static BOOL validSource(NSDictionary *source) {
    if (![source isKindOfClass:NSDictionary.class] || source.count != 2) return NO;
    NSCharacterSet *invalid = [NSCharacterSet characterSetWithCharactersInString:@"0123456789abcdef"].invertedSet;
    for (NSString *key in @[@"commit", @"tree"]) {
        NSString *value = source[key];
        if (![value isKindOfClass:NSString.class] || value.length != 40 ||
            [value rangeOfCharacterFromSet:invalid].location != NSNotFound) return NO;
    }
    return YES;
}

#ifdef P2PKIT_APPLE_CI_CANDIDATE
/* Inactive ordinary-CI candidate. These labels bind the private caller input;
 * they do not authenticate GitHub metadata or authorize product execution.
 * The supplier/keeper must admit the source, complete command and cancellation
 * contract independently. The normal build does not recognize mode "ci". */
static NSString *const ciClock = @"MACH_ABSOLUTE_NANOSECONDS_V1";
static const uint64_t ciSecond = 1000000000;

static BOOL ciHex(NSString *value, NSUInteger length) {
    return [value isKindOfClass:NSString.class] && value.length == length &&
        [value rangeOfCharacterFromSet:[NSCharacterSet characterSetWithCharactersInString:@"0123456789abcdef"].invertedSet].location == NSNotFound &&
        [value stringByReplacingOccurrencesOfString:@"0" withString:@""].length != 0;
}

static BOOL ciValidBoot(NSString *value) {
    if (![value isKindOfClass:NSString.class] || value.length != 36) return NO;
    NSArray *parts = [value componentsSeparatedByString:@"-"];
    if (parts.count != 5) return NO;
    NSArray *lengths = @[@8, @4, @4, @4, @12];
    for (NSUInteger i = 0; i < parts.count; i++) if ([parts[i] length] != [lengths[i] unsignedIntegerValue]) return NO;
    return ciHex([parts componentsJoinedByString:@""], 32);
}

static BOOL ciMachNanoseconds(uint64_t ticks, uint32_t numerator, uint32_t denominator, uint64_t *out) {
    if (!numerator || !denominator || !out) return NO;
    __uint128_t value = (__uint128_t)ticks * numerator / denominator;
    if (value > INT64_MAX) return NO;
    *out = (uint64_t)value;
    return YES;
}

static NSString *ciBootSession(void) {
    char value[37] = {0};
    size_t size = sizeof(value);
    if (sysctlbyname("kern.bootsessionuuid", value, &size, NULL, 0) || size != sizeof(value) || value[36]) return nil;
    NSString *boot = [[NSString alloc] initWithBytes:value length:36 encoding:NSASCIIStringEncoding].lowercaseString;
    return ciValidBoot(boot) ? boot : nil;
}

static NSDictionary *ciObserveClock(void) {
    mach_timebase_info_data_t scale = {0};
    uint64_t before, after;
    struct timespec wall = {0};
    if (mach_timebase_info(&scale) != KERN_SUCCESS ||
        !ciMachNanoseconds(mach_absolute_time(), scale.numer, scale.denom, &before)) return nil;
    NSString *boot = ciBootSession();
    if (!boot || clock_gettime(CLOCK_REALTIME, &wall)) return nil;
    NSString *afterBoot = ciBootSession();
    if (!ciMachNanoseconds(mach_absolute_time(), scale.numer, scale.denom, &after) ||
        after < before || after - before > 50000000 || ![afterBoot isEqual:boot] ||
        wall.tv_sec <= 0 || wall.tv_nsec < 0 || wall.tv_nsec >= (long)ciSecond) return nil;
    __uint128_t wallNs = (__uint128_t)wall.tv_sec * ciSecond + wall.tv_nsec;
    if (wallNs > INT64_MAX) return nil;
    /* Both boot reads and wall are inside the same before/after bracket as
     * admitted CPython >= 3.10. Wall is only a sleep/reversal guard. */
    return @{@"clock":ciClock, @"bootSession":boot, @"monotonicNs":@(before),
        @"wallNs":@((uint64_t)wallNs), @"sampleSpanNs":@(after - before)};
}

static BOOL ciProgress(NSDictionary *envelope, NSDictionary *observation) {
    if (![envelope isKindOfClass:NSDictionary.class] || ![observation isKindOfClass:NSDictionary.class] ||
        observation.count != 5 || ![envelope[@"clock"] isEqual:ciClock] || ![observation[@"clock"] isEqual:ciClock] ||
        !ciValidBoot(envelope[@"bootSession"]) || ![observation[@"bootSession"] isEqual:envelope[@"bootSession"]] ||
        !integer(envelope[@"boundAtMonotonicNs"], 0, INT64_MAX) || !integer(envelope[@"boundAtWallNs"], 1, INT64_MAX) ||
        !integer(envelope[@"boundSampleSpanNs"], 0, 50000000) ||
        !integer(observation[@"monotonicNs"], 0, INT64_MAX) || !integer(observation[@"wallNs"], 1, INT64_MAX) ||
        !integer(observation[@"sampleSpanNs"], 0, 50000000)) return NO;
    uint64_t mono = [observation[@"monotonicNs"] unsignedLongLongValue], wall = [observation[@"wallNs"] unsignedLongLongValue];
    uint64_t bound = [envelope[@"boundAtMonotonicNs"] unsignedLongLongValue], boundWall = [envelope[@"boundAtWallNs"] unsignedLongLongValue];
    uint64_t anchorSpan = [envelope[@"boundSampleSpanNs"] unsignedLongLongValue];
    uint64_t currentSpan = [observation[@"sampleSpanNs"] unsignedLongLongValue];
    if (mono > INT64_MAX - currentSpan || bound > INT64_MAX - anchorSpan || mono < bound || wall < boundWall) return NO;
    uint64_t monoDelta = mono - bound, wallDelta = wall - boundWall;
    /* Every wall sample lies somewhere in its fixed monotonic bracket. The
     * entire possible drift interval, not only its midpoint, must fit 1 second. */
    __int128 drift = (__int128)wallDelta - monoDelta;
    return drift + anchorSpan <= ciSecond && drift - currentSpan >= -(__int128)ciSecond;
}

static BOOL ciEnvelopeValid(NSDictionary *envelope, NSDictionary *config, NSString *tracking, NSString *path) {
    NSArray *keys = @[@"schema", @"scope", @"clock", @"source", @"profile", @"runId", @"runAttempt", @"jobId", @"invocationId", @"bootSession",
        @"boundAtMonotonicNs", @"boundAtWallNs", @"boundSampleSpanNs", @"productCutoffMonotonicNs", @"executorEndMonotonicNs",
        @"nativeFinalizerEndMonotonicNs", @"finalizationCutoffMonotonicNs", @"jobCutoffMonotonicNs"];
    if (![envelope isKindOfClass:NSDictionary.class] || ![config isKindOfClass:NSDictionary.class] ||
        ![[NSSet setWithArray:envelope.allKeys] isEqual:[NSSet setWithArray:keys]] ||
        !integer(envelope[@"schema"], 1, 1) || ![envelope[@"scope"] isEqual:@"ORDINARY_CI_APPLE_TERMINAL_CANDIDATE"] ||
        ![envelope[@"clock"] isEqual:ciClock] || !validSource(envelope[@"source"]) ||
        !ciHex(envelope[@"source"][@"commit"], 40) || !ciHex(envelope[@"source"][@"tree"], 40) ||
        ![envelope[@"source"] isEqual:config[@"source"]] || !ciValidBoot(envelope[@"bootSession"]) ||
        !ciHex(envelope[@"jobId"], 32) || !ciHex(envelope[@"invocationId"], 32) ||
        !integer(envelope[@"runId"], 1, INT64_MAX) || !integer(envelope[@"runAttempt"], 1, INT32_MAX) ||
        ![envelope[@"profile"] isKindOfClass:NSString.class] ||
        ![@[@"platform-full", @"consumers-complete"] containsObject:envelope[@"profile"]] ||
        ![envelope[@"profile"] isEqual:config[@"ciProfile"]]) return NO;
    NSDictionary *env = config[@"environment"];
    if (![env isKindOfClass:NSDictionary.class] || ![env[@"GITHUB_SHA"] isEqual:envelope[@"source"][@"commit"]] ||
        ![env[@"GITHUB_RUN_ID"] isEqual:[envelope[@"runId"] stringValue]] ||
        ![env[@"GITHUB_RUN_ATTEMPT"] isEqual:[envelope[@"runAttempt"] stringValue]]) return NO;
    for (NSString *value in @[tracking ?: @"", path ?: @""]) {
        if (![value isKindOfClass:NSString.class] || !value.length ||
            [value rangeOfCharacterFromSet:NSCharacterSet.controlCharacterSet].location != NSNotFound) return NO;
    }
    if (![env[@"RUNNER_TRACKING_ID"] isEqual:tracking] || ![env[@"PATH"] isEqual:path]) return NO;
    for (NSString *component in [path componentsSeparatedByString:@":"]) if (![component hasPrefix:@"/"]) return NO;
    for (NSString *key in [keys subarrayWithRange:NSMakeRange(10, 8)]) if (!integer(envelope[key], 0, INT64_MAX)) return NO;
    uint64_t bound = [envelope[@"boundAtMonotonicNs"] unsignedLongLongValue];
    uint64_t product = [envelope[@"productCutoffMonotonicNs"] unsignedLongLongValue];
    uint64_t executor = [envelope[@"executorEndMonotonicNs"] unsignedLongLongValue];
    uint64_t native = [envelope[@"nativeFinalizerEndMonotonicNs"] unsignedLongLongValue];
    uint64_t finalization = [envelope[@"finalizationCutoffMonotonicNs"] unsignedLongLongValue];
    uint64_t job = [envelope[@"jobCutoffMonotonicNs"] unsignedLongLongValue];
    return [envelope[@"boundAtWallNs"] unsignedLongLongValue] > 0 &&
        integer(envelope[@"boundSampleSpanNs"], 0, 50000000) &&
        bound <= INT64_MAX - [envelope[@"boundSampleSpanNs"] unsignedLongLongValue] &&
        bound < product && product < executor &&
        executor <= native && native - executor >= 30 * ciSecond && native < finalization && finalization <= job &&
        job - bound <= 3600 * ciSecond;
}

/* -1 refuses without evaluating a predicate; 0 waits; 1 is bounded completion.
 * This pure decision is exercised without launch, native admission or signals. */
static int ciWaitDecision(NSDictionary *envelope, NSDictionary *observation, uint64_t deadline, BOOL finished) {
    if (!deadline || deadline > INT64_MAX || !ciProgress(envelope, observation) ||
        [observation[@"monotonicNs"] unsignedLongLongValue] + [observation[@"sampleSpanNs"] unsignedLongLongValue] >= deadline) return -1;
    return finished ? 1 : 0;
}

static uint64_t ciCappedEnd(uint64_t now, uint64_t allowance, uint64_t cap) {
    return now >= cap || cap > INT64_MAX ? 0 : now + MIN(allowance, cap - now);
}

static BOOL ciWaitUntil(NSDictionary *envelope, uint64_t deadline, BOOL (^finished)(void)) {
    for (;;) {
        if (ciWaitDecision(envelope, ciObserveClock(), deadline, NO) < 0) return NO;
        BOOL done = finished();
        int decision = ciWaitDecision(envelope, ciObserveClock(), deadline, done);
        if (decision) return decision == 1;
        [NSRunLoop.currentRunLoop runMode:NSDefaultRunLoopMode beforeDate:[NSDate dateWithTimeIntervalSinceNow:0.05]];
        [NSThread sleepForTimeInterval:0.01];
    }
}

static NSTimeInterval ciDirectedSeconds(uint64_t ns, double direction) {
    /* Both integer conversions are exact: quotient < 2^35, remainder < 2^30.
     * Round OUTWARD after each inexact operation (division and addition).
     * Thus fraction bounds the exact remainder ratio and the returned sum
     * bounds quotient + fraction. Casting the whole ns value first introduces
     * another rounding error that one final nextafter cannot always cover. */
    uint64_t quotient = ns / ciSecond, remainder = ns % ciSecond;
    if (!remainder) return (double)quotient;
    double fraction = nextafter((double)remainder / (double)ciSecond, direction);
    return nextafter((double)quotient + fraction, direction);
}

static NSTimeInterval ciDeadlineSeconds(uint64_t ns) { return ciDirectedSeconds(ns, -INFINITY); }
static NSTimeInterval ciNowSeconds(uint64_t ns) { return ciDirectedSeconds(ns, INFINITY); }
#endif

static int finalizeApplication(NSMutableDictionary *result, NSDictionary *registration, NSDictionary *source,
                              NSDictionary *terminalIdentity, uid_t uid, NSNumber *childCode,
                              NSTimeInterval quitDeadline, RpcTerminalFinalization operations) {
    NSString *firstFailure = childCode ? nil : result[@"failureCheck"];
    BOOL finalized = NO;
    do {
        /* A result file alone never authorizes Quit. Conversely, missing or
         * malformed child completion cannot inherit success from cleanup. */
        if (![result[@"applicationCreated"] boolValue] || ![result[@"scriptChildReaped"] boolValue]) break;
        result[@"stage"] = @"SHELL";
        result[@"failureCheck"] = @"SHELL_REGISTRATION";
        if (![registration isKindOfClass:NSDictionary.class] || !validSource(source)) break;
        NSArray *shellIdentities = registration[@"shells"];
        if (registration.count != 4 || !integer(registration[@"schema"], 1, 1) ||
            ![registration[@"source"] isEqual:source] || ![registration[@"terminal"] isEqual:terminalIdentity] ||
            ![shellIdentities isKindOfClass:NSArray.class] || shellIdentities.count < 1 || shellIdentities.count > 30) break;
        NSMutableSet *shellPids = [NSMutableSet set];
        BOOL valid = YES;
        for (NSDictionary *shellIdentity in shellIdentities) {
            if (!validShell(shellIdentity, uid) || [shellIdentity[@"pid"] isEqual:terminalIdentity[@"pid"]] ||
                [shellPids containsObject:shellIdentity[@"pid"]]) { valid = NO; break; }
            [shellPids addObject:shellIdentity[@"pid"]];
        }
        if (!valid) break;
        result[@"commandShellsObserved"] = @YES;
        result[@"failureCheck"] = @"SHELL_RETIREMENT";
        __block int shellObservation = 0;
        BOOL observed = operations.wait(quitDeadline - operations.now(), ^BOOL{
            shellObservation = 1;
            for (NSDictionary *shellIdentity in shellIdentities) {
                int observed = operations.retirement(shellIdentity);
                if (observed < 0) { shellObservation = -1; break; }
                if (observed == 0) shellObservation = 0;
            }
            return shellObservation != 0;
        });
        if (shellObservation < 0) { result[@"failureCheck"] = @"SHELL_OBSERVATION"; break; }
        if (!observed || shellObservation != 1 || operations.now() >= quitDeadline) break;
        result[@"commandShellsRetired"] = @YES;
        result[@"failureCheck"] = @"APPLICATION_IDENTITY_CHANGED";
        if (!operations.originalIdentity()) break;
        result[@"originalApplicationIdentity"] = @YES;
        result[@"stage"] = @"QUIT";
        result[@"failureCheck"] = @"QUIT_REQUEST";
        /* Native identity observation can itself consume the remaining bound. */
        if (operations.now() >= quitDeadline || !operations.requestQuit()) break;
        result[@"applicationQuitRequested"] = @YES;
        result[@"failureCheck"] = @"QUIT_COMPLETION";
        if (operations.now() >= quitDeadline ||
            !operations.wait(quitDeadline - operations.now(), operations.terminated) ||
            operations.now() > quitDeadline) break;
        result[@"applicationTerminated"] = @YES;
        result[@"stage"] = @"FINALIZED";
        result[@"failureCheck"] = @"NONE";
        finalized = YES;
    } while (NO);
    /* Cleanup completion is not product success. A child-source failure (or
     * any earlier failure) remains the first diagnostic even if Quit succeeds. */
    if (firstFailure) result[@"failureCheck"] = firstFailure;
    int outcome = finalized && childCode ? childCode.intValue : 125;
    result[@"exitCode"] = @(outcome);
    return outcome;
}

int main(int argc, const char **argv) {
    @autoreleasepool {
        if (argc != 3 || getuid() == 0 || getuid() != geteuid() || getgid() != getegid()) return 125;
        umask(0077);
        uid_t uid = getuid();
        NSString *executionMode = @(argv[2]);
        /* The original 30-minute OS diagnostic lease is unchanged. Native/full
         * inventories need the already-authorized 325-minute workflow envelope,
         * minus finalization margin. This is NOT a product or readiness deadline:
         * each original native, multicast and 120-second GUI bound still applies.
         * No arbitrary duration or command is accepted by this controller. */
        NSNumber *childBound = @{@"network":@1800, @"native":@19200, @"runtime":@19200, @"qualification":@19200}[executionMode];
#ifdef P2PKIT_APPLE_CI_CANDIDATE
        BOOL ciMode = [executionMode isEqualToString:@"ci"];
        if (ciMode) childBound = @0; /* Only the immutable envelope supplies bounds. */
#endif
#ifdef P2PKIT_MODULAR_CI
        /* Fixed modular commands, not the historical CI envelope. Each
         * collector retains its unchanged component command deadline. */
        NSNumber *modularCommand = @{@"modular-jmdns":@1800, @"modular-shared":@7200}[executionMode];
        if (!modularCommand) return 125;
        childBound = @(modularCommand.doubleValue + 240);
#endif
        if (!childBound) return 125;
        NSURL *directory = [NSURL fileURLWithPath:@(argv[1]) isDirectory:YES];
        struct stat parent, console;
        if (![[directory URLByResolvingSymlinksInPath].path isEqualToString:directory.path] ||
            lstat(directory.fileSystemRepresentation, &parent) || !S_ISDIR(parent.st_mode) ||
            parent.st_uid != uid || (parent.st_mode & 0777) != 0700) return 125;
        NSMutableDictionary *result = [@{@"schema":@3, @"executionMode":executionMode, @"stage":@"SETUP", @"exitCode":@125,
            @"failureCheck":@"CONSOLE", @"openErrorDomain":@"NONE", @"openErrorCode":@0,
            @"consoleUser":@NO, @"noPreexistingTerminal":@NO, @"applicationCreated":@NO,
            @"originalApplicationIdentity":@NO, @"nativeChildFinished":@NO, @"scriptChildReaped":@NO,
            @"commandShellsObserved":@NO, @"commandShellsRetired":@NO,
            @"applicationQuitRequested":@NO, @"applicationTerminated":@NO} mutableCopy];
        NSURL *resultURL = [directory URLByAppendingPathComponent:@"application-result.json"];
        NSURL *commandURL = [directory URLByAppendingPathComponent:@"native.command"];
        NSURL *terminalURL = [NSURL fileURLWithPath:@"/System/Applications/Utilities/Terminal.app" isDirectory:YES];
        NSString *bundle = @"com.apple.Terminal";
        int outcome = 125;
        __block NSRunningApplication *application = nil;
        struct proc_bsdinfo before = {0};
        NSNumber *childCode = nil;
        NSDictionary *config = readPrivate([directory URLByAppendingPathComponent:@"config.json"], uid);
#ifdef P2PKIT_APPLE_CI_CANDIDATE
        NSDictionary *ciEnvelope = ciMode ? config[@"ciEnvelope"] : nil;
        NSDictionary *ciEnvironment = nil;
        BOOL ciAdmitted = NO;
        if (ciMode) {
            result[@"schema"] = @5;
            result[@"scope"] = @"ORDINARY_CI_APPLE_TERMINAL_CANDIDATE_NOT_QUALIFICATION";
            result[@"candidateOnly"] = @YES;
            result[@"releaseQualification"] = @NO;
        }
#endif
        do {
#ifdef P2PKIT_APPLE_CI_CANDIDATE
            if (ciMode) {
                result[@"failureCheck"] = @"CI_ENVELOPE";
                const char *trackingValue = getenv("RUNNER_TRACKING_ID"), *pathValue = getenv("PATH");
                NSString *tracking = trackingValue ? [NSString stringWithUTF8String:trackingValue] : nil;
                NSString *path = pathValue ? [NSString stringWithUTF8String:pathValue] : nil;
                if (!ciEnvelopeValid(ciEnvelope, config, tracking, path) ||
                    ciWaitDecision(ciEnvelope, ciObserveClock(), [ciEnvelope[@"productCutoffMonotonicNs"] unsignedLongLongValue], NO) < 0) break;
                ciAdmitted = YES;
                ciEnvironment = @{@"PATH":path, @"RUNNER_TRACKING_ID":tracking};
                result[@"source"] = ciEnvelope[@"source"];
                result[@"profile"] = ciEnvelope[@"profile"];
                result[@"runId"] = ciEnvelope[@"runId"];
                result[@"runAttempt"] = ciEnvelope[@"runAttempt"];
            }
#endif
            result[@"failureCheck"] = @"CONSOLE";
            if (stat("/dev/console", &console) || console.st_uid != uid) break;
            result[@"consoleUser"] = @YES;
            result[@"failureCheck"] = @"PREEXISTING_APPLICATION";
            if ([NSRunningApplication runningApplicationsWithBundleIdentifier:bundle].count != 0) break;
            result[@"noPreexistingTerminal"] = @YES;
            result[@"failureCheck"] = @"SYSTEM_APPLICATION";
            if (![[NSBundle bundleWithURL:terminalURL].bundleIdentifier isEqualToString:bundle]) break;
            result[@"failureCheck"] = @"PRIVATE_COMMAND";
            struct stat script;
            if (lstat(commandURL.fileSystemRepresentation, &script) || !S_ISREG(script.st_mode) ||
                script.st_uid != uid || (script.st_mode & 0777) != 0700) break;
            NSWorkspaceOpenConfiguration *configuration = NSWorkspaceOpenConfiguration.configuration;
            configuration.createsNewApplicationInstance = YES;
            configuration.activates = NO;
            configuration.addsToRecentItems = NO;
            configuration.promptsUserIfNeeded = NO;
            configuration.environment = @{@"PATH":@"/usr/bin:/bin:/usr/sbin:/sbin"};
#ifdef P2PKIT_MODULAR_CI
            /* Preserve the original runner's cancellation custody across
             * LaunchServices. No credentials or ownership-marker chains pass. */
            const char *trackingValue = getenv("RUNNER_TRACKING_ID");
            NSString *tracking = trackingValue ? [NSString stringWithUTF8String:trackingValue] : nil;
            NSCharacterSet *trackingCharacters = [NSCharacterSet characterSetWithCharactersInString:
                @"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-"];
            result[@"failureCheck"] = @"RUNNER_TRACKING";
            id component = config[@"component"];
            NSString *expectedMode = [component isKindOfClass:NSString.class] ?
                @{@"jmdns-diagnostic":@"modular-jmdns", @"macos-shared":@"modular-shared"}[component] : nil;
            if (![expectedMode isEqualToString:executionMode] || !tracking.length || tracking.length > 200 ||
                [tracking rangeOfCharacterFromSet:trackingCharacters.invertedSet].location != NSNotFound ||
                ![config[@"environment"][@"RUNNER_TRACKING_ID"] isEqual:tracking]) break;
            configuration.environment = @{@"PATH":@"/usr/bin:/bin:/usr/sbin:/sbin", @"RUNNER_TRACKING_ID":tracking};
#endif
#ifdef P2PKIT_APPLE_CI_CANDIDATE
            uint64_t ciOpenEnd = 0;
            if (ciMode) {
                configuration.environment = ciEnvironment;
                NSDictionary *observation = ciObserveClock();
                uint64_t productEnd = [ciEnvelope[@"productCutoffMonotonicNs"] unsignedLongLongValue];
                result[@"failureCheck"] = @"CI_SETUP_DEADLINE";
                if (ciWaitDecision(ciEnvelope, observation, productEnd, NO) < 0) break;
                ciOpenEnd = ciCappedEnd([observation[@"monotonicNs"] unsignedLongLongValue], 30 * ciSecond, productEnd);
            }
#endif
            __block BOOL opened = NO, openError = NO;
            result[@"stage"] = @"OPEN";
            result[@"failureCheck"] = @"APPLICATION_OPEN";
            NSDate *requested = NSDate.date;
            [NSWorkspace.sharedWorkspace openURLs:@[commandURL] withApplicationAtURL:terminalURL
                configuration:configuration completionHandler:^(NSRunningApplication *app, NSError *error) {
                    dispatch_async(dispatch_get_main_queue(), ^{
                        application = app; openError = error != nil; opened = YES;
                        if (error) {
                            result[@"openErrorDomain"] = [error.domain isEqualToString:NSCocoaErrorDomain] ? @"COCOA" :
                                [error.domain isEqualToString:NSOSStatusErrorDomain] ? @"OSSTATUS" :
                                [error.domain isEqualToString:NSPOSIXErrorDomain] ? @"POSIX" : @"OTHER";
                            result[@"openErrorCode"] = @(error.code);
                        }
                    });
                }];
            BOOL openCompleted;
#ifdef P2PKIT_APPLE_CI_CANDIDATE
            if (ciMode) openCompleted = ciWaitUntil(ciEnvelope, ciOpenEnd, ^BOOL{ return opened; });
            else
#endif
                openCompleted = waitUntil(30, ^BOOL{ return opened; });
            if (!openCompleted || openError || !application || application.terminated) break;
            result[@"failureCheck"] = @"APPLICATION_IDENTITY";
            if (![application.bundleIdentifier isEqualToString:bundle] ||
                ![[application.bundleURL URLByResolvingSymlinksInPath].path isEqualToString:terminalURL.path] ||
                !application.launchDate || [application.launchDate timeIntervalSinceDate:requested] < -2) break;
            if (!identity(application.processIdentifier, uid, &before)) break;
            result[@"applicationCreated"] = @YES;
            result[@"failureCheck"] = @"ADMISSION_WRITE";
#ifdef P2PKIT_APPLE_CI_CANDIDATE
            if (ciMode && ciWaitDecision(ciEnvelope, ciObserveClock(),
                    [ciEnvelope[@"productCutoffMonotonicNs"] unsignedLongLongValue], NO) < 0) break;
#endif
            if (!save([directory URLByAppendingPathComponent:@"application-admission.json"],
                      @{@"pid":@(before.pbi_pid), @"uid":@(uid), @"startSeconds":@(before.pbi_start_tvsec),
                        @"startMicroseconds":@(before.pbi_start_tvusec)})) break;
            result[@"stage"] = @"CHILD";
            result[@"failureCheck"] = @"CHILD_REAP";
            NSURL *childURL = [directory URLByAppendingPathComponent:@"child-result.json"];
            NSURL *shellURL = [directory URLByAppendingPathComponent:@"shell-result.txt"];
            BOOL childCompleted;
#ifdef P2PKIT_APPLE_CI_CANDIDATE
            if (ciMode) {
                /* Product cutoff belongs to the keeper. This exact child also
                 * performs stop/evidence work within the original executor end. */
                childCompleted = ciWaitUntil(ciEnvelope, [ciEnvelope[@"executorEndMonotonicNs"] unsignedLongLongValue], ^BOOL{
                    return application.terminated || [NSFileManager.defaultManager fileExistsAtPath:shellURL.path];
                });
            } else
#endif
                childCompleted = waitUntil(childBound.doubleValue, ^BOOL{
                return application.terminated || [NSFileManager.defaultManager fileExistsAtPath:shellURL.path];
            });
            if (!childCompleted || application.terminated) break;
            struct stat shellInfo;
            if (lstat(shellURL.fileSystemRepresentation, &shellInfo) || !S_ISREG(shellInfo.st_mode) ||
                shellInfo.st_uid != uid || (shellInfo.st_mode & 0777) != 0600 || shellInfo.st_size > 8) break;
            NSString *shell = [NSString stringWithContentsOfURL:shellURL encoding:NSUTF8StringEncoding error:NULL];
            if (![shell isEqualToString:@"0\n"] && ![shell isEqualToString:@"1\n"] && ![shell isEqualToString:@"125\n"]) break;
            result[@"scriptChildReaped"] = @YES; /* Shell waited for its exact child, not only a pre-exit JSON write. */
            result[@"failureCheck"] = @"CHILD_SOURCE";
            NSDictionary *child = readPrivate(childURL, uid);
            NSNumber *code = @(shell.intValue);
            if (code.intValue != 125) {
                if (!child || child.count != 2 || ![child[@"source"] isEqual:config[@"source"]] ||
                    ![child[@"exitCode"] isEqual:code]) break;
                result[@"nativeChildFinished"] = @YES;
            }
            childCode = code;
        } while (NO);
        /* Every failure after exact application authority reaches this same
         * finalizer. Missing child/shell authority remains a refusal, not a
         * guessed cleanup capability; the first failure is retained. */
        if ([result[@"applicationCreated"] boolValue]) {
            NSTimeInterval quitDeadline = NSProcessInfo.processInfo.systemUptime + 30;
            NSDictionary *registration = readPrivate([directory URLByAppendingPathComponent:@"command-shell.json"], uid);
            NSDictionary *terminalIdentity = @{@"pid":@(before.pbi_pid), @"uid":@(uid),
                @"startSeconds":@(before.pbi_start_tvsec), @"startMicroseconds":@(before.pbi_start_tvusec)};
            RpcTerminalFinalization operations = {
                .now = ^NSTimeInterval{ return NSProcessInfo.processInfo.systemUptime; },
                .wait = ^BOOL(NSTimeInterval seconds, BOOL (^finished)(void)) { return waitUntil(seconds, finished); },
                .retirement = ^int(NSDictionary *shellIdentity) { return shellRetirement(shellIdentity, uid); },
                .originalIdentity = ^BOOL{
                    struct proc_bsdinfo after = {0};
                    if (!identity(application.processIdentifier, uid, &after) || application.terminated ||
                        before.pbi_pid != after.pbi_pid || before.pbi_start_tvsec != after.pbi_start_tvsec ||
                        before.pbi_start_tvusec != after.pbi_start_tvusec) return NO;
                    return YES;
                },
                /* The retained application object, never a reconstructed PID. */
                .requestQuit = ^BOOL{ return [application terminate]; },
                .terminated = ^BOOL{ return application.terminated; }
            };
#ifdef P2PKIT_APPLE_CI_CANDIDATE
            if (ciMode) {
                NSDictionary *observation = ciObserveClock();
                uint64_t nativeEnd = [ciEnvelope[@"nativeFinalizerEndMonotonicNs"] unsignedLongLongValue];
                uint64_t quitEnd = ciWaitDecision(ciEnvelope, observation, nativeEnd, NO) < 0 ? 0 :
                    ciCappedEnd([observation[@"monotonicNs"] unsignedLongLongValue], 30 * ciSecond, nativeEnd);
                quitDeadline = ciDeadlineSeconds(quitEnd);
                operations.now = ^NSTimeInterval{
                    NSDictionary *current = ciObserveClock();
                    return ciWaitDecision(ciEnvelope, current, quitEnd, NO) < 0 ? INFINITY :
                        ciNowSeconds([current[@"monotonicNs"] unsignedLongLongValue] + [current[@"sampleSpanNs"] unsignedLongLongValue]);
                };
                operations.wait = ^BOOL(NSTimeInterval seconds, BOOL (^finished)(void)) {
                    return isfinite(seconds) && seconds > 0 && ciWaitUntil(ciEnvelope, quitEnd, finished);
                };
            }
#endif
            outcome = finalizeApplication(result, registration, config[@"source"], terminalIdentity,
                uid, childCode, quitDeadline, operations);
        }
#ifdef P2PKIT_APPLE_CI_CANDIDATE
        if (ciAdmitted && ciWaitDecision(ciEnvelope, ciObserveClock(),
                [ciEnvelope[@"finalizationCutoffMonotonicNs"] unsignedLongLongValue], NO) < 0) {
            outcome = 125;
            result[@"exitCode"] = @125;
            if ([result[@"failureCheck"] isEqual:@"NONE"]) result[@"failureCheck"] = @"CI_FINALIZATION_DEADLINE";
        }
#endif
        if (!save(resultURL, result)) return 125;
        return outcome;
    }
}
