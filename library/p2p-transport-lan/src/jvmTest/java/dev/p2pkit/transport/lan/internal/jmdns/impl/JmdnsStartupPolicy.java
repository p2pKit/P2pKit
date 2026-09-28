package dev.p2pkit.transport.lan.internal.jmdns.impl;

import java.io.IOException;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.LinkOption;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.nio.file.attribute.BasicFileAttributes;
import java.nio.file.attribute.FileTime;
import java.security.MessageDigest;
import java.util.HexFormat;
import java.util.Map;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicBoolean;

/**
 * One test-only, post-failure DNS-SD observation in the original fixture JVM.
 * The manual driver owns compilation/admission; these properties and files are
 * only its checked handoff, never another execution authority. No library is
 * loaded by class initialization, normal tests, or a successful fixture.
 */
final class JmdnsStartupPolicy {
    private static final String PROPERTY_PREFIX = "p2pkit.audit.jmdnsPolicy";
    private static final Path LIBRARY_SUFFIX = Path.of(
            "library/p2p-transport-lan/build/reports/jmdns-policy-native/libp2pkit-jmdns-policy.dylib");
    private static final String RECORD_NAME = "compile-record.json";
    private static final long LIBRARY_LIMIT = 1_048_576;
    private static final long RECORD_LIMIT = 262_144;
    private static final long UINT32_MAX = 4_294_967_295L;
    private static final long UNOBSERVED = Long.MIN_VALUE;
    private static final long NORMAL_BUDGET_NS = 1_000_000_000L;
    private static final long OUTER_WATCHDOG_NS = 45_000_000_000L;
    private static final int POLICY_DENIED = -65570;
    private static final int CALLBACK_LIMIT = 32;
    private static final int EINTR_RETRY_LIMIT = 4;
    private static final int POLLIN = 0x0001;
    private static final int POLL_BAD = 0x0008 | 0x0010 | 0x0020;
    private static final int EINTR = 4;
    private static final AtomicBoolean ATTEMPTED = new AtomicBoolean();

    // Versioned primitive schema, also fixed in JmdnsStartupPolicy.c.
    private static final int SCHEMA = 0, PID = 1, REAL_UID = 2, EFFECTIVE_UID = 3, INTERFACE_INDEX = 4;
    private static final int OUTCOME = 5, ELAPSED_NS = 6, CLOCK_ERRNO = 7, BROWSE_CODE = 8;
    private static final int REF_CREATED = 9, SOCKET_FD = 10, POLL_CALLS = 11, POLL_RETURN = 12;
    private static final int POLL_ERRNO = 13, POLL_REVENTS = 14, EINTR_RETRIES = 15, PROCESS_CODE = 16;
    private static final int CALLBACK_COUNT = 17, CALLBACK_OVERFLOW = 18, FIRST_CALLBACK_ERROR = 19;
    private static final int CALLBACK_POLICY_COUNT = 20, CALLBACK_CONTEXT_MISMATCH = 21;
    private static final int DEALLOCATE_ATTEMPTED = 22, DEALLOCATE_RETURNED = 23, POLICY_PHASE_MASK = 24;
    private static final int BUDGET_NS = 25, RESULT_FIELDS = 26;
    private static final int ADMISSION_REFUSED = 1, CLOCK_FAILED = 2, BROWSE_ERROR = 3;
    private static final int REFERENCE_UNAVAILABLE = 4, SOCKET_UNAVAILABLE = 5, POLL_TIMED_OUT = 6;
    private static final int POLL_FAILED = 7, EINTR_EXHAUSTED = 8, BUDGET_ELAPSED = 9;
    private static final int PROCESS_RETURNED = 10, REENTRANT_REFUSED = 11;

    private JmdnsStartupPolicy() {
    }

    @FunctionalInterface
    interface MatchedInterface {
        int currentIndex() throws IOException;
    }

    private enum Reason {
        CONTEXT, HANDOFF, JAVA_HOME, PATH, FILE_TYPE, FILE_IDENTITY, FILE_BYTES,
        INTERFACE, ALREADY_ATTEMPTED, CLOCKS, NATIVE_IDENTITY, NATIVE_SCHEMA, NATIVE_FLOW
    }

    private static final class Refusal extends RuntimeException {
        private static final long serialVersionUID = 1L;
        final Reason reason;

