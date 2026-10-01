package dev.p2pkit.sample.rpc.lab

import kotlin.test.Test
import kotlin.test.assertEquals

class LabJfrProfileTest {
    @Test
    fun pathEnumerationIsAttributedToTheSampledLeafNotItsRpcCaller() {
        assertEquals(LabProfileCategory.LanInterfaceEnumeration, labProfileCategory(listOf(
            "java.net.NetworkInterface" to "getAll",
            "dev.p2pkit.transport.lan.JvmOrganizationLanKt" to "organizationJvmTarget",
            "dev.p2pkit.rpc.internal.RpcClientEngine" to "call",
        )))
        assertEquals(LabProfileCategory.LanPathValidation, labProfileCategory(listOf(
            "dev.p2pkit.transport.lan.JvmRawConnection" to "requireAllowedPath",
        )))
    }

    @Test
    fun nativeIoSamplesAreSeparateFromExecutionAndCoroutineCategories() {
        for ((method, expected) in listOf("read0" to LabProfileCategory.SocketRead,
            "write0" to LabProfileCategory.SocketWrite)) {
            assertEquals(expected, labProfileCategory(listOf("sun.nio.ch.SocketDispatcher" to method)))
        }
        assertEquals(LabProfileCategory.SocketPoll, labProfileCategory(listOf("sun.nio.ch.Net" to "poll")))
        assertEquals(LabProfileCategory.CoroutineScheduler,
            labProfileCategory(listOf("kotlinx.coroutines.scheduling.CoroutineScheduler" to "run")))
    }

    @Test
    fun unknownSymbolsAndEmptyOrOversizedStacksCannotEscapeTheClosedVocabulary() {
        assertEquals(LabProfileCategory.Other, labProfileCategory(emptyList()))
        assertEquals(LabProfileCategory.Other, labProfileCategory(listOf("private-value" to "private-value")))
        assertEquals(LabProfileCategory.Other, labProfileCategory(
            List(64) { "unknown" to "unknown" } + ("java.net.NetworkInterface" to "getAll"),
        ))
    }
}
