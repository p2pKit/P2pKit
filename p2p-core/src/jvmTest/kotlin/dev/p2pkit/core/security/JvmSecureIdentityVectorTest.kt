package dev.p2pkit.core.security

import dev.p2pkit.core.AppId
import kotlin.test.Test
import kotlin.test.assertContentEquals
import kotlin.test.assertEquals

class JvmSecureIdentityVectorTest {
    private val crypto: IdentityCryptography = platformSecurityCryptography()

    @Test
    fun frozenDerivationDomainsMatchIndependentSha256Vectors() {
        val namespace = IdentityDerivation.namespace(AppId("a"), crypto)
        val publicKey = ByteArray(32)
        val fingerprintDigest = IdentityDerivation.fingerprintDigest(publicKey, crypto)

        assertEquals(
            "83a56e4fc462678d6d03a957afb7a7571115a31dd5275ba68638264142996ebb",
            namespace.storageKey
        )
        assertEquals(
            "cad8488221050ccff775eb2a8782aa51ed70d574d89f7e51b9ad2aeaff34f8d5",
            fingerprintDigest.toLowerHex()
        )
        assertEquals(
            "p2f1-zlmerarbaugm753v5mvipavkkhwxbvlu3cpx4unzvuvov7zu7dkq",
            IdentityDerivation.fingerprint(publicKey, crypto).value
        )
        assertEquals(
            "p2id2-itm6pro6jfzuwea3ieklectarwebxiejiqegwomzxtfuvtfjjnxq",
            IdentityDerivation.peerId(namespace, fingerprintDigest, crypto).value
        )
        assertEquals(
            "p2a1-6ges3ghbvk4emcsbdw5kkzbuq5tgv4jdgdtifxtkz37jstyyldka",
            IdentityDerivation.appBinding(namespace, crypto)
        )
    }

    @Test
    fun explicitProviderGeneratesCanonicalRoundTrippableX25519Keys() {
        val pair = crypto.generateX25519KeyPair()
        val privateKey = pair.privateKeyBytes()
        val storedPublic = pair.publicKeyBytes()
        try {
            val derivedPublic = crypto.deriveX25519PublicKey(privateKey)
            try {
                assertEquals(32, privateKey.size)
                assertEquals(32, storedPublic.size)
                assertContentEquals(storedPublic, derivedPublic)
            } finally {
                derivedPublic.fill(0)
            }
        } finally {
            privateKey.fill(0)
            storedPublic.fill(0)
            pair.clearPrivate()
        }
    }
}
