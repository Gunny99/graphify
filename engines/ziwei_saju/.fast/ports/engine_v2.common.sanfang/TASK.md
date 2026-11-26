# Port `engine_v2.common.sanfang` to Rust

You're in a Rust crate fast-anything generated for this: `/tmp/claude-0/wt-perf/engines/ziwei_saju/.fast/ports/engine_v2.common.sanfang`.
Write `sanfang` in `src/lib.rs` so it behaves **exactly** like the Python below, and runs fast.
Only edit files in this folder. Don't touch the Python project.

## The original (engine_v2/common.py:31)

```python
def sanfang(z):
    """삼방사정: [본궁, 대궁(천이 자리), 재백 자리(-4), 관록 자리(+4)]."""
    return [z, opp(z), bz(bi(z) - 4), bz(bi(z) + 4)]
```

## Helpers it calls

Port these as private Rust functions in the same crate (they stay in Python for everyone else).

```python
def bi(z):
    return BR.index(z)
```

```python
def bz(i):
    return BR[i % 12]
```

```python
def opp(z):
    return bz(bi(z) + 6)
```

## Real calls

fast-anything recorded 400 real calls (out of 311,052 while the app ran). A few:

```
sanfang("丑")  ->  ["丑", "未", "酉", "巳"]
sanfang("卯")  ->  ["卯", "酉", "亥", "未"]
sanfang("未")  ->  ["未", "丑", "卯", "亥"]
sanfang("酉")  ->  ["酉", "卯", "巳", "丑"]
sanfang("申")  ->  ["申", "寅", "辰", "子"]
sanfang("申")  ->  ["申", "寅", "辰", "子"]
sanfang("子")  ->  ["子", "午", "申", "辰"]
sanfang("卯")  ->  ["卯", "酉", "亥", "未"]
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
- Note: calls bi, bz, opp, they get ported together with it.
- Note: missing type hints, types are inferred from recorded calls.

## Check

Run `cargo check` here. Then fast-anything builds the crate in release mode and replays all 500 recorded calls against it
(`fast-anything verify engine_v2.common.sanfang`).
