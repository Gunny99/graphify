"""L3 운: 명세(판 1.0) 4절과 세부 재결. 사화 표시, 틀별 집계, 중첩(R22), 두 판독 틀과 갈림, 록과 권, 같은 천간의 해(R13),
수용성, 제화 사건, 육길성 사건, 두 경로 대조(R12).

사화는 생년·사주 대운 천간·세운 천간에서만 낸다(궁간사화 없음). 숫자 가중치는 없다. 서열은 원문이 말한 둘만 쓴다.
판정 문장은 만들지 않는다.
"""
import datetime as _dt

from . import luck
from .common import HUA, STEM, YUKGIL, bi, opp, sanfang
from .structure import landing, pair_of, reach, receptivity, sanfang_distribution, effective_main

ORDER = (dict(field='층', greater='대운', lesser='세운', source='R11, 2596~2598'),)
# 화기 중첩의 길흉은 틀마다 다르게 적는다(4절 3·4번). 두 틀로 나눠 적는 것 자체는 추론이다.
FRAME_LABELS = dict(비춤_화기중첩='대흉(3490~3492)', 구조_공망화기중첩='길(1227~1231)')
R13_NOTE = '화기가 대한 삼방에 드는 쪽이 대운 쪽 길을 뒤집은 사례가 하나 있다(R13)'


# ── 1. 표시 ──────────────────────────────────────────────
def marks_for(chart, l1, sihua, stem, src):
    out = []
    for h in HUA:
        s = sihua.of(stem)[h]
        ld = landing(chart, l1['borrow'], s)
        out.append(dict(src=src, stem=stem, hua=h, star=s, **ld))
    return out


def birth_marks(chart, l1, sihua):
    return marks_for(chart, l1, sihua, chart['year_stem'], '생년')


def _sid(m):
    return f"{m['src']}:{m['star']}"


def sources_at(marks, hua, unit):
    return [_sid(m) for m in marks if m['hua'] == hua and reach(m) & set(unit)]


def unit_of(bmap, z):
    """중첩을 세는 단위: 궁이 쌍에 들면 그 쌍, 아니면 궁 하나(R22)."""
    pk = pair_of(bmap, z)
    return pk if pk else z


# ── 2. 틀별 집계 ──────────────────────────────────────────
def in_daehan_sanfang(m, SH, bmap):
    """대한 삼방사정(대한명궁 포함 네 궁)에 듦. 대한 삼방에 든 공궁의 대궁 주성에 든 화기도 센다(R17, 쌍 종류 무관)."""
    if reach(m) & set(SH):
        return True
    if m['hua'] == '기':
        for b in bmap.values():
            if b['status'] in ('성립', '차단') and b['receiver'] in SH and m['palace'] == b['sender']:
                return True
    return False


def frames(m, H, SH, natal_S, bmap):
    cats = []
    if H is not None and H in reach(m):
        cats.append('대한명궁')
    if SH is not None and in_daehan_sanfang(m, SH, bmap):
        cats.append('대한삼방')
    if reach(m) & set(natal_S):
        cats.append('본명삼방')
    return cats


# ── 3. 중첩 ──────────────────────────────────────────────
def overlaps(marks, bmap):
    """한 궁이나 한 쌍에 같은 종류의 사화가 둘 이상(R22). [{hua, unit, sources}]."""
    units = set()
    for m in marks:
        for z in reach(m):
            units.add(z)
            units.add(unit_of(bmap, z))
    out = []
    for h in HUA:
        for u in sorted(units, key=lambda u: (len(u), bi(u[0]))):
            src = sources_at(marks, h, u)
            if len(src) >= 2:
                out.append(dict(hua=h, unit=u, sources=src))
    return out


# ── 4. 두 판독 틀 ────────────────────────────────────────
def kong_palaces(chart):
    """구조 판독의 공망 자리 {궁: [종류]}(정 절공, 정 순공)."""
    out = {}
    for k in ('절공', '순공'):
        out.setdefault(chart['kong']['정_' + k], []).append(k)
    return out


