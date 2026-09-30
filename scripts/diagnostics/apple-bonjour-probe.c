/*
 * Owned, unprivileged OS primitive diagnostic, NOT a P2pKit/LAN acceptance test.
 * No permission changes, external endpoints, payloads, names or addresses in output.
 * Build the SAME source for the actual macOS host and selected iOS simulator.
 * LocalOnly is an explicitly labelled DNS-SD control, never multicast evidence.
 */
#include <TargetConditionals.h>
#include <Network/Network.h>
#include <arpa/inet.h>
#include <dispatch/dispatch.h>
#include <dns_sd.h>
#include <errno.h>
#include <ifaddrs.h>
#include <net/if.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/select.h>
#include <sys/socket.h>
#include <time.h>
#include <unistd.h>

static const char *service_type = "_p2pkit2._tcp";

static uint64_t monotonic_ns(void) {
    struct timespec value;
    if (clock_gettime(CLOCK_MONOTONIC, &value) != 0) abort();
    return (uint64_t)value.tv_sec * 1000000000ULL + (uint64_t)value.tv_nsec;
}

static bool private_ipv4(struct in_addr address) {
    uint32_t value = ntohl(address.s_addr);
    return (value >> 24) == 10 || (value >> 20) == 0xac1 || (value >> 16) == 0xc0a8;
}

static void unique_name(char name[64]) {
    uint8_t random[16];
    arc4random_buf(random, sizeof(random));
    strcpy(name, "p2pkit-probe-");
    for (size_t i = 0; i < sizeof(random); i++) snprintf(name + 13 + i * 2, 3, "%02x", random[i]);
}

static int first_ipv4(struct in_addr *address) {
    struct ifaddrs *all = NULL;
    if (getifaddrs(&all) != 0) return errno;
    int result = ENOENT;
    for (struct ifaddrs *row = all; row != NULL; row = row->ifa_next) {
        if (row->ifa_addr == NULL || row->ifa_addr->sa_family != AF_INET ||
            !(row->ifa_flags & IFF_UP) || !(row->ifa_flags & IFF_MULTICAST) ||
            (row->ifa_flags & IFF_LOOPBACK)) continue;
        *address = ((struct sockaddr_in *)row->ifa_addr)->sin_addr;
        result = 0;
        break;
    }
    freeifaddrs(all);
    return result;
}

static int bsd_probe(void) {
    struct ifaddrs *all = NULL;
    if (getifaddrs(&all) != 0) return 2;
    /* DNS question, PTR _p2pkit2._tcp.local.; zero IDs, no application data. */
    const uint8_t query[] = {0,0,0,0,0,1,0,0,0,0,0,0,
        8,'_','p','2','p','k','i','t','2',4,'_','t','c','p',5,'l','o','c','a','l',0,0,12,0,1};
    size_t count = 0, success = 0;
    printf("\"interfaces\":[");
    for (struct ifaddrs *row = all; row != NULL; row = row->ifa_next) {
        if (row->ifa_addr == NULL || row->ifa_addr->sa_family != AF_INET ||
            !(row->ifa_flags & IFF_UP) || !(row->ifa_flags & IFF_MULTICAST) ||
            (row->ifa_flags & IFF_LOOPBACK)) continue;
        if (count == 64) { freeifaddrs(all); return 2; }
        struct in_addr address = ((struct sockaddr_in *)row->ifa_addr)->sin_addr;
        int fd = socket(AF_INET, SOCK_DGRAM, 0);
        int setup_error = fd < 0 ? errno : 0, send_error = 0, close_error = 0;
        ssize_t sent = -1;
        if (fd >= 0) {
            struct sockaddr_in local = { .sin_len = sizeof(local), .sin_family = AF_INET, .sin_addr = address };
            unsigned char ttl = 1, loop = 1;
            if (bind(fd, (struct sockaddr *)&local, sizeof(local)) != 0 ||
                setsockopt(fd, IPPROTO_IP, IP_MULTICAST_IF, &address, sizeof(address)) != 0 ||
                setsockopt(fd, IPPROTO_IP, IP_MULTICAST_TTL, &ttl, sizeof(ttl)) != 0 ||
                setsockopt(fd, IPPROTO_IP, IP_MULTICAST_LOOP, &loop, sizeof(loop)) != 0) setup_error = errno;
            if (setup_error == 0) {
                struct sockaddr_in remote = { .sin_len = sizeof(remote), .sin_family = AF_INET, .sin_port = htons(5353) };
                if (inet_pton(AF_INET, "224.0.0.251", &remote.sin_addr) != 1) abort();
                sent = sendto(fd, query, sizeof(query), 0, (struct sockaddr *)&remote, sizeof(remote));
                if (sent < 0) send_error = errno;
            }
            if (close(fd) != 0) close_error = errno;
        }
        bool returned = sent == (ssize_t)sizeof(query);
        success += returned && close_error == 0;
        printf("%s{\"privateIpv4\":%s,\"pointToPoint\":%s,\"setupErrno\":%d,"
               "\"sendErrno\":%d,\"closeErrno\":%d,\"sendReturned\":%s}", count++ ? "," : "",
               private_ipv4(address) ? "true" : "false", (row->ifa_flags & IFF_POINTOPOINT) ? "true" : "false",
               setup_error, send_error, close_error, returned ? "true" : "false");
    }
    freeifaddrs(all);
    printf("]");
    return count > 0 && success == count ? 0 : 1;
}

