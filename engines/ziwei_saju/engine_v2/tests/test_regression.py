"""자붕이 구속 단언 회귀시험(L0·L1). 원본: 원점재검토_20261111/A_자붕이_판정목록.md 요약표 B-01~B-63.

대상 명반: 양력 1999-08-04, 남, 시계 10:10(KST), 인천 경도 126.7, 자오선 135 → 진태양시 09:30(명세 판 0.4 9절 12번, guard.py BIRTH는 옛 입력 10:14·-38분).
궁과 별 이름은 여기 기대값에만 나온다. 운(대운·세운)이 필요한 단언은 test_regression_luck.py에 있다.
"""
import pytest

from engine_v2 import compute, luck
from engine_v2.chart import main_stars, names, star
from engine_v2.common import sanfang
from engine_v2.structure import landing, receptivity

from engine_v2.tests.target import DATE, TIME, MALE, KW


@pytest.fixture(scope='module')
def R():
    return compute(DATE, TIME, MALE, 0, **KW, with_l3=False)


@pytest.fixture(scope='module')
def C(R):
    return R['chart']


@pytest.fixture(scope='module')
def L1(R):
    return R['l1']


def grade(C, name):
    return star(C, name)[1]['grade']


def lands(R, stem, hua):
    s = R['sihua'].of(stem)[hua]
    return landing(R['chart'], R['l1']['borrow'], s)


def blocked(L1, sender, receiver):
    return [b for b in L1['borrow_blocked'] if b['sender'] == sender and b['receiver'] == receiver]


def established(L1, sender, receiver):
    return [b for b in L1['borrow_established'] if b['sender'] == sender and b['receiver'] == receiver]


# ── 외부 도구 대조(ref_외부도구_명반.md) ─────────────────────────
def test_ref_mingshi(C):
    """ref: 음력 己卯年 六月廿三, 사주 己卯 辛未 戊子 丁巳, 火六局, 명궁 丙寅, 신궁 子, 命主 녹존, 身主 천동."""
    b = C['birth']
    assert (b['lunar']['month'], b['lunar']['day'], b['lunar']['leap']) == (6, 23, False)
    assert b['saju'] == dict(year='己卯', month='辛未', day='戊子', hour='丁巳')
    assert (C['ming'], C['palaces']['寅']['stem'], C['ju_name'], C['shen']) == ('寅', '丙', '火六局', '子')
    assert (C['mingzhu'], C['shenzhu']) == ('녹존', '천동')


def test_ref_main_stars(C):
    """ref 12궁 주성 배치."""
    want = {'寅': ['탐랑'], '卯': ['천기', '거문'], '辰': ['자미', '천상'], '巳': ['천량'], '午': ['칠살'], '未': [],
            '申': ['염정'], '酉': [], '戌': ['파군'], '亥': ['천동'], '子': ['무곡', '천부'], '丑': ['태양', '태음']}
    for z, w in want.items():
        assert sorted(main_stars(C, z)) == sorted(w), z


def test_ref_aux_and_minor(C):
    """ref 보좌·살·잡성 자리(도구가 적은 것 가운데 엔진이 앉히는 별)."""
    want = {'寅': '화성 천형 은광 천복', '卯': '영성 천수 천월(月) 천곡', '辰': '지겁 천공 음살',
            '巳': '우필 문창 천마 타라 천재 고진 비렴 파쇄', '午': '녹존 지공 천희 천요 천귀',
            '未': '경양 삼태 팔좌 용지 봉각 봉고 화개 천상(傷) 년해', '申': '천월 천무 천주 월덕',
            '酉': '좌보 문곡 천관 순공 천허 천사 절공', '亥': '태보', '子': '천괴 홍란 함지 해신 천덕', '丑': '과숙'}
    for z, w in want.items():
        assert set(w.split()) <= set(names(C, z)), (z, set(w.split()) - set(names(C, z)))


def test_ref_birth_hua(C):
    """ref 생년 사화: 무곡록 子, 탐랑권 寅, 천량과 巳, 문곡기 酉."""
    bh = C['birth_hua']
    assert [(bh[h]['star'], bh[h]['palace']) for h in '록권과기'] == [('무곡', '子'), ('탐랑', '寅'), ('천량', '巳'), ('문곡', '酉')]


