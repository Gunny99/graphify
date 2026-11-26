"""자붕이 구속 단언 회귀시험(운: 대운·대한·세운, L0 운 기간표와 L3). 원본: A_자붕이_판정목록.md 요약표.
명세 판 0.4 4절의 틀(대한명궁, 대한 삼방사정 네 궁, 본명 삼방사정), 중첩(R22), 두 판독 틀과 갈림을 따른다.

대상 명반은 test_regression.py와 같다(시계 10:10, 경도 126.7). 궁·별 이름은 기대값에만 나온다.
"""
import datetime as dt

import pytest

from engine_v2 import compute, luck

from engine_v2.tests.target import DATE, TIME, MALE, KW


@pytest.fixture(scope='module')
def R():
    return compute(DATE, TIME, MALE, 0, **KW)


def dw(R, stem):
    return next(p for p in R['l3']['path_daewoon'] if p['stem'] == stem)


def dh(R, palace):
    return next(p for p in R['l3']['path_daehan'] if p['palace'] == palace)


def year_row(R, palace, y):
    return next(r for r in dh(R, palace)['years'] if r['year'] == y)


def counts(p, z, h):
    return len(p['palace_counts'].get(z, {}).get(h, []))


def ov(p, hua):
    return {o['unit']: o['sources'] for o in p['overlaps'] if o['hua'] == hua}


def stems(years):
    return [luck.seun(y)['stem'] for y in years]


# ── 기간표 ──────────────────────────────────────────────
def test_daewoon_table(R):
    """명세 O1, 감사 C 4절: 小暑 1999-07-07 22:24 KST에서 출생까지 27.49일, 9.16년, 역행.
    庚午 2008-10-02, 己巳 2018-10, 戊辰 2028-10."""
    d = R['daewoon']
    assert d['direction'] == '역행' and d['jie']['name'] == '小暑'
    assert abs(d['days'] - 27.49) < 0.02 and abs(d['years'] - 9.16) < 0.01
    assert d['periods'][0]['start'].date() == dt.date(2008, 10, 2)
    got = [(p['gz'], p['start'].year, p['start'].month) for p in d['periods'][:3]]
    assert got == [('庚午', 2008, 10), ('己巳', 2018, 10), ('戊辰', 2028, 10)]


def test_B44(R):
    """B-44: 26~35 대한명궁 = 子(부처궁)."""
    p = next(p for p in R['daehan'] if p['age_from'] == 26)
    assert (p['palace'], p['age_to'], p['natal_role']) == ('子', 35, '부처')


def test_B52_T13(R):
    """B-52, T13: 만나이 기산이면 丑 대한(만 16~25)이 2025년 8월 생일 전까지 이어지고, 子 대한은 2025년 8월에 시작한다."""
    p = next(p for p in R['daehan'] if p['palace'] == '丑')
    assert (p['age_from'], p['age_to'], p['end']) == (16, 25, dt.date(2025, 8, 4))
    assert next(p for p in R['daehan'] if p['palace'] == '子')['start'] == dt.date(2025, 8, 4)


# ── 경로 2: 대운 ────────────────────────────────────────
def test_B01_B21_B54(R):
    """B-01, B-21, B-54: 己 생년 × 己 대운: 화록 子 2·화권 寅 2·화과 巳 2·화기 酉 2(R22 중첩)."""
    p = dw(R, '己')
    assert (counts(p, '子', '록'), counts(p, '寅', '권'), counts(p, '巳', '과'), counts(p, '酉', '기')) == (2, 2, 2, 2)
    for h, z in (('록', '子'), ('권', '寅'), ('과', '巳'), ('기', '酉')):
        assert z in ov(p, h)


def test_B02_B29_B32(R):
    """B-02, B-29, B-32: 己 대운 → 戊 대운 교체 시 酉 화기 2 → 1(생년 문곡만 남음). 4절 8번 제화 사건."""
    assert counts(dw(R, '己'), '酉', '기') == 2
    assert dw(R, '戊')['palace_counts']['酉']['기'] == ['생년:문곡']
    ev = [e for e in dw(R, '戊')['events'] if e['kind'] == '대운교체_화기감소']
    assert ev and ev[0]['from_gz'] == '己巳' and (ev[0]['before']['palace_n'], ev[0]['after']['palace_n']) == (2, 1)


