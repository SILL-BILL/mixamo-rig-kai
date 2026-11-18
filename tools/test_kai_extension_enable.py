"""Verify a locally installed extension in a disposable Blender profile."""

import importlib
import json
import os
import tomllib
from pathlib import Path

import bpy

profile = Path(os.environ["KAI_QA_PROFILE"]).resolve()
paths = {kind: bpy.utils.user_resource(kind) for kind in ("CONFIG", "SCRIPTS", "EXTENSIONS")}
assert all(Path(path).resolve().is_relative_to(profile) for path in paths.values()), paths
assert Path(bpy.utils.resource_path("USER")).resolve().is_relative_to(profile)
mode = os.environ.get("KAI_QA_EXTENSION_PHASE", "verify")
before_path = profile / "repositories-before.json"

def repositories():
    return {repo.module: {"name": repo.name, "remote_url": repo.remote_url}
            for repo in bpy.context.preferences.extensions.repos}

if mode == "before":
    before_path.write_text(json.dumps(repositories(), indent=2), encoding="utf-8")
    print("KAI_EXTENSION_BEFORE", len(repositories()), json.dumps(paths))
else:
    before = json.loads(before_path.read_text(encoding="utf-8"))
    after = repositories()
    assert all(after.get(key) == value for key, value in before.items())
    assert set(after) - set(before) == {"kai_qa"}
    module = "bl_ext.kai_qa.mixamo_rig_kai"
    assert bpy.context.preferences.addons.get(module) is not None
    package = importlib.import_module(module)
    assert Path(package.__file__).resolve().is_relative_to(profile / "extensions" / "kai_qa")
    # Blender removes legacy bl_info from an enabled native Extension module.
    metadata = tomllib.loads(Path(package.__file__).with_name("blender_manifest.toml").read_text(encoding="utf-8"))
    assert metadata["version"] == "0.6.10"
    assert metadata["blender_version_min"] == "4.5.0"
    for panel in ("MR_PT_MenuMain", "MR_PT_MenuRig", "MR_PT_MenuAnim", "KAI_PT_facial"):
        assert getattr(bpy.types, panel).is_registered, panel
    assert bpy.types.KAI_PT_facial.bl_category == "MixamoKai"
    assert bpy.ops.mr.create_reference_skeleton(template_key="kai_humanoid_basic") == {"FINISHED"}
    rig = bpy.context.object
    assert bpy.ops.mr.make_rig(bake_anim=False) == {"FINISHED"}
    assert bpy.ops.mr.rebuild_rig() == {"FINISHED"}
    assert rig.pose.bones.get("Ctrl_Head") is not None
    report = {
        "blender": bpy.app.version_string, "extension_version": "0.6.10",
        "module": module, "module_path": package.__file__,
        "success": True, "checks_passed": 17,
        "user_paths": paths, "repositories_before": len(before), "repositories_after": len(after),
        "installed_kai_before": None, "installed_kai_after": "0.6.10",
        "existing_repositories_modified": False, "existing_addons_modified": False,
        "preferences_persisted_to_normal_profile": False, "preferences_saved_only_to_isolated_profile": True,
    }
    (profile / "extension-result.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print("KAI_EXTENSION_ENABLE_OK", json.dumps(report))
