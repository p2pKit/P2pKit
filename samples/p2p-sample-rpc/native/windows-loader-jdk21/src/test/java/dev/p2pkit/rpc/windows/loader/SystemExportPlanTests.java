package dev.p2pkit.rpc.windows.loader;

import java.nio.charset.StandardCharsets;
import java.util.Arrays;
import java.util.HashMap;
import java.util.Map;

/** Inert synthetic PE data only. No native lookup, mapped memory, system file or admitted provider. */
public final class SystemExportPlanTests {
    private static final int OPTIONAL = 0x98;
    private static final int SECTION_TABLE = OPTIONAL + 240;
    private static final int EXPORT = 0x400;
    private SystemExportPlanTests() {}

    public static void main(String[] arguments) {
        check(arguments.length == 1);
        switch (arguments[0]) {
            case "direct" -> direct();
            case "ordinal" -> ordinal();
            case "aliases" -> aliases();
            case "forward-name" -> forwardName(false);
            case "forward-extension" -> forwardName(true);
            case "forward-ordinal" -> forwardOrdinal();
            case "snapshot" -> snapshot();
            case "holes" -> holes();
            case "unavailable" -> unavailable();
            case "cycle" -> cycle();
            case "depth" -> depth();
            case "headers" -> headers();
            case "sections" -> sections();
            case "tables" -> tables();
            case "strings" -> strings();
            case "targets" -> targets();
            case "zero-fill-data" -> zeroFillData(false);
            case "zero-fill-only" -> zeroFillData(true);
            case "zero-fill-bounds" -> zeroFillBounds();
            case "zero-fill-forwarders" -> zeroFillForwarders();
            case "bounds" -> bounds();
            case "work" -> work();
            case "inventory" -> inventory();
            case "aggregate" -> aggregate();
            default -> throw new AssertionError("Unknown copied system-export control");
        }
        System.out.println("WINDOWS_SYSTEM_EXPORT_PLAN_PASS case=" + arguments[0] +
            " scope=INERT_COPIED_PE_GRAPH_NOT_SYSTEM_IDENTITY_OR_LOADING_AUTHORITY");
    }

    private static void direct() {
        WindowsSystemExportPlan plan = one("kernel32.dll", simple("kernel32.dll"));
        WindowsSystemExportPlan.Target target = plan.resolve("KERNEL32.DLL", "Target");
        check(target.module().equals("kernel32.dll") && target.rva() == 0x1000 && target.ordinal() == 42);
        check(plan.resolveOrdinal("kernel32.dll", 42).equals(target));
        for (int index = 0; index < 100; index++) check(plan.resolve("kernel32.dll", "Target").equals(target));
    }

    private static void ordinal() {
        byte[] image = image("ntdll.dll", 600, new long[] {0x1000, 0x1010}, new String[0], new int[0], Map.of());
        WindowsSystemExportPlan plan = one("ntdll.dll", image);
        check(plan.resolveOrdinal("ntdll.dll", 601).rva() == 0x1010);
        refuses(() -> plan.resolveOrdinal("ntdll.dll", 599));
        refuses(() -> plan.resolveOrdinal("ntdll.dll", 602));
        refuses(() -> plan.resolve("ntdll.dll", "Target"));
        byte[] highBase = image("ntdll.dll", 0xfffffffeL, new long[] {0x1000, 0x1010},
            new String[] {"Target"}, new int[] {1}, Map.of());
        check(one("ntdll.dll", highBase).resolve("ntdll.dll", "Target").ordinal() == 0xffffffffL);
    }

    private static void aliases() {
        byte[] image = image("kernelbase.dll", 17, new long[] {0x1000}, new String[] {"Alias", "Target"},
            new int[] {0, 0}, Map.of());
        WindowsSystemExportPlan plan = one("kernelbase.dll", image);
        check(plan.resolve("kernelbase.dll", "Alias").equals(plan.resolve("kernelbase.dll", "Target")));
        check(plan.resolve("kernelbase.dll", "Alias").ordinal() == 17);
    }

