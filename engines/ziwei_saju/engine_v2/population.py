"""지적능력 일곱 갈래의 모집단 차례: 표지사전의 확정 표지로 모든 명반(60 년 간지 × 12 월 × 30 일 × 12 시 = 259,200)을 센다.

가중치와 계수는 없다. 명반 하나는 갈래마다 (동궁 수, 삼방 수)를 얻고, 사전식(동궁 먼저, 같으면 삼방)으로 차례를 매긴다.

사전 조건 문법(조건 열, ';'로 이은 토큰, 모두 성립해야 함. 별 자신의 궁을 기준으로 본다):
  궁=子|丑      별이 앉은 지지      간=甲|庚        생년 천간       성별=女   남명반 모집단에서는 성립하지 않음
  동궁=a|b      같은 궁에 a 또는 b가 있음, 'a&b'는 모두 있음
  회=a|b        별 궁의 삼방사정(본궁 포함)에 a 또는 b가 있음, 'a&b'는 모두
  밝기=묘왕|함|평|비묘왕   data/brightness.json의 칸. 값이 없는 칸은 불성립으로 세고 따로 센다
  身命          별이 명궁 또는 신궁   命  별이 명궁   주성없음  별 궁에 주성이 없음   화=록  생년 사화 중 그 별이 받는 화
  #...          주석(셈에 영향 없음)
사전에 없는 배치: 박사는 녹존 궁에서 시작한다(전서 권3 "不拘男女命尋禄存星起"), 화록·화권·화과·화기는 생년 사화가 붙는 별의 궁.
"""
import argparse
import csv
import json
import os
import sys
import time
from collections import Counter

from .chart import place_stars
from .common import BR, MAIN14, STEM, gz60, sanfang
from .tables import Brightness, Sihua

BRANCH_OF_NAME = {}
THREADS = ('이해', '추리', '학습·기억', '언어', '처리 속도', '발상', '끈기')
HUA_NAME = {'록': '화록', '권': '화권', '과': '화과', '기': '화기'}
DEFAULT_DICT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', '지적능력_표지사전_20261113.tsv')
GENDER = '男'          # 모집단은 남명반으로 센다(별 배치는 성별과 무관)
HOURS = '子丑寅卯辰巳午未申酉戌亥'


# ── 사전 ──────────────────────────────────────────────
class Rule:
    __slots__ = ('idx', 'thread', 'star', 'cond_text', 'kind', 'piece', 'src', 'tokens', 'bright', 'female_only')

    def __init__(self, idx, row):
        self.idx = idx
        self.thread, self.star, self.cond_text, self.kind = row['갈래'], row['별'], row['조건'], row['길흉']
        self.piece, self.src = row['원문 조각'], row['출전']
        self.tokens, self.bright, self.female_only = [], None, False
        for tok in filter(None, (t.strip() for t in self.cond_text.split(';'))):
            if tok.startswith('#'):
                continue
            if tok.startswith('밝기='):
                self.bright = tok[3:]
            elif tok.startswith('성별='):
                if tok[3:] != GENDER:
                    self.female_only = True
            else:
                self.tokens.append(self._compile(tok))

    @staticmethod
    def _compile(tok):
        if tok == '身命':
            return lambda c, z, s: z == c['ming'] or z == c['shen']
        if tok == '命':
            return lambda c, z, s: z == c['ming']
        if tok == '주성없음':
            return lambda c, z, s: not any(n in MAIN14 for n in c['at'][z])
        key, _, val = tok.partition('=')
        if key == '궁':
            opts = set(val.split('|'))
            return lambda c, z, s: z in opts
        if key == '간':
            opts = set(val.split('|'))
            return lambda c, z, s: c['stem'] in opts
        if key == '화':
            return lambda c, z, s: c['hua'].get(s) == val
        if key in ('동궁', '회'):
            allm = '&' in val
            names = val.split('&' if allm else '|')

            def f(c, z, s, names=names, allm=allm, same=(key == '동궁')):
                zs = (z,) if same else c['sf'][z]
                have = set()
                for q in zs:
                    have |= c['at'][q]
                have.discard(s)
                return all(n in have for n in names) if allm else any(n in have for n in names)
            return f
        raise ValueError('알 수 없는 조건 토큰: ' + tok)


def load_dictionary(path=DEFAULT_DICT):
    """사전 tsv → (셈에 넣는 확정 Rule 목록, 행 수 집계)."""
    rules, tally = [], Counter()
    with open(path, encoding='utf-8') as f:
        for row in csv.DictReader(f, delimiter='\t'):
            if row['제외']:
                tally['제외'] += 1
            elif row['별'] == '미정':
                tally['미정'] += 1
            elif row['상태'] == '확정':
                tally['확정'] += 1
                rules.append(Rule(len(rules), row))
            else:
                tally[row['상태']] += 1
    return rules, tally


