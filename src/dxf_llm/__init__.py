"""dxf-llm: DXF ⇔ 自然言語 双方向変換エージェント

JWW/DXF/IFC 図面データを LLM 活用して操作・検索・生成可能にする。

コア（このモジュール）は軽量に保つ: parser / model のみを公開。
LLM/Qdrant 連携（query_engine / functions）は重量依存のため明示 import とする。
"""

__version__ = "0.1.0"
__author__ = "PyDXF Japan"
__license__ = "MIT"

from .parser import DxfDocument, DxfEntity, parse_dxf, search_entities
from .model import (
    Component,
    EnrichedModel,
    IFC_CLASS_MAP,
    KIND_WALL,
    KIND_COLUMN,
    KIND_WINDOW,
    KIND_DOOR,
    KIND_BEAM,
    KIND_MARKER,
)

__all__ = [
    # parser
    "parse_dxf",
    "DxfDocument",
    "DxfEntity",
    "search_entities",
    # model
    "Component",
    "EnrichedModel",
    "IFC_CLASS_MAP",
    "KIND_WALL",
    "KIND_COLUMN",
    "KIND_WINDOW",
    "KIND_DOOR",
    "KIND_BEAM",
    "KIND_MARKER",
    "__version__",
]
