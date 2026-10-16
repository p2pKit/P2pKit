#ifndef P2PKIT_LAN_SOCKET_H
#define P2PKIT_LAN_SOCKET_H

#include <stdint.h>

/* Private IPv4 TCP ABI v1. Not a public library API or an admission-policy replacement.
 * All results are 0 or a positive errno. Outputs are cleared before a fallible call.
 * Opaque generation-tagged handles never expose descriptors or native pointers.
 * Operations are nonblocking, except poll (0..100ms) and close (drains in-flight operations).
 * No borrowed buffer survives a call. read/write lengths are 1..65536 bytes.
 * The caller still owns numeric CIDR, local/remote/self, interface-identity and lifecycle checks.
 */
#define P2P_LAN_SOCKET_ABI 1u
#define P2P_LAN_SOCKET_MAX_BYTES 65536u
#define P2P_LAN_SOCKET_MAX_HANDLES 1024u

/* open/accept can return an error AND a nonzero owned handle when setup fails. The caller
 * MUST close every nonzero handle, including on error, and retain both error results.
 * interface_index is an existing kernel interface index. Ports use host byte order.
 */
uint32_t p2p_lan_socket_abi(void);
int32_t p2p_lan_socket_open(uint32_t interface_index, uint64_t *handle);
int32_t p2p_lan_socket_bind(uint64_t handle, const uint8_t address[4], uint16_t port);
int32_t p2p_lan_socket_listen(uint64_t handle, int32_t backlog);
int32_t p2p_lan_socket_accept(uint64_t listener, uint64_t *child);
/* EINPROGRESS means wait for writable, then call connected; never extend the caller's deadline. */
int32_t p2p_lan_socket_connect(uint64_t handle, const uint8_t address[4], uint16_t port);
int32_t p2p_lan_socket_connected(uint64_t handle);
int32_t p2p_lan_socket_endpoint(uint64_t handle, int32_t remote, uint8_t address[4], uint16_t *port);
int32_t p2p_lan_socket_bound_interface(uint64_t handle, uint32_t *interface_index);
/* option: 1 = SO_REUSEADDR, 2 = TCP_NODELAY; enabled: 0 or 1. */
int32_t p2p_lan_socket_option(uint64_t handle, int32_t option, int32_t enabled);
int32_t p2p_lan_socket_read(uint64_t handle, uint8_t *bytes, uint32_t length, uint32_t *count);
int32_t p2p_lan_socket_write(uint64_t handle, const uint8_t *bytes, uint32_t length, uint32_t *count);
/* writable: 0 or 1. ready is 1 for requested readiness, error or hangup; read/connected reports details. */
int32_t p2p_lan_socket_poll(uint64_t handle, int32_t writable, int32_t timeout_ms, int32_t *ready);
/* Close gates new leases and drains existing ones before releasing the descriptor exactly once.
 * A failed OS close is quarantined: no retry against a potentially recycled descriptor number.
 * Concurrent/repeated close and all stale-handle operations fail with EBADF, not a second close.
 */
int32_t p2p_lan_socket_close(uint64_t handle);

#endif
