"""Export a read-only inventory of facial rig data from the open Blender file."""

import json
import os
import sys

import bpy


TARGET_COLLECTIONS = {"CTRL_Eye", "Eye", "CTRL_Face", "FaceCtrlRigRoot"}


def simple(value):
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    try:
        return list(value)
    except (TypeError, ValueError):
        return str(value)


def custom_properties(owner):
    result = {}
    try:
        keys = owner.keys()
    except TypeError:
        return result
    for key in keys:
        if key != "_RNA_UI":
            result[key] = simple(owner[key])
    return result


def collection_names(bone):
    return sorted(collection.name for collection in getattr(bone, "collections", []))


def constraint_info(constraint):
    fields = {
        "name": constraint.name,
        "type": constraint.type,
        "influence": constraint.influence,
        "mute": constraint.mute,
    }
    for attr in (
        "target", "subtarget", "owner_space", "target_space", "mix_mode",
        "use_x", "use_y", "use_z", "invert_x", "invert_y", "invert_z",
        "map_from", "map_to", "from_min_x", "from_max_x", "from_min_y",
        "from_max_y", "from_min_z", "from_max_z", "to_min_x", "to_max_x",
        "to_min_y", "to_max_y", "to_min_z", "to_max_z", "use_min_x",
        "use_max_x", "use_min_y", "use_max_y", "use_min_z", "use_max_z",
        "min_x", "max_x", "min_y", "max_y", "min_z", "max_z",
        "track_axis", "up_axis", "head_tail", "use_offset", "use_transform_limit",
    ):
        if hasattr(constraint, attr):
            value = getattr(constraint, attr)
            fields[attr] = value.name if hasattr(value, "name") else simple(value)
    return fields


def driver_info(id_owner, fcurve):
    driver = fcurve.driver
    variables = []
    for variable in driver.variables:
        targets = []
        for target in variable.targets:
            targets.append({
                "id": getattr(getattr(target, "id", None), "name", None),
                "id_type": getattr(target, "id_type", None),
                "data_path": getattr(target, "data_path", ""),
                "bone_target": getattr(target, "bone_target", ""),
                "transform_type": getattr(target, "transform_type", ""),
                "transform_space": getattr(target, "transform_space", ""),
                "rotation_mode": getattr(target, "rotation_mode", ""),
            })
        variables.append({"name": variable.name, "type": variable.type, "targets": targets})
    modifiers = []
    for modifier in fcurve.modifiers:
        entry = {"type": modifier.type}
        for attr in ("use_restricted_range", "frame_start", "frame_end", "blend_in", "blend_out", "mode", "function_type"):
            if hasattr(modifier, attr):
                entry[attr] = simple(getattr(modifier, attr))
        modifiers.append(entry)
    return {
        "owner": id_owner.name,
        "owner_type": type(id_owner).__name__,
        "data_path": fcurve.data_path,
        "array_index": fcurve.array_index,
        "driver_type": driver.type,
        "expression": driver.expression,
        "use_self": driver.use_self,
        "variables": variables,
        "modifiers": modifiers,
    }


def drivers_for(owner):
    animation_data = getattr(owner, "animation_data", None)
    if not animation_data:
        return []
    return [driver_info(owner, fcurve) for fcurve in animation_data.drivers]


