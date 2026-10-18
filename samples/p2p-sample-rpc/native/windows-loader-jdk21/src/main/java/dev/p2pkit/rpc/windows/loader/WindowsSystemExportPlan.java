package dev.p2pkit.rpc.windows.loader;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.Comparator;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;

/**
 * Bounded, copied system-PE export DATA only. No native call, library lookup, loading or authority.
 * A future caller must bind every input to its original independently admitted file/mapping owner.
 * This reader neither admits those owners nor models API-set routing, loader search, or DllMain.
 */
final class WindowsSystemExportPlan {
    private static final int MAXIMUM_MODULES = 16;
    private static final int MAXIMUM_FILE = 32 * 1024 * 1024;
    private static final long MAXIMUM_FILES = 128L * 1024 * 1024;
    private static final int MAXIMUM_EXPORTS = 65_536;
    private static final int MAXIMUM_NAME = 255;
    private static final int MAXIMUM_STEPS = 16; // Includes the terminal node, not sixteen forward edges.
    private static final long MAXIMUM_WORK = 8L * 1024 * 1024;

    /** The constructor owns a bounded snapshot; the accessor never exposes that original array. */
    record Input(String module, byte[] image) {
        Input {
            module = moduleName(module, false);
            if (image == null || image.length < 512 || image.length > MAXIMUM_FILE) throw refused();
            image = image.clone();
        }
        @Override public byte[] image() { return image.clone(); }
    }

    /** Immutable resolution data, NOT permission to call or load this address. No address is supplied here. */
    record Target(String module, long rva, long ordinal) {}

    private record Forward(String module, String name, long ordinal) {}
    private record Span(long start, long bytes) {
        long end() { return start + bytes; }
        boolean contains(long value) { return value >= start && value < end(); }
        boolean overlaps(Span other) { return start < other.end() && other.start < end(); }
    }
    private record Section(long rva, long mapped, int raw, int rawBytes, long flags) {}

    private static final class Budget {
        private long remaining = MAXIMUM_WORK;
        void consume(long units) {
            if (units < 0 || units > remaining) throw refused();
            remaining -= units;
        }
    }

    private final Map<String, Module> modules;

    private WindowsSystemExportPlan(Map<String, Module> modules) { this.modules = Map.copyOf(modules); }

    static WindowsSystemExportPlan parse(Input[] original) {
        if (original == null || original.length < 1 || original.length > MAXIMUM_MODULES) throw refused();
        Input[] inputs = original.clone();
        long total = 0;
        Set<String> names = new HashSet<>();
        for (Input input : inputs) {
            if (input == null || !names.add(input.module)) throw refused();
            total = checkedAggregateSize(total, input.image.length);
        }
        Budget budget = new Budget();
        Map<String, Module> modules = new HashMap<>();
        for (Input input : inputs) modules.put(input.module, new Module(input, budget));
        return new WindowsSystemExportPlan(modules);
    }

    /** Aggregate arithmetic only; Input independently enforces each copied file's size and ownership. */
    static long checkedAggregateSize(long current, int additional) {
        if (current < 0 || current > MAXIMUM_FILES || additional < 0 || additional > MAXIMUM_FILES - current) {
            throw refused();
        }
        return current + additional; // Both operands are bounded before addition; no overflow or saturation.
    }

    Target resolve(String module, String name) {
        if (!symbol(name)) throw refused();
        return resolveReference(moduleName(module, false), name, 0);
    }

    Target resolveOrdinal(String module, long ordinal) {
        if (ordinal < 1 || ordinal > 65_535) throw refused();
        return resolveReference(moduleName(module, false), null, ordinal);
    }

    private Target resolveReference(String module, String name, long ordinal) {
        Set<String> visited = new HashSet<>();
        for (int hop = 0; hop < MAXIMUM_STEPS; hop++) {
            if (apiSet(module)) throw refused(); // A contract name is not an ordinary DLL mapping.
            Module image = modules.get(module);
            if (image == null) throw refused();
            int index = name == null ? image.ordinalIndex(ordinal) : image.nameIndex(name);
            String key = module + ":" + index; // Aliases share one node, so they cannot hide a cycle.
            if (!visited.add(key) || image.functions[index] == 0) throw refused();
            Forward forward = image.forwarders[index];
            if (forward == null) {
                image.requireTerminal(image.functions[index]);
                return new Target(module, image.functions[index], image.ordinalBase + index);
            }
            module = forward.module;
            name = forward.name;
            ordinal = forward.ordinal;
        }
        throw refused();
    }

