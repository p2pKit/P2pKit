package dev.p2pkit.sample.android

import dev.p2pkit.core.P2pKit
import dev.p2pkit.core.P2pSession
import dev.p2pkit.core.Peer
import dev.p2pkit.core.PeerFingerprint
import kotlinx.coroutines.NonCancellable
import kotlinx.coroutines.withContext

/**
 * The shared Demo has no pre-connect hook. Guard its actual acquisitions (including a dial after
 * suspended discovery), and witness its existing finally-stop instead of blindly stopping twice.
 * A failed stop retains ownership; this does not promise the underlying SDK can retry that failure.
 */
internal class SampleSmokeKitOwner(
    private val delegate: P2pKit,
    private val beforeAcquire: suspend (P2pKit) -> Unit
) : P2pKit by delegate {
    @Volatile
    var stopped = false
        private set

    override suspend fun start() {
        beforeAcquire(this)
        delegate.start()
    }

    override suspend fun startAdvertising() {
        beforeAcquire(this)
        delegate.startAdvertising()
    }

    override suspend fun startDiscovery() {
        beforeAcquire(this)
        delegate.startDiscovery()
    }

    override suspend fun connect(peer: Peer): P2pSession {
        beforeAcquire(this)
        return delegate.connect(peer)
    }

    override suspend fun connect(peer: Peer, expectedFingerprint: PeerFingerprint): P2pSession {
        beforeAcquire(this)
        return delegate.connect(peer, expectedFingerprint)
    }

    override suspend fun stop() {
        if (stopped) return
        withContext(NonCancellable) {
            delegate.stop()
            stopped = true
        }
    }
}
