"""판정표 생성기: engine_v2.compute()의 출력에서 마크다운 문서를 낸다.

엔진이 낸 사실, 원문 구절, 수만 적는다. 해석문과 권고는 쓰지 않는다. 명반 값은 없다.
build(result, rank_table=None, cmd=None, years=None, today=None) -> str
  rank_table: 6절에 붙일 표 문자열(없으면 6절을 뺀다).
  cmd: 생성 정보에 적을 명령(없으면 입력에서 만든다).
  years: (처음, 끝) 5절 해마다 표의 해 범위(없으면 전부).
table_from_file(path): 마크다운 파일의 첫 표(연속한 | 줄)를 문자열로 낸다.
"""
import datetime as dt

from . import grades, l2
from .common import BR

FRAMES = ('대한명궁', '대한삼방', '본명삼방')
HUAS = ('록', '권', '과', '기')


def _s(x):
    """어떤 값이든 한 줄 글로."""
    if x is None:
        return '-'
    if isinstance(x, bool):
        return '예' if x else '아니오'
    if isinstance(x, dict):
        return ', '.join('%s:%s' % (k, _s(v)) for k, v in x.items()) or '-'
    if isinstance(x, (list, tuple, set)):
        return ', '.join(_s(v) for v in x) or '-'
    return str(x)


def _t(x):
    """시각 글을 분 단위까지."""
    return str(x)[:16].replace('T', ' ') if x else '-'


def _items(x):
    """[[이름, 궁, 밝기], ...] 꼴을 '이름 궁 밝기, ...'로."""
    return ', '.join(' '.join(_s(e) if e is not None else '-' for e in it) if isinstance(it, (list, tuple)) else _s(it) for it in x) or '-'


def _c(x):
    """표 칸에 넣을 글(세로줄과 줄바꿈 제거)."""
    return _s(x).replace('|', '/').replace('\n', ' ')


def _table(head, rows):
    out = ['| ' + ' | '.join(head) + ' |', '|' + '|'.join('---' for _ in head) + '|']
    out += ['| ' + ' | '.join(_c(c) for c in r) + ' |' for r in rows]
    return out


def table_from_file(path):
    with open(path, encoding='utf-8') as f:
        lines = f.read().splitlines()
    out, on = [], False
    for ln in lines:
        if ln.startswith('|'):
            out.append(ln)
            on = True
        elif on:
            break
    return '\n'.join(out)


def _star(s):
    g = s.get('grade') or s.get('cls') or ''
    t = s['name'] + (' ' + g if g and g != '미확인' else '')
    return t + (' [화%s]' % s['hua'] if s.get('hua') else '')


