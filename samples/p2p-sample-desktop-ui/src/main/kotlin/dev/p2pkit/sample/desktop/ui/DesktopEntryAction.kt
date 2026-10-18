package dev.p2pkit.sample.desktop.ui

internal enum class DesktopEntryAction {
    UserInterface, NativeReadback, WindowsRuntimeReadback, WindowsLoaderReadback, WindowsInstalledAdmission,
    WindowsProfileCreate, WindowsProfileReopen,
}

internal fun desktopEntryAction(arguments: Array<String>): DesktopEntryAction = when {
    arguments.isEmpty() -> DesktopEntryAction.UserInterface
    arguments.contentEquals(arrayOf("--rpc-native-readback")) -> DesktopEntryAction.NativeReadback
    arguments.contentEquals(arrayOf("--rpc-windows-runtime-readback")) -> DesktopEntryAction.WindowsRuntimeReadback
    arguments.contentEquals(arrayOf("--rpc-windows-loader-readback")) -> DesktopEntryAction.WindowsLoaderReadback
    arguments.contentEquals(arrayOf("--rpc-windows-installed-admission")) -> DesktopEntryAction.WindowsInstalledAdmission
    arguments.contentEquals(arrayOf("--rpc-windows-disposable-profile-create")) -> DesktopEntryAction.WindowsProfileCreate
    arguments.contentEquals(arrayOf("--rpc-windows-disposable-profile-reopen")) -> DesktopEntryAction.WindowsProfileReopen
    else -> throw IllegalArgumentException("Unsupported Desktop arguments")
}
