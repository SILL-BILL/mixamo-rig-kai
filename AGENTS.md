# AGENTS.md

## Project

This repository contains **Mixamo Rig Kai**, a Blender Extension forked from the original Mixamo Rig project.

Kai extends the original rig generator with:

- Reference Skeleton Mapping
- Variable Spine support
- Variable Neck support
- Optional Shoulder support
- Reference Bone Generator
- Reference Templates
- Rebuild Rig / Reset Generated Rig
- Retarget improvements
- Future modular controllers such as Eye / Facial systems

Maintainer: **Gonsaku**

Repository:

`SILL-BILL/mixamo-rig-kai`

---

# Important Branch Rule

## Kai development branch

The active Mixamo Rig Kai development branch is:

```text
mixamorig-kai
```

Do **not** assume `main` contains the current Kai implementation.

The `main` branch may contain code inherited from the upstream/original Mixamo Rig project.

Before making changes, building a release, creating a tag, or preparing a package:

1. Check the current branch.
2. Confirm that the working branch is `mixamorig-kai`.
3. Confirm that the target commit actually contains Kai-specific changes.

Never create a Kai release from `main` unless the repository structure is intentionally changed in the future.

---

# Blender Support

Current supported Blender versions:

```text
Blender 4.2+
```

Primary verification versions:

```text
Blender 4.2.23 LTS
Blender 5.1.1
```

New features should remain compatible with both versions unless explicitly documented otherwise.

Do not introduce Blender API usage that breaks Blender 4.2 compatibility without approval.

---

# Extension Identity

The Blender Extension identity is:

```text
id = "mixamo_rig_kai"
name = "Mixamo Rig Kai"
```

Do not change the extension ID casually.

The Extension ID is part of the installation/update identity used by Blender Extension repositories.

---

# Version Consistency

## Increment the build version for every implementation change

For every code, behavior, UI, data, or packaged-resource modification, increment
the Extension patch/build version before declaring the work complete.

Example:

```text
4.2.0 -> 4.2.1
```

Keep the version synchronized at minimum between:

```text
blender_manifest.toml
__init__.py (`bl_info["version"]`)
README.md changelog/version references when applicable
```

Documentation-only edits to development instructions such as `AGENTS.md` do not
require a version increment. The next implementation change must apply this rule.

Before any release, confirm that version information is consistent.

Check at minimum:

```text
blender_manifest.toml
__init__.py
README.md changelog
Git tag
GitHub Release
Release ZIP
```

Example:

```text
blender_manifest.toml
version = "0.6.1"
```

```python
bl_info = {
    "version": (0, 6, 1),
}
```

Release naming convention:

```text
v0.6.1-preview
```

Extension package version:

```text
0.6.1
```

Package filename:

```text
mixamo_rig_kai-0.6.1.zip
```

The `-preview` suffix belongs to the Git tag / GitHub Release naming convention and should not be added to the Blender Extension semantic version unless the manifest specification explicitly requires it.

---

# Versioning and Build Identification

Mixamo Rig Kaiでは、修正前後のBuildを明確に識別できるよう、**機能・挙動・UI・生成結果に変更が入った修正単位ごとにPatch Versionを1つ繰り上げること**。

## 基本ルール

現在のVersionが`0.6.3`の場合、次の修正Buildは`0.6.4`とする。さらに別の修正を行い、新しい検証Buildを作る場合は`0.6.5`へ繰り上げる。

「同じ0.6.3だが中身が違う」という状態を作らないこと。

## Patch Versionを上げるタイミング

以下のいずれかに該当する変更を行った場合、次の検証Buildを作る前にPatch Versionを上げる。

- Bug Fix
- UI変更
- Operator動作変更
- Rig生成ロジック変更
- Driver / Constraint変更
- Mapping仕様変更
- Controller / Bone生成変更
- Rebuild / Reset / Remove動作変更
- Blender Version互換修正
- ユーザーの実機レビューを受けた挙動修正
- 配布ZIPの中身が実質的に変わるコード変更

例:

