"""Extract a Kai reference armature template from a .blend file.

Run with Blender:
blender --background Kai_Humanoid_Reference.blend --python tools/extract_kai_reference_template.py -- --output kai_reference_template.py
"""

import argparse
import json
import sys
from pathlib import Path

import bpy


def _parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--template-key", default="kai_humanoid_basic")
    parser.add_argument("--template-label", default="Humanoid Basic")
    parser.add_argument("--template-name", default="Kai_Humanoid_Basic")
    parser.add_argument("--armature", default="")
    args = sys.argv
    if "--" in args:
        args = args[args.index("--") + 1 :]
    else:
        args = []
    return parser.parse_args(args)


def _find_armature(armature_name):
    if armature_name:
        obj = bpy.data.objects.get(armature_name)
        if obj is None or obj.type != "ARMATURE":
            raise RuntimeError(f"Armature not found: {armature_name}")
        return obj

    armatures = [obj for obj in bpy.data.objects if obj.type == "ARMATURE"]
    if len(armatures) != 1:
        names = ", ".join(obj.name for obj in armatures) or "none"
        raise RuntimeError(
            "Expected exactly one armature, or pass --armature. "
            f"Found: {names}"
        )
    return armatures[0]


def _sorted_edit_bones(edit_bones):
    remaining = list(edit_bones)
    result = []
    emitted = set()

    while remaining:
        progressed = False
        for bone in list(remaining):
            parent = bone.parent
            if parent is None or parent.name in emitted:
                result.append(bone)
                emitted.add(bone.name)
                remaining.remove(bone)
                progressed = True
        if not progressed:
            raise RuntimeError("Could not sort bones by parent relationship")

    return result


def _round_vec(vec):
    return [round(float(value), 10) for value in vec]


def _extract_template(armature, template_label, template_name):
    bpy.ops.object.mode_set(mode="OBJECT")
    bpy.ops.object.select_all(action="DESELECT")
    armature.select_set(True)
    bpy.context.view_layer.objects.active = armature
    bpy.ops.object.mode_set(mode="EDIT")

    bones = []
    for bone in _sorted_edit_bones(armature.data.edit_bones):
        bones.append(
            {
                "name": bone.name,
                "head": _round_vec(bone.head),
                "tail": _round_vec(bone.tail),
                "roll": round(float(bone.roll), 10),
                "parent": bone.parent.name if bone.parent else None,
                "connected": bool(bone.use_connect),
            }
        )

    bpy.ops.object.mode_set(mode="OBJECT")

    return {
        "label": template_label,
        "name": template_name,
        "source_armature": armature.name,
        "bones": bones,
    }


def _format_template_module(template_key, template):
    text = (
        '"""Reference skeleton templates for Mixamo Rig Kai.\n\n'
        "Generated from the source .blend by tools/extract_kai_reference_template.py.\n"
        '"""\n\n'
        f"DEFAULT_REFERENCE_TEMPLATE = {template_key!r}\n\n"
        "KAI_REFERENCE_TEMPLATES = "
        + json.dumps({template_key: template}, indent=4, ensure_ascii=True)
        .replace("true", "True")
        .replace("false", "False")
        .replace("null", "None")
        + "\n"
    )
    return text


def _write_template_module(output_path, template_key, template):
    text = _format_template_module(template_key, template)
    if output_path == "-":
        print("KAI_TEMPLATE_MODULE_BEGIN")
        print(text)
        print("KAI_TEMPLATE_MODULE_END")
        return

    Path(output_path).write_text(text, encoding="utf-8")


def main():
    args = _parse_args()
    armature = _find_armature(args.armature)
    template = _extract_template(armature, args.template_label, args.template_name)
    _write_template_module(args.output, args.template_key, template)
    print(
        f"Extracted {len(template['bones'])} bones from {armature.name} "
        f"to {args.output}"
    )


if __name__ == "__main__":
    main()
