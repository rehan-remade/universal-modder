"""Call of Duty weapon file inspector, editor, and generator.

    um weapon get raw/weapons/sp/colt
    um weapon get raw/weapons/sp/colt damage
    um weapon set raw/weapons/sp/colt damage=500 clipSize=16 -o mods/MyMod/weapons/sp/colt_modded
    um weapon clone raw/weapons/sp/colt mods/MyMod/weapons/sp/colt_upgraded --damage 1000 --clip 16
    um weapon diff raw/weapons/sp/colt raw/weapons/sp/colt_dirty_harry

Inspects, parses, and edits Call of Duty: World at War and CoD4 weapon files.
Handles the engine's backslash-delimited dictionary format (WEAPONFILE\\key\\value\\...),
preserving all 300+ properties including viewmodel animations, recoil kick, and
ballistic damage falloff curves.

set and clone write a new file (-o / the destination): point it at your mod's copy, never
at the Mod Tools' raw/ folder or the game's files. set --in-place edits the file itself.
Weapon files are Treyarch's and Infinity Ward's data: keep copies of raw/ files out of any
repo, and ship your changes as a diff or a build step that runs set/clone on the player's
own raw/ files.
"""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from um.common import die


def parse_weapon(path: str | Path) -> tuple[str, dict[str, str], list[str]]:
    """Parse a Call of Duty weapon file into (header, dict_of_properties, ordered_keys)."""
    p = Path(path)
    if not p.is_file():
        die(f"weapon file not found: {p}")

    text = p.read_text(encoding="latin-1").strip()  # byte-for-byte, whatever the encoding
    tokens = text.split("\\")
    header = tokens[0] if tokens else "WEAPONFILE"

    props = {}
    ordered_keys = []
    for i in range(1, len(tokens) - 1, 2):
        k = tokens[i]
        v = tokens[i + 1]
        props[k] = v
        ordered_keys.append(k)

    return header, props, ordered_keys