```text
0.6.3
↓ Phase 1.2 Mapping実装
0.6.4

0.6.4
↓ Face UI Scale修正
0.6.5

0.6.5
↓ Remove分離 / Regenerate UI修正
0.6.6
```

複数ファイルを同時に修正していても、**1つの修正タスク / レビュー対応単位で1回だけ**繰り上げればよい。ファイルを保存するたびにVersionを上げる必要はない。

## Versionを上げなくてよい変更

以下のみの変更では、原則としてVersionを上げなくてよい。

- コメント修正
- コードフォーマットのみ
- 開発用ドキュメントのみ
- `AGENTS.md`のみ
- `analysis/`のみ
- `tools/`内の開発・検証用スクリプトのみでRuntimeへ影響しない変更
- READMEの誤字修正のみ
- Runtime / UI / Build内容が変化しない変更

ただし、それらの変更でも配布Runtimeへ影響する場合はVersionを上げること。

## Version同期

Versionを変更した場合、少なくとも以下を同期する。

```text
blender_manifest.toml
version = "X.Y.Z"

__init__.py
bl_info["version"] = (X, Y, Z)
```

Version表記を持つ他のRuntime / Release用ファイルが存在する場合も不整合を残さない。README / ChangelogはRelease準備時に最終整合を確認する。

## Build前チェック

検証用または配布用ZIPをBuildする前に、必ず以下を確認する。

```text
1. 今回Runtime / UI / Rig挙動に変更があるか
2. 変更がある場合、直前BuildよりPatch Versionが上がっているか
3. blender_manifest.toml と bl_info が一致しているか
4. Build filenameに現在Versionが反映されているか
```

例:

```text
mixamo_rig_kai-0.6.4.zip
```

## Report Rule

実装・修正報告には必ず現在Versionを記載する。

```text
Version Before:
Version After:
Version Bumped: Yes / No
Reason:
```

例:

```text
Version Before: 0.6.3
Version After: 0.6.4
Version Bumped: Yes
Reason: Phase 1.2 Facial Shape Key Mappingを追加したため
```

Versionを上げなかった場合も理由を書く。

## Git / Releaseとの関係

**Versionを上げることと、commit / push / tag / releaseを行うことは別。**

ユーザーからcommit / push / releaseを止められている場合でも、Runtime修正後の検証Buildを識別するためのVersion更新は行ってよい。

ただし、

```text
commit
push
tag
GitHub Release
Extension Repository更新
```

はユーザーから明示的な許可があるまで行わない。

## Important

目的はSemantic Versioningを厳密に運用することだけではなく、**「今テストしているZIPが修正前なのか修正後なのかを、人間がVersionを見るだけで判断できる状態を維持すること」**である。

同一Versionで異なるRuntime Buildを複数作らないこと。

---

# Release Tag Safety

Kai previously had a release tag that incorrectly referenced the upstream/original Mixamo Rig commit.

Because of this, release tag validation is mandatory.

Before publishing or modifying a release:

1. Determine the intended Kai commit.
2. Check the commit currently referenced by the release tag.
3. Confirm the tag points to the intended `mixamorig-kai` commit.
4. Confirm the GitHub Release target references the same commit.
5. Confirm the commit contains Kai-specific files and current version metadata.

Never assume an existing tag is correct.

Useful checks include:

```bash
git rev-parse HEAD
git rev-parse vX.Y.Z-preview
git log -1 vX.Y.Z-preview
```

If the tag points to an incorrect commit, report the problem before rewriting or force-updating the tag.

---

# Blender Extension Build

Use Blender's official Extension build tooling.

Preferred command:

```powershell
blender --factory-startup --command extension build
```

The existing project build script may also be used if it produces an equivalent package.

Expected output:

```text
mixamo_rig_kai-X.Y.Z.zip
```

Always build from a clean and correct `mixamorig-kai` checkout.

---

# Extension Package Validation

Before publishing a ZIP, inspect and validate the generated package.

Confirm:

