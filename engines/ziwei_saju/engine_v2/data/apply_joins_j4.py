# -*- coding: utf-8 -*-
"""권4 문장 이음. id를 바꾸지 않고 이어받는 행에 joins(앞 행 id 목록)와 text_full(이은 문장)을 단다.
조건표 json에 필드를 더하는 스크립트다(조건표를 다시 빌드하지 않는다). 기존 구절의 id와 이미 해독된 조건은 바꾸지 않는다.
다시 돌려도 결과가 같다(이미 처리된 구절은 건너뛴다). 사용: python apply_joins_j4.py [json 경로]
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

JOINS = json.loads('{"妻:59":["妻:58"],"子:13":["子:12"],"子:15":["子:14"],"父:18":["父:17"],"父:40":["父:38","父:39"],"福:56":["福:53"]}')

NOTES = json.loads('{"妻:59":"이은 문장은 \\"七殺早尅武曲同亦尅\\"이라 조건 길 문곡(曲 낱글자 읽기)은 동궁 무곡이어야 한다. 이미 해독된 조건이라 바꾸지 않고 표시만 한다. 다음 빌드에서 고친다."}')


def line_text(rows):
    """한 행 id의 가지들은 같은 줄 글이므로 첫 가지의 text와 text_cont를 쓴다."""
    p = rows[0]
    return p['text'] + ''.join(t['text'] for t in p.get('text_cont', []))


def main(path=None):
    path = path or os.path.join(HERE, 'passages_j4.json')
    with open(path, encoding='utf-8') as f:
        data = json.load(f)
    rows = {}
    for p in data:
        rows.setdefault(p['id'].split('#')[0], []).append(p)
    done = 0
    for rid, prev in JOINS.items():
        for p in rows[rid]:
            if 'joins' in p:
                continue
            p['joins'] = list(prev)
            p['text_full'] = ''.join(line_text(rows[q]) for q in prev) + line_text(rows[rid])
            if rid in NOTES:
                p['joins_note'] = NOTES[rid]
            done += 1
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)
    print('권4 문장 이음: 단 가지 %d (행 %d)' % (done, len(JOINS)))


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else None)
