#include <jni.h>
#include <dns_sd.h>
#include <errno.h>
#include <limits.h>
#include <poll.h>
#include <stdint.h>
#include <time.h>
#include <unistd.h>

#if !defined(__APPLE__) || (!defined(__arm64__) && !defined(__aarch64__))
#error "This diagnostic requires the admitted native macOS arm64 compiler"
#endif

/* Test-only schema shared with JmdnsStartupPolicy.java; no exported application API. */
enum result_field {
    SCHEMA = 0, PID = 1, REAL_UID = 2, EFFECTIVE_UID = 3, INTERFACE_INDEX = 4,
    OUTCOME = 5, ELAPSED_NS = 6, CLOCK_ERRNO = 7, BROWSE_CODE = 8,
    REF_CREATED = 9, SOCKET_FD = 10, POLL_CALLS = 11, POLL_RETURN = 12,
    POLL_ERRNO = 13, POLL_REVENTS = 14, EINTR_RETRIES = 15, PROCESS_CODE = 16,
    CALLBACK_COUNT = 17, CALLBACK_OVERFLOW = 18, FIRST_CALLBACK_ERROR = 19,
    CALLBACK_POLICY_COUNT = 20, CALLBACK_CONTEXT_MISMATCH = 21,
    DEALLOCATE_ATTEMPTED = 22, DEALLOCATE_RETURNED = 23, POLICY_PHASE_MASK = 24,
    BUDGET_NS = 25, RESULT_FIELDS = 26
};

enum outcome {
    ADMISSION_REFUSED = 1, CLOCK_FAILED = 2, BROWSE_ERROR = 3,
    REFERENCE_UNAVAILABLE = 4, SOCKET_UNAVAILABLE = 5, POLL_TIMED_OUT = 6,
    POLL_FAILED = 7, EINTR_EXHAUSTED = 8, BUDGET_ELAPSED = 9,
    PROCESS_RETURNED = 10, REENTRANT_REFUSED = 11
};

enum { CALLBACK_LIMIT = 32, EINTR_RETRY_LIMIT = 4 };
static const jlong UNOBSERVED = INT64_MIN;
static const int64_t NORMAL_BUDGET_NS = INT64_C(1000000000);
static const int64_t NS_PER_MILLISECOND = INT64_C(1000000);

_Static_assert(sizeof(jlong) == 8 && sizeof(jint) == 4, "Reviewed JNI integer widths required");
_Static_assert(sizeof(DNSServiceErrorType) == 4, "Reviewed DNS-SD error width required");
_Static_assert(kDNSServiceErr_PolicyDenied == -65570, "Reviewed policy-denied value required");
_Static_assert(POLLIN == 0x0001 && POLLERR == 0x0008 && POLLHUP == 0x0010
        && POLLNVAL == 0x0020 && EINTR == 4, "Reviewed Darwin poll constants required");

struct browse_context {
    DNSServiceRef reference;
    uint32_t interface_index;
    unsigned int callback_count;
    unsigned int policy_count;
    int callback_overflow;
    int context_mismatch;
    int processing;
    DNSServiceErrorType first_error;
};

/* ProcessResult dispatch is synchronous on this JNI thread. This pointer never
 * escapes the call or survives reference deallocation. No queue/thread is added.
 * Error replies document other parameters as undefined, so even their context
 * argument is not read: the one active, same-thread operation supplies our state.
 */
static _Thread_local struct browse_context *active_context;

static void DNSSD_API browse_reply(DNSServiceRef reference, DNSServiceFlags flags,
        uint32_t interface_index, DNSServiceErrorType error, const char *service_name,
        const char *regtype, const char *reply_domain, void *context) {
    struct browse_context *state = active_context;
    if (state == NULL) {
        return; /* An unexpected foreign-thread callback supplies no usable evidence. */
    }
    if (state->callback_count < CALLBACK_LIMIT) {
        state->callback_count++;
    } else {
        state->callback_overflow = 1;
    }
    if (!state->processing) {
        state->context_mismatch = 1;
        return;
    }
    if (error != kDNSServiceErr_NoError) {
        if (state->first_error == kDNSServiceErr_NoError) {
            state->first_error = error;
        }
        if (error == kDNSServiceErr_PolicyDenied && state->policy_count < CALLBACK_LIMIT) {
            state->policy_count++;
        }
        return; /* Do not read any other reply argument on an error. */
    }
    if (reference != state->reference || context != state
            || interface_index != state->interface_index) {
        state->context_mismatch = 1;
    }
    /* Deliberately unused even on success. Never inspect/copy service data. */
    (void) flags;
    (void) service_name;
    (void) regtype;
    (void) reply_domain;
}

