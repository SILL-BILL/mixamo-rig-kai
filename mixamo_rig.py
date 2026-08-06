import math
from math import degrees, pi, radians

import bpy
from bpy.types import Panel
from mathutils import Matrix, Vector

# Import naming constants
from .definitions.naming import (
    arm_names,
    arm_rig_names,
    c_prefix,
    fingers_type,
    head_names,
    head_rig_names,
    leg_names,
    leg_rig_names,
    master_rig_names,
    spine_names,
    spine_rig_names,
)
from .kai_reference_template import DEFAULT_REFERENCE_TEMPLATE, KAI_REFERENCE_TEMPLATES

# Import lib functions
from .lib import animation_compat
from .lib.animation import bake_anim
from .lib.armature import (
    enable_all_armature_layers,
    restore_armature_layers,
)
from .lib.bones_data import set_bone_collection
from .lib.bones_edit import copy_bone_transforms, create_edit_bone, get_edit_bone
from .lib.bones_pose import (
    get_custom_shape_scale,
    get_pose_bone,
    lock_pbone_transform,
    set_bone_color_group,
    set_bone_custom_shape,
    set_pose_bone_selected,
)
from .lib.constraints import (
    add_copy_transf,
    set_constraint_inverse_matrix,
)
from .lib.custom_props import create_custom_prop
from .lib.drivers import add_driver_to_prop
from .lib.maths_geo import (
    align_bone_x_axis,
    align_bone_z_axis,
    get_pole_angle,
    mat3_to_vec_roll,
    project_point_onto_plane,
    project_vector_onto_plane,
    rotate_point,
    signed_angle,
    vec_roll_to_mat3,
)
from .lib.mixamo import get_mix_name
from .lib.objects import (
    append_cs,
    delete_object,
    duplicate_object,
    get_object,
    hide_object,
    set_active_object,
)
from .lib.version import (
    blender_version,
    convert_drivers_cs_to_xyz,
    get_custom_shape_scale_prop_name,
)


KAI_REFERENCE_TEMPLATE_ITEMS = tuple(
    (
        key,
        template.get("label", key),
        template.get("description", ""),
    )
    for key, template in KAI_REFERENCE_TEMPLATES.items()
)

RETARGET_ROTATION_OUTPUT_ITEMS = (
    (
        "QUATERNION",
        "Quaternion",
        "Bake retarget rotations as quaternion keys",
    ),
    (
        "EULER",
        "Euler",
        "Bake retarget rotations as Euler keys",
    ),
    (
        "TARGET_ORIGINAL",
        "Target Original",
        "Use each target bone original rotation mode",
    ),
)



# UTILITY FUNCTIONS
####################
def _deselect_all_objects():
    """
    Safely deselect all objects, handling context issues.
    Falls back to manual deselection if operator fails.
    """
    try:
        # Try to ensure OBJECT mode first if we have an active object
        if bpy.context.active_object and bpy.context.active_object.mode != "OBJECT":
            try:
                bpy.ops.object.mode_set(mode="OBJECT")
            except Exception:
                pass
        bpy.ops.object.select_all(action="DESELECT")
    except Exception:
        # Fallback: manually deselect all objects
        for obj in bpy.context.view_layer.objects:
            try:
                obj.select_set(False)
            except Exception:
                pass


def _kai_vec_matches(actual, expected, tolerance=0.000001):
    return all(abs(actual[index] - expected[index]) <= tolerance for index in range(3))


def _kai_float_matches(actual, expected, tolerance=0.000001):
    return abs(actual - expected) <= tolerance


def _kai_enter_object_mode_if_needed():
    active_object = bpy.context.active_object
    if active_object is not None and active_object.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")


def _kai_validate_reference_skeleton(armature, template, tolerance=0.000001):
    if armature is None or armature.type != "ARMATURE":
        return ["Generated object is not an armature"]

    errors = []
    expected_bones = template.get("bones", [])

    _kai_enter_object_mode_if_needed()
    bpy.ops.object.select_all(action="DESELECT")
    armature.select_set(True)
    bpy.context.view_layer.objects.active = armature
    bpy.ops.object.mode_set(mode="EDIT")

    edit_bones = armature.data.edit_bones
    if len(edit_bones) != len(expected_bones):
        errors.append(f"Bone count mismatch: {len(edit_bones)} != {len(expected_bones)}")

    for bone_data in expected_bones:
        bone = edit_bones.get(bone_data["name"])
        if bone is None:
            errors.append(f"Missing bone: {bone_data['name']}")
            continue

        if not _kai_vec_matches(bone.head, bone_data["head"], tolerance):
            errors.append(f"Head mismatch: {bone.name}")
        if not _kai_vec_matches(bone.tail, bone_data["tail"], tolerance):
            errors.append(f"Tail mismatch: {bone.name}")
        if not _kai_float_matches(bone.roll, bone_data["roll"], tolerance):
            errors.append(f"Roll mismatch: {bone.name}")

        parent_name = bone.parent.name if bone.parent else None
        if parent_name != bone_data.get("parent"):
            errors.append(f"Parent mismatch: {bone.name}")
        if bool(bone.use_connect) != bool(bone_data.get("connected", False)):
            errors.append(f"Connected mismatch: {bone.name}")

    _kai_enter_object_mode_if_needed()
    return errors


def _kai_create_reference_skeleton_from_template(template):
    armature_name = template.get("name", "Kai_Humanoid_Reference")
    if bpy.data.objects.get(armature_name) is not None:
        raise RuntimeError(f"Object already exists: {armature_name}")

    arm_data = bpy.data.armatures.new(armature_name)
    arm_obj = bpy.data.objects.new(armature_name, arm_data)
    bpy.context.collection.objects.link(arm_obj)

    _kai_enter_object_mode_if_needed()
    bpy.ops.object.select_all(action="DESELECT")
    arm_obj.select_set(True)
    bpy.context.view_layer.objects.active = arm_obj
    bpy.ops.object.mode_set(mode="EDIT")

    edit_bones = arm_data.edit_bones
    default_bone = edit_bones.get("Bone")
    if default_bone is not None:
        edit_bones.remove(default_bone)

    for bone_data in template.get("bones", []):
        bone = edit_bones.new(bone_data["name"])
        bone.head = Vector(bone_data["head"])
        bone.tail = Vector(bone_data["tail"])
        bone.roll = bone_data["roll"]

    for bone_data in template.get("bones", []):
        bone = edit_bones[bone_data["name"]]
        parent_name = bone_data.get("parent")
        if parent_name:
            bone.parent = edit_bones[parent_name]
        bone.use_connect = bool(bone_data.get("connected", False))

    bpy.ops.object.mode_set(mode="OBJECT")
    return arm_obj


def search_layer_collection(layer_collection, collection_name):
    """Recursively search for a layer collection by name."""
    if layer_collection.name == collection_name:
        return layer_collection
    for child in layer_collection.children:
        result = search_layer_collection(child, collection_name)
        if result:
            return result
    return None


def _get_armature_pose_bone(armature, bone_name):
    if armature is None or bone_name is None:
        return None

    pose = getattr(armature, "pose", None)
    if pose is None:
        return None

    return pose.bones.get(bone_name)


_shape_fit_mesh_warning_names = set()


def _warn_shape_fit_mesh_once(obj, action, exc):
    obj_name = getattr(obj, "name", "<unknown>")
    key = (obj_name, action)
    if key in _shape_fit_mesh_warning_names:
        return
    _shape_fit_mesh_warning_names.add(key)
    print(f"  Warning: Could not {action} mesh '{obj_name}': {exc}")


def _ensure_ik_fk_switch_prop(pbone, default_value=0.0):
    if pbone is None:
        return False

    if "ik_fk_switch" not in pbone.keys():
        create_custom_prop(
            node=pbone,
            prop_name="ik_fk_switch",
            prop_val=default_value,
            prop_min=0.0,
            prop_max=1.0,
            prop_description="IK-FK switch value",
        )
        pbone["ik_fk_switch"] = default_value
        return True

    return False


def _refresh_control_rig_setup(rig):
    if rig is None or rig.type != "ARMATURE":
        return

    if "mr_control_rig" not in rig.data.keys():
        return

    try:
        _deselect_all_objects()
        set_active_object(rig.name)
        try:
            bpy.ops.object.mode_set(mode="OBJECT")
            bpy.ops.object.mode_set(mode="POSE")
        except Exception:
            pass
        bpy.context.view_layer.update()
        _build_constraints_for_rig(rig)
        bpy.context.view_layer.update()
    except Exception as exc:
        print(f"  Warning: Could not refresh control rig setup: {exc}")


def _resolve_limb_kinematic_mode(
    rig,
    ik_ctrl_name,
    fk_ctrl_name,
    limb_label,
    default_switch=0.0,
):
    ik_ctrl_pb = _get_armature_pose_bone(rig, ik_ctrl_name)
    if ik_ctrl_pb is not None:
        if _ensure_ik_fk_switch_prop(ik_ctrl_pb, default_switch):
            print(f"  Restored IK/FK switch on {ik_ctrl_name}")

        try:
            return "IK" if ik_ctrl_pb["ik_fk_switch"] < 0.5 else "FK"
        except Exception as exc:
            print(
                f"  Warning: Could not read IK/FK switch on {ik_ctrl_name}: {exc}"
            )
            return "IK" if default_switch < 0.5 else "FK"

    if _get_armature_pose_bone(rig, fk_ctrl_name) is not None:
        print(
            f"  Warning: Missing IK controller {ik_ctrl_name} for {limb_label}; "
            "falling back to FK"
        )
        return "FK"

    print(
        f"  Warning: Missing both IK and FK controllers for {limb_label}; "
        "skipping that limb"
    )
    return None


def _detect_mixamo_prefix(rig):
    if rig is None:
        return ""

    for bone in rig.data.bones:
        if bone.name.startswith("mixamorig") and ":" in bone.name:
            return bone.name.split(":")[0] + ":"
    return ""


def _get_src_bone_name_resolver(rig):
    detected_prefix = _detect_mixamo_prefix(rig)

    def get_src_bone_name(base_name):
        if detected_prefix:
            return detected_prefix + base_name
        return base_name

    return get_src_bone_name


def _kai_prefixed_source_bone_name(base_name, detected_prefix):
    if not base_name:
        return base_name
    if detected_prefix and not base_name.startswith(detected_prefix):
        return detected_prefix + base_name
    return base_name


def _kai_bone_exists_on_armature(armature, bone_name):
    if armature is None or not bone_name:
        return False
    data = getattr(armature, "data", None)
    if data is not None and data.bones.get(bone_name) is not None:
        return True
    pose = getattr(armature, "pose", None)
    return bool(pose is not None and pose.bones.get(bone_name) is not None)


def _kai_bone_name_candidates(bone_name, detected_prefix=""):
    candidates = []

    def add_candidate(name):
        if name and name not in candidates:
            candidates.append(name)

    add_candidate(bone_name)
    add_candidate(_kai_prefixed_source_bone_name(bone_name, detected_prefix))

    if detected_prefix and bone_name.startswith(detected_prefix):
        add_candidate(bone_name[len(detected_prefix):])

    if ":" in bone_name:
        unprefixed_name = bone_name.split(":", 1)[1]
        add_candidate(unprefixed_name)
        add_candidate(_kai_prefixed_source_bone_name(unprefixed_name, detected_prefix))

    return candidates


def _kai_resolve_bone_name_on_armature(armature, bone_name, detected_prefix=""):
    for candidate in _kai_bone_name_candidates(bone_name, detected_prefix):
        if _kai_bone_exists_on_armature(armature, candidate):
            return candidate
    return ""


def _kai_resolve_spine_sources(source_spine_names, source_chest_name):
    spine_names = [name for name in source_spine_names if name]
    chest_name = source_chest_name
    first_spine_name = spine_names[0] if spine_names else chest_name
    second_spine_name = spine_names[1] if len(spine_names) > 1 else first_spine_name
    return spine_names, chest_name, first_spine_name, second_spine_name


def _kai_unique_bone_names(bone_names):
    unique_names = []
    seen = set()
    for name in bone_names:
        if not name or name in seen:
            continue
        seen.add(name)
        unique_names.append(name)
    return unique_names


def _kai_build_spine_control_pairs(
    source_spine_names,
    source_chest_name,
    detected_prefix="",
):
    raw_names = _kai_unique_bone_names(
        list(source_spine_names) + ([source_chest_name] if source_chest_name else [])
    )
    return [
        {
            "raw_name": raw_name,
            "source_name": _kai_prefixed_source_bone_name(raw_name, detected_prefix),
            "control_name": c_prefix + raw_name,
        }
        for raw_name in raw_names
    ]


def _kai_get_mapping_names_from_rig_data(rig):
    data = getattr(rig, "data", None)
    if data is None:
        return {
            "hip": spine_names["pelvis"],
            "spines": [spine_names["spine1"], spine_names["spine2"]],
            "chest": spine_names["spine3"],
            "necks": [head_names["neck"]],
            "head": head_names["head"],
            "shoulders": {
                "Left": "Left" + arm_names["shoulder"],
                "Right": "Right" + arm_names["shoulder"],
            },
        }

    if "kai_spine_names" in data.keys():
        spine_source_names = [
            name for name in data.get("kai_spine_names", "").split(",")
            if name
        ]
    else:
        spine_source_names = [spine_names["spine1"], spine_names["spine2"]]

    if "kai_neck_names" in data.keys():
        neck_source_names = [
            name for name in data.get("kai_neck_names", "").split(",")
            if name
        ]
    else:
        neck_source_names = [head_names["neck"]]

    if (
        "kai_shoulder_left_name" in data.keys()
        or "kai_shoulder_right_name" in data.keys()
    ):
        shoulder_source_names = {
            "Left": data.get("kai_shoulder_left_name", ""),
            "Right": data.get("kai_shoulder_right_name", ""),
        }
    else:
        shoulder_source_names = {
            "Left": "Left" + arm_names["shoulder"],
            "Right": "Right" + arm_names["shoulder"],
        }

    return {
        "hip": data.get("kai_hip_name", "") or spine_names["pelvis"],
        "spines": spine_source_names,
        "chest": data.get("kai_chest_name", "") or spine_names["spine3"],
        "necks": neck_source_names,
        "head": data.get("kai_head_name", "") or head_names["head"],
        "shoulders": shoulder_source_names,
    }

def _kai_mapping_names_for_generate(rig):
    return _kai_validate_mapping_for_rebuild(rig)


def _kai_resolve_mapping_bone_name(rig, bone_name):
    if not bone_name:
        return ""

    detected_prefix = _detect_mixamo_prefix(rig)
    resolved_name = _kai_resolve_bone_name_on_armature(
        rig,
        bone_name,
        detected_prefix,
    )
    return resolved_name or bone_name


def _kai_unique_mapping_bone_names(mapping_names):
    names = []
    for name in [
        mapping_names.get("hip", ""),
        *mapping_names.get("spines", []),
        mapping_names.get("chest", ""),
        *mapping_names.get("necks", []),
        mapping_names.get("head", ""),
        *mapping_names.get("shoulders", {}).values(),
    ]:
        if name and name not in names:
            names.append(name)
    return names


def _kai_mapping_topology_record(rig, bone_name):
    resolved_name = _kai_resolve_mapping_bone_name(rig, bone_name)
    bone = rig.data.bones.get(resolved_name)
    if bone is None:
        return None
    parent_name = bone.parent.name if bone.parent else ""
    connected = "1" if bone.use_connect else "0"
    return f"{bone.name}\t{parent_name}\t{connected}"


def _kai_store_mapping_topology(rig, mapping_names):
    records = []
    for bone_name in _kai_unique_mapping_bone_names(mapping_names):
        record = _kai_mapping_topology_record(rig, bone_name)
        if record is not None:
            records.append(record)
    rig.data["kai_mapping_topology"] = "\n".join(records)
    return records


def _kai_parse_mapping_topology(raw_records):
    topology = {}
    if not raw_records:
        return topology

    for record in str(raw_records).split("\n"):
        if not record:
            continue
        parts = record.split("\t")
        if len(parts) != 3:
            continue
        topology[parts[0]] = {
            "parent": parts[1],
            "connected": parts[2] == "1",
        }
    return topology


def _kai_warn_mapping_topology_changes(rig, reporter=None):
    stored_topology = _kai_parse_mapping_topology(
        rig.data.get("kai_mapping_topology", "")
    )
    if not stored_topology:
        return []

    warnings = []
    for bone_name, stored in stored_topology.items():
        resolved_name = _kai_resolve_mapping_bone_name(rig, bone_name)
        bone = rig.data.bones.get(resolved_name)
        if bone is None:
            continue
        parent_name = bone.parent.name if bone.parent else ""
        connected = bool(bone.use_connect)
        if parent_name != stored["parent"]:
            warnings.append(
                f"{bone_name}: parent {stored['parent'] or '<none>'} -> {parent_name or '<none>'}"
            )
        if connected != stored["connected"]:
            warnings.append(
                f"{bone_name}: connected {stored['connected']} -> {connected}"
            )

    if warnings and reporter is not None:
        reporter.report(
            {"WARNING"},
            "[Kai] Reference Skeleton hierarchy/connection changed: "
            + "; ".join(warnings[:4]),
        )
    return warnings


def _kai_validate_mapping_for_rebuild(rig, reporter=None):
    try:
        if bpy.context.active_object == rig and rig.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
    except Exception:
        pass

    mapping_names = _kai_get_mapping_names_from_rig_data(rig)

    required_missing = []
    for label, key in (("Hip", "hip"), ("Chest", "chest"), ("Head", "head")):
        bone_name = mapping_names.get(key, "")
        resolved_name = _kai_resolve_mapping_bone_name(rig, bone_name)
        if not bone_name or rig.data.bones.get(resolved_name) is None:
            required_missing.append(f"{label}={bone_name or '<empty>'}")
        else:
            mapping_names[key] = resolved_name

    if required_missing:
        raise RuntimeError(
            "[Kai] Missing required Mapping bones: " + ", ".join(required_missing)
        )

    missing_optional = []
    filtered_spines = []
    for bone_name in mapping_names.get("spines", []):
        resolved_name = _kai_resolve_mapping_bone_name(rig, bone_name)
        if bone_name and rig.data.bones.get(resolved_name) is not None:
            filtered_spines.append(resolved_name)
        elif bone_name:
            missing_optional.append(f"Spine={bone_name}")

    filtered_necks = []
    for bone_name in mapping_names.get("necks", []):
        resolved_name = _kai_resolve_mapping_bone_name(rig, bone_name)
        if bone_name and rig.data.bones.get(resolved_name) is not None:
            filtered_necks.append(resolved_name)
        elif bone_name:
            missing_optional.append(f"Neck={bone_name}")

    filtered_shoulders = {}
    for side, bone_name in mapping_names.get("shoulders", {}).items():
        resolved_name = _kai_resolve_mapping_bone_name(rig, bone_name)
        if bone_name and rig.data.bones.get(resolved_name) is not None:
            filtered_shoulders[side] = resolved_name
        else:
            filtered_shoulders[side] = ""
            if bone_name:
                missing_optional.append(f"Shoulder {side}={bone_name}")

    mapping_names["spines"] = filtered_spines
    mapping_names["necks"] = filtered_necks
    mapping_names["shoulders"] = filtered_shoulders

    if missing_optional and reporter is not None:
        reporter.report(
            {"WARNING"},
            "[Kai] Ignored missing optional Mapping bones: "
            + ", ".join(missing_optional),
        )

    _kai_warn_mapping_topology_changes(rig, reporter)
    return mapping_names


def _kai_add_mapping_if_target_exists(bones_map, src_name, target_rig, target_name):
    if not src_name or not target_name:
        return False
    if _get_armature_pose_bone(target_rig, target_name) is None:
        return False
    bones_map[src_name] = target_name
    return True


def _kai_add_resolved_source_mapping_if_target_exists(
    bones_map,
    src_arm,
    source_name,
    detected_prefix,
    target_rig,
    target_name,
    role_label,
):
    if not source_name or not target_name:
        print(
            f"    SKIP: Missing retarget mapping name for {role_label}: "
            f"source={source_name or '<empty>'}, target={target_name or '<empty>'}"
        )
        return ""

    target_candidates = [target_name]
    if target_name.startswith(c_prefix):
        target_base_names = _kai_bone_name_candidates(source_name, detected_prefix)
        target_base_names += _kai_bone_name_candidates(
            source_name,
            _detect_mixamo_prefix(target_rig),
        )
        for target_base_name in target_base_names:
            candidate = c_prefix + target_base_name
            if candidate not in target_candidates:
                target_candidates.append(candidate)

    resolved_target_name = ""
    for candidate in target_candidates:
        if _get_armature_pose_bone(target_rig, candidate) is not None:
            resolved_target_name = candidate
            break

    if not resolved_target_name:
        print(
            f"    SKIP: Target control not found for {role_label}: "
            f"saved={target_name}, tried=[{', '.join(target_candidates)}]"
        )
        return ""

    resolved_source_name = _kai_resolve_bone_name_on_armature(
        src_arm,
        source_name,
        detected_prefix,
    )
    if not resolved_source_name:
        candidates = ", ".join(
            _kai_bone_name_candidates(source_name, detected_prefix)
        )
        print(
            f"    SKIP: Source bone not found for {role_label}: "
            f"saved={source_name}, tried=[{candidates}]"
        )
        return ""

    bones_map[resolved_source_name] = resolved_target_name
    return resolved_source_name


def _kai_safe_bone_name(value):
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    try:
        name = getattr(value, "name", "")
    except (ReferenceError, RuntimeError, UnicodeDecodeError, UnicodeError):
        return ""
    if not isinstance(name, str):
        return ""
    return name.strip()


def _kai_split_generated_bone_names(raw_names):
    if not raw_names:
        return []
    return [name for name in str(raw_names).split(",") if name]


def _kai_get_stored_generated_bone_names(rig):
    data = getattr(rig, "data", None)
    if data is None:
        return []
    return _kai_split_generated_bone_names(data.get("kai_generated_bones", ""))


def _kai_get_generated_bone_names_for_reset(rig):
    stored_names = _kai_get_stored_generated_bone_names(rig)
    if stored_names:
        return [name for name in stored_names if rig.data.bones.get(name) is not None]

    if "mr_control_rig" not in rig.data.keys():
        return []

    generated_names = []
    for coll_name in ("CTRL", "MCH"):
        coll = rig.data.collections.get(coll_name)
        if coll is None:
            continue
        for bone in coll.bones:
            if bone.name not in generated_names:
                generated_names.append(bone.name)

    return generated_names


def _kai_store_generated_bones(rig, existing_bone_names):
    generated_names = [
        bone.name
        for bone in rig.data.bones
        if bone.name not in existing_bone_names
    ]
    generated_names.sort()

    for name in generated_names:
        bone = rig.data.bones.get(name)
        if bone is not None:
            bone["kai_generated"] = True

    rig.data["kai_generated_bones"] = ",".join(generated_names)
    return generated_names


def _kai_constraint_key(pbone_name, constraint_name):
    return f"{pbone_name}\t{constraint_name}"


def _kai_snapshot_constraints(rig):
    return {
        _kai_constraint_key(pbone.name, cns.name)
        for pbone in rig.pose.bones
        for cns in pbone.constraints
    }


def _kai_split_generated_constraint_keys(raw_keys):
    if not raw_keys:
        return []
    return [key for key in str(raw_keys).split("\n") if key]


def _kai_store_generated_constraints(rig, existing_constraint_keys, generated_names):
    generated_name_set = set(generated_names)
    generated_constraint_keys = []

    for pbone in rig.pose.bones:
        owner_is_generated = pbone.name in generated_name_set
        for cns in pbone.constraints:
            key = _kai_constraint_key(pbone.name, cns.name)
            if key in existing_constraint_keys:
                continue

            target = getattr(cns, "target", None)
            subtarget = getattr(cns, "subtarget", "")
            targets_generated_bone = target == rig and subtarget in generated_name_set
            if owner_is_generated or targets_generated_bone:
                generated_constraint_keys.append(key)

    generated_constraint_keys.sort()
    rig.data["kai_generated_constraints"] = "\n".join(generated_constraint_keys)
    return generated_constraint_keys


def _kai_driver_uses_generated_bone(driver_fcurve, generated_names):
    data_path = getattr(driver_fcurve, "data_path", "")
    for name in generated_names:
        if f'pose.bones["{name}"]' in data_path:
            return True

    driver = getattr(driver_fcurve, "driver", None)
    if driver is None:
        return False

    for var in driver.variables:
        for target in var.targets:
            target_path = getattr(target, "data_path", "")
            for name in generated_names:
                if f'pose.bones["{name}"]' in target_path:
                    return True

    return False


def _kai_remove_generated_drivers(rig, generated_names):
    if rig.animation_data is None:
        return 0

    removed_count = 0
    for driver_fcurve in list(rig.animation_data.drivers):
        if _kai_driver_uses_generated_bone(driver_fcurve, generated_names):
            rig.driver_remove(driver_fcurve.data_path, driver_fcurve.array_index)
            removed_count += 1
    return removed_count


def _kai_reset_generated_rig(context, reporter=None):
    rig = context.active_object
    if rig is None or rig.type != "ARMATURE":
        raise RuntimeError("No armature selected")

    generated_names = _kai_get_generated_bone_names_for_reset(rig)
    generated_name_set = set(generated_names)

    try:
        bpy.ops.object.mode_set(mode="OBJECT")
    except Exception:
        pass

    _deselect_all_objects()
    set_active_object(rig.name)

    stored_constraint_keys = set(
        _kai_split_generated_constraint_keys(
            rig.data.get("kai_generated_constraints", "")
        )
    )

    removed_constraints = 0
    bpy.ops.object.mode_set(mode="POSE")
    for pbone in rig.pose.bones:
        owner_is_generated = pbone.name in generated_name_set
        for cns in list(pbone.constraints):
            constraint_key = _kai_constraint_key(pbone.name, cns.name)
            remove_constraint = constraint_key in stored_constraint_keys

            if not stored_constraint_keys:
                target = getattr(cns, "target", None)
                subtarget = getattr(cns, "subtarget", "")
                is_kai_target = target == rig and subtarget in generated_name_set
                remove_constraint = owner_is_generated or is_kai_target

            if remove_constraint:
                pbone.constraints.remove(cns)
                removed_constraints += 1

    removed_drivers = _kai_remove_generated_drivers(rig, generated_names)

    bpy.ops.object.mode_set(mode="EDIT")
    removed_bones = 0
    for name in generated_names:
        bone = rig.data.edit_bones.get(name)
        if bone is not None:
            rig.data.edit_bones.remove(bone)
            removed_bones += 1

    bpy.ops.object.mode_set(mode="OBJECT")

    for coll_name in ("CTRL", "MCH"):
        coll = rig.data.collections.get(coll_name)
        if coll is not None and len(coll.bones) == 0:
            try:
                rig.data.collections.remove(coll)
            except Exception:
                pass

    for prop_name in ("mr_control_rig", "kai_generated_bones", "kai_generated_constraints"):
        if prop_name in rig.data.keys():
            del rig.data[prop_name]

    if reporter is not None:
        reporter.report(
            {"INFO"},
            (
                "[Kai] Reset Generated Rig: "
                f"{removed_bones} bones, "
                f"{removed_constraints} constraints, "
                f"{removed_drivers} drivers"
            ),
        )

    return {
        "bones": removed_bones,
        "constraints": removed_constraints,
        "drivers": removed_drivers,
    }


def _has_fk_foot_setup_issue(rig, side):
    if rig is None or rig.type != "ARMATURE":
        return False
    if "mr_control_rig" not in rig.data.keys():
        return False

    _side = "_" + side
    get_src_bone_name = _get_src_bone_name_resolver(rig)
    foot_name = get_src_bone_name(side + leg_names["foot"])
    c_calf_fk_name = c_prefix + leg_rig_names["calf_fk"] + _side
    c_foot_fk_name = c_prefix + leg_rig_names["foot_fk"] + _side
    foot_fk_name = leg_rig_names["foot_fk"] + _side
    c_toe_fk_name = c_prefix + leg_rig_names["toes_fk"] + _side

    foot_bone = rig.data.bones.get(foot_name)
    c_calf_fk_bone = rig.data.bones.get(c_calf_fk_name)
    c_foot_fk_bone = rig.data.bones.get(c_foot_fk_name)
    foot_fk_bone = rig.data.bones.get(foot_fk_name)
    c_toe_fk_bone = rig.data.bones.get(c_toe_fk_name)

    if not all(
        [foot_bone, c_calf_fk_bone, c_foot_fk_bone, foot_fk_bone, c_toe_fk_bone]
    ):
        return False

    if c_foot_fk_bone.parent != c_calf_fk_bone:
        return True
    if foot_fk_bone.parent != c_foot_fk_bone:
        return True
    if c_toe_fk_bone.parent != foot_fk_bone:
        return True

    ctrl_vs_foot_angle = foot_bone.matrix_local.to_quaternion().rotation_difference(
        c_foot_fk_bone.matrix_local.to_quaternion()
    ).angle

    # In the legacy rig, Ctrl_Foot_FK is deliberately flattened relative to the
    # deform foot rest transform. If the two rest rotations match, the helper
    # offset that snap depends on has been lost.
    if ctrl_vs_foot_angle < radians(5):
        return True

    return False


def _control_rig_needs_fk_foot_fix(rig):
    return any(_has_fk_foot_setup_issue(rig, side) for side in ("Left", "Right"))