- Correct Extension ID
- Correct Extension version
- Correct Extension name
- Correct minimum Blender version
- Required Python modules are included
- Required templates/resources are included
- No development caches are included
- No unrelated upstream files are accidentally packaged

The following files/directories must not be distributed unless intentionally required:

```text
.git/
.github/
.vs/
.vscode/
.idea/
__pycache__/
.pytest_cache/
.mypy_cache/
.tox/
tools/
*.pyc
*.pyo
*.log
```

Keep `blender_manifest.toml` build exclusion rules updated when new development-only directories are introduced.

---

# Release Asset Verification

After creating the release package, calculate and record:

```text
Filename
File size
SHA-256
```

Example:

```text
mixamo_rig_kai-0.6.1.zip
194655 bytes
SHA-256: <hash>
```

If a GitHub Release Asset already exists, compare it against the newly built package.

The GitHub Release Asset must match the intended official build.

When replacing an incorrect asset:

1. Build the correct package.
2. Calculate SHA-256.
3. Replace the Release Asset.
4. Download the published asset again.
5. Recalculate SHA-256.
6. Confirm the downloaded asset matches the local official build.

Do not trust an uploaded artifact solely because the filename is correct.

---

# Extension Repository

Mixamo Rig Kai is distributed through the shared SILL-BILL Blender Extension Repository.

Repository:

```text
SILL-BILL/blender-extensions
```

Public repository endpoint:

```text
https://sill-bill.github.io/blender-extensions/index.json
```

The repository also contains other extensions such as Panda Tool.

Do not remove, overwrite, or break existing extensions while updating Kai.

---

# Publishing to Blender Extension Repository

The official Mixamo Rig Kai release ZIP should be copied into:

```text
blender-extensions/docs/
```

Example:

```text
docs/
├─ .nojekyll
├─ index.html
├─ index.json
├─ panda_tool-0.3.0.zip
└─ mixamo_rig_kai-0.6.1.zip
```

Do not repack the release ZIP.

The ZIP used by:

```text
GitHub Release
Extension Repository
Local release archive
```

should be byte-identical whenever possible.

Verify using SHA-256.

---

# Extension Repository Index

Never manually invent or edit extension metadata in `index.json` when Blender can generate it.

Regenerate the repository index using Blender's official CLI:

```powershell
blender --factory-startup --command extension server-generate --repo-dir=docs --html
```

This generates:

```text
docs/index.json
docs/index.html
```

After generation, confirm that existing extensions are still present.

At minimum verify:

```text
panda_tool
mixamo_rig_kai
```

Check Kai metadata including:

```text
id
name
version
archive_url
archive_size
archive_hash
blender_version_min
```

---

# GitHub Pages Validation

After pushing changes to `SILL-BILL/blender-extensions`, validate the published endpoint rather than testing only local files.

Public endpoint:

```text
https://sill-bill.github.io/blender-extensions/index.json
```

Confirm:

1. HTTP endpoint is reachable.
2. New Kai version appears in the published index.
3. Archive URL resolves correctly.
4. Published archive size/hash match the official ZIP.

---

# Blender Installation Test

For release verification, use a clean or isolated Blender profile when practical.

Test with:

```text
Blender 4.2.23 LTS
Blender 5.1.1
```

For each version verify:

1. Add the SILL-BILL repository.
2. Repository Sync succeeds.
3. Mixamo Rig Kai is discovered.
4. Panda Tool remains discoverable.
5. Install Mixamo Rig Kai.
6. Enable Mixamo Rig Kai.
7. Verify registration completes without errors.
8. Verify the `MixamoKai` UI appears.
9. Verify expected panels are registered.
10. Verify no class-registration conflicts occur.

Current expected UI location:

```text
VIEW_3D
→ UI
→ MixamoKai
```

---

## Blender User Environment Safety

Mixamo Rig Kaiの検証では、**ユーザーが日常使用しているBlenderのPreferences、Extension Repository、インストール済みAdd-on / Extensionを変更・初期化・削除してはならない。**

