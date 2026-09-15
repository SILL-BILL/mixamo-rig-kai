"""Mixamo Rig Kai Eye / Face modules (Facial v0.1, Phase 1.2)."""

import json
from math import radians

import bpy
from bpy.types import Panel
from mathutils import Vector

from .lib.bones_data import set_bone_collection
from .lib.bones_pose import set_bone_custom_shape
from .lib.objects import get_object, hide_object


FACE_MODULE_ID = "kai_face_v01"
EYE_MODULE_ID = "kai_eye_v01"
FACE_ROOT = "FaceCtrlRigRoot"
LEGACY_FACE_ROOT = "Face_ControlRigRoot"
FACE_COLLECTION = "CTRL_Face"
FACE_ROOT_COLLECTION = "CTRL_Face_Root"
FACE_ANCHOR_COLLECTION = "MCH_Face"
EYE_TARGET_ROOT = "EyeTargetRoot"
EYE_TARGETS = {"L": "EyeTarget_L", "R": "EyeTarget_R"}
EYE_OUTPUTS = {"L": "Eye_L", "R": "Eye_R"}
EYE_CENTER = "EyeCenterPos"
EYE_COLLECTION = "CTRL_Eye"
EYE_INTERNAL_COLLECTION = "MCH_Eye"
EYE_HEAD_PROPERTY = "kai_eye_head_bone"
EYE_HEAD_STORAGE_PROPERTY = "_kai_eye_head_bone"
FACE_FOLLOW_PROPERTY = "kai_face_head_follow"
FACE_MAPPING_PROPERTY = "kai_face_shape_key_mapping"
FACE_TARGET_PROPERTY = "kai_face_target_object"  # Legacy Phase 1 single target.
FACE_TARGETS_PROPERTY = "kai_face_mesh_mapping"
FACE_MAPPING_SCHEMA_VERSION = 2
FACE_MAPPING_NONE = "__KAI_NONE__"

DEFAULT_EYE_IK_LIMITS = {
    "x": (-radians(30.0), radians(30.0)),
    "y": (0.0, 0.0),
    "z": (-radians(35.0), radians(35.0)),
}

EYE_UI_COLOR = {
    "normal": (1.0, 1.0, 0.0),
    "select": (1.0, 1.0, 0.0),
    "active": (0.0, 1.0, 1.0),
}

FACE_UI_COLORS = {
    "FACE": (1.0, 0.08, 0.03),
    "BROW": (0.05, 0.9, 0.08),
    "EYE": (1.0, 0.03, 0.03),
    "MOUTH": (0.05, 0.2, 1.0),
}


# Mapping IDs are the stable Kai contract.  Values are merely Phase 1 defaults
# and are stored per rig so a later Mapping UI can replace them safely.
DEFAULT_FACE_SHAPE_KEY_MAPPING = {
    "brow_up_l": "Brow_Up_L",
    "brow_down_l": "Brow_Down_L",
    "brow_angry_l": "Brow_Angry_L",
    "brow_sad_l": "Brow_Sad_L",
    "brow_smile_l": "Brow_Smile_L",
    "brow_serious_l": "Brow_Serious_L",
    "brow_up_r": "Brow_Up_R",
    "brow_down_r": "Brow_Down_R",
    "brow_angry_r": "Brow_Angry_R",
    "brow_sad_r": "Brow_Sad_R",
    "brow_smile_r": "Brow_Smile_R",
    "brow_serious_r": "Brow_Serious_R",
    "eye_close_l": "Eyelid_Close_L",
    "eye_smile_l": "Eyelid_Smile_L",
    "eye_surprise_l": "Eyelid_Surprise_L",
    "eye_jito_l": "Eyelid_Jito_L",
    "eye_angry_l": "Eyelid_Angry_L",
    "eye_sad_l": "Eyelid_Sad_L",
    "eye_squint_l": "Eyelid_Squint_L",
    "eye_outer_down_l": "EyeOuterCorner_Down_L",
    "eye_close_r": "Eyelid_Close_R",
    "eye_smile_r": "Eyelid_Smile_R",
    "eye_surprise_r": "Eyelid_Surprise_R",
    "eye_jito_r": "Eyelid_Jito_R",
    "eye_angry_r": "Eyelid_Angry_R",
    "eye_sad_r": "Eyelid_Sad_R",
    "eye_squint_r": "Eyelid_Squint_R",
    "eye_outer_down_r": "EyeOuterCorner_Down_R",
    "mouth_left": "MouthLeft",
    "mouth_right": "MouthRight",
    "mouth_up": "MouthUp",
    "mouth_down": "MouthDown",
    "mouth_spread_l": "Mouth_Spread_L",
    "mouth_narrow_l": "Mouth_Narrow_L",
    "mouth_corner_up_l": "Mouth_CornerUp_L",
    "mouth_corner_down_l": "Mouth_CornerDown_L",
    "mouth_spread_r": "Mouth_Spread_R",
    "mouth_narrow_r": "Mouth_Narrow_R",
    "mouth_corner_up_r": "Mouth_CornerUp_R",
    "mouth_corner_down_r": "Mouth_CornerDown_R",
}

FACE_MAPPING_CATEGORIES = (
    (
        "Brow",
        "kai_face_mapping_expand_brow",
        (
            ("brow_up_l", "Brow Up L"),
            ("brow_up_r", "Brow Up R"),
            ("brow_down_l", "Brow Down L"),
            ("brow_down_r", "Brow Down R"),
            ("brow_angry_l", "Brow Angry L"),
            ("brow_angry_r", "Brow Angry R"),
            ("brow_sad_l", "Brow Sad L"),
            ("brow_sad_r", "Brow Sad R"),
            ("brow_smile_l", "Brow Smile L"),
            ("brow_smile_r", "Brow Smile R"),
            ("brow_serious_l", "Brow Serious L"),
            ("brow_serious_r", "Brow Serious R"),
        ),
    ),
    (
        "Eyelid / Eye",
        "kai_face_mapping_expand_eye",
        (
            ("eye_close_l", "Eyelid Close L"),
            ("eye_close_r", "Eyelid Close R"),
            ("eye_smile_l", "Eyelid Smile L"),
            ("eye_smile_r", "Eyelid Smile R"),
            ("eye_angry_l", "Eyelid Angry L"),
            ("eye_angry_r", "Eyelid Angry R"),
            ("eye_sad_l", "Eyelid Sad L"),
            ("eye_sad_r", "Eyelid Sad R"),
            ("eye_surprise_l", "Eyelid Surprise L"),
            ("eye_surprise_r", "Eyelid Surprise R"),
            ("eye_jito_l", "Eyelid Jito L"),
            ("eye_jito_r", "Eyelid Jito R"),
            ("eye_squint_l", "Eyelid Squint L"),
            ("eye_squint_r", "Eyelid Squint R"),
            ("eye_outer_down_l", "Eye Outer Corner Down L"),
            ("eye_outer_down_r", "Eye Outer Corner Down R"),
        ),
    ),
    (
        "Mouth",
        "kai_face_mapping_expand_mouth",
        (
            ("mouth_left", "Mouth Left"),
            ("mouth_right", "Mouth Right"),
            ("mouth_up", "Mouth Up"),
            ("mouth_down", "Mouth Down"),
            ("mouth_corner_up_l", "Mouth Corner Up L"),
            ("mouth_corner_up_r", "Mouth Corner Up R"),
            ("mouth_corner_down_l", "Mouth Corner Down L"),
            ("mouth_corner_down_r", "Mouth Corner Down R"),
            ("mouth_spread_l", "Mouth Spread L"),
            ("mouth_spread_r", "Mouth Spread R"),
            ("mouth_narrow_l", "Mouth Narrow L"),
            ("mouth_narrow_r", "Mouth Narrow R"),
        ),
    ),
)


