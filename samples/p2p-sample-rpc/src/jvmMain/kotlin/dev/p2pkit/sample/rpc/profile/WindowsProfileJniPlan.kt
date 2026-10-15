package dev.p2pkit.sample.rpc.profile

import java.lang.reflect.Modifier
import java.util.Collections

/**
 * Fixed JNI registration data, not a loader, registration attempt, module owner or provider authority.
 * The later admitted loader must retain the original module and exact class through process termination,
 * including partial RegisterNatives failure. It must never retry, unregister or unload after an attempt.
 * Preparing this inert plan does not establish installed custody, runtime identity or classloader admission.
 */
internal class WindowsProfileJniPlan private constructor(
    val declaringClass: Class<*>,
    val methods: List<Binding>,
    val registrar: RegistrarBinding,
) {
    data class Binding(val name: String, val descriptor: String, val exportName: String, val address: Long)
    /** Separate post-admission C interface, never an extra Java native method or execution authority. */
    data class RegistrarBinding(val exportName: String, val address: Long) {
        val version: Int get() = 1
        val methodCount: Int get() = 23
        val reportBytes: Int get() = 32
    }

    /**
     * Maintained application only: incidental FFM caller/FindClass context is not declaring-class identity.
     * This checks the actual JVM relationship, not independently trusted packaged runtime provenance.
     * Other consumer classloaders require an explicit separate contract; there is no fallback lookup.
     */
    fun requireApplicationClassLoader() {
        val system = ClassLoader.getSystemClassLoader()
        check(system != null && declaringClass.classLoader === system &&
            Class.forName(declaringClass.name, false, system) === declaringClass) {
            "Windows JNI declaring class is not the maintained application class"
        }
    }

    companion object {
        private const val PREFIX = "Java_dev_p2pkit_sample_rpc_profile_WindowsProfileCustodyJni_"
        private val descriptors = mapOf(
            "abi" to "()I",
            "capabilities" to "()J",
            "openRoot" to "()J",
            "child" to "(JLjava/lang/String;)J",
            "createChildDirectory" to "(JLjava/lang/String;)J",
            "identity" to "(J)[J",
            "fileIdentity" to "(JLjava/lang/String;)[J",
            "exists" to "(JLjava/lang/String;)Z",
            "names" to "(J)[Ljava/lang/String;",
            "read" to "(JLjava/lang/String;I)[B",
            "lockExisting" to "(JLjava/lang/String;)J",
            "createProfileLock" to "(J)J",
            "createVaultLock" to "(J)J",
            "stageRecord" to "(JLjava/lang/String;[B)J",
            "prepareRecord" to "(JLjava/lang/String;[B)J",
            "writeRecord" to "(JLjava/lang/String;Ljava/lang/String;[BZ)V",
            "renameCandidate" to "(JLjava/lang/String;)V",
            "replaceCandidate" to "(JLjava/lang/String;)V",
            "syncDirectory" to "(J)V",
            "discardStage" to "(J)V",
            "requestExpectedFileDeletion" to "(JLjava/lang/String;[J)V",
            "deleteRecord" to "(JLjava/lang/String;[J)V",
            "close" to "(J)V",
        )

        fun prepare(
            declaringClass: Class<*>,
            image: WindowsProfileByteManifest.ByteAuthorization,
            moduleBase: Long,
            mappedImageBytes: Long,
            resolved: List<WindowsProfileExportAddresses.ResolvedExport>,
        ): WindowsProfileJniPlan {
            require(declaringClass === WindowsProfileCustodyJni::class.java) {
                "Windows JNI declaring class identity differs"
            }
            val compiled = declaringClass.declaredMethods
            require(compiled.size == descriptors.size && compiled.map { it.name }.toSet().size == compiled.size) {
                "Windows JNI compiled method inventory differs"
            }
            for (method in compiled) {
                val descriptor = method.parameterTypes.joinToString("", prefix = "(", postfix = ")") {
                    it.descriptorString()
                } + method.returnType.descriptorString()
                require(method.modifiers == (Modifier.PUBLIC or Modifier.FINAL or Modifier.NATIVE) &&
                    !method.isBridge && !method.isSynthetic && descriptors[method.name] == descriptor) {
                    "Windows JNI compiled method contract differs"
                }
            }
            require(descriptors.keys.mapTo(linkedSetOf()) { PREFIX + it } == WindowsProfilePeImage.expectedJniExports)
            val count = WindowsProfilePeImage.expectedExports.size
            require(image.namedExports.size == count && resolved.size == count) {
                "Windows JNI/registrar export observations are incomplete"
            }
            // Bounded private snapshots: validate and consume the SAME values, not a mutable list reread
            // after verification. These data classes contain only immutable strings/numbers.
            val exports = List(count) { image.namedExports[it] }
            val addresses = List(count) { resolved[it] }
            WindowsProfileExportAddresses.verify(
                image.copy(namedExports = exports), moduleBase, mappedImageBytes, addresses,
            )
            val byName = addresses.associate { it.name to it.address }
            val bindings = descriptors.map { (name, descriptor) ->
                Binding(name, descriptor, PREFIX + name, byName.getValue(PREFIX + name))
            }
            val registrar = WindowsProfilePeImage.REGISTRATION_EXPORT
            return WindowsProfileJniPlan(declaringClass, Collections.unmodifiableList(bindings),
                RegistrarBinding(registrar, byName.getValue(registrar)))
        }
    }
}
