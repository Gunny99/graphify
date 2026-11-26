#!/usr/bin/env python3
"""Python engine_v2(chart.place_stars/kong/build)로 golden 생성.
사용: python3 engines/ziwei_rs/tests/golden/gen.py   (저장소 어디서든)
sxtwl은 이 환경에 없고 build에는 쓰이지 않으므로(calendar.py가 import만 함) 빈 모듈로 막아 둔다.
"""
import json, os, random, sys, types

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..', 'ziwei_saju'))
sys.path.insert(0, ROOT)
sys.modules.setdefault('sxtwl', types.ModuleType('sxtwl'))

from engine_v2.chart import build, kong, place_stars        # noqa: E402
from engine_v2.common import BR, STEM                        # noqa: E402

N_CASES = 2400
N_FULL = 40          # 앞쪽 N_FULL개는 chart 전체를 그대로 싣는다(나머지는 정규화 JSON의 FNV-1a 64 해시)


def canon(o):
    return json.dumps(o, sort_keys=True, ensure_ascii=False, separators=(',', ':'))


def fnv(s):
    h = 0xcbf29ce484222325
    for b in s.encode('utf-8'):
        h = ((h ^ b) * 0x100000001b3) & 0xFFFFFFFFFFFFFFFF
    return f'{h:016x}'


def main():
    rnd = random.Random(20261126)
    gz = [(STEM[i % 10], BR[i % 12]) for i in range(60)]
    cases = []
    for _ in range(N_CASES):
        ys, yb = rnd.choice(gz)
        inp = dict(year_gz=ys + yb, month=rnd.randint(1, 12), day=rnd.randint(1, 30), hour=rnd.choice(BR),
                   male=rnd.random() < 0.5, leap=False)
        h = BR.index(inp['hour'])
        birth = dict(lunar=dict(year_gz=ys + yb, chart_month=inp['month'], day=inp['day']), hour_index=h,
                     input=dict(male=inp['male']))
        ch = build(birth)
        pos, ming, shen, n, stems, kg = place_stars(ys, yb, inp['month'], inp['day'], h, inp['male'])
        assert kg == kong(ys, yb) == ch['kong']
        ch = {k: v for k, v in ch.items() if k != 'birth'}
        ch['input'] = inp
        c = dict(input=inp, pos=pos, ming=ming, shen=shen, ju=n, stems=stems, kong=kg,
                 hash=fnv(canon(ch)))
        if len(cases) < N_FULL:
            c['chart'] = ch
        cases.append(c)
    with open(os.path.join(HERE, 'chart_golden.json'), 'w', encoding='utf-8') as f:
        json.dump(dict(generator='gen.py', source='engines/ziwei_saju/engine_v2/chart.py', cases=cases), f,
                  ensure_ascii=False, separators=(',', ':'))
    print(len(cases), 'cases')


main()