def _repair_fk_foot_setup(context, rig=None, force=False):
    rig = rig or context.active_object
    if rig is None or rig.type != "ARMATURE":
        return []
    if "mr_control_rig" not in rig.data.keys():
        return []

    sides_to_fix = [
        side
        for side in ("Left", "Right")
        if force or _has_fk_foot_setup_issue(rig, side)
    ]
    if not sides_to_fix:
        return []

    previous_active = context.active_object
    previous_mode = rig.mode
    previous_pose_position = rig.data.pose_position
    fixed_sides = []

    try:
        if previous_active is None or previous_active.name != rig.name:
            _deselect_all_objects()
            set_active_object(rig.name)

        if rig.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")

        rig.data.pose_position = "REST"
        bpy.ops.object.mode_set(mode="EDIT")

        get_src_bone_name = _get_src_bone_name_resolver(rig)
        for side in sides_to_fix:
            _side = "_" + side
            foot_name = get_src_bone_name(side + leg_names["foot"])
            toe_name = get_src_bone_name(side + leg_names["toes"])
            c_calf_fk_name = c_prefix + leg_rig_names["calf_fk"] + _side
            c_foot_fk_name = c_prefix + leg_rig_names["foot_fk"] + _side
            foot_fk_name = leg_rig_names["foot_fk"] + _side
            c_toe_fk_name = c_prefix + leg_rig_names["toes_fk"] + _side

            foot = get_edit_bone(foot_name)
            toe = get_edit_bone(toe_name)
            c_calf_fk = get_edit_bone(c_calf_fk_name)
            c_foot_fk = get_edit_bone(c_foot_fk_name)
            foot_fk = get_edit_bone(foot_fk_name)
            c_toe_fk = get_edit_bone(c_toe_fk_name)

            if not all([foot, toe, c_calf_fk, c_foot_fk, foot_fk, c_toe_fk]):
                continue

            copy_bone_transforms(foot, c_foot_fk)
            c_foot_fk.tail[2] = foot.head[2]
            align_bone_z_axis(c_foot_fk, Vector((0, 0, 1)))
            c_foot_fk.parent = c_calf_fk

            copy_bone_transforms(foot, foot_fk)
            foot_fk.parent = c_foot_fk

            copy_bone_transforms(toe, c_toe_fk)
            c_toe_fk.parent = foot_fk

            fixed_sides.append(side)
    finally:
        if rig.mode != "POSE":
            bpy.ops.object.mode_set(mode="POSE")
        rig.data.pose_position = previous_pose_position

    if fixed_sides:
        _refresh_control_rig_setup(rig)

    if previous_mode != "POSE":
        try:
            bpy.ops.object.mode_set(mode=previous_mode)
        except Exception:
            pass

    if previous_active and previous_active.name != rig.name:
        try:
            _deselect_all_objects()
            set_active_object(previous_active.name)
            if previous_mode != "OBJECT":
                bpy.ops.object.mode_set(mode=previous_mode)
        except Exception:
            pass

    return fixed_sides


def _get_meshes_using_rig(rig):
    if rig is None:
        return []

    meshes = []
    seen = set()

    def add_mesh(obj):
        if obj is None or obj.type != "MESH":
            return
        if obj.name in seen:
            return
        seen.add(obj.name)
        meshes.append(obj)

    stack = list(rig.children)
    while stack:
        child = stack.pop()
        stack.extend(child.children)
        add_mesh(child)

    for obj in bpy.data.objects:
        if obj.type != "MESH":
            continue
        if obj.find_armature() == rig:
            add_mesh(obj)
            continue
        for mod in obj.modifiers:
            if mod.type == "ARMATURE" and mod.object == rig:
                add_mesh(obj)
                break

    return meshes


def _get_custom_shape_display_matrix(rig, pbone):
    if pbone.custom_shape_transform:
        base_matrix = rig.matrix_world @ pbone.custom_shape_transform.matrix
    else:
        base_matrix = rig.matrix_world @ pbone.matrix

    scale_xyz = get_custom_shape_scale(pbone, uniform=False)
    length = max(getattr(pbone, "length", 0.0), 1e-8)
    scale_matrix = Matrix.Diagonal(
        (
            scale_xyz[0] * length,
            scale_xyz[1] * length,
            scale_xyz[2] * length,
            1.0,
        )
    )
    return base_matrix @ scale_matrix


def _get_visible_collection_for_shape_copy(rig, source_obj):
    active_layer_collection = getattr(bpy.context, "layer_collection", None)
    if active_layer_collection and active_layer_collection.is_visible:
        return active_layer_collection.collection

    for col in getattr(rig, "users_collection", []):
        layer_col = search_layer_collection(
            bpy.context.view_layer.layer_collection, col.name
        )
        if layer_col and not layer_col.hide_viewport and not col.hide_viewport:
            return col

    for col in getattr(source_obj, "users_collection", []):
        layer_col = search_layer_collection(
            bpy.context.view_layer.layer_collection, col.name
        )
        if layer_col and not layer_col.hide_viewport and not col.hide_viewport:
            return col

    return bpy.context.scene.collection


def _ensure_unique_custom_shape_copy(rig, pbone):
    shape_obj = getattr(pbone, "custom_shape", None)
    if shape_obj is None or shape_obj.type != "MESH" or shape_obj.data is None:
        return None

    obj_name = ("cs_user_" + pbone.name)[:63]
    if shape_obj.name == obj_name:
        return shape_obj

    existing = bpy.data.objects.get(obj_name)
    if existing is not None and existing.type == "MESH" and existing.data is not None:
        if existing.data != shape_obj.data:
            existing.data = shape_obj.data.copy()
            existing.data.name = obj_name
        existing["mr_armature"] = rig.name
        pbone.custom_shape = existing
        return existing

    new_obj = shape_obj.copy()
    new_obj.data = shape_obj.data.copy()
    new_obj.name = obj_name
    new_obj.data.name = obj_name

    target_collection = _get_visible_collection_for_shape_copy(rig, shape_obj)
    target_collection.objects.link(new_obj)

    new_obj.parent = shape_obj.parent
    new_obj["mr_armature"] = rig.name
    new_obj.hide_viewport = True
    new_obj.hide_render = True
    try:
        hide_object(new_obj)
    except Exception:
        pass

    pbone.custom_shape = new_obj
    return new_obj


def _fit_controller_custom_shapes(rig):
    if rig is None or rig.type != "ARMATURE":
        return

    meshes_using_rig = _get_filtered_meshes_for_shape_fit(
        rig, _get_meshes_using_rig(rig)
    )
    if not meshes_using_rig:
        return

    hips_pb = _get_armature_pose_bone(rig, c_prefix + spine_rig_names["pelvis"])
    if hips_pb is not None:
        _fit_torso_circle_shape_to_meshes(rig, hips_pb, meshes_using_rig, margin=0.06)

    hips_free_pb = _get_armature_pose_bone(rig, c_prefix + spine_rig_names["hips_free"])
    if hips_free_pb is not None:
        _fit_torso_circle_shape_to_meshes(
            rig,
            hips_free_pb,
            meshes_using_rig,
            margin=0.03,
        )

    if "kai_spine_names" in rig.data.keys():
        kai_spine_names = [
            name for name in rig.data.get("kai_spine_names", "").split(",")
            if name
        ]
    else:
        kai_spine_names = [
            spine_names["spine1"],
            spine_names["spine2"],
        ]
    kai_chest_name = rig.data.get("kai_chest_name", "") or spine_names["spine3"]
    torso_ctrl_names = [
        pair["control_name"]
        for pair in _kai_build_spine_control_pairs(
            kai_spine_names,
            kai_chest_name,
        )
    ] + [
        c_prefix + head_rig_names["neck"],
    ]

    for bone_name in dict.fromkeys(torso_ctrl_names):
        torso_pb = _get_armature_pose_bone(rig, bone_name)
        if torso_pb is not None:
            _fit_torso_circle_shape_to_meshes(rig, torso_pb, meshes_using_rig)

    c_head_pb = _get_armature_pose_bone(rig, c_prefix + head_rig_names["head"])
    if c_head_pb is not None:
        _fit_head_circle_shape_to_meshes(rig, c_head_pb, meshes_using_rig)

    for side in ("Left", "Right"):
        c_hand_ik_pb = _get_armature_pose_bone(
            rig, c_prefix + arm_rig_names["hand_ik"] + "_" + side
        )
        c_hand_fk_pb = _get_armature_pose_bone(
            rig, c_prefix + arm_rig_names["hand_fk"] + "_" + side
        )
        if c_hand_ik_pb is not None:
            if _fit_hand_circle_shape_to_meshes(rig, c_hand_ik_pb, meshes_using_rig):
                _copy_custom_shape_geometry(rig, c_hand_ik_pb, c_hand_fk_pb)
        elif c_hand_fk_pb is not None:
            _fit_hand_circle_shape_to_meshes(rig, c_hand_fk_pb, meshes_using_rig)


def _raycast_meshes_world(meshes, depsgraph, origin_world, direction_world, distance):
    best_hit_world = None
    best_hit_dist = None

    for obj in meshes:
        try:
            eval_obj = obj.evaluated_get(depsgraph)
        except RuntimeError as exc:
            _warn_shape_fit_mesh_once(obj, "evaluate", exc)
            continue

        if eval_obj.type != "MESH":
            continue

        inv_world = eval_obj.matrix_world.inverted_safe()
        direction_local = inv_world.to_3x3() @ direction_world
        if direction_local.length_squared < 1e-12:
            continue
        direction_local.normalize()

        try:
            hit, location, _normal, _face_index = eval_obj.ray_cast(
                inv_world @ origin_world,
                direction_local,
                distance=distance,
            )
        except RuntimeError as exc:
            _warn_shape_fit_mesh_once(obj, "ray cast", exc)
            continue

        if not hit:
            continue

        hit_world = eval_obj.matrix_world @ location
        hit_dist = (hit_world - origin_world).length
        if best_hit_dist is None or hit_dist < best_hit_dist:
            best_hit_dist = hit_dist
            best_hit_world = hit_world

    return best_hit_world, best_hit_dist


def _get_mesh_vertices_world(meshes, depsgraph, center_world=None, max_distance=None):
    vertices_world = []
    max_distance_sq = None
    if center_world is not None and max_distance is not None:
        max_distance_sq = max_distance * max_distance

    for obj in meshes:
        if obj.type != "MESH":
            continue

        if center_world is not None and max_distance is not None:
            info = _get_evaluated_mesh_info(obj, depsgraph)
            if info is None:
                continue
            obj_radius = max(info["diagonal_world"] * 0.5, 0.001)
            if (info["center_world"] - center_world).length > max_distance + obj_radius:
                continue

        try:
            eval_obj = obj.evaluated_get(depsgraph)
        except RuntimeError as exc:
            _warn_shape_fit_mesh_once(obj, "evaluate", exc)
            continue

        if eval_obj.type != "MESH":
            continue

        try:
            mesh_data = eval_obj.to_mesh()
        except RuntimeError as exc:
            _warn_shape_fit_mesh_once(obj, "read evaluated", exc)
            continue

        try:
            world_matrix = eval_obj.matrix_world
            for vert in mesh_data.vertices:
                vert_world = world_matrix @ vert.co
                if (
                    center_world is not None
                    and max_distance_sq is not None
                    and (vert_world - center_world).length_squared > max_distance_sq
                ):
                    continue
                vertices_world.append(vert_world)
        finally:
            if mesh_data is not None:
                eval_obj.to_mesh_clear()

    return vertices_world


def _get_evaluated_mesh_info(obj, depsgraph):
    if obj is None or obj.type != "MESH":
        return None

    try:
        eval_obj = obj.evaluated_get(depsgraph)
    except RuntimeError as exc:
        _warn_shape_fit_mesh_once(obj, "evaluate", exc)
        return None

    if eval_obj.type != "MESH":
        return None

    try:
        mesh_data = eval_obj.to_mesh()
    except RuntimeError as exc:
        _warn_shape_fit_mesh_once(obj, "read evaluated", exc)
        return None

    try:
        if not mesh_data.vertices:
            return {
                "object": obj,
                "center_world": eval_obj.matrix_world.translation.copy(),
                "dimensions_world": Vector((0.0, 0.0, 0.0)),
                "diagonal_world": 0.0,
                "vertex_count": 0,
            }

        world_matrix = eval_obj.matrix_world
        first_world = world_matrix @ mesh_data.vertices[0].co
        min_corner = first_world.copy()
        max_corner = first_world.copy()

        for vert in mesh_data.vertices[1:]:
            vert_world = world_matrix @ vert.co
            min_corner.x = min(min_corner.x, vert_world.x)
            min_corner.y = min(min_corner.y, vert_world.y)
            min_corner.z = min(min_corner.z, vert_world.z)
            max_corner.x = max(max_corner.x, vert_world.x)
            max_corner.y = max(max_corner.y, vert_world.y)
            max_corner.z = max(max_corner.z, vert_world.z)

        dimensions_world = max_corner - min_corner
        return {
            "object": obj,
            "center_world": (min_corner + max_corner) * 0.5,
            "dimensions_world": dimensions_world,
            "diagonal_world": dimensions_world.length,
            "vertex_count": len(mesh_data.vertices),
        }
    finally:
        if mesh_data is not None:
            eval_obj.to_mesh_clear()


def _get_filtered_meshes_for_shape_fit(rig, meshes):
    if not meshes:
        return []

    depsgraph = bpy.context.evaluated_depsgraph_get()
    mesh_infos = []
    diagonals = []

    for mesh in meshes:
        info = _get_evaluated_mesh_info(mesh, depsgraph)
        if info is None:
            continue
        mesh_infos.append(info)
        if info["diagonal_world"] > 0.0:
            diagonals.append(info["diagonal_world"])

    if not mesh_infos:
        return []

    diagonals.sort()
    median_diagonal = diagonals[len(diagonals) // 2] if diagonals else 0.0
    diagonal_limit = max(median_diagonal * 4.0, 5.0) if median_diagonal > 0.0 else 5.0

    filtered_meshes = []

    for info in mesh_infos:
        if median_diagonal > 0.0 and info["diagonal_world"] > diagonal_limit:
            continue

        filtered_meshes.append(info["object"])
    return filtered_meshes


def _get_shape_plane_normal_local(verts, center_local):
    offsets = []
    for vert in verts:
        offset = vert.co - center_local
        if offset.length_squared > 1e-12:
            offsets.append(offset)

    for i, offset_a in enumerate(offsets):
        for offset_b in offsets[i + 1 :]:
            normal = offset_a.cross(offset_b)
            if normal.length_squared > 1e-12:
                normal.normalize()
                return normal

    return Vector((0.0, 0.0, 1.0))


def _get_pose_bone_mid_axis_world(rig, pbone):
    if rig is None or pbone is None:
        return None, None

    midpoint_object = (pbone.head + pbone.tail) * 0.5
    midpoint_world = rig.matrix_world @ midpoint_object

    axis_object = pbone.tail - pbone.head
    if axis_object.length_squared <= 1e-12:
        return midpoint_world, None

    axis_world = rig.matrix_world.to_3x3() @ axis_object
    if axis_world.length_squared <= 1e-12:
        return midpoint_world, None

    axis_world.normalize()
    return midpoint_world, axis_world


def _scale_shape_points_in_plane(shape_obj, display_matrix, target_radius_world):
    if shape_obj is None or shape_obj.data is None or not shape_obj.data.vertices:
        return

    verts = shape_obj.data.vertices
    center_local = sum((v.co for v in verts), Vector((0.0, 0.0, 0.0))) / len(verts)
    plane_normal_local = _get_shape_plane_normal_local(verts, center_local)

    center_world = display_matrix @ center_local
    normal_world = display_matrix.to_3x3() @ plane_normal_local
    if normal_world.length_squared < 1e-12:
        return
    normal_world.normalize()

    current_radius_world = 0.0
    for vert in verts:
        point_world = display_matrix @ vert.co
        plane_offset_world = point_world - center_world
        plane_offset_world -= normal_world * plane_offset_world.dot(normal_world)
        current_radius_world = max(current_radius_world, plane_offset_world.length)

    if current_radius_world <= 1e-8:
        return

    if abs(target_radius_world - current_radius_world) < 1e-4:
        return

    scale_factor = target_radius_world / current_radius_world
    for vert in verts:
        local_offset = vert.co - center_local
        local_normal_offset = plane_normal_local * local_offset.dot(plane_normal_local)
        local_plane_offset = local_offset - local_normal_offset
        vert.co = center_local + local_plane_offset * scale_factor + local_normal_offset

    shape_obj.data.update()


def _get_shape_radial_samples_world(
    display_matrix,
    verts,
    center_world,
    plane_normal_world,
    sample_mode="verts",
):
    projected_offsets_world = []
    current_radius_world = 0.0
    directions_world = []

    for vert in verts:
        point_world = display_matrix @ vert.co
        plane_offset_world = point_world - center_world
        plane_offset_world -= (
            plane_normal_world * plane_offset_world.dot(plane_normal_world)
        )
        if plane_offset_world.length <= 1e-8:
            continue
        projected_offsets_world.append(plane_offset_world)

    if not projected_offsets_world:
        return 0.0, []

    if sample_mode != "edge_midpoints":
        for plane_offset_world in projected_offsets_world:
            current_radius_world = max(current_radius_world, plane_offset_world.length)
            directions_world.append(plane_offset_world.normalized())
        return current_radius_world, directions_world

    basis_u = projected_offsets_world[0].normalized()
    basis_v = plane_normal_world.cross(basis_u)
    if basis_v.length_squared <= 1e-12:
        for plane_offset_world in projected_offsets_world:
            current_radius_world = max(current_radius_world, plane_offset_world.length)
            directions_world.append(plane_offset_world.normalized())
        return current_radius_world, directions_world
    basis_v.normalize()

    sorted_offsets = sorted(
        projected_offsets_world,
        key=lambda offset: math.atan2(offset.dot(basis_v), offset.dot(basis_u)),
    )

    for idx, offset_a in enumerate(sorted_offsets):
        offset_b = sorted_offsets[(idx + 1) % len(sorted_offsets)]
        midpoint_offset = (offset_a + offset_b) * 0.5
        if midpoint_offset.length <= 1e-8:
            continue
        current_radius_world = max(current_radius_world, midpoint_offset.length)
        directions_world.append(midpoint_offset.normalized())

    if not directions_world:
        for plane_offset_world in projected_offsets_world:
            current_radius_world = max(current_radius_world, plane_offset_world.length)
            directions_world.append(plane_offset_world.normalized())

    return current_radius_world, directions_world


def _scale_shape_points_in_plane_with_mode(
    shape_obj,
    display_matrix,
    target_radius_world,
    sample_mode="verts",
):
    if shape_obj is None or shape_obj.data is None or not shape_obj.data.vertices:
        return

    verts = shape_obj.data.vertices
    center_local = sum((v.co for v in verts), Vector((0.0, 0.0, 0.0))) / len(verts)
    plane_normal_local = _get_shape_plane_normal_local(verts, center_local)

    center_world = display_matrix @ center_local
    plane_normal_world = display_matrix.to_3x3() @ plane_normal_local
    if plane_normal_world.length_squared < 1e-12:
        return
    plane_normal_world.normalize()

    current_radius_world, _directions_world = _get_shape_radial_samples_world(
        display_matrix,
        verts,
        center_world,
        plane_normal_world,
        sample_mode=sample_mode,
    )

    if current_radius_world <= 1e-8:
        return

    if abs(target_radius_world - current_radius_world) < 1e-4:
        return

    scale_factor = target_radius_world / current_radius_world
    for vert in verts:
        local_offset = vert.co - center_local
        local_normal_offset = plane_normal_local * local_offset.dot(plane_normal_local)
        local_plane_offset = local_offset - local_normal_offset
        vert.co = center_local + local_plane_offset * scale_factor + local_normal_offset

    shape_obj.data.update()


def _copy_custom_shape_geometry(rig, source_pbone, target_pbone):
    if source_pbone is None or target_pbone is None:
        return

    source_shape = _ensure_unique_custom_shape_copy(rig, source_pbone)
    target_shape = _ensure_unique_custom_shape_copy(rig, target_pbone)
    if source_shape is None or target_shape is None or source_shape.data is None:
        return

    if target_shape.data is not None and target_shape.data != source_shape.data:
        target_shape.data = source_shape.data.copy()
        target_shape.data.name = target_shape.name
    elif target_shape.data is None:
        target_shape.data = source_shape.data.copy()
        target_shape.data.name = target_shape.name

def _get_source_data_bone(rig, base_name):
    if rig is None or rig.type != "ARMATURE":
        return None

    candidates = [
        base_name,
        "mixamorig:" + base_name,
    ]

    for bone_name in candidates:
        bone = rig.data.bones.get(bone_name)
        if bone is not None:
            return bone

    for bone in rig.data.bones:
        if bone.name.endswith(":" + base_name):
            return bone

    return None


def _fit_hand_circle_shape_to_meshes(rig, pbone, meshes, margin=0.01):
    shape_obj = getattr(pbone, "custom_shape", None)
    if shape_obj is None or shape_obj.data is None or not shape_obj.data.vertices:
        return False
    if not meshes or pbone is None:
        return False

    display_matrix = _get_custom_shape_display_matrix(rig, pbone)
    verts = shape_obj.data.vertices
    center_local = sum((v.co for v in verts), Vector((0.0, 0.0, 0.0))) / len(verts)
    center_world = display_matrix @ center_local
    plane_normal_local = _get_shape_plane_normal_local(verts, center_local)

    normal_world = display_matrix.to_3x3() @ plane_normal_local
    if normal_world.length_squared < 1e-12:
        return False
    normal_world.normalize()

    current_radius_world = 0.0
    directions_world = []
    for vert in verts:
        point_world = display_matrix @ vert.co
        plane_offset_world = point_world - center_world
        plane_offset_world -= normal_world * plane_offset_world.dot(normal_world)
        radius_world = plane_offset_world.length
        if radius_world <= 1e-8:
            continue
        current_radius_world = max(current_radius_world, radius_world)
        directions_world.append(plane_offset_world.normalized())

    if current_radius_world <= 1e-8 or not directions_world:
        return False

    depsgraph = bpy.context.evaluated_depsgraph_get()
    search_distance = max(current_radius_world * 2.5 + margin, 0.15)
    for obj in meshes:
        info = _get_evaluated_mesh_info(obj, depsgraph)
        if info is None:
            continue
        search_distance = max(
            search_distance,
            (info["center_world"] - center_world).length + info["diagonal_world"] * 0.5,
        )

    target_radius_world = 0.0
    found_hit = False
    ray_hits = 0
    clearance_world = margin * 4.0
    for direction_world in directions_world:
        hit_world, _hit_distance = _raycast_meshes_world(
            meshes,
            depsgraph,
            center_world,
            direction_world,
            search_distance,
        )
        if hit_world is None:
            continue

        hit_radius_world = max(
            (hit_world - center_world).dot(direction_world),
            0.0,
        )
        target_radius_world = max(
            target_radius_world,
            hit_radius_world + clearance_world,
        )
        found_hit = True
        ray_hits += 1

    if not found_hit:
        return False

    shape_obj = _ensure_unique_custom_shape_copy(rig, pbone)
    if shape_obj is None or shape_obj.data is None or not shape_obj.data.vertices:
        return False

    _scale_shape_points_in_plane(shape_obj, display_matrix, target_radius_world)
    return True


def _fit_torso_circle_shape_to_meshes(rig, pbone, meshes, margin=0.01):
    shape_obj = getattr(pbone, "custom_shape", None)
    if shape_obj is None or shape_obj.data is None or not shape_obj.data.vertices:
        return False
    if not meshes or pbone is None:
        return False

    center_world, axis_world = _get_pose_bone_mid_axis_world(rig, pbone)
    if center_world is None or axis_world is None:
        return False

    display_matrix = _get_custom_shape_display_matrix(rig, pbone)
    verts = shape_obj.data.vertices
    sample_mode = "verts"
    if pbone.name == c_prefix + spine_rig_names["pelvis"]:
        sample_mode = "edge_midpoints"

    current_radius_world, directions_world = _get_shape_radial_samples_world(
        display_matrix,
        verts,
        center_world,
        axis_world,
        sample_mode=sample_mode,
    )

    if current_radius_world <= 1e-8 or not directions_world:
        return False

    depsgraph = bpy.context.evaluated_depsgraph_get()
    search_distance = max(current_radius_world * 2.5 + margin, 0.15)
    for obj in meshes:
        info = _get_evaluated_mesh_info(obj, depsgraph)
        if info is None:
            continue
        search_distance = max(
            search_distance,
            (info["center_world"] - center_world).length + info["diagonal_world"] * 0.5,
        )

    target_radius_world = 0.0
    found_hit = False
    ray_hits = 0
    for direction_world in directions_world:
        hit_world, _hit_distance = _raycast_meshes_world(
            meshes,
            depsgraph,
            center_world,
            direction_world,
            search_distance,
        )
        if hit_world is None:
            continue

        hit_radius_world = max((hit_world - center_world).dot(direction_world), 0.0)
        target_radius_world = max(target_radius_world, hit_radius_world + margin)
        found_hit = True
        ray_hits += 1

    if not found_hit:
        return False

    shape_obj = _ensure_unique_custom_shape_copy(rig, pbone)
    if shape_obj is None or shape_obj.data is None or not shape_obj.data.vertices:
        return False

    _scale_shape_points_in_plane_with_mode(
        shape_obj,
        display_matrix,
        target_radius_world,
        sample_mode=sample_mode,
    )
    return True


def _fit_head_circle_shape_to_meshes(rig, pbone, meshes, margin=0.01):
    shape_obj = getattr(pbone, "custom_shape", None)
    if shape_obj is None or shape_obj.data is None or not shape_obj.data.vertices:
        return False
    if not meshes or pbone is None:
        return False

    display_matrix = _get_custom_shape_display_matrix(rig, pbone)
    inv_display = display_matrix.inverted_safe()
    verts = shape_obj.data.vertices
    world_points = [display_matrix @ vert.co for vert in verts]
    center_world = sum(world_points, Vector((0.0, 0.0, 0.0))) / len(world_points)
    center_xy = Vector((center_world.x, center_world.y))

    radius_world = 0.0
    plane_z_world = 0.0
    for point_world in world_points:
        radius_world = max(
            radius_world,
            (Vector((point_world.x, point_world.y)) - center_xy).length,
        )
        plane_z_world += point_world.z
    plane_z_world /= len(world_points)

    if radius_world <= 1e-8:
        return False

    depsgraph = bpy.context.evaluated_depsgraph_get()
    mesh_vertices_world = _get_mesh_vertices_world(meshes, depsgraph)
    if not mesh_vertices_world:
        return False

    max_mesh_z_world = None
    radial_limit = radius_world + margin
    for vert_world in mesh_vertices_world:
        if (Vector((vert_world.x, vert_world.y)) - center_xy).length <= radial_limit:
            if max_mesh_z_world is None or vert_world.z > max_mesh_z_world:
                max_mesh_z_world = vert_world.z

    if max_mesh_z_world is None:
        return False

    shape_obj = _ensure_unique_custom_shape_copy(rig, pbone)
    if shape_obj is None or shape_obj.data is None or not shape_obj.data.vertices:
        return False
    verts = shape_obj.data.vertices

    z_offset_world = (max_mesh_z_world + margin) - plane_z_world
    if abs(z_offset_world) < 1e-4:
        z_offset_world = 0.0

    if abs(z_offset_world) >= 1e-4:
        local_delta = inv_display.to_3x3() @ Vector((0.0, 0.0, z_offset_world))
        for vert in verts:
            vert.co += local_delta

        shape_obj.data.update()

    updated_world_points = [display_matrix @ vert.co for vert in verts]
    updated_center_world = sum(
        updated_world_points, Vector((0.0, 0.0, 0.0))
    ) / len(updated_world_points)
    updated_center_xy = Vector((updated_center_world.x, updated_center_world.y))

    head_bone = _get_source_data_bone(rig, head_names["head"])
    if head_bone is None:
        return False

    head_mid_world = rig.matrix_world @ (
        (head_bone.head_local + head_bone.tail_local) * 0.5
    )
    head_length_world = (
        rig.matrix_world @ head_bone.tail_local
        - rig.matrix_world @ head_bone.head_local
    ).length
    slice_half_height = max(head_length_world * 0.2, margin * 2.0, 0.01)

    radial_samples = []
    for vert_world in mesh_vertices_world:
        if abs(vert_world.z - head_mid_world.z) <= slice_half_height:
            radial_samples.append(
                (Vector((vert_world.x, vert_world.y)) - updated_center_xy).length
            )

    if not radial_samples:
        expanded_half_height = slice_half_height * 2.0
        for vert_world in mesh_vertices_world:
            if abs(vert_world.z - head_mid_world.z) <= expanded_half_height:
                radial_samples.append(
                    (Vector((vert_world.x, vert_world.y)) - updated_center_xy).length
                )

    if not radial_samples:
        return False

    target_radius_world = max(radial_samples) + margin
    _scale_shape_points_in_plane(shape_obj, display_matrix, target_radius_world)
    return True


# OPERATOR CLASSES
##################
class MR_OT_update(bpy.types.Operator):  # noqa: N801
    """Update old control rig to Blender 3.0 and newer"""

    bl_idname = "mr.update"
    bl_label = "update"
    bl_options = {"UNDO"}

    @classmethod
    def poll(cls, context):
        if context.active_object:
            if context.active_object.type == "ARMATURE":
                return "mr_control_rig" in context.active_object.data.keys()

    def execute(self, context):
        try:
            _update(self, context)
        finally:
            pass

        return {"FINISHED"}


class MR_OT_reconnect_rig(bpy.types.Operator):  # noqa: N801
    """Rebuild all constraints for the existing Mixamo control rig"""

    bl_idname = "mr.reconnect_rig"
    bl_label = "reconnect_rig"
    bl_options = {"UNDO"}

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        if obj and obj.type == "ARMATURE":
            return "mr_control_rig" in obj.data.keys()
        return False

    def execute(self, context):
        use_global_undo = context.preferences.edit.use_global_undo
        context.preferences.edit.use_global_undo = False

        try:
            _reconnect_rig_constraints(context)
        finally:
            context.preferences.edit.use_global_undo = use_global_undo

        return {"FINISHED"}



class MR_OT_reset_generated_rig(bpy.types.Operator):  # noqa: N801
    """Remove Kai-generated rig data while keeping the reference skeleton"""

    bl_idname = "mr.reset_generated_rig"
    bl_label = "Reset Generated Rig"
    bl_description = "Remove Kai-generated control rig bones and constraints only"
    bl_options = {"UNDO"}

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return bool(obj and obj.type == "ARMATURE")

    def execute(self, context):
        try:
            _kai_reset_generated_rig(context, self)
        except RuntimeError as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        return {"FINISHED"}


class MR_OT_rebuild_rig(bpy.types.Operator):  # noqa: N801
    """Reset Kai-generated rig data and generate the rig again"""

    bl_idname = "mr.rebuild_rig"
    bl_label = "Rebuild Rig"
    bl_description = "Reset generated rig data, then generate a fresh rig from the current reference skeleton"
    bl_options = {"UNDO"}

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return bool(obj and obj.type == "ARMATURE")

    def execute(self, context):
        rig = context.active_object
        try:
            mapping_names = _kai_validate_mapping_for_rebuild(rig, self)
        except RuntimeError as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        spines = mapping_names.get("spines", [])[:6]
        necks = mapping_names.get("necks", [])[:3]
        shoulders = mapping_names.get("shoulders", {})

        try:
            _kai_reset_generated_rig(context, self)
        except RuntimeError as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}

        try:
            result = bpy.ops.mr.make_rig(
                "EXEC_DEFAULT",
                bake_anim=False,
                ik_arms=True,
                ik_legs=True,
                use_optional_spine=bool(spines),
                use_optional_neck=bool(necks),
                use_optional_shoulder=bool(
                    shoulders.get("Left", "") or shoulders.get("Right", "")
                ),
                map_hip=mapping_names.get("hip", spine_names["pelvis"]),
                map_spine1=spines[0] if len(spines) > 0 else "",
                map_spine2=spines[1] if len(spines) > 1 else "",
                map_spine3=spines[2] if len(spines) > 2 else "",
                map_spine4=spines[3] if len(spines) > 3 else "",
                map_spine5=spines[4] if len(spines) > 4 else "",
                map_spine6=spines[5] if len(spines) > 5 else "",
                map_chest=mapping_names.get("chest", spine_names["spine3"]),
                map_neck1=necks[0] if len(necks) > 0 else "",
                map_neck2=necks[1] if len(necks) > 1 else "",
                map_neck3=necks[2] if len(necks) > 2 else "",
                map_head=mapping_names.get("head", head_names["head"]),
                map_shoulder_left=shoulders.get("Left", ""),
                map_shoulder_right=shoulders.get("Right", ""),
            )
        except Exception as exc:
            self.report({"ERROR"}, f"Rebuild Rig failed during Generate Rig: {exc}")
            return {"CANCELLED"}

        if "FINISHED" not in result:
            self.report({"ERROR"}, "Generate Rig did not finish")
            return {"CANCELLED"}

        self.report({"INFO"}, "Rebuild Rig Done!")
        return {"FINISHED"}


