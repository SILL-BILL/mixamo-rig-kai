# Custom Mixamo Rig フェイシャルコントローラ解析

## 0. 解析対象と確度

- 対象ファイル: `D:\3dmodel\3dmodel-zzz\x01-Zhao\Zhao-001\Zhao.master.blend`
- ファイルサイズ: 3,534,077 bytes
- 更新日時: 2026-09-13 17:09:27 JST
- SHA-256: `DDDB84706C5B19733463C1809B983B9299B805C702027AE5B9DBBBB172D57A45`
- 読み取り環境: Blender 5.1.1 / `--factory-startup --background`
- 解析方法: Blender Data API による Bone、Bone Collection、Pose Constraint、Driver、Shape Key、Action/NLA の静的追跡

依頼文以外の添付ファイルはなかったため、依頼時刻直前に更新され、指定4 Collectionをすべて含む上記ファイルを対象とした。操作感の官能評価やメッシュ変形品質は含まず、データ接続については高い確度、名称から推測する用途については推定として記載する。

## 1. Executive Summary

このリグは、Face と Eye が実際に別系統になっている。

- **Face**: `Kai_Humanoid_Fingers` 内の操作 Bone から、`M_Zhao_Face` の Shape Key へ直接 Driver 接続する方式。顔メッシュには79 Shape Key（Basisを含む）があり、45個が操作 Bone で駆動される。Face用の中間演算 Bone はほぼなく、`FaceCtrlRigRoot` の6 Boneは配置用Root/Anchorである。
- **Eye**: `EyeTarget_L/R` をターゲットに `Eye_L/R` をIKで回し、その結果をReNimの転送用Bone/Driver/Copy Transformsを経由してキャラクター本体 `Root_Zhao` の眼球Boneへ渡す。Shape Keyとは接続していない。
- **AIUEO**: `Face_Mouth_A/I/U/E/O` のLocal X（0..1）を同名Shape Keyへ1:1接続するだけで、PandaLipと機能契約がほぼ同一。ただし現在のPandaLipはBone名とコントローラ構造を厳密に検証するため、この埋め込みBoneをそのままPandaLip入力にはできない。
- **Capture**: 稼働中のCapture専用Driver、Action、NLAは確認できない。空のActionが2個あるだけで、33個の未接続Shape Keyの用途はデータだけでは確定できない。

採用上の最大の長所は、Faceの操作値が正規化され、Local Spaceの単純なDriverで追跡しやすいこと。最大の問題は、Head追従切替が実際に依存関係サイクルを起こしていること、全ControllerがDeform Boneかつ不要チャンネルも未Lockであること、右口角だけLimit Locationが欠落していること、未接続UIが残っていることである。

## 2. Architecture

### Face

```text
Face_ControlRigRoot
├─ Brow / Eyelid / Mouth Anchor
│  └─ User Controller の Local Location
│       └─ Scripted Driver（45本、全て LOCAL_SPACE）
│            └─ M_Zhao_Face の Shape Key value（0..1）
└─ Face_BaseMenuRoot
   ├─ AIUEO Controller ── Driver ── A/I/U/E/O Shape Key
   └─ Head Follow Switch ── Driver ── Root の Child Of Influence
```

Face Shape Key Driverは全45本が `SCRIPTED`、Transform参照は延べ61個、全て `LOCAL_SPACE`。F-Curve Modifier、補間カーブ、Driver側の明示Clampはない。操作範囲は主に `Limit Location`、出力範囲はShape Keyの `slider_min=0 / slider_max=1` に依存する。

### Eye

```text
EyeTargetRoot（両目ターゲット親）
├─ EyeTarget_L ── IK ── Kai Eye_L
└─ EyeTarget_R ── IK ── Kai Eye_R
                         │
                         └─ ReNim転送Driver（Location/Rotation/Scale）
                              └─ SOURCE helper
                                   └─ TARGET helper
                                        └─ Copy Transforms
                                             └─ Root_Zhao Eye_L/R
```

`EyeTargetRoot` は `EyeCenterPos` を `Damped Track` し、左右ターゲットをまとめて保持する。まぶたShape Keyとの連動はなく、眼球目線とFace側のまぶた表情は完全に別入力である。

## 3. Eye Module

### Bone構成

