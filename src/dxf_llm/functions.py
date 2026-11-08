"""dxf-llm 関数モジュール - LLMエージェント向け実行関数

LangChain/LangGraphのToolとして使用可能。
DXFドキュメントをLLMに渡し、自然言語で操作・質問できるようにする。"""

from typing import List, Dict, Any, Optional

from .parser import DxfDocument, DxfEntity
from .query_engine import search_dxf, analyze_dxf_document, extract_geometry_from_text


class DxfLLMTool:
    """DXFをLLMと連携するツールクラス。"""

    def __init__(self, qdrant: Optional[Any] = None, language: str = "ja"):
        self.qdrant = qdrant
        self.language = language

    def search(self, document: DxfDocument, query: str, limit: int = 10) -> List[DxfSearchResult]:
        """DXFドキュメント内で自然言語クエリを実行し、結果を返す。"""
        return search_dxf(self.qdrant, "dxf_models", query, limit)

    def analyze(self, document: DxfDocument, question: str) -> str:
        """DXFドキュメントの概要を簡易的に分析して返す。"""
        return analyze_dxf_document(document, self.language, question)

    def extract_geometry(self, document: DxfDocument, text: str) -> List[Dict[str, Any]]:
        """テキストからDXFの幾何学的座標を抽出。"""
        return extract_geometry_from_text(document, text)

    def modify(self, document: DxfDocument, instruction: str) -> DxfDocument:
        """DXFドキュメントをLLM指示に従って変更（簡易版）。"""
        # 実際の図形操作は複雑なため、簡易的な操作のみ
        # 例: 特定の層の要素を追加・削除する
        if instruction and "remove" in instruction.lower():
            # 簡易: 最初の要素を削除
            if document.entities:
                doc = document.entities[0]
                doc.entities = []
                return DxfDocument(
                    filename=document.filename,
                    entities=[],
                    layers=document.layers,
                    total_points=0,
                    total_faces=0,
                )
        return document

    def get_summary(self, document: DxfDocument) -> str:
        """DXFドキュメントの概要テキストを生成。"""
        return analyze_dxf_document(document, self.language, "この図面の概要を教えてください")


def create_dxf_llm_tool(qdrant: Optional[Any] = None) -> DxfLLMTool:
    """DxfLLMToolインスタンスを作成。"""
    return DxfLLMTool(qdrant=qdrant, language="ja")
