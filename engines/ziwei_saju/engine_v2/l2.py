"""L2 궁별 글귀 판정. 권4 궁별 열한 편의 구절(data/passages_j4.json)을 조건표로 검사한다.

입력은 engine_v2.compute()의 출력 dict. 명반 상수는 쓰지 않는다.
범위 낱말(명세 5절 10번): 加·同 = 동궁, 見·㑹 = 삼방과 대궁(본궁 제외), 遇 = 동궁과 삼방·대궁.
차성: l1.borrow_established의 별은 그 궁에 '있는' 주성으로 보되 동궁 조건에서는 채우지 않는다.
공궁이 차단이면(l1.borrow_blocked) 그 궁은 보내는 궁의 주성 구절을 쓰지 않는다.
새 조건 종류(명세 5절 12번, 11-3, 2026-11-18): 생년지지, 생시(日生·夜生), 대궁·삼합(범위 scope이자 값을 그 범위에서만 보는 종류), 협, 타궁별.
각 검사는 True/False/None(미확인)이고 None은 unknown에 적힌다. 범위 '대궁'은 대궁 하나, '삼합'은 삼방에서 본궁과 대궁을 뺀 두 궁이다.
"""
import json
import os

from .common import MAIN14, sanfang

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'passages_j4.json')
DATA3 = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'passages_j3.json')
HUA_NAME = {'화록': '록', '화권': '권', '화과': '과', '화기': '기'}
ROLES = ('형제', '부처', '자녀', '재백', '질액', '천이', '노복', '관록', '전택', '복덕', '부모')
_CACHE = {}


def load_passages(path=None):
    path = path or DATA
    if path not in _CACHE:
        with open(path, encoding='utf-8') as f:
            _CACHE[path] = json.load(f)
    return _CACHE[path]


def _scope_palaces(z, scope):
    sf = sanfang(z)          # [본궁, 대궁, 재백 자리, 관록 자리]
    if scope == '동궁':
        return [z]
    if scope == '삼방대궁':
        return sf[1:]
    if scope == '대궁':
        return [sf[1]]
    if scope == '삼합':          # 삼방에서 대궁(과 본궁)을 뺀 두 궁
        return sf[2:]
    return sf                # 동궁삼방대궁


class _Ctx:
    def __init__(self, result):
        self.r = result
        self.chart = result['chart']
        self.pal = self.chart['palaces']
        l1 = result.get('l1', {})
        self.borrowed = {}   # 받는 궁 -> {별: cls}
        for b in l1.get('borrow_established', []) or []:
            self.borrowed[b['receiver']] = {s['name']: s.get('cls') for s in b['stars']}
        self.blocked = {b['receiver'] for b in l1.get('borrow_blocked', []) or []}
        k = self.chart.get('kong', {})
        self.kong = {n: set(_as_list(k.get('정_' + n))) for n in ('절공', '순공')}

    def role_palace(self, role):
        for z, p in self.pal.items():
            if p['role'] == role:
                return z

    def stars(self, z):
        return self.pal[z]['stars']

    def names(self, z):
        return {s['name'] for s in self.stars(z)}

    def mains(self, z):
        """(own 주성 {이름: cls}, 차성 {이름: cls})"""
        own = {s['name']: s['cls'] for s in self.stars(z) if s['kind'] == '주성'}
        return own, ({} if own else dict(self.borrowed.get(z, {})))


def _as_list(x):
    if x is None:
        return []
    return list(x) if isinstance(x, (list, tuple, set)) else [x]


def _vals_text(v):
    if isinstance(v, dict):      # 타궁별: {궁 이름: [별...]}
        return ';'.join('%s:%s' % (k, '/'.join(x)) for k, x in v.items())
    return ','.join(v)


def _desc(c):
    sc = c.get('scope')
    return ('없음 ' if c.get('negate') else '') + c['kind'] + (':' + sc if sc else '') + '(' + _vals_text(c['values']) + ')'


# 새 종류(2026-11-18). 일생·야생은 명세 11-3 3번: 辰巳午未 낮, 戌亥子丑 밤, 寅卯申酉 미확인
DAY_BR, NIGHT_BR = frozenset('辰巳午未'), frozenset('戌亥子丑')
PRESENCE_KINDS = ('동궁', '삼방대궁', '살', '길', '공망', '대궁', '삼합')   # 별 이름이 범위 안에 있는지 보는 종류