| Bone | Collection | 分類 | Parent | Children | Custom Shape | 主な設定 |
|---|---|---|---|---|---|---|
| `EyeTargetRoot` | `CTRL_Eye` | User / Group Controller | `Head` | `EyeTarget_L/R` | `cs_eyeRoot` | `EyeCenterPos`へDamped Track、-Z Track |
| `EyeTarget_L` | `CTRL_Eye` | User Controller | `EyeTargetRoot` | — | `cs_eyeTarget` | Local Z=0のLimit Location |
| `EyeTarget_R` | `CTRL_Eye` | User Controller | `EyeTargetRoot` | — | `cs_eyeTarget` | Local Z=0のLimit Location |
| `EyeCenterPos` | `Eye` | Internal Anchor | `Head` | — | — | Target rootの注視基準 |
| `Eye_L` | `Eye` | Output / Deform | `Head` | — | — | `EyeTarget_L`へのIK |
| `Eye_R` | `Eye` | Output / Deform | `Head` | — | — | `EyeTarget_R`へのIK |

全6 Boneは `use_deform=True`、Transform Lockは全チャンネル解除、Inherit Scaleは `FULL`。Target L/RのLimitはZだけを0に固定し、X/Yは自由。`use_transform_limit=False` のため、Transform入力そのものを制限するFace側の設定とは統一されていない。

### 操作

| Controller | 操作 | 結果 |
|---|---|---|
| `EyeTargetRoot` | Location | 左右ターゲットを一括移動し、両目の目線をまとめて変更 |
| `EyeTarget_L` | Local X/Y | 左目だけを個別にAim |
| `EyeTarget_R` | Local X/Y | 右目だけを個別にAim |

RootをHead子にすることで頭部に追従しつつ、左右ターゲットを個別調整できる。IKの軸方向・最終的な画面上の上下左右はBone rollと表示視点に依存するため、静的解析では「Local X+ = 視線右」のような画面方向までは断定しない。

### 本体Rigへの転送

各 `Kai_Humanoid_Fingers.Eye_L/R` のLocation 3軸、Euler Rotation 3軸、Scale 3軸をReNimのDriverが読み、`Root_Zhao` の `SOURCE_Bone.044_Eye_L` / `SOURCE_Bone.045_Eye_R` に書く（左右合計18本）。子の `TARGET_*` を `Root_Zhao.Eye_L/R` が `COPY_TRANSFORMS` し、Owner `LOCAL` / Target `LOCAL_WITH_PARENT` / Mix `BEFORE` で適用する。左右のCopy TransformsのMix Modeにも各1本のReNim Driverがある。Helper表示制御Driverは4本。

`Root_Zhao.Eye_L/R` の子には `EyeLight_L/R` → `EyeLight_End_L/R` があり、眼球回転に追従する。名前上はハイライト系だが、Face側の `Face_EyeHighLight` との接続は見つからない。

### Eye評価

- 両目一括＋左右個別という操作モデルは **KEEP**。
- EyeをFace Shape Key群から分離する境界は **KEEP**。
- ReNimの汎用転送層はこのキャラクターへの接続としては機能するが、Kai Eye Module本体へ内包するべきではなく **IMPROVE**。
- Eye Controller BoneがDeform、全Transformが未Lockなのは **IMPROVE**。
- まぶたと目線の自動連動は存在しない。必要なら将来の任意機能として検討し、Eyeコアへ必須結合しない。

## 4. Face Module

### Root / Anchor構成

| Bone | Collection | 分類 | Parent | Children | Shape / 特記事項 |
|---|---|---|---|---|---|
| `Face_ControlRigRoot` | `FaceCtrlRigRoot` | Root | — | 全6系統Root | `cs_square`、HeadへのChild Of |
| `Face_EyeRoot_L/R` | `FaceCtrlRigRoot` | Anchor | Root | EyeExp、EyeMove | `cs_square` |
| `Face_BrowRoot_L/R` | `FaceCtrlRigRoot` | Anchor | Root | BrowUpDown | `cs_square` |
| `Face_MouthRoot` | `FaceCtrlRigRoot` | Anchor | Root | MouthPosition | `cs_square` |
| `Face_BaseMenuRoot` | `CTRL_Face` | UI Anchor | Root | Switch、EyeScale、Highlight、AIUEO | `cs_FaceMenu` |

Root/Anchor BoneからShape KeyへのDriverはない。役割はコントローラ配置と親子変換の伝播である。`Face_BaseMenuRoot` はUI背景としての性格が強い。

### 機能別Controller

