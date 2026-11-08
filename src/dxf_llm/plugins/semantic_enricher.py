"""意味付け（Semantic Enrichment）プラグイン

「線」を「壁・柱・窓・梁…」といった部材種別へ分類し、
高さ・厚みなどの属性を付与して EnrichedModel を生成する。

分類はデフォルトでレイヤ名の部分一致（ルールベース）。
将来的に ML（軽量 CNN/Transformer）で補正する余地を残す。
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from .base import PluginBase
from ..model import Component, EnrichedModel
from ..parser import DxfDocument, parse_dxf

logger = logging.getLogger(__name__)

# レイヤ語（部分一致・小文字比較）→ 部材属性
DEFAULT_RULES: Dict[str, Dict[str, Any]] = {
    "wall":   {"kind": "wall",   "height": 2400, "thickness": 120},
    "壁":     {"kind": "wall",   "height": 2400, "thickness": 120},
    "column": {"kind": "column", "height": 2800, "thickness": 300},
    "柱":     {"kind": "column", "height": 2800, "thickness": 300},
    "window": {"kind": "window", "height": 1200, "thickness": 100},
    "窓":     {"kind": "window", "height": 1200, "thickness": 100},
    "door":   {"kind": "door",   "height": 2000, "thickness": 80},
    "扉":     {"kind": "door",   "height": 2000, "thickness": 80},
    "ドア":   {"kind": "door",   "height": 2000, "thickness": 80},
    "beam":   {"kind": "beam",   "height": 400,  "thickness": 200},
    "梁":     {"kind": "beam",   "height": 400,  "thickness": 200},
    "slab":   {"kind": "slab",   "height": 150,  "thickness": 150},
    "床":     {"kind": "slab",   "height": 150,  "thickness": 150},
    "stair":  {"kind": "stair",  "height": 900,  "thickness": 250},
    "階段":   {"kind": "stair",  "height": 900,  "thickness": 250},
}

FALLBACK = {"kind": "marker", "height": 100, "thickness": 100}


def classify(layer: str, rules: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """レイヤ名から部材属性を推定。"""
    low = (layer or "").lower()
    for key, spec in rules.items():
        if key.lower() in low:
            return spec
    return FALLBACK


class SemanticEnricherPlugin(PluginBase):
    name = "semantic_enricher"
    version = "0.1.0"
    description = "線を壁・柱・窓などの部材種別へ分類し EnrichedModel を生成"

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        cfg = config or {}
        self.rules = {**DEFAULT_RULES, **(cfg.get("rules") or {})}

    def execute(self, data: Any, context: Dict[str, Any]) -> EnrichedModel:
        doc = self._resolve_document(data, context)
        components: List[Component] = []

        for e in doc.entities:
            spec = classify(e.layer, self.rules)
            geom = e.geometry
            if not geom:
                continue
            if len(geom) == 1:
                # 単一点（TEXT 等）は 1 点ポリライン（長さ 0）として保持
                pass
            components.append(
                Component(
                    kind=spec["kind"],
                    layer=e.layer,
                    geometry=geom,
                    height=float(spec.get("height", 0)),
                    thickness=float(spec.get("thickness", 0)),
                    extra={"entity_type": e.entity_type, "text": e.text_content},
                )
            )

        model = EnrichedModel(filename=doc.filename, components=components)
        context["enriched_model"] = model
        logger.info(
            "Enriched %s: %d components, kinds=%s",
            doc.filename, model.count, model.kinds(),
        )
        return model

    @staticmethod
    def _resolve_document(data: Any, context: Dict[str, Any]) -> DxfDocument:
        if isinstance(data, DxfDocument):
            return data
        if isinstance(data, dict) and isinstance(data.get("dxf_document"), DxfDocument):
            return data["dxf_document"]
        if isinstance(data, str):
            return parse_dxf(data)
        if isinstance(data, dict) and data.get("filepath"):
            return parse_dxf(data["filepath"])
        ctx_doc = context.get("dxf_document")
        if isinstance(ctx_doc, DxfDocument):
            return ctx_doc
        raise ValueError("semantic_enricher: DxfDocument または filepath が必要")
