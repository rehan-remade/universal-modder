# Passthrough installer recovery

`install_passthrough.py` is supported only from Linux/WSL. Native Windows execution fails closed.

## Inspect without changing managed files

Run:

```bash
python gta/install_passthrough.py status "$GTA_DIR"
```

`status` acquires the same parent-scoped process lock as install/remove/recover, pins the selected game-directory inode, and prints JSON containing only transaction-control state and journal-declared path names. It does not scan the full game directory or print file contents.

Important fields:

- `receipt_bound: true` means the manifest and ownership marker are hard links to the same inode.
- `journal: regular` means an interrupted transaction still has recovery evidence.
- `target`, `stage`, `target_quarantine`, and `stage_quarantine` report only `absent`, `regular`, `directory`, `symlink`, or `other`.
- `receipt_error` means the control receipt is malformed or unsafe; preserve it for review.

## Retry automatic recovery

Run:

```bash
python gta/install_passthrough.py recover "$GTA_DIR"
```

Recovery runs under the same lock and pinned-root boundary. It removes only files whose inode and SHA-256 still match the transaction evidence. It also finishes an interrupted receipt retirement only when every managed target is absent. If any target, stage, or quarantine changed, recovery stops and preserves the journal/evidence.

Normal `install` and `remove` operations invoke recovery first, but the explicit command lets an operator inspect with `status` before retrying.

## Retained states

- **Journal plus changed stage/quarantine:** preserve every listed path. Copy the control files and named residue to a separate evidence directory before making a manual decision.
- **Manifest without marker:** the public ownership receipt is invalid. If managed targets remain, recovery fails closed. If targets are absent, recovery may retire the invalid manifest after transaction-owned residue is safely handled.
- **Marker without manifest:** recovery removes the marker only when every receipt-declared target, including broken symlinks, is absent.
- **Visible target plus distinct quarantine:** both are preserved because ownership is ambiguous.
- **Visible target plus same-inode quarantine:** this is an interrupted hardlink restoration; recovery removes only the redundant hidden link.

Do not manually delete `.um-*`, `.universal-modder-*`, manifest, marker, or journal files until they have been copied for inspection and their ownership is understood. If `recover` still exits nonzero, retain the complete state and obtain review rather than forcing removal.
