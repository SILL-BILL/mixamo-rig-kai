# Mixamo Rig Kai validation

## Supported range

From 0.6.10: Blender >= 4.5.0 and < 5.3.0.
Primary versions: 4.5.15 LTS and 5.2.3 LTS.
Comparison version: 5.1.1.
Blender 4.2 LTS is unsupported. Keep previous analysis/ records unchanged.

The manifest maximum is exclusive:
[Blender extension schema](https://developer.blender.org/docs/features/extensions/schema/1.0.0/).

## Protect the source and user environment

1. Inspect branch, commit, status and diff before work. Kai development is on
   mixamorig-kai; use an explicitly requested repair branch/worktree when applicable.
2. Preserve any uncommitted edits. Do not switch, reset or clean another worktree.
3. Use a fresh disposable user directory outside the normal Blender profile.
4. Set BLENDER_USER_RESOURCES, BLENDER_USER_CONFIG, BLENDER_USER_SCRIPTS,
   BLENDER_USER_EXTENSIONS and BLENDER_USER_DATAFILES before starting Blender.
   Pre-create these directories. Redirect TEMP/TMP for test recovery files.
5. Inspect bpy.utils.resource_path("USER") and bpy.utils.user_resource for CONFIG,
   SCRIPTS and EXTENSIONS before registering, installing or editing preferences.
   All must resolve inside the disposable directory. Stop if isolation fails.
6. Never clear the repository list. Add only kai_qa for local package verification.
   Never modify or remove another installed add-on.
7. Save preferences only in a verified isolated profile when package setup needs it.
   Do not save preferences during source regression tests.
8. Use synthetic fixtures or copies of production files. Never overwrite a production file.

Official environment documentation:
[Blender directory layout](https://docs.blender.org/manual/en/latest/advanced/blender_directory_layout.html).

## Source regression suites

Run from the intended worktree in PowerShell. The launcher saves/restores its
process environment and rejects output under the normal APPDATA Blender directory.
Choose a new RunName for each changed candidate.

```powershell
$blenderExe = 'C:\Program Files\Blender Foundation\Blender 4.5\blender.exe'
$qaOutput = Join-Path $env:TEMP 'mixamo-kai-disposable-validation'

.\tools\validate_blender.ps1 -BlenderPath $blenderExe -OutputDirectory $qaOutput -RunName 'v0610-45' -Suite full
.\tools\validate_blender.ps1 -BlenderPath $blenderExe -OutputDirectory $qaOutput -RunName 'v0610-45' -Suite safety
.\tools\validate_blender.ps1 -BlenderPath $blenderExe -OutputDirectory $qaOutput -RunName 'v0610-45' -Suite core
```

Repeat on Blender 5.2.3 LTS and use 5.1.1 for comparison.
The underlying command is:

```text
blender --background --factory-startup --offline-mode --python-exit-code 1 --python tools/run_kai_facial_isolated.py
```

The launcher sets KAI_QA_PROFILE and KAI_QA_SCRIPT. Each run records blender.log
and run-result.json, including version, source/script hashes, user paths,
repository counts, assertion/test counts and success.

| Suite | Script | Current expected success count |
| --- | --- | --- |
| full | test_kai_facial.py | 719 assertions |
| safety | test_kai_facial_safety.py | 16 unittest tests |
| core | test_kai_core_compatibility.py | 16 unittest tests |

Do not add assertion counts and unittest counts into a single test count.
Expected ERROR reports in missing-mapping/conflicting-driver safety tests are
not suite failures; inspect success, unittest results and the Blender exit code.

Core coverage includes both bundled templates, standard prefixed Mixamo-like
skeletons, zero/multiple Spine and Neck counts, optional Shoulder absence,
normal Rebuild, required/optional missing Mapping, hierarchy/connected changes,
user-owned Bone preservation, save/reopen, and actual retarget/bake through
mr.import_anim_to_rig. Retarget checks Quaternion continuity, Euler,
Target Original, nonzero motion, source Action preservation and differing prefixes.

## Verification ZIP

Do not create different runtime ZIPs with the same version.
Synchronize blender_manifest.toml, bl_info and the current README changelog.
Use Blender's official extension build command.

For an explicitly authorized uncommitted verification candidate, copy the exact
source files into a separate staging snapshot and record the source commit and
SHA-256 of every copied file. Do not package another branch or accidentally omit
the authorized edits. This is a local verification build, not an official release.
Official release branch/tag checks in AGENTS.md still apply.

```text
blender --factory-startup --command extension build --source-dir <snapshot> --output-dir <qa-output>
```

Inspect the ZIP manifest, required modules and lib/cs.blend. Compare every packaged
file with the intended worktree, reject development/cache files, and record
filename, byte size and SHA-256. Keep the ZIP outside the source repository.

## Local Extension enable check

Use another pre-created isolated profile, with all paths set and verified as above.
Never run these commands against the normal user profile.

1. Set KAI_QA_EXTENSION_PHASE=before and run test_kai_extension_enable.py with
   --background --factory-startup --offline-mode --python-exit-code 1 --python.
   It verifies isolation and records repositories-before.json.
2. Run the official CLI without --clear-all:

```text
blender --factory-startup --offline-mode --command extension repo-add kai_qa --name "Kai Disposable QA" --directory <isolated-extensions>/kai_qa
blender --offline-mode --command extension install-file -r kai_qa -e <qa-output>/mixamo_rig_kai-0.6.10.zip
```

3. Set KAI_QA_EXTENSION_PHASE=verify, then run the same script with
   --background --offline-mode --python-exit-code 1 --python (without factory-startup
   so the isolated repository/enable preferences are loaded).
4. Inspect extension-result.json and logs. Verify existing repositories are
   unchanged, only kai_qa was added, installed version is 0.6.10, classes/panels
   register, the MixamoKai category exists, and Rig generation/Rebuild succeeds.

This script targets candidate 0.6.10. Update its expected version for later candidates.
Native Extension modules do not retain the legacy bl_info attribute at runtime;
verify installed metadata from blender_manifest.toml, and verify source bl_info separately.

## Automated GUI check

Use the verified installed profile from the previous section and set:

- KAI_QA_PROFILE: its disposable directory
- KAI_QA_OUTPUT: a separate screenshot/results directory
- KAI_QA_INSTALLED_MODULE: bl_ext.kai_qa.mixamo_rig_kai

Start Blender in GUI mode with --offline-mode --python tools/test_kai_facial_gui.py.
Do not pass --factory-startup when using the installed profile.
For a source-only GUI check, omit KAI_QA_INSTALLED_MODULE and use factory-startup.

The script uses synthetic fixtures. It sends Escape only to its own Blender
process to dismiss the splash, checks rename/removal/linked-duplicate rejection,
draws the actual Facial panel as a popover, saves five screenshots and gui-result.json,
then closes only its own Blender process. The Win32 splash helper requires Windows.

Require nontrivial image dimensions and visually inspect the screenshots.
This checks GUI drawing with automated operator execution; it is not a manual
mouse/keyboard, N-panel tab switching or Undo/Redo acceptance test.

## Reporting and cleanup

### Panda Factory standard test data

Canonical test originals belong in the existing Google Drive folder
`panda-factory/test-data/blender/`. Google Drive upload and overwriting are separate
actions requiring user instruction. Until authorized, keep immutable generated
files outside every repository worktree and report them as pending upload.
The local pending directory is temporary staging, not permanent storage.
`lab/` may be used for temporary generation/validation only.

GitHub stores generators, tests, procedures and documentation, together with
required product assets. Preserve `lib/cs.blend`; do not apply a blanket .gitignore
change or delete resources to enforce this policy.

`generate_kai_test_data.py` creates seven synthetic, self-contained .blend originals:

| Filename | Purpose |
| --- | --- |
| kai-v0610-reference-basic.blend | Basic Reference generation / Rebuild |
| kai-v0610-reference-fingers.blend | Fingers Reference generation / Rebuild |
| kai-v0610-reference-minimal.blend | No intermediate Spine, Neck or Shoulder |
| kai-v0610-reference-multichain.blend | Six Spine / three Neck bones |
| kai-v0610-retarget-source.blend | Prefixed source Action over frames 1-12 |
| kai-v0610-facial-independent.blend | Posed/keyed Facial A and independent B with shared Text |
| kai-v0610-facial-linked.blend | Shared Armature data rejection |

Set the same isolated profile variables as above and set KAI_TEST_DATA_OUTPUT
to a new absolute directory outside the repository. Run the generator with
Blender 4.5.15 and --background --factory-startup --offline-mode --python-exit-code 1.
The generator refuses to reuse an output directory, localizes product-shape
data only in memory, and writes fixture-manifest.json with purposes, paths,
provenance, checksums and pending status. It never writes lib/cs.blend.
No FBX file is generated by this script.

Use `test_kai_acceptance_gui.py` on the isolated installed profile:

- KAI_TEST_DATA_ORIGINALS: the generated originals directory
- KAI_QA_OUTPUT: a new repository-external run directory
- KAI_QA_INSTALLED_MODULE: bl_ext.kai_qa.mixamo_rig_kai

It first copies both Facial originals into its run directory. Only those copies
are opened/modified. It checks actual Blender Undo/Redo using the operators'
native undo flag, keyframes/Mapping/labels, add/remove recovery, save/reopen,
linked-data rejection and unchanged original hashes. Input/run copies and logs
are temporary evidence; distinguish them from standard-original upload candidates.
The test uses automated GUI operator execution, not human mouse acceptance.

After an authorized Drive save, register the data in the existing
「Panda Factory｜テストデータ台帳」. Do not create a new database or change
schema/options without first reporting the proposed change.

Before committing, run:

```text
git status --short
git diff --cached --name-only
git diff --cached --stat
```

Inspect actual staged paths for unintended test .blend, FBX, ZIP, images and logs.
Classify by purpose so that legitimate product resources are retained.

Record exact Blender executable/version, source/version hashes, successful and
failed counts with their units, GUI evidence, package hash, untested scenarios,
isolated user paths, repository counts before/after and installed Kai version
before/after. State that normal repositories/add-ons/preferences were not changed.
Keep disposable environments when needed for investigation; never delete a
computed directory without verifying that it is confined to the intended QA root.
Commit, push, tags, release and repository publishing require separate user approval.
