/* Diagnostic-only: one real loopback registration and one continuous Any TXT query. */
#include <TargetConditionals.h>
#if !TARGET_OS_SIMULATOR || !TARGET_OS_IOS || !defined(__x86_64__)
#error This probe must run as an Intel iOS Simulator executable.
#endif
#ifndef P2PKIT_PROBE_SOURCE
#error Missing source binding.
#endif
#ifndef P2PKIT_PROBE_RUN
#error Missing run binding.
#endif
#ifndef P2PKIT_PROBE_ATTEMPT
#error Missing attempt binding.
#endif

#include <arpa/inet.h>
#include <dispatch/dispatch.h>
#include <dns_sd.h>
#include <ifaddrs.h>
#include <limits.h>
#include <net/if.h>
#include <signal.h>
#include <stdatomic.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <time.h>
#include <unistd.h>

enum { CALLBACK_LIMIT = 1024, UNSET_CODE = INT_MIN };
static const int64_t SECOND = 1000000000LL;
static const unsigned char TXT_A[] = {3, 'v', '=', 'A'};
static const unsigned char TXT_B[] = {3, 'v', '=', 'B'};
static const char SERVICE_TYPE[] = "_p2pkit2._tcp";
static const char DOMAIN[] = "local.";

enum reason {
    NONE, ARGUMENT, ALLOCATION, CLOCK, INTERFACE, LISTENER, LISTENER_CHANGED, LISTENER_CLOSE,
    REGISTER_API, REGISTER_QUEUE, REGISTER_CALLBACK, REGISTER_IDENTITY, REGISTER_TIMEOUT,
    QUERY_API, QUERY_QUEUE, QUERY_CALLBACK, QUERY_IDENTITY, INITIAL_A_TIMEOUT,
    UPDATE_API, UPDATE_ORDER, UPDATE_TIMEOUT, CALLBACK_LIMIT_REACHED, CLEANUP_TIMEOUT
};
static const char *const REASONS[] = {
    "NONE", "ARGUMENT", "ALLOCATION", "CLOCK", "INTERFACE", "LISTENER", "LISTENER_CHANGED", "LISTENER_CLOSE",
    "REGISTER_API", "REGISTER_QUEUE", "REGISTER_CALLBACK", "REGISTER_IDENTITY", "REGISTER_TIMEOUT",
    "QUERY_API", "QUERY_QUEUE", "QUERY_CALLBACK", "QUERY_IDENTITY", "INITIAL_A_TIMEOUT",
    "UPDATE_API", "UPDATE_ORDER", "UPDATE_TIMEOUT", "CALLBACK_LIMIT_REACHED", "CLEANUP_TIMEOUT"
};

enum field {
    INTERFACE_VALIDATED, LISTENER_STARTED, LISTENER_PRESERVED, REGISTRATION_READY, INITIAL_A, UPDATED_B,
    PUBLISHER_REF_PRESERVED, QUERY_REF_PRESERVED, CONTEXT_RELEASED,
    REGISTER_CALLS, QUERY_CALLS, UPDATE_CALLS,
    REGISTER_CODE, QUERY_CODE, UPDATE_CODE, REGISTER_QUEUE_CODE, QUERY_QUEUE_CODE,
    REGISTER_CALLBACK_CODE, QUERY_CALLBACK_CODE,
    REGISTER_CALLBACKS, QUERY_CALLBACKS, REMOVE_CALLBACKS, A_CALLBACKS, B_CALLBACKS,
    FIRST_SCOPE, UPDATE_SCOPE, UPDATE_ELAPSED_MS, PUBLISHER_CLEANUP, QUERY_CLEANUP, FIELD_COUNT
};
enum value_kind { NUMBER, BOOLEAN, OPTIONAL_NUMBER, SCOPE, CLEANUP };
struct field_spec { const char *name; enum value_kind kind; };
static const struct field_spec FIELDS[FIELD_COUNT] = {
    {"interfaceValidated", BOOLEAN}, {"listenerStarted", BOOLEAN}, {"listenerPreserved", BOOLEAN},
    {"registrationReady", BOOLEAN}, {"initialA", BOOLEAN}, {"updatedB", BOOLEAN},
    {"publisherRefPreserved", BOOLEAN}, {"queryRefPreserved", BOOLEAN}, {"contextReleased", BOOLEAN},
    {"registerCalls", NUMBER}, {"queryCalls", NUMBER}, {"updateCalls", NUMBER},
    {"registerCode", OPTIONAL_NUMBER}, {"queryCode", OPTIONAL_NUMBER}, {"updateCode", OPTIONAL_NUMBER},
    {"registerQueueCode", OPTIONAL_NUMBER}, {"queryQueueCode", OPTIONAL_NUMBER},
    {"registerCallbackCode", OPTIONAL_NUMBER}, {"queryCallbackCode", OPTIONAL_NUMBER},
    {"registerCallbacks", NUMBER}, {"queryCallbacks", NUMBER}, {"removeCallbacks", NUMBER},
    {"aCallbacks", NUMBER}, {"bCallbacks", NUMBER}, {"firstScope", SCOPE}, {"updateScope", SCOPE},
    {"updateElapsedMs", OPTIONAL_NUMBER}, {"publisherCleanup", CLEANUP}, {"queryCleanup", CLEANUP}
};
static const char *const SCOPES[] = {"NONE", "ANY", "LOCAL_ONLY", "P2P", "UNICAST", "BLE", "INFRA", "CONCRETE"};
static const char *const CLEANUPS[] = {"NOT_STARTED", "COMPLETE", "TIMED_OUT"};

