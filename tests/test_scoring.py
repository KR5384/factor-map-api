"""採点ロジックのテスト（仮の重み：分類c = Q(2c-1)＋Q(2c)）。"""

from app.scoring import calc_links, calc_scores, pick_shown, score


def answers(default=3, **over):
    a = {f"q{i:02d}": default for i in range(1, 21)}
    a.update(over)
    return a


def test_all_lowest_is_low_moyamoya():
    r = score(answers(default=1))
    assert set(r.scores.values()) == {0}
    assert r.low_moyamoya and r.shown == [] and r.main_category_id is None and r.result_type_id is None


def test_all_highest_shows_four_by_id_order():
    r = score(answers(default=5))
    assert set(r.scores.values()) == {100}
    assert r.shown == [(1, 100), (2, 100), (3, 100), (4, 100)]  # 同点は分類IDの小さい順、最大4つ
    assert r.main_category_id == 1 and r.result_type_id == "T01"


def test_round_half_up():
    # (回答−1) の合計 1 ÷ 8 × 100 = 12.5 → 13（偶数丸めではなく四捨五入）
    assert calc_scores(answers(default=1, q01=2))[1] == 13
    assert calc_scores(answers(default=1, q01=4))[1] == 38  # 37.5 → 38


def test_show_ratio_80_percent():
    scores = {c: 0 for c in range(1, 11)} | {1: 100, 2: 80, 3: 79}
    assert pick_shown(scores) == [(1, 100), (2, 80)]


def test_show_min_50():
    scores = {c: 0 for c in range(1, 11)} | {1: 60, 2: 49}
    assert pick_shown(scores) == [(1, 60)]  # 49 は 1位の80%以上だが50点未満
    assert pick_shown({c: 49 for c in range(1, 11)}) == []
    assert pick_shown({c: 0 for c in range(1, 11)} | {5: 50}) == [(5, 50)]


def test_links_from_weights():
    weights = {f"q{i:02d}": {1: 1.0} for i in range(1, 21)}
    weights["q01"] = {1: 0.8, 2: 0.2}
    weights["q02"] = {2: 0.8, 1: 0.2}
    assert calc_links([1, 2], weights) == [{"from": 1, "to": 2, "strength": 0.32}]
    assert calc_links([1, 3], weights) == []


def test_provisional_weights_have_no_links():
    assert score(answers(default=5)).links == []
