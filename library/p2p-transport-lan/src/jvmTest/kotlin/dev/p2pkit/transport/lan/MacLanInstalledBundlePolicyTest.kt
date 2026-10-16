package dev.p2pkit.transport.lan

import java.nio.file.Path
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertFalse
import kotlin.test.assertTrue

class MacLanInstalledBundlePolicyTest {
    @Test fun onlyTheExactRootAdminApplicationsDirectoryMayBeGroupWritable() {
        val applications = Path.of("/Applications")
        val bundle = applications.resolve("P2pKit Sample.app")
        assertTrue(MacLanInstalledBundle.allowedDirectory(applications, 0, 80, 0x1fd, 501, bundle))
        for (path in listOf(bundle, applications.resolve("Other"), Path.of("/Other/Applications"))) {
            assertFalse(MacLanInstalledBundle.allowedDirectory(path, 0, 80, 0x1fd, 501, bundle))
        }
        for ((owner, group, mode) in listOf(Triple(501L, 80L, 0x1fd), Triple(0L, 20L, 0x1fd),
            Triple(0L, 80L, 0x1ff), Triple(0L, 80L, 0x5fd))) {
            assertFalse(MacLanInstalledBundle.allowedDirectory(applications, owner, group, mode, 501, bundle))
        }
        assertTrue(MacLanInstalledBundle.allowedDirectory(bundle, 0, 80, 0x1ed, 501, bundle))
        assertTrue(MacLanInstalledBundle.allowedDirectory(bundle, 501, 20, 0x1c0, 501, bundle))
        assertFalse(MacLanInstalledBundle.allowedDirectory(bundle, 502, 20, 0x1ed, 501, bundle))
    }

    @Test fun actualLauncherShapeIsRequiredNotAnArbitraryPropertyOrRuntimeJava() {
        // Absolute on every JVM host; a leading slash alone is drive-relative on Windows.
        val bundle = Path.of("P2pKit Sample.app").toAbsolutePath().normalize()
        assertEquals(bundle, MacLanInstalledBundle.bundleDirectory(bundle.resolve("Contents/MacOS/P2pKit Sample")))
        for (path in listOf(bundle.resolve("Contents/runtime/Contents/Home/bin/java"),
            Path.of("/tmp/java"), Path.of("relative.app/Contents/MacOS/app"),
            bundle.resolve("Contents/MacOS/../MacOS/app"))) {
            assertFailsWith<IllegalStateException> { MacLanInstalledBundle.bundleDirectory(path) }
        }
    }

    @Test fun explicitAdHocFlagsAreParsedAsBitsAndProductionOrAmbiguousMetadataIsRejected() {
        val good = "CodeDirectory v=20400 size=100 flags=0x10002(adhoc,runtime) hashes=2+2\n" +
            "Signature=adhoc\nTeamIdentifier=not set\n"
        MacLanInstalledBundle.requireAdHoc(good)
        for (bad in listOf(good.replace("0x10002", "0x10000"), good.replace("Signature=adhoc", "Signature=invalid"),
            good.replace("not set", "PRIVATE1234"), good + "Signature=adhoc\n",
            good.replace("CodeDirectory", "Other"))) {
            assertFailsWith<IllegalStateException> { MacLanInstalledBundle.requireAdHoc(bad) }
        }
    }

    @Test fun aclListingRequiresEveryHeaderAndRejectsAllowOrUnknownEntries() {
        val header = "drwxr-xr-x+ 2 501 20 64 Oct 10 12:00 /example"
        MacLanInstalledBundle.verifyAclListing(header + "\n 0: group:everyone deny delete\n", setOf("/example"))
        for (listing in listOf("", header + "\n 0: group:everyone allow read", header + "\n malformed",
            header + "\n" + header, "drwxr-xr-x 2 501 20 64 Oct 10 12:00 /other")) {
            assertFailsWith<IllegalStateException> {
                MacLanInstalledBundle.verifyAclListing(listing, setOf("/example"))
            }
        }
    }
}