def ji_readings(m, marks, l1, SH=None, kongs=None, context_ji=()):
    """화기 하나를 구조 통변(자리)과 대한 삼방 비춤(쌍으로 셈)으로 읽는다.
    구조 통변: 자리의 궁 단위 중첩. 공망과 만난 중첩이면 길(1227~1231). 차단 쌍의 받는 궁에 이미 화기가 있으면 나눠 가짐.
    대한 삼방 비춤: 쌍 단위 중첩이면 대흉(3490~3492).
    갈림: 두 틀의 중첩 여부가 다르거나, 둘 다 중첩인데 구조 쪽이 공망과 만나 길로 읽힐 때(4절 4번)."""
    kongs = kongs or {}
    # context_ji: 나눠 가짐을 볼 때만 더하는 그때의 대운 화기 표시(4절 세부 재결, 추론). 중첩 셈에는 넣지 않는다
    bmap = l1['borrow']
    pos = m['palace']
    src_here = sources_at(marks, '기', pos)
    shared = None
    if m['blocked_pair']:
        b = l1['pairs'][m['blocked_pair']]
        others = [x for x in sources_at(marks, '기', b['receiver']) if x != _sid(m)]
        ctx = [x for x in sources_at(list(context_ji), '기', b['receiver']) if x != _sid(m) and x not in others]
        if others or ctx:
            shared = dict(receiver=b['receiver'], with_=others + ctx,
                          note='대운 화기 포함(4절 세부 재결, 추론)' if ctx else None)
    s_ov = len(src_here) >= 2
    with_kong = kongs.get(pos, [])
    if s_ov:
        s_label = FRAME_LABELS['구조_공망화기중첩'] if with_kong else '중첩'
    else:
        s_label = '나눠 가짐' if shared else '단일'
    structural = dict(position=pos, sources=src_here, 중첩=s_ov, kong=with_kong, 나눠가짐=shared, label=s_label)
    gaze = None
    if SH is not None and in_daehan_sanfang(m, SH, bmap):
        u = unit_of(bmap, pos)
        src = sources_at(marks, '기', u)
        g_ov = len(src) >= 2
        gaze = dict(unit=u, sources=src, 중첩=g_ov, label=FRAME_LABELS['비춤_화기중첩'] if g_ov else '단일')
    galim = gaze is not None and (gaze['중첩'] != s_ov or (s_ov and bool(with_kong)))
    return dict(structural=structural, gaze=gaze, 갈림=galim)


def _jehwa_strike(m, l1):
    """차단 쌍의 보내는 궁에 화기: 공망을 바깥에서 침. 해공은 조건부(1953)."""
    if m['hua'] != '기' or not m['blocked_pair']:
        return None
    b = l1['pairs'][m['blocked_pair']]
    return dict(kind='차단쌍_보내는궁_화기', src=_sid(m), sender=b['sender'], receiver=b['receiver'], kong=b['kong'],
                haegong='조건부(자붕이 추정형, 1953)')


def _yukgil_hua(marks):
    return [dict(src=_sid(m), hua=m['hua'], star=m['star'], palace=m['palace']) for m in marks
            if m['src'] != '생년' and m['star'] in YUKGIL]


def _lu_gwon(marks, SH, natal_S, bmap):
    out = []
    for m in marks:
        if m['src'] != '생년' and m['hua'] in ('록', '권'):
            f = []
            if SH is not None and in_daehan_sanfang(m, SH, bmap):
                f.append('대한삼방')
            if reach(m) & set(natal_S):
                f.append('본명삼방')
            if f:
                out.append(dict(src=_sid(m), hua=m['hua'], star=m['star'], palaces=sorted(reach(m), key=bi), frames=f))
    return out


def _palace_counts(marks):
    out = {}
    for m in marks:
        for z, via in [(m['palace'], '')] + [(c, '(차성)') for c in m['copies']]:
            if z is not None:
                out.setdefault(z, {}).setdefault(m['hua'], []).append(_sid(m) + via)
    return out


# ── R16 화과는 화기를 만나면 뜻이 없다(3486) ─────────────────
R16_BASIS = '자붕이 3486 "화과는 화기랑 만나면 의미없으니". 확인은 한 궁, 그 밖은 추론'