struct probe {
    atomic_llong values[FIELD_COUNT];
    atomic_int failure;
    atomic_bool closing;
    atomic_llong update_started;
    int64_t register_deadline;
    int64_t initial_deadline;
    dispatch_queue_t publisher_queue;
    dispatch_queue_t query_queue;
    dispatch_semaphore_t event;
    /* Each ref and its original value are read/written only on their owning serial queue. */
    DNSServiceRef publisher_ref, original_publisher;
    DNSServiceRef query_ref, original_query;
    char name[64];
    char full_name[kDNSServiceMaxDomainName];
    uint32_t interface_index;
    int listener;
    uint16_t network_port;
};

static long long value(struct probe *p, enum field key) { return atomic_load(&p->values[key]); }
static void set_value(struct probe *p, enum field key, long long n) { atomic_store(&p->values[key], n); }

static void fail(struct probe *p, enum reason reason) {
    int expected = NONE;
    atomic_compare_exchange_strong(&p->failure, &expected, reason);
    if (p->event != NULL) dispatch_semaphore_signal(p->event);
}

static int64_t now_ns(struct probe *p) {
    struct timespec ts;
    if (clock_gettime(CLOCK_MONOTONIC, &ts) != 0) {
        fail(p, CLOCK);
        return 0;
    }
    return (int64_t)ts.tv_sec * SECOND + ts.tv_nsec;
}

static bool count_callback(struct probe *p, enum field key) {
    if (atomic_fetch_add(&p->values[key], 1) >= CALLBACK_LIMIT) {
        set_value(p, key, CALLBACK_LIMIT);
        fail(p, CALLBACK_LIMIT_REACHED);
        return false;
    }
    return true;
}

static void callback_code(struct probe *p, enum field key, DNSServiceErrorType code) {
    if (value(p, key) == UNSET_CODE || value(p, key) == 0) set_value(p, key, code);
}

static bool same_text(const char *actual, const char *expected, bool trailing_dot) {
    if (actual == NULL) return false;
    size_t expected_length = strlen(expected);
    size_t actual_length = strnlen(actual, expected_length + 2);
    if (trailing_dot) {
        if (actual_length > 0 && actual[actual_length - 1] == '.') --actual_length;
        if (expected_length > 0 && expected[expected_length - 1] == '.') --expected_length;
    }
    return actual_length == expected_length && memcmp(actual, expected, expected_length) == 0;
}

static unsigned scope(uint32_t index) {
    if (index == kDNSServiceInterfaceIndexAny) return 1;
    if (index == kDNSServiceInterfaceIndexLocalOnly) return 2;
    if (index == kDNSServiceInterfaceIndexP2P) return 3;
    if (index == kDNSServiceInterfaceIndexUnicast) return 4;
    if (index == kDNSServiceInterfaceIndexBLE) return 5;
    if (index == kDNSServiceInterfaceIndexInfra) return 6;
    return 7;
}