| 機能 | Controller | 使用チャンネル | 有効範囲 | Custom Shape |
|---|---|---|---|---|
| Brow | `Face_BrowUpDown_L/R` | Local Y | -1..1 | `cs_square` |
| Brow | `Face_BrowExp_L/R` | Local X/Y | 各 -1..1 | `cs_sphere` |
| Eyelid | `Face_EyeClose_L/R` | Local Y | -1..0 | `cs_square` |
| Eyelid | `Face_EyeCloseToSmile_L` | Local X | 0..1 | `cs_switch_Arrow` |
| Eyelid | `Face_EyeCloseToSmile_R` | Local X | -1..0 | `cs_switch_Arrow` |
| Eyelid / Eye expression | `Face_EyeExp_L/R` | Local X/Y | 各 -1..1 | `cs_sphere` |
| Eyelid / Outer corner | `Face_EyeMove_L/R` | Local Y | -0.5..0.5 | `cs_circle` |
| Mouth global | `Face_MouthPosition` | Local X/Y | 各 -1..1 | `cs_circle` |
| Mouth corner | `Face_MouthCorner_L` | Local X/Y | 各 -1..1 | `cs_sphere` |
| Mouth corner | `Face_MouthCorner_R` | Local X/Y | 制限なし | `cs_sphere` |
| AIUEO | `Face_Mouth_A/I/U/E/O` | Local X | 0..1 | `cs_cube` |
| Attachment | `Face_TrackFaceSwitch_RigMenu` | Local Y | 0..2 | `cs_circle_025` |
| 未接続UI | `Face_EyeScale` | Local X | 0..1 | `cs_cube` |
| 未接続UI | `Face_EyeHighLight` | Local X | 0..1 | `cs_cube` |

`Face_MouthPosition` にはLocal Z回転 ±15° のLimitもあるが、そのRotationを読むDriver/Constraintはない。`Face_MouthCorner_R` だけLimit Locationがなく、左右非対称である。

### Transform / Propertyの共通状態

- 対象Face BoneにはCustom Propertyなし。
- 全BoneのTransform LockはLocation/Rotation/Scaleとも解除。
- 実際に使うチャンネルはLimit Locationで制限しているが、Rotation/Scaleへの誤キーは防止されない。
- `Face_TrackFaceSwitch_RigMenu`、`Face_EyeScale`、`Face_EyeHighLight`、AIUEO 5 BoneはInherit Scale `AVERAGE`。その他は `FULL`。
- 対象30 Boneすべてが `use_deform=True`。制御専用Boneとしては不要。
- Rotation Modeは全てQuaternionだが、Face出力DriverはLocationだけを読む。

## 5. AIUEO

### 現行接続

| Bone | 入力 | Shape Key | Expression | 範囲 |
|---|---|---|---|---|
| `Face_Mouth_A` | Local X | `A` | `var + 0.0` | 0..1 |
| `Face_Mouth_I` | Local X | `I` | `var + 0.0` | 0..1 |
| `Face_Mouth_U` | Local X | `U` | `var + 0.0` | 0..1 |
| `Face_Mouth_E` | Local X | `E` | `var + 0.0` | 0..1 |
| `Face_Mouth_O` | Local X | `O` | `var + 0.0` | 0..1 |

中間Boneや他のFace表情への依存はなく、Faceメニューの親子配置を除けば独立している。

### PandaLipとの比較

現行PandaLipも、各 `CTRL_Lip_A/I/U/E/O` の `LOC_X` / `LOCAL_SPACE` / 0..1 を、任意Shape Keyへ単一変数の1:1 Driverで接続する。したがって**データモデルは同型**であり、AIUEO部分は **REPLACE** 候補である。

ただし現行PandaLipは次を厳密に要求する。

- 独立Armatureと `PandaLip_Root` + `CTRL_Lip_A/I/U/E/O`
- PandaLipのController識別情報と構造
- Driver変数名 `pandalip_A` 等を含む厳密なDriver signature
- 既存の異なるDriverがある場合は上書きせずConflictで停止

よって現時点の安全な置換は「既存5 Driverを削除し、独立PandaLip Controllerを作り、A/I/U/E/Oへ再Mapping」である。Kai内蔵UIを維持したい場合は、PandaLip側に任意の互換Controller ContractまたはAdapterを設計する必要があり、現状のままBone名だけ読み替えて共用はできない。

## 6. Controller操作一覧