Repository Sync、Extension Install / Uninstall、Factory Startup、Preferences操作など、Blenderのユーザー環境を書き換える可能性があるテストは、必ず隔離された検証環境で実行すること。

### 最重要ルール

通常使用中のBlenderユーザープロファイルを、テスト用環境として直接使用しない。

特に以下を禁止する。

- 既存Extension Repository一覧の全削除
- Blender公式Repositoryの削除・置換
- ユーザーが追加したRepositoryの削除・置換
- 既存Add-on / Extensionの一括削除
- Factory Preferencesを通常プロファイルへ保存
- 通常プロファイルの`userpref.blend`をテスト用設定で上書き
- Repository検証のために既存Repository設定全体を初期化
- テスト後にユーザー環境を「元に戻す」ことを前提とした破壊的操作

「あとで復元する」ではなく、**最初から実環境へ触れないこと**を優先する。

---

## Repository / Install Test Isolation

以下を行うテストは、必ず一時的・破棄可能なBlenderユーザー環境で実施する。

- Repository追加
- Repository削除
- Repository Sync
- Extension Discovery
- Extension Install
- Extension Uninstall
- Extension Enable / Disable
- Preferences保存
- Factory Startupを伴う設定テスト
- Repository Index切り替え
- Extension Repository競合テスト

### 推奨方針

テスト開始時に、対象Blender Version用の一時ユーザー環境を作成する。

例:

```text
temp/
└─ blender-user-env/
   ├─ config/
   ├─ scripts/
   └─ extensions/
```

対象Blender Versionで利用可能なユーザーリソースパス / 環境変数を使用し、通常のユーザー設定ディレクトリとは分離すること。

環境変数名やディレクトリ仕様はBlender Versionによって確認し、推測で使用しない。

---

## Real User Profile Protection

テスト開始前に、Blenderが参照しているユーザーリソースパスを確認する。

少なくとも以下を確認すること。

```python
import bpy

print(bpy.utils.user_resource("CONFIG"))
print(bpy.utils.user_resource("SCRIPTS"))
```

Repository / Install系の自動テストで、これらが通常のユーザー環境を指している場合は、破壊的テストを開始しない。

通常環境の例:

```text
%APPDATA%\Blender Foundation\Blender\<version>\
```

この配下を直接書き換えるRepository / Installテストは禁止する。

---

## Preferences Save Rule

テストコードからPreferencesを保存する必要がある場合は、隔離環境であることを確認してから実行する。

通常ユーザープロファイルに対して以下のような操作を行わない。

```text
Save Preferences
Factory Preferencesの永続保存
Repository一覧の永続保存
テスト用Add-on状態の永続保存
```

通常プロファイルを検出した場合は、テストを中止して報告する。

---

## Repository Mutation Rule

Kai Extension Repositoryのテストでは、**Kai Repositoryだけを操作対象とする。**

既存Repository一覧全体を書き換えない。

禁止例:

```text
既存Repositoryを全削除
↓
Kai Repositoryだけ追加
↓
テスト
```

推奨:

```text
隔離環境を作成
↓
必要なRepositoryだけ追加
↓
テスト
↓
隔離環境を破棄
```

どうしても既存Repositoryを利用する非破壊テストを行う場合でも、

- 既存Repositoryを削除しない
- Blender公式Repositoryを変更しない
- 他プロジェクトのRepositoryを変更しない
- ユーザーがインストール済みのExtensionを削除しない

こと。

---

## Add-on / Extension Safety

KaiのInstall / UninstallテストはKai自身だけを対象とする。

以下を禁止する。

- 他Add-onの削除
- 他Extensionの削除
- 他ExtensionのEnable / Disable変更
- User Scripts配下の一括削除
- Extensionディレクトリの一括初期化

テストCleanupもKaiが生成・インストールした対象だけを削除する。

---

## Before / After Verification

Repository / Install系テストでは、テスト前後の環境を検証する。

隔離環境であっても、最低限以下を記録する。

```text
User Config Path:
User Scripts Path:
Repository Count Before:
Repository Count After:
Installed Kai Version Before:
Installed Kai Version After:
Test Environment Disposable: Yes / No
```

