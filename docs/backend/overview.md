# バックエンド概要

## 構成
```
Browser → Cloudflare Python Workers (FastAPI) → Workers AI
                       └→ D1 (移行予定。現状 items はメモリ保持)
```

## 技術スタック
- 実行環境: Cloudflare Workers (Python Workers)
- フレームワーク: FastAPI (`src/app/`)、入口は `src/worker.py`
- パッケージ管理: uv
- AI: Workers AI (モデル: 未定)
- DB: D1 (予定)

## ディレクトリ
| パス | 内容 |
|---|---|
| `src/app/main.py` | FastAPI 本体、CORS、ルーター登録 |
| `src/app/routers/` | エンドポイントごとのルーター |
| `src/worker.py` | Workers の入口 |

## ローカル起動
ルートの [README](../../README.md) を参照。
