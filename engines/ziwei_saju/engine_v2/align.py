"""사주 판정과 자미두수 값의 결합기(명세 10절 6번, 11-1절 3~7번).

입력: 사주 판정표(data/saju_judgments.json), 낱말 사전(data/trait_lexicon.json), 엔진 결과(compute 출력), l2.evaluate 출력.
출력: 줄마다 {판정_id, 영역, 시기, 방향, 결과, 견준_궁, 근거_구절_id, 맞은_낱말, 신빙성, ...}.
결과는 합치, 상충, 혼재, 무대응 넷이고 대운과 세운이 구간(대한)에 걸쳐 상충이 있으면 '구간 갈림'이다.
격이 온전하지 않은 판정은 결과 구절을 쓰지 않으므로 '제외'다(명세 5절 9번).
가중합이나 비율로 합치를 정하지 않는다. 길흉은 선 구절의 길과 흉이 있는지만 본다(수를 견주지 않는다).
"""
import datetime as _dt
import json
import os

from . import l2
from .common import sanfang

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
JUDGMENTS = os.path.join(DATA, 'saju_judgments.json')
LEXICON = os.path.join(DATA, 'trait_lexicon.json')
_CACHE = {}

# 명세 11-1의 3번: 범주가 가리키는 궁. 직업어는 명세에 없어 명·신·관록으로 둔다(쟁점으로 보고).
CAT_PALACES = {
    '귀천': ('명궁', '신궁', '관록'),
    '빈부': ('명궁', '신궁', '재백', '전택'),
    '수요': ('명궁', '신궁', '질액', '복덕'),
    '질병': ('명궁', '신궁', '질액', '복덕'),
    '지능': ('명궁', '신궁', '복덕'), '강유': ('명궁', '신궁', '복덕'), '문': ('명궁', '신궁', '복덕'),
    '무': ('명궁', '신궁', '복덕'), '재예': ('명궁', '신궁', '복덕'), '색': ('명궁', '신궁', '복덕'), '복': ('명궁', '신궁', '복덕'),
    '직업어': ('명궁', '신궁', '관록'),
    '이동': ('명궁', '천이'),
    '형극': ('명궁', '신궁'),          # 원문이 육친을 들면 그 궁으로 바뀐다
}
RESULTS = ('합치', '상충', '혼재', '무대응')
NEG = '無免不未莫'


# ── 적재 ────────────────────────────────────────────────
def _load(path):
    if path not in _CACHE:
        with open(path, encoding='utf-8') as f:
            _CACHE[path] = json.load(f)
    return _CACHE[path]


def load_judgments(path=None):
    return _load(path or JUDGMENTS)


def load_lexicon(path=None):
    return _load(path or LEXICON)


def passage_texts():
    """구절 id -> result(결과 글귀). 권3과 권4."""
    if 'texts' not in _CACHE:
        t = {}
        for p in l2.load_passages(l2.DATA3) + l2.load_passages(l2.DATA):
            t[p['id']] = p.get('result') or ''
        _CACHE['texts'] = t
    return _CACHE['texts']


# ── 낱말 ────────────────────────────────────────────────
def _index(lexicon):
    ent = {e['낱말']: e for e in lexicon['낱말']}
    poles = lexicon.get('극_정의', {})
    return ent, poles


def extract_words(text, lexicon):
    """text에서 사전 낱말을 가장 긴 것부터 맞춘다. [(낱말, 범주, 극 또는 None)].
    차단어는 건너뛰고, 앞 글자가 부정어(無 免 不 未 莫)이면 세지 않는다(낱말 자신이 부정어로 시작하는 것은 예외)."""
    ent, _ = _index(lexicon)
    ws = sorted(ent, key=lambda w: -len(w))
    masks = sorted(lexicon.get('차단어', {}).get('목록', []), key=lambda w: -len(w))
    out, i = [], 0
    while i < len(text):
        m = next((x for x in masks if text.startswith(x, i)), None)
        if m:
            i += len(m)
            continue
        w = next((x for x in ws if text.startswith(x, i)), None)
        if w:
            neg = i > 0 and text[i - 1] in NEG and w[0] not in NEG
            if not neg:
                out.append((w, ent[w]['범주'], ent[w]['극']))
            i += len(w)
            continue
        i += 1
    return out


