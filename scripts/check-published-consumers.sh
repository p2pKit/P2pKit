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

echo "==> Publishing $VERSION to isolated repository"
(cd "$ROOT" && ./gradlew --console=plain publishToMavenLocal -Dmaven.repo.local="$REPO_DIR")

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
import dev.p2pkit.core.P2pState
import kotlinx.coroutines.flow.StateFlow
import kotlinx.io.RawSink

fun coreState(kit: P2pKit, sink: RawSink): StateFlow<P2pState> {
    sink.flush()
    return kit.state
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
import dev.p2pkit.core.P2pState
import kotlinx.coroutines.flow.StateFlow
import kotlinx.io.RawSink

fun commonState(kit: P2pKit, sink: RawSink): StateFlow<P2pState> {
    sink.flush()
    return kit.state
}
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
(cd "$ROOT" && ./gradlew --console=plain -p "$FIXTURE_DIR" \
    -PconsumerRepo="$REPO_DIR" \
    :coreJvm:compileKotlin \
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
