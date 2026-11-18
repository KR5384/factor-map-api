"""API-01 事前アンケート／API-02 診断／API-03 事後アンケート（API仕様書.xlsx）。"""

import random
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, Request

from app.db import Database, get_db
from app.errors import ApiError
from app.schemas import CAUSE_NONE, CAUSE_UNKNOWN, FactorAnalysisIn, PostSurveyIn, PreSurveyIn
from app.scoring import QUESTION_KEYS, result_from_row, score
from app.settings import is_enabled

router = APIRouter(prefix="/api/v1", tags=["diagnoses"])

POST_KEYS = ["post_explain", "post_relation", "post_fit", "post_discovery", "post_comment"]


def now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def assign_group(request: Request) -> str:
    """ENABLE_GROUP_B が true なら A／B をランダムに振る。"""
    if is_enabled(request, "ENABLE_GROUP_B"):
        return random.choice(["A", "B"])
    return "A"


def decide_is_test(request: Request, x_test_mode: str | None) -> int:
    """FORCE_TEST_MODE が true なら全件テスト。false でもヘッダー X-Test-Mode: 1 ならテスト。"""
    return 1 if is_enabled(request, "FORCE_TEST_MODE") or x_test_mode == "1" else 0


async def find_row(db: Database, diagnosis_id: str) -> dict:
    row = await db.fetch_one("SELECT * FROM diagnoses WHERE diagnosis_id = ?", [diagnosis_id])
    if row is None:
        raise ApiError(404, "NOT_FOUND", "診断IDが見つかりません")
    return row


async def update_row(db: Database, diagnosis_id: str, from_status: str, cols: dict) -> int:
    sets = ", ".join(f"{k} = ?" for k in cols)
    return await db.execute(
        f"UPDATE diagnoses SET {sets} WHERE diagnosis_id = ? AND status = ?",
        [*cols.values(), diagnosis_id, from_status],
    )


def already_submitted() -> ApiError:
    return ApiError(409, "ALREADY_SUBMITTED", "送信済みです")


# ---------------------------------------------------------------- API-01
@router.post("/surveys/pre", status_code=201)
async def post_pre_survey(
    body: PreSurveyIn,
    request: Request,
    x_test_mode: str | None = Header(default=None),
    db: Database = Depends(get_db),
):
    diagnosis_id = str(uuid.uuid4())
    group = assign_group(request)
    is_test = decide_is_test(request, x_test_mode)
    causes = set(body.pre_causes)
    cols = {
        "diagnosis_id": diagnosis_id,
        "status": "pre_done",
        "grp": group,
        "is_test": is_test,
        "consent_version": body.consent_version,
        "client_version": body.client_version,
        "created_at": now_utc(),
        "pre_frequency": body.pre_frequency,
        "pre_explain": body.pre_explain,
        "pre_relation": body.pre_relation,
        **{f"pre_cause_{c:02d}": int(c in causes) for c in range(1, 11)},
        "pre_cause_none": int(CAUSE_NONE in causes),
        "pre_cause_unknown": int(CAUSE_UNKNOWN in causes),
        "age_group": body.age_group,
    }
    await db.execute(
        f"INSERT INTO diagnoses ({', '.join(cols)}) VALUES ({', '.join('?' for _ in cols)})",
        list(cols.values()),
    )
    # is_test を返すのは、フロントが「テストモード」の表示を出して本番切り替え漏れに気づけるようにするため
    return {"diagnosis_id": diagnosis_id, "group": group, "status": "pre_done", "is_test": bool(is_test)}


# ---------------------------------------------------------------- API-02
@router.post("/factor-analyses")
async def post_factor_analysis(body: FactorAnalysisIn, db: Database = Depends(get_db)):
    row = await find_row(db, body.diagnosis_id)
    answers = body.answers.model_dump()

    if row["status"] != "pre_done":
        # 送信済み：同じ回答なら保存済みの結果を返す（再読み込み対策）
        if all(row[q] == answers[q] for q in QUESTION_KEYS):
            return result_from_row(row).to_response(body.diagnosis_id)
        raise already_submitted()

    result = score(answers)
    cols = {**answers, **result.to_columns(), "answered_at": now_utc(), "status": "answered"}
    if await update_row(db, body.diagnosis_id, "pre_done", cols) == 0:
        raise already_submitted()
    return result.to_response(body.diagnosis_id)


# ---------------------------------------------------------------- API-03
@router.post("/surveys/post")
async def post_post_survey(body: PostSurveyIn, db: Database = Depends(get_db)):
    row = await find_row(db, body.diagnosis_id)
    if row["status"] == "pre_done":
        raise ApiError(409, "ORDER_ERROR", "診断がまだ終わっていません")

    is_group_b = row["grp"] == "B"
    if not is_group_b:
        for key in ("post_fit", "post_discovery"):
            if getattr(body, key) is None:
                raise ApiError(400, "VALIDATION_ERROR", f"{key} は必須です", key)

    values = body.model_dump(include=set(POST_KEYS))
    if is_group_b:  # B群は結果を見る前に答えるので、A3・A4 は保存しない
        values["post_fit"] = values["post_discovery"] = None

    if row["status"] == "completed":
        if all(row[k] == values[k] for k in POST_KEYS):
            return {"diagnosis_id": body.diagnosis_id, "status": "completed"}
        raise already_submitted()

    cols = {**values, "post_at": now_utc(), "status": "completed"}
    if await update_row(db, body.diagnosis_id, "answered", cols) == 0:
        raise already_submitted()
    return {"diagnosis_id": body.diagnosis_id, "status": "completed"}
