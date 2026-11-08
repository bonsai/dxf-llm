# Roblox Studio MCP 経由で描画する

JWW/DXF から生成した Luau を **Roblox Studio の MCP サーバ経由**で実行し、
Studio 上にブロック（建物＋添景）を描画するための手順。

---

## 前提: 現状この環境では Roblox MCP は未設定

利用可能な MCP は `jules_*` と `takt` のみで、`roblox` / `studio` / `luau` に
該当するツールは **0 件**。描画するには MCP サーバを追加する必要がある。

（そのため、当面は `out/*.rbxmx` を Studio にドラッグ&ドロップする運用が最短。）

---

## 選択肢

| 方式 | 内容 | 難易度 |
|---|---|---|
| **A. 公式 Studio MCP Server** | Roblox 公式 `studio-rust-mcp-server` + Studio プラグイン | 中 |
| **B. コミュニティ MCP** | `rbx-studio-mcp` 等（Studio プラグイン + ローカル WS） | 中 |
| **C. MCP なし** | `.rbxmx` 取込 or Studio コマンドバーに Luau 貼付 | 低 |

---

## A. 公式 Roblox Studio MCP Server の導入手順（概要）

1. リポジトリ取得: `github.com/Roblox/studio-rust-mcp-server`
2. ビルド or リリース入手（Rust / `cargo build --release`）
3. Studio に **プラグイン**をインストール（同リポジトリの plugin）
4. pi（MCP クライアント）の MCP 設定にサーバを追加

```jsonc
// MCP 設定（例）
{
  "mcpServers": {
    "roblox-studio": {
      "command": "C:/path/to/studio-rust-mcp-server.exe",
      "args": []
    }
  }
}
```

5. Studio で MCP プラグインを有効化 → 接続確認
6. 利用可能ツール（例）: `run_code`, `insert_model`, `get_selection`, `search_objects`

> 設定は pi の MCP 設定ファイル（プロジェクト/ユーザ設定）に追記し、pi を再起動。

---

## B/C. 描画用 Luau（共通で使える）

MCP が使える場合は `run_code` に以下を渡す。使えない場合は Studio の
コマンドバー（`View > Command Bar`）に貼り付ける。

```lua
-- 1) 生成物を ReplicatedStorage に置いて require（A/B）
local Entourage = require(game.ReplicatedStorage.Entourage)
local root = Entourage.build(workspace)

-- 2) あるいは .rbxmx をインポート済みならフォルダ名で取得
-- local root = workspace:WaitForChild("Entourage")

-- 3) 配置＆見た目調整
root:PivotTo(CFrame.new(0, 0, 0))
for _, p in ipairs(root:GetDescendants()) do
    if p:IsA("BasePart") then
        p.Anchored = true
        p.CastShadow = true
        if p.Name:match("entourage") then
            p.Transparency = 0.2
        elseif p.Name:match("plant") then
            p.Material = Enum.Material.Grass
        end
    end
end
print(`描画完了: {#root:GetChildren()} parts`)
```

---

## 典型的なワークフロー（MCP 有効時）

```
JWW ──► DXF ──► jww2luau ──► out/Building.luau
                                   │
        Roblox Studio MCP (run_code) ──► Studio に描画 ──► スクショ /
                                   └► insert_model で .rbxmx を配置
```

- `insert_model`: `out/Building.rbxmx` を Studio へ投入
- `run_code`: 取得したモデルの見た目・配置を調整
- `get_selection`: 選択中パーツの情報取得（デバッグ）

---

## 次アクション（この環境で MCP を使う場合）

1. `scripts/install_roblox_mcp.md` を用意し、公式サーバの導入手順を具体化
2. pi の MCP 設定に `roblox-studio` を追記
3. Studio プラグインを導入し接続確認
4. `run_code` / `insert_model` で `out/*.rbxmx` / `*.luau` を描画

> 必要なら導入手順書とMCP設定の実ファイルを作成します。エンジン（Rust）や
> Studio プラグインの導入はこの環境の外（Studio 側）で行う必要があります。
