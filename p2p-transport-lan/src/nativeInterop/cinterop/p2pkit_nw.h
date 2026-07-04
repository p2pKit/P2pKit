#ifndef P2PKIT_NW_H
#define P2PKIT_NW_H

#include <Network/Network.h>

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
