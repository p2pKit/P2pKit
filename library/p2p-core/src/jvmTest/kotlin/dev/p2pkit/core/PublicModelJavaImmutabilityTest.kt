package dev.p2pkit.core

import dev.p2pkit.core.transport.TransportHint
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue

class PublicModelJavaImmutabilityTest {

    @Test
    fun javaCollectionMutationMethodsCannotChangePublicModels() {
        val peer = Peer(
            PeerId("java-peer"),
            "Java peer",
            Platform.JVM_DESKTOP,
            setOf(TransportKind.LAN)
        )
        val hint = TransportHint(
            TransportKind.LAN,
            metadata = mapOf("key" to "value")
        )

        assertTrue(JavaCollectionMutationProbe.addFails(peer.supportedTransports, TransportKind.BLE))
        assertTrue(JavaCollectionMutationProbe.putFails(hint.metadata, "injected", "value"))
        assertTrue(JavaCollectionMutationProbe.entryMutationFails(hint.metadata, "changed"))
        assertEquals(setOf(TransportKind.LAN), peer.supportedTransports)
        assertEquals(mapOf("key" to "value"), hint.metadata)
    }
}
