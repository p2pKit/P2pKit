package dev.p2pkit.rpc.windows.loader;

import java.io.InputStream;
import java.lang.foreign.Arena;
import java.lang.foreign.MemorySegment;
import java.lang.reflect.Field;
import java.nio.file.Files;
import java.nio.file.LinkOption;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.util.concurrent.atomic.AtomicReference;

/** Actual system-call investigation on Windows, never installed authority or protected-profile admission. */
public final class SystemBootstrapCandidateTests {
    private SystemBootstrapCandidateTests() {}

    private static void check(boolean value) {
        if (!value) throw new AssertionError("System bootstrap candidate control failed");
    }

    private static void refused() {
        try {
            WindowsSystemBootstrapCandidate.inspect();
            throw new AssertionError("Unadmitted system bootstrap candidate was accepted");
        } catch (IllegalStateException expected) {
            // These runtime/thread/duplicate controls must refuse before another lookup or OS operation.
        }
    }

    public static void main(String[] args) throws Exception {
        check(args.length == 1);
        String scope;
        String policy = "";
        if (args[0].equals("runtime") || args[0].equals("unsupported")) {
            refused();
            scope = "RUNTIME_REFUSAL_NO_SYSTEM_BOOTSTRAP";
        } else if (args[0].equals("virtual")) {
            AtomicReference<Throwable> unexpected = new AtomicReference<>();
            Thread worker = Thread.startVirtualThread(() -> {
                try { refused(); } catch (Throwable failure) { unexpected.set(failure); }
            });
            worker.join();
            check(unexpected.get() == null);
            scope = "THREAD_REFUSAL_NO_SYSTEM_BOOTSTRAP";
        } else if (args[0].equals("inspect")) {
            WindowsSystemBootstrapCandidate original = WindowsSystemBootstrapCandidate.inspect();
            check(original.completed());
            check(original.processId() == ProcessHandle.current().pid());
            check(original.observedProviderCount() >= 1 && original.observedProviderCount() <= 2);
            refused();
            check(original.completed() && original.processId() == ProcessHandle.current().pid());
            try {
                WindowsLoader.openInstalledProvider();
                throw new AssertionError("System observations enabled productive loading");
            } catch (UnsupportedOperationException expected) {
                check(WindowsLoader.REFUSAL.equals(expected.getMessage()));
            }
            scope = "DEVELOPMENT_JVM_SYSTEM_CALLS_NOT_INSTALLED_AUTHORITY_OR_PROFILE";
        } else if (args[0].equals("jvm")) {
            WindowsSystemBootstrapCandidate original = WindowsSystemBootstrapCandidate.inspect();
            WindowsOriginalJvmCandidate runtime = original.inspectOriginalJvm();
            check(runtime.completed() && runtime.singleVirtualMachineObserved());
            try {
                original.inspectOriginalJvm();
                throw new AssertionError("Original runtime acquisition was repeated");
            } catch (IllegalStateException expected) {
                // The exact original attachment remains retained, without another native lookup/call.
            }
            AtomicReference<Throwable> unexpected = new AtomicReference<>();
            Thread worker = Thread.startVirtualThread(() -> {
                try {
                    try {
                        runtime.singleVirtualMachineObserved();
                        throw new AssertionError("Original runtime observation crossed its owner thread");
                    } catch (IllegalStateException expected) {
                        // Scoped ownership is not transferred to a different thread by exposing a result.
                    }
                    try {
                        original.inspectOriginalJvm();
                        throw new AssertionError("Original runtime acquisition crossed its owner thread");
                    } catch (IllegalStateException expected) {
                        // Refuse before another native operation.
                    }
                } catch (Throwable failure) { unexpected.set(failure); }
            });
            worker.join();
            check(unexpected.get() == null);
            check(runtime.completed() && runtime.singleVirtualMachineObserved() && original.completed());
            try {
                WindowsLoader.openInstalledProvider();
                throw new AssertionError("Original runtime observations enabled productive loading");
            } catch (UnsupportedOperationException expected) {
                check(WindowsLoader.REFUSAL.equals(expected.getMessage()));
            }
            scope = "DEVELOPMENT_JVM_ONE_VM_NOT_INSTALLED_AUTHORITY_REGISTRATION_OR_PROFILE";
        } else if (args[0].equals("file")) {
            WindowsSystemBootstrapCandidate original = WindowsSystemBootstrapCandidate.inspect();
            WindowsOriginalJvmCandidate runtime = original.inspectOriginalJvm();
            WindowsOriginalJvmFileCandidate file = runtime.inspectFile();
            check(file.completed() && file.leaseHeld());
            try {
                runtime.inspectFile();
                throw new AssertionError("Original runtime file acquisition was repeated");
            } catch (IllegalStateException expected) {
                // Permanent original attachment precludes another native open or observation.
            }
            AtomicReference<Throwable> unexpected = new AtomicReference<>();
            Thread worker = Thread.startVirtualThread(() -> {
                try {
                    try {
                        file.leaseHeld();
                        throw new AssertionError("Original file lease crossed its owner thread");
                    } catch (IllegalStateException expected) {
                        // No arbitrary thread receives the original retained handle.
                    }
                    try {
                        runtime.inspectFile();
                        throw new AssertionError("File acquisition crossed its owner thread");
                    } catch (IllegalStateException expected) {
                        // Refuse before another native call.
                    }
                } catch (Throwable failure) { unexpected.set(failure); }
            });
            worker.join();
            check(unexpected.get() == null);
            System.gc(); // Exercise retained ownership; GC is not a deterministic collection assertion.
            check(file.completed() && file.leaseHeld() && runtime.singleVirtualMachineObserved() && original.completed());
            try {
                WindowsLoader.openInstalledProvider();
                throw new AssertionError("File observation enabled productive loading");
            } catch (UnsupportedOperationException expected) {
                check(WindowsLoader.REFUSAL.equals(expected.getMessage()));
            }
            scope = "DEVELOPMENT_JVM_FILE_LEASE_NOT_INSTALLED_ACL_ANCESTOR_MAPPING_OR_PROFILE";
        } else if (args[0].equals("file-pipeline")) {
            policy = filePipeline();
            scope = "DEVELOPMENT_JVM_SHARED_FILE_PIPELINE_NOT_DLL_OR_INSTALLATION_AUTHORITY";
        } else if (args[0].equals("bytes")) {
            WindowsSystemBootstrapCandidate original = WindowsSystemBootstrapCandidate.inspect();
            WindowsOriginalJvmCandidate runtime = original.inspectOriginalJvm();
            WindowsOriginalJvmFileCandidate file = runtime.inspectFile();
            WindowsOriginalJvmBytesCandidate bytes = file.inspectBytes();
            check(bytes.completed() && bytes.byteCount() > 0 && bytes.byteCount() <= 512L * 1024 * 1024);
            // Independent read of the selected DEVELOPMENT JDK fixture. This pathname and its digest
            // are test observations only; neither supplies production expected-runtime provenance.
            MessageDigest reference = MessageDigest.getInstance("SHA-256", "SUN");
            long count = 0;
            byte[] chunk = new byte[65_536];
            try (InputStream input = Files.newInputStream(
                Path.of(System.getProperty("java.home"), "bin", "server", "jvm.dll"), LinkOption.NOFOLLOW_LINKS)) {
                int read;
                while ((read = input.read(chunk)) != -1) {
                    check(read > 0);
                    count += read;
                    check(count <= bytes.byteCount());
                    reference.update(chunk, 0, read);
                }
            } finally {
                java.util.Arrays.fill(chunk, (byte) 0);
            }
            check(count == bytes.byteCount() && MessageDigest.isEqual(reference.digest(), bytes.sha256()));
            byte[] copy = bytes.sha256();
            check(copy.length == 32);
            copy[0] ^= 1;
            check(!MessageDigest.isEqual(copy, bytes.sha256()));
            try {
                file.inspectBytes();
                throw new AssertionError("Original file bytes were read a second time");
            } catch (IllegalStateException expected) {
                // No reopen, seek or second use of the original file pointer.
            }
            AtomicReference<Throwable> unexpected = new AtomicReference<>();
            Thread worker = Thread.startVirtualThread(() -> {
                try {
                    try {
                        bytes.sha256();
                        throw new AssertionError("Original file digest crossed its owner thread");
                    } catch (IllegalStateException expected) {
                        // Private original file ownership is not transferred through a digest.
                    }
                    try {
                        file.inspectBytes();
                        throw new AssertionError("Original byte acquisition crossed its owner thread");
                    } catch (IllegalStateException expected) {
                        // Refuse before a native read.
                    }
                } catch (Throwable failure) { unexpected.set(failure); }
            });
            worker.join();
            check(unexpected.get() == null);
            System.gc();
            check(bytes.completed() && bytes.byteCount() == count && file.leaseHeld() && runtime.completed());
            try {
                WindowsLoader.openInstalledProvider();
                throw new AssertionError("Original file digest enabled productive loading");
            } catch (UnsupportedOperationException expected) {
                check(WindowsLoader.REFUSAL.equals(expected.getMessage()));
            }
            scope = "DEVELOPMENT_JVM_HANDLE_BYTES_NOT_INSTALLED_IDENTITY_MAPPING_OR_PROFILE";
        } else if (args[0].equals("security")) {
            WindowsSystemBootstrapCandidate original = WindowsSystemBootstrapCandidate.inspect();
            WindowsOriginalJvmCandidate runtime = original.inspectOriginalJvm();
            WindowsOriginalJvmFileCandidate file = runtime.inspectFile();
            WindowsOriginalJvmSecurityCandidate security = file.inspectSecurity();
            check(security.completed());
            boolean accepted = security.descriptorPolicyAccepted();
            try {
                file.inspectSecurity();
                throw new AssertionError("Original file security acquisition was repeated");
            } catch (IllegalStateException expected) {
                // A completed native query does not authorize another query or owner replacement.
            }
            AtomicReference<Throwable> unexpected = new AtomicReference<>();
            Thread worker = Thread.startVirtualThread(() -> {
                try {
                    try {
                        security.descriptorPolicyAccepted();
                        throw new AssertionError("Security observation crossed its original thread");
                    } catch (IllegalStateException expected) {
                        // Descriptor policy is not a transferable installation authority.
                    }
                    try {
                        file.inspectSecurity();
                        throw new AssertionError("Security query crossed its original thread");
                    } catch (IllegalStateException expected) {
                        // Refuse before a second native query.
                    }
                } catch (Throwable failure) { unexpected.set(failure); }
            });
            worker.join();
            check(unexpected.get() == null);
            System.gc();
            check(security.completed() && security.descriptorPolicyAccepted() == accepted);
            check(file.leaseHeld() && runtime.singleVirtualMachineObserved() && original.completed());
            try {
                WindowsLoader.openInstalledProvider();
                throw new AssertionError("Observed file descriptor enabled productive loading");
            } catch (UnsupportedOperationException expected) {
                check(WindowsLoader.REFUSAL.equals(expected.getMessage()));
            }
            scope = "DEVELOPMENT_JVM_HANDLE_SECURITY_NOT_INSTALLED_ANCESTOR_MAPPING_OR_PROFILE";
            // Actual development-file policy may accept OR refuse. Neither outcome admits installation.
            policy = " descriptorPolicy=" + (accepted ? "ACCEPTED" : "REFUSED");
        } else if (args[0].equals("ancestors")) {
            WindowsSystemBootstrapCandidate original = WindowsSystemBootstrapCandidate.inspect();
            WindowsOriginalJvmCandidate runtime = original.inspectOriginalJvm();
            WindowsOriginalJvmFileCandidate file = runtime.inspectFile();
            WindowsOriginalJvmSecurityCandidate security = file.inspectSecurity();
            WindowsOriginalJvmAncestorsCandidate ancestors = security.inspectAncestors();
            check(ancestors.completed());
            int count = ancestors.ancestorCount();
            check(count >= 1 && count <= 63); // Root and directories, not the final identity probe.
            boolean accepted = ancestors.descriptorPoliciesAccepted();
            try {
                security.inspectAncestors();
                throw new AssertionError("Original ancestry acquisition was repeated");
            } catch (IllegalStateException expected) {
                // Original handles and query result stay owned; this is not permission to reopen them.
            }
            AtomicReference<Throwable> unexpected = new AtomicReference<>();
            Thread worker = Thread.startVirtualThread(() -> {
                try {
                    try {
                        ancestors.descriptorPoliciesAccepted();
                        throw new AssertionError("Ancestor observations crossed their owner thread");
                    } catch (IllegalStateException expected) {
                        // No transfer of held directory ownership through a policy boolean.
                    }
                    try {
                        security.inspectAncestors();
                        throw new AssertionError("Ancestor acquisition crossed its owner thread");
                    } catch (IllegalStateException expected) {
                        // No native call or second path traversal.
                    }
                } catch (Throwable failure) { unexpected.set(failure); }
            });
            worker.join();
            check(unexpected.get() == null);
            System.gc();
            check(ancestors.completed() && ancestors.ancestorCount() == count);
            check(ancestors.descriptorPoliciesAccepted() == accepted);
            check(security.completed() && file.leaseHeld() && runtime.singleVirtualMachineObserved());
            try {
                WindowsLoader.openInstalledProvider();
                throw new AssertionError("Ancestor observations enabled productive loading");
            } catch (UnsupportedOperationException expected) {
                check(WindowsLoader.REFUSAL.equals(expected.getMessage()));
            }
            scope = "DEVELOPMENT_JVM_ANCESTOR_HANDLES_NOT_APPROVED_INSTALLATION_MAPPING_OR_PROFILE";
            policy = " descriptorPolicies=" + (accepted ? "ACCEPTED" : "REFUSED");
        } else {
            throw new IllegalArgumentException("Unknown system bootstrap control");
        }
        System.out.println("WINDOWS_SYSTEM_BOOTSTRAP_CANDIDATE_PASS case=" + args[0] + " scope=" + scope + policy);
    }

