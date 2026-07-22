package dev.p2pkit.transport.lan

import dev.p2pkit.core.AppId
import dev.p2pkit.core.PeerId
import dev.p2pkit.core.Platform
import kotlinx.coroutines.runBlocking
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertNotNull
import kotlin.test.assertNull
import kotlin.test.assertTrue

class JvmLanDataTransportLifecycleTest {

    @Test
    fun terminalCloseClearsListenerStateAndRejectsRestart() = runBlocking {
        val registration = LanServiceRegistration(
            appId = AppId("data-close-test"),
            localPeerId = PeerId("data-close-local"),
            deviceName = "local",
            platform = Platform.JVM_DESKTOP
        )
        val transport = JvmLanDataTransport(registration)

        assertTrue(transport.start().isSuccess)
        val port = assertNotNull(transport.tcpPort.value)
        assertEquals(port, registration.tcpPort)

        transport.close()
        transport.close()

        assertNull(transport.tcpPort.value)
        assertEquals(0, registration.tcpPort)
        assertTrue(transport.start().isFailure, "terminally closed transport must not restart")
    }
}
