"""採点ロジック（API仕様書 API-02 の処理 4〜6）。AI は使わない。

重みは factor-map-web の public/questions.json（version 2、2026-11-17）と同じ。
重みを直すときは questions.json と両方を直し、SCORING_VERSION を上げる。
"""

import math
from dataclasses import dataclass
from itertools import combinations

SCORING_VERSION = "2026-11-20-v2"  # 日付＝表示ルールを変えた日、v2＝questions.json の version
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

# 表示ルール（2026-11-20 決定）
# - タイプ：1位の85%以上かつ50点以上の分類、最大3つ。1位が50点未満（もやもやが少ない人）は1位だけ
# - 円：点数の高い順に最大5つ。20点未満は出さない。ただしタイプの分類は必ず出す
# - 線：タイプの分類同士を結ぶ
TYPE_RATIO_PERCENT = 85  # 1位の何%以上をタイプに入れるか（小数の誤差を避けるため整数で比べる）
TYPE_MIN_SCORE = 50      # タイプに入れる最低点。1位がこれ未満なら low_moyamoya
TYPE_MAX = 3             # タイプにする分類の最大数（175types.csv は3つまで）
CIRCLE_MAX = 5           # 円の最大数
CIRCLE_MIN_SCORE = 20    # 円に出す最低点（タイプの分類は例外）【仮】
DB_SHOWN_COLUMNS = 4     # DB の shown_1〜shown_4 にタイプの分類を入れる（shown_4 は今は使わない）


def round_half_up(x: float) -> int:
    return math.floor(x + 0.5)


def rank(scores: dict[int, int]) -> list[tuple[int, int]]:
    """点数の高い順（同点は分類IDの小さい順）。"""
    return sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))


@dataclass
class Result:
    scores: dict[int, int]
    type_categories: list[tuple[int, int]]  # タイプの分類 (分類ID, 点数) を順位順に
    scoring_version: str = SCORING_VERSION

    @property
    def low_moyamoya(self) -> bool:
        return rank(self.scores)[0][1] < TYPE_MIN_SCORE

    @property
    def main_category_id(self) -> int | None:
        return self.type_categories[0][0] if self.type_categories else None

    @property
    def result_type_id(self) -> str | None:
        """タイプの分類IDを小さい順に2桁でつないだもの（例 "05"、"04-05"、"03-05-09"）。
        20_タイプ決め/moyamoya_175types.csv の「タイプID」と同じ。順位は区別しない。"""
        if not self.type_categories:
            return None
        return "-".join(f"{c:02d}" for c in sorted(c for c, _ in self.type_categories))

    @property
    def circles(self) -> list[tuple[int, int]]:
        type_ids = {c for c, _ in self.type_categories}
        return [(c, s) for c, s in rank(self.scores) if s >= CIRCLE_MIN_SCORE or c in type_ids][:CIRCLE_MAX]

    @property
    def links(self) -> list[dict]:
        return [{"from": a, "to": b} for (a, _), (b, _) in combinations(self.type_categories, 2)]

    def to_columns(self) -> dict:
        cols = {"scoring_version": self.scoring_version}
        cols |= {f"score_{c:02d}": self.scores[c] for c in CATEGORY_IDS}
        cols["shown_count"] = len(self.type_categories)
        for i in range(DB_SHOWN_COLUMNS):
            cols[f"shown_{i + 1}"] = self.type_categories[i][0] if i < len(self.type_categories) else None
        cols |= {
            "main_category_id": self.main_category_id,
            "result_type_id": self.result_type_id,
            "low_moyamoya": int(self.low_moyamoya),
        }
        return cols

    def to_response(self, diagnosis_id: str) -> dict:
        def ranked(items):
            return [{"rank": i + 1, "category_id": c, "score": s} for i, (c, s) in enumerate(items)]

        return {
            "diagnosis_id": diagnosis_id,
            "scoring_version": self.scoring_version,
            "scores": [{"category_id": c, "score": self.scores[c]} for c in CATEGORY_IDS],
            "circles": ranked(self.circles),
            "type_categories": ranked(self.type_categories),
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


def pick_type(scores: dict[int, int]) -> list[tuple[int, int]]:
    ranked = rank(scores)
    top = ranked[0][1]
    if top == 0:
        return []  # 全部0点（全問「まったくない」）はタイプを出さない
    if top < TYPE_MIN_SCORE:
        return ranked[:1]  # もやもやが少ない人も、いちばん近いタイプを1つ出す
    return [(c, s) for c, s in ranked if s * 100 >= top * TYPE_RATIO_PERCENT and s >= TYPE_MIN_SCORE][:TYPE_MAX]


def score(answers: dict[str, int], weights=WEIGHTS) -> Result:
    scores = calc_scores(answers, weights)
    return Result(scores=scores, type_categories=pick_type(scores))


def result_from_row(row: dict) -> Result:
    """DB に保存済みの結果からレスポンスを作り直す（再送信されたとき用）。円と線は点数とタイプから決まる。"""
    type_ids = [row[f"shown_{i}"] for i in range(1, DB_SHOWN_COLUMNS + 1) if row[f"shown_{i}"] is not None]
    scores = {c: row[f"score_{c:02d}"] for c in CATEGORY_IDS}
    return Result(
        scores=scores,
        type_categories=[(c, scores[c]) for c in type_ids],
        scoring_version=row["scoring_version"],
    )