struct dns_observation {
    const char *name;
    int registration_callbacks, registration_code, browse_callbacks, browse_code, target_adds;
};

static void registered(DNSServiceRef ref, DNSServiceFlags flags, DNSServiceErrorType error,
                       const char *name, const char *type, const char *domain, void *context) {
    (void)ref; (void)flags; (void)name; (void)type; (void)domain;
    struct dns_observation *value = context;
    value->registration_callbacks++;
    value->registration_code = error;
}

static void browsed(DNSServiceRef ref, DNSServiceFlags flags, uint32_t index, DNSServiceErrorType error,
                    const char *name, const char *type, const char *domain, void *context) {
    (void)ref; (void)index; (void)type; (void)domain;
    struct dns_observation *value = context;
    value->browse_callbacks++;
    value->browse_code = error;
    if (!error && (flags & kDNSServiceFlagsAdd) && name != NULL && strcmp(name, value->name) == 0) value->target_adds++;
}

static int dns_probe(bool local_only) {
    char name[64];
    unique_name(name);
    struct dns_observation value = { .name = name };
    DNSServiceRef registration = NULL, browser = NULL;
    uint32_t index = local_only ? kDNSServiceInterfaceIndexLocalOnly : kDNSServiceInterfaceIndexAny;
    DNSServiceFlags flags = local_only ? 0 : kDNSServiceFlagsIncludeP2P;
    int registration_start = DNSServiceRegister(&registration, flags | kDNSServiceFlagsNoAutoRename,
        index, name, service_type, "local.", NULL, htons(9), 0, NULL, registered, &value);
    int browse_start = DNSServiceBrowse(&browser, flags, index, service_type, "local.", browsed, &value);
    int poll_error = 0, processing_error = 0;
    uint64_t deadline = monotonic_ns() + 10000000000ULL;
    while (monotonic_ns() < deadline && !registration_start && !browse_start &&
           !value.registration_code && !value.browse_code && !value.target_adds) {
        int a = DNSServiceRefSockFD(registration), b = DNSServiceRefSockFD(browser);
        if (a < 0 || b < 0 || a >= FD_SETSIZE || b >= FD_SETSIZE) { poll_error = EINVAL; break; }
        fd_set read;
        FD_ZERO(&read); FD_SET(a, &read); FD_SET(b, &read);
        struct timeval wait = { .tv_sec = 0, .tv_usec = 100000 };
        int ready = select((a > b ? a : b) + 1, &read, NULL, NULL, &wait);
        if (ready < 0) { if (errno == EINTR) continue; poll_error = errno; break; }
        if (ready > 0 && FD_ISSET(a, &read)) processing_error = DNSServiceProcessResult(registration);
        if (ready > 0 && FD_ISSET(b, &read) && !processing_error) processing_error = DNSServiceProcessResult(browser);
        if (processing_error) break;
    }
    /* Synchronous deallocation closes each DNS-SD connection; callbacks use this stack only above. */
    if (browser) DNSServiceRefDeallocate(browser);
    if (registration) DNSServiceRefDeallocate(registration);
    printf("\"registrationStart\":%d,\"browseStart\":%d,\"registrationCallbacks\":%d,"
           "\"registrationCode\":%d,\"browseCallbacks\":%d,\"browseCode\":%d,\"targetAdds\":%d,"
           "\"pollErrno\":%d,\"processingCode\":%d,\"referencesDeallocated\":true",
           registration_start, browse_start, value.registration_callbacks, value.registration_code,
           value.browse_callbacks, value.browse_code, value.target_adds, poll_error, processing_error);
    return !registration_start && !browse_start && !poll_error && !processing_error &&
        value.registration_callbacks > 0 && !value.registration_code && !value.browse_code && value.target_adds > 0 ? 0 : 1;
}

