# dxf-llm

> **JWW/DXF を Python + LLM で「読める・繋がる・自動化できる」構造化データに変える。**

日本の建築 CAD 資産（JWW/DXF）を解析し、プラグイン + ワークフロー（DAG）で
数量拾い・IFC/BIM 変換・自然言語検索まで一気通貫で扱うためのツールキットです。

---

## Status

Early / Pre-alpha. 目的・計画は [`docs/aim.md`](docs/aim.md) を参照。

| フェーズ | ドキュメント | 状態 |
|---|---|---|
| 目的・方針 | [docs/aim.md](docs/aim.md) | ✅ |
| PoC 計画 | [docs/poc.md](docs/poc.md) | ✅ |
| MVP 計画 | [docs/mvp.md](docs/mvp.md) | ✅ |
| 事業計画 | [docs/business_plan.md](docs/business_plan.md) | ✅ |

---

## Concept

```
JWW/DXF ──► 構造化 JSON ──► LLM エージェント ──► 数量 / IFC / 3D / ゲーム
   ①解析         ②意味付け          ③エージェント            ④多出力
```

- **解析**: `ezdxf` + JWW 変換（CP932・レイヤ・色・線種を保持）
- **意味付け**: 「線」を「壁・柱・窓・梁」へ分類（ルール + ML）
- **エージェント**: 自然言語で検索・集計・図形生成
- **多出力**: IFC / glTF / Three.js / Roblox / CSV / JSON

---

## Architecture

```
PluginRegistry + Hooks (Bonsai 風)
        │
        ▼
Workflow (DAG, pyper 風) ── parse → enrich → quantity → export
        │
        ▼
Plugins: dxf_parser / semantic_enricher / quantity_takeoff / ifc_exporter
```

- **Plugin lifecycle**: `setup()` → `execute()` → `teardown()`
- **Hooks**: `before_<step>` / `after_<step>` / `on_error`
- **Workflow**: トポロジカルソート、並列実行、リトライ、YAML 定義

---

## Install

```bash
git clone https://github.com/bonsai/dxf-llm.git
cd dxf-llm
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

---

## Quickstart

```python
from dxf_llm.plugins.registry import PluginRegistry
from dxf_llm.plugins.dxf_parser import DxfParserPlugin
from dxf_llm.workflows import Workflow, StepConfig

registry = PluginRegistry()
registry.register_class(DxfParserPlugin)

wf = Workflow(
    [
        StepConfig(id="parse", plugin="dxf_parser", params={"encoding": "cp932"}),
    ],
    registry=registry,
    name="quickstart",
)
results = wf.run(initial_context={"filepath": "sample.dxf"})
doc = wf.get_step_result(results, "parse")
print(doc.filename, len(doc.entities))
```

YAML ワークフロー:

```yaml
name: dxf_to_ifc
steps:
  - id: parse
    plugin: dxf_parser
    params: { encoding: cp932 }
  - id: enrich
    plugin: semantic_enricher
    depends_on: [parse]
  - id: export_ifc
    plugin: ifc_exporter
    depends_on: [enrich]
```

---

## Layout

```
dxf-llm/
├── docs/            # aim / poc / mvp / business_plan
├── recipes/         # recipes.yaml (TOC), workflows
├── src/dxf_llm/     # package
│   ├── parser.py
│   ├── query_engine.py
│   ├── functions.py
│   ├── plugins/     # PluginBase / Registry
│   └── workflows/   # DAG engine
├── tests/
└── main.py          # FastAPI entry
```

---

## License

MIT — see [LICENSE](LICENSE). Copyright (c) 2025 PyDXF Japan.