def void_gwa(luck_marks, birth_marks_, bmap):
    """운(대운·세운 천간)의 화과마다 화기와 만나는지. 확인: 운의 화기와 같은 궁(차성 복사 포함).
    추론: 생년 화기가 있는 궁이거나 운의 화기와 대궁(또는 같은 쌍)으로 만남. 아니면 None. [{src, star, palace, void_by_ji, with_}]"""
    jis = [m for m in luck_marks if m['hua'] == '기']
    out = []
    for g in luck_marks:
        if g['hua'] != '과':
            continue
        rg = reach(g)
        conf = [_sid(k) for k in jis if rg & reach(k)]
        inf = [_sid(k) + '(대궁 쌍)' for k in jis if not (rg & reach(k)) and
               any(opp(z) in reach(k) or (pair_of(bmap, z) and pair_of(bmap, z) == pair_of(bmap, w))
                   for z in rg for w in reach(k))]
        inf += [_sid(k) + '(생년 화기 궁)' for k in birth_marks_ if k['hua'] == '기' and rg & reach(k)]
        v = '확인' if conf else ('추론' if inf else None)
        out.append(dict(src=_sid(g), star=g['star'], palace=g['palace'], void_by_ji=v, with_=conf or inf, basis=R16_BASIS))
    return out


# ── 8절 1번 노출도, 4번 중첩의 수 ───────────────────────────
FRAME_NAMES = ('대한명궁', '대한삼방', '본명삼방')


def exposure(chart, l1, sihua, H=None, years=None):
    """노출도(명세 8절 1번). 열 천간이 한 번씩 들므로 틀마다 사화 종류별로 k/10을 센다.
    k는 그 틀에 그 사화를 붙이는 천간의 수. 틀에 드는지는 frames()를 그대로 쓴다(공궁 차성, R17 확장은 화기에만).
    H가 None이면 본명 삼방사정만 낸다. 가중치는 없다.
    years(대한의 해마다 행)가 있으면 화기 칸에 overlap_k, overlap_list(화기 중첩이 선 천간과 별)를 더한다(8절 4번)."""
    bmap = l1['borrow']
    natal_S = sanfang(chart['ming'])
    SH = sanfang(H) if H is not None else None
    names = FRAME_NAMES if H is not None else ('본명삼방',)
    out = {f: {h: dict(k=0, of=len(STEM), list=[]) for h in HUA} for f in names}
    for st in STEM:
        for m in marks_for(chart, l1, sihua, st, '노출'):
            for f in frames(m, H, SH, natal_S, bmap):
                cell = out[f][m['hua']]
                cell['list'].append(dict(stem=st, star=m['star']))
                cell['k'] += 1
    for f in out:
        out[f]['기'].update(overlap_k=0, overlap_list=[])
        if years and f != '본명삼방':
            out[f]['과'].update(k_effective=None, void_confirmed=[])
    if years:
        # R16: 세운 천간의 화과가 운의 화기와 같은 궁에서 만나(확인) 무효가 된 해의 천간을 과 칸에서 뺀 수
        vstem = {y['gz'][0] for y in years for m in y['marks'] if m['hua'] == '과' and m.get('void_by_ji') == '확인'}
        for f in out:
            if f == '본명삼방':
                continue    # 본명 삼방 칸은 대한과 무관한 본명 값이라 그대로 둔다(natal과 같아야 함)
            cell = out[f]['과']
            cell['void_confirmed'] = [x['stem'] for x in cell['list'] if x['stem'] in vstem]
            cell['k_effective'] = cell['k'] - len(cell['void_confirmed'])
        seen = set()
        for y in years:
            ji = y['ji']
            for f in ji['frames']:
                g = ji['gaze']
                ov = g['중첩'] if (f != '본명삼방' and g is not None) else ji['structural']['중첩']
                key = (f, y['gz'][0])
                if ov and key not in seen:
                    seen.add(key)
                    cell = out[f]['기']
                    cell['overlap_list'].append(dict(stem=y['gz'][0], star=ji['star']))
                    cell['overlap_k'] += 1
    if H is not None:
        c = out['대한삼방']['기']
        c.update(daehyung=c['overlap_k'] >= 3, daehyung_basis='자붕이 3488~3492, 3/10 명문',
                 beyond_text=c['overlap_k'] > 3)
    return out


