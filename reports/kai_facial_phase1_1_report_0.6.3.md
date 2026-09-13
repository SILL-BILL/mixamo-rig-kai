# Mixamo Rig Kai Facial v0.1 Phase 1.1 実装報告書

報告日: 2026-09-14

対象ブランチ: `mixamorig-kai`

Extension Version: `0.6.3`

対象Blender: 4.2.23 LTS / 5.1.1

## 1. 概要

Mixamo Rig Kai向けのEye Module / Face Moduleについて、実キャラクターでの操作レビューを反映したPhase 1.1実装を完了しました。

既存リグをそのまま複製するのではなく、現在の操作感を維持しつつ、左右差、不要Transform、Dependency Cycle、誤ったDriver参照など、解析で判明した問題を修正したKai独自のモジュールとして再構築しています。

最終調整では、実キャラクターファイル `Zhao.proto.ui.blend` で編集・確認されたController位置、カスタムシェイプ倍率、Eye Controllerのボーンカラーを生成基準へ反映しました。

## 2. Eye Module

### 実装済み機能

- 両目をまとめて移動する `EyeTargetRoot`
- 左右個別の `EyeTarget_L` / `EyeTarget_R`
- ReNimから参照可能な回転出力Bone `Eye_L` / `Eye_R`
- 両Eye出力Boneの中点へ配置される `EyeCenterPos`
- `EyeTargetRoot` から `EyeCenterPos` へのDamped Track
- 左右独立の1 Bone IK Aim
- X/Y/ZのIK Limit
- Head Bone追従
- 再生成時のController位置、Eye位置、IK Limit保持

### Head Bone指定

Eye Moduleの生成元は、選択中のPose Bone / Edit Boneではなく、UIで明示的に指定する `Head Bone` です。

- Kai Rig内のBoneから選択可能
- Reference MappingのHead設定を初期値として利用
- Object Mode / Pose Modeや現在の選択Boneに依存しない
- 未設定または存在しないBoneの場合は明確なエラーを表示

### ReNimとの責任分離

Kai Eye Moduleは `Eye_L / Eye_R` に正しい回転結果を生成するところまでを担当します。

ターゲットキャラクターのEye Boneへの転送はReNim Nodeへ委譲し、旧Direct Bone AdapterおよびEye Module UIのOutput Adapterは削除しました。

### 最新の表示基準

`Zhao.proto.ui.blend` の実機調整値を基準として、次の設定を採用しています。

| Controller | Custom Shape | Scale | 通常・選択色 | Active色 |
|---|---|---|---|---|
| `EyeTargetRoot` | `cs_square` | `(0.35, 0.12, 0.24) × Head Bone長` | Yellow `(1, 1, 0)` | Cyan `(0, 1, 1)` |
| `EyeTarget_L` | `cs_circle_025` | `(0.15, 0.15, 0.15) × Head Bone長` | Yellow `(1, 1, 0)` | Cyan `(0, 1, 1)` |
| `EyeTarget_R` | `cs_circle_025` | `(0.15, 0.15, 0.15) × Head Bone長` | Yellow `(1, 1, 0)` | Cyan `(0, 1, 1)` |

## 3. Face Module

### 実装済みController

- Brow Up / Down
- Brow Expression
- Eye Close
- Close → Smile Blend
- Eye Expression
- Eye Outer Corner / Squint
- Mouth Position
- Mouth Corner
- 左右独立操作

合計15個のFace Controllerを生成します。

### Viewport UI

- Brow領域: Green
- Eye / Eyelid領域: Red
- Mouth領域: Blue
- 各領域のRoot Frameを独立したBone Collectionとして管理
- `FaceCtrlRigRoot` からFace UI全体の移動・拡縮が可能
- `Face_EyeCloseToSmile_L/R` に `cs_switch_Arrow` を採用
- Controller位置とカスタムシェイプ倍率は `Zhao.proto.ui.blend` の実機調整値を基準化

### Driver構造

Face出力は次の流れで生成します。