# ── B 단언 ────────────────────────────────────────────────
def test_B01_static(C, L1):
    """B-01(정적 부분): 酉는 주성 없는 궁이며 절공·순공 둘이 있다. 생년 문곡 화기가 酉에 든다. 대운 부분은 luck 시험."""
    assert '酉' in L1['empty']
    assert {'절공', '순공'} <= set(names(C, '酉'))
    assert C['birth_hua']['기'] == dict(star='문곡', palace='酉')


def test_B03(R, C):
    """B-03: 午에 지공 廟; 戊 화록(탐랑)은 寅 명궁에 든다."""
    assert star(C, '지공')[0] == '午' and grade(C, '지공') == '廟'
    l = lands(R, '戊', '록')
    assert l['palace'] == '寅' and C['palaces']['寅']['role'] == '명'


def test_B04(C, L1):
    """B-04: 酉 절공 → 卯(천기·거문)→酉 차성 불성립; 酉 문곡 화기는 순공에 갇힘(제화 지점)."""
    assert sorted(main_stars(C, '卯')) == ['거문', '천기']
    b = blocked(L1, '卯', '酉')
    assert b and set(b[0]['kong']) == {'절공', '순공'} and b[0]['confirmed'] is True
    assert L1['jehwa'] and L1['jehwa'][0]['palace'] == '酉' and L1['jehwa'][0]['star'] == '문곡'
    assert '순공' in L1['jehwa'][0]['kong']


def test_B05(C):
    """B-05: 身宮 = 子(부처궁)."""
    assert C['shen'] == '子' and C['shen_role'] == '부처'


def test_B06(C):
    """B-06: 천괴 子·천월 申."""
    assert star(C, '천괴')[0] == '子' and star(C, '천월')[0] == '申'


def test_B07_B61(C):
    """B-07, B-61: 戌 파군 旺."""
    assert star(C, '파군')[0] == '戌' and grade(C, '파군') == '旺'


def test_B08(C):
    """B-08: 寅 천형 廟(흉 판정 대상 아님은 L2)."""
    assert star(C, '천형')[0] == '寅' and grade(C, '천형') == '廟'


def test_B09(C):
    """B-09: 辰: 자미 得·천상 得·지겁 陷 동궁."""
    for n, g in (('자미', '得'), ('천상', '得'), ('지겁', '陷')):
        assert star(C, n)[0] == '辰' and grade(C, n) == g


def test_B10(C):
    """B-10: 辰 지겁 陷 ↔ 戌 파군 旺 대궁."""
    from engine_v2.common import opp
    assert opp(star(C, '지겁')[0]) == star(C, '파군')[0]
    assert grade(C, '지겁') == '陷' and grade(C, '파군') == '旺'


def test_B11(C):
    """B-11: 생년 화록(무곡)은 子 부처에 있다."""
    assert C['birth_hua']['록'] == dict(star='무곡', palace='子') and C['palaces']['子']['role'] == '부처'


def test_B12(C, L1):
    """B-12: 未: 경양 廟·삼태·팔좌, 주성 없음."""
    assert '未' in L1['empty']
    assert {'경양', '삼태', '팔좌'} <= set(names(C, '未')) and grade(C, '경양') == '廟'


def test_B13(C):
    """B-13: 巳: 천량 陷 화과·타라 陷·천마."""
    s = star(C, '천량')
    assert s[0] == '巳' and s[1]['grade'] == '陷' and s[1]['hua'] == '과'
    assert star(C, '타라')[0] == '巳' and grade(C, '타라') == '陷'
    assert star(C, '천마')[0] == '巳'


def test_B14_B26(R, L1):
    """B-14, B-26: 戊 화권(태음)은 丑에 들고 대궁 未는 주성이 없다."""
    assert lands(R, '戊', '권')['palace'] == '丑'
    assert '未' in L1['empty']


def test_B15(C):
    """B-15: 十二長生: 寅 장생, 戌 제왕. L0 출력에 따로 실린다(명세 판 0.5 9절 15번)."""
    assert C['palaces']['寅']['changsheng'] == '장생' and C['palaces']['戌']['changsheng'] == '제왕'
    cs = C['changsheng']
    assert cs['start'] == '寅' and cs['by_palace']['戌'] == '제왕'
    from engine_v2.__main__ import brief
    from engine_v2 import compute as _c
    assert brief(_c(DATE, TIME, MALE, 0, **KW))['L0']['changsheng']['by_palace']['寅'] == '장생'


