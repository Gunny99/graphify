# -*- coding: utf-8 -*-
"""권3 限(운) 구절 179개의 조건표화(명세 11-2). passages_j3.json의 scope가 限인 항목에 `limit` 필드를 더한다.
scope, parse(unparsed), reason('운 구절')은 건드리지 않는다(기존 test_j3_table_integrity가 못 박음). 조건은 limit.branches에 둔다.

limit = {type, kind, frame, branches:[{id, clause, conds, polarity, star?, inherits?, unparsed?, note?}], reason?, note?}
  type  : '大限'(大限·大小限을 든 것) | '小限·太歲' | '한통칭'(二限·入限·限臨 따위, 大·小를 가르지 않음) | '한도 낱말 없음'(별 이름과 결과만)
  frame : '大限'(대한 명궁에 L2 방식으로 검사) | '틀밖'(小限·太歲 조건, 11-2의 2번, 검사하지 않음) | None(한도 낱말이 없어 정하지 못함)
  kind  : type이 한통칭이면 '二限' | '限통칭', 大限이면 '大限명시' | '大小限'.
한통칭(二限, 入限 따위)은 小限도 포함하는 말이지만 大限이 만나는 경우에도 성립하는 말이므로 大限에 적용되는 것으로 옮겼다(판단, evaluate_limit의 kinds로 가를 수 있다).
화록·화권·화과·화기 구절은 대한 사화(대한 궁간)인지 생년 사화인지 원문에 없고 L2는 생년 사화만 보므로 옮기지 않는다.
scope를 '틀밖'으로 바꾸지 않고 limit.frame으로 표시한다: 기존 test_j3_table_integrity가 scope를 命·女命·限으로, evaluate_j3가 scope != '限'으로 거르기 때문이다.
減半(명세 11-2 3번): passages_j4.json의 兄:8, 兄:23, 子:31, 子:42#2, 子:69#3에 half 필드를 더한다(수를 곱하지 않고 글만 적는다).
다시 돌려도 결과가 같다. 사용: python apply_limit_j3.py [j3 경로] [j4 경로]
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
MAIN14 = ('자미', '천기', '태양', '무곡', '천동', '염정', '천부', '태음', '탐랑', '거문', '천상', '천량', '칠살', '파군')
GIL = ["좌보", "우필", "문창", "문곡", "천괴", "천월", "녹존", "화록", "화권", "화과"]
SAL6 = ["경양", "타라", "화성", "영성", "지공", "지겁"]
SAMYO = ["辰", "戌", "丑", "未"]
HUA_STARS = ('화록', '화권', '화과', '화기')
TS = re.compile('太歲|太歳|太嵗|太𡻕|歲君|歳君|流年|斗君')

R_HUA = ('화록·화권·화과·화기 구절: 대한 사화(대한 궁간의 사화)인지 생년 사화인지 원문에 없고 L2는 생년 사화만 검사하므로 옮기지 않음'
         '(L3의 대한 사화 표시가 필요)')
R_CONT = '한도 낱말이 없는 줄: 앞 줄 결과의 이음이거나 성질 서술이라 조건 궁을 정할 수 없음(문장 이음 판단이 필요)'
R_GEN = '문장의 뜻이 확실하지 않아 옮기지 않음'


def C(kind, values, word, **kw):
    d = {'kind': kind, 'values': values, 'negate': False}
    d.update(kw)
    d['word'] = word
    return d


def G(stars):
    """주체 별이 이 궁에 있다(관문, 세지 않음). 주성 14는 evaluate_palace가 따로 거르므로 달지 않는다."""
    stars = [stars] if isinstance(stars, str) else stars
    return C('동궁', stars, '', scope='동궁', role='주체')


def B(clause, conds, pol, **kw):
    d = dict(clause=clause, conds=conds, polarity=pol)
    d.update(kw)
    return d


def U(clause, reason):
    return dict(clause=clause, conds=[], polarity='미정', unparsed=reason)


# 옮긴 구절. 키는 passages_j3.json id. 값은 (가지 목록, note). 가지의 star를 따로 주면 그 별이 주체다(None이면 주체 관문 없음).
DEC = {
    '入限:316': ([B('紫微垣内吉星臨，二限相逢福禄興', [C('길', GIL, '吉星臨', scope='동궁')], '길')], '紫微垣内는 자미가 든 대한 명궁, 臨은 동궁(5절 10번의 加·同에 준함)'),
    '入限:318': ([B('紫㣲入限本為祥', [], '길'), U('只恐三方殺破狼', '殺破狼이 셋 모두인지 하나 이상인지와 격의 정의가 엔진에 없음(11-3 4번)')], None),
    '入限:346': ([B('男女二限值天機，禄主科𫞐大有為', [], '길')], None),
    '入限:348': ([B('天機照限不安寕', [C('삼방대궁', ['천기'], '照限', scope='삼방대궁')], '흉', star=None)], '照는 삼방·대궁의 비춤이라 주체 별이 이 궁에 있어야 하는 관문을 두지 않음'),
    '入限:382': ([B('二限偏冝見太陽，添才進業福非常', [C('삼방대궁', ['태양'], '偏冝見太陽', scope='삼방대궁')], '길', star=None)], '見은 5절 10번대로 삼방·대궁(본궁 제외)이라 주체 관문을 두지 않음'),
    '入限:384': ([B('𨺻地湏防𢙣殺侵', [C('밝기', ['함'], '𨺻地'), C('살', SAL6, '𢙣殺侵', scope='동궁삼방대궁')], '흉')], '太陽守限은 주체 관문. 侵은 5절 10번에 범위 낱말 정의가 없어 遇에 준해 동궁과 삼방·대궁으로 읽음(추론)'),
    '入限:419': ([B('大小限逢武曲星，若還入庙主財興', [C('밝기', ['묘왕'], '入庙')], '길')], '大小限의 大限에 적용'),
    '入限:460': ([B('人生二限值天同，喜氣盈門萬事荣', [], '길')], None),
    '入限:505': ([B('𤎉貞入限旺宫臨，喜逢吉矅福駢臻', [C('밝기', ['묘왕'], '旺宫臨'), C('길', GIL, '喜逢吉矅', scope='동궁삼방대궁')], '길')], None),
    '入限:534': ([B('限臨天府能司禄，士庶逢之多發福，添財進喜𣱵無灾', [], '길')], None),
    '入限:536': ([B('南斗尊星入限來，所為謀事稱心懐', [], '길')], '南斗尊星은 이 표의 천부 구절(南斗)로 읽음(추론)'),
    '入限:571': ([B('太隂星矅限中逢，財禄豊盈百事通', [], '길')], None),
    '入限:573': ([B('二限偏冝見太隂，添進財産福非輕', [C('삼방대궁', ['태음'], '偏冝見太隂', scope='삼방대궁')], '길', star=None)], '見은 5절 10번대로 삼방·대궁(본궁 제외)이라 주체 관문을 두지 않음'),
    '入限:609': ([B('北斗貪狼入限來，若還入庙事和諧', [C('밝기', ['묘왕'], '入庙')], '길'), U('科𫞐仕路多成就', '科權은 사화(대한 사화인지 생년 사화인지 불명)')], None),
    '入限:610': ([B('貪狼主限四庫臨，更喜人生四墓生，若見火星多横發', [C('궁지', SAMYO, '四庫臨'), C('생년지지', SAMYO, '人生四墓生'), C('살', ['화성'], '若見火星', scope='삼방대궁')], '길')],
               '四庫와 四墓는 辰戌丑未(11-3 6번 추론). 한 문장의 세 조건을 모두 요구'),
    '入限:611': ([B('限至貪狼𨺻不良', [C('밝기', ['함'], '𨺻')], '흉')], None),
    '入限:613': ([B('女限貪狼事不良', [C('성별', ['여'], '女限')], '흉')], '女限은 여성 명반의 대한으로 읽음'),
    '入限:649': ([B('巨門入限動人愁', [], '흉'), U('若遇喪門事不周', '喪門 별이 엔진의 별 목록에 없음')], None),
    '入限:651': ([B('巨門限𨺻最𠂯張', [C('밝기', ['함'], '𨺻')], '흉')], None),
    '入限:676': ([B('天相之星最主財，照臨二限悉無灾', [C('삼방대궁', ['천상'], '照臨二限', scope='동궁삼방대궁')], '길', star=None)], '照臨은 비춤과 임함이라 동궁과 삼방·대궁'),
    '入限:680': ([B('限臨天相遇擎羊，作禍興殃不可當', [C('살', ['경양'], '遇擎羊', scope='동궁삼방대궁')], '흉')], None),
    '入限:708': ([B('限至天梁最是良，猶如秋菊吐馨香', [], '길')], None),
    '入限:710': ([B('天梁守限壽延長，作事求謀更吉昌', [], '길')], None),
    '入限:743': ([B('二限雖然逢七殺，從容和緩家道發', [], '길')], None),
    '入限:745': ([B('更加𢙣曜在限中，主有官災多病疾', [C('살', SAL6, '更加𢙣曜在限中', scope='동궁')], '흉')], '七殺之星主啾唧는 주체. 惡曜는 6살로 읽음(권4 𢙣殺 해독과 같음)'),
    '入限:780': ([B('破軍入限要推詳，庙地方知福禄昌', [C('밝기', ['묘왕'], '庙地')], '길')], None),
    '入限:781': ([B('更遇文昌同魁鉞，限臨此地極風光', [C('동궁', ['문창', '천괴', '천월'], '文昌同魁鉞', scope='동궁', all=True)], '길', inherits='入限:780')], '更 가지라 780의 조건을 이어받음. 魁鉞은 짝이라 모두(5절 12번 가)'),
    '入限:782': ([B('破軍入限要推詳，庙地無㐫少損傷', [C('밝기', ['묘왕'], '庙地')], '길')], '無㐫은 조건이 아니라 결과문으로 읽음'),
    '入限:784': ([B('破軍主限多膿血，失脫𠂯張不可說', [], '흉')], None),
    '入限:809': ([B('限遇文昌不得地，更有羊陀火鈴忌', [C('밝기', ['함'], '不得地'), C('살', ['경양', '타라', '화성', '영성'], '更有羊陀火鈴', scope='동궁')], '흉')], '목록 끝의 忌(사화)는 뺐다'),
    '入限:831': ([B('二限若逢文曲星，士庶斯年湏發福', [], '길')], None),
    '入限:850': ([B('左輔限行福氣深，常人冨足累千金', [], '길')], None),
    '入限:852': ([B('左輔之星入限來，不冝殺凑主悲哀', [C('살', SAL6, '殺凑', scope='동궁삼방대궁')], '흉')], None),
    '入限:866': ([B('右弼入限最為荣，人財興旺必多能', [], '길')], None),
    '入限:867': ([B('右弼主限遇㐫星，掃盡家資百不成', [C('살', SAL6, '遇㐫星', scope='동궁삼방대궁')], '흉')], '㐫星은 6살로 읽음(권4 㑹㐫星 해독과 같음)'),
    '入限:888': ([B('禄存主限最為良，作事求謀𥁞吉祥', [], '길')], None),
    '入限:890': ([B('禄存主限夀延長，作事营謀萬事昌', [], '길')], None),
    '入限:897': ([B('限歩逢之，必主淸高，名成利就', [], '길', star=['천괴', '천월'])], '之는 魁鉞(천괴·천월 가운데 하나)'),
    '入限:922': ([B('擎羊守限細推詳，四墓生人免禍殃', [C('생년지지', SAMYO, '四墓生人')], '길')], '四墓는 辰戌丑未(11-3 6번 추론)'),
    '入限:926': ([B('擎羊加殺最爲㐫', [C('살', SAL6, '加殺', scope='동궁')], '흉'), B('二限休教落𨺻逢', [C('밝기', ['함'], '𨺻')], '흉')], None),
    '入限:945': ([B('限遇陀羅事亦多，必然忍耐要謙和', [], '미정')], None),
    '入限:957': ([B('火星得地限宫逢，喜氣盈門百事通', [C('밝기', ['묘왕'], '得地')], '길')], None),
    '入限:966': ([B('限至鈴星事若何，貪狼相遇福還多', [C('삼방대궁', ['탐랑'], '貪狼相遇', scope='동궁삼방대궁')], '길')], None),
    '入限:967': ([B('更加入庙逢諸吉，冨貴声揚處處歌', [C('밝기', ['묘왕'], '入庙'), C('길', GIL, '逢諸吉', scope='동궁삼방대궁')], '길', inherits='入限:966')], '更 가지라 966의 조건을 이어받음'),
    '入限:968': ([B('鈴星一宿不可當，守臨二限必顛狂', [], '흉')], None),
    '入限:983': ([B('火鈴限𨺻血膿侵，失脫時常不可尋', [C('밝기', ['함'], '限𨺻')], '흉', star=['화성', '영성'])], '火鈴은 화성·영성 가운데 이 궁에 든 별'),
    '入限:992': ([B('刼星二限若逢之，未免當年無禍危', [], '흉')], None),
    '入限:998': ([B('項羽英雄，限到天空而䘮國', [], '흉')], None),
    '入限:1012': ([B('夫子絶粮，限到天傷之内', [], '흉')], None),
    '入限:1018': ([B('天使限臨人共忌，石崇豪冨破家亡', [], '흉')], None),
    '入限:1023': ([B('天馬臨限最為良', [], '길'), U('紫府禄存遇非常', '紫府禄存이 셋 모두인지 하나 이상인지 불명')], None),
    '入限:1025': ([B('天馬守限不得住，又怕刼空來相遇', [C('살', ['지공', '지겁'], '又怕刼空來相遇', scope='동궁삼방대궁')], '흉')], None),
}

# 옮기지 않은 구절의 구체적 이유
REASON = {
    '入限:575': '限至太隂居反背: 反背의 뜻이 원문에 정의돼 있지 않음',
    '入限:706': '化蔭言星和: 化蔭의 뜻이 불명',
    '入限:833': '𤎉陀羊의 𤎉이 火인지 廉인지 불명',
    '入限:1004': '空亡이 天空·地空·截空·旬空 가운데 무엇인지 불명',
    '入限:1008': '刼空이 地空·地劫 두 별 모두인지 하나 이상인지 5절 12번에 정의가 없음',
    '入限:1017': '天耗가 대모인지 天傷의 다른 이름인지 불명',
    '入限:893': '禄馬交馳의 자리 정의가 불명하고 결과 구절이 없음(最怕刼空은 흉의 조건)',
    '入限:924': '天羅地網(辰戌)의 정의가 원문에 없음',
    '入限:962': '출신지(南人, 北人, 西北人) 조건은 11-3 2번대로 미검사',
    '入限:963': '한도 낱말이 없는 성질 서술',
    '入限:507': '결과가 508~509로 이어지는 한 문장이고 天刑·忌·刄의 뜻이 불명(문장 이음 판단이 필요)',
    '入限:1115': '권말 표제(紫㣲斗數全書下)',
    '入限:421': R_HUA,
    '入限:647': R_HUA,
    '入限:891': R_HUA,
    '入限:901': '魁鉞命身限遇昌: 魁鉞이 명신에 들고 한도에서 문창을 만난다는 뜻인지 한도에 魁鉞이 드는지 불명',
    '入限:1030': R_HUA,
    '入限:1043': R_HUA,
    '入限:1078': R_HUA,
}


def classify(p):
    """-> (type, kind, frame, tokens)"""
    t = p['text']
    if p['id'] == '入限:1115':
        return '한도 낱말 없음', None, None, []
    tok = TS.findall(t)
    t2 = t.replace('大小二限', '').replace('大小限', '')
    small = '小限' in t2
    big = '大限' in t
    dxs = t2 != t
    if p['star'] == '세군' or tok or (small and not big):
        return '小限·太歲', None, '틀밖', tok + (['小限'] if small else [])
    if big or dxs:
        return '大限', '大限명시' if big else '大小限', '大限', []
    if '限' in t:
        return '한통칭', '二限' if '二限' in t else '限통칭', '大限', []
    return '한도 낱말 없음', None, None, []


def numword(text):
    m = re.search('([一二三四五六七八九十]+)人', text)
    if not m:
        return None
    w = m.group(1)
    if w == '十':
        return 10
    return '一二三四五六七八九'.index(w) + 1 if len(w) == 1 else None


HALF = ('兄:8', '兄:23', '子:31', '子:42#2', '子:69#3')


def _dump(obj, path):
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


def main(path3=None, path4=None):
    path3 = path3 or os.path.join(HERE, 'passages_j3.json')
    path4 = path4 or os.path.join(HERE, 'passages_j4.json')
    with open(path3, encoding='utf-8') as f:
        data = json.load(f)
    miss = [i for i in DEC if i not in {p['id'] for p in data}]
    assert not miss, miss
    cnt = {}
    for p in data:
        if p.get('scope') != '限':
            continue
        assert p['parse'] == 'unparsed' and p['reason'] == '운 구절'
        typ, kind, frame, tok = classify(p)
        lim = {'type': typ, 'kind': kind, 'frame': frame}
        if p['id'] in DEC:
            brs, note = DEC[p['id']]
            if frame is None and all(b.get('inherits') for b in brs):
                frame, lim['frame'], lim['kind'] = '大限', '大限', '更 이음'    # 한도 낱말은 이어받는 앞 가지에 있다(5절 12번 아)
            assert frame == '大限', (p['id'], typ)
            multi = len(brs) > 1
            out = []
            for i, b in enumerate(brs, 1):
                b = dict(b)
                b['id'] = '%s#%d' % (p['id'], i) if multi else p['id']
                if 'star' not in b:
                    b['star'] = p['star']
                if not b.get('unparsed'):
                    star = b['star']
                    stars = star if isinstance(star, list) else ([star] if star else [])
                    if stars and not all(s in MAIN14 for s in stars):
                        b['conds'] = [G(stars)] + b['conds']
                out.append(b)
            lim['branches'] = out
            if note:
                lim['note'] = note
        elif frame == '틀밖':
            if p['star'] == '세군':
                lim['reason'] = '歲君(流年 太歲) 절의 구절(11-2의 2번: 틀 밖, 검사하지 않음)'
            else:
                lim['reason'] = '%s를 조건으로 든 구절(11-2의 2번: 틀 밖, 검사하지 않음)' % '·'.join(dict.fromkeys(tok))
        elif p['id'] in REASON:
            lim['reason'] = REASON[p['id']]
        elif p['star'] in HUA_STARS:
            lim['reason'] = R_HUA
        elif typ == '한도 낱말 없음':
            lim['reason'] = R_CONT
        else:
            lim['reason'] = R_GEN
        if p['id'] == '入限:1078':
            lim['note'] = '小限 가지(小限逢之，一年不足)는 틀 밖, 大限 가지(大限相遇，十年悔吝)는 화기라 옮기지 않음'
        p['limit'] = lim
        k = (typ, 'branches' in lim)
        cnt[k] = cnt.get(k, 0) + 1
    _dump(data, path3)
    print('권3 限 구절 limit 필드:', {'%s%s' % (k[0], '(옮김)' if k[1] else ''): v for k, v in sorted(cnt.items())})

    with open(path4, encoding='utf-8') as f:
        d4 = json.load(f)
    byid = {p['id']: p for p in d4}
    miss = [i for i in HALF if i not in byid]
    assert not miss, miss
    for i in HALF:
        p = byid[i]
        n = numword(p['text'])
        p['half'] = {'n': n, 'note': ('減半: %s에서 %s/2' % (n, n)) if n else '減半: n에서 n/2 (이 구절에는 수가 없다)'}
    _dump(d4, path4)
    print('권4 減半 구절:', [(i, byid[i]['half']['note']) for i in HALF])


if __name__ == '__main__':
    main(*sys.argv[1:3])
