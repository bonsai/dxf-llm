# recipe: jww2luau

**JWW/DXF の 2D 建築図面 → Roblox (Luau) の 3D ジオメトリ生成コード**

JWW から書き出した DXF を読み取り、壁・柱・窓などを Roblox の `Part` として
組み立てる Luau スクリプト（`ModuleScript`）を生成します。
生成物を Roblox Studio に貼り付けると、図面に沿ってパーツが自動生成されます。

**添景（人物・植栽・車）も厚み付きブロックで再現**します（→ [entourage.md](entourage.md)）。
「うそっぽくていい」方針で、すべて箱で近似します。

---

## パイプライン

```
JWW ──JWW2DXFConv.exe──► DXF ──jww2luau.py──► .luau (ModuleScript)
                                             └► .json (中間データ)
```

---

## 座標系マッピング

| DXF (mm, XY平面) | Roblox (studs) |
|---|---|
| x | x |
| y | z（地面平面） |
| 高さ（レイヤ/設定） | y（上方向） |
| 線分の向き | CFrame.Angles(0, θ, 0) |

- デフォルト `mm_to_studs = 1 / 280`（1 stud ≒ 280 mm）
- `--studs-per-meter` で変更可（例: 1 m = 3.571 studs）

---

## レイヤ → 部材マッピング（デフォルト）

| レイヤに含まれる語 | 生成物 | 高さ(mm) | 厚み(mm) | 色 |
|---|---|---|---|---|
| `wall`, `壁` | 壁 | 2400 | 120 | 薄灰 |
| `column`, `柱` | 柱 | 2800 | 300 | 濃灰 |
| `window`, `窓` | 窓（開口） | 1200 | 100 | 水色 |
| `door`, `扉`, `ドア` | 扉 | 2000 | 80 | 茶 |
| `beam`, `梁` | 梁 | 400 | 200 | 赤茶 |
| その他 | マーカー | 100 | 100 | 黄 |

マッピングは `--mapping mapping.yaml` で上書き可能です。

---

## 使い方

```bash
# 1. JWW → DXF
JWW2DXFConv.exe -i "C:/jww/木造平面例.jww" -o "C:/tmp/plan.dxf"

# 2. DXF → Luau
python recipes/jww2luau/jww2luau.py "C:/tmp/plan.dxf" -o "./out/Building.luau"

# 3. (任意) 中間 JSON / Roblox モデル(.rbxmx) も出す
python recipes/jww2luau/jww2luau.py "C:/tmp/plan.dxf" -o ./out/Building.luau \
    --emit-json --rbxmx ./out/Building.rbxmx
```

`.rbxmx` は Roblox Studio にドラッグ&ドロップで取り込めるモデル（MCP 不要）。

| 出力 | 用途 |
|---|---|
| `*.luau` | `require` して実行（コマンドバー / MCP `run_code`） |
| `*.rbxmx` | Studio へ直接インポート（MCP `insert_model` でも可） |
| `*.json` | 中間データ（他ツール連携） |

---

## 生成物の使い方（Roblox Studio）

1. `Building.luau` を `ServerScriptService`（または `ReplicatedStorage`）に配置
2. ModuleScript として `require` する

```lua
local Building = require(game.ReplicatedStorage.Building)
Building.build(workspace)              -- 全パーツを生成
Building.build(workspace, { wall = true })  -- 壁だけ
```

`template.luau` のヘルパーが、パーツ生成・グループ化・地形への配置を行います。

---

## 添景（entourage）・Roblox 描画

- 添景のブロック再現の詳細 → [entourage.md](entourage.md)
- Roblox Studio MCP 経由の描画手順 → [mcp-studio.md](mcp-studio.md)

---

## 引数

| 引数 | 説明 | デフォルト |
|---|---|---|
| `input` | 入力 DXF（位置引数） | 必須 |
| `-o, --output` | 出力 `.luau` パス | `out/Building.luau` |
| `--emit-json` | 中間 JSON も出力 | off |
| `--rbxmx` | Roblox モデル `.rbxmx` を出力 | off |
| `--studs-per-meter` | スケール | 3.571 |
| `--base-height-mm` | 生成 Z(=Y) の基準高さ | 0 |
| `--mapping` | レイヤマッピング YAML | 組み込み |

---

## 制約・注意

- DXF は **mm 単位**を前提（図面単位が異なる場合は `--studs-per-meter` で補正）
- `LWPOLYLINE` は線分に分割して生成（曲線は直線近似）
- 2D 平面図のみ対応（Z 情報はレイヤ/設定から付与）
- Roblox 側の `Part` 数が多すぎると重い → `--min-length-mm` で微小線を除外推奨

---

## 発展

- `dxf_llm.plugins.luau_exporter` を使えばワークフローに組み込み可能
- 家具・添景は `Semantic Enrichment` 後に別プラグインで 3D モデルへ置換
- 生成パーツに `Anchored = true` を付け、`Model` にまとめて保存
