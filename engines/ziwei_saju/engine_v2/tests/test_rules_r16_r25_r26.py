"""R16(화과는 화기를 만나면 뜻이 없다), R25(화탐격의 형태와 온전함), R26(명궁 파군·탐랑), 8절 8번(대한 경계값).
대상 명반은 test_regression.py와 같다. 재현 명반은 test_generality의 CASES다."""
import pytest

from engine_v2 import compute
from engine_v2.tests.test_generality import CASES

from engine_v2.tests.target import DATE, TIME, MALE, KW


@pytest.fixture(scope='module')
def R():
    return compute(DATE, TIME, MALE, 0, **KW)


@pytest.fixture(scope='module', params=CASES, ids=[c[0] for c in CASES])
def G(request):
    return compute(*request.param)


def dh(R, palace):
    return next(p for p in R['l3']['path_daehan'] if p['palace'] == palace)


# ── 8절 8번 ──
def test_daehyung_values(R):
    want = {'丑': (True, 3), '子': (False, 0), '亥': (False, 2), '酉': (True, 3)}
    for z, (flag, k) in want.items():
        c = dh(R, z)['exposure']['대한삼방']['기']
        assert (c['daehyung'], c['overlap_k']) == (flag, k), z
        assert c['daehyung_basis'] == '자붕이 3488~3492, 3/10 명문'
        assert c['beyond_text'] == (k > 3)


# ── R16 ──
def test_r16_confirmed_example(R):
    # 丁 세운: 천기 화과와 거문 화기가 같은 궁(卯)에 떨어진다
    y = next(r for r in dh(R, '丑')['years'] if r['year'] == 2017)
    g = next(m for m in y['marks'] if m['hua'] == '과')
    assert g['star'] == '천기' and g['void_by_ji'] == '확인'
    v = next(x for x in y['void_gwa'] if x['src'] == '세운:천기')
    assert v['with_'] == ['세운:거문']


def test_r16_inference_kinds(R):
    kinds = {x['void_by_ji'] for p in R['l3']['path_daehan'] for y in p['years'] for x in y['void_gwa']}
    assert {'확인', '추론', None} <= kinds


def test_r16_k_unchanged_and_effective(R):
    p = dh(R, '丑')
    c = p['exposure']['대한삼방']['과']
    assert c['k'] == 7 and c['k_effective'] == 5 and len(c['void_confirmed']) == 2


# ── R25 ──
def test_r25_target(R):
    h = R['l1']['gyeok']['hwatam']
    assert h['form'] is True and h['complete'] is False
    kinds = {(r['kind'], r['star']) for r in h['reasons']}
    assert ('탐랑 밝기', '탐랑') in kinds and ('공겁', '지공') in kinds
    assert next(r for r in h['reasons'] if r['kind'] == '탐랑 밝기')['grade'] == '平'
    assert next(r for r in h['reasons'] if r['star'] == '지공')['palace'] == '午'


# ── R26 ──
def test_r26_target(R):
    assert R['l1']['ming_volatile'] is True
    assert R['l1']['ming_volatile_basis'] == '자붕이 3889~3894(R26). 끝 문장은 추정형'


def test_r26_borrowed_is_unknown(R):
    # 합성 입력: 명궁을 공궁으로 두고 대궁의 파군(차성)만 들어오게 한다
    from engine_v2 import structure
    ch = {'ming': '子', 'pos': {}}
    fake = {'子': dict(status='성립', sender_main=['파군'])}
    orig = structure.effective_main
    structure.effective_main = lambda c, b, z: [('파군', '차성')]
    try:
        d = structure.ming_volatile(ch, fake)
    finally:
        structure.effective_main = orig
    assert d['value'] is None and d['note'] == '차성, 원문 근거 없음(미확인)' and d['via'] == ['차성']


# ── 재현 명반 세 건 이상(CASES 전부)에서 키가 빠짐없이 ──
def test_keys_present(G):
    l1 = G['l1']
    assert l1['ming_volatile'] in (True, False, None) and l1['ming_volatile_basis']
    h = l1['gyeok']['hwatam']
    assert {'form', 'complete', 'reasons', 'basis'} <= set(h)
    assert isinstance(h['form'], bool)
    if h['form']:
        assert h['complete'] == (not h['reasons'])
    else:
        assert h['complete'] is None
    for p in G['l3']['path_daehan']:
        ex = p['exposure']
        c = ex['대한삼방']['기']
        assert {'daehyung', 'daehyung_basis', 'beyond_text', 'overlap_k'} <= set(c)
        assert c['daehyung'] == (c['overlap_k'] >= 3) and c['beyond_text'] == (c['overlap_k'] > 3)
        for name in ('대한명궁', '대한삼방'):
            g = ex[name]['과']
            assert 'k_effective' in g and 0 <= g['k_effective'] <= g['k']
        assert 'k_effective' not in ex['본명삼방']['과']
        for y in p['years']:
            assert 'void_gwa' in y
            for m in y['marks']:
                if m['hua'] == '과':
                    assert m['void_by_ji'] in ('확인', '추론', None)
            for x in y['void_gwa']:
                assert x['void_by_ji'] in ('확인', '추론', None)