def _cscope(c):
    """조건의 범위. 값 `only: 대궁`(권4 子:74#3, 子:79#1)은 대궁 하나만 본다."""
    if c['kind'] in ('대궁', '삼합'):
        return c['kind']
    if c.get('only') == '대궁':
        return '대궁'
    return c.get('scope', '동궁')


def day_night(ctx):
    """출생 시지로 '日生' | '夜生' | None(寅卯申酉나 시지 없음)"""
    hb = ctx.chart.get('birth', {}).get('hour_branch') or ctx.chart.get('hour_branch')
    return '日生' if hb in DAY_BR else ('夜生' if hb in NIGHT_BR else None)


def _check(ctx, z, p, c):
    """-> (충족 여부 True/False/None(미확인))"""
    kind, vals, scope = c['kind'], c['values'], _cscope(c)
    if kind in PRESENCE_KINDS and not c.get('role'):
        vals = _excl(p, vals)
    got = None
    if c.get('pair'):                       # 짝별(R28): 모두 있어야 한다
        got = all(any(v in ctx.names(q) for q in _scope_palaces(z, '동궁삼방대궁')) for v in vals)
        return 'half' if got else False
    if kind in PRESENCE_KINDS:
        pals = _scope_palaces(z, scope)
        if kind in ('대궁', '삼합') and any(q not in ctx.pal for q in pals):
            return None                                  # 그 범위의 궁 자료가 없다(미확인)
        if kind in ('대궁', '삼합') and vals == ['주성']:     # 그 범위에 주성이 하나라도 있다
            got = any(s['kind'] == '주성' for q in pals for s in ctx.stars(q))
        elif kind == '동궁' and vals == ['주성']:        # 獨守: 다른 주성이 없다(주체 별 자신은 뺀다)
            subj = set(_as_list(p.get('star')))
            got = any(s['kind'] == '주성' and s['name'] not in subj for s in ctx.stars(z))
        elif c.get('all') and not c.get('negate'):   # 묶음 구문(명세 5절 12번 가): 든 별이 모두 있어야 선다
            got = all(_present(ctx, pals, [v], kind) for v in vals)
            if not got and scope == '동궁':
                wide = _scope_palaces(z, '동궁삼방대궁')
                if all(_present(ctx, wide, [v], kind) for v in vals):
                    return 'half'
        else:
            got = _present(ctx, pals, vals, kind)
            if not got and scope == '동궁' and not c.get('negate'):
                # 동궁이 아니라 삼방·대궁에 있거나 차성한 별이면 반만
                if _present(ctx, _scope_palaces(z, '삼방대궁'), vals, kind):
                    return 'half'
                own, bor = ctx.mains(z)
                if kind == '동궁' and any(v in bor for v in vals):
                    return 'half'
    elif kind == '밝기':
        subj = _as_list(p.get('star'))
        own, bor = ctx.mains(z)
        pool = {s['name']: s['cls'] for s in ctx.stars(z)}; pool.update(bor)
        if c.get('of'):                      # 다른 궁에 있는 특정 별의 밝기(예: 太陽在陷宮)
            q = ctx.chart['pos'].get(c['of'])
            pool = {s['name']: s['cls'] for s in ctx.stars(q)} if q else {}
            subj = [c['of']]
        cand = [pool[n] for n in subj if n in pool] if subj else list(pool.values())
        if not cand:
            return False
        if any(x == vals[0] for x in cand):
            got = True
        elif any(x == '미확인' for x in cand):
            return None
        else:
            got = False
    elif kind == '궁지':
        got = z in vals
    elif kind == '생년간':
        got = (ctx.chart['birth'].get('year_stem') or ctx.chart['year_stem']) in vals
    elif kind == '성별':
        got = ctx.chart['male'] == (vals[0] == '남')
    elif kind == '생년지지':
        yz = (ctx.chart.get('year_gz') or '')[1:2]
        if not yz:
            return None
        got = yz in vals
    elif kind == '생시':
        dn = day_night(ctx)
        if dn is None:
            return None
        got = dn in vals
    elif kind == '협':          # 양옆 궁에 짝별이 하나씩. 계산은 grades._jia_ok(양옆 궁의 별 이름 집합)를 그대로 쓴다
        from .grades import _jia_ok
        sets = c.get('sets') or [vals]
        if not any(len(set(x)) >= 2 for x in sets):
            return None                                  # 짝이 안 되는 값은 검사할 수 없다
        got = _jia_ok(ctx, z, sets)
    elif kind == '남북두':       # 값 ['南'] 또는 ['北']: 범위(기본 三方四正) 안에서 그 무리의 별이 다른 무리보다 많다(같으면 아님)
        t = _nanbei()
        pals = _scope_palaces(z, c.get('scope') or '동궁삼방대궁')
        names = [n for q in pals for n in ctx.names(q)]
        ns, nb = sum(n in t['南斗'] for n in names), sum(n in t['北斗'] for n in names)
        got = ns > nb if vals[0] == '南' else nb > ns
    elif kind == '타궁별':       # 값 {궁 이름: [별...]}: 그 궁에 별이 있다(c['all']이면 모두)
        got = True
        for role, stars in vals.items():
            q = ctx.role_palace(role)
            if q is None:
                return None
            have = ctx.names(q)
            got = got and (all(x in have for x in stars) if c.get('all') else any(x in have for x in stars))
    else:
        return None
    return (not got) if c.get('negate') else got


