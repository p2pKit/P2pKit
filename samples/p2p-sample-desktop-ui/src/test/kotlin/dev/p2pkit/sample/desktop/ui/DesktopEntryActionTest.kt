package dev.p2pkit.sample.desktop.ui

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith

class DesktopEntryActionTest {
    @Test fun installedNativeDiagnosticRequiresItsSingleExactExplicitArgument() {
        assertEquals(DesktopEntryAction.WindowsInstalledAdmission,
            desktopEntryAction(arrayOf("--rpc-windows-installed-admission")))
        for (arguments in listOf(arrayOf("--rpc-windows-installed-admission", "extra"),
            arrayOf("--rpc-windows-installed-admission=1"), arrayOf("--rpc-windows-installed-admission "),
            arrayOf("--RPC-WINDOWS-INSTALLED-ADMISSION"),
            arrayOf("--rpc-windows-loader-readback", "--rpc-windows-installed-admission"))) {
            assertFailsWith<IllegalArgumentException> { desktopEntryAction(arguments) }
        }
    }

    @Test fun ordinaryLaunchKeepsUiAndOnlyExactDiagnosticArgumentSelectsReadback() {
        assertEquals(DesktopEntryAction.UserInterface, desktopEntryAction(emptyArray()))
        assertEquals(DesktopEntryAction.NativeReadback, desktopEntryAction(arrayOf("--rpc-native-readback")))
        assertEquals(DesktopEntryAction.WindowsRuntimeReadback,
            desktopEntryAction(arrayOf("--rpc-windows-runtime-readback")))
        assertEquals(DesktopEntryAction.WindowsLoaderReadback,
            desktopEntryAction(arrayOf("--rpc-windows-loader-readback")))
        for (arguments in listOf(arrayOf(""), arrayOf("--rpc-native-readback", "extra"),
            arrayOf("--rpc-native-readback=1"), arrayOf("--rpc-native-readback "), arrayOf("--host"),
            arrayOf("--rpc-windows-runtime-readback", "extra"), arrayOf("--rpc-windows-runtime-readback=1"),
            arrayOf("--rpc-windows-runtime-readback "), arrayOf("--RPC-WINDOWS-RUNTIME-READBACK"),
            arrayOf("--rpc-windows-loader-readback", "extra"), arrayOf("--rpc-windows-loader-readback=1"),
            arrayOf("--rpc-windows-loader-readback "), arrayOf("--RPC-WINDOWS-LOADER-READBACK"))) {
            assertFailsWith<IllegalArgumentException> { desktopEntryAction(arguments) }
        }
    }
}