通常ユーザー環境を使用していないことを完了報告へ明記する。

---

## Fail Safe

隔離環境の作成に失敗した場合、Repository / Install / Preferences書き換えテストを実行しない。

その場合は、

```text
Repository / Install verification skipped:
safe isolated Blender user environment could not be created.
```

のように報告する。

**検証を完遂することより、ユーザー環境を保護することを優先する。**

---

## Release Verification Rule

GitHub ReleaseやExtension Repository公開後の実インストール確認も、原則として隔離環境で行う。

検証項目:

```text
Repository Sync
Discovery
Install
Enable
Kai UI
Version
```

これらを確認するために、普段使用しているBlender環境を初期化・変更する必要はない。

通常環境で最終確認を行う場合は、Kaiの追加・更新のような非破壊操作だけに限定する。

---

## Report Rule

Repository / Install / Preferences関連の検証を行った場合、完了報告へ以下を追加する。

```text
Blender User Environment:
Isolated / Normal

User Config Path:
<path>

Existing User Repositories Modified:
No

Existing Add-ons / Extensions Modified:
No

Preferences Persisted To Normal Profile:
No

Cleanup:
Temporary test environment removed / retained for investigation
```

---

## Incident Prevention Principle

目的は、

**Kaiの検証によって、ユーザーが普段使っているBlenderの設定・Repository・Add-on / Extension環境を失わないこと**

である。

テスト都合でユーザー環境を初期化しない。

「テスト環境をユーザー環境へ近づける」のではなく、

**ユーザー環境を複製・隔離してテストする**

方向を優先する。

---

# Existing Manual Installation

An older manually installed Kai package may conflict with the Repository version.

When testing migration from manual installation:

- Disable the old manually installed version first.
- Remove it if necessary.
- Restart Blender when class registration state is uncertain.
- Then install the Repository version.

Do not treat duplicate class registration errors as a defect in the new package until an old installation has been ruled out.

Automatic migration from arbitrary manually installed historical builds is not guaranteed.

---

# Reference Skeleton Rules

Kai's Reference Skeleton is the source of truth for rig generation.

Required mappings:

```text
Hip
Chest
Head
```

Optional mappings include:

```text
Spine
Neck
Shoulder_L
Shoulder_R
```

Current supported variable chains include:

```text
Spine1-Spine6
Neck1-Neck3
```

Do not reintroduce assumptions that fixed Spine or Neck counts always exist.

Head generation must continue to work when no Neck bone is present.

Chest logic must continue to work when no intermediate Spine bone is present.

Shoulder mappings must remain optional.

---

# Mapping and Prefix Safety

Mapped source bone names may be:

- Unprefixed
- Mixamo-prefixed
- Custom-prefixed
- Custom bone names

Do not blindly concatenate prefixes onto saved Mapping names.

Kai previously had a bug that produced names such as:

```text
mixamorig1:mixamorig1:Head
```

Use the existing prefix-safe source bone resolution logic.

When adding new retarget/mapping code, reuse shared resolver functions rather than implementing independent prefix handling.

---

# Retarget Rules

Kai supports the following Retarget Bake rotation outputs:

```text
Quaternion
Euler
Target Original
```

Quaternion output must preserve quaternion continuity and avoid unnecessary sign flips between frames.

`Target Original` should preserve the original rotation mode of each target controller.

Do not globally force all controllers to XYZ Euler during retarget/reconnect operations.

---

# Rebuild Rig Safety

`Rebuild Rig` performs:

```text
Reset Generated Rig
Generate Rig
```

Before destructive reset operations:

- Validate required Mapping bones.
- Warn about missing optional Mapping bones.
- Detect hierarchy changes when possible.
- Detect `connected` state changes when possible.

If required Mapping data is invalid, stop before deleting the existing generated rig.

Generated rig cleanup must preserve:

- Reference Skeleton
- User-owned bones
- Saved `kai_*` Mapping data

Only Kai-generated data should be removed.

---

# Reference Templates

Current templates include:

