"""전서 확정본(ZWDS_LIBRARY/02_primary/전서_확정본, 2026-11-25) 대조로 조건·극이 바뀐 구절을 고친다(2026-11-25, Opus). 다시 돌려도 같다.

구절표의 text는 진희이구결 전서수록 전사(시험 test_text_verbatim의 기준)라 그대로 두고, 확정본 글자를 note에 적는다.
대조 결과: 구절표 1,500행 가운데 1,425행이 확정본과 글자까지 같고, 다른 75행은 대부분 이체자나 이미 뜻대로 읽은 오자다
(年→羊, 大→火, 甲巳→甲己 따위). 조건이나 극이 바뀌는 것은 아래 여섯이다.
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
J3 = os.path.join(HERE, 'passages_j3.json')
J4 = os.path.join(HERE, 'passages_j4.json')
SAL = ['경양', '타라', '화성', '영성', '지공', '지겁']
GIL = ['좌보', '우필', '문창', '문곡', '천괴', '천월', '녹존', '화록', '화권', '화과']
NOTE = '전서 확정본 대조(apply_canon_j34.py)'


def _note(p, s):
    if NOTE not in (p.get('note') or ''):
        p['note'] = ((p.get('note') or '') + '; ' if p.get('note') else '') + NOTE + ': ' + s


def j3_fix(items):
    for p in items:
        pid = p['id']
        if pid in ('入限:794#1', '入限:812#1'):
            for c in p['conds']:
                if c['kind'] == '궁지' and c['values'] == ['酉', '丑']:
                    c['values'] = ['巳', '酉', '丑']
            _note(p, '확정본 「巳酉丑宫」(전사본 己는 巳의 오자)')
        elif pid in ('入限:859#1', '入限:859#2') and not any(c.get('word') == '㑹吉星' for c in p['conds']):
            p['conds'].append({'kind': '길', 'values': GIL, 'negate': False, 'scope': '동궁삼방대궁', 'word': '㑹吉星'})
            _note(p, '확정본 「女命㑹吉星」(전사본 士는 吉의 오자). 㑹은 삼방사정으로 읽음(추론)')
    return items


def j4_fix(items):
    for p in items:
        pid = p['id']
        if pid == '疾:18' and p['polarity'] == '흉':
            p['polarity'] = '길'
            _note(p, '확정본 「貪狼同庙旺無疾」(전사본 出은 旺의 오자). 無疾이라 길')
        elif pid == '妻:85' and len(p['conds']) == 1:
            p['conds'] += [{'kind': '밝기', 'values': ['묘왕'], 'negate': False, 'word': '入庙'},
                           {'kind': '길', 'values': GIL, 'negate': False, 'scope': '동궁', 'word': '加吉'}]
            _note(p, '확정본 「火鈴星入庙加吉無刑」(전사본 入西加士는 入庙加吉의 오자)')
        elif pid == '兄:14#3' and p['polarity'] == '흉':
            p['conds'].append({'kind': '살', 'values': SAL, 'negate': True, 'scope': '동궁', 'word': '無殺'})
            p['polarity'] = '중'
            _note(p, '확정본 「巨門同無殺三人」(전사본 移는 殺의 오자). 세는 말이라 중')
    return items


def main():
    for path, fn in ((J3, j3_fix), (J4, j4_fix)):
        with open(path, encoding='utf-8') as f:
            raw = json.load(f)
        items = raw if isinstance(raw, list) else raw['passages']
        fn(items)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(raw, f, ensure_ascii=False, indent=1)


if __name__ == '__main__':
    main()
