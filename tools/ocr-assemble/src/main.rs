use serde_json::Value;
use std::collections::BTreeMap;
use std::fmt::Write as _;
use std::fs;
use std::path::Path;

struct Line { text: String, score: f64, bbox: [f64; 4] }
struct Page { vertical: Option<bool>, lines: Vec<Line> }

fn parse_line(s: &str) -> Option<(u64, Page)> {
    let v: Value = serde_json::from_str(s.trim()).ok()?;
    let p = v.get("p")?.as_u64()?;
    let mut lines = vec![];
    for l in v.get("lines")?.as_array()? {
        let a = l.as_array()?;
        let b = a.get(2)?.as_array()?;
        let g = |i: usize| b.get(i).and_then(Value::as_f64).unwrap_or(0.0);
        lines.push(Line {
            text: a.first()?.as_str()?.to_string(),
            score: a.get(1)?.as_f64()?,
            bbox: [g(0), g(1), g(2), g(3)],
        });
    }
    Some((p, Page { vertical: v.get("vertical").and_then(Value::as_bool), lines }))
}

/// Later occurrences of a page overwrite earlier ones; unparsable (truncated) lines are skipped.
fn load_pages(text: &str, pages: &mut BTreeMap<u64, Page>) {
    for s in text.lines() {
        if let Some((p, pg)) = parse_line(s) { pages.insert(p, pg); }
    }
}

fn render(key: &str, pdf: &str, pages: &BTreeMap<u64, Page>, total: u64, low: f64) -> (String, String) {
    let mut md = format!(
        "# {key} — 기계 OCR 未校\n> 원본 PDF: {pdf} · 엔진 RapidOCR 3.10(PP-OCRv6 small, CPU) · 교정 전 기계 전사. 전서·전집 확정본과 섞지 말 것. 〔?〕 표시는 신뢰도 {low} 미만 줄. 완료 {}/{total}쪽.\n",
        pages.len());
    let mut tsv = String::from("p\tidx\tscore\ttext\tx0\ty0\tx1\ty1\n");
    for (p, pg) in pages {
        let _ = write!(md, "\n## p.{p:04}\n");
        if pg.lines.is_empty() { md.push_str("（빈 쪽 또는 그림）\n"); }
        for (i, l) in pg.lines.iter().enumerate() {
            let lowc = l.score < low;
            if lowc {
                md.push_str("〔?〕");
                let t = l.text.replace(['\t', '\n', '\r'], " ");
                let _ = writeln!(tsv, "{p}\t{i}\t{:.4}\t{t}\t{}\t{}\t{}\t{}", l.score, l.bbox[0], l.bbox[1], l.bbox[2], l.bbox[3]);
            }
            md.push_str(&l.text);
            md.push('\n');
        }
    }
    (md, tsv)
}

fn tsv_rows(path: &str) -> Vec<Vec<String>> {
    fs::read_to_string(path).unwrap_or_default().lines()
        .map(|l| l.split('\t').map(String::from).collect()).filter(|r: &Vec<String>| r.len() >= 2).collect()
}

fn arg(args: &[String], name: &str) -> Option<String> {
    args.iter().position(|a| a == name).and_then(|i| args.get(i + 1)).cloned()
}

