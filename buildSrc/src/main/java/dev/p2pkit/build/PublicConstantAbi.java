package dev.p2pkit.build;

import java.io.IOException;
import java.io.PrintWriter;
import java.io.StringWriter;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collection;
import java.util.List;
import java.util.Set;
import java.util.TreeSet;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import java.util.spi.ToolProvider;

/** Supplements Kotlin-aware baselines without freezing every Kotlin-internal JVM declaration. */
public final class PublicConstantAbi {
    private static final Pattern API_CLASS = Pattern.compile("^.*\\bclass ([^\\s]+).*\\{$");
    private static final Pattern JVM_CLASS = Pattern.compile("^.*\\b(?:class|interface) ([^\\s<{]+).*\\{$");
    private static final Pattern JVM_CONSTANT = Pattern.compile(
        "^(?:public|protected) static final [^ ]+ ([^ ]+) = .+;$"
    );
    private static final Pattern CONSTANT_DESCRIPTOR = Pattern.compile("[BCDFIJSZ]|Ljava/lang/String;");
    private static final Pattern RETAINED_FIELD = Pattern.compile(
        "[^\\s#]+#[^\\s#]+ ([BCDFIJSZ]|Ljava/lang/String;)"
    );

    private PublicConstantAbi() {}

    public record Result(int classes, int constants, int retained) {}

    public static Result verify(Path api, Collection<Path> classDirectories, Collection<String> retained)
        throws IOException {
        Set<String> owners = new TreeSet<>();
        Set<String> declared = new TreeSet<>();
        String owner = null;
        for (String line : Files.readAllLines(api)) {
            Matcher header = API_CLASS.matcher(line);
            if (header.matches()) {
                owner = header.group(1);
                if (!owners.add(owner)) throw new IOException("Duplicate ABI class: " + owner);
            } else if (line.equals("}")) {
                owner = null;
            } else {
                List<String> words = Arrays.asList(line.trim().split("\\s+"));
                int field = words.indexOf("field");
                if (field >= 0 && words.contains("static") && words.contains("final") &&
                    (words.contains("public") || words.contains("protected"))) {
                    if (owner == null || field + 3 != words.size()) {
                        throw new IOException("Malformed ABI field declaration");
                    }
                    String descriptor = words.get(field + 2);
                    if (CONSTANT_DESCRIPTOR.matcher(descriptor).matches()) {
                        declared.add(owner + "#" + words.get(field + 1) + " " + descriptor);
                    }
                }
            }
        }
        if (owners.isEmpty()) throw new IOException("ABI baseline contains no classes");

        Set<String> legacy = new TreeSet<>();
        for (String entry : retained) {
            if (!RETAINED_FIELD.matcher(entry).matches() ||
                !owners.contains(entry.substring(0, entry.indexOf('#')))) {
                throw new IOException("Invalid retained constant: " + entry);
            }
            if (!legacy.add(entry)) throw new IOException("Duplicate retained constant: " + entry);
            if (declared.contains(entry)) throw new IOException("Redundant retained constant: " + entry);
        }

        // Pass the actual producer files, never load application classes or fall back to the daemon classpath.
        List<Path> roots = classDirectories.stream().map(p -> p.toAbsolutePath().normalize()).distinct().toList();
        List<String> arguments = new ArrayList<>(List.of("-p", "-s", "-constants"));
        for (String name : owners) {
            List<Path> matches = new ArrayList<>();
            for (Path root : roots) {
                Path candidate = root.resolve(name + ".class").normalize();
                if (!candidate.startsWith(root)) throw new IOException("Invalid ABI class path: " + name);
                if (Files.isRegularFile(candidate)) matches.add(candidate);
            }
            if (matches.size() != 1) {
                throw new IOException("Expected one compiled class for " + name + ", found " + matches.size());
            }
            arguments.add(matches.get(0).toString());
        }

        ToolProvider javap = ToolProvider.findFirst("javap")
            .orElseThrow(() -> new IOException("A full JDK with javap is required for constant ABI verification"));
        StringWriter output = new StringWriter();
        StringWriter errors = new StringWriter();
        int exit = javap.run(new PrintWriter(output), new PrintWriter(errors), arguments.toArray(String[]::new));
        if (exit != 0 || !errors.toString().isBlank()) {
            throw new IOException("javap failed while inspecting compiled ABI: " + errors);
        }

        Set<String> seenOwners = new TreeSet<>();
        Set<String> actual = new TreeSet<>();
        Set<String> actualPublic = new TreeSet<>();
        owner = null;
        String pendingField = null;
        boolean pendingPublic = false;
        for (String raw : output.toString().split("\\R")) {
            String line = raw.trim();
            Matcher header = JVM_CLASS.matcher(line);
            if (header.matches()) {
                owner = header.group(1).replace('.', '/');
                if (!owners.contains(owner) || !seenOwners.add(owner) || pendingField != null) {
                    throw new IOException("Unexpected compiled ABI class: " + owner);
                }
            } else if (line.equals("}")) {
                if (pendingField != null) throw new IOException("Missing constant field descriptor");
                owner = null;
            } else if (pendingField != null) {
                if (!line.startsWith("descriptor: ")) throw new IOException("Missing constant field descriptor");
                String descriptor = line.substring("descriptor: ".length());
                if (!CONSTANT_DESCRIPTOR.matcher(descriptor).matches()) {
                    throw new IOException("Unexpected constant descriptor: " + descriptor);
                }
                String signature = owner + "#" + pendingField + " " + descriptor;
                actual.add(signature);
                if (pendingPublic) actualPublic.add(signature);
                pendingField = null;
            } else if ((line.startsWith("public ") || line.startsWith("protected ")) && line.contains(" = ")) {
                // -constants prints an initializer only for real ConstantValue attributes. Ignore the value:
                // signatures, not constant contents (e.g. generated BuildInfo), are this guard's contract.
                Matcher constant = JVM_CONSTANT.matcher(line);
                if (owner == null || !constant.matches()) {
                    throw new IOException("Unrecognized javap constant declaration");
                }
                pendingField = constant.group(1);
                pendingPublic = line.startsWith("public ");
            }
        }
        // javap can return zero after one bad file in a multi-file invocation.
        // A successful exit is not enough: every requested owner must be seen.
        if (!seenOwners.equals(owners) || pendingField != null) {
            throw new IOException("javap failed to inspect every expected ABI class");
        }

        Set<String> unrecorded = new TreeSet<>(actual);
        unrecorded.removeAll(declared);
        unrecorded.removeAll(legacy);
        Set<String> missing = new TreeSet<>(legacy);
        // The omitted legacy fields are public, not merely accessible to subclasses.
        missing.removeAll(actualPublic);
        if (!unrecorded.isEmpty() || !missing.isEmpty()) {
            throw new IOException("Unrecorded public constants: " + unrecorded +
                "; missing retained public constants: " + missing +
                ". Keep new implementation constants explicitly private; do not remove published RC symbols.");
        }
        return new Result(owners.size(), actual.size(), legacy.size());
    }
}
