# Official local ARM27 qualification continuation

## Accepted baseline and scope

On October 2 the owner accepted native **macOS27 / Xcode27** instead of the
unavailable macOS26/Xcode26.5 environment, from
`e1ae3f37b27780cc4d9efaa16228fcb75c8e159b`. This is the official ARM continuation,
not supplemental host evidence. The older hosted ARM26 matrix is historical;
its environment is **not** a prerequisite for this command. Intel and ART remain
separate lanes. Original failures, prior receipt scopes, and Foundation
**NOT_READY** remain unchanged.

`scripts/run-rpc-local-arm-qualification.py` executes only the outstanding
ordinary Swift, actual production-adapter lifecycle/cancellation, and current
iPhone app gates, with their required source-matched producers. It does not
repeat the already-passed full-platform, ABI, Dokka, SBOM or capacity suites.
It also prepares, but does not execute, the current-source JVM mobile driver;
an older transferred JAR manifest cannot be relabeled as the current phone source.
The plan also runs the real 125-second Mac generator clock/memory preflight,
which requires native authorization but **does not require a phone**. Each later
physical workload still needs a fresh immediately preceding health observation.
New native controls are necessary because a new product-execution session needs
its own admission: the old pure-command readiness proof is not a product receipt.

The controller uses the **same** native executor, original deadlines, individual
XCTest assessors, nested provenance and exact simulator/native finalizers as the
maintained qualification. No fake hosted-runner variables, skipped methods,
timeout extensions, application downloads, private signing, device queries,
permission changes or system installation are admitted. Installed JDK17/JDK21,
XcodeGen2.45.4 and Android compile platforms36/37 are reused. Strict Gradle and
Kotlin/Native dependencies populate fresh private homes; previous build caches
and artifacts are not restored.

## Prepare once, then execute the newly authorized session

Use **only** `$HOME/Projects/P2pKit-RPC-current`, with a clean committed descendant
of the baseline. Never modify the old `$HOME/Projects/P2pKit` checkout.

```bash
cd "$HOME/Projects/P2pKit-RPC-current"
parent=$(mktemp -d "$HOME/Projects/P2pKit-arm27-product.XXXXXXXX")
python=/opt/homebrew/opt/python@3.14/bin/python3.14
"$python" -B scripts/run-rpc-local-arm-qualification.py prepare \
  --owner-authorized-arm27 --parent "$parent" --expected-commit "$(git rev-parse HEAD)" \
  --java-home /opt/homebrew/opt/openjdk@17/libexec/openjdk.jdk/Contents/Home \
  --jdk21 /opt/homebrew/opt/openjdk@21/libexec/openjdk.jdk/Contents/Home \
  --android-sdk "$HOME/Library/Android/sdk" \
  --xcodegen /opt/homebrew/opt/xcodegen/bin/xcodegen
```

Preparation does **not** invoke sudo or run native tools. Product execution
requires one new authorized isolated audit session, not a rerun of either used
readiness session. The existing bootstrap allocates only the process-local
audit session and permanently drops privilege before any observer or product:

```bash
sudo "$python" -I -S "$PWD/scripts/with-darwin-audit-session.py" \
  --bootstrap "$parent/private-session/session-config.json"
```

Do not repeat a consumed command/configuration or retry a failed product phase.
If authentication is unavailable, retain that boundary and continue independent
offline engineering. A prepared request is not a qualification result.

## Evidence and remaining boundaries

The create-only parent retains `prepared.json`, fresh session admission,
`state/context.json`, every native receipt/log, individual XCTest manifests,
`state/private/result.json`, phone diagnostics, and source/tool hashes.
Only a successfully assessed phone app with verified outer/native and simulator
cleanup can export `p2pkit-rpc-iphone-unsigned.app.zip` and `phone-export.json`.
The app is unsigned and **not physically installable** without owner signing.

Report every phase separately. An ordinary assertion failure does not suppress
independent cancellation/phone controls; unproven native ownership does. No
overall percentage follows from adding overlapping methods. Simulator results
do not replace USB publication, physical resource measurements, trust/signing,
real LAN infrastructure or independent external campaigns.
