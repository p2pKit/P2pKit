#ifndef P2PKIT_NW_H
#define P2PKIT_NW_H

#include <Network/Network.h>
#include <arpa/inet.h>
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
 * Build plain TCP parameters with Nagle disabled for small protocol frames.
 * Authenticated-v2 security remains above the byte transport; disabling
 * transport TLS here never permits an authentication downgrade.
 *
 * NW_PARAMETERS_DISABLE_PROTOCOL expands to a global void-returning ObjC
 * block constant which Kotlin/Native cannot box as kotlin.Any. Keep both
 * protocol configuration blocks entirely on the ObjC side; Kotlin only
 * receives the resulting nw_parameters_t, which boxes cleanly.
 */
static inline nw_parameters_t p2pkit_nw_create_plain_tcp_parameters(void) {
    return nw_parameters_create_secure_tcp(
        NW_PARAMETERS_DISABLE_PROTOCOL,
        ^(nw_protocol_options_t options) {
            nw_tcp_options_set_no_delay(options, true);
        }
    );
}

/* Cinterop may compile this Objective-C header with or without ARC. Created/copied
 * Network objects need an explicit release under MRC, but never a second release
 * under ARC. Do not apply this to borrowed callback arguments or returned objects. */
static inline void p2pkit_nw_release_owned(nw_object_t object) {
#if !__has_feature(objc_arc)
    if (object != NULL) nw_release(object);
#else
    (void)object;
#endif
}

/* Do not delegate the accepted spelling to libc: Darwin and other hosts need
 * not reject the same legacy IPv4 forms. Exactly four decimal octets, no leading
 * zeroes, whitespace, shorthand, DNS or radix aliases are allowed. */
static inline bool p2pkit_lan_parse_ipv4(const char *text, struct in_addr *output) {
    if (text == NULL || output == NULL) return false;
    size_t length = strnlen(text, INET_ADDRSTRLEN);
    if (length == 0 || length >= INET_ADDRSTRLEN) return false;
    const char *cursor = text;
    const char *end = text + length;
    uint8_t bytes[4];
    for (size_t index = 0; index < 4; index++) {
        const char *start = cursor;
        unsigned int value = 0;
        while (cursor < end && *cursor >= '0' && *cursor <= '9') {
            value = value * 10 + (unsigned int)(*cursor++ - '0');
            if (value > 255 || cursor - start > 3) return false;
        }
        if (cursor == start || (cursor - start > 1 && *start == '0')) return false;
        bytes[index] = (uint8_t)value;
        if (index < 3) {
            if (cursor == end || *cursor++ != '.') return false;
        } else if (cursor != end) {
            return false;
        }
    }
    memcpy(output, bytes, sizeof(bytes));
    return true;
}

static inline bool p2pkit_lan_parse_ipv6(const char *text, struct in6_addr *output) {
    if (text == NULL || output == NULL) return false;
    size_t length = strnlen(text, INET6_ADDRSTRLEN);
    if (length == 0 || length >= INET6_ADDRSTRLEN) return false;
    const char *last_colon = NULL;
    bool dotted = false;
    for (size_t index = 0; index < length; index++) {
        char c = text[index];
        if (c == ':') last_colon = &text[index];
        else if (c == '.') dotted = true;
        else if (!((c >= '0' && c <= '9') || (c >= 'a' && c <= 'f') || (c >= 'A' && c <= 'F'))) return false;
    }
    if (last_colon == NULL) return false;
    struct in_addr ipv4;
    if (dotted && !p2pkit_lan_parse_ipv4(last_colon + 1, &ipv4)) return false;
    return inet_pton(AF_INET6, text, output) == 1;
}

/* No DNS: numeric comparison also tolerates equivalent IPv6 spellings. */
static inline bool p2pkit_lan_numeric_equal(const char *left, const char *right) {
    struct in_addr l4, r4;
    if (p2pkit_lan_parse_ipv4(left, &l4) && p2pkit_lan_parse_ipv4(right, &r4)) {
        return l4.s_addr == r4.s_addr;
    }
    struct in6_addr l6, r6;
    return p2pkit_lan_parse_ipv6(left, &l6) && p2pkit_lan_parse_ipv6(right, &r6) &&
        memcmp(&l6, &r6, sizeof(l6)) == 0;
}