_NB = {}


def _nanbei():
    """data/nanbeidou.json(전서 권3 별별 해설 머리의 南斗·北斗)"""
    if not _NB:
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'nanbeidou.json'), encoding='utf-8') as f:
            _NB.update(json.load(f))
    return _NB


def _excl(p, vals):
    """주체인 별 자신은 열거에서 세지 않는다(명세 5절 12번 다). 다 빠지면 원래 목록을 쓴다."""
    subj = set(_as_list(p.get('star')))
    new = [v for v in vals if v not in subj]
    return new or list(vals)


def _enum(ctx, z, p, c):
    """값이 둘 이상인 열거 조건의 {k, n, present}. 묶음(all)과 주체 조건은 세지 않는다."""
    if c.get('role') or c.get('all') or c['kind'] not in PRESENCE_KINDS:
        return None
    vals = _excl(p, c['values'])
    if len(vals) < 2:
        return None
    pals = _scope_palaces(z, _cscope(c))
    pres = [v for v in vals if _present(ctx, pals, [v], c['kind'])]
    return {'k': len(pres), 'n': len(vals), 'present': pres}


def _present(ctx, pals, vals, kind):
    for q in pals:
        for s in ctx.stars(q):
            if s['name'] in vals or (s.get('hua') and ('화' + s['hua']) in vals):
                return True
        if kind == '공망':
            for n in ('절공', '순공'):
                if n in vals and q in ctx.kong[n]:
                    return True
    return False


def _subject(ctx, z, p):
    """구절의 주체 별 -> 'own'(이 궁에 있음) | 'borrow'(차성) | None(해당 없음)"""
    subj = _as_list(p.get('star'))
    if subj and all(x in MAIN14 for x in subj):
        own, bor = ctx.mains(z)
        if any(x in own for x in subj):
            return 'own'
        return 'borrow' if any(x in bor for x in subj) else None
    return 'own'


def _same(a, b):
    f = lambda c: {k: v for k, v in c.items() if k not in ('word', '_inh')}
    return f(a) == f(b)


def _inherit(passages):
    """更·又·再로 시작하는 가지는 바로 앞 가지의 조건(주체 조건 포함)을 이어받는다(명세 5절 12번 아).
    앞 가지가 unparsed면 그 가지도 unparsed다."""
    by = {p['id']: p for p in passages}
    cache = {}

    def eff(p):
        if p['id'] in cache:
            return cache[p['id']]
        q = p
        prev = by.get(p.get('inherits')) if p.get('inherits') else None
        if prev is not None:
            pe = eff(prev)
            q = dict(p)
            if pe['parse'] == 'unparsed' or p['parse'] == 'unparsed':
                q['parse'] = 'unparsed'
                q['reason'] = p.get('reason') or '앞 가지(%s)가 unparsed' % prev['id']
            else:
                conds = [dict(c, _inh=True) for c in pe['conds']]
                conds += [c for c in p['conds'] if not any(_same(c, d) for d in conds)]
                q['conds'] = conds
        cache[p['id']] = q
        return q
    return [eff(p) for p in passages]


