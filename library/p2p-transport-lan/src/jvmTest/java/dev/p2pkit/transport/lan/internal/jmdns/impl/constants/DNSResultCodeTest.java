package dev.p2pkit.transport.lan.internal.jmdns.impl.constants;

import org.junit.Test;

import static org.junit.Assert.assertEquals;

public class DNSResultCodeTest {
    @Test
    public void extendedCodesDoNotOverlapHeaderBits() {
        assertEquals(DNSResultCode.Unknown, DNSResultCode.resultCodeForFlags(0, 0x01010000));
        assertEquals(DNSResultCode.Unknown, DNSResultCode.resultCodeForFlags(0x8002, 0x10018000));
    }

    @Test
    public void zeroExtendedCodeIgnoresOtherOptFields() {
        assertEquals(DNSResultCode.NoError, DNSResultCode.resultCodeForFlags(0, 0));
        assertEquals(DNSResultCode.NXRRSet, DNSResultCode.resultCodeForFlags(0x8008, 0x00018001));
    }
}