# A controller declaration is reusable by the future simple-slider generator.
# axes contains normalized UI ranges; missing axes are locked at zero.
FACE_CONTROLLERS = (
    {"name": "Face_BrowUpDown_L", "parent": "Face_BrowRoot_L", "pos": (4.1, 0.0, 5.5), "length": 0.6, "axes": {1: (-1.0, 1.0)}, "shape": "cs_square", "display_scale": (0.6, 1.0, 0.025)},
    {"name": "Face_BrowExp_L", "parent": "Face_BrowUpDown_L", "pos": (4.1, 0.0, 5.5), "length": 0.3, "axes": {0: (-1.0, 1.0), 1: (-1.0, 1.0)}, "shape": "cs_sphere", "display_scale": 0.05},
    {"name": "Face_BrowUpDown_R", "parent": "Face_BrowRoot_R", "pos": (1.9, 0.0, 5.5), "length": 0.6, "axes": {1: (-1.0, 1.0)}, "shape": "cs_square", "display_scale": (0.6, 1.0, 0.025)},
    {"name": "Face_BrowExp_R", "parent": "Face_BrowUpDown_R", "pos": (1.9, 0.0, 5.5), "length": 0.3, "axes": {0: (-1.0, 1.0), 1: (-1.0, 1.0)}, "shape": "cs_sphere", "display_scale": 0.05},
    {"name": "Face_EyeExp_L", "parent": "Face_EyeRoot_L", "pos": (4.1, 0.0, 3.1), "length": 0.3, "axes": {0: (-1.0, 1.0), 1: (-1.0, 1.0)}, "shape": "cs_sphere", "display_scale": 0.05},
    {"name": "Face_EyeMove_L", "parent": "Face_EyeRoot_L", "pos": (4.1, 0.0, 3.1), "length": 0.6, "axes": {1: (-0.5, 0.5)}, "shape": "cs_circle", "display_scale": (0.43, 1.0, 0.43)},
    {"name": "Face_EyeClose_L", "parent": "Face_EyeMove_L", "pos": (4.1, 0.0, 3.5), "length": 0.6, "axes": {1: (-1.0, 0.0)}, "shape": "cs_square", "display_scale": (0.6, 1.0, 0.025)},
    {"name": "Face_EyeCloseToSmile_L", "parent": "Face_EyeClose_L", "pos": (3.6, 0.0, 3.5), "length": 0.6, "axes": {0: (0.0, 1.0)}, "shape": "cs_switch_Arrow", "display_scale": (0.25, 0.25, 1.0), "shape_rotation": (0.0, 0.0, 90.0)},
    {"name": "Face_EyeExp_R", "parent": "Face_EyeRoot_R", "pos": (1.9, 0.0, 3.1), "length": 0.3, "axes": {0: (-1.0, 1.0), 1: (-1.0, 1.0)}, "shape": "cs_sphere", "display_scale": 0.05},
    {"name": "Face_EyeMove_R", "parent": "Face_EyeRoot_R", "pos": (1.9, 0.0, 3.1), "length": 0.6, "axes": {1: (-0.5, 0.5)}, "shape": "cs_circle", "display_scale": (0.43, 1.0, 0.43)},
    {"name": "Face_EyeClose_R", "parent": "Face_EyeMove_R", "pos": (1.9, 0.0, 3.5), "length": 0.6, "axes": {1: (-1.0, 0.0)}, "shape": "cs_square", "display_scale": (0.6, 1.0, 0.025)},
    {"name": "Face_EyeCloseToSmile_R", "parent": "Face_EyeClose_R", "pos": (2.4, 0.0, 3.5), "length": 0.6, "axes": {0: (-1.0, 0.0)}, "shape": "cs_switch_Arrow", "display_scale": (0.25, 0.25, 1.0), "shape_rotation": (0.0, 0.0, 90.0)},
    {"name": "Face_MouthPosition", "parent": "Face_MouthRoot", "pos": (3.0, 0.0, 0.4), "length": 0.6, "axes": {0: (-1.0, 1.0), 1: (-1.0, 1.0)}, "shape": "cs_circle", "display_scale": (0.9, 1.0, 0.43)},
    {"name": "Face_MouthCorner_L", "parent": "Face_MouthPosition", "pos": (3.9, 0.0, 0.4), "length": 0.3, "axes": {0: (-1.0, 1.0), 1: (-1.0, 1.0)}, "shape": "cs_sphere", "display_scale": 0.05},
    {"name": "Face_MouthCorner_R", "parent": "Face_MouthPosition", "pos": (2.1, 0.0, 0.4), "length": 0.3, "axes": {0: (-1.0, 1.0), 1: (-1.0, 1.0)}, "shape": "cs_sphere", "display_scale": 0.05},
)

FACE_ANCHORS = (
    (FACE_ROOT, None, (3.0, 0.0, 3.0)),
    ("Face_EyeRoot_L", FACE_ROOT, (4.1, 0.0, 3.1)),
    ("Face_EyeRoot_R", FACE_ROOT, (1.9, 0.0, 3.1)),
    ("Face_BrowRoot_L", FACE_ROOT, (4.1, 0.0, 5.5)),
    ("Face_BrowRoot_R", FACE_ROOT, (1.9, 0.0, 5.5)),
    ("Face_MouthRoot", FACE_ROOT, (3.0, 0.0, 0.4)),
)

# The Phase 1.1 layout is authored in normalized controller units around this
# point.  One parent scale converts every position, shape, and controller
# movement into character-sized armature-local units.
FACE_LAYOUT_ORIGIN = Vector((3.0, 0.0, 3.0))
FACE_LAYOUT_EYE_HALF_WIDTH = 1.1
FACE_EYE_HALF_WIDTH_PER_HEAD = 0.18

FACE_PART_ROOT_SHAPES = {
    "Face_BrowRoot_L": ("cs_square", (0.61, 1.0, 0.61)),
    "Face_BrowRoot_R": ("cs_square", (0.61, 1.0, 0.61)),
    "Face_EyeRoot_L": ("cs_square", (0.61, 1.0, 0.61)),
    "Face_EyeRoot_R": ("cs_square", (0.61, 1.0, 0.61)),
    "Face_MouthRoot": ("cs_square", (1.28, 1.0, 0.63)),
}

# Output declarations reference stable Mapping IDs, never concrete Shape Key names.
FACE_OUTPUTS = []
for _side in ("L", "R"):
    _s = _side.lower()
    _x_positive = "angry" if _side == "L" else "sad"
    _x_negative = "sad" if _side == "L" else "angry"
    FACE_OUTPUTS.extend((
        (f"brow_up_{_s}", f"Face_BrowUpDown_{_side}", "LOC_Y", "v"),
        (f"brow_down_{_s}", f"Face_BrowUpDown_{_side}", "LOC_Y", "-v"),
        (f"brow_{_x_positive}_{_s}", f"Face_BrowExp_{_side}", "LOC_X", "v"),
        (f"brow_{_x_negative}_{_s}", f"Face_BrowExp_{_side}", "LOC_X", "-v"),
        (f"brow_smile_{_s}", f"Face_BrowExp_{_side}", "LOC_Y", "v"),
        (f"brow_serious_{_s}", f"Face_BrowExp_{_side}", "LOC_Y", "-v"),
    ))

    _blend_sign = 1.0 if _side == "L" else -1.0
    FACE_OUTPUTS.extend((
        (f"eye_close_{_s}", f"Face_EyeClose_{_side}", "LOC_Y", f"-v*(1.0-({_blend_sign})*blend)", f"Face_EyeCloseToSmile_{_side}", "LOC_X"),
        (f"eye_smile_{_s}", f"Face_EyeClose_{_side}", "LOC_Y", f"-v*({_blend_sign})*blend", f"Face_EyeCloseToSmile_{_side}", "LOC_X"),
        (f"eye_surprise_{_s}", f"Face_EyeExp_{_side}", "LOC_Y", "v*(1.0+close)", f"Face_EyeClose_{_side}", "LOC_Y", "close"),
        (f"eye_jito_{_s}", f"Face_EyeExp_{_side}", "LOC_Y", "-v*(1.0+close)", f"Face_EyeClose_{_side}", "LOC_Y", "close"),
        (f"eye_{_x_positive}_{_s}", f"Face_EyeExp_{_side}", "LOC_X", "v*(1.0+close)", f"Face_EyeClose_{_side}", "LOC_Y", "close"),
        (f"eye_{_x_negative}_{_s}", f"Face_EyeExp_{_side}", "LOC_X", "-v*(1.0+close)", f"Face_EyeClose_{_side}", "LOC_Y", "close"),
        (f"eye_squint_{_s}", f"Face_EyeMove_{_side}", "LOC_Y", "2.0*v*(1.0+close)", f"Face_EyeClose_{_side}", "LOC_Y", "close"),
        (f"eye_outer_down_{_s}", f"Face_EyeMove_{_side}", "LOC_Y", "-2.0*v*(1.0+close)", f"Face_EyeClose_{_side}", "LOC_Y", "close"),
    ))

