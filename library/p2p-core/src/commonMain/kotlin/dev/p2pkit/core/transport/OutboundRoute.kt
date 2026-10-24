package dev.p2pkit.core.transport

/**
 * Optional SPI for a successfully connected **outbound** byte stream. Existing transports need not
 * implement it. The candidate describes only the route actually selected for this connection, not
 * alternate discovery hints. An incoming connection must not expose its remote ephemeral port here.
 *
 * Reading this property is resource-inert and does not transfer socket ownership. The route contains
 * no live socket, raw connection, browser handle, or credential. Core may retain a bounded number only
 * after the original connection's authenticated, locally authorized session registration commits.
 * TCP success or an advertised fingerprint alone never authorizes a route.
 */
public interface OutboundRouteConnection : RawConnection {
    public val outboundRoute: OutboundRoute?
}

/**
 * Transport-owned capability to dial the exact numeric destination that one outbound stream reached.
 * This is **routing evidence, not authentication or authorization**. Every new stream still needs the
 * complete authenticated handshake and current application admission decision before use.
 *
 * Implementations capture an immutable numeric address/port (including IPv6 scope and required local
 * network/interface context), the original [transport] instance and its lifecycle generation. Never
 * retain a hostname, Bonjour service name, or whole peer snapshot as if all its addresses were proven.
 * The capability must not retain a socket, connection, native endpoint, or unbounded provider state.
 */
public interface OutboundRoute {
    /** Exact data-transport instance that returned the original connection. */
    public val transport: DataTransport

    /**
     * Fast, resource-inert snapshot of whether the original transport generation and route context
     * remain usable. This is advisory: [connect] must repeat the generation/context checks itself.
     * Stop/close permanently invalidate old capabilities, including after a later transport restart.
     */
    public val isCurrent: Boolean

    /**
     * Dial the captured numeric endpoint independently of discovery-cache capacity. Preserve the
     * transport's address policy, interface/network binding, cancellation, deadlines, pending-resource
     * ownership and cleanup. Check the captured generation before allocation, at pending admission,
     * and at final connection handoff; checking here then calling a dial that captures a NEW generation
     * is invalid. Never consult DNS or substitute a newer unverified discovery endpoint.
     *
     * Return a fresh owned connection, or a typed connection failure. Cancellation propagates. Failure
     * with uncertain cleanup must remain a failure and must not trigger an implicit fallback dial.
     * Only [OutboundRouteUnavailable] permits core to try a current discovery candidate in the same
     * bounded reconnect attempt. It certifies that this route attempt retains no unfinished resource.
     * [timeoutMillis] bounds connection setup and must be positive; enforce the smaller of this budget
     * and the provider's normal connect deadline. Cleanup still retains its existing ownership/bounds.
     * Core uses at most 1,500 ms for this additional probe, then may use the ordinary fallback's normal
     * deadline. There is no claim that arbitrary third-party transport calls share a LAN socket timer.
     */
    public suspend fun connect(timeoutMillis: Long): RawConnection
}

/**
 * Optional route attempt failed **after complete owned cleanup**, or was refused before allocating
 * resources. Unlike an arbitrary exception, this permits another route within the same reconnect
 * budget. Never use it for cancellation, uncertain retirement, or an authentication/authorization
 * failure. A transport must preserve those original failures instead.
 */
public class OutboundRouteUnavailable(message: String) : Exception(message)