static int monotonic_ns(int64_t *value) {
    struct timespec instant;
    if (clock_gettime(CLOCK_MONOTONIC, &instant) != 0) {
        return errno != 0 ? errno : EIO;
    }
    if (instant.tv_sec < 0 || instant.tv_nsec < 0 || instant.tv_nsec >= NORMAL_BUDGET_NS
            || (uint64_t) instant.tv_sec > (uint64_t) (INT64_MAX - instant.tv_nsec)
                    / (uint64_t) NORMAL_BUDGET_NS) {
        return EOVERFLOW;
    }
    *value = (int64_t) instant.tv_sec * NORMAL_BUDGET_NS + instant.tv_nsec;
    return 0;
}

JNIEXPORT jlongArray JNICALL
Java_dev_p2pkit_transport_lan_internal_jmdns_impl_JmdnsStartupPolicy_browse0(
        JNIEnv *env, jclass declaring_class, jint interface_index,
        jlong expected_pid, jlong expected_uid) {
    jlong values[RESULT_FIELDS] = {0};
    struct browse_context state = {0};
    DNSServiceRef reference = NULL;
    int64_t started = 0, now = 0, deadline = 0;
    int have_start = 0, claimed_context = 0;
    int clock_error;
    jlongArray returned;
    (void) declaring_class;

    values[SCHEMA] = 1;
    values[PID] = (jlong) getpid();
    values[REAL_UID] = (jlong) (uint64_t) getuid();
    values[EFFECTIVE_UID] = (jlong) (uint64_t) geteuid();
    values[INTERFACE_INDEX] = interface_index;
    values[OUTCOME] = ADMISSION_REFUSED;
    values[ELAPSED_NS] = UNOBSERVED;
    values[BROWSE_CODE] = UNOBSERVED;
    values[SOCKET_FD] = UNOBSERVED;
    values[POLL_RETURN] = UNOBSERVED;
    values[PROCESS_CODE] = UNOBSERVED;
    values[FIRST_CALLBACK_ERROR] = UNOBSERVED;
    values[BUDGET_NS] = NORMAL_BUDGET_NS;

    clock_error = monotonic_ns(&started);
    if (clock_error != 0 || started > INT64_MAX - NORMAL_BUDGET_NS) {
        values[CLOCK_ERRNO] = clock_error != 0 ? clock_error : EOVERFLOW;
        values[OUTCOME] = CLOCK_FAILED;
        goto finished;
    }
    have_start = 1;
    deadline = started + NORMAL_BUDGET_NS;
    if (interface_index <= 0 || expected_pid <= 0 || expected_pid > INT32_MAX
            || expected_uid < 0 || (uint64_t) expected_uid > UINT32_MAX
            || values[PID] != expected_pid || values[REAL_UID] != expected_uid
            || values[EFFECTIVE_UID] != expected_uid) {
        goto finished;
    }
    if (active_context != NULL) {
        values[OUTCOME] = REENTRANT_REFUSED;
        goto finished;
    }
    state.interface_index = (uint32_t) interface_index;
    active_context = &state;
    claimed_context = 1;

    /* Exactly one new, interface-scoped synthetic browse. No registration,
     * resolver, shared connection, P2P flag, or discovery payload is requested.
     * Its result describes only this post-failure operation, not the raw send.
     */
    values[BROWSE_CODE] = DNSServiceBrowse(&reference, 0, state.interface_index,
            "_p2pkit-audit._tcp", "local.", browse_reply, &state);
    if (values[BROWSE_CODE] != kDNSServiceErr_NoError) {
        values[OUTCOME] = BROWSE_ERROR;
        goto finished; /* On immediate error the reference is uninitialized. */
    }
    if (reference == NULL) {
        values[OUTCOME] = REFERENCE_UNAVAILABLE;
        goto finished;
    }
    values[REF_CREATED] = 1;
    state.reference = reference;
    values[SOCKET_FD] = DNSServiceRefSockFD(reference);
    if (values[SOCKET_FD] < 0) {
        values[OUTCOME] = SOCKET_UNAVAILABLE;
        goto finished;
    }

    /* Only EINTR can repeat this loop, at most four times. The original deadline
     * never refills. Readiness is necessary but cannot guarantee ProcessResult
     * or deallocation will return: the unchanged Java45s watchdog remains final.
     */
    for (;;) {
        struct pollfd descriptor = {(int) values[SOCKET_FD], POLLIN, 0};
        int ready, error, timeout_ms;
        clock_error = monotonic_ns(&now);
        if (clock_error != 0 || now < started) {
            values[CLOCK_ERRNO] = clock_error != 0 ? clock_error : EIO;
            values[OUTCOME] = CLOCK_FAILED;
            break;
        }
        if (now >= deadline) {
            values[OUTCOME] = BUDGET_ELAPSED;
            break;
        }
        timeout_ms = (int) ((deadline - now + NS_PER_MILLISECOND - 1) / NS_PER_MILLISECOND);
        errno = 0;
        ready = poll(&descriptor, 1, timeout_ms);
        error = ready < 0 ? (errno != 0 ? errno : EIO) : 0;
        values[POLL_CALLS]++;
        values[POLL_RETURN] = ready;
        values[POLL_ERRNO] = error;
        values[POLL_REVENTS] = ready > 0 ? (unsigned short) descriptor.revents : 0;
        if (ready < 0 && error == EINTR) {
            if (values[EINTR_RETRIES] == EINTR_RETRY_LIMIT) {
                values[OUTCOME] = EINTR_EXHAUSTED;
                break;
            }
            values[EINTR_RETRIES]++;
            continue;
        }
        if (ready == 0) {
            values[OUTCOME] = POLL_TIMED_OUT;
            break;
        }
        if (ready != 1 || !(descriptor.revents & POLLIN)
                || (descriptor.revents & (POLLERR | POLLHUP | POLLNVAL))) {
            values[OUTCOME] = POLL_FAILED;
            break;
        }
        clock_error = monotonic_ns(&now);
        if (clock_error != 0 || now < started) {
            values[CLOCK_ERRNO] = clock_error != 0 ? clock_error : EIO;
            values[OUTCOME] = CLOCK_FAILED;
            break;
        }
        if (now >= deadline) {
            values[OUTCOME] = BUDGET_ELAPSED;
            break;
        }
        state.processing = 1;
        values[PROCESS_CODE] = DNSServiceProcessResult(reference);
        state.processing = 0;
        values[OUTCOME] = PROCESS_RETURNED;
        break;
    }

finished:
    /* No descriptor watch survives the stack-local poll. This owns only refs
     * actually initialized by a successful Browse, and never closes its borrowed
     * fd separately. A hanging call reaches neither returned flag nor JNI result.
     */
    if (values[REF_CREATED]) {
        values[DEALLOCATE_ATTEMPTED] = 1;
        DNSServiceRefDeallocate(reference);
        values[DEALLOCATE_RETURNED] = 1;
    }
    if (claimed_context) {
        active_context = NULL;
    }
    values[CALLBACK_COUNT] = state.callback_count;
    values[CALLBACK_OVERFLOW] = state.callback_overflow;
    values[FIRST_CALLBACK_ERROR] = state.first_error != kDNSServiceErr_NoError
            ? state.first_error : UNOBSERVED;
    values[CALLBACK_POLICY_COUNT] = state.policy_count;
    values[CALLBACK_CONTEXT_MISMATCH] = state.context_mismatch;
    values[POLICY_PHASE_MASK] = (values[BROWSE_CODE] == kDNSServiceErr_PolicyDenied ? 1 : 0)
            | (values[PROCESS_CODE] == kDNSServiceErr_PolicyDenied ? 2 : 0)
            | (state.policy_count != 0 ? 4 : 0);
    if (have_start) {
        clock_error = monotonic_ns(&now);
        if (clock_error != 0 || now < started) {
            if (values[CLOCK_ERRNO] == 0) {
                values[CLOCK_ERRNO] = clock_error != 0 ? clock_error : EIO;
            }
        } else if (values[CLOCK_ERRNO] == 0) {
            values[ELAPSED_NS] = now - started;
        }
    }
    /* Callback state is retired before any fallible Java allocation. An OOME or
     * pending JNI exception yields no Java-validated completion/closure claim.
     */
    returned = (*env)->NewLongArray(env, RESULT_FIELDS);
    if (returned != NULL) {
        (*env)->SetLongArrayRegion(env, returned, 0, RESULT_FIELDS, values);
    }
    return returned;
}
