/* Deterministic DNS-SD contract doubles: no daemon, multicast or peer qualification claim. */
#include "p2pkit_bonjour.h"
#include <dns_sd.h>
#include <assert.h>
#include <errno.h>
#include <net/if.h>
#include <netinet/in.h>
#include <pthread.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

struct _DNSServiceRef_t {
    int pipes[2];
    int kind;
    uint32_t index;
    const char *type;
    char name[64];
    void *context;
    DNSServiceBrowseReply browse;
    DNSServiceRegisterReply registration;
    DNSServiceResolveReply resolve;
};
static int scenario = 0, allocations = 0, frees = 0;
static pthread_mutex_t gate = PTHREAD_MUTEX_INITIALIZER;
static pthread_cond_t changed = PTHREAD_COND_INITIALIZER;
static bool entered = false, unblock = false, close_entered = false, close_done = false;
static uint32_t selected;
static DNSServiceErrorType create(DNSServiceRef *ref, int kind, uint32_t index,
    const char *type, const char *domain, const char *name, void *context) {
    assert(index == selected && index != 0 && strcmp(type, "_p2pkit2._tcp.") == 0 && strcmp(domain, "local.") == 0);
    if (scenario == 9) return kDNSServiceErr_PolicyDenied;
    *ref = calloc(1, sizeof(**ref)); assert(*ref != NULL);
    assert(pipe((*ref)->pipes) == 0 && write((*ref)->pipes[1], "x", 1) == 1);
    (*ref)->kind = kind; (*ref)->index = index; (*ref)->type = type; (*ref)->context = context;
    snprintf((*ref)->name, sizeof((*ref)->name), "%s", name);
    allocations++; return 0;
}
DNSServiceErrorType DNSSD_API DNSServiceBrowse(DNSServiceRef *ref, DNSServiceFlags flags, uint32_t index,
    const char *type, const char *domain, DNSServiceBrowseReply callback, void *context) {
    assert(flags == 0);
    int error = create(ref, 1, index, type, domain, "peer", context);
    if (!error) (*ref)->browse = callback;
    return error;
}
DNSServiceErrorType DNSSD_API DNSServiceRegister(DNSServiceRef *ref, DNSServiceFlags flags, uint32_t index,
    const char *name, const char *type, const char *domain, const char *host, uint16_t port,
    uint16_t length, const void *txt, DNSServiceRegisterReply callback, void *context) {
    assert(flags == kDNSServiceFlagsNoAutoRename && host == NULL && ntohs(port) == 3456);
    assert(length == 2 && memcmp(txt, "\1x", 2) == 0);
    int error = create(ref, 2, index, type, domain, name, context);
    if (!error) (*ref)->registration = callback;
    return error;
}
DNSServiceErrorType DNSSD_API DNSServiceResolve(DNSServiceRef *ref, DNSServiceFlags flags, uint32_t index,
    const char *name, const char *type, const char *domain, DNSServiceResolveReply callback, void *context) {
    assert(flags == 0);
    int error = create(ref, 3, index, type, domain, name, context);
    if (!error) (*ref)->resolve = callback;
    return error;
}
dnssd_sock_t DNSSD_API DNSServiceRefSockFD(DNSServiceRef ref) { return ref->pipes[0]; }
void DNSSD_API DNSServiceRefDeallocate(DNSServiceRef ref) {
    assert(ref != NULL); close(ref->pipes[0]); close(ref->pipes[1]); frees++; free(ref);
}
DNSServiceErrorType DNSSD_API DNSServiceProcessResult(DNSServiceRef ref) {
    char byte; assert(read(ref->pipes[0], &byte, 1) == 1);
    if (scenario == 8) {
        pthread_mutex_lock(&gate); entered = true; pthread_cond_broadcast(&changed);
        while (!unblock) pthread_cond_wait(&changed, &gate);
        pthread_mutex_unlock(&gate);
    }
    DNSServiceErrorType error = scenario == 4 ? kDNSServiceErr_PolicyDenied : 0;
    uint32_t index = scenario == 2 ? ref->index + 1 : ref->index;
    const char *domain = scenario == 3 ? "example.com." : "local.";
    const char *name = scenario == 6 ? "renamed" : ref->name;
    if (ref->kind == 1) {
        int count = scenario == 5 ? 17 : 1;
        for (int i = 0; i < count; ++i) ref->browse(ref, scenario == 1 ? 0 : kDNSServiceFlagsAdd,
            index, error, name, ref->type, domain, ref->context);
    } else if (ref->kind == 2) ref->registration(ref, kDNSServiceFlagsAdd, error, name, ref->type, domain, ref->context);
    else {
        char fullname[kDNSServiceMaxDomainName];
        assert(DNSServiceConstructFullName(fullname, name, ref->type, domain) == 0);
        ref->resolve(ref, 0, index, error, fullname, "ignored.local.", htons(3456),
            2, (const unsigned char *)"\1x", ref->context);
    }
    return 0;
}
static uint32_t read32(const uint8_t *bytes) {
    return ((uint32_t)bytes[0] << 24) | ((uint32_t)bytes[1] << 16) | ((uint32_t)bytes[2] << 8) | bytes[3];
}
static uint64_t open_ref(int kind) {
    uint64_t handle = 0;
    const uint8_t txt[] = {1, 'x'};
    assert(p2p_bonjour_open(selected, kind, 2, kind == 1 ? "" : "peer", kind == 2 ? 3456 : 0,
        kind == 2 ? txt : NULL, kind == 2 ? 2 : 0, &handle) == 0 && handle != 0);
    return handle;
}
static void test_admission(void) {
    uint64_t out = 123;
    assert(p2p_bonjour_abi() == 1);
    assert(p2p_bonjour_open(0, 1, 2, "", 0, NULL, 0, &out) == ENXIO && out == 0);
    assert(p2p_bonjour_open(UINT32_MAX, 1, 2, "", 0, NULL, 0, &out) == ENXIO);
    assert(p2p_bonjour_open(selected, 0, 2, "", 0, NULL, 0, &out) == EINVAL);
    assert(p2p_bonjour_open(selected, 1, 9, "", 0, NULL, 0, &out) == EINVAL);
    assert(p2p_bonjour_open(selected, 1, 2, "peer", 0, NULL, 0, &out) == EINVAL);
    assert(p2p_bonjour_open(selected, 2, 2, "peer", 0, NULL, 0, &out) == EINVAL);
    assert(p2p_bonjour_open(selected, 3, 2, "peer\n", 0, NULL, 0, &out) == EINVAL);
    assert(p2p_bonjour_open(selected, 3, 2, "peer", 1, NULL, 0, &out) == EINVAL);
    assert(p2p_bonjour_open(selected, 2, 2, "peer", 1, NULL, 1301, &out) == EINVAL);
    puts("PASS admission and explicit scope");
}
static void test_frames(void) {
    uint8_t frame[P2P_BONJOUR_FRAME];
    for (int kind = 1; kind <= 3; ++kind) {
        scenario = 0; uint64_t handle = open_ref(kind);
        assert(p2p_bonjour_poll(handle, 101, frame) == -EINVAL);
        assert(p2p_bonjour_poll(handle, 100, frame) == 1);
        assert(read32(frame) == (uint32_t)(kind == 2 ? 4 : kind));
        assert(read32(frame + 8) == selected && read32(frame + 16) == 4 && memcmp(frame + 24, "peer", 4) == 0);
        if (kind == 3) assert(read32(frame + 12) == 3456 && read32(frame + 20) == 2);
        assert(p2p_bonjour_poll(handle, 0, frame) == 0);
        assert(p2p_bonjour_close(handle) == 0);
        assert(p2p_bonjour_close(handle) == EBADF && p2p_bonjour_poll(handle, 0, frame) == -EBADF);
    }
    scenario = 1; uint64_t handle = open_ref(1);
    assert(p2p_bonjour_poll(handle, 100, frame) == 1 && read32(frame) == 2);
    assert(p2p_bonjour_close(handle) == 0);
    puts("PASS registration browse removal resolve and stale handles");
}
static void test_rejections(void) {
    for (int mode = 2; mode <= 6; ++mode) {
        scenario = mode; uint64_t handle = open_ref(mode == 6 ? 2 : 1);
        uint8_t frame[P2P_BONJOUR_FRAME];
        assert(p2p_bonjour_poll(handle, 100, frame) == 1 && read32(frame) == 5);
        int32_t code = (int32_t)read32(frame + 4);
        assert(code == (mode == 4 ? kDNSServiceErr_PolicyDenied : mode == 5 ? ENOBUFS : EPROTO));
        assert(p2p_bonjour_poll(handle, 0, frame) == 1 && read32(frame) == 5);
        assert(p2p_bonjour_close(handle) == 0);
    }
    scenario = 6; uint64_t handle = open_ref(3); uint8_t frame[P2P_BONJOUR_FRAME];
    assert(p2p_bonjour_poll(handle, 0, frame) == 1 && read32(frame) == 5);
    assert(p2p_bonjour_close(handle) == 0);
    puts("PASS wrong interface domain identity policy and overflow rejection");
}
static void test_failed_open_and_capacity(void) {
    uint64_t handle = 0; scenario = 9;
    assert(p2p_bonjour_open(selected, 1, 2, "", 0, NULL, 0, &handle) == kDNSServiceErr_PolicyDenied && handle != 0);
    assert(p2p_bonjour_close(handle) == 0);
    scenario = 0; uint64_t handles[P2P_BONJOUR_HANDLES];
    for (unsigned i = 0; i < P2P_BONJOUR_HANDLES; ++i) handles[i] = open_ref(1);
    assert(p2p_bonjour_open(selected, 1, 2, "", 0, NULL, 0, &handle) == EMFILE && handle == 0);
    for (unsigned i = 0; i < P2P_BONJOUR_HANDLES; ++i) assert(p2p_bonjour_close(handles[i]) == 0);
    puts("PASS failed-open ownership and bounded capacity");
}
static void *poll_thread(void *context) {
    uint8_t frame[P2P_BONJOUR_FRAME]; assert(p2p_bonjour_poll(*(uint64_t *)context, 100, frame) == 1); return NULL;
}
static void *close_thread(void *context) {
    pthread_mutex_lock(&gate); close_entered = true; pthread_cond_broadcast(&changed); pthread_mutex_unlock(&gate);
    assert(p2p_bonjour_close(*(uint64_t *)context) == 0);
    pthread_mutex_lock(&gate); close_done = true; pthread_cond_broadcast(&changed); pthread_mutex_unlock(&gate);
    return NULL;
}
static void test_race(void) {
    scenario = 8; uint64_t handle = open_ref(1); pthread_t polling, closing;
    assert(pthread_create(&polling, NULL, poll_thread, &handle) == 0);
    pthread_mutex_lock(&gate); while (!entered) pthread_cond_wait(&changed, &gate); pthread_mutex_unlock(&gate);
    uint8_t frame[P2P_BONJOUR_FRAME]; assert(p2p_bonjour_poll(handle, 0, frame) == -EBUSY);
    assert(pthread_create(&closing, NULL, close_thread, &handle) == 0);
    pthread_mutex_lock(&gate); while (!close_entered) pthread_cond_wait(&changed, &gate);
    assert(!close_done); unblock = true; pthread_cond_broadcast(&changed); pthread_mutex_unlock(&gate);
    assert(pthread_join(polling, NULL) == 0 && pthread_join(closing, NULL) == 0);
    assert(close_done && p2p_bonjour_close(handle) == EBADF);
    puts("PASS concurrent poll rejection and close waits for callback lease");
}
int main(void) {
    selected = if_nametoindex("lo0"); assert(selected != 0);
    test_admission(); test_frames(); test_rejections(); test_failed_open_and_capacity(); test_race();
    assert(allocations == frees); puts("PASS every created reference deallocated exactly once");
    return 0;
}