# ---- 1절 ----
def _sec1(R):
    ch = R['chart']
    b = ch['birth']
    inp = b['input']
    lu = b['lunar']
    sj = b['saju']
    o = ['## 1. 명반', '', '### 입력']
    o += _table(['항목', '값'], [
        ('양력 입력', '%s %s %s' % (inp['date'], inp['time'], '남' if inp['male'] else '여')),
        ('진태양시 보정(분)', inp['solar_offset_min']),
        ('시계 시각 / 진태양시', '%s / %s' % (_t(b['clock']), _t(b['solar']))),
        ('시계 UTC 오프셋', inp['tz']),
        ('음력', '%s년 %s월 %s일%s (명반 월 %s)' % (lu['year'], lu['month'], lu['day'], ' 윤달' if lu['leap'] else '', lu['chart_month'])),
        ('시지', b['hour_branch']),
        ('가정(미확인)', b.get('assumptions')),
    ])
    o += ['', '### 사주 네 기둥']
    o += _table(['년', '월', '일', '시'], [(sj['year'], sj['month'], sj['day'], sj['hour'])])
    o += ['', '앞 節 %s %s, 뒤 節 %s %s.' % (b['jie_prev']['name'], _t(b['jie_prev']['at']), b['jie_next']['name'], _t(b['jie_next']['at']))]
    o += ['', '### 명궁과 신궁, 국']
    o += _table(['명궁', '신궁(궁)', '국', '命主', '身主', '대한 방향', '사화표'],
                [(ch['ming'], '%s(%s)' % (ch['shen'], ch.get('shen_role', '-')), ch['ju_name'], ch.get('mingzhu'),
                  ch.get('shenzhu'), ch.get('direction'), ch.get('sihua_variant'))])
    bh = ch.get('birth_hua', {})
    o += ['', '생년 사화(%s): %s.' % (ch.get('year_gz', ''), ', '.join('화%s %s(%s)' % (h, bh[h]['star'], bh[h]['palace']) for h in HUAS if h in bh))]
    kg = ch.get('kong', {})
    o += ['', '공망: ' + ', '.join('%s %s' % (k, _s(v)) for k, v in kg.items()) + '.']
    o += ['', '### 열두 궁의 별 (별 이름 뒤는 밝기, [화X]는 생년 사화)']
    rows = []
    for z in BR:
        p = ch['palaces'][z]
        mains = [_star(s) for s in p['stars'] if s['kind'] == '주성']
        others = [_star(s) for s in p['stars'] if s['kind'] != '주성']
        rows.append((z, p['role'], p['stem'], p.get('changsheng'), ', '.join(mains) or '-', ', '.join(others) or '-'))
    o += _table(['지지', '궁', '궁간', '십이장생', '주성', '보좌·살·잡성'], rows)
    o += ['', '### 대한 표 (자미 10년 궁)']
    o += _table(['n', '궁', '궁 이름', '만 나이', '시작', '끝'],
                [(d['n'], d['palace'], d['natal_role'], '%s-%s' % (d['age_from'], d['age_to']), _t(d['start']), _t(d['end'])) for d in R['daehan']])
    dw = R['daewoon']
    o += ['', '### 대운 표 (사주 10년, %s, 대운수 %.2f년)' % (dw['direction'], dw['years'])]
    pre = dw.get('pre') or {}
    o += ['', '첫 대운 전: %s ~ %s. %s' % (_t(pre.get('start')), _t(pre.get('end')), pre.get('note') or ''), '']
    o += _table(['n', '간지', '시작', '끝', '시작 나이'],
                [(p['n'], p['gz'], _t(p['start']), _t(p['end']), '%.2f' % p['age_start']) for p in dw['periods']])
    return o


# ---- 2절 ----
def _sec2(R):
    l1 = R['l1']
    o = ['## 2. 구조 판독(L1)', '', '- 공궁: %s' % _s(l1.get('empty')), '', '### 공궁과 차성']
    rows = []
    for k, v in (l1.get('pairs') or {}).items():
        stars = ''
        if v.get('status') == '성립':
            for b in l1.get('borrow_established', []):
                if b['pair'] == k:
                    stars = ', '.join('%s(%s)' % (s['name'], s.get('cls')) for s in b['stars'])
        rows.append((k, v.get('status'), v.get('sender'), v.get('receiver'), v.get('kong'), v.get('confirmed'),
                     v.get('relation') if v.get('status') == '차단' else '', stars))
    o += _table(['쌍', '상태', '보내는 궁', '받는 궁', '공망', '확인', '관계(차단)', '차성한 별'], rows)
    o += ['', '제화: ' + ('; '.join('%s궁 %s(공망 %s)' % (x['palace'], x['star'], _s(x.get('kong'))) for x in l1.get('jehwa', [])) or '-')]
    o += ['', '협(양옆 짝별): ' + ('; '.join('%s궁 %s(양옆 %s)' % (x['palace'], '·'.join(x['pair']), ', '.join('%s %s' % kv for kv in x['sides'].items())) for x in l1.get('jia', [])) or '-')]
    ns = l1.get('natal_sanfang', {})
    o += ['', '### 본명 삼방사정 분포']
    o += _table(['항목', '값'], [('궁' if k == 'palaces' else k, _items(v) if k != 'palaces' else _s(v)) for k, v in ns.items()])
    lu = l1.get('lu', {})
    bl = lu.get('birth_lu', {})
    sl = lu.get('stems_lu_into_sanfang') or []
    o += ['', '### 록의 자리', '',
          '생년 화록: %s(%s), 본명 삼방사정 안: %s.' % (bl.get('star'), bl.get('palace'), _s(bl.get('in_natal_sanfang'))), '',
          '화록이 본명 삼방사정에 드는 천간: ' + (', '.join('%s(%s %s)' % (x['stem'], x['star'], _s(x['palaces'])) for x in sl) or '-') + '.']
    gk = l1.get('gyeok', {})
    o += ['', '### 격', '', '기본격 성립: %s. 명궁 주성: %s.' % (_s(gk.get('basic')), _s(gk.get('ming_stars')))]
    hw = gk.get('hwatam')
    if hw is not None:
        if hw.get('form'):
            rs = '; '.join('%s %s(%s)%s' % (r.get('kind'), r.get('star'), r.get('palace'), (' ' + r['grade']) if r.get('grade') else '') for r in hw.get('reasons') or [])
            o += ['', '화탐격(R25): 형태 성립(%s궁). 온전함: %s.%s' % (hw.get('palace'), _s(hw.get('complete')), (' 까닭: ' + rs + '.') if rs else '')]
        else:
            o += ['', '화탐격(R25): 형태 아님(탐랑·화성 동궁 아님). 온전함: 미적용.']
    mv = l1.get('ming_volatile_detail')
    if mv is not None:
        o += ['', '명궁 주성 파군·탐랑(R26): %s. 해당 별: %s, 경로: %s.%s' % (_s(mv.get('value')), _s(mv.get('stars')), _s(mv.get('via')), (' ' + mv['note']) if mv.get('note') else '')]
    o += ['', '### 수용성 (하나도 못 받는 주성 m / 주성 n)']
    rp = l1.get('receptivity', {})
    rows = []
    for z in BR:
        q = (rp.get('by_palace') or {}).get(z)
        if q:
            rows.append((z, '%s/%s' % (q['none_count'], q['main_total']), ', '.join(q.get('none_stars') or []) or '-',
                         ', '.join(q.get('hua_kinds') or []) or '-'))
    o += _table(['궁', 'm/n', '못 받는 별', '받는 사화 종류'], rows)
    nsr = rp.get('natal_sanfang', {})
    o += ['', '본명 삼방사정: 못 받는 %s / 주성 %s.' % (nsr.get('none_count'), nsr.get('main_total'))]
    br = l1.get('brightness', {})
    o += ['', '밝기 지도: 궁별 ' + _s(br.get('palace')) + '. 집계 ' + _s(br.get('groups')) + '.']
    if br.get('hua_on_weak'):
        o += ['', '약한 자리의 사화: ' + _s(br['hua_on_weak']) + '.']
    o += ['', '### 변곡점']
    o += _table(['종류', '궁'], [(k, v) for k, v in (l1.get('inflection') or {}).items()])
    return o


