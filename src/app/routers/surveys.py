"""アンケート保存エンドポイント (API v1)。

- POST /api/v1/surveys/pre   事前アンケート保存 (F-04 / Req 4.5, 4.6)
- POST /api/v1/surveys/post  事後アンケート保存 (F-14 / Req 12.5, 12.6)

契約は factor-map-web/worker/index.ts と同一:
  - 成功: { "ok": true, "data": {...} } を 200 で返す
  - 入力不正: { "ok": false, "error": {...} } を 400 で返す
  - セッション未検出: 404 (SESSION_NOT_FOUND)
  - 保存失敗: 500 (SERVER_ERROR)
D1 へ prepared statement で永続化する。
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Request
from pydantic import BaseModel

from app.db import get_db, session_exists
from app.responses import (
    ok_response,
    server_error,
    session_not_found,
    validation_error,
)

router = APIRouter(prefix="/api/v1/surveys", tags=["surveys"])

SURVEY_SCALE_MIN = 1
SURVEY_SCALE_MAX = 5
FREE_TEXT_MAX_LENGTH = 1000


def _is_valid_scale(v: object) -> bool:
    """clarity/conviction が 1〜5 の整数か (bool は除外)。"""
    return (
        isinstance(v, int)
        and not isinstance(v, bool)
        and SURVEY_SCALE_MIN <= v <= SURVEY_SCALE_MAX
    )


def _is_valid_free_text(v: object) -> bool:
    """自由記述が未指定、または 1000 文字以内の文字列か。"""
    if v is None:
        return True
    return isinstance(v, str) and len(v) <= FREE_TEXT_MAX_LENGTH


def _normalize_free_text(v: object) -> str | None:
    return v if isinstance(v, str) else None


class PreSurveyRequest(BaseModel):
    sessionId: str | None = None
    clarity: object | None = None
    freeText: str | None = None


class PostSurveyRequest(BaseModel):
    sessionId: str | None = None
    clarity: object | None = None
    conviction: object | None = None
    freeText: str | None = None


@router.post("/pre")
async def post_pre_survey(request: Request):
    body = await request.json()
    if not isinstance(body, dict):
        return validation_error("リクエストボディが不正です")

    session_id = body.get("sessionId")
    clarity = body.get("clarity")
    free_text = body.get("freeText")

    if not isinstance(session_id, str) or len(session_id) == 0:
        return validation_error("sessionId が指定されていません", ["sessionId"])
    if not _is_valid_scale(clarity):
        return validation_error("clarityは1〜5で指定してください", ["clarity"])
    if not _is_valid_free_text(free_text):
        return validation_error(
            "freeTextは1000文字以内で指定してください", ["freeText"]
        )

    db = get_db(request)

    try:
        exists = await session_exists(db, session_id)
    except Exception:
        return server_error()
    if not exists:
        return session_not_found()

    pre_survey_id = str(uuid.uuid4())
    try:
        await (
            db.prepare(
                "INSERT INTO pre_survey (id, session_id, clarity, free_text) "
                "VALUES (?, ?, ?, ?)"
            )
            .bind(pre_survey_id, session_id, clarity, _normalize_free_text(free_text))
            .run()
        )
    except Exception:
        return server_error()

    return ok_response({"preSurveyId": pre_survey_id})


@router.post("/post")
async def post_post_survey(request: Request):
    body = await request.json()
    if not isinstance(body, dict):
        return validation_error("リクエストボディが不正です")

    session_id = body.get("sessionId")
    clarity = body.get("clarity")
    conviction = body.get("conviction")
    free_text = body.get("freeText")

    if not isinstance(session_id, str) or len(session_id) == 0:
        return validation_error("sessionId が指定されていません", ["sessionId"])
    if not _is_valid_scale(clarity):
        return validation_error("clarityは1〜5で指定してください", ["clarity"])
    if not _is_valid_scale(conviction):
        return validation_error(
            "convictionは1〜5で指定してください", ["conviction"]
        )
    if not _is_valid_free_text(free_text):
        return validation_error(
            "freeTextは1000文字以内で指定してください", ["freeText"]
        )

    db = get_db(request)

    try:
        exists = await session_exists(db, session_id)
    except Exception:
        return server_error()
    if not exists:
        return session_not_found()

    post_survey_id = str(uuid.uuid4())
    try:
        await (
            db.prepare(
                "INSERT INTO post_survey "
                "(id, session_id, clarity, conviction, free_text) "
                "VALUES (?, ?, ?, ?, ?)"
            )
            .bind(
                post_survey_id,
                session_id,
                clarity,
                conviction,
                _normalize_free_text(free_text),
            )
            .run()
        )
    except Exception:
        return server_error()

    return ok_response({"postSurveyId": post_survey_id})
