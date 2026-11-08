--!strict
-- template.luau — jww2luau 生成物を使うための例 / ランタイムヘルパー
-- このファイルは「使い方の例」です。生成された Building.luau と合わせて使用します。

local ReplicatedStorage = game:GetService("ReplicatedStorage")

-- 生成物（ModuleScript）を require
local Building = require(ReplicatedStorage:WaitForChild("Building"))

-- 1) 全部生成
local root = Building.build(workspace)
print(`生成パーツ数: {#root:GetChildren()}`)

-- 2) 種別でフィルタ（壁と柱だけ）
local wallsAndColumns = Building.build(workspace, { wall = true, column = true })

-- 3) 生成後にまとめて移動・保存
root:PivotTo(CFrame.new(0, 0, 0))

-- 4) パーツをアンカー（既に Anchored=true だが念のため）
for _, part in ipairs(root:GetDescendants()) do
	if part:IsA("BasePart") then
		part.Anchored = true
	end
end

-- 5) 地形（Baseplate）に配置する例
local baseplate = workspace:FindFirstChild("Baseplate")
if baseplate then
	root:PivotTo(CFrame.new(baseplate.Position + Vector3.new(0, 3, 0)))
end

-- 参考: 生成物の中身（Building.luau）は
--   { index, kind, layer, size={x,y,z}, pos={x,y,z}, rotY, color }
-- の配列を持ち、M.build(parent, filter) で Part を生成します。
