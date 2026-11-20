# -*- coding: utf-8 -*-
"""권3 入命 구절 해독 2차(명세 5절 12번, 11-3 1·3번): l2.py에 새로 생긴 조건 종류(생년지지, 삼합, 타궁별)로 옮길 수 있는 구절을 옮긴다.
조건표 json에 필드를 더하는 스크립트다. 기존 id와 이미 해독된 조건(parse가 unparsed가 아닌 구절)은 건드리지 않는다.
다시 돌려도 결과가 같다(처리된 구절은 parse가 manual이 되어 건너뛴다). 사용: python apply_decode2_j3.py [json 경로]
모드: A = raw를 뺀 기존 조건에 새 조건을 더한다(같은 종류·값은 더하지 않음). R = 조건을 통째로 바꾼다(unparsed 구절의 임시 조건만 바뀐다). K = 조건 그대로 확정.
"""
import copy
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = '3_安星諸訣_入限入命斷訣.txt'
GIL = ["좌보", "우필", "문창", "문곡", "천괴", "천월", "녹존", "화록", "화권", "화과"]
SAMYO = ["辰", "戌", "丑", "未"]


def C(kind, values, word, **kw):
    d = {'kind': kind, 'values': values, 'negate': False}
    d.update(kw)
    d['word'] = word
    return d


DEC = {
    '入限:475#1': dict(mode='A', conds=[C('생년지지', ['未', '申'], '未申生人')],
                       why='未申生人은 생년 지지가 未 또는 申(生人=생년, 寅午戌人 따위와 같은 쓰임)'),
    '入限:475#2': dict(mode='K', conds=None, why='在未申宫은 궁지 未申으로 이미 지정돼 있고 원문과 일치(475행 앞 가지 未申生人과 한 문장)'),
    '入限:750': dict(mode='A', conds=[C('생년간', ['丙', '戊'], '丙戊'), C('생년지지', ['寅', '申'], '寅申生人'), C('궁지', ['子', '午'], '坐子午')],
                     why='丙戊寅申生人은 생년 천간 丙·戊이고 생년 지지 寅·申(양간과 양지가 짝이라 丙寅·丙申·戊寅·戊申), 坐子午는 궁지 子午'),
    '入限:904#3': dict(mode='A', conds=[C('생년지지', SAMYO, '四墓生人')],
                       why='四墓生人은 생년 지지 辰戌丑未(四墓=辰戌丑未는 72_해독_유형표 쟁점 3과 같은 상식 읽기). 會日月은 기존 조건'),
    '入限:914#2': dict(mode='A', conds=[C('생년지지', SAMYO, '四墓生人')], why='四墓生人은 생년 지지 辰戌丑未(四墓=辰戌丑未 상식 읽기)'),
    '入限:929#2': dict(mode='A', conds=[C('생년지지', SAMYO, '四墓生人')], why='四墓生人은 생년 지지 辰戌丑未(四墓=辰戌丑未 상식 읽기)'),
    '入限:929#3': dict(mode='A', conds=[C('궁지', SAMYO, '坐四墓宫')],
                       why='坐四墓宫은 궁지 辰戌丑未. 又로 시작하므로 앞 가지(929#2) 조건을 이어받는다(5절 12번 아)'),
    '入限:938#2': dict(mode='A', conds=[C('생년지지', SAMYO, '人生四墓生')],
                       why='人生四墓生은 생년 지지 辰戌丑未. 更로 시작하므로 앞 가지(938#1)의 주체 조건을 이어받는다'),
    '入限:531': dict(mode='R', conds=[C('삼합', ['자미'], '紫㣲三合照')],
                     why='三合照는 삼방에서 대궁을 뺀 두 궁(삼합)의 照. 기존 임시 조건(삼방대궁 자미)을 삼합 자미로 바꾼다'),
    '入限:895#2': dict(mode='R', conds='subject+', extra=[C('길', GIL, '更得諸吉加臨', scope='동궁'), C('길', GIL, '三合吉星守照', scope='삼합')],
                       why='加臨은 5절 10번의 加처럼 동궁, 三合吉星守照는 삼합의 길성. 기존 임시 조건 둘(삼방대궁 길)을 이 둘로 바꾼다. 更로 시작하므로 앞 가지(895#1) 조건을 이어받는다'),
    '入限:1020#1': dict(mode='R', conds=[C('궁지', SAMYO, '命在辰戌丑未'), C('타궁별', {'부처': ['천마']}, '有天馬在夫妻宫')], set={'star': None},
                        why='명궁이 辰戌丑未이고 夫妻宫에 천마가 있다(遇寅申巳亥는 이 두 조건의 결과라 따로 검사하지 않음). 천마는 이 궁의 주체가 아니라 부처궁의 별이므로 주체 별(star) 제한을 푼다'),
}


def note_of(p, why):
    ref = '근거 %s %s행 「%s」' % (p['file'], p['line'], p.get('clause') or p['text'])
    old = p.get('note')
    s = 'O25 해독2: %s. %s' % (why, ref)
    return (old + ' / ' + s) if old else s


def key(c):
    return (c['kind'], json.dumps(c['values'], ensure_ascii=False), c.get('scope'), c.get('negate', False))


def main(path=None):
    path = path or os.path.join(HERE, 'passages_j3.json')
    with open(path, encoding='utf-8') as f:
        data = json.load(f)
    ids = {p['id'] for p in data}
    miss = [i for i in DEC if i not in ids]
    assert not miss, miss
    done = skipped = 0
    for p in data:
        d = DEC.get(p['id'])
        if d is None:
            continue
        if p['parse'] != 'unparsed':
            skipped += 1
            continue
        assert p['file'] == SRC
        old_conds = copy.deepcopy(p['conds'])
        subj = [c for c in p['conds'] if c.get('role') == '주체']
        if d['mode'] == 'A':
            keep = [c for c in p['conds'] if c['kind'] != 'raw']
            have = {key(c) for c in keep}
            keep += [c for c in d['conds'] if key(c) not in have]
            new = keep
        elif d['mode'] == 'R':
            new = subj + d['extra'] if d['conds'] == 'subject+' else d['conds']
        else:
            new = p['conds']
        if d['mode'] == 'R':
            p['decoded_prev_conds'] = old_conds
        p['decoded_from'] = p.get('reason')
        p.pop('reason', None)
        p['conds'] = new
        for k, v in d.get('set', {}).items():
            p['%s_was' % k] = p.get(k)
            p[k] = v
        p['parse'] = 'manual'
        p['note'] = note_of(p, d['why'])
        done += 1
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)
    print('권3 2차: 옮긴 구절 %d, 이미 처리됨 %d' % (done, skipped))


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else None)