def evaluate_palace(ctx, z, passages, role):
    out, unparsed = [], []
    for p in passages:
        if p['palace'] != role:
            continue
        if p['parse'] == 'unparsed':
            # 주체 별이 이 궁에 없으면 이 명반에 걸리지 않으므로 해독 못 한 수에 넣지 않는다(2026-11-18)
            gate = [c for c in p.get('conds', []) if c.get('role') == '주체']
            if _subject(ctx, z, p) and all(_check(ctx, z, p, c) is not False for c in gate):
                unparsed.append({'id': p['id'], 'reason': p.get('reason')})
            continue
        sj = _subject(ctx, z, p)
        if sj is None:
            continue
        met, half, failed, unknown = 0, 0, [], []
        enum = []
        hard = False
        total = 0
        break_out = False
        if sj == 'borrow':                     # 차성한 주성: 이 궁의 별이 아니므로 반만 센다
            total += 1; half += 1; failed.append('주성이 차성(동궁 아님)')
        for c in p['conds']:
            if c.get('role') == '주체':         # 주체 별: 이 궁에 있으면 관문(세지 않음)
                ok = _check(ctx, z, p, c)
                if ok is True:
                    continue
                if not (ok == 'half' and c.get('pair')):
                    break_out = True
                    break
            else:
                ok = _check(ctx, z, p, c)
            e = _enum(ctx, z, p, c)
            if e:
                enum.append(e)
            total += 1
            if ok is False and (c.get('_inh') or c['kind'] in ('궁지', '생년간', '성별', '생년지지', '생시', '타궁별') or c.get('premise') or (c['kind'] == '동궁' and not c.get('negate'))):
                hard = True      # 명세 5절 12번 자: 동궁 조건의 별이 동궁에도 삼방·대궁·차성에도 없으면 다른 조건이 맞아도 서지 않는다
            if ok is True:
                met += 1
            elif ok == 'half':
                half += 1; failed.append(_desc(c) + ' [동궁 밖]')
            elif ok is None:
                unknown.append(_desc(c))
            else:
                failed.append(_desc(c))
        if break_out:
            continue
        nohit = total - met - half
        v = '선다' if met == total else ('반만' if (met > 0 or (half > 0 and nohit == 0)) else '서지 않는다')
        if hard:
            v = '서지 않는다'
        item = {'id': p['id'], 'verdict': v, 'met': met, 'half': half, 'total': total, 'failed': failed + unknown,
                'unknown': unknown, 'polarity': p['polarity'], 'enum': enum}
        if p.get('nature') and total == 0 and v == '선다':   # 조건 없는 읽는 법·성질 서술(명세 5절 12번 라·차): 선다로 세지 않는다
            item['verdict'] = '성질'
        if p.get('half') and v == '선다':      # 減半 구절(명세 11-2 3번): 수를 곱하지 않고 글만 곁에 적는다
            item['half_note'] = p['half']['note']
        out.append(item)
    return out, unparsed


def summarize(items):
    nature = sum(1 for it in items if it['verdict'] == '성질')
    items = [it for it in items if it['verdict'] != '성질']
    s = {'길': {'선다': 0, '반만': 0, 'met': 0, 'total': 0}, '흉': {'선다': 0, '반만': 0, 'met': 0, 'total': 0},
         '중': 0, '미정': 0}
    for it in items:
        pol = it['polarity']
        if pol in ('길', '흉'):
            if it['verdict'] in ('선다', '반만'):
                s[pol][it['verdict']] += 1
            s[pol]['met'] += it['met']
            s[pol]['total'] += it['total']
        elif it['verdict'] != '서지 않는다':
            s[pol] += 1
    s['성질서술'] = nature
    s['길구절수'] = s['길']['선다']
    s['흉구절수'] = s['흉']['선다']
    s['조건충족합'] = {'길': '%d/%d' % (s['길']['met'], s['길']['total']), '흉': '%d/%d' % (s['흉']['met'], s['흉']['total'])}
    return s


