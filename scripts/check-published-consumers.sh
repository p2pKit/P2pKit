#!/usr/bin/env bash
# Publishes every library to an isolated Maven repository, verifies the target
# POM scopes, then compiles fresh JVM/Android/KMP/iOS consumers that depend only
# on the top-level P2pKit artifact under test. Project dependencies and the
# repository source tree are intentionally unavailable to those consumers.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VERSION="$(sed -n 's/^VERSION_NAME=//p' "$ROOT/gradle.properties" | tr -d '[:space:]')"
WORK_DIR="$(mktemp -d "${TMPDIR:-/tmp}/p2pkit-consumer-check.XXXXXX")"
REPO_DIR="$WORK_DIR/repository"
FIXTURE_DIR="$WORK_DIR/consumer"
REMOTE_REPOSITORY_URL="${P2PKIT_CONSUMER_REPOSITORY_URL:-}"
trap 'rm -rf "$WORK_DIR"' EXIT

fail() {
    echo "FAIL: $*" >&2
    exit 1
}

pom_scope() {
    local pom="$1" artifact="$2"
    awk -v artifact="$artifact" '
        /<dependency>/ { in_dependency = 1; matched = 0 }
        in_dependency && index($0, "<artifactId>" artifact "</artifactId>") { matched = 1 }
        in_dependency && matched && /<scope>/ {
            line = $0
            sub(/^.*<scope>/, "", line)
            sub(/<\/scope>.*$/, "", line)
            print line
            exit
        }
        /<\/dependency>/ { in_dependency = 0; matched = 0 }
    ' "$pom"
}

assert_scope() {
    local pom="$1" artifact="$2" expected="$3" actual
    actual="$(pom_scope "$pom" "$artifact")"
    [[ "$actual" == "$expected" ]] ||
        fail "$(basename "$(dirname "$pom")")/$artifact scope was '${actual:-missing}', expected '$expected'"
}