    private static void forwardName(boolean extension) {
        String forward = extension ? "KERNELBASE.dll.Target" : "KERNELBASE.Target";
        byte[] first = image("kernel32.dll", 1, new long[] {0}, new String[] {"Start"}, new int[] {0}, Map.of(0, forward));
        WindowsSystemExportPlan plan = pair(first, simple("kernelbase.dll"));
        WindowsSystemExportPlan.Target target = plan.resolve("kernel32.dll", "Start");
        check(target.module().equals("kernelbase.dll") && target.rva() == 0x1000 && target.ordinal() == 42);
    }

    private static void forwardOrdinal() {
        byte[] first = image("kernel32.dll", 1, new long[] {0}, new String[] {"Start"}, new int[] {0},
            Map.of(0, "kernelbase.#42"));
        check(pair(first, simple("kernelbase.dll")).resolve("kernel32.dll", "Start").ordinal() == 42);
        byte[] decorated = image("kernelbase.dll", 1, new long[] {0x1000}, new String[] {"?Name@@YAXXZ"},
            new int[] {0}, Map.of());
        check(one("kernelbase.dll", decorated).resolve("kernelbase.dll", "?Name@@YAXXZ").rva() == 0x1000);
    }

    private static void snapshot() {
        byte[] source = simple("kernel32.dll");
        WindowsSystemExportPlan.Input input = new WindowsSystemExportPlan.Input("kernel32.dll", source);
        byte[] copy = input.image();
        source[0] = 0;
        copy[0] = 0;
        WindowsSystemExportPlan.Input[] inventory = {input};
        WindowsSystemExportPlan plan = WindowsSystemExportPlan.parse(inventory);
        inventory[0] = null;
        check(input.image()[0] == 'M' && plan.resolve("kernel32.dll", "Target").rva() == 0x1000);
        check(input.image() != input.image());
    }

    private static void holes() {
        WindowsSystemExportPlan plan = one("kernel32.dll", simple("kernel32.dll"));
        refuses(() -> plan.resolveOrdinal("kernel32.dll", 41));
        refuses(() -> plan.resolve("kernel32.dll", "Missing"));
        byte[] namedHole = image("kernel32.dll", 1, new long[] {0}, new String[] {"Hole"}, new int[] {0}, Map.of());
        WindowsSystemExportPlan holePlan = one("kernel32.dll", namedHole);
        refuses(() -> holePlan.resolve("kernel32.dll", "Hole"));
    }

    private static void unavailable() {
        for (String target : new String[] {"absent.Target", "api-ms-win-core-test-l1-1-0.Target",
            "ext-ms-win-test-l1-1-0.Target"}) {
            byte[] image = image("kernel32.dll", 1, new long[] {0}, new String[] {"Start"}, new int[] {0}, Map.of(0, target));
            WindowsSystemExportPlan plan = one("kernel32.dll", image);
            refuses(() -> plan.resolve("kernel32.dll", "Start"));
        }
        byte[] unused = image("kernel32.dll", 1, new long[] {0, 0x1000}, new String[] {"Target"}, new int[] {1},
            Map.of(0, "api-ms-win-unused-l1-1-0.Target"));
        check(one("kernel32.dll", unused).resolve("kernel32.dll", "Target").rva() == 0x1000);
    }

    private static void cycle() {
        byte[] first = image("kernel32.dll", 1, new long[] {0}, new String[] {"Start"}, new int[] {0},
            Map.of(0, "kernelbase.Target"));
        byte[] second = image("kernelbase.dll", 1, new long[] {0}, new String[] {"Target"}, new int[] {0},
            Map.of(0, "kernel32.Start"));
        WindowsSystemExportPlan plan = pair(first, second);
        refuses(() -> plan.resolve("kernel32.dll", "Start"));
        byte[] aliases = image("kernel32.dll", 1, new long[] {0}, new String[] {"Alias", "Start"}, new int[] {0, 0},
            Map.of(0, "kernel32.Alias"));
        WindowsSystemExportPlan aliasPlan = one("kernel32.dll", aliases);
        refuses(() -> aliasPlan.resolve("kernel32.dll", "Start"));
    }

