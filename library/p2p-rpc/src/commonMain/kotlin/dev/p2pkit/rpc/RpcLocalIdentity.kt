package dev.p2pkit.rpc

import dev.p2pkit.core.AppId
import dev.p2pkit.core.P2pKit
import dev.p2pkit.core.PeerFingerprint
import dev.p2pkit.core.PeerId

/**
 * Immutable public facts read from one factory-owned authenticated-v2 Kit at RPC creation.
 * Available before advertising, discovery, enrollment or connection, and retained after close.
 * Contains no keys, endpoint, invitation or admission grant. The device name is display metadata,
 * not a cryptographic identity or proof of application authority. Compare retained fields explicitly;
 * this snapshot neither validates a native-key association nor grants trust.
 */
public class RpcLocalIdentity internal constructor(
    public val appId: AppId,
    public val peerId: PeerId,
    public val fingerprint: PeerFingerprint,
    public val pairingQr: String,
    public val deviceName: String,
)

internal fun P2pKit.rpcLocalIdentity(): RpcLocalIdentity = RpcLocalIdentity(
    appId = appId,
    peerId = localPeerId,
    fingerprint = checkNotNull(localFingerprint),
    pairingQr = checkNotNull(localPairingQr),
    deviceName = localDeviceName,
)
