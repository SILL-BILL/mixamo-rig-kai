"""GUI acceptance on copies of immutable Drive-pending fixtures, including Undo."""

import ctypes
import hashlib
import importlib
import json
import os
import shutil
import traceback
from pathlib import Path

import bpy
from mathutils import Vector


PROFILE = Path(os.environ["KAI_QA_PROFILE"]).resolve()
OUTPUT = Path(os.environ["KAI_QA_OUTPUT"]).resolve()
ORIGINALS = Path(os.environ["KAI_TEST_DATA_ORIGINALS"]).resolve()
REPO = Path(__file__).resolve().parents[1]
assert not OUTPUT.is_relative_to(REPO)
assert not bpy.app.background
paths = {kind: bpy.utils.user_resource(kind) for kind in ("CONFIG", "SCRIPTS", "EXTENSIONS")}
assert all(Path(path).resolve().is_relative_to(PROFILE) for path in paths.values())
OUTPUT.mkdir(parents=True, exist_ok=False)
module_name = os.environ["KAI_QA_INSTALLED_MODULE"]
package = importlib.import_module(module_name)
assert bpy.context.preferences.addons.get(module_name)
facial = package.kai_facial
compat = package.mixamo_rig.animation_compat
source = ORIGINALS / "kai-v0610-facial-independent.blend"
linked_source = ORIGINALS / "kai-v0610-facial-linked.blend"
source_hashes = {path.name: hashlib.sha256(path.read_bytes()).hexdigest()
                 for path in (source, linked_source)}
working = OUTPUT / "input-copy.blend"
linked_working = OUTPUT / "linked-input-copy.blend"
shutil.copy2(source, working)
shutil.copy2(linked_source, linked_working)
saved = OUTPUT / "accepted-copy.blend"
state = {"step": 0, "checks": [], "pending_load": working}
repositories_before = len(bpy.context.preferences.extensions.repos)


def check(value, message):
    if not value:
        raise AssertionError(message)
    state["checks"].append(message)


def rig():
    return bpy.data.objects["PF_Kai_A"]


def label(obj, channel="custom_001"):
    return obj.pose.bones[facial._custom_face_label_name(channel)].custom_shape


def channels():
    return facial.get_custom_face_channels(rig())


def keys():
    return [(curve.data_path, curve.array_index, [tuple(point.co) for point in curve.keyframe_points])
            for curve in compat.get_action_fcurves(rig().animation_data.action)]


def select_rig():
    facial._set_active_object(rig())


def load(path):
    # File reads replace the screen/context. Wait for the next GUI event before
    # using the new data, and never open a file inside a stale temp_override.
    state["pending_load"] = path


def dismiss_splash():
    user32 = ctypes.windll.user32
    @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    def visit(window, _parameter):
        owner = ctypes.c_ulong()
        user32.GetWindowThreadProcessId(window, ctypes.byref(owner))
        if owner.value == os.getpid():
            user32.PostMessageW(window, 0x0100, 0x1B, 0)
            user32.PostMessageW(window, 0x0101, 0x1B, 0)
        return True
    user32.EnumWindows(visit, 0)


def view():
    select_rig()
    bpy.ops.object.mode_set(mode="POSE")
    for obj in bpy.data.objects:
        if obj.type == "ARMATURE":
            obj.show_in_front = True
            for bone in obj.data.bones:
                bone.hide = bone.get("kai_module") != facial.FACE_MODULE_ID
        else:
            obj.hide_set(True)
    area = next(area for area in bpy.context.screen.areas if area.type == "VIEW_3D")
    region = next(region for region in area.regions if region.type == "WINDOW")
    space = area.spaces.active
    space.show_region_ui = False
    space.overlay.show_floor = False
    space.overlay.show_relationship_lines = False
    points = [obj.matrix_world @ bone.head for obj in bpy.data.objects if obj.type == "ARMATURE"
              for bone in obj.pose.bones if bone.bone.get("kai_module") == facial.FACE_MODULE_ID]
    with bpy.context.temp_override(area=area, region=region):
        bpy.ops.view3d.view_axis(type="FRONT", align_active=False)
    space.region_3d.view_location = sum(points, Vector()) / len(points)
    space.region_3d.view_distance = 1.55