        Refusal(Reason reason) {
            super(reason.name());
            this.reason = reason;
        }
    }

    private record FileIdentity(long device, long inode, long mode, long uid, long links,
            long size, long mtimeNanos, long ctimeNanos) {
        static FileIdentity parse(String text) {
            require(text != null && text.length() <= 159, Reason.HANDOFF);
            String[] parts = text.split(":", -1);
            require(parts.length == 8, Reason.HANDOFF);
            long[] fields = new long[8];
            for (int index = 0; index < fields.length; index++) {
                require(parts[index].matches("0|[1-9][0-9]{0,18}"), Reason.HANDOFF);
                try {
                    fields[index] = Long.parseLong(parts[index]);
                } catch (NumberFormatException failure) {
                    throw new Refusal(Reason.HANDOFF);
                }
            }
            return new FileIdentity(fields[0], fields[1], fields[2], fields[3],
                    fields[4], fields[5], fields[6], fields[7]);
        }

        static FileIdentity read(Path path) throws IOException {
            Map<String, Object> attributes = Files.readAttributes(path,
                    "unix:dev,ino,mode,uid,nlink,size,lastModifiedTime,ctime", LinkOption.NOFOLLOW_LINKS);
            Object uid = attributes.get("uid");
            long owner = uid instanceof Integer value ? Integer.toUnsignedLong(value) : number(uid);
            return new FileIdentity(number(attributes.get("dev")), number(attributes.get("ino")),
                    number(attributes.get("mode")), owner, number(attributes.get("nlink")),
                    number(attributes.get("size")), fileTime(attributes.get("lastModifiedTime")),
                    fileTime(attributes.get("ctime")));
        }

        void regular(long owner, long maximum) {
            require(device >= 0 && inode > 0 && mode >= 0 && mode <= 0xffff
                    && (mode & 0170000) == 0100000 && (mode & 0022) == 0
                    && uid == owner && uid >= 0 && uid <= UINT32_MAX && links == 1
                    && size > 0 && size <= maximum && mtimeNanos > 0 && ctimeNanos > 0,
                    Reason.FILE_TYPE);
        }
    }

    private record Handoff(Path library, Path record, Path javaHome, String libraryHash,
            String recordHash, FileIdentity originalLibrary) {
    }

