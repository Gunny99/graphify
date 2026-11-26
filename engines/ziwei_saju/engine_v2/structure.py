"""L1 구조 판독: 명세(판 1.0) 3절 13단계. 구조 궁은 명반에서 찾는다(궁·별 이름 상수 없음).

출력은 구조 사실 dict다. 판정 문장은 만들지 않는다.
"""
from .chart import main_stars, stars
from .common import BR, GONGGEOP, HUA, MAIN14, SAL, STEM, YUKGIL, bi, bz, opp, sanfang

SF_NOTED = ('녹존', '천형')     # 3절 8번(녹존)과 3절 검산값(천형 廟)이 본명 삼방사정 분포에 적은 별
BASIC_GYEOK = {'살파랑': ('칠살', '파군', '탐랑')}     # R19. 다른 기본격은 명세에 없어 두지 않는다
# 3절 13번 협의 짝별(1239~1251)
JIA_PAIRS = (('지공', '지겁'), ('경양', '타라'), ('화성', '영성'), ('천괴', '천월'), ('좌보', '우필'), ('문창', '문곡'))


# 1 ─────────────────────────────────────────────
def empty_palaces(chart):
    return [z for z in BR if not main_stars(chart, z)]


def pair_key(a, b):
    return ''.join(sorted((a, b), key=bi))


# 2·3 ───────────────────────────────────────────
def borrows(chart):
    """쌍 판정. 공궁과 그 대궁(주성이 있을 때)을 한 쌍으로 묶는다(R3).
    받는 공궁에 공망(절공, 순공)이 있으면 차단 쌍(R5). 방공은 쓰지 않는다. 공망 종류를 그대로 내고,
    절공과 순공이 함께일 때만 confirmed=True(3절 3번)."""
    kz = chart['kong']
    out = {}
    for z in empty_palaces(chart):
        o = opp(z)
        base = dict(receiver=z, sender=o, sender_main=main_stars(chart, o), pair=pair_key(z, o))
        if not base['sender_main']:
            out[z] = dict(base, status='쌍 아님', reason='대궁도 공궁')
            continue
        hit = [k for k, pos in (('절공', kz['정_절공']), ('순공', kz['정_순공'])) if pos == z]
        if hit:
            out[z] = dict(base, status='차단', kong=hit, confirmed=set(hit) == {'절공', '순공'}, relation='형극',
                          receiver_reads='자기 보좌성과 그 사화만')
        else:
            out[z] = dict(base, status='성립', relation=dict(채무=o, 채주=z),
                          borrowed=[dict(name=s['name'], grade=s['grade'], cls=s['cls'], hua=s['hua'],
                                         brightness_note='보내는 궁의 값(미확인, 2539·2537)')
                                    for s in stars(chart, o, '주성')])
    return out


def pairs(bmap):
    """쌍 목록 {쌍 키: 판정}. 성립과 차단만."""
    return {b['pair']: b for b in bmap.values() if b['status'] in ('성립', '차단')}


def pair_of(bmap, z):
    """궁이 든 쌍 키(없으면 None)."""
    for b in bmap.values():
        if b['status'] in ('성립', '차단') and z in (b['sender'], b['receiver']):
            return b['pair']
    return None


def effective_main(chart, bmap, z):
    """궁이 읽는 주성 [(별, 경로)]. 경로 '본궁' 또는 '차성'(성립 쌍). 차단 쌍의 받는 궁은 빈 목록."""
    own = main_stars(chart, z)
    if own:
        return [(s, '본궁') for s in own]
    b = bmap.get(z)
    if b and b['status'] == '성립':
        return [(s, '차성') for s in b['sender_main']]
    return []


