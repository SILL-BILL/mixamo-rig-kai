"""Blender background regression test for Kai Facial v0.1 Phase 1.2."""

import sys
import importlib.util
import json
import tempfile
import uuid
from math import degrees, radians
from pathlib import Path

import bpy
from mathutils import Vector


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


def assert_true(value, message):
    if not value:
        raise AssertionError(message)


def create_mesh(name, shape_names):
    mesh_data = bpy.data.meshes.new(name)
    mesh = bpy.data.objects.new(name, mesh_data)
    bpy.context.collection.objects.link(mesh)
    mesh.shape_key_add(name="Basis")
    for shape_name in shape_names:
        mesh.shape_key_add(name=shape_name)
    return mesh


def create_fixture():
    arm_data = bpy.data.armatures.new("KaiFacialTest")
    rig = bpy.data.objects.new("KaiFacialTest", arm_data)
    bpy.context.collection.objects.link(rig)
    bpy.context.view_layer.objects.active = rig
    rig.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")

    def bone(name, head, tail, parent=None):
        item = arm_data.edit_bones.new(name)
        item.head = head
        item.tail = tail
        if parent:
            item.parent = arm_data.edit_bones[parent]
        return item

    bone("Head", (0, 0, 1.6), (0, 0, 1.9))
    bone("Ctrl_Head", (0, 0, 1.6), (0, 0, 1.9))
    bpy.ops.object.mode_set(mode="OBJECT")
    arm_data["kai_head_name"] = "Head"

    face = create_mesh("KaiFaceMesh", kai_facial.DEFAULT_FACE_SHAPE_KEY_MAPPING.values())
    eyebrow = create_mesh("KaiEyebrowMesh", ("Brow_Up_L", "MouthLeft"))
    eyelash = create_mesh("KaiEyelashMesh", ())
    return rig, face, eyebrow, eyelash


