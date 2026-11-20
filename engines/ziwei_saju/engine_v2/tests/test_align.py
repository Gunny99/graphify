"""사주·자미두수 결합기 시험(명세 11-1). 합성 입력으로 결과 다섯 종류와 규칙을, 대상 명반과 재현 명반에서 키와 오류 없음을 본다."""
import datetime as dt

import pytest

from engine_v2 import align, compute, l2
from engine_v2.tests.test_generality import CASES

TARGET = ('1999-08-04', '10:14', True, -38)
KEYS = ('판정_id', '영역', '시기', '방향', '결과', '견준_궁', '근거_구절_id', '맞은_낱말', '신빙성')
ALLOWED = ('합치', '상충', '혼재', '무대응', '구간 갈림', '제외')


def P(id_, verdict, pol):
    return {'id': id_, 'verdict': verdict, 'polarity': pol, 'met': 1, 'total': 1}


def EV(**pal):
    """궁 이름 -> 구절 목록으로 l2.evaluate 출력 꼴을 만든다."""
    return {k: {'palace': '寅', 'passages': v, 'unparsed': [], 'summary': {}} for k, v in pal.items()}


def J(id_, direction, cats, when='평생', words=(), 격=None, 육친=None):
    return {'id': id_, '방향': direction, '범주': list(cats), '시기': when, '낱말': list(words), '신빙성': '조문', '조건': [],
            '격': 격, '육친': 육친}


LEX = {'극_정의': {'귀천': {'첫째': '貴', '둘째': '賤'}, '문': None, '형극': {'첫째': '孤·刑·尅', '둘째': '和·諧'}},
       '차단어': {'목록': ['貴人']},
       '낱말': [{'낱말': '貴', '범주': '귀천', '극': '貴'}, {'낱말': '賤', '범주': '귀천', '극': '賤'},
              {'낱말': '某', '범주': '귀천', '극': None}, {'낱말': '文章', '범주': '문', '극': None},
              {'낱말': '刑', '범주': '형극', '극': '孤·刑·尅'}, {'낱말': '諧', '범주': '형극', '극': '和·諧'}]}


class _AllGui(dict):
    """texts를 주지 않은 시험: 모든 구절의 결과문이 귀천 낱말(貴)을 갖는다."""
    def get(self, k, d=None):
        return '貴'


def run(judgments, ev, tables=None, texts=None):
    kw = dict(daewoon_table=(tables or {}).get('dw'), seun_table=(tables or {}).get('sn'))
    return align.align(None, judgments=judgments, lexicon=LEX, evaluation=ev, texts=texts if texts is not None else _AllGui(), **kw)


# ── 길흉 판정의 결과 넷 ────────────────────────────────
def test_hapchi():
    ev = EV(명궁=[P('a', '선다', '길')], 신궁=[], 관록=[P('b', '반만', '흉')])
    r = run([J('T', '길', ['귀천'])], ev)[0]
    assert r['결과'] == '합치' and r['근거_구절_id'] == ['a'] and r['견준_궁'] == ['명궁', '신궁', '관록']


def test_sangchung():
    ev = EV(명궁=[P('a', '선다', '흉')], 신궁=[], 관록=[])
    r = run([J('T', '길', ['귀천'])], ev)[0]
    assert r['결과'] == '상충' and r['근거_구절_id'] == ['a']


def test_honjae_is_not_decided_by_count():
    ev = EV(명궁=[P('a', '선다', '길'), P('b', '선다', '길'), P('c', '선다', '길')], 신궁=[P('d', '선다', '흉')], 관록=[])
    assert run([J('T', '길', ['귀천'])], ev)[0]['결과'] == '혼재'       # 길이 셋이라도 흉이 하나 서면 혼재다


def test_mudaeung():
    ev = EV(명궁=[P('a', '반만', '길'), P('n', '성질', '길'), P('x', '서지 않는다', '흉')], 신궁=[], 관록=[])
    r = run([J('T', '길', ['귀천'])], ev)[0]
    assert r['결과'] == '무대응' and r['근거_구절_id'] == []


def test_zero_marker_is_mudaeung_for_daewoon():
    t = [{'gz': '己巳', 'segs': [{'daehan': '丑', 'daehan_start': None, '길': [], '흉': []}]}]
    r = run([J('T', '길', ['귀천'], when={'종류': '대운', '간지': ['己巳']})], EV(), {'dw': t})[0]
    assert r['결과'] == '무대응'


