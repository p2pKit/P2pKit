#ifndef P2PKIT_NW_H
#define P2PKIT_NW_H

#include <Network/Network.h>
#include <errno.h>
#include <netinet/in.h>
#include <ifaddrs.h>
#include <net/if.h>
#include <stdbool.h>
#include <stdint.h>
#include <string.h>
#include <sys/socket.h>
#include <unistd.h>

/**
 * Build an nw_parameters_t for plain TCP without TLS.
 *
 * Equivalent to Apple's idiomatic call:
 *
 *     nw_parameters_create_secure_tcp(
 *         NW_PARAMETERS_DISABLE_PROTOCOL,
 *         NW_PARAMETERS_DEFAULT_CONFIGURATION
 *     )
 *
 * The two macros expand to global void-returning ObjC block constants
 * (`_nw_parameters_configure_protocol_disable` /
 *  `_nw_parameters_configure_protocol_default_configuration`) which
 * Kotlin/Native's `Kotlin_Interop_refFromObjC` cannot box as `kotlin.Any` —
 * any direct Kotlin read of those globals crashes at startup. Performing the
 * call inline inside this static-inline C function keeps the block constants
 * entirely on the ObjC side; the Kotlin caller only sees the resulting
 * `nw_parameters_t`, which boxes cleanly.
 */
static inline nw_parameters_t p2pkit_nw_create_plain_tcp_parameters(void) {
    return nw_parameters_create_secure_tcp(
        NW_PARAMETERS_DISABLE_PROTOCOL,
        NW_PARAMETERS_DEFAULT_CONFIGURATION
    );
}

/**
 * Borrowed view of one IPv4/IPv6 address returned by getifaddrs(). Every
 * pointer is valid only for the duration of the enumeration callback. Kotlin
 * callers must copy the bytes/name before the callback returns.
 */
typedef struct p2pkit_lan_interface_address {
    const uint8_t *address_bytes;
    uint32_t address_length;
    uint8_t ip_version;
    const char *interface_name;
    uint32_t interface_index;
    uint32_t address_scope_id;
    bool interface_is_up;
    bool interface_is_running;
    bool interface_is_loopback;
    bool interface_is_point_to_point;
    bool interface_supports_multicast;
    bool address_is_interface_broadcast;
} p2pkit_lan_interface_address_t;

/**
 * Synchronously enumerate a borrowed snapshot of Apple interface addresses.
 *
 * This helper deliberately performs no product-policy filtering beyond the
 * address family: the Kotlin caller owns the LAN-interface and unicast rules
 * and tests them deterministically. The callback is synchronous, and the
 * getifaddrs list is always released before this function returns.
 *
 * Returns 0 on success or an errno value when enumeration cannot start.
 */