    private static final class Module {
        private final byte[] bytes;
        private final Budget budget;
        private final String module;
        private final List<Section> sections = new ArrayList<>();
        private final List<Span> metadata = new ArrayList<>();
        private Span[] mergedMetadata;
        private long imageSize;
        private long ordinalBase;
        private long[] functions;
        private Forward[] forwarders;
        private String[] names;
        private int[] nameIndexes;
        private Span[] tables;

        Module(Input input, Budget budget) {
            // Input is final and already owns this immutable snapshot; no unbounded second copy.
            bytes = input.image;
            module = input.module;
            this.budget = budget;
            read();
        }

        private void read() {
            if (u16(0) != 0x5a4d) throw refused();
            long pe = u32(0x3c);
            fileSpan(pe, 24);
            if (pe < 64 || pe % 4 != 0 || u32(pe) != 0x4550 || u16(pe + 4) != 0x8664) throw refused();
            int sectionCount = u16(pe + 6);
            int characteristics = u16(pe + 22);
            if (sectionCount < 1 || sectionCount > 96 || u16(pe + 20) != 240 ||
                (characteristics & 0x2002) != 0x2002 || (characteristics & 0x100) != 0) throw refused();
            long optional = pe + 24;
            fileSpan(optional, 240);
            if (u16(optional) != 0x20b || u32(optional + 108) != 16) throw refused();
            long sectionAlignment = u32(optional + 32);
            long fileAlignment = u32(optional + 36);
            imageSize = u32(optional + 56);
            long headers = u32(optional + 60);
            long sectionTable = optional + 240;
            fileSpan(sectionTable, sectionCount * 40L);
            if (!powerOfTwo(sectionAlignment) || sectionAlignment < 4096 || sectionAlignment > 65_536 ||
                !powerOfTwo(fileAlignment) || fileAlignment < 512 || fileAlignment > sectionAlignment ||
                imageSize < 4096 || imageSize > 128L * 1024 * 1024 || imageSize % sectionAlignment != 0 ||
                headers < sectionTable + sectionCount * 40L || headers % fileAlignment != 0) throw refused();
            fileSpan(0, headers);
            for (int index = 0; index < sectionCount; index++) {
                budget.consume(1);
                long at = sectionTable + 40L * index;
                long virtualBytes = u32(at + 8), rva = u32(at + 12);
                long rawBytes = u32(at + 16), raw = u32(at + 20), flags = u32(at + 36);
                long mapped = align(Math.max(virtualBytes, rawBytes), sectionAlignment);
                if (mapped == 0 || rva < align(headers, sectionAlignment) || rva % sectionAlignment != 0 ||
                    rva > imageSize || mapped > imageSize - rva || rawBytes % fileAlignment != 0 ||
                    (rawBytes == 0 ? raw != 0 : raw < headers || raw % fileAlignment != 0)) throw refused();
                fileSpan(raw, rawBytes);
                Section section = new Section(rva, mapped, (int) raw, (int) rawBytes, flags);
                for (Section previous : sections) {
                    if (new Span(rva, mapped).overlaps(new Span(previous.rva, previous.mapped)) ||
                        rawBytes != 0 && previous.rawBytes != 0 &&
                        new Span(raw, rawBytes).overlaps(new Span(previous.raw, previous.rawBytes))) throw refused();
                }
                sections.add(section);
            }
            long exportRva = u32(optional + 112), exportBytes = u32(optional + 116);
            if (exportBytes < 40 || exportBytes > MAXIMUM_FILE) throw refused();
            Span directory = new Span(exportRva, exportBytes);
            int export = mapped(exportRva, exportBytes);
            if (u32(export) != 0) throw refused();
            ordinalBase = u32(export + 16);
            long count = u32(export + 20), named = u32(export + 24);
            if (count < 1 || count > MAXIMUM_EXPORTS || named > MAXIMUM_EXPORTS ||
                ordinalBase < 1 || count - 1 > 0xffffffffL - ordinalBase) throw refused();
            Span functionTable = new Span(u32(export + 28), count * 4);
            Span nameTable = new Span(u32(export + 32), named * 4);
            Span ordinalTable = new Span(u32(export + 36), named * 2);
            tables = named == 0 ? new Span[] {new Span(exportRva, 40), functionTable} :
                new Span[] {new Span(exportRva, 40), functionTable, nameTable, ordinalTable};
            for (int index = 0; index < tables.length; index++) {
                mapped(tables[index].start, tables[index].bytes);
                for (int previous = 0; previous < index; previous++) {
                    if (tables[index].overlaps(tables[previous])) throw refused();
                }
                metadata.add(tables[index]);
            }
            if (!moduleName(text(u32(export + 12), Long.MAX_VALUE), false).equals(module)) throw refused();
            functions = new long[(int) count];
            forwarders = new Forward[(int) count];
            int functionOffset = mapped(functionTable.start, functionTable.bytes);
            for (int index = 0; index < count; index++) {
                long rva = u32(functionOffset + 4L * index);
                functions[index] = rva;
                if (rva != 0) {
                    mapped(rva, 1);
                    if (directory.contains(rva)) forwarders[index] = forward(text(rva, directory.end()));
                }
            }
            names = new String[(int) named];
            nameIndexes = new int[(int) named];
            if (named != 0) {
                int nameOffset = mapped(nameTable.start, nameTable.bytes);
                int ordinalOffset = mapped(ordinalTable.start, ordinalTable.bytes);
                for (int index = 0; index < named; index++) {
                    String name = text(u32(nameOffset + 4L * index), Long.MAX_VALUE);
                    int ordinalIndex = u16(ordinalOffset + 2L * index);
                    if (!symbol(name) || index > 0 && names[index - 1].compareTo(name) >= 0 || ordinalIndex >= count) {
                        throw refused();
                    }
                    names[index] = name;
                    nameIndexes[index] = ordinalIndex;
                }
            }
            metadata.sort(Comparator.comparingLong(Span::start));
            List<Span> merged = new ArrayList<>();
            for (Span next : metadata) {
                if (!merged.isEmpty() && merged.getLast().end() >= next.start) {
                    Span previous = merged.removeLast();
                    merged.add(new Span(previous.start, Math.max(previous.end(), next.end()) - previous.start));
                } else merged.add(next);
            }
            mergedMetadata = merged.toArray(Span[]::new);
        }