static bool validate_loopback(struct probe *p) {
    unsigned index = if_nametoindex("lo0");
    if (index == 0 || scope(index) != 7) return false;
    struct ifaddrs *addresses = NULL;
    if (getifaddrs(&addresses) != 0) return false;
    bool found = false;
    const unsigned required = IFF_UP | IFF_RUNNING | IFF_LOOPBACK | IFF_MULTICAST;
    for (const struct ifaddrs *a = addresses; a != NULL; a = a->ifa_next) {
        if (a->ifa_name == NULL || strcmp(a->ifa_name, "lo0") != 0 || a->ifa_addr == NULL ||
            a->ifa_addr->sa_family != AF_INET || (a->ifa_flags & required) != required ||
            if_nametoindex(a->ifa_name) != index) continue;
        const struct sockaddr_in *address = (const struct sockaddr_in *)a->ifa_addr;
        if ((ntohl(address->sin_addr.s_addr) >> 24) == 127) found = true;
    }
    freeifaddrs(addresses);
    if (found) p->interface_index = index;
    return found;
}

static bool start_listener(struct probe *p) {
    p->listener = socket(AF_INET, SOCK_STREAM, 0);
    if (p->listener < 0) return false;
    struct sockaddr_in address = {0};
    address.sin_len = sizeof(address);
    address.sin_family = AF_INET;
    address.sin_addr.s_addr = htonl(INADDR_LOOPBACK);
    if (bind(p->listener, (const struct sockaddr *)&address, sizeof(address)) != 0 ||
        listen(p->listener, 1) != 0) return false;
    socklen_t length = sizeof(address);
    if (getsockname(p->listener, (struct sockaddr *)&address, &length) != 0 ||
        length != sizeof(address) || address.sin_port == 0) return false;
    p->network_port = address.sin_port;
    return true;
}

static bool listener_unchanged(struct probe *p) {
    struct sockaddr_in address = {0};
    socklen_t length = sizeof(address);
    return p->listener >= 0 && getsockname(p->listener, (struct sockaddr *)&address, &length) == 0 &&
        length == sizeof(address) && address.sin_family == AF_INET && address.sin_port == p->network_port &&
        address.sin_addr.s_addr == htonl(INADDR_LOOPBACK);
}

static void DNSSD_API registered(DNSServiceRef ref, DNSServiceFlags flags, DNSServiceErrorType error,
                                 const char *name, const char *type, const char *domain, void *context) {
    struct probe *p = context;
    if (!count_callback(p, REGISTER_CALLBACKS)) return;
    callback_code(p, REGISTER_CALLBACK_CODE, error);
    /* The other callback fields are undefined when error is nonzero. */
    if (error != kDNSServiceErr_NoError) { fail(p, REGISTER_CALLBACK); return; }
    if (ref != p->original_publisher || ref == NULL) {
        set_value(p, PUBLISHER_REF_PRESERVED, 0);
        fail(p, REGISTER_IDENTITY);
        return;
    }
    if (!(flags & kDNSServiceFlagsAdd) || !same_text(name, p->name, false) ||
        !same_text(type, SERVICE_TYPE, true) || !same_text(domain, DOMAIN, true)) {
        fail(p, REGISTER_IDENTITY);
        return;
    }
    if (now_ns(p) > p->register_deadline) { fail(p, REGISTER_TIMEOUT); return; }
    set_value(p, REGISTRATION_READY, 1);
    dispatch_semaphore_signal(p->event);
}

