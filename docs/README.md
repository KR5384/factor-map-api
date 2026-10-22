# ドキュメント

設計書・メモ置き場。Markdown で書き、コードと同じく PR でレビューする。
(セットアップや起動手順はルートの [README](../README.md) を参照)

## 目次
- [backend/overview.md](backend/overview.md) — バックエンド全体像
- [backend/api.md](backend/api.md) — API 仕様
- [backend/ai-prompt.md](backend/ai-prompt.md) — Workers AI のモデル・プロンプト方針
- [backend/todo.md](backend/todo.md) — 未決事項・課題
- [decisions/](decisions/) — 設計判断の記録 (ADR)。[テンプレ](decisions/0000-template.md)
- [meeting-notes/](meeting-notes/) — 議事録

## ルール
- 1ファイル1テーマ。ファイルを足したらこの目次にも追記する
- 未確定のことは確定事項と混ぜず、`todo.md` に書く
- 大きな設計判断は `decisions/` に連番で残す (例: `0001-ai-model.md`)