# ── 대운·세운과 구간 갈림 ──────────────────────────────
def test_gugan_galim():
    t = [{'gz': '庚午', 'segs': [{'daehan': '寅', '길': ['화록 X(대한삼방)'], '흉': []}, {'daehan': '丑', '길': [], '흉': ['화기 Y(대한삼방)']}]}]
    r = run([J('T', '길', ['귀천'], when={'종류': '대운', '지지': ['午']})], EV(), {'dw': t})[0]
    assert r['결과'] == '구간 갈림'
    assert [s['결과'] for s in r['구간']] == ['합치', '상충'] and r['견준_궁'] == ['寅', '丑']


def test_single_gugan_sangchung_is_sangchung():
    t = [{'gz': '庚午', 'segs': [{'daehan': '寅', '길': [], '흉': ['화기 Y(대한삼방)']}]}]
    assert run([J('T', '길', ['귀천'], when={'종류': '대운', '간지': ['庚午']})], EV(), {'dw': t})[0]['결과'] == '상충'


def test_seun_years_are_matched_by_branch():
    sn = [{'year': 2025, 'gz': '乙巳', 'segs': [{'daehan': '子', '길': ['화록 A(본명삼방)'], '흉': []}]},
          {'year': 2026, 'gz': '丙午', 'segs': [{'daehan': '子', '길': [], '흉': ['x']}]}]
    rs = run([J('T', '길', ['귀천'], when={'종류': '세운', '지지': ['巳']})], EV(), {'sn': sn})
    assert [(r['시기'], r['결과']) for r in rs] == [(2025, '합치')]


# ── 성질 판정과 낱말 사전 ──────────────────────────────
def test_trait_hapchi_sangchung_honjae_mudaeung():
    tx = {'a': '貴顯', 'b': '賤人', 'c': '貴而賤'}
    for ids, expect in ((['a'], '합치'), (['b'], '상충'), (['c'], '혼재'), ([], '무대응')):
        ev = EV(명궁=[P(i, '선다', '길') for i in ids], 신궁=[], 관록=[])
        r = run([J('T', '성질', ['귀천'], words=['貴'])], ev, texts=tx)[0]
        assert r['결과'] == expect, (ids, r)


def test_category_only_with_unknown_pole_is_not_hapchi():
    ev = EV(명궁=[P('a', '선다', '길')], 신궁=[], 관록=[])
    r = run([J('T', '성질', ['귀천'], words=['貴'])], ev, texts={'a': '某'})[0]
    assert r['결과'] == '무대응' and r['맞은_낱말'] == []


def test_no_pole_category_is_hapchi_only():
    ev = EV(명궁=[P('a', '선다', '길')], 신궁=[], 복덕=[])
    assert run([J('T', '성질', ['문'], words=['文章'])], ev, texts={'a': '文章有名'})[0]['결과'] == '합치'
    assert run([J('T', '성질', ['문'], words=['文章'])], ev, texts={'a': '武職'})[0]['결과'] == '무대응'


def test_nature_description_counts_for_traits_not_for_direction():
    ev = EV(명궁=[P('a', '성질', '길')], 신궁=[], 관록=[])
    assert run([J('T', '길', ['귀천'])], ev)[0]['결과'] == '무대응'
    assert run([J('T', '성질', ['귀천'], words=['貴'])], ev, texts={'a': '貴'})[0]['결과'] == '합치'


def test_extract_words_negation_and_mask():
    w = lambda t: [x[0] for x in align.extract_words(t, LEX)]
    assert w('不貴，遇貴人') == []          # 不貴는 세지 않고 貴人은 차단어
    assert w('主貴') == ['貴']
    assert w('子刑，免刑') == ['刑']


def test_extract_words_with_real_lexicon():
    lex = align.load_lexicon()
    got = {x[0] for x in align.extract_words('冨貴雙全，無刑，免災，聦明，僧道', lex)}
    assert {'冨', '貴', '聦明', '僧道'} <= got and '刑' not in got and '災' not in got


# ── 격과 제외 ──────────────────────────────────────────
def test_incomplete_gyeok_is_excluded():
    g = {'이름': 'X', '형태': '선다', '온전함': '불온전', '서지_않는_조건': ['c1'], '미확인_조건': []}
    ev = EV(명궁=[P('a', '선다', '길')], 신궁=[], 관록=[])
    r = run([J('T', '길', ['귀천'], 격=g)], ev)[0]
    assert r['결과'] == '제외' and r['견준_궁'] == [] and r['근거_구절_id'] == []


def test_hyung_direction_reverses():
    ev = EV(명궁=[P('a', '선다', '길')], 신궁=[], 관록=[])
    assert run([J('T', '흉', ['귀천'])], ev)[0]['결과'] == '상충'


