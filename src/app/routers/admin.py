"""管理者 API (F-19 / Requirements 18, 19, 20, 21) — API v1。

factor-map-web/worker/index.ts の管理者ハンドラを FastAPI へ移植したもの。
  - POST /api/v1/admin/login        管理者認証 (21.1〜21.5)
  - GET  /api/v1/admin/diagnoses     全診断データ取得 (18.1〜18.3)
  - GET  /api/v1/admin/aggregate     集計 (20.1〜20.3)
  - GET  /api/v1/admin/export.csv    CSV 出力 (19.1〜19.3)

認証されない要求では D1 を変更/参照しない (18.3, 19.3, 20.3, 21.1, 21.5)。
"""

from __future__ import annotations

import io
import csv as _csv
import json as _json

from fastapi import APIRouter, Request
from fastapi.responses import Response

from app.admin_auth import (
    clear_failures,
    credentials_match,
    extract_credentials,
    is_authenticated,
    is_locked,
    issue_access_token,
    now_seconds,
    record_failure,
    requester_key,
)
from app.db import get_db
from app.responses import (
    auth_required,
    locked_response,
    ok_response,
    server_error,
)

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])

CSV_COLUMNS = [
    "sessionId",
    "consented",
    "consentAt",
    "sessionCreatedAt",
    "preClarity",
    "preFreeText",
    "diagnosisTopFactor",
    "diagnosisResult",
    "postClarity",
    "postConviction",
    "postFreeText",
]


def _safe_parse(value):
    """JSON 文字列を安全にパース (失敗時は生文字列)。"""
    if not isinstance(value, str):
        return value
    try:
        return _json.loads(value)
    except Exception:
        return value


# ============================================================
# POST /api/v1/admin/login (Requirements 21.1〜21.5)
# ============================================================


@router.post("/login")
async def admin_login(request: Request):
    now = now_seconds()
    key = requester_key(request)

    # ロック中は資格情報の照合を行わず拒否する (21.4)
    if is_locked(key, now):
        return locked_response()

    try:
        body = await request.json()
    except Exception:
        body = None

    if isinstance(body, dict):
        creds = {
            "username": body.get("username")
            if isinstance(body.get("username"), str)
            else None,
            "password": body.get("password")
            if isinstance(body.get("password"), str)
            else None,
            "token": body.get("token")
            if isinstance(body.get("token"), str)
            else None,
        }
    else:
        creds = extract_credentials(request)

    # ヘッダ経由の資格情報も補完的に許可する
    if not creds.get("token") and not creds.get("username"):
        header_creds = extract_credentials(request)
        creds["token"] = creds.get("token") or header_creds.get("token")
        creds["username"] = creds.get("username") or header_creds.get("username")
        creds["password"] = creds.get("password") or header_creds.get("password")

    if credentials_match(request, creds):
        clear_failures(key)
        return ok_response({"token": issue_access_token(request)})

    # 認証失敗を記録 (21.1, 21.4)
    record_failure(key, now)
    if is_locked(key, now):
        return locked_response()
    return auth_required("認証に失敗しました")


# ============================================================
# GET /api/v1/admin/diagnoses (Requirements 18.1〜18.3)
# ============================================================


@router.get("/diagnoses")
async def admin_diagnoses(request: Request):
    if not is_authenticated(request):
        return auth_required()

    db = get_db(request)
    try:
        res = await db.prepare(
            "SELECT session_id, answers_json, result_json "
            "FROM diagnosis ORDER BY created_at ASC"
        ).all()
        rows = res.results if res is not None else []
        data = [
            {
                "sessionId": row.session_id,
                "answers": _safe_parse(row.answers_json),
                "result": _safe_parse(row.result_json),
            }
            for row in (rows or [])
        ]
        # 0件時も成功として空配列を返す (18.2)
        return ok_response(data)
    except Exception:
        return server_error("診断データの取得に失敗しました")


# ============================================================
# GET /api/v1/admin/aggregate (Requirements 20.1〜20.3)
# ============================================================