def check_face(rig, mesh, eyebrow, eyelash):
    meshes = [mesh, eyebrow, eyelash]
    ui_channels = {
        channel
        for _category, _expand_property, channels in kai_facial.FACE_MAPPING_CATEGORIES
        for channel, _label in channels
    }
    assert_true(ui_channels == set(kai_facial.DEFAULT_FACE_SHAPE_KEY_MAPPING), "Mapping UI channel coverage")
    kai_facial._set_active_object(rig)
    for target in meshes:
        bpy.context.scene.kai_face_mesh_candidate = target
        assert_true(bpy.ops.kai.add_face_mesh() == {"FINISHED"}, f"Face Mesh add: {target.name}")
    assert_true(kai_facial._registered_face_meshes(bpy.context.scene) == meshes, "Face Mesh UI list")
    assert_true(bpy.ops.kai.generate_face_module() == {"FINISHED"}, "Face UI generation")
    controllers = len(kai_facial.FACE_CONTROLLERS)
    drivers = sum(
        len(target.data.shape_keys.animation_data.drivers)
        if target.data.shape_keys.animation_data else 0
        for target in meshes
    )
    missing, unassigned = kai_facial._face_mapping_counts(rig, meshes)
    assert_true(controllers == 15, f"controller count: {controllers}")
    assert_true(drivers == 42 and missing == 0, f"driver/missing result: {drivers}/{missing}")
    assert_true(unassigned == 78, f"unassigned channel result: {unassigned}")
    assert_true(kai_facial.face_module_state(rig) == "GENERATED", "Face generated state")
    rig.data["kai_face_module"] = "broken"
    assert_true(kai_facial.face_module_state(rig) == "PARTIAL", "Face partial state")
    rig.data["kai_face_module"] = kai_facial.FACE_MODULE_ID
    assert_true(len(mesh.data.shape_keys.animation_data.drivers) == 40, "Face driver count")
    assert_true(len(eyebrow.data.shape_keys.animation_data.drivers) == 2, "multi-mesh driver count")
    assert_true(eyelash.data.shape_keys.animation_data is None, "missing Shape Keys were not skipped")
    mapping_payload = kai_facial.get_face_mesh_mapping(rig)
    assert_true(mapping_payload["schema_version"] == 2, "Face mapping schema version")
    assert_true(len(mapping_payload["targets"]) == 3, "Face mesh mapping target count")
    mappings = {target["object"]: target["channels"] for target in mapping_payload["targets"]}
    assert_true(mappings[mesh.name]["eye_angry_l"] == "Eyelid_Angry_L", "full mapping auto detect")
    assert_true(mappings[eyebrow.name]["brow_up_l"] == "Brow_Up_L", "partial mapping auto detect")
    assert_true(mappings[eyebrow.name]["eye_angry_l"] == "", "missing mapping is None")
    assert_true(not any(mappings[eyelash.name].values()), "Basis-only mesh mapping")

    enum_operator = type("MappingEnumProbe", (), {"object_name": mesh.name})()
    enum_ids = {item[0] for item in kai_facial._face_shape_key_enum_items(enum_operator, bpy.context)}
    assert_true("Basis" not in enum_ids, "Basis mapping candidate")
    assert_true(kai_facial.FACE_MAPPING_NONE in enum_ids, "None mapping candidate")

    mesh.shape_key_add(name="Angry_Eye_Left")
    assert_true(
        bpy.ops.kai.set_face_mapping(
            object_name=mesh.name,
            channel="eye_angry_l",
            shape_key="Angry_Eye_Left",
        ) == {"FINISHED"},
        "Mapping UI custom Shape Key selection",
    )
    kai_facial.set_face_channel_mapping(rig, mesh, "eye_sad_l", "")
    kai_facial.set_face_channel_mapping(rig, mesh, "mouth_down", "")
    filled = kai_facial.auto_detect_face_mapping(rig, mesh)
    edited_mapping = kai_facial._mapping_for_mesh(rig, mesh, kai_facial.get_face_mapping(rig))
    assert_true(filled == 2, f"Auto Detect empty fill count: {filled}")
    assert_true(edited_mapping["eye_angry_l"] == "Angry_Eye_Left", "Auto Detect overwrote manual mapping")
    assert_true(edited_mapping["eye_sad_l"] == "Eyelid_Sad_L", "Auto Detect did not fill empty mapping")
    assert_true(edited_mapping["mouth_down"] == "MouthDown", "Auto Detect known candidate")

    assert_true(
        bpy.ops.kai.set_face_mapping(
            object_name=mesh.name,
            channel="eye_sad_l",
            shape_key=kai_facial.FACE_MAPPING_NONE,
        ) == {"FINISHED"},
        "Mapping UI None selection",
    )
    _controllers, _drivers, missing = kai_facial.generate_face_module(rig, meshes)
    assert_true(missing == 0, f"None counted as Missing: {missing}")
    keys = mesh.data.shape_keys
    assert_true(keys.animation_data.drivers.find('key_blocks["Eyelid_Angry_L"].value') is None, "old Kai Driver after remap")
    assert_true(keys.animation_data.drivers.find('key_blocks["Angry_Eye_Left"].value') is not None, "custom-name mapping Driver")
    assert_true(keys.animation_data.drivers.find('key_blocks["Eyelid_Sad_L"].value') is None, "None mapping Driver")
    assert_true(rig.pose.bones.get("Face_EyeExp_L") is not None, "None mapping removed Controller")

    kai_facial.set_face_channel_mapping(rig, mesh, "eye_angry_l", "Missing_Angry_Left")
    assert_true(
        kai_facial._face_mapping_status(rig, mesh, "Missing_Angry_Left") == "INVALID",
        "Invalid mapping status",
    )
    assert_true(bpy.ops.kai.generate_face_module() == {"FINISHED"}, "true Missing generation")
    missing, _unassigned = kai_facial._face_mapping_counts(rig, meshes)
    assert_true(missing == 1, f"true Missing mapping count: {missing}")
    assert_true(keys.animation_data.drivers.find('key_blocks["Angry_Eye_Left"].value') is None, "old Driver after invalid mapping")

    kai_facial.set_face_channel_mapping(rig, mesh, "eye_angry_l", "Eyelid_Angry_L")
    kai_facial.set_face_channel_mapping(rig, mesh, "eye_sad_l", "Eyelid_Sad_L")
    kai_facial.generate_face_module(rig, meshes)
    assert_true(keys.animation_data.drivers.find('key_blocks["Eyelid_Angry_L"].value') is not None, "restored mapping Driver")
    try:
        kai_facial.set_face_channel_mapping(rig, mesh, "eye_angry_l", "Basis")
    except ValueError:
        pass
    else:
        raise AssertionError("Basis mapping was accepted")

    no_shape = bpy.data.objects.new("KaiNoShapeMesh", bpy.data.meshes.new("KaiNoShapeMesh"))
    bpy.context.collection.objects.link(no_shape)
    bpy.context.scene.kai_face_mesh_candidate = no_shape
    assert_true(bpy.ops.kai.add_face_mesh() == {"FINISHED"}, "Shape Key-less Face Mesh add")
    no_shape_mapping = kai_facial._mapping_for_mesh(rig, no_shape, kai_facial.get_face_mapping(rig))
    assert_true(not any(no_shape_mapping.values()), "Shape Key-less mapping defaults")
    assert_true(bpy.ops.kai.generate_face_module() == {"FINISHED"}, "Shape Key-less Face generation")
    assert_true(bpy.ops.kai.remove_face_mesh() == {"FINISHED"}, "Shape Key-less Face Mesh remove")

    migration_data = bpy.data.armatures.new("KaiMappingMigration")
    migration_rig = bpy.data.objects.new("KaiMappingMigration", migration_data)
    bpy.context.collection.objects.link(migration_rig)
    migration_data[kai_facial.FACE_TARGETS_PROPERTY] = json.dumps({
        "schema_version": 1,
        "targets": [{"object": eyebrow.name, "channels": dict(kai_facial.DEFAULT_FACE_SHAPE_KEY_MAPPING)}],
    })
    migrated = kai_facial.ensure_face_mesh_mapping(migration_rig, eyebrow)
    migrated_payload = kai_facial.get_face_mesh_mapping(migration_rig)
    assert_true(migrated_payload["schema_version"] == 2, "v0.6.3 Mapping migration schema")
    assert_true(migrated["brow_up_l"] == "Brow_Up_L", "v0.6.3 existing connection migration")
    assert_true(migrated["eye_angry_l"] == "", "v0.6.3 missing default migration")
    bpy.data.objects.remove(migration_rig, do_unlink=True)

    none_data = bpy.data.armatures.new("KaiAllNoneMapping")
    none_rig = bpy.data.objects.new("KaiAllNoneMapping", none_data)
    bpy.context.collection.objects.link(none_rig)
    kai_facial._set_active_object(none_rig)
    bpy.ops.object.mode_set(mode="EDIT")
    none_head = none_data.edit_bones.new("Head")
    none_head.head = (0.0, 0.0, 0.0)
    none_head.tail = (0.0, 0.0, 1.0)
    bpy.ops.object.mode_set(mode="OBJECT")
    controllers, drivers, missing = kai_facial.generate_face_module(none_rig, [eyelash])
    assert_true((controllers, drivers, missing) == (15, 0, 0), "all-None Mapping generation")
    assert_true(kai_facial._face_mapping_counts(none_rig, [eyelash]) == (0, 40), "all-None status counts")
    assert_true(none_rig.pose.bones.get("Face_EyeExp_L") is not None, "all-None Controller generation")
    kai_facial.remove_face_module(none_rig)
    bpy.data.objects.remove(none_rig, do_unlink=True)
    kai_facial._set_active_object(rig)
    face_center, facial_base_scale = kai_facial._face_layout_basis(rig)
    generated_root = rig.pose.bones[kai_facial.FACE_ROOT]
    assert_true(
        (generated_root.bone.head_local - face_center).length < 0.0001,
        "Face root Head-relative initial position",
    )
    assert_true(
        all(abs(value - facial_base_scale) < 0.0001 for value in generated_root.scale),
        "single facial base scale",
    )
    for spec in kai_facial.FACE_CONTROLLERS:
        pbone = rig.pose.bones[spec["name"]]
        expected_position = kai_facial._face_layout_position(spec["pos"], face_center)
        assert_true(
            (pbone.bone.head_local - expected_position).length < 0.0001,
            f"reference UI position: {pbone.name}",
        )
        expected_scale = spec["display_scale"]
        if isinstance(expected_scale, (int, float)):
            expected_scale = (expected_scale, expected_scale, expected_scale)
        assert_true(
            all(abs(pbone.custom_shape_scale_xyz[index] - expected_scale[index]) < 0.0001 for index in range(3)),
            f"reference UI scale: {pbone.name}",
        )
        assert_true(
            kai_facial.FACE_COLLECTION in {collection.name for collection in pbone.bone.collections},
            f"controller collection: {pbone.name}",
        )
        assert_true(not pbone.bone.use_deform, f"deform: {pbone.name}")
        expected = tuple(index not in spec["axes"] for index in range(3))
        assert_true(tuple(pbone.lock_location) == expected, f"location locks: {pbone.name}")
        assert_true(all(pbone.lock_rotation), f"rotation locks: {pbone.name}")
        assert_true(all(pbone.lock_scale), f"scale locks: {pbone.name}")
        assert_true(pbone.constraints.get("KAI Normalized Location") is not None, f"limit: {pbone.name}")
        color = pbone.color.custom.normal
        region = kai_facial._face_ui_region(pbone.name)
        dominant = {"BROW": 1, "EYE": 0, "MOUTH": 2}[region]
        assert_true(color[dominant] == max(color), f"viewport color: {pbone.name}")
    left = rig.pose.bones["Face_MouthCorner_L"]
    right = rig.pose.bones["Face_MouthCorner_R"]
    assert_true(tuple(left.lock_location) == tuple(right.lock_location), "mouth corner lock asymmetry")
    assert_true(len(left.constraints) == len(right.constraints), "mouth corner limit asymmetry")
    for side in ("L", "R"):
        switch = rig.pose.bones[f"Face_EyeCloseToSmile_{side}"]
        assert_true(switch.custom_shape.name.startswith("cs_switch_Arrow"), f"CloseToSmile arrow: {side}")
        assert_true(abs(degrees(switch.custom_shape_rotation_euler.z) - 90.0) < 0.001, f"CloseToSmile arrow rotation: {side}")
    root = rig.pose.bones[kai_facial.FACE_ROOT]
    assert_true(
        kai_facial.FACE_ROOT_COLLECTION in {collection.name for collection in root.bone.collections},
        "Face root collection",
    )
    assert_true(root.parent is None and not root.bone.use_deform, "FaceCtrlRigRoot structure")
    assert_true(not any(root.lock_location), "FaceCtrlRigRoot location")
    assert_true(all(root.lock_rotation) and root.lock_rotation_w, "FaceCtrlRigRoot rotation")
    assert_true(not any(root.lock_scale), "FaceCtrlRigRoot scale")
    assert_true(abs(degrees(root.custom_shape_rotation_euler.x) - 90.0) < 0.001, "Face root viewport orientation")
    assert_true(tuple(round(value, 2) for value in root.custom_shape_scale_xyz) == (1.5, 1.0, 2.5), "Face root frame")
    assert_true(bpy.data.objects["cs_square"].hide_viewport, "custom shape source visibility")
    for part_name in kai_facial.FACE_PART_ROOT_SHAPES:
        part = rig.pose.bones[part_name]
        assert_true(not part.bone.use_deform, f"part root deform: {part_name}")
        assert_true(not any(part.lock_location), f"part root location: {part_name}")
        assert_true(all(part.lock_rotation), f"part root rotation: {part_name}")
        assert_true(not any(part.lock_scale), f"part root scale: {part_name}")
        assert_true(part.custom_shape is not None, f"part root shape: {part_name}")
        expected_scale = kai_facial.FACE_PART_ROOT_SHAPES[part_name][1]
        assert_true(
            all(abs(part.custom_shape_scale_xyz[index] - expected_scale[index]) < 0.0001 for index in range(3)),
            f"part root reference scale: {part_name}",
        )
    sad = mesh.data.shape_keys.animation_data.drivers.find('key_blocks["Eyelid_Sad_L"].value')
    variables = {variable.name: variable for variable in sad.driver.variables}
    assert_true(variables["kai_face_close"].targets[0].transform_type == "LOC_Y", "Eyelid Sad close axis")
    follow = rig.pose.bones[kai_facial.FACE_ROOT].constraints["KAI Face Head Follow"]
    follow_path = follow.path_from_id("influence")
    follow_driver = rig.animation_data.drivers.find(follow_path)
    target = follow_driver.driver.variables[0].targets[0]
    assert_true(target.data_path == '["kai_face_head_follow"]', "Head Follow source")
    bpy.context.view_layer.update()
    assert_true(follow_driver.is_valid, f"Head Follow driver invalid: {follow_driver.data_path}[{follow_driver.array_index}]")
    assert_true(all(fcurve.is_valid for fcurve in mesh.data.shape_keys.animation_data.drivers), "invalid Face driver")

    rig.pose.bones["Face_EyeClose_L"].location.y = -0.8
    rig.pose.bones["Face_EyeCloseToSmile_L"].location.x = 0.25
    rig.pose.bones["Face_EyeClose_R"].location.y = -0.8
    rig.pose.bones["Face_EyeCloseToSmile_R"].location.x = -0.25
    rig.pose.bones["Face_EyeExp_L"].location.x = -1.0
    bpy.context.view_layer.update()
    keys = mesh.data.shape_keys.key_blocks
    assert_true(abs(keys["Eyelid_Close_L"].value - 0.6) < 0.0001, "left Close blend")
    assert_true(abs(keys["Eyelid_Smile_L"].value - 0.2) < 0.0001, "left Smile blend")
    assert_true(abs(keys["Eyelid_Close_R"].value - 0.6) < 0.0001, "right Close blend")
    assert_true(abs(keys["Eyelid_Smile_R"].value - 0.2) < 0.0001, "right Smile blend")
    assert_true(abs(keys["Eyelid_Sad_L"].value - 0.2) < 0.0001, "Sad Close attenuation")

    rig.pose.bones["Face_EyeClose_L"].location.y = 0.0
    rig.pose.bones["Face_EyeCloseToSmile_L"].location.x = 0.0
    rig.pose.bones["Face_EyeClose_R"].location.y = 0.0
    rig.pose.bones["Face_EyeCloseToSmile_R"].location.x = 0.0
    rig.pose.bones["Face_EyeExp_L"].location.x = 0.0
    root.location = (0.5, -0.25, 0.75)
    root.rotation_mode = "XYZ"
    root.rotation_euler.z = 0.35
    root.scale = (1.75, 1.75, 1.75)
    rig.pose.bones["Face_BrowRoot_L"].location.x = 0.2
    rig.pose.bones["Face_BrowRoot_L"].scale = (1.2, 1.2, 1.2)
    rig.pose.bones["Face_EyeRoot_L"].location.z = -0.15
    rig.pose.bones["Face_EyeRoot_L"].scale = (0.8, 0.8, 0.8)
    rig.pose.bones["Face_MouthRoot"].location.z = -0.25
    rig.pose.bones["Face_MouthRoot"].scale = (1.1, 1.1, 1.1)
    rig.pose.bones["Face_BrowUpDown_L"].location.y = 0.4
    rig.pose.bones["Face_EyeExp_L"].location.y = 0.3
    rig.pose.bones["Face_MouthPosition"].location.x = 0.5
    bpy.context.view_layer.update()
    assert_true(abs(keys["MouthLeft"].value - 0.5) < 0.0001, "Root transform changed local driver")
    assert_true(abs(keys["Brow_Up_L"].value - 0.4) < 0.0001, "BrowRoot changed local driver")
    assert_true(abs(keys["Eyelid_Surprise_L"].value - 0.3) < 0.0001, "EyeRoot changed local driver")
    eyebrow_keys = eyebrow.data.shape_keys.key_blocks
    assert_true(abs(eyebrow_keys["MouthLeft"].value - 0.5) < 0.0001, "multi-mesh channel value")

    rig.pose.bones["Face_EyeClose_L"].location.y = 0.0
    rig.pose.bones["Face_EyeCloseToSmile_L"].location.x = 0.0
    rig.pose.bones["Face_EyeClose_R"].location.y = 0.0
    rig.pose.bones["Face_EyeCloseToSmile_R"].location.x = 0.0
    rig.pose.bones["Face_EyeExp_L"].location.x = 0.0
    rig.pose.bones["Face_EyeExp_L"].location.y = 0.0
    rig.pose.bones["Face_BrowUpDown_L"].location.y = 0.0
    rig.pose.bones["Face_MouthPosition"].location.x = 0.0
    saved_root_location = root.location.copy()
    saved_root_rotation = root.rotation_euler.copy()
    saved_root_scale = root.scale.copy()
    saved_part_transforms = {
        name: (rig.pose.bones[name].location.copy(), rig.pose.bones[name].scale.copy())
        for name in kai_facial.FACE_PART_ROOT_SHAPES
    }
    face_bone_names = [item[0] for item in kai_facial.FACE_ANCHORS]
    face_bone_names += [spec["name"] for spec in kai_facial.FACE_CONTROLLERS]
    saved_rest_positions = {
        name: (rig.data.bones[name].head_local.copy(), rig.data.bones[name].tail_local.copy())
        for name in face_bone_names
    }
    kai_facial.generate_face_module(rig, meshes)
    assert_true(len(mesh.data.shape_keys.animation_data.drivers) == 40, "Face idempotence")
    rebuilt_root = rig.pose.bones[kai_facial.FACE_ROOT]
    assert_true((rebuilt_root.location - saved_root_location).length < 0.0001, "Face root location rebuild")
    assert_true(
        all(abs(rebuilt_root.rotation_euler[index] - saved_root_rotation[index]) < 0.0001 for index in range(3)),
        "Face root rotation rebuild",
    )
    assert_true((rebuilt_root.scale - saved_root_scale).length < 0.0001, "Face root scale rebuild")
    for name, (location, scale) in saved_part_transforms.items():
        rebuilt_part = rig.pose.bones[name]
        assert_true((rebuilt_part.location - location).length < 0.0001, f"part root location rebuild: {name}")
        assert_true((rebuilt_part.scale - scale).length < 0.0001, f"part root scale rebuild: {name}")
    for name, (head, tail) in saved_rest_positions.items():
        rebuilt_bone = rig.data.bones[name]
        assert_true((rebuilt_bone.head_local - head).length < 0.0001, f"Face rest head rebuild: {name}")
        assert_true((rebuilt_bone.tail_local - tail).length < 0.0001, f"Face rest tail rebuild: {name}")

    conflict = create_mesh("KaiConflictMesh", ("Brow_Up_L",))
    conflict_path = 'key_blocks["Brow_Up_L"].value'
    conflict_curve = conflict.data.shape_keys.driver_add(conflict_path)
    conflict_curve.driver.expression = "0.5"
    assert_true(
        kai_facial._face_mapping_status(rig, conflict, "Brow_Up_L") == "CONFLICT",
        "non-Kai Driver Conflict UI status",
    )
    try:
        kai_facial.generate_face_module(rig, [*meshes, conflict])
    except RuntimeError as exc:
        assert_true("KaiConflictMesh.Brow_Up_L" in str(exc), "Conflict detail")
    else:
        raise AssertionError("non-Kai Driver conflict was overwritten")
    assert_true(conflict.data.shape_keys.animation_data.drivers.find(conflict_path) is not None, "Conflict driver removed")