def main(output_path):
    result = {
        "file": bpy.data.filepath,
        "blender_version": bpy.app.version_string,
        "scenes": [scene.name for scene in bpy.data.scenes],
        "scene_collections": {},
        "armatures": [],
        "meshes": [],
        "other_drivers": [],
        "actions": [],
        "animation_bindings": [],
    }

    for action in bpy.data.actions:
        item = {
            "name": action.name,
            "frame_range": list(action.frame_range),
            "is_action_layered": getattr(action, "is_action_layered", False),
            "slots": [getattr(slot, "identifier", str(slot)) for slot in getattr(action, "slots", [])],
            "legacy_fcurves": [],
            "layered_fcurves": [],
        }
        for fcurve in getattr(action, "fcurves", []):
            item["legacy_fcurves"].append({
                "data_path": fcurve.data_path,
                "array_index": fcurve.array_index,
                "keyframes": len(fcurve.keyframe_points),
            })
        for layer in getattr(action, "layers", []):
            for strip in layer.strips:
                channelbag_method = getattr(strip, "channelbag", None)
                if channelbag_method is None:
                    continue
                for slot in getattr(action, "slots", []):
                    channelbag = channelbag_method(slot, ensure=False)
                    if channelbag is None:
                        continue
                    for fcurve in channelbag.fcurves:
                        item["layered_fcurves"].append({
                            "slot": slot.identifier,
                            "data_path": fcurve.data_path,
                            "array_index": fcurve.array_index,
                            "keyframes": len(fcurve.keyframe_points),
                        })
        result["actions"].append(item)

    for groups in (bpy.data.objects, bpy.data.shape_keys):
        for owner in groups:
            animation_data = getattr(owner, "animation_data", None)
            if not animation_data:
                continue
            binding = {
                "owner": owner.name,
                "action": getattr(animation_data.action, "name", None),
                "nla_tracks": [],
            }
            for track in animation_data.nla_tracks:
                binding["nla_tracks"].append({
                    "name": track.name,
                    "mute": track.mute,
                    "strips": [
                        {"name": strip.name, "action": getattr(strip.action, "name", None)}
                        for strip in track.strips
                    ],
                })
            result["animation_bindings"].append(binding)

    for collection in bpy.data.collections:
        result["scene_collections"][collection.name] = {
            "objects": sorted(obj.name for obj in collection.objects),
            "children": sorted(child.name for child in collection.children),
        }

    seen_driver_owners = set()
    for obj in bpy.data.objects:
        if obj.type == "ARMATURE":
            arm = {
                "object": obj.name,
                "data": obj.data.name,
                "parent": getattr(obj.parent, "name", None),
                "object_collections": sorted(c.name for c in obj.users_collection),
                "bone_collections": [],
                "bones": [],
                "object_properties": custom_properties(obj),
                "data_properties": custom_properties(obj.data),
                "drivers": drivers_for(obj) + drivers_for(obj.data),
            }
            seen_driver_owners.update((obj, obj.data))
            for collection in obj.data.collections:
                arm["bone_collections"].append({
                    "name": collection.name,
                    "is_visible": collection.is_visible,
                    "is_solo": collection.is_solo,
                    "bones": sorted(bone.name for bone in collection.bones),
                    "properties": custom_properties(collection),
                })
            for bone in obj.data.bones:
                pose = obj.pose.bones.get(bone.name)
                arm["bones"].append({
                    "name": bone.name,
                    "collections": collection_names(bone),
                    "parent": getattr(bone.parent, "name", None),
                    "children": sorted(child.name for child in bone.children),
                    "use_connect": bone.use_connect,
                    "inherit_scale": bone.inherit_scale,
                    "use_inherit_rotation": bone.use_inherit_rotation,
                    "use_local_location": bone.use_local_location,
                    "hide": bone.hide,
                    "hide_select": bone.hide_select,
                    "deform": bone.use_deform,
                    "head_local": list(bone.head_local),
                    "tail_local": list(bone.tail_local),
                    "roll": bone.matrix_local.to_euler().z,
                    "bone_properties": custom_properties(bone),
                    "pose": None if pose is None else {
                        "rotation_mode": pose.rotation_mode,
                        "lock_location": list(pose.lock_location),
                        "lock_rotation": list(pose.lock_rotation),
                        "lock_rotation_w": pose.lock_rotation_w,
                        "lock_scale": list(pose.lock_scale),
                        "custom_shape": getattr(pose.custom_shape, "name", None),
                        "custom_shape_transform": getattr(pose.custom_shape_transform, "name", None),
                        "custom_shape_translation": list(pose.custom_shape_translation),
                        "custom_shape_rotation_euler": list(pose.custom_shape_rotation_euler),
                        "custom_shape_scale_xyz": list(pose.custom_shape_scale_xyz),
                        "properties": custom_properties(pose),
                        "constraints": [constraint_info(c) for c in pose.constraints],
                    },
                })
            result["armatures"].append(arm)

        if obj.type == "MESH":
            shape_keys = obj.data.shape_keys
            mesh = {
                "object": obj.name,
                "data": obj.data.name,
                "parent": getattr(obj.parent, "name", None),
                "parent_bone": obj.parent_bone,
                "object_collections": sorted(c.name for c in obj.users_collection),
                "armature_modifiers": [
                    {"name": m.name, "object": getattr(m.object, "name", None)}
                    for m in obj.modifiers if m.type == "ARMATURE"
                ],
                "shape_keys": [],
                "drivers": [],
            }
            if shape_keys:
                mesh["shape_keys"] = [
                    {
                        "name": key.name,
                        "value": key.value,
                        "slider_min": key.slider_min,
                        "slider_max": key.slider_max,
                        "mute": key.mute,
                        "vertex_group": key.vertex_group,
                        "relative_key": getattr(key.relative_key, "name", None),
                        "properties": custom_properties(key),
                    }
                    for key in shape_keys.key_blocks
                ]
                mesh["drivers"] = drivers_for(shape_keys)
                seen_driver_owners.add(shape_keys)
            result["meshes"].append(mesh)

    for group in (bpy.data.objects, bpy.data.meshes, bpy.data.curves, bpy.data.materials, bpy.data.node_groups):
        for owner in group:
            if owner in seen_driver_owners:
                continue
            owner_drivers = drivers_for(owner)
            if owner_drivers:
                result["other_drivers"].extend(owner_drivers)

    result["target_collection_presence"] = {
        name: {
            "scene_collection": name in bpy.data.collections,
            "armatures": [
                arm["object"] for arm in result["armatures"]
                if any(collection["name"] == name for collection in arm["bone_collections"])
            ],
        }
        for name in sorted(TARGET_COLLECTIONS)
    }
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as handle:
        json.dump(result, handle, ensure_ascii=False, indent=2)
    print("FACIAL_INVENTORY=" + output_path)


if __name__ == "__main__":
    args = sys.argv[sys.argv.index("--") + 1:]
    main(args[0])