def overlap_years(years):
    """록·권·과 중첩이 선 천간의 수를 사화 종류별로(틀 구분 없음). 화기는 exposure의 틀별 overlap_k로 낸다."""
    by = {h: set() for h in HUA if h != '기'}
    for y in years:
        for o in y['overlaps']:
            if o['hua'] in by:
                by[o['hua']].add(y['gz'][0])
    return dict(of=len(STEM), by_hua={h: len(v) for h, v in by.items()})


# ── 경로 1: 대한 ─────────────────────────────────────────
def path_daehan(chart, l1, sihua, dh, boundary='lichun', dw=None):
    bmap = l1['borrow']
    natal_S = sanfang(chart['ming'])
    tz = chart['birth']['input']['tz']
    bm = birth_marks(chart, l1, sihua)
    kongs = kong_palaces(chart)
    natal_yk = {n for n, _, _ in l1['natal_sanfang']['육길성']}
    out = []
    for p in dh:
        H = p['palace']
        SH = sanfang(H)
        rc = receptivity(chart, sihua, bmap, SH)
        dist = sanfang_distribution(chart, H)
        static = dict(main=[dict(star=s, palace=z, via=via, cls=l1['brightness']['star'][s]['cls'])
                            for z in SH for s, via in effective_main(chart, bmap, z)],
                      dist=dist, roles={z: p['roles'][z] for z in SH})
        new_yk = [r for r in dist['육길성'] if r[0] not in natal_yk]
        years = []
        counts = dict(대한명궁=[], 대한삼방=[], 본명삼방=[], 쌍={})
        for sw in luck.years_of_daehan(p, boundary, tz):
            sm = marks_for(chart, l1, sihua, sw['stem'], '세운')
            allm = bm + sm
            evs = [dict(m, frames=frames(m, H, SH, natal_S, bmap)) for m in sm]
            ji = next(e for e in evs if e['hua'] == '기')
            ctx = []
            cur_dm = []
            if dw is not None:
                a, b = sw['overlap']
                cur = luck.daewoon_on(dw, a + (b - a) / 2)
                if cur.get('stem'):
                    cur_dm = marks_for(chart, l1, sihua, cur['stem'], '대운')
                    ctx = [m for m in cur_dm if m['hua'] == '기']
            vg = void_gwa(sm + cur_dm, bm, bmap)
            vmap = {x['src']: x['void_by_ji'] for x in vg}
            evs = [dict(e, void_by_ji=vmap[_sid(e)]) if e['hua'] == '과' else e for e in evs]
            rd = ji_readings(ji, allm, l1, SH, kongs, ctx)
            pk = pair_of(bmap, ji['palace'])
            for c in ji['frames']:
                counts[c].append(sw['year'])
            if pk:
                counts['쌍'].setdefault(pk, []).append(sw['year'])
            lg = _lu_gwon(sm, SH, natal_S, bmap)
            ov = overlaps(allm, bmap)
            ji_ov = rd['structural']['중첩'] or bool(rd['gaze'] and rd['gaze']['중첩'])
            galim = []
            if rd['갈림']:
                galim.append(dict(type='화기_판독틀', structural=rd['structural'], gaze=rd['gaze']))
            if ji_ov and any(x['hua'] == '록' and '본명삼방' in x['frames'] for x in lg):
                galim.append(dict(type='화록_본명삼방과_화기중첩', lu=[x for x in lg if x['hua'] == '록'],
                                  ji_unit=(rd['gaze'] or {}).get('unit', ji['palace']),
                                  표시='사례 한 건의 추론(2018, 4절 세부 재결)'))
            events = []
            st = _jehwa_strike(ji, l1)
            if st:
                events.append(st)
            events += [dict(kind='육길성_사화', **x) for x in _yukgil_hua(sm)]
            years.append(dict(year=sw['year'], gz=sw['gz'], start=sw['start'], end=sw['end'], partial=sw['partial'],
                              marks=evs, ji=dict(star=ji['star'], palace=ji['palace'], frames=ji['frames'], pair=pk, **rd),
                              lu_gwon=lg, overlaps=ov, void_gwa=vg, galim=galim, events=events,
                              palace_counts=_palace_counts(allm)))
        out.append(dict(n=p['n'], palace=H, natal_role=p['natal_role'], age_from=p['age_from'], age_to=p['age_to'],
                        start=p['start'], end=p['end'], sanfang=SH, static=static, natal_static=l1['natal_sanfang'],
                        receptivity=rc, exposure=exposure(chart, l1, sihua, H, years),
                        overlap_years=overlap_years(years),
                        yukgil_new=new_yk, years=years, ji_counts=counts))
    return out