class MR_OT_fix_fk_foot_setup(bpy.types.Operator):  # noqa: N801
    """Repair the legacy FK foot helper setup on an existing control rig"""

    bl_idname = "mr.fix_fk_foot_setup"
    bl_label = "fix_fk_foot_setup"
    bl_options = {"UNDO"}

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        if obj and obj.type == "ARMATURE":
            return "mr_control_rig" in obj.data.keys()
        return False

    def execute(self, context):
        use_global_undo = context.preferences.edit.use_global_undo
        context.preferences.edit.use_global_undo = False

        try:
            fixed_sides = _repair_fk_foot_setup(context)
            if fixed_sides:
                self.report(
                    {"INFO"},
                    "Fixed FK foot setup for " + ", ".join(fixed_sides),
                )
            else:
                self.report({"INFO"}, "FK foot setup already matches legacy rig")
        finally:
            context.preferences.edit.use_global_undo = use_global_undo

        return {"FINISHED"}


class MR_OT_exportGLTF(bpy.types.Operator):  # noqa: N801
    """Export to GLTF format"""

    bl_idname = "mr.export_gltf"
    bl_label = "export_gltf"
    bl_options = {"UNDO"}

    @classmethod
    def poll(cls, context):
        if context.active_object:
            if context.active_object.type == "ARMATURE":
                return True

    def execute(self, context):
        try:
            bpy.ops.export_scene.gltf()
        finally:
            pass

        return {"FINISHED"}


class MR_OT_apply_shape(bpy.types.Operator):  # noqa: N801
    """Apply the selected shape"""

    bl_idname = "mr.apply_shape"
    bl_label = "apply_shape"
    bl_options = {"UNDO"}

    @classmethod
    def poll(cls, context):
        if context.active_object:
            if context.mode == "EDIT_MESH":
                if "cs_user" in context.active_object.name:
                    return True

    def execute(self, context):
        use_global_undo = context.preferences.edit.use_global_undo
        context.preferences.edit.use_global_undo = False

        try:
            _apply_shape()
        finally:
            context.preferences.edit.use_global_undo = use_global_undo
        return {"FINISHED"}


class MR_OT_edit_custom_shape(bpy.types.Operator):  # noqa: N801
    """Edit the selected bone shape"""

    bl_idname = "mr.edit_custom_shape"
    bl_label = "edit_custom_shape"
    bl_options = {"UNDO"}

    @classmethod
    def poll(cls, context):
        if context.mode == "POSE":
            if context.active_pose_bone:
                return True

    def execute(self, context):
        try:
            cs = context.active_pose_bone.custom_shape
            if cs:
                _edit_custom_shape()
            else:
                self.report({"ERROR"}, "No custom shapes set for this bone.")

        finally:
            pass

        return {"FINISHED"}


class MR_OT_create_reference_skeleton(bpy.types.Operator):  # noqa: N801
    bl_idname = "mr.create_reference_skeleton"
    bl_label = "Create Reference Skeleton"
    bl_description = "Create a Kai Reference Skeleton from the selected bundled template"
    bl_options = {"REGISTER", "UNDO"}

    template_key: bpy.props.EnumProperty(
        name="Template",
        items=KAI_REFERENCE_TEMPLATE_ITEMS,
        default=DEFAULT_REFERENCE_TEMPLATE,
    )

    def execute(self, context):
        template = KAI_REFERENCE_TEMPLATES.get(self.template_key)
        if template is None:
            self.report({"ERROR"}, f"Reference template not found: {self.template_key}")
            return {"CANCELLED"}

        try:
            armature = _kai_create_reference_skeleton_from_template(template)
        except RuntimeError as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}

        errors = _kai_validate_reference_skeleton(armature, template)
        if errors:
            self.report(
                {"ERROR"},
                "Reference Skeleton validation failed: " + "; ".join(errors[:3]),
            )
            print("[Kai] Reference Skeleton validation errors:")
            for error in errors:
                print("  " + error)
            return {"CANCELLED"}

        self.report(
            {"INFO"},
            f"Created {template.get('name', armature.name)} ({len(template.get('bones', []))} bones)",
        )
        return {"FINISHED"}


class MR_OT_make_rig(bpy.types.Operator):  # noqa: N801
    """Generate a control rig from the selected Mixamo skeleton"""

    bl_idname = "mr.make_rig"
    bl_label = "Generate Rig"
    bl_options = {"UNDO"}

    bake_anim: bpy.props.BoolProperty(
        name="Bake Anim",
        description="Bake animation to the control bones",
        default=True,
    )
    retarget_rotation_output: bpy.props.EnumProperty(
        name="Retarget Rotation Output",
        description="Rotation channel type used when baking retargeted animation",
        items=RETARGET_ROTATION_OUTPUT_ITEMS,
        default="QUATERNION",
    )

    ik_arms: bpy.props.BoolProperty(
        name="IK Hands",
        description=(
            "Use IK for arm bones, otherwise use FK "
            "(can be toggled later using the rig properties)"
        ),
        default=True,
    )
    ik_legs: bpy.props.BoolProperty(
        name="IK Legs",
        description=(
            "Use IK for leg bones, otherwise use FK "
            "(can be toggled later using the rig properties)"
        ),
        default=True,
    )

    use_optional_spine: bpy.props.BoolProperty(
        name="Optional Spine",
        description="Use optional Spine mapping fields",
        default=True,
    )
    use_optional_neck: bpy.props.BoolProperty(
        name="Optional Neck",
        description="Use optional Neck mapping fields",
        default=True,
    )
    use_optional_shoulder: bpy.props.BoolProperty(
        name="Optional Shoulder",
        description="Use optional Shoulder mapping fields",
        default=True,
    )

    map_hip: bpy.props.StringProperty(name="Hip", default="Hips")
    map_spine1: bpy.props.StringProperty(name="Spine 1", default="Spine")
    map_spine2: bpy.props.StringProperty(name="Spine 2", default="Spine1")
    map_spine3: bpy.props.StringProperty(name="Spine 3", default="")
    map_spine4: bpy.props.StringProperty(name="Spine 4", default="")
    map_spine5: bpy.props.StringProperty(name="Spine 5", default="")
    map_spine6: bpy.props.StringProperty(name="Spine 6", default="")
    map_chest: bpy.props.StringProperty(name="Chest", default="Chest")

    map_neck1: bpy.props.StringProperty(name="Neck 1", default="Neck")
    map_neck2: bpy.props.StringProperty(name="Neck 2", default="")
    map_neck3: bpy.props.StringProperty(name="Neck 3", default="")
    map_head: bpy.props.StringProperty(name="Head", default="Head")
    map_shoulder_left: bpy.props.StringProperty(
        name="Shoulder Left",
        default="LeftShoulder",
    )
    map_shoulder_right: bpy.props.StringProperty(
        name="Shoulder Right",
        default="RightShoulder",
    )

    animated_armature = None

    @classmethod
    def poll(cls, context):
        if context.active_object:
            if context.active_object.type == "ARMATURE":
                if "mr_control_rig" not in context.active_object.data.keys():
                    return True
        return False

    def invoke(self, context, event):
        wm = context.window_manager
        return wm.invoke_props_dialog(self, width=450)

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "bake_anim", text="Apply Animation")
        if self.bake_anim:
            layout.prop(
                self,
                "retarget_rotation_output",
                text="Rotation Output",
            )
        layout.prop(self, "ik_arms", text="IK Arms")
        layout.prop(self, "ik_legs", text="IK Legs")

        box = layout.box()
        box.label(text="MixamoRig Kai Mapping")

        box.prop_search(self, "map_hip", context.active_object.data, "bones", text="Hip")
        box.prop_search(self, "map_chest", context.active_object.data, "bones", text="Chest")
        box.prop_search(self, "map_head", context.active_object.data, "bones", text="Head")

        box.separator()
        row = box.row()
        row.label(text="Optional Spine")
        row.prop(self, "use_optional_spine", text="")
        if self.use_optional_spine:
            box.prop_search(self, "map_spine1", context.active_object.data, "bones", text="Spine 1")
            box.prop_search(self, "map_spine2", context.active_object.data, "bones", text="Spine 2")
            box.prop_search(self, "map_spine3", context.active_object.data, "bones", text="Spine 3")
            box.prop_search(self, "map_spine4", context.active_object.data, "bones", text="Spine 4")
            box.prop_search(self, "map_spine5", context.active_object.data, "bones", text="Spine 5")
            box.prop_search(self, "map_spine6", context.active_object.data, "bones", text="Spine 6")

        box.separator()
        row = box.row()
        row.label(text="Optional Neck")
        row.prop(self, "use_optional_neck", text="")
        if self.use_optional_neck:
            box.prop_search(self, "map_neck1", context.active_object.data, "bones", text="Neck 1")
            box.prop_search(self, "map_neck2", context.active_object.data, "bones", text="Neck 2")
            box.prop_search(self, "map_neck3", context.active_object.data, "bones", text="Neck 3")

        box.separator()
        row = box.row()
        row.label(text="Optional Shoulder")
        row.prop(self, "use_optional_shoulder", text="")
        if self.use_optional_shoulder:
            box.prop_search(self, "map_shoulder_left", context.active_object.data, "bones", text="Left")
            box.prop_search(self, "map_shoulder_right", context.active_object.data, "bones", text="Right")

    def execute(self, context):
        debug = False

        spine_names = [
            self.map_spine1,
            self.map_spine2,
            self.map_spine3,
            self.map_spine4,
            self.map_spine5,
            self.map_spine6,
        ]

        neck_names = [
            self.map_neck1,
            self.map_neck2,
            self.map_neck3,
        ]
        shoulder_names = {
            "Left": self.map_shoulder_left if self.use_optional_shoulder else "",
            "Right": self.map_shoulder_right if self.use_optional_shoulder else "",
        }

        spine_names = [
            name for name in spine_names
            if self.use_optional_spine and name
        ]
        neck_names = [
            name for name in neck_names
            if self.use_optional_neck and name
        ]

        self.report(
            {"INFO"},
            (
                f"[Kai] Hip={self.map_hip} | "
                f"Spine={', '.join(spine_names)} | "
                f"Chest={self.map_chest} | "
                f"Neck={', '.join(neck_names)} | "
                f"Head={self.map_head} | "
                f"Shoulders={shoulder_names}"
            )
        )

        arm = context.active_object

        hip_bone = arm.data.bones.get(self.map_hip)
        chest_bone = arm.data.bones.get(self.map_chest)
        head_bone = arm.data.bones.get(self.map_head)
        shoulder_bones = {
            side: arm.data.bones.get(name) if name else None
            for side, name in shoulder_names.items()
        }

        spine_bones = [
            arm.data.bones.get(name)
            for name in spine_names
            if arm.data.bones.get(name) is not None
        ]
        neck_bones = [
            arm.data.bones.get(name)
            for name in neck_names
            if arm.data.bones.get(name) is not None
        ]
        hip_bone_name = _kai_safe_bone_name(hip_bone)
        chest_bone_name = _kai_safe_bone_name(chest_bone)
        head_bone_name = _kai_safe_bone_name(head_bone)
        spine_bone_names = [
            name for name in (_kai_safe_bone_name(bone) for bone in spine_bones)
            if name
        ]
        neck_bone_names = [
            name for name in (_kai_safe_bone_name(bone) for bone in neck_bones)
            if name
        ]
        missing_optional_spines = [
            name for name in spine_names
            if arm.data.bones.get(name) is None
        ]
        missing_optional_necks = [
            name for name in neck_names
            if arm.data.bones.get(name) is None
        ]
        missing_optional_shoulders = [
            name for name in shoulder_names.values()
            if name and arm.data.bones.get(name) is None
        ]

        missing_bones = []

        if hip_bone is None:
            missing_bones.append(self.map_hip)
        if chest_bone is None:
            missing_bones.append(self.map_chest)
        if head_bone is None:
            missing_bones.append(self.map_head)
        if hip_bone is not None and not hip_bone_name:
            missing_bones.append(self.map_hip)
        if chest_bone is not None and not chest_bone_name:
            missing_bones.append(self.map_chest)
        if head_bone is not None and not head_bone_name:
            missing_bones.append(self.map_head)

        if missing_bones:
            self.report(
                {"ERROR"},
                "[Kai] Missing bones: " + ", ".join(missing_bones)
            )
            return {"CANCELLED"}

        if missing_optional_spines or missing_optional_necks or missing_optional_shoulders:
            self.report(
                {"WARNING"},
                (
                    "[Kai] Ignored missing optional bones: "
                    + ", ".join(
                        missing_optional_spines
                        + missing_optional_necks
                        + missing_optional_shoulders
                    )
                )
            )

        self.report(
            {"INFO"},
            "[Kai] Spine bones OK: " + ", ".join(spine_bone_names)
        )

        self.report(
            {"INFO"},
            "[Kai] Neck bones OK: " + ", ".join(neck_bone_names)
        )

        self.report(
            {"INFO"},
            (
                "[Kai] Validated mapping names: "
                f"Hip={hip_bone_name} | "
                f"Spines={spine_bone_names} | "
                f"Chest={chest_bone_name} | "
                f"Necks={neck_bone_names} | "
                f"Head={head_bone_name} | "
                f"Shoulders={{"
                f"'Left': '{_kai_safe_bone_name(shoulder_bones['Left'])}', "
                f"'Right': '{_kai_safe_bone_name(shoulder_bones['Right'])}'"
                f"}}"
            )
        )

        reference_mapping = {
            "hip": hip_bone,
            "hip_name": hip_bone_name,
            "spines": spine_bones,
            "spine_names": spine_bone_names,
            "chest": chest_bone,
            "chest_name": chest_bone_name,
            "necks": neck_bones,
            "neck_names": neck_bone_names,
            "head": head_bone,
            "head_name": head_bone_name,
            "shoulder_names": {
                side: _kai_safe_bone_name(bone)
                for side, bone in shoulder_bones.items()
            },
        }
        self.reference_mapping = reference_mapping
        self.report(
            {"INFO"},
            "[Kai] Saved reference_mapping to operator"
        )

        # ~ layer_select = []
        original_mode = "OBJECT"  # Safe default in case mode detection fails
        arm = None
        layer_select = []

        try:
            # only select the armature
            # FIRST THING: Store original mode and switch to OBJECT mode immediately
            if not context.active_object or context.active_object.type != "ARMATURE":
                self.report({"ERROR"}, "No armature selected")
                return {"CANCELLED"}

            original_mode = context.active_object.mode

            # Validate the mode is a valid string
            valid_modes = [
                "OBJECT",
                "EDIT",
                "POSE",
                "SCULPT",
                "VERTEX_PAINT",
                "WEIGHT_PAINT",
                "TEXTURE_PAINT",
                "PARTICLE_EDIT",
                "EDIT_GPENCIL",
                "SCULPT_GPENCIL",
                "PAINT_GPENCIL",
                "WEIGHT_GPENCIL",
                "VERTEX_GPENCIL",
            ]
            if not isinstance(original_mode, str) or original_mode not in valid_modes:
                print(f"WARNING: Invalid mode '{original_mode}', defaulting to OBJECT")
                original_mode = "OBJECT"

            # Switch to OBJECT mode IMMEDIATELY as first operation
            if original_mode != "OBJECT":
                try:
                    bpy.ops.object.mode_set(mode="OBJECT")
                except Exception as e:
                    self.report({"ERROR"}, f"Could not switch to OBJECT mode: {e}")
                    return {"CANCELLED"}

            arm = get_object(context.active_object.name)
            _deselect_all_objects()
            set_active_object(arm.name)

            # enable all armature layers
            layer_select = enable_all_armature_layers()

            # animation import: initial steps
            if self.bake_anim:
                if (
                    "mr_control_rig" not in arm.data.keys()
                ):  # only if the control rig is not already built
                    # duplicate current skeleton
                    duplicate_object()
                    copy_name = arm.name + "_TEMPANIM"
                    self.animated_armature = get_object(context.active_object.name)
                    self.animated_armature.name = copy_name
                    self.animated_armature["mix_to_del"] = True

                    bpy.ops.object.mode_set(mode="OBJECT")
                    _deselect_all_objects()
                    set_active_object(arm.name)

            # set to rest pose, clear animation
            _zero_out(context)

            # build control rig
            _make_rig(self, context)
            _repair_fk_foot_setup(context, arm)

            if blender_version._float < 291:
                # Child Of constraints inverse matrix must be set manually
                # in Blender versions < 2.91
                print("Set inverse ChildOf")
                _reset_inverse_constraints()

            # animation import: retarget
            if self.bake_anim and self.animated_armature:
                _import_anim(
                    self.animated_armature,
                    arm,
                    rotation_output=self.retarget_rotation_output,
                )

            # set KeyingSet
            ks = context.scene.keying_sets_all
            try:
                ks.active = ks["Location & Rotation"]
            except (KeyError, AttributeError):
                # doesn't exist in older Blender versions
                pass

        except Exception:
            raise
        finally:
            try:
                bpy.ops.object.mode_set(mode="OBJECT")
            except Exception:
                pass
            _deselect_all_objects()
            if arm is not None:
                set_active_object(arm.name)

            if not debug:
                restore_armature_layers(layer_select)
                remove_retarget_cns(context.active_object)
                remove_temp_objects()
                remove_temp_actions()
                clean_scene()

            self.report({"INFO"}, "Control Rig Done!")

        # LAST THING: Restore original mode after ALL operations complete
        try:
            mode_type = type(original_mode)
            print(f"DEBUG: Restoring mode to: '{original_mode}' (type: {mode_type})")
            if original_mode != "OBJECT":
                bpy.ops.object.mode_set(mode=original_mode)
        except Exception as e:
            print(f"Warning: Could not restore original mode '{original_mode}': {e}")

        return {"FINISHED"}


class MR_OT_zero_out(bpy.types.Operator):  # noqa: N801
    """Delete all keys and set every bones to (0,0,0) rotation"""

    bl_idname = "mr.zero_out"
    bl_label = "zero_out"
    bl_options = {"UNDO"}

    @classmethod
    def poll(cls, context):
        if context.active_object:
            return context.active_object.type == "ARMATURE"
        return False

    def execute(self, context):
        try:
            _zero_out(context)

        finally:
            print("")

        return {"FINISHED"}


class MR_OT_bake_anim(bpy.types.Operator):  # noqa: N801
    """Merge all animation layers (see NLA editor) into a single layer"""

    bl_idname = "mr.bake_anim"
    bl_label = "bake_anim"
    bl_options = {"UNDO"}

    @classmethod
    def poll(cls, context):
        if context.active_object:
            return context.active_object.type == "ARMATURE"
        return False

    def execute(self, context):
        try:
            _bake_anim(self, context)

        finally:
            pass

        return {"FINISHED"}


class MR_OT_import_anim(bpy.types.Operator):  # noqa: N801
    """Import an animation file (FBX) of the same character to the control rig"""

    bl_idname = "mr.import_anim_to_rig"
    bl_label = "import_anim_to_rig"
    bl_options = {"UNDO"}

    @classmethod
    def poll(cls, context):
        if context.active_object:
            if context.active_object.type == "ARMATURE":
                if "mr_control_rig" in context.active_object.data.keys():
                    return True
        return False

    def execute(self, context):
        scn = context.scene
        debug = False
        error = False
        layer_select = []

        if scn.mix_source_armature is None:
            self.report({"ERROR"}, "Source armature must be set")
            return {"FINISHED"}

        try:
            layer_select = enable_all_armature_layers()
            # tar_arm = scn.mix_target_armature
            tar_arm = get_object(context.active_object.name)
            # src_arm = [i for i in context.selected_objects if i != tar_arm][0]
            src_arm = scn.mix_source_armature
            print("Source", src_arm.name)
            print("Target", tar_arm.name)

            _import_anim(
                src_arm,
                tar_arm,
                import_only=True,
                rotation_output=scn.mr_retarget_rotation_output,
            )

        # except:
        #    error = True
        #    print("Error")

        finally:
            if not debug:
                # Ensure the control rig is active before restoring layers
                try:
                    _deselect_all_objects()
                    if "tar_arm" in locals() and tar_arm:
                        set_active_object(tar_arm.name)
                except Exception:
                    pass
                restore_armature_layers(layer_select)
                remove_retarget_cns(context.active_object)

                if scn.mix_source_armature:
                    try:
                        remove_retarget_cns(scn.mix_source_armature)
                    except Exception:
                        pass

                remove_temp_objects()
                remove_temp_actions()

            self.report({"INFO"}, "Animation imported")

        return {"FINISHED"}


# OPERATOR FUNCTIONS
#####################


def _apply_shape():
    bpy.ops.object.mode_set(mode="OBJECT")
    obj = bpy.context.active_object
    obj_name = obj.name
    shape = bpy.data.objects.get(obj_name)
    delete_obj = False

    cs_grp = get_object("cs_grp")
    if cs_grp:
        shape.parent = bpy.data.objects["cs_grp"]

    mr_armature_name = None
    mr_armature = None

    if len(shape.keys()) > 0:
        for key in shape.keys():
            if "delete" in shape.keys():
                delete_obj = True
            if "mr_armature" in key:
                mr_armature_name = shape["mr_armature"]
                mr_armature = bpy.data.objects.get(mr_armature_name)

    if delete_obj:
        bpy.ops.object.delete(use_global=False)
    else:
        # assign to collection
        if mr_armature:
            if len(mr_armature.users_collection) > 0:
                for collec in mr_armature.users_collection:
                    if len(collec.name.split("_")) == 1:
                        continue
                    if (
                        collec.name.split("_")[1] == "rig"
                        or collec.name.split("_")[1] == "grp"
                    ):
                        cs_collec = bpy.data.collections.get(
                            collec.name.split("_")[0] + "_cs"
                        )
                        if cs_collec:
                            # remove from root collection
                            if bpy.context.scene.collection.objects.get(shape.name):
                                bpy.context.scene.collection.objects.unlink(shape)
                            # remove from other collections
                            for other_collec in shape.users_collection:
                                other_collec.objects.unlink(shape)
                            # assign to cs collection
                            cs_collec.objects.link(shape)
                            print("assigned to collec", cs_collec.name)
                        else:
                            print("cs collec not found")
                    else:
                        print("rig collec not found")

            else:
                print("Armature has no collection")
        else:
            print("Armature not set")

    # hide shape
    try:
        hide_object(shape)
    except Exception:  # weird error 'StructRNA of type Object has been removed'
        print("Error, could not hide shape")
        pass

    if mr_armature:
        set_active_object(mr_armature.name)
        bpy.ops.object.mode_set(mode="POSE")


def _edit_custom_shape():
    bone = bpy.context.active_pose_bone
    rig_name = bpy.context.active_object.name
    rig = get_object(rig_name)

    cs = bone.custom_shape
    cs_mesh = cs.data

    bpy.ops.object.mode_set(mode="OBJECT")

    # make sure the active collection is not hidden,
    # otherwise we can't access the newly created object data
    active_collec = bpy.context.layer_collection
    if not active_collec.is_visible:
        for col in rig.users_collection:
            layer_col = search_layer_collection(
                bpy.context.view_layer.layer_collection, col.name
            )
            if not layer_col.hide_viewport and not col.hide_viewport:
                bpy.context.view_layer.active_layer_collection = layer_col
                break

    # create new mesh data
    bpy.ops.mesh.primitive_plane_add(
        size=1, enter_editmode=False, location=(-0, 0, 0.0), rotation=(0.0, 0.0, 0.0)
    )

    mesh_obj = bpy.context.active_object
    mesh_obj.name = "cs_user_" + bone.name

    if (
        cs.name == "cs_user_" + bone.name
    ):  # make a mesh instance if it's a already edited
        mesh_obj.data = cs_mesh
        mesh_obj["delete"] = 1.0
    else:  # else create new object data
        mesh_obj.data = cs_mesh.copy()
        mesh_obj.data.name = mesh_obj.name
        bone.custom_shape = mesh_obj

    # store the current armature name in a custom prop
    mesh_obj["mr_armature"] = rig_name

    if bone.custom_shape_transform:
        bone_transf = bone.custom_shape_transform
        mesh_obj.matrix_world = rig.matrix_world @ bone_transf.matrix
    else:
        mesh_obj.matrix_world = rig.matrix_world @ bone.matrix

    mesh_obj.scale *= get_custom_shape_scale(bone)
    mesh_obj.scale *= bone.length

    bpy.ops.object.mode_set(mode="EDIT")


def clean_scene():
    # hide cs_grp
    cs_grp = get_object("cs_grp")
    if cs_grp:
        for c in cs_grp.children:
            if c.name in bpy.context.view_layer.objects:
                hide_object(c)
            else:
                print(f"Warning: Object '{c.name}' is not in the current View Layer.")

        if cs_grp.name in bpy.context.view_layer.objects:
            hide_object(cs_grp)
        else:
            print("Warning: Object 'cs_grp' is not in the current View Layer.")

    # Always show custom shapes and set collection visibility
    if bpy.context.object and bpy.context.object.type == "ARMATURE":
        bpy.context.object.data.show_bone_custom_shapes = True

        # Set bone collection visibility - only CTRL visible
        # Use .collections instead of .collections_all for safe property assignment
        for coll in bpy.context.object.data.collections:
            if coll.name == "DEF":
                coll.is_visible = False
            elif coll.name == "MCH":
                coll.is_visible = False
            elif coll.name == "CTRL":
                coll.is_visible = True


def init_armature_transforms(rig):
    bpy.ops.object.mode_set(mode="OBJECT")
    _deselect_all_objects()
    set_active_object(rig.name)
    bpy.ops.object.mode_set(mode="OBJECT")

    # first unparent children meshes
    # (init scale messed up children scale in Blender 2.8)
    child_par_dict = {}
    for child in bpy.data.objects[rig.name].children:
        bone_parent = None
        if child.parent_type == "BONE":
            bone_parent = child.parent_bone
        child_par_dict[child.name] = bone_parent
        child_mat = child.matrix_world.copy()
        child.parent = None
        bpy.context.evaluated_depsgraph_get().update()
        child.matrix_world = child_mat

    # apply armature transforms
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
    bpy.context.evaluated_depsgraph_get().update()

    # restore armature children
    for child_name in child_par_dict:
        child = bpy.data.objects.get(child_name)
        child_mat = child.matrix_world.copy()
        child.parent = bpy.data.objects[rig.name]
        if child_par_dict[child_name] is not None:  # bone parent
            child.parent_type = "BONE"
            child.parent_bone = child_par_dict[child_name]

        bpy.context.evaluated_depsgraph_get().update()
        child.matrix_world = child_mat


def _reset_inverse_constraints():
    bpy.ops.object.mode_set(mode="POSE")

    rig_name = bpy.context.active_object.name
    rig = get_object(rig_name)

    for pb in rig.pose.bones:
        if len(pb.constraints):
            for cns in pb.constraints:
                if cns.type == "CHILD_OF":
                    set_constraint_inverse_matrix(cns)

    bpy.ops.object.mode_set(mode="OBJECT")


def _reconnect_rig_constraints(context):
    obj = context.active_object
    if not obj or obj.type != "ARMATURE":
        return

    rig = obj

    if "mr_control_rig" not in rig.data.keys():
        return

    try:
        bpy.ops.object.mode_set(mode="POSE")
    except Exception:
        return

    for pb in rig.pose.bones:
        while pb.constraints:
            pb.constraints.remove(pb.constraints[0])

    _build_constraints_for_rig(rig)


