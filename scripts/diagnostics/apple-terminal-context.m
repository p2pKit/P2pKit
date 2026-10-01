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
        do {
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
            __block NSRunningApplication *application = nil;
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
            if (!waitUntil(30, ^BOOL{ return opened; }) || openError || !application || application.terminated) break;
            result[@"failureCheck"] = @"APPLICATION_IDENTITY";
            if (![application.bundleIdentifier isEqualToString:bundle] ||
                ![[application.bundleURL URLByResolvingSymlinksInPath].path isEqualToString:terminalURL.path] ||
                !application.launchDate || [application.launchDate timeIntervalSinceDate:requested] < -2) break;
            struct proc_bsdinfo before = {0};
            if (!identity(application.processIdentifier, uid, &before)) break;
            result[@"applicationCreated"] = @YES;
            result[@"failureCheck"] = @"ADMISSION_WRITE";
            if (!save([directory URLByAppendingPathComponent:@"application-admission.json"],
                      @{@"pid":@(before.pbi_pid), @"uid":@(uid), @"startSeconds":@(before.pbi_start_tvsec),
                        @"startMicroseconds":@(before.pbi_start_tvusec)})) break;
            result[@"stage"] = @"CHILD";
            result[@"failureCheck"] = @"CHILD_REAP";
            NSURL *childURL = [directory URLByAppendingPathComponent:@"child-result.json"];
            NSURL *shellURL = [directory URLByAppendingPathComponent:@"shell-result.txt"];
            if (!waitUntil(childBound.doubleValue, ^BOOL{
                return application.terminated || [NSFileManager.defaultManager fileExistsAtPath:shellURL.path];
            }) || application.terminated) break;
            struct stat shellInfo;
            if (lstat(shellURL.fileSystemRepresentation, &shellInfo) || !S_ISREG(shellInfo.st_mode) ||
                shellInfo.st_uid != uid || (shellInfo.st_mode & 0777) != 0600 || shellInfo.st_size > 8) break;
            NSString *shell = [NSString stringWithContentsOfURL:shellURL encoding:NSUTF8StringEncoding error:NULL];
            if (![shell isEqualToString:@"0\n"] && ![shell isEqualToString:@"1\n"] && ![shell isEqualToString:@"125\n"]) break;
            result[@"scriptChildReaped"] = @YES; /* Shell waited for its exact child, not only a pre-exit JSON write. */
            result[@"failureCheck"] = @"CHILD_SOURCE";
            NSDictionary *child = readPrivate(childURL, uid);
            NSDictionary *config = readPrivate([directory URLByAppendingPathComponent:@"config.json"], uid);
            NSNumber *code = @(shell.intValue);
            if (code.intValue != 125) {
                if (!child || child.count != 2 || ![child[@"source"] isEqual:config[@"source"]] ||
                    ![child[@"exitCode"] isEqual:code]) break;
                result[@"nativeChildFinished"] = @YES;
            }
            result[@"exitCode"] = code;
            /* native.command writes shell-result.txt before its own exit. A
             * Quit at that point may ask to close a running shell. Do not click
             * that prompt, force termination or extend the existing bound. */
            NSTimeInterval quitDeadline = NSProcessInfo.processInfo.systemUptime + 30;
            result[@"stage"] = @"SHELL";
            result[@"failureCheck"] = @"SHELL_REGISTRATION";
            NSDictionary *registration = readPrivate([directory URLByAppendingPathComponent:@"command-shell.json"], uid);
            NSArray *shellIdentities = registration[@"shells"];
            NSDictionary *terminalIdentity = @{@"pid":@(before.pbi_pid), @"uid":@(uid),
                @"startSeconds":@(before.pbi_start_tvsec), @"startMicroseconds":@(before.pbi_start_tvusec)};
            if (registration.count != 4 || !integer(registration[@"schema"], 1, 1) ||
                ![registration[@"source"] isEqual:config[@"source"]] ||
                ![registration[@"terminal"] isEqual:terminalIdentity] ||
                ![shellIdentities isKindOfClass:NSArray.class] || shellIdentities.count < 1 || shellIdentities.count > 30) break;
            NSMutableSet *shellPids = [NSMutableSet set];
            BOOL valid = YES;
            for (NSDictionary *shellIdentity in shellIdentities) {
                if (!validShell(shellIdentity, uid) || [shellIdentity[@"pid"] intValue] == application.processIdentifier ||
                    [shellPids containsObject:shellIdentity[@"pid"]]) { valid = NO; break; }
                [shellPids addObject:shellIdentity[@"pid"]];
            }
            if (!valid) break;
            result[@"commandShellsObserved"] = @YES;
            result[@"failureCheck"] = @"SHELL_RETIREMENT";
            __block int shellObservation = 0;
            BOOL observed = waitUntil(quitDeadline - NSProcessInfo.processInfo.systemUptime, ^BOOL{
                shellObservation = 1;
                for (NSDictionary *shellIdentity in shellIdentities) {
                    int observed = shellRetirement(shellIdentity, uid);
                    if (observed < 0) { shellObservation = -1; break; }
                    if (observed == 0) shellObservation = 0;
                }
                return shellObservation != 0;
            });
            if (shellObservation < 0) { result[@"failureCheck"] = @"SHELL_OBSERVATION"; break; }
            if (!observed || shellObservation != 1 || NSProcessInfo.processInfo.systemUptime >= quitDeadline) break;
            result[@"commandShellsRetired"] = @YES;
            /* Identity is a safety check, never a signal capability. The Quit
             * request uses the retained application instance, not a reconstructed PID. */
            struct proc_bsdinfo after = {0};
            result[@"failureCheck"] = @"APPLICATION_IDENTITY_CHANGED";
            if (!identity(application.processIdentifier, uid, &after) || application.terminated ||
                before.pbi_pid != after.pbi_pid || before.pbi_start_tvsec != after.pbi_start_tvsec ||
                before.pbi_start_tvusec != after.pbi_start_tvusec) break;
            result[@"originalApplicationIdentity"] = @YES;
            result[@"stage"] = @"QUIT";
            result[@"failureCheck"] = @"QUIT_REQUEST";
            if (![application terminate]) break;
            result[@"applicationQuitRequested"] = @YES;
            result[@"failureCheck"] = @"QUIT_COMPLETION";
            if (NSProcessInfo.processInfo.systemUptime >= quitDeadline ||
                !waitUntil(quitDeadline - NSProcessInfo.processInfo.systemUptime, ^BOOL{ return application.terminated; }) ||
                NSProcessInfo.processInfo.systemUptime > quitDeadline) break;
            result[@"applicationTerminated"] = @YES;
            result[@"stage"] = @"FINALIZED";
            result[@"failureCheck"] = @"NONE";
            outcome = code.intValue;
        } while (NO);
        if (!save(resultURL, result)) return 125;
        return outcome;
    }
}
