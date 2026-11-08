"""DXF 解析モジュール

ezdxf をラップし、DXF 要素を LLM が操作するための構造化データに変換。
日本語CAD（JWW由来）の CP932 文字コード対応も含む。
"""

import re
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any

import ezdxf


@dataclass
class DxfEntity:
    """DXF エンティティを LLM に適した構造化表現に変換。"""

    entity_type: str          # LINE, CIRCLE, LWPOLYLINE, TEXT, MTEXT 等
    layer: str                # 図元名（例: 壁芯）
    color_index: int          # color index 0-255
    linetype: str             # continuous, CENTER 等
    geometry: List[List[float]]  # 点群 [[x, y], ...] or [[x, y, z], ...]
    text_content: Optional[str] = None
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DxfDocument:
    """構造化DXFドキュメント（LLMが操作するインターフェース）。"""

    filename: str
    entities: List[DxfEntity]
    layers: List[Dict[str, str]]
    total_points: int
    total_faces: int


def parse_dxf(filepath: str) -> DxfDocument:
    """DXFファイルを解析してDxfDocumentを返す。

    Args:
        filepath: DXFファイルパス（JWW由来も対応）

    Returns:
        DxfDocument: 構造化されたDXFドキュメント
    """
    doc = ezdxf.readfile(filepath)
    entities: List[DxfEntity] = []

    for entity in doc.modelspace():
        entity_data = _parse_entity(entity, doc)
        if entity_data is not None:
            entities.append(entity_data)

    # レイヤーリスト作成
    layers = [
        {"name": doc.layers.get(i).dxf.name,
         "color": doc.layers.get(i).dxf.color} 
        for i in range(doc.layers.count) if doc.layers.get(i)
    ]

    return DxfDocument(
        filename=filepath,
        entities=entities,
        layers=layers,
        total_points=sum(len(e.geometry) for e in entities),
        total_faces=sum(len(e.geometry) // 3 for e in entities if len(e.geometry) >= 3),
    )


def _parse_entity(entity, doc) -> Optional[DxfEntity]:
    """個々のエンティティをDxfEntityに変換。"""
    try:
        # 共通属性の取得
        layer = entity.dxf.layer or "0"
        color = entity.dxf.color or doc.layers.get(entity.dxf.layer).dxf.color if entity.dxf.layer in [l.dxf.name for l in doc.layers.values()] else 7

        # GEOMETRY の取得
        geometry = _extract_geometry(entity)

        # TEXT・MTEXT の取得
        text_content = _extract_text(entity)

        return DxfEntity(
            entity_type=entity.dxftype(),
            layer=layer,
            color_index=color,
            linetype=entity.dxf.linetype or "continuous",
            geometry=geometry,
            text_content=text_content,
        )
    except Exception:
        return None


def _extract_geometry(entity) -> List[List[float]]:
    """エンティティから幾何形状を抽出。"""
    geom_list = []

    # LINE: vertices属性
    if entity.dxftype() == "LINE":
        vertices = entity.dxf.vertices
        if vertices:
            for idx in vertices:
                if hasattr(entity, "vertex"):
                    geom_list.append(entity.vertex(idx))

    # CIRCLE / ARC: center + radius
    elif entity.dxftype() in ("CIRCLE", "ARC"):
        center = entity.dxf.center
        radius = entity.dxf.radius
        geom_list.append([float(center[0]), float(center[1]), float(radius)])

    # LWPOLYLINE / POLYLINE: vertices + bulge
    elif entity.dxftype() in ("LWPOLYLINE", "POLYLINE", "MLINE"):
        for vertex in entity.vertices:
            try:
                geom_list.append([float(v[0]), float(v[1])])
            except (ValueError, TypeError):
                pass

    # POINT: single point
    elif entity.dxftype() == "POINT":
        p = entity.dxf.insert
        geom_list.append([float(p[0]), float(p[1])])

    # TEXT / MTEXT (AutoCAD基準)
    elif entity.dxftype() in ("TEXT", "MTEXT"):
        content = _extract_text(entity)
        # テキスト位置を geom に挿入（後でテキストプロパティから分離）
        position = entity.dxf.insertion or entity.dxf.chord_u
        if position and len(geom_list) < len(entity.vertices):
            geom_list.append([float(position[0]), float(position[1])])

    return geom_list


def _extract_text(entity) -> Optional[str]:
    """TEXT/MTEXTの内容を抽出。JWWのCP932文字コードにも対応。"""
    try:
        if entity.dxftype() == "MTEXT":
            height = entity.dxf.char_height or 0
            spacing = entity.dxf.field_length or 0
            alignment = entity.dxf.attachment_point
            text_style = entity.dxf.text_style or "STANDARD"
            transforms = entity.dxf.field_transform

            # MTEXTのテキスト抽出（CP932 encoding auto handled by ezdxf）
            return entity.text

        else:  # TEXT
            base_line = entity.dxf.baselinetype
            pt = entity.dxf.insert or entity.dxf.chord_u
            height = entity.dxf.char_height or 0

            # フォント指定
            font = entity.dxf.font or entity.dxf.object_type_flag_list

            # JWW由来の WINDOW_TEXT_ROOT => "窓表題"
            # AutoCAD基準 TEXTのテキスト抽出
            return entity.dxf.val_txt or ""

    except Exception:
        return None


def search_entities(document: DxfDocument, keyword: str, layer_filter: Optional[str] = None) -> List[DxfEntity]:
    """DXFドキュメントから条件に一致するエンティティを検索。

    Args:
        document: 解析済みDxfDocument
        keyword: 検索キーワード（文字列・数値）
        layer_filter: 図元名フィルタ（Noneなら全検索）

    Returns:
        マッチしたDxfEntityのリスト
    """
    results = []
    lower_keyword = keyword.lower()

    for entity in document.entities:
        if layer_filter and entity.layer != layer_filter:
            continue

        # テキスト検索
        if entity.text_content and lower_keyword in entity.text_content.lower():
            results.append(entity)
            continue

        # レイヤー名検索
        if lower_keyword in entity.layer.lower():
            results.append(entity)
            continue

        # 数値範囲検索（例: "壁高 3500" => y座標3500番地の周辺）
        if re.match(r'^[-\d.]+(\s*[-~至]+\s*[-\d.]+)*$', keyword):
            try:
                nums = [float(x) for x in keyword.split()]
                if all(abs(a - b) < 1.0 for a, b in zip(entity.geometry, nums)) and len(entity.geometry) == len(nums):
                    results.append(entity)
                    continue
            except ValueError:
                pass

        # bbox探索（キーワードが座標「1000,2000」など）
        if len(keyword.split()) == 2:
            try:
                pts = keyword.split()
                x_range = max(float(pts[0]) - 10, 0), min(float(pts[1]) + 10, 99999)
                y_range = min(float(pts[0]) - 10, 0), max(float(pts[1]) + 10, 99999)
                results.extend([
                    e for e in document.entities
                    if e.layer == entity.layer
                    and any(x_range[0] <= x <= x_range[1] and y_range[0] <= y <= y_range[1]
                            for x, y in e.geometry)
                ])
            except ValueError:
                pass

    return results
