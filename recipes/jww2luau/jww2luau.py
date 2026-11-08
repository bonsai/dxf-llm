#!/usr/bin/env python
"""jww2luau — JWW/DXF の 2D 図面から Roblox のブロック群を生成

使い方:
    python jww2luau.py plan.dxf -o out/Building.luau [--emit-json] [--rbxmx out/Building.rbxmx]

- LINE / LWPOLYLINE / POLYLINE をブロック（Part）に変換
- INSERT（図形・添景ブロック）は展開し、内部の線をブロック化
- 添景（人物・植栽・車など）は「厚みのある立ち看板」風ブロックとして再現
- 出力: Luau ModuleScript / 中間 JSON / Roblox モデル (.rbxmx)

「うそっぽくていい」方針: すべて箱で近似。スケール感の再現を優先。

ライセンス: MIT / PyDXF Japan
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    import ezdxf
except ImportError:  # pragma: no cover
    print("ezdxf が必要です: pip install ezdxf", file=sys.stderr)
    raise

# --- デフォルトのレイヤ / ブロック名 → 部材マッピング --------------------------
# 語（部分一致）: {kind, height_mm, thickness_mm, color}
DEFAULT_MAPPING: Dict[str, Dict[str, Any]] = {
    "wall":   {"kind": "wall",   "height": 2400, "thickness": 120, "color": "LightStoneGrey"},
    "壁":     {"kind": "wall",   "height": 2400, "thickness": 120, "color": "LightStoneGrey"},
    "column": {"kind": "column", "height": 2800, "thickness": 300, "color": "DarkStoneGrey"},
    "柱":     {"kind": "column", "height": 2800, "thickness": 300, "color": "DarkStoneGrey"},
    "window": {"kind": "window", "height": 1200, "thickness": 100, "color": "Cyan"},
    "窓":     {"kind": "window", "height": 1200, "thickness": 100, "color": "Cyan"},
    "door":   {"kind": "door",   "height": 2000, "thickness": 80,  "color": "Brown"},
    "扉":     {"kind": "door",   "height": 2000, "thickness": 80,  "color": "Brown"},
    "ドア":   {"kind": "door",   "height": 2000, "thickness": 80,  "color": "Brown"},
    "beam":   {"kind": "beam",   "height": 400,  "thickness": 200, "color": "ReddishBrown"},
    "梁":     {"kind": "beam",   "height": 400,  "thickness": 200, "color": "ReddishBrown"},
    "slab":   {"kind": "slab",   "height": 150,  "thickness": 150, "color": "MediumStoneGrey"},
    "床":     {"kind": "slab",   "height": 150,  "thickness": 150, "color": "MediumStoneGrey"},
    "stair":  {"kind": "stair",  "height": 900,  "thickness": 250, "color": "MediumStoneGrey"},
    "階段":   {"kind": "stair",  "height": 900,  "thickness": 250, "color": "MediumStoneGrey"},
    # --- 添景 (entourage) ---
    "添景":   {"kind": "entourage", "height": 1700, "thickness": 250, "color": "ReallyBlack"},
    "人物":   {"kind": "entourage", "height": 1700, "thickness": 250, "color": "ReallyBlack"},
    "person": {"kind": "entourage", "height": 1700, "thickness": 250, "color": "ReallyBlack"},
    "人":     {"kind": "entourage", "height": 1700, "thickness": 250, "color": "ReallyBlack"},
    "植栽":   {"kind": "plant",   "height": 2000, "thickness": 400, "color": "DarkGreen"},
    "樹":     {"kind": "plant",   "height": 2500, "thickness": 600, "color": "DarkGreen"},
    "木":     {"kind": "plant",   "height": 2500, "thickness": 600, "color": "DarkGreen"},
    "tree":   {"kind": "plant",   "height": 2500, "thickness": 600, "color": "DarkGreen"},
    "車":     {"kind": "vehicle", "height": 1500, "thickness": 1800, "color": "BrightBlue"},
    "car":    {"kind": "vehicle", "height": 1500, "thickness": 1800, "color": "BrightBlue"},
}

FALLBACK = {"kind": "marker", "height": 100, "thickness": 100, "color": "Yellow"}

# Roblox BrickColor 名 → 近似 RGB(0-255)
COLOR_TABLE: Dict[str, Tuple[int, int, int]] = {
    "LightStoneGrey": (163, 162, 165),
    "MediumStoneGrey": (132, 132, 132),
    "DarkStoneGrey": (99, 95, 98),
    "ReallyBlack": (17, 17, 17),
    "Cyan": (4, 175, 236),
    "Brown": (124, 92, 70),
    "ReddishBrown": (112, 67, 42),
    "DarkGreen": (40, 127, 71),
    "BrightBlue": (13, 105, 172),
    "Yellow": (245, 205, 48),
}


def color_to_rgb(name: str) -> Tuple[int, int, int]:
    return COLOR_TABLE.get(name, (163, 162, 165))


# --- データ構造 --------------------------------------------------------------

@dataclass
class Segment:
    """線分 1 本（ブロック化の最小単位）。"""
    x1: float
    y1: float
    x2: float
    y2: float
    kind: str
    layer: str
    height: float
    thickness: float
    color: str

    @property
    def length(self) -> float:
        return math.hypot(self.x2 - self.x1, self.y2 - self.y1)

    @property
    def angle_deg(self) -> float:
        return math.degrees(math.atan2(self.y2 - self.y1, self.x2 - self.x1))

    @property
    def mid(self) -> Tuple[float, float]:
        return ((self.x1 + self.x2) / 2.0, (self.y1 + self.y2) / 2.0)


@dataclass
class Block:
    """点配置オブジェクト（INSERT / POINT）の footprint ブロック。"""
    cx: float
    cy: float
    width: float
    depth: float
    rot_deg: float
    kind: str
    layer: str
    height: float
    thickness: float
    color: str


@dataclass
class Piece:
    """Roblox Part 化される最終ピース（共通表現）。"""
    kind: str
    layer: str
    size: Tuple[float, float, float]   # x, y, z (studs)
    pos: Tuple[float, float, float]    # x, y, z (studs)
    rot_y: float
    rgb: Tuple[int, int, int]


# --- 分類 --------------------------------------------------------------------

def classify(name: str, layer: str, mapping: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """ブロック名 → レイヤ名 の順で部分一致分類。"""
    for candidate in (name, layer):
        low = (candidate or "").lower()
        for key, spec in mapping.items():
            if key.lower() in low:
                return spec
    return FALLBACK


# --- DXF 抽出 ----------------------------------------------------------------

def _transform_point(x: float, y: float, insert, sx: float, sy: float, rot_rad: float) -> Tuple[float, float]:
    rx = x * sx
    ry = y * sy
    c, s = math.cos(rot_rad), math.sin(rot_rad)
    return (insert.x + rx * c - ry * s, insert.y + rx * s + ry * c)


def _entity_points(entity) -> List[Tuple[float, float]]:
    """エンティティを 2D 点列へ（非対応は空）。"""
    t = entity.dxftype()
    if t == "LINE":
        return [(entity.dxf.start.x, entity.dxf.start.y), (entity.dxf.end.x, entity.dxf.end.y)]
    if t == "LWPOLYLINE":
        return [(float(x), float(y)) for x, y in entity.get_points("xy")]
    if t == "POLYLINE":
        return [(v.dxf.location.x, v.dxf.location.y) for v in entity.vertices]
    return []


def extract_segments(
    dxf_path: str,
    mapping: Dict[str, Dict[str, Any]],
    min_length_mm: float = 10.0,
    expand_inserts: bool = True,
) -> List[Segment]:
    """DXF から線分セグメントを抽出（INSERT は展開）。"""
    doc = ezdxf.readfile(dxf_path)
    msp = doc.modelspace()
    segments: List[Segment] = []

    def add_polyline(points: List[Tuple[float, float]], spec: Dict[str, Any], layer: str) -> None:
        for i in range(len(points) - 1):
            (x1, y1), (x2, y2) = points[i], points[i + 1]
            seg = Segment(x1, y1, x2, y2, spec["kind"], layer,
                          spec["height"], spec["thickness"], spec["color"])
            if seg.length >= min_length_mm:
                segments.append(seg)

    def handle(entity, insert_ctx=None) -> None:
        t = entity.dxftype()

        if t == "INSERT":
            if not expand_inserts:
                return
            block_name = entity.dxf.name
            ins = entity.dxf.insert
            rot = math.radians(entity.dxf.get("rotation", 0.0))
            sx = entity.dxf.get("xscale", 1.0) or 1.0
            sy = entity.dxf.get("yscale", 1.0) or 1.0
            try:
                block = doc.blocks.get(block_name)
            except Exception:
                return
            for be in block:
                pts = _entity_points(be)
                if not pts:
                    continue
                transformed = [_transform_point(px, py, ins, sx, sy, rot) for px, py in pts]
                spec = classify(block_name, entity.dxf.layer, mapping)
                add_polyline(transformed, spec, entity.dxf.layer)
            return

        pts = _entity_points(entity)
        if not pts:
            return
        if insert_ctx is not None:
            pts = [_transform_point(px, py, *insert_ctx) for px, py in pts]
        spec = classify("", entity.dxf.layer, mapping)
        add_polyline(pts, spec, entity.dxf.layer)

    for entity in msp:
        handle(entity)

    return segments


def extract_blocks(dxf_path: str, mapping: Dict[str, Dict[str, Any]], default_footprint_mm: float = 600.0) -> List[Block]:
    """INSERT/POINT を footprint ブロックとして抽出（展開しない簡易版）。"""
    doc = ezdxf.readfile(dxf_path)
    msp = doc.modelspace()
    blocks: List[Block] = []
    for e in msp:
        if e.dxftype() != "INSERT":
            continue
        ins = e.dxf.insert
        rot = e.dxf.get("rotation", 0.0)
        name = e.dxf.name
        spec = classify(name, e.dxf.layer, mapping)
        blocks.append(Block(
            cx=ins.x, cy=ins.y,
            width=default_footprint_mm, depth=default_footprint_mm,
            rot_deg=rot, kind=spec["kind"], layer=e.dxf.layer,
            height=spec["height"], thickness=spec["thickness"], color=spec["color"],
        ))
    return blocks


# --- スケール変換 ------------------------------------------------------------

def _mm_factor(studs_per_meter: float) -> float:
    """mm → studs の係数。"""
    if studs_per_meter <= 0:
        return 1.0 / 280.0
    return studs_per_meter / 1000.0


def segments_to_pieces(segments: List[Segment], studs_per_meter: float, base_height_mm: float) -> List[Piece]:
    f = _mm_factor(studs_per_meter)
    out: List[Piece] = []
    for s in segments:
        mx, my = s.mid
        out.append(Piece(
            kind=s.kind, layer=s.layer,
            size=(round(s.length * f, 4), round(s.height * f, 4), round(s.thickness * f, 4)),
            pos=(round(mx * f, 4), round((base_height_mm + s.height / 2.0) * f, 4), round(my * f, 4)),
            rot_y=round(s.angle_deg, 4),
            rgb=color_to_rgb(s.color),
        ))
    return out


def blocks_to_pieces(blocks: List[Block], studs_per_meter: float, base_height_mm: float) -> List[Piece]:
    f = _mm_factor(studs_per_meter)
    return [
        Piece(
            kind=b.kind, layer=b.layer,
            size=(round(b.width * f, 4), round(b.height * f, 4), round(b.depth * f, 4)),
            pos=(round(b.cx * f, 4), round((base_height_mm + b.height / 2.0) * f, 4), round(b.cy * f, 4)),
            rot_y=round(b.rot_deg, 4),
            rgb=color_to_rgb(b.color),
        )
        for b in blocks
    ]


# --- Luau 生成 ---------------------------------------------------------------

LUAU_HEADER = """--!strict
-- Auto-generated by jww2luau (PyDXF Japan)
-- Source DXF: {source}
-- Pieces: {count}
-- Scale: 1 meter = {spm} studs

