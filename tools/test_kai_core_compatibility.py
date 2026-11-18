"""Isolated Reference Rig, Rebuild and real retarget/bake compatibility tests."""

import copy
import json
import math
import os
import unittest
from pathlib import Path

import bpy
from mathutils import Quaternion, Vector


profile = Path(os.environ["KAI_QA_PROFILE"]).resolve()
for kind in ("CONFIG", "SCRIPTS", "EXTENSIONS"):
    assert Path(bpy.utils.user_resource(kind)).resolve().is_relative_to(profile)
fixture_path = Path(__file__).with_name("test_kai_facial.py")
fixture = {"__file__": str(fixture_path), "__name__": "core_fixture"}
exec(compile(fixture_path.read_text(encoding="utf-8").split(
    "rig, mesh, eyebrow, eyelash = create_fixture()"
)[0], str(fixture_path), "exec"), fixture)
from mixamo_rig_kai import mixamo_rig as core
from mixamo_rig_kai.lib import animation_compat


def template_variant(key="kai_humanoid_basic", spine_count=2, neck_count=1,
                     shoulders=True, prefix="", mixamo=False):
    template = copy.deepcopy(core.KAI_REFERENCE_TEMPLATES[key])
    bones = {item["name"]: item for item in template["bones"]}
    for names, start, end, parent, count, stem, child in (
        (["Spine", "Spine1"], bones["Hips"]["tail"], bones["Chest"]["head"],
         "Hips", spine_count, "Spine", "Chest"),
        (["Neck"], bones["Neck"]["head"], bones["Neck"]["tail"],
         "Chest", neck_count, "Neck", "Head"),
    ):
        for name in names:
            bones.pop(name)
        for index in range(count):
            name = stem if index == 0 else stem + str(index)
            bones[name] = {
                "name": name, "head": tuple(Vector(start).lerp(Vector(end), index / count)),
                "tail": tuple(Vector(start).lerp(Vector(end), (index + 1) / count)),
                "roll": 0.0, "parent": parent if index == 0 else (
                    stem if index == 1 else stem + str(index - 1)),
                "connected": False,
            }
        bones[child]["parent"] = parent if count == 0 else (
            stem if count == 1 else stem + str(count - 1))
    if not shoulders:
        for side in ("Left", "Right"):
            bones.pop(side + "Shoulder")
            bones[side + "Arm"]["parent"] = "Chest"
    rename = {name: prefix + ("Spine2" if mixamo and name == "Chest" else name)
              for name in bones}
    for item in bones.values():
        old_name = item["name"]
        item["name"] = rename[old_name]
        item["parent"] = rename.get(item["parent"])
    template["bones"] = list(bones.values())
    kwargs = {
        "bake_anim": False, "map_hip": rename["Hips"], "map_chest": rename["Chest"],
        "map_head": rename["Head"], "use_optional_spine": spine_count > 0,
        "use_optional_neck": neck_count > 0, "use_optional_shoulder": shoulders,
        "map_shoulder_left": rename.get("LeftShoulder", ""),
        "map_shoulder_right": rename.get("RightShoulder", ""),
    }
    for index in range(6):
        kwargs["map_spine" + str(index + 1)] = rename.get(
            "Spine" if index == 0 else "Spine" + str(index), "")
    for index in range(3):
        kwargs["map_neck" + str(index + 1)] = rename.get(
            "Neck" if index == 0 else "Neck" + str(index), "")
    return template, kwargs


def activate(rig):
    fixture["kai_facial"]._set_active_object(rig)


def action_snapshot(action):
    return [(curve.data_path, curve.array_index, [tuple(key.co) for key in curve.keyframe_points])
            for curve in animation_compat.get_action_fcurves(action)]


