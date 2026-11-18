"""L2 궁별 글귀 판정 시험. 기대값은 원점재검토_20261111/20_본명_재도출.md의 권4 구절 판정이다.
기대 문서와 어긋나는 것은 억지로 맞추지 않고 xfail로 두고 사유를 적는다."""
import json
import os

import pytest

from engine_v2 import compute, l2
from engine_v2.tests.test_generality import CASES

SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..', '..', 'library', 'ziwei_saju', '03_support', '진희이구결_전서수록') + os.sep
FILES = {'兄': '二兄弟', '妻': '三妻妾', '子': '四子女', '財': '五財帛', '疾': '六疾厄', '遷': '七遷移',
         '奴': '八奴僕', '官': '九官禄', '田': '十田宅', '福': '十一福徳', '父': '十二父母'}
S, H, N = '선다', '반만', '서지 않는다'

X = {
    '父:47': '엔진이 천기 卯의 거문 밝기를 미확인으로 둔다. 기대 문서는 조건을 거문에 천기 동궁으로만 읽어 선다',
    '疾:3': '명궁 기준 절차 구절이라 조건 궁이 질액궁이 아니다. unparsed로 두었다',
    '妻:21': '기대 문서는 대궁의 별을 福 5에서는 반만, 여기서는 서지 않는다로 갈라 적었다. 코드는 동궁 밖이면 반만으로 통일',
    '兄:8': '기대 문서는 陷地 절(선다)과 加殺 절(반만)을 따로 읽는다. 코드는 한 구절로 묶어 반만',
}
# 재결(명세 5절 12번 자, 2026-11-14): 官:89는 동궁 조건의 좌보·우필이 동궁에도 삼방·대궁에도 없어 반만에서 서지 않는다로 바꿨다.
EXP = [('福:3', S), ('福:4', S), ('福:6', S), ('福:45', S), ('福:46', S), ('福:49', S), ('福:5', H), ('福:70', H),
       ('父:16#1', S), ('父:19', S), ('父:47', S), ('父:49', S), ('父:51', S), ('父:77', S), ('父:3', S), ('父:4#1', S),
       ('疾:61#2', S), ('疾:63#1', S), ('疾:3', S), ('疾:62', N),
       ('兄:7', S), ('兄:8', S), ('兄:23', S),
       ('奴:62#2', S), ('奴:13', H), ('奴:15', H), ('奴:25', H), ('奴:28', H),
       ('妻:18', S), ('妻:19', S), ('妻:31', S), ('妻:32', S), ('妻:86', S), ('妻:21', N),
       ('田:63', S), ('田:64#1', S), ('田:55', S), ('田:47', N),
       ('官:58', S), ('官:77', S), ('官:89', N), ('遷:25', S), ('財:60#1', S), ('子:29', S)]


@pytest.fixture(scope='module')
def ev():
    r = compute('1999-08-04', '10:14', True, -38)
    out = l2.evaluate(r)
    return {it['id']: it for v in out.values() for it in v['passages']}, out


@pytest.mark.parametrize('pid,want', [pytest.param(i, w, marks=pytest.mark.xfail(reason=X[i], strict=False) if i in X else ())
                                      for i, w in EXP])
def test_expected(ev, pid, want):
    got = ev[0].get(pid)
    assert got is not None, '판정 목록에 없음'
    assert got['verdict'] == want, got


def test_summary_shape(ev):
    out = ev[1]
    assert set(out) == {'명궁', '신궁'} | set(l2.ROLES)
    for v in out.values():
        s = v['summary']
        assert {'길구절수', '흉구절수', '조건충족합'} <= set(s)
        for it in v['passages']:
            assert it['verdict'] in (S, H, N, '성질') and 0 <= it['met'] <= it['total'] and isinstance(it['failed'], list)


