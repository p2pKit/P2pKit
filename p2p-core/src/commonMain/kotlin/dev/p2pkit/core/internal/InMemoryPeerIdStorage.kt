package dev.p2pkit.core.internal

import dev.p2pkit.core.PeerId
import kotlin.uuid.ExperimentalUuidApi
import kotlin.uuid.Uuid

/**
 * In-memory [PeerIdStorage] — generates one id per instance and returns it
 * forever. Used as the Android fallback when the host app forgot to call
 * `P2pKitAndroid.initialize(context)`, and as a test fixture.
 *
 * Each instance has its own id; restarting the process loses the id.
 */
internal class InMemoryPeerIdStorage(
    private val seed: PeerId? = null
) : PeerIdStorage {

    private var cached: PeerId? = seed

    @OptIn(ExperimentalUuidApi::class)
    override fun loadOrGenerate(): PeerId {
        cached?.let { return it }
        val fresh = PeerId(Uuid.random().toString())
        cached = fresh
        return fresh
    }
}
