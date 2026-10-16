import java.lang.reflect.Method;
import java.util.List;

/** Reads the real packaged loader, ABI and compiled source. Does not open sockets or start Bonjour. */
public final class RpcPreviewNativeReadback {
    public static void main(String[] args) throws Exception {
        if (args.length != 1 || !args[0].matches("[a-f0-9]{40}")) {
            throw new IllegalArgumentException("Exact source SHA required");
        }
        Class<?> policyType = Class.forName("dev.p2pkit.transport.lan.OrganizationLan");
        Object policy = policyType.getConstructor(List.class, String.class, String.class, int.class)
            .newInstance(List.of("10.0.0.0/8"), "en0", "10.1.2.3", 0);
        Class<?> loader = Class.forName("dev.p2pkit.transport.lan.MacLanNativeLoader");
        Object binding = loader.getMethod("configuredBinding", policyType)
            .invoke(loader.getField("INSTANCE").get(null), policy);
        if (binding == null) throw new AssertionError("Packaged native provider not admitted");
        Class<?> nativeType = Class.forName("dev.p2pkit.transport.lan.MacLanNative");
        Method source = nativeType.getMethod("source");
        String compiled = (String) source.invoke(nativeType.getField("INSTANCE").get(null));
        if (!compiled.startsWith(args[0] + ":")) throw new AssertionError("Wrong packaged native source");
        System.out.println("PACKAGED_NATIVE_SOURCE_AND_ABI_PASS_NO_NETWORK " + args[0]);
    }
}