static inline int p2pkit_lan_enumerate_interface_addresses(
    void (^handler)(const p2pkit_lan_interface_address_t *candidate)
) {
    if (handler == NULL) return EINVAL;

    struct ifaddrs *interfaces = NULL;
    if (getifaddrs(&interfaces) != 0) {
        int enumeration_errno = errno;
        return enumeration_errno != 0 ? enumeration_errno : EIO;
    }
    if (interfaces == NULL) return EIO;

    for (struct ifaddrs *entry = interfaces; entry != NULL; entry = entry->ifa_next) {
        if (entry->ifa_addr == NULL || entry->ifa_name == NULL) continue;

        const uint8_t *bytes = NULL;
        uint32_t length = 0;
        uint8_t version = 0;
        uint32_t scope_id = 0;
        bool is_interface_broadcast = false;
        sa_family_t family = entry->ifa_addr->sa_family;
        if (family == AF_INET) {
            if (entry->ifa_addr->sa_len < sizeof(struct sockaddr_in)) continue;
            const struct sockaddr_in *address =
                (const struct sockaddr_in *)entry->ifa_addr;
            bytes = (const uint8_t *)&address->sin_addr;
            length = (uint32_t)sizeof(struct in_addr);
            version = 4;

            if ((entry->ifa_flags & IFF_BROADCAST) != 0 &&
                entry->ifa_broadaddr != NULL &&
                entry->ifa_broadaddr->sa_family == AF_INET &&
                entry->ifa_broadaddr->sa_len >= sizeof(struct sockaddr_in)) {
                const struct sockaddr_in *broadcast =
                    (const struct sockaddr_in *)entry->ifa_broadaddr;
                is_interface_broadcast =
                    memcmp(&address->sin_addr, &broadcast->sin_addr, sizeof(struct in_addr)) == 0;
            }
        } else if (family == AF_INET6) {
            if (entry->ifa_addr->sa_len < sizeof(struct sockaddr_in6)) continue;
            const struct sockaddr_in6 *address =
                (const struct sockaddr_in6 *)entry->ifa_addr;
            bytes = (const uint8_t *)&address->sin6_addr;
            length = (uint32_t)sizeof(struct in6_addr);
            version = 6;
            scope_id = address->sin6_scope_id;
        } else {
            continue;
        }

        p2pkit_lan_interface_address_t candidate = {
            .address_bytes = bytes,
            .address_length = length,
            .ip_version = version,
            .interface_name = entry->ifa_name,
            .interface_index = if_nametoindex(entry->ifa_name),
            .address_scope_id = scope_id,
            .interface_is_up = (entry->ifa_flags & IFF_UP) != 0,
            .interface_is_running = (entry->ifa_flags & IFF_RUNNING) != 0,
            .interface_is_loopback = (entry->ifa_flags & IFF_LOOPBACK) != 0,
            .interface_is_point_to_point = (entry->ifa_flags & IFF_POINTOPOINT) != 0,
            .interface_supports_multicast = (entry->ifa_flags & IFF_MULTICAST) != 0,
            .address_is_interface_broadcast = is_interface_broadcast,
        };
        handler(&candidate);
    }

    freeifaddrs(interfaces);
    return 0;
}

/**
 * Order-independent fingerprint of live, non-loopback IPv4/IPv6 interface
 * addresses. NWPath exposes interface *types* but not a stable signal for a
 * Wi-Fi-to-Wi-Fi DHCP/address rotation; this fills that gap for rebind logic.
 */
static inline uint64_t p2pkit_lan_interface_fingerprint(void) {
    struct ifaddrs *interfaces = NULL;
    if (getifaddrs(&interfaces) != 0 || interfaces == NULL) return 0;

    uint64_t combined = 1469598103934665603ULL;
    uint64_t count = 0;
    for (struct ifaddrs *entry = interfaces; entry != NULL; entry = entry->ifa_next) {
        if (entry->ifa_addr == NULL || entry->ifa_name == NULL) continue;
        if ((entry->ifa_flags & IFF_UP) == 0 || (entry->ifa_flags & IFF_LOOPBACK) != 0) continue;

        const uint8_t *bytes = NULL;
        size_t length = 0;
        sa_family_t family = entry->ifa_addr->sa_family;
        if (family == AF_INET) {
            bytes = (const uint8_t *)&((const struct sockaddr_in *)entry->ifa_addr)->sin_addr;
            length = sizeof(struct in_addr);
        } else if (family == AF_INET6) {
            bytes = (const uint8_t *)&((const struct sockaddr_in6 *)entry->ifa_addr)->sin6_addr;
            length = sizeof(struct in6_addr);
        } else {
            continue;
        }

        uint64_t item = 1469598103934665603ULL;
        for (const unsigned char *name = (const unsigned char *)entry->ifa_name; *name; ++name) {
            item = (item ^ *name) * 1099511628211ULL;
        }
        item = (item ^ (uint8_t)family) * 1099511628211ULL;
        for (size_t index = 0; index < length; ++index) {
            item = (item ^ bytes[index]) * 1099511628211ULL;
        }
        combined ^= item;
        count++;
    }
    freeifaddrs(interfaces);
    return combined ^ (count * 0x9e3779b97f4a7c15ULL);
}

/**
 * Test seam for proving that an NWListener's exact native port descriptor has
 * been released. Network.framework's `nw_listener_create_with_port` reports
 * EINVAL on the iOS simulator for otherwise valid numeric ports, so it cannot
 * distinguish an occupied port from an unsupported probe. A direct BSD bind
 * gives the required ownership signal and closes the probe descriptor before
 * returning. This static-inline helper is used only by appleTest.
 *
 * Returns 0 on a successful bind, otherwise the errno from bind/socket.
 */
