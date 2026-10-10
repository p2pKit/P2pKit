# Installed macOS native policy

This policy is **development ad-hoc admission**, not Developer ID authentication,
notarization, Gatekeeper approval, or release qualification. The existing private,
clean-source native producer and its owner-only verifier remain separate and strict.
There is no automatic fallback from either policy.

## Native authority and installation boundary

The packaged launcher explicitly selects
`-Ddev.p2pkit.lan.macos.installedPolicy=development-adhoc-v1`; it must not also set
`dev.p2pkit.lan.macos.nativeDir`. Native location is derived from the actual process
executable, not a user-supplied directory. The executable must be the application's
`Contents/MacOS` launcher. The LAN implementation JAR and the sole classpath native
manifest JAR must both reside directly in that same application's `Contents/app`.

The library is loaded only from
`Contents/app/resources/p2pkit-native/macos-arm64`. The existing eight-field native
manifest remains authoritative: exact source, tree, ABI, architecture, filename,
length, ARM64 Mach-O header and SHA-256. External and classpath manifests must match
byte-for-byte. The complete bundle resource seal and the inner dylib are verified
with fixed system `codesign` commands before loading and again afterwards. Only
explicit ad-hoc signatures with no Team ID are admitted by this development policy.
A non-ad-hoc signature is not silently accepted or replaced.

Files must be regular, single-linked and owned by root or the current effective
user. Files and all ancestors must not be group/world writable, contain symlink
ancestry, special permission bits, or an allow ACL. One exact administrative
installation boundary is supported: `/Applications`, owned by root, group `admin`
(GID 80), mode `0775`, without an allow ACL. This does **not** permit group-writable
application contents or any other writable ancestor. Root, the current account and
administrators able to replace applications are trusted by this development model;
ad-hoc signatures do not authenticate a publisher against them.

## Verification command scope

Runtime subprocesses are restricted to fixed `/usr/bin/id`, `/bin/ls` and
`/usr/bin/codesign` invocations, with a cleared environment. A sole reader polls
available bytes without waiting on an inherited pipe writer. The contract is the
exact tool's successful exit, bounded captured output, complete/unique required
metadata fields, and retirement of the owned process and streams (15-second command
limit, 5-second retirement limit). It does **not** prove termination of unowned
descendants or universal pipe EOF; no descendant is signalled. Missing or ambiguous
signature/ACL metadata fails closed. The Python staging helper uses nonblocking
pipes and also requires EOF within its 30-second command limit; a held writer fails
rather than blocking cleanup or being relabelled as complete output.

## Existing application packaging

`scripts/stage-rpc-macos-app.py` accepts a clean-source native producer and creates a
**new copy** of the existing Desktop app image. It does not create another app
identity, installer or release pipeline. It validates the real launcher classpath,
including renamed manifest JARs, and refuses ambiguous resources, external entries,
private native-directory options and alternate agent/class-loader authorities.

The producer signs the inner native bytes **before** generating the pinned manifest.
The finalizer never re-signs that pinned dylib. It adds those exact bytes to the new
app copy, verifies existing nested signatures without replacing vendor signatures,
signs only the containing development app last, then independently verifies the
result. Invalid or non-ad-hoc existing outer signatures are rejected. Existing inputs,
prior outputs and failed copies are preserved; reruns require a new output location.

The helper's `nativeSource`/`nativeTree` receipt covers the native producer only.
Application source/version binding must still pass Foundation's existing identity,
package, freeze and publication verification. Final DMG production must consume the
finalized app image, and publication must consume the existing frozen artifact set.
Developer ID signing would require an independently reviewed policy, authorized
credentials, inner-signature-before-manifest ordering and all normal release gates;
this development mode is not a substitute.

## Focused verification

- Portable policy tests cover installation ownership, executable layout, structured
  signature flags, complete ACL listings and subprocess failure/interruption cleanup.
- Existing private-artifact tests must continue to pass unchanged.
- `scripts/tests/stage-rpc-macos-app-test.py` checks bounded inputs and launcher parsing.
- `scripts/tests/build-macos-installed-fixtures.py --output <new-owned-directory>`
  creates synthetic signed bundles and tampered copies for the explicit
  `MacLanInstalledBundleNativeTest` suite. This never launches an application or loads
  native code; it is signed-file admission evidence, not end-to-end RPC qualification.
- A current-source packaged-launcher/native smoke test remains necessary. Installed
  application behavior, DMG extraction, permissions, signatures and exact bytes must
  be rechecked on the final candidate before any release claim.

The maintained launcher accepts exactly `--rpc-native-readback` for this last
diagnostic. It requires a clean Mac ARM64 installed-development build, invokes
the real admission loader and validates its compiled source/ABI, then retires
the inert binding. Fixed internal-ABI reflection has no caller-selected class,
method, path, access override or fallback. It does not activate a transport,
open a socket, start Bonjour, create an identity/profile, or show the UI.
Success is native admission only, not RPC connectivity or storage qualification.
Unknown arguments and failed admission/cleanup return failure without launching UI.