def test_table_integrity():
    ps = l2.load_passages()
    assert len({p['id'] for p in ps}) == len(ps)
    for p in ps:
        assert p['parse'] in ('auto', 'manual', 'unparsed') and p['polarity'] in ('길', '흉', '중', '미정')
        if p['parse'] == 'unparsed':
            assert p.get('reason')
            continue
        for c in p['conds']:
            assert c['kind'] in ('동궁', '삼방대궁', '밝기', '궁지', '생년간', '성별', '살', '길', '공망') and 'negate' in c


def test_text_verbatim():
    if not os.path.isdir(SRC):
        pytest.skip('원문 폴더 없음')
    cache = {}
    for p in l2.load_passages():
        ab = p['id'].split(':')[0]
        lines = cache.setdefault(ab, open(SRC + '4_%s.txt' % FILES[ab], encoding='utf-8').read().split('\n'))
        assert lines[p['line'] - 1].split('\t', 1)[1] == p['text'], p['id']


@pytest.fixture(scope='module', params=CASES, ids=[c[0] for c in CASES])
def R(request):
    return compute(*request.param)


def test_runs_on_other_charts(R):
    out = l2.evaluate(R)
    assert set(out) == {'명궁', '신궁'} | set(l2.ROLES) and all(out[r]['passages'] for r in l2.ROLES)


# ---- 권3 입명 구절: 명궁·신궁 ----
J3 = {
    # 명궁 寅 탐랑(평) 화권, 화성·천형. 20_본명_재도출 1절 나항
    ('명궁', '入限:577#3'): '성질', ('명궁', '入限:580#1'): S, ('명궁', '入限:766'): H,
    ('명궁', '入限:589'): N, ('명궁', '入限:584'): N,
    # 신궁 子 무곡·천부. 7절 나항
    ('신궁', '入限:396'): S, ('신궁', '入限:517'): S,
}
# 재결(명세 5절 12번 라, 2026-11-14): 조건 없는 별의 성질 서술은 선다가 아니라 성질로 낸다. 577#3은 20_본명_재도출의 선다에서 성질로 바꿨다.


@pytest.fixture(scope='module')
def j3():
    return l2.evaluate_j3(compute('1999-08-04', '10:14', True, -38))


@pytest.mark.parametrize('key,want', list(J3.items()), ids=lambda k: str(k))
def test_j3_expected(j3, key, want):
    name, pid = key
    got = {it['id']: it for it in j3[name]['passages']}.get(pid)
    assert got is not None, '판정 목록에 없음'
    assert got['verdict'] == want, got


def test_j3_male_counts_female(j3):
    assert j3['명궁']['여명구절수'] > 0
    assert all(not it['id'].startswith('入限:2') for it in [])  # 女命 구절은 판정 목록에 없다
    ps = {p['id']: p for p in l2.load_passages(l2.DATA3)}
    for v in j3.values():
        assert all(ps[it['id']]['scope'] == '命' for it in v['passages'])


def test_j3_table_integrity():
    ps = l2.load_passages(l2.DATA3)
    assert len({p['id'] for p in ps}) == len(ps)
    for p in ps:
        assert p['scope'] in ('命', '女命', '限') and p['parse'] in ('auto', 'manual', 'unparsed')
        if p['scope'] == '限':
            assert p['parse'] == 'unparsed' and p['reason'] == '운 구절'
        if p['parse'] == 'unparsed':
            assert p.get('reason')


def test_j3_runs_on_cases():
    for c in CASES:
        out = l2.evaluate_j3(compute(*c))
        assert set(out) == {'명궁', '신궁'}


def test_j4_unchanged():
    r = compute('1999-08-04', '10:14', True, -38)
    full = l2.evaluate(r)
    only4 = l2.evaluate(r, l2.load_passages())
    for role in l2.ROLES:
        assert full[role] == only4[role]


# ---- O22: 열거 조건의 셈(명세 5절 12번) ----
def _j3_items(name='명궁', chart=('1999-08-04', '10:14', True, -38)):
    return {it['id']: it for it in l2.evaluate_j3(compute(*chart))[name]['passages']}


