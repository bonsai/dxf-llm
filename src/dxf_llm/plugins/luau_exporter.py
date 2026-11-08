"""Luau エクスポータープラグイン

DXF から抽出したセグメント（または意味付け済みモデル）を
Roblox (Luau) の ModuleScript として出力する。

recipe: recipes/jww2luau/ の変換ロジックをワークフローに組み込むためのラッパー。
"""

from __future__ import annotations

import importlib.util
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from .base import PluginBase
from ..parser import DxfDocument

logger = logging.getLogger(__name__)

# recipe の変換関数を動的 import（単体依存を避ける）
_RECIPE_PATH = Path(__file__).resolve().parents[3] / "recipes" / "jww2luau" / "jww2luau.py"


def _load_recipe_module():
    spec = importlib.util.spec_from_file_location("jww2luau_recipe", _RECIPE_PATH)
    if spec is None or spec.loader is None:
        raise ImportError(f"jww2luau recipe not found at {_RECIPE_PATH}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class LuauExporterPlugin(PluginBase):
    name = "luau_exporter"
    version = "0.1.0"
    description = "セグメント/DXF を Roblox Luau ModuleScript として出力"

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        cfg = config or {}
        self.output = cfg.get("output", "out/Building.luau")
        self.studs_per_meter = cfg.get("studs_per_meter", 3.571)
        self.base_height_mm = cfg.get("base_height_mm", 0.0)

    def execute(self, data: Any, context: Dict[str, Any]) -> Path:
        """data は以下のいずれか:
          - DxfDocument（context に dxf_filepath がある）
          - 入力 DXF ファイルパス（str）
        """
        filepath: Optional[str] = None
        if isinstance(data, DxfDocument):
            filepath = context.get("dxf_filepath")
        elif isinstance(data, str):
            filepath = data
        elif isinstance(data, dict):
            filepath = data.get("filepath") or context.get("dxf_filepath")

        if not filepath:
            raise ValueError("luau_exporter: 入力 DXF ファイルパスが解決できません")

        recipe = _load_recipe_module()
        segments = recipe.extract_segments(filepath, recipe.DEFAULT_MAPPING)
        luau = recipe.generate_luau(
            segments,
            source=filepath,
            studs_per_meter=self.studs_per_meter,
            base_height_mm=self.base_height_mm,
        )
        out = Path(self.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(luau, encoding="utf-8")
        logger.info("Luau exported: %s (%d segments)", out, len(segments))
        context["luau_output"] = str(out)
        return out