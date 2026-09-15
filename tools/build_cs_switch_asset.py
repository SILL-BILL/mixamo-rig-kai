"""Bake the supplied cs_switch FBX into a copy of Kai's cs.blend library."""

import json
import os

import bpy
from mathutils import Vector


fbx_path = os.environ["KAI_CS_SWITCH_FBX"]
output_path = os.environ["KAI_CS_BLEND_OUTPUT"]

existing = bpy.data.objects.get("cs_switch")
if existing is not None:
    old_data = existing.data
    bpy.data.objects.remove(existing, do_unlink=True)
    if old_data is not None and old_data.users == 0:
        bpy.data.meshes.remove(old_data)

before = set(bpy.data.objects)
bpy.ops.import_scene.fbx(filepath=fbx_path, use_anim=False)
imported = [obj for obj in bpy.data.objects if obj not in before]
meshes = [obj for obj in imported if obj.type == "MESH"]
if len(meshes) != 1 or len(imported) != 1:
    raise RuntimeError(f"Expected one imported Mesh, got {[(obj.name, obj.type) for obj in imported]}")

obj = meshes[0]
obj.name = "cs_switch"
obj.data.name = "cs_switch"
for material in list(obj.data.materials):
    obj.data.materials.pop(index=0)
obj.animation_data_clear()
for modifier in list(obj.modifiers):
    obj.modifiers.remove(modifier)

bpy.context.view_layer.objects.active = obj
obj.select_set(True)
bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
obj.location = (0.0, 0.0, 0.0)
obj.rotation_euler = (0.0, 0.0, 0.0)
obj.scale = (1.0, 1.0, 1.0)

center = sum((vertex.co for vertex in obj.data.vertices), Vector()) / len(obj.data.vertices)
if center.length > 1.0e-6:
    for vertex in obj.data.vertices:
        vertex.co -= center

obj.hide_render = True
obj.hide_select = True
obj.display_type = "WIRE"

bpy.ops.wm.save_as_mainfile(filepath=output_path, check_existing=False)
report = {
    "object": obj.name,
    "mesh": obj.data.name,
    "dimensions": list(obj.dimensions),
    "location": list(obj.location),
    "rotation": list(obj.rotation_euler),
    "scale": list(obj.scale),
    "vertices": len(obj.data.vertices),
    "edges": len(obj.data.edges),
    "polygons": len(obj.data.polygons),
    "materials": len(obj.data.materials),
    "actions": len(bpy.data.actions),
    "armatures": len(bpy.data.armatures),
    "output": output_path,
}
print("KAI_CS_SWITCH_BUILD_OK", json.dumps(report, sort_keys=True))
