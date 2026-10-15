#include "p2pkit_lan_socket.h"

#ifndef __APPLE__
#error "This implementation requires Darwin IP_BOUND_IF and SO_NOSIGPIPE"
#endif

#include <errno.h>
#include <fcntl.h>
#include <limits.h>
#include <net/if.h>
#include <netinet/in.h>
#include <netinet/tcp.h>
#include <poll.h>
#include <pthread.h>
#include <stdbool.h>
#include <string.h>
#include <sys/socket.h>
#include <unistd.h>

typedef struct {
    uint64_t token;
    int fd;
    uint32_t users;
    bool closing;
} owned_socket;

static pthread_mutex_t registry_lock = PTHREAD_MUTEX_INITIALIZER;
static pthread_cond_t registry_changed = PTHREAD_COND_INITIALIZER;
static owned_socket registry[P2P_LAN_SOCKET_MAX_HANDLES];
static uint64_t next_token = 1;

uint32_t p2p_lan_socket_abi(void) { return P2P_LAN_SOCKET_ABI; }

static int32_t own(int fd, uint64_t *handle) {
    int32_t result = EMFILE;
    pthread_mutex_lock(&registry_lock);
    for (uint32_t i = 0; i < P2P_LAN_SOCKET_MAX_HANDLES && next_token != 0; ++i) {
        if (registry[i].token == 0) {
            registry[i] = (owned_socket){ .token = next_token++, .fd = fd };
            *handle = registry[i].token;
            result = 0;
            break;
        }
    }
    pthread_mutex_unlock(&registry_lock);
    return result;
}

static owned_socket *acquire(uint64_t token) {
    owned_socket *found = NULL;
    pthread_mutex_lock(&registry_lock);
    for (uint32_t i = 0; token != 0 && i < P2P_LAN_SOCKET_MAX_HANDLES; ++i) {
        owned_socket *slot = &registry[i];
        if (slot->token == token && !slot->closing && slot->users != UINT32_MAX) {
            slot->users++;
            found = slot;
            break;
        }
    }
    pthread_mutex_unlock(&registry_lock);
    return found;
}

static void release(owned_socket *slot) {
    pthread_mutex_lock(&registry_lock);
    slot->users--;
    if (slot->users == 0) pthread_cond_broadcast(&registry_changed);
    pthread_mutex_unlock(&registry_lock);
}

#ifdef P2P_LAN_SOCKET_TESTING
extern int32_t p2p_lan_test_configure_error(void);
extern void p2p_lan_test_poll_leased(void);
#endif

static int32_t configure(int fd) {
#ifdef P2P_LAN_SOCKET_TESTING
    int32_t injected = p2p_lan_test_configure_error();
    if (injected != 0) return injected;
#endif
    int flags = fcntl(fd, F_GETFL);
    if (flags < 0 || fcntl(fd, F_SETFL, flags | O_NONBLOCK) < 0) return errno;
    flags = fcntl(fd, F_GETFD);
    if (flags < 0 || fcntl(fd, F_SETFD, flags | FD_CLOEXEC) < 0) return errno;
    int enabled = 1;
    return setsockopt(fd, SOL_SOCKET, SO_NOSIGPIPE, &enabled, sizeof(enabled)) == 0 ? 0 : errno;
}

static int32_t bound_interface(int fd, uint32_t *index) {
    unsigned int actual = 0;
    socklen_t size = sizeof(actual);
    if (getsockopt(fd, IPPROTO_IP, IP_BOUND_IF, &actual, &size) < 0) return errno;
    if (size != sizeof(actual) || actual == 0) return EPROTO;
    *index = actual;
    return 0;
}

static struct sockaddr_in endpoint(const uint8_t address[4], uint16_t port) {
    struct sockaddr_in value = { .sin_len = sizeof(value), .sin_family = AF_INET, .sin_port = htons(port) };
    memcpy(&value.sin_addr, address, 4);
    return value;
}

int32_t p2p_lan_socket_open(uint32_t interface_index, uint64_t *handle) {
    if (handle == NULL) return EINVAL;
    *handle = 0;
    char name[IF_NAMESIZE];
    if (interface_index == 0 || if_indextoname(interface_index, name) == NULL) return ENXIO;
    /* Reserve registry ownership before creating a descriptor. Exhaustion cannot strand an
     * unregistered descriptor, even when cleanup itself fails. An empty reservation is closeable. */
    int32_t result = own(-1, handle);
    if (result != 0) return result;
    owned_socket *slot = acquire(*handle);
    int fd = socket(AF_INET, SOCK_STREAM, IPPROTO_TCP);
    if (fd < 0) {
        result = errno;
        release(slot);
        return result;
    }
    slot->fd = fd;
    result = configure(fd);
    if (result == 0 && setsockopt(fd, IPPROTO_IP, IP_BOUND_IF, &interface_index, sizeof(interface_index)) < 0) {
        result = errno;
    }
    uint32_t actual = 0;
    if (result == 0) result = bound_interface(fd, &actual);
    if (result == 0 && actual != interface_index) result = EPROTO;
    release(slot);
    return result;
}

