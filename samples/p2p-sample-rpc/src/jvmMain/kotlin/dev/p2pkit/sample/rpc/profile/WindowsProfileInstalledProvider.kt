package dev.p2pkit.sample.rpc.profile

import java.lang.reflect.InvocationTargetException
import java.lang.reflect.Method
import java.lang.reflect.Modifier

/**
 * Fixed Java-17 application connection to the separately packaged, original boot-module loader.
 * No supplied path, native calls, classloader, owner token or capability flag grants admission here.
 * The loader's normal return owns the genuine installed production
 * image and original JNI registration permanently; the development deny-storage DLL is not a provider.
 */
internal object WindowsProfileInstalledProvider {
    /** A closed, before-effects observation, not a classification inferred from exception text. */
    class Unavailable private constructor(original: Throwable?) : IllegalStateException(
        "Windows protected profile unavailable: installed provider admission is not available", original,
    ) {
        companion object {
            internal fun beforeEffects(original: Throwable? = null): Unavailable = Unavailable(original)
        }
    }

    private class Entry(val method: Method, val unavailable: Class<*>)

    /** Before-effects consistency check only; no method invocation, provider or native-load authority. */
    fun requireInstalledEntry() { fixedEntry() }

    /** Only WindowsProfileFiles' zero-argument production factory uses this entry. No validation overload. */
    fun acquireNative(): WindowsProfileNativeApi {
        val entry = fixedEntry()
        try {
            // The exact loader owns every resource even when invocation fails before producing a session.
            // Do not retry, invoke a substitute, unload, or downgrade an arbitrary Throwable to no-effects.
            entry.method.invoke(null)
        } catch (failure: InvocationTargetException) {
            val original = failure.targetException
            if (original.javaClass === entry.unavailable) throw Unavailable.beforeEffects(original)
            throw original
        }
        // This class is private and is constructed only after the fixed production entry returns normally.
        // Existing process roots retain the actual image/JVM/JNI ownership beyond any profile Stop/close.
        return CompleteAdapter()
    }

    private fun fixedEntry(): Entry {
        try {
            val boot = ModuleLayer.boot()
            val module = boot.findModule(MODULE).orElseThrow { Unavailable.beforeEffects() }
            val system = ClassLoader.getSystemClassLoader()
            check(system != null && module.isNamed && module.layer === boot && !module.descriptor.isAutomatic &&
                module.classLoader === system)
            val loader = checkNotNull(Class.forName(module, LOADER))
            val unavailable = checkNotNull(Class.forName(module, "$LOADER\$Unavailable"))
            check(loader.module === module && loader.classLoader === system && Modifier.isPublic(loader.modifiers) &&
                Modifier.isFinal(loader.modifiers) && !loader.isInterface)
            check(unavailable.module === module && unavailable.classLoader === system &&
                unavailable.declaringClass === loader && Modifier.isPublic(unavailable.modifiers) &&
                Modifier.isFinal(unavailable.modifiers) &&
                unavailable.superclass === UnsupportedOperationException::class.java)
            val constructors = unavailable.declaredConstructors
            check(constructors.size == 1 && constructors.single().parameterCount == 0 &&
                Modifier.isPrivate(constructors.single().modifiers))
            val method = loader.getDeclaredMethod("openInstalledProvider")
            check(method.declaringClass === loader && method.returnType === Void.TYPE &&
                Modifier.isPublic(method.modifiers) && Modifier.isStatic(method.modifiers) &&
                !method.isBridge && !method.isSynthetic)
            // Exact system-loaded application declarations, without initializing the JNI singleton.
            // This is a consistency requirement, not proof of their package/runtime provenance.
            val application = system.unnamedModule
            for (type in arrayOf(WindowsProfileInstalledProvider::class.java, WindowsProfileFiles::class.java,
                WindowsProfileCustodyBridge::class.java, WindowsProfileCustodyJni::class.java)) {
                check(type.classLoader === system && type.module === application)
            }
            return Entry(method, unavailable)
        } catch (failure: Unavailable) {
            throw failure
        } catch (failure: Throwable) {
            // No method invocation, JNI singleton initialization or storage acquisition occurred here.
            throw Unavailable.beforeEffects(failure)
        }
    }

    /**
     * Separately versioned managed composition, not a change to the actual native ABI/capabilities.
     * Root/metadata/locks/atomic create/replace/durable namespace/cleanup use the original custody bridge.
     * Native ABI13/0x43 is rechecked before reporting this contract and before every storage entry.
     * Qualification is not a capability bit; real productive storage still requires its own evidence.
     */
    private class CompleteAdapter private constructor(
        private val custody: WindowsProfileCustodyBridge,
    ) : WindowsProfileNativeApi by custody {
        constructor() : this(WindowsProfileCustodyBridge())

        override fun abi(): Int {
            requireRawContract()
            return 1
        }

        override fun capabilities(): Long {
            requireRawContract()
            return 0x7fL
        }

        private fun requireRawContract() {
            check(custody.abi() == WindowsProfilePeImage.ABI && custody.capabilities() == 0x43L) {
                "Unsupported original Windows custody contract"
            }
        }
    }

    private const val MODULE = "dev.p2pkit.rpc.windows.loader"
    private const val LOADER = "$MODULE.WindowsLoader"
}
