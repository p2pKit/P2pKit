package dev.p2pkit.build;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;
import java.util.List;
import javax.tools.JavaCompiler;
import javax.tools.ToolProvider;

/** Real classfile controls; no application class is loaded or initialized by the verifier. */
public final class PublicConstantAbiTest {
    private static final String LEGACY = "fixture/Api#LEGACY Ljava/lang/String;";
    private static final String SOURCE = """
        package fixture;
        public class Api<T> {
            public static final String LEGACY = "retained";
            public static final int NUMBER = 17;
            public static final boolean FLAG = true;
            public static final byte BYTE = 1;
            public static final short SHORT = 2;
            public static final char CHARACTER = '\\n';
            public static final float FLOAT = Float.NaN;
            public static final double DOUBLE = Double.NEGATIVE_INFINITY;
            public static final String ESCAPED = "first\\nsecond\\\"line";
            public static final String RUNTIME = new String("not a ConstantValue");
            public static final Object OBJECT = new Object();
            private static final int PRIVATE = 4;
            public static int mutable = 5;
            public void extraMethod() {}
            public static class Nested {
                protected static final long NESTED = 6;
            }
            static {
                if (System.getProperty("p2pkit.test.shouldNeverInitialize") == null) {
                    throw new AssertionError("ABI inspection must not initialize application classes");
                }
            }
        }
        class Internal {
            public static final int NOT_A_SUPPORTED_OWNER = 7;
        }
        interface Contract {
            int INTERFACE_NUMBER = 8;
        }
        """;
    private static final String BASELINE = """
        public class fixture/Api {
            public static final field NUMBER I
            public static final field FLAG Z
            public static final field BYTE B
            public static final field SHORT S
            public static final field CHARACTER C
            public static final field FLOAT F
            public static final field DOUBLE D
            public static final field ESCAPED Ljava/lang/String;
            public static final field RUNTIME Ljava/lang/String;
        }
        public class fixture/Api$Nested {
            protected static final field NESTED J
        }
        public abstract interface class fixture/Contract {
            public static final field INTERFACE_NUMBER I
        }
        """;

    private final Path root;
    private final Path classes;
    private final Path api;
    private int checks;

    private PublicConstantAbiTest(Path root) throws IOException {
        this.root = root;
        classes = Files.createDirectories(root.resolve("classes with spaces"));
        api = root.resolve("fixture.api");
    }

    public static void main(String[] args) throws IOException {
        PublicConstantAbiTest suite = new PublicConstantAbiTest(Path.of(args[0]));
        suite.run();
        System.out.println("PASS: " + suite.checks + " compiled constant ABI controls (JDK " +
            System.getProperty("java.version") + ")");
    }

    private void compile(String source) throws IOException {
        Path input = root.resolve("Api.java");
        Files.writeString(input, source);
        JavaCompiler compiler = ToolProvider.getSystemJavaCompiler();
        if (compiler == null || compiler.run(null, null, null, "--release", "17", "-proc:none",
            "-encoding", "UTF-8", "-d", classes.toString(), input.toString()) != 0) {
            throw new AssertionError("Fixture must compile before checking ABI");
        }
    }

    private PublicConstantAbi.Result verify(String baseline, List<String> retained) throws IOException {
        Files.writeString(api, baseline);
        return PublicConstantAbi.verify(api, List.of(classes), retained);
    }

    private void accepted(String name, String baseline, List<String> retained, int expectedConstants) throws IOException {
        PublicConstantAbi.Result result = verify(baseline, retained);
        if (result.classes() != 3 || result.constants() != expectedConstants || result.retained() != retained.size()) {
            throw new AssertionError(name + ": incorrect inspection counts: " + result);
        }
        checks++;
    }

    private void rejected(String name, String baseline, List<String> retained, String diagnostic) throws IOException {
        expectFailure(name, () -> verify(baseline, retained), diagnostic);
    }

    private void expectFailure(String name, CheckedAction action, String diagnostic) throws IOException {
        try {
            action.run();
        } catch (IOException expected) {
            if (!expected.getMessage().contains(diagnostic)) throw new AssertionError(name, expected);
            checks++;
            return;
        }
        throw new AssertionError(name + ": verifier accepted a deliberately invalid case");
    }