# ---- 3절 ----
def _txt(p):
    """표에 싣는 글귀. 가지로 나눈 문장(#n)은 그 가지의 글귀만(명세 5절 12번 바), 앞 행을 이은 구절(joins)은 이은 문장 전체(사)."""
    if '#' in p['id']:
        return p.get('clause') or p['result']
    return (p.get('text_full') or p['text']) if p.get('joins') else p['text']


def _sec3(R, passages):
    ev = dict(l2.evaluate(R, passages))
    ev.update(l2.evaluate_j3(R))
    text = {p['id']: _txt(p) for p in passages}
    text.update({p['id']: _txt(p) for p in l2.load_passages(l2.DATA3)})
    enum = lambda it: ', '.join('%d/%d' % (e['k'], e['n']) for e in it.get('enum', []))
    labels = ('명궁', '신궁') + tuple(r + '궁' for r in l2.ROLES)
    keys = ('명궁', '신궁') + tuple(l2.ROLES)
    o = ['## 3. 궁별 글귀 판정(L2)', '',
         '명궁과 신궁은 권3 별별 해설(入命 구절, 안명·좌명·수명은 명궁만, 身命과 별의 성질 서술은 명궁과 신궁)의 표로, 나머지 열한 궁(%s)은 권4 궁별 구절표로 검사한다. 남명반에서 女命 구절은 검사하지 않고 수만 센다. 아래 표는 선 구절(선다)과 반만 선 구절(반만)만 적는다. 선 조건/조건은 구절의 조건 가운데 이 명반에서 선 것의 수다.' % ', '.join(l2.ROLES), '']
    rows = []
    for role in keys:
        v = ev[role]
        its = v['passages']
        g = lambda pol, vd: sum(1 for it in its if it['polarity'] == pol and it['verdict'] == vd)
        rows.append((role, v['palace'], g('길', '선다'), g('흉', '선다'), g('길', '반만'), g('흉', '반만'),
                     sum(1 for it in its if it['verdict'] == '서지 않는다'), sum(1 for it in its if it['verdict'] == '성질'), len(v['unparsed']),
                     '%s / %s' % (v['summary']['조건충족합']['길'], v['summary']['조건충족합']['흉'])))
    o += ['### 궁별 집계']
    o += _table(['궁', '지지', '길 선다', '흉 선다', '길 반만', '흉 반만', '서지 않는 구절', '성질 서술', '해독 못 한 구절', '조건 충족 합(길 / 흉)'], rows)
    o += ['', '길·흉은 구절 원문의 길흉 표지다. 중·미정 구절과 성질 서술(조건이 없는 별의 성질 글귀)은 길흉 집계에 넣지 않는다. 열거 칸은 값이 둘 이상인 열거 조건(길성·살 목록 등)에서 이 명반에 있는 수/든 수다. 판정에는 쓰지 않고 하나 이상이면 선다. 해독 못 한 구절은 조건표로 옮기지 못해 검사하지 않은 구절의 수다.', '']
    for role, lab in zip(keys, labels):
        v = ev[role]
        o += ['### %s (%s)' % (lab, v['palace']), '']
        if '여명구절수' in v and v['여명구절수']:
            o += ['남명반이라 女命 구절 %d개는 검사하지 않았다.' % v['여명구절수'], '']
        shown = [it for it in v['passages'] if it['verdict'] not in ('서지 않는다', '성질')]
        if shown:
            rank = {'흉': 0, '길': 1}
            shown.sort(key=lambda it: (0 if it['verdict'] == '선다' else 1, rank.get(it['polarity'], 2)))
            o += _table(['id', '원문', '선 조건/조건', '열거', '길흉', '판정'],
                        [(it['id'], text.get(it['id'], ''), '%d/%d' % (it['met'], it['total']), enum(it), it['polarity'], it['verdict']) for it in shown])
        else:
            o.append('선 구절과 반만 선 구절이 없다.')
        nat = [it for it in v['passages'] if it['verdict'] == '성질']
        if nat:
            o += ['', '별의 성질 서술(조건이 없어 선다로 세지 않는다)', '']
            o += _table(['id', '원문', '길흉'], [(it['id'], text.get(it['id'], ''), it['polarity']) for it in nat])
        o.append('')
    return o


