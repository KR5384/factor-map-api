"""採点ロジックのテスト（重みは questions.json version 2 と同じもの）。"""

from types import SimpleNamespace

from app.scoring import Result, calc_scores, pick_type, score
from app.settings import get_setting, is_enabled


def answers(default=3, **over):
    a = {f"q{i:02d}": default for i in range(1, 21)}
    a.update(over)
    return a


def zeros(**over):
    return {c: 0 for c in range(1, 11)} | {int(k[1:]): v for k, v in over.items()}


def test_all_lowest_has_no_type():
    r = score(answers(default=1))
    assert set(r.scores.values()) == {0}
    assert r.low_moyamoya and r.type_categories == [] and r.main_category_id is None and r.result_type_id is None
    assert r.circles == [] and r.links == []


def test_all_highest_type_is_three_by_id_order():
    r = score(answers(default=5))
    assert set(r.scores.values()) == {100}
    assert [c for c, _ in r.type_categories] == [1, 2, 3]  # 同点は分類IDの小さい順、最大3つ
    assert r.main_category_id == 1 and r.result_type_id == "01-02-03"
    assert [c for c, _ in r.circles] == [1, 2, 3, 4, 5]    # 円は最大5つ
    assert r.links == [{"from": 1, "to": 2}, {"from": 1, "to": 3}, {"from": 2, "to": 3}]
    assert r.to_columns()["shown_4"] is None


def test_result_type_id_is_sorted_category_ids():
    # 順位ではなく分類IDの小さい順につなぐ（175types.csv のタイプIDと同じ）
    assert Result(scores=zeros(c5=80), type_categories=[(5, 80)]).result_type_id == "05"
    assert Result(scores=zeros(c9=90, c3=80), type_categories=[(9, 90), (3, 80)]).result_type_id == "03-09"
    r = Result(scores=zeros(c10=90, c4=85, c7=80), type_categories=[(10, 90), (4, 85), (7, 80)])
    assert r.result_type_id == "04-07-10"


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


def test_type_ratio_85_percent():
    assert pick_type(zeros(c1=100, c2=85, c3=84)) == [(1, 100), (2, 85)]
    # 60 の85%＝51 ちょうどは入れる（小数の誤差で外れない）
    assert pick_type(zeros(c1=60, c2=51, c3=50)) == [(1, 60), (2, 51)]


def test_type_max_3():
    assert [c for c, _ in pick_type(zeros(c1=90, c2=89, c3=88, c4=87))] == [1, 2, 3]


def test_type_min_50():
    assert pick_type(zeros(c1=55, c2=49)) == [(1, 55)]  # 49 は 55 の85%以上だが50点未満
    assert pick_type(zeros(c5=50)) == [(5, 50)]


def test_low_moyamoya_still_gets_top_type():
    # 1位が50点未満なら low_moyamoya。それでも1位のタイプを1つ出す（線は無し）
    r = Result(scores=zeros(c4=22, c2=17, c3=16), type_categories=pick_type(zeros(c4=22, c2=17, c3=16)))
    assert r.low_moyamoya is True
    assert r.type_categories == [(4, 22)] and r.result_type_id == "04" and r.main_category_id == 4
    assert r.links == []
    assert r.circles == [(4, 22)]  # 20点未満は円に出さない


def test_circles_min_20_but_type_always_shown():
    r = Result(scores=zeros(c1=80, c2=70, c3=30, c4=20, c5=19), type_categories=[(1, 80)])
    assert [c for c, _ in r.circles] == [1, 2, 3, 4]  # 19点は出さない
    r = Result(scores=zeros(c1=15), type_categories=[(1, 15)])
    assert r.circles == [(1, 15)]  # タイプの分類は20点未満でも出す


def test_circles_max_5():
    r = Result(scores={c: 100 - c for c in range(1, 11)}, type_categories=[(1, 99)])
    assert [c for c, _ in r.circles] == [1, 2, 3, 4, 5]


def test_settings_prefer_workers_env(monkeypatch):
    monkeypatch.setenv("FORCE_TEST_MODE", "true")
    workers = SimpleNamespace(scope={"env": SimpleNamespace(FORCE_TEST_MODE="false")})
    assert get_setting(workers, "FORCE_TEST_MODE") == "false"
    assert is_enabled(workers, "FORCE_TEST_MODE") is False
    # Workers の env に無い設定は OS の環境変数 → 既定値の順
    assert is_enabled(workers, "ENABLE_GROUP_B") is False
    local = SimpleNamespace(scope={})
    assert is_enabled(local, "FORCE_TEST_MODE") is True
