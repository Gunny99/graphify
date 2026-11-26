"""모집단 차례: 명반 수, 비율 범위, 표본 예외 없음. 전수 셈은 population.py 스크립트로만 돌린다."""
from engine_v2 import population as P


def test_chart_count():
    assert sum(1 for _ in P.iter_charts()) == 60 * 12 * 30 * 12 == 259200


def test_sample_runs_and_ratios():
    rules, tally = P.load_dictionary()
    assert tally['확정'] == len(rules) > 0
    ctx = P.Ctx(rules)
    pop = P.population(ctx, every=500)
    assert pop['n'] > 400
    res, _ = ctx.count('己', '卯', 6, 23, 5)
    assert set(res) == set(P.THREADS)
    for t in P.THREADS:
        assert sum(pop['dist'][t].values()) == pop['n']
        ge, gt = P.ranks(pop['dist'][t], res[t][:2])
        assert 0 <= gt <= ge <= 1