    static void report(String mode, int interfaceIndex, MatchedInterface currentInterface) {
        String phase = "ADMISSION";
        try {
            if (!"true".equals(System.getProperty("p2pkit.audit.jmdnsStartupPrimitives"))) {
                return;
            }
            require("control".equals(mode) && "Mac OS X".equals(System.getProperty("os.name"))
                    && ("aarch64".equals(System.getProperty("os.arch"))
                        || "arm64".equals(System.getProperty("os.arch")))
                    && Runtime.version().feature() == 17 && !Thread.currentThread().isInterrupted()
                    && System.getProperty("p2pkit.audit.pythonExecutable") != null
                    && interfaceIndex > 0 && currentInterface != null, Reason.CONTEXT);
            require(currentInterface.currentIndex() == interfaceIndex, Reason.INTERFACE);
            Handoff handoff = handoff();
            FileIdentity recordIdentity = verifyFile(handoff.record, handoff.recordHash, null,
                    handoff.originalLibrary.uid, RECORD_LIMIT);
            verifyFile(handoff.library, handoff.libraryHash, handoff.originalLibrary,
                    handoff.originalLibrary.uid, LIBRARY_LIMIT);
            long pid = ProcessHandle.current().pid();
            require(pid > 0 && pid <= Integer.MAX_VALUE, Reason.NATIVE_IDENTITY);
            require(!Thread.currentThread().isInterrupted()
                    && currentInterface.currentIndex() == interfaceIndex, Reason.INTERFACE);
            require(ATTEMPTED.compareAndSet(false, true), Reason.ALREADY_ATTEMPTED);

            phase = "LOAD_ATTEMPT";
            long loadMonotonicBefore = System.nanoTime();
            long loadUtcBefore = System.currentTimeMillis();
            emit(phase, "mode=control pid=" + pid + " librarySha256=" + handoff.libraryHash
                    + " recordSha256=" + handoff.recordHash + " observation=POST_FAILURE"
                    + " utcBeforeMillis=" + loadUtcBefore + " monotonicBeforeNanos=" + loadMonotonicBefore);
            System.load(handoff.library.toString());
            long loadUtcAfter = System.currentTimeMillis();
            long loadMonotonicAfter = System.nanoTime();
            phase = "LOAD_RETURNED";
            emit(phase, "result=UNVALIDATED utcAfterMillis=" + loadUtcAfter
                    + " monotonicAfterNanos=" + loadMonotonicAfter);
            enclosedElapsed(loadMonotonicBefore, loadMonotonicAfter, loadUtcBefore, loadUtcAfter);
            verifyHandoff(handoff, recordIdentity);

            phase = "NATIVE_CALL_ATTEMPT";
            long monotonicBefore = System.nanoTime();
            long utcBefore = System.currentTimeMillis();
            emit(phase, "pid=" + pid + " interfaceIndex=" + interfaceIndex
                    + " utcBeforeMillis=" + utcBefore + " monotonicBeforeNanos=" + monotonicBefore);
            require(!Thread.currentThread().isInterrupted()
                    && currentInterface.currentIndex() == interfaceIndex, Reason.INTERFACE);
            long[] result = browse0(interfaceIndex, pid, handoff.originalLibrary.uid);
            long utcAfter = System.currentTimeMillis();
            long monotonicAfter = System.nanoTime();
            phase = "NATIVE_RETURNED";
            emit(phase, "result=UNVALIDATED utcAfterMillis=" + utcAfter
                    + " monotonicAfterNanos=" + monotonicAfter + " " + rawResult(result));
            long elapsed = enclosedElapsed(monotonicBefore, monotonicAfter, utcBefore, utcAfter);
            validateResult(result, interfaceIndex, pid, handoff.originalLibrary.uid, elapsed);
            verifyHandoff(handoff, recordIdentity);

            // Metadata saturation is not a bound on callbacks inside the system
            // call. Uncertain context/clock/overflow never becomes policy credit.
            boolean denied = result[POLICY_PHASE_MASK] != 0 && result[CLOCK_ERRNO] == 0
                    && result[CALLBACK_CONTEXT_MISMATCH] == 0 && result[CALLBACK_OVERFLOW] == 0;
            phase = "OBSERVATION";
            emit(phase, "result=" + (denied ? "POLICY_DENIED_POST_FAILURE_OPERATION" : "UNKNOWN")
                    + " policyPhaseMask=" + result[POLICY_PHASE_MASK] + " pid=" + result[PID]
                    + " realUid=" + result[REAL_UID] + " effectiveUid=" + result[EFFECTIVE_UID]
                    + " interfaceIndex=" + result[INTERFACE_INDEX] + " outcome=" + result[OUTCOME]
                    + " elapsedNanos=" + result[ELAPSED_NS] + " clockErrno=" + result[CLOCK_ERRNO]
                    + " browseCode=" + result[BROWSE_CODE] + " processCode=" + result[PROCESS_CODE]
                    + " callbackCount=" + result[CALLBACK_COUNT]
                    + " callbackOverflow=" + result[CALLBACK_OVERFLOW]
                    + " firstCallbackError=" + result[FIRST_CALLBACK_ERROR]
                    + " callbackPolicyCount=" + result[CALLBACK_POLICY_COUNT]
                    + " callbackContextMismatch=" + result[CALLBACK_CONTEXT_MISMATCH]
                    + " referenceInitialized=" + result[REF_CREATED]
                    + " deallocateAttempted=" + result[DEALLOCATE_ATTEMPTED]
                    + " deallocateReturned=" + result[DEALLOCATE_RETURNED]
                    + " librarySha256=" + handoff.libraryHash + " recordSha256=" + handoff.recordHash
                    + " priorSendCause=UNKNOWN lifecycleAcceptance=NOT_PERFORMED");
        } catch (Refusal refusal) {
            emit(phase, "result=UNKNOWN reason=" + refusal.reason.name());
        } catch (Throwable failure) {
            // Only fixed text: no exception messages, paths, names or native text.
            // The caller still performs its original rescue and rethrows its
            // original failure. This is not success or a replacement exception.
            emit(phase, "result=UNKNOWN reason=DIAGNOSTIC_FAILURE");
        }
    }

