"""L0 운의 기간표: 사주 대운(절기), 자미 대한(오행국 수, 만 나이 생일 경계), 세운 간지.

고친 것: yun.birth/dayun의 1999년 고정과 1999~2000 절기 표, guard의 BIRTH·寅·국수·월 창 상수.
"""
from functools import lru_cache as _lru_cache
import datetime as _dt

import sxtwl

from .calendar import _dt_from_jd
from .common import BR, STEM, bi, bz, gz60, gz_index, roles_from, yang_stem, year_gz

TROPICAL_YEAR = 365.2422      # 대운 시작일 환산(guard.dayun_su_exact와 같은 법)


def _birthday(d, age):
    y = d.year + age
    try:
        return _dt.date(y, d.month, d.day)
    except ValueError:                                     # 2월 29일생: 평년에는 2월 28일
        return _dt.date(y, 2, 28)


def daewoon(birth, count=10):
    """사주 대운. 陽年 남자·陰年 여자 순행, 반대는 역행. 대운수 = 그 방향의 節까지 날수 ÷ 3(三日折一年)."""
    ystem = birth['saju']['year'][0]
    male = birth['input']['male']
    fwd = yang_stem(ystem) == male
    days = (birth['next_jd'] - birth['birth_jd_utc8']) if fwd else (birth['birth_jd_utc8'] - birth['prev_jd'])
    years = days / 3.0
    clock = birth['clock']
    m0 = gz_index(birth['saju']['month'])
    periods = []
    for k in range(1, count + 1):
        start = clock + _dt.timedelta(days=(years + 10 * (k - 1)) * TROPICAL_YEAR)
        end = clock + _dt.timedelta(days=(years + 10 * k) * TROPICAL_YEAR)
        gz = gz60(m0 + (k if fwd else -k))
        periods.append(dict(n=k, gz=gz, stem=gz[0], start=start, end=end, age_start=round(years + 10 * (k - 1), 2)))
    pre = dict(n=0, gz=None, stem=None, start=clock, end=periods[0]['start'], note='첫 대운 전(대운 천간 사화 없음)')
    return dict(direction='순행' if fwd else '역행', days=days, years=years,
                jie=(birth['jie_next'] if fwd else birth['jie_prev']), pre=pre, periods=periods)


def daehan(chart):
    """자미 대한 열둘. 명궁에서 시작, 陽男陰女 순행(+1)·陰男陽女 역행(-1), 시작 나이 = 오행국 수(만 나이), 경계 = 양력 생일."""
    ming = chart['ming']
    fwd = chart['direction'] == '순행'
    n = chart['ju']
    bd = chart['birth']['clock'].date()
    out = []
    for k in range(12):
        z = bz(bi(ming) + (k if fwd else -k))
        a0 = n + 10 * k
        out.append(dict(n=k + 1, palace=z, natal_role=chart['palaces'][z]['role'], age_from=a0, age_to=a0 + 9,
                        start=_birthday(bd, a0), end=_birthday(bd, a0 + 10), roles=roles_from(z)))
    return out


def seun(year):
    gz = year_gz(year)
    return dict(year=year, gz=gz, stem=gz[0])


def daewoon_on(dw, when):
    """그 시점의 대운(첫 대운 전이면 pre)."""
    for p in dw['periods']:
        if p['start'] <= when < p['end']:
            return p
    return dw['pre']


def daehan_on(dh, day):
    for p in dh:
        if p['start'] <= day < p['end']:
            return p
    return None


def daewoon_in_year(dw, year, boundary='lichun', tz=9):
    """그해 세운 기간에 걸치는 대운 목록(교체 해면 둘)."""
    a, b = seun_period(year, boundary, tz)
    out = [p for p in [dw['pre']] + dw['periods'] if p['start'] < b and p['end'] > a]
    return out


SEUN_BOUNDARY_NOTE = '세운 해 경계는 가정(미확인). 기본 입춘: 사화의 천간이 사주의 세운이므로(명세 9절 11번)'


@_lru_cache(maxsize=None)
def seun_period(year, boundary='lichun', tz=9):
    """세운 year의 기간 [start, end). boundary: 'lichun'(입춘 순간, 기본), 'seol'(음력 1월 1일), 'jan1'(양력 1월 1일)."""
    def start(y):
        if boundary == 'lichun':
            j = next(x for x in sxtwl.getJieQiByYear(y) if x.jqIndex == 3)
            return _dt_from_jd(j.jd, tz)
        if boundary == 'seol':
            d = sxtwl.fromLunar(y, 1, 1)
            return _dt.datetime(d.getSolarYear(), d.getSolarMonth(), d.getSolarDay())
        if boundary == 'jan1':
            return _dt.datetime(y, 1, 1)
        raise ValueError(boundary)
    return start(year), start(year + 1)


def seun_years_between(a, b, boundary='lichun', tz=9):
    """[a, b)에 걸치는 세운. 기간 일부만 걸치면 partial."""
    a = a if isinstance(a, _dt.datetime) else _dt.datetime.combine(a, _dt.time())
    b = b if isinstance(b, _dt.datetime) else _dt.datetime.combine(b, _dt.time())
    out = []
    for y in range(a.year - 1, b.year + 1):
        s, e = seun_period(y, boundary, tz)
        if s < b and e > a:
            out.append(dict(seun(y), start=s, end=e, partial=not (a <= s and e <= b),
                            overlap=(max(a, s), min(b, e))))
    return out


def years_of_daehan(p, boundary='lichun', tz=9):
    return seun_years_between(p['start'], p['end'], boundary, tz)


__all__ = ['daewoon', 'daehan', 'seun', 'daewoon_on', 'daehan_on', 'daewoon_in_year', 'years_of_daehan', 'seun_period', 'seun_years_between', 'STEM', 'BR']