def test_B23(R):
    """B-23: 戊: 록 탐랑(寅)·권 태음(丑)·과 우필(巳)·기 천기(卯)."""
    ev = {m['hua']: (m['star'], m['palace']) for m in dw(R, '戊')['marks']}
    assert ev == {'록': ('탐랑', '寅'), '권': ('태음', '丑'), '과': ('우필', '巳'), '기': ('천기', '卯')}


def test_B24(R):
    """B-24: 戊 대운 천기 화기는 酉에 들지 못하고 卯에 머문다. 받는 궁 酉에 생년 화기가 있어 나눠 가짐(3절 5번)."""
    ji = dw(R, '戊')['ji']
    assert ji['palace'] == '卯' and ji['structural']['position'] == '卯'
    assert ji['structural']['나눠가짐']['receiver'] == '酉' and ji['structural']['나눠가짐']['with_'] == ['생년:문곡']
    assert not any('대운' in x for x in dw(R, '戊')['palace_counts']['酉'].get('기', []))


def test_B25(R):
    """B-25: 戊 화과(우필)는 巳에 들어 생년 화과(천량)와 같은 궁 → 巳 화과 2, 중첩(R22 새 정의)."""
    assert sorted(ov(dw(R, '戊'), '과')['巳']) == sorted(['생년:천량', '대운:우필'])


def test_B26_B36(R):
    """B-26, B-36: 戊 화권 태음 丑 → 未(주성 없음, 성립 쌍)에도 표시."""
    p = dw(R, '戊')
    assert p['palace_counts']['丑']['권'] == ['대운:태음'] and p['palace_counts']['未']['권'] == ['대운:태음(차성)']


def test_B33(R):
    """B-33: 戊 대운: 화기 卯 1(천기)·酉 1(문곡) → 卯·酉 쌍 화기 합 2, 각 1."""
    p = dw(R, '戊')
    assert (counts(p, '卯', '기'), counts(p, '酉', '기')) == (1, 1)
    c = p['ji_count_at_birth']
    assert (c['unit'], c['unit_n']) == ('卯酉', 2)


def test_B40(R):
    """B-40: 戊 대운 화기가 차단 쌍의 보내는 궁 卯에 듦 → 공망을 바깥에서 치는 사건. 해공은 조건부로만(1953)."""
    ev = [e for e in dw(R, '戊')['events'] if e['kind'] == '차단쌍_보내는궁_화기']
    assert ev and ev[0]['receiver'] == '酉' and ev[0]['haegong'].startswith('조건부')
    assert not [e for e in dw(R, '己')['events'] if e['kind'] == '차단쌍_보내는궁_화기']


def test_R18_lu(R):
    """B-35 후반·T08: 戊 대운 록(탐랑)은 본명 삼방사정에 들고, 己 대운 록(무곡 子)은 들지 않는다(R18)."""
    assert dw(R, '戊')['lu_into_natal_sanfang'] is True
    assert dw(R, '己')['lu_into_natal_sanfang'] is False


def test_T14_R13(R):
    """T14(2734~2742), R13(명세 판 0.5 9절 14번): 己 대운 안의 己년(2019)은 그 화기가 대한 삼방(丑 대한)에 들고
    생년 화기(酉 문곡)와 겹쳐 단서가 붙는다. 둘 중 하나만이면 단서가 없다."""
    y2019 = next(s for s in dw(R, '己')['same_stem_years'] if s['year'] == 2019)
    assert y2019['R13_단서'] is True and y2019['daehan'] == '丑'
    assert y2019['in_daehan_sanfang'] is True and y2019['overlaps_with'] == ['생년:문곡']
    for p in R['l3']['path_daewoon']:
        for s in p['same_stem_years']:
            assert s['R13_단서'] == (s['in_daehan_sanfang'] and bool(s['overlaps_with']))
    y2010 = next(s for s in dw(R, '庚')['same_stem_years'] if s['year'] == 2010)
    assert y2010['R13_단서'] is False and y2010['overlaps_with'] == []
    y2028 = next(s for s in dw(R, '戊')['same_stem_years'] if s['year'] == 2028)
    assert y2028['overlaps_with'] and y2028['in_daehan_sanfang'] is False and y2028['R13_단서'] is False


