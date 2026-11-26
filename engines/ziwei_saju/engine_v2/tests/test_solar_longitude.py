"""진태양시 경도 보정(resolve longitude·meridian·eot)과 CLI. 균시차는 Rust solar.rs와 같은 식."""
import json
import subprocess
import sys

import pytest

from engine_v2 import compute
from engine_v2.calendar import equation_of_time, resolve
from engine_v2.tests.target import DATE, KW, MALE, OLD, TIME


def test_basis_values():
    b = resolve(DATE, TIME, MALE, **KW)
    sb = b['solar_basis']
    assert sb['lon_correction_min'] == pytest.approx(-33.2, abs=0.01)
    assert sb['eot_min'] == pytest.approx(-6.33, abs=0.01)        # Rust solar.rs: -6.33
    assert sb['meridian'] == 135.0
    assert (b['solar'].hour, b['solar'].minute) == (9, 30)          # 09:30:28
    assert abs(b['solar'].hour * 60 + b['solar'].minute - (9 * 60 + 31)) <= 1
    assert b['hour_branch'] == '巳' and b['hour_index'] == 5
    assert b['saju']['year'] + ' ' + b['saju']['month'] + ' ' + b['saju']['day'] + ' ' + b['saju']['hour'] == '己卯 辛未 戊子 丁巳'


def test_old_input_same_chart_and_saju():
    new = compute(DATE, TIME, MALE, **KW, with_l3=False)
    old = compute(*OLD, with_l3=False)          # 옛 입력, 같은 巳時 명반
    assert old['chart']['birth']['hour_branch'] == new['chart']['birth']['hour_branch'] == '巳'
    assert old['chart']['birth']['saju'] == new['chart']['birth']['saju']
    assert old['chart']['birth']['lunar'] == new['chart']['birth']['lunar']
    for k in ('ming', 'shen', 'ju', 'pos', 'palaces', 'birth_hua', 'kong', 'changsheng'):
        assert old['chart'][k] == new['chart'][k], k


def test_no_eot_and_meridian():
    b = resolve(DATE, TIME, MALE, longitude=126.7, eot=False)
    assert b['solar_basis']['eot_min'] == 0.0
    b = resolve(DATE, TIME, MALE, longitude=127.5, meridian=127.5)     # 1954~61 UTC+8:30 입력 예
    assert b['solar_basis']['lon_correction_min'] == 0.0


def test_both_offset_and_longitude_is_error():
    with pytest.raises(ValueError):
        resolve(DATE, TIME, MALE, -38, longitude=126.7)
    with pytest.raises(ValueError):
        resolve(DATE, TIME, MALE, meridian=135.0)


def test_eot_matches_rust_values():
    # solar.rs의 같은 식(tests/solar.rs 출력과 맞춘 값, ±0.01분)
    assert equation_of_time(1999, 8, 4) == pytest.approx(-6.33, abs=0.01)


def test_zi_rule_uses_solar_time():
    # 시계 23:50 + (-39.5) = 23:10 → 子時, 다음 날로 셈
    b = resolve('1999-08-04', '23:50', True, **KW)
    assert b['hour_branch'] == '子' and b['solar'].hour == 23
    # 시계 00:20 → 전날 23:40 (진태양시), 날짜 경계를 넘어 전날로 셈
    b = resolve('1999-08-05', '00:20', True, **KW)
    assert b['solar'].day == 4 and b['hour_branch'] == '子'


def test_cli_and_default_cmd():
    from engine_v2 import report
    r = compute(DATE, TIME, MALE, **KW)
    assert report.default_cmd(r) == 'python -m engine_v2 1999-08-04 10:10 M --longitude 126.7'
    r2 = compute(DATE, TIME, MALE, longitude=127.5, meridian=127.5, eot=False)
    assert report.default_cmd(r2).endswith('--longitude 127.5 --meridian 127.5 --no-eot')
    assert '--solar-offset -38' in report.default_cmd(compute(*OLD, with_l3=False) | {'chart': compute(*OLD, with_l3=False)['chart']})
    out = subprocess.run([sys.executable, '-m', 'engine_v2', DATE, TIME, 'M', '--longitude', '126.7'],
                         capture_output=True, text=True, check=True, cwd=__import__('os').path.dirname(__import__('os').path.dirname(__import__('os').path.dirname(__file__))))
    assert json.loads(out.stdout)['L0']['hour_branch'] == '巳'
    bad = subprocess.run([sys.executable, '-m', 'engine_v2', DATE, TIME, 'M', '--longitude', '126.7', '--solar-offset', '-38'],
                         capture_output=True, text=True, cwd=__import__('os').path.dirname(__import__('os').path.dirname(__import__('os').path.dirname(__file__))))
    assert bad.returncode != 0


