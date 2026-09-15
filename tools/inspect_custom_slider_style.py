"""Print Custom Slider shape and bone-color settings from the opened blend."""

import bpy


def color_payload(owner):
    color = getattr(owner, "color", None)
    if color is None:
        return None
    custom = color.custom
    return {
        "palette": color.palette,
        "normal": tuple(round(value, 6) for value in custom.normal),
        "select": tuple(round(value, 6) for value in custom.select),
        "active": tuple(round(value, 6) for value in custom.active),
    }


for rig in (obj for obj in bpy.data.objects if obj.type == "ARMATURE"):
    sliders = [
        pbone
        for pbone in rig.pose.bones
        if pbone.name == "Face_CustomRoot"
        or pbone.name.startswith("Face_Custom_")
        or pbone.name.startswith("MCH_Face_CustomTrack_")
        or pbone.name.startswith("MCH_Face_CustomLabel_")
    ]
    if not sliders:
        continue
    print("KAI_CUSTOM_STYLE_RIG", rig.name)
    for pbone in sliders:
        shape = pbone.custom_shape
        print(
            "KAI_CUSTOM_STYLE",
            pbone.name,
            f"shape={shape.name if shape else None}",
            f"shape_dimensions={tuple(round(v, 6) for v in shape.dimensions) if shape else None}",
            f"translation={tuple(round(v, 6) for v in pbone.custom_shape_translation)}",
            f"rotation={tuple(round(v, 6) for v in pbone.custom_shape_rotation_euler)}",
            f"scale={tuple(round(v, 6) for v in pbone.custom_shape_scale_xyz)}",
            f"bone_color={color_payload(pbone.bone)}",
            f"pose_color={color_payload(pbone)}",
        )