local PIECES: {{ [number]: {{ [string]: any }} }} = {data}

local M = {{}}

local MATERIALS: {{ [string]: Enum.Material }} = {{
\twall = Enum.Material.Concrete,
\tcolumn = Enum.Material.Concrete,
\twindow = Enum.Material.Glass,
\tdoor = Enum.Material.Wood,
\tbeam = Enum.Material.WoodPlanks,
\tslab = Enum.Material.Concrete,
\tstair = Enum.Material.Concrete,
\tentourage = Enum.Material.SmoothPlastic,
\tplant = Enum.Material.Grass,
\tvehicle = Enum.Material.Metal,
\tmarker = Enum.Material.SmoothPlastic,
}}

local function makePart(spec): Part
\tlocal p = Instance.new("Part")
\tp.Name = spec.kind .. "_" .. tostring(spec.index)
\tp.Anchored = true
\tp.CanCollide = false
\tp.Size = Vector3.new(spec.size.x, spec.size.y, spec.size.z)
\tp.CFrame = CFrame.new(spec.pos.x, spec.pos.y, spec.pos.z) * CFrame.Angles(0, math.rad(spec.rotY), 0)
\tp.Color = Color3.new(spec.color.r, spec.color.g, spec.color.b)
\tp.Material = MATERIALS[spec.kind] or Enum.Material.SmoothPlastic
\treturn p
end

