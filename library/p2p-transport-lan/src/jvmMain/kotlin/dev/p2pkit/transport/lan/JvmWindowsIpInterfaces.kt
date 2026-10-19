package dev.p2pkit.transport.lan

import java.net.InetAddress

/** Optional installed observer; absence preserves the strict portable policy, failure refuses the scan. */
internal fun readWindowsIpSocketSnapshot(): JvmLanSocketSnapshot? {
    if (!System.getProperty("os.name").startsWith("Windows")) return null
    val boot = ModuleLayer.boot()
    val module = boot.findModule("dev.p2pkit.rpc.windows.loader").orElse(null) ?: return null
    check(Runtime.version().feature() == 21 && module.isNamed && !module.descriptor.isAutomatic && module.layer === boot)
    val type = Class.forName(module, "dev.p2pkit.rpc.windows.loader.WindowsIpInterfaces")
    check(type != null && type.module === module)
    val raw = type.getMethod("snapshotOrNull").invoke(null) ?: return null
    return decodeWindowsIpSocketSnapshot(raw)
}

internal fun decodeWindowsIpSocketSnapshot(raw: Any): JvmLanSocketSnapshot {
    val data = raw as Array<*>
    check(data.size == 3 && data[0] == 1)
    val rows = data[1] as Array<*>
    check(rows.size in 1..4096)
    val names = mutableSetOf<String>()
    val indices = mutableMapOf<String, Int>()
    val snapshots = rows.map { rawRow ->
        val row = rawRow as Array<*>
        check(row.size == 9)
        val name = row[0] as String
        val index = row[6] as Int
        check(name.length in 1..256 && names.add(name) && index > 0 && index !in indices.values)
        indices[name] = index
        val addresses = row[7] as Array<*>
        val lengths = row[8] as IntArray
        check(addresses.size <= 256 && addresses.size == lengths.size)
        JvmLanInterfaceSnapshot(name, row[1] as Boolean, row[2] as Boolean, row[3] as Boolean,
            row[4] as Boolean, row[5] as Boolean, addresses.mapIndexed { n, address ->
                address as InetAddress
                check(lengths[n] in 0..address.address.size * 8)
                LanInterfaceAddress(address, lengths[n])
            })
    }
    val local = (data[2] as Array<*>).map { it as InetAddress }.toSet()
    check(snapshots.all { snapshot -> snapshot.addresses.all { it.address in local } })
    return JvmLanSocketSnapshot(snapshots, local, indices)
}