def check_eye(rig):
    kai_facial._set_active_object(rig)
    bpy.ops.object.mode_set(mode="OBJECT")
    rig.data.bones.active = rig.data.bones["Ctrl_Head"]
    assert_true(not hasattr(bpy.types.Scene, "kai_eye_adapter"), "Eye adapter UI property remains")
    assert_true(not hasattr(bpy.types.Scene, "kai_eye_left_bone"), "Eye adapter left property remains")
    assert_true(not hasattr(bpy.types.Scene, "kai_eye_right_bone"), "Eye adapter right property remains")
    assert_true(rig.data.bones.get("LeftEye") is None, "Head-only fixture has LeftEye")
    assert_true(rig.data.bones.get("RightEye") is None, "Head-only fixture has RightEye")
    assert_true(rig.data.kai_eye_head_bone == "Head", "Reference Mapping Head default")
    unmapped = bpy.data.armatures.new("KaiEyeUnmappedQA")
    assert_true(unmapped.kai_eye_head_bone == "", "Unmapped Head default")
    bpy.data.armatures.remove(unmapped)
    try:
        kai_facial.generate_eye_module(rig, "")
    except RuntimeError as exc:
        assert_true("Set Head Bone" in str(exc), "Unset Head error")
    else:
        raise AssertionError("Unset Head Bone was accepted")
    try:
        kai_facial.generate_eye_module(rig, "MissingHead")
    except RuntimeError as exc:
        assert_true("Head Bone not found: MissingHead" in str(exc), "Missing Head error")
    else:
        raise AssertionError("Missing Head Bone was accepted")
    result = bpy.ops.kai.generate_eye_module()
    assert_true(result == {"FINISHED"}, f"Object Mode Head-field Eye generation: {result}")
    assert_true(kai_facial.eye_module_state(rig) == "GENERATED", "Eye generated state")
    rig.data["kai_eye_module"] = "broken"
    assert_true(kai_facial.eye_module_state(rig) == "PARTIAL", "Eye partial state")
    rig.data["kai_eye_module"] = kai_facial.EYE_MODULE_ID
    for name in (kai_facial.EYE_TARGET_ROOT, *kai_facial.EYE_TARGETS.values(), kai_facial.EYE_CENTER):
        assert_true(not rig.data.bones[name].use_deform, f"Eye deform: {name}")
    assert_true(rig.data.bones[kai_facial.EYE_TARGET_ROOT].parent.name == "Head", "Eye root parent")
    assert_true(rig.pose.bones[kai_facial.EYE_TARGET_ROOT].custom_shape.name.startswith("cs_square"), "Eye frame shape")
    assert_true(
        abs(degrees(rig.pose.bones[kai_facial.EYE_TARGET_ROOT].custom_shape_rotation_euler.x) - 90.0) < 0.001,
        "Eye frame viewport orientation",
    )
    head_length = rig.data.bones["Head"].length
    root = rig.pose.bones[kai_facial.EYE_TARGET_ROOT]
    assert_true(
        all(
            abs(root.custom_shape_scale_xyz[index] - expected) < 0.0001
            for index, expected in enumerate((head_length * 0.35, head_length * 0.12, head_length * 0.24))
        ),
        "Eye frame reference scale",
    )
    assert_true(root.color.palette == "CUSTOM", "Eye frame custom color")
    for state, expected in kai_facial.EYE_UI_COLOR.items():
        actual = getattr(root.color.custom, state)
        assert_true(all(abs(actual[index] - expected[index]) < 0.0001 for index in range(3)), f"Eye frame {state} color")
    center = rig.data.bones[kai_facial.EYE_CENTER]
    left_output = rig.data.bones[kai_facial.EYE_OUTPUTS["L"]]
    right_output = rig.data.bones[kai_facial.EYE_OUTPUTS["R"]]
    expected_center = (left_output.head_local + right_output.head_local) * 0.5
    assert_true((center.head_local - expected_center).length < 0.0001, "EyeCenterPos midpoint")
    assert_true(center.parent.name == "Head", "EyeCenterPos parent")
    assert_true(center.hide_select, "EyeCenterPos selection")
    center_track = rig.pose.bones[kai_facial.EYE_TARGET_ROOT].constraints.get("KAI Eye Center Damped Track")
    assert_true(center_track is not None and center_track.type == "DAMPED_TRACK", "Eye root Damped Track")
    assert_true(center_track.target == rig and center_track.subtarget == kai_facial.EYE_CENTER, "Eye center target")
    assert_true(center_track.track_axis == "TRACK_NEGATIVE_Z", "Eye center track axis")
    left_target = rig.pose.bones[kai_facial.EYE_TARGETS["L"]]
    right_target = rig.pose.bones[kai_facial.EYE_TARGETS["R"]]
    left_before = left_target.head.copy()
    right_before = right_target.head.copy()
    rig.pose.bones[kai_facial.EYE_TARGET_ROOT].location.x = 0.2
    bpy.context.view_layer.update()
    left_group_delta = left_target.head - left_before
    right_group_delta = right_target.head - right_before
    assert_true(left_group_delta.length > 0.1, "Eye root group motion")
    assert_true(right_group_delta.length > 0.1, "Eye root right group motion")
    assert_true(
        abs((left_target.head - right_target.head).length - (left_before - right_before).length) < 0.0001,
        "Eye root rigid group motion",
    )
    right_grouped = right_target.head.copy()
    left_target.location.x = 0.3
    bpy.context.view_layer.update()
    assert_true((left_target.head - left_before).x > 0.45, "Eye left individual motion")
    assert_true((right_target.head - right_grouped).length < 0.0001, "Eye right moved with left")
    for side in ("L", "R"):
        target = rig.pose.bones[kai_facial.EYE_TARGETS[side]]
        assert_true(tuple(target.lock_location) == (False, False, True), f"Eye target locks: {side}")
        assert_true(all(target.lock_rotation) and all(target.lock_scale), f"Eye transform locks: {side}")
        assert_true(target.custom_shape.name.startswith("cs_circle_025"), f"Eye target circle: {side}")
        assert_true(
            all(abs(value - head_length * 0.15) < 0.0001 for value in target.custom_shape_scale_xyz),
            f"Eye target reference scale: {side}",
        )
        assert_true(target.color.palette == "CUSTOM", f"Eye target custom color: {side}")
        for state, expected in kai_facial.EYE_UI_COLOR.items():
            actual = getattr(target.color.custom, state)
            assert_true(
                all(abs(actual[index] - expected[index]) < 0.0001 for index in range(3)),
                f"Eye target {state} color: {side}",
            )
        output = rig.pose.bones[kai_facial.EYE_OUTPUTS[side]]
        aim = output.constraints.get("KAI Eye Aim")
        assert_true(aim is not None and aim.type == "IK" and aim.chain_count == 1, f"Eye IK: {side}")
        for axis in "xyz":
            assert_true(getattr(output, f"use_ik_limit_{axis}"), f"Eye IK limit {axis}: {side}")
        assert_true(rig.data.bones[output.name].parent.name == "Head", f"Eye output parent: {side}")
    output = rig.pose.bones[kai_facial.EYE_OUTPUTS["L"]]
    output_data = rig.data.bones[output.name]
    rest_direction = (output_data.tail_local - output_data.head_local).normalized()
    left_target.location.x = 100.0
    bpy.context.view_layer.update()
    posed_direction = (output.tail - output.head).normalized()
    aim_angle = degrees(rest_direction.angle(posed_direction))
    assert_true(1.0 < aim_angle <= 36.0, f"Eye IK limit result: {aim_angle}")
    output.ik_max_z = radians(20.0)
    legacy_adapter = rig.pose.bones["Ctrl_Head"].constraints.new("COPY_ROTATION")
    legacy_adapter.name = "KAI Eye Direct Adapter"
    bpy.ops.object.mode_set(mode="EDIT")
    edited_eye = rig.data.edit_bones[kai_facial.EYE_OUTPUTS["L"]]
    edited_eye.head.x += 0.05
    edited_eye.tail.x += 0.05
    saved_eye_head = edited_eye.head.copy()
    rig.data.edit_bones.active = rig.data.edit_bones["Ctrl_Head"]
    result = bpy.ops.kai.generate_eye_module()
    assert_true(result == {"FINISHED"}, f"Edit Mode non-Head selection rebuild: {result}")
    rebuilt_eye = rig.data.bones[kai_facial.EYE_OUTPUTS["L"]]
    assert_true((rebuilt_eye.head_local - saved_eye_head).length < 0.0001, "Eye position rebuild")
    rebuilt_center = rig.data.bones[kai_facial.EYE_CENTER]
    rebuilt_midpoint = (
        rebuilt_eye.head_local
        + rig.data.bones[kai_facial.EYE_OUTPUTS["R"]].head_local
    ) * 0.5
    assert_true((rebuilt_center.head_local - rebuilt_midpoint).length < 0.0001, "EyeCenterPos rebuild midpoint")
    assert_true(abs(rig.pose.bones[rebuilt_eye.name].ik_max_z - radians(20.0)) < 0.0001, "Eye IK limit rebuild")
    assert_true(rig.pose.bones["Ctrl_Head"].constraints.get("KAI Eye Direct Adapter") is None, "Legacy adapter remains")


