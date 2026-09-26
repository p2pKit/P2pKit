package dev.p2pkit.build;

import java.io.IOException;
import java.io.StringReader;
import java.util.Properties;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/** One source version, with injective numeric encodings for application installers. */
public final class ApplicationReleaseVersion {
    private static final Pattern VERSION = Pattern.compile(
        "(0|[1-9][0-9]?)\\.(0|[1-9][0-9]?)\\.(0|[1-9][0-9]?)(?:-(SNAPSHOT|(?:alpha|beta|rc)[1-9][0-9]?))?"
    );

    private final String name;
    private final int androidCode;
    private final String nativeVersion;

    private ApplicationReleaseVersion(String name, int major, int minor, int patch, int rank) {
        this.name = name;
        this.androidCode = 1 + ((major * 100 + minor) * 100 + patch) * 400 + rank;
        // MSI: first/second components <= 255; third <= 65535. jpackage: major > 0.
        this.nativeVersion = (major + 1) + "." + minor + "." + (patch * 400 + rank);
    }

    public static ApplicationReleaseVersion parse(String name) {
        if (name == null) {
            throw new IllegalArgumentException("Missing canonical VERSION_NAME");
        }
        Matcher match = VERSION.matcher(name);
        if (!match.matches()) {
            throw new IllegalArgumentException("Unsupported canonical VERSION_NAME: " + name);
        }
        String suffix = match.group(4);
        int rank = 399;
        if ("SNAPSHOT".equals(suffix)) {
            rank = 0;
        } else if (suffix != null) {
            if (suffix.startsWith("alpha")) {
                rank = Integer.parseInt(suffix.substring(5));
            } else if (suffix.startsWith("beta")) {
                rank = 100 + Integer.parseInt(suffix.substring(4));
            } else {
                rank = 200 + Integer.parseInt(suffix.substring(2));
            }
        }
        return new ApplicationReleaseVersion(name, Integer.parseInt(match.group(1)),
            Integer.parseInt(match.group(2)), Integer.parseInt(match.group(3)), rank);
    }

    /** Reject duplicates (including escaped aliases) and any Gradle/environment override. */
    public static ApplicationReleaseVersion fromProperties(String content, Object effectiveVersion) {
        Properties properties = new Properties() {
            @Override
            public synchronized Object put(Object key, Object value) {
                if ("VERSION_NAME".equals(key) && containsKey(key)) {
                    throw new IllegalArgumentException("Duplicate VERSION_NAME");
                }
                return super.put(key, value);
            }
        };
        try {
            properties.load(new StringReader(content));
        } catch (IOException exception) {
            throw new IllegalArgumentException("Cannot read canonical VERSION_NAME", exception);
        }
        ApplicationReleaseVersion version = parse(properties.getProperty("VERSION_NAME"));
        long exactLines = content.lines().filter(line -> line.equals("VERSION_NAME=" + version.name)).count();
        if (exactLines != 1 || !version.name.equals(effectiveVersion)) {
            throw new IllegalArgumentException("VERSION_NAME must be one canonical repository declaration, not an override");
        }
        return version;
    }

    public String getName() { return name; }
    public int getAndroidCode() { return androidCode; }
    public String getNativeVersion() { return nativeVersion; }
    public String getDebianVersion() { return nativeVersion + "-1"; }

    public String identityJson(String sourceCommit) {
        if (!sourceCommit.matches("[0-9a-f]{40}|unknown")) {
            throw new IllegalArgumentException("Invalid sample source commit");
        }
        return "{\"schema\":1,\"sourceCommit\":\"" + sourceCommit + "\",\"canonicalVersion\":\"" + name
            + "\",\"androidVersionCode\":" + androidCode + ",\"nativeVersion\":\"" + nativeVersion
            + "\",\"debianVersion\":\"" + getDebianVersion() + "\"}\n";
    }
}
