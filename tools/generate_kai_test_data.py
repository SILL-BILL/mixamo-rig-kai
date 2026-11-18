"""Create immutable, synthetic Drive-pending fixtures outside the repository."""

import hashlib
import json
import os
from pathlib import Path

import bpy


REPO = Path(__file__).resolve().parents[1]
PROFILE = Path(os.environ["KAI_QA_PROFILE"]).resolve()
OUTPUT = Path(os.environ["KAI_TEST_DATA_OUTPUT"]).resolve()
assert not OUTPUT.is_relative_to(REPO), OUTPUT
assert not OUTPUT.is_relative_to(Path(r"D:/dev-blender-addon/mixamo-rig-kai")), OUTPUT
for kind in ("CONFIG", "SCRIPTS", "EXTENSIONS"):
    assert Path(bpy.utils.user_resource(kind)).resolve().is_relative_to(PROFILE)
OUTPUT.mkdir(parents=True, exist_ok=False)
bpy.context.preferences.use_preferences_save = False
# Reuse the existing template variants and registration, without running tests.
helper_path = REPO / "tools/test_kai_core_compatibility.py"
helper = {"__file__": str(helper_path), "__name__": "fixture_generation"}
exec(compile(helper_path.read_text(encoding="utf-8").split(
    "class CoreCompatibilityTests"
)[0], str(helper_path), "exec"), helper)
core = helper["core"]
facial = helper["fixture"]["kai_facial"]
entries = []


def clear_scene():
    if bpy.context.object and bpy.context.object.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")
    bpy.context.scene.kai_face_meshes.clear()
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)


def portable_data():
    # Localize linked product-shape data in this generated scene only.
    # Never modify the actual lib/cs.blend file.
    for item in list(bpy.data.user_map()):
        if item.library:
            item.make_local()
    remaining = [item.name for item in bpy.data.user_map() if item.library]
    assert not remaining, remaining
    for library in list(bpy.data.libraries):
        bpy.data.libraries.remove(library)
    bpy.ops.file.pack_all()
    assert not bpy.data.libraries


def save_fixture(stem, purpose):
    portable_data()
    path = OUTPUT / (stem + ".blend")
    assert not path.exists()
    bpy.context.scene["panda_factory_fixture"] = stem
    bpy.context.scene["panda_factory_fixture_purpose"] = purpose
    bpy.context.scene["panda_factory_drive_destination"] = "panda-factory/test-data/blender/"
    bpy.ops.wm.save_as_mainfile(filepath=str(path), check_existing=False, compress=True, copy=True)
    entries.append({
        "filename": path.name, "purpose": purpose, "local_path": str(path),
        "drive_destination": "panda-factory/test-data/blender/",
        "drive_status": "pending_upload_not_authorized",
        "generator": "tools/generate_kai_test_data.py", "blender": bpy.app.version_string,
        "bytes": path.stat().st_size, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    })


for stem, purpose, options in (
    ("kai-v0610-reference-basic", "Humanoid Basic: generation and Rebuild baseline", {}),
    ("kai-v0610-reference-fingers", "Humanoid Fingers: generation and Rebuild baseline", {"key": "kai_humanoid_fingers"}),
    ("kai-v0610-reference-minimal", "No Spine, no Neck, no Shoulder: optional-chain baseline",
     {"spine_count": 0, "neck_count": 0, "shoulders": False}),
    ("kai-v0610-reference-multichain", "Six Spine and three Neck bones: variable-chain baseline",
     {"spine_count": 6, "neck_count": 3}),
):
    clear_scene()
    template, kwargs = helper["template_variant"](**options)
    rig = core._kai_create_reference_skeleton_from_template(template)
    assert not core._kai_validate_reference_skeleton(rig, template)
    rig.data["panda_factory_generate_kwargs"] = json.dumps(kwargs)
    save_fixture(stem, purpose)