int32_t p2p_lan_socket_bind(uint64_t handle, const uint8_t address[4], uint16_t port) {
    if (address == NULL) return EINVAL;
    if (address[0] == 0) return EADDRNOTAVAIL; /* Never a wildcard listener. */
    owned_socket *slot = acquire(handle);
    if (slot == NULL) return EBADF;
    struct sockaddr_in value = endpoint(address, port);
    int32_t result = bind(slot->fd, (struct sockaddr *)&value, sizeof(value)) == 0 ? 0 : errno;
    release(slot);
    return result;
}

static int32_t require_explicit_binding(int fd) {
    struct sockaddr_in value;
    socklen_t size = sizeof(value);
    if (getsockname(fd, (struct sockaddr *)&value, &size) < 0) return errno;
    if (size != sizeof(value) || value.sin_family != AF_INET || value.sin_port == 0 ||
        value.sin_addr.s_addr == INADDR_ANY) return EADDRNOTAVAIL;
    return 0;
}

int32_t p2p_lan_socket_listen(uint64_t handle, int32_t backlog) {
    if (backlog < 1 || backlog > 128) return EINVAL;
    owned_socket *slot = acquire(handle);
    if (slot == NULL) return EBADF;
    int32_t result = require_explicit_binding(slot->fd);
    if (result == 0 && listen(slot->fd, backlog) < 0) result = errno;
    release(slot);
    return result;
}

int32_t p2p_lan_socket_accept(uint64_t listener, uint64_t *child) {
    if (child == NULL) return EINVAL;
    *child = 0;
    owned_socket *slot = acquire(listener);
    if (slot == NULL) return EBADF;
    uint32_t expected = 0;
    int32_t result = bound_interface(slot->fd, &expected);
    if (result == 0) result = own(-1, child);
    if (result != 0) { release(slot); return result; }
    int fd = accept(slot->fd, NULL, NULL);
    if (fd < 0) {
        result = errno;
        /* Empty reservation: there is no OS descriptor to release and no cleanup guess. */
        (void)p2p_lan_socket_close(*child);
        *child = 0;
        release(slot);
        return result;
    }
    owned_socket *accepted = acquire(*child);
    accepted->fd = fd;
    result = configure(fd);
    uint32_t actual = 0;
    if (result == 0) result = bound_interface(fd, &actual);
    /* Verify inherited scope; do NOT repair a child after an unscoped accept. */
    if (result == 0 && actual != expected) result = EPROTO;
    release(accepted);
    release(slot);
    return result;
}

int32_t p2p_lan_socket_connect(uint64_t handle, const uint8_t address[4], uint16_t port) {
    if (address == NULL || port == 0 || address[0] == 0) return EINVAL;
    owned_socket *slot = acquire(handle);
    if (slot == NULL) return EBADF;
    struct sockaddr_in value = endpoint(address, port);
    int32_t result = require_explicit_binding(slot->fd);
    if (result == 0 && connect(slot->fd, (struct sockaddr *)&value, sizeof(value)) < 0) result = errno;
    release(slot);
    return result;
}

int32_t p2p_lan_socket_connected(uint64_t handle) {
    owned_socket *slot = acquire(handle);
    if (slot == NULL) return EBADF;
    int pending = 0;
    socklen_t size = sizeof(pending);
    int32_t result = getsockopt(slot->fd, SOL_SOCKET, SO_ERROR, &pending, &size) == 0 ? pending : errno;
    if (result == 0 && size != sizeof(pending)) result = EPROTO;
    struct sockaddr_in peer;
    size = sizeof(peer);
    if (result == 0 && getpeername(slot->fd, (struct sockaddr *)&peer, &size) < 0) result = errno;
    release(slot);
    return result;
}

int32_t p2p_lan_socket_endpoint(uint64_t handle, int32_t remote, uint8_t address[4], uint16_t *port) {
    if (address == NULL || port == NULL) return EINVAL;
    memset(address, 0, 4);
    *port = 0;
    if (remote != 0 && remote != 1) return EINVAL;
    owned_socket *slot = acquire(handle);
    if (slot == NULL) return EBADF;
    struct sockaddr_in value;
    socklen_t size = sizeof(value);
    int rc = remote ? getpeername(slot->fd, (struct sockaddr *)&value, &size) :
        getsockname(slot->fd, (struct sockaddr *)&value, &size);
    int32_t result = rc == 0 ? 0 : errno;
    if (result == 0 && (size != sizeof(value) || value.sin_family != AF_INET)) result = EPROTO;
    if (result == 0) {
        memcpy(address, &value.sin_addr, 4);
        *port = ntohs(value.sin_port);
    }
    release(slot);
    return result;
}

