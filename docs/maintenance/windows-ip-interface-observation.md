# Windows IP-interface observation

This change supplies Windows IP-layer observations to the existing strict
single-interface discovery and TCP policy. It is not a multi-interface transport,
release approval, or Windows Host/Client qualification.

The installed JDK21 can report NDIS filter and WAN link rows as up even when they
have no IP binding. The admitted loader now observes the already-loaded
`iphlpapi.dll` through its original system-module file/ancestor custody and copied
export checks. Actual `GetProcAddress` returns must match the physical export
provider; retained module PINs and shared callable views last for the process.
There is no arbitrary DLL path, library lookup fallback, provider-enable switch,
JNI ABI/capability promotion, or runtime supplier change.

Each observation brackets a complete Java interface/address/flag scan with two
fresh `GetIpInterfaceTable(AF_UNSPEC)` results. Both IPv4 and IPv6 are included.
All native IP indices must appear in Java, each omitted link must have neither an
IP binding nor any address, and LUID/index/family/connection/routing metadata must
remain equal across the scan. Unreadable flags, weak-host/forwarding configuration,
duplicate identities, unknown layouts and incomplete snapshots refuse. Multiple
active IP paths still fail the original policy. Fresh socket checks retain local
address, approved subnet and same-host rejection; discovery remains bound to the
selected interface. No result is cached between path checks.

The read-only pre-unlock UI can still show the conservative Java observation.
After actual installed registration, UI Start and the transport use the same
native observer. A retained admission/cleanup failure never falls back to a
permissive scan. Every OS-allocated table is owned before parsing and freed once;
uncertain query/free completion seals the observer with the original frame retained.

Local controls include `WindowsIpInterfaceTableTests`,
`JvmWindowsIpInterfacesTest`, and the Windows SDK compile-time assertions in
`ip_interface_layout_test.c`. Managed controls are not native execution evidence.
Exact installed admission, actual discovery/socket behavior, topology-change
controls and peer operations still require separately bound Windows results.
The campaign remains **NOT_READY** until its outstanding qualification completes.
