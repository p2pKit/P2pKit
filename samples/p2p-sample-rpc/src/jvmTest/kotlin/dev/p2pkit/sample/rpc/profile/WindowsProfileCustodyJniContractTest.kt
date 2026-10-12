package dev.p2pkit.sample.rpc.profile

import java.lang.reflect.Method
import java.lang.reflect.Modifier
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertTrue

/** Compiled JVM descriptors only: reflection never invokes JNI or loads the unqualified Windows component. */
class WindowsProfileCustodyJniContractTest {
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
        "discardStage" to "(J)V",
        "prepareRecord" to "(JLjava/lang/String;[B)J",
        "renameCandidate" to "(JLjava/lang/String;)V",
        "requestExpectedFileDeletion" to "(JLjava/lang/String;[J)V",
        "close" to "(J)V",
        "syncDirectory" to "(J)V",
        "replaceCandidate" to "(JLjava/lang/String;)V",
    )

    private val methods: List<Method> get() = WindowsProfileCustodyJni::class.java.declaredMethods.toList()

    @Test
    fun compiledMethodsMatchEveryExactNativeNameAndDescriptorWithoutOverloads() {
        val compiled = methods
        assertEquals(21, compiled.size)
        assertEquals(compiled.size, compiled.map { it.name }.toSet().size)
        assertEquals(descriptors, compiled.associate { method -> method.name to method.descriptor() })
    }

    @Test
    fun everyEntryRemainsAnInstanceNativeMethodWithNoManagedOrStaticFallback() {
        methods.forEach { method ->
            assertTrue(Modifier.isPublic(method.modifiers), method.name)
            assertTrue(Modifier.isFinal(method.modifiers), method.name)
            assertTrue(Modifier.isNative(method.modifiers), method.name)
            assertFalse(Modifier.isStatic(method.modifiers), method.name)
            assertFalse(Modifier.isSynchronized(method.modifiers), method.name)
            assertFalse(method.isSynthetic, method.name)
            assertFalse(method.isBridge, method.name)
        }
    }

    @Test
    fun structuralPeExportPolicyMatchesCompiledJniMethodsButDoesNotEnableTheProvider() {
        val prefix = "Java_dev_p2pkit_sample_rpc_profile_WindowsProfileCustodyJni_"
        assertEquals(descriptors.keys.mapTo(linkedSetOf()) { prefix + it }, WindowsProfilePeImage.expectedExports)
        assertEquals(methods.mapTo(linkedSetOf()) { prefix + it.name }, WindowsProfilePeImage.expectedExports)
        assertEquals(10, WindowsProfilePeImage.ABI)
        assertFalse(WindowsProfileAvailability.IMPLEMENTED)
        assertFalse(WindowsProfileAvailability.QUALIFIED)
    }

    private fun Method.descriptor(): String =
        parameterTypes.joinToString("", prefix = "(", postfix = ")") { it.descriptorString() } +
            returnType.descriptorString()
}