FACE_OUTPUTS.extend((
    ("mouth_left", "Face_MouthPosition", "LOC_X", "v"),
    ("mouth_right", "Face_MouthPosition", "LOC_X", "-v"),
    ("mouth_up", "Face_MouthPosition", "LOC_Y", "v"),
    ("mouth_down", "Face_MouthPosition", "LOC_Y", "-v"),
))
for _side in ("L", "R"):
    _s = _side.lower()
    _positive = "spread" if _side == "L" else "narrow"
    _negative = "narrow" if _side == "L" else "spread"
    FACE_OUTPUTS.extend((
        (f"mouth_{_positive}_{_s}", f"Face_MouthCorner_{_side}", "LOC_X", "v"),
        (f"mouth_{_negative}_{_s}", f"Face_MouthCorner_{_side}", "LOC_X", "-v"),
        (f"mouth_corner_up_{_s}", f"Face_MouthCorner_{_side}", "LOC_Y", "v"),
        (f"mouth_corner_down_{_s}", f"Face_MouthCorner_{_side}", "LOC_Y", "-v"),
    ))


def _active_armature(context):
    obj = context.active_object
    return obj if obj is not None and obj.type == "ARMATURE" else None


def _set_active_object(rig):
    if bpy.context.active_object and bpy.context.active_object.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")
    bpy.ops.object.select_all(action="DESELECT")
    rig.select_set(True)
    bpy.context.view_layer.objects.active = rig


def _ensure_collection(rig, name):
    return rig.data.collections.get(name) or rig.data.collections.new(name)


def _create_edit_bone(rig, name, head, length=0.1, parent=None, collection=None):
    bone = rig.data.edit_bones.new(name)
    bone.head = Vector(head)
    bone.tail = Vector((head[0], head[1], head[2] + length))
    bone.use_deform = False
    if parent:
        bone.parent = rig.data.edit_bones.get(parent)
    if collection:
        set_bone_collection(rig, bone, collection)
    bone["kai_module"] = FACE_MODULE_ID if "Face" in name else EYE_MODULE_ID
    return bone


def _lock_pose_bone(pbone, used_location_axes=()):
    pbone.lock_location = tuple(index not in used_location_axes for index in range(3))
    pbone.lock_rotation = (True, True, True)
    pbone.lock_rotation_w = True
    pbone.lock_scale = (True, True, True)
    pbone.rotation_mode = "QUATERNION"


def _set_front_facing_custom_shape(
    pbone,
    shape_name,
    scale,
    rotation=(90.0, 0.0, 0.0),
):
    """Display planar controls in the controller's local X/Y animation plane."""
    set_bone_custom_shape(pbone, shape_name)
    pbone.use_custom_shape_bone_size = False
    pbone.custom_shape_rotation_euler = tuple(radians(value) for value in rotation)
    if isinstance(scale, (int, float)):
        scale = (scale, scale, scale)
    pbone.custom_shape_scale_xyz = scale


def _finish_custom_shape_setup(rig):
    """Keep source objects out of the viewport while their bone shapes remain visible."""
    group = get_object("cs_grp")
    if group is not None:
        for child in group.children:
            hide_object(child)
        hide_object(group)
    rig.data.show_bone_custom_shapes = True


def _face_ui_region(name):
    if "Brow" in name:
        return "BROW"
    if "Eye" in name:
        return "EYE"
    if "Mouth" in name:
        return "MOUTH"
    return "FACE"


def _set_face_ui_color(pbone, region=None):
    color = FACE_UI_COLORS[region or _face_ui_region(pbone.name)]
    pbone.color.palette = "CUSTOM"
    pbone.color.custom.normal = color
    pbone.color.custom.select = tuple(min(channel + 0.18, 1.0) for channel in color)
    pbone.color.custom.active = tuple(min(channel + 0.32, 1.0) for channel in color)


def _set_eye_ui_color(pbone):
    pbone.color.palette = "CUSTOM"
    pbone.color.custom.normal = EYE_UI_COLOR["normal"]
    pbone.color.custom.select = EYE_UI_COLOR["select"]
    pbone.color.custom.active = EYE_UI_COLOR["active"]


def _snapshot_pose_transform(pbone):
    if pbone is None:
        return None
    return {
        "location": pbone.location.copy(),
        "rotation_mode": pbone.rotation_mode,
        "rotation_quaternion": pbone.rotation_quaternion.copy(),
        "rotation_euler": pbone.rotation_euler.copy(),
        "rotation_axis_angle": tuple(pbone.rotation_axis_angle),
        "scale": pbone.scale.copy(),
    }


def _restore_pose_transform(pbone, snapshot):
    if not snapshot:
        return
    pbone.location = snapshot["location"]
    pbone.rotation_mode = snapshot["rotation_mode"]
    pbone.rotation_quaternion = snapshot["rotation_quaternion"]
    pbone.rotation_euler = snapshot["rotation_euler"]
    pbone.rotation_axis_angle = snapshot["rotation_axis_angle"]
    pbone.scale = snapshot["scale"]


def _snapshot_eye_rebuild_data(rig, head_name):
    if rig.data.get("kai_eye_head", "") != head_name:
        return {}, {}
    bones = {}
    limits = {}
    for name in (EYE_TARGET_ROOT, *EYE_TARGETS.values(), *EYE_OUTPUTS.values()):
        bone = (
            rig.data.edit_bones.get(name)
            if rig.mode == "EDIT"
            else rig.data.bones.get(name)
        )
        if bone is None or bone.get("kai_module") != EYE_MODULE_ID:
            continue
        bones[name] = {
            "head": (bone.head if rig.mode == "EDIT" else bone.head_local).copy(),
            "tail": (bone.tail if rig.mode == "EDIT" else bone.tail_local).copy(),
        }
    for side, name in EYE_OUTPUTS.items():
        pbone = rig.pose.bones.get(name)
        if pbone is None:
            continue
        limits[side] = {
            axis: (
                getattr(pbone, f"use_ik_limit_{axis}"),
                getattr(pbone, f"ik_min_{axis}"),
                getattr(pbone, f"ik_max_{axis}"),
            )
            for axis in "xyz"
        }
    return bones, limits


def _snapshot_face_rebuild_bones(rig):
    root = (
        rig.data.edit_bones.get(FACE_ROOT)
        if rig.mode == "EDIT"
        else rig.data.bones.get(FACE_ROOT)
    )
    if root is None or root.get("kai_module") != FACE_MODULE_ID:
        return {}
    snapshots = {}
    names = [name for name, _parent, _position in FACE_ANCHORS]
    names.extend(spec["name"] for spec in FACE_CONTROLLERS)
    for name in names:
        bone = (
            rig.data.edit_bones.get(name)
            if rig.mode == "EDIT"
            else rig.data.bones.get(name)
        )
        if bone is None or bone.get("kai_module") != FACE_MODULE_ID:
            continue
        snapshots[name] = {
            "head": (bone.head if rig.mode == "EDIT" else bone.head_local).copy(),
            "tail": (bone.tail if rig.mode == "EDIT" else bone.tail_local).copy(),
        }
    return snapshots


def _face_layout_basis(rig):
    mapped_name = rig.data.get("kai_head_name", "")
    head = rig.data.bones.get(mapped_name) if mapped_name else None
    if head is None:
        head = rig.data.bones.get("Head") or rig.data.bones.get("Ctrl_Head")
    if head is None:
        raise RuntimeError("Face Module requires a valid Head bone in Reference Mapping")

    head_length = max(head.length, 1.0e-6)
    local_z = head.matrix_local.to_3x3().col[2].normalized()
    face_center = head.head_local + (head.tail_local - head.head_local) * 0.42
    face_center += local_z * head_length * 0.1
    base_scale = (
        head_length
        * FACE_EYE_HALF_WIDTH_PER_HEAD
        / FACE_LAYOUT_EYE_HALF_WIDTH
    )
    return face_center, base_scale


