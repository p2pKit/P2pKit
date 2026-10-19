/* Windows SDK ABI control only: no network/profile calls or native DLL loading. */
#define WIN32_LEAN_AND_MEAN
#include <winsock2.h>
#include <ws2ipdef.h>
#include <windows.h>
#include <iphlpapi.h>
#include <stddef.h>
#include <stdio.h>

_Static_assert(sizeof(void *) == 8, "AMD64 pointer layout required");
_Static_assert(sizeof(MIB_IPINTERFACE_ROW) == 168, "IP row size");
_Static_assert(offsetof(MIB_IPINTERFACE_TABLE, Table) == 8, "IP row table offset");
_Static_assert(offsetof(MIB_IPINTERFACE_ROW, Family) == 0, "family offset");
_Static_assert(offsetof(MIB_IPINTERFACE_ROW, InterfaceLuid) == 8, "LUID offset");
_Static_assert(offsetof(MIB_IPINTERFACE_ROW, InterfaceIndex) == 16, "index offset");
_Static_assert(offsetof(MIB_IPINTERFACE_ROW, ForwardingEnabled) == 41, "forwarding offset");
_Static_assert(offsetof(MIB_IPINTERFACE_ROW, WeakHostSend) == 42, "weak send offset");
_Static_assert(offsetof(MIB_IPINTERFACE_ROW, WeakHostReceive) == 43, "weak receive offset");
_Static_assert(offsetof(MIB_IPINTERFACE_ROW, Metric) == 148, "metric offset");
_Static_assert(offsetof(MIB_IPINTERFACE_ROW, NlMtu) == 152, "MTU offset");
_Static_assert(offsetof(MIB_IPINTERFACE_ROW, Connected) == 156, "connected offset");

int main(void) {
    puts("WINDOWS_IP_INTERFACE_LAYOUT_PASS scope=SDK_ABI_NOT_NETWORK_EXECUTION");
    return 0;
}