        int nameIndex(String name) {
            int index = Arrays.binarySearch(names, name);
            if (index < 0) throw refused();
            return nameIndexes[index];
        }

        int ordinalIndex(long ordinal) {
            if (ordinal < ordinalBase || ordinal - ordinalBase >= functions.length) throw refused();
            return (int) (ordinal - ordinalBase);
        }

        void requireTerminal(long rva) {
            Section section = null;
            for (Section candidate : sections) {
                long offset = rva - candidate.rva;
                if (offset >= 0 && offset < candidate.rawBytes) { section = candidate; break; }
            }
            if (section == null) throw refused();
            if ((section.flags & 0x60000000L) != 0x60000000L || (section.flags & 0x80000000L) != 0) throw refused();
            int low = 0, high = mergedMetadata.length;
            while (low < high) {
                int middle = (low + high) >>> 1;
                if (mergedMetadata[middle].end() <= rva) low = middle + 1;
                else high = middle;
            }
            if (low < mergedMetadata.length && mergedMetadata[low].contains(rva)) throw refused();
        }

        private String text(long rva, long exclusiveEnd) {
            Section section = section(rva, 1);
            int at = mapped(rva, 1);
            long available = Math.min(section.rawBytes - (rva - section.rva), exclusiveEnd - rva);
            for (int length = 0; length <= MAXIMUM_NAME && length < available; length++) {
                budget.consume(1);
                int value = bytes[at + length] & 255;
                if (value == 0) {
                    Span span = new Span(rva, length + 1L);
                    for (Span table : tables) if (span.overlaps(table)) throw refused();
                    metadata.add(span);
                    if (length == 0) throw refused();
                    return new String(bytes, at, length, java.nio.charset.StandardCharsets.US_ASCII);
                }
                if (value < 33 || value > 126) throw refused();
            }
            throw refused();
        }

