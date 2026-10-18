package dev.p2pkit.rpc.windows.loader;

import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Comparator;
import java.util.List;
import java.util.Map;

/** Synthetic namespace bounds/routing tests only; no OS namespace, module lookup or native load. */
public final class ApiSetPlanTests {
    private static final String CONTRACT = "api-ms-win-core-example-l1-1-3";
    private static final String REQUEST = "api-ms-win-core-example-l1-1-0.dll";
    private ApiSetPlanTests() {}

    public static void main(String[] args) {
        switch (args[0]) {
            case "default-host" -> defaultHost();
            case "snapshot" -> snapshot();
            case "headers" -> headers();
            case "ranges" -> ranges();
            case "hashes" -> hashes();
            case "metadata-alias" -> metadataAlias();
            case "contracts" -> contracts();
            case "revisions" -> revisions();
            case "values" -> values();
            case "strings" -> strings();
            case "bounds" -> bounds();
            case "collisions" -> collisions();
            case "graph" -> graph();
            default -> throw new IllegalArgumentException("Unknown API-set test");
        }
        System.out.println("API_SET_PLAN_MODEL_PASS");
    }

    private static void defaultHost() {
        WindowsApiSetPlan plan = WindowsApiSetPlan.parse(simple());
        check(plan.defaultHost(REQUEST).equals("kernelbase.dll"));
        check(plan.defaultHost(CONTRACT).equals("kernelbase.dll"));
        check(plan.defaultHost(REQUEST.toUpperCase(java.util.Locale.ROOT)).equals("kernelbase.dll"));
    }

    private static void snapshot() {
        byte[] source = simple();
        WindowsApiSetPlan plan = WindowsApiSetPlan.parse(source);
        Arrays.fill(source, (byte) 0);
        check(plan.defaultHost(REQUEST).equals("kernelbase.dll"));
    }

    private static void headers() {
        for (int[] change : new int[][] {{0, 0}, {0, 5}, {0, 7}, {4, 28}, {4, -1}, {8, 1},
            {12, 0}, {12, 8193}, {12, -1}, {24, 0}, {24, 2}}) {
            byte[] image = simple();
            put(image, change[0], change[1]);
            refuses(() -> WindowsApiSetPlan.parse(image));
        }
    }

    private static void ranges() {
        for (int offset : new int[] {16, 20, 28 + 16}) {
            for (int value : new int[] {-1, 1, 8192, 8188}) {
                byte[] image = simple();
                put(image, offset, value);
                refuses(() -> WindowsApiSetPlan.parse(image));
            }
        }
        byte[] overlap = simple();
        put(overlap, 20, 28);
        refuses(() -> WindowsApiSetPlan.parse(overlap));
        byte[] finalOverlap = simple();
        put(finalOverlap, 28 + 16, 28);
        refuses(() -> WindowsApiSetPlan.parse(finalOverlap));
    }

    private static void hashes() {
        for (boolean wrongIndex : new boolean[] {false, true}) {
            byte[] image = simple();
            put(image, get(image, 20) + (wrongIndex ? 4 : 0), wrongIndex ? 1 : 123);
            refuses(() -> WindowsApiSetPlan.parse(image));
        }
        byte[] image = image(31, spec(CONTRACT), spec("ext-ms-win-example-l1-1-0"));
        int at = get(image, 20);
        put(image, at + 12, get(image, at + 4));
        refuses(() -> WindowsApiSetPlan.parse(image));
    }

    private static void metadataAlias() {
        byte[] source = simple();
        for (int at : new int[] {28 + 4, get(source, 28 + 16) + 12}) {
            byte[] image = source.clone();
            put(image, at, 28);
            refuses(() -> WindowsApiSetPlan.parse(image));
        }
        byte[] nested = simple();
        put(nested, 28 + 16, get(nested, 20));
        refuses(() -> WindowsApiSetPlan.parse(nested));
    }

    private static void contracts() {
        for (String invalid : new String[] {"kernel32.dll", "api-ms-test", "api-ms-x-l1-1-01", "api-ms-x-l1-1-",
            "api-ms-x-l1-1-10000", "api-ms-x-l1-1-0.dll", "api-ms-x-l1-1-0/", "api-ms-x-l1-1-0\u0000"}) {
            refuses(() -> WindowsApiSetPlan.parse(image(31, spec(invalid))));
        }
        refuses(() -> WindowsApiSetPlan.parse(image(31, spec(CONTRACT), spec(CONTRACT))));
        refuses(() -> WindowsApiSetPlan.parse(image(31, spec(CONTRACT), spec(CONTRACT.replace("-3", "-2")))));
        byte[] wrongPrefix = simple();
        put(wrongPrefix, 28 + 12, CONTRACT.length() * 2);
        refuses(() -> WindowsApiSetPlan.parse(wrongPrefix));
    }