def _build_constraints_for_rig(rig):
    detected_prefix = ""
    try:
        for bone in rig.data.bones:
            if bone.name.startswith("mixamorig") and ":" in bone.name:
                detected_prefix = bone.name.split(":")[0] + ":"
                break
    except Exception:
        pass

    def get_src_bone_name(base_name):
        if detected_prefix:
            return detected_prefix + base_name
        return base_name

    bpy.ops.object.mode_set(mode="POSE")

    c_master_name = c_prefix + master_rig_names["master"]

    if get_pose_bone(c_master_name) is None:
        return

    if get_pose_bone(c_master_name) is not None:
        c_master_pb = get_pose_bone(c_master_name)
        c_master_pb.bone["mixamo_ctrl"] = 1
        set_bone_custom_shape(c_master_pb, "cs_master")
        c_master_pb.rotation_mode = "XYZ"
        set_bone_color_group(rig, c_master_pb, "master")

    kai_raw_hip_name = rig.data.get("kai_hip_name", spine_names["pelvis"])
    hips_name = _kai_prefixed_source_bone_name(kai_raw_hip_name, detected_prefix)
    kai_spine_names = rig.data.get("kai_spine_names", "")
    kai_chest_name = rig.data.get("kai_chest_name", "")

    print(
        "[Kai] Loaded Kai mapping from rig.data: "
        f"Spines={kai_spine_names} | "
        f"Chest={kai_chest_name}"
    )

    if "kai_spine_names" in rig.data.keys():
        kai_raw_spine_names = [
            name for name in kai_spine_names.split(",")
            if name
        ]
    else:
        kai_raw_spine_names = [
            spine_names["spine1"],
            spine_names["spine2"],
        ]
    kai_raw_chest_name = kai_chest_name or spine_names["spine3"]

    kai_source_spine_names, kai_source_chest_name, _, _ = _kai_resolve_spine_sources(
        [
            _kai_prefixed_source_bone_name(name, detected_prefix)
            for name in kai_raw_spine_names
        ],
        _kai_prefixed_source_bone_name(kai_raw_chest_name, detected_prefix),
    )

    print(
        "[Kai] Parsed Kai mapping: "
        f"Spines={kai_source_spine_names} | "
        f"Chest={kai_source_chest_name}"
    )

    c_hips_name = c_prefix + spine_rig_names["pelvis"]
    hips_free_h_name = spine_rig_names["hips_free_helper"]
    c_hips_free_name = c_prefix + spine_rig_names["hips_free"]
    spine_control_pairs = _kai_build_spine_control_pairs(
        kai_raw_spine_names,
        kai_raw_chest_name,
        detected_prefix,
    )

    mixamo_spine_pb = get_pose_bone(hips_name)
    c_hips_pb = get_pose_bone(c_hips_name)
    hips_free_h_pb = get_pose_bone(hips_free_h_name)
    c_hips_free_pb = get_pose_bone(c_hips_free_name)
    spine_control_pbones = [
        get_pose_bone(pair["control_name"])
        for pair in spine_control_pairs
    ]

    if mixamo_spine_pb and hips_free_h_pb:
        cns = mixamo_spine_pb.constraints.get("Copy Transforms")
        if cns is None:
            cns = mixamo_spine_pb.constraints.new("COPY_TRANSFORMS")
            cns.name = "Copy Transforms"
        cns.target = rig
        cns.subtarget = hips_free_h_name

    if c_hips_pb and c_hips_free_pb and all(spine_control_pbones):
        for pb in [c_hips_pb, c_hips_free_pb] + spine_control_pbones:
            pb.bone["mixamo_ctrl"] = 1

        set_bone_custom_shape(c_hips_pb, "cs_square_2")
        set_bone_custom_shape(c_hips_free_pb, "cs_hips")
        for pb in spine_control_pbones:
            set_bone_custom_shape(pb, "cs_circle")

        c_hips_pb.rotation_mode = "XYZ"
        c_hips_free_pb.rotation_mode = "XYZ"
        for pb in spine_control_pbones:
            pb.rotation_mode = "XYZ"

        set_bone_color_group(rig, c_hips_pb, "root_master")
        set_bone_color_group(rig, c_hips_free_pb, "body_mid")
        for pb in spine_control_pbones:
            set_bone_color_group(rig, pb, "body_mid")

        for pair in spine_control_pairs:
            mixamo_spine_pb = get_pose_bone(pair["source_name"])
            if mixamo_spine_pb is None:
                continue

            cns = mixamo_spine_pb.constraints.get("Copy Transforms")

            if cns is None:
                cns = mixamo_spine_pb.constraints.new("COPY_TRANSFORMS")
                cns.name = "Copy Transforms"

            cns.target = rig
            cns.subtarget = pair["control_name"]

    kai_neck_names = rig.data.get("kai_neck_names", "")
    kai_head_name = rig.data.get("kai_head_name", "")
    kai_source_neck_names = [
        _kai_prefixed_source_bone_name(name, detected_prefix)
        for name in kai_neck_names.split(",")
        if name
    ]
    kai_raw_head_name = kai_head_name or head_names["head"]

    neck_control_pairs = _kai_build_spine_control_pairs(
        kai_source_neck_names,
        None,
    )
    head_name = _kai_prefixed_source_bone_name(kai_raw_head_name, detected_prefix)
    c_head_name = c_prefix + head_rig_names["head"]

    head_pb = get_pose_bone(head_name)
    c_head_pb = get_pose_bone(c_head_name)

    for pair in neck_control_pairs:
        neck_pb = get_pose_bone(pair["source_name"])
        c_neck_pb = get_pose_bone(pair["control_name"])
        if c_neck_pb is None:
            continue

        c_neck_pb.bone["mixamo_ctrl"] = 1
        set_bone_custom_shape(c_neck_pb, "cs_neck")
        c_neck_pb.rotation_mode = "XYZ"
        set_bone_color_group(rig, c_neck_pb, "neck")

        if neck_pb is not None:
            add_copy_transf(neck_pb, rig, pair["control_name"])

    if c_head_pb:
        c_head_pb.bone["mixamo_ctrl"] = 1
        set_bone_custom_shape(c_head_pb, "cs_head")
        c_head_pb.custom_shape_scale_xyz[0] = 1.9
        c_head_pb.custom_shape_scale_xyz[1] = 1.9
        c_head_pb.custom_shape_scale_xyz[2] = 1.9
        c_head_pb.rotation_mode = "XYZ"
        set_bone_color_group(rig, c_head_pb, "head")

    if head_pb and c_head_pb:
        add_copy_transf(head_pb, rig, c_head_name)

    for side in ["Left", "Right"]:
        _side = "_" + side

        thigh_name = get_src_bone_name(side + leg_names["thigh"])
        calf_name = get_src_bone_name(side + leg_names["calf"])
        foot_name = get_src_bone_name(side + leg_names["foot"])
        toe_name = get_src_bone_name(side + leg_names["toes"])

        thigh_pb = get_pose_bone(thigh_name)
        calf_pb = get_pose_bone(calf_name)
        foot_pb = get_pose_bone(foot_name)
        toe_pb = get_pose_bone(toe_name)

        calf_ik_name = leg_rig_names["calf_ik"] + _side
        foot_ik_name = leg_rig_names["foot_ik"] + _side
        c_foot_ik_name = c_prefix + leg_rig_names["foot_ik"] + _side
        c_pole_ik_name = c_prefix + leg_rig_names["pole_ik"] + _side
        toes_end_name = leg_rig_names["toes_end"] + _side
        toe_01_ik_name = leg_rig_names["toes_01_ik"] + _side
        toe_02_name = leg_rig_names["toes_02"] + _side
        toe_track_name = leg_rig_names["toes_track"] + _side
        heel_mid_name = leg_rig_names["heel_mid"] + _side
        heel_in_name = leg_rig_names["heel_in"] + _side
        heel_out_name = leg_rig_names["heel_out"] + _side
        c_foot_01_name = c_prefix + leg_rig_names["foot_01"] + _side
        c_foot_roll_cursor_name = c_prefix + leg_rig_names["foot_roll_cursor"] + _side
        foot_ik_target_name = leg_rig_names["foot_ik_target"] + _side
        foot_01_pole_name = leg_rig_names["foot_01_pole"] + _side
        c_thigh_fk_name = c_prefix + leg_rig_names["thigh_fk"] + _side
        c_calf_fk_name = c_prefix + leg_rig_names["calf_fk"] + _side
        c_foot_fk_name = c_prefix + leg_rig_names["foot_fk"] + _side
        c_toe_ik_name = c_prefix + leg_rig_names["toes_ik"] + _side
        c_toe_fk_name = c_prefix + leg_rig_names["toes_fk"] + _side
        foot_fk_name = leg_rig_names["foot_fk"] + _side

        calf_ik_pb = get_pose_bone(calf_ik_name)
        foot_ik_pb = get_pose_bone(foot_ik_name)
        c_foot_ik_pb = get_pose_bone(c_foot_ik_name)
        c_pole_ik_pb = get_pose_bone(c_pole_ik_name)
        toes_end_pb = get_pose_bone(toes_end_name)
        toe_01_ik_pb = get_pose_bone(toe_01_ik_name)
        toe_02_pb = get_pose_bone(toe_02_name)
        toe_track_pb = get_pose_bone(toe_track_name)
        heel_mid_pb = get_pose_bone(heel_mid_name)
        heel_in_pb = get_pose_bone(heel_in_name)
        heel_out_pb = get_pose_bone(heel_out_name)
        c_foot_01_pb = get_pose_bone(c_foot_01_name)
        c_foot_roll_cursor_pb = get_pose_bone(c_foot_roll_cursor_name)
        c_thigh_fk_pb = get_pose_bone(c_thigh_fk_name)
        c_calf_fk_pb = get_pose_bone(c_calf_fk_name)
        c_foot_fk_pb = get_pose_bone(c_foot_fk_name)
        c_toe_ik_pb = get_pose_bone(c_toe_ik_name)
        c_toe_fk_pb = get_pose_bone(c_toe_fk_name)

        if not (
            calf_ik_pb
            and foot_ik_pb
            and c_foot_ik_pb
            and c_pole_ik_pb
            and toes_end_pb
            and toe_01_ik_pb
            and toe_02_pb
            and toe_track_pb
            and heel_mid_pb
            and heel_in_pb
            and heel_out_pb
            and foot_pb
            and thigh_pb
            and calf_pb
            and toe_pb
            and c_foot_01_pb
            and c_foot_roll_cursor_pb
            and c_thigh_fk_pb
            and c_calf_fk_pb
            and c_foot_fk_pb
            and c_toe_ik_pb
            and c_toe_fk_pb
        ):
            continue

        cns_name = "IK"
        ik_cns = calf_ik_pb.constraints.get(cns_name)
        if ik_cns is None:
            ik_cns = calf_ik_pb.constraints.new("IK")
            ik_cns.name = cns_name
        ik_cns.target = rig
        ik_cns.subtarget = foot_ik_target_name
        ik_cns.pole_target = rig
        ik_cns.pole_subtarget = c_pole_ik_name
        try:
            thigh_ik_pb = get_pose_bone(leg_rig_names["thigh_ik"] + _side)
            if thigh_ik_pb is not None:
                ik_cns.pole_angle = get_pole_angle(
                    thigh_ik_pb,
                    calf_ik_pb,
                    c_pole_ik_pb.head,
                )
        except Exception:
            pass
        ik_cns.chain_count = 2
        ik_cns.use_tail = True
        ik_cns.use_stretch = False

        calf_ik_pb.lock_ik_y = True
        calf_ik_pb.lock_ik_z = True

        cns_name = "Copy Location"
        copy_loc_cns = foot_ik_pb.constraints.get(cns_name)
        if copy_loc_cns is None:
            copy_loc_cns = foot_ik_pb.constraints.new("COPY_LOCATION")
            copy_loc_cns.name = cns_name
        copy_loc_cns.target = rig
        copy_loc_cns.subtarget = calf_ik_name
        copy_loc_cns.head_tail = 1.0

        cns_name = "TrackTo"
        cns = foot_ik_pb.constraints.get(cns_name)
        if cns is None:
            cns = foot_ik_pb.constraints.new("TRACK_TO")
            cns.name = cns_name
        cns.target = rig
        cns.subtarget = c_foot_01_name
        cns.head_tail = 0.0
        cns.track_axis = "TRACK_Y"
        cns.up_axis = "UP_Z"
        cns.use_target_z = True

        cns_name = "Locked Track"
        cns = foot_ik_pb.constraints.get(cns_name)
        if cns is None:
            cns = foot_ik_pb.constraints.new("LOCKED_TRACK")
            cns.name = cns_name
        cns.target = rig
        cns.subtarget = foot_01_pole_name
        cns.head_tail = 0.0
        cns.track_axis = "TRACK_Z"
        cns.lock_axis = "LOCK_Y"

        cns_name = "Copy Scale"
        cns = foot_ik_pb.constraints.get(cns_name)
        if cns is None:
            cns = foot_ik_pb.constraints.new("COPY_SCALE")
            cns.name = cns_name
        cns.target = rig
        cns.subtarget = c_foot_ik_name

        cns_name = "Child Of"
        cns = c_foot_ik_pb.constraints.get(cns_name)
        if cns is None:
            cns = c_foot_ik_pb.constraints.new("CHILD_OF")
            cns.name = cns_name
        cns.target = rig
        cns.subtarget = c_master_name

        cns_name = "Child Of"
        child_cns = c_pole_ik_pb.constraints.get(cns_name)
        if child_cns is None:
            child_cns = c_pole_ik_pb.constraints.new("CHILD_OF")
            child_cns.name = cns_name
        child_cns.target = rig
        child_cns.subtarget = c_foot_ik_name

        cns_power = 8

        length_toes_end = toes_end_pb.length * cns_power

        cns_name = "Transformation"
        cns = toes_end_pb.constraints.get(cns_name)
        if cns is None:
            cns = toes_end_pb.constraints.new("TRANSFORM")
            cns.name = cns_name
        cns.target = rig
        cns.subtarget = c_foot_roll_cursor_name
        cns.use_motion_extrapolate = True
        cns.target_space = cns.owner_space = "LOCAL"
        cns.map_from = "LOCATION"
        cns.from_min_z = 0.5 * length_toes_end
        cns.from_max_z = -0.5 * length_toes_end
        cns.map_to = "ROTATION"
        cns.map_to_x_from = "Z"
        cns.map_to_z_from = "X"
        cns.to_min_x_rot = -2.61
        cns.to_max_x_rot = 2.61
        cns.mix_mode_rot = "ADD"

        cns_name = "Limit Rotation"
        cns = toes_end_pb.constraints.get(cns_name)
        if cns is None:
            cns = toes_end_pb.constraints.new("LIMIT_ROTATION")
            cns.name = cns_name
        cns.owner_space = "LOCAL"
        cns.use_limit_x = True
        cns.min_x = -2 * pi
        cns.max_x = 0.0

        cns_name = "Copy Transforms"
        cns = toe_01_ik_pb.constraints.get(cns_name)
        if cns is None:
            cns = toe_01_ik_pb.constraints.new("COPY_TRANSFORMS")
            cns.name = cns_name
        cns.target = rig
        cns.subtarget = c_toe_ik_name
        cns.mix_mode = "REPLACE"
        cns.target_space = cns.owner_space = "WORLD"

        cns_name_fk_rot = "FK_Rot_follow"
        cns_fk_rot = toe_02_pb.constraints.get(cns_name_fk_rot)
        if cns_fk_rot is None:
            cns_fk_rot = toe_02_pb.constraints.new("COPY_ROTATION")
            cns_fk_rot.name = cns_name_fk_rot
        cns_fk_rot.target = rig
        cns_fk_rot.subtarget = c_toe_ik_name
        cns_fk_rot.mix_mode = "REPLACE"
        cns_fk_rot.target_space = cns.owner_space = "WORLD"

        cns_name = "TrackTo"
        cns = toe_track_pb.constraints.get(cns_name)
        if cns is None:
            cns = toe_track_pb.constraints.new("TRACK_TO")
            cns.name = cns_name
        cns.target = rig
        cns.subtarget = leg_rig_names["toes_end_01"] + _side
        cns.head_tail = 0.0
        cns.track_axis = "TRACK_Y"
        cns.up_axis = "UP_Z"
        cns.use_target_z = True

        length_heel_mid = heel_mid_pb.length * cns_power

        cns_name = "Transformation"
        cns = heel_mid_pb.constraints.get(cns_name)
        if cns is None:
            cns = heel_mid_pb.constraints.new("TRANSFORM")
            cns.name = cns_name
        cns.target = rig
        cns.subtarget = c_foot_roll_cursor_name
        cns.owner_space = cns.target_space = "LOCAL"
        cns.map_from = "LOCATION"
        cns.from_min_z = -0.25 * length_heel_mid
        cns.from_max_z = 0.25 * length_heel_mid
        cns.map_to = "ROTATION"
        cns.map_to_x_from = "Z"
        cns.map_to_y_from = "X"
        cns.map_to_z_from = "Y"
        cns.to_min_x_rot = radians(100)
        cns.to_max_x_rot = -radians(100)
        cns.mix_mode_rot = "ADD"

        cns_name = "Limit Rotation"
        cns = heel_mid_pb.constraints.get(cns_name)
        if cns is None:
            cns = heel_mid_pb.constraints.new("LIMIT_ROTATION")
            cns.name = cns_name
        cns.use_limit_x = True
        cns.min_x = radians(0)
        cns.max_x = radians(360)
        cns.owner_space = "LOCAL"

        length_heel_in = heel_in_pb.length * cns_power

        cns_name = "Transformation"
        cns = heel_in_pb.constraints.get(cns_name)
        if cns is None:
            cns = heel_in_pb.constraints.new("TRANSFORM")
            cns.name = cns_name
        cns.target = rig
        cns.subtarget = c_foot_roll_cursor_name
        cns.owner_space = cns.target_space = "LOCAL"
        cns.map_from = "LOCATION"
        cns.from_min_x = -0.25 * length_heel_in
        cns.from_max_x = 0.25 * length_heel_in
        cns.map_to = "ROTATION"
        cns.map_to_x_from = "Z"
        cns.map_to_y_from = "X"
        cns.map_to_z_from = "Y"
        cns.to_min_y_rot = -radians(100)
        cns.to_max_y_rot = radians(100)
        cns.mix_mode_rot = "ADD"

        cns_name = "Limit Rotation"
        cns = heel_in_pb.constraints.get(cns_name)
        if cns is None:
            cns = heel_in_pb.constraints.new("LIMIT_ROTATION")
            cns.name = cns_name
        cns.use_limit_y = True
        if side == "Left":
            cns.min_y = 0.0
            cns.max_y = radians(90)
        else:
            cns.min_y = radians(-90)
            cns.max_y = 0.0
        cns.owner_space = "LOCAL"

        length_heel_out = heel_out_pb.length * cns_power

        cns_name = "Transformation"
        cns = heel_out_pb.constraints.get(cns_name)
        if cns is None:
            cns = heel_out_pb.constraints.new("TRANSFORM")
            cns.name = cns_name
        cns.target = rig
        cns.subtarget = c_foot_roll_cursor_name
        cns.owner_space = cns.target_space = "LOCAL"
        cns.map_from = "LOCATION"
        cns.from_min_x = -0.25 * length_heel_out
        cns.from_max_x = 0.25 * length_heel_out
        cns.map_to = "ROTATION"
        cns.map_to_x_from = "Z"
        cns.map_to_y_from = "X"
        cns.map_to_z_from = "Y"
        cns.to_min_y_rot = -radians(100)
        cns.to_max_y_rot = radians(100)
        cns.mix_mode_rot = "ADD"

        cns_name = "Limit Rotation"
        cns = heel_out_pb.constraints.get(cns_name)
        if cns is None:
            cns = heel_out_pb.constraints.new("LIMIT_ROTATION")
            cns.name = cns_name
        cns.use_limit_y = True
        if side == "Left":
            cns.min_y = radians(-90)
            cns.max_y = 0.0
        else:
            cns.min_y = 0.0
            cns.max_y = radians(90)
        cns.owner_space = "LOCAL"

        if "ik_fk_switch" not in c_foot_ik_pb.keys():
            create_custom_prop(
                node=c_foot_ik_pb,
                prop_name="ik_fk_switch",
                prop_val=0.0,
                prop_min=0.0,
                prop_max=1.0,
                prop_description="IK-FK switch value",
            )

        cns_name = "IK_follow"
        cns_ik = thigh_pb.constraints.get(cns_name)
        if cns_ik is None:
            cns_ik = thigh_pb.constraints.new("COPY_TRANSFORMS")
            cns_ik.name = cns_name
        cns_ik.target = rig
        cns_ik.subtarget = leg_rig_names["thigh_ik"] + _side
        cns_ik.influence = 1.0

        cns_name = "FK_follow"
        cns_fk = thigh_pb.constraints.get(cns_name)
        if cns_fk is None:
            cns_fk = thigh_pb.constraints.new("COPY_TRANSFORMS")
            cns_fk.name = cns_name
        cns_fk.target = rig
        cns_fk.subtarget = c_thigh_fk_name
        cns_fk.influence = 0.0

        add_driver_to_prop(
            rig,
            'pose.bones["'
            + thigh_name
            + '"].constraints["'
            + cns_name
            + '"].influence',
            'pose.bones["' + c_foot_ik_name + '"]["ik_fk_switch"]',
            array_idx=-1,
            exp="var",
        )

        cns_name = "IK_follow"
        cns_ik = calf_pb.constraints.get(cns_name)
        if cns_ik is None:
            cns_ik = calf_pb.constraints.new("COPY_TRANSFORMS")
            cns_ik.name = cns_name
        cns_ik.target = rig
        cns_ik.subtarget = calf_ik_name
        cns_ik.influence = 1.0

        cns_name = "FK_follow"
        cns_fk = calf_pb.constraints.get(cns_name)
        if cns_fk is None:
            cns_fk = calf_pb.constraints.new("COPY_TRANSFORMS")
            cns_fk.name = cns_name
        cns_fk.target = rig
        cns_fk.subtarget = c_calf_fk_name
        cns_fk.influence = 0.0

        add_driver_to_prop(
            rig,
            f'pose.bones["{calf_name}"].constraints["{cns_name}"].influence',
            'pose.bones["' + c_foot_ik_name + '"]["ik_fk_switch"]',
            array_idx=-1,
            exp="var",
        )

        cns_name = "IK_follow"
        cns_ik = foot_pb.constraints.get(cns_name)
        if cns_ik is None:
            cns_ik = foot_pb.constraints.new("COPY_TRANSFORMS")
            cns_ik.name = cns_name
        cns_ik.target = rig
        cns_ik.subtarget = foot_ik_name
        cns_ik.influence = 1.0

        cns_name = "FK_follow"
        cns_fk = foot_pb.constraints.get(cns_name)
        if cns_fk is None:
            cns_fk = foot_pb.constraints.new("COPY_TRANSFORMS")
            cns_fk.name = cns_name
        cns_fk.target = rig
        cns_fk.subtarget = foot_fk_name
        cns_fk.influence = 0.0

        add_driver_to_prop(
            rig,
            f'pose.bones["{foot_name}"].constraints["{cns_name}"].influence',
            'pose.bones["' + c_foot_ik_name + '"]["ik_fk_switch"]',
            array_idx=-1,
            exp="var",
        )

        cns_name = "IK_Rot_follow"
        cns_ik_rot = toe_pb.constraints.get(cns_name)
        if cns_ik_rot is None:
            cns_ik_rot = toe_pb.constraints.new("COPY_ROTATION")
            cns_ik_rot.name = cns_name
        cns_ik_rot.target = rig
        cns_ik_rot.subtarget = c_toe_ik_name
        cns_ik_rot.influence = 1.0

        cns_name = "IK_Scale_follow"
        cns_ik_scale = toe_pb.constraints.get(cns_name)
        if cns_ik_scale is None:
            cns_ik_scale = toe_pb.constraints.new("COPY_SCALE")
            cns_ik_scale.name = cns_name
        cns_ik_scale.target = rig
        cns_ik_scale.subtarget = c_toe_ik_name
        cns_ik_scale.influence = 1.0

        cns_name_fk_rot = "FK_Rot_follow"
        cns_fk_rot = toe_pb.constraints.get(cns_name_fk_rot)
        if cns_fk_rot is None:
            cns_fk_rot = toe_pb.constraints.new("COPY_ROTATION")
            cns_fk_rot.name = cns_name_fk_rot
        cns_fk_rot.target = rig
        cns_fk_rot.subtarget = c_toe_fk_name
        cns_fk_rot.influence = 1.0

        cns_name_fk_scale = "FK_Scale_follow"
        cns_fk_scale = toe_pb.constraints.get(cns_name_fk_scale)
        if cns_fk_scale is None:
            cns_fk_scale = toe_pb.constraints.new("COPY_SCALE")
            cns_fk_scale.name = cns_name_fk_scale
        cns_fk_scale.target = rig
        cns_fk_scale.subtarget = c_toe_fk_name
        cns_fk_scale.influence = 1.0

        add_driver_to_prop(
            rig,
            'pose.bones["'
            + toe_name
            + '"].constraints["'
            + cns_name_fk_rot
            + '"].influence',
            'pose.bones["' + c_foot_ik_name + '"]["ik_fk_switch"]',
            array_idx=-1,
            exp="var",
        )
        add_driver_to_prop(
            rig,
            'pose.bones["'
            + toe_name
            + '"].constraints["'
            + cns_name_fk_scale
            + '"].influence',
            'pose.bones["' + c_foot_ik_name + '"]["ik_fk_switch"]',
            array_idx=-1,
            exp="var",
        )

        lock_pbone_transform(c_foot_roll_cursor_pb, "location", [1])
        lock_pbone_transform(c_foot_roll_cursor_pb, "rotation", [0, 1, 2])
        lock_pbone_transform(c_foot_roll_cursor_pb, "scale", [0, 1, 2])

        lock_pbone_transform(c_foot_01_pb, "location", [0, 1, 2])
        lock_pbone_transform(c_foot_01_pb, "rotation", [1, 2])
        lock_pbone_transform(c_foot_01_pb, "scale", [0, 1, 2])

        lock_pbone_transform(c_foot_fk_pb, "location", [0, 1, 2])

        lock_pbone_transform(c_pole_ik_pb, "rotation", [0, 1, 2])
        lock_pbone_transform(c_pole_ik_pb, "scale", [0, 1, 2])

        lock_pbone_transform(c_thigh_fk_pb, "location", [0, 1, 2])
        lock_pbone_transform(c_calf_fk_pb, "location", [0, 1, 2])

        c_pbones_list = [
            c_foot_ik_pb,
            c_pole_ik_pb,
            c_foot_01_pb,
            c_foot_roll_cursor_pb,
            c_thigh_fk_pb,
            c_calf_fk_pb,
            c_foot_fk_pb,
            c_toe_fk_pb,
            c_toe_ik_pb,
        ]

        for pb in c_pbones_list:
            pb.bone["mixamo_ctrl"] = 1

        set_bone_custom_shape(c_thigh_fk_pb, "cs_thigh_fk")
        set_bone_custom_shape(c_calf_fk_pb, "cs_calf_fk")
        set_bone_custom_shape(c_foot_ik_pb, "cs_foot")
        set_bone_custom_shape(c_foot_fk_pb, "cs_foot")
        set_bone_custom_shape(c_pole_ik_pb, "cs_sphere_012")
        set_bone_custom_shape(c_foot_roll_cursor_pb, "cs_foot_roll")
        set_bone_custom_shape(c_foot_01_pb, "cs_foot_01")
        set_bone_custom_shape(c_toe_fk_pb, "cs_toe")
        set_bone_custom_shape(c_toe_ik_pb, "cs_toe")

        ik_controls_names = [
            c_foot_ik_name,
            c_foot_01_name,
            c_toe_ik_name,
            c_foot_roll_cursor_name,
            c_pole_ik_name,
        ]

        arr_ids = [-1]
        if blender_version._float >= 300:
            arr_ids = [0, 1, 2]

        for n in ik_controls_names:
            dr_dp = 'pose.bones["' + n + '"].' + get_custom_shape_scale_prop_name()
            tar_dp = 'pose.bones["' + c_foot_ik_name + '"]["ik_fk_switch"]'
            for arr_id in arr_ids:
                add_driver_to_prop(rig, dr_dp, tar_dp, array_idx=arr_id, exp="1-var")

        fk_controls_names = [
            c_foot_fk_name,
            c_thigh_fk_name,
            c_calf_fk_name,
            c_toe_fk_name,
        ]

        for n in fk_controls_names:
            dr_dp = 'pose.bones["' + n + '"].' + get_custom_shape_scale_prop_name()
            tar_dp = 'pose.bones["' + c_foot_ik_name + '"]["ik_fk_switch"]'
            for arr_id in arr_ids:
                add_driver_to_prop(rig, dr_dp, tar_dp, array_idx=arr_id, exp="var")

        for pb in c_pbones_list:
            pb.rotation_mode = "XYZ"
            set_bone_color_group(rig, pb, "body" + _side.lower())

    for side in ["Left", "Right"]:
        _side = "_" + side

        kai_shoulder_names = _kai_get_mapping_names_from_rig_data(rig).get(
            "shoulders",
            {},
        )
        mapped_shoulder_name = kai_shoulder_names.get(side, side + arm_names["shoulder"])
        shoulder_name = (
            _kai_prefixed_source_bone_name(mapped_shoulder_name, detected_prefix)
            if mapped_shoulder_name
            else None
        )
        arm_name = get_src_bone_name(side + arm_names["arm"])
        forearm_name = get_src_bone_name(side + arm_names["forearm"])
        hand_name = get_src_bone_name(side + arm_names["hand"])

        c_shoulder_name = c_prefix + arm_rig_names["shoulder"] + _side
        arm_ik_name = arm_rig_names["arm_ik"] + _side
        forearm_ik_name = arm_rig_names["forearm_ik"] + _side
        c_arm_fk_name = c_prefix + arm_rig_names["arm_fk"] + _side
        c_forearm_fk_name = c_prefix + arm_rig_names["forearm_fk"] + _side
        c_pole_ik_name = c_prefix + arm_rig_names["pole_ik"] + _side
        c_hand_ik_name = c_prefix + arm_rig_names["hand_ik"] + _side
        c_hand_fk_name = c_prefix + arm_rig_names["hand_fk"] + _side

        c_shoulder_pb = get_pose_bone(c_shoulder_name)
        shoulder_pb = get_pose_bone(shoulder_name) if shoulder_name else None
        has_shoulder = c_shoulder_pb is not None and shoulder_pb is not None
        c_arm_fk_pb = get_pose_bone(c_arm_fk_name)
        forearm_ik_pb = get_pose_bone(forearm_ik_name)
        c_pole_ik_pb = get_pose_bone(c_pole_ik_name)
        c_hand_ik_pb = get_pose_bone(c_hand_ik_name)
        hand_pb = get_pose_bone(hand_name)
        arm_pb = get_pose_bone(arm_name)
        forearm_pb = get_pose_bone(forearm_name)
        c_forearm_fk_pb = get_pose_bone(c_forearm_fk_name)
        c_hand_fk_pb = get_pose_bone(c_hand_fk_name)

        if not (
            c_arm_fk_pb
            and forearm_ik_pb
            and c_pole_ik_pb
            and c_hand_ik_pb
            and hand_pb
            and arm_pb
            and forearm_pb
            and c_forearm_fk_pb
            and c_hand_fk_pb
        ):
            continue

        if has_shoulder:
            cns_name = "Copy Location"
            cns = c_arm_fk_pb.constraints.get(cns_name)
            if cns is None:
                cns = c_arm_fk_pb.constraints.new("COPY_LOCATION")
                cns.name = cns_name
            cns.head_tail = 1.0
            cns.target = rig
            cns.subtarget = c_shoulder_name

        cns_name = "IK"
        ik_cns = forearm_ik_pb.constraints.get(cns_name)
        if ik_cns is None:
            ik_cns = forearm_ik_pb.constraints.new("IK")
            ik_cns.name = cns_name
        ik_cns.target = rig
        ik_cns.subtarget = c_hand_ik_name
        ik_cns.pole_target = rig
        ik_cns.pole_subtarget = c_pole_ik_name
        ik_cns.pole_angle = 0.0
        if side == "Right":
            ik_cns.pole_angle = radians(180)
        ik_cns.chain_count = 2
        ik_cns.use_tail = True
        ik_cns.use_stretch = False

        forearm_ik_pb.lock_ik_y = True
        forearm_ik_pb.lock_ik_x = True

        cns_name = "Child Of"
        cns = c_pole_ik_pb.constraints.get(cns_name)
        if cns is None:
            cns = c_pole_ik_pb.constraints.new("CHILD_OF")
            cns.name = cns_name
        cns.target = rig
        cns.subtarget = c_prefix + spine_rig_names["pelvis"]

        cns_name = "Child Of"
        cns = c_hand_ik_pb.constraints.get(cns_name)
        if cns is None:
            cns = c_hand_ik_pb.constraints.new("CHILD_OF")
            cns.name = cns_name
        cns.target = rig
        cns.subtarget = c_master_name

        fingers_names = []
        c_fingers_names = []
        for fname in fingers_type:
            for i in range(1, 4):
                finger_name = get_mix_name(side + "Hand" + fname + str(i), True)
                finger_pb = get_pose_bone(finger_name)
                if finger_pb is None:
                    continue
                fingers_names.append(finger_name)
                c_finger_name = c_prefix + fname + str(i) + _side
                c_fingers_names.append(c_finger_name)
                c_finger_pb = get_pose_bone(c_finger_name)
                if c_finger_pb is None:
                    continue
                add_copy_transf(finger_pb, rig, c_finger_pb.name)

        if has_shoulder:
            add_copy_transf(shoulder_pb, rig, c_shoulder_name)

        if "ik_fk_switch" not in c_hand_ik_pb.keys():
            create_custom_prop(
                node=c_hand_ik_pb,
                prop_name="ik_fk_switch",
                prop_val=0.0,
                prop_min=0.0,
                prop_max=1.0,
                prop_description="IK-FK switch value",
            )

        cns_ik_name = "IK_follow"
        cns_ik = arm_pb.constraints.get(cns_ik_name)
        if cns_ik is None:
            cns_ik = arm_pb.constraints.new("COPY_TRANSFORMS")
            cns_ik.name = cns_ik_name
        cns_ik.target = rig
        cns_ik.subtarget = arm_ik_name
        cns_ik.influence = 1.0

        cns_fk_name = "FK_Follow"
        cns_fk = arm_pb.constraints.get(cns_fk_name)
        if cns_fk is None:
            cns_fk = arm_pb.constraints.new("COPY_TRANSFORMS")
            cns_fk.name = cns_fk_name
        cns_fk.target = rig
        cns_fk.subtarget = c_arm_fk_name
        cns_fk.influence = 0.0

        add_driver_to_prop(
            rig,
            'pose.bones["'
            + arm_name
            + '"].constraints["'
            + cns_fk_name
            + '"].influence',
            'pose.bones["' + c_hand_ik_name + '"]["ik_fk_switch"]',
            array_idx=-1,
            exp="var",
        )

        cns_ik_name = "IK_follow"
        cns_ik = forearm_pb.constraints.get(cns_ik_name)
        if cns_ik is None:
            cns_ik = forearm_pb.constraints.new("COPY_TRANSFORMS")
            cns_ik.name = cns_ik_name
        cns_ik.target = rig
        cns_ik.subtarget = forearm_ik_name
        cns_ik.influence = 1.0

        cns_fk_name = "FK_Follow"
        cns_fk = forearm_pb.constraints.get(cns_fk_name)
        if cns_fk is None:
            cns_fk = forearm_pb.constraints.new("COPY_TRANSFORMS")
            cns_fk.name = cns_fk_name
        cns_fk.target = rig
        cns_fk.subtarget = c_forearm_fk_name
        cns_fk.influence = 0.0

        add_driver_to_prop(
            rig,
            'pose.bones["'
            + forearm_name
            + '"].constraints["'
            + cns_fk_name
            + '"].influence',
            'pose.bones["' + c_hand_ik_name + '"]["ik_fk_switch"]',
            array_idx=-1,
            exp="var",
        )

        lock_pbone_transform(c_forearm_fk_pb, "location", [0, 1, 2])

        cns_ik_name = "IK_follow"
        cns_ik = hand_pb.constraints.get(cns_ik_name)
        if cns_ik is None:
            cns_ik = hand_pb.constraints.new("COPY_ROTATION")
            cns_ik.name = cns_ik_name
        cns_ik.target = rig
        cns_ik.subtarget = c_hand_ik_name
        cns_ik.influence = 1.0

        cns_fk_name = "FK_Follow"
        cns_fk = hand_pb.constraints.get(cns_fk_name)
        if cns_fk is None:
            cns_fk = hand_pb.constraints.new("COPY_ROTATION")
            cns_fk.name = cns_fk_name
        cns_fk.target = rig
        cns_fk.subtarget = c_hand_fk_name
        cns_fk.influence = 0.0

        add_driver_to_prop(
            rig,
            'pose.bones["'
            + hand_name
            + '"].constraints["'
            + cns_fk_name
            + '"].influence',
            'pose.bones["' + c_hand_ik_name + '"]["ik_fk_switch"]',
            array_idx=-1,
            exp="var",
        )

        lock_pbone_transform(c_hand_fk_pb, "location", [0, 1, 2])

        if has_shoulder:
            set_bone_custom_shape(c_shoulder_pb, "cs_shoulder_" + side.lower())
        set_bone_custom_shape(c_arm_fk_pb, "cs_arm_fk")
        set_bone_custom_shape(c_forearm_fk_pb, "cs_forearm_fk")
        set_bone_custom_shape(c_pole_ik_pb, "cs_sphere_012")
        set_bone_custom_shape(c_hand_fk_pb, "cs_circle")
        set_bone_custom_shape(c_hand_ik_pb, "cs_circle")

        c_fingers_pb = []
        for fname in fingers_type:
            for i in range(1, 4):
                c_finger_name = c_prefix + fname + str(i) + _side
                finger_pb = get_pose_bone(c_finger_name)
                if finger_pb is None:
                    continue
                c_fingers_pb.append(finger_pb)
                set_bone_custom_shape(finger_pb, "cs_circle_025")

        c_pbones_list = [
            c_arm_fk_pb,
            c_forearm_fk_pb,
            c_pole_ik_pb,
            c_hand_fk_pb,
            c_hand_ik_pb,
        ] + c_fingers_pb
        if has_shoulder:
            c_pbones_list.insert(0, c_shoulder_pb)

        for pb in c_pbones_list:
            pb.bone["mixamo_ctrl"] = 1

        ik_controls_names = [c_pole_ik_name, c_hand_ik_name]

        arr_ids = [-1]
        if blender_version._float >= 300:
            arr_ids = [0, 1, 2]

        for n in ik_controls_names:
            dr_dp = 'pose.bones["' + n + '"].' + get_custom_shape_scale_prop_name()
            tar_dp = 'pose.bones["' + c_hand_ik_name + '"]["ik_fk_switch"]'
            for arr_id in arr_ids:
                add_driver_to_prop(rig, dr_dp, tar_dp, array_idx=arr_id, exp="1-var")

        fk_controls_names = [
            c_arm_fk_name,
            c_forearm_fk_name,
            c_hand_fk_name,
        ]

        for n in fk_controls_names:
            dr_dp = 'pose.bones["' + n + '"].' + get_custom_shape_scale_prop_name()
            tar_dp = 'pose.bones["' + c_hand_ik_name + '"]["ik_fk_switch"]'
            for arr_id in arr_ids:
                add_driver_to_prop(rig, dr_dp, tar_dp, array_idx=arr_id, exp="var")

        for pb in c_pbones_list:
            pb.rotation_mode = "XYZ"
            set_bone_color_group(rig, pb, "body" + _side.lower())

    coll_ctrl_name = "CTRL"
    ctrl_collection = rig.data.collections.get(coll_ctrl_name)
    if ctrl_collection:
        for bone in ctrl_collection.bones:
            pose_bone = rig.pose.bones.get(bone.name)
            if pose_bone:
                pose_bone.custom_shape_wire_width = 3.0

    _fit_controller_custom_shapes(rig)

    rig.show_in_front = False