        private Section section(long rva, long length) {
            if (rva < 0 || length < 1 || rva > imageSize || length > imageSize - rva) throw refused();
            for (Section section : sections) {
                budget.consume(1);
                long offset = rva - section.rva;
                if (offset >= 0 && offset <= section.rawBytes && length <= section.rawBytes - offset) return section;
            }
            throw refused();
        }

        private int mapped(long rva, long length) {
            Section section = section(rva, length);
            return (int) (section.raw + (rva - section.rva));
        }

        private int u16(long at) {
            int offset = fileSpan(at, 2);
            budget.consume(2);
            return (bytes[offset] & 255) | (bytes[offset + 1] & 255) << 8;
        }

        private long u32(long at) {
            int offset = fileSpan(at, 4);
            budget.consume(4);
            return Integer.toUnsignedLong((bytes[offset] & 255) | (bytes[offset + 1] & 255) << 8 |
                (bytes[offset + 2] & 255) << 16 | (bytes[offset + 3] & 255) << 24);
        }

        private int fileSpan(long at, long length) {
            if (at < 0 || length < 0 || at > bytes.length || length > bytes.length - at) throw refused();
            return (int) at;
        }
    }

    private static Forward forward(String value) {
        int separator = value.indexOf('.');
        if (separator < 1) throw refused();
        int symbolAt = separator + 1;
        if (value.regionMatches(true, separator, ".dll.", 0, 5)) symbolAt = separator + 5;
        String module = moduleName(value.substring(0, symbolAt - 1), true);
        String target = value.substring(symbolAt);
        if (target.startsWith("#")) {
            if (target.length() < 2 || target.length() > 6 || target.charAt(1) == '0') throw refused();
            long ordinal = 0;
            for (int index = 1; index < target.length(); index++) {
                char digit = target.charAt(index);
                if (digit < '0' || digit > '9') throw refused();
                ordinal = ordinal * 10 + digit - '0';
            }
            if (ordinal < 1 || ordinal > 65_535) throw refused();
            return new Forward(module, null, ordinal);
        }
        if (!symbol(target)) throw refused();
        return new Forward(module, target, 0);
    }

    private static String moduleName(String source, boolean extensionOptional) {
        if (source == null || source.isEmpty() || source.length() > 64) throw refused();
        for (int index = 0; index < source.length(); index++) {
            if (source.charAt(index) < 33 || source.charAt(index) > 126) throw refused();
        }
        String name = source.toLowerCase(java.util.Locale.ROOT);
        if (extensionOptional && !name.endsWith(".dll")) name += ".dll";
        if (!name.endsWith(".dll") || name.length() < 5 || name.length() > 64) throw refused();
        for (int index = 0; index < name.length() - 4; index++) {
            char value = name.charAt(index);
            if (!(value >= 'a' && value <= 'z' || value >= '0' && value <= '9' || value == '_' || value == '-')) {
                throw refused();
            }
        }
        if (!extensionOptional && apiSet(name)) throw refused();
        return name;
    }

    private static boolean apiSet(String name) { return name.startsWith("api-") || name.startsWith("ext-"); }
    private static boolean symbol(String value) {
        if (value == null || value.isEmpty() || value.length() > MAXIMUM_NAME || value.charAt(0) == '#') return false;
        for (int index = 0; index < value.length(); index++) {
            char character = value.charAt(index);
            if (character < 33 || character > 126 || character == '/' || character == '\\' || character == ':') return false;
        }
        return true;
    }
    private static boolean powerOfTwo(long value) { return value > 0 && (value & (value - 1)) == 0; }
    private static long align(long value, long alignment) { return (value + alignment - 1) & -alignment; }
    private static IllegalArgumentException refused() {
        return new IllegalArgumentException("Unsupported or incomplete copied system export data");
    }
}
