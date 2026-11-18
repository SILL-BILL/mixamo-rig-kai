# Mixamo Rig Kai 0.6.9 — Facial review and verification

Date: 2026-11-18 (Asia/Tokyo)

## 結論

受領コードの方針（改名で再生成しない、共有ラベルを保護する）は妥当です。
ただし、受領HEADのままでは共有ラベルの改名で KeyError が発生し、
3つの検証バージョンすべてで既存テストが停止しました。
追加修正後は、対象のP2修正について次の検証候補に進める状態です。
公開・配布・本番制作データ全般の安全性を保証するリリース判定ではありません。

## 作業対象と保護

- Source branch: codex/facial-rename-label-safety-2026-11-18
- Source HEAD: 92dd0a3be10b48fe36ee4c7d2e2937b9263afb3f
- Kai base: d0f5e0918a5273d04733ff5499b65003de18f20b
- 指定HEADがKai baseの子孫であることを確認しました。
- 元作業場所: D:/dev-blender-addon/mixamo-rig-kai
- 元作業ブランチ: mixamorig-kai（変更なし）
- 検証用worktree: C:/Users/lost5/.codex/visualizations/2026/11/18/01a1ed4a-443f-7760-a394-44fade92cb50/kai-069
- 検証用worktreeは指定HEADのdetached checkoutです。追加修正は未コミットです。
- main、タグ、GitHub Release、Extension Repositoryは変更していません。
- Commit / Push: 実行していません。
- Release ZIP: 作成していません。

## 受領コードの独立レビュー

1. 改名時に全Face再生成を除去した点は適切です。
   ただし、ラベル生成関数は channel_id を受け取る一方、改名側は id を持つ
   channel辞書をそのまま渡していました。共有ラベルのコピーと欠落ラベルの再作成で
   KeyError: 'channel_id' が発生します。既存追加テスト自体はこの失敗を正しく検出しました。
2. 他Armature Objectの custom_shape 参照を確認する削除保護は適切です。
   ラベル参照をBone削除前に収集する変更も必要な修正です。
3. Armature Dataを共有する複製では、Boneと定義JSONも共有されています。
   ラベルだけを保護しても、Custom/Face削除や再生成による共有Boneの変更を防げません。
4. TextのデータはTextCurveであり、RNA識別子を文字列 Curve と完全一致させる
   従来条件では、不要になったFONTデータを削除できません。

## 追加修正

- ラベル生成に渡す辞書を channel_id / display_name の契約へ合わせました。
- 別Armature Objectとデータを共有している場合、Custom追加・改名・削除、
  Face生成・再生成・削除を、変更前にRuntimeErrorで拒否します。
  操作メッセージはArmature Dataの単独化を案内します。
- Operatorはエラーを報告してCANCELLEDを返します。
  Python bpy.ops経由ではERROR報告によりRuntimeErrorとして観測されます。
- Armature Dataは自動でコピーしません。意図しない共有解除を避けています。
- TextCurveを含むCurve型で未使用データを判定し、生成ラベルと一緒に削除します。
- 共有Textオブジェクトのコピーと、別オブジェクトと共有するTextデータのコピーを検証しました。
- READMEに0.6.9の変更内容と共有データに対する操作制約を記載しました。

## テストコードの補強

既存 tools/test_kai_facial.py はそのまま保持し、専用の安全性テストを追加しました。
既存テストはActionの同一性を見ますが、キーフレームの中身や別フレームの評価、
リンク複製、欠落ラベル、繰り返し時の未使用Curveまではカバーしていませんでした。

tools/test_kai_facial_safety.py の16テスト:

1. 複数Customと既存Faceのポーズ、Action、キーフレーム座標・補間、
   Bone識別子、Driver識別子・式、Mappingの改名前後比較
