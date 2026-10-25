#include "p2pkit_lan_socket.h"

#include <assert.h>
#include <errno.h>
#include <fcntl.h>
#include <net/if.h>
#include <netinet/in.h>
#include <pthread.h>
#include <signal.h>
#include <stdatomic.h>
#include <stdbool.h>
#include <stdio.h>
#include <string.h>
#include <sys/resource.h>
#include <sys/socket.h>
#include <time.h>
#include <unistd.h>

static const uint8_t loopback[4] = {127, 0, 0, 1};
static unsigned int lo;
static unsigned int tests;
static atomic_int configure_error;
static pthread_mutex_t poll_barrier = PTHREAD_MUTEX_INITIALIZER;
static pthread_cond_t poll_changed = PTHREAD_COND_INITIALIZER;
static bool pause_poll, poll_leased;

int32_t p2p_lan_test_configure_error(void) { return atomic_exchange(&configure_error, 0); }
void p2p_lan_test_poll_leased(void) {
    pthread_mutex_lock(&poll_barrier);
    if (pause_poll) {
        poll_leased = true;
        pthread_cond_broadcast(&poll_changed);
        while (pause_poll) pthread_cond_wait(&poll_changed, &poll_barrier);
    }
    pthread_mutex_unlock(&poll_barrier);
}