struct network_observation {
    nw_listener_t listener;
    nw_connection_t connection;
    dispatch_queue_t queue;
    dispatch_group_t cancelled;
    struct in_addr address;
    bool has_address, listener_ready, browser_ready, listener_cancelled, browser_cancelled, connection_cancelled;
    bool connection_ready, closing;
    int listener_domain, listener_code, browser_domain, browser_code, connection_domain, connection_code;
    int registration_adds, browse_callbacks, target_adds, accepted, path_status, path_reason, connection_path_reason;
};

static nw_parameters_t parameters(void) {
    nw_parameters_t value = nw_parameters_create_secure_tcp(NW_PARAMETERS_DISABLE_PROTOCOL, NW_PARAMETERS_DEFAULT_CONFIGURATION);
    nw_parameters_prohibit_interface_type(value, nw_interface_type_cellular);
    nw_parameters_set_include_peer_to_peer(value, true);
    return value;
}

static void connect_local(struct network_observation *value) {
    if (!value->has_address || value->connection || value->closing) return;
    char host[INET_ADDRSTRLEN], port[8];
    if (inet_ntop(AF_INET, &value->address, host, sizeof(host)) == NULL) abort();
    snprintf(port, sizeof(port), "%u", nw_listener_get_port(value->listener));
    nw_endpoint_t endpoint = nw_endpoint_create_host(host, port);
    nw_parameters_t params = parameters();
    value->connection = nw_connection_create(endpoint, params);
    nw_release(endpoint); nw_release(params);
    if (!value->connection) abort();
    nw_connection_set_queue(value->connection, value->queue);
    dispatch_group_enter(value->cancelled);
    nw_connection_set_state_changed_handler(value->connection, ^(nw_connection_state_t state, nw_error_t error) {
        if (error) { value->connection_domain = nw_error_get_error_domain(error); value->connection_code = nw_error_get_error_code(error); }
        nw_path_t path = nw_connection_copy_current_path(value->connection);
        if (path) {
            int reason = nw_path_get_unsatisfied_reason(path);
            /* Preserve a real denial observation across the later cancelled path. */
            if (reason != 0) value->connection_path_reason = reason;
            nw_release(path);
        }
        if (state == nw_connection_state_ready) value->connection_ready = true;
        if (state == nw_connection_state_cancelled && !value->connection_cancelled) {
            value->connection_cancelled = true;
            dispatch_group_leave(value->cancelled);
        }
    });
    nw_connection_start(value->connection);
}

