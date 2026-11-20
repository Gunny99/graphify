"""판정표 생성기 시험: 대상 명반과 test_generality의 CASES 여덟에서 예외 없이 문서가 나온다."""
import pytest

from engine_v2 import compute, report
from engine_v2.tests.test_generality import CASES

TARGET = ('1999-08-04', '10:14', True, -38)
TABLE = '| 갈래 | 동궁 |\n|---|---|\n| 이해 | 2 |'
TITLES = ('## 1. 명반', '## 2. 구조 판독(L1)', '## 3. 궁별 글귀 판정(L2)', '## 4. 등급', '## 5. 운(L3)', '## 6. 능력 차례')


@pytest.fixture(scope='module')
def target_doc():
    return report.build(compute(*TARGET), rank_table=TABLE)


@pytest.mark.parametrize('case', [TARGET] + CASES, ids=lambda c: c[0] + ('*' if c == TARGET else ''))
def test_doc_builds_with_six_sections(case):
    md = report.build(compute(*case), rank_table=TABLE)
    heads = [ln for ln in md.splitlines() if ln.startswith('## ')]
    for t in TITLES:
        assert any(h.startswith(t) for h in heads), t
    assert md.splitlines()[-1].startswith('생성: ')


def test_no_rank_table_drops_section_6():
    md = report.build(compute(*TARGET))
    assert '## 6.' not in md and '## 5.' in md


def test_chou_daehan_sanfang_ji(target_doc):
    rows = [[c.strip() for c in ln.strip('|').split('|')] for ln in target_doc.splitlines()
            if ln.startswith('| 丑 | 대한삼방 |')]
    assert len(rows) == 1
    r = rows[0]            # 대한, 틀, 록, 권, 과, 기, 화기 중첩, ...
    assert r[5] == '6/10' and r[6] == '3'


def test_year_range_trims():
    md = report.build(compute(*TARGET), years=(2005, 2065))
    assert '| 2066' not in md and '| 2065' in md


def test_section3_starts_with_ming_and_shen(target_doc):
    i = target_doc.index('## 3. 궁별 글귀 판정(L2)')
    j = target_doc.index('## 4. 등급')
    sec = target_doc[i:j]
    assert sec.index('### 명궁 (寅)') < sec.index('### 신궁 (子)') < sec.index('### 형제궁')
    assert '入限:396' in sec


def test_section3_enum_column_and_branch_text(target_doc):
    i = target_doc.index('## 3. 궁별 글귀 판정(L2)')
    sec = target_doc[i:target_doc.index('## 4. 등급')]
    assert '| 열거 |' in sec and '별의 성질 서술' in sec
    # 가지로 나눈 문장은 그 가지의 글귀만 싣는다: 580#1 행에 같은 문장의 불합 가지(不喜六癸生人)가 없다
    row = [ln for ln in sec.splitlines() if ln.startswith('| 入限:580#1')][0]
    assert '不喜六癸生人' not in row and '遇火鈴' in row


def test_section2_gyeok_extras_and_section5_daehyung_table(target_doc):
    i = target_doc.index('## 2. 구조 판독(L1)')
    sec2 = target_doc[i:target_doc.index('## 3. 궁별 글귀 판정(L2)')]
    assert '화탐격(R25)' in sec2 and '명궁 주성 파군·탐랑(R26)' in sec2
    sec5 = target_doc[target_doc.index('## 5. 운(L3)'):target_doc.index('## 6. 능력 차례')]
    assert 'daehyung' in sec5 and 'k_effective' in sec5


def test_unconfirmed_condition_is_not_asserted():
    from engine_v2 import compute
    from engine_v2.report import _sec7
    R = compute('1999-08-04', '10:14', True, -38)
    row = [l for l in '\n'.join(_sec7(R)).splitlines() if l.startswith('| SJ29 ') and '지능' in l][0]
    assert '단정하지 않는다' in row


def test_joined_passage_shows_full_sentence():
    p = {'id': '妻:47', 'text': '無四殺', 'text_full': '太陽同。無四殺', 'joins': ['妻:46']}
    assert report._txt(p) == '太陽同。無四殺'
    assert report._txt(dict(p, id='妻:47#1', clause='가지')) == '가지'
    assert report._txt({'id': 'a', 'text': 't'}) == 't'
