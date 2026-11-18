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

Workers と同じ環境で起動（D1 はローカル版を使う。手順は「ローカルでのテスト」の 3）:

```powershell
uv run pywrangler dev
```

- API: http://localhost:8787

## デプロイ

初回だけ、D1 のデータベースを作ってテーブルを用意する:

```powershell
npx wrangler login
npx wrangler d1 create factor-map-db                                   # 表示された database_id を wrangler.jsonc に書く
npx wrangler d1 execute factor-map-db --remote --file=db/schema.sql    # 本番の D1 にテーブルを作る
```

デプロイ:

```powershell
uv run pywrangler deploy
```

> `wrangler.jsonc` は英語（ASCII）だけで書く。日本語を入れると pywrangler が Windows で読み込めずに止まる。

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
| POST | `/api/v1/surveys/pre` | 利用同意＋事前アンケート（診断IDを発行） |
| POST | `/api/v1/factor-analyses` | 診断（20問の採点・保存・結果を返す） |
| POST | `/api/v1/surveys/post` | 事後アンケート |

仕様は Box の `10_アプリ開発/API仕様書.xlsx`（API-01〜03）。テーブル定義は `db/schema.sql`。

- DB は `src/app/db.py` の `Database`（`fetch_one` / `execute`）経由で使う。どの DB を使うかは自動で決まる。

| 動かし方 | 使う DB |
|---|---|
| Workers（`pywrangler dev` / デプロイ後） | **D1**（`wrangler.jsonc` の `"binding": "DB"`） |
| `fastapi dev` | SQLite（`local.db`） |
| `pytest` | SQLite（メモリ上。テストごとに空） |
- 採点の重み（`src/app/scoring.py` の `WEIGHTS`）は仮。診断チームの重みの表が届いたら差し替える。

> items は今はメモリ上に保持しています。Workers ではリクエスト間でデータが残らないので、今後 D1 に移行予定です。

## ローカルでのテスト

テストのやり方は3つある。**コードを直したらまず 1 を流し**、実際の値を確かめたいときに 2、本番と同じ Workers + D1 で確かめたいときに 3 を使う。

### 1. 自動テスト（pytest）

```powershell
uv run pytest                                  # 全部（約4秒）
uv run pytest -v                               # テスト名を1件ずつ表示
uv run pytest tests/test_scoring.py            # 採点ロジックだけ
uv run pytest -k post                          # 名前に post を含むテストだけ
```

- テストごとに**メモリ上の空の SQLite** を作り、`db/schema.sql` でテーブルを作ってから API を呼ぶ。ファイルは作らないので、何度流してもよい。
- テストファイル

| ファイル | 内容 |
|---|---|
| `tests/test_api.py` | 3本の API（入力チェック、DBへの保存内容、送信の順番、再送信、A群／B群） |
| `tests/test_scoring.py` | 採点（四捨五入、表示ルール、つながり） |
| `tests/test_db.py` | DB の選び方（D1 があれば D1）と、D1 用クラスの動き（D1 と同じ呼び方をする偽物で確認） |
| `tests/conftest.py` | テスト用の DB と、リクエストの見本（`pre_body` / `answers` / `post_body`） |

### 2. サーバーを起動して手で呼ぶ

```powershell
uv run fastapi dev src/app/main.py
```

- 起動したフォルダに `local.db`（SQLite）ができ、そこに保存される。テーブルは起動時に自動で作る。
- **Swagger UI（http://127.0.0.1:8000/docs）** を開くと、ブラウザから API を試せる（各 API の「Try it out」）。

PowerShell から呼ぶ場合（サーバーとは別のウィンドウで）:

