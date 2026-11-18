"""Run a Facial test script only after verifying disposable user paths.

Set KAI_QA_PROFILE, BLENDER_USER_RESOURCES, BLENDER_USER_CONFIG, BLENDER_USER_SCRIPTS,
BLENDER_USER_EXTENSIONS and KAI_QA_SCRIPT in the launching process.
Use Blender --background --factory-startup --python-exit-code 1 --python <this>.
"""

import hashlib
import json
import os
import tomllib
from pathlib import Path

import bpy


profile = Path(os.environ["KAI_QA_PROFILE"]).resolve()
paths = {kind: bpy.utils.user_resource(kind) for kind in ("CONFIG", "SCRIPTS", "EXTENSIONS")}
assert all(Path(path).resolve().is_relative_to(profile) for path in paths.values()), paths
assert all(Path(path).is_dir() for path in paths.values()), paths
user_root = Path(bpy.utils.resource_path("USER")).resolve()
assert user_root.is_relative_to(profile), user_root
normal_root = Path(os.environ["APPDATA"]) / "Blender Foundation" / "Blender"
assert not profile.is_relative_to(normal_root.resolve()), profile
script = Path(os.environ["KAI_QA_SCRIPT"]).resolve()
source = script.read_text(encoding="utf-8")
source = source.replace(
    "def assert_true(value, message):\n",
    "ASSERTIONS_PASSED = 0\ndef assert_true(value, message):\n"
    "    global ASSERTIONS_PASSED\n    if value:\n        ASSERTIONS_PASSED += 1\n",
)
repositories_before = len(bpy.context.preferences.extensions.repos)
namespace = {"__file__": str(script), "__name__": "__main__"}
report = {
    "blender": bpy.app.version_string,
    "version_cycle": bpy.app.version_cycle,
    "script": str(script),
    "script_sha256": hashlib.sha256(script.read_bytes()).hexdigest(),
    "runtime_sha256": hashlib.sha256((script.parent.parent / "kai_facial.py").read_bytes()).hexdigest(),
    "extension_version": tomllib.loads((script.parent.parent / "blender_manifest.toml").read_text(encoding="utf-8"))["version"],
    "source_sha256": {
        name: hashlib.sha256((script.parent.parent / name).read_bytes()).hexdigest()
        for name in ("__init__.py", "blender_manifest.toml", "mixamo_rig.py", "kai_facial.py")
    },
    "user_paths": paths,
    "user_resource_root": str(user_root),
    "repositories_before": repositories_before,
    "installed_kai_before": None,
    "disposable": True,
    "normal_profile_modified": False,
    "preferences_saved": False,
    "success": False,
}
print("ISOLATED_ENVIRONMENT", json.dumps(report))
try:
    exec(compile(source, str(script), "exec"), namespace)
    report["success"] = True
finally:
    report["repositories_after"] = len(bpy.context.preferences.extensions.repos)
    report["installed_kai_after"] = None
    report["assertions_passed"] = namespace.get("ASSERTIONS_PASSED")
    result = namespace.get("result")
    if result is not None:
        report.update(
            tests=result.testsRun, failures=len(result.failures),
            errors=len(result.errors), skipped=len(result.skipped),
        )
    profile.mkdir(parents=True, exist_ok=True)
    (profile / "run-result.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print("ISOLATED_RESULT", json.dumps(report))