def _face_layout_position(position, center):
    return center + Vector(position) - FACE_LAYOUT_ORIGIN


def _add_local_limits(pbone, axes):
    constraint = pbone.constraints.new("LIMIT_LOCATION")
    constraint.name = "KAI Normalized Location"
    constraint.owner_space = "LOCAL"
    constraint.use_transform_limit = True
    for index in range(3):
        low, high = axes.get(index, (0.0, 0.0))
        axis = "xyz"[index]
        setattr(constraint, f"use_min_{axis}", True)
        setattr(constraint, f"use_max_{axis}", True)
        setattr(constraint, f"min_{axis}", low)
        setattr(constraint, f"max_{axis}", high)


def _shape_keys(mesh):
    return getattr(getattr(mesh, "data", None), "shape_keys", None)


def _shape_key_names(mesh):
    keys = _shape_keys(mesh)
    if keys is None:
        return set()
    return {
        key.name
        for key in keys.key_blocks
        if key != keys.reference_key and key.name != "Basis"
    }


def get_face_mapping(rig):
    mapping = dict(DEFAULT_FACE_SHAPE_KEY_MAPPING)
    raw = rig.data.get(FACE_MAPPING_PROPERTY, "")
    if raw:
        try:
            stored = json.loads(raw)
            if isinstance(stored, dict):
                mapping.update({str(k): str(v) for k, v in stored.items()})
        except (TypeError, ValueError):
            pass
    return mapping


def get_face_mesh_mapping(rig):
    """Return the extensible Object -> channel -> Shape Key mapping payload."""
    raw = rig.data.get(FACE_TARGETS_PROPERTY, "")
    if raw:
        try:
            payload = json.loads(raw)
            if isinstance(payload, dict) and isinstance(payload.get("targets"), list):
                return _normalize_face_mesh_mapping(rig, payload)
        except (TypeError, ValueError):
            pass
    return {"schema_version": FACE_MAPPING_SCHEMA_VERSION, "targets": []}


def _detected_face_mapping(mesh, candidates=None):
    available = _shape_key_names(mesh)
    candidates = candidates or DEFAULT_FACE_SHAPE_KEY_MAPPING
    return {
        channel: candidate if candidate and candidate in available else ""
        for channel, default_name in DEFAULT_FACE_SHAPE_KEY_MAPPING.items()
        for candidate in (str(candidates.get(channel, default_name)),)
    }


def _normalize_face_mesh_mapping(rig, payload):
    """Migrate v0.6.3 mappings without preserving its nonexistent defaults."""
    try:
        source_version = int(payload.get("schema_version", 1) or 1)
    except (TypeError, ValueError):
        source_version = 1
    fallback = get_face_mapping(rig)
    targets = []
    seen = set()
    for source in payload.get("targets", []):
        if not isinstance(source, dict):
            continue
        object_name = str(source.get("object", ""))
        if not object_name or object_name in seen:
            continue
        seen.add(object_name)
        mesh = bpy.data.objects.get(object_name)
        stored = source.get("channels", {})
        stored = stored if isinstance(stored, dict) else {}
        if source_version < FACE_MAPPING_SCHEMA_VERSION:
            available = _shape_key_names(mesh)
            channels = {}
            for channel, default_name in DEFAULT_FACE_SHAPE_KEY_MAPPING.items():
                value = str(stored.get(channel, fallback.get(channel, default_name)) or "")
                channels[channel] = value if value != "Basis" and value in available else ""
        else:
            channels = {
                channel: str(stored.get(channel, "") or "")
                for channel in DEFAULT_FACE_SHAPE_KEY_MAPPING
            }
        targets.append({"object": object_name, "channels": channels})
    return {"schema_version": FACE_MAPPING_SCHEMA_VERSION, "targets": targets}


def _find_face_mapping_target(payload, object_name):
    return next(
        (target for target in payload["targets"] if target.get("object") == object_name),
        None,
    )


def _write_face_mesh_mapping(rig, payload):
    normalized = _normalize_face_mesh_mapping(rig, payload)
    rig.data[FACE_TARGETS_PROPERTY] = json.dumps(normalized, sort_keys=True)
    return normalized


def ensure_face_mesh_mapping(rig, mesh):
    payload = get_face_mesh_mapping(rig)
    target = _find_face_mapping_target(payload, mesh.name)
    if target is None:
        target = {
            "object": mesh.name,
            "channels": _detected_face_mapping(mesh, get_face_mapping(rig)),
        }
        payload["targets"].append(target)
    payload = _write_face_mesh_mapping(rig, payload)
    return dict(_find_face_mapping_target(payload, mesh.name)["channels"])


def set_face_channel_mapping(rig, mesh, channel, shape_name):
    if channel not in DEFAULT_FACE_SHAPE_KEY_MAPPING:
        raise ValueError(f"Unknown Kai Facial Channel: {channel}")
    shape_name = str(shape_name or "")
    if shape_name == "Basis":
        raise ValueError("Basis cannot be used as a Facial mapping target")
    payload = get_face_mesh_mapping(rig)
    target = _find_face_mapping_target(payload, mesh.name)
    if target is None:
        ensure_face_mesh_mapping(rig, mesh)
        payload = get_face_mesh_mapping(rig)
        target = _find_face_mapping_target(payload, mesh.name)
    target["channels"][channel] = shape_name
    _write_face_mesh_mapping(rig, payload)


def auto_detect_face_mapping(rig, mesh):
    mapping = ensure_face_mesh_mapping(rig, mesh)
    detected = _detected_face_mapping(mesh, get_face_mapping(rig))
    changed = 0
    for channel, shape_name in detected.items():
        if not mapping.get(channel) and shape_name:
            mapping[channel] = shape_name
            changed += 1
    _store_face_mesh_mapping(rig, ((mesh, mapping),))
    return changed


def _mapping_for_mesh(rig, mesh, fallback):
    payload = get_face_mesh_mapping(rig)
    target = _find_face_mapping_target(payload, mesh.name)
    if target is not None:
        return dict(target["channels"])
    return _detected_face_mapping(mesh, fallback)


def _store_face_mesh_mapping(rig, mesh_mappings):
    payload = get_face_mesh_mapping(rig)
    for mesh, mapping in mesh_mappings:
        target = _find_face_mapping_target(payload, mesh.name)
        if target is None:
            target = {"object": mesh.name, "channels": {}}
            payload["targets"].append(target)
        target["channels"] = {
            channel: str(mapping.get(channel, "") or "")
            for channel in DEFAULT_FACE_SHAPE_KEY_MAPPING
        }
    _write_face_mesh_mapping(rig, payload)


def _is_kai_face_driver(fcurve, rig=None):
    variables = [
        variable
        for variable in fcurve.driver.variables
        if variable.name.startswith("kai_face_")
    ]
    if not variables:
        return False
    if rig is None:
        return True
    return any(
        target.id == rig
        for variable in variables
        for target in variable.targets
    )


def _find_driver(shape_keys, data_path):
    animation_data = shape_keys.animation_data
    if animation_data is None:
        return None
    return animation_data.drivers.find(data_path)


def _driver_path(shape_name):
    escaped = bpy.utils.escape_identifier(shape_name)
    return f'key_blocks["{escaped}"].value'


def _add_transform_variable(driver, name, rig, bone_name, transform_type):
    variable = driver.variables.new()
    variable.name = name
    variable.type = "TRANSFORMS"
    target = variable.targets[0]
    target.id = rig
    target.bone_target = bone_name
    target.transform_type = transform_type
    target.transform_space = "LOCAL_SPACE"


def _add_shape_driver(shape_keys, shape_name, rig, spec):
    path = _driver_path(shape_name)
    old = _find_driver(shape_keys, path)
    if old is not None:
        shape_keys.driver_remove(path)
    fcurve = shape_keys.driver_add(path)
    driver = fcurve.driver
    driver.type = "SCRIPTED"
    while driver.variables:
        driver.variables.remove(driver.variables[0])
    _add_transform_variable(driver, "kai_face_v", rig, spec[1], spec[2])
    expression = spec[3].replace("v", "kai_face_v")
    if len(spec) >= 7:
        extra_name = spec[6]
        _add_transform_variable(driver, f"kai_face_{extra_name}", rig, spec[4], spec[5])
        expression = expression.replace(extra_name, f"kai_face_{extra_name}")
    elif len(spec) >= 6:
        _add_transform_variable(driver, "kai_face_blend", rig, spec[4], spec[5])
        expression = expression.replace("blend", "kai_face_blend")
    driver.expression = f"min(max({expression}, 0.0), 1.0)"


