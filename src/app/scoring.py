"""採点ロジック（API仕様書 API-02 の処理 4〜6）。AI は使わない。

重みは factor-map-web の public/questions.json（version 2、2026-11-17）と同じ。
重みを直すときは questions.json と両方を直し、SCORING_VERSION を上げる。
"""

import math
from dataclasses import dataclass, field
from itertools import combinations

SCORING_VERSION = "2026-11-17-v2"
CATEGORY_IDS = list(range(1, 11))
QUESTION_KEYS = [f"q{i:02d}" for i in range(1, 21)]

# questions.json の要因ID → 分類ID（DB項目一覧.xlsx の「分類ID」シートと同じ順）
FACTOR_IDS = {
    "time_margin": 1,          # 時間・余白不足
    "recovery": 2,             # 回復不足
    "info_overload": 3,        # 情報過多・認知負荷
    "comparison": 4,           # 他者比較・自己評価の揺らぎ
    "loneliness": 5,           # 孤独・つながり不足
    "future_uncertainty": 6,   # 将来の不確実性・不安
    "control": 7,              # コントロール感の低下
    "ideal_gap": 8,            # 理想と現実のギャップ
    "rumination": 9,           # 反すう・考え続ける状態
    "indecision": 10,          # 決められない・行動できない
}

# questions.json の weights をそのまま写したもの
_WEIGHTS_BY_FACTOR: dict[str, dict[str, float]] = {
    "q01": {"time_margin": 0.8, "recovery": 0.2},
    "q02": {"recovery": 0.8, "time_margin": 0.2},
    "q03": {"info_overload": 0.8, "rumination": 0.2},
    "q04": {"comparison": 0.8, "loneliness": 0.2},
    "q05": {"loneliness": 0.8, "comparison": 0.2},
    "q06": {"future_uncertainty": 0.8, "ideal_gap": 0.2},
    "q07": {"control": 0.8, "time_margin": 0.2},
    "q08": {"ideal_gap": 0.8, "control": 0.2},
    "q09": {"rumination": 0.8, "info_overload": 0.2},
    "q10": {"indecision": 0.8, "future_uncertainty": 0.2},
    "q11": {"info_overload": 0.4, "indecision": 0.3, "time_margin": 0.2, "recovery": 0.1},
    "q12": {"rumination": 0.4, "future_uncertainty": 0.3, "loneliness": 0.2, "ideal_gap": 0.1},
    "q13": {"time_margin": 0.4, "control": 0.3, "info_overload": 0.2, "indecision": 0.1},
    "q14": {"loneliness": 0.4, "comparison": 0.3, "ideal_gap": 0.2, "rumination": 0.1},
    "q15": {"comparison": 0.4, "ideal_gap": 0.3, "control": 0.2, "loneliness": 0.1},
    "q16": {"future_uncertainty": 0.4, "control": 0.3, "indecision": 0.2, "comparison": 0.1},
    "q17": {"control": 0.4, "loneliness": 0.3, "comparison": 0.2, "time_margin": 0.1},
    "q18": {"ideal_gap": 0.4, "indecision": 0.3, "future_uncertainty": 0.2, "info_overload": 0.1},
    "q19": {"recovery": 0.4, "time_margin": 0.3, "rumination": 0.2, "control": 0.1},
    "q20": {"indecision": 0.4, "future_uncertainty": 0.3, "rumination": 0.2, "ideal_gap": 0.1},
}

# 設問 → {分類ID: 重み}
WEIGHTS: dict[str, dict[int, float]] = {
    q: {FACTOR_IDS[f]: w for f, w in ws.items()} for q, ws in _WEIGHTS_BY_FACTOR.items()
}

# 表示ルール【要確認：診断チーム】
SHOW_RATIO = 0.8      # 1位の何%以上を表示するか
SHOW_MIN_SCORE = 50   # 表示する最低点
SHOW_MAX = 4          # 最大何分類表示するか
LINK_MIN_STRENGTH = 0.3


def round_half_up(x: float) -> int:
    return math.floor(x + 0.5)


