# -*- coding: utf-8 -*-
"""독립 검증(2026-11-18) 후속. 권4에 두 가지를 더한다(조건표를 다시 빌드하지 않고 필드만 더함, id 불변, 다시 돌려도 같음).
1. 조건 없는 읽는 법 문장은 nature: true(성질 서술, 명세 5절 12번 라·차). l2.evaluate_palace가 이 필드를 읽어 선다로 세지 않는 처리는 l2 몫.
2. 앞 행이 조건 동사(同, 加)로 끝나 이어지는 구절(명세 5절 12번 사·차): joins, text_full을 달고 앞 행의 조건을 더한다.
사용: python apply_fix2_j4.py [json 경로]"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
NATURE = {'父:3': '조건어 없는 읽는 법 문장(凢看父母，以太陽星為父，太隂星為母). 4_十二父母.txt 0002'}


def C(kind, values, word, scope='동궁'):
    return {'kind': kind, 'values': values, 'negate': False, 'scope': scope, 'word': word}


SAL6 = ['경양', '타라', '화성', '영성', '지공', '지겁']
# 받는 행 -> (앞 행 id 목록, 더할 조건, 근거)
JOIN2 = {
    '疾:51': (['疾:50'], [C('동궁', ['무곡'], '武曲同')], '앞 행 "武曲同。"의 마침표는 줄 나눔의 흔적(같은 편 47행 "武曲同，加四殺破相"과 같은 꼴)'),
    '疾:58': (['疾:57'], [C('동궁', ['염정'], '𤎉貞同')], '앞 행 "𤎉貞同。"에 이어짐'),
    '父:23': (['父:22'], [C('동궁', ['거문'], '巨門同')], '앞 행 "巨門同。"에 이어짐'),
    '父:57': (['父:56'], [C('동궁', ['천동'], '天同同')], '앞 행 "天同同。"에 이어짐'),
    '父:63': (['父:62'], [C('동궁', ['자미'], '紫微同')], '앞 행 "紫微同。"에 이어짐'),
    '子:55': (['子:54'], [C('동궁', ['무곡'], '武曲同')], '앞 행 "武曲同。"에 이어짐'),
    '子:61': (['子:60'], [], '更·又·再가 아닌 再加이나 inherits(子:60)가 이미 앞 조건을 잇고 있어 joins만 단다'),
    '妻:47': (['妻:46'], [C('동궁', ['태양'], '太陽同')], '앞 행 "太陽同。"에 이어짐'),
    '奴:48': (['奴:47'], [C('살', SAL6, '加羊陀火鈴空刼')], '앞 행이 "𤎉貞欠力加"로 끝남: 加+羊陀火鈴空刼, 동궁(명세 5절 10번 加)'),
    '子:78': (['子:76'], [{'kind': '동궁', 'values': ['주성'], 'negate': True, 'scope': '동궁', 'word': '獨守'}], '앞 행 "鈴星獨守。"에 이어짐(子:76과 같은 獨守 조건)'),
}


def key(c):
    return (c['kind'], tuple(c['values']), c.get('scope'), c.get('negate', False))


def line_text(rows):
    p = rows[0]
    return p['text'] + ''.join(t['text'] for t in p.get('text_cont', []))


def main(path=None):
    path = path or os.path.join(HERE, 'passages_j4.json')
    with open(path, encoding='utf-8') as f:
        data = json.load(f)
    rows = {}
    for p in data:
        rows.setdefault(p['id'].split('#')[0], []).append(p)
    nat = joined = 0
    for rid, why in NATURE.items():
        for p in rows[rid]:
            if not p.get('nature'):
                p['nature'] = True
                p['note'] = ((p.get('note') + ' / ') if p.get('note') else '') + '성질 서술: ' + why
                nat += 1
    for rid, (prev, conds, why) in JOIN2.items():
        for p in rows[rid]:
            if 'joins' in p:
                continue
            p['joins'] = list(prev)
            p['text_full'] = ''.join(line_text(rows[q]) for q in prev) + line_text(rows[rid])
            have = {key(c) for c in p['conds']}
            p['conds'] = p['conds'] + [c for c in conds if key(c) not in have]
            p['note'] = ((p.get('note') + ' / ') if p.get('note') else '') + '문장 이음: ' + why
            joined += 1
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)
    print('성질 서술 표시 %d, 새로 이은 가지 %d (행 %d)' % (nat, joined, len(JOIN2)))


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else None)
