"""Interactive-context QA for the Facial Mapping search popup."""

import ctypes
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

armature = bpy.data.armatures.new("KaiMappingInteractiveQA")
rig = bpy.data.objects.new("KaiMappingInteractiveQA", armature)
bpy.context.collection.objects.link(rig)
bpy.context.view_layer.objects.active = rig
rig.select_set(True)
bpy.ops.object.mode_set(mode="EDIT")
head = armature.edit_bones.new("Head")
head.head = (0.0, 0.0, 0.0)
head.tail = (0.0, 0.0, 1.0)
bpy.ops.object.mode_set(mode="OBJECT")

mesh_data = bpy.data.meshes.new("KaiMappingInteractiveMesh")
mesh = bpy.data.objects.new("KaiMappingInteractiveMesh", mesh_data)
bpy.context.collection.objects.link(mesh)
mesh.shape_key_add(name="Basis")
mesh.shape_key_add(name="Angry_Eye_Left")
kai_facial.ensure_face_mesh_mapping(rig, mesh)

user32 = ctypes.windll.user32
state = {"step": 0, "invoke": None, "execute": None}


def press_key(key):
    user32.keybd_event(key, 0, 0, 0)
    user32.keybd_event(key, 0, 0x0002, 0)


def run_test():
    if state["step"] == 0:
        press_key(0x1B)  # Close Blender's splash screen.
        state["step"] = 1
        return 0.6
    if state["step"] == 1:
        area = next(area for area in bpy.context.screen.areas if area.type == "VIEW_3D")
        region = next(region for region in area.regions if region.type == "WINDOW")
        with bpy.context.temp_override(
            window=bpy.context.window,
            screen=bpy.context.screen,
            area=area,
            region=region,
        ):
            state["invoke"] = bpy.ops.kai.set_face_mapping(
                "INVOKE_DEFAULT",
                object_name=mesh.name,
                channel="eye_angry_l",
            )
        print("KAI_MAPPING_INVOKE_RESULT", state["invoke"])
        state["step"] = 2
        return 0.8
    if state["step"] == 2:
        press_key(0x1B)  # Close the popup after confirming it opened.
        area = next(area for area in bpy.context.screen.areas if area.type == "VIEW_3D")
        region = next(region for region in area.regions if region.type == "WINDOW")
        with bpy.context.temp_override(
            window=bpy.context.window,
            screen=bpy.context.screen,
            area=area,
            region=region,
        ):
            state["execute"] = bpy.ops.kai.set_face_mapping(
                "EXEC_DEFAULT",
                object_name=mesh.name,
                channel="eye_angry_l",
                shape_key="Angry_Eye_Left",
            )
        print("KAI_MAPPING_EXECUTE_RESULT", state["execute"])
        state["step"] = 3
        return 0.8

    mapping = kai_facial._mapping_for_mesh(rig, mesh, kai_facial.get_face_mapping(rig))
    selected = mapping["eye_angry_l"]
    success = (
        state["invoke"] == {"RUNNING_MODAL"}
        and state["execute"] == {"FINISHED"}
        and selected == "Angry_Eye_Left"
    )
    print("KAI_MAPPING_INTERACTIVE_OK", success, "selected=", selected)
    bpy.ops.wm.quit_blender()
    return None


bpy.app.timers.register(run_test, first_interval=0.5)