def test_B16(C):
    """B-16: 寅 탐랑에 생년 화권."""
    s = star(C, '탐랑')
    assert s[0] == '寅' and s[1]['hua'] == '권'


def test_B17(C):
    """B-17: 생년 화록 子; 午 녹존·지공 동궁."""
    assert C['birth_hua']['록']['palace'] == '子'
    assert {'녹존', '지공'} <= set(names(C, '午'))


def test_B18(C):
    """B-18: 午: 칠살 旺·녹존·지공 廟·천요."""
    assert {'칠살', '녹존', '지공', '천요'} <= set(names(C, '午'))
    assert grade(C, '칠살') == '旺' and grade(C, '지공') == '廟'


def test_B19(C):
    """B-19: 寅: 화성 廟·천형 廟 동궁."""
    assert {'화성', '천형'} <= set(names(C, '寅'))
    assert grade(C, '화성') == '廟' and grade(C, '천형') == '廟'


def test_B20(R, C):
    """B-20: 戊 화기(천기)는 卯에 들고, 대궁 酉에 절공·순공."""
    l = lands(R, '戊', '기')
    assert l['palace'] == '卯' and l['copies'] == [] and l['blocked_pair'] == '卯酉'
    assert {'절공', '순공'} <= set(names(C, '酉'))


def test_B22(C):
    """B-22: 巳는 辰(지겁)·午(지공) 사이에 끼인다; 생년 화과는 巳 천량 陷."""
    assert star(C, '지겁')[0] == '辰' and star(C, '지공')[0] == '午'
    assert C['birth_hua']['과'] == dict(star='천량', palace='巳') and grade(C, '천량') == '陷'


def test_B27_B31(C):
    """B-27, B-31: 卯 천곡·酉 천허 대궁; 酉 절공+순공."""
    assert star(C, '천곡')[0] == '卯' and star(C, '천허')[0] == '酉'
    assert C['kong']['정_절공'] == '酉' and C['kong']['정_순공'] == '酉'


def test_B28(L1):
    """B-28: 卯→酉 차성 불성립 → 卯·酉 형극."""
    b = blocked(L1, '卯', '酉')
    assert b and b[0]['relation'] == '형극' and b[0]['receiver_has_birth_ji'] is True


def test_B30(C):
    """B-30: 卯 천기 旺."""
    assert star(C, '천기')[0] == '卯' and grade(C, '천기') == '旺'


def test_B34_B41(C, L1):
    """B-34, B-41: 丑 태음 廟(태양과 함께) → 未(주성 없음) 차성 성립."""
    assert grade(C, '태음') == '廟' and star(C, '태음')[0] == '丑'
    e = established(L1, '丑', '未')
    assert e and sorted(s['name'] for s in e[0]['stars']) == ['태양', '태음']
    assert e[0]['relation'] == dict(채무='丑', 채주='未')


def test_B35(L1):
    """B-35: 생년 화록 子는 寅 삼방사정(寅·午·戌·申) 밖, 戊 화록 寅은 안."""
    lu = L1['lu']
    assert set(lu['natal_sanfang']) == set('寅午戌申')
    assert lu['birth_lu']['palace'] == '子' and lu['birth_lu']['in_natal_sanfang'] is False
    assert any(x['stem'] == '戊' and x['palaces'] == ['寅'] for x in lu['stems_lu_into_sanfang'])


def test_B37(R):
    """B-37: 戊 화록 탐랑 → 寅."""
    assert R['sihua'].of('戊')['록'] == '탐랑' and lands(R, '戊', '록')['palace'] == '寅'


def test_B38(C):
    """B-38: 酉 절공·순공 2."""
    assert [s['name'] for s in C['palaces']['酉']['stars'] if s['name'] in ('절공', '순공')] == ['절공', '순공']


def test_B39(C):
    """B-39: 戌 파군 旺; 寅 천형 廟."""
    assert grade(C, '파군') == '旺' and grade(C, '천형') == '廟'


def test_B42(C):
    """B-42: 卯·酉는 寅 삼방사정(寅·午·戌·申) 밖."""
    assert not ({'卯', '酉'} & set(sanfang(C['ming'])))


