"""Inspect the supplied cs_switch FBX without saving user or project data."""

import json
import os

import bpy


filepath = os.environ["KAI_CS_SWITCH_FBX"]
before = set(bpy.data.objects)
bpy.ops.import_scene.fbx(filepath=filepath, use_anim=False)
imported = [obj for obj in bpy.data.objects if obj not in before]
report = []
for obj in imported:
    data = obj.data
    report.append(
        {
            "name": obj.name,
            "type": obj.type,
            "location": list(obj.location),
            "rotation_mode": obj.rotation_mode,
            "rotation_euler": list(obj.rotation_euler),
            "scale": list(obj.scale),
            "dimensions": list(obj.dimensions),
            "vertices": len(data.vertices) if obj.type == "MESH" else None,
            "edges": len(data.edges) if obj.type == "MESH" else None,
            "polygons": len(data.polygons) if obj.type == "MESH" else None,
            "materials": len(data.materials) if obj.type == "MESH" else None,
            "parent": obj.parent.name if obj.parent else None,
            "animation_data": obj.animation_data is not None,
            "modifiers": len(obj.modifiers),
        }
    )
print("KAI_CS_SWITCH_FBX_REPORT", json.dumps(report, ensure_ascii=False, sort_keys=True))
print("KAI_CS_SWITCH_ACTIONS", len(bpy.data.actions))
print("KAI_CS_SWITCH_ARMATURES", len(bpy.data.armatures))
