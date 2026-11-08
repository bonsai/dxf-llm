# dxf-llm - DXF ⇔ 自然言語 双方向変換エージェント

## 概要

**dxf-llm** は、日本の建築業界で使われているレガシーCADデータ（JWW/DXF）を、  
Python と LLM (Large Language Model) を活用して、以下のようなことができるようにするプロジェクトです。

- **自然言語で図面を検索**（「この壁の高さは？」）
- **図面から数量を自動計算**（「この建物の壁長さは？」）
- **自然言語で図形を生成・修正**（「この壁を2000mm延長して」）
- **図面を IFC / Three.js / Roblox 形式に変換**
- **LLM とのエージェント連携**（自動化・自動化・自動化）

### 核となる機能

| 機能 | 説明 |
|------|------|
| **DXF 解析** | JWW/DXF を正しく読み込み、レイヤー・色・文字コード（CP932）まで保持 |
| **構造化データ** | エンティティを JSON のような構造化形式で管理（Entity, Document） |
| **ベクトル検索** | Qdrant + OpenAI Embeddings で自然言語検索 |
| **LLM エージェント** | LangChain + LangGraph でエージェント連携 |
| **関数呼び出し** | 図形操作・数量計算・構造解析の実行関数 |
| **API インターフェース** | FastAPI で HTTP API 提供（RESTful） |

---

## インストール

### 1. 開発環境（推奨）

```bash
# プロジェクトのルートに移動
cd C:/Users/dance/dxf-llm

# 仮想環境を作成
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 依存関係をインストール
pip install -r requirements.txt

# 開発用の追加依存をインストール（オプション）
pip install -r requirements-dev.txt
```

### 2. インストール（本番環境）

```bash
pip install dxf-llm
```

> **注意**: 現在はローカル開発用に設計されています。本番環境では Docker コンテナ化が推奨されます。

---

## インストールと設定

### 1. Qdrant のセットアップ（推奨）

```bash
# Docker で Qdrant を起動（開発用）
docker run -p 6333:6333 -p 6334:6334 qdrantinc/qdrant:v1.25.2
```

> 開発環境ではローカルに Qdrant を起動することを推奨します。

### 2. 初期設定

```bash
# 開発環境で実行
python -m dxf_llm.init --config config.yaml
```

`config.yaml` の例:

```yaml
collection_name: "dxf_models"
model_name: "text-embedding-3-small"  # OpenAI Embedding
language: "ja"  # 図面言語（日本語）
```

### 2. 開発環境での初期化

```bash
# プロジェクトのルートで実行
python -m dxf_llm.init --config config.yaml
```

---

## API エンドポイント

### 1. `/search` - 自然言語クエリで DXF を検索

```http
POST /search
Content-Type: application/json

{
  "document": "C:/Users/dance/dxf-llm/data/sample.jww",
  "query": "この壁の高さは？",
  "limit": 5
]
```

**レスポンス例**:
```json
[
  {
    "filename": "C:/Users/dance/dxf-llm/data/sample.jww",
    "total_entities": 12,
    "layers_found": ["wall", "window"],
    "geometry_samples": [[1000, 2000], [1000, 2500]],
    "text_contents": ["壁芯", "高さ3000"],
    "source_text": "壁芯 1000,2000 3000"
  }
]
```

### 2. `/analyze` - DXF ドキュメントの概要解析

```http
POST /analyze
Content-Type: application/json

{
  "document": "C:/Users/dance/dxf-llm/data/sample.jww",
  "question": "この図面の構造を説明してください。"
]
```

**レスポンス**:
```json
{
  "summary": "図面ファイル: sample.jww\n総点数: 1200\n総面数: 300\n図層: wall, window\n最初のエンティティ: LINE\n最初のエンティテキスト: 壁芯"
```

### 3. `/modify` - 図形操作指示

```http
POST /modify
Content-Type: application/json

{
  "document": "C:/Users/dance/dxf-llm/data/sample.jww",
  "instruction": "壁芯を2000mm延長してください"
}
```

**レスポンス**:
```json
{
  "status": "ok",
  "message": "最初のエンティティを削除しました"
}
```

---

## 開発環境での実行

### 1. 開発サーバー起動

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### 2. テスト実行

```bash
pytest tests/ -v
```

---

## 開発の流れ

1. **初期化**: `dxf-llm init` で設定ファイル生成
2. **DXF 変換**: JWW → DXF → DXF → JSON (自動化)
3. **ベクトル化**: DXF → Embedding → Qdrant に保存
4. **検索/分析**: LLM エージェントが自然言語で操作
5. **API 提供**: FastAPI でエンドポイント提供
5. **API 利用**: FastAPI で HTTP リクエスト

---

## 開発の流れ（実践的）

### ステップ 1: DXF 変換

```bash
# JWW → DXF
JWW2DXFConv.exe -i "C:/Users/dance/dxf-llm/data/sample.jww" -o "C:/Users/dxf-llm/data/sample.dxf"

# DXF → DXF 解析 (Python)
python -c "from dxf_llm.parser import DxfDocument; doc = DxfDocument('C:/Users/dxf-llm/data/sample.dxf'); print(f'{len(doc.entities)} エンティティがあります')"
```

### ステップ 2: ベクトル化

```bash
python -c "from dxf_llm import DxfDocument, DxfLLMTool; doc = DxfDocument('C:/Users/dxf-llm/data/sample.dxf'); DxfLLMTool().store_dxf_document(dxf, 'qdrant', 'dxf_models')"
```

---

## 開発のベストプラクティス

1. **JWW から DXF への変換**は必ず `JWW2DXFConv.exe` を使用
2. **レイヤー・色・文字コード**は正しく保持する
3. **エンティティの幾何学的正規化**を必須とする
4. **LLM との連携**は `DxfSearchResult` 形式で返す
5. **API は RESTful に設計**し、FastAPI を使用
5. **テストは必須** - `pytest` で単体テストを書く

---

## ドキュメント

- **API 仕様書**: `docs/api_spec.md`
- **開発ガイド**: `docs/development.md`
- **デプロイガイド**: `docs/deployment.md`

---

## サポートとコミュニティ

- **GitHub Issues**: [https://github.com/pydxf-japan/dxf-llm/issues](https://github.com/pydxf-japan/dxf-llm/issues)
- **Slack/Discord**: `#pydxf-japan` に参加
- **メール**: pydxf-japan@example.com

---

## License

MIT License - [LICENSE](LICENSE) ファイルを参照

---

## 著作権

Copyright (c) 2025 PyDXF Japan. All rights reserved.

---

## サポート

質問や要望は GitHub Issues にてお知らせください。  
優秀な PR があれば歓迎します。  

**Happy DXF Hacking!** 🚀