    private void run() throws IOException {
        compile(SOURCE);
        // Covers all primitive/String descriptors, escaped values, generic/nested/interface owners,
        // non-constant fields, and an unlisted internal owner. Static initializer must never execute.
        accepted("original", BASELINE, List.of(LEGACY), 11);
        rejected("unrecorded legacy", BASELINE, List.of(), "fixture/Api#LEGACY Ljava/lang/String;");
        rejected("wrong legacy descriptor", BASELINE, List.of("fixture/Api#LEGACY J"),
            "missing retained public constants: [fixture/Api#LEGACY J]");
        rejected("stale exception", BASELINE, List.of(LEGACY, "fixture/Api#REMOVED I"),
            "missing retained public constants: [fixture/Api#REMOVED I]");
        rejected("duplicate exception", BASELINE, List.of(LEGACY, LEGACY), "Duplicate retained constant");
        rejected("wildcard exception", BASELINE, List.of("fixture/*#LEGACY Ljava/lang/String;"),
            "Invalid retained constant");
        rejected("unscoped exception", BASELINE, List.of("fixture/Internal#NOT_A_SUPPORTED_OWNER I"),
            "Invalid retained constant");
        rejected("redundant exception", BASELINE, List.of("fixture/Api#NUMBER I"), "Redundant retained constant");
        rejected("empty baseline", "// no declarations\n", List.of(), "ABI baseline contains no classes");
        rejected("duplicate owner", BASELINE + "public class fixture/Api {\n}\n", List.of(), "Duplicate ABI class");
        rejected("field outside owner", "public static final field NUMBER I\n" + BASELINE, List.of(),
            "Malformed ABI field declaration");
        rejected("missing owner bytecode", BASELINE + "public class fixture/Missing {\n}\n", List.of(LEGACY),
            "Expected one compiled class for fixture/Missing, found 0");
        rejected("missing regular baseline field", BASELINE.replace("public static final field NUMBER I", ""),
            List.of(LEGACY), "fixture/Api#NUMBER I");

        compile(SOURCE.replace("private static final int PRIVATE", "public static final int PRIVATE"));
        rejected("new emitted field", BASELINE, List.of(LEGACY), "fixture/Api#PRIVATE I");
        accepted("reviewed explicit API addition", BASELINE.replace("public static final field NUMBER I",
            "public static final field NUMBER I\n    public static final field PRIVATE I"), List.of(LEGACY), 12);

        compile(SOURCE.replace("public static final String LEGACY", "private static final String LEGACY"));
        rejected("retained field made private", BASELINE, List.of(LEGACY),
            "missing retained public constants: [" + LEGACY + "]");
        compile(SOURCE.replace("public static final String LEGACY", "protected static final String LEGACY"));
        rejected("retained field made protected", BASELINE, List.of(LEGACY),
            "missing retained public constants: [" + LEGACY + "]");
        compile(SOURCE.replace("public static final String LEGACY = \"retained\";", ""));
        rejected("retained field removed", BASELINE, List.of(LEGACY),
            "missing retained public constants: [" + LEGACY + "]");
        compile(SOURCE.replace("String LEGACY = \"retained\"", "int LEGACY = 10"));
        rejected("retained field type changed", BASELINE, List.of(LEGACY), "fixture/Api#LEGACY I");
        compile(SOURCE.replace("String LEGACY = \"retained\"", "String LEGACY = new String(\"retained\")"));
        rejected("retained field is no longer constant", BASELINE, List.of(LEGACY),
            "missing retained public constants: [" + LEGACY + "]");

        // Guard scope is names/types/access, not constant values or a second general-purpose ABI dump.
        compile(SOURCE.replace("NUMBER = 17", "NUMBER = 18"));
        accepted("value-only change", BASELINE, List.of(LEGACY), 11);
        compile(SOURCE.replace("private static final int PRIVATE = 4;",
            "private static final int PRIVATE = 4; private static final int NEW_PRIVATE = 9;"));
        accepted("explicitly private implementation addition", BASELINE, List.of(LEGACY), 11);

        Files.writeString(api, BASELINE);
        expectFailure("empty compiled inputs", () -> PublicConstantAbi.verify(api, List.of(), List.of(LEGACY)),
            "Expected one compiled class");
        Path duplicateRoot = Files.createDirectories(root.resolve("duplicate/fixture"));
        Files.copy(classes.resolve("fixture/Api.class"), duplicateRoot.resolve("Api.class"));
        expectFailure("ambiguous compiled owner", () -> PublicConstantAbi.verify(api,
            List.of(classes, duplicateRoot.getParent()), List.of(LEGACY)), "found 2");
        Files.copy(classes.resolve("fixture/Internal.class"), classes.resolve("fixture/Api.class"),
            StandardCopyOption.REPLACE_EXISTING);
        expectFailure("wrong class at producer path", () -> PublicConstantAbi.verify(api, List.of(classes),
            List.of(LEGACY)), "Unexpected compiled ABI class");
        Files.write(classes.resolve("fixture/Api.class"), new byte[] {0, 1, 2});
        expectFailure("truncated classfile", () -> PublicConstantAbi.verify(api, List.of(classes), List.of(LEGACY)),
            "javap failed");
    }

    @FunctionalInterface
    private interface CheckedAction {
        void run() throws IOException;
    }
}