def _remove_face_drivers(rig, meshes=None):
    targets = []
    for mesh in meshes or ():
        if mesh is not None and mesh not in targets:
            targets.append(mesh)
    stored_name = rig.data.get(FACE_TARGET_PROPERTY, "")
    stored = bpy.data.objects.get(stored_name) if stored_name else None
    if stored is not None and stored not in targets:
        targets.append(stored)
    for candidate in bpy.data.objects:
        if candidate.type == "MESH" and candidate not in targets:
            targets.append(candidate)
    removed = 0
    for target in targets:
        keys = _shape_keys(target)
        if keys is None or keys.animation_data is None:
            continue
        for fcurve in list(keys.animation_data.drivers):
            if _is_kai_face_driver(fcurve, rig):
                keys.driver_remove(fcurve.data_path, fcurve.array_index)
                removed += 1
    return removed


def _remove_face_follow_driver(rig):
    if rig.animation_data is None:
        return 0
    tokens = {
        f'pose.bones["{root_name}"].constraints["KAI Face Head Follow"].influence'
        for root_name in (FACE_ROOT, LEGACY_FACE_ROOT)
    }
    removed = 0
    for fcurve in list(rig.animation_data.drivers):
        if fcurve.data_path in tokens:
            rig.driver_remove(fcurve.data_path, fcurve.array_index)
            removed += 1
    return removed


def _remove_module_bones(rig, module_id):
    names = [bone.name for bone in rig.data.bones if bone.get("kai_module") == module_id]
    if not names:
        return 0
    _set_active_object(rig)
    bpy.ops.object.mode_set(mode="EDIT")
    for name in names:
        bone = rig.data.edit_bones.get(name)
        if bone is not None:
            rig.data.edit_bones.remove(bone)
    bpy.ops.object.mode_set(mode="OBJECT")
    return len(names)


def _remove_empty_collection(rig, name):
    collection = rig.data.collections.get(name)
    if collection is not None and len(collection.bones) == 0:
        rig.data.collections.remove(collection)


def remove_face_module(rig, meshes=None):
    drivers = _remove_face_drivers(rig, meshes)
    drivers += _remove_face_follow_driver(rig)
    bones = _remove_module_bones(rig, FACE_MODULE_ID)
    _remove_empty_collection(rig, FACE_COLLECTION)
    _remove_empty_collection(rig, FACE_ROOT_COLLECTION)
    _remove_empty_collection(rig, FACE_ANCHOR_COLLECTION)
    for name in (FACE_TARGET_PROPERTY,):
        if name in rig.data:
            del rig.data[name]
    if "kai_face_module" in rig.data:
        del rig.data["kai_face_module"]
    return bones, drivers


def remove_eye_module(rig):
    # Migration cleanup for rigs generated before the Direct Bone Adapter was removed.
    for pbone in rig.pose.bones:
        legacy = pbone.constraints.get("KAI Eye Direct Adapter")
        if legacy is not None:
            pbone.constraints.remove(legacy)
    bones = _remove_module_bones(rig, EYE_MODULE_ID)
    _remove_empty_collection(rig, EYE_COLLECTION)
    _remove_empty_collection(rig, EYE_INTERNAL_COLLECTION)
    if "kai_eye_module" in rig.data:
        del rig.data["kai_eye_module"]
    for name in ("kai_eye_source_l", "kai_eye_source_r"):
        if name in rig.data:
            del rig.data[name]
    return bones


def remove_all_modules(rig):
    face_bones, drivers = remove_face_module(rig)
    eye_bones = remove_eye_module(rig)
    return face_bones + eye_bones, drivers


def _module_state(rig, module_id, bone_names):
    marker_name = "kai_face_module" if module_id == FACE_MODULE_ID else "kai_eye_module"
    marker_valid = rig.data.get(marker_name) == module_id
    matching = sum(
        rig.data.bones.get(name) is not None
        and rig.data.bones[name].get("kai_module") == module_id
        for name in bone_names
    )
    if marker_valid and matching == len(bone_names):
        return "GENERATED"
    if marker_valid or matching:
        return "PARTIAL"
    return "NOT_GENERATED"


def face_module_state(rig):
    names = [name for name, _parent, _position in FACE_ANCHORS]
    names.extend(spec["name"] for spec in FACE_CONTROLLERS)
    return _module_state(rig, FACE_MODULE_ID, names)


def eye_module_state(rig):
    names = [EYE_TARGET_ROOT, EYE_CENTER, *EYE_TARGETS.values(), *EYE_OUTPUTS.values()]
    return _module_state(rig, EYE_MODULE_ID, names)


def _face_mapping_counts(rig, meshes):
    fallback = get_face_mapping(rig)
    missing = 0
    unassigned = 0
    for mesh in meshes:
        if mesh is None or mesh.type != "MESH":
            continue
        mapping = _mapping_for_mesh(rig, mesh, fallback)
        names = _shape_key_names(mesh)
        for channel in DEFAULT_FACE_SHAPE_KEY_MAPPING:
            shape_name = mapping.get(channel, "")
            if not shape_name:
                unassigned += 1
            elif shape_name not in names:
                missing += 1
    return missing, unassigned


def _validate_face_targets(rig, meshes, fallback_mapping):
    valid_meshes = []
    seen = set()
    available = {}
    conflicts = []
    for mesh in meshes:
        if mesh is None or mesh.name in seen:
            continue
        seen.add(mesh.name)
        if mesh.type != "MESH":
            continue
        valid_meshes.append(mesh)
        mapping = _mapping_for_mesh(rig, mesh, fallback_mapping)
        available[mesh.name] = []
        keys = _shape_keys(mesh)
        if keys is None:
            continue
        for spec in FACE_OUTPUTS:
            shape_name = mapping.get(spec[0], "")
            if not shape_name or keys.key_blocks.get(shape_name) is None:
                continue
            available[mesh.name].append(shape_name)
            old = _find_driver(keys, _driver_path(shape_name))
            if old is not None and not _is_kai_face_driver(old, rig):
                conflicts.append(f"{mesh.name}.{shape_name}")
    if conflicts:
        raise RuntimeError("Existing non-Kai drivers: " + ", ".join(sorted(set(conflicts))))
    if not valid_meshes:
        raise RuntimeError("Add at least one mesh to Face Meshes")
    return valid_meshes, available


def _validate_module_bone_names(rig, module_id, names):
    conflicts = [
        name
        for name in names
        if rig.data.bones.get(name) is not None
        and rig.data.bones[name].get("kai_module") != module_id
    ]
    if conflicts:
        raise RuntimeError(
            "Bone names already used by non-Kai module data: "
            + ", ".join(conflicts)
        )


