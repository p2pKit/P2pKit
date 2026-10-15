package dev.p2pkit.sample.rpc.desktop

import dev.p2pkit.sample.rpc.RpcPhoneBuildStamp
import dev.p2pkit.transport.lan.OrganizationLan

/** Fixed internal-ABI diagnostic, not an RPC role, public library API or network qualification. */
public object RpcDesktopNativeReadback {
    public fun run(): String = checkedNativeReadback(
        RpcPhoneBuildStamp.SOURCE_COMMIT, RpcPhoneBuildStamp.SOURCE_CLEAN,
        System.getProperty("os.name"), System.getProperty("os.arch"),
        System.getProperty("dev.p2pkit.lan.macos.nativeDir"),
        System.getProperty("dev.p2pkit.lan.macos.installedPolicy"),
        ::loadInstalledNative,
    )

    private fun loadInstalledNative(): String {
        // Reuse the diagnostic's fixed ABI, not reflection selected by arguments or a classpath override.
        // The real loader still verifies the actual executable, bundle, source, bytes, signatures and ABI.
        val loader = Class.forName("dev.p2pkit.transport.lan.MacLanNativeLoader")
        val binding = checkNotNull(loader.getMethod("configuredBinding", OrganizationLan::class.java).invoke(
            loader.getField("INSTANCE").get(null), OrganizationLan(listOf("10.0.0.0/8"), "en0", "10.1.2.3"),
        ))
        return AutoCloseable { binding.javaClass.getMethod("retire").invoke(binding) }.use {
            // Never activate the binding or invoke socket, listener, target, discovery or a core/identity factory.
            val native = Class.forName("dev.p2pkit.transport.lan.MacLanNative")
            native.getMethod("source").invoke(native.getField("INSTANCE").get(null)) as String
        }
    }
}

internal fun checkedNativeReadback(
    source: String, clean: Boolean, os: String, architecture: String,
    nativeDirectory: String?, installedPolicy: String?, load: () -> String,
): String {
    check(clean && source.matches(Regex("[a-f0-9]{40}")))
    check(os == "Mac OS X" && architecture in setOf("arm64", "aarch64"))
    check(nativeDirectory == null && installedPolicy == "development-adhoc-v1")
    val actual = load()
    check(actual.matches(Regex("[a-f0-9]{40}:[a-f0-9]{40}")) && actual.substringBefore(':') == source)
    return "PACKAGED_NATIVE_SOURCE_AND_ABI_PASS_NO_NETWORK $source"
}
