"""Blender script: build an animated, skinned viewmodel from b3d_skin.py JSON and export FBX for Roblox.

Run:
  blender -b --factory-startup --python tools/cb2/vm_build.py -- IN.json OUT_DIR --scale 0.06
          --tex brush=path.png [--tex ...]

Space: Blitz3D is left-handed (x right, y up, z forward). Blender = (x, z, y) of Blitz, a reflection, so
every Blitz matrix M becomes P M P with P swapping y and z. FBX export (-Z forward, Y up) then gives
(x, y, -z) of Blitz, the same frame the OBJ pipeline (port_model.py) uploads in.
Rotations: Blitz3D applies the conjugate of the stored quaternion (checked: only then does the
`weaponfire` node land on the P90's muzzle, z = 17.03 against the mesh's 17.02).

Every node becomes a bone (so Roblox gets Bones for CameraBone, weaponfire, ...), each brush becomes its
own skinned mesh (Roblox MeshParts take one texture and at most 20k triangles), and one action per SEQS
range is made for previewing in Blender (the game samples the keys itself at runtime).
"""
import json
import os
import sys

import bpy
from mathutils import Matrix, Quaternion, Vector

argv = sys.argv[sys.argv.index("--") + 1:]
SRC, OUT = argv[0], argv[1]
SCALE = float(argv[argv.index("--scale") + 1]) if "--scale" in argv else 1.0
TEX = {}
for i, a in enumerate(argv):
    if a == "--tex":
        k, v = argv[i + 1].split("=", 1)
        TEX[k] = v
NAME = os.path.splitext(os.path.basename(SRC))[0]

P = Matrix(((1, 0, 0, 0), (0, 0, 1, 0), (0, 1, 0, 0), (0, 0, 0, 1)))


def blitz_local(pos, rot):
    w, x, y, z = rot
    m = Quaternion((w, -x, -y, -z)).to_matrix().to_4x4()
    m.translation = Vector(pos) * SCALE
    return P @ m @ P


data = json.load(open(SRC, encoding="utf-8"))
root = data["root"]

# Unique names: the b3d has two nodes called Scene_Root.
nodes, seen = [], {}


def collect(n, parent):
    name = n["name"]
    if name in seen:
        seen[name] += 1
        name = "%s_%d" % (name, seen[name])
    else:
        seen[name] = 0
    n["uname"] = name
    nodes.append((n, parent))
    for c in n["children"]:
        collect(c, n)


collect(root, None)
for n, parent in nodes:
    n["rest_local"] = blitz_local(n["pos"], n["rot"])
    n["rest_world"] = (parent["rest_world"] if parent else Matrix.Identity(4)) @ n["rest_local"]

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene

# Armature: the mesh node (root) is the object origin; every other node is a bone.
arm_data = bpy.data.armatures.new(NAME + "_rig")
arm = bpy.data.objects.new(NAME + "_rig", arm_data)
scene.collection.objects.link(arm)
bpy.context.view_layer.objects.active = arm
bpy.ops.object.mode_set(mode="EDIT")
for n, parent in nodes[1:]:
    eb = arm_data.edit_bones.new(n["uname"])
    eb.head = (0, 0, 0)
    eb.tail = (0, 0.3 * SCALE, 0)
    eb.matrix = n["rest_world"]
    if parent is not None and parent is not root:
        eb.parent = arm_data.edit_bones[parent["uname"]]
bpy.ops.object.mode_set(mode="OBJECT")

# Meshes, one per brush.
mesh = root["mesh"]
V = mesh["verts"]
weights = {}
for n, _ in nodes:
    for vid, w in n.get("bone", []):
        weights.setdefault(vid, []).append((n["uname"], w))