-- build(parent, filter?)
-- filter: {{ wall = true, entourage = true, ... }} で種別絞り込み
function M.build(parent: Instance?, filter: {{ [string]: boolean }}?): Folder
\tlocal root = Instance.new("Folder")
\troot.Name = "JWW_Building"
\tfor _, spec in ipairs(PIECES) do
\t\tif filter == nil or filter[spec.kind] then
\t\t\tlocal p = makePart(spec)
\t\t\tp.Parent = root
\t\tend
\tend
\troot.Parent = parent or workspace
\treturn root
end

function M.count(): number
\treturn #PIECES
end

return M
"""


def _fmt_color(rgb: Tuple[int, int, int]) -> Tuple[float, float, float]:
    r, g, b = rgb
    return (round(r / 255.0, 4), round(g / 255.0, 4), round(b / 255.0, 4))


def to_luau_table(pieces: List[Piece]) -> str:
    lines = ["{"]
    for i, p in enumerate(pieces):
        r, g, b = _fmt_color(p.rgb)
        lines.append(
            "\t{ index = %d, kind = %r, layer = %r, "
            "size = { x = %s, y = %s, z = %s }, "
            "pos = { x = %s, y = %s, z = %s }, "
            "rotY = %s, color = { r = %s, g = %s, b = %s } },"
            % (i, p.kind, p.layer, p.size[0], p.size[1], p.size[2],
               p.pos[0], p.pos[1], p.pos[2], p.rot_y, r, g, b)
        )
    lines.append("}")
    return "\n".join(lines)


def generate_luau(
    segments: List[Segment],
    source: str,
    studs_per_meter: float,
    base_height_mm: float,
    blocks: Optional[List[Block]] = None,
) -> str:
    pieces = segments_to_pieces(segments, studs_per_meter, base_height_mm)
    if blocks:
        pieces += blocks_to_pieces(blocks, studs_per_meter, base_height_mm)
    return LUAU_HEADER.format(
        source=source,
        count=len(pieces),
        spm=studs_per_meter,
        data=to_luau_table(pieces),
    )


# --- Roblox モデル (.rbxmx) 生成 ----------------------------------------------

def to_rbxmx(pieces: List[Piece], model_name: str = "JWW_Building") -> str:
    """Roblox の .rbxmx (XML モデル) を生成。Studio にドラッグ&ドロップで取込可能。"""
    def part_xml(i: int, p: Piece) -> str:
        r, g, b = p.rgb
        color_u32 = (255 << 24) | (r << 16) | (g << 8) | b
        th = math.radians(p.rot_y)
        c, s = math.cos(th), math.sin(th)
        # 行優先: R00 R01 R02 / R10 R11 R12 / R20 R21 R22 （Y軸回転）
        return f"""    <Item class="Part" referent="RBX{i}">
      <Properties>
        <string name="Name">{p.kind}_{i}</string>
        <bool name="Anchored">true</bool>
        <bool name="CanCollide">false</bool>
        <Color3uint8 name="Color3uint8">{color_u32}</Color3uint8>
        <Vector3 name="size">
          <X>{p.size[0]}</X><Y>{p.size[1]}</Y><Z>{p.size[2]}</Z>
        </Vector3>
        <CoordinateFrame name="CFrame">
          <X>{p.pos[0]}</X><Y>{p.pos[1]}</Y><Z>{p.pos[2]}</Z>
          <R00>{round(c,6)}</R00><R01>0</R01><R02>{round(s,6)}</R02>
          <R10>0</R10><R11>1</R11><R12>0</R12>
          <R20>{round(-s,6)}</R20><R21>0</R21><R22>{round(c,6)}</R22>
        </CoordinateFrame>
      </Properties>
    </Item>"""

    inner = "\n".join(part_xml(i, p) for i, p in enumerate(pieces))
    return f"""<roblox xmlns:xmime="http://www.w3.org/2005/05/xmlmime" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="http://www.roblox.com/roblox.xsd" version="4">
  <Item class="Model" referent="RBXModel">
    <Properties>
      <string name="Name">{model_name}</string>
    </Properties>
{inner}
  </Item>