    private static void depth() {
        for (int count : new int[] {16, 17}) {
            long[] rvas = new long[count];
            rvas[count - 1] = 0x1000;
            Map<Integer, String> forward = new HashMap<>();
            for (int index = 0; index < count - 1; index++) forward.put(index, "kernel32.#" + (index + 2));
            WindowsSystemExportPlan plan = one("kernel32.dll",
                image("kernel32.dll", 1, rvas, new String[0], new int[0], forward));
            if (count == 16) check(plan.resolveOrdinal("kernel32.dll", 1).ordinal() == 16);
            else refuses(() -> plan.resolveOrdinal("kernel32.dll", 1));
        }
    }

    private static void headers() {
        byte[] source = simple("kernel32.dll");
        for (int[] change : new int[][] {{0, 0}, {0x80, 0}, {0x84, 0x14c}, {0x86, 0}, {0x86, 97},
            {0x94, 224}, {0x96, 0x202}, {OPTIONAL, 0x10b}}) {
            byte[] image = source.clone();
            put16(image, change[0], change[1]);
            refuses(() -> one("kernel32.dll", image));
        }
        for (int[] change : new int[][] {{0x3c, -1}, {OPTIONAL + 108, 15}, {OPTIONAL + 32, 512},
            {OPTIONAL + 36, 300}, {OPTIONAL + 56, -1}, {OPTIONAL + 60, 256}}) {
            byte[] image = source.clone();
            put32(image, change[0], change[1]);
            refuses(() -> one("kernel32.dll", image));
        }
        refuses(() -> one("another.dll", source));
    }

    private static void sections() {
        byte[] source = simple("kernel32.dll");
        for (int[] change : new int[][] {{SECTION_TABLE + 40 + 12, 0x1000}, {SECTION_TABLE + 40 + 20, 0x200},
            {SECTION_TABLE + 40 + 20, 0}, {SECTION_TABLE + 16, -1}, {SECTION_TABLE + 12, -1},
            {SECTION_TABLE + 40 + 12, 0x2800}}) {
            byte[] image = source.clone();
            put32(image, change[0], change[1]);
            refuses(() -> one("kernel32.dll", image));
        }
        byte[] noRaw = source.clone();
        put32(noRaw, SECTION_TABLE + 40 + 16, 0);
        put32(noRaw, SECTION_TABLE + 40 + 20, 0);
        refuses(() -> one("kernel32.dll", noRaw));
    }

    private static void tables() {
        byte[] source = simple("kernel32.dll");
        for (int[] change : new int[][] {{EXPORT + 16, -1}, {EXPORT + 20, 0}, {EXPORT + 20, 65_537},
            {EXPORT + 24, 65_537}, {EXPORT + 28, 0x2000}, {EXPORT + 28, -1},
            {EXPORT + 32, 0x2fff}, {EXPORT + 36, 0x100}}) {
            byte[] image = source.clone();
            put32(image, change[0], change[1]);
            refuses(() -> one("kernel32.dll", image));
        }
        byte[] duplicate = image("kernel32.dll", 1, new long[] {0x1000}, new String[] {"Same", "Same"},
            new int[] {0, 0}, Map.of());
        refuses(() -> one("kernel32.dll", duplicate));
        byte[] unsorted = image("kernel32.dll", 1, new long[] {0x1000}, new String[] {"Z", "A"},
            new int[] {0, 0}, Map.of());
        refuses(() -> one("kernel32.dll", unsorted));
        byte[] badIndex = image("kernel32.dll", 1, new long[] {0x1000}, new String[] {"Target"}, new int[] {1}, Map.of());
        refuses(() -> one("kernel32.dll", badIndex));
        long[] overlappingFunctions = new long[66];
        Arrays.fill(overlappingFunctions, 0x1000);
        byte[] tableString = image("kernel32.dll", 1, overlappingFunctions, new String[] {"A"}, new int[] {65}, Map.of());
        check(one("kernel32.dll", tableString).resolve("kernel32.dll", "A").ordinal() == 66);
        // Ordinal 65 has bytes 'A', NUL. Without the metadata exclusion it is a valid-looking export name.
        int pointers = raw((int) u32(tableString, EXPORT + 32));
        put32(tableString, pointers, u32(tableString, EXPORT + 36));
        refuses(() -> one("kernel32.dll", tableString));
    }