def test_B43(C):
    """B-43: 寅 탐랑 = 平; 천형 = 廟."""
    assert grade(C, '탐랑') == '平' and grade(C, '천형') == '廟'


def test_B48(C):
    """B-48: 午 지공 = 廟."""
    assert star(C, '지공')[0] == '午' and grade(C, '지공') == '廟'


def test_B49(R):
    """B-49: 子 대한 삼방사정 주성 6개 사화 수용: 록 = 무곡·염정 / 권 = 자미·무곡 / 과 = 자미·무곡 / 기 = 무곡·염정;
    천부·천상·칠살 = 0. 子 대한은 L0 대한표에서 찾는다."""
    dh = [p for p in luck.daehan(R['chart']) if p['age_from'] <= 26 <= p['age_to']][0]
    assert dh['palace'] == '子'
    rc = receptivity(R['chart'], R['sihua'], R['l1']['borrow'], sanfang(dh['palace']))
    assert {h: sorted(v) for h, v in rc['by_hua'].items()} == {
        '록': ['무곡', '염정'], '권': ['무곡', '자미'], '과': ['무곡', '자미'], '기': ['무곡', '염정']}
    assert sorted(s for s, _ in rc['main_receives_none']) == ['천부', '천상', '칠살']
    assert (rc['main_total'], rc['none_count']) == (6, 3)        # 판정어 없이 수만(명세 판 0.5 9절 6번)
    assert 'incomplete' not in rc


def test_B49_variant_breaks():
    """B-49 대조: 壬 화과를 천부로 두는 표(남양당본·왕정지)에서는 천부 수용이 0이 아니게 된다(명세 6절)."""
    r = compute(DATE, TIME, MALE, 0, **KW, sihua_variant='nanyang', with_l3=False)
    rc = receptivity(r['chart'], r['sihua'], r['l1']['borrow'], sanfang('子'))
    assert '천부' not in [s for s, _ in rc['main_receives_none']]


def test_B51(C):
    """B-51: 辰 천상 得 + 지겁 陷 동궁; 子 천부 廟."""
    assert {'천상', '지겁'} <= set(names(C, '辰')) and grade(C, '천상') == '得' and grade(C, '지겁') == '陷'
    assert star(C, '천부')[0] == '子' and grade(C, '천부') == '廟'


def test_B59(R, C):
    """B-59: 寅 탐랑 平; 탐랑이 받는 사화 = 록(戊)·권(己)·기(癸)."""
    assert grade(C, '탐랑') == '平'
    assert R['sihua'].received('탐랑') == {'록': ['戊'], '권': ['己'], '기': ['癸']}


def test_B60(C):
    """B-60: 己卯생 → 고서 "무년·기년에 난 사람이면 격에 맞는다"의 생년 조건 충족.
    L0이 내는 것은 생년 천간까지다. 고서 격 조건과의 대조는 L2(원전 구절) 범위다."""
    assert C['year_gz'] == '己卯' and C['year_stem'] in '戊己'


def test_B62(L1):
    """B-62: 寅 삼방사정(寅·午·戌·申) 안 살성 = 화성(寅)·지공(午)."""
    ns = L1['natal_sanfang']
    assert sorted((n, z) for n, z, _ in ns['살성']) == sorted([('화성', '寅'), ('지공', '午')])
    assert {(n, g) for n, _, g in ns['살성']} == {('화성', '廟'), ('지공', '廟')}


def test_B63(C):
    """B-63: 寅: 탐랑 平·화성 廟·천형 廟."""
    assert {'탐랑', '화성', '천형'} <= set(names(C, '寅'))
    assert (grade(C, '탐랑'), grade(C, '화성'), grade(C, '천형')) == ('平', '廟', '廟')


