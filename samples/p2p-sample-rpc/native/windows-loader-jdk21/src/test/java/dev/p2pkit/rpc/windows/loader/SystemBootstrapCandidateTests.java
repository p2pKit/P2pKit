package dev.p2pkit.rpc.windows.loader;

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

    public static void main(String[] args) throws InterruptedException {
        check(args.length == 1);
        String scope;
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
        } else {
            throw new IllegalArgumentException("Unknown system bootstrap control");
        }
        System.out.println("WINDOWS_SYSTEM_BOOTSTRAP_CANDIDATE_PASS case=" + args[0] + " scope=" + scope);
    }
}