| Controller | 操作方向 | 出力 |
|---|---|---|
| `Face_BrowUpDown_L/R` | Y+ / Y- | `Brow_Up_L/R` / `Brow_Down_L/R` |
| `Face_BrowExp_L` | X+ / X- | `Brow_Angry_L` / `Brow_Sad_L` |
| `Face_BrowExp_L` | Y+ / Y- | `Brow_Smile_L` / `Brow_Serious_L` |
| `Face_BrowExp_R` | X+ / X- | `Brow_Sad_R` / `Brow_Angry_R` |
| `Face_BrowExp_R` | Y+ / Y- | `Brow_Smile_R` / `Brow_Serious_R` |
| `Face_EyeClose_L/R` | Y- | 閉じ量。Close/Smileの合計強度 |
| `Face_EyeCloseToSmile_L` | X 0→1 | CloseからSmileへブレンド |
| `Face_EyeCloseToSmile_R` | X 0→-1 | CloseからSmileへブレンド |
| `Face_EyeExp_L` | X+ / X- | `Eyelid_Angry_L` / `Eyelid_Sad_L` |
| `Face_EyeExp_R` | X+ / X- | `Eyelid_Sad_R` / `Eyelid_Angry_R` |
| `Face_EyeExp_L/R` | Y+ / Y- | `Eyelid_Surprise_L/R` / `Eyelid_Jito_L/R` |
| `Face_EyeMove_L/R` | Y+ / Y- | `Eyelid_Squint_L/R` / `EyeOuterCorner_Down_L/R`（入力を2倍） |
| `Face_MouthPosition` | X+ / X- | `MouthLeft` / `MouthRight` |
| `Face_MouthPosition` | Y+ / Y- | `MouthUp` / `MouthDown` |
| `Face_MouthCorner_L` | X+ / X- | `Mouth_Spread_L` / `Mouth_Narrow_L` |
| `Face_MouthCorner_R` | X+ / X- | `Mouth_Narrow_R` / `Mouth_Spread_R` |
| `Face_MouthCorner_L/R` | Y+ / Y- | `Mouth_CornerUp_L/R` / `Mouth_CornerDown_L/R` |
| `Face_Mouth_A/I/U/E/O` | X+ | 対応するA/I/U/E/O Shape Key |
| `Face_TrackFaceSwitch_RigMenu` | Y 0→2 | RootのHead追従Influence 0→1 |
| `Face_EyeScale` | X+ | 接続なし |
| `Face_EyeHighLight` | X+ | 接続なし |

## 7. Driver / Shape Key対応表

全てDriver対象は `M_Zhao_Face.shape_keys.key_blocks[...].value`、Driver Typeは `SCRIPTED`、Source Objectは `Kai_Humanoid_Fingers`、Transform Spaceは `LOCAL_SPACE`。

| Source / Channel | Shape Key | Expression / Mapping |
|---|---|---|
| `Mouth_A/I/U/E/O.LOC_X` | `A/I/U/E/O` | `var + 0.0` |
| `EyeClose_L.LOC_Y`, `CloseToSmile_L.LOC_X` | `Eyelid_Close_L` | `-close * (1-toSmile)` |
| 同上 | `Eyelid_Smile_L` | `-close * toSmile` |
| `EyeClose_R.LOC_Y`, `CloseToSmile_R.LOC_X` | `Eyelid_Close_R` | `-close * (1+toSmile)` |
| 同上 | `Eyelid_Smile_R` | `-close * -toSmile` |
| `EyeExp_L.LOC_Y` | `Eyelid_Surprise_L` / `Eyelid_Jito_L` | `var*(1+close)` / `-var*(1+close)` |
| `EyeExp_R.LOC_Y` | `Eyelid_Surprise_R` / `Eyelid_Jito_R` | 同上 |
| `EyeExp_L.LOC_X` | `Eyelid_Angry_L` / `Eyelid_Sad_L` | `var*(1+close)` / `-var*(1+close)` |
| `EyeExp_R.LOC_X` | `Eyelid_Sad_R` / `Eyelid_Angry_R` | `var*(1+close)` / `-var*(1+close)` |
| `EyeMove_L/R.LOC_Y` | `Eyelid_Squint_L/R` | `var*2*(1+close)` |
| 同上 | `EyeOuterCorner_Down_L/R` | `-var*2*(1+close)` |
| `BrowUpDown_L/R.LOC_Y` | `Brow_Up_L/R` / `Brow_Down_L/R` | `var` / `-var` |
| `BrowExp_L.LOC_X` | `Brow_Angry_L` / `Brow_Sad_L` | `var` / `-var` |
| `BrowExp_R.LOC_X` | `Brow_Sad_R` / `Brow_Angry_R` | `var` / `-var` |
| `BrowExp_L/R.LOC_Y` | `Brow_Smile_L/R` / `Brow_Serious_L/R` | `var` / `-var` |
| `MouthPosition.LOC_X` | `MouthLeft` / `MouthRight` | `var` / `-var` |
| `MouthPosition.LOC_Y` | `MouthUp` / `MouthDown` | `var` / `-var` |
| `MouthCorner_L.LOC_X` | `Mouth_Spread_L` / `Mouth_Narrow_L` | `var` / `-var` |
| `MouthCorner_R.LOC_X` | `Mouth_Narrow_R` / `Mouth_Spread_R` | `var` / `-var` |
| `MouthCorner_L/R.LOC_Y` | `Mouth_CornerUp_L/R` / `Mouth_CornerDown_L/R` | `var` / `-var` |