# ── 자붕이의 명시 판정(명세 5절 11번): 이 넷에 한해 엔진 값 대신 쓴다 ──────────
def zabungi_explicit(result):
    """이 명반에서 조건이 서는 명시 판정만 {궁: {...}}로 낸다.
    부처궁 록(R29), 노복 경양 제화(560~632), 명궁 화성·천형(1081~1089), 화탐격(R25, 값 없음)."""
    ch = result['chart']
    pal = ch['palaces']
    role_z = {p['role']: z for z, p in pal.items()}
    names = lambda role: {s['name'] for s in pal[role_z[role]]['stars']} if role in role_z else set()
    out = {}
    bl = (ch.get('birth_hua') or {}).get('록') or {}
    if bl.get('palace') is not None and pal.get(bl['palace'], {}).get('role') in ('부처', '형제'):
        r = pal[bl['palace']]['role']
        if r == '부처':
            out['부처'] = dict(방향='흉', 범주=None, 낱말=[], 출전='R29(474~478, 1155~1157): 생년 화록이 부처궁에 있으면 불리')
    nm = names('노복')
    if '경양' in nm and {'삼태', '팔좌'} & nm:
        out['노복'] = dict(방향='제화', 범주=None, 낱말=[], 출전='노복의 경양을 삼태와 팔좌가 제화함(560~632). 흉으로 세지 않는다')
    nm = names('명')
    if {'화성', '천형'} <= nm:
        out['명궁'] = dict(방향='흉', 범주=['질병'], 낱말=[('정신질환', '질병', None)], 출전='명궁 화성과 천형의 글귀를 정신질환으로 읽음(1081~1089)')
    hw = ((result.get('l1') or {}).get('gyeok') or {}).get('hwatam')
    if hw and hw.get('form') and not hw.get('complete'):
        # 기록용: 궁 이름이 아니라 life_direction·life_traits가 읽지 않는다. 화탐격의 결과 구절을 쓰지 않는다는 것 자체가 판정이다
        out['화탐격'] = dict(방향='무효', 범주=None, 낱말=[], 출전='화탐격은 형태만 서고 온전하지 않아 결과 구절을 쓰지 않는다(R25, 3922~3929)')
    return out


# ── 평생 값 ─────────────────────────────────────────────
def palaces_for(cats, 육친=None):
    ps = []
    for c in cats:
        base = CAT_PALACES.get(c, ('명궁', '신궁'))
        if c == '형극' and 육친:
            base = tuple(육친)
        for p in base:
            if p not in ps:
                ps.append(p)
    return ps


def life_direction(ev, palaces, explicit=None, cats=(), lexicon=None, texts=None):
    """평생의 길흉. 궁들의 L2에서 '선다'인 구절만 본다(반만과 성질 서술은 뺀다). 길만이면 길, 흉만이면 흉,
    둘 다이면 혼재, 하나도 없으면 없음. 수를 견주지 않는다. 자붕이의 명시 판정이 있으면 그 궁은 그것이 값이다."""
    explicit = explicit or {}
    gil, hyung, notes = [], [], []
    per = {}
    for pl in palaces:
        ex = explicit.get(pl)
        if ex and (ex.get('범주') is None or set(ex['범주']) & set(cats)):
            per[pl] = {'길': [], '흉': [], '명시': ex['방향']}
            if ex['방향'] == '흉':
                hyung.append('ZB:' + pl)
            notes.append('%s궁은 자붕이 명시 판정(%s)' % (pl, ex['출전']))
            continue
        v = ev.get(pl)
        if not v:
            continue
        def same_cat(it):      # 명세 11-1 4번 가(2026-11-18 정정): 결과문에 사주 판정과 같은 범주 낱말이 든 구절만 견준다
            if lexicon is None:
                return True
            return any(c in cats for _, c, _ in extract_words((texts if texts is not None else {}).get(it['id'], ''), lexicon))
        g = [it['id'] for it in v['passages'] if it['verdict'] == '선다' and it['polarity'] == '길' and same_cat(it)]
        h = [it['id'] for it in v['passages'] if it['verdict'] == '선다' and it['polarity'] == '흉' and same_cat(it)]
        per[pl] = {'길': g, '흉': h}
        gil += g
        hyung += h
    val = '혼재' if gil and hyung else ('길' if gil else ('흉' if hyung else '없음'))
    return dict(값=val, 길=gil, 흉=hyung, 궁별=per, 주=notes)


