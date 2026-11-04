"""診断結果保存エンドポイント (API v1)。

- POST /api/v1/factor-analyses   診断結果保存 (F-11 / Req 9.7, 9.8)

契約は factor-map-web/worker/index.ts の handleDiagnosis と同一:
  - sessionId 非空・answers/result 必須を検証
  - result.topFactorId を集計用に top_factor として取り出す
  - 成功: { "ok": true, "data": { "diagnosisId": ... } }
  - 保存失敗: 500 (SERVER_ERROR)
"""

from __future__ import annotations

import json as _json
import uuid

from fastapi import APIRouter, Request

from app.db import get_db
from app.responses import ok_response, server_error, validation_error

router = APIRouter(prefix="/api/v1/factor-analyses", tags=["factor-analyses"])


def _extract_top_factor(result: object) -> str:
    """result から topFactorId を取り出す (無ければ空文字)。"""
    if isinstance(result, dict):
        top = result.get("topFactorId")
        if isinstance(top, str):
            return top
    return ""


@router.post("")
async def post_factor_analysis(request: Request):
    body = await request.json()
    if not isinstance(body, dict):
        return validation_error("リクエストボディが不正です")

    session_id = body.get("sessionId")
    answers = body.get("answers")
    result = body.get("result")

    if not isinstance(session_id, str) or len(session_id) == 0:
        return validation_error("sessionId が指定されていません", ["sessionId"])
    if answers is None:
        return validation_error("answers が指定されていません", ["answers"])
    if result is None:
        return validation_error("result が指定されていません", ["result"])

    top_factor = _extract_top_factor(result)

    db = get_db(request)

    diagnosis_id = str(uuid.uuid4())
    try:
        await (
            db.prepare(
                "INSERT INTO diagnosis "
                "(id, session_id, answers_json, result_json, top_factor) "
                "VALUES (?, ?, ?, ?, ?)"
            )
            .bind(
                diagnosis_id,
                session_id,
                _json.dumps(answers, ensure_ascii=False),
                _json.dumps(result, ensure_ascii=False),
                top_factor,
            )
            .run()
        )
    except Exception:
        return server_error()

    return ok_response({"diagnosisId": diagnosis_id})
