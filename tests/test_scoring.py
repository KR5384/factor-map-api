"""採点ロジックのテスト（重みは questions.json version 2 と同じもの）。"""

from types import SimpleNamespace

from app.scoring import Result, calc_links, calc_scores, pick_shown, score
from app.settings import get_setting, is_enabled


def answers(default=3, **over):
    a = {f"q{i:02d}": default for i in range(1, 21)}
    a.update(over)
    return a


def test_all_lowest_is_low_moyamoya():
    r = score(answers(default=1))
    assert set(r.scores.values()) == {0}
    assert r.low_moyamoya and r.shown == [] and r.main_category_id is None and r.result_type_id is None


def test_all_highest_shows_three_by_id_order():
    r = score(answers(default=5))
    assert set(r.scores.values()) == {100}
    assert [c for c, _ in r.shown] == [1, 2, 3]  # 同点は分類IDの小さい順、最大3つ
    assert r.main_category_id == 1 and r.result_type_id == "01-02-03"
    assert r.to_columns()["shown_4"] is None


def test_result_type_id_is_sorted_category_ids():
    # 順位ではなく分類IDの小さい順につなぐ（175types.csv のタイプIDと同じ）
    one = {c: 0 for c in range(1, 11)} | {5: 80}
    assert Result(scores=one, shown=[(5, 80)]).result_type_id == "05"
    assert Result(scores=one, shown=[(9, 90), (3, 80)]).result_type_id == "03-09"
    assert Result(scores=one, shown=[(10, 90), (4, 85), (7, 80)]).result_type_id == "04-07-10"


def test_scores_by_hand():
    # Q1だけ5、ほかは1。
    # 時間・余白不足：Q1(0.8)×4 ÷ (4×(Q1 0.8+Q2 0.2+Q7 0.2+Q11 0.2+Q13 0.4+Q17 0.1+Q19 0.3)=8.8) = 36.4 → 36
    # 回復不足：Q1(0.2)×4 ÷ (4×(Q1 0.2+Q2 0.8+Q11 0.1+Q19 0.4)=6.0) = 13.3 → 13
    s = calc_scores(answers(default=1, q01=5))
    assert (s[1], s[2]) == (36, 13)
    assert all(s[c] == 0 for c in range(3, 11))


def test_round_half_up():
    # (回答−1) の合計 1 ÷ 8 × 100 = 12.5 → 13（偶数丸めではなく四捨五入）
    simple = {f"q{i:02d}": {(i + 1) // 2: 1.0} for i in range(1, 21)}
    assert calc_scores(answers(default=1, q01=2), simple)[1] == 13
    assert calc_scores(answers(default=1, q01=4), simple)[1] == 38  # 37.5 → 38


def test_show_ratio_85_percent():
    scores = {c: 0 for c in range(1, 11)} | {1: 100, 2: 85, 3: 84}
    assert pick_shown(scores) == [(1, 100), (2, 85)]
    # 60 の85%＝51 ちょうどは表示する（小数の誤差で外れない）
    assert pick_shown({c: 0 for c in range(1, 11)} | {1: 60, 2: 51, 3: 50}) == [(1, 60), (2, 51)]


def test_show_max_3():
    scores = {c: 0 for c in range(1, 11)} | {1: 90, 2: 89, 3: 88, 4: 87}
    assert [c for c, _ in pick_shown(scores)] == [1, 2, 3]


def test_show_min_50():
    scores = {c: 0 for c in range(1, 11)} | {1: 60, 2: 49}
    assert pick_shown(scores) == [(1, 60)]  # 49 は 1位の85%（51）未満で、しかも50点未満
    assert pick_shown({c: 49 for c in range(1, 11)}) == []
    assert pick_shown({c: 0 for c in range(1, 11)} | {5: 50}) == [(5, 50)]


def test_links_match_result_screen_comparison():
    # 結果画面の見せ方_ABC比較.html の「つながりの強さ」と同じ値になる
    assert calc_links([5, 4]) == [{"from": 5, "to": 4, "strength": 0.54}]   # 孤独×他者比較
    assert calc_links([1, 2]) == [{"from": 1, "to": 2, "strength": 0.46}]   # 時間・余白×回復
    assert calc_links([6, 10]) == [{"from": 6, "to": 10, "strength": 0.42}]  # 将来不安×決められない
    assert calc_links([3, 9]) == [{"from": 3, "to": 9, "strength": 0.32}]   # 情報過多×反すう
    assert calc_links([5, 6]) == []                                           # 0.06 は 0.3 未満


def test_settings_prefer_workers_env(monkeypatch):
    monkeypatch.setenv("FORCE_TEST_MODE", "true")
    workers = SimpleNamespace(scope={"env": SimpleNamespace(FORCE_TEST_MODE="false")})
    assert get_setting(workers, "FORCE_TEST_MODE") == "false"
    assert is_enabled(workers, "FORCE_TEST_MODE") is False
    # Workers の env に無い設定は OS の環境変数 → 既定値の順
    assert is_enabled(workers, "ENABLE_GROUP_B") is False
    local = SimpleNamespace(scope={})
    assert is_enabled(local, "FORCE_TEST_MODE") is True