#define OK(call) do { int32_t error = (call); if (error != 0) { \
    fprintf(stderr, "line %d: %s returned errno %d\n", __LINE__, #call, error); assert(error == 0); } } while (0)
#define PASS(name) do { ++tests; printf("PASS %s\n", name); fflush(stdout); } while (0)

static int64_t nanos(void) {
    struct timespec now;
    assert(clock_gettime(CLOCK_MONOTONIC, &now) == 0);
    return (int64_t)now.tv_sec * INT64_C(1000000000) + now.tv_nsec;
}

static unsigned int descriptors(void) {
    struct rlimit limit;
    assert(getrlimit(RLIMIT_NOFILE, &limit) == 0);
    unsigned int count = 0;
    for (rlim_t fd = 0; fd < limit.rlim_cur; ++fd) {
        if (fcntl((int)fd, F_GETFD) >= 0) ++count;
        else assert(errno == EBADF);
    }
    return count;
}

static void ready(uint64_t h, int write) {
    int64_t deadline = nanos() + INT64_C(2000000000);
    int32_t value = 0;
    do { OK(p2p_lan_socket_poll(h, write, 100, &value)); assert(nanos() < deadline); } while (!value);
}

typedef struct { uint64_t listener, outgoing, incoming; uint16_t port; } pair;

static pair connected_pair(void) {
    pair p = {0};
    uint8_t address[4];
    OK(p2p_lan_socket_open(lo, &p.listener));
    OK(p2p_lan_socket_bind(p.listener, loopback, 0));
    OK(p2p_lan_socket_listen(p.listener, 5));
    OK(p2p_lan_socket_endpoint(p.listener, 0, address, &p.port));
    assert(p.port != 0 && memcmp(address, loopback, 4) == 0);
    OK(p2p_lan_socket_open(lo, &p.outgoing));
    OK(p2p_lan_socket_bind(p.outgoing, loopback, 0));
    int32_t error = p2p_lan_socket_connect(p.outgoing, loopback, p.port);
    assert(error == 0 || error == EINPROGRESS);
    ready(p.outgoing, 1);
    OK(p2p_lan_socket_connected(p.outgoing));
    ready(p.listener, 0);
    OK(p2p_lan_socket_accept(p.listener, &p.incoming));
    return p;
}

static void close_pair(pair p) {
    OK(p2p_lan_socket_close(p.incoming));
    OK(p2p_lan_socket_close(p.outgoing));
    OK(p2p_lan_socket_close(p.listener));
}

static void inputs(void) {
    assert(p2p_lan_socket_abi() == P2P_LAN_SOCKET_ABI);
    assert(p2p_lan_socket_open(lo, NULL) == EINVAL);
    uint64_t h = 42;
    assert(p2p_lan_socket_open(0, &h) == ENXIO && h == 0);
    assert(p2p_lan_socket_open(UINT32_MAX, &h) == ENXIO && h == 0);
    PASS("abi-and-invalid-interface-do-not-publish-handle");
    assert(p2p_lan_socket_close(0) == EBADF);
    assert(p2p_lan_socket_close(UINT64_MAX) == EBADF);
    uint32_t index = 42;
    assert(p2p_lan_socket_bound_interface(0, &index) == EBADF && index == 0);
    PASS("invalid-handles-and-cleared-outputs");
    OK(p2p_lan_socket_open(lo, &h));
    uint8_t bytes[4] = {0};
    assert(p2p_lan_socket_bind(h, NULL, 0) == EINVAL);
    assert(p2p_lan_socket_bind(h, bytes, 0) == EADDRNOTAVAIL);
    assert(p2p_lan_socket_listen(h, 5) == EADDRNOTAVAIL);
    assert(p2p_lan_socket_connect(h, loopback, 12345) == EADDRNOTAVAIL);
    assert(p2p_lan_socket_listen(h, 0) == EINVAL);
    assert(p2p_lan_socket_listen(h, 129) == EINVAL);
    assert(p2p_lan_socket_connect(h, loopback, 0) == EINVAL);
    assert(p2p_lan_socket_option(h, 0, 0) == EINVAL);
    assert(p2p_lan_socket_option(h, 1, 2) == EINVAL);
    PASS("wildcard-and-invalid-socket-arguments-rejected");
    uint32_t count = 42;
    assert(p2p_lan_socket_read(h, bytes, 0, &count) == EINVAL && count == 0);
    assert(p2p_lan_socket_write(h, bytes, P2P_LAN_SOCKET_MAX_BYTES + 1, &count) == EINVAL);
    assert(p2p_lan_socket_read(h, NULL, 1, &count) == EINVAL);
    assert(p2p_lan_socket_read(h, bytes, 1, NULL) == EINVAL);
    int32_t r = 42;
    assert(p2p_lan_socket_poll(h, 0, 101, &r) == EINVAL && r == 0);
    assert(p2p_lan_socket_poll(h, 2, 0, &r) == EINVAL);
    assert(p2p_lan_socket_poll(h, 0, -1, &r) == EINVAL);
    PASS("bounded-buffers-and-poll-arguments");
    uint16_t port = 42;
    memset(bytes, 42, sizeof(bytes));
    assert(p2p_lan_socket_endpoint(h, 2, bytes, &port) == EINVAL && port == 0);
    assert(memcmp(bytes, (uint8_t[4]){0}, 4) == 0);
    OK(p2p_lan_socket_close(h));
    assert(p2p_lan_socket_close(h) == EBADF);
    assert(p2p_lan_socket_bound_interface(h, &index) == EBADF);
    PASS("close-rejects-stale-handle-without-second-release");
}

static void check_live_descriptor_flags(void) {
    struct rlimit limit;
    assert(getrlimit(RLIMIT_NOFILE, &limit) == 0);
    unsigned int matched = 0;
    for (rlim_t fd = 0; fd < limit.rlim_cur; ++fd) {
        int descriptor_flags = fcntl((int)fd, F_GETFD);
        if (descriptor_flags < 0) continue;
        unsigned int index = 0;
        socklen_t size = sizeof(index);
        if (getsockopt((int)fd, IPPROTO_IP, IP_BOUND_IF, &index, &size) < 0 || index != lo) continue;
        assert(size == sizeof(index));
        assert((descriptor_flags & FD_CLOEXEC) != 0);
        int status = fcntl((int)fd, F_GETFL);
        assert(status >= 0 && (status & O_NONBLOCK) != 0);
        int suppressed = 0;
        size = sizeof(suppressed);
        assert(getsockopt((int)fd, SOL_SOCKET, SO_NOSIGPIPE, &suppressed, &size) == 0);
        assert(size == sizeof(suppressed) && suppressed == 1);
        ++matched;
    }
    assert(matched == 3);
    PASS("independent-fd-flags-and-per-socket-sigpipe-readback");
}

static void exchange(void) {
    pair p = connected_pair();
    uint64_t handles[3] = {p.listener, p.outgoing, p.incoming};
    for (unsigned int i = 0; i < 3; ++i) {
        uint32_t actual = 0;
        OK(p2p_lan_socket_bound_interface(handles[i], &actual));
        assert(actual == lo);
    }
    PASS("kernel-readback-listener-outgoing-and-inherited-child-scope");
    check_live_descriptor_flags();
    uint8_t address[4];
    uint16_t local = 0, remote = 0;
    OK(p2p_lan_socket_endpoint(p.outgoing, 0, address, &local));
    assert(memcmp(address, loopback, 4) == 0 && local != 0);
    OK(p2p_lan_socket_endpoint(p.incoming, 1, address, &remote));
    assert(memcmp(address, loopback, 4) == 0 && remote == local);
    OK(p2p_lan_socket_endpoint(p.outgoing, 1, address, &remote));
    assert(memcmp(address, loopback, 4) == 0 && remote == p.port);
    PASS("numeric-endpoint-pair-correlation");
    OK(p2p_lan_socket_option(p.outgoing, 2, 1));
    OK(p2p_lan_socket_option(p.incoming, 2, 1));
    uint8_t bytes[64] = {0};
    uint32_t count = 42;
    assert(p2p_lan_socket_read(p.incoming, bytes, sizeof(bytes), &count) == EAGAIN && count == 0);
    int32_t r = 42;
    int64_t start = nanos();
    OK(p2p_lan_socket_poll(p.incoming, 0, 20, &r));
    assert(r == 0 && nanos() - start < INT64_C(1000000000));
    PASS("nonblocking-read-and-bounded-idle-poll");
    const uint8_t message[] = "isolated native socket fixture, not RPC";
    OK(p2p_lan_socket_write(p.outgoing, message, sizeof(message), &count));
    assert(count == sizeof(message));
    ready(p.incoming, 0);
    OK(p2p_lan_socket_read(p.incoming, bytes, sizeof(bytes), &count));
    assert(count == sizeof(message) && memcmp(bytes, message, count) == 0);
    OK(p2p_lan_socket_write(p.incoming, bytes, count, &count));
    ready(p.outgoing, 0);
    memset(bytes, 0, sizeof(bytes));
    OK(p2p_lan_socket_read(p.outgoing, bytes, sizeof(bytes), &count));
    assert(count == sizeof(message) && memcmp(bytes, message, count) == 0);
    PASS("bidirectional-byte-exact-loopback-transfer");
    OK(p2p_lan_socket_close(p.incoming));
    ready(p.outgoing, 0);
    OK(p2p_lan_socket_read(p.outgoing, bytes, sizeof(bytes), &count));
    assert(count == 0);
    PASS("peer-close-is-eof-not-retry");
    /* A reset/closed-peer write must be an errno, not process-wide SIGPIPE. */
    int64_t deadline = nanos() + INT64_C(2000000000);
    int32_t error;
    do {
        error = p2p_lan_socket_write(p.outgoing, message, sizeof(message), &count);
        assert(nanos() < deadline);
    } while (error == 0 || error == EAGAIN || error == EINTR);
    assert(error == EPIPE || error == ECONNRESET);
    PASS("closed-peer-write-does-not-terminate-process-with-sigpipe");
    OK(p2p_lan_socket_close(p.outgoing));
    OK(p2p_lan_socket_close(p.listener));
    uint64_t replacement = 0;
    OK(p2p_lan_socket_open(lo, &replacement));
    OK(p2p_lan_socket_option(replacement, 1, 1));
    OK(p2p_lan_socket_bind(replacement, loopback, p.port));
    OK(p2p_lan_socket_close(replacement));
    PASS("listener-port-released-after-close");
}

typedef struct { uint64_t handle; atomic_bool completed; int32_t result; } socket_job;
static void *poll_until_closed(void *opaque) {
    socket_job *job = opaque;
    int32_t r;
    do { job->result = p2p_lan_socket_poll(job->handle, 0, 100, &r); } while (job->result == 0);
    atomic_store(&job->completed, true);
    return NULL;
}
static void *close_owned(void *opaque) {
    socket_job *job = opaque;
    job->result = p2p_lan_socket_close(job->handle);
    atomic_store(&job->completed, true);
    return NULL;
}

typedef struct { uint64_t wake, handle; int32_t result, ready; } batch_job;
static void *poll_batch(void *opaque) {
    batch_job *job = opaque;
    int32_t operation = 1;
    job->result = p2p_lan_socket_poll_many(job->wake, &job->handle, &operation, 1, &job->ready);
    return NULL;
}

static void batch_close_lifecycle(void) {
    pair p = connected_pair();
    uint64_t wake[2];
    OK(p2p_lan_socket_wake_open(wake));
    batch_job batch = {.wake = wake[0], .handle = p.incoming};
    socket_job closing = {.handle = p.incoming};
    pthread_t worker, closer;
    pthread_mutex_lock(&poll_barrier);
    pause_poll = true; poll_leased = false;
    assert(pthread_create(&worker, NULL, poll_batch, &batch) == 0);
    while (!poll_leased) pthread_cond_wait(&poll_changed, &poll_barrier);
    pthread_mutex_unlock(&poll_barrier);
    assert(pthread_create(&closer, NULL, close_owned, &closing) == 0);
    uint32_t index;
    int64_t deadline = nanos() + INT64_C(1000000000);
    int32_t gate;
    do {
        gate = p2p_lan_socket_bound_interface(p.incoming, &index);
        assert(gate == 0 || gate == EBADF);
        assert(nanos() < deadline);
    } while (gate == 0);
    assert(!atomic_load(&closing.completed));
    OK(p2p_lan_socket_wake(wake[1]));
    pthread_mutex_lock(&poll_barrier);
    pause_poll = false;
    pthread_cond_broadcast(&poll_changed);
    pthread_mutex_unlock(&poll_barrier);
    assert(pthread_join(worker, NULL) == 0 && pthread_join(closer, NULL) == 0);
    assert(batch.result == 0 && batch.ready == 0 && closing.result == 0);
    assert(nanos() < deadline);
    OK(p2p_lan_socket_close(p.outgoing));
    OK(p2p_lan_socket_close(p.listener));
    OK(p2p_lan_socket_close(wake[1]));
    OK(p2p_lan_socket_close(wake[0]));
    PASS("batch-close-drains-original-lease-and-sticky-wake-without-fd-reuse");
}

static void lifecycle(void) {
    pair p = connected_pair();
    socket_job poll_job = {.handle = p.incoming};
    socket_job close_job = {.handle = p.incoming};
    pthread_t worker, closer;
    pthread_mutex_lock(&poll_barrier);
    pause_poll = true;
    poll_leased = false;
    assert(pthread_create(&worker, NULL, poll_until_closed, &poll_job) == 0);
    while (!poll_leased) pthread_cond_wait(&poll_changed, &poll_barrier);
    pthread_mutex_unlock(&poll_barrier);
    /* The test-only barrier proves a live descriptor lease, not merely a scheduled thread. */
    assert(pthread_create(&closer, NULL, close_owned, &close_job) == 0);
    int64_t start = nanos();
    uint32_t index;
    int32_t gate;
    do {
        gate = p2p_lan_socket_bound_interface(p.incoming, &index);
        assert(gate == 0 || gate == EBADF);
        assert(nanos() - start < INT64_C(1000000000));
    } while (gate == 0);
    assert(!atomic_load(&close_job.completed));
    pthread_mutex_lock(&poll_barrier);
    pause_poll = false;
    pthread_cond_broadcast(&poll_changed);
    pthread_mutex_unlock(&poll_barrier);
    assert(pthread_join(worker, NULL) == 0 && pthread_join(closer, NULL) == 0);
    assert(poll_job.result == EBADF && close_job.result == 0);
    assert(nanos() - start < INT64_C(1000000000));
    OK(p2p_lan_socket_close(p.outgoing));
    OK(p2p_lan_socket_close(p.listener));
    PASS("concurrent-close-gates-poll-and-drains-proven-live-lease");
    uint64_t stale = 0;
    OK(p2p_lan_socket_open(lo, &stale));
    OK(p2p_lan_socket_close(stale));
    for (unsigned int i = 0; i < 128; ++i) {
        uint64_t current = 0;
        OK(p2p_lan_socket_open(lo, &current));
        assert(current != stale);
        assert(p2p_lan_socket_close(stale) == EBADF);
        uint32_t index = 0;
        OK(p2p_lan_socket_bound_interface(current, &index));
        assert(index == lo);
        OK(p2p_lan_socket_close(current));
    }
    PASS("generation-token-prevents-recycled-descriptor-close");
    for (unsigned int i = 0; i < 32; ++i) close_pair(connected_pair());
    PASS("repeated-connect-accept-close-lifecycle");
}

static void failures(void) {
    unsigned int before = descriptors();
    uint64_t failed = 0;
    atomic_store(&configure_error, EIO);
    assert(p2p_lan_socket_open(lo, &failed) == EIO && failed != 0);
    OK(p2p_lan_socket_close(failed));
    assert(descriptors() == before);
    PASS("failed-open-configuration-retains-closeable-ownership");
    pair p = connected_pair();
    OK(p2p_lan_socket_close(p.incoming));
    OK(p2p_lan_socket_close(p.outgoing));
    OK(p2p_lan_socket_open(lo, &p.outgoing));
    OK(p2p_lan_socket_bind(p.outgoing, loopback, 0));
    int32_t rc = p2p_lan_socket_connect(p.outgoing, loopback, p.port);
    assert(rc == 0 || rc == EINPROGRESS);
    ready(p.outgoing, 1);
    OK(p2p_lan_socket_connected(p.outgoing));
    ready(p.listener, 0);
    atomic_store(&configure_error, EIO);
    failed = 0;
    assert(p2p_lan_socket_accept(p.listener, &failed) == EIO && failed != 0);
    OK(p2p_lan_socket_close(failed));
    OK(p2p_lan_socket_close(p.outgoing));
    /* No pending connection: empty reservation must be retired without leaking a handle. */
    for (unsigned int i = 0; i < P2P_LAN_SOCKET_MAX_HANDLES + 1; ++i) {
        assert(p2p_lan_socket_accept(p.listener, &failed) == EAGAIN && failed == 0);
    }
    OK(p2p_lan_socket_close(p.listener));
    assert(descriptors() == before);
    PASS("failed-child-configuration-and-idle-accept-retain-no-unowned-resource");
    uint64_t handles[P2P_LAN_SOCKET_MAX_HANDLES] = {0};
    for (unsigned int i = 0; i < P2P_LAN_SOCKET_MAX_HANDLES; ++i) OK(p2p_lan_socket_open(lo, &handles[i]));
    failed = 42;
    assert(p2p_lan_socket_open(lo, &failed) == EMFILE && failed == 0);
    for (unsigned int i = 0; i < P2P_LAN_SOCKET_MAX_HANDLES; ++i) OK(p2p_lan_socket_close(handles[i]));
    assert(descriptors() == before);
    PASS("bounded-registry-exhaustion-and-recovery-without-descriptor-leak");
}

static void batched_readiness(void) {
    unsigned int before = descriptors();
    uint64_t wake[2] = {0};
    OK(p2p_lan_socket_wake_open(wake));
    assert(wake[0] != 0 && wake[1] != 0 && wake[0] != wake[1]);
    uint64_t tokens[256] = {0};
    int32_t ops[256] = {0}, events[256] = {0};
    assert(p2p_lan_socket_poll_many(wake[0], tokens, ops, 257 + P2P_LAN_SOCKET_MAX_HANDLES, events) == EINVAL);
    OK(p2p_lan_socket_wake(wake[1]));
    int64_t start = nanos();
    OK(p2p_lan_socket_poll_many(wake[0], tokens, ops, 0, events));
    assert(nanos() - start < INT64_C(500000000));
    PASS("batched-sticky-wake-without-socket-or-per-client-timer");
    pair peers[256];
    for (unsigned int i = 0; i < 256; ++i) {
        peers[i] = connected_pair();
        tokens[i] = peers[i].incoming;
        ops[i] = 1;
        uint8_t byte = (uint8_t)i;
        uint32_t sent = 0;
        OK(p2p_lan_socket_write(peers[i].outgoing, &byte, 1, &sent));
        assert(sent == 1);
    }
    unsigned int received = 0;
    bool done[256] = {false};
    int64_t deadline = nanos() + INT64_C(2000000000);
    while (received != 256) {
        assert(nanos() < deadline);
        OK(p2p_lan_socket_poll_many(wake[0], tokens, ops, 256, events));
        for (unsigned int i = 0; i < 256; ++i) if (!done[i] && (events[i] & 1)) {
            uint8_t byte = 0;
            uint32_t count = 0;
            OK(p2p_lan_socket_read(tokens[i], &byte, 1, &count));
            assert(count == 1 && byte == (uint8_t)i);
            done[i] = true; ++received;
        }
    }
    PASS("one-batch-256-original-scoped-sockets-delivers-every-byte");
    uint64_t stale = tokens[0];
    OK(p2p_lan_socket_close(stale));
    tokens[1] = UINT64_MAX;
    OK(p2p_lan_socket_poll_many(wake[0], tokens, ops, 2, events));
    assert(events[0] == 1 && events[1] == 1);
    assert(p2p_lan_socket_close(stale) == EBADF);
    // Real children remain owned even when a stale-token waiter is present in another batch.
    OK(p2p_lan_socket_close(peers[0].outgoing));
    OK(p2p_lan_socket_close(peers[0].listener));
    for (unsigned int i = 1; i < 256; ++i) close_pair(peers[i]);
    OK(p2p_lan_socket_close(wake[1]));
    OK(p2p_lan_socket_close(wake[0]));
    assert(p2p_lan_socket_wake(wake[1]) == EBADF);
    assert(descriptors() == before);
    PASS("batch-stale-token-refusal-and-all-socket-wake-descriptors-retired");
    atomic_store(&configure_error, EIO);
    assert(p2p_lan_socket_wake_open(wake) == EIO && wake[0] != 0 && wake[1] != 0);
    OK(p2p_lan_socket_close(wake[1]));
    OK(p2p_lan_socket_close(wake[0]));
    assert(descriptors() == before);
    PASS("failed-wake-pair-setup-preserves-both-closeable-owners");
}

int main(void) {
    /* Python/shell supervisors may inherit SIG_IGN. Establish SIG_DFL in THIS test process before
     * any library operation, so a missing per-socket SO_NOSIGPIPE really terminates the test.
     * Production must not change this disposition; verify it again after the complete contract. */
    struct sigaction original_signal, action = {0};
    assert(sigaction(SIGPIPE, NULL, &original_signal) == 0);
    action.sa_handler = SIG_DFL;
    assert(sigemptyset(&action.sa_mask) == 0);
    assert(sigaction(SIGPIPE, &action, NULL) == 0);
    assert(sigaction(SIGPIPE, NULL, &action) == 0 && action.sa_handler == SIG_DFL);
    alarm(20);
    // Test-process-only budget: 256 pairs currently include a separate listener each.
    // Raising a finite soft limit here neither changes product defaults nor leaks host settings.
    struct rlimit original, capacity;
    assert(getrlimit(RLIMIT_NOFILE, &original) == 0);
    capacity = original;
    if (capacity.rlim_cur < 1024) {
        assert(capacity.rlim_max >= 1024);
        capacity.rlim_cur = 1024;
        assert(setrlimit(RLIMIT_NOFILE, &capacity) == 0);
    }
    printf("TEST_NOFILE original=%llu active=%llu\n",
        (unsigned long long)original.rlim_cur, (unsigned long long)capacity.rlim_cur);
    lo = if_nametoindex("lo0");
    assert(lo != 0);
    unsigned int before = descriptors();
    inputs();
    exchange();
    lifecycle();
    batch_close_lifecycle();
    failures();
    batched_readiness();
    assert(descriptors() == before);
    PASS("independent-open-descriptor-inventory-restored");
    assert(setrlimit(RLIMIT_NOFILE, &original) == 0);
    assert(sigaction(SIGPIPE, NULL, &action) == 0 && action.sa_handler == SIG_DFL);
    assert(sigaction(SIGPIPE, &original_signal, NULL) == 0);
    alarm(0);
    printf("RESULT: PASS %u native contract groups; loopback only; no JVM/RPC/LAN qualification claimed\n", tests);
    return 0;
}
