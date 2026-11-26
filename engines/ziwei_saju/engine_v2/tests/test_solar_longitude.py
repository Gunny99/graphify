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
