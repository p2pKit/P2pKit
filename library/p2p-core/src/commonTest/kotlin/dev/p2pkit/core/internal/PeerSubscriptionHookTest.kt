package dev.p2pkit.core.internal

import dev.p2pkit.core.Peer
import dev.p2pkit.core.PeerId
import dev.p2pkit.core.Platform
import dev.p2pkit.core.TransportKind
import dev.p2pkit.core.transport.InternalPeer
import dev.p2pkit.core.transport.PeerEvent
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.CoroutineExceptionHandler
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.CoroutineStart
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.awaitCancellation
import kotlinx.coroutines.cancelAndJoin
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.onSubscription
import kotlinx.coroutines.launch
import kotlinx.coroutines.test.runCurrent
import kotlinx.coroutines.test.runTest
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue

@OptIn(ExperimentalCoroutinesApi::class)
class PeerSubscriptionHookTest {
    @Test
    fun peerSubscriptionHookRunsBeforeInitialValueAndCanPublishCurrentPeers() = runTest {
        val peer = Peer(
            id = PeerId("subscription-hook"),
            name = "Subscription hook",
            platform = Platform.JVM_DESKTOP,
            supportedTransports = setOf(TransportKind.LAN)
        )
        val registry = PeerRegistry(emptyList(), backgroundScope, clock = { 1_000L })
        val reference = MutableStateFlow<List<Peer>>(emptyList())
        suspend fun trace(
            flow: StateFlow<List<Peer>>,
            publish: () -> Unit
        ): List<Pair<String, List<Peer>>> {
            val observations = mutableListOf<Pair<String, List<Peer>>>()
            val collector = backgroundScope.launch {
                flow.onSubscription {
                    observations += "subscription" to flow.value
                    publish()
                }.collect { observations += "value" to it }
            }
            try {
                runCurrent()
                return observations.toList()
            } finally {
                collector.cancelAndJoin()
            }
        }
        val expected = listOf("subscription" to emptyList<Peer>(), "value" to listOf(peer))
        assertEquals(expected, trace(reference) { reference.value = listOf(peer) }, "reference control")
        assertEquals(
            expected,
            trace(registry.peers) {
                registry.processEvent(PeerEvent.Found(InternalPeer(peer, emptyList())))
            },
            "the public peer flow must run the subscription hook before its current-value emission"
        )
    }

    @Test
    fun suspendingAndNestedHooksRunBeforeTheLatestInitialValue() = runTest {
        val intermediate = hookPeer("intermediate")
        val publishedByHook = hookPeer("final")
        val emitted = hookPeer("emitted by hook")
        val registry = PeerRegistry(emptyList(), backgroundScope, clock = { 1_000L })
        val reference = MutableStateFlow<List<Peer>>(emptyList())
        suspend fun trace(
            flow: StateFlow<List<Peer>>,
            publish: (Peer) -> Unit
        ): List<Pair<String, List<Peer>>> {
            val observations = mutableListOf<Pair<String, List<Peer>>>()
            val release = CompletableDeferred<Unit>()
            val collector = backgroundScope.launch(start = CoroutineStart.UNDISPATCHED) {
                flow.onSubscription {
                    observations += "hook entered" to flow.value
                    release.await()
                    observations += "hook resumed" to flow.value
                    emit(listOf(emitted))
                    publish(publishedByHook)
                }.onSubscription {
                    observations += "nested hook" to flow.value
                }.collect { observations += "value" to it }
            }
            try {
                assertEquals(listOf("hook entered" to emptyList<Peer>()), observations)
                publish(intermediate)
                runCurrent()
                assertEquals(listOf("hook entered" to emptyList<Peer>()), observations)
                release.complete(Unit)
                runCurrent()
                return observations.toList()
            } finally {
                collector.cancelAndJoin()
            }
        }
        val expected = listOf(
            "hook entered" to emptyList(),
            "hook resumed" to listOf(intermediate),
            "value" to listOf(emitted),
            "nested hook" to listOf(publishedByHook),
            "value" to listOf(publishedByHook)
        )
        assertEquals(expected, trace(reference) { reference.value = listOf(it) }, "reference control")
        assertEquals(expected, trace(registry.peers) { registry.publishHookPeer(it) })
    }

