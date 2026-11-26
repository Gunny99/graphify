"""대상 명식 입력 한 곳. 시계 10:10(KST), 출생지 인천 경도 126.7, 자오선 135 → 진태양시 09:30:28, 巳時.
옛 입력(시계 10:14, 수동 보정 -38분 = 09:36)은 OLD로 남겨 같은 명반·사주인지 회귀 시험한다(test_regression.py)."""
DATE, TIME, MALE, LON = '1999-08-04', '10:10', True, 126.7
TARGET = (DATE, TIME, MALE, 0)          # 4번째는 solar_offset_min(0): 보정은 longitude로 준다
KW = dict(longitude=LON)
OLD = ('1999-08-04', '10:14', True, -38)


def kw_for(case):
    return KW if tuple(case) == TARGET else {}