    private static void strings() {
        for (String forward : new String[] {"kernelbase", ".Target", "kernelbase.", "C:\\kernelbase.Target",
            "kernelbase/other.Target", "kernelbase.#0", "kernelbase.#01", "kernelbase.#65536", "kernelbase.#x",
            "kernelbase.#999999999999", "kernelbase.Target\n", "kernelbase.Target/Other"}) {
            byte[] image = image("kernel32.dll", 1, new long[] {0}, new String[] {"Start"}, new int[] {0}, Map.of(0, forward));
            refuses(() -> one("kernel32.dll", image));
        }
        byte[] unterminated = image("kernel32.dll", 1, new long[] {0}, new String[] {"Start"}, new int[] {0},
            Map.of(0, "kernelbase.Target"));
        int end = (int) u32(unterminated, OPTIONAL + 112) + (int) u32(unterminated, OPTIONAL + 116);
        put32(unterminated, raw((int) u32(unterminated, EXPORT + 28)), end - 2);
        unterminated[raw(end - 2)] = 'A';
        unterminated[raw(end - 1)] = 'B';
        refuses(() -> one("kernel32.dll", unterminated));
        String destination = "kernelbase.Target";
        byte[] boundary = image("kernel32.dll", 1, new long[] {0}, new String[] {"Start"}, new int[] {0},
            Map.of(0, destination));
        long forwardRva = u32(boundary, raw((int) u32(boundary, EXPORT + 28)));
        long directoryRva = u32(boundary, OPTIONAL + 112);
        long exactExtent = forwardRva - directoryRva + destination.length() + 1;
        put32(boundary, OPTIONAL + 116, exactExtent); // The final allowed byte is the actual NUL.
        check(pair(boundary, simple("kernelbase.dll")).resolve("kernel32.dll", "Start").ordinal() == 42);
        put32(boundary, OPTIONAL + 116, exactExtent - 1); // Same NUL now lies just beyond the directory.
        refuses(() -> pair(boundary, simple("kernelbase.dll")));
        byte[] high = simple("kernel32.dll");
        int nameRva = (int) u32(high, raw((int) u32(high, EXPORT + 32)));
        high[raw(nameRva)] = (byte) 0xff;
        refuses(() -> one("kernel32.dll", high));
    }