正負を同じ式で出してもShape Key valueが0..1に制限されるため、反対側出力は0にClampされる。これは簡潔だが、Driver式だけを見てもClampが分からない暗黙仕様である。

### Driver上の不整合

`Eyelid_Sad_L/R` の `close` 変数だけは `Face_EyeClose_L/R.LOC_X` を読んでいる。他のまぶたDriverは `LOC_Y` を読み、Close BoneのXはLimitで0固定なので、Sadだけ閉じ量による減衰が実質働かない。左右とも同じ不整合であり、意図が他と同じなら `LOC_Y` の誤設定と考えられる。

### 未接続Shape Key

Basis以外の78個中33個はDriverなし。主なものは、左右統合版（`Mouth_Smile`、`Eyelid_Close`、`Brow_Up`等）、`Mouth_Open`、`Mouth_Shout`、`Mouth_Smirk*`、`I2/E2/E3`、`Eye_Squint_L/R`、`Eyelid_Serious_L/R`。これらは手動値、Capture入力候補、旧仕様の残骸のいずれかだが、接続データがないため断定しない。

## 8. ConstraintとDependencies

### Constraint一覧

| Owner | Type | Target / Subtarget | Space / Axis | 備考 |
|---|---|---|---|---|
| `EyeTargetRoot` | Damped Track | self / `EyeCenterPos` | Track `-Z` | 両目ターゲットRootの向き |
| `EyeTarget_L/R` | Limit Location | — | Owner Local | Z=0、X/Y自由 |
| Kai `Eye_L/R` | IK | self / `EyeTarget_L/R` | World | 眼球Aim |
| `Face_ControlRigRoot` | Child Of | self / `Head` | Owner Pose / Target World | InfluenceをSwitch Driverで0..1 |
| Face操作Bone（右口角を除く） | Limit Location | — | Owner Local | UI操作域を正規化 |
| `Face_MouthPosition` | Limit Rotation | — | Owner Local | Z ±15°だが出力接続なし |
| Root_Zhao `Eye_L/R` | Copy Transforms | self / ReNim `TARGET_*` | Local / Local With Parent | Mix `BEFORE` |

### 依存関係

| 系統 | 依存先 | 結合度 |
|---|---|---|
| Face Controller | `Kai_Humanoid_Fingers` のBone名、`M_Zhao_Face` Shape Key名 | 強い。DriverにObject/Bone/Keyを直接保持 |
| Face Root | `Head`、子孫のFollow Switch | 強い。実際にDepsgraph cycleあり |
| Eye Controller | Kai `Head`、`EyeCenterPos`、`Eye_L/R` | 中程度 |
| Eye Output | ReNim helper、`Root_Zhao.Eye_L/R` | キャラクター固有で強い |
| AIUEO | Face menu親子と5 Shape Key | 演算上は弱い、UI階層上はFaceに内包 |
| Capture | 接続なし | 確認不能 |

Blender 5.1.1でファイル読込時、`Face_ControlRigRoot` のChild Of influenceが、同Rootの子孫 `Face_TrackFaceSwitch_RigMenu` を読むため、2件のDependency Cycleが報告された。これは推測ではなく実際のDepsgraph警告である。

## 9. KEEP / IMPROVE / REPLACE / REMOVE