static inline int p2pkit_test_bind_tcp_port(uint16_t port, bool ipv6) {
    int family = ipv6 ? AF_INET6 : AF_INET;
    int fd = socket(family, SOCK_STREAM, 0);
    if (fd < 0) return errno;

    int result;
    if (ipv6) {
        struct sockaddr_in6 address = {0};
        address.sin6_family = AF_INET6;
        address.sin6_port = htons(port);
        address.sin6_addr = in6addr_any;
        result = bind(fd, (const struct sockaddr *)&address, sizeof(address));
    } else {
        struct sockaddr_in address = {0};
        address.sin_family = AF_INET;
        address.sin_port = htons(port);
        address.sin_addr.s_addr = htonl(INADDR_ANY);
        result = bind(fd, (const struct sockaddr *)&address, sizeof(address));
    }

    int bind_errno = result == 0 ? 0 : errno;
    close(fd);
    return bind_errno;
}

/**
 * Send the given byte buffer over an established connection using the
 * default-message context. Performs the dispatch_data_create + nw_connection_send
 * pair entirely on the ObjC side.
 *
 * Wraps these C calls so Kotlin/Native never has to box `dispatch_data_t` or
 * `nw_content_context_t` values that originate as void-returning block sentinels
 * (`NW_CONNECTION_DEFAULT_MESSAGE_CONTEXT`); from the Kotlin caller's view it's
 * just `(connection, buffer, size, completion)`. `completion` is the ordinary
 * Kotlin-lambda → ObjC-block direction, which Kotlin/Native handles correctly.
 *
 * `buffer` must remain valid until this function returns: dispatch_data_create
 * is called with a NULL destructor, which copies the bytes synchronously.
 */
static inline void p2pkit_nw_connection_send_default(
    nw_connection_t connection,
    const void *buffer,
    size_t size,
    bool is_complete,
    void (^completion)(nw_error_t error)
) {
    dispatch_data_t data = dispatch_data_create(buffer, size, NULL, NULL);
    nw_connection_send(connection, data, NW_CONNECTION_DEFAULT_MESSAGE_CONTEXT, is_complete, completion);
}

/**
 * Read up to `max_length` bytes from the connection and deliver them via a
 * byte-buffer completion. Wraps `nw_connection_receive` so Kotlin never has
 * to handle `dispatch_data_t` directly. The C side calls
 * `dispatch_data_create_map` on the received data and hands a contiguous
 * pointer + length to the completion block, which is the typical
 * Kotlin-lambda → ObjC-block direction.
 *
 * The buffer is valid only for the duration of the completion call.
 */
static inline void p2pkit_nw_connection_receive_default(
    nw_connection_t connection,
    uint32_t min_incomplete_length,
    uint32_t max_length,
    void (^completion)(const void *buffer, size_t size, bool is_complete, nw_error_t error)
) {
    nw_connection_receive(
        connection,
        min_incomplete_length,
        max_length,
        ^(dispatch_data_t content, nw_content_context_t context, bool is_complete, nw_error_t error) {
            (void)context;
            if (content != NULL && dispatch_data_get_size(content) > 0) {
                const void *buffer = NULL;
                size_t buffer_size = 0;
                /* objc_precise_lifetime: under ARC a plain local has imprecise
                 * lifetime and `(void)mapped` is a dead use, so the mapping
                 * (sole owner of `buffer`) could be released BEFORE the
                 * completion reads it — a latent use-after-free. The attribute
                 * is the sanctioned way to pin it for the full scope
                 * (AUDIT-2026-06 fix). */
                __attribute__((objc_precise_lifetime))
                dispatch_data_t mapped = dispatch_data_create_map(content, &buffer, &buffer_size);
                completion(buffer, buffer_size, is_complete, error);
                (void)mapped;
            } else {
                completion(NULL, 0, is_complete, error);
            }
        }
    );
}

#endif /* P2PKIT_NW_H */
