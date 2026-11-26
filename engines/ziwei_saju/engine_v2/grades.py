"""권2 定冨貴貧賤十等論·一十四等訣 표제별 조건 검사. 표제 사이의 위아래는 매기지 않는다(원문에 없다).

조건표는 data/grades_j2.json. 조건 검사와 범위 처리는 l2의 함수를 그대로 쓰고,
l2에 없는 종류(협, 동궁함께, 별화, unknown)만 여기서 다룬다. 명반 상수는 없다.
앵커(at): 명 | 신 | 명신 | 별:<별> | 궁:<궁 이름>. 앵커가 여럿이면 하나라도 서면 선다.
"""
import json
import os

from .common import bi, bz
from .l2 import _Ctx, _check, _scope_palaces

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'grades_j2.json')
_CACHE = {}


def load_grades(path=None):
    path = path or DATA
    if path not in _CACHE:
        with open(path, encoding='utf-8') as f:
            _CACHE[path] = json.load(f)
    return _CACHE[path]


def _anchors(ctx, at):
    ch = ctx.chart
    if at == '명':
        zs = [ch['ming']]
    elif at == '신':
        zs = [ch['shen']]
    elif at == '명신':
        zs = [ch['ming'], ch['shen']]
    elif at.startswith('별:'):
        zs = [ch['pos'].get(at[2:])]
    elif at.startswith('궁:'):
        zs = [ctx.role_palace(at[2:])]
    else:
        zs = []
    out = []
    for z in zs:
        if z and z not in out:
            out.append(z)
    return out


def _tokens(ctx, z):
    t = set(ctx.names(z))
    for s in ctx.stars(z):
        if s.get('hua'):
            t.add('화' + s['hua'])
    return t


def _jia_ok(ctx, z, sets):
    left, right = _tokens(ctx, bz(bi(z) - 1)), _tokens(ctx, bz(bi(z) + 1))
    for vals in sets:
        for x in vals:
            for y in vals:
                if x != y and x in left and y in right:
                    return True
    return False


def _one(ctx, z, c):
    kind = c['kind']
    if kind == 'unknown':
        return None
    if kind == '협':
        got = _jia_ok(ctx, z, c['sets'])
    elif kind == '동궁함께':
        got = any(set(c['values']) <= ctx.names(q) for q in _scope_palaces(z, c['scope']))
    elif kind == '별화':
        star, hua = c['values']
        got = any(s['name'] == star and s.get('hua') == hua for s in ctx.stars(z))
    else:
        p = {'star': c.get('subject')}
        if c.get('subject') == 'main':
            own, bor = ctx.mains(z)
            p = {'star': list(own) + list(bor)}
            if kind == '밝기' and not p['star']:
                return False
        return _check(ctx, z, p, c)
    return (not got) if c.get('negate') else got


def check_cond(ctx, c):
    """-> True | False | 'half' | None(미확인). 앵커가 여럿이면 가장 좋은 결과."""
    res = [_one(ctx, z, c) for z in _anchors(ctx, c.get('at', '명'))]
    if any(r is True for r in res):
        return True
    if any(r == 'half' for r in res):
        return 'half'
    if not res or any(r is None for r in res):
        return None if (c['kind'] == 'unknown' or res) else False
    return False


def _desc(c):
    if c['kind'] == 'unknown':
        return 'unknown(' + c['values'][0] + ')'
    v = c['sets'] if c['kind'] == '협' else c['values']
    return ('없음 ' if c.get('negate') else '') + c['kind'] + ':' + c.get('scope', '') + '@' + c.get('at', '명') + str(v)


_ENUM_KINDS = ('동궁', '삼방대궁', '살', '길')


def _units(c):
    """별 열거 조건은 별 하나가 한 단위. any_of 표시가 있거나 별 하나뿐이면 조건 하나가 한 단위."""
    if c['kind'] in _ENUM_KINDS and len(c['values']) > 1 and not c.get('any_of') and not c.get('negate'):
        return [dict(c, values=[v]) for v in c['values']]
    return [c]


def evaluate(result, entries=None):
    """파싱된 표제마다 {id, title, verdict(선다|반만|서지 않는다), met, total, failed, unknown, half, polarity,
    present, absent}. 별 열거는 낱개로 센다(any_of 줄 제외). unknown 조건은 충족으로 세지 않는다.
    선다 = met == total, 반만 = 0 < met < total, 서지 않는다 = met 0.
    present/absent = 별·화 값 단위 조건 가운데 말한 범위에 있는 것과 없는 것."""
    entries = entries if entries is not None else load_grades()
    ctx = _Ctx(result)
    out = []
    for e in entries:
        if e['parse'] == 'unparsed' or not e['conds']:
            continue
        met = half = total = 0
        failed, unknown, present, absent = [], [], [], []
        for c0 in e['conds']:
            for c in _units(c0):
                total += 1
                r = check_cond(ctx, c)
                tag = c['kind'] in _ENUM_KINDS and not c.get('negate')
                if tag and c.get('any_of'):      # any_of 줄도 목록에는 실제로 있는 별만 적는다
                    for v in c['values']:
                        (present if check_cond(ctx, dict(c, values=[v])) is True else absent).append(v)
                if r is True:
                    met += 1
                    if tag and not c.get('any_of'):
                        present += c['values']
                elif r == 'half':
                    half += 1
                    failed.append(_desc(c) + ' [동궁 밖]')
                elif r is None:
                    unknown.append(_desc(c))
                else:
                    failed.append(_desc(c))
                    if tag and not c.get('any_of'):
                        absent += c['values']
        v = '선다' if met == total else ('반만' if met > 0 else '서지 않는다')
        out.append({'id': e['id'], 'title': e['title'], 'verdict': v, 'met': met, 'total': total,
                    'failed': failed + unknown, 'unknown': unknown, 'half': half, 'polarity': e['polarity'],
                    'present': present, 'absent': absent})
    return out


def unparsed(entries=None):
    entries = entries if entries is not None else load_grades()
    return [{'id': e['id'], 'title': e['title'], 'reason': e.get('reason')} for e in entries if e['parse'] == 'unparsed']
