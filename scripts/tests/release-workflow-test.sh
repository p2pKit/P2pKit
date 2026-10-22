#!/usr/bin/env bash
# Active modular workflow contract. Obsolete C1/custody snapshots remain in Git
# history, not executable release prerequisites.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
ruby "$ROOT/scripts/check-modular-ci-policy.rb"
ruby "$ROOT/scripts/tests/check-modular-ci-policy-test.rb"
ruby "$ROOT/scripts/check-workflow-checkout-policy.rb"
ruby "$ROOT/scripts/tests/check-consumer-gradle-policy-test.rb"
scripts/tests/check-release-identity-test.sh
scripts/tests/check-maven-release-environment-test.sh
scripts/tests/check-maven-namespace-access-test.sh
scripts/tests/check-maven-central-version-test.sh
scripts/tests/publish-central-portal-bundle-test.sh
# The real disposable-key bundle integration test runs in the macOS compatibility component.
