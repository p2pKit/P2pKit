package dev.p2pkit.sample.desktop.ui

internal enum class DesktopEntryAction { UserInterface, NativeReadback, WindowsRuntimeReadback, WindowsLoaderReadback }

internal fun desktopEntryAction(arguments: Array<String>): DesktopEntryAction = when {
    arguments.isEmpty() -> DesktopEntryAction.UserInterface
    arguments.contentEquals(arrayOf("--rpc-native-readback")) -> DesktopEntryAction.NativeReadback
    arguments.contentEquals(arrayOf("--rpc-windows-runtime-readback")) -> DesktopEntryAction.WindowsRuntimeReadback
    arguments.contentEquals(arrayOf("--rpc-windows-loader-readback")) -> DesktopEntryAction.WindowsLoaderReadback
    else -> throw IllegalArgumentException("Unsupported Desktop arguments")
}