def run_step():
    try:
        step = state["step"]
        if step == 0:
            dismiss_splash()
            select_rig()
            check(not bpy.data.libraries, "Fixture is portable without external blend libraries")
            check(len(channels()) == 2, "Baseline has two Custom channels")
            check(rig().data != bpy.data.objects["PF_Kai_B"].data, "Baseline Armature data is independent")
            check(label(rig()) == label(bpy.data.objects["PF_Kai_B"]), "Baseline shares label object")
            state["keys"] = keys()
            state["mapping"] = rig().data[facial.FACE_TARGETS_PROPERTY]
            bpy.ops.ed.undo_push(message="Kai acceptance baseline")
        elif step == 1:
            select_rig()
            pointer = rig().data.bones[facial.custom_face_bone_name("custom_001")].as_pointer()
            check(bpy.ops.kai.rename_custom_face_controller(
                "EXEC_DEFAULT", True, channel_id="custom_001", display_name="Acceptance Renamed"
            ) == {"FINISHED"}, "Rename with native undo enabled")
            check(rig().data.bones[facial.custom_face_bone_name("custom_001")].as_pointer() == pointer,
                  "Rename does not regenerate Bone")
            check(abs(rig().pose.bones[facial.custom_face_bone_name("custom_001")].location.x - 0.65) < 1e-5,
                  "Rename preserves keyed live pose")
            check(keys() == state["keys"], "Rename preserves all keyframes")
            check(rig().data[facial.FACE_TARGETS_PROPERTY] == state["mapping"], "Rename preserves Mapping")
        elif step == 2:
            check(bpy.ops.ed.undo() == {"FINISHED"}, "Undo rename executes")
            check(channels()[0]["display_name"] == "Cheek Puff", "Undo restores channel name")
            check(label(rig()).data.body == "Cheek Puff", "Undo restores label")
            check(keys() == state["keys"], "Undo preserves Action keys")
        elif step == 3:
            check(bpy.ops.ed.redo() == {"FINISHED"}, "Redo rename executes")
            check(label(rig()).data.body == "Acceptance Renamed", "Redo restores renamed label")
            check(label(bpy.data.objects["PF_Kai_B"]).data.body == "Cheek Puff", "Redo keeps B label")
        elif step == 4:
            select_rig()
            check(bpy.ops.kai.remove_custom_face_controller(
                "EXEC_DEFAULT", True, channel_id="custom_001") == {"FINISHED"}, "Remove with native undo enabled")
            check(len(channels()) == 1, "Remove deletes only target channel")
            check(label(bpy.data.objects["PF_Kai_B"]).data.body == "Cheek Puff", "Remove protects B label")
        elif step == 5:
            check(bpy.ops.ed.undo() == {"FINISHED"}, "Undo remove executes")
            check(len(channels()) == 2, "Undo restores removed channel")
            check(label(rig()).data.body == "Acceptance Renamed", "Undo restores removed Text")
            check(rig().data[facial.FACE_TARGETS_PROPERTY] == state["mapping"], "Undo restores Mapping")
        elif step == 6:
            check(bpy.ops.ed.redo() == {"FINISHED"}, "Redo remove executes")
            check(len(channels()) == 1, "Redo removes channel again")
        elif step == 7:
            check(bpy.ops.ed.undo() == {"FINISHED"}, "Undo restores baseline for add test")
            check(len(channels()) == 2, "Channel restored before add")
        elif step == 8:
            select_rig()
            bpy.context.scene.kai_custom_face_target_shape_key = "Acceptance Extra"
            bpy.context.scene.kai_custom_face_display_name = "Acceptance Extra"
            check(bpy.ops.kai.add_custom_face_controller("EXEC_DEFAULT", True) == {"FINISHED"},
                  "Add with native undo enabled")
            check(len(channels()) == 3, "Add creates third channel")
            check(rig().pose.bones.get(facial.custom_face_bone_name("custom_003")) is not None,
                  "Add creates third controller")
        elif step == 9:
            check(bpy.ops.ed.undo() == {"FINISHED"}, "Undo add executes")
            check(len(channels()) == 2, "Undo removes added definition")
            check(rig().pose.bones.get(facial.custom_face_bone_name("custom_003")) is None,
                  "Undo removes added Bone")
        elif step == 10:
            check(bpy.ops.ed.redo() == {"FINISHED"}, "Redo add executes")
            check(len(channels()) == 3, "Redo restores third channel")
            check(label(rig(), "custom_003").data.body == "Acceptance Extra", "Redo restores added label")
            bpy.context.scene.frame_set(2)
            bpy.context.scene.frame_set(1)
            state["saved_channels"] = channels()
            state["saved_mapping"] = rig().data[facial.FACE_TARGETS_PROPERTY]
            view()
        elif step == 11:
            area = next(area for area in bpy.context.screen.areas if area.type == "VIEW_3D")
            with bpy.context.temp_override(area=area):
                bpy.ops.wm.redraw_timer(type="DRAW_WIN_SWAP", iterations=2)
                bpy.ops.screen.screenshot(filepath=str(OUTPUT / "acceptance-after-redo.png"), check_existing=False)
            check(not saved.exists(), "Save destination is a new copy")
            bpy.ops.wm.save_as_mainfile(filepath=str(saved), check_existing=False, compress=True)
            load(saved)
        elif step == 12:
            check(channels() == state["saved_channels"], "Save/reopen preserves definitions")
            check(rig().data[facial.FACE_TARGETS_PROPERTY] == state["saved_mapping"], "Save/reopen preserves Mapping")
            check(keys() == state["keys"], "Save/reopen preserves Action keys")
            check(label(rig()).data.body == "Acceptance Renamed", "Save/reopen preserves A label")
            check(label(bpy.data.objects["PF_Kai_B"]).data.body == "Cheek Puff", "Save/reopen preserves B label")
            load(linked_working)
        elif step == 13:
            linked = bpy.data.objects["PF_Kai_Linked"]
            check(linked.data == rig().data, "Linked fixture shares Armature data")
            before = rig().data[facial.CUSTOM_FACE_CHANNELS_PROPERTY]
            for operation in (
                lambda: bpy.ops.kai.rename_custom_face_controller(channel_id="custom_001", display_name="Blocked"),
                lambda: bpy.ops.kai.remove_custom_face_controller(channel_id="custom_001"),
            ):
                try:
                    operation()
                except RuntimeError as error:
                    check("single-user Armature" in str(error), "Shared-data operation rejected")
                else:
                    raise AssertionError("Linked edit unexpectedly succeeded")
            check(rig().data[facial.CUSTOM_FACE_CHANNELS_PROPERTY] == before, "Rejection preserves shared definition")
            check(label(linked).data.body == "Cheek Puff", "Rejection preserves linked label")
            for path in (source, linked_source):
                check(hashlib.sha256(path.read_bytes()).hexdigest() == source_hashes[path.name],
                      "Original fixture unchanged: " + path.name)
            report = {
                "success": True, "blender": bpy.app.version_string, "extension_version": "0.6.10",
                "checks": state["checks"], "operator_undo_flag": True, "manual_mouse_review": False,
                "user_paths": paths, "repositories_before": repositories_before,
                "repositories_after": len(bpy.context.preferences.extensions.repos),
                "normal_profile_modified": False, "preferences_saved": False,
                "saved_copy": str(saved), "original_hashes": source_hashes,
                "drive_upload_performed": False, "notion_registration_performed": False,
            }
            (OUTPUT / "acceptance-result.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
            print("KAI_ACCEPTANCE_OK", len(state["checks"]), flush=True)
            bpy.ops.wm.quit_blender()
            return None
        state["step"] += 1
        return 0.7
    except Exception:
        error = traceback.format_exc()
        print(error, flush=True)
        (OUTPUT / "acceptance-result.json").write_text(json.dumps({
            "success": False, "step": state["step"], "checks": state["checks"], "error": error,
        }, indent=2), encoding="utf-8")
        bpy.ops.wm.quit_blender()
        return None


def run():
    pending = state.pop("pending_load", None)
    if pending is not None:
        bpy.ops.wm.open_mainfile(filepath=str(pending))
        return 1.0
    window = bpy.context.window_manager.windows[0]
    area = next(area for area in window.screen.areas if area.type == "VIEW_3D")
    region = next(region for region in area.regions if region.type == "WINDOW")
    with bpy.context.temp_override(window=window, area=area, region=region):
        bpy.context.preferences.use_preferences_save = False
        bpy.context.preferences.edit.use_global_undo = True
        bpy.context.preferences.view.show_splash = False
        return run_step()


bpy.app.timers.register(run, first_interval=2.0, persistent=True)
