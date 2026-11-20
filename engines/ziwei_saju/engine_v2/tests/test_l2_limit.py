"""권3 限(운) 구절 판정 시험(명세 11-2). 합성 입력으로 大限 구절의 선다·서지 않음, 小限 구절의 검사 제외, 減半 노트를 보고,
재현 명반 세 건에서 대한 열두 구간이 오류 없이 도는지 본다."""
import json

import pytest

from engine_v2 import compute, l2
from engine_v2.common import sanfang
from engine_v2.tests.test_generality import CASES

S, H, N = '선다', '반만', '서지 않는다'
REPRO = CASES[-3:]          # 재현 A(子時 경계), B(윤4월 芒種 뒤), C(立春 뒤)


@pytest.fixture(scope='module')
def R():
    return compute('1999-08-04', '10:14', True, -38)


def _main_star(R, z):
    return next(s['name'] for s in R['chart']['palaces'][z]['stars'] if s['kind'] == '주성')


def _limit_p(pid, star, conds, frame='大限', pol='길', kind='二限', line=1):
    """합성 限 구절. 항목 하나가 가지 하나인 꼴(apply_limit_j3.py의 출력과 같은 필드)."""
    lim = {'type': '한통칭', 'kind': kind, 'frame': frame}
    if frame == '大限':
        lim['branches'] = [{'id': pid, 'clause': '합성 ' + pid, 'conds': conds, 'polarity': pol, 'star': star}]
    else:
        lim['reason'] = '小限을 조건으로 든 구절(합성)'
    return {'file': 'x', 'line': line, 'palace': '명', 'text': '합성 ' + pid, 'id': pid, 'scope': '限', 'cond_palace': None, 'star': star,
            'conds': [], 'result': '', 'polarity': '미정', 'parse': 'unparsed', 'reason': '운 구절', 'limit': lim}


def _by_id(e):
    return {it['id']: it for it in e['passages']}


def test_daehan_star_stands(R):
    """대한 명궁에 든 주성을 든 大限 구절은 선다. 같은 별이 다른 대한 명궁에 없으면 그 대한에서는 목록에 없다."""
    z = R['daehan'][2]['palace']
    star = _main_star(R, z)
    ps = [_limit_p('限:T1', star, [])]
    e = l2.evaluate_limit(R, 2, ps)
    it = _by_id(e)['限:T1']
    assert it['verdict'] == S and (it['met'], it['total']) == (1, 1) and it['subject_only'] is True
    assert e['palace'] == z and e['outside'] == []
    other = next(i for i, d in enumerate(R['daehan']) if star not in {s['name'] for s in R['chart']['palaces'][d['palace']]['stars']})
    assert 'T1' not in ' '.join(_by_id(l2.evaluate_limit(R, other, ps)))


def test_condition_not_met(R):
    """조건(궁지)이 이 대한 명궁이 아니면 서지 않는다. 맞으면 선다. 조건은 L2의 같은 종류(궁지, 밝기, 살 따위)로 검사한다."""
    z = R['daehan'][2]['palace']
    star = _main_star(R, z)
    wrong = next(d['palace'] for d in R['daehan'] if d['palace'] != z)
    ps = [_limit_p('限:T2', star, [{'kind': '궁지', 'values': [wrong], 'negate': False, 'word': '합성'}]),
          _limit_p('限:T3', star, [{'kind': '궁지', 'values': [z], 'negate': False, 'word': '합성'}], line=2)]
    e = _by_id(l2.evaluate_limit(R, 2, ps))
    assert e['限:T2']['verdict'] == N
    assert e['限:T3']['verdict'] == S and e['限:T3']['total'] == 1


def test_enum_counts(R):
    """열거 조건(길성 목록)은 있는 수/든 수(열거 k/n)를 낸다. 판정은 하나 이상이면 선다(5절 12번 나)."""
    z = R['daehan'][2]['palace']
    star = _main_star(R, z)
    lst = ['좌보', '우필', '문창', '문곡', '천괴', '천월', '녹존']
    conds = [{'kind': '길', 'values': lst, 'negate': False, 'scope': '삼방대궁', 'word': '합성'}]
    it = _by_id(l2.evaluate_limit(R, 2, [_limit_p('限:T4', star, conds)]))['限:T4']
    have = {s['name'] for q in sanfang(z)[1:] for s in R['chart']['palaces'][q]['stars']}
    k = len([x for x in lst if x in have])
    assert it['enum'] == [{'k': k, 'n': 7, 'present': [x for x in lst if x in have]}]
    assert it['verdict'] == (S if k else N)


def test_xiaoxian_not_checked(R):
    """小限·太歲 조건 구절(limit.frame '틀밖')은 검사하지 않고 outside에 적는다. 같은 별이 대한 명궁에 있어도 목록에 나오지 않는다."""
    z = R['daehan'][2]['palace']
    star = _main_star(R, z)
    ps = [_limit_p('限:T5', star, [], frame='틀밖', kind=None), _limit_p('限:T6', star, [])]
    e = l2.evaluate_limit(R, 2, ps)
    ids = _by_id(e)
    assert '限:T5' not in ids and '限:T6' in ids
    assert [x['id'] for x in e['outside']] == ['限:T5']
    assert all(x['id'] != '限:T5' for x in e['unparsed'])