def test_R13_generic_not_wu_year(R):
    """감사 C 9절 8(gujo 34행 버그): 같은 천간 해는 대운 천간과 같은 해만. 戊년이라도 대운이 戊가 아니면 적지 않는다."""
    for p in R['l3']['path_daewoon']:
        for s in p['same_stem_years']:
            assert s['gz'][0] == p['stem']
    assert all(s['year'] != 2048 for s in dw(R, '丁')['same_stem_years'])


def test_order_one_only(R):
    """명세 판 0.5 9절 7번: 서열은 "대운이 세운보다 큼" 하나만. 화기 중첩의 길흉은 틀별 표지로만 둔다."""
    assert [(o['greater'], o['lesser']) for o in R['l3']['order']] == [('대운', '세운')]
    fl = R['l3']['frame_labels']
    assert fl['비춤_화기중첩'].startswith('대흉') and fl['구조_공망화기중첩'].startswith('길')
    assert all('label' not in o for p in R['l3']['path_daewoon'] for o in p['overlaps'])


# ── 경로 1: 대한 ────────────────────────────────────────
def test_B46_B47(R):
    """B-46, B-47: 子 대한: 대한관록 = 辰(지겁), 대한천이 = 午(지공), 대한재백 = 申; 삼방 안 공겁은 辰 지겁 1·午 지공 1."""
    p = dh(R, '子')
    roles = {v: k for k, v in p['static']['roles'].items()}
    assert (roles['관록'], roles['천이'], roles['재백']) == ('辰', '午', '申')
    assert sorted((n, z) for n, z, _ in p['static']['dist']['공겁']) == sorted([('지겁', '辰'), ('지공', '午')])


def test_B49_receptivity_count(R):
    """B-49, 2559~2569: 子 대한 삼방 주성 여섯 가운데 셋(천부·천상·칠살)이 사화를 하나도 못 받는다. 판정어는 없다(9절 6번)."""
    p = dh(R, '子')
    rc = p['receptivity']
    assert sorted(s for s, _ in rc['main_receives_none']) == ['천부', '천상', '칠살']
    assert (rc['main_total'], rc['none_count']) == (6, 3)
    assert '가리기_어려움' not in p and 'incomplete' not in rc


def test_B53_T05(R):
    """B-53, T05: 甲(2024)·乙(2025)년 화기(태양·태음)는 丑 대한명궁에 든다."""
    p = dh(R, '丑')
    assert set(stems(p['ji_counts']['대한명궁'])) == set('甲乙')
    for y, s in ((2024, '태양'), (2025, '태음')):
        r = year_row(R, '丑', y)
        assert r['ji']['star'] == s and '대한명궁' in r['ji']['frames']


def test_B55(R):
    """B-55: 丑 대한: 대한재백 = 酉, 대한복덕 = 卯; 2019 己 화기(문곡) → 酉."""
    assert dh(R, '丑')['static']['roles']['酉'] == '재백'
    assert next(x for x in R['daehan'] if x['palace'] == '丑')['roles']['卯'] == '복덕'
    r = year_row(R, '丑', 2019)
    assert (r['ji']['star'], r['ji']['palace']) == ('문곡', '酉')


def test_B57_T04(R):
    """B-57, T04: 丑 대한 10년 동안 세운 화기가 酉·卯 쌍에 드는 천간은 丁(거문)·戊(천기)·己(문곡) 셋.
    자리는 실제 궁(卯, 卯, 酉)이고, 셋 모두 대한 삼방으로 센다(R17, 쌍 종류 무관)."""
    p = dh(R, '丑')
    ys = p['ji_counts']['쌍']['卯酉']
    assert stems(ys) == list('丁戊己')
    assert {y: year_row(R, '丑', y)['ji']['palace'] for y in ys} == {2017: '卯', 2018: '卯', 2019: '酉'}
    assert set(ys) <= set(p['ji_counts']['대한삼방'])


def test_B58_T04(R):
    """B-58, T04: 본명 명궁·천이 주성 화기 천간 = 癸(탐랑 寅)·丙(염정 申) 둘; 쌍 셋과 합쳐 "10년중 5번"."""
    p = dh(R, '丑')
    assert sorted(stems(p['ji_counts']['본명삼방'])) == sorted('癸丙')
    assert len(p['ji_counts']['쌍']['卯酉']) + len(p['ji_counts']['본명삼방']) == 5