def generate_face_module(rig, meshes):
    mapping = get_face_mapping(rig)
    previous_bones = _snapshot_face_rebuild_bones(rig)
    face_center, base_scale = _face_layout_basis(rig)
    root_transforms = {
        name: _snapshot_pose_transform(rig.pose.bones.get(name))
        for name, _parent, _position in FACE_ANCHORS
    }
    valid_meshes, available = _validate_face_targets(rig, meshes, mapping)
    mesh_mappings = [
        (mesh, _mapping_for_mesh(rig, mesh, mapping))
        for mesh in valid_meshes
    ]
    _validate_module_bone_names(
        rig,
        FACE_MODULE_ID,
        [name for name, _parent, _position in FACE_ANCHORS]
        + [spec["name"] for spec in FACE_CONTROLLERS],
    )
    remove_face_module(rig, valid_meshes)
    _set_active_object(rig)
    _ensure_collection(rig, FACE_COLLECTION)
    _ensure_collection(rig, FACE_ROOT_COLLECTION)

    bpy.ops.object.mode_set(mode="EDIT")
    for name, parent, position in FACE_ANCHORS:
        _create_edit_bone(
            rig,
            name,
            _face_layout_position(position, face_center),
            0.1,
            parent,
            FACE_ROOT_COLLECTION,
        )
    for spec in FACE_CONTROLLERS:
        _create_edit_bone(
            rig,
            spec["name"],
            _face_layout_position(spec["pos"], face_center),
            spec["length"],
            spec["parent"],
            FACE_COLLECTION,
        )
    for name, snapshot in previous_bones.items():
        bone = rig.data.edit_bones.get(name)
        if bone is not None:
            bone.head = snapshot["head"]
            bone.tail = snapshot["tail"]
    bpy.ops.object.mode_set(mode="POSE")

    for name, _parent, _position in FACE_ANCHORS:
        pbone = rig.pose.bones[name]
        _lock_pose_bone(pbone)
        pbone.bone.hide_select = False
        pbone.bone["mixamo_ctrl"] = 1
        pbone.lock_location = (False, False, False)
        pbone.lock_scale = (False, False, False)
        if name in FACE_PART_ROOT_SHAPES:
            shape_name, display_scale = FACE_PART_ROOT_SHAPES[name]
            _set_front_facing_custom_shape(pbone, shape_name, display_scale)
        _set_face_ui_color(pbone)
        _restore_pose_transform(pbone, root_transforms.get(name))
    root = rig.pose.bones[FACE_ROOT]
    if root_transforms.get(FACE_ROOT) is None:
        root.scale = (base_scale, base_scale, base_scale)
    _set_front_facing_custom_shape(root, "cs_square", (1.5, 1.0, 2.5))
    for spec in FACE_CONTROLLERS:
        pbone = rig.pose.bones[spec["name"]]
        pbone.bone["mixamo_ctrl"] = 1
        pbone.bone["kai_facial_channel"] = spec["name"]
        _lock_pose_bone(pbone, tuple(spec["axes"].keys()))
        _add_local_limits(pbone, spec["axes"])
        _set_front_facing_custom_shape(
            pbone,
            spec["shape"],
            spec.get("display_scale", 1.0),
            spec.get("shape_rotation", (90.0, 0.0, 0.0)),
        )
        _set_face_ui_color(pbone)
    _finish_custom_shape_setup(rig)

    if FACE_FOLLOW_PROPERTY not in rig:
        rig[FACE_FOLLOW_PROPERTY] = 1.0
    ui = rig.id_properties_ui(FACE_FOLLOW_PROPERTY)
    ui.update(min=0.0, max=1.0, soft_min=0.0, soft_max=1.0, description="Face controller Head follow")
    head_name = "Ctrl_Head" if rig.pose.bones.get("Ctrl_Head") else rig.data.get("kai_head_name", "Head")
    head = rig.pose.bones.get(head_name)
    if head is not None:
        constraint = root.constraints.new("CHILD_OF")
        constraint.name = "KAI Face Head Follow"
        constraint.target = rig
        constraint.subtarget = head.name
        constraint.inverse_matrix = head.bone.matrix_local.to_4x4().inverted()
        fcurve = constraint.driver_add("influence")
        driver = fcurve.driver
        driver.type = "SCRIPTED"
        variable = driver.variables.new()
        variable.name = "kai_follow"
        variable.type = "SINGLE_PROP"
        variable.targets[0].id = rig
        variable.targets[0].data_path = f'["{FACE_FOLLOW_PROPERTY}"]'
        driver.expression = "min(max(kai_follow, 0.0), 1.0)"

    connected = []
    missing = 0
    for mesh, target_mapping in mesh_mappings:
        keys = _shape_keys(mesh)
        for spec in FACE_OUTPUTS:
            shape_name = target_mapping.get(spec[0], "")
            if not shape_name:
                continue
            if keys is None or keys.key_blocks.get(shape_name) is None:
                missing += 1
                continue
            _add_shape_driver(keys, shape_name, rig, spec)
            connected.append((mesh.name, shape_name))

    rig.data[FACE_MAPPING_PROPERTY] = json.dumps(mapping, sort_keys=True)
    _store_face_mesh_mapping(rig, mesh_mappings)
    rig.data["kai_face_module"] = FACE_MODULE_ID
    bpy.ops.object.mode_set(mode="OBJECT")
    return len(FACE_CONTROLLERS), len(connected), missing


def _get_eye_head_bone(armature):
    if EYE_HEAD_STORAGE_PROPERTY in armature:
        return armature[EYE_HEAD_STORAGE_PROPERTY]
    mapped = armature.get("kai_head_name", "")
    return mapped if mapped and armature.bones.get(mapped) is not None else ""


def _set_eye_head_bone(armature, value):
    armature[EYE_HEAD_STORAGE_PROPERTY] = value


def generate_eye_module(rig, head_name):
    if not head_name:
        raise RuntimeError("Set Head Bone before generating the Eye Module")
    if rig.data.bones.get(head_name) is None:
        raise RuntimeError(f"Head Bone not found: {head_name}")
    previous_bones, previous_limits = _snapshot_eye_rebuild_data(rig, head_name)
    _validate_module_bone_names(
        rig,
        EYE_MODULE_ID,
        [EYE_TARGET_ROOT, *EYE_TARGETS.values(), *EYE_OUTPUTS.values(), EYE_CENTER],
    )
    remove_eye_module(rig)
    _set_active_object(rig)
    _ensure_collection(rig, EYE_COLLECTION)
    _ensure_collection(rig, EYE_INTERNAL_COLLECTION).is_visible = False
    head = rig.data.bones.get(head_name)
    head_length = max(head.length, 0.1)

    eye_positions = {}
    for side, sign in (("L", 1.0), ("R", -1.0)):
        eye_positions[side] = head.head_local + Vector(
            (sign * head_length * 0.18, -head_length * 0.1, head_length * 0.42)
        )
    center = (eye_positions["L"] + eye_positions["R"]) * 0.5
    target_distance = max(0.25, head_length * 1.75)
    target_center = center + Vector((0.0, -target_distance, 0.0))

    bpy.ops.object.mode_set(mode="EDIT")
    root = _create_edit_bone(rig, EYE_TARGET_ROOT, target_center, head_length * 0.3, head_name, EYE_COLLECTION)
    _create_edit_bone(
        rig,
        EYE_CENTER,
        center,
        head_length * 0.2,
        head_name,
        EYE_INTERNAL_COLLECTION,
    )
    for side in ("L", "R"):
        offset = eye_positions[side] - center
        _create_edit_bone(rig, EYE_TARGETS[side], target_center + offset, head_length * 0.25, root.name, EYE_COLLECTION)
        output = rig.data.edit_bones.new(EYE_OUTPUTS[side])
        output.head = eye_positions[side]
        output.tail = eye_positions[side] + Vector((0.0, -head_length * 0.3, 0.0))
        output.parent = rig.data.edit_bones.get(head_name)
        output.use_deform = False
        set_bone_collection(rig, output, EYE_INTERNAL_COLLECTION)
        output["kai_module"] = EYE_MODULE_ID
    for name, snapshot in previous_bones.items():
        bone = rig.data.edit_bones.get(name)
        if bone is not None:
            bone.head = snapshot["head"]
            bone.tail = snapshot["tail"]
    center_bone = rig.data.edit_bones[EYE_CENTER]
    center_bone.head = (
        rig.data.edit_bones[EYE_OUTPUTS["L"]].head
        + rig.data.edit_bones[EYE_OUTPUTS["R"]].head
    ) * 0.5
    center_bone.tail = center_bone.head + Vector((0.0, 0.0, head_length * 0.2))
    bpy.ops.object.mode_set(mode="POSE")

    root_pb = rig.pose.bones[EYE_TARGET_ROOT]
    root_pb.bone["mixamo_ctrl"] = 1
    _lock_pose_bone(root_pb, (0, 1, 2))
    _set_front_facing_custom_shape(
        root_pb,
        "cs_square",
        (
            head_length * 0.35,
            head_length * 0.12,
            head_length * 0.24,
        ),
    )
    _set_eye_ui_color(root_pb)
    center_pb = rig.pose.bones[EYE_CENTER]
    _lock_pose_bone(center_pb)
    center_pb.bone.hide_select = True
    center_track = root_pb.constraints.new("DAMPED_TRACK")
    center_track.name = "KAI Eye Center Damped Track"
    center_track.target = rig
    center_track.subtarget = EYE_CENTER
    center_track.track_axis = "TRACK_NEGATIVE_Z"
    for side in ("L", "R"):
        target = rig.pose.bones[EYE_TARGETS[side]]
        target.bone["mixamo_ctrl"] = 1
        _lock_pose_bone(target, (0, 1))
        _add_local_limits(target, {0: (-1.0, 1.0), 1: (-1.0, 1.0)})
        _set_front_facing_custom_shape(
            target,
            "cs_circle_025",
            (
                head_length * 0.15,
                head_length * 0.15,
                head_length * 0.15,
            ),
        )
        _set_eye_ui_color(target)
        output = rig.pose.bones[EYE_OUTPUTS[side]]
        _lock_pose_bone(output)
        output.rotation_mode = "XYZ"
        output.bone.hide_select = True
        for axis, limits in DEFAULT_EYE_IK_LIMITS.items():
            saved = previous_limits.get(side, {}).get(axis)
            setattr(output, f"use_ik_limit_{axis}", saved[0] if saved else True)
            setattr(output, f"ik_min_{axis}", saved[1] if saved else limits[0])
            setattr(output, f"ik_max_{axis}", saved[2] if saved else limits[1])
        aim = output.constraints.new("IK")
        aim.name = "KAI Eye Aim"
        aim.target = rig
        aim.subtarget = target.name
        aim.chain_count = 1
        aim.use_tail = True

    _finish_custom_shape_setup(rig)

    rig.data["kai_eye_module"] = EYE_MODULE_ID
    rig.data["kai_eye_head"] = head_name
    bpy.ops.object.mode_set(mode="OBJECT")