def landing(chart, bmap, star_name):
    """별에 붙는 사화의 표시(4절 1번). palace(앉은 궁), copies(성립 쌍의 받는 궁에도 표시, 주성만),
    blocked_pair(차단 쌍의 보내는 궁이면 그 쌍 키: 자리는 그대로)."""
    z = chart['pos'].get(star_name)
    if z is None:
        return dict(palace=None, copies=[], blocked_pair=None)
    copies, bp = [], None
    if star_name in MAIN14:
        for r, b in bmap.items():
            if b['sender'] == z and b['status'] == '성립':
                copies.append(r)
            elif b['sender'] == z and b['status'] == '차단':
                bp = b['pair']
    return dict(palace=z, copies=copies, blocked_pair=bp)


def reach(land):
    """표시된 궁 집합(앉은 궁 + 성립 쌍 복사)."""
    return {land['palace'], *land['copies']} - {None}


# 4·5 ───────────────────────────────────────────
def borrow_facts(chart, bmap):
    est, blk = [], []
    for z, b in bmap.items():
        if b['status'] == '성립':
            est.append(dict(pair=b['pair'], sender=b['sender'], receiver=z, stars=b['borrowed'],
                            birth_hua_marked=[(s['name'], s['hua']) for s in b['borrowed'] if s['hua']],
                            relation=b['relation']))
        elif b['status'] == '차단':
            own = [dict(name=s['name'], hua=s['hua']) for s in stars(chart, z) if s['kind'] != '잡성']
            blk.append(dict(pair=b['pair'], sender=b['sender'], receiver=z, kong=b['kong'], confirmed=b['confirmed'],
                            relation='형극', receiver_own=own,
                            receiver_has_birth_ji=any(x['hua'] == '기' for x in own),
                            luck_ji_on_sender='자리는 보내는 궁 그대로. 받는 궁에 이미 화기가 있을 때만 나눠 가짐(3절 5번)'))
    return est, blk


# 6 ─────────────────────────────────────────────
def jehwa_points(chart):
    """생년 화기가 있는 궁에 공망(정 절공·정 순공)이 있으면 제화 지점(R6)."""
    ji = chart['birth_hua']['기']
    z = ji['palace']
    kz = chart['kong']
    hit = [k for k, pos in (('절공', kz['정_절공']), ('순공', kz['정_순공'])) if pos == z]
    return [dict(palace=z, star=ji['star'], kong=hit)] if hit else []


# 7 ─────────────────────────────────────────────
def brightness_map(chart):
    per_star, per_palace, hua_on_weak = {}, {}, []
    for z in BR:
        ms = stars(chart, z, '주성')
        for s in ms:
            per_star[s['name']] = dict(palace=z, grade=s['grade'], cls=s['cls'], layer=s['grade_layer'])
            if s['cls'] == '함' and s['hua'] in ('록', '권', '과'):
                hua_on_weak.append(dict(star=s['name'], palace=z, hua=s['hua'], status='작동 여부 미정(R8, 3절 검산값)'))
        cl = [s['cls'] for s in ms]
        if not ms:
            kind = '공궁'
        elif any(c in ('평', '함') for c in cl):
            kind = '열린'
        elif all(c == '묘왕' for c in cl):
            kind = '묘왕'
        else:
            kind = '미확인'
        per_palace[z] = kind
    groups = {c: sorted([k for k, v in per_star.items() if v['cls'] == c], key=MAIN14.index)
              for c in ('묘왕', '평', '함', '미확인')}
    return dict(star=per_star, palace=per_palace, groups=groups, hua_on_weak=hua_on_weak)


# 8 ─────────────────────────────────────────────
def sanfang_distribution(chart, z):
    """삼방사정의 육길성, 살성, 녹존(과 천형)을 밝기와 함께. 공겁은 살성의 부분집합으로 따로 적는다. 판정은 L2."""
    out = dict(palaces=sanfang(z), 육길성=[], 살성=[], 공겁=[], **{k: [] for k in SF_NOTED})
    for p in sanfang(z):
        for s in stars(chart, p):
            n = s['name']
            row = (n, p, s['grade'])
            if n in YUKGIL:
                out['육길성'].append(row)
            if n in SAL:
                out['살성'].append(row)
            if n in GONGGEOP:
                out['공겁'].append(row)
            if n in SF_NOTED:
                out[n].append(row)
    return out


