"""DB へのアクセス。

ルーターは Database（fetch_one / execute の2つだけ）を通して DB を使う。
- Workers 上で D1 のバインディング（wrangler.jsonc の "binding": "DB"）があれば D1Database
- それ以外（ローカルの fastapi dev・テスト）は SQLiteDatabase
"""

import os
from pathlib import Path
from typing import Any, Protocol, Sequence

from fastapi import Request

SCHEMA_PATH = Path(__file__).resolve().parents[2] / "db" / "schema.sql"
D1_BINDING = "DB"


class Database(Protocol):
    async def fetch_one(self, sql: str, params: Sequence[Any] = ()) -> dict | None: ...

    async def execute(self, sql: str, params: Sequence[Any] = ()) -> int:
        """SQL を実行し、変更した行数を返す。"""
        ...


class SQLiteDatabase:
    """ローカル開発・テスト用。"""

    def __init__(self, path: str = ":memory:"):
        import sqlite3  # Workers 上では使わないので、ここで読み込む

        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row

    def init_schema(self, schema_path: Path = SCHEMA_PATH) -> None:
        self.conn.executescript(schema_path.read_text(encoding="utf-8"))

    async def fetch_one(self, sql: str, params: Sequence[Any] = ()) -> dict | None:
        row = self.conn.execute(sql, params).fetchone()
        return dict(row) if row else None

    async def execute(self, sql: str, params: Sequence[Any] = ()) -> int:
        cur = self.conn.execute(sql, params)
        self.conn.commit()
        return cur.rowcount


def _to_py(value: Any) -> Any:
    """D1 の戻り値（JS のオブジェクトの場合がある）を Python の dict に直す。"""
    if value is None:
        return None
    if hasattr(value, "to_py"):
        value = value.to_py()
    return value


class D1Database:
    """Cloudflare D1 用。テーブルは wrangler d1 execute で db/schema.sql から作っておく。"""

    def __init__(self, binding: Any):
        self.binding = binding

    def _statement(self, sql: str, params: Sequence[Any]):
        return self.binding.prepare(sql).bind(*params)

    async def fetch_one(self, sql: str, params: Sequence[Any] = ()) -> dict | None:
        row = _to_py(await self._statement(sql, params).first())
        return dict(row) if row else None

    async def execute(self, sql: str, params: Sequence[Any] = ()) -> int:
        result = _to_py(await self._statement(sql, params).run())
        return int(result["meta"]["changes"])


_local_db: SQLiteDatabase | None = None


def _get_local_db() -> SQLiteDatabase:
    global _local_db
    if _local_db is None:
        _local_db = SQLiteDatabase(os.environ.get("FACTOR_MAP_SQLITE", "local.db"))
        _local_db.init_schema()
    return _local_db


def get_db(request: Request) -> Database:
    """FastAPI の依存関係。テストでは app.dependency_overrides で差し替える。"""
    env = request.scope.get("env")  # Workers 上でだけ入っている
    binding = getattr(env, D1_BINDING, None) if env is not None else None
    if binding is not None:
        return D1Database(binding)
    return _get_local_db()
