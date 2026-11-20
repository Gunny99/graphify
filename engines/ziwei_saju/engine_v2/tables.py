"""data/의 십간사화표와 밝기표를 읽는다. 표는 한 벌씩이고 칸마다 출처가 있다."""
from .common import HUA, STEM, load_json


class Sihua:
    """십간사화표. table[천간] = {'록': 별, ...}. source[(천간, 화)] = 출처."""

    def __init__(self, variant=None, overrides=None):
        raw = load_json('sihua.json')
        self.table = {s: {h: raw['default'][s][h]['star'] for h in HUA} for s in STEM}
        self.source = {(s, h): raw['default'][s][h]['source'] for s in STEM for h in HUA}
        cells = {}
        if variant:
            v = raw['variants'][variant]
            cells.update({k: (val, v['_source']) for k, val in v.items() if not k.startswith('_')})
        for k, val in (overrides or {}).items():
            cells[k] = (val, '호출자 설정')
        for k, (val, src) in cells.items():
            if k not in raw['configurable_cells']:
                raise ValueError(f'설정으로 바꿀 수 없는 칸: {k}')
            s, h = k.split('.')
            self.table[s][h] = val
            self.source[(s, h)] = src
        self.variant = variant or 'default'

    def of(self, stem):
        return dict(self.table[stem])

    def received(self, star):
        """별이 받는 사화: {'록': [천간...], ...}(빈 화는 빠짐)."""
        out = {}
        for s in STEM:
            for h in HUA:
                if self.table[s][h] == star:
                    out.setdefault(h, []).append(s)
        return out


class Brightness:
    def __init__(self):
        raw = load_json('brightness.json')
        self.cells = {(c['star'], c['branch']): c for c in raw['cells']}
        self.cls = raw['class']

    def grade(self, star, branch):
        c = self.cells.get((star, branch))
        return None if c is None else c['grade']

    def source(self, star, branch):
        c = self.cells.get((star, branch))
        return None if c is None else c['layer']

    def klass(self, grade):
        """묘왕 / 평 / 함 / 미확인."""
        return '미확인' if grade is None else self.cls[grade]