def judge(direction, value):
    """길흉 판정의 결과(명세 11-1의 5번). 방향이 같으면 합치, 반대면 상충, 자미가 혼재면 혼재, 없음이면 무대응."""
    if value == '혼재':
        return '혼재'
    if value == '없음':
        return '무대응'
    return '합치' if value == direction else '상충'


def life_traits(ev, palaces, lexicon, texts, explicit=None, cat=None):
    """평생의 성질. 궁들의 선 구절('선다')과 명궁·신궁의 성질 서술('성질')의 result에 나온 낱말의 [(낱말, 범주, 극, 구절 id, 궁)]."""
    explicit = explicit or {}
    out = []
    for pl in palaces:
        ex = explicit.get(pl)
        if ex and ex.get('낱말') and (ex.get('범주') is None or cat in ex['범주']):
            for w, c, p in ex['낱말']:
                out.append((w, c, p, 'ZB:' + pl, pl))
        v = ev.get(pl)
        if not v:
            continue
        for it in v['passages']:
            if it['verdict'] not in ('선다', '성질'):
                continue
            for w, c, p in extract_words(texts.get(it['id'], ''), lexicon):
                out.append((w, c, p, it['id'], pl))
    return out


def judge_trait(cat, jwords, evidence, lexicon):
    """성질 판정의 한 범주(명세 11-1의 5번). 극이 없는 범주는 있으면 합치. 극이 있는 범주는 같은 극이 있으면 합치,
    같은 극은 없고 반대 극만 있으면 상충, 둘 다 있으면 혼재, 극을 아는 낱말이 하나도 없으면 무대응(범주만 같고 극을 모르는 것은 합치가 아니다).
    jwords: 판정의 낱말 [(낱말, 극)], evidence: life_traits 출력 중 이 범주의 것."""
    polar = bool(lexicon.get('극_정의', {}).get(cat))
    if not evidence:
        return '무대응', [], [], []
    if not polar:
        return '합치', [e[0] for e in evidence], [e[3] for e in evidence], []
    jp = {p for _, p in jwords if p}
    ep = {e[2] for e in evidence if e[2]}
    if not jp or not ep:      # 판정 쪽이나 자미두수 쪽 극을 모르면 견줄 수 없다
        return '무대응', [], [], []
    same = jp & ep
    opp = ep - jp
    if same and opp:
        res = '혼재'
    elif same:
        res = '합치'
    elif opp:
        res = '상충'
    else:
        res = '무대응'
    hit = [e for e in evidence if e[2] in (same if res in ('합치', '혼재') else opp)]
    return res, [e[0] for e in hit], [e[3] for e in hit], sorted(opp) if res == '혼재' else []


# ── 대운·세운 값 ────────────────────────────────────────
def _dt_of(x):
    return x if isinstance(x, _dt.datetime) else _dt.datetime.combine(x, _dt.time())


def build_daewoon_table(result):
    """대운마다 걸친 대한 구간별 표지. [{gz, start, end, segs:[{daehan, 길:[...], 흉:[...]}]}].
    대운 천간의 사화 가운데 록·권이 대한 삼방 틀이나 본명 삼방 틀에 들면 길 표지, 화기가 그 틀에 들면 흉 표지(명세 11-1의 4번 다)."""
    from .fortune import frames, marks_for
    ch, l1, sh = result['chart'], result['l1'], result['sihua']
    bmap = l1['borrow']
    natal_S = sanfang(ch['ming'])
    out = []
    for p in result['daewoon']['periods']:
        segs = []
        for d in result['daehan']:
            a, b = max(_dt_of(p['start']), _dt_of(d['start'])), min(_dt_of(p['end']), _dt_of(d['end']))
            if not a < b:
                continue
            H = d['palace']
            SH = sanfang(H)
            gil, hyung = [], []
            for m in marks_for(ch, l1, sh, p['stem'], '대운'):
                fr = [f for f in frames(m, H, SH, natal_S, bmap) if f in ('대한삼방', '본명삼방')]
                if not fr:
                    continue
                tag = '화%s %s(%s)' % (m['hua'], m['star'], '/'.join(fr))
                if m['hua'] in ('록', '권'):
                    gil.append(tag)
                elif m['hua'] == '기':
                    hyung.append(tag)
            segs.append(dict(daehan=H, start=a, end=b, 길=gil, 흉=hyung))
        out.append(dict(gz=p['gz'], start=p['start'], end=p['end'], segs=segs))
    return out


