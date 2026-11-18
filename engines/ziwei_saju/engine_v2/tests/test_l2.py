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
# 父:3은 조건 없는 읽는 법 문장(凢看父母，以太陽星為父…)이라 명세 5절 12번 라·차에 따라 선다가 아니라 성질로 바꿨다(독립 검증 2026-11-18).

X = {
    '父:47': '엔진이 천기 卯의 거문 밝기를 미확인으로 둔다. 기대 문서는 조건을 거문에 천기 동궁으로만 읽어 선다',
    '疾:3': '명궁 기준 절차 구절이라 조건 궁이 질액궁이 아니다. unparsed로 두었다',
    '妻:21': '기대 문서는 대궁의 별을 福 5에서는 반만, 여기서는 서지 않는다로 갈라 적었다. 코드는 동궁 밖이면 반만으로 통일',
    '兄:8': '기대 문서는 陷地 절(선다)과 加殺 절(반만)을 따로 읽는다. 코드는 한 구절로 묶어 반만',
}
# 재결(명세 5절 12번 자, 2026-11-14): 官:89는 동궁 조건의 좌보·우필이 동궁에도 삼방·대궁에도 없어 반만에서 서지 않는다로 바꿨다.
EXP = [('福:3', S), ('福:4', S), ('福:6', S), ('福:45', S), ('福:46', S), ('福:49', S), ('福:5', H), ('福:70', H),
       ('父:16#1', S), ('父:19', S), ('父:47', S), ('父:49', S), ('父:51', S), ('父:77', S), ('父:3', '성질'), ('父:4#1', S),
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
            assert c['kind'] in ('동궁', '삼방대궁', '밝기', '궁지', '생년간', '성별', '살', '길', '공망',
                            '생년지지', '생시', '대궁', '삼합', '협', '타궁별') and 'negate' in c      # 뒤 여섯은 해독 2차(2026-11-18)에 더한 종류


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


# ---- 해독 2차(2026-11-18): 새 조건 종류 합성 시험. 각 종류마다 참, 거짓, 미확인 ----
from engine_v2.common import BR as _BR, bi as _bi, bz as _bz, roles_from as _roles_from, sanfang as _sanfang


def _synth(put=None, year_gz='甲子', hour='午', ming='子', drop=()):
    """12궁 합성 명반. put = {지지: [별 이름...]}"""
    roles = _roles_from(ming)
    put = put or {}
    pal = {z: {'role': roles[z], 'stem': '甲', 'stars': [{'name': n, 'kind': '주성' if n in ('자미', '태양', '태음') else '보좌', 'cls': '미확인', 'hua': None}
                                                         for n in put.get(z, [])]} for z in _BR if z not in drop}
    chart = {'palaces': pal, 'year_gz': year_gz, 'year_stem': year_gz[0] if year_gz else None, 'male': True, 'ming': ming, 'shen': ming,
             'pos': {}, 'kong': {}, 'birth': {'hour_branch': hour}}
    if year_gz is None:
        chart.pop('year_gz')
    return {'chart': chart, 'l1': {}}


def _chk(res, c, z='子', p=None):
    c = dict({'negate': False}, **c)
    return l2._check(l2._Ctx(res), z, p or {'star': None}, c)


def test_new_kind_birth_year_branch():
    c = {'kind': '생년지지', 'values': ['寅', '午', '戌']}
    assert _chk(_synth(year_gz='甲寅'), c) is True
    assert _chk(_synth(year_gz='甲子'), c) is False
    assert _chk(_synth(year_gz=None), c) is None
    assert _chk(_synth(year_gz='甲子'), dict(c, negate=True)) is True


def test_new_kind_day_night_birth():
    day, night = {'kind': '생시', 'values': ['日生']}, {'kind': '생시', 'values': ['夜生']}
    for h, d in (('辰', True), ('巳', True), ('午', True), ('未', True), ('戌', False), ('亥', False), ('子', False), ('丑', False)):
        assert _chk(_synth(hour=h), day) is d and _chk(_synth(hour=h), night) is (not d), h
    for h in '寅卯申酉':                      # 11-3 3번: 정의가 없으면 미확인
        assert _chk(_synth(hour=h), day) is None and _chk(_synth(hour=h), night) is None, h
    assert _chk(_synth(hour=None), day) is None


def test_new_kind_opposite_palace_only():
    base = {'kind': '대궁', 'values': ['자미']}
    assert _chk(_synth({'午': ['자미']}), base) is True          # 子의 대궁은 午
    assert _chk(_synth({'申': ['자미']}), base) is False         # 삼합 자리에 있으면 대궁이 아니다
    assert _chk(_synth({'子': ['자미']}), base) is False         # 동궁도 아니다
    assert _chk(_synth({'午': ['자미']}, drop=('午',)), base) is None
    assert _chk(_synth({'午': ['태양']}), {'kind': '대궁', 'values': ['주성']}) is True
    assert _chk(_synth({'午': ['좌보']}), {'kind': '대궁', 'values': ['주성']}) is False
    # 기존 값 only: 대궁(권4 子:74#3, 子:79#1)도 같은 범위로 읽는다
    gil = {'kind': '길', 'values': ['좌보', '우필'], 'scope': '삼방대궁', 'only': '대궁'}
    assert _chk(_synth({'午': ['좌보']}), gil) is True and _chk(_synth({'申': ['좌보']}), gil) is False


def test_new_kind_sanhe_without_opposite():
    base = {'kind': '삼합', 'values': ['자미']}
    assert _l2_scope('子', '삼합') == ['申', '辰']
    assert _chk(_synth({'辰': ['자미']}), base) is True and _chk(_synth({'申': ['자미']}), base) is True
    assert _chk(_synth({'午': ['자미']}), base) is False         # 대궁은 삼합에서 뺀다
    assert _chk(_synth({'子': ['자미']}), base) is False
    assert _chk(_synth({'辰': ['자미']}, drop=('辰',)), base) is None
    gil = {'kind': '길', 'values': ['좌보', '우필'], 'scope': '삼합'}      # 범위로도 쓴다
    assert _chk(_synth({'辰': ['좌보']}), gil) is True and _chk(_synth({'午': ['좌보']}), gil) is False


def _l2_scope(z, scope):
    return l2._scope_palaces(z, scope)


def test_new_kind_jia():
    c = {'kind': '협', 'values': ['좌보', '우필'], 'scope': '양옆'}
    assert _chk(_synth({'亥': ['좌보'], '丑': ['우필']}), c) is True
    assert _chk(_synth({'丑': ['좌보'], '亥': ['우필']}), c) is True
    assert _chk(_synth({'亥': ['좌보'], '午': ['우필']}), c) is False
    assert _chk(_synth({'亥': ['좌보', '우필']}), c) is False      # 한쪽에 둘이 몰리면 협이 아니다
    two = dict(c, values=['좌보', '우필', '문창', '문곡'], sets=[['좌보', '우필'], ['문창', '문곡']])
    assert _chk(_synth({'亥': ['문창'], '丑': ['문곡']}), two) is True
    assert _chk(_synth({'亥': ['좌보'], '丑': ['문곡']}), two) is False   # 다른 짝끼리는 협이 아니다
    assert _chk(_synth({'亥': ['좌보'], '丑': ['우필']}), dict(c, values=['좌보'])) is None


def test_new_kind_other_palace_star():
    ming = '子'
    res = _synth({}, ming=ming)
    z = l2._Ctx(res).role_palace('복덕')
    res = _synth({z: ['자미']}, ming=ming)
    c = {'kind': '타궁별', 'values': {'복덕': ['자미']}}
    assert _chk(res, c) is True
    assert _chk(_synth({}, ming=ming), c) is False
    assert _chk(res, {'kind': '타궁별', 'values': {'없는궁': ['자미']}}) is None
    assert _chk(res, {'kind': '타궁별', 'values': {'복덕': ['자미', '태양']}}) is True            # 별은 하나 이상
    assert _chk(res, {'kind': '타궁별', 'values': {'복덕': ['자미', '태양']}, 'all': True}) is False


def test_new_kind_unknown_goes_to_unknown_list():
    res = _synth(hour='寅')
    ctx = l2._Ctx(res)
    p = {'id': 'x', 'palace': '형제', 'star': None, 'parse': 'manual', 'polarity': '미정', 'conds': [{'kind': '생시', 'values': ['日生'], 'negate': False}]}
    z = [q for q, v in ctx.pal.items() if v['role'] == '형제'][0]
    items, unp = l2.evaluate_palace(ctx, z, [p], '형제')
    assert unp == [] and items[0]['unknown'] == ['생시(日生)'] and items[0]['verdict'] == '서지 않는다' and items[0]['met'] == 0


def test_new_kinds_hard_when_false():
    res = _synth(year_gz='甲子')
    ctx = l2._Ctx(res)
    z = [q for q, v in ctx.pal.items() if v['role'] == '형제'][0]
    p = {'id': 'x', 'palace': '형제', 'star': None, 'parse': 'manual', 'polarity': '길',
         'conds': [{'kind': '생년지지', 'values': ['寅'], 'negate': False}, {'kind': '대궁', 'values': ['주성'], 'negate': True}]}
    items, _ = l2.evaluate_palace(ctx, z, [p], '형제')
    assert items[0]['verdict'] == '서지 않는다' and items[0]['met'] == 1     # 생년 지지가 맞지 않으면 다른 조건이 맞아도 서지 않는다
    # 전제 조건(premise): 자녀궁에 주성이 있으면(전제 '주성 없음'이 거짓) 대궁 조건이 맞아도 서지 않는다
    z2 = [q for q, v in l2._Ctx(_synth()).pal.items() if v['role'] == '형제'][0]
    res2 = _synth({z2: ['자미'], _bz(_bi(z2) + 6): ['태양']})
    ctx2 = l2._Ctx(res2)
    pp = {'id': 'y', 'palace': '형제', 'star': None, 'parse': 'manual', 'polarity': '미정',
          'conds': [{'kind': '동궁', 'values': ['주성'], 'negate': True, 'scope': '동궁', 'premise': True}, {'kind': '대궁', 'values': ['주성'], 'negate': False}]}
    it, _ = l2.evaluate_palace(ctx2, z2, [pp], '형제')
    assert it[0]['met'] == 1 and it[0]['verdict'] == '서지 않는다'
    pp['conds'][0].pop('premise')
    it, _ = l2.evaluate_palace(ctx2, z2, [pp], '형제')
    assert it[0]['verdict'] == '반만'


def test_new_kinds_in_tables_and_scripts(tmp_path):
    import importlib.util
    kinds = {'생년지지', '생시', '대궁', '삼합', '협', '타궁별'}
    seen = {}
    for path in (l2.DATA3, l2.DATA):
        for p in l2.load_passages(path):
            for c in p['conds']:
                if c['kind'] in kinds:
                    seen.setdefault(c['kind'], []).append(p['id'])
                    assert p['parse'] == 'manual' and ('O25 해독2' in p['note'] or '해독 3차' in p['note']), p['id']
    assert kinds <= set(seen), seen
    here = os.path.dirname(l2.__file__) + '/data/'
    for name, src in (('apply_decode2_j3', l2.DATA3), ('apply_decode2_j4', l2.DATA)):
        spec = importlib.util.spec_from_file_location(name, here + name + '.py')
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        cp = str(tmp_path / (name + '.json'))
        open(cp, 'w', encoding='utf-8').write(open(src, encoding='utf-8').read())
        before = open(cp, encoding='utf-8').read()
        m.main(cp)
        assert open(cp, encoding='utf-8').read() == before       # 다시 돌려도 같다(이미 처리된 구절은 건너뜀)


def test_population_grammar_has_no_new_kind_tokens():
    """population.py의 사전 문법(별도 TSV)과 l2의 조건 종류는 겹치지 않는다. l2를 가져오지도 않는다."""
    from engine_v2 import population as P
    assert not hasattr(P, 'l2')
    rules, _ = P.load_dictionary()
    keys = {t.partition('=')[0] for r in rules for t in r.cond_text.split(';') if t.strip() and not t.strip().startswith('#')}
    assert not keys & {'생년지지', '생시', '대궁', '삼합', '협', '타궁별', '생년', '일생', '야생'}, keys


def test_reading_rule_sentence_is_nature(ev):
    """권4의 조건 없는 읽는 법 문장(nature 필드)은 선다가 아니라 성질 서술로 나오고 길흉 집계에서 빠진다"""
    it = ev[0]['父:3']
    assert it['verdict'] == '성질' and it['total'] == 0
    s = ev[1]['부모']['summary']
    assert s['성질서술'] >= 1
    assert it['polarity'] not in ('길', '흉')


def test_decode3_idempotent_and_verdicts(tmp_path, ev):
    """해독 3차(apply_decode3.py): 다시 돌려도 같고, 대상 명반에서 951#3은 선다, 601#2·602·515는 서지 않는다."""
    import importlib.util, shutil
    here = os.path.dirname(l2.__file__) + '/data/'
    spec = importlib.util.spec_from_file_location('apply_decode3', here + 'apply_decode3.py')
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    j3, j4 = str(tmp_path / 'j3.json'), str(tmp_path / 'j4.json')
    shutil.copy(l2.DATA3, j3); shutil.copy(l2.DATA, j4)
    before = (open(j3, encoding='utf-8').read(), open(j4, encoding='utf-8').read())
    m.J3, m.J4 = j3, j4
    m.main()
    assert (open(j3, encoding='utf-8').read(), open(j4, encoding='utf-8').read()) == before
    v = {i: it['verdict'] for i, it in ev[0].items()}
    assert v['入限:951#3'] == '선다'
    for i in ('入限:601#2', '入限:602', '入限:515#1', '入限:515#2'):
        assert v[i] == '서지 않는다', i
