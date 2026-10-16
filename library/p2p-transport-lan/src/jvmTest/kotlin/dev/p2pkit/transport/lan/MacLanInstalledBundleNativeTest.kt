package dev.p2pkit.transport.lan

import java.net.URL
import java.nio.file.Files
import java.nio.file.Path
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith

/** Explicit Mac fixture suite: never run by portable check, never skips missing fixtures, never loads native code. */
class MacLanInstalledBundleNativeTest {
    private val root: Path get() = Path.of(checkNotNull(System.getProperty("dev.p2pkit.test.macos.bundleFixtures")))
    private val source = "1".repeat(40)

    private fun verify(name: String): MacLanArtifact {
        val bundle = root.resolve("$name/P2pKit Native Fixture.app")
        val executable = bundle.resolve("Contents/MacOS/P2pKitNativeFixture")
        val native = bundle.resolve(MacLanInstalledBundle.NATIVE_RELATIVE)
        val jar = bundle.resolve("Contents/app/p2pkit-macos-tcp-manifest.jar")
        val trusted = Files.readAllBytes(root.resolve("trusted.properties"))
        return MacLanInstalledBundle.verify(executable,
            bundle.resolve("Contents/app/transport-fixture.jar").toUri().toURL(),
            URL("jar:${jar.toUri()}!/${MacLanNativeLoader.RESOURCE}"), trusted, source).also {
            assertEquals(native.resolve("libp2pkit_lan_socket.dylib"), it.library)
        }
    }

    @Test fun signedReadOnlyPublicFilesPassOnlyTheInstalledDevelopmentPolicy() {
        assertEquals(source, verify("good").source)
        val native = root.resolve("good/P2pKit Native Fixture.app").resolve(MacLanInstalledBundle.NATIVE_RELATIVE)
        assertFailsWith<IllegalStateException> {
            MacLanArtifact.verify(native, Files.readAllBytes(root.resolve("trusted.properties")), source)
        }
    }

    @Test fun modifiedNativeAndManifestAndResourceSealAreRejected() {
        for (name in listOf("changed-native", "changed-manifest", "changed-resource", "unsigned")) {
            assertFailsWith<IllegalStateException>(name) { verify(name) }
        }
    }

    @Test fun linksPermissionsAndAllowAclsAreRejectedWithoutNativeExecution() {
        for (name in listOf("symlink", "hardlink", "writable-file", "writable-directory", "allow-acl")) {
            assertFailsWith<IllegalStateException>(name) { verify(name) }
        }
    }
}