def test_O4_xin_is_daehan_sanfang(R):
    """명세 O4: 辛(2021)의 문창 화기 巳는 대한 삼방 사건(대한명궁·본명 삼방 아님)."""
    r = year_row(R, '丑', 2021)
    assert r['ji']['frames'] == ['대한삼방'] and r['ji']['palace'] == '巳'


def test_galim_wu_tianji(R):
    """4절 4번 갈림: 戊 천기 화기(2018, 丑 대한)는 구조 통변으로는 卯에 머물러 나눠 가짐(궁 단위 중첩 아님),
    대한 삼방 비춤으로는 卯·酉 쌍에서 생년 문곡과 쌍 중첩. 둘이 달라 갈림."""
    ji = year_row(R, '丑', 2018)['ji']
    assert ji['star'] == '천기'
    assert ji['structural']['position'] == '卯' and ji['structural']['중첩'] is False and ji['structural']['나눠가짐']
    assert ji['gaze']['unit'] == '卯酉' and ji['gaze']['중첩'] is True
    assert ji['갈림'] is True


def test_galim_2018_lu_and_pair_ji(R):
    """2018 戊년: 화록(탐랑)이 명궁(본명 삼방)에 들고 같은 해 화기가 쌍 중첩에 걸려 갈림으로 나온다."""
    r = year_row(R, '丑', 2018)
    types = [g['type'] for g in r['galim']]
    assert '화록_본명삼방과_화기중첩' in types
    lu = next(g for g in r['galim'] if g['type'] == '화록_본명삼방과_화기중첩')['lu'][0]
    assert lu['star'] == '탐랑' and lu['palaces'] == ['寅']


def test_copy_counts_once(R):
    """명세 판 0.5 9절 13번: 성립 쌍의 복사 표시는 하나로 센다. 丑 대한의 甲(2024)·乙(2015, 2025)은
    丑과 未 두 궁에 보이지만 화기 하나라 중첩이 아니다."""
    for y in (2015, 2024, 2025):
        r = year_row(R, '丑', y)
        assert next(m for m in r['marks'] if m['hua'] == '기')['copies'] == ['未']
        assert not [o for o in r['overlaps'] if o['hua'] == '기']
        assert r['ji']['gaze']['중첩'] is False and r['ji']['structural']['중첩'] is False and r['ji']['갈림'] is False


def test_galim_ji_you_overlap(R):
    """명세 판 0.5 4절 3·4번, 7절 2번: 己의 酉 화기 중첩은 구조 통변으로는 공망과 만난 중첩이라 길(1227~1231),
    대한 삼방 비춤으로는 쌍 중첩이라 대흉(3490~3492). 두 틀이 달라 갈림."""
    ji = year_row(R, '丑', 2019)['ji']
    assert ji['structural']['중첩'] is True and set(ji['structural']['kong']) == {'절공', '순공'}
    assert ji['structural']['label'].startswith('길') and ji['gaze']['label'].startswith('대흉')
    assert ji['갈림'] is True
    row = next(r for r in R['l3']['contrast'] if r['daehan'] == '丑' and r['daewoon'] == '己巳')
    assert row['compare']['대운화기_판독틀'] == '갈림' and '대운화기_판독틀' in row['compare']['갈림']
    rd = row['daewoon_frame']['ji_readings']
    assert rd['structural']['label'].startswith('길') and rd['gaze']['label'].startswith('대흉')


def test_B45_B50(R):
    """B-45, B-50: 戊년(다음 戊년 2028 戊申): 화록 寅(탐랑, 명궁) + 생년 화록 子(무곡) → 寅·子에 록 각 1."""
    assert luck.seun(2028)['gz'] == '戊申'
    pc = year_row(R, '子', 2028)['palace_counts']
    assert pc['寅']['록'] == ['세운:탐랑'] and pc['子']['록'] == ['생년:무곡']


def test_B56(R):
    """B-56: 2018 = 戊년 → 화록 탐랑 寅(명궁)."""
    r = year_row(R, '丑', 2018)
    lu = next(m for m in r['marks'] if m['hua'] == '록')
    assert r['gz'][0] == '戊' and (lu['star'], lu['palace']) == ('탐랑', '寅')