# ---- 4절 ----
def _sec4(R):
    gs = grades.evaluate(R)
    o = ['## 4. 등급 (권2 十等論·一十四等訣)', '',
         '표제 사이의 위아래는 원문에 없어 매기지 않는다. 반만 이상 선 표제만 적고 나머지는 수만 적는다. met/total은 선 조건 수/조건 수다.', '']
    groups = {}
    for x in gs:
        groups.setdefault(x['id'].split(':')[0], []).append(x)
    for name in ('十等', '十四等'):
        items = groups.get(name, [])
        shown = [x for x in items if x['verdict'] != '서지 않는다']
        o += ['### %s' % name, '',
              '검사한 표제 %d, 선다 %d, 반만 %d, 서지 않는다 %d.' % (
                  len(items), sum(1 for x in items if x['verdict'] == '선다'), sum(1 for x in items if x['verdict'] == '반만'),
                  len(items) - len(shown))]
        if shown:
            o += ['']
            o += _table(['id', '표제', 'met/total', '길흉', '판정', '있는 별', '없는 별'],
                        [(x['id'], x['title'], '%d/%d' % (x['met'], x['total']), x['polarity'], x['verdict'],
                          ', '.join(x['present']) or '-', ', '.join(x['absent']) or '-') for x in shown])
        o.append('')
    o += ['조건표로 옮기지 못해 검사하지 않은 표제 %d.' % len(grades.unparsed()), '']
    return o


