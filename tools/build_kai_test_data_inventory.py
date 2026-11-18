"""Build a local-only Drive registration inventory; never uploads or edits Notion."""

import argparse
import csv
import hashlib
import json
import shutil
from pathlib import Path


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pending-root", type=Path, required=True)
    options = parser.parse_args()
    root = options.pending_root.resolve()
    repo = Path(__file__).resolve().parents[1]
    assert not root.is_relative_to(repo)
    output = root / "drive-registration-inventory.json"
    assert not output.exists(), output
    manifest = json.loads((root / "originals-r2/fixture-manifest.json").read_text(encoding="utf-8"))
    entries = manifest["entries"]
    for entry in entries:
        path = Path(entry["local_path"])
        assert digest(path) == entry["sha256"], path
        entry.update(
            role="standard_fixture", upload_candidate=True,
            generator_sha256=digest(repo / entry["generator"]),
        )
    evidence = root / "evidence"
    evidence.mkdir(exist_ok=False)
    acceptance = []
    for version, exact in (("4.5", "4.5.15"), ("5.2", "5.2.3")):
        run = root / ("acceptance-r2-" + version)
        result = json.loads((run / "acceptance-result.json").read_text(encoding="utf-8"))
        assert result["success"] and len(result["checks"]) == 49
        acceptance.append(result)
        target = evidence / ("kai-v0610-acceptance-blender-" + exact + ".png")
        shutil.copy2(run / "acceptance-after-redo.png", target)
        entries.append({
            "filename": target.name,
            "purpose": "Automated GUI evidence after rename/remove/add Undo and Redo on Blender " + exact,
            "local_path": str(target), "drive_destination": "panda-factory/test-data/blender/",
            "drive_status": "pending_upload_not_authorized",
            "generator": "tools/test_kai_acceptance_gui.py",
            "generator_sha256": digest(repo / "tools/test_kai_acceptance_gui.py"),
            "blender": result["blender"], "bytes": target.stat().st_size, "sha256": digest(target),
            "role": "acceptance_evidence", "upload_candidate": True,
        })
    report = {
        "extension_version": "0.6.10",
        "intended_drive_folder": "panda-factory/test-data/blender/",
        "drive_folder_verified_via_connector": False,
        "drive_upload_performed": False, "drive_files_overwritten": False,
        "notion_ledger": "Panda Factory｜テストデータ台帳",
        "notion_registration_performed": False, "notion_schema_changed": False,
        "local_storage_status": "temporary staging pending authorized Drive registration; not durable storage",
        "entries": entries,
        "temporary_non_upload_locations": [
            str(root / "originals"),  # incomplete first generator attempt, retained for investigation
            *[str(root / (name + version)) for name in (
                "acceptance-", "acceptance-r2-", "fixture-audit-") for version in ("4.5", "5.2")],
        ],
        "acceptance_results": acceptance,
        "fbx_generated": False,
    }
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    columns = ("filename", "purpose", "local_path", "drive_destination", "drive_status",
               "role", "bytes", "sha256", "generator", "generator_sha256")
    with (root / "drive-registration-inventory.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(entries)
    lines = [
        "# Panda Factory — Drive registration pending",
        "",
        "Destination: panda-factory/test-data/blender/",
        "Status: Local staging only. Upload/overwrite is not authorized.",
        "Notion: Use the existing Panda Factory｜テストデータ台帳 after authorized Drive storage.",
        "No upload, ledger registration, schema change or new database has been performed.",
        "",
        "| Filename | Purpose | Local path | SHA-256 |",
        "| --- | --- | --- | --- |",
    ]
    lines.extend("| " + " | ".join(str(entry[key]) for key in (
        "filename", "purpose", "local_path", "sha256")) + " |" for entry in entries)
    lines.extend([
        "",
        "Input copies, acceptance save copies, audit copies, initial failed attempts and logs are",
        "temporary verification artifacts, not standard-original upload candidates. See JSON for locations.",
        "No FBX was generated. Canonical originals were authored in Blender 4.5.15 and validated in both target versions.",
    ])
    (root / "DRIVE_REGISTRATION_PENDING.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"standard_blends": 7, "evidence_images": 2, "upload_performed": False,
                      "inventory": str(output)}))


if __name__ == "__main__":
    main()
