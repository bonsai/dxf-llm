"""ワークフローエンジン（DAG）のテスト"""

import ezdxf
import pytest

from dxf_llm.plugins.registry import PluginRegistry
from dxf_llm.plugins.dxf_parser import DxfParserPlugin
from dxf_llm.plugins.semantic_enricher import SemanticEnricherPlugin
from dxf_llm.workflows import Workflow, StepConfig, StepStatus


def _make_dxf(path):
    doc = ezdxf.new("R2010")
    msp = doc.modelspace()
    doc.layers.add("wall")
    msp.add_line((0, 0), (4000, 0), dxfattribs={"layer": "wall"})
    msp.add_line((4000, 0), (4000, 3000), dxfattribs={"layer": "wall"})
    doc.saveas(path)


def _registry():
    r = PluginRegistry()
    r.register_class(DxfParserPlugin)
    r.register_class(SemanticEnricherPlugin)
    return r


def test_workflow_sequential(tmp_path):
    dxf = tmp_path / "plan.dxf"
    _make_dxf(str(dxf))

    wf = Workflow(
        [
            StepConfig(id="parse", plugin="dxf_parser"),
            StepConfig(id="enrich", plugin="semantic_enricher", depends_on=["parse"]),
        ],
        registry=_registry(),
        name="test_seq",
    )
    results = wf.run(initial_context={"filepath": str(dxf)})
    assert results["parse"].status == StepStatus.SUCCESS
    assert results["enrich"].status == StepStatus.SUCCESS
    model = wf.get_step_result(results, "enrich")
    assert model.count == 2


def test_workflow_cycle_detection():
    with pytest.raises(ValueError):
        Workflow(
            [
                StepConfig(id="a", plugin="dxf_parser", depends_on=["b"]),
                StepConfig(id="b", plugin="dxf_parser", depends_on=["a"]),
            ],
            registry=_registry(),
            name="cycle",
        )


def test_workflow_unknown_dependency():
    with pytest.raises(ValueError):
        Workflow(
            [StepConfig(id="a", plugin="dxf_parser", depends_on=["nope"])],
            registry=_registry(),
            name="bad",
        )


def test_workflow_execution_levels():
    wf = Workflow(
        [
            StepConfig(id="a", plugin="dxf_parser"),
            StepConfig(id="b", plugin="dxf_parser"),
            StepConfig(id="c", plugin="dxf_parser", depends_on=["a", "b"]),
        ],
        registry=_registry(),
        name="levels",
    )
    # a, b は同一レベル、c は次レベル
    assert sorted(wf.execution_levels[0]) == ["a", "b"]
    assert wf.execution_levels[1] == ["c"]