if [[ -n "$REMOTE_REPOSITORY_URL" ]]; then
    [[ "$REMOTE_REPOSITORY_URL" == https://* ]] ||
        fail "remote consumer repository must use HTTPS"
    command -v curl >/dev/null 2>&1 || fail "curl is required for remote consumer verification"
    echo "==> Downloading $VERSION POMs from remote repository"
    mkdir -p "$REPO_DIR/dev/p2pkit"
    for artifact in \
        p2p-core-jvm \
        p2p-transport-lan-jvm \
        p2p-network-provisioning-android-android \
        p2p-network-provisioning-desktop; do
        directory="$REPO_DIR/dev/p2pkit/$artifact/$VERSION"
        mkdir -p "$directory"
        curl --fail --silent --show-error --location \
            "$REMOTE_REPOSITORY_URL/dev/p2pkit/$artifact/$VERSION/$artifact-$VERSION.pom" \
            --output "$directory/$artifact-$VERSION.pom"
    done
    CONSUMER_REPOSITORY="$REMOTE_REPOSITORY_URL"
else
    echo "==> Publishing $VERSION to isolated repository"
    (cd "$ROOT" && ./gradlew --console=plain publishToMavenLocal -Dmaven.repo.local="$REPO_DIR")
    CONSUMER_REPOSITORY="$REPO_DIR"
fi

BASE="$REPO_DIR/dev/p2pkit"
CORE_JVM="$BASE/p2p-core-jvm/$VERSION/p2p-core-jvm-$VERSION.pom"
LAN_JVM="$BASE/p2p-transport-lan-jvm/$VERSION/p2p-transport-lan-jvm-$VERSION.pom"
PROV_ANDROID="$BASE/p2p-network-provisioning-android-android/$VERSION/p2p-network-provisioning-android-android-$VERSION.pom"
PROV_DESKTOP="$BASE/p2p-network-provisioning-desktop/$VERSION/p2p-network-provisioning-desktop-$VERSION.pom"

for pom in "$CORE_JVM" "$LAN_JVM" "$PROV_ANDROID" "$PROV_DESKTOP"; do
    [[ -f "$pom" ]] || fail "missing generated POM: $pom"
done

assert_scope "$CORE_JVM" kotlinx-coroutines-core-jvm compile
assert_scope "$CORE_JVM" kotlinx-io-core-jvm compile
assert_scope "$CORE_JVM" kotlinx-serialization-json-jvm runtime
assert_scope "$CORE_JVM" cryptography-core-jvm runtime
assert_scope "$CORE_JVM" cryptography-provider-jdk-jvm runtime
assert_scope "$CORE_JVM" bcprov-jdk18on runtime

assert_scope "$LAN_JVM" p2p-core-jvm compile
assert_scope "$LAN_JVM" kotlinx-coroutines-core-jvm compile
assert_scope "$LAN_JVM" jmdns runtime

assert_scope "$PROV_ANDROID" p2p-core-android compile
assert_scope "$PROV_ANDROID" kotlinx-coroutines-core-jvm compile

assert_scope "$PROV_DESKTOP" p2p-core-jvm compile
assert_scope "$PROV_DESKTOP" kotlinx-coroutines-core-jvm compile
[[ -z "$(pom_scope "$PROV_DESKTOP" p2p-transport-lan-jvm)" ]] ||
    fail "desktop provisioning still publishes its test-only LAN dependency"

mkdir -p \
    "$FIXTURE_DIR/coreJvm/src/main/kotlin/consumer" \
    "$FIXTURE_DIR/coreJvm/src/main/java/consumer" \
    "$FIXTURE_DIR/lanJvm/src/main/kotlin/consumer" \
    "$FIXTURE_DIR/desktopJvm/src/main/kotlin/consumer" \
    "$FIXTURE_DIR/androidConsumer/src/main/kotlin/consumer" \
    "$FIXTURE_DIR/kmpConsumer/src/commonMain/kotlin/consumer" \
    "$FIXTURE_DIR/kmpConsumer/src/jvmMain/kotlin/consumer" \
    "$FIXTURE_DIR/kmpConsumer/src/androidMain/kotlin/consumer" \
    "$FIXTURE_DIR/kmpConsumer/src/iosMain/kotlin/consumer"

if [[ -z "${ANDROID_HOME:-}" && -z "${ANDROID_SDK_ROOT:-}" ]]; then
    SDK_LINE="$(sed -n '/^sdk\.dir=/p' "$ROOT/local.properties" 2>/dev/null | tail -n 1)"
    [[ -n "$SDK_LINE" ]] || fail "Android SDK is unavailable (set ANDROID_HOME/ANDROID_SDK_ROOT or local.properties sdk.dir)"
    printf '%s\n' "$SDK_LINE" > "$FIXTURE_DIR/local.properties"
fi

cat > "$FIXTURE_DIR/settings.gradle.kts" <<'EOF'
pluginManagement {
    repositories {
        google()
        gradlePluginPortal()
        mavenCentral()
    }
}
dependencyResolutionManagement {
    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories {
        maven { url = uri(providers.gradleProperty("consumerRepo").get()) }
        google()
        mavenCentral()
    }
}
rootProject.name = "p2pkit-published-consumers"
include(":coreJvm", ":lanJvm", ":desktopJvm", ":androidConsumer", ":kmpConsumer")
EOF

cat > "$FIXTURE_DIR/build.gradle.kts" <<'EOF'
plugins {
    kotlin("jvm") version "2.3.21" apply false
    kotlin("multiplatform") version "2.3.21" apply false
    id("com.android.application") version "9.1.1" apply false
    id("com.android.library") version "9.1.1" apply false
    id("com.android.kotlin.multiplatform.library") version "9.1.1" apply false
}
EOF

cat > "$FIXTURE_DIR/coreJvm/build.gradle.kts" <<EOF
plugins { kotlin("jvm") }
kotlin { jvmToolchain(17) }
dependencies { implementation("dev.p2pkit:p2p-core-jvm:$VERSION") }
EOF
cat > "$FIXTURE_DIR/coreJvm/src/main/kotlin/consumer/CoreConsumer.kt" <<'EOF'
package consumer

import dev.p2pkit.core.P2pKit
import dev.p2pkit.core.P2pError
import dev.p2pkit.core.P2pSession
import dev.p2pkit.core.P2pState
import dev.p2pkit.core.FeatureState
import dev.p2pkit.core.ExperimentalP2pApi
import dev.p2pkit.core.FileTransferFailureKind
import dev.p2pkit.core.FileTransferPhase
import dev.p2pkit.core.Peer
import dev.p2pkit.core.PeerFingerprint
import dev.p2pkit.core.Retryability
import dev.p2pkit.core.TransportKind
import dev.p2pkit.core.provisioning.JoinNetworkResult
import dev.p2pkit.core.provisioning.LocalNetworkConfig
import dev.p2pkit.core.provisioning.LocalNetworkResult
import dev.p2pkit.core.provisioning.ManualConnectionInfo
import dev.p2pkit.core.provisioning.NetworkProvisioningEvent
import dev.p2pkit.core.provisioning.NetworkProvisioningManager
import dev.p2pkit.core.provisioning.NetworkProvisioningState
import dev.p2pkit.core.provisioning.NetworkState
import dev.p2pkit.core.provisioning.WifiCredentials
import dev.p2pkit.core.transport.DataTransport
import dev.p2pkit.core.transport.InternalPeer
import dev.p2pkit.core.transport.RawConnection
import dev.p2pkit.core.transport.TransportContext
import dev.p2pkit.core.transport.TransportDescriptor
import dev.p2pkit.core.transport.TransportFactory
import dev.p2pkit.core.transport.TransportPair
import dev.p2pkit.core.transfer.P2pFileOffer
import dev.p2pkit.core.transfer.FileTransferDestination
import dev.p2pkit.core.transfer.PreparedFileSource
import dev.p2pkit.core.transfer.Sha256Digest
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.emptyFlow
import kotlinx.io.RawSink
import kotlinx.io.RawSource
import kotlinx.io.Buffer

fun coreState(kit: P2pKit, sink: RawSink): StateFlow<P2pState> {
    sink.flush()
    return kit.state
}

fun featureStates(kit: P2pKit): Pair<StateFlow<FeatureState>, StateFlow<FeatureState>> =
    kit.advertisingState to kit.discoveryState

fun pendingOffers(session: P2pSession): StateFlow<List<P2pFileOffer>> =
    session.pendingFileOffers

fun classifyTransferFailure(error: P2pError.FileTransferFailed): String =
    "${error.kind}:${error.phase}:${error.retryability}:${error.transferId}:${error.reason}"

fun constructTransferFailure(): P2pError.FileTransferFailed =
    P2pError.FileTransferFailed(
        kind = FileTransferFailureKind.STORAGE,
        phase = FileTransferPhase.DURABLE_COMMIT,
        retryability = Retryability.RETRY_AFTER_USER_ACTION,
        transferId = "0123456789abcdef0123456789abcdef",
        reason = "fixture"
    )

class ExternalPreparedFileSource(private val content: ByteArray) : PreparedFileSource {
    override val sizeBytes: Long = content.size.toLong()
    override val sha256: Sha256Digest = Sha256Digest(ByteArray(32))
    override fun open(): RawSource = Buffer().apply { write(content) }
}

class ExternalFileDestination : FileTransferDestination {
    override fun openSink(): RawSink = Buffer()
    override suspend fun commit() = Unit
    override suspend fun abort(cause: P2pError.FileTransferFailed?) = Unit
}

suspend fun secureTransferSurface(
    session: P2pSession,
    offer: P2pFileOffer,
    source: PreparedFileSource,
    destination: FileTransferDestination
) {
    session.sendFile("fixture.bin", "application/octet-stream", source)
    offer.accept(destination)
    P2pError.UnsupportedFeature("fixture-feature").feature
}

fun copyPeer(peer: Peer): Peer {
    val (id, name, platform, transports) = peer
    return peer.copy(id, name, platform, transports)
}

class ExternalDataTransport : DataTransport {
    override val type: TransportKind = TransportKind.LAN
    override val priority: Int = 1
    override suspend fun stop() = Unit
    override fun canConnect(peer: InternalPeer): Boolean = false
    override suspend fun connect(peer: InternalPeer): RawConnection = error("not supported")
    override fun incomingConnections(): Flow<RawConnection> = emptyFlow()
    override suspend fun close() = Unit
}

class ExternalTransportFactory : TransportFactory {
    override val descriptor: TransportDescriptor =
        TransportDescriptor.dataOnly(TransportKind.LAN)

    override fun build(context: TransportContext): TransportPair =
        TransportPair(data = ExternalDataTransport())
}

@OptIn(ExperimentalP2pApi::class)
class ExternalProvisioningManager : NetworkProvisioningManager {
    override val state: StateFlow<NetworkProvisioningState> =
        MutableStateFlow(NetworkProvisioningState.Idle)
    override val networkState: StateFlow<NetworkState> = MutableStateFlow(NetworkState.Unknown)
    override val events: Flow<NetworkProvisioningEvent> = emptyFlow()

    override suspend fun startLocalNetwork(config: LocalNetworkConfig): LocalNetworkResult =
        LocalNetworkResult.Unsupported("external fixture")
    override suspend fun stopLocalNetwork() = Unit
    override suspend fun joinLocalNetwork(credentials: WifiCredentials): JoinNetworkResult =
        JoinNetworkResult.Unsupported("external fixture")
    override suspend fun getManualConnectionInfo(): ManualConnectionInfo? = null

    @Deprecated("legacy fixture overload")
    override suspend fun createManualPeer(host: String, port: Int): Peer = error("not supported")

    override suspend fun createManualPeer(
        host: String,
        port: Int,
        expectedFingerprint: PeerFingerprint
    ): Peer = error("not supported")

    override suspend fun close() = Unit
}
EOF
cat > "$FIXTURE_DIR/coreJvm/src/main/java/consumer/ImmutableModelJavaConsumer.java" <<'EOF'
package consumer;

import dev.p2pkit.core.P2pMessage;
import dev.p2pkit.core.P2pError;
import dev.p2pkit.core.FileTransferFailureKind;
import dev.p2pkit.core.FileTransferPhase;
import dev.p2pkit.core.Retryability;
import dev.p2pkit.core.TransportKind;
import dev.p2pkit.core.provisioning.NetworkState;
import dev.p2pkit.core.transport.TransportCapability;
import dev.p2pkit.core.transport.TransportDescriptor;
import dev.p2pkit.core.transport.TransportPair;
import dev.p2pkit.core.transport.TransportHint;
import dev.p2pkit.core.transfer.Sha256Digest;
import dev.p2pkit.core.transfer.PreparedFileSource;
import dev.p2pkit.core.transfer.FileTransferDestination;
import java.util.List;
import java.util.Map;

final class ImmutableModelJavaConsumer {
    static void compilePublicSurface() {
        P2pMessage.Text text = new P2pMessage.Text("hello", Map.of("key", "value"));
        P2pMessage.Text copied = text.copy(text.getValue(), text.getMetadata());
        TransportHint hint = new TransportHint(
            TransportKind.LAN,
            "192.0.2.1",
            4242,
            Map.of("scope", "lan")
        );
        NetworkState.ConnectedToEthernet ethernet =
            new NetworkState.ConnectedToEthernet(List.of("192.0.2.10"));
        TransportDescriptor descriptor =
            TransportDescriptor.Companion.dataOnly(TransportKind.LAN);
        TransportPair pair = new TransportPair(new ExternalDataTransport(), null);
        copied.getMetadata();
        hint.getMetadata();
        ethernet.getLocalIpAddresses();
        descriptor.getCapabilities().contains(TransportCapability.DATA);
        pair.getData();
        P2pError.FileTransferFailed failure = new P2pError.FileTransferFailed(
            FileTransferFailureKind.STORAGE,
            FileTransferPhase.FLUSH,
            Retryability.RETRY_AFTER_USER_ACTION,
            "0123456789abcdef0123456789abcdef",
            "fixture"
        );
        failure.getKind();
        failure.getPhase();
        failure.getRetryability();
        failure.getTransferId();
        Sha256Digest digest = new Sha256Digest(new byte[32]);
        digest.getBytes();
        Class<PreparedFileSource> preparedType = PreparedFileSource.class;
        Class<FileTransferDestination> destinationType = FileTransferDestination.class;
        preparedType.getName();
        destinationType.getName();
        new P2pError.UnsupportedFeature("fixture-feature").getFeature();
    }
}
EOF

cat > "$FIXTURE_DIR/lanJvm/build.gradle.kts" <<EOF
plugins { kotlin("jvm") }
kotlin { jvmToolchain(17) }
dependencies { implementation("dev.p2pkit:p2p-transport-lan-jvm:$VERSION") }
EOF
cat > "$FIXTURE_DIR/lanJvm/src/main/kotlin/consumer/LanConsumer.kt" <<'EOF'
package consumer

import dev.p2pkit.core.P2pKit
import dev.p2pkit.core.P2pState
import dev.p2pkit.transport.lan.JvmLanDiag
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.flow.StateFlow

fun lanEvents(): SharedFlow<String> = JvmLanDiag.events
fun lanCoreState(kit: P2pKit): StateFlow<P2pState> = kit.state
EOF

cat > "$FIXTURE_DIR/desktopJvm/build.gradle.kts" <<EOF
plugins { kotlin("jvm") }
kotlin { jvmToolchain(17) }
dependencies { implementation("dev.p2pkit:p2p-network-provisioning-desktop:$VERSION") }
EOF
cat > "$FIXTURE_DIR/desktopJvm/src/main/kotlin/consumer/DesktopConsumer.kt" <<'EOF'
package consumer

import dev.p2pkit.core.provisioning.NetworkProvisioningManager
import dev.p2pkit.core.provisioning.NetworkProvisioningState
import dev.p2pkit.core.provisioning.ProvisioningContext
import dev.p2pkit.provisioning.desktop.JvmNetworkProvisioningManager
import kotlinx.coroutines.flow.StateFlow

fun desktopManager(context: ProvisioningContext): NetworkProvisioningManager =
    JvmNetworkProvisioningManager(context)

fun desktopState(manager: NetworkProvisioningManager): StateFlow<NetworkProvisioningState> =
    manager.state
EOF

cat > "$FIXTURE_DIR/androidConsumer/build.gradle.kts" <<EOF
plugins { id("com.android.application") }
android {
    namespace = "consumer.p2pkit.android"
    compileSdk = 36
    defaultConfig {
        applicationId = "consumer.p2pkit.android"
        minSdk = 24
    }
}
dependencies { implementation("dev.p2pkit:p2p-network-provisioning-android-android:$VERSION") }
dependencies { implementation("dev.p2pkit:p2p-transport-lan-android:$VERSION") }
EOF
cat > "$FIXTURE_DIR/androidConsumer/src/main/AndroidManifest.xml" <<'EOF'
<?xml version="1.0" encoding="utf-8"?>
<manifest xmlns:android="http://schemas.android.com/apk/res/android">
    <application />
</manifest>
EOF
cat > "$FIXTURE_DIR/androidConsumer/src/main/kotlin/consumer/AndroidConsumer.kt" <<'EOF'
package consumer

import android.content.Context
import dev.p2pkit.core.dsl.NetworkProvisioningConfigBuilder
import dev.p2pkit.core.provisioning.NetworkProvisioningManager
import dev.p2pkit.core.provisioning.NetworkProvisioningState
import dev.p2pkit.provisioning.android.android
import kotlinx.coroutines.flow.StateFlow

fun configureAndroidProvisioning(builder: NetworkProvisioningConfigBuilder, context: Context) {
    builder.android(context)
}

fun androidState(manager: NetworkProvisioningManager): StateFlow<NetworkProvisioningState> =
    manager.state
EOF

cat > "$FIXTURE_DIR/kmpConsumer/build.gradle.kts" <<EOF
plugins {
    kotlin("multiplatform")
    id("com.android.kotlin.multiplatform.library")
}

kotlin {
    jvm()
    android {
        namespace = "consumer.p2pkit.kmp"
        compileSdk = 36
        minSdk = 24
    }
    iosSimulatorArm64()

    sourceSets {
        commonMain.dependencies {
            implementation("dev.p2pkit:p2p-transport-lan:$VERSION")
        }
    }
}
EOF
cat > "$FIXTURE_DIR/kmpConsumer/src/commonMain/kotlin/consumer/CommonConsumer.kt" <<'EOF'
package consumer

import dev.p2pkit.core.P2pKit
import dev.p2pkit.core.P2pMessage
import dev.p2pkit.core.P2pState
import dev.p2pkit.core.FeatureState
import dev.p2pkit.core.P2pError
import dev.p2pkit.core.FileTransferFailureKind
import dev.p2pkit.core.FileTransferPhase
import dev.p2pkit.core.Retryability
import dev.p2pkit.core.transfer.FileTransferDestination
import dev.p2pkit.core.transfer.PreparedFileSource
import dev.p2pkit.core.transfer.Sha256Digest
import dev.p2pkit.core.provisioning.NetworkState
import kotlinx.coroutines.flow.StateFlow
import kotlinx.io.RawSink
import kotlinx.io.RawSource
import kotlinx.io.Buffer

fun commonState(kit: P2pKit, sink: RawSink): StateFlow<P2pState> {
    sink.flush()
    return kit.state
}

fun commonFeatureState(kit: P2pKit): StateFlow<FeatureState> = kit.discoveryState

fun commonTransferFailure(): P2pError.FileTransferFailed =
    P2pError.FileTransferFailed(
        FileTransferFailureKind.TIMEOUT,
        FileTransferPhase.OFFER,
        Retryability.RETRY_SAME_SESSION,
        null,
        "fixture"
    )

class CommonPreparedSource(private val content: ByteArray) : PreparedFileSource {
    override val sizeBytes: Long = content.size.toLong()
    override val sha256: Sha256Digest = Sha256Digest(ByteArray(32))
    override fun open(): RawSource = Buffer().apply { write(content) }
}

class CommonDestination : FileTransferDestination {
    override fun openSink(): RawSink = Buffer()
    override suspend fun commit() = Unit
    override suspend fun abort(cause: P2pError.FileTransferFailed?) = Unit
}

fun immutableValues(): Pair<P2pMessage.Text, NetworkState.ConnectedToEthernet> =
    P2pMessage.Text("hello", mapOf("key" to "value")) to
        NetworkState.ConnectedToEthernet(listOf("192.0.2.10"))
EOF
cat > "$FIXTURE_DIR/kmpConsumer/src/jvmMain/kotlin/consumer/JvmConsumer.kt" <<'EOF'
package consumer

import dev.p2pkit.transport.lan.JvmLanDiag
import kotlinx.coroutines.flow.SharedFlow

fun jvmEvents(): SharedFlow<String> = JvmLanDiag.events
EOF
cat > "$FIXTURE_DIR/kmpConsumer/src/androidMain/kotlin/consumer/AndroidConsumer.kt" <<'EOF'
package consumer

import android.content.Context
import dev.p2pkit.core.dsl.TransportsBuilder
import dev.p2pkit.transport.lan.lan

fun configureAndroidLan(builder: TransportsBuilder, context: Context) {
    builder.lan(context)
}
EOF
cat > "$FIXTURE_DIR/kmpConsumer/src/iosMain/kotlin/consumer/IosConsumer.kt" <<'EOF'
package consumer

import dev.p2pkit.transport.lan.IosLanDebug
import kotlinx.coroutines.flow.SharedFlow

fun iosEvents(): SharedFlow<String> = IosLanDebug.events
EOF

echo "==> Compiling isolated published consumers"
run_consumer_gradle() {
    if [[ -n "$REMOTE_REPOSITORY_URL" ]]; then
        GRADLE_USER_HOME="$WORK_DIR/gradle-home" "$@"
    else
        "$@"
    fi
}
(cd "$ROOT" && run_consumer_gradle ./gradlew --console=plain -p "$FIXTURE_DIR" \
    -PconsumerRepo="$CONSUMER_REPOSITORY" \
    ${REMOTE_REPOSITORY_URL:+--refresh-dependencies} \
    :coreJvm:compileKotlin \
    :coreJvm:compileJava \
    :lanJvm:compileKotlin \
    :desktopJvm:compileKotlin \
    :androidConsumer:compileDebugKotlin \
    :androidConsumer:processDebugManifest \
    :kmpConsumer:compileKotlinJvm \
    :kmpConsumer:compileAndroidMain \
    :kmpConsumer:compileKotlinIosSimulatorArm64)

MERGED_MANIFEST="$(find "$FIXTURE_DIR/androidConsumer/build/intermediates" \
    -path '*/processDebugManifest/AndroidManifest.xml' -print -quit)"
[[ -f "$MERGED_MANIFEST" ]] || fail "Android consumer merged manifest was not produced"
for permission in \
    android.permission.INTERNET \
    android.permission.ACCESS_NETWORK_STATE \
    android.permission.ACCESS_WIFI_STATE \
    android.permission.CHANGE_WIFI_MULTICAST_STATE; do
    grep -Fq "android:name=\"$permission\"" "$MERGED_MANIFEST" ||
        fail "Android consumer merged manifest is missing $permission"
done

echo "RESULT: PASS — published scopes, Android LAN permissions, and isolated JVM/Android/KMP/iOS consumers are complete"
