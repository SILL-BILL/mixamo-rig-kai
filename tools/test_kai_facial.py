"""Blender background smoke test for Kai Facial v0.1 Phase 1.1."""

import sys
import importlib.util
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
    missing = len(meshes) * len(kai_facial.DEFAULT_FACE_SHAPE_KEY_MAPPING) - drivers
    assert_true(controllers == 15, f"controller count: {controllers}")
    assert_true(drivers == 42 and missing == 78, f"driver result: {drivers}/{missing}")
    assert_true(len(mesh.data.shape_keys.animation_data.drivers) == 40, "Face driver count")
    assert_true(len(eyebrow.data.shape_keys.animation_data.drivers) == 2, "multi-mesh driver count")
    assert_true(eyelash.data.shape_keys.animation_data is None, "missing Shape Keys were not skipped")
    mapping_payload = kai_facial.get_face_mesh_mapping(rig)
    assert_true(len(mapping_payload["targets"]) == 3, "Face mesh mapping target count")
    for spec in kai_facial.FACE_CONTROLLERS:
        pbone = rig.pose.bones[spec["name"]]
        expected_position = Vector(spec["pos"])
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

    conflict = create_mesh("KaiConflictMesh", ("Brow_Up_L",))
    conflict_path = 'key_blocks["Brow_Up_L"].value'
    conflict_curve = conflict.data.shape_keys.driver_add(conflict_path)
    conflict_curve.driver.expression = "0.5"
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


rig, mesh, eyebrow, eyelash = create_fixture()
check_face(rig, mesh, eyebrow, eyelash)
check_eye(rig)
bones, drivers = kai_facial.remove_all_modules(rig)
assert_true(drivers == 43, f"removed drivers: {drivers}")
assert_true(not any(bone.get("kai_module") for bone in rig.data.bones), "module bones remain")
assert_true(not rig.animation_data or len(rig.animation_data.drivers) == 0, "rig drivers remain")
package.unregister()
bpy.context.preferences.addons.remove(addon_entry)
print(f"KAI_FACIAL_TEST_OK bones={bones} drivers={drivers}")
