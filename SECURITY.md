# Security policy

## Supported version

Security fixes target the current default branch and the latest published release. Older snapshots may be used
for comparison but are not maintained.

## Reporting a vulnerability

Do not open a public issue for a suspected vulnerability, credential exposure, unsafe installer behavior, or a
path that could modify files outside its declared target. Use GitHub's **Security → Report a vulnerability**
(private vulnerability reporting) for this repository. Include:

- the exact commit and platform;
- the affected command and minimal reproduction;
- expected versus observed filesystem, process, network, or credential behavior;
- whether real credentials, paid provider requests, game saves, or third-party systems were involved.

Never include live keys, tokens, cookies, private save data, or proprietary game files. Revoke exposed
credentials with their provider before reporting.

## Security boundaries

- Backups and restore archives are untrusted input and must pass path, member, size, and digest validation.
- `FAL_KEY` may be sent only to canonical fal API origins; provider output downloads must resolve publicly.
- ComfyUI is loopback-only by default; remote use requires explicit HTTPS opt-in.
- Windows values are transported as data, not interpolated into PowerShell source.
- Publishing and knowledge PRs fail closed on secrets, symlinks, decompiler fingerprints, unrelated staged
  changes, and remote/SHA mismatches.
- Game-folder installers must preserve pre-existing and user-modified files.

A green local suite is not evidence that native Windows/WSL, paid-provider, game-runtime, or release-governance
requirements were exercised.
