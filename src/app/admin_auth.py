"""管理者認証 (F-19 / Requirements 21)。

factor-map-web/worker/index.ts の認証ロジックを FastAPI へ移植したもの。
  - Authorization: Bearer <ADMIN_TOKEN>
  - Authorization: Basic base64(user:password)
  - Cookie: admin_token=<ADMIN_TOKEN>
のいずれかで認証する。連続5回失敗で 60 秒ロックする (21.4)。

NOTE: 失敗カウントはプロセス内メモリで保持する。Workers の isolate 単位と
      同様、インスタンス再生成や分散で失われる/分裂する可能性がある。
      厳密な分散レート制限が必要なら KV/Durable Objects 相当へ移行する。
"""

from __future__ import annotations

import base64
import os
import re
import time

from fastapi import Request

ADMIN_MAX_FAILURES = 5  # 連続失敗の上限 (21.4)
ADMIN_LOCK_SECONDS = 60  # ロック時間 (21.4)


class _FailureState:
    __slots__ = ("count", "locked_until")

    def __init__(self) -> None:
        self.count = 0
        self.locked_until = 0.0  # epoch 秒。0 はロックなし


_admin_failures: dict[str, _FailureState] = {}


def _env_value(request: Request, key: str) -> str | None:
    """env (Workers) → os.environ (ローカル) の順で変数を取得する。"""
    env = request.scope.get("env")
    if env is not None:
        val = getattr(env, key, None)
        if isinstance(val, str) and len(val) > 0:
            return val
    val = os.environ.get(key)
    return val if val else None


def requester_key(request: Request) -> str:
    """要求元を識別するキー (CF-Connecting-IP を優先)。"""
    headers = request.headers
    return (
        headers.get("CF-Connecting-IP")
        or headers.get("X-Forwarded-For")
        or (request.client.host if request.client else None)
        or "unknown"
    )


def is_locked(key: str, now: float) -> bool:
    """現在ロック中か (期限切れなら状態をリセット)。"""
    state = _admin_failures.get(key)
    if state is None:
        return False
    if state.locked_until > now:
        return True
    if state.locked_until != 0.0:
        _admin_failures.pop(key, None)
    return False


def record_failure(key: str, now: float) -> None:
    """認証失敗を記録し、上限到達でロックする (21.4)。"""
    state = _admin_failures.get(key)
    if state is None:
        state = _FailureState()
        _admin_failures[key] = state
    state.count += 1
    if state.count >= ADMIN_MAX_FAILURES:
        state.locked_until = now + ADMIN_LOCK_SECONDS


def clear_failures(key: str) -> None:
    """認証成功で失敗カウントをクリアする。"""
    _admin_failures.pop(key, None)


def extract_credentials(request: Request) -> dict[str, str | None]:
    """Authorization ヘッダ / Cookie から資格情報を抽出する。"""
    auth = request.headers.get("Authorization") or ""

    if auth.startswith("Bearer "):
        return {"token": auth[len("Bearer ") :].strip(), "username": None, "password": None}

    if auth.startswith("Basic "):
        try:
            decoded = base64.b64decode(auth[len("Basic ") :].strip()).decode("utf-8")
            idx = decoded.find(":")
            if idx >= 0:
                return {
                    "username": decoded[:idx],
                    "password": decoded[idx + 1 :],
                    "token": None,
                }
        except Exception:
            # 不正な base64 は未認証扱い
            pass
        return {"username": None, "password": None, "token": None}

    cookie = request.headers.get("Cookie") or ""
    match = re.search(r"(?:^|;\s*)admin_token=([^;]+)", cookie)
    if match:
        return {"token": match.group(1), "username": None, "password": None}

    return {"username": None, "password": None, "token": None}


def credentials_match(request: Request, creds: dict[str, str | None]) -> bool:
    """資格情報が設定済みの正しい値と一致するか。"""
    admin_token = _env_value(request, "ADMIN_TOKEN")
    admin_user = _env_value(request, "ADMIN_USER")
    admin_password = _env_value(request, "ADMIN_PASSWORD")

    token = creds.get("token")
    if admin_token and token and token == admin_token:
        return True

    username = creds.get("username")
    password = creds.get("password")
    if (
        admin_user
        and admin_password
        and username
        and password
        and username == admin_user
        and password == admin_password
    ):
        return True

    return False


def is_authenticated(request: Request) -> bool:
    """Authorization/Cookie の資格情報で認証されているか。"""
    return credentials_match(request, extract_credentials(request))


def issue_access_token(request: Request) -> str:
    """後続要求用のアクセストークンを発行する。

    ADMIN_TOKEN があればそれを、無ければ ADMIN_PASSWORD を返す
    (Worker 実装と同じ方針)。
    """
    admin_token = _env_value(request, "ADMIN_TOKEN")
    if admin_token:
        return admin_token
    return _env_value(request, "ADMIN_PASSWORD") or ""


def now_seconds() -> float:
    return time.time()
