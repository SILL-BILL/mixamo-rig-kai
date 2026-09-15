# Blender User Environment Safety Incident — 2026-09-15

## Status

- Phase 2 implementation work is frozen.
- Repository Sync / Install / Enable tests are suspended.
- No Blender process was launched during this incident investigation.
- Root cause is identified from the Codex execution log, filesystem timestamps, hashes, and surviving QA directories.
- The normal Blender 4.2 and 5.1 preferences were modified by the QA. The earlier report that both tests were isolated was incorrect.

## Confirmed impact

The following normal-profile files were atomically replaced or rewritten during the final QA commands:

| Version | Normal-profile file | Creation time UTC | Last-write UTC | SHA-256 after incident |
| --- | --- | --- | --- | --- |
| 4.2 | `C:\Users\lost5\AppData\Roaming\Blender Foundation\Blender\4.2\config\userpref.blend` | 2026-09-15 10:12:43.397 | 2026-09-15 10:12:44.629 | `E7F094715119F5A18BC2CAB2A20D9C7413A839E0A8E5438FD328FAC809E18E99` |
| 5.1 | `C:\Users\lost5\AppData\Roaming\Blender Foundation\Blender\5.1\config\userpref.blend` | 2026-09-15 10:13:04.153 | 2026-09-15 10:13:06.651 | `8A396F416E33008CD99B255C8DB26F784D5D2FEB447B9F69B1D27ADFA398DFAB` |

Related normal-profile compatibility cache files were also rewritten in the same command windows:

| Version | File | Last-write UTC | SHA-256 after incident |
| --- | --- | --- | --- |
| 4.2 | `extensions\.cache\compat.dat` | 2026-09-15 10:12:44.469 | `947DC786B7FC740820278CFE489B1F335C5EBF922DE6B9A3DEE09B801AA43E96` |
| 5.1 | `extensions\.cache\compat.dat` | 2026-09-15 10:13:06.453 | `5920FAD9104B25027641B1BFF76EFFF7F0B3E22F32FA170AF452C0062C1CD027` |

Printable strings in both current `userpref.blend` files contain only the `kai_dev` repository identity and the corresponding `phase2_final42` / `phase2_final51` repository directory among repository-related identifiers. The QA `repo-list` output likewise showed only `kai_dev` immediately after `repo-add --clear-all`.

Existing repository directories and index files under the normal `extensions` directories still exist. This does not mean their registrations remain in Preferences: registration state is stored in `userpref.blend`, which was replaced. Existing extension payloads were not deleted by the four install command groups because `install-file` used an explicit isolated `--directory` repository, but enabled/disabled state and repository registrations may have been changed or lost with the replaced preferences.

No pre-incident hash snapshot was taken, and no `userpref.blend1` backup exists beside either affected file. Therefore the precise pre-incident contents cannot be proven or reconstructed from these files alone.

## Root cause

The incident was caused by an incomplete isolation contract combined with a destructive repository option:

1. QA set `BLENDER_USER_CONFIG`, `BLENDER_USER_SCRIPTS`, and `BLENDER_USER_DATAFILES`, but never set `BLENDER_USER_RESOURCES`.
2. The referenced `config`, `scripts`, and `datafiles` directories were not created before Blender started. All six retained repository/install roots (`b42`, `b51`, `phase2_install42`, `phase2_install51`, `phase2_final42`, and `phase2_final51`) confirm `config=False`, `scripts=False`, and `datafiles=False`; only `extensions=True` existed because the commands created explicit repository directories.
3. The validation script printed `bpy.utils.user_resource("CONFIG")` and `bpy.utils.user_resource("SCRIPTS")`, but did not verify those directories existed or verify the actual `userpref.blend` destination. A returned resource path was incorrectly treated as proof that persistence was isolated.
4. `extension repo-add ... --clear-all` then cleared the repositories in the preferences Blender actually loaded and saved. `--directory` isolated the extension payload directory; it did not itself isolate the preferences file.
5. `extension repo-add` and `extension install-file` persisted Preferences automatically. The 4.2 output explicitly reported `Info: Preferences saved`. No QA Python script called `bpy.ops.wm.save_userpref()`.

Blender documents `BLENDER_USER_RESOURCES` as the top-level override for user files. It also documents `config/userpref.blend` and `extensions` as siblings beneath that user directory. The safer contract is therefore a pre-created isolated top-level resource directory plus explicit subordinate overrides, not subordinate path strings alone:

- https://docs.blender.org/manual/en/latest/advanced/blender_directory_layout.html
- https://docs.blender.org/manual/en/4.0/advanced/command_line/arguments.html

## QA command inventory

The complete Phase 2 Codex session (started 2026-09-13) contains:

| Item | Count |
| --- | ---: |
| Shell command records that launched Blender | 279 |
| Individual Blender invocations | 305 |
| Command records setting `BLENDER_USER_CONFIG` | 35 |
| Command records setting `BLENDER_USER_RESOURCES` | 0 |
| Repository-operation command records | 11 |
| Install/help command records matched by inventory | 7 |
| Command records using `--clear-all` | 7 |
| Command records whose stdout reported `Preferences saved` | 4 |
| Command records whose stdout reported `Blender quit` | 205 |