def _update(self, context):
    if blender_version._float >= 300:
        convert_drivers_cs_to_xyz(context.active_object)


def _make_rig(self, context):
    print("\nBuilding control rig...")

    if hasattr(self, "reference_mapping"):
        self.report(
            {"INFO"},
            "[Kai] reference_mapping received"
        )
    else:
        self.report(
            {"ERROR"},
            "[Kai] reference_mapping missing"
        )

    reference_mapping = self.reference_mapping

    reference_chest = reference_mapping["chest"]
    reference_spine_names = reference_mapping.get("spine_names", [])
    reference_chest_name = reference_mapping.get("chest_name", "")
    reference_last_spine_name = (
        reference_spine_names[-1]
        if reference_spine_names
        else reference_chest_name
    )

    self.report(
        {"INFO"},
        (
            "[Kai] _make_rig spine chain: "
            f"Spines={reference_spine_names} | "
            f"Chest={reference_chest_name} | "
            f"LastSpine={reference_last_spine_name}"
        )
    )

    # kai_chest_ctrl_name = c_prefix + spine_rig_names["spine3"]
    kai_chest_ctrl_name = c_prefix + reference_chest_name
    kai_parent_spine_name = kai_chest_ctrl_name

    self.report(
        {"INFO"},
        (
            "[Kai] Chest control target: "
            f"ReferenceChest={reference_chest_name} | "
            f"CtrlChest={kai_chest_ctrl_name}"
        )
)

    rig_name = context.active_object.name
    rig = get_object(rig_name)
    existing_bone_names = {bone.name for bone in rig.data.bones}
    existing_constraint_keys = _kai_snapshot_constraints(rig)

    # Ensure we're in OBJECT mode - do NOT force dependency graph update here
    try:
        bpy.ops.object.mode_set(mode="OBJECT")
    except Exception as e:
        print(f"  Warning: Could not set initial mode: {e}")

    # Preload all custom shape objects in a single, safe place to avoid appending
    # while rapidly switching modes during rig construction.
    try:
        shape_names = [
            "cs_master",
            "cs_circle",
            "cs_square_2",
            "cs_hips",
            "cs_neck",
            "cs_head",
            "cs_thigh_fk",
            "cs_calf_fk",
            "cs_foot",
            "cs_sphere_012",
            "cs_foot_roll",
            "cs_foot_01",
            "cs_toe",
            "cs_shoulder_left",
            "cs_shoulder_right",
            "cs_arm_fk",
            "cs_forearm_fk",
            "cs_hand",
            "cs_circle_025",
        ]
        append_cs(shape_names)
    except Exception:
        # Fallback silently; set_bone_custom_shape will try best-effort lookups
        pass

    coll_mix_name = "DEF"
    coll_ctrl_name = "CTRL"
    coll_intern_name = "MCH"

    # Create collections if they don't exist
    for coll_name in [coll_mix_name, coll_ctrl_name, coll_intern_name]:
        if not rig.data.collections.get(coll_name):
            rig.data.collections.new(coll_name)

    use_name_prefix = True

    c_master_name = c_prefix + master_rig_names["master"]

    # Init transforms
    init_armature_transforms(rig)

    # Detect if source armature uses mixamorig: prefix
    detected_prefix = ""
    try:
        for bone in rig.data.bones:
            if bone.name.startswith("mixamorig") and ":" in bone.name:
                detected_prefix = bone.name.split(":")[0] + ":"
                print(f"  Detected Mixamo prefix: {detected_prefix}")
                break
    except Exception as e:
        print(f"  Warning: Could not detect prefix: {e}")

    if not detected_prefix:
        print("  No Mixamo prefix detected, using plain bone names")

    # Helper function to construct source bone names with the correct prefix
    def get_src_bone_name(base_name):
        result = (detected_prefix + base_name) if detected_prefix else base_name
        return result

    # ==========================================
    # PHASE 1: ALL EDIT MODE OPERATIONS
    # ==========================================
    print("  Phase 1: Creating all edit bones...")
    bpy.ops.object.mode_set(mode="EDIT")

    # Data structures to store information needed for pose mode
    edit_data = {
        "master": {},
        "spine": {},
        "head": {},
        "leg_left": {},
        "leg_right": {},
        "arm_left": {},
        "arm_right": {},
    }

    # Master bones
    print("    Creating Master bones...")
    c_master = create_edit_bone(c_master_name)
    c_master.head = [0, 0, 0]
    c_master.tail = [0, 0, 0.05 * rig.dimensions[2]]
    c_master.roll = 0.01
    ctrl_collection = rig.data.collections.get(coll_ctrl_name)
    if not ctrl_collection:
        ctrl_collection = rig.data.collections.new(coll_ctrl_name)
    ctrl_collection.assign(c_master)

    # Spine bones
    print("    Creating Spine bones...")

    kai_source_spine_names, kai_source_chest_name, _, _ = (
        _kai_resolve_spine_sources(
            reference_mapping.get("spine_names", []),
            reference_chest_name,
        )
    )

    self.report(
        {"INFO"},
        (
            "[Kai] Source spine setup: "
            f"Spines={kai_source_spine_names} | "
            f"Chest={kai_source_chest_name}"
        )
    )

    hips_name = _kai_prefixed_source_bone_name(
        reference_mapping.get("hip_name", ""),
        detected_prefix,
    )
    spine_control_pairs = _kai_build_spine_control_pairs(
        kai_source_spine_names,
        kai_source_chest_name,
        detected_prefix,
    )

    hips = get_edit_bone(hips_name)
    spine_source_bones = [
        (pair, get_edit_bone(pair["source_name"]))
        for pair in spine_control_pairs
    ]

    if hips and spine_source_bones and all(bone for _, bone in spine_source_bones):
        for b in [hips] + [bone for _, bone in spine_source_bones]:
            set_bone_collection(rig, b, coll_mix_name)

        # Hips Ctrl
        c_hips_name = c_prefix + spine_rig_names["pelvis"]
        c_hips = create_edit_bone(c_hips_name)
        copy_bone_transforms(hips, c_hips)
        c_hips.parent = get_edit_bone(c_prefix + master_rig_names["master"])
        set_bone_collection(rig, c_hips, coll_ctrl_name)

        # Free Hips Ctrl
        c_hips_free_name = c_prefix + spine_rig_names["hips_free"]
        c_hips_free = create_edit_bone(c_hips_free_name)
        try:
            c_hips_free.head = hips.tail.copy()
            c_hips_free.tail = hips.head.copy()
            align_bone_x_axis(c_hips_free, hips.x_axis)
        except Exception as e:
            print(f"    Warning: Error setting hips_free transforms: {e}")
            copy_bone_transforms(hips, c_hips_free)

        c_hips_free.parent = c_hips
        set_bone_collection(rig, c_hips_free, coll_ctrl_name)

        # Free Hips helper
        hips_free_h_name = spine_rig_names["hips_free_helper"]
        hips_free_helper = create_edit_bone(hips_free_h_name)
        copy_bone_transforms(hips, hips_free_helper)
        hips_free_helper.parent = c_hips_free
        set_bone_collection(rig, hips_free_helper, coll_intern_name)

        spine_controls = []
        parent_ctrl = c_hips
        for pair, source_bone in spine_source_bones:
            c_spine = create_edit_bone(pair["control_name"])
            copy_bone_transforms(source_bone, c_spine)
            c_spine.parent = parent_ctrl
            set_bone_collection(rig, c_spine, coll_ctrl_name)
            spine_controls.append(
                {
                    "source_name": pair["source_name"],
                    "control_name": pair["control_name"],
                }
            )
            parent_ctrl = c_spine

        kai_parent_spine_name = spine_controls[-1]["control_name"]

        # Store data for pose mode
        edit_data["spine"] = {
            "exists": True,
            "hips_name": hips_name,
            "c_hips_name": c_hips_name,
            "hips_free_h_name": hips_free_h_name,
            "c_hips_free_name": c_hips_free_name,
            "spine_controls": spine_controls,
            "last_spine_control_name": kai_parent_spine_name,
        }
    else:
        print("    Spine bones are missing, skip spine")
        edit_data["spine"]["exists"] = False

    # Head bones
    print("    Creating Head bones...")
    kai_source_neck_names = reference_mapping.get("neck_names", [])
    kai_source_head_name = reference_mapping.get("head_name", "")
    neck_control_pairs = _kai_build_spine_control_pairs(
        kai_source_neck_names,
        None,
        detected_prefix,
    )
    head_name = _kai_prefixed_source_bone_name(kai_source_head_name, detected_prefix)
    head_end_name = get_src_bone_name(head_names["head_end"])

    neck_source_bones = [
        (pair, get_edit_bone(pair["source_name"]))
        for pair in neck_control_pairs
    ]
    head = get_edit_bone(head_name)
    head_end = get_edit_bone(head_end_name)

    if head and all(bone for _, bone in neck_source_bones):
        for b in [bone for _, bone in neck_source_bones] + [head, head_end]:
            if b is not None:
                set_bone_collection(rig, b, coll_mix_name)

        neck_controls = []
        parent_ctrl = get_edit_bone(kai_parent_spine_name)
        for pair, source_bone in neck_source_bones:
            c_neck = create_edit_bone(pair["control_name"])
            copy_bone_transforms(source_bone, c_neck)
            c_neck.parent = parent_ctrl
            set_bone_collection(rig, c_neck, coll_ctrl_name)
            neck_controls.append(
                {
                    "source_name": pair["source_name"],
                    "control_name": pair["control_name"],
                }
            )
            parent_ctrl = c_neck

        # Head Ctrl
        c_head_name = c_prefix + head_rig_names["head"]
        c_head = create_edit_bone(c_head_name)
        copy_bone_transforms(head, c_head)
        c_head.parent = parent_ctrl
        set_bone_collection(rig, c_head, coll_ctrl_name)

        edit_data["head"] = {
            "exists": True,
            "head_name": head_name,
            "neck_controls": neck_controls,
            "c_head_name": c_head_name,
        }
    else:
        print("    Head bone is missing, skip head")
        edit_data["head"]["exists"] = False

    # Leg bones for both sides
    for side in ["Left", "Right"]:
        print(f"    Creating Leg bones for {side}...")
        _side = "_" + side
        thigh_name = get_src_bone_name(side + leg_names["thigh"])
        calf_name = get_src_bone_name(side + leg_names["calf"])
        foot_name = get_src_bone_name(side + leg_names["foot"])
        toe_name = get_src_bone_name(side + leg_names["toes"])
        toe_end_name = get_src_bone_name(side + leg_names["toes_end"])

        thigh = get_edit_bone(thigh_name)
        calf = get_edit_bone(calf_name)
        foot = get_edit_bone(foot_name)
        toe = get_edit_bone(toe_name)
        toe_end = get_edit_bone(toe_end_name)

        hips = get_edit_bone(get_src_bone_name(spine_names["pelvis"]))
        c_hips_free_name = c_prefix + spine_rig_names["hips_free"]
        c_hips_free = get_edit_bone(c_hips_free_name)

        if not thigh or not calf or not foot or not toe:
            print(f"    Leg bones are missing, skip leg: {side}")
            edit_data[f"leg_{side.lower()}"]["exists"] = False
            continue

        # Set Mixamo bones in layer
        for b in [thigh, calf, foot, toe, toe_end]:
            set_bone_collection(rig, b, coll_mix_name)

        # Create bones
        # correct straight leg angle
        def get_leg_angle(thigh=thigh, calf=calf, foot=foot):  # noqa: B023
            vec1 = calf.head - thigh.head
            vec2 = foot.head - calf.head
            return degrees(vec1.angle(vec2))

        leg_angle = get_leg_angle()

        if leg_angle < 0.1:
            print(f"    ! Straight leg bones, angle = {leg_angle}")
            max_iter = 10000
            i = 0

            while leg_angle < 0.1 and i < max_iter:
                dir = ((thigh.z_axis + calf.z_axis) * 0.5).normalized()
                calf.head += dir * (calf.tail - calf.head).magnitude * 0.0001
                leg_angle = get_leg_angle()
                i += 1

            print(f"      corrected leg angle: {leg_angle}")

        # Thigh IK
        thigh_ik_name = leg_rig_names["thigh_ik"] + _side
        thigh_ik = create_edit_bone(thigh_ik_name)
        copy_bone_transforms(thigh, thigh_ik)

        # auto-align knee position
        leg_axis = calf.tail - thigh.head
        leg_midpoint = (thigh.head + calf.tail) * 0.5

        dir = calf.head - leg_midpoint
        cur_vec = project_vector_onto_plane(dir, leg_axis)
        global_y_vec = project_vector_onto_plane(Vector((0, -1, 0)), leg_axis)

        signed_cur_angle = signed_angle(cur_vec, global_y_vec, leg_axis)

        # rotate
        rotated_point = rotate_point(
            calf.head.copy(), -signed_cur_angle, leg_midpoint, leg_axis
        )

        thigh_ik.tail = rotated_point
        thigh_ik.parent = c_hips_free
        set_bone_collection(rig, thigh_ik, coll_intern_name)

        # Thigh FK Ctrl
        c_thigh_fk_name = c_prefix + leg_rig_names["thigh_fk"] + _side
        c_thigh_fk = create_edit_bone(c_thigh_fk_name)
        copy_bone_transforms(thigh_ik, c_thigh_fk)
        c_thigh_fk.parent = c_hips_free
        set_bone_collection(rig, c_thigh_fk, coll_ctrl_name)

        # Calf IK
        calf_ik_name = leg_rig_names["calf_ik"] + _side
        calf_ik_exist = get_edit_bone(calf_ik_name)

        calf_ik = create_edit_bone(calf_ik_name)
        if calf_ik_exist is None:
            copy_bone_transforms(calf, calf_ik)
        calf_ik.head = thigh_ik.tail.copy()
        calf_ik.tail = foot.head.copy()
        calf_ik.parent = thigh_ik
        calf_ik.use_connect = True
        set_bone_collection(rig, calf_ik, coll_intern_name)

        # align thigh and calf IK roll
        align_bone_z_axis(calf_ik, (calf_ik.head - leg_midpoint))
        align_bone_z_axis(thigh_ik, calf_ik.z_axis)
        copy_bone_transforms(thigh_ik, c_thigh_fk)

        # Calf FK Ctrl
        c_calf_fk_name = c_prefix + leg_rig_names["calf_fk"] + _side
        c_calf_fk = create_edit_bone(c_calf_fk_name)
        copy_bone_transforms(calf_ik, c_calf_fk)
        c_calf_fk.parent = c_thigh_fk
        set_bone_collection(rig, c_calf_fk, coll_ctrl_name)

        # Foot FK Ctrl
        c_foot_fk_name = c_prefix + leg_rig_names["foot_fk"] + _side
        c_foot_fk = create_edit_bone(c_foot_fk_name)
        copy_bone_transforms(foot, c_foot_fk)
        c_foot_fk.tail[2] = foot.head[2]
        align_bone_z_axis(c_foot_fk, Vector((0, 0, 1)))
        c_foot_fk.parent = c_calf_fk
        set_bone_collection(rig, c_foot_fk, coll_ctrl_name)

        # Foot FK
        foot_fk_name = leg_rig_names["foot_fk"] + _side
        foot_fk = create_edit_bone(foot_fk_name)
        copy_bone_transforms(foot, foot_fk)
        foot_fk.parent = c_foot_fk
        set_bone_collection(rig, foot_fk, coll_intern_name)

        # Foot IK Ctrl
        c_foot_ik_name = c_prefix + leg_rig_names["foot_ik"] + _side
        c_foot_ik = create_edit_bone(c_foot_ik_name)
        copy_bone_transforms(foot, c_foot_ik)
        c_foot_ik.tail[2] = foot.head[2]
        align_bone_z_axis(c_foot_ik, Vector((0, 0, 1)))
        set_bone_collection(rig, c_foot_ik, coll_ctrl_name)

        # Foot IK
        foot_ik_name = leg_rig_names["foot_ik"] + _side
        foot_ik = create_edit_bone(foot_ik_name)
        copy_bone_transforms(foot, foot_ik)
        foot_ik.parent = c_foot_ik
        set_bone_collection(rig, foot_ik, coll_intern_name)

        # Foot Snap
        foot_snap_name = leg_rig_names["foot_snap"] + _side
        foot_snap = create_edit_bone(foot_snap_name)
        copy_bone_transforms(c_foot_ik, foot_snap)
        foot_snap.parent = foot_ik
        set_bone_collection(rig, foot_snap, coll_intern_name)

        # Foot IK target
        foot_ik_target_name = leg_rig_names["foot_ik_target"] + _side
        foot_ik_target = create_edit_bone(foot_ik_target_name)
        foot_ik_target.head = foot_ik.head.copy()
        foot_vec = foot.tail - foot.head
        foot_ik_target.tail = foot_ik_target.head - (foot_vec * 0.25)
        align_bone_z_axis(foot_ik_target, Vector((0, 0, 1)))
        set_bone_collection(rig, foot_ik_target, coll_intern_name)

        # Foot Heel Out
        heel_out_name = leg_rig_names["heel_out"] + _side
        heel_out = create_edit_bone(heel_out_name)
        heel_out.head, heel_out.tail = Vector((0, 0, 0)), Vector((0, 0, 1))
        heel_out.parent = c_foot_ik
        set_bone_collection(rig, heel_out, coll_intern_name)

        # Foot Heel In
        heel_in_name = leg_rig_names["heel_in"] + _side
        heel_in = create_edit_bone(heel_in_name)
        heel_in.head, heel_in.tail = Vector((0, 0, 0)), Vector((0, 0, 1))
        heel_in.parent = heel_out
        set_bone_collection(rig, heel_in, coll_intern_name)

        # Foot Heel Mid
        heel_mid_name = leg_rig_names["heel_mid"] + _side
        heel_mid = create_edit_bone(heel_mid_name)
        heel_mid.head, heel_mid.tail = Vector((0, 0, 0)), Vector((0, 0, 1))
        heel_mid.parent = heel_in
        set_bone_collection(rig, heel_mid, coll_intern_name)

        heel_mid.head[0], heel_mid.head[1], heel_mid.head[2] = (
            foot.head[0],
            foot.head[1],
            foot.tail[2],
        )
        heel_mid.tail = foot.tail.copy()
        heel_mid.tail[2] = heel_mid.head[2]
        heel_mid.tail = heel_mid.head + (heel_mid.tail - heel_mid.head) * 0.5
        align_bone_x_axis(heel_mid, foot.x_axis)

        copy_bone_transforms(heel_mid, heel_in)
        fac = 1
        if side == "Right":
            fac = -1

        heel_in.head += foot.x_axis.normalized() * foot.length * 0.3 * fac
        heel_in.tail += foot.x_axis.normalized() * foot.length * 0.3 * fac

        copy_bone_transforms(heel_mid, heel_out)
        heel_out.head += foot.x_axis.normalized() * foot.length * 0.3 * -fac
        heel_out.tail += foot.x_axis.normalized() * foot.length * 0.3 * -fac

        # Toe End
        toes_end_name = leg_rig_names["toes_end"] + _side
        toes_end = create_edit_bone(toes_end_name)
        copy_bone_transforms(toe, toes_end)
        toe_vec = toes_end.tail - toes_end.head
        toes_end.tail += toe_vec
        toes_end.head += toe_vec
        toes_end.parent = heel_mid
        set_bone_collection(rig, toes_end, coll_intern_name)

        # Toe End 01
        toes_end_01_name = leg_rig_names["toes_end_01"] + _side
        toes_end_01 = create_edit_bone(toes_end_01_name)
        copy_bone_transforms(toes_end, toes_end_01)
        vec = toes_end_01.tail - toes_end_01.head
        toes_end_01.tail = toes_end_01.head + (vec * 0.5)
        toes_end_01.parent = toes_end
        set_bone_collection(rig, toes_end_01, coll_intern_name)

        # Foot 01 Ctrl
        c_foot_01_name = c_prefix + leg_rig_names["foot_01"] + _side
        c_foot_01 = create_edit_bone(c_foot_01_name)
        copy_bone_transforms(foot, c_foot_01)
        c_foot_01_vec = c_foot_01.tail - c_foot_01.head
        c_foot_01.tail += c_foot_01_vec
        c_foot_01.head += c_foot_01_vec
        c_foot_01.parent = toes_end
        set_bone_collection(rig, c_foot_01, coll_ctrl_name)

        # Foot_ik_target parent
        foot_ik_target.parent = c_foot_01

        # Foot 01 Pole
        foot_01_pole_name = leg_rig_names["foot_01_pole"] + _side
        foot_01_pole = create_edit_bone(foot_01_pole_name)
        foot_01_pole.head = c_foot_01.head + (
            c_foot_01.z_axis * 0.05 * c_foot_01.length * 40
        )
        foot_01_pole.tail = foot_01_pole.head + (
            c_foot_01.z_axis * 0.05 * c_foot_01.length * 40
        )
        foot_01_pole.roll = radians(180)
        foot_01_pole.parent = c_foot_01
        set_bone_collection(rig, foot_01_pole, coll_intern_name)

        # Toe IK Ctrl
        c_toe_ik_name = c_prefix + leg_rig_names["toes_ik"] + _side
        c_toe_ik = create_edit_bone(c_toe_ik_name)
        copy_bone_transforms(toe, c_toe_ik)
        c_toe_ik.parent = toes_end
        set_bone_collection(rig, c_toe_ik, coll_ctrl_name)

        # Toe FK Ctrl
        c_toe_fk_name = c_prefix + leg_rig_names["toes_fk"] + _side
        c_toe_fk = create_edit_bone(c_toe_fk_name)
        copy_bone_transforms(toe, c_toe_fk)
        c_toe_fk.parent = foot_fk
        set_bone_collection(rig, c_toe_fk, coll_ctrl_name)

        # Toe Track
        toe_track_name = leg_rig_names["toes_track"] + _side
        toe_track = create_edit_bone(toe_track_name)
        copy_bone_transforms(toe, toe_track)
        toe_track.parent = foot_ik
        set_bone_collection(rig, toe_track, coll_intern_name)

        # Toe_01 IK
        toe_01_ik_name = leg_rig_names["toes_01_ik"] + _side
        toe_01_ik = create_edit_bone(toe_01_ik_name)
        copy_bone_transforms(toe, toe_01_ik)
        toe_01_ik.tail = toe_01_ik.head + (toe_01_ik.tail - toe_01_ik.head) * 0.5
        toe_01_ik.parent = toe_track
        set_bone_collection(rig, toe_01_ik, coll_intern_name)

        # Toe_02
        toe_02_name = leg_rig_names["toes_02"] + _side
        toe_02 = create_edit_bone(toe_02_name)
        copy_bone_transforms(toe, toe_02)
        toe_02.head = toe_02.head + (toe_02.tail - toe_02.head) * 0.5
        toe_02.parent = toe_01_ik
        set_bone_collection(rig, toe_02, coll_intern_name)

        # Foot Roll Cursor Ctrl
        c_foot_roll_cursor_name = c_prefix + leg_rig_names["foot_roll_cursor"] + _side
        c_foot_roll_cursor = create_edit_bone(c_foot_roll_cursor_name)
        copy_bone_transforms(c_foot_ik, c_foot_roll_cursor)
        vec = c_foot_roll_cursor.tail - c_foot_roll_cursor.head
        dist = 1.2
        c_foot_roll_cursor.head -= vec * dist
        c_foot_roll_cursor.tail -= vec * dist
        c_foot_roll_cursor.parent = c_foot_ik
        set_bone_collection(rig, c_foot_roll_cursor, coll_ctrl_name)

        # Pole IK Ctrl
        c_pole_ik_name = c_prefix + leg_rig_names["pole_ik"] + _side
        c_pole_ik = create_edit_bone(c_pole_ik_name)
        set_bone_collection(rig, c_pole_ik, coll_ctrl_name)

        plane_normal = thigh_ik.head - calf_ik.tail
        prepole_dir = calf_ik.head - leg_midpoint
        pole_pos = calf_ik.head + prepole_dir.normalized()
        pole_pos = project_point_onto_plane(pole_pos, calf_ik.head, plane_normal)
        pole_pos = calf_ik.head + (
            (pole_pos - calf_ik.head).normalized()
            * (calf_ik.head - thigh.head).magnitude
            * 1.7
        )

        c_pole_ik.head = pole_pos
        c_pole_ik.tail = [
            c_pole_ik.head[0],
            c_pole_ik.head[1],
            c_pole_ik.head[2] + (0.165 * thigh_ik.length * 2),
        ]

        ik_pole_angle = get_pole_angle(thigh_ik, calf_ik, c_pole_ik.head)

        # Add slight bend to avoid singularities
        add_slight_bend(calf_ik, Vector((1, 0, 0)))  # +X axis for both legs

        # Store data for pose mode
        edit_data[f"leg_{side.lower()}"] = {
            "exists": True,
            "side": side,
            "thigh_name": thigh_name,
            "calf_name": calf_name,
            "foot_name": foot_name,
            "toe_name": toe_name,
            "thigh_ik_name": thigh_ik_name,
            "calf_ik_name": calf_ik_name,
            "foot_ik_name": foot_ik_name,
            "foot_ik_target_name": foot_ik_target_name,
            "c_foot_ik_name": c_foot_ik_name,
            "c_pole_ik_name": c_pole_ik_name,
            "c_thigh_fk_name": c_thigh_fk_name,
            "c_calf_fk_name": c_calf_fk_name,
            "c_foot_fk_name": c_foot_fk_name,
            "foot_fk_name": foot_fk_name,
            "c_toe_ik_name": c_toe_ik_name,
            "c_toe_fk_name": c_toe_fk_name,
            "c_foot_01_name": c_foot_01_name,
            "c_foot_roll_cursor_name": c_foot_roll_cursor_name,
            "toes_end_name": toes_end_name,
            "toes_end_01_name": toes_end_01_name,
            "toe_01_ik_name": toe_01_ik_name,
            "toe_02_name": toe_02_name,
            "toe_track_name": toe_track_name,
            "heel_mid_name": heel_mid_name,
            "heel_in_name": heel_in_name,
            "heel_out_name": heel_out_name,
            "foot_01_pole_name": foot_01_pole_name,
            "ik_pole_angle": ik_pole_angle,
        }

    # Arm bones for both sides
    for side in ["Left", "Right"]:
        print(f"    Creating Arm bones for {side}...")
        _side = "_" + side
        mapped_shoulder_name = reference_mapping.get("shoulder_names", {}).get(side, "")
        shoulder_name = (
            _kai_prefixed_source_bone_name(mapped_shoulder_name, detected_prefix)
            if mapped_shoulder_name
            else None
        )
        arm_name = get_src_bone_name(side + arm_names["arm"])
        forearm_name = get_src_bone_name(side + arm_names["forearm"])
        hand_name = get_src_bone_name(side + arm_names["hand"])

        shoulder = get_edit_bone(shoulder_name) if shoulder_name else None
        arm = get_edit_bone(arm_name)
        forearm = get_edit_bone(forearm_name)
        hand = get_edit_bone(hand_name)
        has_shoulder = shoulder is not None

        if not arm or not forearm or not hand:
            print(f"    Arm bones are missing, skip arm: {side}")
            edit_data[f"arm_{side.lower()}"]["exists"] = False
            continue

        # Create bones
        # Fingers
        fingers_names = []
        c_fingers_names = []
        fingers = []
        finger_leaves = []

        for fname in fingers_type:
            for i in range(1, 4):
                finger_name = get_mix_name(
                    side + "Hand" + fname + str(i), use_name_prefix
                )
                finger = get_edit_bone(finger_name)
                if finger is None:
                    continue

                fingers_names.append(finger_name)
                fingers.append(finger)
                c_finger_name = c_prefix + fname + str(i) + _side
                c_fingers_names.append(c_finger_name)
                c_finger = create_edit_bone(c_finger_name)
                copy_bone_transforms(finger, c_finger)
                set_bone_collection(rig, c_finger, coll_ctrl_name)

                if i == 1:
                    c_finger.parent = hand
                else:
                    prev_finger_name = c_prefix + fname + str(i - 1) + _side
                    prev_finger = get_edit_bone(prev_finger_name)
                    c_finger.parent = prev_finger

        # fingers "leaves"/tip bones
        for fname in fingers_type:
            finger_name = get_src_bone_name(side + "Hand" + fname + "4")
            finger_leaf = get_edit_bone(finger_name)
            finger_leaves.append(finger_leaf)

        # Set Mixamo bones in layer
        for b in [shoulder, arm, forearm, hand] + fingers + finger_leaves:
            if b is not None:
                set_bone_collection(rig, b, coll_mix_name)

        # Shoulder Ctrl
        c_shoulder_name = None
        c_shoulder = None
        if has_shoulder:
            c_shoulder_name = c_prefix + arm_rig_names["shoulder"] + _side
            c_shoulder = create_edit_bone(c_shoulder_name)
            copy_bone_transforms(shoulder, c_shoulder)
            # c_shoulder.parent = get_edit_bone(c_prefix + spine_rig_names["spine3"])
            c_shoulder.parent = get_edit_bone(kai_parent_spine_name)
            set_bone_collection(rig, c_shoulder, coll_ctrl_name)

        # Arm IK
        arm_ik_name = arm_rig_names["arm_ik"] + _side
        arm_ik = create_edit_bone(arm_ik_name)
        copy_bone_transforms(arm, arm_ik)

        # correct straight arms angle
        angle_min = 0.1

        def get_arm_angle(arm=arm, forearm=forearm, hand=hand):  # noqa: B023
            vec1 = forearm.head - arm.head
            vec2 = hand.head - forearm.head
            return degrees(vec1.angle(vec2))

        arm_angle = get_arm_angle()

        if arm_angle < angle_min:
            print(f"    ! Straight arm bones, angle = {arm_angle}")

            max_iter = 10000
            i = 0

            while arm_angle < angle_min and i < max_iter:
                dir = ((arm.x_axis + forearm.x_axis) * 0.5).normalized()
                if side == "Right":
                    dir *= -1

                forearm.head += dir * (forearm.tail - forearm.head).magnitude * 0.0001
                arm_angle = get_arm_angle()
                i += 1

            print(f"      corrected arm angle: {arm_angle}")

        # auto-align elbow position
        arm_axis = forearm.tail - arm.head
        arm_midpoint = (arm.head + forearm.tail) * 0.5

        dir = forearm.head - arm_midpoint
        cur_vec = project_vector_onto_plane(dir, arm_axis)
        global_y_vec = project_vector_onto_plane(Vector((0, 1, 0)), arm_axis)
        signed_cur_angle = signed_angle(cur_vec, global_y_vec, arm_axis)

        # rotate
        rotated_point = rotate_point(
            forearm.head.copy(), -signed_cur_angle, arm_midpoint, arm_axis
        )

        arm_ik.tail = rotated_point
        arm_ik.parent = c_shoulder if c_shoulder is not None else get_edit_bone(kai_parent_spine_name)
        set_bone_collection(rig, arm_ik, coll_intern_name)

        # Arm FK Ctrl
        c_arm_fk_name = c_prefix + arm_rig_names["arm_fk"] + _side
        c_arm_fk = create_edit_bone(c_arm_fk_name)
        # c_arm_fk.parent = get_edit_bone(c_prefix + spine_rig_names["spine3"])
        c_arm_fk.parent = get_edit_bone(kai_parent_spine_name)
        copy_bone_transforms(arm_ik, c_arm_fk)
        set_bone_collection(rig, c_arm_fk, coll_ctrl_name)

        # ForeArm IK
        forearm_ik_name = arm_rig_names["forearm_ik"] + _side
        forearm_ik = create_edit_bone(forearm_ik_name)
        copy_bone_transforms(forearm, forearm_ik)
        forearm_ik.head = arm_ik.tail.copy()
        forearm_ik.tail = hand.head.copy()
        forearm_ik.parent = arm_ik
        set_bone_collection(rig, forearm_ik, coll_intern_name)

        # align arm and forearm IK roll
        align_bone_x_axis(forearm_ik, (forearm_ik.head - arm_midpoint))
        align_bone_x_axis(arm_ik, forearm_ik.x_axis)
        copy_bone_transforms(arm_ik, c_arm_fk)

        if side == "Right":
            forearm_ik.roll += radians(180)
            arm_ik.roll += radians(180)
            c_arm_fk.roll += radians(180)

        # Forearm FK Ctrl
        c_forearm_fk_name = c_prefix + arm_rig_names["forearm_fk"] + _side
        c_forearm_fk = create_edit_bone(c_forearm_fk_name)
        copy_bone_transforms(forearm_ik, c_forearm_fk)
        c_forearm_fk.parent = c_arm_fk
        set_bone_collection(rig, c_forearm_fk, coll_ctrl_name)

        # Pole IK Ctrl
        c_pole_ik_name = c_prefix + arm_rig_names["pole_ik"] + _side
        c_pole_ik = create_edit_bone(c_pole_ik_name)
        set_bone_collection(rig, c_pole_ik, coll_ctrl_name)

        arm_midpoint = (arm_ik.head + forearm_ik.tail) * 0.5

        plane_normal = arm_ik.head - forearm_ik.tail
        prepole_dir = forearm_ik.head - arm_midpoint
        pole_pos = forearm_ik.head + prepole_dir.normalized()
        pole_pos = project_point_onto_plane(pole_pos, forearm_ik.head, plane_normal)
        pole_pos = forearm_ik.head + (
            (pole_pos - forearm_ik.head).normalized()
            * (forearm_ik.head - arm.head).magnitude
            * 1.0
        )

        c_pole_ik.head = pole_pos
        c_pole_ik.tail = [
            c_pole_ik.head[0],
            c_pole_ik.head[1],
            c_pole_ik.head[2] + (0.165 * arm_ik.length * 4),
        ]

        ik_pole_angle = get_pole_angle(arm_ik, forearm_ik, c_pole_ik.head)

        # Hand IK Ctrl
        c_hand_ik_name = c_prefix + arm_rig_names["hand_ik"] + _side
        c_hand_ik = create_edit_bone(c_hand_ik_name)
        set_bone_collection(rig, c_hand_ik, coll_ctrl_name)
        copy_bone_transforms(hand, c_hand_ik)

        # Hand FK Ctrl
        c_hand_fk_name = c_prefix + arm_rig_names["hand_fk"] + _side
        c_hand_fk = create_edit_bone(c_hand_fk_name)
        copy_bone_transforms(hand, c_hand_fk)
        c_hand_fk.parent = c_forearm_fk
        set_bone_collection(rig, c_hand_fk, coll_ctrl_name)

        # Add Slight bend to arms to avoid singularity
        if side == "Left":
            add_slight_bend(forearm_ik, Vector((0, 0, -1)))  # -Z axis for left
        else:  # Right
            add_slight_bend(forearm_ik, Vector((0, 0, 1)))  # +Z axis for right

        # Store data for pose mode
        edit_data[f"arm_{side.lower()}"] = {
            "exists": True,
            "side": side,
            "shoulder_name": shoulder_name,
            "has_shoulder": has_shoulder,
            "arm_name": arm_name,
            "forearm_name": forearm_name,
            "hand_name": hand_name,
            "c_shoulder_name": c_shoulder_name,
            "arm_ik_name": arm_ik_name,
            "forearm_ik_name": forearm_ik_name,
            "c_arm_fk_name": c_arm_fk_name,
            "c_forearm_fk_name": c_forearm_fk_name,
            "c_pole_ik_name": c_pole_ik_name,
            "c_hand_ik_name": c_hand_ik_name,
            "c_hand_fk_name": c_hand_fk_name,
            "fingers_names": fingers_names,
            "c_fingers_names": c_fingers_names,
            "ik_pole_angle": ik_pole_angle,
        }

    # Ensure eye bones are in DEF collection
    eye_bone_names = ["RightEye", "LeftEye"]
    for eye_name in eye_bone_names:
        eye_bone = rig.data.edit_bones.get(eye_name)
        if eye_bone:
            set_bone_collection(rig, eye_bone, coll_mix_name)

    # ==========================================
    # PHASE 2: ALL POSE MODE OPERATIONS
    # ==========================================
    print("  Phase 2: Setting up all pose bones...")
    bpy.ops.object.mode_set(mode="POSE")
    bpy.context.view_layer.update()

    # Master pose setup
    print("    Setting up Master pose...")
    c_master_pb = get_pose_bone(c_master_name)
    c_master_pb.bone["mixamo_ctrl"] = 1
    set_bone_custom_shape(c_master_pb, "cs_master")
    c_master_pb.rotation_mode = "XYZ"
    set_bone_color_group(rig, c_master_pb, "master")

    # Spine pose setup
    if edit_data["spine"].get("exists"):
        print("    Setting up Spine pose...")
        spine_data = edit_data["spine"]

        self.report(
            {"INFO"},
            f"[Kai] Spine Data: {spine_data}"
        )

        c_hips_pb = get_pose_bone(spine_data["c_hips_name"])
        get_pose_bone(spine_data["hips_free_h_name"])
        c_hips_free_pb = get_pose_bone(spine_data["c_hips_free_name"])
        spine_control_pbones = [
            get_pose_bone(ctrl_data["control_name"])
            for ctrl_data in spine_data.get("spine_controls", [])
        ]

        # tag controller bones
        for pb in [c_hips_pb, c_hips_free_pb] + spine_control_pbones:
            if pb is None:
                continue
            pb.bone["mixamo_ctrl"] = 1

        # set custom shapes
        set_bone_custom_shape(c_hips_pb, "cs_square_2")
        set_bone_custom_shape(c_hips_free_pb, "cs_hips")
        for pb in spine_control_pbones:
            if pb is not None:
                set_bone_custom_shape(pb, "cs_circle")

        # set rotation mode
        c_hips_pb.rotation_mode = "XYZ"
        c_hips_free_pb.rotation_mode = "XYZ"
        for pb in spine_control_pbones:
            if pb is not None:
                pb.rotation_mode = "XYZ"

        # set color group
        set_bone_color_group(rig, c_hips_pb, "root_master")
        set_bone_color_group(rig, c_hips_free_pb, "body_mid")
        for pb in spine_control_pbones:
            if pb is not None:
                set_bone_color_group(rig, pb, "body_mid")

        # constraints
        mixamo_spine_pb = get_pose_bone(spine_data["hips_name"])
        cns = mixamo_spine_pb.constraints.get("Copy Transforms")
        if cns is None:
            cns = mixamo_spine_pb.constraints.new("COPY_TRANSFORMS")
            cns.name = "Copy Transforms"
        cns.target = rig
        cns.subtarget = spine_data["hips_free_h_name"]

        self.report(
            {"INFO"},
            f"[Kai] Pose spine data = {spine_data}"
        )

        for ctrl_data in spine_data.get("spine_controls", []):
            mixamo_spine_pb = get_pose_bone(ctrl_data["source_name"])

            if mixamo_spine_pb is None:
                continue

            cns = mixamo_spine_pb.constraints.get("Copy Transforms")
            if cns is None:
                cns = mixamo_spine_pb.constraints.new("COPY_TRANSFORMS")
                cns.name = "Copy Transforms"

            cns.target = rig
            cns.subtarget = ctrl_data["control_name"]

    # Head pose setup
    if edit_data["head"].get("exists"):
        print("    Setting up Head pose...")
        head_data = edit_data["head"]

        neck_control_pbones = [
            get_pose_bone(ctrl_data["control_name"])
            for ctrl_data in head_data.get("neck_controls", [])
        ]
        c_head_pb = get_pose_bone(head_data["c_head_name"])

        # tag controller bones
        for pb in neck_control_pbones:
            if pb is not None:
                pb.bone["mixamo_ctrl"] = 1
        if c_head_pb is not None:
            c_head_pb.bone["mixamo_ctrl"] = 1

        # set custom shapes
        for pb in neck_control_pbones:
            if pb is not None:
                set_bone_custom_shape(pb, "cs_neck")
        if c_head_pb is not None:
            set_bone_custom_shape(c_head_pb, "cs_head")

        # set custom shape scale for head controller
        if c_head_pb is not None:
            c_head_pb.custom_shape_scale_xyz[0] = 1.9
            c_head_pb.custom_shape_scale_xyz[1] = 1.9
            c_head_pb.custom_shape_scale_xyz[2] = 1.9

        # set rotation mode
        for pb in neck_control_pbones:
            if pb is not None:
                pb.rotation_mode = "XYZ"
        if c_head_pb is not None:
            c_head_pb.rotation_mode = "XYZ"

        # set color group
        for pb in neck_control_pbones:
            if pb is not None:
                set_bone_color_group(rig, pb, "neck")
        if c_head_pb is not None:
            set_bone_color_group(rig, c_head_pb, "head")

        # constraints
        for ctrl_data in head_data.get("neck_controls", []):
            neck_pb = get_pose_bone(ctrl_data["source_name"])
            c_neck_pb = get_pose_bone(ctrl_data["control_name"])
            if neck_pb is not None and c_neck_pb is not None:
                add_copy_transf(neck_pb, rig, ctrl_data["control_name"])

        head_pb = get_pose_bone(head_data["head_name"])

        if head_pb is not None and c_head_pb is not None:
            add_copy_transf(head_pb, rig, head_data["c_head_name"])

    # Leg pose setup for both sides
    for side in ["left", "right"]:
        if not edit_data[f"leg_{side}"].get("exists"):
            continue

        print(f"    Setting up Leg pose for {side}...")
        leg_data = edit_data[f"leg_{side}"]
        _side = "_" + leg_data["side"]

        # Get pose bones
        calf_ik_pb = get_pose_bone(leg_data["calf_ik_name"])
        foot_ik_pb = get_pose_bone(leg_data["foot_ik_name"])
        c_foot_ik_pb = get_pose_bone(leg_data["c_foot_ik_name"])
        c_pole_ik_pb = get_pose_bone(leg_data["c_pole_ik_name"])
        toes_end_pb = get_pose_bone(leg_data["toes_end_name"])
        toe_01_ik_pb = get_pose_bone(leg_data["toe_01_ik_name"])
        toe_02_pb = get_pose_bone(leg_data["toe_02_name"])
        toe_track_pb = get_pose_bone(leg_data["toe_track_name"])
        heel_mid_pb = get_pose_bone(leg_data["heel_mid_name"])
        heel_in_pb = get_pose_bone(leg_data["heel_in_name"])
        heel_out_pb = get_pose_bone(leg_data["heel_out_name"])
        foot_pb = get_pose_bone(leg_data["foot_name"])
        thigh_pb = get_pose_bone(leg_data["thigh_name"])
        calf_pb = get_pose_bone(leg_data["calf_name"])
        toe_pb = get_pose_bone(leg_data["toe_name"])
        c_foot_01_pb = get_pose_bone(leg_data["c_foot_01_name"])
        c_foot_roll_cursor_pb = get_pose_bone(leg_data["c_foot_roll_cursor_name"])
        c_thigh_fk_pb = get_pose_bone(leg_data["c_thigh_fk_name"])
        c_calf_fk_pb = get_pose_bone(leg_data["c_calf_fk_name"])
        c_foot_fk_pb = get_pose_bone(leg_data["c_foot_fk_name"])
        c_toe_ik_pb = get_pose_bone(leg_data["c_toe_ik_name"])
        c_toe_fk_pb = get_pose_bone(leg_data["c_toe_fk_name"])

        # Calf IK constraint
        cns_name = "IK"
        ik_cns = calf_ik_pb.constraints.get(cns_name)
        if ik_cns is None:
            ik_cns = calf_ik_pb.constraints.new("IK")
            ik_cns.name = cns_name
        ik_cns.target = rig
        ik_cns.subtarget = leg_data["foot_ik_target_name"]
        ik_cns.pole_target = rig
        ik_cns.pole_subtarget = leg_data["c_pole_ik_name"]
        ik_cns.pole_angle = leg_data["ik_pole_angle"]
        ik_cns.chain_count = 2
        ik_cns.use_tail = True
        ik_cns.use_stretch = False

        calf_ik_pb.lock_ik_y = True
        calf_ik_pb.lock_ik_z = True

        # Foot IK constraints
        cns_name = "Copy Location"
        copy_loc_cns = foot_ik_pb.constraints.get(cns_name)
        if copy_loc_cns is None:
            copy_loc_cns = foot_ik_pb.constraints.new("COPY_LOCATION")
            copy_loc_cns.name = cns_name
        copy_loc_cns.target = rig
        copy_loc_cns.subtarget = leg_data["calf_ik_name"]
        copy_loc_cns.head_tail = 1.0

        cns_name = "TrackTo"
        cns = foot_ik_pb.constraints.get(cns_name)
        if cns is None:
            cns = foot_ik_pb.constraints.new("TRACK_TO")
            cns.name = cns_name
        cns.target = rig
        cns.subtarget = leg_data["c_foot_01_name"]
        cns.head_tail = 0.0
        cns.track_axis = "TRACK_Y"
        cns.up_axis = "UP_Z"
        cns.use_target_z = True

        cns_name = "Locked Track"
        cns = foot_ik_pb.constraints.get(cns_name)
        if cns is None:
            cns = foot_ik_pb.constraints.new("LOCKED_TRACK")
            cns.name = cns_name
        cns.target = rig
        cns.subtarget = leg_data["foot_01_pole_name"]
        cns.head_tail = 0.0
        cns.track_axis = "TRACK_Z"
        cns.lock_axis = "LOCK_Y"

        cns_name = "Copy Scale"
        cns = foot_ik_pb.constraints.get(cns_name)
        if cns is None:
            cns = foot_ik_pb.constraints.new("COPY_SCALE")
            cns.name = cns_name
        cns.target = rig
        cns.subtarget = leg_data["c_foot_ik_name"]

        # Foot Ctrl IK
        cns_name = "Child Of"
        cns = c_foot_ik_pb.constraints.get(cns_name)
        if cns is None:
            cns = c_foot_ik_pb.constraints.new("CHILD_OF")
            cns.name = cns_name
        cns.target = rig
        cns.subtarget = "Ctrl_Master"

        # Pole IK
        cns_name = "Child Of"
        child_cns = c_pole_ik_pb.constraints.get(cns_name)
        if child_cns is None:
            child_cns = c_pole_ik_pb.constraints.new("CHILD_OF")
            child_cns.name = cns_name
        child_cns.target = rig
        child_cns.subtarget = leg_data["c_foot_ik_name"]

        cns_power = 8

        # Toe End
        toe_end_length = toes_end_pb.length * cns_power

        cns_name = "Transformation"
        cns = toes_end_pb.constraints.get(cns_name)
        if cns is None:
            cns = toes_end_pb.constraints.new("TRANSFORM")
            cns.name = cns_name
        cns.target = rig
        cns.subtarget = leg_data["c_foot_roll_cursor_name"]
        cns.use_motion_extrapolate = True
        cns.target_space = cns.owner_space = "LOCAL"
        cns.map_from = "LOCATION"
        cns.from_min_z = 0.5 * toe_end_length
        cns.from_max_z = -0.5 * toe_end_length
        cns.map_to = "ROTATION"
        cns.map_to_x_from = "Z"
        cns.map_to_z_from = "X"
        cns.to_min_x_rot = -2.61
        cns.to_max_x_rot = 2.61
        cns.mix_mode_rot = "ADD"

        cns_name = "Limit Rotation"
        cns = toes_end_pb.constraints.get(cns_name)
        if cns is None:
            cns = toes_end_pb.constraints.new("LIMIT_ROTATION")
            cns.name = cns_name
        cns.owner_space = "LOCAL"
        cns.use_limit_x = True
        cns.min_x = -2 * pi
        cns.max_x = 0.0

        # Toe 01 ik
        cns_name = "Copy Transforms"
        cns = toe_01_ik_pb.constraints.get(cns_name)
        if cns is None:
            cns = toe_01_ik_pb.constraints.new("COPY_TRANSFORMS")
            cns.name = cns_name
        cns.target = rig
        cns.subtarget = leg_data["c_toe_ik_name"]
        cns.mix_mode = "REPLACE"
        cns.target_space = cns.owner_space = "WORLD"

        # Toe 02
        cns_name = "Copy CopyRotation"
        cns = toe_02_pb.constraints.get(cns_name)
        if cns is None:
            cns = toe_02_pb.constraints.new("COPY_ROTATION")
            cns.name = cns_name
        cns.target = rig
        cns.subtarget = leg_data["c_toe_ik_name"]
        cns.mix_mode = "REPLACE"
        cns.target_space = cns.owner_space = "WORLD"

        # Toe Track
        cns_name = "TrackTo"
        cns = toe_track_pb.constraints.get(cns_name)
        if cns is None:
            cns = toe_track_pb.constraints.new("TRACK_TO")
            cns.name = cns_name
        cns.target = rig
        cns.subtarget = leg_data["toes_end_01_name"]
        cns.head_tail = 0.0
        cns.track_axis = "TRACK_Y"
        cns.up_axis = "UP_Z"
        cns.use_target_z = True

        # Heel Mid
        heel_mid_length = heel_mid_pb.length * cns_power

        cns_name = "Transformation"
        cns = heel_mid_pb.constraints.get(cns_name)
        if cns is None:
            cns = heel_mid_pb.constraints.new("TRANSFORM")
            cns.name = cns_name
        cns.target = rig
        cns.subtarget = leg_data["c_foot_roll_cursor_name"]
        cns.owner_space = cns.target_space = "LOCAL"
        cns.map_from = "LOCATION"
        cns.from_min_z = -0.25 * heel_mid_length
        cns.from_max_z = 0.25 * heel_mid_length
        cns.map_to = "ROTATION"
        cns.map_to_x_from = "Z"
        cns.map_to_y_from = "X"
        cns.map_to_z_from = "Y"
        cns.to_min_x_rot = radians(100)
        cns.to_max_x_rot = -radians(100)
        cns.mix_mode_rot = "ADD"

        cns_name = "Limit Rotation"
        cns = heel_mid_pb.constraints.get(cns_name)
        if cns is None:
            cns = heel_mid_pb.constraints.new("LIMIT_ROTATION")
            cns.name = cns_name
        cns.use_limit_x = True
        cns.min_x = radians(0)
        cns.max_x = radians(360)
        cns.owner_space = "LOCAL"

        # Heel In
        heel_in_length = heel_in_pb.length * cns_power

        cns_name = "Transformation"
        cns = heel_in_pb.constraints.get(cns_name)
        if cns is None:
            cns = heel_in_pb.constraints.new("TRANSFORM")
            cns.name = cns_name
        cns.target = rig
        cns.subtarget = leg_data["c_foot_roll_cursor_name"]
        cns.owner_space = cns.target_space = "LOCAL"
        cns.map_from = "LOCATION"
        cns.from_min_x = -0.25 * heel_in_length
        cns.from_max_x = 0.25 * heel_in_length
        cns.map_to = "ROTATION"
        cns.map_to_x_from = "Z"
        cns.map_to_y_from = "X"
        cns.map_to_z_from = "Y"
        cns.to_min_y_rot = -radians(100)
        cns.to_max_y_rot = radians(100)
        cns.mix_mode_rot = "ADD"

        cns_name = "Limit Rotation"
        cns = heel_in_pb.constraints.get(cns_name)
        if cns is None:
            cns = heel_in_pb.constraints.new("LIMIT_ROTATION")
            cns.name = cns_name
        cns.use_limit_y = True

        if leg_data["side"] == "Left":
            cns.min_y = 0.0
            cns.max_y = radians(90)
        elif leg_data["side"] == "Right":
            cns.min_y = radians(-90)
            cns.max_y = radians(0.0)

        cns.owner_space = "LOCAL"

        # Heel Out
        heel_out_length = heel_out_pb.length * cns_power

        cns_name = "Transformation"
        cns = heel_out_pb.constraints.get(cns_name)
        if cns is None:
            cns = heel_out_pb.constraints.new("TRANSFORM")
            cns.name = cns_name
        cns.target = rig
        cns.subtarget = leg_data["c_foot_roll_cursor_name"]
        cns.owner_space = cns.target_space = "LOCAL"
        cns.map_from = "LOCATION"
        cns.from_min_x = -0.25 * heel_out_length
        cns.from_max_x = 0.25 * heel_out_length
        cns.map_to = "ROTATION"
        cns.map_to_x_from = "Z"
        cns.map_to_y_from = "X"
        cns.map_to_z_from = "Y"
        cns.to_min_y_rot = -radians(100)
        cns.to_max_y_rot = radians(100)
        cns.mix_mode_rot = "ADD"

        cns_name = "Limit Rotation"
        cns = heel_out_pb.constraints.get(cns_name)
        if cns is None:
            cns = heel_out_pb.constraints.new("LIMIT_ROTATION")
            cns.name = cns_name
        cns.use_limit_y = True

        if leg_data["side"] == "Left":
            cns.min_y = radians(-90)
            cns.max_y = radians(0.0)
        elif leg_data["side"] == "Right":
            cns.min_y = radians(0.0)
            cns.max_y = radians(90)

        cns.owner_space = "LOCAL"

        # IK-FK switch property
        if "ik_fk_switch" not in c_foot_ik_pb.keys():
            create_custom_prop(
                node=c_foot_ik_pb,
                prop_name="ik_fk_switch",
                prop_val=0.0,
                prop_min=0.0,
                prop_max=1.0,
                prop_description="IK-FK switch value",
            )

        c_foot_ik_pb["ik_fk_switch"] = 0.0 if self.ik_legs else 1.0

        # Thigh
        cns_name = "IK_follow"
        cns_ik = thigh_pb.constraints.get(cns_name)
        if cns_ik is None:
            cns_ik = thigh_pb.constraints.new("COPY_TRANSFORMS")
            cns_ik.name = cns_name
        cns_ik.target = rig
        cns_ik.subtarget = leg_data["thigh_ik_name"]
        cns_ik.influence = 1.0

        cns_name = "FK_follow"
        cns_fk = thigh_pb.constraints.get(cns_name)
        if cns_fk is None:
            cns_fk = thigh_pb.constraints.new("COPY_TRANSFORMS")
            cns_fk.name = cns_name
        cns_fk.target = rig
        cns_fk.subtarget = leg_data["c_thigh_fk_name"]
        cns_fk.influence = 0.0

        add_driver_to_prop(
            rig,
            'pose.bones["'
            + leg_data["thigh_name"]
            + '"].constraints["'
            + cns_name
            + '"].influence',
            'pose.bones["' + leg_data["c_foot_ik_name"] + '"]["ik_fk_switch"]',
            array_idx=-1,
            exp="var",
        )

        # Calf
        cns_name = "IK_follow"
        cns_ik = calf_pb.constraints.get(cns_name)
        if cns_ik is None:
            cns_ik = calf_pb.constraints.new("COPY_TRANSFORMS")
            cns_ik.name = cns_name
        cns_ik.target = rig
        cns_ik.subtarget = leg_data["calf_ik_name"]
        cns_ik.influence = 1.0

        cns_name = "FK_follow"
        cns_fk = calf_pb.constraints.get(cns_name)
        if cns_fk is None:
            cns_fk = calf_pb.constraints.new("COPY_TRANSFORMS")
            cns_fk.name = cns_name
        cns_fk.target = rig
        cns_fk.subtarget = leg_data["c_calf_fk_name"]
        cns_fk.influence = 0.0

        add_driver_to_prop(
            rig,
            f'pose.bones["{leg_data["calf_name"]}"].constraints["{cns_name}"].influence',
            'pose.bones["' + leg_data["c_foot_ik_name"] + '"]["ik_fk_switch"]',
            array_idx=-1,
            exp="var",
        )

        # Foot
        cns_name = "IK_follow"
        cns_ik = foot_pb.constraints.get(cns_name)
        if cns_ik is None:
            cns_ik = foot_pb.constraints.new("COPY_TRANSFORMS")
            cns_ik.name = cns_name
        cns_ik.target = rig
        cns_ik.subtarget = leg_data["foot_ik_name"]
        cns_ik.influence = 1.0

        cns_name = "FK_follow"
        cns_fk = foot_pb.constraints.get(cns_name)
        if cns_fk is None:
            cns_fk = foot_pb.constraints.new("COPY_TRANSFORMS")
            cns_fk.name = cns_name
        cns_fk.target = rig
        cns_fk.subtarget = leg_data["foot_fk_name"]
        cns_fk.influence = 0.0

        add_driver_to_prop(
            rig,
            f'pose.bones["{leg_data["foot_name"]}"].constraints["{cns_name}"].influence',
            'pose.bones["' + leg_data["c_foot_ik_name"] + '"]["ik_fk_switch"]',
            array_idx=-1,
            exp="var",
        )

        # Toe
        cns_name = "IK_Rot_follow"
        cns_ik_rot = toe_pb.constraints.get(cns_name)
        if cns_ik_rot is None:
            cns_ik_rot = toe_pb.constraints.new("COPY_ROTATION")
            cns_ik_rot.name = cns_name
        cns_ik_rot.target = rig
        cns_ik_rot.subtarget = leg_data["c_toe_ik_name"]
        cns_ik_rot.influence = 1.0

        cns_name = "IK_Scale_follow"
        cns_ik_scale = toe_pb.constraints.get(cns_name)
        if cns_ik_scale is None:
            cns_ik_scale = toe_pb.constraints.new("COPY_SCALE")
            cns_ik_scale.name = cns_name
        cns_ik_scale.target = rig
        cns_ik_scale.subtarget = leg_data["c_toe_ik_name"]
        cns_ik_scale.influence = 1.0

        cns_name_fk_rot = "FK_Rot_follow"
        cns_fk_rot = toe_pb.constraints.get(cns_name_fk_rot)
        if cns_fk_rot is None:
            cns_fk_rot = toe_pb.constraints.new("COPY_ROTATION")
            cns_fk_rot.name = cns_name_fk_rot
        cns_fk_rot.target = rig
        cns_fk_rot.subtarget = leg_data["c_toe_fk_name"]
        cns_fk_rot.influence = 1.0

        cns_name_fk_scale = "FK_Scale_follow"
        cns_fk_scale = toe_pb.constraints.get(cns_name_fk_scale)
        if cns_fk_scale is None:
            cns_fk_scale = toe_pb.constraints.new("COPY_SCALE")
            cns_fk_scale.name = cns_name_fk_scale
        cns_fk_scale.target = rig
        cns_fk_scale.subtarget = leg_data["c_toe_fk_name"]
        cns_fk_scale.influence = 1.0

        add_driver_to_prop(
            rig,
            'pose.bones["'
            + leg_data["toe_name"]
            + '"].constraints["'
            + cns_name_fk_rot
            + '"].influence',
            'pose.bones["' + leg_data["c_foot_ik_name"] + '"]["ik_fk_switch"]',
            array_idx=-1,
            exp="var",
        )
        add_driver_to_prop(
            rig,
            'pose.bones["'
            + leg_data["toe_name"]
            + '"].constraints["'
            + cns_name_fk_scale
            + '"].influence',
            'pose.bones["' + leg_data["c_foot_ik_name"] + '"]["ik_fk_switch"]',
            array_idx=-1,
            exp="var",
        )

        # Set transforms locks
        lock_pbone_transform(c_foot_roll_cursor_pb, "location", [1])
        lock_pbone_transform(c_foot_roll_cursor_pb, "rotation", [0, 1, 2])
        lock_pbone_transform(c_foot_roll_cursor_pb, "scale", [0, 1, 2])

        lock_pbone_transform(c_foot_01_pb, "location", [0, 1, 2])
        lock_pbone_transform(c_foot_01_pb, "rotation", [1, 2])
        lock_pbone_transform(c_foot_01_pb, "scale", [0, 1, 2])

        lock_pbone_transform(c_foot_fk_pb, "location", [0, 1, 2])

        lock_pbone_transform(c_pole_ik_pb, "rotation", [0, 1, 2])
        lock_pbone_transform(c_pole_ik_pb, "scale", [0, 1, 2])

        lock_pbone_transform(c_thigh_fk_pb, "location", [0, 1, 2])
        lock_pbone_transform(c_calf_fk_pb, "location", [0, 1, 2])

        c_pbones_list = [
            c_foot_ik_pb,
            c_pole_ik_pb,
            c_foot_01_pb,
            c_foot_roll_cursor_pb,
            c_thigh_fk_pb,
            c_calf_fk_pb,
            c_foot_fk_pb,
            c_toe_fk_pb,
            c_toe_ik_pb,
        ]

        # tag controller bones
        for pb in c_pbones_list:
            pb.bone["mixamo_ctrl"] = 1

        # Set custom shapes
        set_bone_custom_shape(c_thigh_fk_pb, "cs_thigh_fk")
        set_bone_custom_shape(c_calf_fk_pb, "cs_calf_fk")
        set_bone_custom_shape(c_foot_ik_pb, "cs_foot")
        set_bone_custom_shape(c_foot_fk_pb, "cs_foot")
        set_bone_custom_shape(c_pole_ik_pb, "cs_sphere_012")
        set_bone_custom_shape(c_foot_roll_cursor_pb, "cs_foot_roll")
        set_bone_custom_shape(c_foot_01_pb, "cs_foot_01")
        set_bone_custom_shape(c_toe_fk_pb, "cs_toe")
        set_bone_custom_shape(c_toe_ik_pb, "cs_toe")

        # set custom shape drivers
        ik_controls_names = [
            leg_data["c_foot_ik_name"],
            leg_data["c_foot_01_name"],
            leg_data["c_toe_ik_name"],
            leg_data["c_foot_roll_cursor_name"],
            leg_data["c_pole_ik_name"],
        ]

        arr_ids = [-1]
        if blender_version._float >= 300:
            arr_ids = [0, 1, 2]

        for n in ik_controls_names:
            dr_dp = 'pose.bones["' + n + '"].' + get_custom_shape_scale_prop_name()
            tar_dp = 'pose.bones["' + leg_data["c_foot_ik_name"] + '"]["ik_fk_switch"]'
            for arr_id in arr_ids:
                add_driver_to_prop(rig, dr_dp, tar_dp, array_idx=arr_id, exp="1-var")

        fk_controls_names = [
            leg_data["c_foot_fk_name"],
            leg_data["c_thigh_fk_name"],
            leg_data["c_calf_fk_name"],
            leg_data["c_toe_fk_name"],
        ]

        for n in fk_controls_names:
            dr_dp = 'pose.bones["' + n + '"].' + get_custom_shape_scale_prop_name()
            tar_dp = 'pose.bones["' + leg_data["c_foot_ik_name"] + '"]["ik_fk_switch"]'
            for arr_id in arr_ids:
                add_driver_to_prop(rig, dr_dp, tar_dp, array_idx=arr_id, exp="var")

        for pb in c_pbones_list:
            # set rotation euler
            pb.rotation_mode = "XYZ"
            # set color group
            set_bone_color_group(rig, pb, "body" + _side.lower())

    # Arm pose setup for both sides
    for side in ["left", "right"]:
        if not edit_data[f"arm_{side}"].get("exists"):
            continue

        print(f"    Setting up Arm pose for {side}...")
        arm_data = edit_data[f"arm_{side}"]
        _side = "_" + arm_data["side"]

        # Get pose bones
        has_shoulder = arm_data.get("has_shoulder", False)
        c_shoulder_pb = (
            get_pose_bone(arm_data["c_shoulder_name"])
            if has_shoulder
            else None
        )
        shoulder_pb = (
            get_pose_bone(arm_data["shoulder_name"])
            if has_shoulder
            else None
        )
        c_arm_fk_pb = get_pose_bone(arm_data["c_arm_fk_name"])
        forearm_ik_pb = get_pose_bone(arm_data["forearm_ik_name"])
        c_pole_ik_pb = get_pose_bone(arm_data["c_pole_ik_name"])
        c_hand_ik_pb = get_pose_bone(arm_data["c_hand_ik_name"])
        hand_pb = get_pose_bone(arm_data["hand_name"])
        arm_pb = get_pose_bone(arm_data["arm_name"])
        forearm_pb = get_pose_bone(arm_data["forearm_name"])
        c_forearm_fk_pb = get_pose_bone(arm_data["c_forearm_fk_name"])
        c_hand_fk_pb = get_pose_bone(arm_data["c_hand_fk_name"])

        # Arm FK Ctrl
        if has_shoulder and c_shoulder_pb is not None:
            cns_name = "Copy Location"
            cns = c_arm_fk_pb.constraints.get(cns_name)
            if cns is None:
                cns = c_arm_fk_pb.constraints.new("COPY_LOCATION")
                cns.name = cns_name
            cns.head_tail = 1.0
            cns.target = rig
            cns.subtarget = arm_data["c_shoulder_name"]

        # Forearm IK
        cns_name = "IK"
        ik_cns = forearm_ik_pb.constraints.get(cns_name)
        if ik_cns is None:
            ik_cns = forearm_ik_pb.constraints.new("IK")
            ik_cns.name = cns_name
        ik_cns.target = rig
        ik_cns.subtarget = arm_data["c_hand_ik_name"]
        ik_cns.pole_target = rig
        ik_cns.pole_subtarget = arm_data["c_pole_ik_name"]
        ik_cns.pole_angle = 0.0
        if arm_data["side"] == "Right":
            ik_cns.pole_angle = radians(180)
        ik_cns.chain_count = 2
        ik_cns.use_tail = True
        ik_cns.use_stretch = False

        forearm_ik_pb.lock_ik_y = True
        forearm_ik_pb.lock_ik_x = True

        # Pole IK Ctrl
        cns_name = "Child Of"
        cns = c_pole_ik_pb.constraints.get(cns_name)
        if cns is None:
            cns = c_pole_ik_pb.constraints.new("CHILD_OF")
            cns.name = cns_name
        cns.target = rig
        cns.subtarget = c_prefix + spine_rig_names["pelvis"]

        # Hand IK Ctrl
        cns_name = "Child Of"
        cns = c_hand_ik_pb.constraints.get(cns_name)
        if cns is None:
            cns = c_hand_ik_pb.constraints.new("CHILD_OF")
            cns.name = cns_name
        cns.target = rig
        cns.subtarget = c_master_name

        # Fingers
        for i, fname in enumerate(arm_data["c_fingers_names"]):
            c_finger_pb = get_pose_bone(fname)
            finger_pb = get_pose_bone(arm_data["fingers_names"][i])
            add_copy_transf(finger_pb, rig, c_finger_pb.name)

        # Shoulder
        if has_shoulder and shoulder_pb is not None and c_shoulder_pb is not None:
            add_copy_transf(shoulder_pb, rig, c_shoulder_pb.name)

        # IK-FK switch property
        if "ik_fk_switch" not in c_hand_ik_pb.keys():
            create_custom_prop(
                node=c_hand_ik_pb,
                prop_name="ik_fk_switch",
                prop_val=0.0,
                prop_min=0.0,
                prop_max=1.0,
                prop_description="IK-FK switch value",
            )

        c_hand_ik_pb["ik_fk_switch"] = 0.0 if self.ik_arms else 1.0

        # Arm
        cns_ik_name = "IK_follow"
        cns_ik = arm_pb.constraints.get(cns_ik_name)
        if cns_ik is None:
            cns_ik = arm_pb.constraints.new("COPY_TRANSFORMS")
            cns_ik.name = cns_ik_name
        cns_ik.target = rig
        cns_ik.subtarget = arm_data["arm_ik_name"]
        cns_ik.influence = 1.0

        cns_fk_name = "FK_Follow"
        cns_fk = arm_pb.constraints.get(cns_fk_name)
        if cns_fk is None:
            cns_fk = arm_pb.constraints.new("COPY_TRANSFORMS")
            cns_fk.name = cns_fk_name
        cns_fk.target = rig
        cns_fk.subtarget = arm_data["c_arm_fk_name"]
        cns_fk.influence = 0.0

        add_driver_to_prop(
            rig,
            'pose.bones["'
            + arm_data["arm_name"]
            + '"].constraints["'
            + cns_fk_name
            + '"].influence',
            'pose.bones["' + arm_data["c_hand_ik_name"] + '"]["ik_fk_switch"]',
            array_idx=-1,
            exp="var",
        )

        # ForeArm
        cns_ik_name = "IK_follow"
        cns_ik = forearm_pb.constraints.get(cns_ik_name)
        if cns_ik is None:
            cns_ik = forearm_pb.constraints.new("COPY_TRANSFORMS")
            cns_ik.name = cns_ik_name
        cns_ik.target = rig
        cns_ik.subtarget = arm_data["forearm_ik_name"]
        cns_ik.influence = 1.0

        cns_fk_name = "FK_Follow"
        cns_fk = forearm_pb.constraints.get(cns_fk_name)
        if cns_fk is None:
            cns_fk = forearm_pb.constraints.new("COPY_TRANSFORMS")
            cns_fk.name = cns_fk_name
        cns_fk.target = rig
        cns_fk.subtarget = arm_data["c_forearm_fk_name"]
        cns_fk.influence = 0.0

        add_driver_to_prop(
            rig,
            'pose.bones["'
            + arm_data["forearm_name"]
            + '"].constraints["'
            + cns_fk_name
            + '"].influence',
            'pose.bones["' + arm_data["c_hand_ik_name"] + '"]["ik_fk_switch"]',
            array_idx=-1,
            exp="var",
        )

        lock_pbone_transform(c_forearm_fk_pb, "location", [0, 1, 2])

        # Hand
        cns_ik_name = "IK_follow"
        cns_ik = hand_pb.constraints.get(cns_ik_name)
        if cns_ik is None:
            cns_ik = hand_pb.constraints.new("COPY_ROTATION")
            cns_ik.name = cns_ik_name
        cns_ik.target = rig
        cns_ik.subtarget = arm_data["c_hand_ik_name"]
        cns_ik.influence = 1.0

        cns_fk_name = "FK_Follow"
        cns_fk = hand_pb.constraints.get(cns_fk_name)
        if cns_fk is None:
            cns_fk = hand_pb.constraints.new("COPY_ROTATION")
            cns_fk.name = cns_fk_name
        cns_fk.target = rig
        cns_fk.subtarget = arm_data["c_hand_fk_name"]
        cns_fk.influence = 0.0

        add_driver_to_prop(
            rig,
            'pose.bones["'
            + arm_data["hand_name"]
            + '"].constraints["'
            + cns_fk_name
            + '"].influence',
            'pose.bones["' + arm_data["c_hand_ik_name"] + '"]["ik_fk_switch"]',
            array_idx=-1,
            exp="var",
        )

        lock_pbone_transform(c_hand_fk_pb, "location", [0, 1, 2])

        # Set custom shapes
        if has_shoulder and c_shoulder_pb is not None:
            set_bone_custom_shape(c_shoulder_pb, "cs_shoulder_" + arm_data["side"].lower())
        set_bone_custom_shape(c_arm_fk_pb, "cs_arm_fk")
        set_bone_custom_shape(c_forearm_fk_pb, "cs_forearm_fk")
        set_bone_custom_shape(c_pole_ik_pb, "cs_sphere_012")
        set_bone_custom_shape(c_hand_fk_pb, "cs_circle")
        set_bone_custom_shape(c_hand_ik_pb, "cs_circle")

        c_fingers_pb = []

        for fname in arm_data["c_fingers_names"]:
            finger_pb = get_pose_bone(fname)
            c_fingers_pb.append(finger_pb)
            set_bone_custom_shape(finger_pb, "cs_circle_025")

        c_pbones_list = [
            c_arm_fk_pb,
            c_forearm_fk_pb,
            c_pole_ik_pb,
            c_hand_fk_pb,
            c_hand_ik_pb,
        ] + c_fingers_pb
        if has_shoulder and c_shoulder_pb is not None:
            c_pbones_list.insert(0, c_shoulder_pb)

        # tag controller bones
        for pb in c_pbones_list:
            pb.bone["mixamo_ctrl"] = 1

        # set custom shape drivers
        ik_controls_names = [arm_data["c_pole_ik_name"], arm_data["c_hand_ik_name"]]

        arr_ids = [-1]
        if blender_version._float >= 300:
            arr_ids = [0, 1, 2]

        for n in ik_controls_names:
            dr_dp = 'pose.bones["' + n + '"].' + get_custom_shape_scale_prop_name()
            tar_dp = 'pose.bones["' + arm_data["c_hand_ik_name"] + '"]["ik_fk_switch"]'
            for arr_id in arr_ids:
                add_driver_to_prop(rig, dr_dp, tar_dp, array_idx=arr_id, exp="1-var")

        fk_controls_names = [
            arm_data["c_arm_fk_name"],
            arm_data["c_forearm_fk_name"],
            arm_data["c_hand_fk_name"],
        ]

        for n in fk_controls_names:
            dr_dp = 'pose.bones["' + n + '"].' + get_custom_shape_scale_prop_name()
            tar_dp = 'pose.bones["' + arm_data["c_hand_ik_name"] + '"]["ik_fk_switch"]'
            for arr_id in arr_ids:
                add_driver_to_prop(rig, dr_dp, tar_dp, array_idx=arr_id, exp="var")

        for pb in c_pbones_list:
            # set rotation euler
            pb.rotation_mode = "XYZ"
            # set color group
            set_bone_color_group(rig, pb, "body" + _side.lower())

    # Set custom_shape_wire_width for all control bones
    print("  Setting wire width for control bones...")
    ctrl_collection = rig.data.collections.get(coll_ctrl_name)
    if ctrl_collection:
        for bone in ctrl_collection.bones:
            pose_bone = rig.pose.bones.get(bone.name)
            if pose_bone:
                pose_bone.custom_shape_wire_width = 3.0

    # Store Kai mapping before fitting custom shapes so variable controller names
    # such as Ctrl_Chest can be discovered by the shape fitting pass.
    safe_spine_names = [
        name for name in reference_mapping.get("spine_names", [])
        if name
    ]
    safe_neck_names = [
        name for name in reference_mapping.get("neck_names", [])
        if name
    ]
    safe_hip_name = reference_mapping.get("hip_name", "")
    safe_chest_name = reference_mapping.get("chest_name", "")
    safe_head_name = reference_mapping.get("head_name", "")
    safe_shoulder_names = reference_mapping.get("shoulder_names", {})
    safe_shoulder_left_name = safe_shoulder_names.get("Left", "")
    safe_shoulder_right_name = safe_shoulder_names.get("Right", "")

    self.report(
        {"INFO"},
        (
            "[Kai] Saving validated mapping names: "
            f"Hip={safe_hip_name} | "
            f"Spines={safe_spine_names} | "
            f"Chest={safe_chest_name} | "
            f"Necks={safe_neck_names} | "
            f"Head={safe_head_name} | "
            f"Shoulders={{'Left': '{safe_shoulder_left_name}', "
            f"'Right': '{safe_shoulder_right_name}'}}"
        )
    )

    rig.data["kai_spine_names"] = ",".join(safe_spine_names)
    rig.data["kai_chest_name"] = safe_chest_name
    rig.data["kai_hip_name"] = safe_hip_name
    rig.data["kai_neck_names"] = ",".join(safe_neck_names)
    rig.data["kai_head_name"] = safe_head_name
    rig.data["kai_shoulder_left_name"] = safe_shoulder_left_name
    rig.data["kai_shoulder_right_name"] = safe_shoulder_right_name
    _kai_store_mapping_topology(
        rig,
        {
            "hip": safe_hip_name,
            "spines": safe_spine_names,
            "chest": safe_chest_name,
            "necks": safe_neck_names,
            "head": safe_head_name,
            "shoulders": {
                "Left": safe_shoulder_left_name,
                "Right": safe_shoulder_right_name,
            },
        },
    )

    self.report(
        {"INFO"},
        (
            "[Kai] Saved Kai mapping to rig.data: "
            f"Hip={rig.data['kai_hip_name']} | "
            f"Spines={rig.data['kai_spine_names']} | "
            f"Chest={rig.data['kai_chest_name']} | "
            f"Necks={rig.data['kai_neck_names']} | "
            f"Head={rig.data['kai_head_name']} | "
            f"Shoulders={{'Left': '{rig.data['kai_shoulder_left_name']}', "
            f"'Right': '{rig.data['kai_shoulder_right_name']}'}}"
        )
    )

    print("  Fitting hand and head control shapes...")
    _fit_controller_custom_shapes(rig)

    # Set rig to not show in front
    rig.show_in_front = False

    generated_names = _kai_store_generated_bones(rig, existing_bone_names)
    _kai_store_generated_constraints(rig, existing_constraint_keys, generated_names)
    self.report(
        {"INFO"},
        f"[Kai] Stored generated bones: {len(generated_names)}",
    )

    # tag the armature with a custom prop to specify the control rig is built
    rig.data["mr_control_rig"] = True

    print("  Control rig build complete!")


