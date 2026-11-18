"""Automated GUI smoke test; run only with a disposable KAI_QA_PROFILE."""

import json
import ctypes
import importlib
import os
import struct
import traceback
from pathlib import Path

import bpy
from mathutils import Vector


PROFILE = Path(os.environ["KAI_QA_PROFILE"]).resolve()
OUTPUT = Path(os.environ["KAI_QA_OUTPUT"]).resolve()
OUTPUT.mkdir(parents=True, exist_ok=True)
paths = {kind: bpy.utils.user_resource(kind) for kind in ("CONFIG", "SCRIPTS", "EXTENSIONS")}
assert all(Path(path).resolve().is_relative_to(PROFILE) for path in paths.values()), paths
assert not bpy.app.background
repositories_before = len(bpy.context.preferences.extensions.repos)
bpy.context.preferences.use_preferences_save = False
bpy.context.preferences.view.show_splash = False
fixture_path = Path(__file__).with_name("test_kai_facial.py")
source = fixture_path.read_text(encoding="utf-8").split(
    "rig, mesh, eyebrow, eyelash = create_fixture()"
)[0]
fixture = {"__file__": str(fixture_path), "__name__": "gui_fixture"}
installed_module = os.environ.get("KAI_QA_INSTALLED_MODULE", "")
if installed_module:
    package = importlib.import_module(installed_module)
    assert bpy.context.preferences.addons.get(installed_module) is not None
    fixture.update(bpy=bpy, Vector=Vector, package=package, kai_facial=package.kai_facial)
    exec(compile(source[source.index("def assert_true"):], str(fixture_path), "exec"), fixture)
else:
    exec(compile(source, str(fixture_path), "exec"), fixture)
facial = fixture["kai_facial"]
rig, mesh, _, _ = fixture["create_fixture"]()
rig.name = "A"
scene = bpy.context.scene
scene.kai_face_mesh_candidate = mesh
bpy.ops.kai.add_face_mesh()
channels = []
for name in ("Cheek Puff", "Tongue Out"):
    mesh.shape_key_add(name=name)
    channel = facial.add_custom_face_channel(rig, name)
    facial.set_face_channel_mapping(rig, mesh, channel["id"], name)
    channels.append(channel)
facial.generate_face_module(rig, [mesh])
facial._set_active_object(rig)
bpy.ops.object.duplicate(linked=False)
duplicate = bpy.context.object
duplicate.name = "B"
duplicate.location.x = 0.58
for obj in bpy.data.objects:
    if obj.type != "ARMATURE":
        obj.hide_set(True)
for armature in (rig, duplicate):
    armature.show_in_front = True
    for bone in armature.data.bones:
        bone.hide = not bone.get("kai_module")
facial._set_active_object(rig)
duplicate.select_set(True)
bpy.ops.object.mode_set(mode="POSE")
first_bone = facial.custom_face_bone_name(channels[0]["id"])
rig.pose.bones[first_bone].location.x = 0.65
original_bone_pointer = rig.data.bones[first_bone].as_pointer()
area = next(area for area in bpy.context.screen.areas if area.type == "VIEW_3D")
region = next(region for region in area.regions if region.type == "WINDOW")
space = area.spaces.active
space.show_region_ui = False
space.overlay.show_relationship_lines = False
space.overlay.show_floor = False
space.overlay.show_axis_x = False
space.overlay.show_axis_y = False
space.overlay.show_axis_z = False
points = [
    armature.matrix_world @ bone.head
    for armature in (rig, duplicate)
    for bone in armature.pose.bones
    if bone.bone.get("kai_module")
]
center = sum(points, Vector()) / len(points)
with bpy.context.temp_override(area=area, region=region):
    bpy.ops.view3d.view_axis(type="FRONT", align_active=False)
space.region_3d.view_location = center + Vector((0.04, 0.0, 0.0))
space.region_3d.view_distance = 1.45
state = {"step": -1, "checks": []}


def dismiss_splash():
    # Send Escape only to this disposable Blender process, without moving the
    # user's cursor or sending input to another Blender window.
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


def position_popup_event():
    # Set only this window's event position, without warping the user's cursor.
    user32 = ctypes.windll.user32
    @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    def visit(window, _parameter):
        owner = ctypes.c_ulong()
        user32.GetWindowThreadProcessId(window, ctypes.byref(owner))
        if owner.value == os.getpid():
            user32.PostMessageW(window, 0x0200, 0, (400 << 16) | 700)
        return True
    user32.EnumWindows(visit, 0)


def check(value, name):
    if not value:
        raise AssertionError(name)
    state["checks"].append(name)