def check_mapping_persistence(rig, mesh, eyebrow, eyelash):
    kai_facial.set_face_channel_mapping(rig, mesh, "eye_angry_l", "")
    kai_facial.set_face_channel_mapping(rig, mesh, "mouth_left", "MouthRight")
    rig_name = rig.name
    mesh_name = mesh.name
    eyebrow_name = eyebrow.name
    eyelash_name = eyelash.name
    expected_meshes = [mesh.name, eyebrow.name, eyelash.name]
    filepath = Path(tempfile.gettempdir()) / f"kai_facial_mapping_{uuid.uuid4().hex}.blend"
    try:
        bpy.ops.wm.save_as_mainfile(filepath=str(filepath), check_existing=False)
        kai_facial.set_face_channel_mapping(rig, mesh, "eye_angry_l", "Eyelid_Angry_L")
        kai_facial.set_face_channel_mapping(rig, mesh, "mouth_left", "MouthLeft")
        bpy.context.scene.kai_face_meshes.clear()
        bpy.ops.wm.open_mainfile(filepath=str(filepath))

        rig = bpy.data.objects[rig_name]
        mesh = bpy.data.objects[mesh_name]
        eyebrow = bpy.data.objects[eyebrow_name]
        eyelash = bpy.data.objects[eyelash_name]
        restored = kai_facial._mapping_for_mesh(rig, mesh, kai_facial.get_face_mapping(rig))
        restored_meshes = [item.object.name for item in bpy.context.scene.kai_face_meshes if item.object]
        assert_true(restored["eye_angry_l"] == "", "None mapping persistence")
        assert_true(restored["mouth_left"] == "MouthRight", "manual mapping persistence")
        assert_true(restored_meshes == expected_meshes, "Face Mesh list persistence")
        assert_true(kai_facial.get_face_mesh_mapping(rig)["schema_version"] == 2, "schema persistence")
        return rig, mesh, eyebrow, eyelash
    finally:
        if filepath.exists():
            filepath.unlink()


