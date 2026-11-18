# Mixamo Rig Kai 0.6.10 — acceptance and Panda Factory test data

Date: 2026-11-18 (Asia/Tokyo)

## Result

Panda Factoryの共通リソース管理方針をAGENTS.mdとtools/VALIDATION.mdへ反映しました。
Drive原本の予定保存先は既存の panda-factory/test-data/blender/ です。
Driveアップロード、上書き、Notion登録、DB作成、schema変更は行っていません。
Drive接続での保存先確認も今回行っていません（ユーザー指定の既存パスを予定先として記録）。

| Blender | Standard fixture copies | GUI acceptance checks | Final failures |
| --- | --- | --- | --- |
| 4.5.15 LTS | 7/7 success | 49/49 success | 0 |
| 5.2.3 LTS | 7/7 success | 49/49 success | 0 |

以前の719 Facialチェック、P2 16テスト、Core 16テストの記録は保持しています。
今回それらのスイートは変更・再実行していません。Runtimeと既存テストに変更がないため、
新しい標準Fixtureと不足していたUndo/Redo受入検証に絞りました。

## Acceptance coverage

インストール済み0.6.10の隔離GUIで、標準原本をコピーして実行しました。

- 改名でBoneを再生成せず、0.65のポーズ、Actionキー、Mappingを保持
- 改名のUndoで定義・Textを復元し、Redo後も複製BのTextを維持
- Custom削除のUndo/Redoで定義、Bone、Mapping、Textを復元/削除し、Bを保護
- Custom追加のUndo/Redoで追加定義、Bone、Textを復元/削除
- 新規accepted-copy.blendへの保存・再読込で定義、Mapping、Actionキー、A/BのTextを維持
- 共有Armature Dataの改名・削除を拒否し、定義とラベルを維持
- 標準原本のSHA-256が実行前後で同一

OperatorをEXEC_DEFAULTのnative undo flag=Trueで実行し、Blenderの実際のed.undo/redoを使っています。
履歴初期化のため最初にundo_pushを1回使用しました。Operator後の独自のundo_pushは行っていません。
自動GUI操作であり、人間のマウスによるCtrl-Z/Ctrl-Shift-Z受入テストとは区別しています。
キー未設定のGenerate/Regenerate時ポーズ初期化は今回変更していません。

## Local staging and Drive registration candidates

以下は登録待ちの一時保管であり、永続的な保管先ではありません。

Pending root:
C:/Users/lost5/.codex/visualizations/2026/11/18/01a1ed4a-443f-7760-a394-44fade92cb50/kai-0610-qa/drive-pending-2026-11-18

標準.blend原本は上記 originals-r2/、画像は evidence/ にあります。
全件の絶対パス・用途・size・SHA-256・生成元・予定保存先は以下に記録しました:

- DRIVE_REGISTRATION_PENDING.md
- drive-registration-inventory.csv
- drive-registration-inventory.json
- originals-r2/fixture-manifest.json

予定保存先は全件 panda-factory/test-data/blender/、状態は pending_upload_not_authorized です。
ファイル名を変えて既存Driveデータへ上書きしたり、新しい保存先フォルダーを作ったりしていません。

| Filename | Purpose | Local subdirectory |
| --- | --- | --- |
| kai-v0610-reference-basic.blend | Humanoid Basic生成・Rebuild | originals-r2/ |
| kai-v0610-reference-fingers.blend | Fingers生成・Rebuild | originals-r2/ |
| kai-v0610-reference-minimal.blend | Spine/Neck/Shoulderなし | originals-r2/ |
| kai-v0610-reference-multichain.blend | 6 Spine / 3 Neck | originals-r2/ |
| kai-v0610-retarget-source.blend | prefixed source Action、1-12 frame | originals-r2/ |
| kai-v0610-facial-independent.blend | ポーズ・キー付きAと独立Armature B、共有Text | originals-r2/ |
| kai-v0610-facial-linked.blend | Armature Data共有時の操作拒否 | originals-r2/ |
| kai-v0610-acceptance-blender-4.5.15.png | 4.5のUndo/Redo後のGUI証拠 | evidence/ |
| kai-v0610-acceptance-blender-5.2.3.png | 5.2のUndo/Redo後のGUI証拠 | evidence/ |