# ── 경로 2: 대운 ─────────────────────────────────────────
def _ji_count_at_birth(marks, chart, bmap):
    z = chart['birth_hua']['기']['palace']
    return dict(palace=z, palace_n=len(sources_at(marks, '기', z)), unit=unit_of(bmap, z),
                unit_n=len(sources_at(marks, '기', unit_of(bmap, z))))


def path_daewoon(chart, l1, sihua, dw, dh, boundary='lichun'):
    bmap = l1['borrow']
    natal_S = set(sanfang(chart['ming']))
    tz = chart['birth']['input']['tz']
    bm = birth_marks(chart, l1, sihua)
    kongs = kong_palaces(chart)
    out = []
    prev = dict(gz=None, count=_ji_count_at_birth(bm, chart, bmap))
    for p in dw['periods']:
        dm = marks_for(chart, l1, sihua, p['stem'], '대운')
        allm = bm + dm
        for m in dm:
            m['중첩'] = bool([o for o in overlaps(allm, bmap) if o['hua'] == m['hua'] and _sid(m) in o['sources']])
        ji = next(m for m in dm if m['hua'] == '기')
        rd = ji_readings(ji, allm, l1, None, kongs)
        cnt = _ji_count_at_birth(allm, chart, bmap)
        events = []
        if cnt['palace_n'] < prev['count']['palace_n'] or cnt['unit_n'] < prev['count']['unit_n']:
            events.append(dict(kind='대운교체_화기감소', from_gz=prev['gz'], to_gz=p['gz'], before=prev['count'], after=cnt))
        st = _jehwa_strike(ji, l1)
        if st:
            events.append(st)
        events += [dict(kind='육길성_사화', **x) for x in _yukgil_hua(dm)]
        same = []
        for sw in luck.seun_years_between(p['start'], p['end'], boundary, tz):
            if sw['stem'] != p['stem']:
                continue
            a, b = sw['overlap']
            d = luck.daehan_on(dh, (a + (b - a) / 2).date())
            sj = next(m for m in marks_for(chart, l1, sihua, sw['stem'], '세운') if m['hua'] == '기')
            in_sf = d is not None and in_daehan_sanfang(sj, sanfang(d['palace']), bmap)
            # 이미 있는 화기 = 생년 화기(같은 궁이나 쌍). 같은 천간 대운의 화기는 세운과 같은 별이라 늘 겹치므로 세지 않는다
            already = sources_at(bm, '기', unit_of(bmap, sj['palace']))
            same.append(dict(year=sw['year'], gz=sw['gz'], partial=sw['partial'], daehan=None if d is None else d['palace'],
                             ji_palace=sj['palace'], in_daehan_sanfang=in_sf, overlaps_with=already,
                             R13_단서=in_sf and bool(already)))
        out.append(dict(n=p['n'], gz=p['gz'], stem=p['stem'], start=p['start'], end=p['end'],
                        marks=dm, ji=dict(star=ji['star'], palace=ji['palace'], pair=pair_of(bmap, ji['palace']), **rd),
                        overlaps=overlaps(allm, bmap), palace_counts=_palace_counts(allm),
                        lu_into_natal_sanfang=bool(reach(next(m for m in dm if m['hua'] == '록')) & natal_S),
                        lu_gwon=_lu_gwon(dm, None, natal_S, bmap),
                        events=events, same_stem_years=same, ji_count_at_birth=cnt))
        prev = dict(gz=p['gz'], count=cnt)
    return out


