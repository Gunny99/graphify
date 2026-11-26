# ocr-batch / ocr-assemble

스캔 PDF를 모델 사용량 없이 기계 OCR해 쪽별 md로 만드는 도구. 결과는 교정 전(未校)이다.

1. `ocr_batch.py`: RapidOCR(PP-OCRv6 small, onnxruntime CPU)로 쪽마다 줄·신뢰도·상자를 jsonl에 붙여 쓴다. 쪽 단위 체크포인트라 중단 후 같은 명령으로 이어진다. 세로쓰기는 오른쪽 열부터, 펼친면은 세로면 오른쪽 면부터 읽는다. 광고 워터마크 줄은 버린다.
   ```
   python -m venv ocrenv && ocrenv/bin/pip install rapidocr onnxruntime pymupdf
   # jobs.tsv: key<TAB>pdf<TAB>first<TAB>last (40쪽 묶음 권장)
   for w in 0 1 2 3; do ocrenv/bin/python -I ocr_batch.py worker jobs.tsv $w 4 ocrout & done
   ```
2. `../ocr-assemble`(Rust): jsonl을 책별 `<key>.md`, `<key>.lowconf.tsv`(신뢰도 0.8 미만 줄), `00_목록.md`로 조립한다.
   ```
   cargo build --release --manifest-path ../ocr-assemble/Cargo.toml
   ../ocr-assemble/target/release/ocr-assemble --jsonl-dir ocrout --jobs jobs.tsv --books books.tsv --out out
   ```

4코어 CPU에서 쪽당 약 1~5초(판면 밀도에 따라). 저신뢰 줄은 인용할 때만 상자 좌표로 원본을 잘라 다시 읽는다.