# 9 ─────────────────────────────────────────────
def lu_position(chart, sihua, bmap):
    S = set(sanfang(chart['ming']))
    lu = chart['birth_hua']['록']
    stems = []
    for s in STEM:
        r = reach(landing(chart, bmap, sihua.of(s)['록']))
        if r & S:
            stems.append(dict(stem=s, star=sihua.of(s)['록'], palaces=sorted(r & S, key=bi)))
    return dict(birth_lu=dict(star=lu['star'], palace=lu['palace'],
                              in_natal_sanfang=bool(reach(landing(chart, bmap, lu['star'])) & S)),
                natal_sanfang=sanfang(chart['ming']), stems_lu_into_sanfang=stems)


# 10 ────────────────────────────────────────────
def gyeok(chart, bmap):
    """기본격의 성립 여부만(R19). 등급은 L2."""
    eff = [s for s, _ in effective_main(chart, bmap, chart['ming'])]
    basic = {g: bool(set(eff) & set(members)) for g, members in BASIC_GYEOK.items()}
    return dict(basic=basic, ming_stars=[s['name'] for s in stars(chart, chart['ming']) if s['kind'] != '잡성'],
                hwatam=hwatam(chart))


# R25 화탐격 ────────────────────────────────────
HWATAM_PAIR = ('탐랑', '화성')     # R25: 형태는 이 둘의 동궁
HWATAM_BASIS = '자붕이 729~733, 3922~3929(R25). 영성(鈴貪)은 넣지 않는다'


def hwatam(chart):
    """화탐격(R25, 5절 9번). 형태: 탐랑과 화성이 한 궁. 온전함: 탐랑이 묘왕이고 그 궁의 삼방사정에 지공·지겁이 없다.
    온전하지 않으면 까닭 목록을 낸다. 형태가 아니면 온전함은 None."""
    pos = chart['pos']
    main_, fire_ = HWATAM_PAIR
    z = pos.get(main_)
    form = z is not None and pos.get(fire_) == z
    out = dict(form=form, palace=z if form else None, complete=None, reasons=[], basis=HWATAM_BASIS)
    if not form:
        return out
    tl = next(s for s in stars(chart, z, '주성') if s['name'] == main_)
    if tl['cls'] != '묘왕':
        out['reasons'].append(dict(kind='탐랑 밝기', star='탐랑', palace=z, grade=tl['grade'], cls=tl['cls']))
    for p in sanfang(z):
        for s in stars(chart, p):
            if s['name'] in GONGGEOP:
                out['reasons'].append(dict(kind='공겁', star=s['name'], palace=p, grade=s['grade']))
    out['complete'] = not out['reasons']
    return out


# R26 ───────────────────────────────────────────
MING_VOLATILE_STARS = ('파군', '탐랑')
MING_VOLATILE_BASIS = '자붕이 3889~3894(R26). 끝 문장은 추정형'


def ming_volatile(chart, bmap):
    """명궁 주성이 파군이나 탐랑이면 True(칠살보다 대한·세한에 더 흔들림). 명궁이 공궁이라 차성으로만 들어오면
    원문 근거가 없어 None(미확인)으로 낸다."""
    eff = effective_main(chart, bmap, chart['ming'])
    hit = [(s, via) for s, via in eff if s in MING_VOLATILE_STARS]
    via = sorted({v for _, v in hit})
    value = bool(hit)
    note = None
    if hit and via == ['차성']:
        value, note = None, '차성, 원문 근거 없음(미확인)'
    return dict(value=value, stars=[s for s, _ in hit], via=via, note=note, basis=MING_VOLATILE_BASIS)


