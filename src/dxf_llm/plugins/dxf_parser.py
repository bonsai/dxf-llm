"""DXF パーサープラグイン

JWW/DXF ファイルを読み込み、構造化された DxfDocument を返す。
ワークフローの最初のステップで使用を想定。
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from .base import PluginBase
from ..parser import DxfDocument, parse_dxf

logger = logging.getLogger(__name__)


class DxfParserPlugin(PluginBase):
    name = "dxf_parser"
    version = "0.1.0"
    description = "JWW/DXF ファイルを読み込み、構造化 DxfDocument を返す"

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self.default_encoding = config.get("encoding", "cp932") if config else "cp932"

    def execute(
        self, data: Any, context: Dict[str, Any]
    ) -> DxfDocument:
        """DXF ファイルを読み込んで DxfDocument を返す。

        Args:
            data: 入力データ。以下の形式を受け付ける
                - str: ファイルパス
                - dict: {"filepath": "...", "encoding": "..."}
                - Path: パスオブジェクト
            context: ワークフロー共有コンテキスト

        Returns:
            DxfDocument
        """
        # 入力正規化
        filepath: Optional[str] = None
        encoding = self.default_encoding

        if isinstance(data, str):
            filepath = data
        elif isinstance(data, dict):
            filepath = data.get("filepath")
            encoding = data.get("encoding", encoding)
        elif isinstance(data, Path):
            filepath = str(data)
        else:
            raise ValueError(f"Unsupported input type for dxf_parser: {type(data)}")

        if not filepath:
            raise ValueError("filepath is required")

        logger.info("Parsing DXF: %s (encoding=%s)", filepath, encoding)

        # 実際のパース（ezdxf 内部で encoding 処理）
        doc = parse_dxf(filepath)

        # コンテキストに保存（次のステップで参照可能）
        context["dxf_document"] = doc
        context["dxf_filepath"] = filepath

        logger.info(
            "Parsed %s: %d entities, %d layers",
            filepath,
            len(doc.entities),
            len(doc.layers),
        )
        return doc


# 便利関数（レジストリ登録用）
def create_dxf_parser(config: Optional[Dict[str, Any]] = None) -> DxfParserPlugin:
    return DxfParserPlugin(config=config)