2. Face Moduleが未生成の状態での定義改名
3. 欠落Textラベルの再作成とBone識別子の維持
4. 通常のObject Duplicate（独立Armature Data）のラベル改名分離
5. AのCustom削除でBのBone・ラベルを保持
6. BのFace Module削除とObject削除でAを保持
7. AのFace再生成でBの共有ラベルを保持し、最後の利用者の削除で後片付け
8. リンク複製で共有Bone・定義の編集を拒否
9. Object.copy()だけでArmature Dataを共有する場合の拒否
10. リンク複製後にデータを単独化すれば改名可能
11. 共有データに対する5種のUI Operatorのエラーと無変更
12. 複製Objectだけを削除してもAが残り、後のModule削除で共有ラベルを回収
13. 別Text Objectと共有するCurveデータの改名時コピー
14. 改名・再生成の繰り返しでラベル数とCurve数が増殖しない
15. Rig Object / Armature Dataの改名後も生きた参照からラベルを後片付け
16. 保存・再読み込み後もA/Bの名前とラベルを分離して維持

## Blender検証結果

| Blender | 受領HEADの既存スイート | 修正後の既存チェック | 追加テスト | 最終失敗 / エラー / スキップ |
| --- | --- | --- | --- | --- |
| 5.2.3 LTS | 350チェック通過後KeyErrorで停止 | 719成功 | 16成功 | 0 / 0 / 0 |
| 5.1.1 | 350チェック通過後KeyErrorで停止 | 719成功 | 16成功 | 0 / 0 / 0 |
| 4.2.23 LTS | 350チェック通過後KeyErrorで停止 | 719成功 | 16成功 | 0 / 0 / 0 |

既存チェックはassertion実行数、追加テストはunittestテストメソッド数です。
異なる単位のため合算してテスト件数とは扱っていません。
最終実行は合計2,157既存チェックと48追加テストが成功しました。
既存スイートはFace Mapping、Multi Mesh、None/Missing/Conflict、Custom操作、
Eye Module、Module独立削除、保存再読み込み、最終Cleanupを含みます。

実行ファイル:

- C:/Program Files/Blender Foundation/Blender 5.2/blender.exe — 5.2.3 LTS
- C:/Program Files/Blender Foundation/Blender 5.1/blender.exe — 5.1.1
- C:/Program Files/Blender Foundation/Blender 4.2/blender.exe — 4.2.23 LTS

## GUI

Blender 5.2.3 LTSを別プロセスで起動し、自動GUI操作で12項目と5つの
有効なスクリーンショットを確認しました（17チェック成功）。

- Aの改名後も0.65のスライダー値とBone識別子が維持される
- Aは A Renamed、Bは Cheek Puff のまま表示される
- AのCustom削除後もBのラベルが表示される
- BのModule / Object削除後もAの残りラベルが表示される
- 共有Armature Dataの削除操作が拒否され、BのBoneと定義が維持される
- 実際のFacial Panelのdrawをポップオーバーとして実行し、表示を確認

最終の5画像は目視でも確認しました。人間のマウス操作による受入テスト、
実制作メッシュでの外観評価、Nパネルのタブ切り替え操作は未実施です。
5.1.1 / 4.2.23のGUI検証は未実施です。

初期のGUI試行ではスクリーンショットが1x1で、別の試行ではスプラッシュが
描画を遮ったため、その画像を表示検証の証拠には使っていません。
最終試行は1600x1000のウィンドウ画像を検証し、スプラッシュを
検証対象プロセスだけにEscapeを送って閉じています。
途中のGUIテスト補助コードでは読み取り専用プロパティへの代入も修正しました。
これらはテスト手順の問題であり、最終合格数には含めていません。

## Blenderユーザー環境

Blender User Environment: Isolated
Test Environment Disposable: Yes
Existing User Repositories Modified: No
Existing Add-ons / Extensions Modified: No
Preferences Persisted To Normal Profile: No
Cleanup: Temporary test environments retained for investigation

全最終バックグラウンド実行は、事前作成した次の専用ディレクトリを使用しました。
User Resource / Config / Scripts / Extensionsが全て専用ルート内であることを起動後に検査し、
通常APPDATA配下を検証ルートとして使用しないようにしています。

