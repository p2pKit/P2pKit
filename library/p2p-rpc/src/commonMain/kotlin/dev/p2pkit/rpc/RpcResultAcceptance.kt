package dev.p2pkit.rpc

import dev.p2pkit.core.PeerFingerprint

/**
 * One decoded terminal result offered to [RpcClient.callWithAcceptance] before its Receipt.
 * [details] carries the actual wire request ID and typed reply; the other fields identify its
 * authenticated Host, Host lifetime and procedure. No field grants trust or authorizes another call.
 * This object contains application data and identity metadata; store it privately, never in automatic logs.
 *
 * Returning normally from the acceptance callback promises that application validation and durable
 * persistence have completed. RPC cannot verify a database commit or make an application's storage durable.
 * There is no public acknowledge method: only the owning call can send its matching Receipt.
 */
public class RpcResultAcceptance<out Response, out ApplicationError> internal constructor(
    public val details: RpcCallDetails<Response, ApplicationError>,
    public val hostFingerprint: PeerFingerprint,
    public val hostIncarnation: String,
    public val procedureName: String,
    public val procedureVersion: Int,
) {
    override fun toString(): String = "RpcResultAcceptance(application data and identity omitted)"
}