def _registered_face_meshes(scene):
    return [
        item.object
        for item in scene.kai_face_meshes
        if item.object is not None and item.object.type == "MESH"
    ]


def _selected_face_mesh(scene):
    if not scene.kai_face_meshes:
        return None
    index = min(max(scene.kai_face_mesh_index, 0), len(scene.kai_face_meshes) - 1)
    mesh = scene.kai_face_meshes[index].object
    return mesh if mesh is not None and mesh.type == "MESH" else None


def _face_mapping_status(rig, mesh, shape_name):
    if not shape_name:
        return "NONE"
    keys = _shape_keys(mesh)
    if keys is None or shape_name not in _shape_key_names(mesh):
        return "INVALID"
    driver = _find_driver(keys, _driver_path(shape_name))
    if driver is not None and not _is_kai_face_driver(driver, rig):
        return "CONFLICT"
    return "MAPPED"


_SHAPE_KEY_ENUM_CACHE = {}


def _face_shape_key_enum_items(operator, _context):
    mesh = bpy.data.objects.get(operator.object_name)
    names = sorted(_shape_key_names(mesh)) if mesh is not None else []
    items = [(FACE_MAPPING_NONE, "None", "Leave this Kai Facial Channel disconnected", "X", 0)]
    items.extend(
        (name, name, f"Map to {mesh.name}.{name}", "SHAPEKEY_DATA", index)
        for index, name in enumerate(names, 1)
    )
    _SHAPE_KEY_ENUM_CACHE[operator.object_name] = items
    return items


class KAI_PG_face_mesh_item(bpy.types.PropertyGroup):
    object: bpy.props.PointerProperty(type=bpy.types.Object)


class KAI_UL_face_meshes(bpy.types.UIList):
    def draw_item(
        self,
        _context,
        layout,
        _data,
        item,
        _icon,
        _active_data,
        _active_property,
        _index=0,
        _flt_flag=0,
    ):
        if item.object is None:
            layout.label(text="Missing Mesh", icon="ERROR")
        else:
            layout.label(text=item.object.name, icon="MESH_DATA")


class KAI_OT_add_face_mesh(bpy.types.Operator):
    bl_idname = "kai.add_face_mesh"
    bl_label = "Add Face Mesh"
    bl_description = "Add the selected mesh to Kai Facial mapping targets"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        scene = context.scene
        mesh = scene.kai_face_mesh_candidate
        if mesh is None or mesh.type != "MESH":
            self.report({"ERROR"}, "Select a mesh to add")
            return {"CANCELLED"}
        if any(item.object == mesh for item in scene.kai_face_meshes):
            self.report({"WARNING"}, f"{mesh.name} is already registered")
            return {"CANCELLED"}
        item = scene.kai_face_meshes.add()
        item.object = mesh
        scene.kai_face_mesh_index = len(scene.kai_face_meshes) - 1
        scene.kai_face_mesh_candidate = None
        rig = _active_armature(context)
        if rig is not None:
            ensure_face_mesh_mapping(rig, mesh)
        return {"FINISHED"}


class KAI_OT_remove_face_mesh(bpy.types.Operator):
    bl_idname = "kai.remove_face_mesh"
    bl_label = "Remove Face Mesh"
    bl_description = "Remove the active mesh from the Facial target list"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return len(context.scene.kai_face_meshes) > 0

    def execute(self, context):
        scene = context.scene
        index = min(max(scene.kai_face_mesh_index, 0), len(scene.kai_face_meshes) - 1)
        scene.kai_face_meshes.remove(index)
        scene.kai_face_mesh_index = max(0, min(index, len(scene.kai_face_meshes) - 1))
        return {"FINISHED"}


class KAI_OT_set_face_mapping(bpy.types.Operator):
    bl_idname = "kai.set_face_mapping"
    bl_label = "Select Shape Key"
    bl_description = "Select the Shape Key driven by this Kai Facial Channel"
    bl_options = {"REGISTER", "UNDO"}
    bl_property = "shape_key"

    object_name: bpy.props.StringProperty(options={"HIDDEN"})
    channel: bpy.props.StringProperty(options={"HIDDEN"})
    shape_key: bpy.props.EnumProperty(items=_face_shape_key_enum_items, options={"SKIP_SAVE"})

    def invoke(self, context, _event):
        context.window_manager.invoke_search_popup(self)
        return {"RUNNING_MODAL"}

    def execute(self, context):
        rig = _active_armature(context)
        mesh = bpy.data.objects.get(self.object_name)
        if rig is None or mesh is None or mesh.type != "MESH":
            self.report({"ERROR"}, "Select a Kai Rig and a valid Face Mesh")
            return {"CANCELLED"}
        shape_name = "" if self.shape_key == FACE_MAPPING_NONE else self.shape_key
        if shape_name and shape_name not in _shape_key_names(mesh):
            self.report({"ERROR"}, f"Shape Key not found: {mesh.name}.{shape_name}")
            return {"CANCELLED"}
        try:
            set_face_channel_mapping(rig, mesh, self.channel, shape_name)
        except ValueError as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        return {"FINISHED"}


class KAI_OT_auto_detect_face_mapping(bpy.types.Operator):
    bl_idname = "kai.auto_detect_face_mapping"
    bl_label = "Auto Detect"
    bl_description = "Fill only empty mappings using known Phase 1 Shape Key names"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return _active_armature(context) is not None and _selected_face_mesh(context.scene) is not None

    def execute(self, context):
        rig = _active_armature(context)
        mesh = _selected_face_mesh(context.scene)
        changed = auto_detect_face_mapping(rig, mesh)
        if changed:
            self.report({"INFO"}, f"Auto Detect filled {changed} empty mappings for {mesh.name}")
        else:
            self.report({"INFO"}, f"No empty mappings detected for {mesh.name}")
        return {"FINISHED"}


class KAI_OT_generate_face_module(bpy.types.Operator):
    bl_idname = "kai.generate_face_module"
    bl_label = "Generate Face Module"
    bl_description = "Generate or rebuild Phase 1 Face controllers and mapped Shape Key drivers"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return _active_armature(context) is not None

    def execute(self, context):
        rig = _active_armature(context)
        meshes = _registered_face_meshes(context.scene)
        try:
            _controllers, drivers, _missing = generate_face_module(rig, meshes)
        except RuntimeError as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        missing, unassigned = _face_mapping_counts(rig, meshes)
        if missing:
            self.report({"WARNING"}, f"Face Module: {drivers} drivers created; {missing} mappings missing")
        elif unassigned:
            self.report({"INFO"}, f"Face Module: {drivers} drivers created; {unassigned} channels unassigned")
        else:
            self.report({"INFO"}, f"Face Module: {drivers} drivers created")
        return {"FINISHED"}


