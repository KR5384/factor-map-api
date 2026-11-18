"""API-01〜03 のテスト。DB は SQLite（メモリ上）。"""

import uuid

import pytest

from app.routers import diagnoses
from conftest import answers, post_body, pre_body

PRE, FA, POST = "/api/v1/surveys/pre", "/api/v1/factor-analyses", "/api/v1/surveys/post"


def row(db, diagnosis_id):
    return dict(db.conn.execute("SELECT * FROM diagnoses WHERE diagnosis_id = ?", [diagnosis_id]).fetchone())


def start(client, **over):
    res = client.post(PRE, json=pre_body(**over))
    assert res.status_code == 201, res.text
    return res.json()["diagnosis_id"]


def diagnose(client, did, **ans):
    res = client.post(FA, json={"diagnosis_id": did, "answers": answers(**ans)})
    assert res.status_code == 200, res.text
    return res.json()


def assert_error(res, status, code, field=None):
    assert res.status_code == status, res.text
    err = res.json()["error"]
    assert err["code"] == code
    if field:
        assert err["field"] == field


# ---------------------------------------------------------------- 通しの流れ
def test_full_flow_saves_everything(client, db):
    res = client.post(PRE, json=pre_body())
    assert res.status_code == 201
    body = res.json()
    did = body["diagnosis_id"]
    assert uuid.UUID(did).version == 4
    assert body == {"diagnosis_id": did, "group": "A", "status": "pre_done"}

    result = diagnose(client, did, q05=5, q06=5, q17=5, q18=4)  # 分類3=100点、分類9=88点
    assert [s["category_id"] for s in result["scores"]] == list(range(1, 11))
    assert result["shown"] == [
        {"rank": 1, "category_id": 3, "score": 100},
        {"rank": 2, "category_id": 9, "score": 88},
    ]
    assert result["main_category_id"] == 3
    assert result["result_type_id"] == "T03"
    assert result["low_moyamoya"] is False

    res = client.post(POST, json=post_body(did))
    assert res.status_code == 200
    assert res.json() == {"diagnosis_id": did, "status": "completed"}

    r = row(db, did)
    assert r["status"] == "completed" and r["grp"] == "A" and r["is_test"] == 0
    assert r["consent_version"] == "2026-11-v1" and r["client_version"] == "web-0.3.0"
    assert (r["pre_frequency"], r["pre_explain"], r["pre_relation"], r["age_group"]) == (2, 2, 1, "30s")
    assert [r[f"pre_cause_{c:02d}"] for c in range(1, 11)] == [0, 0, 1, 0, 0, 0, 0, 0, 1, 0]
    assert (r["pre_cause_none"], r["pre_cause_unknown"]) == (0, 0)
    assert r["q05"] == 5 and r["q18"] == 4 and r["q01"] == 3
    assert r["score_03"] == 100 and r["score_09"] == 88 and r["score_01"] == 50
    assert (r["shown_count"], r["shown_1"], r["shown_2"], r["shown_3"]) == (2, 3, 9, None)
    assert (r["main_category_id"], r["result_type_id"], r["low_moyamoya"]) == (3, "T03", 0)
    assert r["scoring_version"] == result["scoring_version"]
    assert (r["post_explain"], r["post_relation"], r["post_fit"], r["post_discovery"]) == (4, 4, 5, 3)
    assert r["post_comment"] == "情報の多さと考えすぎが関係していると分かった"
    for col in ("created_at", "answered_at", "post_at"):
        assert r[col].endswith("Z") and len(r[col]) == 20


# ---------------------------------------------------------------- API-01
def test_pre_test_mode_header_sets_is_test(client, db):
    res = client.post(PRE, json=pre_body(), headers={"X-Test-Mode": "1"})
    assert row(db, res.json()["diagnosis_id"])["is_test"] == 1


@pytest.mark.parametrize("causes, none, unknown", [([98], 1, 0), ([99], 0, 1)])
def test_pre_none_or_unknown(client, db, causes, none, unknown):
    r = row(db, start(client, pre_causes=causes))
    assert (r["pre_cause_none"], r["pre_cause_unknown"]) == (none, unknown)
    assert sum(r[f"pre_cause_{c:02d}"] for c in range(1, 11)) == 0


def test_pre_age_group_optional(client, db):
    body = pre_body()
    del body["age_group"]
    res = client.post(PRE, json=body)
    assert res.status_code == 201
    assert row(db, res.json()["diagnosis_id"])["age_group"] is None


