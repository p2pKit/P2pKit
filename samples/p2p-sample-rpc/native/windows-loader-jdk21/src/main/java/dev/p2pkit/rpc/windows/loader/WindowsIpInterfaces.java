package dev.p2pkit.rpc.windows.loader;

import java.net.InetAddress;
import java.net.NetworkInterface;
import java.util.ArrayList;
import java.util.Collections;
import java.util.HashSet;
import java.util.List;
import java.util.Set;

/**
 * Fresh copied Java/IP-layer intersection for the existing single-interface policy. This creates no
 * sockets, relaxes no route or multicast policy, and does not authorize another native provider.
 */
public final class WindowsIpInterfaces {
    private WindowsIpInterfaces() {}

    /**
     * Schema 1: {schema, rows, complete local addresses}; rows contain name, up, loopback, point-to-point,
     * virtual, multicast, index, prefix addresses, prefix lengths. Only boot Java values cross the module.
     * Null is exclusively a pre-admission advisory observation; failures never become a permissive scan.
     */
    @SuppressWarnings("removal")
    public static Object[] snapshotOrNull() throws Exception {
        WindowsLoaderRuntime.requireDiagnosticRuntime();
        WindowsOriginalIpInterfaces nativeOwner = WindowsLoader.originalIpInterfacesOrNull();
        if (nativeOwner == null) return null;
        if (System.getSecurityManager() != null) throw refused();
        List<WindowsIpInterfaceTable.Row> before = nativeOwner.read();
        Set<Integer> bound = boundIndices(before);
        var seen = new HashSet<Integer>();
        var names = new HashSet<String>();
        var local = new HashSet<InetAddress>();
        var result = new ArrayList<Object[]>();
        List<NetworkInterface> networks = Collections.list(NetworkInterface.getNetworkInterfaces());
        if (networks.isEmpty() || networks.size() > 4096) throw refused();
        for (NetworkInterface network : networks) {
            int index = network.getIndex();
            String name = network.getName();
            if (index <= 0 || !seen.add(index) || name == null || name.isEmpty() || name.length() > 256 ||
                !names.add(name)) throw refused();
            List<InetAddress> addresses = Collections.list(network.getInetAddresses());
            if (addresses.size() > 256 || network.getSubInterfaces().hasMoreElements()) throw refused();
            local.addAll(addresses);
            // Do not discard an address or an unreadable flag, including on an allegedly unbound row.
            boolean up = network.isUp(), loop = network.isLoopback(), point = network.isPointToPoint();
            boolean virtual = network.isVirtual(), multicast = network.supportsMulticast();
            var prefixes = network.getInterfaceAddresses();
            if (prefixes.size() > 256) throw refused();
            InetAddress[] prefixAddresses = new InetAddress[prefixes.size()];
            int[] lengths = new int[prefixes.size()];
            for (int n = 0; n < prefixes.size(); n++) {
                prefixAddresses[n] = prefixes.get(n).getAddress();
                lengths[n] = prefixes.get(n).getNetworkPrefixLength();
                if (prefixAddresses[n] == null || !addresses.contains(prefixAddresses[n]) || lengths[n] < 0 ||
                    lengths[n] > prefixAddresses[n].getAddress().length * 8) throw refused();
            }
            if (!bound.contains(index)) {
                if (!addresses.isEmpty() || !prefixes.isEmpty()) throw refused();
                continue;
            }
            result.add(new Object[] {name, up, loop, point, virtual, multicast, index, prefixAddresses, lengths});
        }
        // Every native IP interface must be visible to Java; every omitted link must lack an IP binding
        // AND all addresses. A new/removed binding, LUID reuse or relevant state change refuses the scan.
        if (!seen.containsAll(bound) || !before.equals(nativeOwner.read()) || System.getSecurityManager() != null) {
            throw refused();
        }
        return new Object[] {1, result.toArray(Object[][]::new), local.toArray(InetAddress[]::new)};
    }

    static Set<Integer> boundIndices(List<WindowsIpInterfaceTable.Row> rows) {
        Set<Integer> result = new HashSet<>();
        for (var row : rows) {
            // Weak-host/forwarding configurations need stronger actual socket routing authority.
            if (row.forwarding() || row.weakSend() || row.weakReceive()) throw refused();
            result.add(row.index());
        }
        if (result.isEmpty()) throw refused();
        return Set.copyOf(result);
    }

    private static IllegalStateException refused() { return new IllegalStateException("Windows IP topology unavailable"); }
}