class CoreCompatibilityTests(unittest.TestCase):
    def tearDown(self):
        if bpy.context.object and bpy.context.object.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
        bpy.context.scene.mix_source_armature = None
        bpy.context.scene.kai_face_meshes.clear()
        for obj in list(bpy.data.objects):
            bpy.data.objects.remove(obj, do_unlink=True)
        for datablocks in (bpy.data.armatures, bpy.data.meshes, bpy.data.curves, bpy.data.actions):
            for data in list(datablocks):
                if data.users == 0:
                    datablocks.remove(data)

    def make(self, **options):
        template, kwargs = template_variant(**options)
        rig = core._kai_create_reference_skeleton_from_template(template)
        self.assertEqual(core._kai_validate_reference_skeleton(rig, template), [])
        source_names = {bone.name for bone in rig.data.bones}
        activate(rig)
        self.assertEqual(bpy.ops.mr.make_rig(**kwargs), {"FINISHED"})
        self.assertIn("mr_control_rig", rig.data)
        self.assertTrue(source_names.issubset(rig.data.bones.keys()))
        self.assertIsNotNone(rig.pose.bones.get("Ctrl_Head"))
        self.assertTrue(all(math.isfinite(value) for bone in rig.pose.bones
                            for row in bone.matrix for value in row))
        return rig, source_names

    def generate_rebuild(self, **options):
        rig, source_names = self.make(**options)
        activate(rig)
        bpy.ops.object.mode_set(mode="EDIT")
        user = rig.data.edit_bones.new("UserOwnedKeep")
        user.head, user.tail = (0, 0, 2), (0, 0, 2.1)
        bpy.ops.object.mode_set(mode="OBJECT")
        saved_mapping = core._kai_get_mapping_names_from_rig_data(rig)
        count = len(rig.data.bones)
        self.assertEqual(bpy.ops.mr.rebuild_rig(), {"FINISHED"})
        self.assertEqual(len(rig.data.bones), count)
        self.assertTrue(source_names.issubset(rig.data.bones.keys()))
        self.assertIn("UserOwnedKeep", rig.data.bones)
        self.assertEqual(core._kai_get_mapping_names_from_rig_data(rig), saved_mapping)
        self.assertIsNotNone(rig.pose.bones.get("Ctrl_Head"))
        return rig

    def test_basic_template_generate_rebuild(self):
        self.generate_rebuild()

    def test_fingers_template_generate_rebuild(self):
        self.generate_rebuild(key="kai_humanoid_fingers")

    def test_no_neck_generate_rebuild(self):
        self.generate_rebuild(neck_count=0)

    def test_minimal_spine_generate_rebuild(self):
        self.generate_rebuild(spine_count=0)

    def test_multiple_spines_and_necks_generate_rebuild(self):
        self.generate_rebuild(spine_count=6, neck_count=3)

    def test_optional_shoulders_absent_generate_rebuild(self):
        self.generate_rebuild(shoulders=False)

    def test_minimal_all_optional_absent_generate_rebuild(self):
        self.generate_rebuild(spine_count=0, neck_count=0, shoulders=False)

    def test_standard_prefixed_mixamo_generate_rebuild(self):
        self.generate_rebuild(prefix="mixamorig1:", mixamo=True)

    def test_rebuild_missing_required_stops_before_cleanup(self):
        rig, _ = self.make()
        original = {bone.name: bone.as_pointer() for bone in rig.data.bones}
        rig.data["kai_head_name"] = "MissingRequiredHead"
        with self.assertRaisesRegex(RuntimeError, "Missing required Mapping"):
            bpy.ops.mr.rebuild_rig()
        self.assertEqual({bone.name: bone.as_pointer() for bone in rig.data.bones}, original)

    def test_rebuild_missing_optional_continues(self):
        rig, _ = self.make(neck_count=0)
        rig.data["kai_neck_names"] = "MissingOptionalNeck"
        self.assertEqual(bpy.ops.mr.rebuild_rig(), {"FINISHED"})
        self.assertEqual(rig.data["kai_neck_names"], "")
        self.assertIsNotNone(rig.pose.bones.get("Ctrl_Head"))

    def test_rebuild_hierarchy_and_connected_changes_warn(self):
        rig, _ = self.make()
        activate(rig)
        bpy.ops.object.mode_set(mode="EDIT")
        neck = rig.data.edit_bones["Neck"]
        neck.parent = rig.data.edit_bones["Hips"]
        neck.use_connect = not neck.use_connect
        bpy.ops.object.mode_set(mode="OBJECT")
        reports = []
        class Reporter:
            def report(self, levels, message):
                reports.append((levels, message))
        core._kai_validate_mapping_for_rebuild(rig, Reporter())
        self.assertTrue(any("WARNING" in levels for levels, _ in reports), reports)
        self.assertEqual(bpy.ops.mr.rebuild_rig(), {"FINISHED"})
        self.assertIsNotNone(rig.pose.bones.get("Ctrl_Head"))

    def retarget(self, output, source_prefix="", target_prefix=""):
        target, _ = self.make(prefix=target_prefix)
        template, kwargs = template_variant(prefix=source_prefix)
        template["name"] = "RetargetSource"
        source = core._kai_create_reference_skeleton_from_template(template)
        head = source.pose.bones[kwargs["map_head"]]
        hip = source.pose.bones[kwargs["map_hip"]]
        head.rotation_mode = "XYZ"
        for frame, angle in ((1, 0.0), (3, 0.2), (5, 0.4)):
            head.rotation_euler.z = angle
            hip.location.x = angle * 0.1
            head.keyframe_insert(data_path="rotation_euler", frame=frame)
            hip.keyframe_insert(data_path="location", frame=frame)
        source_action = source.animation_data.action
        source_keys = action_snapshot(source_action)
        target.pose.bones["Ctrl_Head"].rotation_mode = "ZXY"
        original_modes = {bone.name: bone.rotation_mode for bone in target.pose.bones}
        bpy.context.scene.mix_source_armature = source
        bpy.context.scene.mr_retarget_rotation_output = output
        activate(target)
        self.assertEqual(bpy.ops.mr.import_anim_to_rig(), {"FINISHED"})
        self.assertIsNotNone(target.animation_data.action)
        curves = list(animation_compat.get_action_fcurves(target.animation_data.action))
        self.assertTrue(curves)
        self.assertEqual(source.animation_data.action, source_action)
        self.assertEqual(action_snapshot(source_action), source_keys)
        self.assertTrue(all(math.isfinite(value) for curve in curves
                            for key in curve.keyframe_points for value in key.co))
        head_curves = [curve for curve in curves if 'pose.bones["Ctrl_Head"]' in curve.data_path]
        self.assertTrue(head_curves, [curve.data_path for curve in curves])
        mode = target.pose.bones["Ctrl_Head"].rotation_mode
        if output == "QUATERNION":
            self.assertEqual(mode, "QUATERNION")
            rotations = sorted([curve for curve in head_curves if "rotation_quaternion" in curve.data_path],
                               key=lambda curve: curve.array_index)
            self.assertEqual(len(rotations), 4)
            previous = None
            for frame in range(1, 6):
                current = Quaternion([curve.evaluate(frame) for curve in rotations])
                if previous is not None:
                    self.assertGreaterEqual(previous.dot(current), 0.0)
                previous = current
        elif output == "EULER":
            self.assertIn(mode, {"XYZ", "XZY", "YXZ", "YZX", "ZXY", "ZYX"})
            self.assertTrue(any("rotation_euler" in curve.data_path for curve in head_curves))
        else:
            self.assertEqual(mode, "ZXY")
            self.assertTrue(all(target.pose.bones[name].rotation_mode == mode
                                for name, mode in original_modes.items()
                                if target.pose.bones[name].bone.get("mixamo_ctrl")))
        bpy.context.scene.frame_set(5)
        self.assertGreater(target.pose.bones["Ctrl_Head"].matrix_basis.to_quaternion().angle, 0.05)
        self.assertFalse(any(obj.get("mix_to_del") for obj in bpy.data.objects))
        self.assertFalse(any(constraint.name.startswith("mixamo") for bone in target.pose.bones
                             for constraint in bone.constraints))

    def test_retarget_quaternion(self):
        self.retarget("QUATERNION")

    def test_retarget_euler(self):
        self.retarget("EULER")

    def test_retarget_target_original(self):
        self.retarget("TARGET_ORIGINAL")

    def test_retarget_different_mixamo_prefixes(self):
        self.retarget("QUATERNION", "mixamorig1:", "mixamorig2:")

    def test_body_save_reopen(self):
        rig = self.generate_rebuild()
        name = rig.name
        names = set(rig.data.bones.keys())
        mapping = core._kai_get_mapping_names_from_rig_data(rig)
        path = profile / "core-save-reopen.blend"
        bpy.ops.wm.save_as_mainfile(filepath=str(path), check_existing=False)
        bpy.ops.wm.open_mainfile(filepath=str(path))
        restored = bpy.data.objects[name]
        self.assertEqual(set(restored.data.bones.keys()), names)
        self.assertEqual(core._kai_get_mapping_names_from_rig_data(restored), mapping)
        activate(restored)
        self.assertEqual(bpy.ops.mr.rebuild_rig(), {"FINISHED"})
        self.assertIn("UserOwnedKeep", restored.data.bones)


result = unittest.TextTestRunner(verbosity=2).run(
    unittest.defaultTestLoader.loadTestsFromTestCase(CoreCompatibilityTests))
print("KAI_CORE_COMPATIBILITY_RESULT", json.dumps({
    "blender": bpy.app.version_string, "tests": result.testsRun,
    "failures": len(result.failures), "errors": len(result.errors), "skipped": len(result.skipped),
}))
fixture["package"].unregister()
bpy.context.preferences.addons.remove(fixture["addon_entry"])
if not result.wasSuccessful():
    raise AssertionError("Core compatibility verification failed")
