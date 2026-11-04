"""共通 API レスポンスヘルパ。

factor-map-web/worker/index.ts の契約と同一の JSON 形を返す:
  成功: { "ok": true, "data": T }
  失敗: { "ok": false, "error": { "code", "message", "fields"? } }

Web 側 (apiClient.ts / errorHandler.ts) はこの形を前提に動くため、
HTTP ステータスとエラーコードを Worker 実装と揃える。
"""

from __future__ import annotations

from typing import Any

from fastapi.responses import JSONResponse


def ok_response(data: Any) -> JSONResponse:
    """成功レスポンス (200)。"""
    return JSONResponse(status_code=200, content={"ok": True, "data": data})


def validation_error(
    message: str, fields: list[str] | None = None
) -> JSONResponse:
    """入力不正 (400 / VALIDATION)。"""
    error: dict[str, Any] = {"code": "VALIDATION", "message": message}
    if fields is not None:
        error["fields"] = fields
    return JSONResponse(status_code=400, content={"ok": False, "error": error})


def session_not_found() -> JSONResponse:
    """セッション未検出 (404 / SESSION_NOT_FOUND)。"""
    return JSONResponse(
        status_code=404,
        content={
            "ok": False,
            "error": {
                "code": "SESSION_NOT_FOUND",
                "message": "指定されたセッションが見つかりません",
            },
        },
    )


def server_error(message: str = "保存に失敗しました") -> JSONResponse:
    """サーバエラー (500 / SERVER_ERROR)。"""
    return JSONResponse(
        status_code=500,
        content={
            "ok": False,
            "error": {"code": "SERVER_ERROR", "message": message},
        },
    )


def auth_required(message: str = "認証が必要です") -> JSONResponse:
    """認証が必要 / 認証失敗 (401 / AUTH_REQUIRED)。"""
    return JSONResponse(
        status_code=401,
        content={
            "ok": False,
            "error": {"code": "AUTH_REQUIRED", "message": message},
        },
    )


def locked_response(
    message: str = "試行回数の上限に達しました。しばらくしてから再試行してください",
) -> JSONResponse:
    """ロック中 (429 / LOCKED)。"""
    return JSONResponse(
        status_code=429,
        content={
            "ok": False,
            "error": {"code": "LOCKED", "message": message},
        },
    )
