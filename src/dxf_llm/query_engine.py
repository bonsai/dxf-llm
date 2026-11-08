"""dxf-llm クエリエンジン - 構造化DXFデータとLLMの自然言語橋渡し

LangChainスタイルのFunction CallingとRAGを活用して、図面データ（DXF）を自然言語で検索・操作可能にする。
"""

import json
from typing import List, Dict, Any, Callable
from dataclasses import dataclass

from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool

from .parser import DxfDocument, DxfEntity


@dataclass
class ChatHistory:
    """LLMとの会話履歴を管理。"""

    messages: List[Dict[str, Any]] = None

    def __post_init__(self):
        if self.messages is None:
            self.messages = []

    def add(self, role: str, content: str):
        """メッセージを追加。"""
        self.messages.append({"role": role, "content": content})

    def get_context(self) -> str:
        """チャット履歴をHTML形式で返却（参照提示用）。"""
        return "\n".join(
            f"<div class=\"{'user' if m['role'] == 'user' else 'assistant'}\" style=\"padding:8px;margin:4px;\">{m['content']}</div>"
            for m in self.messages
        )


@dataclass
class DxfSearchResult:
    """DXF検索結果構造化表現。"""

    filename: str
    total_entities: int
    layers_found: List[str]
    geometry_samples: List[List[float]]
    text_contents: List[str]
    source_text: str


def store_dxf_document(document: DxfDocument, qdrant: QdrantClient, collection_name: str):
    """DxfDocument を Qdrant ベクトルデータベースに保存。

    Args:
        document: 構造化DXFドキュメント
        qdrant: QdrantClientインスタンス
        collection_name: コレクション名
    """
    # ドキュメントを JSON文字列として保存
    doc_text = json.dumps({
        "filename": document.filename,
        "layers": document.layers,
        "entities": [
            {
                "type": e.entity_type,
                "layer": e.layer,
                "color": e.color_index,
                "geometry": e.geometry,
                "text": e.text_content,
            } for e in document.entities
        ],
        "total_points": document.total_points,
        "total_faces": document.total_faces,
    }, ensure_ascii=False)

    # またはベクトル埋め込みを生成
    from langchain_openai import OpenAIEmbeddings
    embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
    vector = embeddings.embed_query(doc_text)

    # Qdrant に保存
    point = PointStruct(
        id=hash(document.filename),
        vector=vector,
        payload={
            "filename": document.filename,
            "content": doc_text,
            "file_size": len(doc_text),
        },
    )
    qdrant.upsert_points(collection_name=collection_name, points=[point])


def search_dxf(qdrant: QdrantClient, collection_name: str, query: str, limit: int = 10) -> List[DxfSearchResult]:
    """DXFベクトルDBで自然言語クエリを実行し、JSON表現を返却。

    Args:
        qdrant: QdrantClientインスタンス
        collection_name: コレクション名
        query: 検索クエリ（自然言語）
        limit: 検索件数制限

    Returns:
        DxfSearchResult のリスト
    """
    # ベクトル埋め込み生成
    from langchain_openai import OpenAIEmbeddings
    embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
    query_vector = embeddings.embed_query(query)

    # Qdrant で類似度検索
    search_result = qdrant.search_points(
        collection_name=collection_name,
        query_vector=query_vector,
        limit=limit,
        with_payload=True,
    )

    results = []
    for point in search_result:
        payload = point.payload or {}
        results.append(DxfSearchResult(
            filename=payload.get("filename", "unknown"),
            total_entities=len(json.loads(payload.get("content", "{}"))["entities"]),
            layers_found=[e["layer"] for e in json.loads(payload.get("content", "{}")).get("entities", [])],\n            geometry_samples=json.loads(payload.get("content", "{}")).get("entities", [])[0:1],
            text_contents=[e.get("text", "") for e in json.loads(payload.get("content", "{}")).get("entities", [])],
            source_text=payload.get("content", ""),
        ))

    return results


def analyze_dxf_document(document: DxfDocument, language: str = "ja", question: str = "この図面は何ですか？") -> str:
    """DxfDocument に簡単なテキスト生成（LLM代用）。簡易版では概要テキストを返却する """

    summary_parts = [
        f"図面ファイル: {document.filename}",
        f"総点数: {document.total_points}、総面数: {document.total_faces}",
        f"図層: {', '.join([l.get('name', '') for l in document.layers])}",
        f"最初のエンティティタイプ: {document.entities[0].entity_type if document.entities else '不明'}",
        f"最初のエンティティテキスト: {document.entities[0].text_content or 'テキストなし'}",
    ]

    if language == "en":
        summary_parts = [
            f"Drawing file: {document.filename}",
            f"Total points: {document.total_points}, Total faces: {document.total_faces}",
            f"Layers: {', '.join([l.get('name', '') for l in document.layers])}",
            f"First entity type: {document.entities[0].entity_type if document.entities else 'unknown'}",
            f"First entity text: {document.entities[0].text_content or 'no text'}",
        ]

    return "\n".join(summary_parts)


def extract_geometry_from_text(document: DxfDocument, text: str) -> List[Dict[str, Any]]:
    """テキストから図形座標を抽出（例: "壁芯は1000,2000と2000,2000"）。"""

    # 単純な正規表現例
    points = []
    pattern = r'([0-9\.]+)[:,]\\s*([0-9\.]+)'

    matches = re.findall(pattern, text)
    for x, y in matches:
        points.append({"x": float(x), "y": float(y)})

    return points


def generate_dxf_modification(document: DxfDocument, instruction: str) -> DxfDocument:
    """DL/E Instruction に基づき、DxfDocument を生成。簡易版では通りすがる処理を返す。"""

    # 実際に図形を生成するのではなく、新しい DxfDocument を返す
    return DxfDocument(
        filename=document.filename + "_modified",
        entities=[],
        layers=document.layers,
        total_points=0,
        total_faces=0,
    )