package dev.p2pkit.sample.rpc.desktop

import dev.p2pkit.transport.lan.OrganizationLan
import java.net.Inet4Address

/** Advisory and Start scans use the same installed IP-layer observer as fresh transport/socket checks. */
internal fun desktopWindowsIpNetworks(): List<DesktopRpcNetwork>? {
    if (!System.getProperty("os.name").startsWith("Windows")) return null
    val boot = ModuleLayer.boot()
    val module = boot.findModule("dev.p2pkit.rpc.windows.loader").orElse(null) ?: return null
    check(Runtime.version().feature() == 21 && module.layer === boot && !module.descriptor.isAutomatic)
    val type = Class.forName(module, "dev.p2pkit.rpc.windows.loader.WindowsIpInterfaces")
    check(type != null && type.module === module)
    val raw = type.getMethod("snapshotOrNull").invoke(null) ?: return null
    val data = raw as Array<*>
    check(data.size == 3 && data[0] == 1)
    val rows = (data[1] as Array<*>).map { it as Array<*> }
    check(rows.size in 1..4096 && rows.all { it.size == 9 })
    val active = rows.filter { it[1] as Boolean && !(it[2] as Boolean) }.map { it[0] as String }
    return rows.flatMap { row ->
        if (!(row[1] as Boolean) || row[2] as Boolean || row[3] as Boolean || row[4] as Boolean) emptyList()
        else {
            val name = row[0] as String
            val addresses = row[7] as Array<*>
            val prefixes = row[8] as IntArray
            check(addresses.size <= 256 && addresses.size == prefixes.size)
            addresses.mapIndexedNotNull { index, value ->
                val address = value as? Inet4Address ?: return@mapIndexedNotNull null
                runCatching {
                    val text = checkNotNull(address.hostAddress)
                    val subnet = desktopRpcSubnet(text, prefixes[index])
                    OrganizationLan(listOf(subnet), name, text)
                    DesktopRpcNetwork(name, text, subnet, active.count { it != name })
                }.getOrNull()
            }
        }
    }.distinct().sortedWith(compareBy(DesktopRpcNetwork::interfaceName, DesktopRpcNetwork::address))
}
