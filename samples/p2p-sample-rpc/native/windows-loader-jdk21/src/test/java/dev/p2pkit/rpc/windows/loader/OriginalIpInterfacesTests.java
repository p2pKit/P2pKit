package dev.p2pkit.rpc.windows.loader;

import java.lang.foreign.Arena;
import java.lang.foreign.MemorySegment;
import java.lang.foreign.ValueLayout;
import java.lang.invoke.MethodHandles;
import java.lang.invoke.MethodType;
import java.util.concurrent.atomic.AtomicReference;

import static dev.p2pkit.rpc.windows.loader.OriginalFileBytesLeaseTests.field;
import static dev.p2pkit.rpc.windows.loader.OriginalFileBytesLeaseTests.value;

/** Original allocator-return/free lifecycle with inert Java handles; never an OS call or native authority. */
public final class OriginalIpInterfacesTests {
    private OriginalIpInterfacesTests() {}

    public static void main(String[] args) throws Throwable {
        check(args.length == 0);
        completedModuleHandoff();
        for (String mode : new String[] {"normal", "query-failure", "late-pointer", "query-unknown", "free-unknown",
            "bad-count", "malformed-row"}) {
            try (Fixture fixture = new Fixture(mode)) {
                if (mode.equals("normal")) {
                    check(fixture.owner.read().get(0).index() == 7);
                    check(value(fixture.owner, "retainedQuery") == null);
                    AtomicReference<Throwable> problem = new AtomicReference<>();
                    Thread thread = new Thread(() -> {
                        try { check(fixture.owner.read().get(0).index() == 7); }
                        catch (Throwable caught) { problem.set(caught); }
                    });
                    thread.start(); thread.join(2000);
                    check(!thread.isAlive() && problem.get() == null && fixture.queries == 2 && fixture.frees == 2);
                } else {
                    reject(fixture.owner::read);
                    boolean unknown = mode.endsWith("unknown") || mode.equals("late-pointer");
                    check((value(fixture.owner, "retainedQuery") != null) == unknown);
                    check(fixture.frees == (mode.equals("free-unknown") || mode.equals("bad-count") ||
                        mode.equals("malformed-row") ? 1 : 0));
                    if (unknown) {
                        reject(fixture.owner::read);
                        check(fixture.queries == 1); // Never retry an uncertain query/free.
                    }
                }
            }
        }
        System.out.println("WINDOWS_IP_OWNER_CONTROLS_PASS cases=8 scope=INERT_ALLOCATOR_LIFETIME_NOT_NATIVE_AUTHORITY");
    }

