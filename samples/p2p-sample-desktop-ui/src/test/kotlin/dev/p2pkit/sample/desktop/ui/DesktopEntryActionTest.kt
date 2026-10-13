package dev.p2pkit.sample.desktop.ui

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith

class DesktopEntryActionTest {
    @Test fun ordinaryLaunchKeepsUiAndOnlyExactDiagnosticArgumentSelectsReadback() {
        assertEquals(DesktopEntryAction.UserInterface, desktopEntryAction(emptyArray()))
        assertEquals(DesktopEntryAction.NativeReadback, desktopEntryAction(arrayOf("--rpc-native-readback")))
        assertEquals(DesktopEntryAction.WindowsRuntimeReadback,
            desktopEntryAction(arrayOf("--rpc-windows-runtime-readback")))
        for (arguments in listOf(arrayOf(""), arrayOf("--rpc-native-readback", "extra"),
            arrayOf("--rpc-native-readback=1"), arrayOf("--rpc-native-readback "), arrayOf("--host"),
            arrayOf("--rpc-windows-runtime-readback", "extra"), arrayOf("--rpc-windows-runtime-readback=1"),
            arrayOf("--rpc-windows-runtime-readback "), arrayOf("--RPC-WINDOWS-RUNTIME-READBACK"))) {
            assertFailsWith<IllegalArgumentException> { desktopEntryAction(arguments) }
        }
    }
}
