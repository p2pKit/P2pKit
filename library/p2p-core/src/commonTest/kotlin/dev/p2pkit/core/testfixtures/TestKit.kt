package dev.p2pkit.core.testfixtures

import dev.p2pkit.core.P2pKit
import dev.p2pkit.core.SecurityMode
import dev.p2pkit.core.dsl.P2pKitBuilder

/**
 * Standard kit-construction path for kit-level behavioral suites (fixture
 * change F6 / TST-9, decision #15a).
 *
 * Identical to [P2pKit.create] except that it enables the internal
 * [P2pKitBuilder.strictSessionInvariants] knob **before** applying [block],
 * so the kit's `SessionStore` throws [IllegalStateException] on a detected
 * bookkeeping-invariant violation instead of `logger.warn`ing into the
 * (typically NoOp) test logger. Every behavioral suite that builds kits
 * through this helper therefore doubles as an invariant net — a store
 * regression fails the suite loudly instead of passing silently.
 *
 * Production behavior is untouched: the knob is `internal`, defaults to
 * `false` (log-don't-crash), and only this fixture sets it. The
 * `KitStrictInvariantsTest` meta-test (P1-03) proves both dispositions
 * through the full builder → kit → manager → store threading.
 *
 * New kit-level suites should construct kits through this helper, not
 * through [P2pKit.create] directly. A suite that deliberately needs the
 * production warn-only disposition can set `strictSessionInvariants = false`
 * inside its [block] (and should say why in a comment).
 */
internal fun createTestKit(block: P2pKitBuilder.() -> Unit): P2pKit =
    P2pKit.create {
        strictSessionInvariants = true
        // The pre-v2 behavioral suites exercise the legacy protocol and use
        // arbitrary seeded UUID identities. Secure-v2 tests opt in through a
        // dedicated fixture with real key material and explicit authorization.
        @Suppress("DEPRECATION")
        securityMode = SecurityMode.NoneForMvp
        block()
    }