    private static void targets() {
        byte[] lastRawByte = image("kernel32.dll", 1, new long[] {0x11ff}, new String[] {"Target"}, new int[] {0}, Map.of());
        check(one("kernel32.dll", lastRawByte).resolve("kernel32.dll", "Target").rva() == 0x11ff);
        for (long target : new long[] {0x100, 0x1200, 0x1300, 0x3000, 0xffffffffL}) {
            byte[] image = image("kernel32.dll", 1, new long[] {target}, new String[] {"Target"}, new int[] {0}, Map.of());
            refuses(() -> one("kernel32.dll", image).resolve("kernel32.dll", "Target"));
        }
        byte[] metadataTarget = image("kernel32.dll", 1, new long[] {0x1040}, new String[] {"Target"}, new int[] {0}, Map.of());
        put32(metadataTarget, EXPORT + 28, 0x1040); // Complete EAT moved into raw-backed executable bytes.
        put32(metadataTarget, raw(0x1040), 0x1040);
        WindowsSystemExportPlan metadataPlan = one("kernel32.dll", metadataTarget);
        refuses(() -> metadataPlan.resolve("kernel32.dll", "Target"));
        for (boolean moduleString : new boolean[] {true, false}) {
            byte[] stringTarget = simple("kernel32.dll");
            int executableRva = moduleString ? 0x1040 : 0x1080;
            string(stringTarget, executableRva, moduleString ? "kernel32.dll" : "Target");
            if (moduleString) put32(stringTarget, EXPORT + 12, executableRva);
            else put32(stringTarget, raw((int) u32(stringTarget, EXPORT + 32)), executableRva);
            put32(stringTarget, raw((int) u32(stringTarget, EXPORT + 28)) + 4, executableRva);
            // Parsing succeeds: these strings have unambiguous raw-backed executable placement.
            // Resolving into their metadata bytes must nevertheless fail rather than publish a target.
            WindowsSystemExportPlan stringPlan = one("kernel32.dll", stringTarget);
            refuses(() -> stringPlan.resolve("kernel32.dll", "Target"));
        }
        for (long flags : new long[] {0x40000040L, 0x20000020L, 0xe0000020L}) {
            byte[] image = simple("kernel32.dll");
            put32(image, SECTION_TABLE + 36, flags);
            refuses(() -> one("kernel32.dll", image).resolve("kernel32.dll", "Target"));
        }
    }

    private static byte[] zeroFillImage(String module, long target, boolean entirelyZero) {
        byte[] image = image(module, 41, new long[] {target, 0x1000}, new String[] {"Data", "Target"},
            new int[] {0, 1}, Map.of());
        int rawBytes = entirelyZero ? 0 : 512;
        int raw = entirelyZero ? 0 : image.length;
        image = Arrays.copyOf(image, image.length + rawBytes);
        put16(image, 0x86, 3);
        put32(image, OPTIONAL + 56, 0x4000);
        section(image, SECTION_TABLE + 80, ".data", 0x3000, rawBytes, raw, 0xc0000040L);
        put32(image, SECTION_TABLE + 80 + 8, 0x301); // Deliberately not page aligned.
        return image;
    }

    private static void zeroFillData(boolean entirelyZero) {
        for (long target : new long[] {entirelyZero ? 0x3000 : 0x3200, 0x3300}) {
            WindowsSystemExportPlan plan = one("kernel32.dll", zeroFillImage("kernel32.dll", target, entirelyZero));
            check(plan.resolve("kernel32.dll", "Target").rva() == 0x1000);
            check(plan.resolveOrdinal("kernel32.dll", 42).rva() == 0x1000);
            refuses(() -> plan.resolve("kernel32.dll", "Data"));
            refuses(() -> plan.resolveOrdinal("kernel32.dll", 41));
        }
    }

    private static void zeroFillBounds() {
        // Rounded mapping padding, image end, gaps and invalid RVAs do not become valid data exports.
        for (long target : new long[] {0x100, 0x2fff, 0x3301, 0x3fff, 0x4000, 0xffffffffL}) {
            byte[] image = zeroFillImage("kernel32.dll", target, false);
            refuses(() -> one("kernel32.dll", image));
        }
        // Executable/unreadable zero-fill cannot enter even a copied data graph.
        for (long flags : new long[] {0x60000020L, 0xe0000020L, 0x20000020L, 0x80000080L, 0}) {
            byte[] image = zeroFillImage("kernel32.dll", 0x3200, false);
            put32(image, SECTION_TABLE + 80 + 36, flags);
            refuses(() -> one("kernel32.dll", image));
        }
        for (int field : new int[] {8, 12, 16, 20}) {
            byte[] image = zeroFillImage("kernel32.dll", 0x3200, false);
            put32(image, SECTION_TABLE + 80 + field, 0xffffffffL);
            refuses(() -> one("kernel32.dll", image));
        }
        // Export tables and names must still be present in the file, never read from synthesized zeros.
        for (int field : new int[] {12, 28, 32, 36}) {
            byte[] image = zeroFillImage("kernel32.dll", 0x3200, false);
            put32(image, EXPORT + field, 0x3200);
            refuses(() -> one("kernel32.dll", image));
        }
    }

