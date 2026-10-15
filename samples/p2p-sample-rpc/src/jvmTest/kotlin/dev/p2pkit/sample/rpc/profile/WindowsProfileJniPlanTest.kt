package dev.p2pkit.sample.rpc.profile

import java.security.MessageDigest
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertFalse
import kotlin.test.assertNotSame
import kotlin.test.assertSame

/** Inert JNI registration data. Does not load a native library, register methods or establish module custody. */
class WindowsProfileJniPlanTest {
    @Test fun allExactCompiledDescriptorsBindToOriginalExportAddresses() {
        val image = image()
        val plan = prepare(image)
        assertSame(WindowsProfileCustodyJni::class.java, plan.declaringClass)
        assertEquals(23, plan.methods.size)
        // The separate custody contract test pins all 23 descriptors independently of both these implementations.
        val compiled = plan.declaringClass.declaredMethods.associate { method ->
            method.name to method.parameterTypes.joinToString("", prefix = "(", postfix = ")") {
                it.descriptorString()
            } + method.returnType.descriptorString()
        }
        assertEquals(compiled, plan.methods.associate { it.name to it.descriptor })
        val exports = image.namedExports.associateBy { it.name }
        assertEquals("pwp_jni_register_once", plan.registrar.exportName)
        assertEquals(BASE + exports.getValue(plan.registrar.exportName).functionRva, plan.registrar.address)
        assertEquals(1, plan.registrar.version)
        assertEquals(23, plan.registrar.methodCount)
        assertEquals(32, plan.registrar.reportBytes)
        assertFalse(plan.methods.any { it.exportName == plan.registrar.exportName })
        for (method in plan.methods) {
            assertEquals(PREFIX + method.name, method.exportName)
            assertEquals(BASE + exports.getValue(method.exportName).functionRva, method.address)
        }
        assertFalse(WindowsProfileAvailability.IMPLEMENTED)
        assertFalse(WindowsProfileAvailability.QUALIFIED)
    }

    @Test fun planOrderAndDescriptorsDoNotDependOnLookupOrderOrPreferredBase() {
        val image = image()
        val normal = prepare(image)
        val reversed = prepare(image, addresses(image).reversed())
        assertEquals(normal.methods, reversed.methods)
        assertEquals(normal.registrar, reversed.registrar)
        val otherBase = 0x7ff900000000L
        val relocated = WindowsProfileJniPlan.prepare(
            WindowsProfileCustodyJni::class.java, image, otherBase, image.imageBytes, addresses(image, otherBase),
        )
        assertEquals(normal.methods.map { it.copy(address = it.address - BASE + otherBase) }, relocated.methods)
        assertEquals(normal.registrar.copy(address = normal.registrar.address - BASE + otherBase), relocated.registrar)
    }

    @Test fun immutableBindingsDoNotRereadMutableInputLists() {
        val image = image()
        val exports = image.namedExports.toMutableList()
        val addresses = addresses(image).toMutableList()
        val plan = prepare(image.copy(namedExports = exports), addresses)
        val original = plan.methods.toList()
        val registrar = plan.registrar
        exports.clear()
        addresses.clear()
        assertEquals(original, plan.methods)
        assertEquals(registrar, plan.registrar)
        assertFailsWith<UnsupportedOperationException> { (plan.methods as MutableList).clear() }
    }

    @Test fun eachBoundedObservationIsReadOnlyOnceBeforeVerification() {
        val image = image()
        val original = addresses(image)
        val reads = IntArray(24)
        val exportReads = IntArray(24)
        val changing = object : AbstractList<WindowsProfileExportAddresses.ResolvedExport>() {
            override val size = 24
            override fun get(index: Int) = original[index].also {
                check(++reads[index] == 1) { "Resolution reread after verification" }
            }
        }
        val changingExports = object : AbstractList<WindowsProfilePeImage.NamedExport>() {
            override val size = 24
            override fun get(index: Int) = image.namedExports[index].also {
                check(++exportReads[index] == 1) { "Pinned binding reread after verification" }
            }
        }
        assertEquals(prepare(image).methods, prepare(image.copy(namedExports = changingExports), changing).methods)
        assertEquals(List(24) { 1 }, reads.toList())
        assertEquals(List(24) { 1 }, exportReads.toList())
    }

    @Test fun incompleteDuplicateUnknownAndWrongFunctionBindingsRefuse() {
        val image = image()
        val original = addresses(image)
        val variants = listOf(
            original.dropLast(1), original + original.first(),
            original.toMutableList().apply { this[1] = first() },
            original.toMutableList().apply { this[0] = first().copy(name = "Java_unknown") },
            original.toMutableList().apply { this[0] = first().copy(address = first().address + 1) },
        )
        for (candidate in variants) assertFailsWith<IllegalArgumentException> { prepare(image, candidate) }
    }

