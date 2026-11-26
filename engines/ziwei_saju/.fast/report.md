# ⚡ ziwei_saju: 18× faster

`python -m engine_v2.population --target 己卯 7 1 子 --sample 10` went from **2.50s** to **142ms** (median of 5 rounds, each running the original twice and Rust once in rotated order; middle half of the rounds 15–21×).

- CPU time 18×: **2.47s** → **139ms** (user + system, the app and the processes it waits for)
- A/A control, the original against itself in the same rounds: +2.7% (middle half -8.4% to +17.6%); the Rust ports' change is clearly beyond that

![fast-anything report](report.svg)

| function | per call | checked against |
|---|---|---|
| `engine_v2.popcore.count_batch` | **48×** (86.6ms → 1.8ms) | 310/310 recorded real calls |

The original code stays in place: set `FAST_ANYTHING_DISABLE=1` to run it, or `fast-anything disable <id>` to remove the switch.

<sub>Made with [fast-anything](https://github.com/EL4CTEO/fast-anything)</sub>
