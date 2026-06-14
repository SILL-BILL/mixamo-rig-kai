"""Validate bundled Kai reference skeleton templates in Blender."""

import importlib
import sys
import types
from pathlib import Path


def main():
    repo_root = Path(__file__).resolve().parents[1]
    package_name = "mixamo_rig_kai"

    if package_name not in sys.modules:
        package = types.ModuleType(package_name)
        package.__path__ = [str(repo_root)]
        sys.modules[package_name] = package

    mixamo_rig = importlib.import_module(f"{package_name}.mixamo_rig")
    print("items:", mixamo_rig.KAI_REFERENCE_TEMPLATE_ITEMS)

    failed = []
    for key, template in mixamo_rig.KAI_REFERENCE_TEMPLATES.items():
        armature = mixamo_rig._kai_create_reference_skeleton_from_template(template)
        errors = mixamo_rig._kai_validate_reference_skeleton(armature, template)
        print(key, armature.name, len(template["bones"]), errors)
        failed.extend(errors)

    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    main()