/* Effective NWPath endpoints may be sockaddr-backed, not hostname-backed.
 * Normalize only literal IPv4/IPv6 values; never resolve DNS or a Bonjour name.
 * A scoped address is deliberately not stripped into an apparently unscoped one. */
static inline bool p2pkit_lan_endpoint_numeric(nw_endpoint_t endpoint, char *output, size_t capacity) {
    if (endpoint == NULL || output == NULL || capacity < INET6_ADDRSTRLEN) return false;
    nw_endpoint_type_t type = nw_endpoint_get_type(endpoint);
    if (type == nw_endpoint_type_address) {
        const struct sockaddr *address = nw_endpoint_get_address(endpoint);
        if (address == NULL) return false;
        if (address->sa_family == AF_INET && address->sa_len >= sizeof(struct sockaddr_in)) {
            return inet_ntop(AF_INET, &((const struct sockaddr_in *)address)->sin_addr, output, capacity) != NULL;
        }
        if (address->sa_family == AF_INET6 && address->sa_len >= sizeof(struct sockaddr_in6)) {
            const struct sockaddr_in6 *ipv6 = (const struct sockaddr_in6 *)address;
            return ipv6->sin6_scope_id == 0 && inet_ntop(AF_INET6, &ipv6->sin6_addr, output, capacity) != NULL;
        }
        return false;
    }
    if (type != nw_endpoint_type_host) return false;
    const char *host = nw_endpoint_get_hostname(endpoint);
    if (host == NULL) return false;
    struct in_addr ipv4;
    if (p2pkit_lan_parse_ipv4(host, &ipv4)) {
        return inet_ntop(AF_INET, &ipv4, output, capacity) != NULL;
    }
    struct in6_addr ipv6;
    return p2pkit_lan_parse_ipv6(host, &ipv6) && inet_ntop(AF_INET6, &ipv6, output, capacity) != NULL;
}

static inline bool p2pkit_lan_endpoint_numeric_equal(nw_endpoint_t endpoint, const char *expected) {
    char numeric[INET6_ADDRSTRLEN];
    return p2pkit_lan_endpoint_numeric(endpoint, numeric, sizeof(numeric)) &&
        p2pkit_lan_numeric_equal(numeric, expected);
}

static inline bool p2pkit_lan_selected_address_is_live(const char *name, const char *address) {
    if (name == NULL || address == NULL) return false;
    struct ifaddrs *interfaces = NULL;
    if (getifaddrs(&interfaces) != 0 || interfaces == NULL) return false;
    bool found = false;
    for (struct ifaddrs *entry = interfaces; entry != NULL; entry = entry->ifa_next) {
        if (entry->ifa_addr == NULL || entry->ifa_name == NULL || strcmp(name, entry->ifa_name) != 0) continue;
        unsigned int flags = entry->ifa_flags;
        if ((flags & (IFF_UP | IFF_RUNNING)) != (IFF_UP | IFF_RUNNING) ||
            (flags & (IFF_LOOPBACK | IFF_POINTOPOINT)) != 0) continue;
        char numeric[INET6_ADDRSTRLEN];
        const void *bytes = NULL;
        int family = entry->ifa_addr->sa_family;
        if (family == AF_INET) bytes = &((struct sockaddr_in *)entry->ifa_addr)->sin_addr;
        if (family == AF_INET6) bytes = &((struct sockaddr_in6 *)entry->ifa_addr)->sin6_addr;
        if (bytes != NULL && inet_ntop(family, bytes, numeric, sizeof(numeric)) != NULL &&
            p2pkit_lan_numeric_equal(numeric, address)) found = true;
    }
    freeifaddrs(interfaces);
    return found;
}

