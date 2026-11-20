"""일반성 시험: 음양·남녀를 섞은 다른 생년월일에서 예외 없이 산출되고 불변식을 지킨다.
그리고 엔진 코드에 명반 상수(특정 궁·별 이름 조건문)가 없는지 정적으로 검사한다."""
import ast
import datetime as dt
import os

import pytest

from engine_v2 import compute
from engine_v2.chart import main_stars
from engine_v2.common import BR, MAIN14, STEM, bi, opp, yang_stem

CASES = [
    ('1990-03-15', '14:00', False, 0),     # 庚午 陽年 여 → 대운 역행
    ('1985-11-02', '06:00', True, 0),      # 乙丑 陰年 남 → 역행
    ('2004-01-10', '23:30', True, -30),    # 입춘 전·설 전(癸未), 23시대 子時 경계
    ('1987-02-18', '08:10', False, 0),     # 丁卯 陰年 여 → 순행
    ('2023-04-10', '12:00', True, 0),      # 윤2월
    ('1993-05-20', '23:40', False, 0),     # 재현 A: 子時(다음 날로 세면 음력 4-01, 같은 날이면 윤3-29)
    ('2020-06-05', '14:30', True, 0),      # 재현 B: 윤4월, 芒種(13:58 KST) 32분 뒤
    ('1996-02-04', '22:30', True, 0),      # 재현 C: 立春(22:07 KST) 23분 뒤, 사주 년 丙子·자미 생년 乙亥
]


@pytest.fixture(scope='module', params=CASES, ids=[c[0] for c in CASES])
def R(request):
    return compute(*request.param)


def test_main14_once(R):
    seen = [s['name'] for z in BR for s in R['chart']['palaces'][z]['stars'] if s['name'] in MAIN14]
    assert sorted(seen) == sorted(MAIN14)


def test_every_star_once(R):
    names = [s['name'] for z in BR for s in R['chart']['palaces'][z]['stars']]
    assert len(names) == len(set(names))


def test_daehan_contiguous(R):
    d = R['daehan']
    assert len(d) == 12 and len({p['palace'] for p in d}) == 12
    assert d[0]['palace'] == R['chart']['ming'] and d[0]['age_from'] == R['chart']['ju']
    for a, b in zip(d, d[1:]):
        assert a['end'] == b['start'] and b['age_from'] == a['age_to'] + 1
        step = (bi(b['palace']) - bi(a['palace'])) % 12
        assert step == (1 if R['chart']['direction'] == '순행' else 11)


def test_daewoon_rule(R):
    b = R['chart']['birth']
    fwd = yang_stem(b['saju']['year'][0]) == b['input']['male']
    d = R['daewoon']
    assert d['direction'] == ('순행' if fwd else '역행')
    m = b['saju']['month']
    first = d['periods'][0]['gz']
    assert (STEM.index(first[0]) - STEM.index(m[0])) % 10 == (1 if fwd else 9)
    assert (bi(first[1]) - bi(m[1])) % 12 == (1 if fwd else 11)
    assert 0 <= d['years'] <= 10.5
    for a, c in zip(d['periods'], d['periods'][1:]):
        assert a['end'] == c['start']


def test_empty_vs_borrow_consistent(R):
    ch, l1 = R['chart'], R['l1']
    assert set(l1['empty']) == {z for z in BR if not main_stars(ch, z)}
    assert set(l1['borrow']) == set(l1['empty'])
    kz = set(ch['kong']['정공'])
    for z, b in l1['borrow'].items():
        assert b['sender'] == opp(z)
        if b['status'] == '차단':
            assert z in kz
        if b['status'] == '성립':
            assert z not in kz and main_stars(ch, opp(z))
    for z in BR:
        if main_stars(ch, z):
            assert z not in l1['borrow']        # 주성이 있는 궁은 받지 않는다(R3)


def test_birth_hua_matches_table(R):
    ch, sh = R['chart'], R['sihua']
    for h, v in ch['birth_hua'].items():
        assert sh.of(ch['year_stem'])[h] == v['star'] and ch['pos'][v['star']] == v['palace']


def test_l3_runs(R):
    l3 = R['l3']
    assert len(l3['path_daehan']) == 12 and l3['path_daewoon'] and l3['contrast']
    words = repr(l3)
    assert '확정' not in words