@dataclass
class Result:
    scores: dict[int, int]
    shown: list[tuple[int, int]]  # (分類ID, 点数) を順位順に
    links: list[dict] = field(default_factory=list)
    scoring_version: str = SCORING_VERSION

    @property
    def low_moyamoya(self) -> bool:
        return not self.shown

    @property
    def main_category_id(self) -> int | None:
        return self.shown[0][0] if self.shown else None

    @property
    def result_type_id(self) -> str | None:
        # 当面は「T + 1位の分類ID2桁」。複合タイプが決まったら判定ルールを足す
        return f"T{self.main_category_id:02d}" if self.shown else None

    def to_columns(self) -> dict:
        cols = {"scoring_version": self.scoring_version}
        cols |= {f"score_{c:02d}": self.scores[c] for c in CATEGORY_IDS}
        cols["shown_count"] = len(self.shown)
        for i in range(SHOW_MAX):
            cols[f"shown_{i + 1}"] = self.shown[i][0] if i < len(self.shown) else None
        cols |= {
            "main_category_id": self.main_category_id,
            "result_type_id": self.result_type_id,
            "low_moyamoya": int(self.low_moyamoya),
        }
        return cols

    def to_response(self, diagnosis_id: str) -> dict:
        return {
            "diagnosis_id": diagnosis_id,
            "scoring_version": self.scoring_version,
            "scores": [{"category_id": c, "score": self.scores[c]} for c in CATEGORY_IDS],
            "shown": [{"rank": i + 1, "category_id": c, "score": s} for i, (c, s) in enumerate(self.shown)],
            "main_category_id": self.main_category_id,
            "result_type_id": self.result_type_id,
            "low_moyamoya": self.low_moyamoya,
            "links": self.links,
        }


def calc_scores(answers: dict[str, int], weights=WEIGHTS) -> dict[int, int]:
    """分類c の点数 = Σ((回答−1)×重み) ÷ Σ(4×重み) × 100（四捨五入）"""
    got = {c: 0.0 for c in CATEGORY_IDS}
    full = {c: 0.0 for c in CATEGORY_IDS}
    for q, cat_weights in weights.items():
        for c, w in cat_weights.items():
            got[c] += (answers[q] - 1) * w
            full[c] += 4 * w
    return {c: round_half_up(got[c] / full[c] * 100) if full[c] else 0 for c in CATEGORY_IDS}


def pick_shown(scores: dict[int, int]) -> list[tuple[int, int]]:
    ranked = sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))
    top = ranked[0][1]
    if top < SHOW_MIN_SCORE:
        return []
    return [(c, s) for c, s in ranked if s >= top * SHOW_RATIO and s >= SHOW_MIN_SCORE][:SHOW_MAX]


def calc_links(shown_ids: list[int], weights=WEIGHTS) -> list[dict]:
    """表示した分類同士のつながり＝同じ設問の中での重みの積の合計（設計上の想定）。"""
    links = []
    for a, b in combinations(shown_ids, 2):
        strength = round(sum(w.get(a, 0) * w.get(b, 0) for w in weights.values()), 2)
        if strength >= LINK_MIN_STRENGTH:
            links.append({"from": a, "to": b, "strength": strength})
    return links


def score(answers: dict[str, int], weights=WEIGHTS) -> Result:
    scores = calc_scores(answers, weights)
    shown = pick_shown(scores)
    return Result(scores=scores, shown=shown, links=calc_links([c for c, _ in shown], weights))


def result_from_row(row: dict, weights=WEIGHTS) -> Result:
    """DB に保存済みの結果からレスポンスを作り直す（再送信されたとき用）。"""
    shown_ids = [row[f"shown_{i}"] for i in range(1, SHOW_MAX + 1) if row[f"shown_{i}"] is not None]
    scores = {c: row[f"score_{c:02d}"] for c in CATEGORY_IDS}
    return Result(
        scores=scores,
        shown=[(c, scores[c]) for c in shown_ids],
        links=calc_links(shown_ids, weights),
        scoring_version=row["scoring_version"],
    )