    private static void zeroFillForwarders() {
        byte[] second = zeroFillImage("kernelbase.dll", 0x3200, false);
        for (String symbol : new String[] {"Data", "#41"}) {
            byte[] first = image("kernel32.dll", 1, new long[] {0}, new String[] {"Start"}, new int[] {0},
                Map.of(0, "kernelbase." + symbol));
            WindowsSystemExportPlan plan = pair(first, second);
            check(plan.resolve("kernelbase.dll", "Target").rva() == 0x1000);
            refuses(() -> plan.resolve("kernel32.dll", "Start"));
        }
        byte[] forwardInZeroFill = zeroFillImage("kernel32.dll", 0x3200, false);
        put32(forwardInZeroFill, OPTIONAL + 116, 0x1300);
        refuses(() -> one("kernel32.dll", forwardInZeroFill));
    }

    private static void bounds() {
        WindowsSystemExportPlan plan = one("kernel32.dll", simple("kernel32.dll"));
        for (long ordinal : new long[] {Long.MIN_VALUE, -1, 0, 65_536, Long.MAX_VALUE}) {
            refuses(() -> plan.resolveOrdinal("kernel32.dll", ordinal));
        }
        for (String name : new String[] {"", "#42", "Private\n", "a".repeat(256), "path/name", "x:y"}) {
            refuses(() -> plan.resolve("kernel32.dll", name));
        }
        refuses(() -> plan.resolve("kernel32.dll", null));
        refuses(() -> plan.resolve("absent.dll", "Target"));
    }

    private static void work() {
        Map<Integer, String> forwarders = new HashMap<>();
        String target = "kernelbase." + "F".repeat(240);
        for (int index = 0; index < 65_536; index++) forwarders.put(index, target);
        byte[] image = image("kernel32.dll", 1, new long[65_536], new String[0], new int[0], forwarders);
        check(image.length < 32 * 1024 * 1024);
        refuses(() -> one("kernel32.dll", image)); // Aggregate parser work, not a tiny malformed table.
    }

    private static void inventory() {
        byte[] image = simple("kernel32.dll");
        for (String module : new String[] {"", "kernel32", "../kernel32.dll", "C:\\kernel32.dll", "a/b.dll",
            "kernel32.dll ", "\u212aernel32.dll", "api-ms-win-test.dll", "ext-ms-win-test.dll"}) {
            refuses(() -> new WindowsSystemExportPlan.Input(module, image));
        }
        refuses(() -> new WindowsSystemExportPlan.Input("kernel32.dll", null));
        refuses(() -> new WindowsSystemExportPlan.Input("kernel32.dll", new byte[511]));
        refuses(() -> WindowsSystemExportPlan.parse(null));
        refuses(() -> WindowsSystemExportPlan.parse(new WindowsSystemExportPlan.Input[0]));
        refuses(() -> WindowsSystemExportPlan.parse(new WindowsSystemExportPlan.Input[17]));
        refuses(() -> WindowsSystemExportPlan.parse(new WindowsSystemExportPlan.Input[] {null}));
        WindowsSystemExportPlan.Input original = new WindowsSystemExportPlan.Input("kernel32.dll", image);
        refuses(() -> WindowsSystemExportPlan.parse(new WindowsSystemExportPlan.Input[] {original, original}));
    }

