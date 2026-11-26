"""L0 안성: 명궁·신궁·오행국, 14주성, 보좌·살·잡성, 밝기, 생년 사화, 공망, 十二長生.

자리 계산은 byeonseong/anxing.chart_any와 zaxing.place에서 옮겼다(전서 卷3 安星諸訣, 왕정지 初級講義 安星法).
고친 것: 천재·천수의 卯년 고정(+3) → 생년 지지 수, 밝기 ADOPT·REC 덮어쓰기와 빈칸 平 기본값 제거,
양력·윤달·성별 입력, 命主·身主·蜚廉·十二長生 추가.
"""
from .calendar import TIGER, resolve
from .common import BR, CHANGSHENG, GONGGEOP, HUA, MAIN14, SAL, STEM, YUKGIL, bi, bz, roles_from, yang_stem
from .tables import Brightness, Sihua

NAYIN = '金金火火木木土土金金火火水水土土金金木木水水土土火火木木水水金金火火木木土土金金火火水水土土金金木木水水土土火火木木水水'
JU = {'水': 2, '木': 3, '金': 4, '土': 5, '火': 6}
JU_NAME = {2: '水二局', 3: '木三局', 4: '金四局', 5: '土五局', 6: '火六局'}
LU = dict(zip(STEM, '寅卯巳午巳午申酉亥子'))                                    # 安祿存
KUI = {'甲': '丑未', '戊': '丑未', '庚': '丑未', '乙': '子申', '己': '子申', '丙': '亥酉', '丁': '亥酉',
       '辛': '午寅', '壬': '卯巳', '癸': '卯巳'}                                   # 天魁·天鉞
MA = {'寅': '申', '午': '申', '戌': '申', '申': '寅', '子': '寅', '辰': '寅', '巳': '亥', '酉': '亥', '丑': '亥',
      '亥': '巳', '卯': '巳', '未': '巳'}
HL = {'寅': '丑卯', '午': '丑卯', '戌': '丑卯', '申': '寅戌', '子': '寅戌', '辰': '寅戌', '巳': '卯戌', '酉': '卯戌',
      '丑': '卯戌', '亥': '酉戌', '卯': '酉戌', '未': '酉戌'}                     # 화성·영성 起宮
SAN = {'寅': '寅午戌', '午': '寅午戌', '戌': '寅午戌', '申': '申子辰', '子': '申子辰', '辰': '申子辰',
       '巳': '巳酉丑', '酉': '巳酉丑', '丑': '巳酉丑', '亥': '亥卯未', '卯': '亥卯未', '未': '亥卯未'}
SEA = {'亥': 0, '子': 0, '丑': 0, '寅': 1, '卯': 1, '辰': 1, '巳': 2, '午': 2, '未': 2, '申': 3, '酉': 3, '戌': 3}
JIEKONG = {'甲': '申酉', '己': '申酉', '乙': '午未', '庚': '午未', '丙': '辰巳', '辛': '辰巳', '丁': '寅卯',
           '壬': '寅卯', '戊': '子丑', '癸': '子丑'}
MINGZHU = {'子': '탐랑', '丑': '거문', '亥': '거문', '寅': '녹존', '戌': '녹존', '卯': '문곡', '酉': '문곡',
           '辰': '염정', '申': '염정', '巳': '무곡', '未': '무곡', '午': '파군'}
SHENZHU = {'子': '화성', '午': '화성', '丑': '천상', '未': '천상', '寅': '천량', '申': '천량', '卯': '천동',
           '酉': '천동', '巳': '천기', '亥': '천기', '辰': '문창', '戌': '문창'}
FEILIAN = dict(zip(BR, '申酉戌巳午未寅卯辰亥子丑'))                               # 蜚廉(年支). 출처 미확인, 외부 도구와 대조만
CS_START = {2: '申', 3: '亥', 4: '巳', 5: '申', 6: '寅'}                          # 十二長生 起宮(오행국)
BOJWA = ('녹존', '천마')


def kind_of(name):
    if name in MAIN14:
        return '주성'
    if name in YUKGIL or name in BOJWA:
        return '보좌'
    if name in SAL:
        return '살'
    return '잡성'


