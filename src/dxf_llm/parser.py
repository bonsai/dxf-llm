"""DXF 解析モジュール

ezdxf をラップし、DXF 要素を LLM / プラグインが扱いやすい構造化データに変換する。
日本語 CAD（JWW 由来）の CP932 文字列・レイヤ・色・線種を保持する。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import ezdxf

# LINE などの座標を [x, y] へ正規化するユーティリティ ----------------------------


@dataclass
class DxfEntity:
    """DXF エンティティの構造化表現。"""

    entity_type: str  # LINE, CIRCLE, LWPOLYLINE, TEXT, MTEXT 等
    layer: str
    color_index: int  # ACI 0-255（BYLAYER は 256）
    linetype: str
    geometry: List[List[float]] = field(default_factory=list)
    text_content: Optional[str] = None
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DxfDocument:
    """構造化 DXF ドキュメント。"""

    filename: str
    entities: List[DxfEntity] = field(default_factory=list)
    layers: List[Dict[str, Any]] = field(default_factory=list)
    total_points: int = 0
    total_faces: int = 0


# --- 解析 --------------------------------------------------------------------


def parse_dxf(filepath: str) -> DxfDocument:
    """DXF ファイルを解析して DxfDocument を返す。"""
    doc = ezdxf.readfile(filepath)
    msp = doc.modelspace()

    entities: List[DxfEntity] = []
    for entity in msp:
        parsed = _parse_entity(entity, doc)
        if parsed is not None:
            entities.append(parsed)

    layers = [
        {"name": layer.dxf.name, "color": layer.dxf.color}
        for layer in doc.layers
    ]

    total_points = sum(max(len(e.geometry), 0) for e in entities)
    total_faces = sum(1 for e in entities if len(e.geometry) >= 3)

    return DxfDocument(
        filename=filepath,
        entities=entities,
        layers=layers,
        total_points=total_points,
        total_faces=total_faces,
    )


def _resolve_color(entity, doc) -> int:
    """エンティティ色を解決（BYLAYER なら layer の色）。"""
    try:
        color = entity.dxf.get("color", 256)
    except Exception:
        color = 256
    if color in (0, 256):  # BYBLOCK / BYLAYER
        try:
            layer = doc.layers.get(entity.dxf.layer)
            return int(layer.dxf.color)
        except Exception:
            return 7
    return int(color)


def _parse_entity(entity, doc) -> Optional[DxfEntity]:
    """1 エンティティを DxfEntity に変換。未対応種別は None。"""
    try:
        etype = entity.dxftype()
        layer = entity.dxf.get("layer", "0")
        linetype = entity.dxf.get("linetype", "continuous")
        color = _resolve_color(entity, doc)

        geometry, text, extra = _extract(entity, etype)

        if geometry is None and text is None:
            return None

        return DxfEntity(
            entity_type=etype,
            layer=layer,
            color_index=color,
            linetype=linetype,
            geometry=geometry or [],
            text_content=text,
            extra=extra,
        )
    except Exception:
        return None


def _extract(entity, etype: str):
    """種別ごとに geometry / text / extra を抽出。"""
    geometry: List[List[float]] = []
    text: Optional[str] = None
    extra: Dict[str, Any] = {}

    if etype == "LINE":
        s, e = entity.dxf.start, entity.dxf.end
        geometry = [[float(s.x), float(s.y)], [float(e.x), float(e.y)]]

    elif etype == "CIRCLE":
        c = entity.dxf.center
        geometry = [[float(c.x), float(c.y)], [float(entity.dxf.radius)]]

    elif etype == "ARC":
        c = entity.dxf.center
        geometry = [[float(c.x), float(c.y)], [float(entity.dxf.radius)]]
        extra = {
            "start_angle": float(entity.dxf.start_angle),
            "end_angle": float(entity.dxf.end_angle),
        }

    elif etype == "LWPOLYLINE":
        geometry = [[float(x), float(y)] for x, y in entity.get_points("xy")]
        extra = {"closed": bool(entity.closed)}

    elif etype == "POLYLINE":
        pts = []
        try:
            for v in entity.vertices:
                loc = v.dxf.location
                pts.append([float(loc.x), float(loc.y)])
        except Exception:
            pts = []
        geometry = pts

    elif etype == "POINT":
        p = entity.dxf.location
        geometry = [[float(p.x), float(p.y)]]

    elif etype == "TEXT":
        t = entity.dxf.get("text", "") or ""
        text = t
        try:
            p = entity.dxf.insert
            geometry = [[float(p.x), float(p.y)]]
        except Exception:
            geometry = []
        extra = {"height": float(entity.dxf.get("height", 0) or 0)}

    elif etype == "MTEXT":
        try:
            text = entity.plain_text()
        except Exception:
            text = entity.text if hasattr(entity, "text") else ""
        try:
            p = entity.dxf.insert
            geometry = [[float(p.x), float(p.y)]]
        except Exception:
            geometry = []

    else:
        return None, None, {}

    return geometry, text, extra


# --- 検索 --------------------------------------------------------------------


def search_entities(
    document: DxfDocument,
    keyword: str,
    layer_filter: Optional[str] = None,
) -> List[DxfEntity]:
    """DXF ドキュメントから条件に一致するエンティティを検索。

    Args:
        document: 解析済み DxfDocument
        keyword: 検索語（テキスト・レイヤ名の部分一致）
        layer_filter: レイヤ名フィルタ（None なら全検索）

    Returns:
        マッチした DxfEntity のリスト
    """
    results: List[DxfEntity] = []
    kw = (keyword or "").lower()

    for entity in document.entities:
        if layer_filter is not None and entity.layer != layer_filter:
            continue

        if not kw:
            results.append(entity)
            continue

        if entity.text_content and kw in entity.text_content.lower():
            results.append(entity)
            continue

        if kw in entity.layer.lower():
            results.append(entity)

    return results
