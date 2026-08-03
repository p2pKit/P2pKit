# Maven Central release workflow

P2pKit publishes immutable release-candidate artifacts from an exact Git tag.
The current release identity is `dev.p2pkit:*:0.7.0-rc1`, derived from
`gradle.properties`, and the only accepted tag is `v0.7.0-rc1`.

## Trust boundary

The `Publish Maven Central` workflow first runs a secret-free complete release
gate. The second job references the protected `maven-central` GitHub
Environment. Its secrets are unavailable until the required reviewer approves
the deployment. Approval authorizes a one-shot upload with Central Portal
`publishingType=AUTOMATIC`; a validated deployment may therefore become public
without a second prompt.

Never rerun an upload after a transport error without inspecting Central Portal.
The request may have been accepted even when the response was lost. Maven
Central versions cannot be overwritten or removed through the release workflow.

## GitHub Environment contract

Create an environment named `maven-central`, require reviewer
`Apdelrahman1911`, disallow administrator bypass, and restrict deployment to
the tag pattern `v*`. `prevent_self_review` remains disabled intentionally:
the sole designated release owner may both push the reviewed tag and provide
the one explicit publication approval.

Environment secrets:

| Name | Value |
|---|---|
| `MAVEN_CENTRAL_USERNAME` | Central Portal user-token username |
| `MAVEN_CENTRAL_PASSWORD` | Central Portal user-token password |
| `MAVEN_SIGNING_KEY_B64` | Base64 of the ASCII-armored secret-key export |
| `MAVEN_SIGNING_PASSWORD` | Non-empty signing-key passphrase |

Environment variables:

| Name | Value |
|---|---|
| `MAVEN_SIGNING_KEY_FINGERPRINT` | Complete uppercase primary-key fingerprint |
| `MAVEN_CENTRAL_TOKEN_ROTATE_BY` | Maintainer-enforced token rotation deadline as `YYYY-MM-DD`, more than 14 days away |

The rotation deadline is a conservative local control and may be earlier than
the expiration selected in Central Portal. Replacing the Portal token must also
move this date and update both Central environment secrets together.

Do not put any secret in repository variables, workflow inputs, command-line
arguments, issues, release notes, or logs. The workflow verifies secret presence
without printing values and masks the derived Portal bearer value.

## Local dry run

The complete secret-free release gate is:

```bash
scripts/check-release-tag.sh v0.7.0-rc1
scripts/run-release-gate.sh
```

A signed local bundle requires the same key material used by the environment:

```bash
ORG_GRADLE_PROJECT_signingInMemoryKeyBase64="$MAVEN_SIGNING_KEY_B64" \
ORG_GRADLE_PROJECT_signingInMemoryKeyPassword="$MAVEN_SIGNING_PASSWORD" \
MAVEN_SIGNING_KEY_FINGERPRINT="$MAVEN_SIGNING_KEY_FINGERPRINT" \
  scripts/build-central-portal-bundle.sh
```

This command creates the ZIP, an inventory manifest, and a JSON summary. It
does not upload. Automated tests use a disposable one-day signing key and never
use the production secrets.

## Publication sequence

1. Merge the verified release commit into `main`.
2. Confirm `dev.p2pkit:*:0.7.0-rc1` is absent from Maven Central.
3. Push the exact tag `v0.7.0-rc1` only with owner authorization.
4. Review the secret-free job results and commit SHA.
5. Approve the pending `maven-central` environment deployment.
6. Do not cancel the workflow after upload begins; Central may continue even if
   the runner stops.
7. Retain the deployment ID, bundle hash, status JSON, artifact inventory, and
   remote-consumer evidence uploaded by the workflow.

The release is complete only when Portal reports `PUBLISHED`, every downloaded
file matches the bundle, and isolated JVM, Android, KMP, and iOS consumers
compile against `https://repo.maven.apache.org/maven2` without `mavenLocal()`.
