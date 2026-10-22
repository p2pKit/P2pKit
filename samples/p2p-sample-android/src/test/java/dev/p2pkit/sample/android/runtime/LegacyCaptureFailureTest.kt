package dev.p2pkit.sample.android.runtime

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertSame

/** Pure fixed-diagnostic controls, not Android screenshot or FLAG_SECURE evidence. */
class LegacyCaptureFailureTest {
    @Test
    fun unavailableScreenshotFailsWithSpecificCodeRatherThanPassingAsSecure() {
        val failure = assertFailsWith<LegacyCaptureFailure> {
            requireLegacyCaptureValue<Any>(null, LegacyCaptureFailureCode.SCREENSHOT_UNAVAILABLE)
        }
        assertEquals(LegacyCaptureFailureCode.SCREENSHOT_UNAVAILABLE, failure.code)
    }

    @Test
    fun successfulValueIsUnchangedAndStillOwnedByCaller() {
        val bitmapBoundary = Any()
        assertSame(bitmapBoundary,
            requireLegacyCaptureValue(bitmapBoundary, LegacyCaptureFailureCode.SCREENSHOT_UNAVAILABLE))
    }

    @Test
    fun everyFailedOracleRetainsItsExactFixedCode() {
        LegacyCaptureFailureCode.entries.forEach { code ->
            val failure = assertFailsWith<IllegalStateException> { checkLegacyCapture(false, code) }
            assertEquals(code, (failure as LegacyCaptureFailure).code)
            assertEquals(code.name, failure.message)
        }
    }

    @Test
    fun successfulChecksDoNotRaiseFalseFailures() {
        LegacyCaptureFailureCode.entries.forEach { checkLegacyCapture(true, it) }
    }

    @Test
    fun absentOutputIsNotMisclassifiedAsScreenshotRefusal() {
        val failure = assertFailsWith<LegacyCaptureFailure> {
            requireLegacyCaptureValue<Any>(null, LegacyCaptureFailureCode.OUTPUT_DIRECTORY_UNAVAILABLE)
        }
        assertEquals(LegacyCaptureFailureCode.OUTPUT_DIRECTORY_UNAVAILABLE, failure.code)
    }
}