def test_unparsed_and_order(R):
    """조건표 없는 구절은 unparsed(주체 별이 든 것만). 구절 차례는 선다, 반만, 동궁 조건만, 삼방, 흉, 길, 행 번호(11-2 4번)."""
    z = R['daehan'][2]['palace']
    star = _main_star(R, z)
    un = _limit_p('限:T7', star, [])
    un['limit'] = {'type': '한도 낱말 없음', 'kind': None, 'frame': None, 'reason': '합성 이음'}
    wide = [{'kind': '삼방대궁', 'values': [star], 'negate': False, 'scope': '동궁삼방대궁', 'word': '합성'}]
    ps = [_limit_p('限:A', star, [], pol='길', line=5), _limit_p('限:B', star, [], pol='흉', line=9),
          _limit_p('限:C', star, [], pol='길', line=2), _limit_p('限:D', None, wide, pol='흉', line=1), un]
    e = l2.evaluate_limit(R, 2, ps)
    assert [it['id'] for it in e['passages']] == ['限:B', '限:C', '限:A', '限:D']
    assert [u['id'] for u in e['unparsed']] == ['限:T7'] and e['unparsed'][0]['reason'] == '합성 이음'


def test_kinds_filter(R):
    z = R['daehan'][2]['palace']
    star = _main_star(R, z)
    ps = [_limit_p('限:K1', star, [], kind='二限'), _limit_p('限:K2', star, [], kind='大限명시')]
    e = l2.evaluate_limit(R, 2, ps, kinds=('大限명시',))
    assert list(_by_id(e)) == ['限:K2'] and e['skipped_kinds'] == 1


def test_half_note_synthetic(R):
    """減半 구절이 그 궁에서 서면 half_note를 단다. 서지 않으면 달지 않는다."""
    z = next(p for p, v in R['chart']['palaces'].items() if v['role'] == '형제')
    star = _main_star(R, z)
    base = {'file': 'x', 'line': 1, 'palace': '형제', 'id': '兄:H1', 'star': star, 'text': '五人減半', 'result': '五人減半', 'polarity': '흉',
            'parse': 'manual', 'conds': [], 'half': {'n': 5, 'note': '減半: 5에서 5/2'}}
    nope = dict(base, id='兄:H2', conds=[{'kind': '궁지', 'values': ['?'], 'negate': False, 'word': '합성'}])
    plain = dict(base, id='兄:H3')
    plain.pop('half')
    out = l2.evaluate(R, [base, nope, plain])
    it = {x['id']: x for x in out['형제']['passages']}
    assert it['兄:H1']['verdict'] == S and it['兄:H1']['half_note'] == '減半: 5에서 5/2'
    assert it['兄:H2']['verdict'] == N and 'half_note' not in it['兄:H2']
    assert 'half_note' not in it['兄:H3']


def test_half_data():
    """실제 표의 減半 구절 다섯에 half 필드가 있고 수를 곱한 값은 없다."""
    ps = {p['id']: p for p in l2.load_passages()}
    for i, note in (('兄:8', '減半: 5에서 5/2'), ('兄:23', '減半: 5에서 5/2'), ('子:69#3', '減半: 3에서 3/2')):
        assert ps[i]['half']['note'] == note
    for i in ('子:31', '子:42#2'):
        assert ps[i]['half']['n'] is None and ps[i]['half']['note'].startswith('減半: n에서 n/2')
    assert sum(1 for p in ps.values() if 'half' in p) == 5


def test_limit_table_integrity():
    """限 179구절 전부에 limit 필드가 있고 scope·parse·reason은 그대로. 小限·太歲는 가지가 없다."""
    ps = [p for p in l2.load_passages(l2.DATA3) if p['scope'] == '限']
    assert len(ps) == 179
    ids = set()
    for p in ps:
        lim = p['limit']
        assert p['parse'] == 'unparsed' and p['reason'] == '운 구절'
        assert lim['type'] in ('大限', '小限·太歲', '한통칭', '한도 낱말 없음')
        if lim['frame'] == '틀밖':
            assert 'branches' not in lim and lim['reason']
        if 'branches' in lim:
            assert lim['frame'] == '大限'
            for b in lim['branches']:
                assert b['id'] not in ids
                ids.add(b['id'])
                assert b['polarity'] in ('길', '흉', '중', '미정')
        else:
            assert lim['reason']
    assert sum(1 for p in ps if p['limit']['type'] == '小限·太歲') == 20


def test_existing_j3_untouched(R):
    """限 구절은 evaluate_j3가 여전히 검사하지 않는다(scope가 命인 구절만 판정 목록에 든다)."""
    ps = {p['id']: p for p in l2.load_passages(l2.DATA3)}
    for v in l2.evaluate_j3(R).values():
        assert all(ps[it['id']]['scope'] == '命' for it in v['passages'])


@pytest.mark.parametrize('case', REPRO, ids=[c[0] for c in REPRO])
def test_runs_on_repro_charts(case):
    r = compute(*case)
    for i, d in enumerate(r['daehan']):
        e = l2.evaluate_limit(r, i)
        assert e['palace'] == d['palace'] and len(e['outside']) == 20
        assert all(it['verdict'] in (S, H, N) and 0 <= it['met'] <= it['total'] for it in e['passages'])
        assert all(isinstance(it['failed'], list) for it in e['passages'])
        assert len({it['id'] for it in e['passages']}) == len(e['passages'])
        assert e['summary']['성질서술'] == 0


def test_target_chart_seven_periods(R):
    """대상 명반의 출생 뒤 대한 일곱 구간이 돈다. 小限·太歲 20구절은 어느 구간에서도 검사되지 않는다."""
    out = [l2.evaluate_limit(R, i) for i in range(7)]
    assert [e['palace'] for e in out] == [d['palace'] for d in R['daehan'][:7]]
    outside = {x['id'] for x in out[0]['outside']}
    for e in out:
        assert {it['id'] for it in e['passages']}.isdisjoint(outside)
        assert {x['id'] for x in e['outside']} == outside
    assert sum(1 for e in out for it in e['passages'] if it['verdict'] == S) > 0
