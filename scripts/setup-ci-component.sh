#!/usr/bin/env bash
# Tool setup only; no private tests/logs or source mutation.
set -euo pipefail
component="$1"
if [[ "$component" == source ]]; then
  dir="$RUNNER_TEMP/p2pkit-actionlint"
  mkdir -m 700 "$dir"
  curl --fail --location --proto '=https' --tlsv1.2 --connect-timeout 15 --max-time 120 \
    --output "$dir/actionlint.tar.gz" https://github.com/rhysd/actionlint/releases/download/v1.7.12/actionlint_1.7.12_linux_amd64.tar.gz
  echo "8aca8db96f1b94770f1b0d72b6dddcb1ebb8123cb3712530b08cc387b349a3d8  $dir/actionlint.tar.gz" | sha256sum --check
  tar -xzf "$dir/actionlint.tar.gz" -C "$dir" actionlint
  echo "$dir" >> "$GITHUB_PATH"
fi
# Shared-check, consumer/writer and focused JmDNS CLI routes select one explicit
# macOS 15 Intel baseline. Native/installer/Swift lanes retain their images.
if [[ "$component" == macos-shared || "$component" == consumers || "$component" == published-consumers-diagnostic || "$component" == consumers-pom-diagnostic || "$component" == jmdns-diagnostic || "$component" == dependency-update ]]; then
  [[ "${RUNNER_OS:-}" == macOS && "${RUNNER_ARCH:-}" == X64 ]] || exit 1
  [[ "$(sw_vers -productVersion)" == 15.* ]] || exit 1
fi
if [[ "${RUNNER_OS:-}" == macOS ]]; then
  if [[ "$component" == macos-shared || "$component" == consumers || "$component" == published-consumers-diagnostic || "$component" == consumers-pom-diagnostic || "$component" == jmdns-diagnostic || "$component" == dependency-update ]]; then
    xcode=/Applications/Xcode_26.3.app/Contents/Developer
  elif [[ "${RUNNER_ARCH:-}" == ARM64 ]]; then xcode=/Applications/Xcode_26.5.app/Contents/Developer
  else xcode=/Applications/Xcode_26.3.app/Contents/Developer; fi
  test -d "$xcode"
  if [[ "$component" == macos-shared || "$component" == consumers || "$component" == published-consumers-diagnostic || "$component" == consumers-pom-diagnostic || "$component" == jmdns-diagnostic || "$component" == dependency-update ]]; then
    version="$(DEVELOPER_DIR="$xcode" xcodebuild -version)"
    [[ "${version%%$'\n'*}" == 'Xcode 26.3' ]] || exit 1
  fi
  echo "DEVELOPER_DIR=$xcode" >> "$GITHUB_ENV"
  xcodegen_bin_dir="$(scripts/install-xcodegen.sh "$RUNNER_TEMP/p2pkit-xcodegen")"
  echo "$xcodegen_bin_dir" >> "$GITHUB_PATH"
fi
# Android AARs are also built by compatibility, consumers, and signed Maven
# publication/recovery. Install the producer pin on every Gradle-capable lane.
if [[ "$component" != source && "$component" != security ]]; then
  sdk="${ANDROID_HOME:-${ANDROID_SDK_ROOT:-}}"
  if [[ "${RUNNER_OS:-}" == Windows ]]; then
    sdk="$(cygpath -u "$sdk")"
    "$sdk/cmdline-tools/latest/bin/sdkmanager.bat" 'platforms;android-36' 'platforms;android-37.0' 'ndk;29.0.14206865'
  else
    "$sdk/cmdline-tools/latest/bin/sdkmanager" 'platforms;android-36' 'platforms;android-37.0' 'ndk;29.0.14206865'
  fi
fi
if [[ "$component" == security ]]; then
  dir="$RUNNER_TEMP/p2pkit-modular-osv"
  mkdir -m 700 "$dir"
  curl --fail --location --proto '=https' --tlsv1.2 --connect-timeout 15 --max-time 180 \
    --output "$dir/osv-scanner" https://github.com/google/osv-scanner/releases/download/v2.5.0/osv-scanner_linux_amd64
  echo "edcfc41d257db36148f065055655fe3fcfc434b0b423ea67468a84c207524e0c  $dir/osv-scanner" | sha256sum --check
  chmod 700 "$dir/osv-scanner"
  echo "CI_OSV_BINARY=$dir/osv-scanner" >> "$GITHUB_ENV"
  {
    echo 'OSV_SCAN_ARGS<<P2PKIT_OSV_ARGS'
    echo '--config=./osv-scanner.toml'
    echo '--sbom=./library/p2p-transport-lan/vendor/jmdns/upstream.cdx.json'
    git ls-files '*gradle.lockfile' | while IFS= read -r path; do
      # Match the maintained OSV route: empty Gradle roots are not dependency
      # inputs, and nonstandard basenames need the explicit Gradle parser.
      if ! grep -Eq '^[^#[:space:]][^=]*:[^=]*=' "$path"; then continue; fi
      if [[ "${path##*/}" != gradle.lockfile ]]; then echo "--lockfile=gradle.lockfile:./$path"
      else echo "--lockfile=./$path"; fi
    done
    echo 'P2PKIT_OSV_ARGS'
  } >> "$GITHUB_ENV"
fi
# The Windows preview runtime is still disabled for productive RPC, but its
# packaging tools must come from the reviewed exact supplier archive. Standard
# setup-java provides the installation; Gradle compares its actual bytes below.
if [[ "$component" == desktop-windows ]]; then
  pin=samples/p2p-sample-rpc/native/windows-loader-jdk21/runtime-supplier.properties
  archive="$RUNNER_TEMP/p2pkit-windows-runtime-supplier.zip"
  url="$(sed -n 's/^url=//p' "$pin")"
  expected="$(sed -n 's/^sha256=//p' "$pin")"
  [[ "$url" == https://github.com/adoptium/temurin21-binaries/releases/download/* ]]
  [[ "$expected" =~ ^[0-9a-f]{64}$ ]]
  test ! -e "$archive"
  curl --fail --location --proto '=https' --tlsv1.2 --connect-timeout 15 --max-time 600 \
    --output "$archive" "$url"
  printf '%s  %s\n' "$expected" "$archive" | sha256sum --check
  echo "P2PKIT_RPC_WINDOWS_JDK21_ARCHIVE=$(cygpath -w "$archive")" >> "$GITHUB_ENV"
fi
# Hosted images differ; GPG is used only with the pinned public recipient.
if ! command -v gpg >/dev/null; then
  if [[ "${RUNNER_OS:-}" == macOS ]]; then
    brew install gnupg
  elif [[ "${RUNNER_OS:-}" == Windows && -x /c/Program\ Files/Git/usr/bin/gpg.exe ]]; then
    echo 'C:\Program Files\Git\usr\bin' >> "$GITHUB_PATH"
  else
    echo 'Required public-key encryption tool gpg is unavailable' >&2
    exit 1
  fi
fi
