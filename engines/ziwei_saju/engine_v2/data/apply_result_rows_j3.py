"""권3 命·女命 조건 없는 구절 정리(2026-11-19, PR #14 리뷰 대응, 원점 재검토 Opus 판단). 다시 돌려도 같다.

l2.evaluate_j3는 조건이 없는 선 구절을 cond_palace가 '성질'일 때만 성질 서술로 돌린다. 그래서 cond_palace가 명·명신이고
conds가 빈 구절 56건을 셋으로 가른다.
- 자리만 조건인 구절(별 이름과 坐命·守命·命身 따위만 있음): 그대로 두어 길흉 집계에 넣는다.
- 원문에 자리 밖의 조건어가 있는데 조건표가 빈 구절: 해독 못 한 구절로 돌린다(명세 5절 12번 마).
- 별 이름도 조건어도 없는 대구의 뒤 행(결과 행): 바로 앞 행의 조건을 이어받는다(명세 5절 12번 카, 해독 3차 子:12+13과 같은 처리).
  앞 행이 가지로 나뉘었으면 마지막 가지를 잇는다(추론: 결과 행은 가까운 쪽 조건의 결과다). 앞 행이 해독 못 한 구절이면 이 행도 그렇다.
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
J3 = os.path.join(HERE, 'passages_j3.json')
NOTE = '결과 행 정리(apply_result_rows_j3.py)'

COND = {   # 자리 밖 조건어가 원문에 있는 구절 -> 그 조건어
    '入限:311': '天府同到宫', '入限:313#1': '守夫宫, 三方吉拱', '入限:341': '吉星扶', '入限:342': '𫞐禄宫中逢守照',
    '入限:375': '正照', '入限:377#1': '𨺻地', '入限:379#1': '反照', '入限:414#1': '天府加之', '入限:415': '左右再來相逢聚',
    '入限:456': '昌曲更來相會', '入限:516#1': '遇紫㣲左右同垣', '入限:566#1': '月㑹同陽, 三方吉拱', '入限:606#1': '𨺻地',
    '入限:636': '三合化吉科𫞐禄', '入限:638#1': '若然入庙', '入限:703': '辰戍機鿄, 破軍卯酉', '入限:740': '貪宿逢, 火陀凑合',
    '入限:777#1': '擎羊加𨺻',
}
CONT = {   # 결과 행 -> 이어받을 앞 행(앞 행이 가지면 마지막 가지)
    '入限:339': '入限:338', '入限:344': '入限:343', '入限:378': '入限:377#2', '入限:380': '入限:379#2',
    '入限:410': '入限:409#2', '入限:417': '入限:416', '入限:458': '入限:457', '入限:494': '入限:493',
    '入限:503': '入限:502', '入限:559': '入限:558', '入限:569': '入限:568#2', '入限:607': '入限:606#2',
    '入限:640': '入限:639', '入限:645': '入限:644', '入限:673#1': '入限:672#2', '入限:739': '入限:738#2',
    '入限:741#1': '入限:740', '入限:741#2': '入限:740', '入限:769': '入限:768', '入限:776#1': '入限:775',
    '入限:778': '入限:777#2', '入限:643#1': None, '入限:643#2': None,
}


def fix(items):
    by = {p['id']: p for p in items}
    prev_of = {}
    for p in items:   # 643의 앞 행은 같은 파일 바로 앞 줄의 마지막 가지
        if p['id'] in CONT and CONT[p['id']] is None:
            cand = [q for q in items if q['file'] == p['file'] and q['line'] == p['line'] - 1]
            prev_of[p['id']] = cand[-1]['id'] if cand else None
    for p in items:
        pid = p['id']
        if pid in COND and p['parse'] != 'unparsed' and not p.get('conds'):
            p['parse'] = 'unparsed'
            p['reason'] = '원문 조건어(%s)를 조건표로 옮기지 못함(명세 5절 12번 마)' % COND[pid]
            p['note'] = NOTE
        elif pid in CONT and not p.get('inherits'):
            src = CONT[pid] or prev_of.get(pid)
            if src and src in by:
                p['inherits'] = src
                p['note'] = NOTE + ': 결과 행, 앞 행 %s의 조건을 이어받음(명세 5절 12번 카)' % src
    return items


def main():
    with open(J3, encoding='utf-8') as f:
        raw = json.load(f)
    items = raw if isinstance(raw, list) else raw['passages']
    fix(items)
    with open(J3, 'w', encoding='utf-8') as f:
        json.dump(raw, f, ensure_ascii=False, indent=1)


if __name__ == '__main__':
    main()
