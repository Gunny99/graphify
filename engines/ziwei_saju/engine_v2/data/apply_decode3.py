"""해독 3차(2026-11-18, 원점 재검토 Opus 판단). 대상 명반의 명궁·신궁·열한 궁에 주체 별이 있는 미해독 구절 가운데
원문 정의가 있는 것만 옮긴다. 다시 돌려도 같은 결과가 나온다(이미 옮긴 구절은 건너뜀).

옮긴 것
- 권4 약칭 열거: 𤎉=염정, 殺=칠살(破·武와 붙을 때), 破=파군, 鈴=영성, 日月=태양·태음, 巨机=거문·천기, 武殺=무곡·칠살.
  加는 동궁, 見은 삼방대궁(기존 자동 판독과 같음), 有는 동궁. 목록은 하나 이상이고 열거 k/n(명세 5절 12번 나).
- 권3 入限:601·602: 四墓=辰戌丑未(명세 11-3 6번). 601의 조건 머리를 601#2에 합치고 602(再化)는 그 조건을 이어받는다.
- 권3 入限:525·526: 525는 조건만 있는 머리라 526에 합친다(天府 守命 + 加之權祿 + 魁昌左右 來相會).
- 권3 入限:951#3: "及喜寅卯己午生人，禍輕"의 己는 巳의 오자로 읽는다(추론: 지지 열거 가운데 하나만 천간일 수 없다). 생년지지 조건.

옮기지 않은 것(이유는 reason에 적음)
- 相生: 무엇과 무엇의 상생인지(별과 궁, 별과 명) 원문 정의가 없다.
- 疾:32 "加刼殺空亡": 刼殺(地劫인지 劫殺 신살인지)와 空亡(旬空·截空)이 갈린다.
- 신분(武職·文人·常人)과 출신지 조건: 명주 사실로 검사할 수 없다.
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
J3 = os.path.join(HERE, 'passages_j3.json')
J4 = os.path.join(HERE, 'passages_j4.json')
SAL = ['경양', '타라', '화성', '영성', '지공', '지겁']
GIL = ['좌보', '우필', '문창', '문곡', '천괴', '천월', '녹존', '화록', '화권', '화과']
NOTE = '해독 3차(apply_decode3.py)'


def subj(star):
    return {'kind': '동궁', 'values': [star], 'negate': False, 'scope': '동궁', 'role': '주체'}


def j4_fix(items):
    by = {p['id']: p for p in items}
    out = []
    for p in items:
        pid = p['id']
        if pid == '兄:55#2' and p['parse'] == 'unparsed':
            p['conds'] = [subj('화성'), {'kind': '동궁', 'values': ['염정', '칠살', '파군', '영성'], 'negate': False,
                                         'scope': '동궁', 'word': '加𤎉殺破鈴'}]
            p['result'] = '孤尅'; p['parse'] = 'manual'; p['reason'] = None; p['note'] = NOTE + ': 𤎉殺破鈴 = 염정·칠살·파군·영성'
        elif pid == '妻:83' and p['parse'] == 'unparsed':
            p['conds'] = [{'kind': '동궁', 'values': ['경양', '타라'], 'negate': False, 'scope': '동궁', 'role': '주체'},
                          {'kind': '동궁', 'values': ['태양', '태음', '거문', '천기', '화성', '영성', '무곡', '칠살'],
                           'negate': False, 'scope': '동궁', 'word': '加日月、巨机、火鈴武殺'}]
            p['result'] = '主生離'; p['parse'] = 'manual'; p['reason'] = None
            p['note'] = NOTE + ': 日月 巨机 火鈴 武殺 = 태양·태음·거문·천기·화성·영성·무곡·칠살'
        elif pid == '子:68' and p['parse'] == 'unparsed':
            p['conds'] = [subj('좌보'), {'kind': '삼방대궁', 'values': ['무곡', '칠살'] + SAL, 'negate': False,
                                         'scope': '삼방대궁', 'word': '見武殺、羊陀火鈴，空刼'}]
            p['result'] = '止二人，有也，不成噐'; p['parse'] = 'manual'; p['reason'] = None
            p['note'] = NOTE + ': 武殺 = 무곡·칠살, 見은 삼방대궁'
        elif pid == '子:70' and p['parse'] == 'unparsed':
            a = dict(p, id='子:70#1', conds=[subj('문창'), {'kind': '길', 'values': GIL, 'negate': False, 'scope': '동궁',
                                                          'word': '加吉星'}],
                     result='加吉星更多', polarity='길', parse='manual', reason=None, note=NOTE + ': 加는 동궁')
            b = dict(p, id='子:70#2', conds=[subj('문창'), {'kind': '살', 'values': SAL, 'negate': False, 'scope': '동궁',
                                                          'word': '有擎陀、火鈴，空刼'}],
                     result='只可一子之分', polarity='흉', parse='manual', reason=None, note=NOTE + ': 有는 동궁')
            out += [a, b]
            continue
        elif pid in ('兄:53', '兄:56#1', '妻:72', '妻:77', '父:69#3') and p['parse'] == 'unparsed':
            p['reason'] = '相生: 무엇과 무엇의 상생인지(별과 궁, 별과 명) 원문 정의가 없어 옮기지 않음'
        elif pid == '疾:32' and p['parse'] == 'unparsed':
            p['reason'] = '刼殺(地劫인지 劫殺 신살인지)과 空亡(旬空·截空)이 갈려 옮기지 않음'
        elif pid in ('子:12#1', '子:12#2') and p['polarity'] == '미정':
            p['result'] = p['result'] + '，教君到老無児呌'; p['polarity'] = '흉'
            p['note'] = (p.get('note') or '') + '; ' + NOTE + ': 결과 행 子:13을 합침'
        elif pid == '子:13' and p['parse'] == 'unparsed':
            p['reason'] = '결과 행: 子:12#1·#2에 합침(해독 3차)'
        out.append(p)
    return out


def j3_fix(items):
    by = {p['id']: p for p in items}
    out = []
    for p in items:
        pid = p['id']
        if pid == '入限:601#1' and p['parse'] == 'unparsed':
            p['reason'] = '조건 머리: 601#2에 합침(해독 3차)'
        elif pid == '入限:601#2' and not any(c['kind'] == '궁지' for c in p['conds']):
            p['conds'] = [{'kind': '궁지', 'values': ['辰', '戌', '丑', '未'], 'negate': False, 'word': '四墓'},
                          {'kind': '밝기', 'values': ['묘왕'], 'negate': False, 'word': '庙旺'}] + p['conds']
            p['parse'] = 'manual'; p['note'] = NOTE + ': 601 머리(四墓 묘왕)를 합침'
        elif pid == '入限:602' and p['parse'] == 'unparsed':
            p['inherits'] = '入限:601#2'
            p['conds'] = [{'kind': '동궁', 'values': ['화과', '화권', '화록'], 'negate': False, 'scope': '동궁',
                           'word': '再化科權禄'}]
            p['result'] = '文武材能顕大功'; p['polarity'] = '길'; p['parse'] = 'manual'; p['reason'] = None
            p['note'] = NOTE + ': 再는 앞 가지 조건을 이어받음(명세 5절 12번 아)'
        elif pid == '入限:525' and p['parse'] == 'unparsed':
            p['reason'] = '조건 머리: 526에 합침(해독 3차)'
        elif pid == '入限:526' and not any(c.get('word') == '加之權禄' for c in p['conds']):
            p['conds'] = [subj('천부'), {'kind': '동궁', 'values': ['화권', '화록'], 'negate': False, 'scope': '동궁',
                                         'word': '加之權禄'}] + p['conds']
            p['parse'] = 'manual'; p['note'] = (p.get('note') or '') + '; ' + NOTE + ': 525 머리(天府 守命, 加之權禄)를 합침'
        elif pid == '入限:951#3' and p['parse'] == 'unparsed':
            p['conds'] = [subj('화성'), {'kind': '생년지지', 'values': ['寅', '卯', '巳', '午'], 'negate': False,
                                         'word': '喜寅卯己午生人'}]
            p['result'] = '禍輕'; p['polarity'] = '길'; p['parse'] = 'manual'; p['reason'] = None
            p['note'] = NOTE + ': 己는 巳의 오자로 읽음(추론)'
        elif pid == '入限:515' and p['parse'] == 'unparsed':
            base = {k: v for k, v in p.items() if k not in ('reason',)}
            a = dict(base, id='入限:515#1', conds=[
                {'kind': '생년지지', 'values': ['巳', '酉', '丑'], 'negate': False, 'word': '巳酉丑'},
                {'kind': '생년간', 'values': ['乙', '丙', '戊', '辛'], 'negate': False, 'word': '乙丙戊辛人'}],
                result='文武財官格', polarity='길', parse='manual',
                note=NOTE + ': "加亥卯未、辰酉上安命者"가 이 가지의 덧조건인지 갈려 넣지 않음(생년 조건이 먼저 걸림)')
            b = dict(base, id='入限:515#2', conds=[
                {'kind': '생년간', 'values': ['甲', '庚'], 'negate': False, 'word': '甲庚人'}],
                result='不貴，先大後小，有始無終', polarity='흉', parse='manual', note=NOTE)
            out += [a, b]
            continue
        out.append(p)
    return out


def main():
    for path, fn in ((J4, j4_fix), (J3, j3_fix)):
        with open(path, encoding='utf-8') as f:
            raw = json.load(f)
        items = raw if isinstance(raw, list) else raw['passages']
        new = fn(items)
        if isinstance(raw, list):
            raw = new
        else:
            raw['passages'] = new
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(raw, f, ensure_ascii=False, indent=1)


if __name__ == '__main__':
    main()