QAルート:
C:/Users/lost5/.codex/visualizations/2026/11/18/01a1ed4a-443f-7760-a394-44fade92cb50/facial-069-qa

| 実行 | User Config Path | User Scripts Path | Repository Count Before / After |
| --- | --- | --- | --- |
| Full 5.2 | QA/verified-full-5.2/config | QA/verified-full-5.2/scripts | 3 / 3 |
| Safety 5.2 | QA/verified-safety-5.2/config | QA/verified-safety-5.2/scripts | 3 / 3 |
| Full 5.1 | QA/verified-full-5.1/config | QA/verified-full-5.1/scripts | 3 / 3 |
| Safety 5.1 | QA/verified-safety-5.1/config | QA/verified-safety-5.1/scripts | 3 / 3 |
| Full 4.2 | QA/verified-full-4.2/config | QA/verified-full-4.2/scripts | 3 / 3 |
| Safety 4.2 | QA/verified-safety-4.2/config | QA/verified-safety-4.2/scripts | 3 / 3 |
| GUI 5.2 | QA/gui-reviewed-5.2-profile/config | QA/gui-reviewed-5.2-profile/scripts | 3 / 3 |

QA/は上記QAルートを表します。実際の絶対パスは各run-result.json / gui-result.jsonにも記録しました。
Installed Kai Version Before / After: None / None（インストールせず、ソース0.6.9を一時登録し、
バックグラウンドテストでは解除。GUIはプロセス終了。Preferences保存なし）。
Repository Sync / Discovery / Install: 今回の対象外のため未実施です。

隔離方式の公式資料:
https://docs.blender.org/manual/en/latest/advanced/blender_directory_layout.html
https://docs.blender.org/manual/en/3.6/advanced/command_line/arguments.html

## 制約・残課題

- 共有Armature DataのBone / 定義を独立に編集する機能は提供しません。先に単独化が必要です。
- Eye Module、Body Rebuild等、今回のFace以外の共有Armature編集仕様は変更していません。
- Mappingデータ自体がArmature Dataに保存される既存仕様も変更していません。
- 改名に対するポーズ保持を保証しています。従来のGenerate / Regenerate（Custom追加・削除から
  呼ばれる場合を含む）の、キー未設定コントローラーのポーズ初期化は今回変更していません。
- 共有Actionや共有Mesh / Shape Keyを持つ複製を、独立したアニメーション用キャラクターへ
  自動変換する機能ではありません。
- 任意のデータ破損、リンクライブラリOverride、多数の実制作キャラクター、
  人手のUndo/Redo、実制作ファイルでの受入テストは未実施です。
- 配布ZIP作成・Install・Repository公開・配信後検証は未実施です。
- 今回の2件を修正した検証候補としては合格です。上記制約を明示し、実制作コピーで
  人手の受入確認を行ってから公開を判断してください。

## Version

Version Before: 0.6.9（受領修正コード）
Version After: 0.6.9
Version Bumped: No
Reason: 今回は0.6.9を維持するというユーザー指定を優先しました。
blender_manifest.toml / bl_infoは一致しています。
0.6.9の異なるZIPは作成・配布していません。

## 成果物

- kai_facial.py: 追加のRuntime安全性修正
- README.md: 0.6.9の変更内容と共有データ制約
- tools/test_kai_facial_safety.py: 16追加テスト
- tools/run_kai_facial_isolated.py: 環境検証と結果記録
- tools/test_kai_facial_gui.py: Windows用隔離GUIスモークテスト
- analysis/facial_069_review_2026-11-18.md: 本レポート

検証ログ・環境JSON・画像はQAルートへ保持しました。
追加差分のみを適用するパッチはQA/facial-0.6.9-followup.patchです。
指定HEAD 92dd0a3 に対するパッチで、mainや0.6.8へ直接適用するものではありません。