    private static Handoff handoff() throws IOException {
        Path library = propertyPath(PROPERTY_PREFIX + "Library");
        require(library.endsWith(LIBRARY_SUFFIX), Reason.PATH);
        Path record = library.getParent().resolve(RECORD_NAME);
        Path javaHome = propertyPath(PROPERTY_PREFIX + "JavaHome");
        require(Files.isDirectory(javaHome, LinkOption.NOFOLLOW_LINKS)
                && javaHome.equals(Path.of(System.getProperty("java.home", "")).toRealPath()), Reason.JAVA_HOME);
        String libraryHash = hashProperty(PROPERTY_PREFIX + "LibrarySha256");
        String recordHash = hashProperty(PROPERTY_PREFIX + "RecordSha256");
        FileIdentity original = FileIdentity.parse(System.getProperty(PROPERTY_PREFIX + "LibraryIdentity"));
        original.regular(original.uid, LIBRARY_LIMIT);
        privateReportDirectories(library.getParent(), original.uid);
        return new Handoff(library, record, javaHome, libraryHash, recordHash, original);
    }

    private static void verifyHandoff(Handoff handoff, FileIdentity recordIdentity) throws Exception {
        require(Runtime.version().feature() == 17
                && handoff.javaHome.equals(Path.of(System.getProperty("java.home", "")).toRealPath()), Reason.JAVA_HOME);
        privateReportDirectories(handoff.library.getParent(), handoff.originalLibrary.uid);
        verifyFile(handoff.record, handoff.recordHash, recordIdentity, handoff.originalLibrary.uid, RECORD_LIMIT);
        verifyFile(handoff.library, handoff.libraryHash, handoff.originalLibrary,
                handoff.originalLibrary.uid, LIBRARY_LIMIT);
    }

    private static Path propertyPath(String property) throws IOException {
        String value = System.getProperty(property);
        require(value != null && !value.isEmpty()
                && value.getBytes(StandardCharsets.UTF_8).length <= 16_384
                && value.equals(new String(value.getBytes(StandardCharsets.UTF_8), StandardCharsets.UTF_8))
                && value.chars().noneMatch(character -> character < 32 || character == 127), Reason.HANDOFF);
        Path path = Path.of(value);
        require(path.isAbsolute() && path.toString().equals(value) && path.equals(path.normalize()), Reason.PATH);
        physical(path);
        return path;
    }

    private static String hashProperty(String property) {
        String value = System.getProperty(property);
        require(value != null && value.matches("[0-9a-f]{64}"), Reason.HANDOFF);
        return value;
    }

    private static void physical(Path path) throws IOException {
        require(path.isAbsolute() && path.equals(path.normalize()), Reason.PATH);
        for (Path item = path; item != null; item = item.getParent()) {
            BasicFileAttributes attributes = Files.readAttributes(item,
                    BasicFileAttributes.class, LinkOption.NOFOLLOW_LINKS);
            require(!attributes.isSymbolicLink() && (item.equals(path) || attributes.isDirectory()), Reason.PATH);
        }
        require(path.equals(path.toRealPath()), Reason.PATH);
    }

    private static void privateReportDirectories(Path path, long owner) throws IOException {
        // Only these three driver-created levels are private: native, reports,
        // build. Tracked source/system ancestors must be physical, not 0700.
        for (int level = 0; level < 3; level++) {
            physical(path);
            FileIdentity identity = FileIdentity.read(path);
            require(identity.uid == owner && (identity.mode & 0170000) == 0040000
                    && (identity.mode & 07777) == 0700, Reason.FILE_TYPE);
            path = path.getParent();
        }
    }

    private static FileIdentity verifyFile(Path path, String expectedHash, FileIdentity original,
            long owner, long maximum) throws Exception {
        physical(path);
        FileIdentity before = FileIdentity.read(path);
        before.regular(owner, maximum);
        require(original == null || before.equals(original), Reason.FILE_IDENTITY);
        MessageDigest digest = MessageDigest.getInstance("SHA-256");
        long size = 0;
        byte[] block = new byte[8192];
        try (InputStream stream = Files.newInputStream(path, StandardOpenOption.READ, LinkOption.NOFOLLOW_LINKS)) {
            for (;;) {
                int count = stream.read(block);
                if (count == -1) {
                    break;
                }
                require(count > 0 && count <= block.length, Reason.FILE_BYTES);
                size += count;
                require(size <= maximum, Reason.FILE_BYTES);
                digest.update(block, 0, count);
            }
        }
        FileIdentity after = FileIdentity.read(path);
        require(before.equals(after) && (original == null || after.equals(original)), Reason.FILE_IDENTITY);
        require(size == before.size && HexFormat.of().formatHex(digest.digest()).equals(expectedHash), Reason.FILE_BYTES);
        physical(path);
        return before;
    }

