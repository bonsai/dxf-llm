"""model.py のテスト（Component / EnrichedModel）"""

import math

from dxf_llm.model import (
    Component,
    EnrichedModel,
    IFC_CLASS_MAP,
    KIND_COLUMN,
    KIND_WALL,
)


def test_component_length():
    c = Component(kind=KIND_WALL, layer="wall", geometry=[[0, 0], [3000, 0], [3000, 4000]])
    assert c.length() == 7000.0


def test_component_segments():
    c = Component(kind=KIND_WALL, layer="wall", geometry=[[0, 0], [1000, 0], [1000, 500]])
    segs = c.segments()
    assert segs[0] == ([0, 0], [1000, 0])
    assert segs[1] == ([1000, 0], [1000, 500])


def test_component_area_square():
    c = Component(kind=KIND_COLUMN, layer="column", geometry=[[0, 0], [100, 0], [100, 100], [0, 100]])
    assert c.area_xy() == 10000.0


def test_component_ifc_class():
    c = Component(kind=KIND_WALL, layer="wall")
    assert c.ifc_class == "IfcWall"
    assert IFC_CLASS_MAP[KIND_COLUMN] == "IfcColumn"


def test_enriched_model_by_kind():
    model = EnrichedModel(
        filename="x.dxf",
        components=[
            Component(kind=KIND_WALL, layer="wall", geometry=[[0, 0], [1, 0]]),
            Component(kind=KIND_WALL, layer="壁", geometry=[[0, 0], [2, 0]]),
            Component(kind=KIND_COLUMN, layer="column", geometry=[[0, 0], [3, 0]]),
        ],
    )
    assert model.count == 3
    assert len(model.by_kind(KIND_WALL)) == 2
    assert model.kinds() == ["column", "wall"]