def build_seun_table(result, n_daehan=7):
    """해마다 걸친 대한 구간별 표지. [{year, gz, segs:[{daehan, 길, 흉}]}].
    흉 표지: 그해 세운 화기가 대한 삼방이나 본명 삼방 틀에 들고 틀 안 중첩이 선다(대한 삼방 비춤 중첩, 또는 공망과 만나지 않은 구조 중첩).
    길 표지: 그해 화록·화권이 틀에 들거나, 화기가 틀에 들고 구조 중첩이 공망과 만나 길로 읽힌다(1227~1231)."""
    out = {}
    for p in result['l3']['path_daehan'][:n_daehan]:      # 판정표 5절과 같이 출생 뒤 대한 일곱 구간
        for y in p['years']:
            ji = y['ji']
            gil, hyung = [], []
            fr = ji.get('frames') or []
            st, gz_ = ji.get('structural') or {}, ji.get('gaze')
            if fr:
                if (gz_ and gz_.get('중첩')) or (st.get('중첩') and not st.get('kong')):
                    hyung.append('화기 %s(%s) 틀 안 중첩(%s)' % (ji['star'], ji['palace'], '/'.join(fr)))
                if st.get('중첩') and st.get('kong'):
                    gil.append('화기 %s(%s) 구조 중첩이 공망과 만남' % (ji['star'], ji['palace']))
            for x in y.get('lu_gwon') or []:
                gil.append('화%s %s(%s)' % (x['hua'], x['star'], '/'.join(x['frames'])))
            out.setdefault(y['year'], dict(year=y['year'], gz=y['gz'], segs=[]))['segs'].append(
                dict(daehan=p['palace'], partial=y.get('partial'), 길=gil, 흉=hyung))
    return [out[k] for k in sorted(out)]


def _matches(when, gz, year=None):
    """시기 조건: 간지 목록, 천간 목록, 지지 목록, 연도 목록 가운데 적힌 것이 모두 맞아야 한다."""
    if '간지' in when and gz not in when['간지']:
        return False
    if '천간' in when and gz[0] not in when['천간']:
        return False
    if '지지' in when and gz[1] not in when['지지']:
        return False
    if '연도' in when and year not in when['연도']:
        return False
    return True


def _seg_value(seg):
    g, h = bool(seg['길']), bool(seg['흉'])
    return '혼재' if g and h else ('길' if g else ('흉' if h else '없음'))


def combine_segments(results):
    """구간 결과를 한 줄로. 구간이 둘 이상이고 상충이 하나라도 있으면 '구간 갈림', 그렇지 않으면 혼재, 합치, 무대응 차례."""
    rs = list(results)
    if len(rs) >= 2 and '상충' in rs:
        return '구간 갈림'
    if len(rs) == 1:
        return rs[0]
    for x in ('상충', '혼재', '합치'):
        if x in rs:
            return x
    return '무대응'


# ── 본체 ────────────────────────────────────────────────
def _row(j, **kw):
    r = dict(판정_id=j['id'], 영역='·'.join(j.get('범주') or []), 시기='평생', 방향=j['방향'], 결과=None, 견준_궁=[],
             근거_구절_id=[], 맞은_낱말=[], 신빙성=j['신빙성'], 비고=[])
    r.update(kw)
    return r