def _subject3(ctx, z, p):
    """권3 구절의 주체 별이 이 궁에 있는가(별 이름·사화 이름·차성)"""
    subj = _as_list(p.get('star'))
    if not subj:
        return True
    if all(x in MAIN14 for x in subj):
        return _subject(ctx, z, p) is not None
    have = set(ctx.names(z)) | {'화' + s['hua'] for s in ctx.stars(z) if s.get('hua')}
    return any(x in have for x in subj)


def evaluate_j3(result, passages3=None):
    """권3 별별 해설(入命 구절)로 명궁과 신궁을 판정한다. 명세 5절 8번: 安命·坐命·守命은 명궁만, 身命과 별의 성질 서술은 명궁과 신궁.
    남명반은 女命 구절을 검사하지 않고 수만 센다. 限(운) 구절은 판정 대상이 아니다."""
    passages3 = _inherit(passages3 if passages3 is not None else load_passages(DATA3))
    ctx = _Ctx(result)
    male = bool(ctx.chart['male'])
    out = {}
    for name, z, cps in (('명궁', ctx.role_palace('명'), ('명', '명신', '성질')), ('신궁', ctx.chart['shen'], ('명신', '성질'))):
        ps = [p for p in passages3 if p['scope'] != '限' and _subject3(ctx, z, p)
              and (p['parse'] == 'unparsed' or p.get('cond_palace') in cps)]
        main = [p for p in ps if p['scope'] == '命']
        fem = [p for p in ps if p['scope'] == '女命']
        use = main + ([] if male else fem)
        items, unp = evaluate_palace(ctx, z, use, '명')
        cp = {p['id']: p.get('cond_palace') for p in use}
        for it in items:     # 조건이 없는 별의 성질 서술(cond_palace 성질)은 선다로 세지 않는다(명세 5절 12번 라).
            if it['total'] == 0 and it['verdict'] == '선다' and cp.get(it['id']) == '성질':   # 자리만 조건인 명·명신 구절은 결과 구절이다
                it['verdict'] = '성질'
        out[name] = {'palace': z, 'passages': items, 'unparsed': unp, 'summary': summarize(items),
                     '여명구절수': len(fem) if male else 0}
    return out


def evaluate(result, passages=None):
    """궁(역할)마다 {palace, passages:[{id, verdict, met, total, failed}], unparsed, summary}."""
    default = passages is None
    passages = _inherit(passages if passages is not None else load_passages())
    ctx = _Ctx(result)
    res = {}
    for role in ROLES:
        z = ctx.role_palace(role)
        items, unp = evaluate_palace(ctx, z, passages, role)
        res[role] = {'palace': z, 'passages': items, 'unparsed': unp, 'summary': summarize(items)}
    if default:
        res.update(evaluate_j3(result))
    return res


# ── 운(限) 구절 (명세 11-2, 2026-11-18) ───────────────────────────────────
def _expand_limit(passages3, kinds=None):
    """권3 限 구절의 limit 가지를 evaluate_palace가 읽는 구절 꼴로 편다(data/apply_limit_j3.py가 만든 limit 필드).
    -> (가지 목록, 옮기지 못한 구절 목록, 틀 밖 구절 목록, 종류 제외 수)"""
    enc, unp, out, skipped = [], [], [], 0
    for p in passages3:
        if p.get('scope') != '限':
            continue
        lim = p.get('limit')
        base = {'id': p['id'], 'line': p['line'], 'text': p['text'], 'star': p['star']}
        if not lim:
            unp.append(dict(base, reason='limit 필드 없음(data/apply_limit_j3.py를 돌리지 않았다)', type=None))
            continue
        if lim.get('frame') == '틀밖':
            out.append(dict(base, reason=lim.get('reason'), type=lim.get('type')))
            continue
        if not lim.get('branches'):
            unp.append(dict(base, reason=lim.get('reason'), type=lim.get('type')))
            continue
        if kinds is not None and lim.get('kind') not in kinds:
            skipped += 1
            continue
        for b in lim['branches']:
            q = {'id': b['id'], 'palace': '명', 'line': p['line'], 'text': p['text'], 'clause': b['clause'], 'result': b['clause'],
                 'star': b['star'], 'conds': b['conds'], 'polarity': b['polarity'], 'scope': '限',
                 'parse': 'unparsed' if b.get('unparsed') else 'manual', 'limit_kind': lim.get('kind'), 'limit_type': lim.get('type')}
            if b.get('nature'):
                q['nature'] = True
            if b.get('inherits'):
                q['inherits'] = b['inherits']
            if b.get('unparsed'):
                q['reason'] = b['unparsed']
            enc.append(q)
    return enc, unp, out, skipped


