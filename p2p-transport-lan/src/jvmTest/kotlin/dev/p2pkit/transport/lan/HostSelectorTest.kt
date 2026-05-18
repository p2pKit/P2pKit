package dev.p2pkit.transport.lan

import java.net.Inet6Address
import java.net.InetAddress
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertNotNull
import kotlin.test.assertNull
import kotlin.test.assertTrue

/**
 * Pins the routability rules for V0.4-IPV6's [selectRoutableHost]. The
 * Android-side selector in `AndroidLanDiscoveryTransport.kt` is a verbatim
 * copy of this function (commonMain cannot host `java.net.InetAddress`-
 * based helpers without a `jvmAndAndroidMain` source set); these tests
 * pin the contract for both copies.
 */
class HostSelectorTest {

    private fun ipv4(s: String) = InetAddress.getByName(s)
    private fun ipv6(s: String) = InetAddress.getByName(s)

    private fun scopedIpv6(literal: String, scopeId: Int): Inet6Address {
        val raw = InetAddress.getByName(literal).address
        return Inet6Address.getByAddress(null, raw, scopeId)
    }

    @Test
    fun emptyCandidatesReturnsNull() {
        assertNull(selectRoutableHost(emptyList()))
    }

    @Test
    fun routableIpv4IsPreferredOverEverythingElse() {
        val host = selectRoutableHost(
            listOf(
                ipv6("2001:db8::1"),               // routable IPv6 — should NOT win
                ipv4("10.0.0.5"),                  // should win
                ipv4("192.168.1.20")
            )
        )
        assertEquals("10.0.0.5", host)
    }

    @Test
    fun nonLinkLocalIpv6IsAcceptedWhenNoIpv4() {
        // Compare against the platform's own getHostAddress() rendering —
        // Java expands `::` to `:0:0:...:0:` and we must NOT post-process.
        val addr = ipv6("2001:db8::1")
        assertEquals(addr.hostAddress, selectRoutableHost(listOf(addr)))
    }

    @Test
    fun unscopedIpv6LinkLocalIsRejected() {
        // The Test 3 failure mode: fe80::... with no scope id. Java/Kotlin's
        // Socket constructor returns EINVAL on these; selector must skip.
        assertNull(selectRoutableHost(listOf(ipv6("fe80::1f:24c:c3cb:9ef2"))))
    }

    @Test
    fun scopedIpv6LinkLocalIsAcceptedAndScopePreserved() {
        val scoped = scopedIpv6("fe80::1", scopeId = 5)
        val host = selectRoutableHost(listOf(scoped))
        assertNotNull(host)
        // The selector must preserve the `%scope` suffix verbatim — no
        // hidden normalization. Compare against the platform's own
        // rendering for parity (Java expands the address into its long
        // form, e.g. `fe80:0:0:0:0:0:0:1%5`, but the `%5` survives).
        assertEquals(scoped.hostAddress, host)
        assertTrue("%" in host, "scope id must be preserved: '$host'")
    }

    @Test
    fun mixedUnscopedLinkLocalAndGlobalIpv6PicksGlobal() {
        val global = ipv6("2001:db8::42")
        val host = selectRoutableHost(
            listOf(
                ipv6("fe80::1f:24c:c3cb:9ef2"),    // rejected (unscoped link-local)
                global                             // accepted
            )
        )
        assertEquals(global.hostAddress, host)
    }

    @Test
    fun ipv4LinkLocalIsAccepted() {
        // 169.254/16 IS sometimes dialable on direct-cable / auto-config
        // segments; matches prior JVM behaviour. If hardware testing
        // reveals this should change, it's a one-line refinement.
        assertEquals("169.254.10.20", selectRoutableHost(listOf(ipv4("169.254.10.20"))))
    }

    @Test
    fun ipv4LoopbackIsRejected() {
        assertNull(selectRoutableHost(listOf(ipv4("127.0.0.1"))))
    }

    @Test
    fun ipv6LoopbackIsRejected() {
        assertNull(selectRoutableHost(listOf(ipv6("::1"))))
    }

    @Test
    fun ipv4WildcardIsRejected() {
        assertNull(selectRoutableHost(listOf(ipv4("0.0.0.0"))))
    }

    @Test
    fun ipv6WildcardIsRejected() {
        assertNull(selectRoutableHost(listOf(ipv6("::"))))
    }

    @Test
    fun loopbackPlusIpv4PicksIpv4() {
        assertEquals(
            "192.168.1.20",
            selectRoutableHost(listOf(ipv4("127.0.0.1"), ipv4("192.168.1.20")))
        )
    }

    @Test
    fun loopbackOnlyReturnsNull() {
        assertNull(selectRoutableHost(listOf(ipv4("127.0.0.1"), ipv6("::1"))))
    }

    @Test
    fun ipv4PreferredOverScopedIpv6() {
        // Even a perfectly-routable scoped IPv6 should lose to IPv4.
        val scoped = scopedIpv6("fe80::1", scopeId = 5)
        assertEquals("10.0.0.5", selectRoutableHost(listOf(scoped, ipv4("10.0.0.5"))))
    }
}
