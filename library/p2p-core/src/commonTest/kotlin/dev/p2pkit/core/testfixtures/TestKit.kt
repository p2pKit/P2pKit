package dev.p2pkit.core.testfixtures

import dev.p2pkit.core.P2pKit
import dev.p2pkit.core.SecurityMode
import dev.p2pkit.core.dsl.P2pKitBuilder

/**
 * **Legacy plaintext-v1** kit fixture for the pre-v2 behavioral suites.
 * It deliberately diverges from the production authenticated-v2 default.
 * New secure lifecycle/session tests should use [createSecureTestKit] with
 * real key material and an explicit authorization policy instead.
 *
 * Selects [SecurityMode.NoneForMvp] and enables the internal
 * [P2pKitBuilder.strictSessionInvariants] knob **before** applying [block],
 * so the kit's `SessionStore` throws [IllegalStateException] on a detected
 * bookkeeping-invariant violation instead of `logger.warn`ing into the
 * (typically NoOp) test logger. Every behavioral suite that builds kits
 * through this helper therefore doubles as an invariant net — a store
 * regression fails the suite loudly instead of passing silently.
 *
 * Production behavior is untouched: the knob is `internal`, defaults to
 * `false` (log-don't-crash), and both test fixtures enable it. The
 * `KitStrictInvariantsTest` meta-test (P1-03) proves both dispositions
 * through the full builder → kit → manager → store threading.
 *
 * Legacy tests may override `securityMode` inside [block], but must then
 * supply a secure store and authorization; prefer the secure sibling.
 * A test of production warn-only disposition can deliberately set
 * `strictSessionInvariants = false` inside [block] and explain why.
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