# 11 ────────────────────────────────────────────
def palace_receptivity(chart, sihua, bmap, z):
    """궁 단위 수용성: 주성(본궁, 성립 쌍의 차성)이 받는 사화를 합친다. 보좌의 사화는 따로."""
    per_star = {}
    for s, via in effective_main(chart, bmap, z):
        per_star[s] = dict(via=via, receives=sihua.received(s))
    union = {}
    for s, v in per_star.items():
        for h, stems_ in v['receives'].items():
            union.setdefault(h, []).extend((s, st) for st in stems_)
    aux = {s['name']: sihua.received(s['name']) for s in stars(chart, z) if s['kind'] != '주성' and sihua.received(s['name'])}
    none = [s for s, v in per_star.items() if not v['receives']]
    return dict(main=per_star, union=union, hua_kinds=[h for h in HUA if h in union],
                none_stars=none, main_total=len(per_star), none_count=len(none), aux=aux)


def receptivity(chart, sihua, bmap, palaces):
    """삼방사정 수용성. 궁 단위로 합치고 사화를 하나도 못 받는 주성의 수를 낸다. 판정어는 붙이지 않는다(9절 6번, R15)."""
    by_palace = {z: palace_receptivity(chart, sihua, bmap, z) for z in palaces}
    none = [(s, z) for z, v in by_palace.items() for s in v['none_stars']]
    by_hua = {h: sorted({s for v in by_palace.values() for s, _ in v['union'].get(h, [])}) for h in HUA}
    total = sum(v['main_total'] for v in by_palace.values())
    return dict(by_palace=by_palace, by_hua=by_hua, main_receives_none=none, main_total=total, none_count=len(none))


# 12 ────────────────────────────────────────────
def inflection(chart, bmap, jehwa):
    """R9 여섯 종류 가운데 명반만으로 정해지는 넷. 대세운 제화와 육길성 이로공명은 L3 사건."""
    out = dict(함지주성궁=[], 공궁=empty_palaces(chart), 화기공망=[j['palace'] for j in jehwa], 평지궁=[])
    for z in BR:
        cls = [s['cls'] for s in stars(chart, z, '주성')]
        if '함' in cls:
            out['함지주성궁'].append(z)
        if '평' in cls:
            out['평지궁'].append(z)
    out['all'] = sorted(set().union(*[set(v) for v in out.values()]), key=bi)
    return out


# 13 ────────────────────────────────────────────
def jia(chart):
    """협: 양옆 궁에 짝별이 하나씩 있으면 가운데 궁을 협으로 적는다(3절 13번). [{palace, pair, sides}]."""
    pos = chart['pos']
    out = []
    for z in BR:
        left, right = bz(bi(z) - 1), bz(bi(z) + 1)
        for a, b in JIA_PAIRS:
            pa, pb = pos.get(a), pos.get(b)
            if {pa, pb} == {left, right}:
                out.append(dict(palace=z, pair=(a, b), sides={a: pa, b: pb}))
    return out


def analyze(chart, sihua):
    bmap = borrows(chart)
    est, blk = borrow_facts(chart, bmap)
    jehwa = jehwa_points(chart)
    S = sanfang(chart['ming'])
    mv = ming_volatile(chart, bmap)
    return dict(
        empty=empty_palaces(chart),
        borrow=bmap,
        pairs=pairs(bmap),
        borrow_established=est,
        borrow_blocked=blk,
        jehwa=jehwa,
        brightness=brightness_map(chart),
        natal_sanfang=sanfang_distribution(chart, chart['ming']),
        lu=lu_position(chart, sihua, bmap),
        gyeok=gyeok(chart, bmap),
        receptivity=dict(by_palace={z: palace_receptivity(chart, sihua, bmap, z) for z in BR},
                         natal_sanfang=receptivity(chart, sihua, bmap, S)),
        inflection=inflection(chart, bmap, jehwa),
        jia=jia(chart),
        ming_volatile=mv['value'],
        ming_volatile_basis=mv['basis'],
        ming_volatile_detail=mv,
    )
