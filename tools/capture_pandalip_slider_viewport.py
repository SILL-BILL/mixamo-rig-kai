"""Capture the local PandaLip controller as a visual comparison reference."""

import ctypes
import importlib.util
import os
import sys
from pathlib import Path

import bpy


PANDA_PACKAGE = Path(r"D:\dev-blender-addon\panda-lip-blender\panda_lip_blender")
OUTPUT = Path(
    r"C:\Users\lost5\.codex\visualizations\2026\09\13\01a09a28-8b46-7c92-abda-5e9efaf4a8b7\pandalip_slider_reference.png"
)
spec = importlib.util.spec_from_file_location(
    "panda_lip_blender",
    PANDA_PACKAGE / "__init__.py",
    submodule_search_locations=[str(PANDA_PACKAGE)],
)
package = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = package
spec.loader.exec_module(package)
from panda_lip_blender.controller import create_controller  # noqa: E402

controller = create_controller(bpy.context)
bpy.ops.object.mode_set(mode="POSE")
controller.data.show_names = False


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


state = {"step": 0}


def capture():
    if state["step"] == 0:
        close_splash()
        state["step"] = 1
        return 0.5
    area = next(area for area in bpy.context.screen.areas if area.type == "VIEW_3D")
    region = next(region for region in area.regions if region.type == "WINDOW")
    space = area.spaces.active
    space.overlay.show_relationship_lines = False
    space.overlay.show_floor = False
    with bpy.context.temp_override(
        window=bpy.context.window,
        screen=bpy.context.screen,
        area=area,
        region=region,
    ):
        bpy.ops.view3d.view_axis(type="FRONT", align_active=False)
        space.region_3d.view_location = (0.72, 0.0, 0.0)
        space.region_3d.view_distance = 1.25
        bpy.ops.wm.redraw_timer(type="DRAW_WIN_SWAP", iterations=2)
    with bpy.context.temp_override(window=bpy.context.window, screen=bpy.context.screen, area=area):
        print(
            "PANDALIP_VIEWPORT_CAPTURE",
            bpy.ops.screen.screenshot_area(
                "EXEC_DEFAULT",
                filepath=str(OUTPUT),
                check_existing=False,
            ),
        )
    bpy.ops.wm.quit_blender()
    return None


bpy.app.timers.register(capture, first_interval=0.5)
