package dev.p2pkit.transport.lan.internal.jmdns.impl;

import dev.p2pkit.transport.lan.internal.jmdns.ServiceInfo;
import dev.p2pkit.transport.lan.internal.jmdns.ServiceInfo.Fields;
import dev.p2pkit.transport.lan.internal.jmdns.impl.constants.DNSRecordClass;
import dev.p2pkit.transport.lan.internal.jmdns.impl.constants.DNSRecordType;
import org.junit.Test;

import java.util.EnumMap;
import java.util.Map;

import static org.junit.Assert.assertEquals;

public class ServiceTypeDecoderTest {
    @Test
    public void legacyAliasesRetainReverseMarkersInRealEntriesAndPointers() {
        String[] instances = {
            "office.in-addr.arpa", "office.ip6.arpa", "in-addr.arpa", "ip6.arpa",
            "office-xin-addr.arpa", "office-xip6.arpa", "Office.IN-ADDR.ArPa", "Étage.ip6.arpa"
        };
        for (String instance : instances) {
            assertServiceAlias(instance, "p2pkit", "", false);
            assertServiceAlias(instance, "p2pkit", "", true);
        }
    }

    @Test
    public void pointerRetainsItsOwnersSubtypeWhileDecodingTheAlias() {
        assertServiceAlias("office.ip6.arpa", "p2pkit", "printing", true);
    }

    @Test
    public void terminalReverseNamespacesRetainOriginalPrefixAndCase() {
        String ipv6 = "1.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0";
        String[][] cases = {
            {"1.0.0.127", "in-addr.arpa"}, {ipv6, "ip6.arpa"},
            {"1.0.0.127", "In-AdDr.ArPa"}, {"8.B.D.0.1.0.0.2", "IP6.ARPA"},
            {"", "in-addr.arpa"}, {"", "ip6.arpa"},
            {"one.in-addr.arpa", "ip6.arpa"}, {"one.ip6.arpa", "in-addr.arpa"},
            {"one.in-addr.arpa", "in-addr.arpa"}, {"İ", "in-addr.arpa"}
        };
        for (String[] item : cases) {
            String name = (item[0].isEmpty() ? "" : item[0] + ".") + item[1];
            assertEntryMap(name, item[0], "", "", item[1], "");
            assertEntryMap(name + ".", item[0], "", "", item[1], "");
        }
    }

    @Test
    public void nonterminalOrUnboundedMarkersKeepOrdinaryParsing() {
        assertEntryMap("notin-addr.arpa.", "notin-addr", "", "", "arpa", "");
        assertEntryMap("notip6.arpa.", "notip6", "", "", "arpa", "");
        for (String marker : new String[] {"in-addr.arpa", "ip6.arpa"}) {
            assertEntryMap("one.two." + marker + ".example.", "one", "", "", "two." + marker + ".example", "");
            assertEntryMap("one.two." + marker + "..", "one", "", "", "two." + marker + ".", "");
            // Absolute end, not '$': a final line terminator retains the existing unmatched-name fallback.
            assertEntryMap("one.two." + marker + ".\n", "", "one.two." + marker, "", "", "");
        }
    }

    @Test
    public void ordinaryServiceHostSubtypeAndMetaQueryParsingIsPreserved() {
        assertServiceAlias("ordinary-peer", "p2pkit", "", true);
        assertServiceAlias("ordinary-peer", "p2pkit2", "", true);
        assertEntryMap("_p2pkit._tcp.local.", "", "p2pkit", "tcp", "local", "");
        assertEntryMap("_p2pkit2._tcp.local.", "", "p2pkit2", "tcp", "local", "");
        assertEntryMap("Host.local.", "Host", "", "", "local", "");
        assertEntryMap("_printing._sub._p2pkit._tcp.local.", "", "p2pkit", "tcp", "local", "printing");
        assertEntryMap("_services._dns-sd._udp.local.", "_services", "dns-sd", "udp", "local", "");
    }

    private static void assertServiceAlias(String instance, String application, String subtype, boolean rootDot) {
        String expectedType = "_" + application + "._tcp.local.";
        String owner = subtype.isEmpty() ? expectedType : "_" + subtype + "._sub." + expectedType;
        String alias = instance + "." + expectedType;
        if (!rootDot) {
            alias = alias.substring(0, alias.length() - 1);
        }
        assertEntryMap(alias, instance, application, "tcp", "local", "");
        DNSRecord.Pointer pointer = new DNSRecord.Pointer(owner, DNSRecordClass.CLASS_IN, false, 120, alias);
        ServiceInfo info = pointer.getServiceInfo(false);
        assertEquals(alias, fields(instance, application, "tcp", "local", subtype), info.getQualifiedNameMap());
        // This exact canonical type is the key used by the existing event/listener dispatch, not a fake event.
        assertEquals(alias, expectedType, info.getType());
        assertEquals(alias, owner, info.getTypeWithSubtype());
        if (rootDot) {
            assertEquals(alias, instance, JmDNSImpl.toUnqualifiedName(info.getType(), alias));
        }
    }

    private static void assertEntryMap(
        String name, String instance, String application, String protocol, String domain, String subtype
    ) {
        DNSQuestion question = DNSQuestion.newQuestion(name, DNSRecordType.TYPE_PTR, DNSRecordClass.CLASS_IN, false);
        assertEquals(name, fields(instance, application, protocol, domain, subtype), question.getQualifiedNameMap());
    }

    private static Map<Fields, String> fields(
        String instance, String application, String protocol, String domain, String subtype
    ) {
        Map<Fields, String> expected = new EnumMap<>(Fields.class);
        expected.put(Fields.Instance, instance);
        expected.put(Fields.Application, application);
        expected.put(Fields.Protocol, protocol);
        expected.put(Fields.Domain, domain);
        expected.put(Fields.Subtype, subtype);
        return expected;
    }
}
