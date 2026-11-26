"""기계 OCR 일괄: PDF 쪽 → RapidOCR(PP-OCRv6) → 쪽별 jsonl 체크포인트.
사용: python -I ocr_batch.py worker <jobs.tsv> <wid> <nworkers> <outdir>
jobs.tsv: key\tpdf_path\tfirst\tlast (1-based 쪽, 한 묶음)
"""
import sys, os, json, re

AD = re.compile(r'获取更多|易学资料|加微信|微信[:：]|yixue8|易学巴巴|www\.|http|t\.cn|qq\d|QQ|进交流群|免费学习|Anna-s-Archive|z-lib\.org')

def check_key(key):
    if (not key or '/' in key or '\\' in key or '\0' in key or key in ('.', '..')
            or key.startswith('.') or os.path.isabs(key)):
        raise SystemExit(f"invalid key in jobs: {key!r}")

def order(boxes, txts, scores, W, H):
    items = []
    for b, t, s in zip(boxes, txts, scores):
        x0, x1 = float(b[:, 0].min()), float(b[:, 0].max())
        y0, y1 = float(b[:, 1].min()), float(b[:, 1].max())
        items.append(dict(x0=x0, x1=x1, y0=y0, y1=y1, t=t, s=float(s),
                          tall=(y1 - y0) > 1.5 * (x1 - x0) or (len(t) == 1 and (y1 - y0) >= (x1 - x0))))
    if not items:
        return [], False, False
    ntall = sum(i['tall'] for i in items)
    vertical = ntall >= 0.5 * len(items)
    spread = W > 1.15 * H
    halves = [items]
    if spread:
        mid = W / 2
        L = [i for i in items if (i['x0'] + i['x1']) / 2 < mid]
        R = [i for i in items if (i['x0'] + i['x1']) / 2 >= mid]
        halves = [R, L] if vertical else [L, R]
    out = []
    for h in halves:
        if vertical:
            # 오른쪽 열부터: x 중심 내림차순으로 열 묶기, 열 안에서 y 오름차순
            h = sorted(h, key=lambda i: -(i['x0'] + i['x1']) / 2)
            cols = []
            for i in h:
                c = (i['x0'] + i['x1']) / 2
                w = max(i['x1'] - i['x0'], 1)
                if cols and abs(cols[-1]['c'] - c) < 0.5 * w and i['tall']:
                    cols[-1]['m'].append(i)
                else:
                    cols.append(dict(c=c, m=[i]))
            # 가로 상자(제목 등)는 y가 작은 것부터 앞에
            for col in cols:
                out.extend(sorted(col['m'], key=lambda i: i['y0']))
        else:
            h = sorted(h, key=lambda i: (i['y0'] + i['y1']) / 2)
            rows = []
            for i in h:
                cy = (i['y0'] + i['y1']) / 2
                hh = max(i['y1'] - i['y0'], 1)
                if rows and abs(rows[-1]['cy'] - cy) < 0.5 * hh:
                    rows[-1]['m'].append(i)
                else:
                    rows.append(dict(cy=cy, m=[i]))
            for r in rows:
                out.extend(sorted(r['m'], key=lambda i: i['x0']))
    return out, vertical, spread

def main():
    _, jobs, wid, nw, outdir = sys.argv[1:6]
    wid, nw = int(wid), int(nw)
    lines = [l.rstrip('\n').split('\t') for l in open(jobs, encoding='utf-8') if l.strip()]
    for row in lines:
        check_key(row[0])
    import pymupdf
    from rapidocr import RapidOCR
    eng = RapidOCR(params={"EngineConfig.onnxruntime.intra_op_num_threads": 1,
                           "EngineConfig.onnxruntime.inter_op_num_threads": 1})
    os.makedirs(outdir, exist_ok=True)
    for k, (key, pdf, a, b) in enumerate(lines):
        if k % nw != wid:
            continue
        a, b = int(a), int(b)
        fn = os.path.join(outdir, f"{key}.{a:05d}.jsonl")
        done = set()
        if os.path.exists(fn):
            good, bad = [], False
            with open(fn, encoding='utf-8', errors='replace') as rf:
                for l in rf:
                    if not l.strip():
                        continue
                    try:
                        done.add(json.loads(l)['p'])
                        good.append(l if l.endswith('\n') else l + '\n')
                    except (ValueError, KeyError, TypeError):
                        bad = True
            if bad:
                with open(fn + '.tmp', 'w', encoding='utf-8') as wf:
                    wf.writelines(good)
                os.replace(fn + '.tmp', fn)
        doc = pymupdf.open(pdf)
        with open(fn, 'a', encoding='utf-8') as f:
            for p in range(a, b + 1):
                if p in done:
                    continue
                pg = doc[p - 1]
                long = max(pg.rect.width, pg.rect.height)
                zoom = max(200 / 72, 2000 / long)
                pix = pg.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), colorspace=pymupdf.csRGB)
                png = pix.tobytes('png')
                r = eng(png)
                rec = dict(p=p, W=pix.width, H=pix.height, lines=[], vertical=None, spread=None)
                if r.boxes is not None and len(r.boxes) > 0:
                    o, v, s = order(r.boxes, r.txts, r.scores, pix.width, pix.height)
                    rec['vertical'], rec['spread'] = v, s
                    for i in o:
                        if AD.search(i['t']):
                            continue
                        rec['lines'].append([i['t'], round(i['s'], 3),
                                             [round(i['x0']), round(i['y0']), round(i['x1']), round(i['y1'])]])
                f.write(json.dumps(rec, ensure_ascii=False) + '\n')
                f.flush()
        print(f"[w{wid}] done {key} {a}-{b}", flush=True)

if __name__ == '__main__':
    main()