static void DNSSD_API answered(DNSServiceRef ref, DNSServiceFlags flags, uint32_t interface_index,
                               DNSServiceErrorType error, const char *name, uint16_t type, uint16_t class,
                               uint16_t length, const void *data, uint32_t ttl, void *context) {
    (void)ttl;
    struct probe *p = context;
    if (!count_callback(p, QUERY_CALLBACKS)) return;
    callback_code(p, QUERY_CALLBACK_CODE, error);
    /* No name, type, class, RDATA, flags or interface access before this error check. */
    if (error != kDNSServiceErr_NoError) { fail(p, QUERY_CALLBACK); return; }
    if (ref != p->original_query || ref == NULL) {
        set_value(p, QUERY_REF_PRESERVED, 0);
        fail(p, QUERY_IDENTITY);
        return;
    }
    if (!same_text(name, p->full_name, false) || type != kDNSServiceType_TXT || class != kDNSServiceClass_IN) {
        fail(p, QUERY_IDENTITY);
        return;
    }
    if (!(flags & kDNSServiceFlagsAdd)) { count_callback(p, REMOVE_CALLBACKS); return; }
    if (data == NULL || length != sizeof(TXT_A)) { fail(p, QUERY_IDENTITY); return; }
    int64_t received = now_ns(p);
    if (memcmp(data, TXT_A, sizeof(TXT_A)) == 0) {
        if (!count_callback(p, A_CALLBACKS)) return;
        if (!value(p, INITIAL_A)) {
            if (received > p->initial_deadline) { fail(p, INITIAL_A_TIMEOUT); return; }
            set_value(p, FIRST_SCOPE, scope(interface_index));
            set_value(p, INITIAL_A, 1);
            /* Signal from this callback, without imposing a callback-return barrier. */
            dispatch_semaphore_signal(p->event);
        }
    } else if (memcmp(data, TXT_B, sizeof(TXT_B)) == 0) {
        if (!count_callback(p, B_CALLBACKS)) return;
        int64_t started = atomic_load(&p->update_started);
        if (!value(p, INITIAL_A) || value(p, UPDATE_CALLS) != 1 || started <= 0 || received < started) {
            fail(p, UPDATE_ORDER);
            return;
        }
        if (!value(p, UPDATED_B)) {
            set_value(p, UPDATE_ELAPSED_MS, (received - started) / 1000000);
            set_value(p, UPDATE_SCOPE, scope(interface_index));
            if (received - started >= 30 * SECOND) { fail(p, UPDATE_TIMEOUT); return; }
            set_value(p, UPDATED_B, 1);
            dispatch_semaphore_signal(p->event);
        }
    } else {
        fail(p, QUERY_IDENTITY);
    }
}

static bool wait_for(struct probe *p, enum field key, int64_t deadline, enum reason timeout) {
    while (!value(p, key) && atomic_load(&p->failure) == NONE) {
        int64_t remaining = deadline - now_ns(p);
        if (remaining <= 0) { fail(p, timeout); break; }
        dispatch_semaphore_wait(p->event, dispatch_time(DISPATCH_TIME_NOW, remaining));
    }
    return value(p, key) != 0 && atomic_load(&p->failure) == NONE;
}

static void begin_registration(struct probe *p) {
    dispatch_async(p->publisher_queue, ^{
        if (atomic_load(&p->closing)) return;
        DNSServiceRef output = NULL;
        set_value(p, REGISTER_CALLS, 1);
        DNSServiceErrorType code = DNSServiceRegister(&output,
            kDNSServiceFlagsNoAutoRename | kDNSServiceFlagsIncludeP2P, p->interface_index,
            p->name, SERVICE_TYPE, DOMAIN, NULL, p->network_port, sizeof(TXT_A), TXT_A, registered, p);
        set_value(p, REGISTER_CODE, code);
        if (code != 0) { fail(p, REGISTER_API); return; }
        /* Error output is undefined; acquire ownership only after success. */
        p->publisher_ref = p->original_publisher = output;
        if (output == NULL) { fail(p, REGISTER_API); return; }
        set_value(p, PUBLISHER_REF_PRESERVED, 1);
        code = DNSServiceSetDispatchQueue(output, p->publisher_queue);
        set_value(p, REGISTER_QUEUE_CODE, code);
        if (code != 0) fail(p, REGISTER_QUEUE);
    });
}

static void begin_query(struct probe *p) {
    dispatch_async(p->query_queue, ^{
        if (atomic_load(&p->closing)) return;
        DNSServiceRef output = NULL;
        set_value(p, QUERY_CALLS, 1);
        DNSServiceErrorType code = DNSServiceQueryRecord(&output,
            kDNSServiceFlagsIncludeP2P | kDNSServiceFlagsLongLivedQuery, kDNSServiceInterfaceIndexAny,
            p->full_name, kDNSServiceType_TXT, kDNSServiceClass_IN, answered, p);
        set_value(p, QUERY_CODE, code);
        if (code != 0) { fail(p, QUERY_API); return; }
        p->query_ref = p->original_query = output;
        if (output == NULL) { fail(p, QUERY_API); return; }
        set_value(p, QUERY_REF_PRESERVED, 1);
        code = DNSServiceSetDispatchQueue(output, p->query_queue);
        set_value(p, QUERY_QUEUE_CODE, code);
        if (code != 0) fail(p, QUERY_QUEUE);
    });
}

