# -*- coding: utf-8 -*-
"""권4 구절 해독 2차(명세 5절 12번, 11-3 1·3번): l2.py의 새 조건 종류(생시, 대궁, 협)로 옮길 수 있는 구절을 옮긴다.
기존 id와 이미 해독된 조건(parse가 unparsed가 아닌 구절)은 건드리지 않는다. 다시 돌려도 결과가 같다. 사용: python apply_decode2_j4.py [json 경로]
모드: A = raw를 뺀 기존 조건에 새 조건을 더한다. R = 조건을 통째로 바꾼다(unparsed 구절의 임시 조건만).
"""
import copy
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SHISI = ('생시 정의: 해당 원문(4_四子女.txt, 4_十二父母.txt)에 日生·夜生·本生時의 정의가 없다. 명세 11-3 3번의 기본대로 '
         '辰巳午未 시는 日生, 戌亥子丑 시는 夜生, 寅卯申酉 시는 미확인(None)')


def C(kind, values, word, **kw):
    d = {'kind': kind, 'values': values, 'negate': False}
    d.update(kw)
    d['word'] = word
    return d


DEC = {
    '子:12#1': dict(mode='A', conds=[C('생시', ['日生'], '日生'), C('동궁', ['태음'], '太隂臨', scope='동궁')],
                    why='日生은 생시 조건, 太隂臨은 태음이 자녀궁에 임함(바로 아래 子:13 "此星若在児女宫"이 이 별이 자녀궁에 있는 경우로 읽음)에서 동궁. ' + SHISI),
    '子:12#2': dict(mode='A', conds=[C('생시', ['夜生'], '夜生'), C('동궁', ['태양'], '太陽照', scope='동궁')],
                    why='夜生은 생시 조건, 太陽照도 子:13이 자녀궁 소재로 이어 읽으므로 동궁(삼방·대궁에 있으면 반만). ' + SHISI),
    '父:5#3': dict(mode='A', conds=[C('생시', ['日生'], '日生者')], why='日生者는 생시 조건(二星俱在陷地는 앞 가지 父:5#1). ' + SHISI),
    '父:5#4': dict(mode='A', conds=[C('생시', ['夜生'], '夜生者')], why='夜生者는 생시 조건. ' + SHISI),
    '父:6#1': dict(mode='A', conds=[C('생시', ['夜生'], '若夜生者')], why='夜生은 생시 조건(結果는 뒤 가지). ' + SHISI),
    '父:7#1': dict(mode='A', conds=[C('생시', ['日生'], '日生時者')], why='日生時는 생시 조건. ' + SHISI),
    '子:5': dict(mode='A', conds=[C('동궁', ['주성'], '本宫無星曜', scope='동궁', negate=True, premise=True), C('대궁', ['주성'], '專看對宫有何星宿')],
                 why='本宫無星曜는 자녀궁에 주성이 없음(星曜를 주성으로 읽음, 동궁 "주성" 값은 獨守와 같은 쓰임), 對宫有何星宿는 대궁 scope에 주성이 있음. 本宫無星曜는 전제 조건(premise)이라 서지 않으면 다른 조건이 맞아도 서지 않는다'),
    '田:4#2': dict(mode='R', conds=[C('협', ['좌보', '우필', '문창', '문곡'], '得左右昌曲夾輔', scope='양옆', sets=[['좌보', '우필'], ['문창', '문곡']])],
                   why='夾輔는 양옆 궁에 짝별이 하나씩 있는 협. 左右와 昌曲은 각각 한 짝이다. 기존 임시 조건(길 동궁)은 夾의 뜻에 맞지 않아 바꾼다'),
}


def note_of(p, why):
    ref = '근거 %s %s행 「%s」' % (p['file'], p['line'], p['text'])
    old = p.get('note')
    s = 'O25 해독2: %s. %s' % (why, ref)
    return (old + ' / ' + s) if old else s


def key(c):
    return (c['kind'], json.dumps(c['values'], ensure_ascii=False), c.get('scope'), c.get('negate', False))


def main(path=None):
    path = path or os.path.join(HERE, 'passages_j4.json')
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
        old_conds = copy.deepcopy(p['conds'])
        if d['mode'] == 'A':
            keep = [c for c in p['conds'] if c['kind'] != 'raw']
            have = {key(c) for c in keep}
            keep += [c for c in d['conds'] if key(c) not in have]
            new = keep
        else:
            new = d['conds']
            p['decoded_prev_conds'] = old_conds
        p['decoded_from'] = p.get('reason')
        p.pop('reason', None)
        p['conds'] = new
        p['parse'] = 'manual'
        p['note'] = note_of(p, d['why'])
        done += 1
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)
    print('권4 2차: 옮긴 구절 %d, 이미 처리됨 %d' % (done, skipped))


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else None)