</roblox>
"""


def generate_rbxmx(segments: List[Segment], blocks: Optional[List[Block]], studs_per_meter: float, base_height_mm: float, model_name: str) -> str:
    pieces = segments_to_pieces(segments, studs_per_meter, base_height_mm)
    if blocks:
        pieces += blocks_to_pieces(blocks, studs_per_meter, base_height_mm)
    return to_rbxmx(pieces, model_name)


# --- CLI ---------------------------------------------------------------------

def load_mapping(path: Optional[str]) -> Dict[str, Dict[str, Any]]:
    if not path:
        return DEFAULT_MAPPING
    try:
        import yaml
    except ImportError:
        print("mapping を指定するには PyYAML が必要です", file=sys.stderr)
        raise
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return {**DEFAULT_MAPPING, **data.get("layers", data)}


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="JWW/DXF → Roblox Luau / rbxmx コンバーター")
    ap.add_argument("input", help="入力 DXF ファイル")
    ap.add_argument("-o", "--output", default="out/Building.luau", help="出力 .luau パス")
    ap.add_argument("--emit-json", action="store_true", help="中間 JSON も出力")
    ap.add_argument("--rbxmx", help="Roblox モデル (.rbxmx) も出力")
    ap.add_argument("--studs-per-meter", type=float, default=3.571, help="スケール（1mあたりstuds）")
    ap.add_argument("--base-height-mm", type=float, default=0.0, help="基準高さ(mm)")
    ap.add_argument("--min-length-mm", type=float, default=10.0, help="無視する最小線長(mm)")
    ap.add_argument("--mapping", help="レイヤ/ブロック名マッピング YAML")
    args = ap.parse_args(argv)

    mapping = load_mapping(args.mapping)
    segments = extract_segments(args.input, mapping, min_length_mm=args.min_length_mm)
    blocks = extract_blocks(args.input, mapping)

    if not segments and not blocks:
        print("警告: 図形が抽出できませんでした（レイヤ/単位を確認してください）", file=sys.stderr)

    # サマリ（種別ごと）
    from collections import Counter
    kinds = Counter([s.kind for s in segments] + [b.kind for b in blocks])
    print("種別内訳:", ", ".join(f"{k}={v}" for k, v in sorted(kinds.items())))

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    luau = generate_luau(segments, source=args.input, studs_per_meter=args.studs_per_meter,
                         base_height_mm=args.base_height_mm, blocks=blocks)
    out.write_text(luau, encoding="utf-8")
    print(f"Luau 出力: {out} ({len(segments)} segments + {len(blocks)} blocks)")

    if args.emit_json:
        jpath = out.with_suffix(".json")
        pieces = segments_to_pieces(segments, args.studs_per_meter, args.base_height_mm)
        pieces += blocks_to_pieces(blocks, args.studs_per_meter, args.base_height_mm)
        jpath.write_text(json.dumps([p.__dict__ for p in pieces], ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"JSON 出力: {jpath}")

    if args.rbxmx:
        rpath = Path(args.rbxmx)
        rpath.parent.mkdir(parents=True, exist_ok=True)
        rpath.write_text(generate_rbxmx(segments, blocks, args.studs_per_meter, args.base_height_mm,
                                        model_name=rpath.stem), encoding="utf-8")
        print(f"rbxmx 出力: {rpath}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
