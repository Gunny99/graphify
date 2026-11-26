# 계산코드 (2026-11-14 현행)

자미두수 판정은 `engine_v2/`가 한다. 규칙의 원본은 `../원점재검토_20261111/10_모델명세.md`다. 코드를 고치면 명세와 함께 맞춘다.

## engine_v2

아무 생년월일시를 받아 명식·명반·운 기간(L0), 구조 판독(L1), 궁별 글귀 판정(L2), 등급, 운(L3)을 구조화된 사실로 낸다. 명반 하나의 값은 코드에 없다. 설계와 한계는 `engine_v2/README.md`, 상태는 `engine_v2/STATE.md`에 있다.

```
pip install sxtwl pytest
cd engines/ziwei_saju
python -m engine_v2 1999-08-04 10:10 M --longitude 126.7                  # 요약 JSON
python -m engine_v2 1999-08-04 10:10 M --longitude 126.7 --full           # 전체 JSON
python -m engine_v2 1999-08-04 10:10 M --longitude 126.7 \
  --report ../02_판정표_engine_v2.md \
  --rank-table ../원점재검토_20261111/60_지적능력_모집단차례.md              # 판정표 문서
python -m pytest engine_v2/tests -q                                        # 시험
```

출력은 둘이다. JSON은 층별 사실이고, `--report`는 그 사실에서 만든 마크다운 판정표(명반, 구조, 궁별 구절, 등급, 운, 능력 차례)다. 판정표에는 해석문과 권고가 없고 엔진이 낸 사실과 원문 구절과 수만 있다. `--rank-table`을 빼면 능력 차례 절이 빠진다. `--report-years 2005-2065`로 해마다 표의 범위를 줄일 수 있다. 

옛 판(byeonseong)은 올리지 않았다.
