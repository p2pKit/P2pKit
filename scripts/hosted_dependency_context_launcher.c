/*
 * Fixed launchd privilege prelude, not a general command launcher.
 * The nonroot foreground prepares and binds the closed generated header and
 * compiler output. Admin admits only the exact original root-owned executable.
 * No project interpreter, project file, network or caller-selected command is
 * entered while privileged. Every failure exits without cleanup or diagnostics.
 */
#define _DARWIN_C_SOURCE 1

#if !defined(__APPLE__) || !(defined(__arm64__) || defined(__aarch64__))
#error "The dependency context launcher requires Darwin ARM64"
#endif

#include <sys/types.h>
#include <sys/stat.h>
#include <sys/proc_info.h>
#include <errno.h>
#include <fcntl.h>
#include <libproc.h>
#include <limits.h>
#include <stddef.h>
#include <string.h>
#include <unistd.h>

#include "hosted_dependency_context_launcher_config.h"

enum { FD_CAPACITY = 256, GROUP_CAPACITY = 256 };
enum failure {
    BAD_ENTRY = 100,
    BAD_CONFIG = 101,
    SETGROUPS_FAILED = 102,
    SETGID_FAILED = 103,
    SETUID_FAILED = 104,
    IDENTITY_FAILED = 105,
    GROUPS_FAILED = 106,
    ROOT_REACQUIRED = 107,
    FD_LIST_FAILED = 108,
    FD_CLOSE_FAILED = 109,
    STDIO_FAILED = 110,
    CHDIR_FAILED = 111,
    EXEC_FAILED = 112,
    SETGROUPS_EINVAL_OVER_SDK_LIMIT = 113,
    SETGROUPS_EINVAL_WITHIN_SDK_LIMIT = 114,
    SETGROUPS_EPERM = 115
};

_Static_assert(P2PKIT_UID != (uid_t)0, "Target UID must be nonroot");
_Static_assert(P2PKIT_GROUP_COUNT >= 0 && P2PKIT_GROUP_COUNT <= GROUP_CAPACITY,
               "The original group set must fit its fixed capacity");
_Static_assert(sizeof(P2PKIT_GROUPS) / sizeof(P2PKIT_GROUPS[0]) == GROUP_CAPACITY,
               "The group array must have its fixed capacity");
_Static_assert(sizeof(P2PKIT_D_ARGV) / sizeof(P2PKIT_D_ARGV[0]) == 8,
               "Only the existing seven-argument isolated D entry is supported");
_Static_assert(sizeof(P2PKIT_D_ENV) / sizeof(P2PKIT_D_ENV[0]) > 1,
               "The closed child environment must have a terminator");

static _Noreturn void
refuse(enum failure code)
{
    _exit((int)code);
}

static void
check_config(void)
{
    const size_t env_count = sizeof(P2PKIT_D_ENV) / sizeof(P2PKIT_D_ENV[0]);

    for (size_t i = 0; i < 7; i++) {
        if (P2PKIT_D_ARGV[i] == NULL) {
            refuse(BAD_CONFIG);
        }
    }
    if (P2PKIT_D_ARGV[7] != NULL || P2PKIT_D_ENV[env_count - 1] != NULL ||
        P2PKIT_D_ARGV[0][0] != '/' || P2PKIT_D_ARGV[4][0] != '/' ||
        P2PKIT_D_ARGV[6][0] != '/' || P2PKIT_SOURCE_DIRECTORY[0] != '/' ||
        strcmp(P2PKIT_D_ARGV[1], "-I") != 0 || strcmp(P2PKIT_D_ARGV[2], "-B") != 0 ||
        strcmp(P2PKIT_D_ARGV[3], "-S") != 0 || strcmp(P2PKIT_D_ARGV[5], "_service") != 0) {
        refuse(BAD_CONFIG);
    }
    for (size_t i = 0; i + 1 < env_count; i++) {
        if (P2PKIT_D_ENV[i] == NULL) {
            refuse(BAD_CONFIG);
        }
    }
    for (int i = 1; i < P2PKIT_GROUP_COUNT; i++) {
        if (P2PKIT_GROUPS[i - 1] >= P2PKIT_GROUPS[i]) {
            refuse(BAD_CONFIG);
        }
    }
}

static void
check_ids(uid_t uid, gid_t gid, enum failure code)
{
    struct proc_bsdinfo info = {0};
    const pid_t pid = getpid();
    const int copied = proc_pidinfo(pid, PROC_PIDTBSDINFO, 0, &info, sizeof(info));

    if (pid <= 1 || getppid() != 1 || copied != (int)sizeof(info) ||
        info.pbi_pid != (unsigned int)pid || info.pbi_ppid != 1 ||
        getuid() != uid || geteuid() != uid || getgid() != gid || getegid() != gid ||
        info.pbi_uid != uid || info.pbi_ruid != uid || info.pbi_svuid != uid ||
        info.pbi_gid != gid || info.pbi_rgid != gid || info.pbi_svgid != gid) {
        refuse(code);
    }
}

