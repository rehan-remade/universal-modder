#!/usr/bin/env python3
"""Launch a Modrinth profile's Minecraft directly, without the launcher UI.

The Modrinth App is a GUI with no CLI, and the profile it manages is just a normal Minecraft
installation: a version JSON with a main class and a library list, plus an assets root. This builds
the java command from that JSON and runs it, so an agent can start the guest game from a script.

    tools/launch-mc.py                       # the BlockCraft Passthrough profile
    tools/launch-mc.py --print               # show the command instead of running it

The account is offline (a passthrough test never needs the real one); set MC_USERNAME to change it.
This is for development and tests on your own profile, like Loom's runClient. To play, start the profile
from your own launcher (the Modrinth App), signed in.
"""
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

APP = Path.home() / ".var/app/com.modrinth.ModrinthApp/data/ModrinthApp"
PROFILES = APP / "profiles"
META = APP / "meta"


def rules_allow(entry, features):
    """Minecraft's argument/library rules: no rules means allowed, else the first match wins.

    Feature semantics (launcher spec): a rule's `features` entry with value `null` matches when that
    feature is not enabled, and `true` matches when it is. Comparing straight against a dict that
    happens to hold `False` for such a feature makes `False != None` and silently drops the rule - which
    is how --width/--height went missing.
    """
    rules = entry.get("rules")
    if not rules:
        return True
    allowed = False
    for r in rules:
        os_rule = r.get("os", {})
        if "name" in os_rule and os_rule["name"] != "linux":
            continue
        if "arch" in os_rule and os_rule["arch"] not in ("x86_64", "amd64"):
            continue
        if "features" in r:
            if not all(features.get(k, None) == v for k, v in r["features"].items()):
                continue
        allowed = r["action"] == "allow"
    return allowed


def expand(value, ctx):
    out = value
    for k, v in ctx.items():
        out = out.replace("${" + k + "}", str(v))
    return out


def library_path(meta_root, lib):
    """Resolve one version-JSON library entry to a jar path, or None.

    Only some entries carry a pre-resolved 'downloads.artifact'. Modrinth's own launcher metadata
    lists the Fabric loader stack (fabric-loader, intermediary, sponge-mixin) and its ASM dependency
    as bare Maven coordinates - 'name' plus a 'url' - and expects the launcher to resolve them. Those
    are exactly the jars that make KnotClient exist, so skipping them produces
    "Could not find or load main class net.fabricmc.loader.impl.launch.knot.KnotClient".
    """
    artifact = lib.get("downloads", {}).get("artifact")
    if artifact:
        return meta_root / "libraries" / artifact["path"]

    name = lib.get("name")
    if not name:
        return None
    parts = name.split(":")
    if len(parts) < 3:
        return None
    group, art, version = parts[0], parts[1], parts[2]
    classifier = parts[3] if len(parts) > 3 else None
    file = f"{art}-{version}" + (f"-{classifier}" if classifier else "") + ".jar"
    path = meta_root / "libraries" / Path(*group.split(".")) / art / version / file
    return path if path.exists() else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", default="BlockCraft Passthrough")
    ap.add_argument("--username", default=os.environ.get("MC_USERNAME", "Passthrough"))
    ap.add_argument("--print", dest="print_only", action="store_true")
    ap.add_argument("--version", default="26.3-0.19.5")
    ap.add_argument("--width", default="1280")
    ap.add_argument("--height", default="720")
    ap.add_argument("--log", help="tee stdout/stderr here instead of inheriting the terminal")
    args = ap.parse_args()

    profile = PROFILES / args.profile
    if not profile.is_dir():
        sys.exit(f"no such profile: {profile}")

    version_json = META / "versions" / args.version / f"{args.version}.json"
    data = json.loads(version_json.read_text())

    # libraries: honour the platform rules and the explicit include_in_classpath flag, and resolve the
    # Maven-only entries too (see library_path).
    classpath = []
    for lib in data["libraries"]:
        if not rules_allow(lib, {}):
            continue
        if lib.get("include_in_classpath") is False:
            continue
        path = library_path(META, lib)
        if path is not None:
            classpath.append(str(path))
        else:
            print(f"warning: dropped library {lib.get('name')}", file=sys.stderr)

    # The game itself. It is not a library entry: it comes from the version JSON's 'downloads.client'
    # and the launcher stores it as <version>/<version>.jar. Without it Fabric's game provider fails
    # with "Minecraft game provider couldn't locate the game!".
    game_jar = version_json.with_suffix(".jar")
    if game_jar.exists():
        classpath.append(str(game_jar))
    else:
        sys.exit(f"missing game jar {game_jar}")


    # jvm + game arguments, expanded
    ctx = {
        "auth_player_name": args.username,
        "auth_uuid": "0" * 32,
        "auth_access_token": "0",
        "auth_session": "0",
        "version_name": args.version,
        "game_directory": str(profile),
        "assets_root": str(META / "assets"),
        "assets_index_name": data.get("assetIndex", {}).get("id", data.get("assets", "")),
        "natives_directory": str(META / "natives" / args.version),
        "launcher_name": "blockcraft",
        "launcher_version": "1.0",
        "classpath": ":".join(classpath),
        "user_type": "legacy",
        "resolution_width": args.width,
        "resolution_height": args.height,
    }

    # Minecraft gates some arguments behind launcher features. --width/--height only appear when
    # has_custom_resolution is on, and the rule check silently drops them otherwise (so the window
    # ignores the requested size and comes up at the profile's options.txt size). Only list features
    # that are actually enabled: a rule asking for a feature to be null is matched by leaving it out.
    features = {
        "has_custom_resolution": True,
        "is_demo_user": False,
    }

    jvm = []
    for a in data["arguments"].get("jvm", []):
        if isinstance(a, str):
            jvm.append(expand(a, ctx))
        elif rules_allow(a, features):
            jvm.extend(expand(v, ctx) for v in a["value"])

    game = []
    for a in data["arguments"].get("game", []):
        if isinstance(a, str):
            game.append(expand(a, ctx))
        elif rules_allow(a, features):
            game.extend(expand(v, ctx) for v in a["value"])

    java = META / "java_versions/zulu25.36.205-ca-jre25.0.4.1-linux_x64/bin/java"
    if not java.exists():
        java = "java"

    # We need to see the guest's log lines even when the launcher is on the far side of a pipe, so add
    # a console appender with timestamps; the mod's own INFO lines are what the link tracing reads.
    cmd = [str(java), "-Dlog4j2.formatMsgNoLookups=true", "--enable-native-access=ALL-UNNAMED",
           *jvm, "-cp", ctx["classpath"], data["mainClass"], *game]
    if args.print_only:
        print(" ".join(cmd))
        return
    os.chdir(profile)
    if args.log:
        with open(args.log, "wb") as fh:
            sys.exit(subprocess.call(cmd, stdout=fh, stderr=subprocess.STDOUT))
    sys.exit(subprocess.call(cmd))


if __name__ == "__main__":
    main()