def align(result, judgments=None, lexicon=None, evaluation=None, texts=None, daewoon_table=None, seun_table=None):
    """판정표의 줄마다 엔진 값과 견주어 줄 리스트를 낸다. 인자를 비우면 엔진 결과와 data의 표를 쓴다."""
    judgments = judgments if judgments is not None else load_judgments()
    judgments = judgments['판정'] if isinstance(judgments, dict) else judgments
    lexicon = lexicon or load_lexicon()
    texts = texts if texts is not None else passage_texts()
    ev = evaluation if evaluation is not None else l2.evaluate(result)
    ent, _ = _index(lexicon)
    explicit = zabungi_explicit(result) if result is not None else {}
    rows = []
    dwt, snt = daewoon_table, seun_table
    for j in judgments:
        cats = j.get('범주') or []
        g = j.get('격')
        unk = (g or {}).get('미확인_조건') or [c['조건'] for c in j.get('조건', []) if c['검사'] == '미확인']
        when = j.get('시기', '평생')
        if g and g.get('온전함') == '불온전':
            rows.append(_row(j, 시기=_시기_글(when), 결과='제외',
                             비고=['격 %s의 형태는 %s이나 온전하지 않아 결과 구절을 쓰지 않는다(5절 9번): %s' % (
                                 g['이름'], g.get('형태'), ' / '.join(g.get('서지_않는_조건') or [])), ]))
            continue
        extra = ['미확인 조건 %d건: %s' % (len(unk), ' / '.join(unk))] if unk else []
        if when == '평생' or isinstance(when, str):
            if j['방향'] == '성질':
                rows += _trait_rows(j, ev, lexicon, texts, explicit, extra)
            elif not cats:          # 결과 원문에 범주 낱말이 없으면(忌·愛 따위) 견줄 궁이 없다(O23)
                rows.append(_row(j, 결과='무대응', 비고=extra + ['결과 원문에 범주 낱말이 없어 견줄 궁이 없다(O23)']))
            else:
                for cat in cats:        # 범주마다 따로 줄을 낸다
                    ps = palaces_for([cat], j.get('육친'))
                    d = life_direction(ev, ps, explicit, [cat], lexicon, texts)
                    res = judge(j['방향'], d['값'])
                    same, opp = (d['길'], d['흉']) if j['방향'] == '길' else (d['흉'], d['길'])
                    ids = same if res == '합치' else (opp if res == '상충' else (same + opp if res == '혼재' else []))
                    rows.append(_row(j, 영역=cat, 결과=res, 견준_궁=ps, 근거_구절_id=ids,
                                     자미_값=dict(값=d['값'], 궁별=d['궁별']), 비고=extra + d['주']))
            continue
        # 대운·세운
        if when['종류'] == '대운':
            if dwt is None:
                dwt = build_daewoon_table(result)
            table = [dict(t, key=t['gz']) for t in dwt if _matches(when, t['gz'])]
        else:
            if snt is None:
                snt = build_seun_table(result)
            table = [dict(t, key=t['year']) for t in snt if _matches(when, t['gz'], t['year'])]
        for t in table:
            if j['방향'] == '성질':
                rows.append(_row(j, 시기=t['key'], 결과='무대응', 비고=extra + ['대운·세운의 성질 값은 엔진이 내지 않는다']))
                continue
            segs = []
            for s in t['segs']:
                v = _seg_value(s)
                segs.append(dict(대한=s['daehan'], 값=v, 길=s['길'], 흉=s['흉'], 결과=judge(j['방향'], v)))
            res = combine_segments([s['결과'] for s in segs]) if segs else '무대응'
            rows.append(_row(j, 시기=t['key'], 결과=res, 견준_궁=[s['대한'] for s in segs],
                             구간=segs, 비고=extra + (['구간이 없다'] if not segs else [])))
    return rows


def _시기_글(when):
    if isinstance(when, str):
        return when
    return '%s(%s)' % (when['종류'], ','.join('%s=%s' % (k, v) for k, v in when.items() if k != '종류'))


def _trait_rows(j, ev, lexicon, texts, explicit, extra):
    ent, _ = _index(lexicon)
    by = {}
    for w in j.get('낱말', []):
        if w in ent:
            by.setdefault(ent[w]['범주'], []).append((w, ent[w]['극']))
    if not by:
        return [_row(j, 결과='무대응', 비고=extra + ['낱말이 사전에 없다'])]
    rows = []
    for cat, jw in by.items():
        ps = palaces_for([cat], j.get('육친'))
        evid = [e for e in life_traits(ev, ps, lexicon, texts, explicit, cat) if e[1] == cat]
        res, words, ids, opp = judge_trait(cat, jw, evid, lexicon)
        note = list(extra)
        if res == '혼재':
            note.append('반대 극 낱말도 서 있다: %s' % ', '.join(opp))
        if evid and res == '무대응':
            note.append('범주는 있으나 극을 아는 낱말이 없다')
        rows.append(_row(j, 영역=cat, 결과=res, 견준_궁=ps, 근거_구절_id=sorted(set(ids)), 맞은_낱말=sorted(set(words)),
                         자미_값=dict(낱말=sorted({(e[0], e[2]) for e in evid}, key=str)), 비고=note,
                         판정_낱말=[w for w, _ in jw]))
    return rows


def tally(rows):
    out = {}
    for r in rows:
        out[r['결과']] = out.get(r['결과'], 0) + 1
    return out