# ---- 고객 선택(choices): 윤달, 子時(진태양시 23:00~00:59) ----
def _kinds(b):
    return {c['kind']: c for c in b['choices']}


def test_choices_empty_for_target():
    assert resolve(DATE, TIME, MALE, **KW)['choices'] == []


def test_choices_leap_2023():
    b = resolve('2023-03-31', '12:00', True)               # 2023 윤2월 10일
    assert b['lunar']['leap'] and b['lunar']['month'] == 2 and b['lunar']['day'] == 10
    c = _kinds(b)['leap']
    assert [o['rule'] for o in c['options']] == ['same', 'next', 'split15']
    assert [o['chart_month'] for o in c['options']] == [2, 3, 2]       # 10일은 15일 이전이라 split15는 그 달
    assert c['chosen'] is None and c['default'] == 'same'
    assert c['options'][0]['ming'] != c['options'][1]['ming'] and c['same_result'] is False
    assert all(o['ju_name'] and o['shen'] for o in c['options'])
    b2 = resolve('2023-03-31', '12:00', True, leap_rule='next')
    assert _kinds(b2)['leap']['chosen'] == 'next' and b2['lunar']['chart_month'] == 3
    b3 = resolve('2023-04-10', '12:00', True)               # 윤2월 20일: split15는 다음 달
    assert [o['chart_month'] for o in _kinds(b3)['leap']['options']] == [2, 3, 3]


def test_zi_is_not_a_choice():
    for t in ('23:30', '00:30'):
        assert 'zi' not in _kinds(resolve('2000-03-02', t, True))


def _day_gz(date, time, rule, **kw):
    b = resolve(date, time, True, zi_rule=rule, **kw)
    return b['saju']['day'], b['lunar']['day'], b['hour_branch']


def test_prev_day_rule():
    # 23:30: prev_day와 same_day는 그날, next_day는 다음 날
    assert _day_gz('2000-03-01', '23:30', 'prev_day') == _day_gz('2000-03-01', '23:30', 'same_day')
    assert _day_gz('2000-03-01', '23:30', 'prev_day')[0] != _day_gz('2000-03-01', '23:30', 'next_day')[0]
    # 00:30: prev_day는 전날 일주·전날 음력 일, 다른 규칙은 그날
    prev = _day_gz('2000-03-02', '00:30', 'prev_day')
    assert prev[:2] == _day_gz('2000-03-01', '12:00', 'next_day')[:2]
    assert prev[0] != _day_gz('2000-03-02', '00:30', 'next_day')[0]
    assert _day_gz('2000-03-02', '00:30', 'same_day') == _day_gz('2000-03-02', '00:30', 'next_day')
    assert prev[2] == '子'
    # 시계 00:20 → 경도 보정으로 진태양시 전날 23:40: 규칙과 무관하게 전날 23시대
    b = resolve('1999-08-05', '00:20', True, zi_rule='prev_day', **KW)
    assert (b['solar'].day, b['solar'].hour, b['solar'].minute) == (4, 23, 40)
    assert b['saju']['day'] == resolve('1999-08-04', '12:00', True)['saju']['day']
    n = resolve('1999-08-05', '00:20', True, zi_rule='next_day', **KW)       # next_day는 시계 날짜
    assert n['saju']['day'] == resolve('1999-08-05', '12:00', True)['saju']['day']
    # 시계 23:30이라도 보정으로 22:50이면 子時가 아니라 亥時
    assert resolve('1999-08-04', '23:30', True, zi_rule='prev_day', **KW)['hour_branch'] == '亥'
    assert resolve('2000-03-01', '23:30', True)['input']['zi_rule'] == 'prev_day'      # 기본값(Gunny 11-26 확정)