@pytest.mark.parametrize("over, field", [
    ({"consent": False}, "consent"),
    ({"consent": "true"}, "consent"),
    ({"consent_version": ""}, "consent_version"),
    ({"pre_frequency": 5}, "pre_frequency"),
    ({"pre_explain": 0}, "pre_explain"),
    ({"pre_explain": 6}, "pre_explain"),
    ({"pre_explain": "3"}, "pre_explain"),
    ({"pre_explain": True}, "pre_explain"),
    ({"pre_relation": None}, "pre_relation"),
    ({"pre_causes": []}, "pre_causes"),
    ({"pre_causes": [3, 3]}, "pre_causes"),
    ({"pre_causes": [11]}, "pre_causes"),
    ({"pre_causes": [98, 3]}, "pre_causes"),
    ({"pre_causes": [98, 99]}, "pre_causes"),
    ({"age_group": "60s"}, "age_group"),
])
def test_pre_validation(client, db, over, field):
    res = client.post(PRE, json=pre_body(**over))
    assert_error(res, 400, "VALIDATION_ERROR", field)
    assert db.conn.execute("SELECT COUNT(*) FROM diagnoses").fetchone()[0] == 0


def test_pre_missing_field(client):
    body = pre_body()
    del body["pre_frequency"]
    assert_error(client.post(PRE, json=body), 400, "VALIDATION_ERROR", "pre_frequency")


def test_pre_broken_json(client):
    res = client.post(PRE, content="{broken", headers={"Content-Type": "application/json"})
    assert_error(res, 400, "VALIDATION_ERROR")


def test_non_utf8_body_is_validation_error(client):
    # Shift_JIS の「テスト」。UTF-8 として読めない本文
    res = client.post(POST, content=b'{"diagnosis_id":"x","post_comment":"\x83e\x83X\x83g"}',
                      headers={"Content-Type": "application/json"})
    assert_error(res, 400, "VALIDATION_ERROR")


def test_japanese_comment_saved_as_is(client, db):
    did = start(client)
    diagnose(client, did)
    text = "情報の多さと考えすぎが関係していると分かった"
    assert client.post(POST, json=post_body(did, post_comment=text)).status_code == 200
    assert row(db, did)["post_comment"] == text


def test_pre_group_b(client, db, monkeypatch):
    monkeypatch.setenv("ENABLE_GROUP_B", "true")
    monkeypatch.setattr(diagnoses.random, "choice", lambda _: "B")
    res = client.post(PRE, json=pre_body())
    assert res.json()["group"] == "B"
    assert row(db, res.json()["diagnosis_id"])["grp"] == "B"


def test_pre_group_b_disabled_by_default(client, monkeypatch):
    monkeypatch.delenv("ENABLE_GROUP_B", raising=False)
    groups = {client.post(PRE, json=pre_body()).json()["group"] for _ in range(20)}
    assert groups == {"A"}


# ---------------------------------------------------------------- API-02
def test_fa_unknown_id(client):
    res = client.post(FA, json={"diagnosis_id": str(uuid.uuid4()), "answers": answers()})
    assert_error(res, 404, "NOT_FOUND")


@pytest.mark.parametrize("ans, field", [
    ({"q20": None}, "answers.q20"),
    ({"q07": 6}, "answers.q07"),
    ({"q01": 0}, "answers.q01"),
    ({"q03": "5"}, "answers.q03"),
])
def test_fa_validation(client, db, ans, field):
    did = start(client)
    res = client.post(FA, json={"diagnosis_id": did, "answers": answers(**ans)})
    assert_error(res, 400, "VALIDATION_ERROR", field)
    assert row(db, did)["status"] == "pre_done"


def test_fa_missing_answer(client):
    did = start(client)
    a = answers()
    del a["q12"]
    assert_error(client.post(FA, json={"diagnosis_id": did, "answers": a}), 400, "VALIDATION_ERROR", "answers.q12")


def test_fa_resend_same_returns_saved_result(client, db):
    did = start(client)
    first = diagnose(client, did, q05=5, q06=5)
    answered_at = row(db, did)["answered_at"]
    second = diagnose(client, did, q05=5, q06=5)
    assert second == first
    assert row(db, did)["answered_at"] == answered_at  # 上書きしていない


