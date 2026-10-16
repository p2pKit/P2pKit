#ifndef P2PKIT_BONJOUR_H
#define P2PKIT_BONJOUR_H
#include <stdint.h>

/* Private DNS-SD ABI v1. Fixed local. domain, explicit positive interface, no default-interface fallback.
 * One opaque generation handle owns one DNSServiceRef. Native callbacks only enqueue bounded records;
 * they never enter the JVM. Only poll processes callbacks. Concurrent poll is rejected (EBUSY).
 * close gates new operations and waits for the current poll (0..100ms) before deallocation.
 * DNSServiceProcessResult talks to the trusted local system daemon, not an arbitrary remote socket.
 * Results: open/close: 0 or errno/DNSServiceErrorType. poll: 0 or 1, negative errno on failure.
 * Every nonzero open output must be closed, including when open returns an error.
 */
#define P2P_BONJOUR_ABI 1u
#define P2P_BONJOUR_FRAME 2048u
#define P2P_BONJOUR_NAME 63u
#define P2P_BONJOUR_TXT 1300u
#define P2P_BONJOUR_HANDLES 128u
#define P2P_BONJOUR_QUEUE 16u

uint32_t p2p_bonjour_abi(void);
/* operation: 1=browse, 2=register (no auto-renaming), 3=resolve.
 * profile: 1=_p2pkit._tcp, 2=_p2pkit2._tcp. name is NUL-terminated UTF-8, <=63 bytes.
 * Browse requires empty name/TXT and zero port; resolve requires name, no TXT/port.
 */
int32_t p2p_bonjour_open(uint32_t index, int32_t operation, int32_t profile,
    const char *name, uint16_t port, const uint8_t *txt, uint32_t txt_length, uint64_t *output);
/* Entire output is zeroed. Big-endian frame: kind:u32,error:i32,index:u32,port:u32,
 * name_length:u32,txt_length:u32, followed by name UTF-8 bytes, then raw DNS-SD TXT.
 * Kinds: 1=added,2=removed,3=resolved,4=registered,5=error. Overflow is terminal error, never silent loss.
 */
int32_t p2p_bonjour_poll(uint64_t handle, int32_t timeout_ms, uint8_t output[P2P_BONJOUR_FRAME]);
int32_t p2p_bonjour_close(uint64_t handle);
#endif
