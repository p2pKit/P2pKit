package dev.p2pkit.rpc.windows.loader;

import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;

/** Copied AMD64 IP Helper data, never native addresses or authority to omit an interface. */
final class WindowsIpInterfaceTable {
    static final int ROW_BYTES = 168;
    static final int MAX_ROWS = 4096;
    record Row(int family, int index, long luid, boolean connected, boolean forwarding,
               boolean weakSend, boolean weakReceive, long metric, long mtu) {}

    private WindowsIpInterfaceTable() {}

    static List<Row> parse(byte[] bytes, int count) {
        if (count < 1 || count > MAX_ROWS || bytes == null || bytes.length != count * ROW_BYTES) throw refused();
        ByteBuffer data = ByteBuffer.wrap(bytes).order(ByteOrder.LITTLE_ENDIAN);
        List<Row> rows = new ArrayList<>(count);
        var identities = new HashMap<Integer, Long>();
        var indices = new HashMap<Long, Integer>();
        var keys = new HashSet<Long>();
        for (int n = 0; n < count; n++) {
            int at = n * ROW_BYTES;
            int family = Short.toUnsignedInt(data.getShort(at));
            int index = data.getInt(at + 16);
            long luid = data.getLong(at + 8);
            if ((family != 2 && family != 23) || index <= 0 || luid == 0 ||
                !keys.add(((long) index << 16) | family)) throw refused();
            Long previous = identities.putIfAbsent(index, luid);
            Integer previousIndex = indices.putIfAbsent(luid, index);
            if (previous != null && previous != luid || previousIndex != null && previousIndex != index) throw refused();
            rows.add(new Row(family, index, luid, bool(data, at + 156), bool(data, at + 41),
                bool(data, at + 42), bool(data, at + 43),
                Integer.toUnsignedLong(data.getInt(at + 148)), Integer.toUnsignedLong(data.getInt(at + 152))));
        }
        rows.sort(Comparator.comparingInt(Row::index).thenComparingInt(Row::family));
        return List.copyOf(rows);
    }

    private static boolean bool(ByteBuffer data, int at) {
        byte value = data.get(at);
        if (value != 0 && value != 1) throw refused();
        return value == 1;
    }

    private static IllegalStateException refused() { return new IllegalStateException("Windows IP table refused"); }
}