@pytest.mark.parametrize('boundary', ['lichun', 'seol', 'jan1'])
def test_seun_boundary_options(boundary):
    """세운 해 경계는 설정값(기본 입춘, 명세 판 0.4 9절 11번)."""
    r = compute('1990-03-15', '14:00', False, 0, seun_boundary=boundary)
    assert r['l3']['seun_boundary']['value'] == boundary and '가정' in r['l3']['seun_boundary']['note']


def test_zi_hour_next_day():
    """23시대는 다음 날 子時로 센다(zi_rule='next_day' 기본값)."""
    r = compute('2004-01-10', '23:30', True, 0, with_l3=False)
    b = r['chart']['birth']
    assert b['hour_branch'] == '子' and b['lunar']['day'] == 20


def test_leap_month_rules():
    """윤달: 기본 'same'은 그 달, 'next'는 다음 달로 명반을 세운다."""
    a = compute('2023-04-10', '12:00', True, 0, with_l3=False)
    b = compute('2023-04-10', '12:00', True, 0, with_l3=False, leap_rule='next')
    assert a['chart']['birth']['lunar']['leap'] is True
    assert (a['chart']['birth']['lunar']['chart_month'], b['chart']['birth']['lunar']['chart_month']) == (2, 3)


def test_yearpillar_lichun():
    """2004-01-10은 입춘 전이라 사주 년주는 癸未, 설 전이라 자미 생년도 癸未."""
    r = compute('2004-01-10', '12:00', True, 0, with_l3=False)
    assert r['chart']['birth']['saju']['year'] == '癸未' and r['chart']['year_gz'] == '癸未'


# ── 명반 상수 검사 ────────────────────────────────────────
ENGINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENGINE_FILES = ['calendar.py', 'chart.py', 'luck.py', 'structure.py', 'fortune.py', 'common.py', 'tables.py', '__main__.py']
BRANCH_SET = set(BR)
STAR_SET = set(MAIN14) | {'좌보', '우필', '문창', '문곡', '천괴', '천월', '녹존', '경양', '타라', '화성', '영성', '지공', '지겁', '천마', '천형'}


def _consts(node):
    return [n.value for n in ast.walk(node) if isinstance(n, ast.Constant) and isinstance(n.value, str)]


@pytest.mark.parametrize('fname', ENGINE_FILES)
def test_no_chart_constants_in_conditions(fname):
    """엔진 조건문(if, 비교, while, 조건식)에 지지 한 글자나 별 이름 상수가 없다.
    안성 공식의 기점(예: 寅에서 월 순행)은 대입문의 표 값이라 조건문이 아니다."""
    path = os.path.join(ENGINE, fname)
    if not os.path.exists(path):
        pytest.skip('없음')
    tree = ast.parse(open(path, encoding='utf-8').read())
    bad = []
    for node in ast.walk(tree):
        tests = []
        if isinstance(node, (ast.If, ast.While, ast.IfExp)):
            tests.append(node.test)
        if isinstance(node, ast.comprehension):
            tests.extend(node.ifs)
        if isinstance(node, ast.Compare):
            tests.append(node)
        for t in tests:
            for c in _consts(t):
                if c in BRANCH_SET or c in STAR_SET:
                    bad.append((getattr(t, 'lineno', '?'), c))
    assert not bad, bad


# ── 노출도(명세 8절 1번)와 중첩의 수(8절 4번) ─────────────────
def test_exposure_bounds(R):
    """모든 틀과 사화 종류에서 0 ≤ k ≤ 10이고 목록 길이 = k, 분모는 10."""
    expo = R['l3']['exposure']
    frames = [expo['natal']] + [d['frames'] for d in expo['daehan']]
    assert len(expo['daehan']) == 12
    for fr in frames:
        for cells in fr.values():
            for cell in cells.values():
                assert 0 <= cell['k'] <= 10 and cell['of'] == 10 and len(cell['list']) == cell['k']
    for d in expo['daehan']:
        assert set(d['frames']) == {'대한명궁', '대한삼방', '본명삼방'}
        for cells in d['frames'].values():
            c = cells['기']
            assert 0 <= c['overlap_k'] <= c['k'] <= 10 and len(c['overlap_list']) == c['overlap_k']
        assert 'k' not in d['overlap_years'] and all(0 <= v <= 10 for v in d['overlap_years']['by_hua'].values())
