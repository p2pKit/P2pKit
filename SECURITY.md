# Security policy

## Supported versions

| Version | Security support |
| --- | --- |
| Latest published `0.7.x` release candidate | Supported |
| `0.6.x` and older | Unsupported legacy line |

Published artifacts remain immutable. Security fixes are released under a new
version; old Maven coordinates and Git tags are never overwritten.

## Report a vulnerability

Use [GitHub private vulnerability reporting](https://github.com/p2pKit/P2pKit/security/advisories/new).
Do not open a public issue for an unpatched vulnerability and do not include
private keys, credentials, tokens, signing material, personal data, or sensitive
payloads in reports or diagnostic exports.

Include the affected version/commit, platform, impact, prerequisites, minimal
reproduction, and any safe logs or traces. You should receive an initial
best-effort acknowledgement through the private advisory. Disclosure timing
will be coordinated after triage and a fix/release plan exists.

## Security scope

Authenticated v2 is the default, but product authorization and safe application
payload handling remain the consumer's responsibility. Read the
[security model](docs/security/model.md) before deployment.

Independent secure-v2 interoperability validation and a professional
cryptographic audit are still pending. The current release candidate must not
be represented as independently audited or fully production validated.