clear_scene()
template, kwargs = helper["template_variant"](prefix="mixamorig1:")
rig = core._kai_create_reference_skeleton_from_template(template)
rig.name = "PF_Kai_AnimatedSource"
head = rig.pose.bones[kwargs["map_head"]]
hips = rig.pose.bones[kwargs["map_hip"]]
head.rotation_mode = "XYZ"
for frame, angle in ((1, 0.0), (6, 0.2), (12, 0.4)):
    head.rotation_euler.z = angle
    hips.location.x = angle * 0.1
    head.keyframe_insert(data_path="rotation_euler", frame=frame)
    hips.keyframe_insert(data_path="location", frame=frame)
bpy.context.scene.frame_end = 12
bpy.context.scene.frame_set(1)
save_fixture("kai-v0610-retarget-source", "Prefixed source Action, frames 1-12: Retarget/Bake baseline")

clear_scene()
template, kwargs = helper["template_variant"]()
rig = core._kai_create_reference_skeleton_from_template(template)
assert bpy.ops.mr.make_rig(**kwargs) == {"FINISHED"}
rig.name = "PF_Kai_A"
data = bpy.data.meshes.new("PF_Kai_FaceMesh")
data.from_pydata([(-0.07, -0.04, 1.36), (0.07, -0.04, 1.36),
                  (0.07, -0.04, 1.46), (-0.07, -0.04, 1.46)], [], [(0, 1, 2, 3)])
mesh = bpy.data.objects.new("PF_Kai_FaceMesh", data)
bpy.context.collection.objects.link(mesh)
mesh.shape_key_add(name="Basis")
for index, name in enumerate(("Cheek Puff", "Tongue Out", "Acceptance Extra")):
    key = mesh.shape_key_add(name=name)
    key.data[index % 4].co.x += 0.03
    key.data[(index + 1) % 4].co.z += 0.02
group = mesh.vertex_groups.new(name="Head")
group.add(list(range(4)), 1.0, "REPLACE")
modifier = mesh.modifiers.new("Reference Armature", "ARMATURE")
modifier.object = rig
mesh.parent = rig
facial._set_active_object(rig)
bpy.context.scene.kai_face_mesh_candidate = mesh
assert bpy.ops.kai.add_face_mesh() == {"FINISHED"}
for name in ("Cheek Puff", "Tongue Out"):
    channel = facial.add_custom_face_channel(rig, name)
    facial.set_face_channel_mapping(rig, mesh, channel["id"], name)
facial.generate_face_module(rig, [mesh])
bone = rig.pose.bones[facial.custom_face_bone_name("custom_001")]
for frame, value in ((1, 0.65), (12, 0.25)):
    bone.location.x = value
    bone.keyframe_insert(data_path="location", frame=frame)
bpy.context.scene.frame_set(1)
facial._set_active_object(rig)
bpy.ops.object.duplicate(linked=False)
duplicate = bpy.context.object
duplicate.name = "PF_Kai_B"
duplicate.location.x = 0.65
facial._set_active_object(rig)
save_fixture("kai-v0610-facial-independent", "Facial P2: posed/keyed A with independently duplicated B sharing Text shapes")

# The linked case intentionally shares Armature data and must reject Face edits.
bpy.data.objects.remove(duplicate, do_unlink=True)
duplicate = rig.copy()
duplicate.name = "PF_Kai_Linked"
bpy.context.collection.objects.link(duplicate)
duplicate.location.x = 0.65
save_fixture("kai-v0610-facial-linked", "Facial P2: linked Armature data must reject destructive/definition edits")

(OUTPUT / "fixture-manifest.json").write_text(json.dumps({
    "extension_version": "0.6.10", "synthetic_only": True, "self_contained": True,
    "drive_upload_performed": False, "notion_registration_performed": False,
    "entries": entries,
}, indent=2), encoding="utf-8")
print("KAI_FIXTURES_CREATED", json.dumps({"files": len(entries), "output": str(OUTPUT)}))