def _wide(q):
    """조건에 삼방·대궁·삼합 범위가 든 구절인가(구절 차례 11-2 4번의 '동궁 조건만인 구절'을 가른다)"""
    return any(c['kind'] in PRESENCE_KINDS and not c.get('role') and _cscope(c) != '동궁' for c in q['conds'])


def evaluate_limit(result, daehan_index, passages=None, kinds=None):
    """한 대한(result['daehan'][daehan_index], 0부터)의 대한 명궁에 권3 限 구절 가운데 大限에 적용되는 구절을 L2 방식으로 검사한다.
    小限·太歲 조건 구절(limit.frame '틀밖')은 검사하지 않고 outside에 적는다(11-2 2번). 사화 구절 따위 옮기지 못한 구절은 unparsed(대한 명궁에 주체 별이 든 것만).
    kinds: 검사할 limit.kind의 모임(None이면 모두: 大限명시, 大小限, 二限, 限통칭, 更 이음). 대한의 길흉 판정(노출도, 화기 중첩)과 합치지 않는다(11-2 1번).
    반환은 evaluate_j3의 한 궁과 같다: {palace, passages:[{id, verdict(선다·반만·서지 않는다), met, total, failed, enum, polarity, ...}], unparsed, summary}.
    구절 차례(11-2 4번): 선다가 반만보다 앞, 동궁 조건만인 구절이 삼방을 든 구절보다 앞, 흉이 길보다 앞, 그다음 원문 행 번호."""
    passages3 = passages if passages is not None else load_passages(DATA3)
    ctx = _Ctx(result)
    d = result['daehan'][daehan_index]
    z = d['palace']
    enc, unp, outside, skipped = _expand_limit(passages3, kinds)
    enc = _inherit(enc)
    use = []
    for q in enc:
        if q['parse'] == 'unparsed':
            if _subject3(ctx, z, q):
                unp.append({'id': q['id'], 'line': q['line'], 'text': q.get('clause') or q['text'], 'star': q['star'], 'reason': q.get('reason'), 'type': q['limit_type']})
        else:
            use.append(q)
    unp = [{'id': u['id'], 'line': u['line'], 'text': u.get('text'), 'reason': u.get('reason'), 'type': u.get('type')} for u in unp
           if u.get('star') is None or _subject3(ctx, z, u)]
    items, _ = evaluate_palace(ctx, z, use, '명')
    by = {q['id']: q for q in use}
    rank = {'흉': 0, '길': 1}
    for it in items:
        q = by[it['id']]
        if it['total'] == 0 and it['verdict'] != '성질':                  # 주체 별이 이 대한 명궁에 든 것이 곧 조건이다(조건 하나가 선 것으로 센다)
            it['met'] = it['total'] = 1
            it['subject_only'] = True
        it.update(line=q['line'], text=q['clause'], limit_kind=q['limit_kind'], limit_type=q['limit_type'], wide=_wide(q))
    order = {'선다': 0, '반만': 1, '서지 않는다': 2}
    items.sort(key=lambda it: (order[it['verdict']], 1 if it['wide'] else 0, rank.get(it['polarity'], 2), it['line'], it['id']))
    return {'palace': z, 'daehan': {k: d[k] for k in ('n', 'natal_role', 'age_from', 'age_to')}, 'passages': items,
            'unparsed': unp, 'outside': outside, 'skipped_kinds': skipped, 'summary': summarize(items)}