    private static void revisions() {
        WindowsApiSetPlan plan = WindowsApiSetPlan.parse(simple());
        for (String invalid : new String[] {CONTRACT.replace("-3", "-4"), "api-ms-win-core-example-l1-2-0",
            "api-ms-win-core-example-l2-1-0", "kernelbase.dll", "../" + REQUEST, "", REQUEST + "\n"}) {
            refuses(() -> plan.defaultHost(invalid));
        }
        refuses(() -> plan.defaultHost(null));
        WindowsApiSetPlan unsealed = WindowsApiSetPlan.parse(image(31,
            new Spec(CONTRACT, 0, new String[][] {{"", "kernelbase.dll"}})));
        refuses(() -> unsealed.defaultHost(REQUEST));
    }

    private static void values() {
        for (String[][] values : new String[][][] {
            {{"kernel32.dll", "kernelbase.dll"}}, {{"", "kernelbase.dll"}, {"kernel32.dll", "combase.dll"}},
            {{"", ""}}, {{"", "api-ms-win-test-l1-1-0.dll"}},
            {{"", "winspool.drv"}}, {{"", "ntosext.sys"}},
        }) {
            WindowsApiSetPlan plan = WindowsApiSetPlan.parse(image(31, new Spec(CONTRACT, 1, values)));
            refuses(() -> plan.defaultHost(REQUEST));
        }
        refuses(() -> WindowsApiSetPlan.parse(image(31, new Spec(CONTRACT, 1,
            new String[][] {{"", "kernelbase.dll"}, {"", "combase.dll"}}))));
        for (int count : new int[] {0, 17, -1}) {
            byte[] image = simple(); put(image, 28 + 20, count);
            refuses(() -> WindowsApiSetPlan.parse(image));
        }
        byte[] image = simple(); put(image, get(image, 28 + 16), 1);
        refuses(() -> WindowsApiSetPlan.parse(image));
    }

    private static void strings() {
        for (String host : new String[] {"../evil.dll", "C:\\evil.dll", "evil.dll\u0000", "evil.DLL", "..dll", "evil"}) {
            refuses(() -> WindowsApiSetPlan.parse(image(31, new Spec(CONTRACT, 1, new String[][] {{"", host}}))));
        }
        for (int size : new int[] {1, 514, -1}) {
            byte[] image = simple(); put(image, 28 + 8, size);
            refuses(() -> WindowsApiSetPlan.parse(image));
        }
        byte[] unicode = simple(); unicode[get(unicode, 28 + 4) + 1] = 1;
        refuses(() -> WindowsApiSetPlan.parse(unicode));
    }

    private static void bounds() {
        refuses(() -> WindowsApiSetPlan.parse(null));
        for (byte[] input : new byte[][] {new byte[0], new byte[27], new byte[WindowsApiSetPlan.MAXIMUM_BYTES + 1]}) {
            refuses(() -> WindowsApiSetPlan.parse(input));
        }
        byte[] size = simple(); put(size, 28 + 4, -2);
        refuses(() -> WindowsApiSetPlan.parse(size));
    }

    private static void collisions() {
        WindowsApiSetPlan plan = WindowsApiSetPlan.parse(image(1,
            spec("api-ms-win-ab-l1-1-0"), spec("api-ms-win-ba-l1-1-0")));
        check(plan.defaultHost("api-ms-win-ab-l1-1-0").equals("kernelbase.dll"));
        check(plan.defaultHost("api-ms-win-ba-l1-1-0").equals("kernelbase.dll"));
    }