    private static long number(Object value) {
        require(value instanceof Integer || value instanceof Long, Reason.FILE_IDENTITY);
        return ((Number) value).longValue();
    }

    private static long fileTime(Object value) {
        require(value instanceof FileTime, Reason.FILE_IDENTITY);
        return ((FileTime) value).to(TimeUnit.NANOSECONDS);
    }

    private static boolean errorCode(long value) {
        return value == UNOBSERVED || value >= Integer.MIN_VALUE && value <= Integer.MAX_VALUE;
    }

    private static boolean readable(long[] value) {
        return value[POLL_RETURN] == 1 && (value[POLL_REVENTS] & POLLIN) != 0
                && (value[POLL_REVENTS] & POLL_BAD) == 0;
    }

    private static long enclosedElapsed(long monotonicBefore, long monotonicAfter, long utcBefore, long utcAfter) {
        long elapsed = monotonicAfter - monotonicBefore;
        require(elapsed >= 0 && elapsed <= OUTER_WATCHDOG_NS && utcBefore > 0
                && utcAfter >= utcBefore && utcAfter - utcBefore <= 45_000, Reason.CLOCKS);
        return elapsed;
    }

    private static void validateResult(long[] value, int interfaceIndex, long pid, long uid, long javaElapsed) {
        require(value != null && value.length == RESULT_FIELDS && value[SCHEMA] == 1
                && value[BUDGET_NS] == NORMAL_BUDGET_NS && value[OUTCOME] >= ADMISSION_REFUSED
                && value[OUTCOME] <= REENTRANT_REFUSED, Reason.NATIVE_SCHEMA);
        require(value[PID] == pid && value[REAL_UID] == uid && value[EFFECTIVE_UID] == uid
                && value[INTERFACE_INDEX] == interfaceIndex, Reason.NATIVE_IDENTITY);
        for (int field : new int[] {REF_CREATED, CALLBACK_OVERFLOW, CALLBACK_CONTEXT_MISMATCH,
                DEALLOCATE_ATTEMPTED, DEALLOCATE_RETURNED}) {
            require(value[field] == 0 || value[field] == 1, Reason.NATIVE_SCHEMA);
        }
        require(value[CLOCK_ERRNO] >= 0 && value[CLOCK_ERRNO] <= Integer.MAX_VALUE
                && (value[CLOCK_ERRNO] == 0 ? value[ELAPSED_NS] >= 0 && value[ELAPSED_NS] <= javaElapsed
                        : value[ELAPSED_NS] == UNOBSERVED), Reason.NATIVE_SCHEMA);
        require(errorCode(value[BROWSE_CODE]) && errorCode(value[PROCESS_CODE])
                && errorCode(value[FIRST_CALLBACK_ERROR]) && value[FIRST_CALLBACK_ERROR] != 0,
                Reason.NATIVE_SCHEMA);
        require(value[SOCKET_FD] == UNOBSERVED || value[SOCKET_FD] >= -1 && value[SOCKET_FD] <= Integer.MAX_VALUE,
                Reason.NATIVE_SCHEMA);
        require(value[DEALLOCATE_ATTEMPTED] == value[REF_CREATED]
                && value[DEALLOCATE_RETURNED] == value[REF_CREATED], Reason.NATIVE_FLOW);
        require(value[POLL_CALLS] >= 0 && value[POLL_CALLS] <= EINTR_RETRY_LIMIT + 1
                && value[EINTR_RETRIES] >= 0 && value[EINTR_RETRIES] <= EINTR_RETRY_LIMIT
                && value[POLL_ERRNO] >= 0 && value[POLL_ERRNO] <= Integer.MAX_VALUE
                && value[POLL_REVENTS] >= 0 && value[POLL_REVENTS] <= 0xffff, Reason.NATIVE_SCHEMA);
        if (value[POLL_CALLS] == 0) {
            require(value[POLL_RETURN] == UNOBSERVED && value[POLL_ERRNO] == 0
                    && value[POLL_REVENTS] == 0 && value[EINTR_RETRIES] == 0, Reason.NATIVE_FLOW);
        } else {
            require(value[POLL_RETURN] >= -1 && value[POLL_RETURN] <= 1
                    && (value[POLL_RETURN] == -1 ? value[POLL_ERRNO] > 0
                            : value[POLL_ERRNO] == 0)
                    && (value[POLL_RETURN] > 0 || value[POLL_REVENTS] == 0)
                    && value[EINTR_RETRIES] <= value[POLL_CALLS]
                    && value[POLL_CALLS] <= value[EINTR_RETRIES] + 1, Reason.NATIVE_FLOW);
            if (value[POLL_RETURN] != -1 || value[POLL_ERRNO] != EINTR) {
                require(value[POLL_CALLS] == value[EINTR_RETRIES] + 1, Reason.NATIVE_FLOW);
            } else if (value[OUTCOME] != EINTR_EXHAUSTED) {
                require(value[POLL_CALLS] == value[EINTR_RETRIES]
                        && (value[OUTCOME] == CLOCK_FAILED || value[OUTCOME] == BUDGET_ELAPSED),
                        Reason.NATIVE_FLOW);
            }
        }
        require(value[CALLBACK_COUNT] >= 0 && value[CALLBACK_COUNT] <= CALLBACK_LIMIT
                && value[CALLBACK_POLICY_COUNT] >= 0 && value[CALLBACK_POLICY_COUNT] <= value[CALLBACK_COUNT]
                && (value[CALLBACK_OVERFLOW] == 0 || value[CALLBACK_COUNT] == CALLBACK_LIMIT)
                && (value[CALLBACK_CONTEXT_MISMATCH] == 0 || value[CALLBACK_COUNT] > 0), Reason.NATIVE_SCHEMA);
        if (value[CALLBACK_COUNT] == 0) {
            require(value[FIRST_CALLBACK_ERROR] == UNOBSERVED && value[CALLBACK_POLICY_COUNT] == 0,
                    Reason.NATIVE_FLOW);
        }
        if (value[CALLBACK_POLICY_COUNT] > 0) {
            require(value[FIRST_CALLBACK_ERROR] != UNOBSERVED, Reason.NATIVE_FLOW);
        }
        if (value[FIRST_CALLBACK_ERROR] == POLICY_DENIED) {
            require(value[CALLBACK_POLICY_COUNT] > 0, Reason.NATIVE_FLOW);
        }
        if (value[CALLBACK_OVERFLOW] == 0) {
            long otherError = value[FIRST_CALLBACK_ERROR] != UNOBSERVED
                    && value[FIRST_CALLBACK_ERROR] != POLICY_DENIED ? 1 : 0;
            require(value[CALLBACK_COUNT] >= value[CALLBACK_POLICY_COUNT]
                    + otherError + value[CALLBACK_CONTEXT_MISMATCH], Reason.NATIVE_FLOW);
        }
        if (value[PROCESS_CODE] == UNOBSERVED) {
            require(value[CALLBACK_POLICY_COUNT] == 0 && value[FIRST_CALLBACK_ERROR] == UNOBSERVED
                    && (value[CALLBACK_COUNT] == 0 || value[CALLBACK_CONTEXT_MISMATCH] == 1), Reason.NATIVE_FLOW);
        } else {
            require(value[OUTCOME] == PROCESS_RETURNED && readable(value), Reason.NATIVE_FLOW);
        }
        if (value[BROWSE_CODE] != 0 || value[REF_CREATED] == 0) {
            require(value[REF_CREATED] == 0 && value[SOCKET_FD] == UNOBSERVED && value[POLL_CALLS] == 0
                    && value[PROCESS_CODE] == UNOBSERVED, Reason.NATIVE_FLOW);
        } else {
            require(value[SOCKET_FD] != UNOBSERVED, Reason.NATIVE_FLOW);
        }
        if (value[SOCKET_FD] == UNOBSERVED || value[SOCKET_FD] < 0) {
            require(value[POLL_CALLS] == 0 && value[PROCESS_CODE] == UNOBSERVED, Reason.NATIVE_FLOW);
        }
        long mask = (value[BROWSE_CODE] == POLICY_DENIED ? 1 : 0)
                | (value[PROCESS_CODE] == POLICY_DENIED ? 2 : 0)
                | (value[CALLBACK_POLICY_COUNT] > 0 ? 4 : 0);
        require(value[POLICY_PHASE_MASK] == mask, Reason.NATIVE_FLOW);
        switch ((int) value[OUTCOME]) {
            case ADMISSION_REFUSED, REENTRANT_REFUSED ->
                require(value[BROWSE_CODE] == UNOBSERVED && value[CALLBACK_COUNT] == 0, Reason.NATIVE_FLOW);
            case CLOCK_FAILED ->
                require(value[CLOCK_ERRNO] > 0 && value[PROCESS_CODE] == UNOBSERVED
                        && (value[BROWSE_CODE] == UNOBSERVED && value[CALLBACK_COUNT] == 0
                            || value[BROWSE_CODE] == 0 && value[REF_CREATED] == 1 && value[SOCKET_FD] >= 0
                                && (value[POLL_CALLS] == 0 || readable(value)
                                    || value[POLL_RETURN] == -1 && value[POLL_ERRNO] == EINTR)),
                        Reason.NATIVE_FLOW);
            case BROWSE_ERROR ->
                require(value[BROWSE_CODE] != UNOBSERVED && value[BROWSE_CODE] != 0, Reason.NATIVE_FLOW);
            case REFERENCE_UNAVAILABLE ->
                require(value[BROWSE_CODE] == 0 && value[REF_CREATED] == 0, Reason.NATIVE_FLOW);
            case SOCKET_UNAVAILABLE ->
                require(value[REF_CREATED] == 1 && value[SOCKET_FD] == -1, Reason.NATIVE_FLOW);
            case POLL_TIMED_OUT ->
                require(value[POLL_CALLS] > 0 && value[POLL_RETURN] == 0, Reason.NATIVE_FLOW);
            case POLL_FAILED ->
                require(value[POLL_CALLS] > 0 && (value[POLL_RETURN] == -1 && value[POLL_ERRNO] != EINTR
                        || value[POLL_RETURN] == 1 && !readable(value)), Reason.NATIVE_FLOW);
            case EINTR_EXHAUSTED ->
                require(value[POLL_CALLS] == EINTR_RETRY_LIMIT + 1 && value[EINTR_RETRIES] == EINTR_RETRY_LIMIT
                        && value[POLL_RETURN] == -1 && value[POLL_ERRNO] == EINTR, Reason.NATIVE_FLOW);
            case BUDGET_ELAPSED ->
                require(value[REF_CREATED] == 1 && value[SOCKET_FD] >= 0 && value[PROCESS_CODE] == UNOBSERVED
                        && (value[POLL_CALLS] == 0 || readable(value)
                            || value[POLL_RETURN] == -1 && value[POLL_ERRNO] == EINTR)
                        && (value[CLOCK_ERRNO] != 0 || value[ELAPSED_NS] >= NORMAL_BUDGET_NS), Reason.NATIVE_FLOW);
            case PROCESS_RETURNED ->
                require(value[PROCESS_CODE] != UNOBSERVED && value[REF_CREATED] == 1
                        && value[POLL_CALLS] > 0 && readable(value), Reason.NATIVE_FLOW);
            default -> throw new Refusal(Reason.NATIVE_SCHEMA);
        }
    }

    private static String rawResult(long[] result) {
        if (result == null || result.length != RESULT_FIELDS) {
            return "fields=" + (result == null ? -1 : result.length);
        }
        StringBuilder text = new StringBuilder("fields=26 raw=");
        for (int index = 0; index < RESULT_FIELDS; index++) {
            if (index != 0) {
                text.append(',');
            }
            text.append(result[index]);
        }
        return text.toString();
    }

    private static void emit(String phase, String fields) {
        System.out.println("startup policy phase=" + phase + " " + fields);
        System.out.flush();
    }

    private static void require(boolean condition, Reason reason) {
        if (!condition) {
            throw new Refusal(reason);
        }
    }

    private static native long[] browse0(int interfaceIndex, long expectedPid, long expectedUid);
}