static void update_once(struct probe *p) {
    dispatch_async(p->publisher_queue, ^{
        if (atomic_load(&p->closing)) return;
        if (p->publisher_ref == NULL || p->publisher_ref != p->original_publisher) {
            set_value(p, PUBLISHER_REF_PRESERVED, 0);
            fail(p, UPDATE_ORDER);
            return;
        }
        if (value(p, UPDATE_CALLS) != 0 || !value(p, INITIAL_A)) { fail(p, UPDATE_ORDER); return; }
        set_value(p, UPDATE_CALLS, 1);
        DNSServiceErrorType code = DNSServiceUpdateRecord(p->publisher_ref, NULL, 0, sizeof(TXT_B), TXT_B, 0);
        set_value(p, UPDATE_CODE, code);
        if (code != 0) fail(p, UPDATE_API);
    });
}

static bool drain_queues(struct probe *p) {
    atomic_store(&p->closing, true);
    dispatch_group_t drain = dispatch_group_create();
    if (drain == NULL) { fail(p, ALLOCATION); return false; }
    if (p->publisher_queue != NULL) dispatch_group_async(drain, p->publisher_queue, ^{
        if (p->publisher_ref != NULL) DNSServiceRefDeallocate(p->publisher_ref);
        p->publisher_ref = NULL;
        /* Explicit deallocation has no cancellation callback. Drain a later queue turn. */
        dispatch_group_async(drain, p->publisher_queue, ^{
            set_value(p, PUBLISHER_CLEANUP, 1);
        });
    });
    else set_value(p, PUBLISHER_CLEANUP, 1);
    if (p->query_queue != NULL) dispatch_group_async(drain, p->query_queue, ^{
        if (p->query_ref != NULL) DNSServiceRefDeallocate(p->query_ref);
        p->query_ref = NULL;
        dispatch_group_async(drain, p->query_queue, ^{
            set_value(p, QUERY_CLEANUP, 1);
        });
    });
    else set_value(p, QUERY_CLEANUP, 1);
    /* Group completion follows block return, not an in-block semaphore acknowledgement.
       Cleanup remains mandatory even after the original functional failure. */
    bool complete = dispatch_group_wait(drain, dispatch_time(DISPATCH_TIME_NOW, 5 * SECOND)) == 0;
    dispatch_release(drain);
    if (!complete) fail(p, CLEANUP_TIMEOUT);
    return complete;
}

static bool fixed_binding(const char *text, size_t length, bool hexadecimal) {
    if (strlen(text) != length || length == 0) return false;
    for (size_t i = 0; i < length; ++i) {
        if ((text[i] < '0' || text[i] > '9') && (!hexadecimal || text[i] < 'a' || text[i] > 'f')) return false;
    }
    return true;
}

static void print_result(enum reason failure, const long long values[FIELD_COUNT]) {
    printf("{\"schema\":1,\"scope\":\"SIMULATOR_LOOPBACK_DNS_SD_NATIVE_V1\","
           "\"source\":\"%s\",\"runId\":\"%s\",\"runAttempt\":%d,\"target\":\"IOS_SIMULATOR_X86_64\","
           "\"status\":\"%s\",\"reason\":\"%s\"", P2PKIT_PROBE_SOURCE, P2PKIT_PROBE_RUN,
           P2PKIT_PROBE_ATTEMPT, failure == NONE ? "PASS" : "FAIL", REASONS[failure]);
    for (unsigned i = 0; i < FIELD_COUNT; ++i) {
        printf(",\"%s\":", FIELDS[i].name);
        switch (FIELDS[i].kind) {
            case BOOLEAN: printf("%s", values[i] ? "true" : "false"); break;
            case OPTIONAL_NUMBER:
                if (values[i] == UNSET_CODE) printf("null"); else printf("%lld", values[i]);
                break;
            case SCOPE: printf("\"%s\"", SCOPES[values[i]]); break;
            case CLEANUP: printf("\"%s\"", CLEANUPS[values[i]]); break;
            case NUMBER: printf("%lld", values[i]); break;
        }
    }
    puts("}");
    fflush(stdout);
}