static int network_probe(void) {
    char name[64];
    unique_name(name);
    struct network_observation storage = {0}, *value = &storage;
    value->has_address = first_ipv4(&value->address) == 0;
    value->queue = dispatch_queue_create("dev.p2pkit.probe", DISPATCH_QUEUE_SERIAL);
    value->cancelled = dispatch_group_create();
    nw_parameters_t params = parameters();
    value->listener = nw_listener_create(params);
    nw_release(params);
    nw_advertise_descriptor_t advertised = nw_advertise_descriptor_create_bonjour_service(name, service_type, "local.");
    nw_advertise_descriptor_set_no_auto_rename(advertised, true);
    nw_listener_set_advertise_descriptor(value->listener, advertised);
    nw_release(advertised);
    nw_listener_set_queue(value->listener, value->queue);
    dispatch_group_enter(value->cancelled);
    nw_listener_set_state_changed_handler(value->listener, ^(nw_listener_state_t state, nw_error_t error) {
        if (error) { value->listener_domain = nw_error_get_error_domain(error); value->listener_code = nw_error_get_error_code(error); }
        if (state == nw_listener_state_ready) { value->listener_ready = true; connect_local(value); }
        if (state == nw_listener_state_cancelled && !value->listener_cancelled) {
            value->listener_cancelled = true;
            dispatch_group_leave(value->cancelled);
        }
    });
    nw_listener_set_advertised_endpoint_changed_handler(value->listener, ^(nw_endpoint_t endpoint, bool added) {
        (void)endpoint;
        if (added) value->registration_adds++;
    });
    nw_listener_set_new_connection_handler(value->listener, ^(nw_connection_t connection) {
        value->accepted++;
        nw_connection_cancel(connection); /* Primitive reachability only; never accept application data. */
    });
    nw_browse_descriptor_t description = nw_browse_descriptor_create_bonjour_service(service_type, "local.");
    nw_parameters_t browse_params = nw_parameters_create();
    nw_parameters_prohibit_interface_type(browse_params, nw_interface_type_cellular);
    nw_parameters_set_include_peer_to_peer(browse_params, true);
    nw_browser_t browser = nw_browser_create(description, browse_params);
    nw_release(description); nw_release(browse_params);
    nw_browser_set_queue(browser, value->queue);
    dispatch_group_enter(value->cancelled);
    nw_browser_set_state_changed_handler(browser, ^(nw_browser_state_t state, nw_error_t error) {
        if (error) { value->browser_domain = nw_error_get_error_domain(error); value->browser_code = nw_error_get_error_code(error); }
        if (state == nw_browser_state_ready) value->browser_ready = true;
        if (state == nw_browser_state_cancelled && !value->browser_cancelled) {
            value->browser_cancelled = true;
            dispatch_group_leave(value->cancelled);
        }
    });
    /* A heap copy, not a reference to a C array captured by an escaping block. */
    char *expected_name = strdup(name);
    if (!expected_name) abort();
    nw_browser_set_browse_results_changed_handler(browser, ^(nw_browse_result_t old, nw_browse_result_t next, bool complete) {
        (void)old; (void)complete;
        value->browse_callbacks++;
        if (next) {
            nw_endpoint_t endpoint = nw_browse_result_copy_endpoint(next);
            if (endpoint) {
                const char *observed = nw_endpoint_get_bonjour_service_name(endpoint);
                if (observed && strcmp(observed, expected_name) == 0) value->target_adds++;
                nw_release(endpoint);
            }
        }
    });
    nw_path_monitor_t monitor = nw_path_monitor_create();
    nw_path_monitor_set_queue(monitor, value->queue);
    nw_path_monitor_set_update_handler(monitor, ^(nw_path_t path) {
        value->path_status = nw_path_get_status(path);
        value->path_reason = nw_path_get_unsatisfied_reason(path);
    });
    nw_path_monitor_start(monitor);
    nw_listener_start(value->listener);
    nw_browser_start(browser);
    /* Fixed diagnostic observation, not a larger/retried production discovery deadline. */
    struct timespec pause = { .tv_sec = 10 };
    while (nanosleep(&pause, &pause) != 0) if (errno != EINTR) abort();
    dispatch_sync(value->queue, ^{
        value->closing = true;
        if (value->connection) nw_connection_cancel(value->connection);
        nw_browser_cancel(browser);
        nw_listener_cancel(value->listener);
        nw_path_monitor_cancel(monitor);
    });
    bool cleanup = dispatch_group_wait(value->cancelled, dispatch_time(DISPATCH_TIME_NOW, 5000000000LL)) == 0;
    /* A missed callback is a failed cleanup, never a release of still-referenced stack storage. */
    if (!cleanup) { printf("\"cleanupComplete\":false"); fflush(stdout); _exit(3); }
    dispatch_sync(value->queue, ^{
        /* Unlike the listener/browser setters, this SDK parameter is nonnull.
         * Replace the cancelled monitor's callback with a non-capturing block.
         * This breaks the reference to stack storage without violating its API.
         */
        nw_path_monitor_set_update_handler(monitor, ^(nw_path_t unused) { (void)unused; });
        nw_browser_set_browse_results_changed_handler(browser, NULL);
        nw_browser_set_state_changed_handler(browser, NULL);
        nw_listener_set_new_connection_handler(value->listener, NULL);
        nw_listener_set_advertised_endpoint_changed_handler(value->listener, NULL);
        nw_listener_set_state_changed_handler(value->listener, NULL);
        if (value->connection) nw_connection_set_state_changed_handler(value->connection, NULL);
    });
    if (value->connection) nw_release(value->connection);
    nw_release(browser); nw_release(value->listener); nw_release(monitor);
    dispatch_release(value->cancelled); dispatch_release(value->queue); free(expected_name);
    printf("\"hasIpv4\":%s,\"listenerReady\":%s,\"browserReady\":%s,\"connectionReady\":%s,"
           "\"listenerDomain\":%d,\"listenerCode\":%d,\"browserDomain\":%d,\"browserCode\":%d,"
           "\"connectionDomain\":%d,\"connectionCode\":%d,\"registrationAdds\":%d,\"browseCallbacks\":%d,"
           "\"targetAdds\":%d,\"acceptedConnections\":%d,\"pathStatus\":%d,\"pathReason\":%d,"
           "\"connectionPathReason\":%d,\"cleanupComplete\":true",
           value->has_address ? "true" : "false", value->listener_ready ? "true" : "false",
           value->browser_ready ? "true" : "false", value->connection_ready ? "true" : "false",
           value->listener_domain, value->listener_code, value->browser_domain, value->browser_code,
           value->connection_domain, value->connection_code, value->registration_adds, value->browse_callbacks,
           value->target_adds, value->accepted, value->path_status, value->path_reason, value->connection_path_reason);
    return value->listener_ready && value->browser_ready && value->registration_adds > 0 &&
        value->target_adds > 0 && value->accepted > 0 && value->connection_ready ? 0 : 1;
}

int main(int argc, char **argv) {
    if (argc != 2 || getuid() == 0 || getuid() != geteuid() || getgid() != getegid()) return 2;
    const char *mode = argv[1];
    if (strcmp(mode, "bsd") && strcmp(mode, "dns-any") && strcmp(mode, "dns-local") && strcmp(mode, "network")) return 2;
    uint64_t start = monotonic_ns();
    printf("{\"schema\":1,\"mode\":\"%s\",\"simulator\":%s,\"unprivileged\":true,", mode,
           TARGET_OS_SIMULATOR ? "true" : "false");
    int result = !strcmp(mode, "bsd") ? bsd_probe() : !strcmp(mode, "network") ? network_probe() :
        dns_probe(!strcmp(mode, "dns-local"));
    printf(",\"elapsedMillis\":%llu,\"probeExit\":%d}\n",
           (unsigned long long)((monotonic_ns() - start) / 1000000ULL), result);
    return result;
}
