"""設定値（環境変数）の読み込み。

- Workers 上：wrangler の vars／ダッシュボードの「変数」（request.scope["env"]）
- ローカル（fastapi dev・pytest）：OS の環境変数
の順に探し、どちらにも無ければ既定値を使う。
"""

import os

from fastapi import Request

# 既定値。FORCE_TEST_MODE は「付け忘れても本番データに混ざらない」ように true にしておく
DEFAULTS = {
    "FORCE_TEST_MODE": "true",   # true の間は全件 is_test=1。検証開始時に false にする
    "ENABLE_GROUP_B": "false",   # true で A／B をランダムに振る
}


def get_setting(request: Request, name: str) -> str:
    env = request.scope.get("env")
    if env is not None:
        value = getattr(env, name, None)
        if value is not None:
            return str(value)
    return os.environ.get(name, DEFAULTS[name])


def is_enabled(request: Request, name: str) -> bool:
    return get_setting(request, name).strip().lower() in ("1", "true", "yes", "on")