int main(int argc, char **argv) {
    /* Build-bound fields are validated before being included in the finite JSON. */
    size_t run_length = strlen(P2PKIT_PROBE_RUN);
    if (!fixed_binding(P2PKIT_PROBE_SOURCE, 40, true) || run_length > 20 ||
        !fixed_binding(P2PKIT_PROBE_RUN, run_length, false) || P2PKIT_PROBE_ATTEMPT != 1) return 64;
    /* Keep the native bound through allocation, cleanup and final output. */
    if (signal(SIGALRM, SIG_DFL) == SIG_ERR) return 71;
    alarm(90);
    struct probe *p = calloc(1, sizeof(*p));
    if (p == NULL) return 70;
    for (unsigned i = 0; i < FIELD_COUNT; ++i) {
        atomic_init(&p->values[i], FIELDS[i].kind == OPTIONAL_NUMBER ? UNSET_CODE : 0);
    }
    atomic_init(&p->failure, NONE);
    atomic_init(&p->closing, false);
    atomic_init(&p->update_started, 0);
    p->listener = -1;
    p->event = dispatch_semaphore_create(0);
    p->publisher_queue = dispatch_queue_create("p2pkit.probe.publisher", DISPATCH_QUEUE_SERIAL);
    p->query_queue = dispatch_queue_create("p2pkit.probe.query", DISPATCH_QUEUE_SERIAL);
    if (p->event == NULL || p->publisher_queue == NULL || p->query_queue == NULL) fail(p, ALLOCATION);
    else if (argc != 2 || !fixed_binding(argv[1], 32, true)) fail(p, ARGUMENT);
    else if (!validate_loopback(p)) fail(p, INTERFACE);
    else {
        set_value(p, INTERFACE_VALIDATED, 1);
        if (!start_listener(p)) fail(p, LISTENER);
        else {
            set_value(p, LISTENER_STARTED, 1);
            snprintf(p->name, sizeof(p->name), "p2pkit-route-%s", argv[1]);
            if (DNSServiceConstructFullName(p->full_name, p->name, SERVICE_TYPE, DOMAIN) != 0) fail(p, ARGUMENT);
            else {
                p->register_deadline = now_ns(p) + 5 * SECOND;
                begin_registration(p);
                if (wait_for(p, REGISTRATION_READY, p->register_deadline, REGISTER_TIMEOUT)) {
                    p->initial_deadline = now_ns(p) + 30 * SECOND;
                    begin_query(p);
                    if (wait_for(p, INITIAL_A, p->initial_deadline, INITIAL_A_TIMEOUT)) {
                        if (!listener_unchanged(p)) fail(p, LISTENER_CHANGED);
                        else {
                            int64_t started = now_ns(p);
                            atomic_store(&p->update_started, started);
                            update_once(p);
                            wait_for(p, UPDATED_B, started + 30 * SECOND, UPDATE_TIMEOUT);
                        }
                    }
                }
            }
        }
    }
    if (value(p, LISTENER_STARTED)) {
        bool unchanged = listener_unchanged(p);
        set_value(p, LISTENER_PRESERVED, unchanged);
        if (!unchanged) fail(p, LISTENER_CHANGED);
    }
    bool drained = p->event != NULL && drain_queues(p);
    if (p->listener >= 0 && close(p->listener) != 0) fail(p, LISTENER_CLOSE);
    long long report[FIELD_COUNT];
    for (unsigned i = 0; i < FIELD_COUNT; ++i) report[i] = value(p, (enum field)i);
    if (!drained) {
        if (report[PUBLISHER_CLEANUP] != 1) report[PUBLISHER_CLEANUP] = 2;
        if (report[QUERY_CLEANUP] != 1) report[QUERY_CLEANUP] = 2;
    }
    enum reason failure = atomic_load(&p->failure);
    if (drained) {
        if (p->publisher_queue != NULL) dispatch_release(p->publisher_queue);
        if (p->query_queue != NULL) dispatch_release(p->query_queue);
        dispatch_release(p->event);
        free(p);
        report[CONTEXT_RELEASED] = 1;
    }
    /* On incomplete drain keep the callback context alive until process exit. */
    print_result(failure, report);
    _Exit(failure == NONE ? 0 : 2);
}
