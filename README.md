# factor-map-api

FastAPI で作る API サーバーです。Cloudflare Workers（Python Workers）にデプロイします。

## 必要なもの

- [uv](https://docs.astral.sh/uv/) 0.12.3 以上（`uv self update` で更新）
- Node.js（wrangler が内部で使用）

## セットアップ

```powershell
uv sync
```

## ローカルで起動

通常の FastAPI として起動（開発はこちらが速い）:

```powershell
uv run fastapi dev src/app/main.py
```

- API: http://127.0.0.1:8000
- ドキュメント (Swagger UI): http://127.0.0.1:8000/docs

Workers と同じ環境で起動:

```powershell
uv run pywrangler dev
```

- API: http://localhost:8787

## デプロイ

```powershell
npx wrangler login      # 初回のみ
uv run pywrangler deploy
```

## 構成

| パス | 内容 |
|---|---|
| `src/app/` | FastAPI アプリ本体 |
| `src/worker.py` | Workers の入口（FastAPI を ASGI で公開） |
| `wrangler.jsonc` | Workers の設定 |
| `pyproject.toml` | 依存パッケージ |

## エンドポイント

| メソッド | パス | 内容 |
|---|---|---|
| GET | `/` | ヘルスチェック |
| GET | `/api/items` | 一覧 |
| GET | `/api/items/{item_id}` | 1件取得 |
| POST | `/api/items` | 追加（`{"name": "..."}`） |

> items は今はメモリ上に保持しています。Workers ではリクエスト間でデータが残らないので、今後 D1 に移行予定です。
