"""Validate standard fixture copies, leaving Drive-pending originals unchanged."""

import hashlib
import json
import os
import shutil
from pathlib import Path

import bpy


REPO = Path(__file__).resolve().parents[1]
ORIGINALS = Path(os.environ["KAI_TEST_DATA_ORIGINALS"]).resolve()
OUTPUT = Path(os.environ["KAI_TEST_DATA_OUTPUT"]).resolve()
assert not OUTPUT.is_relative_to(REPO)
OUTPUT.mkdir(parents=True, exist_ok=False)
fixture_path = REPO / "tools/test_kai_facial.py"
namespace = {"__file__": str(fixture_path), "__name__": "fixture_validation"}
exec(compile(fixture_path.read_text(encoding="utf-8").split("def assert_true")[0],
             str(fixture_path), "exec"), namespace)
facial = namespace["kai_facial"]
manifest = json.loads((ORIGINALS / "fixture-manifest.json").read_text(encoding="utf-8"))
results = []
for entry in manifest["entries"]:
    original = ORIGINALS / entry["filename"]
    assert hashlib.sha256(original.read_bytes()).hexdigest() == entry["sha256"]
    working = OUTPUT / original.name
    shutil.copy2(original, working)
    bpy.ops.wm.open_mainfile(filepath=str(working))
    assert not bpy.data.libraries, original.name
    if "reference-" in original.name:
        rig = bpy.context.object
        kwargs = json.loads(rig.data["panda_factory_generate_kwargs"])
        assert bpy.ops.mr.make_rig(**kwargs) == {"FINISHED"}
        assert bpy.ops.mr.rebuild_rig() == {"FINISHED"}
        assert rig.pose.bones.get("Ctrl_Head") is not None
    elif "retarget-source" in original.name:
        rig = bpy.data.objects["PF_Kai_AnimatedSource"]
        assert tuple(rig.animation_data.action.frame_range) == (1.0, 12.0)
    else:
        rig = bpy.data.objects["PF_Kai_A"]
        companion = bpy.data.objects.get("PF_Kai_B") or bpy.data.objects.get("PF_Kai_Linked")
        assert (rig.data == companion.data) == ("linked" in original.name)
        assert len(facial.get_custom_face_channels(rig)) == 2
        mesh = bpy.data.objects["PF_Kai_FaceMesh"]
        assert len(mesh.data.vertices) == 4
        bpy.context.scene.frame_set(1)
        bpy.context.view_layer.update()
        assert abs(mesh.data.shape_keys.key_blocks["Cheek Puff"].value - 0.65) < 1e-4
    assert hashlib.sha256(original.read_bytes()).hexdigest() == entry["sha256"]
    results.append({"filename": original.name, "success": True, "working_copy": str(working)})
(OUTPUT / "fixture-validation.json").write_text(json.dumps({
    "success": True, "blender": bpy.app.version_string, "fixtures_passed": len(results),
    "originals_modified": False, "results": results,
}, indent=2), encoding="utf-8")
print("KAI_FIXTURE_VALIDATION_OK", len(results))
