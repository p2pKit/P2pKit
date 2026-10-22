#ifndef P2PKIT_SAMPLE_TRANSFER_POSIX_H
#define P2PKIT_SAMPLE_TRANSFER_POSIX_H

#include <sys/file.h>
#include <sys/stat.h>

// Swift's Darwin-qualified stat/flock names also name C structs. Keep the
// function lookup in C, using the SDK declarations (including stat's ABI
// selection), rather than binding a guessed symbol or changing lock semantics.
static inline int p2pkit_sample_file_status(const char *path, struct stat *information) {
    return stat(path, information);
}

static inline int p2pkit_sample_lock_file(int descriptor, int operation) {
    return flock(descriptor, operation);
}

#endif
