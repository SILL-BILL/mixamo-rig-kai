"""Focused Facial rename/duplicate regression tests in an isolated Blender.

Run through tools/run_kai_facial_isolated.py, never in a normal user profile.
"""

import json
import os
import sys
import unittest
from pathlib import Path

import bpy


PROFILE = Path(os.environ["KAI_QA_PROFILE"]).resolve()
for resource in ("CONFIG", "SCRIPTS", "EXTENSIONS"):
    assert Path(bpy.utils.user_resource(resource)).resolve().is_relative_to(PROFILE)

# Reuse the existing fixture and package registration without running its suite.
fixture_path = Path(__file__).with_name("test_kai_facial.py")
fixture_source = fixture_path.read_text(encoding="utf-8").split(
    "rig, mesh, eyebrow, eyelash = create_fixture()"
)[0]
fixture = {"__file__": str(fixture_path), "__name__": "facial_safety_fixture"}
exec(compile(fixture_source, str(fixture_path), "exec"), fixture)
facial = fixture["kai_facial"]


def action_curves(rig):
    action = rig.animation_data.action
    if hasattr(action, "fcurves"):
        return list(action.fcurves)
    slot = rig.animation_data.action_slot
    return [
        curve
        for layer in action.layers
        for strip in layer.strips
        if strip.type == "KEYFRAME"
        for bag in [strip.channelbag(slot)]
        if bag is not None
        for curve in bag.fcurves
    ]


def animation_snapshot(rig):
    return [
        (
            curve.data_path,
            curve.array_index,
            [(tuple(key.co), key.interpolation) for key in curve.keyframe_points],
        )
        for curve in action_curves(rig)
    ]