The complete exact command strings for the full session are recorded in `analysis/blender_qa_commands_full_session.json`.

The incident-day subset for 2026-09-15 contains:

| Item | Count |
| --- | ---: |
| Shell command records that launched Blender | 31 |
| Individual Blender invocations | 44 |
| Command records setting `BLENDER_USER_CONFIG` | 26 |
| Command records setting `BLENDER_USER_RESOURCES` | 0 |
| Command records with no `BLENDER_USER_CONFIG` | 5 |
| Repository-operation command records | 4 |
| Install/help command records matched by inventory | 5 |
| Command records using `--clear-all` | 4 |
| Command records whose stdout reported `Preferences saved` | 2 |
| Command records whose stdout reported `Blender quit` | 26 |

The exact incident-day command strings, environment variables, executable paths, exit codes, operation flags, Python script paths, and quit/save indicators are recorded in `analysis/blender_qa_commands_2026-09-15.json`.

The state-mutating `repo-add --clear-all` attempts began no later than 08:17 UTC. Seven such command records exist:

| Completion UTC | Version | Repository name | Operations |
| --- | --- | --- | --- |
| 2026-09-15 08:17:08 | 4.2.23 | QA repository | `repo-add --clear-all` |
| 2026-09-15 08:18:17 | 4.2.23 | QA repository | `repo-add --clear-all` |
| 2026-09-15 08:19:44 | 5.1.1 | QA repository | `repo-add --clear-all` |
| 2026-09-15 10:09:38 | 4.2.23 | Kai Development QA | `repo-add --clear-all`, `repo-list`, `install-file`, enable/verify |
| 2026-09-15 10:10:05 | 5.1.1 | Kai Development QA | `repo-add --clear-all`, `repo-list`, `install-file`, enable/verify |
| 2026-09-15 10:12:45 | 4.2.23 | Kai Final Build QA | `repo-add --clear-all`, `install-file`, enable/verify |
| 2026-09-15 10:13:08 | 5.1.1 | Kai Final Build QA | `repo-add --clear-all`, `install-file`, enable/verify |

All seven were unsafe because none set `BLENDER_USER_RESOURCES` and none had an existing isolated config directory. The final two groups provide exact timestamp correlation with the currently present `userpref.blend` files.

## Preferences and exit processing

- `tools/test_kai_facial.py` creates an in-memory `bpy.context.preferences.addons` entry and removes it at the end. It does not save Preferences.
- `tools/test_kai_facial_mapping_interactive.py` creates an in-memory add-on entry and calls `bpy.ops.wm.quit_blender()` from a timer. It does not remove the entry or explicitly save Preferences.
- `capture_phase2_viewport.py` creates an in-memory add-on entry and calls `bpy.ops.wm.quit_blender()` after capture. It does not remove the entry or explicitly save Preferences.
- `verify_dev_build_install.py` reads the enabled extension state, validates it, and calls `bpy.ops.wm.quit_blender()`.
- Background tests otherwise terminated normally. The PowerShell command groups used `$LASTEXITCODE` checks but had no environment-safety cleanup or normal-profile postcondition check.

The direct persistence trigger observed in the logs is Blender's extension CLI, not an explicit Python `save_userpref` call.

## Containment and automatic guard

`tools/audit_blender_user_environment.ps1` now provides:

- `Snapshot`: hashes every normal-profile config file plus Extension repository metadata/cache for Blender 4.2 and 5.1.
- `Compare`: compares existence, size, last-write time, and SHA-256, returning exit code 3 on any change.
- `RunIsolated`: pre-creates `config`, `scripts`, `datafiles`, `extensions`, and `temp`; sets `BLENDER_USER_RESOURCES` plus subordinate overrides; restores process environment variables in `finally`; records the exact Blender command/environment/exit code; and fails if the normal profile changes.

The post-incident baseline is `analysis/normal_blender_profile_post_incident_baseline.json`. A read-only immediate comparison completed with:

```text
unchanged: true
changed_file_count: 0
```

This only proves that the normal files stayed unchanged during this investigation after the baseline was captured. It does not undo or negate the confirmed earlier modifications.

`tools/extract_blender_qa_history.ps1` creates the complete command inventory directly from the Codex JSONL execution log.

## Recovery status

No restoration, repository mutation, extension enable/disable, Preferences save, or Blender launch was performed during this investigation. Recovery is intentionally pending because there is no verified pre-incident `userpref.blend` snapshot to restore automatically. Any reconstruction from surviving extension directories would be a new Preferences mutation and requires explicit user direction.

## Version report

```text
Version Before: 0.6.5
Version After: 0.6.5
Version Bumped: No
Reason: Incident report, command inventory, and tools-only safety/audit scripts; no Runtime, UI, rig behavior, or packaged resource changed.
```
