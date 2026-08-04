#!/usr/bin/env bash
# Install the reviewed XcodeGen release into a caller-owned directory.
set -euo pipefail

XCODEGEN_VERSION="2.45.4"
XCODEGEN_SHA256="090ec29491aad50aec10631bf6e62253fed733c50f3aab0f5ffc86bc170bdbef"
XCODEGEN_URL="https://github.com/yonaskolb/XcodeGen/releases/download/$XCODEGEN_VERSION/xcodegen.zip"

calculate_sha256() {
    shasum -a 256 "$1" | awk '{print $1}'
}

verify_xcodegen_archive() {
    local archive="$1"
    local expected_sha256="$2"
    local actual_sha256
    actual_sha256="$(calculate_sha256 "$archive")"
    if [[ "$actual_sha256" != "$expected_sha256" ]]; then
        echo "FATAL: XcodeGen archive checksum mismatch." >&2
        echo "Expected: $expected_sha256" >&2
        echo "Actual:   $actual_sha256" >&2
        return 1
    fi
}

install_xcodegen_archive() {
    local archive="$1"
    local install_root="$2"
    local expected_version="$3"
    local unpack_root binary version_output

    if [[ -e "$install_root" ]]; then
        echo "FATAL: XcodeGen install destination already exists: $install_root" >&2
        return 1
    fi

    unpack_root="$(mktemp -d "${TMPDIR:-/tmp}/p2pkit-xcodegen-unpack.XXXXXX")"
    if ! unzip -q "$archive" -d "$unpack_root"; then
        rm -rf -- "$unpack_root"
        return 1
    fi
    binary="$unpack_root/xcodegen/bin/xcodegen"
    if [[ ! -x "$binary" ]]; then
        echo "FATAL: reviewed XcodeGen archive does not contain an executable binary." >&2
        rm -rf -- "$unpack_root"
        return 1
    fi
    version_output="$($binary --version)"
    if [[ "$version_output" != "Version: $expected_version" ]]; then
        echo "FATAL: XcodeGen version mismatch: $version_output" >&2
        rm -rf -- "$unpack_root"
        return 1
    fi

    mkdir -p -- "$(dirname "$install_root")"
    mv -- "$unpack_root/xcodegen" "$install_root"
    rmdir -- "$unpack_root"
    printf '%s\n' "$install_root/bin"
}

main() {
    if [[ $# -ne 1 || -z "$1" ]]; then
        echo "Usage: $0 INSTALL_ROOT" >&2
        return 2
    fi

    local install_root="$1"
    local download_root archive bin_dir
    download_root="$(mktemp -d "${TMPDIR:-/tmp}/p2pkit-xcodegen-download.XXXXXX")"
    archive="$download_root/xcodegen.zip"
    trap 'rm -rf -- "${download_root:-}"' EXIT

    curl \
        --fail \
        --location \
        --silent \
        --show-error \
        --retry 3 \
        --retry-all-errors \
        --connect-timeout 30 \
        --max-time 180 \
        --output "$archive" \
        "$XCODEGEN_URL"
    verify_xcodegen_archive "$archive" "$XCODEGEN_SHA256"
    bin_dir="$(install_xcodegen_archive "$archive" "$install_root" "$XCODEGEN_VERSION")"
    rm -rf -- "$download_root"
    download_root=""
    trap - EXIT
    printf '%s\n' "$bin_dir"
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
    main "$@"
fi