# ── 한 명반 ───────────────────────────────────────────
class Ctx:
    """명반 하나를 셈에 쓰기 좋게 풀어 둔다."""

    def __init__(self, rules, brightness=None, sihua=None):
        self.rules = rules
        self.br = brightness or Brightness()
        self.sh = sihua or Sihua()
        self.hua_stars = {s: [] for s in HUA_NAME}
        self.by_thread = {t: [r for r in rules if r.thread == t] for t in THREADS}
        names = {r.star for r in rules} | set(MAIN14)
        for r in rules:
            for tok in r.cond_text.split(';'):
                _, _, v = tok.partition('=')
                if tok.startswith(('동궁=', '회=')):
                    names |= set(v.replace('&', '|').split('|'))
        self.names = names

    def count(self, ys, yb, m, d, h):
        """{갈래: (동궁 수, 삼방 수, 흉 수, 밝기 값 없음 수)}, 밝기 값 없음 행 목록."""
        pos, ming, shen, _n, _stems, _kg = place_stars(ys, yb, m, d, h, True)
        pos['박사'] = pos['녹존']
        hua = {}
        for hh, star in self.sh.of(ys).items():
            pos[HUA_NAME[hh]] = pos[star]
            hua[star] = hh
        at = {z: set() for z in BR}
        for n in self.names:
            if n in pos:
                at[pos[n]].add(n)
        sf = {z: sanfang(z) for z in BR}
        c = dict(ming=ming, shen=shen, stem=ys, at=at, hua=hua, sf=sf)
        zone = {ming: 1, shen: 1}
        for z in sf[ming]:
            zone.setdefault(z, 2)
        out, missed = {}, []
        for t in THREADS:
            dong = sam = hung = miss = 0
            for r in self.by_thread[t]:
                if r.female_only:
                    continue
                z = pos.get(r.star)
                zn = zone.get(z)
                if zn is None:
                    continue
                if not all(f(c, z, r.star) for f in r.tokens):
                    continue
                if r.bright is not None:
                    g = self.br.grade(r.star, z)
                    if g is None:
                        miss += 1
                        missed.append(r)
                        continue
                    k = self.br.klass(g)
                    ok = {'묘왕': k == '묘왕', '함': k == '함', '평': k == '평', '비묘왕': k != '묘왕'}[r.bright]
                    if not ok:
                        continue
                if r.kind == '흉' and t != '끈기':
                    hung += 1
                    continue
                if zn == 1:
                    dong += 1
                else:
                    sam += 1
                if r.kind == '흉':
                    hung += 1
            out[t] = (dong, sam, hung, miss)
        return out, missed


def iter_charts():
    """모든 명반: 년 간지 60 × 음력 월 12 × 일 30 × 시 12."""
    for k in range(60):
        gz = gz60(k)
        for m in range(1, 13):
            for d in range(1, 31):
                for h in range(12):
                    yield gz[0], gz[1], m, d, h


def population(ctx, limit=None, every=1):
    """갈래별 (동궁, 삼방) 분포, 명반 수, 밝기 값 없음 경우의 수. limit·every는 시험용 표본."""
    dist = {t: Counter() for t in THREADS}
    miss_by_rule, nchart = Counter(), 0
    for i, ch in enumerate(iter_charts()):
        if i % every:
            continue
        if limit is not None and nchart >= limit:
            break
        res, missed = ctx.count(*ch)
        for t, (dg, sm, _hg, _ms) in res.items():
            dist[t][(dg, sm)] += 1
        for r in missed:
            miss_by_rule[r.idx] += 1
        nchart += 1
    return dict(dist=dist, n=nchart, miss_by_rule=miss_by_rule)


def ranks(dist, mine):
    """(같거나 높은 명반 비율, 더 높은 명반 비율). 사전식: 동궁 수 먼저, 같으면 삼방 수."""
    n = sum(dist.values())
    ge = sum(v for k, v in dist.items() if k >= mine)
    gt = sum(v for k, v in dist.items() if k > mine)
    return ge / n, gt / n


def parse_target(args):
    ys, yb = args.target[0][0], args.target[0][1]
    if ys not in STEM or yb not in BR:
        raise SystemExit('대상 년 간지 오류')
    return ys, yb, int(args.target[1]), int(args.target[2]), HOURS.index(args.target[3])


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--dict', default=DEFAULT_DICT)
    ap.add_argument('--target', nargs=4, metavar=('년간지', '음력월', '음력일', '시지'), required=True)
    ap.add_argument('--sample', type=int, default=1, help='N이면 N번째마다 한 명반(전수는 1)')
    ap.add_argument('--dist-out', help='분포를 json으로 저장')
    args = ap.parse_args(argv)
    rules, tally = load_dictionary(args.dict)
    ctx = Ctx(rules)
    ys, yb, m, d, h = parse_target(args)
    mine, missed = ctx.count(ys, yb, m, d, h)
    t0 = time.time()
    pop = population(ctx, every=args.sample)
    print(f'명반 {pop["n"]}  ({time.time() - t0:.0f}초)  사전 행: {dict(tally)}')
    den = Counter(r.thread for r in rules if not r.female_only)
    fem = Counter(r.thread for r in rules if r.female_only)
    print('| 갈래 | 동궁 | 삼방 | 흉 | 분모 | 같거나 높은 | 더 높은 | 밝기 없음 |')
    for t in THREADS:
        dg, sm, hg, ms = mine[t]
        ge, gt = ranks(pop['dist'][t], (dg, sm))
        print(f'| {t} | {dg} | {sm} | {hg} | {den[t]}(+여 {fem[t]}) | {ge:.4f} | {gt:.4f} | {ms} |')
    print('대상 밝기 값 없음 행:', [(r.thread, r.star, r.src) for r in missed])
    print('모집단 밝기 값 없음 경우의 수(행별):', {rules[i].thread + '/' + rules[i].star + '/' + rules[i].src: v
                                              for i, v in sorted(pop['miss_by_rule'].items())})
    print('모집단 밝기 값 없음 합계:', sum(pop['miss_by_rule'].values()))
    if args.dist_out:
        with open(args.dist_out, 'w', encoding='utf-8') as f:
            json.dump(dict(n=pop['n'], dist={t: {f'{a},{b}': v for (a, b), v in c.items()} for t, c in pop['dist'].items()},
                           miss={f'{rules[i].thread}/{rules[i].star}/{rules[i].src}': v for i, v in pop['miss_by_rule'].items()}),
                      f, ensure_ascii=False)


if __name__ == '__main__':
    main()