class KAI_OT_generate_eye_module(bpy.types.Operator):
    bl_idname = "kai.generate_eye_module"
    bl_label = "Generate Eye Module"
    bl_description = "Generate or rebuild Eye targets and Eye_L / Eye_R rotation outputs"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return _active_armature(context) is not None

    def execute(self, context):
        rig = _active_armature(context)
        head_name = rig.data.kai_eye_head_bone.strip()
        try:
            generate_eye_module(rig, head_name)
        except RuntimeError as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        self.report({"INFO"}, f"Eye Module generated from {head_name}")
        return {"FINISHED"}


class KAI_OT_remove_eye_module(bpy.types.Operator):
    bl_idname = "kai.remove_eye_module"
    bl_label = "Remove Eye Module"
    bl_description = "Remove only Kai Eye module bones and constraints"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        rig = _active_armature(context)
        return rig is not None and eye_module_state(rig) != "NOT_GENERATED"

    def execute(self, context):
        bones = remove_eye_module(_active_armature(context))
        self.report({"INFO"}, f"Removed Eye Module: {bones} bones")
        return {"FINISHED"}


class KAI_OT_remove_face_module(bpy.types.Operator):
    bl_idname = "kai.remove_face_module"
    bl_label = "Remove Face Module"
    bl_description = "Remove only Kai Face module bones and Shape Key drivers; keep mappings"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        rig = _active_armature(context)
        return rig is not None and face_module_state(rig) != "NOT_GENERATED"

    def execute(self, context):
        rig = _active_armature(context)
        bones, drivers = remove_face_module(rig, _registered_face_meshes(context.scene))
        self.report({"INFO"}, f"Removed Face Module: {bones} bones, {drivers} drivers")
        return {"FINISHED"}


class KAI_PT_facial(Panel):
    bl_label = "Eye / Face Modules"
    bl_idname = "KAI_PT_facial"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "MixamoKai"
    bl_parent_id = "MR_PT_MenuMain"

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False
        rig = _active_armature(context)

        eye = layout.box()
        eye.label(text="Eye Module")
        eye_state = eye_module_state(rig) if rig is not None else "NOT_GENERATED"
        if rig is not None:
            eye.prop_search(rig.data, EYE_HEAD_PROPERTY, rig.data, "bones", text="Head Bone")
        else:
            eye.label(text="Select a Kai Rig", icon="ERROR")
        if eye_state == "PARTIAL":
            warning = eye.row()
            warning.alert = True
            warning.label(text="Partial Eye Module; regenerate to repair", icon="ERROR")
        eye.operator(
            KAI_OT_generate_eye_module.bl_idname,
            text="Generate Eye Module" if eye_state == "NOT_GENERATED" else "Regenerate Eye Module",
        )
        eye.operator(KAI_OT_remove_eye_module.bl_idname)

        face = layout.box()
        face.label(text="Face Module")
        face_state = face_module_state(rig) if rig is not None else "NOT_GENERATED"
        face.prop(context.scene, "kai_face_mesh_candidate", text="Mesh")
        row = face.row()
        row.template_list(
            KAI_UL_face_meshes.__name__,
            "",
            context.scene,
            "kai_face_meshes",
            context.scene,
            "kai_face_mesh_index",
            rows=3,
        )
        buttons = row.column(align=True)
        buttons.operator(KAI_OT_add_face_mesh.bl_idname, text="", icon="ADD")
        buttons.operator(KAI_OT_remove_face_mesh.bl_idname, text="", icon="REMOVE")
        selected_mesh = _selected_face_mesh(context.scene)
        mapping_box = face.box()
        mapping_box.label(text="Facial Shape Key Mapping")
        if rig is None:
            mapping_box.label(text="Select a Kai Rig", icon="ERROR")
        elif selected_mesh is None:
            mapping_box.label(text="Select a Face Mesh", icon="INFO")
        else:
            mapping_box.label(text=f"Target: {selected_mesh.name}", icon="MESH_DATA")
            if _shape_keys(selected_mesh) is None:
                mapping_box.label(text="This Object has no Shape Keys", icon="ERROR")
            mapping_box.operator(KAI_OT_auto_detect_face_mapping.bl_idname, icon="VIEWZOOM")
            target_mapping = _mapping_for_mesh(rig, selected_mesh, get_face_mapping(rig))
            for category, expand_property, channels in FACE_MAPPING_CATEGORIES:
                expanded = getattr(context.scene, expand_property)
                header = mapping_box.row()
                header.prop(
                    context.scene,
                    expand_property,
                    text=category,
                    icon="TRIA_DOWN" if expanded else "TRIA_RIGHT",
                    emboss=False,
                )
                if not expanded:
                    continue
                column = mapping_box.column(align=True)
                for channel, label in channels:
                    shape_name = target_mapping.get(channel, "")
                    status = _face_mapping_status(rig, selected_mesh, shape_name)
                    icon = {
                        "NONE": "X",
                        "INVALID": "QUESTION",
                        "CONFLICT": "ERROR",
                        "MAPPED": "CHECKMARK",
                    }[status]
                    display_name = shape_name or "None"
                    if status == "INVALID":
                        display_name += " (Missing)"
                    elif status == "CONFLICT":
                        display_name += " (Conflict)"
                    row = column.row(align=True)
                    row.alert = status in {"INVALID", "CONFLICT"}
                    row.label(text=label)
                    operator = row.operator(
                        KAI_OT_set_face_mapping.bl_idname,
                        text=display_name,
                        icon=icon,
                    )
                    operator.object_name = selected_mesh.name
                    operator.channel = channel
        if face_state == "PARTIAL":
            warning = face.row()
            warning.alert = True
            warning.label(text="Partial Face Module; regenerate to repair", icon="ERROR")
        face.operator(
            KAI_OT_generate_face_module.bl_idname,
            text="Generate Face Module" if face_state == "NOT_GENERATED" else "Regenerate Face Module",
        )
        face.operator(KAI_OT_remove_face_module.bl_idname)
        if rig is not None and face_state != "NOT_GENERATED" and FACE_FOLLOW_PROPERTY in rig:
            face.prop(rig, f'["{FACE_FOLLOW_PROPERTY}"]', text="Head Follow", slider=True)


CLASSES = (
    KAI_PG_face_mesh_item,
    KAI_UL_face_meshes,
    KAI_OT_add_face_mesh,
    KAI_OT_remove_face_mesh,
    KAI_OT_set_face_mapping,
    KAI_OT_auto_detect_face_mapping,
    KAI_OT_generate_face_module,
    KAI_OT_generate_eye_module,
    KAI_OT_remove_eye_module,
    KAI_OT_remove_face_module,
    KAI_PT_facial,
)


def _mesh_poll(_self, obj):
    return obj is not None and obj.type == "MESH"


def register():
    for cls in CLASSES:
        bpy.utils.register_class(cls)
    bpy.types.Scene.kai_face_mesh_candidate = bpy.props.PointerProperty(type=bpy.types.Object, poll=_mesh_poll)
    bpy.types.Scene.kai_face_meshes = bpy.props.CollectionProperty(type=KAI_PG_face_mesh_item)
    bpy.types.Scene.kai_face_mesh_index = bpy.props.IntProperty(default=0, min=0)
    bpy.types.Scene.kai_face_mapping_expand_brow = bpy.props.BoolProperty(default=True)
    bpy.types.Scene.kai_face_mapping_expand_eye = bpy.props.BoolProperty(default=False)
    bpy.types.Scene.kai_face_mapping_expand_mouth = bpy.props.BoolProperty(default=False)
    bpy.types.Armature.kai_eye_head_bone = bpy.props.StringProperty(
        name="Head Bone",
        description="Head bone used to generate the Kai Eye Module",
        get=_get_eye_head_bone,
        set=_set_eye_head_bone,
    )


def unregister():
    if hasattr(bpy.types.Armature, EYE_HEAD_PROPERTY):
        delattr(bpy.types.Armature, EYE_HEAD_PROPERTY)
    for name in (
        "kai_face_mesh_candidate",
        "kai_face_meshes",
        "kai_face_mesh_index",
        "kai_face_mapping_expand_brow",
        "kai_face_mapping_expand_eye",
        "kai_face_mapping_expand_mouth",
    ):
        if hasattr(bpy.types.Scene, name):
            delattr(bpy.types.Scene, name)
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)