def test_pending_choice_warns_on_cli_and_report():
    import os
    cwd = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    run = lambda *a: subprocess.run([sys.executable, '-m', 'engine_v2', *a], capture_output=True, text=True, check=True, cwd=cwd)
    r = run('2023-03-31', '12:00', 'M')
    assert '고객 선택 필요' in r.stderr and 'leap' in r.stderr
    assert run('2023-03-31', '12:00', 'M', '--leap-rule', 'next').stderr == ''
    assert run('2000-03-01', '23:30', 'M').stderr == ''            # 子時는 고객 선택이 아니다
    assert run('2000-03-02', '00:30', 'M', '--zi-rule', 'prev_day').stderr == ''
    from engine_v2 import report
    assert '고객 선택 필요' in report.build(compute('2023-03-31', '12:00', True))
    assert '고객 선택 필요' not in report.build(compute('2023-03-31', '12:00', True, leap_rule='same'))
    assert '고객 선택 필요' not in report.build(compute(DATE, TIME, MALE, **KW))


# ---- PR #14 레드팀 반영 ----
def test_eot_only_vector():
    b = resolve('2026-11-26', '12:00', True, longitude=135, meridian=135)
    assert abs(b['solar'].hour * 60 + b['solar'].minute - (12 * 60 + 12)) <= 1      # 진태양시 = 시계 + 0 + EoT(+12.4분)


def test_leap_rule_vectors():
    def months(d):
        c = _kinds(resolve(d, '12:00', True))['leap']
        return {o['rule']: o['chart_month'] for o in c['options']}
    assert months('2023-03-30') == {'same': 2, 'next': 3, 'split15': 2}      # 윤2월 9일
    assert months('2023-04-10') == {'same': 2, 'next': 3, 'split15': 3}      # 윤2월 20일


def test_zi_boundary_vectors_1993():
    def r(t, rule):
        b = resolve('1993-05-20', t, True, zi_rule=rule)
        return b['hour_branch'], b['lunar']['month'], b['lunar']['day'], b['lunar']['leap']
    assert r('23:40', 'next_day') == ('子', 4, 1, False)
    assert r('23:40', 'same_day') == ('子', 3, 29, True)
    assert r('23:40', 'prev_day') == ('子', 3, 29, True)         # 23시대는 same_day와 같다. 다른 점은 00시대
    assert r('22:59', 'next_day')[0] == '亥' and r('22:59', 'next_day')[1:] == (3, 29, True)      # 날짜 넘김 없음
    assert r('23:00', 'next_day') == ('子', 4, 1, False)
    assert r('23:00', 'same_day') == ('子', 3, 29, True)


def test_zi_boundary_is_solar_not_clock():
    # 시계 23:10 + 보정(-39.5분) = 진태양시 22:30 → 亥, 다음 날로 넘기지 않는다
    b = resolve('1999-08-04', '23:10', True, zi_rule='next_day', **KW)
    assert b['hour_branch'] == '亥' and (b['solar'].hour, b['solar'].day) == (22, 4)
    assert b['lunar'] == resolve('1999-08-04', '12:00', True)['lunar'] | dict(chart_month=b['lunar']['chart_month'])
    # 반대로 시계 23:50(+보정 없음)은 子時, 시계 23:30 + 보정 +20분(경도 +5)도 子時
    assert resolve('1999-08-04', '23:30', True, longitude=140.0, meridian=135.0, eot=False)['hour_branch'] == '子'


def test_rule_validation_up_front():
    for kw in (dict(leap_rule='bogus'), dict(zi_rule='bogus')):
        with pytest.raises(ValueError):
            resolve('1999-08-04', '12:00', True, **kw)      # 윤달·子時가 아니어도 오류


def test_default_zi_rule_prev_day_and_target_unaffected():
    b = resolve(DATE, TIME, MALE, **KW)
    assert b['input']['zi_rule'] == 'prev_day' and b['assumptions']['zi_rule'] == 'prev_day: Gunny 11-26 확정'
    base = compute(DATE, TIME, MALE, **KW, with_l3=False)['chart']
    for rule in ('next_day', 'same_day', 'prev_day'):          # 대상 명식(巳時)은 규칙과 무관
        c = compute(DATE, TIME, MALE, **KW, zi_rule=rule, with_l3=False)['chart']
        assert c['birth']['saju'] == base['birth']['saju'] and c['pos'] == base['pos'] and c['ming'] == base['ming']
    # 00:30은 기본값에서 전날 날짜
    d = resolve('2000-03-02', '00:30', True)
    assert d['saju']['day'] == resolve('2000-03-01', '12:00', True)['saju']['day']
    from engine_v2 import report
    assert 'zi-rule' not in report.default_cmd(compute('2000-03-02', '00:30', True, with_l3=False))
    assert '--zi-rule next_day' in report.default_cmd(compute('2000-03-02', '00:30', True, zi_rule='next_day', with_l3=False))
