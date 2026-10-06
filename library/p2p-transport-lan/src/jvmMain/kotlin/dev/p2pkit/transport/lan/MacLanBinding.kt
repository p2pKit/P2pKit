package dev.p2pkit.transport.lan

import java.io.Closeable
import java.net.InetAddress
import java.net.NetworkInterface
import java.net.Socket
import java.net.SocketException

/** TCP-only policy strategy; never supplied to JmDNS or treated as proof that a not-yet-open socket is scoped. */
internal class MacLanBinding(
    private val policy: OrganizationLan,
    private val api: MacLanCalls,
    private val errors: MacLanErrnos,
    private val readSnapshot: () -> JvmLanSocketSnapshot? = ::readJvmLanSocketSnapshot,
    private val isAssignedLocally: (InetAddress) -> Boolean = { NetworkInterface.getByInetAddress(it) != null },
) {
    // Connection/core owners may intentionally suppress close exceptions. A quarantined native ownership
    // failure remains pinned to this transport and prevents a later Stop/start from claiming cleanup.
    private val ownershipGate = Any()
    private val owners = mutableSetOf<Closeable>()
    private var active = false
    fun activate() = synchronized(ownershipGate) {
        requireCleanupHealthy()
        if (!active) { check(owners.isEmpty()); active = true }
    }
    fun seal() { synchronized(ownershipGate) { active = false } }
    fun retire() {
        val remaining = synchronized(ownershipGate) { active = false; owners.toList() }
        val errors = remaining.mapNotNull { runCatching { it.close() }.exceptionOrNull() }
        requireCleanupHealthy()
        if (errors.isNotEmpty()) throw java.io.IOException("Scoped TCP retirement failed", errors.first())
        synchronized(ownershipGate) { check(owners.isEmpty()) { "Scoped TCP ownership remains" } }
    }
    private fun released(owner: Closeable) { synchronized(ownershipGate) { owners -= owner } }
    private fun <T : Closeable> register(factory: () -> T): T = synchronized(ownershipGate) {
        check(active) { "Scoped TCP transport is retired" }
        requireCleanupHealthy()
        factory().also { owners += it } // Inert object is owned before any native allocation can occur.
    }

    private val cleanupFailures = mutableSetOf<Throwable>()
    private fun retainFailure(failure: Throwable) { synchronized(cleanupFailures) { cleanupFailures += failure } }
    fun requireCleanupHealthy() {
        synchronized(cleanupFailures) {
            if (cleanupFailures.isNotEmpty()) throw java.io.IOException(
                "Scoped TCP has quarantined native ownership", cleanupFailures.first(),
            )
        }
    }

    private fun target(snapshot: JvmLanSocketSnapshot): Pair<JvmLanBindTarget, Int>? {
        val selected = snapshot.interfaces.singleOrNull { it.name == policy.interfaceName } ?: return null
        if (!selected.isUp || selected.isLoopback || selected.isVirtual || selected.isPointToPoint ||
            isForbiddenLanInterface(selected.name)
        ) return null
        val index = snapshot.interfaceIndices[selected.name]?.takeIf { it > 0 } ?: return null
        val address = selected.addresses.map { it.address }.firstOrNull {
            it.address.size == 4 && policy.isLocal(it.hostAddress.orEmpty())
        } ?: return null
        return JvmLanBindTarget(selected.name, address, "${selected.name}:${address.hostAddress}") to index
    }

    /** Selection is not admission: bind/connect must independently prove native scope on their actual handle. */
    fun target(): JvmLanBindTarget? = runCatching { readSnapshot()?.let(::target)?.first }.getOrNull()

    private fun prepare(local: InetAddress): Int {
        synchronized(ownershipGate) {
            if (!active) throw SocketException("Scoped TCP transport is retired")
            requireCleanupHealthy()
        }
        val selected = readSnapshot()?.let(::target) ?: throw SocketException("Selected scoped LAN is unavailable")
        if (selected.first.address != local) throw SocketException("Selected scoped LAN address changed")
        return selected.second
    }

    private fun newSocket(index: Int = 0): MacLanSocket = register {
        lateinit var result: MacLanSocket
        result = MacLanSocket(api, errors, ::prepare, initialIndex = index,
            retainFailure = ::retainFailure, released = { released(result) },
            beforeConnect = { socket, destination ->
                if (!allowsEndpoint(socket, destination)) throw SocketException("Scoped TCP destination rejected")
            })
        result
    }
    fun socket(): Socket = newSocket()
    fun listener(): MacLanServerSocket = register {
        lateinit var result: MacLanServerSocket
        result = MacLanServerSocket(api, errors, ::prepare, ::retainFailure,
            released = { released(result) }, childFactory = ::newSocket)
        result
    }

    fun allows(socket: Socket): Boolean = socket.inetAddress?.let { allowsEndpoint(socket, it) } ?: false

    private fun allowsEndpoint(socket: Socket, remote: InetAddress): Boolean = runCatching {
        if (!synchronized(ownershipGate) { active }) return@runCatching false
        val scoped = socket as? MacLanSocket ?: return@runCatching false
        val snapshot = readSnapshot() ?: return@runCatching false
        val selected = target(snapshot) ?: return@runCatching false
        if (scoped.interfaceIndex != selected.second || !scoped.verifyScope() ||
            scoped.localAddress != selected.first.address || !policy.isLocal(scoped.localAddress.hostAddress.orEmpty())
        ) return@runCatching false
        if (remote.address.size != 4 || !policy.allows(remote.hostAddress.orEmpty())) return@runCatching false
        snapshot.completeLocalAddresses?.let { remote !in it } ?: !isAssignedLocally(remote)
    }.getOrDefault(false)
}
