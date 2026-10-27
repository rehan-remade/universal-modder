"""Blender: render frames of a vm_build.py .blend from the viewmodel camera (Blitz origin, looking +z).
Run: blender -b FILE.blend --python scripts/roblox/vm_render.py -- OUT_DIR HFOV_DEG frame [frame ...]"""
import math, os, sys
import bpy
argv = sys.argv[sys.argv.index("--") + 1:]
out, hfov, frames = argv[0], float(argv[1]), [int(f) for f in argv[2:]]
sc = bpy.context.scene
cam = bpy.data.objects.new("vmcam", bpy.data.cameras.new("vmcam"))
sc.collection.objects.link(cam)
cam.rotation_euler = (math.radians(90), 0, 0)  # Blender camera looks -Z; this makes it look +Y (= Blitz +z)
cam.data.sensor_fit = "HORIZONTAL"
cam.data.angle = math.radians(hfov)
cam.data.clip_start = 0.001
sc.camera = cam
try:
    sc.render.engine = "BLENDER_WORKBENCH"
except TypeError as e:
    print(e)
sc.display.shading.color_type = "TEXTURE"
sc.display.shading.light = "STUDIO"
sc.render.resolution_x, sc.render.resolution_y = 640, 360
for f in frames:
    sc.frame_set(f)
    sc.render.filepath = os.path.join(out, "f%03d.png" % f)
    bpy.ops.render.render(write_still=True)
