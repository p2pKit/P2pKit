package dev.p2pkit.core

import java.lang.reflect.Modifier
import kotlin.test.Test
import kotlin.test.assertTrue

/** Inspect emitted field flags; a scheduling stress test cannot prove volatile visibility. */
class ErrorCauseVisibilityJvmTest {
    @Test
    fun localIdentityCauseSlotIsVolatile() = assertVolatileCauseSlot(P2pError.LocalIdentityUnavailable::class.java)

    @Test
    fun connectionCauseSlotIsVolatile() = assertVolatileCauseSlot(P2pError.ConnectionFailed::class.java)

    @Test
    fun fileTransferCauseSlotIsVolatile() = assertVolatileCauseSlot(P2pError.FileTransferFailed::class.java)

    @Test
    fun authenticationCauseSlotIsVolatile() = assertVolatileCauseSlot(P2pError.AuthenticationFailed::class.java)

    private fun assertVolatileCauseSlot(errorClass: Class<out P2pError>) {
        val field = errorClass.getDeclaredField("underlying")
        assertTrue(Modifier.isVolatile(field.modifiers), "${errorClass.simpleName}.underlying must be volatile")
    }
}