    private static void graph() {
        WindowsApiSetPlan namespace = WindowsApiSetPlan.parse(simple());
        for (String target : new String[] {"Target", "#1"}) {
            byte[] forwarder = SystemExportPlanTests.image("kernel32.dll", 1, new long[] {0},
                new String[] {"Start"}, new int[] {0}, Map.of(0, REQUEST + "." + target));
            byte[] host = SystemExportPlanTests.image("kernelbase.dll", 1, new long[] {0x1000},
                new String[] {"Target"}, new int[] {0}, Map.of());
            WindowsSystemExportPlan graph = WindowsSystemExportPlan.parse(new WindowsSystemExportPlan.Input[] {
                new WindowsSystemExportPlan.Input("kernel32.dll", forwarder),
                new WindowsSystemExportPlan.Input("kernelbase.dll", host),
            });
            check(graph.resolve("kernel32.dll", "Start", namespace).equals(
                new WindowsSystemExportPlan.Target("kernelbase.dll", 0x1000, 1)));
            refuses(() -> graph.resolve("kernel32.dll", "Start"));
            WindowsSystemExportPlan missing = WindowsSystemExportPlan.parse(new WindowsSystemExportPlan.Input[] {
                new WindowsSystemExportPlan.Input("kernel32.dll", forwarder),
            });
            refuses(() -> missing.resolve("kernel32.dll", "Start", namespace));
            byte[] cyclic = SystemExportPlanTests.image("kernelbase.dll", 1, new long[] {0},
                new String[] {"Target"}, new int[] {0}, Map.of(0, "kernel32.Start"));
            WindowsSystemExportPlan cycle = WindowsSystemExportPlan.parse(new WindowsSystemExportPlan.Input[] {
                new WindowsSystemExportPlan.Input("kernel32.dll", forwarder),
                new WindowsSystemExportPlan.Input("kernelbase.dll", cyclic),
            });
            refuses(() -> cycle.resolve("kernel32.dll", "Start", namespace));
        }
    }

    private record Spec(String name, int flags, String[][] values) {}
    private static Spec spec(String name) { return new Spec(name, 1, new String[][] {{"", "kernelbase.dll"}}); }
    private static byte[] simple() { return image(31, spec(CONTRACT)); }
    static byte[] namespaceData() { return simple(); }
    static byte[] namespaceWithHost(String host) { return image(31, new Spec(CONTRACT, 1, new String[][] {{"", host}})); }

    private static byte[] image(int factor, Spec... entries) {
        byte[] data = new byte[8192];
        int hashesAt = 28 + entries.length * 24;
        int valueAt = hashesAt + entries.length * 8;
        int textAt = 4096;
        put(data, 0, 6); put(data, 4, data.length); put(data, 12, entries.length);
        put(data, 16, 28); put(data, 20, hashesAt); put(data, 24, factor);
        List<long[]> hashes = new ArrayList<>();
        for (int index = 0; index < entries.length; index++) {
            Spec entry = entries[index];
            int at = 28 + index * 24;
            put(data, at, entry.flags); put(data, at + 4, textAt); put(data, at + 8, entry.name.length() * 2);
            int prefix = entry.name.lastIndexOf('-');
            put(data, at + 12, Math.max(0, prefix * 2));
            textAt = text(data, textAt, entry.name);
            put(data, at + 16, valueAt); put(data, at + 20, entry.values.length);
            for (String[] value : entry.values) {
                put(data, valueAt + 4, textAt); put(data, valueAt + 8, value[0].length() * 2);
                textAt = text(data, textAt, value[0]);
                put(data, valueAt + 12, textAt); put(data, valueAt + 16, value[1].length() * 2);
                textAt = text(data, textAt, value[1]); valueAt += 20;
            }
            long hash = 0;
            for (int character = 0; character < prefix; character++) hash = (hash * factor + entry.name.charAt(character)) & 0xffffffffL;
            hashes.add(new long[] {hash, index});
        }
        hashes.sort(Comparator.comparingLong(value -> value[0]));
        for (int index = 0; index < hashes.size(); index++) {
            put(data, hashesAt + index * 8, (int) hashes.get(index)[0]);
            put(data, hashesAt + index * 8 + 4, (int) hashes.get(index)[1]);
        }
        return data;
    }

    private static int text(byte[] data, int at, String value) {
        byte[] encoded = value.getBytes(StandardCharsets.UTF_16LE);
        System.arraycopy(encoded, 0, data, at, encoded.length);
        return at + encoded.length;
    }
    private static void put(byte[] data, int at, int value) {
        for (int index = 0; index < 4; index++) data[at + index] = (byte) (value >>> (index * 8));
    }
    private static int get(byte[] data, int at) {
        int value = 0;
        for (int index = 0; index < 4; index++) value |= (data[at + index] & 255) << (index * 8);
        return value;
    }
    private static void refuses(Runnable action) {
        try { action.run(); } catch (IllegalArgumentException expected) { return; }
        throw new AssertionError("Expected namespace refusal");
    }
    private static void check(boolean value) { if (!value) throw new AssertionError(); }
}
