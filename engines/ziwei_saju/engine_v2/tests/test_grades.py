"""권2 등급 조건 검사: 여덟 생년월일과 대상 명반에서 예외 없이 돌고 met <= total."""
import json

import pytest

from engine_v2 import compute
from engine_v2.grades import evaluate, load_grades, unparsed
from engine_v2.tests.test_generality import CASES

TARGET = ('1999-08-04', '10:14', True, -38)
ALL = list(CASES) + [TARGET]


@pytest.mark.parametrize('case', ALL, ids=[c[0] for c in ALL])
def test_evaluate_runs(case):
    out = evaluate(compute(*case))
    assert out
    for it in out:
        assert it['verdict'] in ('선다', '반만', '서지 않는다')
        assert 0 <= it['met'] <= it['total']
        assert len(it['unknown']) <= it['total']
        assert (it['verdict'] == '선다') == (it['met'] == it['total'])
        assert (it['verdict'] == '서지 않는다') == (it['met'] == 0)


def test_table_shape():
    g = load_grades()
    ids = [e['id'] for e in g]
    assert len(ids) == len(set(ids))
    for e in g:
        assert e['parse'] in ('auto', 'manual', 'unparsed') and e['polarity'] in ('길', '흉', '중')
        assert e['text'] and (e['conds'] or e['parse'] == 'unparsed')
    assert len(evaluate(compute(*TARGET))) + len(unparsed()) == len(g)


def test_any_of_marked():
    for e in load_grades():
        for c in e['conds']:
            if c.get('any_of'):
                assert c.get('any_of_reason')


def test_print_target(capsys):
    out = evaluate(compute(*TARGET))
    with capsys.disabled():
        for v in ('선다', '반만'):
            print('\n[%s]' % v)
            for it in out:
                if it['verdict'] == v:
                    print(' ', it['id'], it['title'], '%d/%d' % (it['met'], it['total']), 'unknown=%d' % len(it['unknown']), '있음', it['present'])
