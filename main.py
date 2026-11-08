"""dxf-llm main entry point - Flask/FastAPI サーバー

DxfLLMTool を expose して、自然言語クエリ・検索・分析を HTTP API で提供。

Usage:
    from dxf_llm.main import app, DxfLLMTool
    tool = DxfLLMTool()
    client = app.Client(tool=tool)
"""

from fastapi import FastAPI, Request, Query
from pydantic import BaseModel
import uvicorn

from .parser import DxfDocument
from .query_engine import search_dxf, analyze_dxf_document, store_dxf_document
from .functions import DxfLLMTool


class SearchRequest(BaseModel):
    document: str
    query: str
    limit: int = 10


class AnalyzeRequest(BaseModel):
    document: str
    question: str


class ModifyRequest(BaseModel):
    document: str
    instruction: str


app = FastAPI(title="dxf-llm API", version="0.1.0")


# グローバルツール
default_tool = DxfLLMTool()


@app.get("/documents/{filename}")
async def get_document(filename: str):
    """DXFファイルの構造化ドキュメントを取得（ローカルファイルが必要）。"""
    # 実際はファイルパスを受け取る
    return {"error": "ファイルパスが必須"}


@app.post("/search")
async def search(
    body: SearchRequest,
    tool: DxfLLMTool = Query(default_tool),
):
    """自然言語クエリで DXF ドキュメントを検索。"""
    doc_file = body.document
    query = body.query
    limit = body.limit or 10

    if not doc_file.endswith(".jww") and not doc_file.endswith(".dxf"):
        return {"error": f"{doc_file} は JWW/DXF ファイルではないか？"}
    
    results = search_dxf(tool.qdrant, "dxf_models", query, limit)

    return [
        {
            "filename": r.filename,
            "total_entities": r.total_entities,
            "layers_found": r.layers_found,
            "geometry_samples": r.geometry_samples[:3],
            "text_contents": r.text_contents,
            "source_text": r.source_text,
        }
        for r in results
    ]


@app.post("/analyze")
async def analyze(
    body: AnalyzeRequest,
    tool: DxfLLMTool = Query(default_tool),
):
    """DXFドキュメントの概要を分析して返す。"""
    result = analyze_dxf_document(body.document, tool.language, body.question)
    return {"summary": result}


@app.post("/modify")
async def modify(
    body: ModifyRequest,
    tool: DxfLLMTool = Query(default_tool),
):
    """図形操作指示を実行（簡易版）。"""
    doc_file = body.document
    instruction = body.instruction.lower()

    # 実際には複雑な操作が必要だが、ここでは簡易処理のみ
    if instruction == "remove":
        # 最初のエンティティを削除
        if tool.qdrant is None:
            # ローカルファイルから読み込み
            try:
                import ezdxf
                doc = ezdxf.readfile(doc_file)
                entities = []
                for entity in doc.modelspace():
                    entities.append(_parse_entity(entity, doc))
                tool.qdrant = QdrantClient()  # 必要に応じて初期化
                tool.search(tool.qdrant, doc_file, "remove", limit=1)
            except Exception as e:
                return {"error": str(e)}
        else:
            return {"error": "Qdrantクライアントが設定されていない"}

    return {"status": "ok"}


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