# ── 명세 3절 검산값(T01, T02, T11, T12) ─────────────────────
def test_spec3_check(L1):
    """명세 판 0.4 3절 검산값: 공궁 未·酉; 丑·未 성립 쌍, 卯·酉 차단 쌍(酉에 절공과 순공이 함께); 제화 지점 酉;
    평 寅 탐랑, 함 巳 천량(자붕이 값)·丑 태양(전서 성론 값); 천량 화과의 작동은 미정;
    본명 삼방사정에 화성 廟·지공 廟·천형 廟·녹존·천월; 생년 록 子 삼방 밖, 戊·甲·癸에서 록이 삼방에 듦."""
    assert L1['empty'] == ['未', '酉']
    assert established(L1, '丑', '未') and blocked(L1, '卯', '酉')
    assert [j['palace'] for j in L1['jehwa']] == ['酉']
    g = L1['brightness']['groups']
    assert g['평'] == ['탐랑'] and sorted(g['함']) == ['천량', '태양']
    assert star_layer(L1, '천량') == '자붕이' and star_layer(L1, '태양') == '전서권3성론'
    hw = L1['brightness']['hua_on_weak']
    assert [(x['star'], x['hua']) for x in hw] == [('천량', '과')] and hw[0]['status'].startswith('작동 여부 미정')
    ns = L1['natal_sanfang']
    have = {(n, g) for k in ('육길성', '살성', '녹존', '천형') for n, _, g in ns[k]}
    assert {('화성', '廟'), ('지공', '廟'), ('천형', '廟'), ('녹존', None), ('천월', None)} == have
    assert L1['borrow']['酉']['confirmed'] is True
    assert sorted(x['stem'] for x in L1['lu']['stems_lu_into_sanfang']) == sorted('戊甲癸')


def star_layer(L1, name):
    return L1['brightness']['star'][name]['layer']


def test_T11_gyeok(L1):
    """T11(3895·3925): 기본격 살파랑 성립(명세 판 0.4 3절 10번: 성립 여부만), 명궁에 탐랑과 화성 동궁."""
    gy = L1['gyeok']
    assert gy['basic'] == {'살파랑': True}
    assert {'탐랑', '화성'} <= set(gy['ming_stars'])


def test_receptivity_palace_unit(R):
    """명세 6절 끝 문단(3485): "거문천기는 권록과기를 다 받는다"는 卯 한 궁의 합으로 재현된다."""
    pr = R['l1']['receptivity']['by_palace']['卯']
    assert pr['hua_kinds'] == ['록', '권', '과', '기']


def test_brightness_classes(C, L1):
    """명세 판 0.4 3절 7번: 得은 묘왕 쪽(2621), 출처 없는 칸은 None(미확인)."""
    assert L1['brightness']['star']['자미']['cls'] == '묘왕'
    assert grade(C, '좌보') is None and grade(C, '천괴') is None


def test_brightness_second_layer(C, L1):
    """명세 판 1.0 3절 검산값, 밝기의 둘째 층(전서 권3 별별 해설 395, 517, 626, 486, 442행):
    무곡 子 旺, 거문 卯 入廟, 염정 申 入廟, 천동 亥 入廟. 천부 子는 자붕이 값 廟를 두고 517행(旺)을 함께 적는다."""
    for n, g in (('무곡', '旺'), ('거문', '廟'), ('염정', '廟'), ('천동', '廟')):
        assert grade(C, n) == g and L1['brightness']['star'][n]['layer'] == '전서권3성론'
    from engine_v2.tables import Brightness
    c = Brightness().cells[('천부', '子')]
    assert c['grade'] == '廟' and c['layer'] == '자붕이' and '517행' in c['source_also']
    assert {z: L1['brightness']['palace'][z] for z in '子卯申亥'} == dict.fromkeys('子卯申亥', '묘왕')


def test_B22_jia(L1):
    """B-22, 명세 판 1.0 3절 13번: 巳는 辰(지겁)·午(지공) 사이에 끼인다 → 巳가 공겁의 협."""
    j = [x for x in L1['jia'] if x['palace'] == '巳']
    assert j and j[0]['pair'] == ('지공', '지겁') and j[0]['sides'] == {'지공': '午', '지겁': '辰'}


def test_T12(C):
    """T12: 관록의 지공은 廟이고 재백의 파군은 旺이다."""
    assert C['palaces'][star(C, '지공')[0]]['role'] == '관록' and grade(C, '지공') == '廟'
    assert C['palaces'][star(C, '파군')[0]]['role'] == '재백' and grade(C, '파군') == '旺'


def test_inflection(L1):
    """R9 변곡점: 함지 주성 궁, 공궁, 화기와 공망, 평지 궁이 명세 3절 값과 맞는다."""
    inf = L1['inflection']
    assert sorted(inf['함지주성궁']) == sorted(['丑', '巳']) and inf['평지궁'] == ['寅']
    assert inf['공궁'] == ['未', '酉'] and inf['화기공망'] == ['酉']