# ── 두 경로 대조 ─────────────────────────────────────────
def contrast(chart, l1, sihua, p1, p2, boundary='lichun'):
    """(대한, 대운)이 같은 구간마다 대한 틀(세운으로 본 화기 중첩 자리)과 대운 틀(대운 천간 사화의 화기 중첩 자리)을
    나란히 두고 일치·불일치를 적는다(R12, 4절 10번). 화록 항목은 뺐다(4절 세부 재결: 대한 틀 쪽이 거의 늘 참)."""
    bmap = l1['borrow']
    natal_S = sanfang(chart['ming'])
    bm = birth_marks(chart, l1, sihua)
    kongs = kong_palaces(chart)
    D = lambda d: d if isinstance(d, _dt.datetime) else _dt.datetime.combine(d, _dt.time())
    cuts = set()
    for p in p1:
        cuts |= {D(p['start']), D(p['end'])}
    for p in p2:
        cuts |= {p['start'], p['end']}
    lo, hi = D(p1[0]['start']), D(p1[-1]['end'])
    cuts = sorted(c for c in cuts if lo <= c <= hi)
    rows = []
    for a, b in zip(cuts, cuts[1:]):
        mid = a + (b - a) / 2
        d1 = next(p for p in p1 if D(p['start']) <= mid < D(p['end']))
        d2 = next((p for p in p2 if p['start'] <= mid < p['end']), None)
        SH = d1['sanfang']
        yrs = [y for y in d1['years'] if y['start'] < b and y['end'] > a]
        k1_ji = sorted({o['unit'] for y in yrs for o in y['overlaps'] if o['hua'] == '기'
                        and any(in_daehan_sanfang(m, SH, bmap) for m in bm + y['marks'] if m['hua'] == '기' and _sid(m) in o['sources'])},
                       key=lambda u: (len(u), bi(u[0])))
        row = dict(start=a, end=b, daehan=d1['palace'], daewoon=None if d2 is None else d2['gz'],
                   daehan_frame=dict(ji_overlap_units=k1_ji))
        if d2 is None:
            row.update(daewoon_frame=None, compare=None)
        else:
            dm = d2['marks']
            k2_ji = sorted({o['unit'] for o in d2['overlaps'] if o['hua'] == '기'}, key=lambda u: (len(u), bi(u[0])))
            cmp_ji = '일치' if k1_ji == k2_ji else '불일치'
            jm = next(m for m in dm if m['hua'] == '기')
            rd2 = ji_readings(jm, bm + dm, l1, SH, kongs)
            row.update(daewoon_frame=dict(ji_overlap_units=k2_ji, ji_readings=rd2),
                       compare=dict(화기중첩자리=cmp_ji, 대운화기_판독틀='갈림' if rd2['갈림'] else '같음',
                                    갈림=(['화기중첩자리'] if cmp_ji == '불일치' else []) + (['대운화기_판독틀'] if rd2['갈림'] else []),
                                    note=R13_NOTE if cmp_ji == '불일치' else None))
        rows.append(row)
    return rows


def analyze(chart, l1, dw, dh, sihua, boundary='lichun'):
    p1 = path_daehan(chart, l1, sihua, dh, boundary, dw)
    p2 = path_daewoon(chart, l1, sihua, dw, dh, boundary)
    expo = dict(natal=exposure(chart, l1, sihua),
                daehan=[dict(n=p['n'], palace=p['palace'], frames=p['exposure'], overlap_years=p['overlap_years']) for p in p1])
    return dict(path_daehan=p1, path_daewoon=p2, exposure=expo, contrast=contrast(chart, l1, sihua, p1, p2, boundary),
                order=ORDER, frame_labels=FRAME_LABELS, seun_boundary=dict(value=boundary, note=luck.SEUN_BOUNDARY_NOTE))
