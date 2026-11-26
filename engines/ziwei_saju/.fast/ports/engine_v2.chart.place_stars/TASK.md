# Port `engine_v2.chart.place_stars` to Rust

You're in a Rust crate fast-anything generated for this: `/tmp/claude-0/wt-perf/engines/ziwei_saju/.fast/ports/engine_v2.chart.place_stars`.
Write `place_stars` in `src/lib.rs` so it behaves **exactly** like the Python below, and runs fast.
Only edit files in this folder. Don't touch the Python project.

## The original (engine_v2/chart.py:62)

```python
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
```

## Helpers it calls

Port these as private Rust functions in the same crate (they stay in Python for everyone else).

```python
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
```

## Real calls

fast-anything recorded 400 real calls (out of 25,921 while the app ran). A few:

```
place_stars("己", "亥", 3, 3, 6, True)  ->  ({"자미": "亥", "천기": "戌", "태양": "申", "무곡": "未", "천동": "午", "염…
place_stars("戊", "子", 10, 12, 8, True)  ->  ({"자미": "未", "천기": "午", "태양": "辰", "무곡": "卯", "천동": "寅", "염…
place_stars("乙", "丑", 7, 6, 0, True)  ->  ({"자미": "辰", "천기": "卯", "태양": "丑", "무곡": "子", "천동": "亥", "염…
place_stars("戊", "寅", 10, 28, 6, True)  ->  ({"자미": "酉", "천기": "申", "태양": "午", "무곡": "巳", "천동": "辰", "염…
place_stars("己", "酉", 8, 11, 0, True)  ->  ({"자미": "卯", "천기": "寅", "태양": "子", "무곡": "亥", "천동": "戌", "염…
place_stars("辛", "未", 2, 11, 0, True)  ->  ({"자미": "辰", "천기": "卯", "태양": "丑", "무곡": "子", "천동": "亥", "염…
place_stars("丙", "辰", 3, 9, 4, True)  ->  ({"자미": "寅", "천기": "丑", "태양": "亥", "무곡": "戌", "천동": "酉", "염…
place_stars("甲", "寅", 6, 9, 4, True)  ->  ({"자미": "子", "천기": "亥", "태양": "酉", "무곡": "申", "천동": "未", "염…
```

100 more recorded calls are held out: verify checks them too and reports a mismatch there without the values.

## Rules

- Same result for every input, edge cases included: empty input, zero, negatives, NaN and infinity, non-ASCII text, very long input. verify tests these too.
- Python `str` indexes by Unicode code point: use `.chars()` (or bytes only after checking `is_ascii()`).
- Python ints don't overflow. `i64` is fine unless the recorded values are bigger.
- Floats must match within 1e-9 of their size (or of the largest value in the same list), and zeros keep their sign: -0.0 is not 0.0. Keep the same order of float operations.
- Where Python raises, raise too (`PyValueError::new_err(...)`, `PyKeyError`, ...).
- Make it fast: no needless allocation or cloning, borrow inputs, `with_capacity`, fast paths for common cases.
- std only, unless a crate clearly pays off. Keep the function and module names as they are.
- Note: calls kong, they get ported together with it.
- Note: missing type hints, types are inferred from recorded calls.

## Check

Run `cargo check` here. Then fast-anything builds the crate in release mode and replays all 500 recorded calls against it
(`fast-anything verify engine_v2.chart.place_stars`).