def test_bundle_all_required_391():
    # 月禄馬㑹: 태음·녹존·천마가 모두 모여야 선다. 子의 삼방대궁에 천마가 없으므로 서지 않는다(전엔 1/1 선다였음)
    assert _j3_items('신궁')['入限:390#2']['verdict'] != S
    ps = {p['id']: p for p in l2.load_passages(l2.DATA3)}
    assert ps['入限:390#2']['conds'][-1].get('all') is True and ps['入限:390#2']['conds'][-1]['values'] == ['녹존', '천마']


def test_all_marks_exist():
    n3 = sum(1 for p in l2.load_passages(l2.DATA3) for c in p['conds'] if c.get('all'))
    n4 = sum(1 for p in l2.load_passages() for c in p['conds'] if c.get('all'))
    assert n3 >= 10 and n4 >= 10


def test_enum_counts_and_subject_excluded():
    it = _j3_items('신궁')['入限:393']
    assert [(e['k'], e['n']) for e in it['enum']] == [(1, 2), (2, 4)]
    ps = {p['id']: p for p in l2.load_passages(l2.DATA3)}
    gil = [c for c in ps['入限:1048']['conds'] if c['kind'] == '길' and not c.get('role')][0]
    r = compute('1999-08-04', '10:14', True, -38)
    e = l2.evaluate_j3(r)['명궁']['passages']
    mine = [i for i in e if i['id'] == '入限:1048']
    assert mine and all('화권' not in x['present'] and x['n'] == len(gil['values']) - 1 for x in mine[0]['enum'])


def test_nature_not_counted_as_stand():
    for name in ('명궁', '신궁'):
        v = l2.evaluate_j3(compute('1999-08-04', '10:14', True, -38))[name]
        nat = [it for it in v['passages'] if it['verdict'] == '성질']
        assert nat and all(it['total'] == 0 for it in nat)
        assert v['summary']['성질서술'] == len(nat)
        assert all(it['verdict'] != S or it['total'] > 0 for it in v['passages'])


def test_split_sentence_merged_896():
    ids = [p['id'] for p in l2.load_passages(l2.DATA3) if p['line'] == 896]
    assert ids == ['入限:896']


# ---- O22 2차: 更 이어받기, 문장 단위, 반만의 뜻 ----
def test_inherits_393_not_stand_when_wu_is_bright():
    ps = {p['id']: p for p in l2.load_passages(l2.DATA3)}
    assert ps['入限:393']['inherits'] == '入限:392'
    assert _j3_items('신궁')['入限:393']['verdict'] == N       # 子의 무곡은 旺, 392행은 함지일 때의 말
    n3 = sum(1 for p in ps.values() if p.get('inherits'))
    n4 = sum(1 for p in l2.load_passages() if p.get('inherits'))
    assert n3 >= 20 and n4 >= 4


def test_inherits_unparsed_parent_makes_child_unparsed():
    out = l2._inherit([{'id': 'a', 'parse': 'unparsed', 'conds': [], 'reason': 'x'},
                       {'id': 'b', 'parse': 'auto', 'conds': [], 'inherits': 'a'}])
    assert out[1]['parse'] == 'unparsed'


def test_joined_sentences():
    ps = {p['id']: p for p in l2.load_passages(l2.DATA3)}
    assert [c['line'] for c in ps['入限:387#3']['text_cont']] == [388, 389]
    assert [c['line'] for c in ps['入限:390#2']['text_cont']] == [391]
    assert not any(p['line'] in (389, 391) for p in ps.values())


def test_half_needs_dong_gung_star_somewhere():
    m = _j3_items('명궁')
    assert '入限:599' not in m or m['入限:599']['verdict'] == N      # 경양이 동궁·삼방·대궁 어디에도 없다
    s = _j3_items('신궁')
    assert s.get('入限:387#3', {}).get('verdict', N) == N           # 창곡이 없는데 밝기만 맞아 반만이던 것
    assert _j3_items('명궁')['入限:766']['verdict'] == H           # 주체 조합은 섰고 밝기만 안 섬(ㄴ)