def capture(name):
    area.tag_redraw()
    print("GUI_DIMENSIONS", bpy.context.window.width, bpy.context.window.height,
          area.width, area.height, region.width, region.height, flush=True)
    with bpy.context.temp_override(window=bpy.context.window, area=area, region=region):
        bpy.ops.wm.redraw_timer(type="DRAW_WIN_SWAP", iterations=2)
        path = OUTPUT / name
        bpy.ops.screen.screenshot(filepath=str(path), check_existing=False)
        width, height = struct.unpack(">II", path.read_bytes()[16:24])
        check(width > 100 and height > 100, "Screenshot contains a drawable window: " + name)


def run():
    try:
        step = state["step"]
        remaining_label = facial._custom_face_label_name(channels[1]["id"])
        if step == -1:
            dismiss_splash()
        elif step == 0:
            check(bpy.types.KAI_PT_facial.is_registered, "Facial panel registered")
            capture("01-shared-labels-before.png")
        elif step == 1:
            check(bpy.ops.kai.rename_custom_face_controller(
                channel_id=channels[0]["id"], display_name="A Renamed"
            ) == {"FINISHED"}, "Rename operator finished in GUI")
            check(abs(rig.pose.bones[first_bone].location.x - 0.65) < 0.0001, "Live pose preserved")
            check(rig.data.bones[first_bone].as_pointer() == original_bone_pointer, "Bone identity preserved")
            label_name = facial._custom_face_label_name(channels[0]["id"])
            check(duplicate.pose.bones[label_name].custom_shape.data.body == "Cheek Puff", "B label unchanged")
            check(rig.pose.bones[label_name].custom_shape.data.body == "A Renamed", "A label updated")
            capture("02-rename-preserves-pose-and-b.png")
        elif step == 2:
            check(bpy.ops.kai.remove_custom_face_controller(
                channel_id=channels[0]["id"]
            ) == {"FINISHED"}, "Remove custom operator finished in GUI")
            label_name = facial._custom_face_label_name(channels[0]["id"])
            check(duplicate.pose.bones[label_name].custom_shape.data.body == "Cheek Puff", "B label survives A removal")
            capture("03-remove-a-preserves-b.png")
        elif step == 3:
            facial.remove_face_module(duplicate)
            bpy.data.objects.remove(duplicate, do_unlink=True)
            remaining_label = facial._custom_face_label_name(channels[1]["id"])
            check(rig.pose.bones[remaining_label].custom_shape.data.body == "Tongue Out", "A label survives B removal")
            capture("04-remove-b-preserves-a.png")
            position_popup_event()
        elif step == 4:
            facial._set_active_object(rig)
            linked = rig.copy()
            bpy.context.collection.objects.link(linked)
            snapshot = rig.data[facial.CUSTOM_FACE_CHANNELS_PROPERTY]
            try:
                bpy.ops.kai.remove_custom_face_controller(channel_id=channels[1]["id"])
            except RuntimeError as exc:
                check("single-user Armature" in str(exc), "Linked duplicate reports actionable error")
            else:
                raise AssertionError("Shared Armature deletion was not blocked")
            check(rig.data[facial.CUSTOM_FACE_CHANNELS_PROPERTY] == snapshot, "Blocked operator preserves shared definition")
            check(linked.pose.bones.get(remaining_label) is not None, "Blocked operator preserves B bone")
            bpy.data.objects.remove(linked, do_unlink=True)
            bpy.ops.object.mode_set(mode="POSE")
            # Display the real N panel and capture any draw errors in the log.
            space.show_region_ui = True
            with bpy.context.temp_override(area=area, region=region):
                print("FACIAL_PANEL_POPUP", bpy.ops.wm.call_panel(name="KAI_PT_facial", keep_open=True), flush=True)
        elif step == 5:
            capture("05-facial-panel.png")
            report = {
                "blender": bpy.app.version_string,
                "automated_gui": True,
                "manual_mouse_review": False,
                "installed_module": installed_module or None,
                "success": True,
                "checks": state["checks"],
                "user_paths": paths,
                "repositories_before": repositories_before,
                "repositories_after": len(bpy.context.preferences.extensions.repos),
                "normal_profile_modified": False,
                "preferences_saved": False,
            }
            (OUTPUT / "gui-result.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
            print("KAI_GUI_OK", json.dumps(report), flush=True)
            bpy.ops.wm.quit_blender()
            return None
        state["step"] += 1
        return 1.0
    except Exception:
        error = traceback.format_exc()
        print(error, flush=True)
        (OUTPUT / "gui-result.json").write_text(json.dumps({
            "success": False, "error": error, "step": state["step"]
        }, indent=2), encoding="utf-8")
        bpy.ops.wm.quit_blender()
        return None


bpy.app.timers.register(run, first_interval=3.0)