class FacialSafetyTests(unittest.TestCase):
    def setUp(self):
        self.rig, self.mesh, _, _ = fixture["create_fixture"]()
        scene = bpy.context.scene
        scene.kai_face_meshes.clear()
        scene.kai_face_mesh_candidate = self.mesh
        bpy.ops.kai.add_face_mesh()
        self.channels = []
        for name in ("SafetyCheek", "SafetyTongue"):
            self.mesh.shape_key_add(name=name)
            channel = facial.add_custom_face_channel(self.rig, name)
            facial.set_face_channel_mapping(self.rig, self.mesh, channel["id"], name)
            self.channels.append(channel)
        facial.generate_face_module(self.rig, [self.mesh])

    def tearDown(self):
        if bpy.context.object and bpy.context.object.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
        bpy.context.scene.kai_face_meshes.clear()
        for obj in list(bpy.data.objects):
            bpy.data.objects.remove(obj, do_unlink=True)
        for collection in (bpy.data.armatures, bpy.data.meshes, bpy.data.curves, bpy.data.actions):
            for data in list(collection):
                if data.users == 0:
                    collection.remove(data)

    def label(self, rig=None, index=0):
        return (rig or self.rig).pose.bones[
            facial._custom_face_label_name(self.channels[index]["id"])
        ]

    def rename(self, index=0, name="Renamed"):
        facial._set_active_object(self.rig)
        return bpy.ops.kai.rename_custom_face_controller(
            channel_id=self.channels[index]["id"], display_name=name
        )

    def duplicate(self, kind="independent"):
        facial._set_active_object(self.rig)
        if kind == "object_copy":
            duplicate = self.rig.copy()
            bpy.context.collection.objects.link(duplicate)
        else:
            bpy.ops.object.duplicate(linked=(kind == "linked"))
            duplicate = bpy.context.object
        facial._set_active_object(self.rig)
        self.assertEqual(duplicate.data == self.rig.data, kind != "independent")
        return duplicate

    def test_rename_preserves_pose_action_keyframes_bones_drivers_mapping(self):
        rig = self.rig
        names = [
            facial.custom_face_bone_name(channel["id"]) for channel in self.channels
        ] + ["Face_BrowUpDown_L"]
        for index, name in enumerate(names):
            bone = rig.pose.bones[name]
            bone.location = (0.2 + index * 0.1, 0.0, 0.0)
            bone.keyframe_insert(data_path="location", frame=1)
            bone.location = (0.6 + index * 0.1, 0.0, 0.0)
            bone.keyframe_insert(data_path="location", frame=10)
        bpy.context.scene.frame_set(5)
        poses = {name: tuple(rig.pose.bones[name].location) for name in names}
        bones = {bone.name: bone.as_pointer() for bone in rig.data.bones}
        action = rig.animation_data.action
        keys = animation_snapshot(rig)
        mapping = rig.data[facial.FACE_TARGETS_PROPERTY]
        drivers = [
            (curve.as_pointer(), curve.data_path, curve.driver.expression)
            for curve in self.mesh.data.shape_keys.animation_data.drivers
        ]
        for index in range(2):
            self.assertEqual(self.rename(index, "New " + str(index)), {"FINISHED"})
        self.assertEqual({name: tuple(rig.pose.bones[name].location) for name in names}, poses)
        self.assertEqual({bone.name: bone.as_pointer() for bone in rig.data.bones}, bones)
        self.assertEqual(rig.animation_data.action, action)
        self.assertEqual(animation_snapshot(rig), keys)
        self.assertEqual(rig.data[facial.FACE_TARGETS_PROPERTY], mapping)
        self.assertEqual([
            (curve.as_pointer(), curve.data_path, curve.driver.expression)
            for curve in self.mesh.data.shape_keys.animation_data.drivers
        ], drivers)
        for frame, expected in ((1, 0.2), (10, 0.6)):
            bpy.context.scene.frame_set(frame)
            self.assertAlmostEqual(rig.pose.bones[names[0]].location.x, expected, places=5)
        # Unkeyed live poses must also survive a rename.
        rig.pose.bones[names[1]].location.x = 0.85
        self.rename(1, "Live pose")
        self.assertAlmostEqual(rig.pose.bones[names[1]].location.x, 0.85, places=5)

    def test_rename_without_module_keeps_definition(self):
        facial.remove_face_module(self.rig)
        self.assertEqual(self.rename(name="Saved only"), {"FINISHED"})
        self.assertEqual(facial.get_custom_face_channels(self.rig)[0]["display_name"], "Saved only")
        self.assertIsNone(self.rig.pose.bones.get(facial.custom_face_bone_name(self.channels[0]["id"])))

    def test_missing_label_recreated_without_bone_rebuild(self):
        label = self.label()
        pointer = label.bone.as_pointer()
        obj = label.custom_shape
        curve = obj.data
        bpy.data.objects.remove(obj, do_unlink=True)
        bpy.data.curves.remove(curve)
        self.assertEqual(self.rename(name="Recovered"), {"FINISHED"})
        self.assertEqual(self.label().bone.as_pointer(), pointer)
        self.assertEqual(self.label().custom_shape.data.body, "Recovered")

    def test_independent_duplicate_rename_is_copy_on_write(self):
        duplicate = self.duplicate()
        old = self.label(duplicate).custom_shape
        self.assertEqual(old, self.label().custom_shape)
        self.rename(name="Only A")
        self.assertEqual(self.label().custom_shape.data.body, "Only A")
        self.assertEqual(self.label(duplicate).custom_shape, old)
        self.assertEqual(old.data.body, "SafetyCheek")
        self.assertEqual(facial.get_custom_face_channels(duplicate)[0]["display_name"], "SafetyCheek")

    def test_independent_duplicate_remove_a_channel_preserves_b_labels(self):
        duplicate = self.duplicate()
        label = self.label(duplicate).custom_shape
        label_name = label.name
        facial.remove_custom_face_channel(self.rig, self.channels[0]["id"])
        self.assertEqual(self.label(duplicate).custom_shape, label)
        self.assertEqual(label.data.body, "SafetyCheek")
        self.assertIsNotNone(duplicate.pose.bones.get(facial.custom_face_bone_name(self.channels[0]["id"])))
        facial.remove_face_module(duplicate)
        self.assertNotIn(label_name, bpy.data.objects)

    def test_independent_duplicate_remove_b_module_preserves_a(self):
        duplicate = self.duplicate()
        labels = [self.label(index=index).custom_shape for index in range(2)]
        facial.remove_face_module(duplicate)
        bpy.data.objects.remove(duplicate, do_unlink=True)
        for index, obj in enumerate(labels):
            self.assertEqual(self.label(index=index).custom_shape, obj)
            self.assertIn(obj.name, bpy.data.objects)
        self.assertEqual(facial.face_module_state(self.rig), "GENERATED")

    def test_independent_duplicate_regenerate_a_preserves_b(self):
        duplicate = self.duplicate()
        labels = [self.label(duplicate, index).custom_shape for index in range(2)]
        facial.generate_face_module(self.rig, [self.mesh])
        for index, obj in enumerate(labels):
            self.assertEqual(self.label(duplicate, index).custom_shape, obj)
        facial.remove_face_module(duplicate)
        facial.remove_face_module(self.rig)
        self.assertFalse(any(obj.get("kai_face_label") for obj in bpy.data.objects))
        self.assertFalse(any(curve.name.startswith("KAI_FaceLabel_") for curve in bpy.data.curves))

    def assert_shared_edits_blocked(self, kind):
        duplicate = self.duplicate(kind)
        bones = {bone.name: bone.as_pointer() for bone in self.rig.data.bones}
        metadata = self.rig.data[facial.CUSTOM_FACE_CHANNELS_PROPERTY]
        label = self.label().custom_shape
        driver_count = len(self.mesh.data.shape_keys.animation_data.drivers)
        for operation in (
            lambda: facial.rename_custom_face_channel(self.rig, self.channels[0]["id"], "Blocked"),
            lambda: facial.add_custom_face_channel(self.rig, "Blocked"),
            lambda: facial.remove_custom_face_channel(self.rig, self.channels[0]["id"]),
            lambda: facial.remove_face_module(self.rig),
            lambda: facial.generate_face_module(self.rig, [self.mesh]),
            lambda: facial.remove_all_modules(self.rig),
        ):
            with self.subTest(operation=operation):
                with self.assertRaisesRegex(RuntimeError, "single-user Armature"):
                    operation()
                self.assertEqual({bone.name: bone.as_pointer() for bone in self.rig.data.bones}, bones)
                self.assertEqual(self.rig.data[facial.CUSTOM_FACE_CHANNELS_PROPERTY], metadata)
                self.assertEqual(self.label().custom_shape, label)
                self.assertEqual(self.label(duplicate).custom_shape, label)
                self.assertEqual(len(self.mesh.data.shape_keys.animation_data.drivers), driver_count)

    def test_linked_duplicate_blocks_shared_bone_and_definition_edits(self):
        self.assert_shared_edits_blocked("linked")

    def test_object_copy_blocks_shared_bone_and_definition_edits(self):
        self.assert_shared_edits_blocked("object_copy")

    def test_linked_duplicate_can_be_made_single_user_then_renamed(self):
        duplicate = self.duplicate("linked")
        duplicate.data = duplicate.data.copy()
        self.rename(name="Independent A")
        self.assertEqual(self.label(duplicate).custom_shape.data.body, "SafetyCheek")
        facial.remove_face_module(duplicate)
        self.assertEqual(self.label().custom_shape.data.body, "Independent A")

    def test_shared_data_operators_report_error_without_mutating(self):
        self.duplicate("linked")
        original = self.rig.data[facial.CUSTOM_FACE_CHANNELS_PROPERTY]
        scene = bpy.context.scene
        scene.kai_custom_face_target_shape_key = "SafetyCheek"
        scene.kai_custom_face_display_name = "Blocked"
        for operation in (
            lambda: bpy.ops.kai.rename_custom_face_controller(
                channel_id=self.channels[0]["id"], display_name="Blocked"),
            lambda: bpy.ops.kai.add_custom_face_controller(),
            lambda: bpy.ops.kai.remove_custom_face_controller(channel_id=self.channels[0]["id"]),
            lambda: bpy.ops.kai.remove_face_module(),
            lambda: bpy.ops.kai.generate_face_module(),
        ):
            with self.subTest(operation=operation):
                with self.assertRaisesRegex(RuntimeError, "single-user Armature"):
                    operation()
                self.assertEqual(self.rig.data[facial.CUSTOM_FACE_CHANNELS_PROPERTY], original)
                self.assertEqual(facial.face_module_state(self.rig), "GENERATED")

    def test_delete_duplicate_object_alone_preserves_a(self):
        duplicate = self.duplicate()
        self.rename(name="A survives")
        label = self.label().custom_shape
        bpy.data.objects.remove(duplicate, do_unlink=True)
        self.assertEqual(self.label().custom_shape, label)
        self.assertEqual(label.data.body, "A survives")
        facial.remove_face_module(self.rig)
        self.assertFalse(any(obj.get("kai_face_label") for obj in bpy.data.objects))
        self.assertFalse(any(curve.name.startswith("KAI_FaceLabel_") for curve in bpy.data.curves))

    def test_shared_text_datablock_copied_on_rename(self):
        shape = self.label().custom_shape
        other = bpy.data.objects.new("UserText", shape.data)
        bpy.context.collection.objects.link(other)
        original = other.data
        self.rename(name="Independent text")
        self.assertEqual(other.data, original)
        self.assertEqual(other.data.body, "SafetyCheek")
        self.assertNotEqual(self.label().custom_shape.data, original)
        self.assertEqual(self.label().custom_shape.data.body, "Independent text")

    def test_repeated_rename_regenerate_remove_leaves_no_label_data(self):
        for index in range(4):
            self.rename(name="Rename " + str(index))
            facial.generate_face_module(self.rig, [self.mesh])
            self.assertEqual(sum(bool(obj.get("kai_face_label")) for obj in bpy.data.objects), 2)
            self.assertEqual(sum(curve.name.startswith("KAI_FaceLabel_") for curve in bpy.data.curves), 2)
        facial.remove_face_module(self.rig)
        self.assertFalse(any(obj.get("kai_face_label") for obj in bpy.data.objects))
        self.assertFalse(any(curve.name.startswith("KAI_FaceLabel_") for curve in bpy.data.curves))

    def test_renamed_rig_and_armature_cleanup_uses_live_references(self):
        self.rig.name = "RenamedRig"
        self.rig.data.name = "RenamedArmature"
        facial.remove_custom_face_channel(self.rig, self.channels[0]["id"])
        self.assertEqual(sum(bool(obj.get("kai_face_label")) for obj in bpy.data.objects), 1)
        facial.remove_face_module(self.rig)
        self.assertFalse(any(obj.get("kai_face_label") for obj in bpy.data.objects))
        self.assertFalse(any(curve.name.startswith("KAI_FaceLabel_") for curve in bpy.data.curves))

    def test_save_reopen_preserves_independent_labels(self):
        duplicate = self.duplicate()
        name_a, name_b = self.rig.name, duplicate.name
        self.rename(name="Saved A")
        path = PROFILE / "facial-safety.blend"
        path.parent.mkdir(parents=True, exist_ok=True)
        bpy.ops.wm.save_as_mainfile(filepath=str(path), check_existing=False)
        bpy.ops.wm.open_mainfile(filepath=str(path))
        self.rig = bpy.data.objects[name_a]
        duplicate = bpy.data.objects[name_b]
        self.assertEqual(self.label().custom_shape.data.body, "Saved A")
        self.assertEqual(self.label(duplicate).custom_shape.data.body, "SafetyCheek")
        self.assertEqual(facial.get_custom_face_channels(self.rig)[0]["display_name"], "Saved A")


suite = unittest.defaultTestLoader.loadTestsFromTestCase(FacialSafetyTests)
result = unittest.TextTestRunner(verbosity=2).run(suite)
print("KAI_FACIAL_SAFETY_RESULT", json.dumps({
    "blender": bpy.app.version_string,
    "tests": result.testsRun,
    "failures": len(result.failures),
    "errors": len(result.errors),
    "skipped": len(result.skipped),
}))
fixture["package"].unregister()
bpy.context.preferences.addons.remove(fixture["addon_entry"])
if not result.wasSuccessful():
    raise AssertionError("Facial safety regression failed")
