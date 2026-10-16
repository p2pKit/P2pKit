#include "p2pkit_bonjour.h"
#include <dns_sd.h>
#include <errno.h>
#include <fcntl.h>
#include <limits.h>
#include <net/if.h>
#include <netinet/in.h>
#include <poll.h>
#include <pthread.h>
#include <stdbool.h>
#include <stdlib.h>
#include <string.h>

/* Slots have stable addresses. A token is never reused, including after a failed open. */
typedef struct {
    uint64_t token;
    bool busy;
    bool closing;
    DNSServiceRef ref;
    uint32_t index;
    const char *type;
    char name[P2P_BONJOUR_NAME + 1];
    uint8_t (*queue)[P2P_BONJOUR_FRAME];
    uint32_t head;
    uint32_t count;
    int32_t terminal;
} owned_bonjour;
static owned_bonjour registry[P2P_BONJOUR_HANDLES];
static pthread_mutex_t gate = PTHREAD_MUTEX_INITIALIZER;
static pthread_cond_t changed = PTHREAD_COND_INITIALIZER;
static uint64_t next_token = 1;

uint32_t p2p_bonjour_abi(void) { return P2P_BONJOUR_ABI; }
static void put32(uint8_t *out, uint32_t value) {
    out[0] = (uint8_t)(value >> 24); out[1] = (uint8_t)(value >> 16);
    out[2] = (uint8_t)(value >> 8); out[3] = (uint8_t)value;
}
static size_t safe_name(const char *name) {
    if (name == NULL) return 0;
    size_t size = strnlen(name, P2P_BONJOUR_NAME + 1);
    if (size == 0 || size > P2P_BONJOUR_NAME) return 0;
    for (size_t i = 0; i < size; ++i) if ((uint8_t)name[i] < 32 || (uint8_t)name[i] == 127) return 0;
    return size;
}
static void enqueue(owned_bonjour *slot, uint32_t kind, const char *name,
    uint16_t port, const void *txt, uint16_t length) {
    if (slot->terminal != 0) return;
    size_t namesize = safe_name(name);
    if (namesize == 0 || length > P2P_BONJOUR_TXT || (length != 0 && txt == NULL)) {
        slot->terminal = EPROTO; return;
    }
    if (slot->count == P2P_BONJOUR_QUEUE) { slot->terminal = ENOBUFS; return; }
    uint8_t *frame = slot->queue[(slot->head + slot->count++) % P2P_BONJOUR_QUEUE];
    memset(frame, 0, P2P_BONJOUR_FRAME);
    put32(frame, kind); put32(frame + 8, slot->index); put32(frame + 12, port);
    put32(frame + 16, (uint32_t)namesize); put32(frame + 20, length);
    memcpy(frame + 24, name, namesize);
    if (length != 0) memcpy(frame + 24 + namesize, txt, length);
}
static void DNSSD_API browse_reply(DNSServiceRef ref, DNSServiceFlags flags, uint32_t index,
    DNSServiceErrorType error, const char *name, const char *type, const char *domain, void *context) {
    (void)ref; owned_bonjour *slot = context;
    if (error != 0) { slot->terminal = error; return; }
    if (index != slot->index || type == NULL || domain == NULL ||
        strcmp(type, slot->type) != 0 || strcmp(domain, "local.") != 0) {
        slot->terminal = EPROTO; return;
    }
    enqueue(slot, (flags & kDNSServiceFlagsAdd) ? 1u : 2u, name, 0, NULL, 0);
}
static void DNSSD_API register_reply(DNSServiceRef ref, DNSServiceFlags flags, DNSServiceErrorType error,
    const char *name, const char *type, const char *domain, void *context) {
    (void)ref; (void)flags; owned_bonjour *slot = context;
    if (error != 0) { slot->terminal = error; return; }
    if (name == NULL || type == NULL || domain == NULL || strcmp(name, slot->name) != 0 ||
        strcmp(type, slot->type) != 0 || strcmp(domain, "local.") != 0) {
        slot->terminal = EPROTO; return;
    }
    /* RegisterReply does not report an interface. Its scope is the explicit index passed to Register,
     * not a fabricated callback readback or evidence of off-host delivery. */
    enqueue(slot, 4, name, 0, NULL, 0);
}
static void DNSSD_API resolve_reply(DNSServiceRef ref, DNSServiceFlags flags, uint32_t index,
    DNSServiceErrorType error, const char *fullname, const char *host, uint16_t port,
    uint16_t length, const unsigned char *txt, void *context) {
    (void)ref; (void)flags; (void)host; owned_bonjour *slot = context;
    if (error != 0) { slot->terminal = error; return; }
    char expected[kDNSServiceMaxDomainName];
    if (index != slot->index || fullname == NULL ||
        DNSServiceConstructFullName(expected, slot->name, slot->type, "local.") != 0 ||
        strcmp(expected, fullname) != 0 || port == 0) { slot->terminal = EPROTO; return; }
    /* Never resolve hostTarget through unicast/default DNS. The shared strict TXT parser owns numeric hints. */
    enqueue(slot, 3, slot->name, ntohs(port), txt, length);
}
static owned_bonjour *lease(uint64_t token, int32_t *error) {
    owned_bonjour *result = NULL; *error = EBADF;
    pthread_mutex_lock(&gate);
    for (uint32_t i = 0; token != 0 && i < P2P_BONJOUR_HANDLES; ++i) {
        owned_bonjour *slot = &registry[i];
        if (slot->token != token || slot->closing) continue;
        if (slot->busy) *error = EBUSY;
        else { slot->busy = true; result = slot; *error = 0; }
        break;
    }
    pthread_mutex_unlock(&gate);
    return result;
}
static void release(owned_bonjour *slot) {
    pthread_mutex_lock(&gate); slot->busy = false; pthread_cond_broadcast(&changed); pthread_mutex_unlock(&gate);
}
int32_t p2p_bonjour_open(uint32_t index, int32_t operation, int32_t profile,
    const char *name, uint16_t port, const uint8_t *txt, uint32_t length, uint64_t *output) {
    if (output == NULL) return EINVAL;
    *output = 0;
    char interface_name[IF_NAMESIZE];
    if (index == 0 || if_indextoname(index, interface_name) == NULL) return ENXIO;
    if (name == NULL || operation < 1 || operation > 3 || (profile != 1 && profile != 2) ||
        length > P2P_BONJOUR_TXT || (length != 0 && txt == NULL)) return EINVAL;
    if (operation == 1 ? name[0] != '\0' : safe_name(name) == 0) return EINVAL;
    if (operation == 2 ? port == 0 : (port != 0 || length != 0)) return EINVAL;
    owned_bonjour *slot = NULL;
    pthread_mutex_lock(&gate);
    for (uint32_t i = 0; next_token != 0 && i < P2P_BONJOUR_HANDLES; ++i) {
        if (registry[i].token == 0) {
            slot = &registry[i];
            *slot = (owned_bonjour){ .token = next_token++, .busy = true, .index = index,
                .type = profile == 1 ? "_p2pkit._tcp." : "_p2pkit2._tcp." };
            *output = slot->token; break;
        }
    }
    pthread_mutex_unlock(&gate);
    if (slot == NULL) return EMFILE;
    memcpy(slot->name, name, strlen(name) + 1);
    slot->queue = calloc(P2P_BONJOUR_QUEUE, P2P_BONJOUR_FRAME);
    int32_t error = ENOMEM;
    if (slot->queue != NULL) {
        if (operation == 1) error = DNSServiceBrowse(&slot->ref, 0, index, slot->type, "local.", browse_reply, slot);
        else if (operation == 2) error = DNSServiceRegister(&slot->ref, kDNSServiceFlagsNoAutoRename,
            index, name, slot->type, "local.", NULL, htons(port), (uint16_t)length, txt, register_reply, slot);
        else error = DNSServiceResolve(&slot->ref, 0, index, name, slot->type, "local.", resolve_reply, slot);
    }
    if (error == 0) {
        int fd = DNSServiceRefSockFD(slot->ref);
        int flags = fd < 0 ? -1 : fcntl(fd, F_GETFD);
        if (flags < 0 || fcntl(fd, F_SETFD, flags | FD_CLOEXEC) < 0) error = fd < 0 ? EBADF : errno;
    }
    release(slot);
    return error;
}
int32_t p2p_bonjour_poll(uint64_t handle, int32_t timeout_ms, uint8_t output[P2P_BONJOUR_FRAME]) {
    if (output == NULL) return -EINVAL;
    memset(output, 0, P2P_BONJOUR_FRAME);
    if (timeout_ms < 0 || timeout_ms > 100) return -EINVAL;
    int32_t error = 0;
    owned_bonjour *slot = lease(handle, &error);
    if (slot == NULL) return -error;
    if (slot->ref == NULL) { release(slot); return -EBADF; }
    if (slot->count == 0 && slot->terminal == 0) {
        struct pollfd fd = { .fd = DNSServiceRefSockFD(slot->ref), .events = POLLIN };
        if (fd.fd < 0) slot->terminal = EBADF;
        else {
            int ready = poll(&fd, 1, timeout_ms);
            if (ready < 0 && errno != EINTR) slot->terminal = errno;
            if (ready > 0) {
                if (fd.revents & (POLLERR | POLLHUP | POLLNVAL)) slot->terminal = EIO;
                else if (fd.revents & POLLIN) {
                    DNSServiceErrorType result = DNSServiceProcessResult(slot->ref);
                    if (result != 0) slot->terminal = result;
                }
            }
        }
    }
    int32_t result = 0;
    if (slot->terminal != 0) {
        put32(output, 5); put32(output + 4, (uint32_t)slot->terminal); put32(output + 8, slot->index);
        result = 1; /* Failure supersedes queued callbacks; no stale record escapes overflow. */
    } else if (slot->count != 0) {
        memcpy(output, slot->queue[slot->head], P2P_BONJOUR_FRAME);
        slot->head = (slot->head + 1) % P2P_BONJOUR_QUEUE; slot->count--; result = 1;
    }
    release(slot);
    return result;
}
int32_t p2p_bonjour_close(uint64_t token) {
    pthread_mutex_lock(&gate);
    owned_bonjour *slot = NULL;
    for (uint32_t i = 0; token != 0 && i < P2P_BONJOUR_HANDLES; ++i) {
        if (registry[i].token == token && !registry[i].closing) { slot = &registry[i]; break; }
    }
    if (slot == NULL) { pthread_mutex_unlock(&gate); return EBADF; }
    slot->closing = true;
    while (slot->busy) pthread_cond_wait(&changed, &gate);
    pthread_mutex_unlock(&gate);
    if (slot->ref != NULL) DNSServiceRefDeallocate(slot->ref);
    free(slot->queue);
    pthread_mutex_lock(&gate); memset(slot, 0, sizeof(*slot)); pthread_mutex_unlock(&gate);
    return 0;
}