| 対象 | 一次分類 | 理由 |
|---|---|---|
| Faceの2Dスライダー操作 | KEEP | 少数Controllerで正負の表情を直感的に選べる |
| Local Space 0..1正規化 | KEEP | Driver追跡、再利用、外部入力が容易 |
| 左右独立Controller | KEEP | 非対称表情を作りやすい |
| Close→Smile連続ブレンド | KEEP | 1つの閉じ量を保ったまま質感を変更できる |
| Eyeの一括Target＋左右Target | KEEP | 基本的な目線操作として分かりやすい |
| Eye / Faceモジュール分離 | KEEP | Kaiの将来構成と一致 |
| Root/Anchor配置方式 | IMPROVE | 考え方は有効だがController/内部BoneのCollection分類を明瞭化したい |
| Head Follow Switch | IMPROVE | 機能は有用だが、子孫から親Constraintを駆動してcycleを作らない構成が必要 |
| まぶた式の相互補正 | IMPROVE | 有用だがSadの参照チャンネル不整合を修正し、式を共通生成すべき |
| 右口角Controller | IMPROVE | 左右同じLimitとLockを生成・検証すべき |
| ControllerのTransform保護 | IMPROVE | 使用軸以外をLockし、Limitと二重で事故を防ぐ |
| Control BoneのDeform設定 | IMPROVE | Controller / Anchorは原則 `use_deform=False` |
| ReNim眼球転送 | IMPROVE | Adapter層として外出しし、Eye Module本体を特定転送方式から独立させる |
| AIUEO 5 Bone / Driver | REPLACE | PandaLipと同型。共通Controller ContractまたはAdapterを整備して一本化 |
| `Face_EyeScale` | REMOVE（暫定） | 入力制限とWidgetだけで出力接続なし。用途確認できれば再評価 |
| `Face_EyeHighLight` | REMOVE（暫定） | 同上。`EyeLight_*`とも接続なし |
| `Face_MouthPosition` Z回転 | REMOVE（暫定） | 制限はあるが出力なし |
| 空Action 2個 | REMOVE（暫定） | Frame 0..0、Active Action/NLAなし。由来確認後に除去 |
| 未接続の左右統合Shape Key | 要選別 | Capture互換・造形補助の可能性があり、一括削除は危険 |

## 10. Unknown / 要確認事項

1. `Face_EyeScale` と `Face_EyeHighLight` が、外部スクリプトや手動オペレーション前提なのか、単なる残骸なのか。
2. 未接続33 Shape KeyがCapture規格、手動補助、左右Shape Key作成用の中間形状のどれか。特に左右統合版を削除してよいかは造形ワークフロー確認が必要。
3. `Mouth_Open` / `Mouth_Shout` を手付けFace Moduleに含める意図があるか。現行Controllerからは操作不能。
4. `Eyelid_Sad` のClose参照がLOC_Xなのは意図か設定ミスか。周囲との一貫性からは設定ミスの可能性が高い。
5. `Face_MouthPosition` のLocal X+が画面上の左を意味するのは、アニメーター視点の命名として望ましいか。
6. Eye IKの画面方向と回転限界。静的データには眼球可動域Limitがなく、極端なTarget位置でも制限されない。
7. `Face_ControlRigRoot` のWorld/Head切替時にChild Of inverseが保たれ、アニメ中にポップしない運用になっているか。
8. Blender 4.2.23での実ファイル読込・操作再生は未実施。データ構造は一般的APIだが、今回の対象ファイルはBlender 5.1.1で検査した。
9. メッシュ変形の見た目、左右対称性、複数Shape Key同時使用時の破綻は静的解析対象外。次段階では操作クリップによる視覚QAが必要。

## 次段階へ渡す設計条件

この解析から、Kai独自Face Moduleの初期仕様検討では次を前提にできる。

- Eye、Face、Lip Input（PandaLip）を別モジュール/Adapterとして扱う。
- Face出力は、Controller Contract → 正規化チャンネル → Character Shape Key Mappingの三層に分ける。
- Driverを手書き複製せず、左右・正負・Close連動を宣言データから生成して検証する。
- Controller Boneは非Deform、使用軸以外Lock、左右同一の制約を自動テストする。
- Head FollowはRootの子孫値をRoot自身へ戻す循環を避け、Armature/Object Custom Property、独立設定Bone、または非循環のSpace Switching層へ移す。
- PandaLipはAIUEOの唯一の入力契約候補とし、Kai側はShape Key名を固定せずMappingで接続する。
