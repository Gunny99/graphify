"""L0 역법: 양력 일시 → 음력(윤달 포함), 시지, 사주 네 기둥, 절기 앞뒤.

시각 규약
- clock: 입력한 시계 시각(tz 시간대). 절기와 대운수 계산은 이 순간을 쓴다.
- solar: clock + solar_offset_min(진태양시 보정). 시지와 날짜 경계는 이 시각으로 정한다.
- sxtwl의 절기 JD는 UTC+8 기준이므로 출생 순간을 UTC+8로 옮겨 비교한다.
"""
import datetime as _dt

import sxtwl

from .common import BR, STEM, gz60

JIE_BRANCH = {3: '寅', 5: '卯', 7: '辰', 9: '巳', 11: '午', 13: '未', 15: '申', 17: '酉', 19: '戌', 21: '亥', 23: '子', 1: '丑'}
JIE_NAME = {1: '小寒', 3: '立春', 5: '驚蟄', 7: '清明', 9: '立夏', 11: '芒種', 13: '小暑', 15: '立秋', 17: '白露', 19: '寒露', 21: '立冬', 23: '大雪'}
TIGER = {'甲': '丙', '己': '丙', '乙': '戊', '庚': '戊', '丙': '庚', '辛': '庚', '丁': '壬', '壬': '壬', '戊': '甲', '癸': '甲'}   # 五虎遁
RAT = {'甲': '甲', '己': '甲', '乙': '丙', '庚': '丙', '丙': '戊', '辛': '戊', '丁': '庚', '壬': '庚', '戊': '壬', '癸': '壬'}     # 五鼠遁


def _jd(t):
    return sxtwl.toJD(sxtwl.Time(t.year, t.month, t.day, t.hour, t.minute, t.second))


def _dt_from_jd(jd, tz):
    d = sxtwl.JD2DD(jd)
    base = _dt.datetime(int(d.Y), int(d.M), int(d.D)) + _dt.timedelta(hours=d.h, minutes=d.m, seconds=d.s)
    return base + _dt.timedelta(hours=tz - 8)


def jie_list(year):
    """year-1 ~ year+1의 節(홀수 절기)을 (jd, jqIndex)로, UTC+8 기준."""
    seen = {}
    for y in (year - 1, year, year + 1):
        for j in sxtwl.getJieQiByYear(y):
            if j.jqIndex % 2 == 1:
                seen[round(j.jd, 5)] = (j.jd, j.jqIndex)
    return sorted(seen.values())


def month_stem(year_stem, month_branch):
    return STEM[(STEM.index(TIGER[year_stem]) + (BR.index(month_branch) - BR.index('寅'))) % 10]


def resolve(date, time='12:00', male=True, solar_offset_min=0, tz=9, zi_rule='next_day', leap_rule='same'):
    """생년월일시 해석.

    date 'YYYY-MM-DD', time 'HH:MM'(시계 시각), male bool, solar_offset_min 진태양시 보정 분(시계 + 보정 = 진태양시),
    tz 시계의 UTC 오프셋 시간, zi_rule 'next_day'(23시 이후 子時는 다음 날로 셈) 또는 'same_day',
    leap_rule 윤달 처리: 'same'(윤달을 그 달로), 'next'(다음 달로), 'split15'(15일까지 그 달, 16일부터 다음 달).
    """
    if male not in (True, False):
        raise ValueError('성별(male)은 True/False여야 한다')
    clock = _dt.datetime.strptime(f'{date} {time}', '%Y-%m-%d %H:%M')
    solar = clock + _dt.timedelta(minutes=solar_offset_min)
    h = ((solar.hour + 1) // 2) % 12                       # 子=0 … 亥=11
    day = solar.date()
    if zi_rule == 'next_day' and solar.hour == 23:
        day = day + _dt.timedelta(days=1)
    elif zi_rule not in ('next_day', 'same_day'):
        raise ValueError(zi_rule)
    lday = sxtwl.fromSolar(day.year, day.month, day.day)
    lm, ld, leap, ly = lday.getLunarMonth(), lday.getLunarDay(), bool(lday.isLunarLeap()), lday.getLunarYear()
    chart_month = lm
    if leap:
        if leap_rule == 'next' or (leap_rule == 'split15' and ld > 15):
            chart_month = lm % 12 + 1
        elif leap_rule not in ('same', 'next', 'split15'):
            raise ValueError(leap_rule)
    lunar_year_gz = gz60(ly - 4)

    # 사주: 년주는 立春 순간, 월주는 節 순간으로 가른다
    bjd = _jd(clock) - (tz - 8) / 24.0
    jl = jie_list(clock.year)
    prev = max(x for x in jl if x[0] <= bjd)
    nxt = min(x for x in jl if x[0] > bjd)
    lichun = max(x for x in jl if x[1] == 3 and x[0] <= bjd)
    ystem_year = _dt_from_jd(lichun[0], 8).year
    ygz = gz60(ystem_year - 4)
    mbr = JIE_BRANCH[prev[1]]
    mgz = month_stem(ygz[0], mbr) + mbr
    dg = lday.getDayGZ()
    dgz = STEM[dg.tg] + BR[dg.dz]
    hgz = STEM[(STEM.index(RAT[dgz[0]]) + h) % 10] + BR[h]

    return dict(
        input=dict(date=date, time=time, male=male, solar_offset_min=solar_offset_min, tz=tz, zi_rule=zi_rule, leap_rule=leap_rule),
        clock=clock, solar=solar, hour_index=h, hour_branch=BR[h],
        lunar=dict(year=ly, month=lm, day=ld, leap=leap, chart_month=chart_month, year_gz=lunar_year_gz),
        saju=dict(year=ygz, month=mgz, day=dgz, hour=hgz),
        jie_prev=dict(name=JIE_NAME[prev[1]], at=_dt_from_jd(prev[0], tz)),
        jie_next=dict(name=JIE_NAME[nxt[1]], at=_dt_from_jd(nxt[0], tz)),
        birth_jd_utc8=bjd, prev_jd=prev[0], next_jd=nxt[0],
        assumptions=dict(zi_rule=f'{zi_rule}: 가정(미확인)', leap_rule=f'{leap_rule}: 가정(미확인)'),
    )
