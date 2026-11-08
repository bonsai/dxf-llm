"""dxf-llm テストコード - DXF 解析モジュールのテスト"""

import pytest
from pathlib import Path

from dxf_llm.parser import DxfDocument, DxfEntity, parse_dxf, search_entities


def test_dxf_document_creation():
    """DxfDocument が正しく作成できることを確認"""
    doc = DxfDocument(
        filename="test.dxf",
        entities=[
            DxfEntity(
                entity_type="LINE",
                layer="wall",
                color_index=7,
                linetype="continuous",
                geometry=[[0, 0], [1000, 0]],
                text_content="壁芯",
            )
        ],
        layers=[{"name": "wall", "color": 7}],
        total_points=2,
        total_faces=0,
    )
    assert doc.filename == "test.dxf"
    assert len(doc.entities) == 1
    assert doc.entities[0].entity_type == "LINE"
    assert doc.total_points == 2


def test_dxf_document_empty():
    """空の DXF ドキュメントが正しく作成できることを確認"""
    doc = DxfDocument(
        filename="empty.dxf",
        entities=[],
        layers=[],
        total_points=0,
        total_faces=0,
    )
    assert len(doc.entities) == 0
    assert doc.total_points == 0


def test_dxf_entity_attributes():
    """DxfEntity の属性が正しく設定できることを確認"""
    entity = DxfEntity(
        entity_type="CIRCLE",
        layer="column",
        color_index=1,
        linetype="dashed",
        geometry=[[500, 500], [100]],  # center + radius
        text_content="柱1",
    )
    assert entity.entity_type == "CIRCLE"
    assert entity.layer == "column"
    assert entity.color_index == 1
    assert entity.linetype == "dashed"
    assert entity.geometry == [[500, 500], [100]]
    assert entity.text_content == "柱1"


def test_search_entities_by_layer():
    """エンティティの検索（レイヤー指定）が正しく動作することを確認"""
    doc = DxfDocument(
        filename="test.dxf",
        entities=[
            DxfEntity(
                entity_type="LINE",
                layer="wall",
                color_index=7,
                linetype="continuous",
                geometry=[[0, 0], [1000, 0]],
                text_content="壁1",
            ),
            DxfEntity(
                entity_type="LINE",
                layer="window",
                color_index=1,
                linetype="dashed",
                geometry=[[2000, 0], [3000, 0]],
                text_content="窓1",
            ),
        ],
        layers=[
            {"name": "wall", "color": 7},
            {"name": "window", "color": 1},
        ],
        total_points=4,
        total_faces=0,
    )

    results = search_entities(doc, "", layer_filter="wall")
    assert len(results) == 1
    assert results[0].layer == "wall"
    assert results[0].text_content == "壁1"


def test_search_entities_by_text():
    """エンティティの検索（テキスト指定）が正しく動作することを確認"""
    doc = DxfDocument(
        filename="test.dxf",
        entities=[
            DxfEntity(
                entity_type="TEXT",
                layer="annotation",
                color_index=7,
                linetype="continuous",
                geometry=[[100, 100]],
                text_content="壁高 3500",
            ),
        ],
        layers=[{"name": "annotation", "color": 7}],
        total_points=1,
        total_faces=0,
    )

    results = search_entities(doc, "壁高")
    assert len(results) == 1
    assert results[0].text_content == "壁高 3500"


def test_search_entities_by_keyword():
    """エンティティの検索（キーワード指定）が正しく動作することを確認"""
    doc = DxfDocument(
        filename="test.dxf",
        entities=[
            DxfEntity(
                entity_type="LINE",
                layer="wall",
                color_index=7,
                linetype="continuous",
                geometry=[[0, 0], [1000, 0]],
                text_content="壁芯",
            ),
        ],
        layers=[{"name": "wall", "color": 7}],
        total_points=2,
        total_faces=0,
    )

    results = search_entities(doc, "壁芯")
    assert len(results) == 1
    assert results[0].entity_type == "LINE"
