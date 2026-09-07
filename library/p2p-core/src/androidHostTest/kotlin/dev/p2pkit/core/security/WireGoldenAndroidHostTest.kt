package dev.p2pkit.core.security

import dev.p2pkit.core.internal.security.noise.SecureSessionWireGoldenTest
import dev.p2pkit.core.protocol.AppMessageEnvelopeGoldenTest
import kotlin.test.Test

/** Android-source provider on a host JVM, not Keystore/ART/device or cross-process interoperability. */
class WireGoldenAndroidHostTest {
    @Test
    fun androidInitiatorMatchesFrozenComposedChannel() {
        SecureSessionWireGoldenTest().initiatorDecodesFrozenResponderAndProducesFrozenInitiatorBytes()
    }

    @Test
    fun androidResponderMatchesFrozenComposedChannel() {
        SecureSessionWireGoldenTest().responderDecodesFrozenInitiatorAndProducesFrozenResponderBytes()
    }

    @Test
    fun androidEnvelopeEncodingMatchesFourFrozenVariants() {
        AppMessageEnvelopeGoldenTest().apply {
            textEncodingMatchesFrozenEnvelopesWithAndWithoutMetadata()
            binaryEncodingMatchesFrozenEnvelopesWithAndWithoutMetadata()
        }
    }

    @Test
    fun androidDecodesFourFrozenEnvelopeVariantsWithoutCallingEncoder() {
        AppMessageEnvelopeGoldenTest().apply {
            frozenTextEnvelopesDecodeWithoutCallingEncoder()
            frozenBinaryEnvelopesDecodeWithoutCallingEncoder()
        }
    }
}