@router.get("/aggregate")
async def admin_aggregate(request: Request):
    if not is_authenticated(request):
        return auth_required()

    db = get_db(request)

    def _to_item(row) -> dict:
        count = (getattr(row, "cnt", 0) if row is not None else 0) or 0
        avg = getattr(row, "avg", None) if row is not None else None
        # 0件時は average を null とし件数0を返す (20.2)
        return {"count": count, "average": avg if count > 0 else None}

    try:
        pre_clarity = await db.prepare(
            "SELECT COUNT(clarity) AS cnt, AVG(clarity) AS avg "
            "FROM pre_survey WHERE clarity BETWEEN 1 AND 5"
        ).first()
        post_clarity = await db.prepare(
            "SELECT COUNT(clarity) AS cnt, AVG(clarity) AS avg "
            "FROM post_survey WHERE clarity BETWEEN 1 AND 5"
        ).first()
        post_conviction = await db.prepare(
            "SELECT COUNT(conviction) AS cnt, AVG(conviction) AS avg "
            "FROM post_survey WHERE conviction BETWEEN 1 AND 5"
        ).first()

        return ok_response(
            {
                "preClarity": _to_item(pre_clarity),
                "postClarity": _to_item(post_clarity),
                "postConviction": _to_item(post_conviction),
            }
        )
    except Exception:
        return server_error("集計に失敗しました")


# ============================================================
# GET /api/v1/admin/export.csv (Requirements 19.1〜19.3)
# ============================================================


@router.get("/export.csv")
async def admin_export_csv(request: Request):
    if not is_authenticated(request):
        return auth_required()

    db = get_db(request)
    try:
        res = await db.prepare(
            """SELECT
                 s.id            AS session_id,
                 s.consented     AS consented,
                 s.consent_at    AS consent_at,
                 s.created_at    AS session_created_at,
                 pre.clarity     AS pre_clarity,
                 pre.free_text   AS pre_free_text,
                 diag.top_factor AS diag_top_factor,
                 diag.result_json AS diag_result,
                 post.clarity    AS post_clarity,
                 post.conviction AS post_conviction,
                 post.free_text  AS post_free_text
               FROM sessions s
               LEFT JOIN pre_survey pre
                 ON pre.id = (SELECT id FROM pre_survey WHERE session_id = s.id ORDER BY created_at DESC LIMIT 1)
               LEFT JOIN diagnosis diag
                 ON diag.id = (SELECT id FROM diagnosis WHERE session_id = s.id ORDER BY created_at DESC LIMIT 1)
               LEFT JOIN post_survey post
                 ON post.id = (SELECT id FROM post_survey WHERE session_id = s.id ORDER BY created_at DESC LIMIT 1)
               ORDER BY s.created_at ASC"""
        ).all()
        rows = (res.results if res is not None else []) or []
    except Exception:
        return server_error("CSV出力に失敗しました")

    buffer = io.StringIO()
    # RFC 4180: 改行は CRLF、必要時のみクォート
    writer = _csv.writer(buffer, lineterminator="\r\n", quoting=_csv.QUOTE_MINIMAL)
    writer.writerow(CSV_COLUMNS)

    for r in rows:
        writer.writerow(
            [
                _cell(getattr(r, "session_id", None)),
                _cell(getattr(r, "consented", None)),
                _cell(getattr(r, "consent_at", None)),
                _cell(getattr(r, "session_created_at", None)),
                _cell(getattr(r, "pre_clarity", None)),
                _cell(getattr(r, "pre_free_text", None)),
                _cell(getattr(r, "diag_top_factor", None)),
                _cell(getattr(r, "diag_result", None)),
                _cell(getattr(r, "post_clarity", None)),
                _cell(getattr(r, "post_conviction", None)),
                _cell(getattr(r, "post_free_text", None)),
            ]
        )

    csv_text = buffer.getvalue()
    return Response(
        content=csv_text,
        status_code=200,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": 'attachment; filename="moyamoya-export.csv"',
        },
    )


def _cell(value) -> str:
    """CSV セル値を文字列へ正規化 (None/undefined は空文字)。"""
    if value is None:
        return ""
    return str(value)
