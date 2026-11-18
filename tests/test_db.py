"""DB の選び方と D1Database のテスト。

D1 本体はローカルの pytest では動かせないため、D1 と同じ呼び方
（prepare(sql).bind(*params).first() / .run()）をする偽物を SQLite で作って確かめる。
実際の D1 での確認は README の「Workers + D1 で動かす」の手順で行う。
"""

import asyncio
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app import db as db_module
from app.db import D1Database, SQLiteDatabase, get_db
from app.main import app
from conftest import answers, post_body, pre_body


class FakeD1:
    """D1 のバインディングの代わり。戻り値は D1 と同じ形（first は dict、run は {"meta": {"changes": n}}）。"""

    def __init__(self):
        self.sqlite = SQLiteDatabase(":memory:")
        self.sqlite.init_schema()
        self.calls = []

    def prepare(self, sql):
        return FakeStatement(self, sql)


class FakeStatement:
    def __init__(self, d1, sql, params=()):
        self.d1, self.sql, self.params = d1, sql, params

    def bind(self, *params):
        return FakeStatement(self.d1, self.sql, params)

    async def first(self):
        self.d1.calls.append(("first", self.sql))
        return await self.d1.sqlite.fetch_one(self.sql, self.params)

    async def run(self):
        self.d1.calls.append(("run", self.sql))
        changes = await self.d1.sqlite.execute(self.sql, self.params)
        return {"success": True, "meta": {"changes": changes}}


def test_get_db_uses_d1_when_binding_exists():
    binding = FakeD1()
    request = SimpleNamespace(scope={"env": SimpleNamespace(DB=binding)})
    db = get_db(request)
    assert isinstance(db, D1Database) and db.binding is binding


def test_get_db_uses_sqlite_without_env(monkeypatch, tmp_path):
    monkeypatch.setenv("FACTOR_MAP_SQLITE", str(tmp_path / "x.db"))
    monkeypatch.setattr(db_module, "_local_db", None)
    assert isinstance(get_db(SimpleNamespace(scope={})), SQLiteDatabase)
    assert (tmp_path / "x.db").exists()


def test_get_db_uses_sqlite_when_env_has_no_db(monkeypatch, tmp_path):
    monkeypatch.setenv("FACTOR_MAP_SQLITE", str(tmp_path / "y.db"))
    monkeypatch.setattr(db_module, "_local_db", None)
    assert isinstance(get_db(SimpleNamespace(scope={"env": SimpleNamespace()})), SQLiteDatabase)


def test_full_flow_through_d1_adapter():
    fake = FakeD1()
    app.dependency_overrides[get_db] = lambda: D1Database(fake)
    try:
        client = TestClient(app)
        did = client.post("/api/v1/surveys/pre", json=pre_body()).json()["diagnosis_id"]
        fa = client.post("/api/v1/factor-analyses", json={"diagnosis_id": did, "answers": answers(q05=5, q06=5)})
        assert fa.status_code == 200 and fa.json()["main_category_id"] == 5
        assert client.post("/api/v1/surveys/post", json=post_body(did)).status_code == 200
        # 再送信（同じ内容）・違う内容・存在しないID も D1 経由で正しく判定できる
        assert client.post("/api/v1/surveys/post", json=post_body(did)).status_code == 200
        assert client.post("/api/v1/surveys/post", json=post_body(did, post_explain=1)).status_code == 409
        assert client.post("/api/v1/surveys/post", json=post_body("nope")).status_code == 404
    finally:
        app.dependency_overrides.clear()

    row = fake.sqlite.conn.execute("SELECT status, shown_1, post_explain FROM diagnoses").fetchone()
    assert tuple(row) == ("completed", 5, 4)
    kinds = {k for k, _ in fake.calls}
    assert kinds == {"first", "run"}


def test_d1_converts_js_like_results():
    """Workers で JS のオブジェクトのまま返ってきた場合（to_py を持つ）にも dict に直せる。"""

    class JsLike:
        def __init__(self, v):
            self.v = v

        def to_py(self):
            return self.v

    class Stmt:
        def bind(self, *_):
            return self

        async def first(self):
            return JsLike({"diagnosis_id": "a"})

        async def run(self):
            return JsLike({"meta": {"changes": 1}})

    d1 = D1Database(SimpleNamespace(prepare=lambda _sql: Stmt()))
    assert asyncio.run(d1.fetch_one("SELECT 1")) == {"diagnosis_id": "a"}
    assert asyncio.run(d1.execute("UPDATE x")) == 1