def write_weapon(path: str | Path, header: str, props: dict[str, str], ordered_keys: list[str]):
    """Serialize a weapon dictionary back to the engine's slash-delimited format."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)

    parts = [header]
    seen = set()
    for k in ordered_keys:
        if k in props:
            parts.append(k)
            parts.append(str(props[k]))
            seen.add(k)

    for k, v in props.items():
        if k not in seen:
            parts.append(k)
            parts.append(str(v))

    serialized = "\\".join(parts) + "\\"
    p.write_text(serialized, encoding="latin-1")


def get_weapon(path: str | Path, key: str | None = None):
    """Display weapon properties or a specific key."""
    header, props, _ = parse_weapon(path)
    p = Path(path)

    if key:
        if key in props:
            print(f"{key} = {props[key]}")
        else:
            die(f"key '{key}' not found in {p.name}")
        return

    print(f"Weapon: {p.name} ({len(props)} properties)")
    highlights = [
        "displayName",
        "weaponClass",
        "weaponType",
        "damage",
        "minDamage",
        "clipSize",
        "maxAmmo",
        "fireTime",
        "reloadTime",
        "moveSpeedScale",
        "projectileModel",
        "explosionRadius",
        "explosionInnerDamage",
    ]
    for h in highlights:
        if h in props and props[h]:
            print(f"  {h:22} = {props[h]}")


def set_weapon(path: str | Path, updates: list[str], out: str | Path | None = None, in_place: bool = False):
    """Set key=value properties in a weapon file."""
    if not out and not in_place:
        die("pass -o <file> (your mod's copy) or --in-place; set never overwrites its input by default")
    header, props, ordered_keys = parse_weapon(path)
    dest = Path(out) if out else Path(path)

    for u in updates:
        if "=" not in u:
            die(f"invalid property format: '{u}' (expected key=value)")
        k, v = u.split("=", 1)
        props[k.strip()] = v.strip()
        if k.strip() not in ordered_keys:
            ordered_keys.append(k.strip())

    write_weapon(dest, header, props, ordered_keys)
    print(f"Updated {len(updates)} properties -> {dest}")


def clone_weapon(
    src: str | Path,
    dst: str | Path,
    damage: int | None = None,
    clip: int | None = None,
    ammo: int | None = None,
    explosive: bool = False,
):
    """Clone an existing weapon with customizable adjustments."""
    header, props, ordered_keys = parse_weapon(src)
    dst_p = Path(dst)

    if damage is not None:
        props["damage"] = str(damage)
        props["minDamage"] = str(max(10, damage // 3))
    if clip is not None:
        props["clipSize"] = str(clip)
    if ammo is not None:
        props["maxAmmo"] = str(ammo)
        props["startAmmo"] = str(ammo)

    if explosive:
        props["weaponType"] = "projectile"
        props["weaponClass"] = "grenade"
        props["impactType"] = "rifle_grenade"
        props["projectileModel"] = "projectile_usa_m9a1_riflegrenade"
        props["projectileSpeed"] = "2400"
        props["explosionRadius"] = "220"
        props["explosionInnerDamage"] = str(damage or 250)
        props["explosionOuterDamage"] = "75"
        props["projImpactExplode"] = "1"
        props["projTrailEffect"] = "weapon/grenade/fx_trail_rifle_grenade"

    write_weapon(dst_p, header, props, ordered_keys)
    print(f"Cloned {Path(src).name} -> {dst_p} ({len(props)} properties)")


def diff_weapons(path1: str | Path, path2: str | Path):
    """Diff two weapon files."""
    _, p1, _ = parse_weapon(path1)
    _, p2, _ = parse_weapon(path2)
    p1_name = Path(path1).name
    p2_name = Path(path2).name

    all_keys = sorted(set(p1.keys()) | set(p2.keys()))
    diffs = []
    for k in all_keys:
        v1 = p1.get(k, "<absent>")
        v2 = p2.get(k, "<absent>")
        if v1 != v2:
            diffs.append((k, v1, v2))

    print(f"Comparing {p1_name} vs {p2_name} ({len(diffs)} differences):")
    for k, v1, v2 in diffs[:40]:
        print(f"  {k:24} | {v1:24} -> {v2:24}")
    if len(diffs) > 40:
        print(f"  ... and {len(diffs) - 40} more differences.")


def main(a):
    if a.cmd == "get":
        get_weapon(a.file, a.key)
    elif a.cmd == "set":
        set_weapon(a.file, a.updates, a.out, a.in_place)
    elif a.cmd == "clone":
        clone_weapon(a.src, a.dst, a.damage, a.clip, a.ammo, a.explosive)
    elif a.cmd == "diff":
        diff_weapons(a.file1, a.file2)


def register(sub):
    p = sub.add_parser(
        "weapon",
        help="inspect, edit, and clone Call of Duty weapon files",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    cs = p.add_subparsers(dest="cmd", metavar="<cmd>")

    q = cs.add_parser("get", help="view weapon stats or query a property")
    q.add_argument("file", help="path to weapon file")
    q.add_argument("key", nargs="?", help="optional specific property name")
    q.set_defaults(func=main)

    q = cs.add_parser("set", help="modify weapon properties and save to file")
    q.add_argument("file", help="path to weapon file")
    q.add_argument("updates", nargs="+", help="key=value pairs (e.g. damage=500 clipSize=30)")
    q.add_argument("-o", "--out", help="output file path (your mod's copy)")
    q.add_argument("--in-place", action="store_true", help="overwrite the input file instead")
    q.set_defaults(func=main)

    q = cs.add_parser("clone", help="clone a weapon with stats or explosive ammo presets")
    q.add_argument("src", help="source weapon file")
    q.add_argument("dst", help="destination weapon file")
    q.add_argument("--damage", type=int, help="override damage")
    q.add_argument("--clip", type=int, help="override clip size")
    q.add_argument("--ammo", type=int, help="override max reserve ammo")
    q.add_argument("--explosive", action="store_true", help="turn weapon into an explosive projectile launcher")
    q.set_defaults(func=main)

    q = cs.add_parser("diff", help="compare differences between two weapon files")
    q.add_argument("file1", help="first weapon file")
    q.add_argument("file2", help="second weapon file")
    q.set_defaults(func=main)