    @Test
    fun cancellationDuringHookPreventsNestedHookAndValues() = runTest {
        val peer = hookPeer("while suspended")
        val registry = PeerRegistry(emptyList(), backgroundScope, clock = { 1_000L })
        val reference = MutableStateFlow<List<Peer>>(emptyList())
        suspend fun trace(
            flow: StateFlow<List<Peer>>,
            publish: () -> Unit
        ): List<String> {
            val observations = mutableListOf<String>()
            val collector = backgroundScope.launch(start = CoroutineStart.UNDISPATCHED) {
                flow.onSubscription {
                    observations += "hook entered"
                    try {
                        awaitCancellation()
                    } finally {
                        observations += "hook cancelled"
                    }
                }.onSubscription {
                    observations += "nested hook"
                }.collect { observations += "value" }
            }
            try {
                assertEquals(listOf("hook entered"), observations)
                collector.cancelAndJoin()
                publish()
                runCurrent()
                return observations.toList()
            } finally {
                collector.cancelAndJoin()
            }
        }
        val expected = listOf("hook entered", "hook cancelled")
        assertEquals(expected, trace(reference) { reference.value = listOf(peer) }, "reference control")
        assertEquals(expected, trace(registry.peers) { registry.publishHookPeer(peer) })
    }

    @Test
    fun hookPublicationDuringAnEarlierNotificationIsTheNewCollectorsFirstValue() {
        val initial = hookPeer("before hook")
        val updated = hookPeer("from hook")
        fun trace(
            flow: StateFlow<List<Peer>>,
            scope: CoroutineScope,
            publish: (Peer) -> Unit
        ): List<Pair<String, List<Peer>>> {
            val observations = mutableListOf<Pair<String, List<Peer>>>()
            var nestedStarted = false
            var insidePublication = false
            var hookRanInsidePublication = false
            scope.launch(start = CoroutineStart.UNDISPATCHED) {
                flow.collect { peers ->
                    if (!nestedStarted && peers == listOf(initial)) {
                        nestedStarted = true
                        scope.launch(start = CoroutineStart.UNDISPATCHED) {
                            flow.onSubscription {
                                hookRanInsidePublication = insidePublication
                                observations += "hook" to flow.value
                                publish(updated)
                                observations += "published" to flow.value
                            }.collect { observations += "value" to it }
                        }
                    }
                }
            }
            insidePublication = true
            try {
                publish(initial)
            } finally {
                insidePublication = false
            }
            assertTrue(hookRanInsidePublication, "the hook must run inside the active native notification pass")
            return observations.toList()
        }
        fun actualTrace(registryFlow: Boolean): List<Pair<String, List<Peer>>> {
            val owner = SupervisorJob()
            val failures = mutableListOf<Throwable>()
            val scope = CoroutineScope(
                Dispatchers.Unconfined + owner + CoroutineExceptionHandler { _, failure -> failures += failure }
            )
            try {
                val registry = PeerRegistry(emptyList(), scope, clock = { 1_000L })
                val reference = MutableStateFlow<List<Peer>>(emptyList())
                val observed = if (registryFlow) {
                    trace(registry.peers, scope) { registry.publishHookPeer(it) }
                } else {
                    trace(reference, scope) { reference.value = listOf(it) }
                }
                assertEquals(emptyList<Throwable>(), failures, "unexpected owned collector failures")
                return observed
            } finally {
                owner.cancel()
                assertTrue(owner.isCompleted, "all owned collectors must finish during cancellation")
            }
        }
        val expected = listOf(
            "hook" to listOf(initial),
            "published" to listOf(updated),
            "value" to listOf(updated)
        )
        assertEquals(expected, actualTrace(registryFlow = false), "reference control")
        assertEquals(expected, actualTrace(registryFlow = true))
    }

    private fun hookPeer(name: String): Peer = Peer(
        id = PeerId("hook-peer"),
        name = name,
        platform = Platform.JVM_DESKTOP,
        supportedTransports = setOf(TransportKind.LAN)
    )

    private fun PeerRegistry.publishHookPeer(peer: Peer) {
        processEvent(PeerEvent.Updated(InternalPeer(peer, emptyList())))
    }
}
