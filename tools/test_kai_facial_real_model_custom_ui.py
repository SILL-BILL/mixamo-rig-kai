"""Read-only in-memory QA of Phase 2 Custom UI on an already opened real model."""

import importlib.util
import sys
from pathlib import Path

import bpy


REPO = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "mixamo_rig_kai",
    REPO / "__init__.py",
    submodule_search_locations=[str(REPO)],
)
package = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = package
spec.loader.exec_module(package)
from mixamo_rig_kai import kai_facial  # noqa: E402

addon_entry = bpy.context.preferences.addons.new()
addon_entry.module = package.__name__
package.register()

rig = next(
    obj
    for obj in bpy.data.objects
    if obj.type == "ARMATURE" and obj.data.bones.get(kai_facial.FACE_ROOT) is not None
)
mesh = max(
    (
        obj
        for obj in bpy.data.objects
        if obj.type == "MESH" and getattr(obj.data, "shape_keys", None) is not None
    ),
    key=lambda obj: len(obj.data.shape_keys.key_blocks),
)
kai_facial._set_active_object(rig)
existing_ids = {item["id"] for item in kai_facial.get_custom_face_channels(rig)}

for index in range(1, 6):
    shape_name = f"KAI_QA_Custom_{index}"
    if mesh.data.shape_keys.key_blocks.get(shape_name) is None:
        mesh.shape_key_add(name=shape_name)
    channel = kai_facial.add_custom_face_channel(rig, shape_name)
    kai_facial.ensure_face_mesh_mapping(rig, mesh)
    kai_facial.set_face_channel_mapping(rig, mesh, channel["id"], shape_name)

kai_facial.generate_face_module(rig, [mesh])
custom_specs = kai_facial._custom_face_controller_specs(rig)
qa_specs = [item for item in custom_specs if item["channel_id"] not in existing_ids]
built_in_max_x = max(rig.data.bones[item["name"]].head_local.x for item in kai_facial.FACE_CONTROLLERS)
custom_min_x = min(rig.data.bones[item["name"]].head_local.x for item in custom_specs)
assert custom_min_x > built_in_max_x
assert len(qa_specs) == 5
for item in qa_specs:
    knob = rig.pose.bones[item["name"]]
    bar = rig.pose.bones[item["track_name"]]
    label = rig.pose.bones[item["label_name"]]
    assert knob.parent.name == kai_facial.FACE_CUSTOM_ROOT
    assert bar.parent.name == kai_facial.FACE_CUSTOM_ROOT
    assert label.parent.name == kai_facial.FACE_CUSTOM_ROOT
    assert label.custom_shape is not None and label.custom_shape.type == "FONT"
    assert knob.custom_shape is not None and knob.custom_shape.name.startswith("cs_switch")
    assert tuple(round(value, 6) for value in knob.custom_shape_scale_xyz) == (1.0, 1.0, 0.25)
    assert knob.color.palette == "CUSTOM"
    assert tuple(round(value, 6) for value in knob.color.custom.normal) == (1.0, 1.0, 0.0)
    assert tuple(round(value, 6) for value in knob.color.custom.select) == (1.0, 1.0, 0.0)
    assert tuple(round(value, 6) for value in knob.color.custom.active) == (0.0, 1.0, 1.0)
    assert tuple(round(value, 6) for value in bar.custom_shape_scale_xyz) == (0.45, 1.0, 0.01)
    assert tuple(round(value, 6) for value in label.custom_shape_scale_xyz) == (0.4, 0.4, 0.4)
    for display in (bar, label):
        assert display.color.palette == "CUSTOM"
        assert tuple(round(value, 6) for value in display.color.custom.normal) == (0.0, 1.0, 1.0)
        assert tuple(round(value, 6) for value in display.color.custom.select) == (0.0, 1.0, 1.0)
        assert tuple(round(value, 6) for value in display.color.custom.active) == (0.0, 1.0, 1.0)
    assert not knob.bone.hide_select
    assert bar.bone.hide_select
    assert label.bone.hide_select
    assert label.custom_shape.hide_select
    assert {collection.name for collection in knob.bone.collections} == {
        kai_facial.FACE_CUSTOM_COLLECTION
    }
    assert {collection.name for collection in bar.bone.collections} == {
        kai_facial.FACE_CUSTOM_UI_COLLECTION
    }
    assert {collection.name for collection in label.bone.collections} == {
        kai_facial.FACE_CUSTOM_UI_COLLECTION
    }

print(
    "KAI_REAL_MODEL_CUSTOM_UI_OK",
    f"file={bpy.data.filepath}",
    f"rig={rig.name}",
    f"mesh={mesh.name}",
    f"built_in_max_x={built_in_max_x:.6f}",
    f"custom_min_x={custom_min_x:.6f}",
    f"labels={len(qa_specs)}",
)