def test_yukgil_events(R):
    """4절 9번: 대한 삼방으로 새로 드는 육길성과 운 사화가 육길성에 붙는 해를 사실로 낸다(이로공명 판정 없음)."""
    p = dh(R, '丑')
    assert {n for n, _, _ in p['yukgil_new']} == {'좌보', '문곡', '우필', '문창'}
    assert any(e['kind'] == '육길성_사화' and e['star'] == '우필' for e in year_row(R, '丑', 2018)['events'])


def test_shared_includes_daewoon_ji(R):
    """명세 판 1.0 4절 세부 재결(추론): 받는 궁의 나눠 가짐을 볼 때 그때의 대운 화기도 이미 있는 화기로 넣는다.
    子 대한 2027 丁(거문 卯)은 己巳 대운 안이라 酉의 생년 문곡과 대운 문곡을 함께 적는다. 중첩 셈에는 넣지 않는다."""
    ji = year_row(R, '子', 2027)['ji']
    sh = ji['structural']['나눠가짐']
    assert sh['with_'] == ['생년:문곡', '대운:문곡'] and '추론' in sh['note']
    assert ji['structural']['sources'] == ['세운:거문']


def test_2018_galim_marked_inference(R):
    """명세 판 1.0 4절 세부 재결: 2018년의 "화록의 본명 삼방 진입과 화기 중첩" 갈림은 사례 한 건의 추론으로 표시."""
    g = next(g for g in year_row(R, '丑', 2018)['galim'] if g['type'] == '화록_본명삼방과_화기중첩')
    assert '사례 한 건의 추론' in g['표시']


def test_contrast_shape(R):
    """4절 10번: 구간마다 두 경로를 나란히 두고 일치·불일치. "확정"이라는 말은 쓰지 않는다.
    丑 대한 × 己巳 대운: 화기 중첩 자리가 두 경로 모두 酉와 卯·酉 쌍이라 일치."""
    rows = R['l3']['contrast']
    assert '확정' not in repr(rows)
    assert all('화록삼방진입' not in (r['compare'] or {}) and 'lu_years' not in r['daehan_frame'] for r in rows)   # 판 1.0: 화록 항목 뺌
    r = next(r for r in rows if r['daehan'] == '丑' and r['daewoon'] == '己巳')
    assert r['compare']['화기중첩자리'] == '일치' and r['daehan_frame']['ji_overlap_units'] == ['酉', '卯酉']


# ── 노출도(명세 8절 1번) 검산값 ───────────────────────────────
def test_exposure_natal_sanfang_checkvalues(R):
    """명세 8절 1번: 본명 삼방사정 화기 2/10(丙 염정, 癸 탐랑), 화록 3/10(甲 염정, 戊 탐랑, 癸 파군)."""
    n = R['l3']['exposure']['natal']['본명삼방']
    pick = lambda h: [(c['stem'], c['star']) for c in n[h]['list']]
    assert (n['기']['k'], pick('기')) == (2, [('丙', '염정'), ('癸', '탐랑')])
    assert (n['록']['k'], pick('록')) == (3, [('甲', '염정'), ('戊', '탐랑'), ('癸', '파군')])
    for d in R['l3']['exposure']['daehan']:
        assert d['frames']['본명삼방'] == n


def test_exposure_daehan_ji(R):
    """회귀 고정값(코드 출력, 독립 검산 아님): 대한 삼방 기준 화기 노출도 子 대한 2, 亥 6, 戌 1."""
    d = {x['palace']: x['frames']['대한삼방']['기']['k'] for x in R['l3']['exposure']['daehan']}
    assert (d['子'], d['亥'], d['戌']) == (2, 6, 1)


def test_exposure_ji_overlap_checkvalues(R):
    """명세 8절 4번(주 루프 재결): 丑 대한 대한삼방 화기 6/10 가운데 중첩 3/10(丁 거문, 戊 천기, 己 문곡), 子 대한 중첩 0/10."""
    d = {x['palace']: x['frames']['대한삼방']['기'] for x in R['l3']['exposure']['daehan']}
    assert d['丑']['k'] == 6 and d['丑']['overlap_k'] == 3
    assert [(c['stem'], c['star']) for c in d['丑']['overlap_list']] == [('丁', '거문'), ('戊', '천기'), ('己', '문곡')]
    assert d['子']['overlap_k'] == 0 and d['子']['overlap_list'] == []