```text
Humanoid Basic
Humanoid Fingers
```

Template changes should preserve validation and predictable mapping behavior.

Future templates may include quadrupeds or additional appendages.

Do not hard-code humanoid assumptions into generic template infrastructure unless the logic is explicitly humanoid-only.

---

# Modular Controller Direction

Future Eye / Facial / additional controller systems should preferably be designed as optional modules.

Avoid tightly coupling optional facial systems to the core humanoid rig generator when a modular attachment design is possible.

Current direction:

```text
Core Mixamo Rig Kai
├─ Reference Skeleton
├─ Body Control Rig
├─ Eye Controller Module
├─ Facial Controller Module
└─ Future optional modules
```

---

# Code Change Policy

Prefer minimal, targeted changes.

When fixing bugs:

1. Identify the actual cause.
2. Reuse existing helpers where possible.
3. Avoid unrelated refactors.
4. Preserve compatibility with existing Kai rigs where practical.
5. Document behavior changes.

Do not silently rename public properties, saved Mapping keys, bone names, operators, or Extension IDs without migration consideration.

---

# Testing Expectations

When modifying rig generation:

Test at least:

```text
Standard Mixamo skeleton
Reference Mapping workflow
No Neck
1 Neck
Multiple Neck bones
Minimal Spine configuration
Multiple Spine bones
Optional Shoulder present
Optional Shoulder absent
```

When modifying retargeting:

Test:

```text
Quaternion
Euler
Target Original
Prefixed source names
Unprefixed source names
Different source/mapping prefixes
Custom Head / Neck mappings
```

When modifying Rebuild Rig:

Test:

```text
Normal rebuild
Missing required mapping
Missing optional mapping
Hierarchy changes
Connected-state changes
```

---

# Git Safety

Before committing:

```bash
git status
git diff
```

Check for:

- Generated ZIP files accidentally staged in the development repository
- Cache files
- `.vs/`
- Temporary test data
- Unrelated changes
- Version mismatch

Do not commit local IDE/session caches.

---

# Release Checklist

Before declaring a Kai release complete:

- [ ] Correct branch is `mixamorig-kai`
- [ ] Working tree reviewed
- [ ] Manifest version updated
- [ ] `bl_info` version updated
- [ ] README changelog updated
- [ ] Extension build succeeds
- [ ] Package contents inspected
- [ ] Development files excluded
- [ ] SHA-256 calculated
- [ ] Release tag points to correct Kai commit
- [ ] GitHub Release target is correct
- [ ] GitHub Release Asset matches official ZIP
- [ ] Release Asset re-download hash verified
- [ ] ZIP copied unchanged to `blender-extensions/docs/`
- [ ] Repository index regenerated with Blender CLI
- [ ] Panda Tool remains in repository
- [ ] Kai appears in repository
- [ ] GitHub Pages deployment verified
- [ ] Blender 4.2.23 LTS Sync / Install / Enable test passes
- [ ] Blender 5.1.1 Sync / Install / Enable test passes
- [ ] Final commits pushed
- [ ] Final commit SHAs reported

---

# Final Report Format

After release or repository work, report:

## Mixamo Rig Kai

```text
Branch:
Commit:
Tag:
Release:
Extension Version:
ZIP:
ZIP Size:
SHA-256:
```

## Extension Repository

```text
Files changed:
Index result:
README result:
Commit:
Push:
Published endpoint:
```

## Blender Verification

```text
Blender 4.2.23 LTS
Repository Sync:
Discovery:
Install:
Enable:
UI:
Result:

Blender 5.1.1
Repository Sync:
Discovery:
Install:
Enable:
UI:
Result:
```

Report any untested scenario explicitly instead of assuming success.

---

# Guiding Principle

Mixamo Rig Kai is used in production animation workflows.

Prioritize:

```text
Predictability
Compatibility
Recoverability
Clear validation
Minimal destructive behavior
```

A successful operation is not merely one that runs without an exception. It should also preserve the user's rig, mappings, animation data, and ability to recover or rebuild safely.