def material(bi):
    b = data["brus"][bi]
    mat = bpy.data.materials.new(b["name"] or "brush%d" % bi)
    mat.use_nodes = True
    bsdf = next(nd for nd in mat.node_tree.nodes if nd.type == "BSDF_PRINCIPLED")
    path = TEX.get(b["name"])
    if path:
        tex = mat.node_tree.nodes.new("ShaderNodeTexImage")
        tex.image = bpy.data.images.load(path)
        mat.node_tree.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    return mat

meshes = []
for surf in mesh["surfaces"]:
    bi = surf["brush"]
    used = sorted({i for t in surf["tris"] for i in t})
    remap = {old: new for new, old in enumerate(used)}
    verts = [tuple(P @ Vector([c * SCALE for c in V["pos"][i]])) for i in used]
    # Reflection flips handedness: reverse each triangle to keep faces pointing the stored way.
    faces = [(remap[t[0]], remap[t[2]], remap[t[1]]) for t in surf["tris"]]
    bname = data["brus"][bi]["name"] or "brush%d" % bi
    me = bpy.data.meshes.new(bname)
    me.from_pydata(verts, [], faces)
    uv = me.uv_layers.new(name="UVMap")
    for poly in me.polygons:
        for li in poly.loop_indices:
            u, v = V["uv"][used[me.loops[li].vertex_index]][:2]
            uv.data[li].uv = (u, 1.0 - v)
    if V["normal"]:
        nrm = [tuple(P @ Vector(V["normal"][used[me.loops[li].vertex_index]])) for li in range(len(me.loops))]
        me.normals_split_custom_set(nrm)
    me.materials.append(material(bi))
    ob = bpy.data.objects.new(bname, me)
    scene.collection.objects.link(ob)
    for old, new in remap.items():
        for bone, w in weights.get(old, []):
            vg = ob.vertex_groups.get(bone) or ob.vertex_groups.new(name=bone)
            vg.add([new], w, "REPLACE")
    ob.parent = arm
    mod = ob.modifiers.new("Armature", "ARMATURE")
    mod.object = arm
    meshes.append((bname, len(faces), len(used), len(ob.vertex_groups)))

# Preview actions from the keys (pose basis = rest_local^-1 @ keyed_local).
seqs = root.get("seqs", [])
keyed = {}
for n, _ in nodes[1:]:
    ks = {k["frame"]: k for k in n.get("keys", [])}
    keyed[n["uname"]] = (n, ks)
first = min(s["first"] for s in seqs) if seqs else 1
last = max(s["last"] for s in seqs) if seqs else 1
action = bpy.data.actions.new(NAME + "_all")
arm.animation_data_create().action = action
for f in range(first, last + 1):
    for name, (n, ks) in keyed.items():
        k = ks.get(f)
        if k is None:
            continue
        local = blitz_local(k.get("pos", n["pos"]), k.get("rot", n["rot"]))
        pb = arm.pose.bones[name]
        pb.matrix_basis = n["rest_local"].inverted() @ local
        pb.keyframe_insert("location", frame=f)
        pb.keyframe_insert("rotation_quaternion", frame=f)
for s in seqs:
    m = scene.timeline_markers.new(s["name"], frame=s["first"])
scene.frame_start, scene.frame_end = first, last
scene.render.fps = int(root.get("anim", {}).get("fps", 20))

os.makedirs(OUT, exist_ok=True)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, NAME + ".blend"))
# Roblox gets the bind pose only; animation is sampled from the JSON at runtime.
arm.animation_data.action = None
for pb in arm.pose.bones:
    pb.matrix_basis = Matrix.Identity(4)
bpy.ops.export_scene.fbx(filepath=os.path.join(OUT, NAME + ".fbx"), object_types={"ARMATURE", "MESH"},
                         axis_forward="-Z", axis_up="Y", apply_scale_options="FBX_SCALE_UNITS",
                         path_mode="COPY", embed_textures=True, add_leaf_bones=False, bake_anim=False,
                         mesh_smooth_type="OFF", use_armature_deform_only=False)
print("VMBUILD", json.dumps({"bones": len(nodes) - 1, "meshes": meshes, "frames": [first, last]}))
