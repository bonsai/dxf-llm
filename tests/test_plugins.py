"""プラグイン（registry / parser / semantic_enricher）のテスト"""

import ezdxf
import pytest

from dxf_llm.parser import DxfDocument, parse_dxf
from dxf_llm.model import EnrichedModel
from dxf_llm.plugins.registry import PluginRegistry
from dxf_llm.plugins.dxf_parser import DxfParserPlugin
from dxf_llm.plugins.semantic_enricher import (
    SemanticEnricherPlugin,
    classify,
    DEFAULT_RULES,
)


def _make_dxf(path):
    doc = ezdxf.new("R2010")
    msp = doc.modelspace()
    for name in ("wall", "column", "window"):
        doc.layers.add(name)
    msp.add_line((0, 0), (4000, 0), dxfattribs={"layer": "wall"})
    msp.add_line((0, 0), (0, 3000), dxfattribs={"layer": "wall"})
    msp.add_lwpolyline([(0, 0), (200, 0), (200, 200), (0, 200), (0, 0)],
                       dxfattribs={"layer": "column"})
    doc.saveas(path)


def test_classify_rules():
    assert classify("wall", DEFAULT_RULES)["kind"] == "wall"
    assert classify("壁", DEFAULT_RULES)["kind"] == "wall"
    assert classify("column", DEFAULT_RULES)["kind"] == "column"
    assert classify("unknown_layer", DEFAULT_RULES)["kind"] == "marker"


def test_dxf_parser_plugin(tmp_path):
    dxf = tmp_path / "plan.dxf"
    _make_dxf(str(dxf))

    registry = PluginRegistry()
    registry.register_class(DxfParserPlugin)
    plugin = registry.get_instance("dxf_parser")
    assert plugin.is_initialized()

    ctx = {}
    doc = plugin.execute(str(dxf), ctx)
    assert isinstance(doc, DxfDocument)
    assert len(doc.entities) == 3
    assert ctx["dxf_document"] is doc
    assert any(e.entity_type == "LWPOLYLINE" for e in doc.entities)


def test_semantic_enricher_plugin(tmp_path):
    dxf = tmp_path / "plan.dxf"
    _make_dxf(str(dxf))
    parsed = parse_dxf(str(dxf))

    enricher = SemanticEnricherPlugin()
    ctx = {"dxf_document": parsed}
    model = enricher.execute(parsed, ctx)
    assert isinstance(model, EnrichedModel)
    assert model.count == 3
    assert len(model.by_kind("wall")) == 2
    assert len(model.by_kind("column")) == 1
    assert "wall" in model.kinds()


def test_registry_list_and_teardown():
    registry = PluginRegistry()
    registry.register_class(DxfParserPlugin)
    registry.register_class(SemanticEnricherPlugin)
    names = registry.list_plugins()
    assert "dxf_parser" in names
    assert "semantic_enricher" in names
    registry.get_instance("dxf_parser")
    assert "dxf_parser" in registry.list_instances()
    registry.teardown_all()
    assert registry.list_instances() == []
