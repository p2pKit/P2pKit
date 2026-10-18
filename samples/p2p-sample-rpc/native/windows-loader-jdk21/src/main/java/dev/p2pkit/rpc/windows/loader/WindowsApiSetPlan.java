package dev.p2pkit.rpc.windows.loader;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;

/**
 * Bounded copied version-6 API-set namespace DATA. This parser grants no native-call or load authority.
 * Only a sealed contract with one unnamed physical host can resolve. Importer-specific aliases,
 * missing hosts, future contract revisions and namespace extensions are deliberately unsupported.
 * Productive use additionally requires the original process namespace and actual retained OS route.
 */
final class WindowsApiSetPlan {
    static final int MAXIMUM_BYTES = 2 * 1024 * 1024;
    private static final int MAXIMUM_ENTRIES = 8192;
    private static final int MAXIMUM_VALUES = 32768;
    private static final int MAXIMUM_STRING_BYTES = 512;

    private record Span(int start, int end) {
        boolean overlaps(Span other) { return start < other.end && other.start < end; }
    }
    private record Contract(String prefix, int revision) {}
    private record Entry(String name, int flags, List<Value> values) {}
    private record Value(String alias, String host) {}

    private final Map<String, Entry> entries;

    private WindowsApiSetPlan(Map<String, Entry> entries) { this.entries = Map.copyOf(entries); }

    static WindowsApiSetPlan parse(byte[] original) {
        if (original == null || original.length < 28 || original.length > MAXIMUM_BYTES) throw refused();
        return new Reader(original.clone()).parse();
    }

    String defaultHost(String requested) {
        String name = contractName(requested);
        Contract contract = contract(name);
        Entry entry = entries.get(contract.prefix);
        if (entry == null || entry.flags != 1 || contract.revision > contract(entry.name).revision ||
            entry.values.size() != 1) throw refused();
        Value value = entry.values.getFirst();
        if (!value.alias.isEmpty() || !value.host.endsWith(".dll") || apiSet(value.host)) throw refused();
        return value.host;
    }

    private static final class Reader {
        private final byte[] data;
        private final List<Span> tables = new ArrayList<>();
        private final List<Span> strings = new ArrayList<>();
        private long remaining = 8L * 1024 * 1024;

        Reader(byte[] data) { this.data = data; }

        WindowsApiSetPlan parse() {
            if (u32(0) != 6 || u32(4) != data.length || u32(8) != 0) throw refused();
            int count = bounded(u32(12), 1, MAXIMUM_ENTRIES);
            long factor = u32(24);
            if (factor < 1 || (factor & 1) == 0) throw refused();
            int entriesAt = table(u32(16), count * 24L);
            int hashesAt = table(u32(20), count * 8L);
            tables.add(new Span(0, 28));
            long[] computedHashes = new long[count];
            Map<String, Entry> result = new HashMap<>();
            int totalValues = 0;
            for (int index = 0; index < count; index++) {
                int at = entriesAt + index * 24;
                int flags = bounded(u32(at), 0, 1);
                String name = text(u32(at + 4), u32(at + 8), false);
                if (!name.equals(contractName(name)) || name.endsWith(".dll")) throw refused();
                Contract contract = contract(name);
                int hashedBytes = bounded(u32(at + 12), 2, MAXIMUM_STRING_BYTES);
                if (hashedBytes != contract.prefix.length() * 2) throw refused();
                long hash = 0;
                for (int character = 0; character < contract.prefix.length(); character++) {
                    hash = (hash * factor + contract.prefix.charAt(character)) & 0xffffffffL;
                }
                computedHashes[index] = hash;
                int valueCount = bounded(u32(at + 20), 1, 16);
                if (valueCount > MAXIMUM_VALUES - totalValues) throw refused();
                totalValues += valueCount;
                int valuesAt = table(u32(at + 16), valueCount * 20L);
                List<Value> values = new ArrayList<>();
                Set<String> aliases = new HashSet<>();
                for (int valueIndex = 0; valueIndex < valueCount; valueIndex++) {
                    int valueAt = valuesAt + valueIndex * 20;
                    if (u32(valueAt) != 0) throw refused();
                    String alias = text(u32(valueAt + 4), u32(valueAt + 8), true);
                    String host = text(u32(valueAt + 12), u32(valueAt + 16), true);
                    if (!alias.isEmpty()) moduleName(alias);
                    if (!host.isEmpty()) moduleName(host);
                    if (!aliases.add(alias)) throw refused();
                    values.add(new Value(alias, host));
                }
                if (result.put(contract.prefix, new Entry(name, flags, List.copyOf(values))) != null) throw refused();
            }
            boolean[] indexed = new boolean[count];
            long previous = -1;
            for (int index = 0; index < count; index++) {
                int at = hashesAt + index * 8;
                long hash = u32(at);
                int target = bounded(u32(at + 4), 0, count - 1);
                if (indexed[target] || hash < previous || hash != computedHashes[target]) throw refused();
                indexed[target] = true;
                previous = hash;
            }
            tables.sort(Comparator.comparingInt(Span::start));
            for (int index = 1; index < tables.size(); index++) {
                if (tables.get(index - 1).overlaps(tables.get(index))) throw refused();
            }
            // String sharing is permitted; strings may never reinterpret a header/hash/value table.
            strings.sort(Comparator.comparingInt(Span::start));
            int tableIndex = 0;
            for (Span string : strings) {
                while (tableIndex < tables.size() && tables.get(tableIndex).end <= string.start) tableIndex++;
                if (tableIndex < tables.size() && tables.get(tableIndex).overlaps(string)) throw refused();
            }
            return new WindowsApiSetPlan(result);
        }