    @Test fun registrarMustHaveItsOwnExactOriginalNameAndAddressBeforeAnyBindingIsReturned() {
        val image = image()
        val original = addresses(image)
        val registrar = original.single { it.name == "pwp_jni_register_once" }
        val method = original.first { it.name != registrar.name }
        val variants = listOf(
            original.filterNot { it.name == registrar.name },
            original.map { if (it == registrar) it.copy(name = "pwp_jni_register_other") else it },
            original.map { if (it == registrar) it.copy(address = registrar.address + 1) else it },
            original.map {
                when (it.name) {
                    registrar.name -> it.copy(address = method.address)
                    method.name -> it.copy(address = registrar.address)
                    else -> it
                }
            },
        )
        for (candidate in variants) assertFailsWith<IllegalArgumentException> { prepare(image, candidate) }
        val withoutRegistrar = image.copy(namedExports = image.namedExports.filterNot { it.name == registrar.name })
        assertFailsWith<IllegalArgumentException> { prepare(withoutRegistrar, original) }
    }

    @Test fun oversizedInventoriesRefuseBeforeReadingAnyEntry() {
        val image = image()
        val oversized = object : AbstractList<WindowsProfileExportAddresses.ResolvedExport>() {
            override val size = Int.MAX_VALUE
            override fun get(index: Int): WindowsProfileExportAddresses.ResolvedExport =
                error("Oversized inventory must not be consumed")
        }
        assertFailsWith<IllegalArgumentException> { prepare(image, oversized) }
    }

    @Test fun mismatchedSizeOrBaseCannotProduceAPlan() {
        val image = image()
        for ((base, size) in listOf(0L to image.imageBytes, BASE to image.imageBytes + 1)) {
            assertFailsWith<IllegalArgumentException> {
                WindowsProfileJniPlan.prepare(WindowsProfileCustodyJni::class.java, image, base, size, addresses(image))
            }
        }
    }

    @Test fun unrelatedDeclaringClassRefusesBeforeInspectingExportEntries() {
        val image = image()
        assertFailsWith<IllegalArgumentException> {
            WindowsProfileJniPlan.prepare(String::class.java, image, BASE, image.imageBytes, emptyList())
        }
    }

    @Test fun identicalClassBytesInAnotherLoaderAreNotTheOriginalDeclaringClass() {
        val original = WindowsProfileCustodyJni::class.java
        val resource = "/" + original.name.replace('.', '/') + ".class"
        val bytes = original.getResourceAsStream(resource)!!.use { it.readBytes() }
        val loader = object : ClassLoader(original.classLoader) {
            fun duplicate(): Class<*> = defineClass(original.name, bytes, 0, bytes.size)
        }
        val duplicate = loader.duplicate()
        assertEquals(original.name, duplicate.name)
        assertNotSame(original, duplicate)
        val image = image()
        assertFailsWith<IllegalArgumentException> {
            WindowsProfileJniPlan.prepare(duplicate, image, BASE, image.imageBytes, addresses(image))
        }
    }

    @Test fun applicationLoaderCheckUsesTheActualJvmClassRelationship() {
        val plan = prepare(image())
        if (plan.declaringClass.classLoader === ClassLoader.getSystemClassLoader()) {
            plan.requireApplicationClassLoader()
        } else {
            // Gradle's isolated test loader is not the packaged application's system classloader.
            assertFailsWith<IllegalStateException> { plan.requireApplicationClassLoader() }
        }
        assertFalse(WindowsProfileAvailability.IMPLEMENTED)
    }

    private fun prepare(
        image: WindowsProfileByteManifest.ByteAuthorization,
        resolved: List<WindowsProfileExportAddresses.ResolvedExport> = addresses(image),
    ) = WindowsProfileJniPlan.prepare(WindowsProfileCustodyJni::class.java, image, BASE, image.imageBytes, resolved)

    private fun addresses(image: WindowsProfileByteManifest.ByteAuthorization, base: Long = BASE) =
        image.namedExports.map { WindowsProfileExportAddresses.ResolvedExport(it.name, base + it.functionRva) }

    private fun image(): WindowsProfileByteManifest.ByteAuthorization {
        val bytes = WindowsProfilePeFixture.create()
        val source = "a".repeat(40)
        val tree = "b".repeat(40)
        val manifest = WindowsProfileByteManifest.produce(source, tree, true, bytes)
        val hash = MessageDigest.getInstance("SHA-256").digest(manifest).joinToString("") { "%02x".format(it) }
        return WindowsProfileByteManifest.authorize(
            manifest, bytes, WindowsProfileByteManifest.Authority(hash, source, tree),
        )
    }

    private companion object {
        const val BASE = 0x180000000L
        const val PREFIX = "Java_dev_p2pkit_sample_rpc_profile_WindowsProfileCustodyJni_"
    }
}
