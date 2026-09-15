"""Validate the packaged Kai Custom Shape library in the active Blender version."""

import bpy


shape = bpy.data.objects.get("cs_switch")
assert shape is not None, "cs_switch object is missing"
assert shape.type == "MESH", f"cs_switch type is {shape.type}"
assert len(shape.data.vertices) == 8
assert shape.hide_select
assert shape.hide_render
print(
    "KAI_CS_LIBRARY_OK",
    f"blender={bpy.app.version_string}",
    f"objects={len(bpy.data.objects)}",
    f"dimensions={tuple(round(value, 6) for value in shape.dimensions)}",
)
