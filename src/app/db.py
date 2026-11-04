"""D1 データベースアクセスの共通ヘルパ。

Cloudflare Python Workers では D1 バインディングは ASGI scope 経由で渡される。
FastAPI のハンドラからは `request.scope["env"].DB` で取得する
(参照: cloudflare/python-workers-examples fastapi-todo)。

ローカルの `uv run fastapi dev` では Workers ランタイムが無く env が存在しないため、
D1 が利用できない場合は明示的に 503 を返して利用者に状況を伝える。
"""

from __future__ import annotations

from fastapi import HTTPException, Request


def get_db(request: Request):
    """ASGI scope から D1 データベースバインディング (DB) を取得する。

    Workers ランタイム外 (ローカルの素の FastAPI) では env が無いため 503 を返す。
    """
    env = request.scope.get("env")
    if env is None:
        raise HTTPException(
            status_code=503,
            detail="D1 is not available outside the Workers runtime",
        )
    db = getattr(env, "DB", None)
    if db is None:
        raise HTTPException(
            status_code=503,
            detail="D1 binding 'DB' is not configured",
        )
    return db


async def session_exists(db, session_id: str) -> bool:
    """sessions テーブルに session_id が存在するか判定する。"""
    row = (
        await db.prepare("SELECT id FROM sessions WHERE id = ?")
        .bind(session_id)
        .first()
    )
    return row is not None
