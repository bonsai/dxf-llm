"""共通データモデル

プラグイン間で受け渡す中間表現。
- DxfDocument / DxfEntity: 解析直後の生データ（parser.py）
- EnrichedModel / Component: 意味付け後の中間表現（本モジュール）

単一ソース → 多出力（quantity / IFC / Luau ...）を支える。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# 部材種別（IFC クラスへのマッピングも兼ねる）
KIND_WALL = "wall"
KIND_COLUMN = "column"
KIND_WINDOW = "window"
KIND_DOOR = "door"
KIND_BEAM = "beam"
KIND_SLAB = "slab"
KIND_STAIR = "stair"
KIND_MARKER = "marker"

# 部材種別 → IFC4 クラス名
IFC_CLASS_MAP: Dict[str, str] = {
    KIND_WALL: "IfcWall",
    KIND_COLUMN: "IfcColumn",
    KIND_WINDOW: "IfcWindow",
    KIND_DOOR: "IfcDoor",
    KIND_BEAM: "IfcBeam",
    KIND_SLAB: "IfcSlab",
    KIND_STAIR: "IfcStair",
    KIND_MARKER: "IfcBuildingElementProxy",
}


@dataclass
class Component:
    """意味付けされた 1 部材。

    geometry は XY 平面上の点列 [[x, y], ...]（mm）。
    height / thickness は mm。
    """

    kind: str
    layer: str
    geometry: List[List[float]] = field(default_factory=list)
    height: float = 0.0
    thickness: float = 0.0
    extra: Dict[str, Any] = field(default_factory=dict)

    # --- 幾何ヘルパ -------------------------------------------------------

    def segments(self) -> List[tuple]:
        """ポリラインを線分 (p1, p2) のリストに分解。"""
        out = []
        for i in range(len(self.geometry) - 1):
            out.append((self.geometry[i], self.geometry[i + 1]))
        return out

    def length(self) -> float:
        """折れ線長の合計（mm）。"""
        import math

        total = 0.0
        for (x1, y1), (x2, y2) in self.segments():
            total += math.hypot(x2 - x1, y2 - y1)
        return total

    def area_xy(self) -> float:
        """閉じた多角形の面積（mm^2、shapely があれば正確、なければ符号付き面積）。"""
        pts = [(p[0], p[1]) for p in self.geometry]
        if len(pts) < 3:
            return 0.0
        try:
            from shapely.geometry import Polygon

            return abs(Polygon(pts).area)
        except Exception:
            # 靴紐公式
            s = 0.0
            for i in range(len(pts)):
                x1, y1 = pts[i]
                x2, y2 = pts[(i + 1) % len(pts)]
                s += x1 * y2 - x2 * y1
            return abs(s) / 2.0

    @property
    def ifc_class(self) -> str:
        return IFC_CLASS_MAP.get(self.kind, "IfcBuildingElementProxy")


@dataclass
class EnrichedModel:
    """意味付け済みモデル（単一ソース）。"""

    filename: str
    components: List[Component] = field(default_factory=list)
    units: str = "mm"

    def by_kind(self, kind: str) -> List[Component]:
        return [c for c in self.components if c.kind == kind]

    def kinds(self) -> List[str]:
        return sorted({c.kind for c in self.components})

    @property
    def count(self) -> int:
        return len(self.components)