    private static void aggregate() {
        final int fileLimit = 32 * 1024 * 1024;
        final long aggregateLimit = 128L * 1024 * 1024;
        long total = 0;
        for (int index = 0; index < 4; index++) {
            total = WindowsSystemExportPlan.checkedAggregateSize(total, fileLimit);
            check(total == (long) (index + 1) * fileLimit);
        }
        check(total == aggregateLimit && WindowsSystemExportPlan.checkedAggregateSize(aggregateLimit, 0) == aggregateLimit);
        check(WindowsSystemExportPlan.checkedAggregateSize(aggregateLimit - 1, 1) == aggregateLimit);
        check(WindowsSystemExportPlan.checkedAggregateSize(0, 0) == 0);
        check(WindowsSystemExportPlan.checkedAggregateSize(0, 512) == 512);
        for (long current : new long[] {Long.MIN_VALUE, -1, aggregateLimit + 1, Long.MAX_VALUE}) {
            refuses(() -> WindowsSystemExportPlan.checkedAggregateSize(current, 0));
        }
        for (int additional : new int[] {Integer.MIN_VALUE, -1, Integer.MAX_VALUE}) {
            refuses(() -> WindowsSystemExportPlan.checkedAggregateSize(0, additional));
        }
        refuses(() -> WindowsSystemExportPlan.checkedAggregateSize(aggregateLimit, 1));
        refuses(() -> WindowsSystemExportPlan.checkedAggregateSize(aggregateLimit - 1, 2));
        refuses(() -> WindowsSystemExportPlan.checkedAggregateSize(aggregateLimit, fileLimit));
        refuses(() -> WindowsSystemExportPlan.checkedAggregateSize(Long.MAX_VALUE, Integer.MAX_VALUE));
        // Exercise the real parser's production-used addition path with five small valid copied images.
        // Numeric cap/overflow controls above do not require allocating the cap under a 128 MiB JVM heap.
        WindowsSystemExportPlan.Input[] inventory = new WindowsSystemExportPlan.Input[5];
        for (int index = 0; index < inventory.length; index++) {
            String module = "module" + index + ".dll";
            inventory[index] = new WindowsSystemExportPlan.Input(module, simple(module));
        }
        WindowsSystemExportPlan plan = WindowsSystemExportPlan.parse(inventory);
        for (int index = 0; index < inventory.length; index++) {
            check(plan.resolve("module" + index + ".dll", "Target").ordinal() == 42);
        }
    }

    private static byte[] simple(String module) {
        return image(module, 41, new long[] {0, 0x1000, 0x1010}, new String[] {"Target"}, new int[] {1}, Map.of());
    }
    private static WindowsSystemExportPlan one(String module, byte[] image) {
        return WindowsSystemExportPlan.parse(new WindowsSystemExportPlan.Input[] {new WindowsSystemExportPlan.Input(module, image)});
    }
    private static WindowsSystemExportPlan pair(byte[] first, byte[] second) {
        return WindowsSystemExportPlan.parse(new WindowsSystemExportPlan.Input[] {
            new WindowsSystemExportPlan.Input("kernel32.dll", first), new WindowsSystemExportPlan.Input("kernelbase.dll", second)});
    }

