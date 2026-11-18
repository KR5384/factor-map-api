"""採点ロジック（API仕様書 API-02 の処理 4〜6）。AI は使わない。

【要確認：診断チーム】重み WEIGHTS は仮。診断チームの重みの表（20問×10分類）が届いたら差し替え、
SCORING_VERSION を上げる。いまは「分類c に Q(2c-1) と Q(2c) が重み1.0で効く」としている。
"""

import math
from dataclasses import dataclass, field
from itertools import combinations

SCORING_VERSION = "provisional-2026-11-18"
CATEGORY_IDS = list(range(1, 11))
QUESTION_KEYS = [f"q{i:02d}" for i in range(1, 21)]

# 設問 → {分類ID: 重み}
WEIGHTS: dict[str, dict[int, float]] = {
    f"q{q:02d}": {(q + 1) // 2: 1.0} for q in range(1, 21)
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