def test_relatives_use_named_palace():
    ev = EV(형제=[P('a', '선다', '흉')], 명궁=[P('z', '선다', '길')], 신궁=[])
    r = run([J('T', '흉', ['형극'], 육친=['형제'])], ev, texts={'a': '刑', 'z': '貴'})[0]
    assert r['견준_궁'] == ['형제'] and r['결과'] == '합치'


# ── 판정표 자체 ────────────────────────────────────────
def test_judgment_file_integrity():
    d = align.load_judgments()
    ids = [j['id'] for j in d['판정']]
    assert len(ids) == len(set(ids)) >= 15
    lex = align.load_lexicon()
    for j in d['판정']:
        assert j['출전'] and all(s['원문'] and s['행'] and s['파일'] for s in j['출전'])
        assert j['신빙성'] in ('명례', '조문', '후대', '월령격')
        assert j['방향'] in ('길', '흉', '성질')
        if j['격']:
            assert j['격']['온전함'] in ('온전', '불온전') and j['격']['형태'] in ('선다', '서지 않는다')
    for e in lex['낱말']:
        assert e['출전_id'] and e['범주'] in lex['극_정의']


# ── 대상 명반과 재현 명반 ───────────────────────────────
@pytest.fixture(scope='module')
def target():
    R = compute(*TARGET)
    return R, align.align(R)


def test_target_all_keys_present(target):
    R, rows = target
    assert rows
    for r in rows:
        for k in KEYS:
            assert k in r, (r['판정_id'], k)
        assert r['결과'] in ALLOWED
    ids = {j['id'] for j in align.load_judgments()['판정']}
    assert {r['판정_id'] for r in rows} == ids
    for r in rows:
        if r['결과'] in ('합치', '상충', '혼재'):
            assert r['견준_궁'] and r['근거_구절_id'] or r['시기'] != '평생'
        if r['결과'] == '제외':
            assert r['견준_궁'] == []


def test_target_zabungi_four(target):
    R, _ = target
    ex = align.zabungi_explicit(R)
    assert set(ex) == {'부처', '노복', '명궁', '화탐격'}
    assert ex['부처']['방향'] == '흉' and ex['노복']['방향'] == '제화'


@pytest.mark.parametrize('case', CASES[-3:], ids=lambda c: c[0])
def test_reproduction_charts_run(case):
    R = compute(*case)
    rows = align.align(R)
    assert rows and all(r['결과'] in ALLOWED for r in rows)
    for r in rows:
        for k in KEYS:
            assert k in r


# ── 명세 11-1 4번 가(2026-11-18 정정): 같은 범주 구절만 견준다 ──
def test_other_category_passage_does_not_make_sangchung():
    ev = EV(명궁=[P('a', '선다', '길')], 신궁=[], 관록=[])
    r = run([J('T', '흉', ['형극'])], ev, texts={'a': '貴顯'})[0]      # 귀천 길 구절은 형극 흉 판정과 같은 물음이 아니다
    assert r['결과'] == '무대응' and r['근거_구절_id'] == []


def test_same_category_passage_makes_sangchung():
    ev = EV(명궁=[P('a', '선다', '길')], 신궁=[], 관록=[])
    r = run([J('T', '흉', ['형극'])], ev, texts={'a': '諧'})[0]
    assert r['결과'] == '상충' and r['근거_구절_id'] == ['a']


def test_two_categories_make_two_rows():
    ev = EV(명궁=[P('a', '선다', '길')], 신궁=[], 관록=[], 재백=[], 전택=[])
    rs = run([J('T', '길', ['귀천', '형극'])], ev, texts={'a': '貴'})
    assert [(r['영역'], r['결과']) for r in rs] == [('귀천', '합치'), ('형극', '무대응')]


def test_no_category_is_one_mudaeung_row():
    ev = EV(명궁=[P('a', '선다', '길')], 신궁=[], 관록=[])
    rs = run([J('T', '흉', [])], ev, texts={'a': '貴'})
    assert len(rs) == 1 and rs[0]['결과'] == '무대응' and rs[0]['견준_궁'] == []


def test_nabeum_year_root_rows(target):
    _, rows = target
    by = {r['판정_id']: r for r in rows}
    assert by['SJ27']['방향'] == '길' and by['SJ28']['방향'] == '흉'
    assert by['SJ27']['결과'] == by['SJ28']['결과'] == '무대응'


def test_trait_without_judgment_pole_is_mudaeung():
    ev = [('貴', '귀천', '貴', 'a', '명궁')]
    assert align.judge_trait('귀천', [('某', None)], ev, LEX)[0] == '무대응'