def _zero_out(context):
    print("\nZeroing out...")
    arm = context.object

    print("  Clear anim")
    # Store the action for later if needed, then completely clear animation_data
    # This is the most reliable way to avoid dependency graph crashes in Blender 4.5+
    stored_action = None
    if arm.animation_data:
        try:
            stored_action = animation_compat.get_action_from_animdata(
                arm.animation_data
            )
            # Completely clear animation_data to avoid any dependency graph issues
            arm.animation_data_clear()
            action_name = stored_action.name if stored_action else "None"
            print(f"  Animation data cleared (action was: {action_name})")
        except Exception as e:
            print(f"  Warning: Could not clear animation data: {e}")
            # Fallback: just unlink
            try:
                arm.animation_data.action = None
                has_slots = animation_compat.has_slotted_actions()
                if has_slots and hasattr(arm.animation_data, "action_slot"):
                    arm.animation_data.action_slot = None
            except Exception:
                pass

    print("  Clear pose")
    # Reset pose
    bpy.ops.object.mode_set(mode="POSE")

    for b in arm.pose.bones:
        b.location = [0, 0, 0]
        b.rotation_euler = [0, 0, 0]
        b.rotation_quaternion = [1, 0, 0, 0]
        b.scale = [1, 1, 1]

    print("Zeroed out.")