static void
check_groups(void)
{
    gid_t actual[GROUP_CAPACITY] = {0};
    const int count = getgroups(GROUP_CAPACITY, actual);

    if (count < 0 || count != P2PKIT_GROUP_COUNT) {
        refuse(GROUPS_FAILED);
    }
    /* Darwin may reorder the effective GID; compare the exact original set. */
    for (int i = 1; i < count; i++) {
        const gid_t value = actual[i];
        int j = i;
        while (j > 0 && actual[j - 1] > value) {
            actual[j] = actual[j - 1];
            j--;
        }
        actual[j] = value;
    }
    for (int i = 0; i < count; i++) {
        if (actual[i] != P2PKIT_GROUPS[i]) {
            refuse(GROUPS_FAILED);
        }
    }
}

static size_t
list_fds(struct proc_fdinfo entries[FD_CAPACITY])
{
    const size_t capacity_bytes = FD_CAPACITY * sizeof(entries[0]);
    const int copied = proc_pidinfo(getpid(), PROC_PIDLISTFDS, 0, entries, (int)capacity_bytes);
    unsigned int stdio = 0;

    /* A full buffer may hide more descriptors. Do not infer an fd ceiling. */
    if (copied <= 0 || (size_t)copied >= capacity_bytes || (size_t)copied % sizeof(entries[0]) != 0) {
        refuse(FD_LIST_FAILED);
    }
    const size_t count = (size_t)copied / sizeof(entries[0]);
    for (size_t i = 0; i < count; i++) {
        const int fd = entries[i].proc_fd;
        if (fd < 0) {
            refuse(FD_LIST_FAILED);
        }
        for (size_t j = 0; j < i; j++) {
            if (entries[j].proc_fd == fd) {
                refuse(FD_LIST_FAILED);
            }
        }
        if (fd < 3) {
            stdio |= 1U << fd;
        }
    }
    if (stdio != 7) {
        refuse(FD_LIST_FAILED);
    }
    return count;
}

static void
close_extra_fds(void)
{
    struct proc_fdinfo entries[FD_CAPACITY] = {{0}};
    const size_t count = list_fds(entries);

    /* This prelude creates no threads, handlers or descriptors. No retries. */
    for (size_t i = 0; i < count; i++) {
        if (entries[i].proc_fd >= 3 && close(entries[i].proc_fd) != 0) {
            refuse(FD_CLOSE_FAILED);
        }
    }
    if (list_fds(entries) != 3) {
        refuse(FD_LIST_FAILED);
    }
}

static void
check_stdio(void)
{
    struct stat null_info;

    if (lstat("/dev/null", &null_info) != 0 || !S_ISCHR(null_info.st_mode) || null_info.st_uid != 0) {
        refuse(STDIO_FAILED);
    }
    for (int fd = 0; fd < 3; fd++) {
        struct stat info;
        const int flags = fcntl(fd, F_GETFD);
        if (flags < 0 || (flags & FD_CLOEXEC) != 0 || fstat(fd, &info) != 0 ||
            !S_ISCHR(info.st_mode) || info.st_dev != null_info.st_dev || info.st_ino != null_info.st_ino ||
            info.st_rdev != null_info.st_rdev || info.st_uid != null_info.st_uid ||
            info.st_gid != null_info.st_gid) {
            refuse(STDIO_FAILED);
        }
    }
}

int
main(int argc, char **argv)
{
    (void)argv;
    if (argc != 1) {
        refuse(BAD_ENTRY);
    }
    check_ids(0, 0, BAD_ENTRY);
    check_config();
    check_stdio();
    if (setgroups(P2PKIT_GROUP_COUNT, P2PKIT_GROUPS) != 0) {
        const int saved_errno = errno;
        if (saved_errno == EINVAL) {
            refuse(P2PKIT_GROUP_COUNT > NGROUPS_MAX ?
                   SETGROUPS_EINVAL_OVER_SDK_LIMIT : SETGROUPS_EINVAL_WITHIN_SDK_LIMIT);
        }
        if (saved_errno == EPERM) {
            refuse(SETGROUPS_EPERM);
        }
        refuse(SETGROUPS_FAILED);
    }
    if (setgid(P2PKIT_GID) != 0) {
        refuse(SETGID_FAILED);
    }
    if (setuid(P2PKIT_UID) != 0) {
        refuse(SETUID_FAILED);
    }
    check_ids(P2PKIT_UID, P2PKIT_GID, IDENTITY_FAILED);
    check_groups();
    errno = 0;
    if (setuid(0) != -1 || errno != EPERM) {
        refuse(ROOT_REACQUIRED);
    }
    errno = 0;
    if (seteuid(0) != -1 || errno != EPERM) {
        refuse(ROOT_REACQUIRED);
    }
    check_ids(P2PKIT_UID, P2PKIT_GID, IDENTITY_FAILED);
    check_groups();
    close_extra_fds();
    check_stdio();
    if (chdir(P2PKIT_SOURCE_DIRECTORY) != 0) {
        refuse(CHDIR_FAILED);
    }
    execve(P2PKIT_D_ARGV[0], P2PKIT_D_ARGV, P2PKIT_D_ENV);
    refuse(EXEC_FAILED);
}
