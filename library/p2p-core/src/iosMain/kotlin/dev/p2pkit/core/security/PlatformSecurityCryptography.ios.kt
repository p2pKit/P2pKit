package dev.p2pkit.core.security

import dev.whyoleg.cryptography.CryptographyProvider
import dev.whyoleg.cryptography.providers.cryptokit.CryptoKit

private val iosSecurityCryptography: PlatformSecurityCryptography by lazy {
    ProviderSecurityCryptography(CryptographyProvider.CryptoKit)
}

internal actual fun platformSecurityCryptography(): PlatformSecurityCryptography =
    iosSecurityCryptography
