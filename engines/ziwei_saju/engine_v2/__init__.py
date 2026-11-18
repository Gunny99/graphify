"""자미두수·사주 간명 엔진 v2: L0(명식·명반·운 기간), L1(구조 판독), L3(두 경로 운 사건).

명반 하나의 궁·별 값을 코드에 적지 않는다. 출력은 구조화된 사실(dict)이며 판정 문장을 만들지 않는다.
"""


def compute(date, time='12:00', male=True, solar_offset_min=0, tz=9, sihua_variant=None, sihua_overrides=None,
            with_l3=True, seun_boundary='lichun', **kw):
    from . import luck, structure
    from .calendar import resolve
    from .chart import build
    from .tables import Sihua
    sh = Sihua(sihua_variant, sihua_overrides)
    birth = resolve(date, time, male, solar_offset_min, tz, **kw)
    ch = build(birth, sihua=sh)
    l1 = structure.analyze(ch, sh)
    dw = luck.daewoon(birth)
    dh = luck.daehan(ch)
    out = dict(chart=ch, l1=l1, daewoon=dw, daehan=dh, sihua=sh)
    if with_l3:
        from . import fortune
        out['l3'] = fortune.analyze(ch, l1, dw, dh, sh, seun_boundary)
    return out
