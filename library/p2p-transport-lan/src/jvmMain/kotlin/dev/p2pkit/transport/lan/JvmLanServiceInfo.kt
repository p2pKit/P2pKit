package dev.p2pkit.transport.lan

import dev.p2pkit.core.transport.LocalPeerInfo
import dev.p2pkit.transport.lan.internal.jmdns.ServiceInfo

/** Read raw TXT, not JmDNS's already-normalized string or byte property map. */
internal fun validateJmdnsDiscoveryRecord(
    info: ServiceInfo,
    registration: LanServiceRegistration
): ValidatedLanDiscoveryRecord? {
    val properties = decodeLanTxtRecord(info.textBytes) ?: return null
    return validateLanDiscoveryRecord(
        properties = properties,
        expectedAppId = registration.appId,
        localPeerId = registration.localPeerId,
        securityProfile = registration.securityProfile
    )
}

/** Production service-token construction, separate from native handle ownership. */
internal fun buildJmdnsServiceInfo(registration: LanServiceRegistration, localPeer: LocalPeerInfo): ServiceInfo {
    val port = registration.boundTcpPortForAdvertisement()
    val properties = buildLanTxtProperties(
        peerId = registration.localPeerId,
        appId = registration.appId,
        deviceName = localPeer.deviceName,
        platform = localPeer.platform,
        supportedTransports = localPeer.supportedTransports,
        protocolVersion = registration.protocolVersion,
        fingerprint = registration.fingerprint
    )
    return ServiceInfo.create(
        registration.serviceTypeJmdns,
        registration.localPeerId.value,
        port,
        /* weight = */ 0,
        /* priority = */ 0,
        properties
    )
}