```powershell
$base = "http://127.0.0.1:8000/api/v1"

# API-01 事前アンケート（診断IDが返る）
$pre = Invoke-RestMethod -Method Post "$base/surveys/pre" -ContentType "application/json" -Body '{"consent":true,"consent_version":"2026-11-v1","client_version":"web-0.3.0","pre_frequency":2,"pre_explain":2,"pre_relation":1,"pre_causes":[3,9],"age_group":"30s"}'
$pre

# API-02 診断（20問すべて3、Q5とQ6だけ5）
$answers = @{}; 1..20 | ForEach-Object { $answers["q{0:D2}" -f $_] = 3 }
$answers["q05"] = 5; $answers["q06"] = 5
$fa = Invoke-RestMethod -Method Post "$base/factor-analyses" -ContentType "application/json" -Body (@{ diagnosis_id = $pre.diagnosis_id; answers = $answers } | ConvertTo-Json)
$fa.shown

# API-03 事後アンケート（日本語を送るときは UTF-8 のバイト列にする。Windows PowerShell 5.1 の仕様）
$body = @{ diagnosis_id = $pre.diagnosis_id; post_explain = 4; post_relation = 4; post_fit = 5; post_discovery = 3; post_comment = "テスト" } | ConvertTo-Json
Invoke-RestMethod -Method Post "$base/surveys/post" -ContentType "application/json; charset=utf-8" -Body ([System.Text.Encoding]::UTF8.GetBytes($body))
```

- エラーの中身を見るとき: `try { <上のコマンド> } catch { $_.ErrorDetails.Message }`
- テストデータとして保存したいとき: `-Headers @{ "X-Test-Mode" = "1" }` を付ける（`is_test=1` になる）

保存された中身を見る:

```powershell
uv run python -c "import sqlite3; c=sqlite3.connect('local.db'); [print(r) for r in c.execute('SELECT diagnosis_id, status, grp, is_test, shown_1, main_category_id, post_explain FROM diagnoses')]"
```

（VS Code なら拡張機能「SQLite Viewer」で `local.db` を開いても見られる）

### 3. Workers + D1（ローカル版）で動かす

本番と同じ Workers の環境で、D1 はパソコンの中のローカル版を使う。Cloudflare 上には何も作らない。

```powershell
# 初回と、db/schema.sql を変えたとき：ローカルの D1 にテーブルを作る
npx wrangler d1 execute factor-map-db --local --file=db/schema.sql

# 起動（初回はパッケージの準備で数分かかる。「Ready on http://127.0.0.1:8787」が出たら使える）
uv run pywrangler dev
```

- 呼び方は 2 と同じ。`$base` を `http://127.0.0.1:8787/api/v1` にする。
- 保存された中身を見る:

```powershell
npx wrangler d1 execute factor-map-db --local --command "SELECT diagnosis_id, status, shown_1, post_explain FROM diagnoses"
```

- データを消す: `npx wrangler d1 execute factor-map-db --local --command "DELETE FROM diagnoses"`
- ローカルの D1 のデータは `.wrangler/state/` に保存される（Git には入らない）。

### 環境変数（fastapi dev のとき）

| 名前 | 既定値 | 内容 |
|---|---|---|
| `FACTOR_MAP_SQLITE` | `local.db` | 使う SQLite ファイルのパス。**変わるのは SQLite ファイルの場所だけ**。D1 を使うかどうかは環境変数ではなく、Workers で動いているか（D1 のバインディングがあるか）で決まる |
| `ENABLE_GROUP_B` | `false` | `true` にすると事前アンケートで A／B をランダムに振る（Workers での設定方法は未対応。今は Workers では常に A） |

```powershell
$env:FACTOR_MAP_SQLITE = "test2.db"   # 別のファイルで試す
$env:ENABLE_GROUP_B = "true"          # B群を混ぜる
uv run fastapi dev src/app/main.py
```

- 環境変数はそのウィンドウだけで有効。元に戻すときは `Remove-Item Env:FACTOR_MAP_SQLITE` などで消す。

### データを消してやり直す

サーバーを止めて（Ctrl+C）、`local.db` を消す。次に起動したとき空のテーブルが作られる。

```powershell
Remove-Item local.db
```

> `db/schema.sql` を変えたときも、`local.db` を消してから起動する（`CREATE TABLE IF NOT EXISTS` なので、古いテーブルは作り直されない）。
