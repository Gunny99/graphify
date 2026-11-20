"""python -m engine_v2 1999-08-04 10:14 M [--solar-offset -38] [--tz 9] [--sihua nanyang|wangtingzhi] [--full]

L0·L1·L3 요약을 JSON으로 낸다. --full이면 전체 dict를 낸다.
"""
import argparse
import datetime as dt
import json
import sys

from . import compute
from .chart import summary


def _plain(x):
    if isinstance(x, (dt.datetime, dt.date)):
        return x.isoformat(timespec='minutes') if isinstance(x, dt.datetime) else x.isoformat()
    if isinstance(x, dict):
        return {str(k): _plain(v) for k, v in x.items()}
    if isinstance(x, (list, tuple, set)):
        return [_plain(v) for v in x]
    if hasattr(x, 'table') and hasattr(x, 'variant'):
        return dict(variant=x.variant, table=x.table)
    return x


def brief(r):
    ch, l1, l3 = r['chart'], r['l1'], r['l3']
    b = ch['birth']
    return dict(
        L0=dict(lunar=b['lunar'], saju=b['saju'], hour_branch=b['hour_branch'], ming=ch['ming'], shen=ch['shen'],
                ju=ch['ju_name'], mingzhu=ch['mingzhu'], shenzhu=ch['shenzhu'], kong=ch['kong'], birth_hua=ch['birth_hua'],
                changsheng=ch['changsheng'], assumptions=b['assumptions'],
                sihua_variant=ch['sihua_variant'], palaces=summary(ch),
                daewoon=dict(direction=r['daewoon']['direction'], years=round(r['daewoon']['years'], 2),
                             periods=[dict(gz=p['gz'], start=p['start']) for p in r['daewoon']['periods']]),
                daehan=[dict(palace=p['palace'], role=p['natal_role'], age=f"{p['age_from']}-{p['age_to']}", start=p['start'])
                        for p in r['daehan']]),
        L1=dict(empty=l1['empty'], pairs={k: dict(status=v['status'], sender=v['sender'], receiver=v['receiver'],
                                                  kong=v.get('kong'), confirmed=v.get('confirmed')) for k, v in l1['pairs'].items()},
                jehwa=l1['jehwa'], brightness=l1['brightness']['groups'], hua_on_weak=l1['brightness']['hua_on_weak'],
                natal_sanfang=l1['natal_sanfang'], lu=l1['lu'], gyeok=l1['gyeok'],
                natal_receptivity=dict(main_total=l1['receptivity']['natal_sanfang']['main_total'],
                                       none_count=l1['receptivity']['natal_sanfang']['none_count']),
                inflection=l1['inflection']),
        L3=dict(
            daehan=[dict(palace=p['palace'], start=p['start'], sanfang=p['sanfang'],
                         receptivity=dict(main_total=p['receptivity']['main_total'], none_count=p['receptivity']['none_count'],
                                          none=p['receptivity']['main_receives_none']),
                         ji_counts=p['ji_counts'], yukgil_new=p['yukgil_new'],
                         years=[dict(year=y['year'], gz=y['gz'], ji=(y['ji']['star'], y['ji']['palace']), frames=y['ji']['frames'],
                                     structural=y['ji']['structural']['label'],
                                     gaze=None if y['ji']['gaze'] is None else y['ji']['gaze']['label'],
                                     galim=[g['type'] for g in y['galim']], events=[e['kind'] for e in y['events']])
                                for y in p['years']]) for p in l3['path_daehan']],
            daewoon=[dict(gz=p['gz'], start=p['start'], marks=[(m['hua'], m['star'], m['palace'], m['copies']) for m in p['marks']],
                          overlaps=[(o['hua'], o['unit'], o['sources']) for o in p['overlaps']],
                          ji_structural=p['ji']['structural']['label'], events=p['events'],
                          lu_into_natal_sanfang=p['lu_into_natal_sanfang'], same_stem_years=p['same_stem_years'])
                     for p in l3['path_daewoon']],
            contrast=[dict(start=c['start'], end=c['end'], daehan=c['daehan'], daewoon=c['daewoon'], compare=c['compare'])
                      for c in l3['contrast']],
            exposure=l3['exposure'],
            order=l3['order'], frame_labels=l3['frame_labels'], seun_boundary=l3['seun_boundary']),
    )


def main(argv=None):
    ap = argparse.ArgumentParser(prog='python -m engine_v2')
    ap.add_argument('date', help='양력 YYYY-MM-DD')
    ap.add_argument('time', help='시계 시각 HH:MM')
    ap.add_argument('sex', choices=['M', 'F'])
    ap.add_argument('--solar-offset', type=int, default=0, help='진태양시 보정 분(시계 + 보정 = 진태양시)')
    ap.add_argument('--tz', type=float, default=9)
    ap.add_argument('--sihua', default=None, choices=[None, 'nanyang', 'wangtingzhi'])
    ap.add_argument('--zi-rule', default='next_day', choices=['next_day', 'same_day'])
    ap.add_argument('--leap-rule', default='same', choices=['same', 'next', 'split15'])
    ap.add_argument('--seun-boundary', default='lichun', choices=['lichun', 'seol', 'jan1'])
    ap.add_argument('--full', action='store_true')
    ap.add_argument('--report', default=None, metavar='경로', help='판정표 마크다운을 이 경로에 쓴다(JSON은 내지 않는다)')
    ap.add_argument('--rank-table', default=None, metavar='경로', help='--report의 6절에 붙일 표가 든 마크다운 파일(없으면 6절을 뺀다)')
    ap.add_argument('--report-years', default=None, metavar='처음-끝', help='--report 5절 해마다 표의 해 범위(예 2005-2065)')
    a = ap.parse_args(argv)
    r = compute(a.date, a.time, a.sex == 'M', a.solar_offset, a.tz, sihua_variant=a.sihua,
                zi_rule=a.zi_rule, leap_rule=a.leap_rule, seun_boundary=a.seun_boundary)
    if a.report:
        from . import report
        tbl = report.table_from_file(a.rank_table) if a.rank_table else None
        yrs = tuple(int(x) for x in a.report_years.split('-')) if a.report_years else None
        cmd = 'python -m engine_v2 ' + ' '.join(sys.argv[1:] if argv is None else argv)
        md = report.build(r, rank_table=tbl, cmd=cmd, years=yrs)
        with open(a.report, 'w', encoding='utf-8') as f:
            f.write(md)
        sys.stdout.write('%s (%d bytes)\n' % (a.report, len(md.encode('utf-8'))))
        return
    out = r if a.full else brief(r)
    json.dump(_plain(out), sys.stdout, ensure_ascii=False, indent=1)
    sys.stdout.write('\n')


if __name__ == '__main__':
    main()