        private int table(long at, long bytes) {
            int start = span(at, bytes);
            if ((start & 3) != 0) throw refused();
            tables.add(new Span(start, Math.toIntExact(at + bytes)));
            return start;
        }

        private String text(long at, long bytes, boolean empty) {
            if (bytes > MAXIMUM_STRING_BYTES || (bytes & 1) != 0 || (at & 1) != 0 || (!empty && bytes == 0)) throw refused();
            int start = span(at, bytes);
            if (bytes == 0) return "";
            strings.add(new Span(start, Math.toIntExact(at + bytes)));
            consume(bytes);
            StringBuilder result = new StringBuilder((int) bytes / 2);
            for (int index = 0; index < bytes; index += 2) {
                int value = (data[start + index] & 255) | (data[start + index + 1] & 255) << 8;
                if (!(value >= 'a' && value <= 'z' || value >= '0' && value <= '9' ||
                    value == '-' || value == '_' || value == '.')) throw refused();
                result.append((char) value);
            }
            return result.toString();
        }

        private long u32(int at) {
            int start = span(at, 4);
            consume(4);
            return Integer.toUnsignedLong((data[start] & 255) | (data[start + 1] & 255) << 8 |
                (data[start + 2] & 255) << 16 | (data[start + 3] & 255) << 24);
        }

        private int span(long at, long bytes) {
            if (at < 0 || bytes < 0 || at > data.length || bytes > data.length - at) throw refused();
            return (int) at;
        }

        private void consume(long bytes) {
            if (bytes < 0 || bytes > remaining) throw refused();
            remaining -= bytes;
        }
    }

    private static int bounded(long value, int minimum, int maximum) {
        if (value < minimum || value > maximum) throw refused();
        return (int) value;
    }

    private static String contractName(String source) {
        if (source == null || source.length() < 12 || source.length() > 128) throw refused();
        for (int index = 0; index < source.length(); index++) {
            if (source.charAt(index) < 33 || source.charAt(index) > 126) throw refused();
        }
        String name = source.toLowerCase(Locale.ROOT);
        if (name.endsWith(".dll")) name = name.substring(0, name.length() - 4);
        if (!apiSet(name)) throw refused();
        for (int index = 0; index < name.length(); index++) {
            char value = name.charAt(index);
            if (!(value >= 'a' && value <= 'z' || value >= '0' && value <= '9' || value == '-')) throw refused();
        }
        contract(name);
        return name;
    }

    private static Contract contract(String name) {
        int last = name.lastIndexOf('-');
        if (last < 8 || last == name.length() - 1 || name.length() - last > 5) throw refused();
        int revision = 0;
        for (int index = last + 1; index < name.length(); index++) {
            char digit = name.charAt(index);
            if (digit < '0' || digit > '9' || (index == last + 1 && digit == '0' && index + 1 < name.length())) throw refused();
            revision = revision * 10 + digit - '0';
        }
        return new Contract(name.substring(0, last), revision);
    }

    private static void moduleName(String name) {
        if (name.length() < 5 || name.length() > 128 ||
            !(name.endsWith(".dll") || name.endsWith(".sys") || name.endsWith(".drv") || name.endsWith(".exe")) || name.contains("..") ||
            name.charAt(0) == '.') throw refused();
    }

    private static boolean apiSet(String name) { return name.startsWith("api-") || name.startsWith("ext-"); }
    private static IllegalArgumentException refused() {
        return new IllegalArgumentException("Unsupported or incomplete copied API-set namespace data");
    }
}