    private static String filePipeline() throws Exception {
        WindowsSystemBootstrapCandidate original = WindowsSystemBootstrapCandidate.inspect();
        WindowsOriginalJvmCandidate runtime = original.inspectOriginalJvm();
        WindowsOriginalJvmFileCandidate file = runtime.inspectFile();
        WindowsOriginalFileLease lease = (WindowsOriginalFileLease) originalField(file, "lease");
        MemorySegment handle = (MemorySegment) originalField(lease, "handle");
        Arena handleArena = (Arena) originalField(lease, "handleArena");
        long rawHandle = (long) originalField(lease, "rawHandle");
        check(file.completed() && file.leaseHeld() && lease.completed() && handleArena.scope().isAlive());
        check(rawHandle > 0 && handle.address() == rawHandle && handle.scope().equals(handleArena.scope()));
        check(originalField(original, "originalJvm") == runtime && originalField(runtime, "file") == file);
        check(originalField(lease, "originalOwner") == file);
        check(((WindowsOriginalFileLease.Failure) originalField(lease, "failure")).retainedCandidate == lease);
        char[] runtimePath = (char[]) originalField(runtime, "observedModulePath");
        char[] leasePath = (char[]) originalField(lease, "sourcePath");
        check(leasePath != runtimePath && java.util.Arrays.equals(leasePath, runtimePath));

        WindowsOriginalJvmSecurityCandidate security = file.inspectSecurity();
        WindowsOriginalFileSecurityQuery securityQuery =
            (WindowsOriginalFileSecurityQuery) originalField(security, "query");
        check(security.completed() && originalField(securityQuery, "fileHandle") == handle &&
            originalField(securityQuery, "fileArena") == handleArena &&
            originalField(securityQuery, "originalJvmOwner") == security &&
            originalField(securityQuery, "originalProfileDllOwner") == null);
        boolean filePolicy = security.descriptorPolicyAccepted();
        WindowsOriginalJvmAncestorsCandidate ancestors = security.inspectAncestors();
        check(ancestors.completed() && ancestors.ancestorCount() >= 1 && ancestors.ancestorCount() <= 63);
        WindowsOriginalFileAncestorsLease ancestorCore =
            (WindowsOriginalFileAncestorsLease) originalField(ancestors, "core");
        check(originalField(ancestorCore, "originalFileHandle") == handle &&
            originalField(ancestorCore, "originalFileArena") == handleArena);
        check(originalField(ancestorCore, "originalJvmOwner") == ancestors &&
            originalField(ancestorCore, "originalProfileDllOwner") == null);
        boolean ancestorPolicy = ancestors.descriptorPoliciesAccepted();
        WindowsOriginalJvmBytesCandidate bytes = file.inspectBytes();
        WindowsOriginalFileBytesLease byteCore = (WindowsOriginalFileBytesLease) originalField(bytes, "core");
        check(bytes.completed() && originalField(byteCore, "fileHandle") == handle &&
            originalField(byteCore, "fileArena") == handleArena);
        check(originalField(byteCore, "originalJvmOwner") == bytes &&
            originalField(byteCore, "originalProfileDllOwner") == null && originalField(byteCore, "originalSnapshot") == null);
        check(bytes.byteCount() > 0 && bytes.byteCount() <= 512L * 1024 * 1024);

        // Independent bounded read of the DEVELOPMENT fixture, not an expected installed/runtime pin.
        MessageDigest reference = MessageDigest.getInstance("SHA-256", "SUN");
        long count = 0;
        byte[] chunk = new byte[65_536];
        try (InputStream input = Files.newInputStream(
            Path.of(System.getProperty("java.home"), "bin", "server", "jvm.dll"), LinkOption.NOFOLLOW_LINKS)) {
            int read;
            while ((read = input.read(chunk)) != -1) {
                check(read > 0);
                count += read;
                check(count <= bytes.byteCount());
                reference.update(chunk, 0, read);
            }
        } finally {
            java.util.Arrays.fill(chunk, (byte) 0);
        }
        check(count == bytes.byteCount() && MessageDigest.isEqual(reference.digest(), bytes.sha256()));
        WindowsOriginalFileLease substitute = new WindowsOriginalFileLease(file);
        pipelineRefused(substitute::observe);
        check(!(boolean) originalField(substitute, "attempted") && originalField(substitute, "frameArena") == null);
        pipelineRefused(runtime::inspectFile);
        pipelineRefused(file::inspectSecurity);
        pipelineRefused(security::inspectAncestors);
        pipelineRefused(file::inspectBytes);
        pipelineRefused(lease::observe);

        AtomicReference<Throwable> unexpected = new AtomicReference<>();
        Thread worker = Thread.startVirtualThread(() -> {
            try {
                pipelineRefused(file::leaseHeld);
                pipelineRefused(lease::completed);
                pipelineRefused(security::descriptorPolicyAccepted);
                pipelineRefused(ancestors::descriptorPoliciesAccepted);
                pipelineRefused(bytes::sha256);
                pipelineRefused(file::inspectSecurity);
                pipelineRefused(file::inspectBytes);
            } catch (Throwable failure) { unexpected.set(failure); }
        });
        worker.join();
        check(unexpected.get() == null);
        System.gc(); // GC is not an assertion that any particular object was collected.
        check(originalField(file, "lease") == lease && originalField(lease, "handle") == handle &&
            (long) originalField(lease, "rawHandle") == rawHandle && handleArena.scope().isAlive());
        check(originalField(original, "originalJvm") == runtime && originalField(runtime, "file") == file &&
            originalField(lease, "originalOwner") == file);
        check(bytes.completed() && bytes.byteCount() == count && lease.completed() && file.leaseHeld());
        check(security.descriptorPolicyAccepted() == filePolicy &&
            ancestors.descriptorPoliciesAccepted() == ancestorPolicy && runtime.completed() && original.completed());
        try {
            WindowsLoader.openInstalledProvider();
            throw new AssertionError("Shared file pipeline enabled productive loading");
        } catch (UnsupportedOperationException expected) {
            check(WindowsLoader.REFUSAL.equals(expected.getMessage()));
        }
        return " descriptorPolicy=" + (filePolicy ? "ACCEPTED" : "REFUSED") +
            " descriptorPolicies=" + (ancestorPolicy ? "ACCEPTED" : "REFUSED");
    }

    private static Object originalField(Object owner, String name) throws ReflectiveOperationException {
        Field field = owner.getClass().getDeclaredField(name);
        field.setAccessible(true); // Test-patched module only; not a production pointer/owner observation API.
        return field.get(owner);
    }

    private interface PipelineAction { void run(); }
    private static void pipelineRefused(PipelineAction action) {
        try {
            action.run();
            throw new AssertionError("Shared file pipeline accepted a duplicate/substitute/thread access");
        } catch (IllegalStateException expected) {
            // All original ownership refusals precede further native effects.
        }
    }

}
