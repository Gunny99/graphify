"""모집단 셈의 명반별 핵심: 평범한 자료(튜플·문자열·정수)만 받고 돌려주는 순수 함수.

population.Ctx가 사전·밝기표·사화표를 spec 튜플 하나로 풀어 넘긴다. 셈의 뜻은 Ctx.count의 이전 구현과 같다.
spec = (names, hua_table, bright, threads)
  names      셈에 쓰는 별 이름 튜플
  hua_table  {천간: ((화 글자, 화 이름, 별), ...)}
  bright     ((별, 지지, 밝기 칸 분류), ...)
  threads    갈래마다 행 튜플. 행 = (행 번호, 별, 밝기 조건 또는 '', 흉이면 True, 흉이면 동궁·삼방에 안 넣고 흉만 셈, 조건 토큰 튜플)
  토큰 = (연산, 선택지 튜플, 모두여야 하면 True)
"""
from .chart import place_stars
from .common import BR, MAIN14, sanfang

_BRIGHT_OK = {'묘왕': lambda k: k == '묘왕', '함': lambda k: k == '함', '평': lambda k: k == '평', '비묘왕': lambda k: k != '묘왕'}


def _holds(tok, c, z, s):
    op, opts, flag = tok
    if op == '身命':
        return z == c['ming'] or z == c['shen']
    if op == '命':
        return z == c['ming']
    if op == '주성없음':
        return not any(n in MAIN14 for n in c['at'][z])
    if op == '궁':
        return z in opts
    if op == '간':
        return c['stem'] in opts
    if op == '화':
        return c['hua'].get(s) == opts[0]
    zs = (z,) if op == '동궁' else c['sf'][z]
    have = set()
    for q in zs:
        have |= c['at'][q]
    have.discard(s)
    return all(n in have for n in opts) if flag else any(n in have for n in opts)


def count_chart(spec, ys, yb, m, d, h):
    """명반 하나: (갈래마다 (동궁, 삼방, 흉, 밝기 값 없음) 튜플, 밝기 값 없음 행 번호 목록)."""
    names, hua_table, bright, threads = spec
    pos, ming, shen, _n, _stems, _kg = place_stars(ys, yb, m, d, h, True)
    pos['박사'] = pos['녹존']
    hua = {}
    for hh, hname, star in hua_table[ys]:
        pos[hname] = pos[star]
        hua[star] = hh
    at = {z: set() for z in BR}
    for n in names:
        if n in pos:
            at[pos[n]].add(n)
    sf = {z: sanfang(z) for z in BR}
    c = dict(ming=ming, shen=shen, stem=ys, at=at, hua=hua, sf=sf)
    zone = {ming: 1, shen: 1}
    for z in sf[ming]:
        zone.setdefault(z, 2)
    cells = {(s, b): k for s, b, k in bright}
    out, missed = [], []
    for rules in threads:
        dong = sam = hung = miss = 0
        for idx, star, br, is_hung, hung_only, toks in rules:
            z = pos.get(star)
            zn = zone.get(z)
            if zn is None:
                continue
            if not all(_holds(t, c, z, star) for t in toks):
                continue
            if br:
                k = cells.get((star, z))
                if k is None:
                    miss += 1
                    missed.append(idx)
                    continue
                if not _BRIGHT_OK[br](k):
                    continue
            if hung_only:
                hung += 1
                continue
            if zn == 1:
                dong += 1
            else:
                sam += 1
            if is_hung:
                hung += 1
        out.append((dong, sam, hung, miss))
    return tuple(out), missed


def count_batch(spec, charts):
    """명반 여러 개: (명반 수, 갈래마다 [(동궁, 삼방, 개수), ...](처음 나온 차례), [(행 번호, 개수), ...](처음 나온 차례))."""
    dist = [{} for _ in spec[3]]
    miss = {}
    n = 0
    for ch in charts:
        res, missed = count_chart(spec, *ch)
        for dct, (dg, sm, _hg, _ms) in zip(dist, res):
            k = (dg, sm)
            dct[k] = dct.get(k, 0) + 1
        for i in missed:
            miss[i] = miss.get(i, 0) + 1
        n += 1
    return n, [[(a, b, v) for (a, b), v in dct.items()] for dct in dist], [(i, v) for i, v in miss.items()]

# >>> fast-anything: engine_v2.popcore.count_batch >>>
# Uses the verified Rust port. FAST_ANYTHING_DISABLE=1 runs the Python above instead.
# Undo with:  fast-anything disable engine_v2.popcore.count_batch
def _fast_anything_load():
    import os, sys
    if os.environ.get("FAST_ANYTHING_DISABLE"):
        return None
    lib = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "../.fast/lib"))
    if lib not in sys.path:
        sys.path.append(lib)
    try:
        from fa_engine_v2_popcore_count_batch import count_batch
    except ImportError:
        return None
    return count_batch
count_batch = _fast_anything_load() or count_batch
del _fast_anything_load
# <<< fast-anything: engine_v2.popcore.count_batch <<<