標準原本は4.5.15で合成データから生成し、両バージョンでコピーを検証しました。
Facial fixtureには4頂点の実メッシュと実際に形状を変えるShape Keysを含め、
Driver出力0.65も確認しました。外部.blend Libraryへの依存はありません。
素材をローカル化したのは生成データのメモリ内だけで、製品lib/cs.blendは変更していません。
FBXは生成していません。Retarget用ソースは.blendで用意しています。
画像は概観の証拠であり、ラベル本文・データ保持の判定はプログラムによる検査も使っています。

## Temporary artifacts

Pending root内のacceptance-r2-4.5/とacceptance-r2-5.2/にはinputコピー、
linked-inputコピー、accepted-copy.blend、結果JSON、元スクリーンショットがあります。
fixture-audit-4.5/とfixture-audit-5.2/にも検証コピーがあります。
これらは標準原本のアップロード候補と区別してinventory JSONに記録しました。
初回失敗時のpartial originals/、acceptance-4.5/、acceptance-5.2/とログも
調査用の一時データとして保持し、登録候補には含めていません。
既存データの削除は行っていません。

## Notion

Drive保存が未実施のため、台帳の取得・登録・schema確認/変更は行っていません。
保存完了後は既存「Panda Factory｜テストデータ台帳」を使います。
新DBは作成せず、必要なschema/選択肢の変更は実施前に報告します。

## Source changes

- AGENTS.md — 共通リソース管理方針、Commit前の3チェックを追加
- tools/VALIDATION.md — 原本・一時データの区別と生成・検証手順
- tools/generate_kai_test_data.py — 原本7件の生成、外部依存除去、manifest出力
- tools/validate_kai_test_data.py — 両バージョンでの原本コピー検証
- tools/test_kai_acceptance_gui.py — native Undo/Redoと保存再読込の自動受入検証
- tools/build_kai_test_data_inventory.py — ローカル一覧のみ作成、外部更新なし
- analysis/test_data_acceptance_0610_2026-11-18.md — 本報告

Runtime、製品素材、Manifest、bl_info、README、.gitignoreは今回変更していません。
Version Before: 0.6.10
Version After: 0.6.10
Version Bumped: No
Reason: 開発用テスト・生成スクリプトと手順のみ。Runtime/同梱製品素材/検証ZIPは変更なし。

## Diagnostics and safety

最初のgeneratorは外部Libraryが残ることを検出して停止しました。
製品ファイルを変更せず全Library依存を生成データ内でlocalizeし、新しい出力先へ生成し直しています。
初回GUIテストはファイル読込直後の無効なContextで停止し、4.5終了時に
EXCEPTION_ACCESS_VIOLATIONも発生しました。読込と操作を別GUIイベントへ分離し、
新しいWindow/Area contextを使うテスト補助処理へ修正しました。
最終実行は両バージョンで49チェック成功し、正常終了しています。Runtime修正は不要でした。

Blender User Environment: Isolated
Existing User Repositories Modified: No
Existing Add-ons / Extensions Modified: No
Preferences Persisted To Normal Profile: No
Cleanup: Temporary test environment and pending data retained

User Config Path:
QA/extension-4.5/config
QA/extension-5.2/config
QA/fixture-audit-4.5-profile/config
QA/fixture-audit-5.2-profile/config
QA/fixture-generation-r2-profile/config

User Scripts Path: 各profile内のscripts/
Repository Count Before / After: GUI 4/4、fixture audit 3/3
Installed Kai Version Before / After: GUI 0.6.10/0.6.10、auditはソース一時登録
Test Environment Disposable: Yes

QAは上記Pending rootの親kai-0610-qaを表します。
実際の絶対パスは各run-result.jsonとacceptance-result.jsonへ記録しています。
通常ユーザー環境や制作データを検証に使用していません。

## Git checks

作業開始時と完了前に以下を確認しました:

```text
git status --short
git diff --cached --name-only
git diff --cached --stat
```

ステージ領域は空です。テストblend、FBX、ZIP、画像、ログは新規ステージされていません。
lib/cs.blendと.gitignoreの差分はありません。
元のmixamorig-kai worktreeは変更せず、既存修正worktreeに開発用差分を保持しています。
Commit / Push / Tag / Release / Extension Repository更新は行っていません。

## Remaining limits

- Drive登録とNotion台帳登録は未実施です。永続保管の完了とは扱いません。
- 保存先Drive folder IDや既存台帳schemaは未確認です。
- FBXファイルの生成・読み書き、人手のクリック、実制作データ、他OSは未検証です。
- 初回のテスト補助コード失敗ログは残してあります。最終成功と区別してください。