def _bake_anim(self, context):
    scn = context.scene

    # get min-max frame range
    rig = context.object

    if rig.animation_data is None:
        print("No animation data, exit bake")
        return

    if rig.animation_data.nla_tracks is None:
        print("No NLA tracks found, exit bake")
        return

    tracks = rig.animation_data.nla_tracks

    fs = None
    fe = None

    # from NLA tracks
    for track in tracks:
        for strip in track.strips:
            if fs is None:
                fs = strip.frame_start
            if fe is None:
                fe = strip.frame_end

            if strip.frame_start < fs:
                fs = strip.frame_start
            if strip.frame_end > fe:
                fe = strip.frame_end

    if fs is None or fe is None:
        print("No NLA tracks found, exit")
        return

    # get active action frame range (compatible with both legacy and slotted actions)
    act = (
        animation_compat.get_action_from_animdata(rig.animation_data)
        if rig.animation_data
        else None
    )
    if act is not None:
        frame_range = animation_compat.get_action_frame_range(act)
        if frame_range[0] < fs:
            fs = frame_range[0]
        if frame_range[1] > fe:
            fe = frame_range[1]

    # select only controllers bones
    bpy.ops.object.mode_set(mode="POSE")
    bpy.ops.pose.select_all(action="DESELECT")

    found_ctrl = False
    for pbone in rig.pose.bones:
        if "mixamo_ctrl" in pbone.bone.keys():
            rig.data.bones.active = pbone.bone
            set_pose_bone_selected(pbone, True)
            found_ctrl = True

    if not found_ctrl:  # backward compatibility, use layer 0 instead
        print("Ctrl bones not tagged, search in layer 0 instead...")
        c0 = rig.data.collections.get("CTRL")
        if c0 is not None:
            for b in c0.bones:
                pb = rig.pose.bones.get(b.name)
                if pb is not None:
                    rig.data.bones.active = pb.bone
                    set_pose_bone_selected(pb, True)

        # ~ for pbone in rig.pose.bones:
        # ~ if pbone.bone.layers[0]:
        # ~ rig.data.bones.active = pbone.bone
        # ~ pbone.select = True

    fs, fe = int(fs), int(fe)

    scn.frame_set(fs)
    bpy.context.view_layer.update()

    # bake NLA strips
    print("Baking, frame start:", fs, ",frame end", fe)
    bpy.ops.nla.bake(
        frame_start=fs,
        frame_end=fe,
        step=1,
        only_selected=True,
        visual_keying=False,
        clear_constraints=False,
        clear_parents=False,
        use_current_action=False,
        clean_curves=False,
        bake_types={"POSE"},
    )

    # remove tracks
    while len(tracks):
        rig.animation_data.nla_tracks.remove(tracks[0])


def redefine_source_rest_pose(src_arm, tar_arm):
    """
    Redefine the source armature's rest pose to match the target's rest pose.
    This modifies src_arm directly (like 3.6 version)
    to ensure proper helper bone creation.
    """
    print("  Redefining source rest pose...")

    # Get frame range using compatibility function
    src_action = animation_compat.get_action_from_animdata(src_arm.animation_data)
    fr_range = animation_compat.get_action_frame_range(src_action)
    fr_start = int(fr_range[0])
    fr_end = int(fr_range[1])

    # Save source location
    src_arm_loc = src_arm.location.copy()
    src_arm.location = [0, 0, 0]

    # Duplicate source armature to preserve animation
    _deselect_all_objects()
    set_active_object(src_arm.name)
    try:
        bpy.ops.object.mode_set(mode="OBJECT")
    except Exception:
        pass
    duplicate_object()
    src_arm_dupli = get_object(bpy.context.active_object.name)
    src_arm_dupli["mix_to_del"] = True

    """
    # Store bone matrices
    bpy.ops.object.mode_set(mode='OBJECT')
    bpy.ops.object.select_all(action='DESELECT')
    set_active_object(src_arm.name)
    bpy.ops.object.mode_set(mode='POSE')

    bones_data = []

    for f in range(fr_start, fr_end+1):
        print("Frame", f)
        scn.frame_set(f)
        bpy.context.view_layer.update()

        bones_matrices = {}

        for pbone in src_arm.pose.bones:
            bones_matrices[pbone.name] = pbone.matrix.copy()
            # bones_matrices[pbone.name] = src_arm.convert_space(
            #     pose_bone=pbone, matrix=pbone.matrix,
            #     from_space="POSE", to_space="LOCAL"
            # )


        bones_data.append((f, bones_matrices))
    """

    # Store target bones rest transforms
    _deselect_all_objects()
    set_active_object(tar_arm.name)
    try:
        bpy.ops.object.mode_set(mode="EDIT")
    except Exception:
        try:
            bpy.ops.object.mode_set(mode="OBJECT")
            bpy.ops.object.mode_set(mode="EDIT")
        except Exception:
            pass

    rest_bones = {}

    for ebone in tar_arm.data.edit_bones:
        rest_bones[ebone.name] = (
            ebone.head.copy(),
            ebone.tail.copy(),
            vec_roll_to_mat3(ebone.y_axis, ebone.roll),
        )

    # Apply target rest pose to the ORIGINAL src_arm (like 3.6 version)
    print("  Set rest pose...")
    _deselect_all_objects()
    set_active_object(src_arm.name)
    try:
        bpy.ops.object.mode_set(mode="EDIT")
    except Exception:
        try:
            bpy.ops.object.mode_set(mode="OBJECT")
            bpy.ops.object.mode_set(mode="EDIT")
        except Exception:
            pass

    for bname in rest_bones:
        ebone = src_arm.data.edit_bones.get(bname)

        if ebone is None:
            # print("Warning, bone not found on source armature:", bname)
            continue

        head, tail, mat3 = rest_bones[bname]
        ebone.head, ebone.tail, ebone.roll = (
            src_arm.matrix_world.inverted() @ head,
            src_arm.matrix_world.inverted() @ tail,
            mat3_to_vec_roll(src_arm.matrix_world.inverted().to_3x3() @ mat3),
        )

    # Add constraints to src_arm to follow duplicate's animation
    _deselect_all_objects()
    set_active_object(src_arm.name)
    try:
        bpy.ops.object.mode_set(mode="POSE")
    except Exception:
        try:
            bpy.ops.object.mode_set(mode="OBJECT")
            bpy.ops.object.mode_set(mode="POSE")
        except Exception:
            pass

    for pb in src_arm.pose.bones:
        cns = pb.constraints.new("COPY_TRANSFORMS")
        cns.name = "temp"
        cns.target = src_arm_dupli
        cns.subtarget = pb.name

    # Restore animation
    print("Restore animation...")
    bake_anim(
        frame_start=fr_start,
        frame_end=fr_end,
        only_selected=False,
        bake_bones=True,
        bake_object=False,
    )

    # Restore location
    src_arm.location = src_arm_loc

    # Delete temp constraints
    for pb in src_arm.pose.bones:
        if len(pb.constraints):
            cns = pb.constraints.get("temp")
            if cns:
                pb.constraints.remove(cns)

    # Delete the duplicate
    delete_object(src_arm_dupli)

    print("  Source armature rest pose redefined.")