# ---- 5절 ----
def _sec5(R, years):
    l3 = R['l3']
    o = ['## 5. 운(L3)', '', '### 대한별 노출도 (k/10)', '',
         '틀마다 록·권·과·기를 붙이는 천간 수/10. 화기 중첩은 그 틀에서 화기 중첩이 선 해의 수. 수용성 m/n은 대한 삼방사정 주성 n 가운데 사화를 하나도 받지 못하는 별 m. 중첩 록/권/과는 R22 중첩이 선 천간 수(10 중).', '']
    pd = {p['n']: p for p in l3['path_daehan']}
    rows = []
    for d in l3['exposure']['daehan']:
        rc = pd[d['n']]['receptivity']
        oy = d['overlap_years']['by_hua']
        for i, f in enumerate(FRAMES):
            fr = d['frames'][f]
            rows.append((d['palace'], f, *['%d/%d' % (fr[h]['k'], fr[h]['of']) for h in HUAS], fr['기'].get('overlap_k', '-'),
                         '%s/%s' % (rc['none_count'], rc['main_total']) if f == '대한삼방' else '',
                         '%s/%s/%s' % (oy.get('록', 0), oy.get('권', 0), oy.get('과', 0)) if i == 0 else ''))
    o += _table(['대한', '틀', '록', '권', '과', '기', '화기 중첩', '수용성 m/n', '중첩 록/권/과'], rows)
    dh = []
    for d in l3['exposure']['daehan']:
        c = d['frames'].get('대한삼방', {})
        gi, gw = c.get('기', {}), c.get('과', {})
        if 'daehyung' in gi or 'k_effective' in gw:
            dh.append((d['palace'], gi.get('overlap_k', '-'), '표지' if gi.get('daehyung') else '-', '예' if gi.get('beyond_text') else '-',
                       '%s/%s' % (gw.get('k_effective'), gw.get('k')) if gw.get('k_effective') is not None else '-', _s(gw.get('void_confirmed')) or '-'))
    if dh:
        o += ['', '대한삼방 화기 중첩 표지(자붕이 3488~3492, 3/10 명문)와 화과 k_effective(R16, 화기와 만나 무효로 확인된 천간 제외).', '']
        o += _table(['대한', '화기 중첩 k', 'daehyung', '3 초과', '화과 k_effective/k', '무효 확인 천간'], dh)
    nat = l3['exposure']['natal']['본명삼방']
    o += ['', '본명 삼방사정만: ' + ', '.join('%s %d/%d' % (h, nat[h]['k'], nat[h]['of']) for h in HUAS) + ', 화기 중첩 %s.' % nat['기'].get('overlap_k', '-')]
    o += ['', '### 해마다 표 (출생 뒤 대한 일곱 구간)', '',
          '화기: 세운 천간의 화기 별(궁)과 그것이 든 틀. 대한 틀 중첩: 그 해에 화기 중첩이 선 대한 쪽 틀(쌍 단위는 쌍 이름). 구조 표지는 구조 통변 읽기, 비춤 표지는 대한 삼방 비춤 읽기의 표지. 갈림은 두 틀이 다르게 읽은 항목. 록·권: 그 해 화록·화권 별이 드는 틀. 해 뒤 *는 그 해의 일부만 이 대한에 드는 것.', '']
    lo, hi = years if years else (None, None)
    for p in l3['path_daehan'][:7]:
        ji = p['ji_counts']
        rows = []
        for y in p['years']:
            yy = y['year']
            if (lo is not None and yy < lo) or (hi is not None and yy > hi):
                continue
            ov = [f for f in ('대한명궁', '대한삼방') if yy in ji.get(f, [])] + [u + '쌍' for u, ys in (ji.get('쌍') or {}).items() if yy in ys]
            j = y['ji']
            lg = ', '.join('%s %s(%s)' % (e['hua'], e['star'], '/'.join(e['frames']) or '틀 밖') for e in y['lu_gwon']) or '-'
            rows.append(('%s%s' % (yy, '*' if y.get('partial') else ''), y['gz'], '%s(%s) %s' % (j['star'], j['palace'], '/'.join(j['frames']) or '틀 밖'),
                         '/'.join(ov) or '-', (j.get('structural') or {}).get('label'), (j.get('gaze') or {}).get('label', '-'),
                         ', '.join(g['type'] for g in y['galim']) or '-', lg))
        if rows:
            o += ['#### %s 대한 (%s ~ %s)' % (p['palace'], _t(p['start'])[:10], _t(p['end'])[:10]), '']
            o += _table(['해', '간지', '화기', '대한 틀 중첩', '구조 표지', '비춤 표지', '갈림', '록·권(드는 틀)'], rows)
            o.append('')
    o += _sec5_limit(R)
    return o


