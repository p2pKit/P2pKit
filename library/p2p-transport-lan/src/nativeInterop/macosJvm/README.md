# macOS JVM socket foundation (not integrated)

This private C ABI is groundwork for a strict, per-socket IPv4 adapter. **The JVM
transport and Desktop preview do not load it yet.** Their multi-interface rejection
remains in force. No Android/iOS implementation, public API, lockfile, route, permission,
or global signal disposition is changed.

## Contract

- `IP_BOUND_IF` is applied before bind/listen/connect and independently read back.
  Accepted children must already inherit the same scope; an unscoped child is rejected,
  not repaired after accepting traffic.
- The descriptor is nonblocking, close-on-exec and uses `SO_NOSIGPIPE` per socket.
  Bind/listen/connect cannot silently create a wildcard local endpoint.
- A bounded registry owns descriptors behind generation-tagged 64-bit handles.
  Closing rejects new operations, drains outstanding leases, then releases exactly once.
  Failed OS closes remain quarantined rather than retrying a potentially recycled fd.
- A failed open/accept may return a nonzero owned handle. The caller must close it and
  retain cleanup errors separately. Buffer ownership never crosses a call boundary;
  transfers are at most 64 KiB and each poll is at most 100 ms.
- This is **not** network admission. A future JVM adapter must retain existing
  interface identity, numeric CIDR/local/remote/self-address, cancellation, and path
  revalidation checks. IPv6 and non-Darwin implementations are not provided here.

## Focused validation

Run `scripts/tests/check-macos-lan-sockets.sh` from any directory on a Mac. It compiles
with warnings-as-errors, then repeats the native contract controls with AddressSanitizer
and UndefinedBehaviorSanitizer. Test-only seams inject configuration errors and hold a
known live poll lease; those seams are absent from production compilation.

The fixture uses only `lo0` and `127.0.0.1`. Controls cover actual inherited scope,
independent descriptor-option readback, byte-exact TCP exchange, EOF/SIGPIPE, close races,
setup rollback ownership, handle exhaustion/recycling and restored descriptor inventory.
Its ports, binaries and temporary directory are retired. A pass proves native mechanics,
**not** JVM integration, physical LAN/multicast, peer authentication or RPC qualification.

## Remaining integration

1. Add a bounds-checked JNI bridge and JVM ownership adapter, including failed-setup,
   cancelled-connect/accept and cleanup-retention regression coverage.
2. Package the correct architecture with a source/hash-bound manifest and secure loader;
   reject missing/tampered libraries, ABI mismatches, symlinks and global search paths.
3. Connect the restricted transport to proven socket scope. Preserve the portable
   fallback's topology guard and every existing policy assertion and deadline.
4. Rebuild the Desktop preview and run affected JVM/CLI checks, followed by the authorized
   real-LAN diagnostic. No loopback result may be promoted into that diagnostic's pass.
