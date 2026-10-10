package dev.p2pkit.sample.desktop.ui

internal enum class DesktopEntryAction { UserInterface, NativeReadback }

internal fun desktopEntryAction(arguments: Array<String>): DesktopEntryAction = when {
    arguments.isEmpty() -> DesktopEntryAction.UserInterface
    arguments.contentEquals(arrayOf("--rpc-native-readback")) -> DesktopEntryAction.NativeReadback
    else -> throw IllegalArgumentException("Unsupported Desktop arguments")
}
