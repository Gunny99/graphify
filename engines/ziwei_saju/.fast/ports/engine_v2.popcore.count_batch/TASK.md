# Port `engine_v2.popcore.count_batch` to Rust

You're in a Rust crate fast-anything generated for this: `/tmp/claude-0/wt-perf/engines/ziwei_saju/.fast/ports/engine_v2.popcore.count_batch`.
Write `count_batch` in `src/lib.rs` so it behaves **exactly** like the Python below, and runs fast.
Only edit files in this folder. Don't touch the Python project.

## The original (engine_v2/popcore.py:89)

```python
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
```

## Helpers it calls

Port these as private Rust functions in the same crate (they stay in Python for everyone else).

```python
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
```

## Real calls

fast-anything recorded 21 real calls (out of 26 while the app ran). A few:

```
count_batch((("거문", "경양", "녹존", "무곡", "문곡", "문창", "박사", "염정", "영성", "우필", "자미", "좌보", "지겁", "지공", "천괴", "천기",…  ->  (1024, [[(1, 1, 143), (1, 0, 106), (3, 2, 15), (2, 2, 44), …
count_batch((("거문", "경양", "녹존", "무곡", "문곡", "문창", "박사", "염정", "영성", "우필", "자미", "좌보", "지겁", "지공", "천괴", "천기",…  ->  (1024, [[(1, 1, 135), (1, 0, 107), (1, 2, 65), (0, 0, 70), …
count_batch((("거문", "경양", "녹존", "무곡", "문곡", "문창", "박사", "염정", "영성", "우필", "자미", "좌보", "지겁", "지공", "천괴", "천기",…  ->  (1024, [[(2, 0, 68), (1, 2, 97), (1, 0, 118), (0, 2, 56), (…
count_batch((("거문", "경양", "녹존", "무곡", "문곡", "문창", "박사", "염정", "영성", "우필", "자미", "좌보", "지겁", "지공", "천괴", "천기",…  ->  (1024, [[(0, 2, 65), (1, 2, 91), (1, 1, 129), (2, 1, 113), …
count_batch((("거문", "경양", "녹존", "무곡", "문곡", "문창", "박사", "염정", "영성", "우필", "자미", "좌보", "지겁", "지공", "천괴", "천기",…  ->  (1024, [[(1, 0, 106), (1, 2, 71), (3, 2, 20), (2, 1, 100), …
count_batch((("거문", "경양", "녹존", "무곡", "문곡", "문창", "박사", "염정", "영성", "우필", "자미", "좌보", "지겁", "지공", "천괴", "천기",…  ->  (1024, [[(0, 0, 69), (1, 0, 112), (3, 0, 25), (0, 1, 105), …
count_batch((("거문", "경양", "녹존", "무곡", "문곡", "문창", "박사", "염정", "영성", "우필", "자미", "좌보", "지겁", "지공", "천괴", "천기",…  ->  (1024, [[(1, 1, 135), (3, 1, 48), (0, 2, 62), (1, 0, 128), …
count_batch((("거문", "경양", "녹존", "무곡", "문곡", "문창", "박사", "염정", "영성", "우필", "자미", "좌보", "지겁", "지공", "천괴", "천기",…  ->  (1024, [[(1, 2, 94), (2, 2, 47), (2, 1, 92), (6, 0, 1), (1,…
```

5 more recorded calls are held out: verify checks them too and reports a mismatch there without the values.

## Rules

- Same result for every input, edge cases included: empty input, zero, negatives, NaN and infinity, non-ASCII text, very long input. verify tests these too.
- Python `str` indexes by Unicode code point: use `.chars()` (or bytes only after checking `is_ascii()`).
- Python ints don't overflow. `i64` is fine unless the recorded values are bigger.
- Floats must match within 1e-9 of their size (or of the largest value in the same list), and zeros keep their sign: -0.0 is not 0.0. Keep the same order of float operations.
- Where Python raises, raise too (`PyValueError::new_err(...)`, `PyKeyError`, ...).
- Make it fast: no needless allocation or cloning, borrow inputs, `with_capacity`, fast paths for common cases.
- std only, unless a crate clearly pays off. Keep the function and module names as they are.
- Note: calls count_chart, they get ported together with it.
- Note: missing type hints, types are inferred from recorded calls.

## Check

Run `cargo check` here. Then fast-anything builds the crate in release mode and replays all 26 recorded calls against it
(`fast-anything verify engine_v2.popcore.count_batch`).
