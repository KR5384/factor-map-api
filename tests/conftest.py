import pytest
from fastapi.testclient import TestClient

from app.db import SQLiteDatabase, get_db
from app.main import app


@pytest.fixture(autouse=True)
def settings_env(monkeypatch):
    """テストの既定：本番モード（FORCE_TEST_MODE=false）、B群なし。テストごとに上書きできる。"""
    monkeypatch.setenv("FORCE_TEST_MODE", "false")
    monkeypatch.delenv("ENABLE_GROUP_B", raising=False)


@pytest.fixture
def db():
    """テストごとに空の SQLite（メモリ上）を用意し、db/schema.sql でテーブルを作る。"""
    d = SQLiteDatabase(":memory:")
    d.init_schema()
    return d


@pytest.fixture
def client(db):
    app.dependency_overrides[get_db] = lambda: db
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.clear()


def pre_body(**over):
    body = {
        "consent": True,
        "consent_version": "2026-11-v1",
        "client_version": "web-0.3.0",
        "pre_frequency": 2,
        "pre_explain": 2,
        "pre_relation": 1,
        "pre_causes": [3, 9],
        "age_group": "30s",
    }
    body.update(over)
    return body


def answers(default=3, **over):
    a = {f"q{i:02d}": default for i in range(1, 21)}
    a.update(over)
    return a


def post_body(diagnosis_id, **over):
    body = {
        "diagnosis_id": diagnosis_id,
        "post_explain": 4,
        "post_relation": 4,
        "post_fit": 5,
        "post_discovery": 3,
        "post_comment": "情報の多さと考えすぎが関係していると分かった",
    }
    body.update(over)
    return body
