package dev.p2pkit.transport.lan

import platform.Foundation.NSBundle

internal data class AppleLanPackagingSnapshot(
    val localNetworkUsageDescription: String?,
    val bonjourServices: List<String>?
)

internal fun evaluateAppleLanPackaging(
    snapshot: AppleLanPackagingSnapshot,
    requiredBonjourService: String
): List<String> = buildList {
    if (snapshot.localNetworkUsageDescription.isNullOrBlank()) {
        add(
            "Host Info.plist is missing a nonblank NSLocalNetworkUsageDescription; " +
                "iOS may deny local-network access before Bonjour callbacks are delivered"
        )
    }
    if (snapshot.bonjourServices.orEmpty().none { it == requiredBonjourService }) {
        add(
            "Host Info.plist NSBonjourServices is missing '$requiredBonjourService'; " +
                "add the exact service type used by this P2pKit security profile"
        )
    }
}

internal fun currentAppleLanPackagingIssues(requiredBonjourService: String): List<String> {
    val bundle = NSBundle.mainBundle
    val usage = bundle.objectForInfoDictionaryKey("NSLocalNetworkUsageDescription") as? String
    val services = (bundle.objectForInfoDictionaryKey("NSBonjourServices") as? List<*>)
        ?.filterIsInstance<String>()
    return evaluateAppleLanPackaging(
        AppleLanPackagingSnapshot(
            localNetworkUsageDescription = usage,
            bonjourServices = services
        ),
        requiredBonjourService
    )
}

internal fun logAppleLanPackagingIssues(requiredBonjourService: String, phase: String) {
    currentAppleLanPackagingIssues(requiredBonjourService).forEach { issue ->
        IosLanDebug.log("packaging", "$phase: $issue")
    }
}
