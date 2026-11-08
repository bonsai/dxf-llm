# poc.md — Proof of Concept 計画

## 目的

**「JWW/DXF を Python + LLM で 3D/IFC 化し、自然言語で扱える」ことを最短で実証する。**
事業判断ではなく「技術的に成立するか」の検証。期間: **2〜4 週間**。

---

## スコープ（やること / やらないこと）

| やること | やらないこと |
|---|---|
| `C:\jww` のサンプル 1 枚を対象 | 大量ファイルの一括処理 |
| JWW → DXF 変換 | DWG 双方向編集 |
| 構造化 JSON + LLM 質問応答 | 完全自動の意味分類 |
| IFC 出力 → BlenderBIM で確認 | 構造計算 |
| 数量（壁長など）1 種類の自動算出 | 全数量拾い |
| プラグイン + ワークフロー 1 本 | マーケットプレイス |

---

## シナリオ（デモで見せること）

題材: `C:\jww\木造平面例.jww`（または `C:\jww\Sample.jww`）

```
① JWW2DXFConv.exe  で DXF 化
② dxf_parser プラグイン で構造化
③ LLM に「この図面の壁は何本？合計長さは？」
    → DXFQueryEngine が JSON を返し、回答を生成
④ semantic_enricher で wall/window を分類
⑤ ifc_exporter で .ifc 出力
⑥ BlenderBIM で開いて 3D 確認（スクショ）
```

---

## ワークフロー定義（PoC 版）

```yaml
# recipes/workflows/poc_dxf_to_ifc.yaml
name: poc_dxf_to_ifc
steps:
  - id: parse
    plugin: dxf_parser
    params: { encoding: cp932 }
  - id: enrich
    plugin: semantic_enricher
    depends_on: [parse]
  - id: quantity
    plugin: quantity_takeoff
    depends_on: [enrich]
  - id: export_ifc
    plugin: ifc_exporter
    depends_on: [enrich]
```

---

## 成果物（Deliverables）

- [ ] `parse → enrich → quantity → export_ifc` が通る YAML ワークフロー
- [ ] PoC 用 3 プラグイン（`semantic_enricher` / `quantity_takeoff` / `ifc_exporter`）
- [ ] LLM 質問応答デモ（`/analyze`, `/search`）
- [ ] 生成した `.ifc` と BlenderBIM のスクショ
- [ ] 再現手順書（README + 実行コマンド）

---

## 技術的検証項目（Go / No-Go）

| # | 検証項目 | Go 条件 | No-Go 時の対応 |
|---|---|---|---|
| 1 | JWW → DXF 変換 | レイヤ・文字が保持される | JWW2DXFConv オプション調整 |
| 2 | 座標・単位の整合 | mm スケールが一致 | スケール補正ステップ追加 |
| 3 | 壁芯の閉合 | 主要壁が閉ループ判定できる | トポロジ修復を強化 |
| 4 | IFC 出力 | BlenderBIM で破綻なく開く | IfcOpenShell スキーマ調整 |
| 5 | LLM 質問応答 | 壁本数・長さを正答 | 抽出ロジック or プロンプト改善 |
| 6 | ワークフロー実行 | 直列・並列ともに完走 | DAG/依存定義を見直し |

---

## 成功基準（Definition of Done）

1. 上記 YAML を 1 コマンドで実行でき、`results` が SUCCESS
2. `.ifc` が BlenderBIM で表示できる
3. LLM が「壁は N 本、総長 X mm」を正しく答える
4. 手順書どおりに第三者が再現できる

→ すべて Yes なら **MVP へ進む**。

---

## 想定リスクと対処

| リスク | 対処 |
|---|---|
| JWW レイヤ規約が不明 | サンプル複数枚を目視で突き合わせ、規約表を作る |
| DXF の座標系ズレ | 既知寸法（通り芯）でスケール検証 |
| LLM のハルシネーション | 回答は必ず `DXFQueryEngine` の JSON に根拠を限定 |
| IFC スキーマ不整合 | IFC4 で最小構成から開始 |

---

## スケジュール（目安）

| 週 | 内容 |
|---|---|
| 1 | JWW→DXF 変換、`dxf_parser` 動作確認 |
| 2 | `semantic_enricher` / `quantity_takeoff` 実装 |
| 3 | `ifc_exporter` + BlenderBIM 確認 |
| 4 | LLM 質問応答 + ワークフロー統合・手順書 |

---

## PoC 完了の次

`mvp.md` へ。実案件 1 棟を対象に、実務での工数削減を数値化する。
