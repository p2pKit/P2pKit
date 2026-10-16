import dev.p2pkit.build.ApplicationReleaseVersion;
import java.nio.file.Files;
import java.nio.file.Path;

/** JDK-only hosted test: no Gradle or application build. */
public final class ApplicationReleaseVersionTest {
    public static void main(String[] args) throws Exception {
        int vectors = 0;
        for (String row : Files.readAllLines(Path.of(args[0]))) {
            if (row.startsWith("#")) continue;
            String[] fields = row.split("\t");
            ApplicationReleaseVersion version = ApplicationReleaseVersion.parse(fields[0]);
            if (version.getAndroidCode() != Integer.parseInt(fields[1])
                    || !version.getNativeVersion().equals(fields[2])
                    || !version.getDebianVersion().equals(fields[3])) {
                throw new AssertionError("Version vector differs: " + fields[0]);
            }
            String content = "VERSION_NAME=" + fields[0] + "\n";
            ApplicationReleaseVersion.fromProperties(content, fields[0]);
            fails(() -> ApplicationReleaseVersion.fromProperties(content, "0.1.0"));
            fails(() -> ApplicationReleaseVersion.fromProperties(content + content, fields[0]));
            fails(() -> ApplicationReleaseVersion.fromProperties(content + "VERSION\\u005fNAME=" + fields[0], fields[0]));
            vectors++;
        }
        for (String bad : new String[] {"", "v0.8.0", "0.08.0", "100.0.0", "0.8.0-rc01", "0.8.0-rc100",
                "0.8.0-rc1+build", "0.8.0\n", "0.8.0-snapshot", "0.8.0-alpha.1"}) {
            fails(() -> ApplicationReleaseVersion.parse(bad));
        }
        for (char separator : new char[] {'\f', 0x0b, 0x85, 0x2028, 0x2029}) {
            fails(() -> ApplicationReleaseVersion.fromProperties("VERSION_NAME=0.8.0" + separator + "OTHER=1\n", "0.8.0"));
        }
        System.out.println("PASS: " + vectors + " Java application version vectors and negative controls");
    }

    private static void fails(Runnable call) {
        try {
            call.run();
        } catch (IllegalArgumentException expected) {
            return;
        }
        throw new AssertionError("Expected fail-closed version rejection");
    }
}
