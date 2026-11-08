# 添景（entourage）を Luau でブロック再現

> 方針: **「うそっぽくていい」**。JWW の添景（人物・植栽・車など）を、厚みのある
> ブロックとして 3D 空間に立てる。スケール感の再現を優先し、見た目の作り込みはしない。

---

## なぜブロックか

- JWW の添景は **2D シルエット**（線画 or 図形ブロック）で、面情報を持たない
- 3D 化する際、輪郭を面に張って押し出す（カットアウト/立ち看板）のが最短
- 建築パースでは意図的にこの「シルエット添景」を使う手法も一般的
- Roblox では薄い箱（Part）で十分それらしく見える

```
JWW 添景（2D線画） ──押し出し──► 厚みのあるブロック ──► Roblox Part
```

---

## 実装（jww2luau）

`添景` / `人物` / `person` などのレイヤ・ブロック名を検出し、

- **INSERT ブロック** → ブロック定義内の線を展開し、1 本ずつ厚み付きブロック化
- **footprint ブロック** → INSERT 位置に箱を配置（展開しない簡易モード）

| 種別 | kind | 高さ(mm) | 厚み(mm) | 色 |
|---|---|---|---|---|
| 人物 | `entourage` | 1700 | 250 | ReallyBlack |
| 植栽・樹木 | `plant` | 2000–2500 | 400–600 | DarkGreen |
| 車 | `vehicle` | 1500 | 1800 | BrightBlue |

座標: DXF の (x, y) → Roblox (x, z)、高さは y 方向。厚みは線の直交方向。

```bash
python recipes/jww2luau/jww2luau.py tests/fixtures/sample_entourage.dxf \
    -o out/Entourage.luau --rbxmx out/Entourage.rbxmx --emit-json
# 種別内訳: entourage=26, plant=13, wall=4
```

---

## マッピングのカスタム

`mapping.yaml`:

```yaml
layers:
  添景_人:  { kind: entourage, height: 1700, thickness: 250, color: ReallyBlack }
  添景_自転車: { kind: vehicle, height: 1200, thickness: 600, color: BrightBlue }
```

```bash
python recipes/jww2luau/jww2luau.py plan.dxf -o out/B.luau --mapping mapping.yaml
```

---

## Roblox での描画（2 通り）

### A. `.rbxmx` を直接インポート（MCP 不要）

`out/Entourage.rbxmx` を Roblox Studio にドラッグ&ドロップ → `Workspace` に配置。
一部パーツを選んで `entourage` フォルダにまとめると管理しやすい。

### B. Luau を実行（Studio のコマンドバー / MCP 経由）

```lua
local Entourage = require(game.ReplicatedStorage.Entourage)
local root = Entourage.build(workspace, { entourage = true, plant = true })
-- 添景だけを半透明にして「らしく」
for _, p in ipairs(root:GetDescendants()) do
    if p:IsA("BasePart") then
        if p.Name:match("entourage") then
            p.Transparency = 0.2
        end
    end
end
```

Roblox Studio の MCP（`run_code`）経由なら、この Luau をそのまま送り込んで描画できる。
詳細は `mcp-studio.md` を参照。

---

## 見た目を少し良くするコツ（任意）

- 人物は `Transparency = 0.0〜0.3`、`Material = SmoothPlastic`
- 植栽は `Material = Grass`、少しランダム回転
- 車は `Material = Metal`
- 影を落とすため `CastShadow = true`
- 大量配置は `--min-length-mm` で微小線を除外して負荷軽減

---

## 既知の制約

- 円弧（ARC/CIRCLE）は直線近似されない（現状は非対応 → 将来対応）
- 塗り（HATCH/SOLID）は線ではないため現状は外形線のみ
- 2D 平面図前提（高さはレイヤ/設定から付与）