def _sec5_limit(R):
    """대한별 入限 구절(명세 11-2). l2.evaluate_limit의 출력 값만 옮긴다. 대한의 길흉 판정(노출도, 화기 중첩)과 합치지 않고 나란히 둔다."""
    o = ['### 대한별 入限 구절 (전서 권3 限, 명세 11-2)', '',
         '대한 명궁에 권3 限(운) 구절 가운데 大限에 적용되는 구절을 L2와 같은 조건 종류로 검사한 것이다(출생 뒤 대한 일곱 구간). 선다와 반만 선 구절만 적는다. 선 조건/조건과 열거는 3절과 같다. '
         '유형은 원문의 한도 낱말(大限명시, 大小限, 二限, 限통칭, 更 이음)이다. 二限과 限통칭은 小限도 가리키는 말이나 大限이 만날 때도 성립하는 말로 읽어 검사했다. '
         '小限이나 太歲를 조건으로 든 구절은 틀 밖이라 검사하지 않았다(小限 안성은 넣지 않았다). 해독 못 한 구절은 조건표로 옮기지 못한 구절 가운데 주체 별이 이 대한 명궁에 든 것의 수다. '
         '위 노출도·화기 중첩 표와 합치거나 가중하지 않고 나란히 둔다. 구절 차례는 선다, 반만, 동궁 조건만인 구절, 삼방을 든 구절, 흉, 길, 원문 행 번호 순이다.', '']
    for i, d in enumerate(R['daehan'][:7]):
        e = l2.evaluate_limit(R, i)
        its = e['passages']
        shown = [it for it in its if it['verdict'] in ('선다', '반만')]
        cnt = lambda v: sum(1 for it in its if it['verdict'] == v)
        o += ['#### %s 대한 (%s, 만 %s-%s세)' % (e['palace'], d['natal_role'], d['age_from'], d['age_to']), '',
              '선다 %d, 반만 %d, 서지 않는 구절 %d, 해독 못 한 구절 %d, 틀 밖 %d.' % (cnt('선다'), cnt('반만'), cnt('서지 않는다'), len(e['unparsed']), len(e['outside'])), '']
        if shown:
            o += _table(['id', '원문', '선 조건/조건', '열거', '길흉', '판정', '유형'],
                        [(it['id'], it['text'], '%d/%d' % (it['met'], it['total']), ', '.join('%d/%d' % (x['k'], x['n']) for x in it.get('enum', [])),
                          it['polarity'], it['verdict'], it['limit_kind']) for it in shown])
        else:
            o.append('선 구절과 반만 선 구절이 없다.')
        o.append('')
    ev = l2.evaluate(R)
    text = {p['id']: p['text'] for p in l2.load_passages()}
    hn = [(role, it['id'], text.get(it['id'], ''), it['verdict'], it['half_note']) for role in l2.ROLES for it in ev[role]['passages'] if it.get('half_note')]
    o += ['#### 減半 노트 (전서 권4 형제·자녀, 명세 11-2 3번)', '',
          '減半이 든 구절이 그 궁에서 서면 그 구절 곁에 적은 글이다. 수를 곱하거나 합산하지 않는다.', '']
    if hn:
        o += _table(['궁', 'id', '원문', '판정', '노트'], hn)
    else:
        o.append('이 명반에서 선 減半 구절이 없다.')
    o.append('')
    return o


# ---- 6절 ----
def _sec6(table):
    return ['## 6. 능력 차례', '', table.strip(), '']


# ---- 7절 ----
_POLICY = {'합치': '본문에 쓴다', '상충': '본문에서 빼고 기록만 남긴다', '혼재': '자미두수의 길 구절과 흉 구절을 함께 적은 곁에 쓴다',
           '무대응': '"사주 보완"으로 쓴다', '구간 갈림': '상충 구간이 있어 본문에서 빼고 구간별로 기록만 남긴다',
           '제외': '격이 온전하지 않아 결과 구절을 쓰지 않는다'}


def _zami_value(r):
    """대조표의 '자미두수 값' 칸. 엔진 출력에서 옮긴 값만 적는다."""
    if r.get('구간'):
        return '; '.join('%s 대한 %s(길 %s, 흉 %s)' % (s['대한'], s['값'], ', '.join(s['길']) or '-', ', '.join(s['흉']) or '-') for s in r['구간'])
    zv = r.get('자미_값')
    if not zv:
        return '-'
    if '궁별' in zv:
        per = ['%s 길%d 흉%d%s' % (p, len(v['길']), len(v['흉']), '(자붕이 명시 %s)' % v['명시'] if v.get('명시') else '') for p, v in zv['궁별'].items()]
        return '%s: %s' % (zv['값'], ', '.join(per))
    return ', '.join('%s(%s)' % (w, p or '극 모름') for w, p in zv.get('낱말', [])) or '-'