    /** Regression for the actual post-registration refusal: completed custody is readable but the
     * earlier acquisition guard must stay sealed. All objects/addresses here are fabricated owners. */
    private static void completedModuleHandoff() throws Throwable {
        var profileConstructor = Class.forName(InstalledProfilePreparationTests.class.getName() + "$Fixture")
            .getDeclaredConstructor();
        profileConstructor.setAccessible(true);
        var systemConstructor = Class.forName(OriginalApiSetTests.class.getName() + "$Fixture")
            .getDeclaredConstructor(String.class);
        systemConstructor.setAccessible(true);
        try (AutoCloseable profileFixture = (AutoCloseable) profileConstructor.newInstance();
             AutoCloseable systemFixture = (AutoCloseable) systemConstructor.newInstance("normal")) {
            var core = (OriginalSystemModulesTests.Fixture) value(systemFixture, "core");
            var parent = (WindowsInstalledProfileCandidate) value(profileFixture, "child");
            var bootstrap = (WindowsSystemBootstrapCandidate) value(profileFixture, "bootstrap");
            // Join the existing inert fixtures into one original-root graph. This is test-only
            // reflection, never a production authority/context constructor or a native call.
            field(core.collection, "bootstrap").set(core.collection, bootstrap);
            field(bootstrap, "systemModules").set(bootstrap, core.collection);
            field(bootstrap, "systemModulesAttempted").setBoolean(bootstrap, true);
            field(parent, "systems").set(parent, core.collection);
            var observer = new WindowsOriginalIpInterfaces(parent);
            field(parent, "ipInterfaces").set(parent, observer);
            field(observer, "attempted").setBoolean(observer, true);
            field(observer, "systems").set(observer, core.collection);
            field(observer, "ip").set(observer, core.modules[8]);
            reject(core.collection::requireOriginalNativeInputs); // Never reopen acquisition.
            check(core.modules[8].originalIpModule(observer) == value(core.modules[8], "module"));
            reject(() -> core.modules[8].originalIpModule(null));
            reject(() -> core.modules[0].originalIpModule(observer));
            reject(() -> core.modules[8].originalIpModule(new WindowsOriginalIpInterfaces(parent)));
            field(core.collection, "bootstrap").set(core.collection, core.bootstrap);
            reject(() -> core.modules[8].originalIpModule(observer));
            field(core.collection, "bootstrap").set(core.collection, bootstrap);
            Object query = value(core.modules[8], "security");
            field(query, "policyAccepted").setBoolean(query, false);
            reject(() -> core.modules[8].originalIpModule(observer));
            field(query, "policyAccepted").setBoolean(query, true);
            field(core.collection, "completed").setBoolean(core.collection, false);
            reject(() -> core.modules[8].originalIpModule(observer));
            field(core.collection, "completed").setBoolean(core.collection, true);
            AtomicReference<Throwable> problem = new AtomicReference<>();
            Thread thread = new Thread(() -> {
                try { reject(() -> core.modules[8].originalIpModule(observer)); }
                catch (Throwable caught) { problem.set(caught); }
            });
            thread.start(); thread.join(2000);
            check(!thread.isAlive() && problem.get() == null && value(observer, "permanentEntries") == null);
            check(core.modules[8].originalIpModule(observer) == value(core.modules[8], "module"));
            reject(core.collection::requireOriginalNativeInputs);
        }
    }

    private static final class Fixture implements AutoCloseable {
        final WindowsOriginalIpInterfaces owner = new WindowsOriginalIpInterfaces(null);
        final Arena data = Arena.ofShared();
        final MemorySegment table = data.allocate(176, 8);
        final String mode;
        int queries, frees;
        Fixture(String mode) throws ReflectiveOperationException {
            this.mode = mode;
            table.fill((byte) 0);
            table.set(ValueLayout.JAVA_INT, 0, mode.equals("bad-count") ? 4097 : 1);
            table.set(ValueLayout.JAVA_SHORT, 8, (short) (mode.equals("malformed-row") ? 0 : 2));
            table.set(ValueLayout.JAVA_LONG, 16, 100);
            table.set(ValueLayout.JAVA_INT, 24, 7);
            field(owner, "completed").setBoolean(owner, true);
            field(owner, "query").set(owner, MethodHandles.lookup().findVirtual(Fixture.class, "query",
                MethodType.methodType(int.class, short.class, MemorySegment.class)).bindTo(this));
            field(owner, "free").set(owner, MethodHandles.lookup().findVirtual(Fixture.class, "free",
                MethodType.methodType(void.class, MemorySegment.class)).bindTo(this));
        }
        private int query(short family, MemorySegment output) {
            queries++; check(family == 0 && output.byteSize() == 8);
            if (mode.equals("query-unknown")) throw new LinkageError("inert unknown return");
            if (mode.equals("query-failure")) return 5;
            output.set(ValueLayout.ADDRESS, 0, table);
            return mode.equals("late-pointer") ? 5 : 0;
        }
        private void free(MemorySegment original) {
            frees++; check(original.address() == table.address());
            if (mode.equals("free-unknown")) throw new LinkageError("inert unknown free return");
        }
        public void close() throws ReflectiveOperationException {
            // These are explicitly fabricated test-owned arenas, not a production repair/retirement path.
            Object retained = value(owner, "retainedQuery");
            if (retained != null) ((Arena) value(retained, "frame")).close();
            data.close();
        }
    }
    private static void check(boolean value) { if (!value) throw new AssertionError(); }
    private static void reject(Runnable action) {
        try { action.run(); } catch (IllegalStateException expected) { return; }
        throw new AssertionError("Expected retained refusal");
    }
}