def kong(ys, yb):
    """공망. 순공(旬空) 두 자리, 절공(截空) 두 자리. 생년 음양에 맞는 자리를 정(正), 나머지를 방(傍)으로 둔다."""
    k = next(i for i in range(60) if STEM[i % 10] == ys and BR[i % 12] == yb)
    x0 = k - k % 10
    xun = [BR[(x0 + 10) % 12], BR[(x0 + 11) % 12]]
    jie = list(JIEKONG[ys])
    yang = yang_stem(ys)

    def pick(pair):
        return [z for z in pair if (bi(z) % 2 == 0) == yang][0]

    zj, zx = pick(jie), pick(xun)
    zheng = sorted({zj, zx}, key=bi)
    pang = sorted((set(xun) | set(jie)) - set(zheng), key=bi)
    return dict(순공=xun, 절공=jie, 정_절공=zj, 정_순공=zx, 정공=zheng, 방공=pang)


def place_stars(ys, yb, m, d, h, male):
    """별 자리 {이름: 지지}. m 음력 월(명반용), d 음력 일, h 시지 번호."""
    ming = (bi('寅') + m - 1 - h) % 12
    shen = (bi('寅') + m - 1 + h) % 12
    stems = {bz(bi('寅') + k): STEM[(STEM.index(TIGER[ys]) + k) % 10] for k in range(12)}
    k60 = next(i for i in range(60) if STEM[i % 10] == stems[bz(ming)] and BR[i % 12] == bz(ming))
    n = JU[NAYIN[k60]]
    x = 0
    while (d + x) % n:
        x += 1
    q = (d + x) // n
    zw = (bi('寅') + q - 1 + (-x if x % 2 else x)) % 12
    tf = (4 - zw) % 12
    y = bi(yb)
    si = STEM.index(ys)
    pos = {'자미': zw, '천기': zw - 1, '태양': zw - 3, '무곡': zw - 4, '천동': zw - 5, '염정': zw - 8,
           '천부': tf, '태음': tf + 1, '탐랑': tf + 2, '거문': tf + 3, '천상': tf + 4, '천량': tf + 5, '칠살': tf + 6, '파군': tf + 10,
           '좌보': bi('辰') + m - 1, '우필': bi('戌') - (m - 1), '문창': bi('戌') - h, '문곡': bi('辰') + h,
           '천괴': bi(KUI[ys][0]), '천월': bi(KUI[ys][1]), '녹존': bi(LU[ys]), '경양': bi(LU[ys]) + 1, '타라': bi(LU[ys]) - 1,
           '천마': bi(MA[yb]), '화성': bi(HL[yb][0]) + h, '영성': bi(HL[yb][1]) + h, '지겁': bi('亥') + h, '지공': bi('亥') - h,
           '천형': bi('酉') + m - 1, '천요': bi('丑') + m - 1,
           '삼태': bi('辰') + m - 1 + d - 1, '팔좌': bi('戌') - (m - 1) - (d - 1)}
    pos.update({'홍란': bi('卯') - y, '천희': bi('酉') - y,
                '함지': bi({'寅午戌': '卯', '申子辰': '酉', '巳酉丑': '午', '亥卯未': '子'}[SAN[yb]]),
                '천덕': bi('酉') + y, '용덕': bi('未') + y, '월덕': bi('巳') + y, '년해': bi('戌') - y,
                '대모': y + 6 + (1 if y % 2 == 0 else -1),
                '겁살': bi({'寅午戌': '亥', '申子辰': '巳', '巳酉丑': '寅', '亥卯未': '申'}[SAN[yb]]),
                '화개': bi({'寅午戌': '戌', '申子辰': '辰', '巳酉丑': '丑', '亥卯未': '未'}[SAN[yb]]),
                '고진': bi('寅巳申亥'[SEA[yb]]), '과숙': bi('戌丑辰未'[SEA[yb]]),
                '파쇄': bi('巳酉丑'['子午卯酉寅申巳亥辰戌丑未'.index(yb) // 4]),
                '용지': bi('辰') + y, '봉각': bi('戌') - y, '천곡': bi('午') - y, '천허': bi('午') + y, '천공': y + 1,
                '천관': bi('未辰巳寅卯酉亥酉戌午'[si]), '천복': bi('酉申子亥卯寅午巳午巳'[si]),
                '천주': bi('巳午子巳午申寅午酉戌'[si]), '홍염': bi('午申寅未辰辰戌酉子申'[si]),
                '비렴': bi(FEILIAN[yb]),
                '천무': bi('巳申寅亥'[(m - 1) % 4]), '천월(月)': bi('戌巳辰寅未卯亥未寅午戌寅'[m - 1]),
                '음살': bi('寅子戌申午辰'[(m - 1) % 6]), '해신': bi('申戌子寅辰午'[(m - 1) // 2]),
                '은광': pos['문창'] + d - 2, '천귀': pos['문곡'] + d - 2,
                '태보': bi('午') + h, '봉고': bi('寅') + h,
                '천재': ming + y, '천수': shen + y,                                # 명·신에서 子부터 생년 지지까지 순행
                '천상(傷)': ming - 7, '천사': ming - 5})
    kg = kong(ys, yb)
    pos['절공'] = bi(kg['정_절공'])
    pos['순공'] = bi(kg['정_순공'])
    return {k: bz(v) for k, v in pos.items()}, bz(ming), bz(shen), n, stems, kg


def build(birth, sihua=None, brightness=None):
    """calendar.resolve의 결과 → 명반 dict."""
    sihua = sihua or Sihua()
    brightness = brightness or Brightness()
    ys, yb = birth['lunar']['year_gz']
    m, d, h = birth['lunar']['chart_month'], birth['lunar']['day'], birth['hour_index']
    male = birth['input']['male']
    pos, ming, shen, n, stems, kg = place_stars(ys, yb, m, d, h, male)
    hua_of = {star: hh for hh, star in sihua.of(ys).items()}
    roles = roles_from(ming)
    fwd = yang_stem(ys) == male                                               # 陽男陰女 순행
    cs0 = bi(CS_START[n])
    cs = {bz(cs0 + (k if fwd else -k)): CHANGSHENG[k] for k in range(12)}
    palaces = {z: dict(role=roles[z], stem=stems[z], stars=[], changsheng=cs[z]) for z in BR}
    for name, z in pos.items():
        g = brightness.grade(name, z)
        palaces[z]['stars'].append(dict(name=name, kind=kind_of(name), grade=g, grade_layer=brightness.source(name, z),
                                        cls=brightness.klass(g), hua=hua_of.get(name)))
    birth_hua = {hh: dict(star=star, palace=pos.get(star)) for hh, star in sihua.of(ys).items()}
    return dict(
        birth=birth, year_gz=ys + yb, year_stem=ys, male=male, direction='순행' if fwd else '역행',
        ming=ming, shen=shen, shen_role=roles[shen], ju=n, ju_name=JU_NAME[n],
        mingzhu=MINGZHU[ming], shenzhu=SHENZHU[yb],
        palaces=palaces, pos=pos, birth_hua=birth_hua, kong=kg,
        changsheng=dict(start=CS_START[n], direction='순행' if fwd else '역행', by_palace=cs),
        sihua_variant=sihua.variant,
    )


def chart_from(date, time='12:00', male=True, solar_offset_min=0, tz=9, sihua=None, **kw):
    return build(resolve(date, time, male, solar_offset_min, tz, **kw), sihua=sihua)


# ── 조회 도우미 ─────────────────────────────────────────────
def stars(chart, z, kind=None):
    return [s for s in chart['palaces'][z]['stars'] if kind is None or s['kind'] == kind]


def names(chart, z, kind=None):
    return [s['name'] for s in stars(chart, z, kind)]


def star(chart, name):
    z = chart['pos'][name]
    return z, next(s for s in chart['palaces'][z]['stars'] if s['name'] == name)


def main_stars(chart, z):
    return names(chart, z, '주성')


def kong_zheng(chart):
    """구조 판독에 쓰는 공망 자리(정 절공, 정 순공). 방공은 쓰지 않는다(명세 O8)."""
    return set(chart['kong']['정공'])


def summary(chart):
    out = {}
    for z in BR:
        p = chart['palaces'][z]
        out[z] = dict(role=p['role'], stem=p['stem'], changsheng=p['changsheng'],
                      stars=[s['name'] + (f"({s['grade']})" if s['grade'] else '') + (f"[{s['hua']}]" if s['hua'] else '')
                             for s in p['stars'] if s['kind'] != '잡성'],
                      minor=[s['name'] for s in p['stars'] if s['kind'] == '잡성'])
    return out


__all__ = ['build', 'chart_from', 'stars', 'names', 'star', 'main_stars', 'kong', 'kong_zheng', 'summary',
           'GONGGEOP', 'HUA']

# >>> fast-anything: engine_v2.chart.place_stars >>>
# Uses the verified Rust port. FAST_ANYTHING_DISABLE=1 runs the Python above instead.
# Undo with:  fast-anything disable engine_v2.chart.place_stars
def _fast_anything_load():
    import os, sys
    if os.environ.get("FAST_ANYTHING_DISABLE"):
        return None
    lib = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "../.fast/lib"))
    if lib not in sys.path:
        sys.path.append(lib)
    try:
        from fa_engine_v2_chart_place_stars import place_stars
    except ImportError:
        return None
    return place_stars
place_stars = _fast_anything_load() or place_stars
del _fast_anything_load
# <<< fast-anything: engine_v2.chart.place_stars <<<