def _sec7(R):
    from . import align
    data = align.load_judgments()
    meta = {j['id']: j for j in data['판정']}
    rows = align.align(R)
    tl = align.tally(rows)
    o = ['## 7. 사주 층', '',
         '사주 판정(data/saju_judgments.json)과 자미두수 값(2·3·5절)을 같은 영역, 같은 시기, 같은 방향으로 견준 대조표다(명세 10절 6번, 11-1절). 사주는 %s. 자미두수 값은 이 문서 2·3·5절의 값과 같다. 길흉은 선 구절(선다)에 길과 흉이 있는지만 보고 수를 견주지 않는다. 성질은 선 구절과 성질 서술의 결과 낱말을 data/trait_lexicon.json의 (범주, 극)으로 맞춘다. 자붕이의 명시 판정은 명세 5절 11번의 넷(%s)에 한해 그 값을 쓴다. 대운은 대한 구간마다 보고 구간이 둘 이상이면서 상충이 하나라도 있으면 구간 갈림이다.' % (
             data['명식']['사주'], ', '.join(sorted(align.zabungi_explicit(R))) or '이 명반에서는 조건이 서지 않음'), '',
         '결과 수: ' + ', '.join('%s %d' % (k, tl[k]) for k in ('합치', '상충', '혼재', '무대응', '구간 갈림', '제외') if tl.get(k)) + '. 줄은 판정 하나가 범주나 시기마다 갈라진 것이다.', '']
    body = []
    for r in rows:
        j = meta[r['판정_id']]
        body.append((r['판정_id'], j['제목'], '; '.join('%s:%s' % ('/'.join(s['파일'].split('/')[-2:]), s['행']) for s in j['출전'] if s['구실'] in ('본문', '명례')),
                     j['신빙성'], r['영역'], r['시기'], r['방향'], ', '.join(r['견준_궁']) or '-', _zami_value(r),
                     ', '.join(r['근거_구절_id'][:6]) + (' 외' if len(r['근거_구절_id']) > 6 else '') or '-', ', '.join(r['맞은_낱말']) or '-', r['결과'],
                     _POLICY[r['결과']] + (' (추정형)' if r['결과'] == '무대응' and j['신빙성'] in ('후대', '월령격') else '')
                     + (' (미확인 조건이 있어 단정하지 않는다)' if any(str(b).startswith('미확인 조건') for b in r.get('비고') or []) else '')))
    o += _table(['판정', '사주 판정', '출전(01_raw 폴더/파일:행)', '신빙성', '영역', '시기', '방향', '견준 궁', '자미두수 값', '근거 구절 id', '맞은 낱말', '결과', '처리'], body)
    o += ['', '### 격의 형태와 온전함', '']
    gy = [(j['id'], j['격']['이름'], j['격']['형태'], j['격']['온전함'], '; '.join(j['격']['서지_않는_조건']) or '-', '; '.join(j['격']['미확인_조건']) or '-') for j in data['판정'] if j.get('격')]
    o += _table(['판정', '격', '형태', '온전함', '서지 않는 조건', '미확인 조건'], gy)
    o.append('')
    return o


def default_cmd(result):
    """결과를 다시 낼 명령. 기본값과 다른 선택만 붙인다(__main__의 기본값과 같아야 한다)."""
    inp = result['chart']['birth']['input']
    opt = result.get('options') or {}
    cmd = 'python -m engine_v2 %s %s %s --solar-offset %s' % (inp['date'], inp['time'], 'M' if inp['male'] else 'F', inp['solar_offset_min'])
    for flag, val, default in (('--tz', inp.get('tz', 9), 9), ('--sihua', opt.get('sihua'), None),
                               ('--zi-rule', inp.get('zi_rule', 'next_day'), 'next_day'), ('--leap-rule', inp.get('leap_rule', 'same'), 'same'),
                               ('--seun-boundary', opt.get('seun_boundary', 'lichun'), 'lichun')):
        if val != default:
            cmd += ' %s %s' % (flag, val)
    return cmd


def build(result, rank_table=None, cmd=None, years=None, today=None):
    if cmd is None:
        cmd = default_cmd(result)
    today = today or dt.date.today().isoformat()
    o = ['# 판정표 (engine_v2 출력)', '']
    o += _sec1(result) + [''] + _sec2(result) + [''] + _sec3(result, l2.load_passages()) + _sec4(result) + _sec5(result, years)
    if rank_table:
        o += _sec6(rank_table)
    o += _sec7(result)
    o += ['---', '', '생성: `%s`, %s' % (cmd, today), '']
    return '\n'.join(o)