def test_fa_resend_different_is_409(client, db):
    did = start(client)
    diagnose(client, did, q05=5)
    res = client.post(FA, json={"diagnosis_id": did, "answers": answers(q05=1)})
    assert_error(res, 409, "ALREADY_SUBMITTED")
    assert row(db, did)["q05"] == 5


def test_fa_low_moyamoya(client, db):
    did = start(client)
    result = diagnose(client, did, default=1)
    assert result["low_moyamoya"] is True
    assert result["shown"] == [] and result["main_category_id"] is None and result["result_type_id"] is None
    r = row(db, did)
    assert (r["low_moyamoya"], r["shown_count"], r["shown_1"], r["main_category_id"]) == (1, 0, None, None)


def test_fa_resend_after_completed_still_returns_result(client):
    did = start(client)
    first = diagnose(client, did, q01=5)
    client.post(POST, json=post_body(did))
    assert diagnose(client, did, q01=5) == first


# ---------------------------------------------------------------- API-03
def test_post_before_diagnosis_is_order_error(client, db):
    did = start(client)
    assert_error(client.post(POST, json=post_body(did)), 409, "ORDER_ERROR")
    assert row(db, did)["post_explain"] is None


def test_post_unknown_id(client):
    assert_error(client.post(POST, json=post_body(str(uuid.uuid4()))), 404, "NOT_FOUND")


@pytest.mark.parametrize("missing", ["post_fit", "post_discovery"])
def test_post_group_a_requires_fit_and_discovery(client, missing):
    did = start(client)
    diagnose(client, did)
    body = post_body(did)
    del body[missing]
    assert_error(client.post(POST, json=body), 400, "VALIDATION_ERROR", missing)


def test_post_group_b_ignores_fit_and_discovery(client, db, monkeypatch):
    monkeypatch.setenv("ENABLE_GROUP_B", "true")
    monkeypatch.setattr(diagnoses.random, "choice", lambda _: "B")
    did = start(client)
    diagnose(client, did)
    assert client.post(POST, json=post_body(did)).status_code == 200  # A3・A4 を送ってきても
    r = row(db, did)
    assert (r["post_fit"], r["post_discovery"]) == (None, None)  # 保存しない
    assert r["post_explain"] == 4


def test_post_group_b_without_fit(client, monkeypatch):
    monkeypatch.setenv("ENABLE_GROUP_B", "true")
    monkeypatch.setattr(diagnoses.random, "choice", lambda _: "B")
    did = start(client)
    diagnose(client, did)
    body = post_body(did)
    del body["post_fit"], body["post_discovery"]
    assert client.post(POST, json=body).status_code == 200


@pytest.mark.parametrize("comment, saved", [("  よかった  ", "よかった"), ("   ", None), (None, None), ("あ" * 200, "あ" * 200)])
def test_post_comment(client, db, comment, saved):
    did = start(client)
    diagnose(client, did)
    assert client.post(POST, json=post_body(did, post_comment=comment)).status_code == 200
    assert row(db, did)["post_comment"] == saved


@pytest.mark.parametrize("over, field", [
    ({"post_comment": "あ" * 201}, "post_comment"),
    ({"post_explain": 6}, "post_explain"),
    ({"post_relation": "4"}, "post_relation"),
    ({"post_fit": 0}, "post_fit"),
])
def test_post_validation(client, db, over, field):
    did = start(client)
    diagnose(client, did)
    assert_error(client.post(POST, json=post_body(did, **over)), 400, "VALIDATION_ERROR", field)
    assert row(db, did)["status"] == "answered"


def test_post_resend_same_ok_and_different_409(client, db):
    did = start(client)
    diagnose(client, did)
    assert client.post(POST, json=post_body(did)).status_code == 200
    post_at = row(db, did)["post_at"]
    assert client.post(POST, json=post_body(did)).status_code == 200
    assert row(db, did)["post_at"] == post_at
    assert_error(client.post(POST, json=post_body(did, post_explain=1)), 409, "ALREADY_SUBMITTED")
    assert row(db, did)["post_explain"] == 4


# ---------------------------------------------------------------- 共通
def test_unknown_path_uses_error_format(client):
    assert_error(client.get("/api/v1/nothing"), 404, "NOT_FOUND")


def test_unknown_fields_are_ignored(client):
    assert client.post(PRE, json=pre_body(extra="x")).status_code == 201