def add_slight_bend(bone, axis, angle=0.01):
    # Convert degrees to radians
    angle_rad = math.radians(angle)

    # Create a rotation matrix for a slight rotation around the specified axis
    rot_mat = Matrix.Rotation(angle_rad, 4, axis)

    # Apply the rotation to the bone's matrix
    bone.matrix = bone.matrix @ rot_mat


def _import_anim(src_arm, tar_arm, import_only=False, rotation_output="QUATERNION"):
    print("\nImporting animation...")
    print(f"  Retarget rotation output: {rotation_output}")

    if src_arm.animation_data is None:
        print("  No action found on the source armature")
        return

    src_action_check = animation_compat.get_action_from_animdata(src_arm.animation_data)
    if src_action_check is None:
        print("  No action found on the source armature")
        return

    src_fcurves = animation_compat.get_action_fcurves(src_action_check)
    if len(src_fcurves) == 0:
        print("  No keyframes to import")
        return

    # CRITICAL FIX: Work on a duplicate, then reassign src_arm like 3.6 does
    _deselect_all_objects()
    set_active_object(src_arm.name)

    # Detect if source armature uses mixamorig: prefix
    use_name_prefix = False
    detected_prefix = ""
    for bone in src_arm.data.bones:
        if bone.name.startswith("mixamorig") and ":" in bone.name:
            use_name_prefix = True
            detected_prefix = bone.name.split(":")[0] + ":"
            print(f"  Detected Mixamo prefix: {detected_prefix}")
            break
    if not use_name_prefix:
        print("  No Mixamo prefix detected, using plain bone names")
    try:
        bpy.ops.object.mode_set(mode="OBJECT")
    except Exception:
        pass

    duplicate_object()
    src_arm_copy_name = src_arm.name + "_COPY"
    bpy.context.active_object.name = src_arm_copy_name

    # CRITICAL: Reassign src_arm to the copy, like 3.6 line 2465
    src_arm = get_object(src_arm_copy_name)
    src_arm["mix_to_del"] = True

    # Store the detected prefix on the source armature data
    # so get_mixamo_prefix() can find it
    # This is critical because get_mixamo_prefix() reads from active_object,
    # but we'll be
    # working with the target armature active when creating constraints
    src_arm.data["mixamo_prefix"] = detected_prefix

    # Helper function to construct source bone names with the correct prefix
    def get_src_bone_name(base_name):
        if use_name_prefix:
            return detected_prefix + base_name
        else:
            return base_name

    # Redefine source armature rest pose if importing only animation
    if import_only:
        redefine_source_rest_pose(src_arm, tar_arm)

    # Get anim data - AFTER redefine_source_rest_pose
    if src_arm.animation_data:
        action_src_anim_data = src_arm.animation_data
        action = animation_compat.get_action_from_animdata(action_src_anim_data)
    else:
        print("  ERROR: No animation data after rest pose redefine")
        return

    if action is None:
        print("  ERROR: No action found")
        return

    # Ensure proper slot assignment (4.4+)
    try:
        src_anim_data = src_arm.animation_data_create()
        animation_compat.assign_action_to_animdata(src_anim_data, action, src_arm)
    except Exception:
        pass

    frame_range = animation_compat.get_action_frame_range(action)
    fr_start = int(frame_range[0])
    fr_end = int(frame_range[1])

    # Ensure target is active for bone data collection
    _deselect_all_objects()
    set_active_object(tar_arm.name)
    try:
        bpy.ops.object.mode_set(mode="OBJECT")
        bpy.ops.object.mode_set(mode="POSE")
    except Exception:
        pass

    _refresh_control_rig_setup(tar_arm)

    arm_left_kinematic = _resolve_limb_kinematic_mode(
        tar_arm,
        c_prefix + arm_rig_names["hand_ik"] + "_Left",
        c_prefix + arm_rig_names["hand_fk"] + "_Left",
        "left arm",
    )
    arm_right_kinematic = _resolve_limb_kinematic_mode(
        tar_arm,
        c_prefix + arm_rig_names["hand_ik"] + "_Right",
        c_prefix + arm_rig_names["hand_fk"] + "_Right",
        "right arm",
    )
    leg_left_kinematic = _resolve_limb_kinematic_mode(
        tar_arm,
        c_prefix + leg_rig_names["foot_ik"] + "_Left",
        c_prefix + leg_rig_names["foot_fk"] + "_Left",
        "left leg",
    )
    leg_right_kinematic = _resolve_limb_kinematic_mode(
        tar_arm,
        c_prefix + leg_rig_names["foot_ik"] + "_Right",
        c_prefix + leg_rig_names["foot_fk"] + "_Right",
        "right leg",
    )

    # Set bones mapping for retargetting
    bones_map = {}

    kai_mapping_names = _kai_get_mapping_names_from_rig_data(tar_arm)
    hip_source_names = set()
    resolved_hip_source = _kai_add_resolved_source_mapping_if_target_exists(
        bones_map,
        src_arm,
        kai_mapping_names["hip"],
        detected_prefix,
        tar_arm,
        c_prefix + spine_rig_names["pelvis"],
        "Hip",
    )
    if resolved_hip_source:
        hip_source_names.add(resolved_hip_source)

    for pair in _kai_build_spine_control_pairs(
        kai_mapping_names["spines"],
        kai_mapping_names["chest"],
    ):
        _kai_add_resolved_source_mapping_if_target_exists(
            bones_map,
            src_arm,
            pair["raw_name"],
            detected_prefix,
            tar_arm,
            pair["control_name"],
            f"Spine/Chest {pair['raw_name']}",
        )
    for pair in _kai_build_spine_control_pairs(
        kai_mapping_names["necks"],
        None,
    ):
        _kai_add_mapping_if_target_exists(
            bones_map,
            get_src_bone_name(pair["raw_name"]),
            tar_arm,
            pair["control_name"],
        )
    _kai_add_mapping_if_target_exists(
        bones_map,
        get_src_bone_name(kai_mapping_names["head"]),
        tar_arm,
        c_prefix + head_rig_names["head"],
    )
    if _get_armature_pose_bone(tar_arm, c_prefix + "Shoulder_Left") is not None:
        bones_map[get_src_bone_name("LeftShoulder")] = c_prefix + "Shoulder_Left"
    if _get_armature_pose_bone(tar_arm, c_prefix + "Shoulder_Right") is not None:
        bones_map[get_src_bone_name("RightShoulder")] = c_prefix + "Shoulder_Right"

    # Arm
    if arm_left_kinematic == "FK":
        bones_map[get_src_bone_name("LeftArm")] = c_prefix + "Arm_FK_Left"
        bones_map[get_src_bone_name("LeftForeArm")] = c_prefix + "ForeArm_FK_Left"
        bones_map[get_src_bone_name("LeftHand")] = c_prefix + "Hand_FK_Left"
    elif arm_left_kinematic == "IK":
        bones_map[c_prefix + "Hand_IK_Left"] = c_prefix + "Hand_IK_Left"

    if arm_right_kinematic == "FK":
        bones_map[get_src_bone_name("RightArm")] = c_prefix + "Arm_FK_Right"
        bones_map[get_src_bone_name("RightForeArm")] = c_prefix + "ForeArm_FK_Right"
        bones_map[get_src_bone_name("RightHand")] = c_prefix + "Hand_FK_Right"
    elif arm_right_kinematic == "IK":
        bones_map[c_prefix + "Hand_IK_Right"] = c_prefix + "Hand_IK_Right"

    # Fingers
    bones_map[get_src_bone_name("LeftHandThumb1")] = c_prefix + "Thumb1_Left"
    bones_map[get_src_bone_name("LeftHandThumb2")] = c_prefix + "Thumb2_Left"
    bones_map[get_src_bone_name("LeftHandThumb3")] = c_prefix + "Thumb3_Left"
    bones_map[get_src_bone_name("LeftHandIndex1")] = c_prefix + "Index1_Left"
    bones_map[get_src_bone_name("LeftHandIndex2")] = c_prefix + "Index2_Left"
    bones_map[get_src_bone_name("LeftHandIndex3")] = c_prefix + "Index3_Left"
    bones_map[get_src_bone_name("LeftHandMiddle1")] = c_prefix + "Middle1_Left"
    bones_map[get_src_bone_name("LeftHandMiddle2")] = c_prefix + "Middle2_Left"
    bones_map[get_src_bone_name("LeftHandMiddle3")] = c_prefix + "Middle3_Left"
    bones_map[get_src_bone_name("LeftHandRing1")] = c_prefix + "Ring1_Left"
    bones_map[get_src_bone_name("LeftHandRing2")] = c_prefix + "Ring2_Left"
    bones_map[get_src_bone_name("LeftHandRing3")] = c_prefix + "Ring3_Left"
    bones_map[get_src_bone_name("LeftHandPinky1")] = c_prefix + "Pinky1_Left"
    bones_map[get_src_bone_name("LeftHandPinky2")] = c_prefix + "Pinky2_Left"
    bones_map[get_src_bone_name("LeftHandPinky3")] = c_prefix + "Pinky3_Left"
    bones_map[get_src_bone_name("RightHandThumb1")] = c_prefix + "Thumb1_Right"
    bones_map[get_src_bone_name("RightHandThumb2")] = c_prefix + "Thumb2_Right"
    bones_map[get_src_bone_name("RightHandThumb3")] = c_prefix + "Thumb3_Right"
    bones_map[get_src_bone_name("RightHandIndex1")] = c_prefix + "Index1_Right"
    bones_map[get_src_bone_name("RightHandIndex2")] = c_prefix + "Index2_Right"
    bones_map[get_src_bone_name("RightHandIndex3")] = c_prefix + "Index3_Right"
    bones_map[get_src_bone_name("RightHandMiddle1")] = c_prefix + "Middle1_Right"
    bones_map[get_src_bone_name("RightHandMiddle2")] = c_prefix + "Middle2_Right"
    bones_map[get_src_bone_name("RightHandMiddle3")] = c_prefix + "Middle3_Right"
    bones_map[get_src_bone_name("RightHandRing1")] = c_prefix + "Ring1_Right"
    bones_map[get_src_bone_name("RightHandRing2")] = c_prefix + "Ring2_Right"
    bones_map[get_src_bone_name("RightHandRing3")] = c_prefix + "Ring3_Right"
    bones_map[get_src_bone_name("RightHandPinky1")] = c_prefix + "Pinky1_Right"
    bones_map[get_src_bone_name("RightHandPinky2")] = c_prefix + "Pinky2_Right"
    bones_map[get_src_bone_name("RightHandPinky3")] = c_prefix + "Pinky3_Right"

    if leg_left_kinematic == "FK":
        bones_map[get_src_bone_name("LeftUpLeg")] = c_prefix + "UpLeg_FK_Left"
        bones_map[get_src_bone_name("LeftLeg")] = c_prefix + "Leg_FK_Left"
        bones_map[c_prefix + "Foot_FK_Left"] = c_prefix + "Foot_FK_Left"
        bones_map[get_src_bone_name("LeftToeBase")] = c_prefix + "Toe_FK_Left"
    elif leg_left_kinematic == "IK":
        bones_map[c_prefix + "Foot_IK_Left"] = c_prefix + "Foot_IK_Left"
        bones_map[get_src_bone_name("LeftToeBase")] = c_prefix + "Toe_IK_Left"

    if leg_right_kinematic == "FK":
        bones_map[get_src_bone_name("RightUpLeg")] = c_prefix + "UpLeg_FK_Right"
        bones_map[get_src_bone_name("RightLeg")] = c_prefix + "Leg_FK_Right"
        bones_map[c_prefix + "Foot_FK_Right"] = c_prefix + "Foot_FK_Right"
        bones_map[get_src_bone_name("RightToeBase")] = c_prefix + "Toe_FK_Right"
    elif leg_right_kinematic == "IK":
        bones_map[c_prefix + "Foot_IK_Right"] = c_prefix + "Foot_IK_Right"
        bones_map[get_src_bone_name("RightToeBase")] = c_prefix + "Toe_IK_Right"

    # Store bones data from target armature
    try:
        bpy.ops.object.mode_set(mode="EDIT")
    except Exception:
        pass

    ctrl_matrices = {}
    ik_bones_data = {}

    kinematics = {}

    if arm_left_kinematic is not None:
        kinematics["HandLeft"] = ["Hand", arm_left_kinematic, "Left"]
    if arm_right_kinematic is not None:
        kinematics["HandRight"] = ["Hand", arm_right_kinematic, "Right"]
    if leg_left_kinematic is not None:
        kinematics["FootLeft"] = ["Foot", leg_left_kinematic, "Left"]
    if leg_right_kinematic is not None:
        kinematics["FootRight"] = ["Foot", leg_right_kinematic, "Right"]

    for b in kinematics:
        type, kin_mode, side = kinematics[b]
        ctrl_name = c_prefix + type + "_" + kin_mode + "_" + side
        ctrl_ebone = tar_arm.data.edit_bones.get(ctrl_name)
        mix_bone_name = get_src_bone_name(side + type)

        if ctrl_ebone is None:
            print(f"  Warning: Missing target control bone {ctrl_name}; skipping")
            continue
        ctrl_matrices[ctrl_name] = ctrl_ebone.matrix.copy(), mix_bone_name

        # store corrected ik bones
        if kin_mode == "IK":
            ik_bones = {}
            ik_chain = []

            if type == "Foot":
                ik_chain = ["UpLeg_IK_" + side, "Leg_IK_" + side]
            elif type == "Hand":
                ik_chain = ["Arm_IK_" + side, "ForeArm_IK_" + side]

            ik1 = tar_arm.data.edit_bones.get(ik_chain[0])
            ik2 = tar_arm.data.edit_bones.get(ik_chain[1])

            if ik1 is None or ik2 is None:
                print(
                    "  Warning: Missing IK helper bones on target rig for "
                    f"{type} {side}; skipping IK helper setup"
                )
                continue

            ik_bones["ik1"] = ik1.name, ik1.head.copy(), ik1.tail.copy(), ik1.roll
            ik_bones["ik2"] = ik2.name, ik2.head.copy(), ik2.tail.copy(), ik2.roll
            ik_bones_data[b] = type, side, ik_bones

    # Init source armature rotation and scale
    _deselect_all_objects()
    set_active_object(src_arm.name)

    try:
        bpy.ops.object.mode_set(mode="OBJECT")
    except Exception:
        pass

    bpy.context.view_layer.update()

    scale_fac = src_arm.scale[0]
    print(f"  Source scale factor: {scale_fac}")

    try:
        bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
        bpy.context.evaluated_depsgraph_get().update()
    except Exception as e:
        print(f"  Warning: Could not apply transforms: {e}")

    # Get F-Curves and scale location keyframes
    action_fcurves = animation_compat.get_action_fcurves(action)
    print(f"  Scaling {len(action_fcurves)} fcurves")
    for fc in action_fcurves:
        dp = fc.data_path
        if dp.startswith("pose.bones") and dp.endswith(".location"):
            for k in fc.keyframe_points:
                k.co[1] *= scale_fac

    # CRITICAL: Re-establish src_arm as active in EDIT mode for helper bone creation
    _deselect_all_objects()
    set_active_object(src_arm.name)
    bpy.context.view_layer.update()

    try:
        bpy.ops.object.mode_set(mode="EDIT")
    except Exception as e:
        print(f"  ERROR: Could not switch to EDIT mode: {e}")
        try:
            bpy.ops.object.mode_set(mode="OBJECT")
            bpy.ops.object.mode_set(mode="EDIT")
        except Exception as e2:
            print(f"  CRITICAL: Mode switch failed: {e2}")
            return

    print(f"  Creating helper bones on {src_arm.name}")

    # Add helper source bones
    # add feet/hand bones helpers
    for name in ctrl_matrices:
        foot_ebone = create_edit_bone(name)
        foot_ebone.head, foot_ebone.tail = [0, 0, 0], [0, 0, 0.1]
        foot_ebone.matrix = ctrl_matrices[name][0]
        parent_bone = get_edit_bone(ctrl_matrices[name][1])
        if parent_bone is None:
            print(
                "    Warning: Helper parent bone not found: "
                f"{ctrl_matrices[name][1]}"
            )
        else:
            foot_ebone.parent = parent_bone
        print(f"    Created helper bone: {name}")

    # add IK bones helpers
    for b in ik_bones_data:
        type, side, ik_bones = ik_bones_data[b]
        for bone_type in ik_bones:
            bname, bhead, btail, broll = ik_bones[bone_type]
            ebone = create_edit_bone(bname)
            ebone.head, ebone.tail, ebone.roll = bhead, btail, broll
            print(f"    Created IK helper bone: {bname}")

    # set constraints in POSE mode
    try:
        bpy.ops.object.mode_set(mode="POSE")
    except Exception:
        pass

    bake_ik_data = {"src_arm": src_arm}

    for b in ik_bones_data:
        type, side, ik_bones = ik_bones_data[b]
        b1_name = ik_bones["ik1"][0]
        b2_name = ik_bones["ik2"][0]
        b1_pb = _get_armature_pose_bone(src_arm, b1_name)
        b2_pb = _get_armature_pose_bone(src_arm, b2_name)

        chain = []
        if type == "Foot":
            chain = [
                get_src_bone_name(side + "UpLeg"),
                get_src_bone_name(side + "Leg"),
            ]
            bake_ik_data["Leg" + side] = chain

        elif type == "Hand":
            chain = [
                get_src_bone_name(side + "Arm"),
                get_src_bone_name(side + "ForeArm"),
            ]
            bake_ik_data["Arm" + side] = chain

        if b1_pb is None or b2_pb is None:
            print(
                "  Warning: Missing source IK helper pose bones for "
                f"{type} {side}; skipping IK bake helpers"
            )
            continue

        cns = b1_pb.constraints.new("COPY_TRANSFORMS")
        cns.name = "Copy Transforms"
        cns.target = src_arm
        cns.subtarget = chain[0]

        cns = b2_pb.constraints.new("COPY_TRANSFORMS")
        cns.name = "Copy Transforms"
        cns.target = src_arm
        cns.subtarget = chain[1]

    # Retarget - Method 2: Constrained retargetting
    _deselect_all_objects()
    set_active_object(tar_arm.name)

    try:
        bpy.ops.object.mode_set(mode="OBJECT")
        bpy.ops.object.mode_set(mode="POSE")
    except Exception as e:
        print(f"  ERROR switching to POSE: {e}")
        return

    bpy.ops.pose.select_all(action="DESELECT")
    bpy.context.view_layer.update()

    print("  Adding retarget constraints...")

    # add constraints
    for src_name in bones_map:
        tar_name = bones_map[src_name]
        src_bone = src_arm.pose.bones.get(src_name)
        tar_bone = tar_arm.pose.bones.get(tar_name)

        if src_bone is None:
            print(f"    SKIP: Source bone not found: {src_name}")
            continue
        if tar_bone is None:
            print(f"    SKIP: Target bone not found: {tar_name}")
            continue

        # All bones get COPY_ROTATION first
        cns_name = "Copy Rotation_retarget"
        cns = tar_bone.constraints.new("COPY_ROTATION")
        cns.name = cns_name
        cns.target = src_arm
        cns.subtarget = src_name

        # Hips gets COPY_LOCATION in LOCAL space
        if src_name in hip_source_names:
            cns_name = "Copy Location_retarget"
            cns = tar_bone.constraints.new("COPY_LOCATION")
            cns.name = cns_name
            cns.target = src_arm
            cns.subtarget = src_name
            cns.owner_space = cns.target_space = "LOCAL"
            print(f"    Added Hips constraints: {src_name} -> {tar_name}")

        # Foot IK, Hand IK get COPY_LOCATION in POSE space
        if (
            (leg_left_kinematic == "IK" and "Foot_IK_Left" in src_name)
            or (leg_right_kinematic == "IK" and "Foot_IK_Right" in src_name)
            or (arm_left_kinematic == "IK" and "Hand_IK_Left" in src_name)
            or (arm_right_kinematic == "IK" and "Hand_IK_Right" in src_name)
        ):
            cns_name = "Copy Location_retarget"
            cns = tar_bone.constraints.new("COPY_LOCATION")
            cns.name = cns_name
            cns.target = src_arm
            cns.subtarget = src_name
            cns.target_space = cns.owner_space = "POSE"
            print(f"    Added IK constraints: {src_name} -> {tar_name}")

            # select IK poles
            _side = "_Left" if "Left" in src_name else "_Right"
            ik_pole_name = ""
            if "Hand" in src_name:
                ik_pole_name = c_prefix + arm_rig_names["pole_ik"] + _side
            elif "Foot" in src_name:
                ik_pole_name = c_prefix + leg_rig_names["pole_ik"] + _side

            ik_pole_ctrl = _get_armature_pose_bone(tar_arm, ik_pole_name)
            if ik_pole_ctrl is not None:
                tar_arm.data.bones.active = ik_pole_ctrl.bone
                set_pose_bone_selected(ik_pole_ctrl, True)
            else:
                print(f"    Warning: IK pole control not found: {ik_pole_name}")

        # select
        tar_arm.data.bones.active = tar_bone.bone
        set_pose_bone_selected(tar_bone, True)

    bpy.context.view_layer.update()

    # bake
    print(f"  Baking animation frames {fr_start} to {fr_end}...")
    bake_anim(
        frame_start=fr_start,
        frame_end=fr_end,
        only_selected=True,
        bake_bones=True,
        bake_object=False,
        ik_data=bake_ik_data,
        rotation_output=rotation_output,
    )

    # Cleanup
    try:
        _deselect_all_objects()
        set_active_object(tar_arm.name)
        bpy.ops.object.mode_set(mode="OBJECT")
    except Exception:
        pass

    print("Animation imported.")

    # Ensure target has proper action slot (4.4+)
    try:
        if tar_arm.animation_data and tar_arm.animation_data.action:
            animation_compat.assign_action_to_animdata(
                tar_arm.animation_data, tar_arm.animation_data.action, tar_arm
            )
    except Exception:
        pass


def remove_retarget_cns(armature):
    # print("Removing constraints...")
    for pb in armature.pose.bones:
        if len(pb.constraints):
            for cns in pb.constraints:
                if cns.name.endswith("_retarget") or cns.name == "temp":
                    pb.constraints.remove(cns)


def remove_temp_objects():
    for obj in bpy.data.objects:
        if "mix_to_del" in obj.keys():
            delete_object(obj)


def remove_temp_actions():
    for action in list(bpy.data.actions):
        try:
            lower_name = (getattr(action, "name", "") or "").lower()
            if "|mixamo.com|layer" not in lower_name and "|layer0" not in lower_name:
                continue
            try:
                action.use_fake_user = False
            except Exception:
                pass
            if getattr(action, "users", 0) != 0:
                continue
            bpy.data.actions.remove(action)
        except Exception:
            continue


def update_mixamo_tab():
    try:
        bpy.utils.unregister_class(MR_PT_MenuMain)
        bpy.utils.unregister_class(MR_PT_MenuRig)
        bpy.utils.unregister_class(MR_PT_MenuAnim)
        bpy.utils.unregister_class(MR_PT_MenuExport)
        bpy.utils.unregister_class(MR_PT_MenuUpdate)
    except Exception:
        pass

    MixamoRigPanel.bl_category = bpy.context.preferences.addons[
        __package__
    ].preferences.mixamo_tab_name
    bpy.utils.register_class(MR_PT_MenuMain)
    bpy.utils.register_class(MR_PT_MenuRig)
    bpy.utils.register_class(MR_PT_MenuAnim)
    bpy.utils.register_class(MR_PT_MenuExport)
    bpy.utils.register_class(MR_PT_MenuUpdate)


###########  UI PANELS  ###################
class MixamoRigPanel:
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "MixamoKai"


class MR_PT_MenuMain(Panel, MixamoRigPanel):  # noqa: N801
    bl_label = "Mixamo Control Rig"

    def draw(self, context):
        layt = self.layout
        layt.use_property_split = True
        layt.use_property_decorate = False

        # col = layt.column(align=True)
        # col.scale_y = 1.3
        # col.prop_search(scn, "mix_source_armature", scn, "objects", text="Skeleton")
        arm_name = "None"

        if context.active_object is not None:
            if context.active_object.type == "ARMATURE":
                arm_name = context.active_object.name

        layt.label(text="Character: " + arm_name)


class MR_PT_MenuRig(Panel, MixamoRigPanel):  # noqa: N801
    bl_label = "Control Rig"
    bl_parent_id = "MR_PT_MenuMain"

    def draw(self, context):
        layt = self.layout
        layt.use_property_split = True
        layt.use_property_decorate = False

        """
        has_rigged = False
        if obj:
            if obj.type == "ARMATURE":
                if len(obj.data.keys()):
                    if "mr_data" in obj.data.keys():
                        has_rigged = True
        """

        col = layt.column(align=True)
        col.scale_y = 1.3

        col.prop(context.scene, "mr_reference_template", text="Template")
        op = col.operator(
            MR_OT_create_reference_skeleton.bl_idname,
            text="Create Reference Skeleton",
        )
        op.template_key = context.scene.mr_reference_template
        col.operator(MR_OT_make_rig.bl_idname, text="Generate Rig")
        col.operator(MR_OT_rebuild_rig.bl_idname, text="Rebuild Rig")
        col.operator(MR_OT_zero_out.bl_idname, text="Zero Out Rig")

        col = layt.column(align=True)
        col.separator()

        if context.mode != "EDIT_MESH":
            col.operator(MR_OT_edit_custom_shape.bl_idname, text="Edit Control Shape")
            col.operator(MR_OT_reset_generated_rig.bl_idname, text="Reset Generated Rig")
            col.operator(MR_OT_reconnect_rig.bl_idname, text="Reconnect Rig")
        else:
            col.operator(MR_OT_apply_shape.bl_idname, text="Apply Control Shape")


class MR_PT_MenuAnim(Panel, MixamoRigPanel):  # noqa: N801
    bl_label = "Animation"
    bl_parent_id = "MR_PT_MenuMain"

    def draw(self, context):
        layt = self.layout
        layt.use_property_split = True
        layt.use_property_decorate = False  # No animation.
        scn = context.scene
        layt.use_property_split = True
        layt.use_property_decorate = False

        col = layt.column(align=True)
        col.scale_y = 1
        # col.prop_search(
        #     scn, "mix_target_armature", scn, "objects", text="Control Rig"
        # )
        col.label(text="Source Skeleton:")
        col.prop_search(scn, "mix_source_armature", scn, "objects", text="")
        col.prop(scn, "mr_retarget_rotation_output", text="Rotation Output")
        col.separator()

        col = layt.column(align=True)
        col.scale_y = 1.3
        col.operator(MR_OT_import_anim.bl_idname, text="Apply Animation to Control Rig")

        col = layt.column(align=True)
        col.scale_y = 1.3
        col.operator(MR_OT_bake_anim.bl_idname, text="Bake Animation")


class MR_PT_MenuUpdate(Panel, MixamoRigPanel):  # noqa: N801
    bl_label = "Update"
    bl_parent_id = "MR_PT_MenuMain"

    def draw(self, context):
        layt = self.layout
        layt.operator(MR_OT_update.bl_idname, text="Update Control Rig")
        if _control_rig_needs_fk_foot_fix(context.active_object):
            col = layt.column(align=True)
            col.alert = True
            col.operator(MR_OT_fix_fk_foot_setup.bl_idname, text="Fix FK Foot Setup")


class MR_PT_MenuExport(Panel, MixamoRigPanel):  # noqa: N801
    bl_label = "Export"
    bl_parent_id = "MR_PT_MenuMain"

    def draw(self, context):
        layt = self.layout
        layt.operator(
            "export_scene.gltf", text="GLTF Export..."
        )  # MR_OT_exportGLTF.bl_idname


###########  REGISTER  ##################
classes = (
    MR_PT_MenuMain,
    MR_PT_MenuRig,
    MR_PT_MenuAnim,
    MR_PT_MenuExport,
    MR_PT_MenuUpdate,
    MR_OT_create_reference_skeleton,
    MR_OT_make_rig,
    MR_OT_reset_generated_rig,
    MR_OT_rebuild_rig,
    MR_OT_zero_out,
    MR_OT_bake_anim,
    MR_OT_import_anim,
    MR_OT_reconnect_rig,
    MR_OT_fix_fk_foot_setup,
    MR_OT_edit_custom_shape,
    MR_OT_apply_shape,
    MR_OT_exportGLTF,
    MR_OT_update,
)


def register():
    from bpy.utils import register_class

    for cls in classes:
        register_class(cls)

    update_mixamo_tab()

    bpy.types.Scene.mix_source_armature = bpy.props.PointerProperty(
        type=bpy.types.Object
    )
    bpy.types.Scene.mix_target_armature = bpy.props.PointerProperty(
        type=bpy.types.Object
    )
    bpy.types.Scene.mr_retarget_rotation_output = bpy.props.EnumProperty(
        name="Retarget Rotation Output",
        description="Rotation channel type used when baking retargeted animation",
        items=RETARGET_ROTATION_OUTPUT_ITEMS,
        default="QUATERNION",
    )

    bpy.types.Scene.mr_reference_template = bpy.props.EnumProperty(
        name="Reference Template",
        items=KAI_REFERENCE_TEMPLATE_ITEMS,
        default=DEFAULT_REFERENCE_TEMPLATE,
    )


def unregister():
    from bpy.utils import unregister_class

    for cls in reversed(classes):
        unregister_class(cls)

    del bpy.types.Scene.mix_source_armature
    del bpy.types.Scene.mix_target_armature
    del bpy.types.Scene.mr_retarget_rotation_output
    del bpy.types.Scene.mr_reference_template


if __name__ == "__main__":
    register()