```text
Controller Local Transform
→ 正規化・Clamp 0..1
→ Declarative Driver
→ Kai Facial Channel Mapping
→ Character Shape Key
```

- 左右、正負方向、Eye Close連動を共通宣言から生成
- Shape Key名を各処理へ分散して直書きしない構造
- 安定した内部Channel IDと実際のShape Key名を分離
- 複数Meshへ同一Facial Channelを出力可能
- Meshごとに存在しないShape Keyは安全にスキップ
- 既存のKai以外のDriverと競合する場合は上書きせず報告

将来のCharacter Shape Key Mapping UIおよびPhase 2 Controller Generatorへ拡張できる構造を維持しています。

## 4. Controller安全設定

Eye / FaceのControllerおよびAnchor Boneへ、以下の共通方針を適用しました。

- `use_deform = False`
- 使用するLocation軸のみ操作可能
- 未使用Location軸をLock
- 未使用RotationをLock
- ScaleをLock（Face UI全体の調整Rootを除く）
- Transform LockとLimit Locationを併用
- 左右Controllerへ同一ルールを適用

## 5. 修正した既存問題

- 右Mouth CornerだけLimit Locationが欠落する左右非対称を解消
- `Eyelid_Sad_L/R` のEye Close連動を正しいLocation軸へ統一
- Controller BoneがDeformになる状態を解消
- 不要Transformが操作可能な状態を解消
- 子孫Controllerから親RootのChild Of InfluenceをDriver制御する循環構造を廃止
- Head FollowをArmature Object Propertyから制御する非循環構造へ変更
- Eye Direct Bone Adapter依存を削除し、ReNimとの責任範囲を明確化

## 6. Phase 1対象外

以下は意図的に実装していません。

- `Face_EyeScale`
- `Face_EyeHighLight`
- Mouth Positionの未接続Z Rotation
- Capture用機能
- 未接続Shape Keyの自動利用
- AIUEOのFace Module独自固定
- Custom Shape Key Controller Generator

AIUEOはPandaLipとの共通化を前提とし、Custom Controller GeneratorはPhase 2で追加予定です。

## 7. 検証結果

### 自動回帰テスト

| 環境 | 結果 |
|---|---|
| Blender 4.2.23 LTS | PASS |
| Blender 5.1.1 | PASS |

確認項目:

- Eye / Face Module生成
- Head Bone明示指定とReference Mapping初期値
- Eye Controllerの色とカスタムシェイプ倍率
- EyeCenterPosの中点配置
- Damped TrackターゲットとTrack Axis
- 左右個別Aimと1 Bone IK
- IK Limit動作
- Controller Transform Lock / Limit
- Eye位置およびIK Limitの再生成保持
- Face Controller数、Shape Key Driver、複数Mesh Mapping
- Head Followの非循環構造
- Module削除時の生成Bone / Driverクリーンアップ

自動テスト最終出力:

```text
KAI_FACIAL_TEST_OK bones=27 drivers=43
```

### Extension Package検証

Blender公式Extension Buildで `mixamo_rig_kai-0.6.3.zip` の生成と内容検査に成功しました。

```text
ZIP Size: 206234 bytes
SHA-256: 9FFABE6C0850305372BC843019628B033D2CE06EF7BF69DA4DB333EAC89C1BD9
```

確認済み:

- Manifest Version `0.6.3`
- `bl_info` Version `(0, 6, 3)`
- `kai_facial.py` を収録
- `lib/cs.blend` を収録
- `tools/`、`AGENTS.md`、`analysis/` を除外

検証用ZIPは内容確認後に作業ツリーから削除しており、Release、Tag、Pushは行っていません。

## 8. 現在の状態

Phase 1.1として要求されたEye / Face操作、実キャラクター基準のController配置・表示調整、既知問題の修正、Blender 4.2 / 5.1互換確認まで完了しています。

次段階は、Phase 1.1の運用確認後にPhase 2として任意Shape Key用Controller Generatorを追加する予定です。Phase 2の先行実装は行っていません。