int32_t p2p_lan_socket_bound_interface(uint64_t handle, uint32_t *interface_index) {
    if (interface_index == NULL) return EINVAL;
    *interface_index = 0;
    owned_socket *slot = acquire(handle);
    if (slot == NULL) return EBADF;
    int32_t result = bound_interface(slot->fd, interface_index);
    release(slot);
    return result;
}

int32_t p2p_lan_socket_option(uint64_t handle, int32_t option, int32_t enabled) {
    if ((option != 1 && option != 2) || (enabled != 0 && enabled != 1)) return EINVAL;
    owned_socket *slot = acquire(handle);
    if (slot == NULL) return EBADF;
    int value = enabled;
    int32_t result = setsockopt(slot->fd, option == 1 ? SOL_SOCKET : IPPROTO_TCP,
        option == 1 ? SO_REUSEADDR : TCP_NODELAY, &value, sizeof(value)) == 0 ? 0 : errno;
    release(slot);
    return result;
}

int32_t p2p_lan_socket_read(uint64_t handle, uint8_t *bytes, uint32_t length, uint32_t *count) {
    if (count == NULL) return EINVAL;
    *count = 0;
    if (bytes == NULL || length == 0 || length > P2P_LAN_SOCKET_MAX_BYTES) return EINVAL;
    owned_socket *slot = acquire(handle);
    if (slot == NULL) return EBADF;
    ssize_t size = recv(slot->fd, bytes, length, 0);
    int32_t result = size >= 0 ? 0 : errno;
    if (size >= 0) *count = (uint32_t)size;
    release(slot);
    return result;
}

int32_t p2p_lan_socket_write(uint64_t handle, const uint8_t *bytes, uint32_t length, uint32_t *count) {
    if (count == NULL) return EINVAL;
    *count = 0;
    if (bytes == NULL || length == 0 || length > P2P_LAN_SOCKET_MAX_BYTES) return EINVAL;
    owned_socket *slot = acquire(handle);
    if (slot == NULL) return EBADF;
    ssize_t size = send(slot->fd, bytes, length, 0); /* SO_NOSIGPIPE is already set on this descriptor. */
    int32_t result = size >= 0 ? 0 : errno;
    if (size >= 0) *count = (uint32_t)size;
    release(slot);
    return result;
}

int32_t p2p_lan_socket_poll(uint64_t handle, int32_t writable, int32_t timeout_ms, int32_t *ready) {
    if (ready == NULL) return EINVAL;
    *ready = 0;
    if ((writable != 0 && writable != 1) || timeout_ms < 0 || timeout_ms > 100) return EINVAL;
    owned_socket *slot = acquire(handle);
    if (slot == NULL) return EBADF;
#ifdef P2P_LAN_SOCKET_TESTING
    p2p_lan_test_poll_leased();
#endif
    struct pollfd row = { .fd = slot->fd, .events = writable ? POLLOUT : POLLIN };
    int rc = poll(&row, 1, timeout_ms);
    int32_t result = rc >= 0 ? 0 : errno;
    if (rc > 0) {
        if (row.revents & POLLNVAL) result = EBADF;
        else if (row.revents & (row.events | POLLERR | POLLHUP)) *ready = 1;
    }
    release(slot);
    return result;
}

int32_t p2p_lan_socket_close(uint64_t handle) {
    pthread_mutex_lock(&registry_lock);
    owned_socket *slot = NULL;
    for (uint32_t i = 0; handle != 0 && i < P2P_LAN_SOCKET_MAX_HANDLES; ++i) {
        if (registry[i].token == handle && !registry[i].closing) { slot = &registry[i]; break; }
    }
    if (slot == NULL) { pthread_mutex_unlock(&registry_lock); return EBADF; }
    slot->closing = true;
    while (slot->users != 0) pthread_cond_wait(&registry_changed, &registry_lock);
    int fd = slot->fd;
    pthread_mutex_unlock(&registry_lock);
    int32_t result = fd < 0 || close(fd) == 0 ? 0 : errno;
    pthread_mutex_lock(&registry_lock);
    if (result == 0) memset(slot, 0, sizeof(*slot));
    /* Failure stays quarantined; never guess whether an interrupted close recycled fd. */
    pthread_mutex_unlock(&registry_lock);
    return result;
}