def check_independent_module_removal(rig, mesh, eyebrow, eyelash):
    meshes = [mesh, eyebrow, eyelash]
    kai_facial._set_active_object(rig)
    assert_true(bpy.ops.kai.generate_face_module() == {"FINISHED"}, "Face regenerate before remove cases")
    assert_true(kai_facial.face_module_state(rig) == "GENERATED", "Face state before remove")
    assert_true(kai_facial.eye_module_state(rig) == "GENERATED", "Eye state before remove")
    mapping_before = rig.data[kai_facial.FACE_TARGETS_PROPERTY]
    mesh_list_before = [item.object.name for item in bpy.context.scene.kai_face_meshes if item.object]
    face_bones_before = {
        bone.name for bone in rig.data.bones
        if bone.get("kai_module") == kai_facial.FACE_MODULE_ID
    }

    assert_true(bpy.ops.kai.remove_eye_module() == {"FINISHED"}, "Remove Eye operator")
    assert_true(kai_facial.eye_module_state(rig) == "NOT_GENERATED", "Eye state after remove")
    assert_true(kai_facial.face_module_state(rig) == "GENERATED", "Face affected by Eye remove")
    assert_true(face_bones_before <= set(rig.data.bones.keys()), "Face bones affected by Eye remove")
    assert_true(rig.data[kai_facial.FACE_TARGETS_PROPERTY] == mapping_before, "Mapping affected by Eye remove")

    assert_true(bpy.ops.kai.generate_eye_module() == {"FINISHED"}, "Regenerate Eye after remove")
    assert_true(kai_facial.eye_module_state(rig) == "GENERATED", "Eye state after regenerate")
    eye_bones_before = {
        name: rig.data.bones[name].head_local.copy()
        for name in (kai_facial.EYE_CENTER, kai_facial.EYE_TARGET_ROOT, *kai_facial.EYE_TARGETS.values(), *kai_facial.EYE_OUTPUTS.values())
    }

    assert_true(bpy.ops.kai.remove_face_module() == {"FINISHED"}, "Remove Face operator")
    assert_true(kai_facial.face_module_state(rig) == "NOT_GENERATED", "Face state after remove")
    assert_true(kai_facial.eye_module_state(rig) == "GENERATED", "Eye affected by Face remove")
    assert_true(rig.data[kai_facial.FACE_TARGETS_PROPERTY] == mapping_before, "Face Mapping removed")
    assert_true(
        [item.object.name for item in bpy.context.scene.kai_face_meshes if item.object] == mesh_list_before,
        "Face Mesh list removed",
    )
    for name, head in eye_bones_before.items():
        assert_true((rig.data.bones[name].head_local - head).length < 0.0001, f"Eye changed by Face remove: {name}")

    assert_true(bpy.ops.kai.generate_face_module() == {"FINISHED"}, "Generate Face after remove")
    assert_true(kai_facial.face_module_state(rig) == "GENERATED", "Face state after restore")
    assert_true(rig.data[kai_facial.FACE_TARGETS_PROPERTY] == mapping_before, "Mapping changed after Face restore")
    restored = kai_facial._mapping_for_mesh(rig, mesh, kai_facial.get_face_mapping(rig))
    assert_true(restored["eye_angry_l"] == "", "None changed through remove/regenerate")
    assert_true(restored["mouth_left"] == "MouthRight", "custom mapping changed through remove/regenerate")

    kai_facial.set_face_channel_mapping(rig, mesh, "eye_angry_l", "Eyelid_Angry_L")
    kai_facial.set_face_channel_mapping(rig, mesh, "mouth_left", "MouthLeft")
    assert_true(bpy.ops.kai.generate_face_module() == {"FINISHED"}, "Restore default mappings")


rig, mesh, eyebrow, eyelash = create_fixture()
assert_true(kai_facial.face_module_state(rig) == "NOT_GENERATED", "initial Face state")
assert_true(kai_facial.eye_module_state(rig) == "NOT_GENERATED", "initial Eye state")
check_face(rig, mesh, eyebrow, eyelash)
check_eye(rig)
rig, mesh, eyebrow, eyelash = check_mapping_persistence(rig, mesh, eyebrow, eyelash)
check_independent_module_removal(rig, mesh, eyebrow, eyelash)
bones, drivers = kai_facial.remove_all_modules(rig)
assert_true(drivers == 43, f"removed drivers: {drivers}")
assert_true(not any(bone.get("kai_module") for bone in rig.data.bones), "module bones remain")
assert_true(not rig.animation_data or len(rig.animation_data.drivers) == 0, "rig drivers remain")
package.unregister()
bpy.context.preferences.addons.remove(addon_entry)
print(f"KAI_FACIAL_TEST_OK bones={bones} drivers={drivers}")
