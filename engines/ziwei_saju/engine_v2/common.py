"""공통 상수와 궁 셈. 특정 명반 값은 없다."""
import json
import os

BR = '子丑寅卯辰巳午未申酉戌亥'
STEM = '甲乙丙丁戊己庚辛壬癸'
HUA = ('록', '권', '과', '기')

MAIN14 = ('자미', '천기', '태양', '무곡', '천동', '염정', '천부', '태음', '탐랑', '거문', '천상', '천량', '칠살', '파군')
YUKGIL = ('좌보', '우필', '문창', '문곡', '천괴', '천월')
SAL = ('경양', '타라', '화성', '영성', '지공', '지겁')      # 六煞. B-62의 살성(화성·지공)과 같은 묶음
GONGGEOP = ('지공', '지겁')
PAL_ROLES = ('명', '형제', '부처', '자녀', '재백', '질액', '천이', '노복', '관록', '전택', '복덕', '부모')
CHANGSHENG = ('장생', '목욕', '관대', '임관', '제왕', '쇠', '병', '사', '묘', '절', '태', '양')

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')


def bi(z):
    return BR.index(z)


def bz(i):
    return BR[i % 12]


def opp(z):
    return bz(bi(z) + 6)


def sanfang(z):
    """삼방사정: [본궁, 대궁(천이 자리), 재백 자리(-4), 관록 자리(+4)]."""
    return [z, opp(z), bz(bi(z) - 4), bz(bi(z) + 4)]


def roles_from(ming):
    """ming을 명궁으로 둘 때 지지마다 궁 이름(명 → 형제 → 부처 … 역순 배열)."""
    return {bz(bi(ming) - k): PAL_ROLES[k] for k in range(12)}


def yang_stem(s):
    return STEM.index(s) % 2 == 0


def gz60(i):
    return STEM[i % 10] + BR[i % 12]


def gz_index(gz):
    return next(k for k in range(60) if gz60(k) == gz)


def year_gz(y):
    """양력 연도의 세운 간지(연 단위, 입춘·설 경계는 보지 않는다)."""
    return gz60(y - 4)


def load_json(name):
    with open(os.path.join(DATA, name), encoding='utf-8') as f:
        return json.load(f)