/* Bind both the actual NWInterface and local endpoint. Never infer an interface from an IP prefix. */
static inline bool p2pkit_nw_restrict_lan_parameters(
    nw_parameters_t parameters, nw_path_t path, const char *name, const char *local, const char *port
) {
    if (parameters == NULL || path == NULL || nw_path_get_status(path) != nw_path_status_satisfied ||
        !p2pkit_lan_selected_address_is_live(name, local)) return false;
    __block bool found = false;
    nw_path_enumerate_interfaces(path, ^bool(nw_interface_t interface) {
        const char *candidate = nw_interface_get_name(interface);
        nw_interface_type_t type = nw_interface_get_type(interface);
        if (candidate != NULL && strcmp(candidate, name) == 0 &&
            (type == nw_interface_type_wifi || type == nw_interface_type_wired)) {
            nw_parameters_require_interface(parameters, interface);
            found = true;
            return false;
        }
        return true;
    });
    if (!found) return false;
    nw_parameters_set_include_peer_to_peer(parameters, false);
    nw_parameters_prohibit_interface_type(parameters, nw_interface_type_cellular);
    nw_parameters_prohibit_interface_type(parameters, nw_interface_type_other);
    nw_parameters_prohibit_interface_type(parameters, nw_interface_type_loopback);
    if (port != NULL) {
        nw_endpoint_t endpoint = nw_endpoint_create_host(local, port);
        if (endpoint == NULL) return false;
        nw_parameters_set_local_endpoint(parameters, endpoint);
        p2pkit_nw_release_owned(endpoint);
    }
    return true;
}

/* Called before I/O and on NWConnection path changes; opaque/unverifiable endpoints fail closed. */
static inline bool p2pkit_nw_lan_path_is_allowed(
    nw_connection_t connection, const char *name, const char *local,
    bool (^remote_allowed)(const char *address)
) {
    if (connection == NULL || remote_allowed == NULL || !p2pkit_lan_selected_address_is_live(name, local)) return false;
    __attribute__((objc_precise_lifetime))
    nw_path_t path = nw_connection_copy_current_path(connection);
    __attribute__((objc_precise_lifetime)) nw_endpoint_t source = NULL;
    __attribute__((objc_precise_lifetime)) nw_endpoint_t destination = NULL;
    bool allowed = false;
    if (path == NULL || nw_path_get_status(path) != nw_path_status_satisfied ||
        nw_path_uses_interface_type(path, nw_interface_type_cellular) ||
        nw_path_uses_interface_type(path, nw_interface_type_other) ||
        nw_path_uses_interface_type(path, nw_interface_type_loopback) ||
        !(nw_path_uses_interface_type(path, nw_interface_type_wifi) ||
          nw_path_uses_interface_type(path, nw_interface_type_wired))) goto cleanup;
    source = nw_path_copy_effective_local_endpoint(path);
    destination = nw_path_copy_effective_remote_endpoint(path);
    if (!p2pkit_lan_endpoint_numeric_equal(source, local)) goto cleanup;
    {
        char remote[INET6_ADDRSTRLEN];
        allowed = p2pkit_lan_endpoint_numeric(destination, remote, sizeof(remote)) && remote_allowed(remote);
    }
cleanup:
    p2pkit_nw_release_owned(destination);
    p2pkit_nw_release_owned(source);
    p2pkit_nw_release_owned(path);
    return allowed;
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

/** Test-only TCP write-half-close; keep the native peer alive to observe remote termination. */
static inline void p2pkit_test_nw_connection_send_fin(
    nw_connection_t connection,
    void (^completion)(nw_error_t error)
) {
    nw_connection_send(connection, NULL, NW_CONNECTION_FINAL_MESSAGE_CONTEXT, true, completion);
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
#if !__has_feature(objc_arc)
    if (data != NULL) dispatch_release(data);
#endif
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
#if !__has_feature(objc_arc)
                if (mapped != NULL) dispatch_release(mapped);
#endif
            } else {
                completion(NULL, 0, is_complete, error);
            }
        }
    );
}

#endif /* P2PKIT_NW_H */
