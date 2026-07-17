package dev.p2pkit.core.security

import dev.whyoleg.cryptography.CryptographyProvider
import dev.whyoleg.cryptography.providers.jdk.JDK
import org.bouncycastle.jce.provider.BouncyCastleProvider

private val androidSecurityCryptography: PlatformSecurityCryptography by lazy {
    ProviderSecurityCryptography(
        CryptographyProvider.JDK(BouncyCastleProvider()),
    )
}

internal actual fun platformSecurityCryptography(): PlatformSecurityCryptography =
    androidSecurityCryptography
