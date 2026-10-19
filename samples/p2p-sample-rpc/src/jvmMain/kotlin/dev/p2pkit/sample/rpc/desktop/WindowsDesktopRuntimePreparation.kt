package dev.p2pkit.sample.rpc.desktop

import java.awt.Toolkit
import java.net.NetworkInterface

/**
 * The installed Desktop diagnostic must initialize its real Desktop runtime before native admission,
 * just as the UI path does. This is conditional on the independently admitted installed JDK/OS/startup;
 * a toolkit instance is never installation authority or permission to load the profile DLL.
 */
internal object WindowsDesktopRuntimePreparation {
    private var attempted = false
    private var retainedToolkit: Toolkit? = null
    private var retainedFailure: Throwable? = null
    private var completed = false

    @Synchronized
    fun prepare() {
        retainedFailure?.let { throw it }
        if (completed) {
            checkNotNull(retainedToolkit)
            return
        }
        check(!attempted) { "Desktop runtime preparation is already in progress" }
        attempted = true // Retain the attempt before class initialization or native toolkit effects.
        try {
            check(Runtime.version().feature() == 21 && System.getProperty("os.name").startsWith("Windows")) {
                "Installed Desktop preparation requires the Windows JDK21 runtime"
            }
            requireOriginalDesktopClass(Toolkit::class.java, "java.awt.Toolkit")
            val toolkit = Toolkit.getDefaultToolkit()
            retainedToolkit = toolkit // Preserve the actual runtime owner even if its type is refused.
            requireOriginalDesktopClass(toolkit.javaClass, "sun.awt.windows.WToolkit")
            // Initialize the actual pinned JDK's networking library before observing already-loaded
            // iphlpapi. This performs no socket creation and supplies no native-library trust authority.
            check(NetworkInterface::class.java.classLoader == null &&
                NetworkInterface::class.java.module === Any::class.java.module)
            checkNotNull(NetworkInterface.getNetworkInterfaces())
            completed = true
        } catch (original: Throwable) {
            retainedFailure = original
            throw original
        }
    }
}

/** Exact boot-class identity check; no class name alone or caller-supplied object admits a runtime. */
internal fun requireOriginalDesktopClass(type: Class<*>, expected: String) {
    val boot = ModuleLayer.boot()
    val module = boot.findModule("java.desktop").orElse(null)
    val resolved = boot.configuration().findModule("java.desktop").orElse(null)
    check(type.name == expected && type.classLoader == null && module != null && type.module === module &&
        module.isNamed && module.layer === boot && !module.descriptor.isAutomatic &&
        resolved?.reference()?.location()?.orElse(null)?.toString() == "jrt:/java.desktop") {
        "Desktop runtime class is not from the original boot image"
    }
}
