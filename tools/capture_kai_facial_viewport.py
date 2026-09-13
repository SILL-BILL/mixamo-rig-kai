"""Interactive Blender viewport capture for Kai Facial Phase 1.1 QA."""

import importlib.util
import sys
import ctypes
import os
from pathlib import Path

import bpy


REPO = Path(__file__).resolve().parents[1]
OUTPUT_DIR = Path(
    r"C:\Users\lost5\.codex\visualizations\2026\09\13\01a09a28-8b46-7c92-abda-5e9efaf4a8b7"
)

spec = importlib.util.spec_from_file_location(
    "mixamo_rig_kai",
    REPO / "__init__.py",
    submodule_search_locations=[str(REPO)],
)
package = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = package
spec.loader.exec_module(package)
from mixamo_rig_kai import kai_facial  # noqa: E402
from mixamo_rig_kai.lib.bones_pose import set_pose_bone_selected  # noqa: E402

addon_entry = bpy.context.preferences.addons.new()
addon_entry.module = package.__name__
package.register()

for scene_object in bpy.context.scene.objects:
    scene_object.hide_viewport = True

armature = bpy.data.armatures.new("KaiFacialViewportQA")
rig = bpy.data.objects.new("KaiFacialViewportQA", armature)
bpy.context.collection.objects.link(rig)
bpy.context.view_layer.objects.active = rig
rig.select_set(True)
bpy.ops.object.mode_set(mode="EDIT")
head = armature.edit_bones.new("Head")
head.head = (0.0, 0.0, 1.6)
head.tail = (0.0, 0.0, 1.9)
bpy.ops.object.mode_set(mode="OBJECT")
armature["kai_head_name"] = "Head"

mesh_data = bpy.data.meshes.new("KaiFaceViewportQA")
mesh = bpy.data.objects.new("KaiFaceViewportQA", mesh_data)
bpy.context.collection.objects.link(mesh)
mesh.hide_viewport = True
mesh.shape_key_add(name="Basis")
for shape_name in kai_facial.DEFAULT_FACE_SHAPE_KEY_MAPPING.values():
    mesh.shape_key_add(name=shape_name)

kai_facial.generate_face_module(rig, [mesh])
kai_facial.generate_eye_module(rig, "Head")
kai_facial._set_active_object(rig)
bpy.ops.object.mode_set(mode="POSE")
armature.show_names = False
rig.show_in_front = True


def set_collection_visibility(controller_visible, root_visible):
    for collection in armature.collections:
        collection.is_visible = False
    face = armature.collections.get(kai_facial.FACE_COLLECTION)
    if face:
        face.is_visible = controller_visible
    roots = armature.collections.get(kai_facial.FACE_ROOT_COLLECTION)
    if roots:
        roots.is_visible = root_visible


def capture(names, view_location, view_distance, filepath, show_names=False):
    armature.show_names = show_names
    for bone in armature.bones:
        bone.hide = bone.name not in names
    for pbone in rig.pose.bones:
        set_pose_bone_selected(pbone, False)
    armature.bones.active = None
    area = next(area for area in bpy.context.screen.areas if area.type == "VIEW_3D")
    region = next(region for region in area.regions if region.type == "WINDOW")
    space = area.spaces.active
    window = bpy.context.window
    screen = window.screen
    space.overlay.show_text = True
    space.overlay.show_relationship_lines = False
    space.overlay.show_floor = False
    space.overlay.show_axis_x = False
    space.overlay.show_axis_y = False
    space.overlay.show_axis_z = False
    with bpy.context.temp_override(window=window, screen=screen, area=area, region=region):
        bpy.ops.view3d.view_axis(type="FRONT", align_active=False)
        space.region_3d.view_location = view_location
        space.region_3d.view_distance = view_distance
        bpy.ops.wm.redraw_timer(type="DRAW_WIN_SWAP", iterations=2)
    with bpy.context.temp_override(window=window, screen=screen, area=area):
        result = bpy.ops.screen.screenshot_area(
            "EXEC_DEFAULT",
            filepath=str(filepath),
            check_existing=False,
        )
        print("KAI_VIEWPORT_CAPTURE", filepath, result)


state = {"step": 0}


def close_splash():
    user32 = ctypes.windll.user32
    process_id = os.getpid()

    @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    def send_escape(window, _param):
        owner = ctypes.c_ulong()
        user32.GetWindowThreadProcessId(window, ctypes.byref(owner))
        if owner.value == process_id:
            user32.PostMessageW(window, 0x0100, 0x1B, 0)
            user32.PostMessageW(window, 0x0101, 0x1B, 0)
        return True

    user32.EnumWindows(send_escape, 0)


def run_capture():
    if state["step"] == 0:
        close_splash()
        state["step"] = 1
        return 0.5
    if state["step"] == 1:
        set_collection_visibility(True, False)
        capture(
            [spec["name"] for spec in kai_facial.FACE_CONTROLLERS],
            (3.0, 0.0, 3.0),
            5.8,
            OUTPUT_DIR / "kai_face_controller_ui.png",
        )
        state["step"] = 2
        return 0.5
    if state["step"] == 2:
        set_collection_visibility(False, True)
        capture(
            [name for name, _parent, _position in kai_facial.FACE_ANCHORS],
            (3.0, 0.0, 3.0),
            7.0,
            OUTPUT_DIR / "kai_face_root_ui.png",
        )
        state["step"] = 3
        return 1.0
    bpy.ops.wm.quit_blender()
    return None


bpy.app.timers.register(run_capture, first_interval=0.5)