fn main() {
    let args: Vec<String> = std::env::args().collect();
    let (Some(dir), Some(jobs), Some(books), Some(out)) =
        (arg(&args, "--jsonl-dir"), arg(&args, "--jobs"), arg(&args, "--books"), arg(&args, "--out"))
    else { eprintln!("usage: ocr-assemble --jsonl-dir DIR --jobs FILE --books FILE --out DIR [--low 0.8]"); std::process::exit(2) };
    let low: f64 = arg(&args, "--low").and_then(|s| s.parse().ok()).unwrap_or(0.8);
    fs::create_dir_all(&out).expect("create out dir");
    let mut totals: BTreeMap<String, u64> = BTreeMap::new();
    for r in tsv_rows(&jobs) {
        if let Some(last) = r.get(3).and_then(|s| s.trim().parse::<u64>().ok()) {
            let e = totals.entry(r[0].clone()).or_insert(0);
            *e = (*e).max(last);
        }
    }
    let mut names: Vec<String> = fs::read_dir(&dir).map(|d| d.flatten().map(|e| e.file_name().to_string_lossy().into_owned()).collect()).unwrap_or_default();
    names.sort();
    let mut idx = String::from("# 기계 OCR 목록\n\n| key | 쪽(완료/전체) | 글자수 | 저신뢰 줄 | 저신뢰 비율 | 세로쪽 비율 |\n|---|---|---|---|---|---|\n");
    for r in tsv_rows(&books) {
        let (key, pdf) = (&r[0], &r[1]);
        let pre = format!("{key}.");
        let mut pages = BTreeMap::new();
        for n in &names {
            let ok = n.strip_prefix(&pre).and_then(|s| s.strip_suffix(".jsonl")).is_some_and(|m| !m.is_empty() && m.bytes().all(|b| b.is_ascii_digit()));
            if ok {
                // lossy: a partially written multibyte tail must not abort the read
                let bytes = fs::read(Path::new(&dir).join(n)).unwrap_or_default();
                load_pages(&String::from_utf8_lossy(&bytes), &mut pages);
            }
        }
        let total = totals.get(key).copied().unwrap_or(0).max(pages.keys().next_back().copied().unwrap_or(0));
        let (md, tsv) = render(key, pdf, &pages, total, low);
        let _ = fs::write(Path::new(&out).join(format!("{key}.md")), md);
        let _ = fs::write(Path::new(&out).join(format!("{key}.lowconf.tsv")), tsv);
        let nl: usize = pages.values().map(|p| p.lines.len()).sum();
        let nlow = pages.values().flat_map(|p| &p.lines).filter(|l| l.score < low).count();
        let chars: usize = pages.values().flat_map(|p| &p.lines).map(|l| l.text.chars().count()).sum();
        let vert = pages.values().filter(|p| p.vertical == Some(true)).count();
        let pct = |a: usize, b: usize| if b == 0 { "-".into() } else { format!("{:.1}%", a as f64 * 100.0 / b as f64) };
        let _ = writeln!(idx, "| {key} | {}/{total} | {chars} | {nlow} | {} | {} |", pages.len(), pct(nlow, nl), pct(vert, pages.len()));
    }
    fs::write(Path::new(&out).join("00_목록.md"), idx).expect("write index");
}

#[cfg(test)]
mod tests {
    use super::*;
    const A: &str = r#"{"p":1,"W":1,"H":1,"vertical":true,"spread":null,"lines":[["甲",0.95,[0,0,1,1]],["乙",0.5,[1,2,3,4]]]}"#;

    #[test]
    fn dedupe_keeps_last() {
        let mut m = BTreeMap::new();
        load_pages(&format!("{A}\n{}\n", A.replace("甲", "丙")), &mut m);
        assert_eq!(m.len(), 1);
        assert_eq!(m[&1].lines[0].text, "丙");
    }
    #[test]
    fn lowconf_marked() {
        let mut m = BTreeMap::new();
        load_pages(A, &mut m);
        m.insert(2, Page { vertical: None, lines: vec![] });
        let (md, tsv) = render("k", "k.pdf", &m, 5, 0.8);
        assert!(md.contains("완료 2/5쪽"));
        assert!(md.contains("\n甲\n") && md.contains("〔?〕乙"));
        assert!(md.contains("## p.0002\n（빈 쪽 또는 그림）"));
        assert!(tsv.contains("1\t1\t0.5000\t乙\t1\t2\t3\t4"));
    }
    #[test]
    fn truncated_tail_ignored() {
        let mut m = BTreeMap::new();
        load_pages(&format!("{A}\n{{\"p\":2,\"lines\":[[\"x\",0."), &mut m);
        assert_eq!(m.len(), 1);
    }
}