    private static byte[] image(String module, long ordinalBase, long[] functions, String[] names, int[] indexes,
                                Map<Integer, String> forwarders) {
        check(names.length == indexes.length);
        int functionTable = 0x2040;
        int nameTable = aligned(functionTable + functions.length * 4, 8);
        int ordinalTable = aligned(nameTable + names.length * 4, 8);
        int strings = aligned(ordinalTable + names.length * 2, 16);
        int stringBytes = module.length() + 1;
        for (String name : names) stringBytes += name.length() + 1;
        for (String forward : forwarders.values()) stringBytes += forward.length() + 1;
        int rawBytes = aligned(strings - 0x2000 + stringBytes, 512);
        byte[] image = new byte[EXPORT + rawBytes];
        put16(image, 0, 0x5a4d);
        put32(image, 0x3c, 0x80);
        put32(image, 0x80, 0x4550);
        put16(image, 0x84, 0x8664);
        put16(image, 0x86, 2);
        put16(image, 0x94, 240);
        put16(image, 0x96, 0x2022);
        put16(image, OPTIONAL, 0x20b);
        put32(image, OPTIONAL + 32, 4096);
        put32(image, OPTIONAL + 36, 512);
        put32(image, OPTIONAL + 56, 0x2000L + aligned(rawBytes, 4096));
        put32(image, OPTIONAL + 60, 512);
        put32(image, OPTIONAL + 108, 16);
        put32(image, OPTIONAL + 112, 0x2000);
        put32(image, OPTIONAL + 116, rawBytes);
        section(image, SECTION_TABLE, ".text", 0x1000, 512, 512, 0x60000020L);
        section(image, SECTION_TABLE + 40, ".edata", 0x2000, rawBytes, EXPORT, 0x40000040L);
        image[0x200] = (byte) 0xc3;
        put32(image, EXPORT + 12, strings);
        put32(image, EXPORT + 16, ordinalBase);
        put32(image, EXPORT + 20, functions.length);
        put32(image, EXPORT + 24, names.length);
        put32(image, EXPORT + 28, functionTable);
        put32(image, EXPORT + 32, names.length == 0 ? 0 : nameTable);
        put32(image, EXPORT + 36, names.length == 0 ? 0 : ordinalTable);
        for (int index = 0; index < functions.length; index++) put32(image, raw(functionTable) + index * 4, functions[index]);
        strings += string(image, strings, module);
        for (int index = 0; index < names.length; index++) {
            put32(image, raw(nameTable) + index * 4, strings);
            put16(image, raw(ordinalTable) + index * 2, indexes[index]);
            strings += string(image, strings, names[index]);
        }
        for (Map.Entry<Integer, String> forwarder : forwarders.entrySet()) {
            put32(image, raw(functionTable) + forwarder.getKey() * 4, strings);
            strings += string(image, strings, forwarder.getValue());
        }
        return image;
    }

    private static void section(byte[] image, int at, String name, int rva, int bytes, int raw, long flags) {
        System.arraycopy(name.getBytes(StandardCharsets.US_ASCII), 0, image, at, name.length());
        put32(image, at + 8, bytes);
        put32(image, at + 12, rva);
        put32(image, at + 16, bytes);
        put32(image, at + 20, raw);
        put32(image, at + 36, flags);
    }
    private static int string(byte[] image, int rva, String text) {
        byte[] bytes = text.getBytes(StandardCharsets.US_ASCII);
        System.arraycopy(bytes, 0, image, raw(rva), bytes.length);
        return bytes.length + 1;
    }
    private static int raw(int rva) { return rva < 0x2000 ? 0x200 + rva - 0x1000 : EXPORT + rva - 0x2000; }
    private static int aligned(int value, int alignment) { return (value + alignment - 1) & -alignment; }
    private static long u32(byte[] bytes, int at) {
        return Integer.toUnsignedLong((bytes[at] & 255) | (bytes[at + 1] & 255) << 8 |
            (bytes[at + 2] & 255) << 16 | (bytes[at + 3] & 255) << 24);
    }
    private static void put16(byte[] bytes, int at, int value) {
        bytes[at] = (byte) value;
        bytes[at + 1] = (byte) (value >>> 8);
    }
    private static void put32(byte[] bytes, int at, long value) {
        for (int index = 0; index < 4; index++) bytes[at + index] = (byte) (value >>> (8 * index));
    }
    private static void refuses(Runnable action) {
        try { action.run(); }
        catch (IllegalArgumentException expected) { return; }
        throw new AssertionError("Expected copied system-export refusal");
    }
    private static void check(boolean condition) {
        if (!condition) throw new AssertionError("Copied system-export control failed");
    }
}
