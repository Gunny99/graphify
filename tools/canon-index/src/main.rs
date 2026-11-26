use canon_index::cases::{cases_json, collect_cases, sealed_jsonl, summary_md};
use canon_index::norm::normalize;
use canon_index::passage::*;
use serde_json::Value;
use std::collections::BTreeMap;
use std::fs;
use std::io::Write;
use std::path::{Path, PathBuf};

const JEONSEO: &str = "/mnt/project-files/ZWDS_LIBRARY/02_primary/전서_확정본/전서_확정본.txt";
const JEONJIP_DIR: &str = "/mnt/project-files/ZWDS_LIBRARY/02_primary/전집_확정본";
const OCR_DIR: &str = "/mnt/project-files/OCR_기계전사_未校";
const TXT_DIR: &str = "/mnt/project-files";
const DALBAT_ROOT: &str = "/mnt/project-files/ZWDS_LIBRARY/01_raw";
const OUT_DIR: &str = "/mnt/project-files/간명모델_원전학습/index";

const TXT_FILES: &[&str] = &[
    "1016036253-中州派紫微斗数深造讲义-上.txt",
    "1043918902-斗数四书-八喜楼钞本古诀与斗数格局.txt",
    "1067563089-王亭之-斗数四书-二-骨髓赋与女命骨髓赋.txt",
    "433892448-紫微斗數講義.txt",
    "507050814-斗数宣微第三集-斗数观测录.txt",
    "664522149-陆斌兆紫微斗数斗数讲义评注.txt",
    "708087138-王亭之-安星法与推断实例.txt",
    "761380858-王亭之-安星法与推断实例.txt",
    "761380908-王亭之注-太微赋.txt",
    "826283561-王亭之-谈斗数.txt",
    "828612316-中州派紫微斗数深造讲义-王亭之.txt",
    "871559757-王亭之-斗数零谈.txt",
    "902759887-王亭之谈斗数b.txt",
    "910674556-王亭之-中州派紫微斗数深造讲义-上.txt",
    "910674898-王亭之-中州派紫微斗数深造讲义-下.txt",
    "934352038-談紫微斗數-王亭之-閱.txt",
    "939555762-王亭之谈星-精排.txt",
    "991103935-骨髓赋.txt",
];

struct Opts {
    jeonseo: PathBuf,
    jeonjip: PathBuf,
    ocr: PathBuf,
    txt: PathBuf,
    dalbat: PathBuf,
    out: PathBuf,
}

fn opts(args: &[String]) -> Opts {
    let mut o = Opts {
        jeonseo: JEONSEO.into(),
        jeonjip: JEONJIP_DIR.into(),
        ocr: OCR_DIR.into(),
        txt: TXT_DIR.into(),
        dalbat: DALBAT_ROOT.into(),
        out: OUT_DIR.into(),
    };
    let mut i = 0;
    while i + 1 < args.len() {
        let v = PathBuf::from(&args[i + 1]);
        match args[i].as_str() {
            "--jeonseo" => o.jeonseo = v,
            "--jeonjip" => o.jeonjip = v,
            "--ocr" => o.ocr = v,
            "--txt" => o.txt = v,
            "--dalbat" => o.dalbat = v,
            "--out" => o.out = v,
            _ => {
                i += 1;
                continue;
            }
        }
        i += 2;
    }
    o
}

/// UTF-8(BOM 허용), 아니면 UTF-16(BOM)을 변환한다. 감지한 인코딩 이름을 함께 돌려준다.
fn read_text(p: &Path) -> Result<(String, &'static str), String> {
    let b = fs::read(p).map_err(|e| format!("{}: {e}", p.display()))?;
    if b.starts_with(&[0xEF, 0xBB, 0xBF]) {
        return String::from_utf8(b[3..].to_vec())
            .map(|s| (s, "utf-8-bom"))
            .map_err(|e| format!("{}: {e}", p.display()));
    }
    if b.starts_with(&[0xFF, 0xFE]) || b.starts_with(&[0xFE, 0xFF]) {
        let le = b[0] == 0xFF;
        let u: Vec<u16> = b[2..]
            .chunks(2)
            .filter(|c| c.len() == 2)
            .map(|c| if le { u16::from_le_bytes([c[0], c[1]]) } else { u16::from_be_bytes([c[0], c[1]]) })
            .collect();
        return String::from_utf16(&u).map(|s| (s, "utf-16")).map_err(|e| format!("{}: {e}", p.display()));
    }
    String::from_utf8(b).map(|s| (s, "utf-8")).map_err(|e| format!("{}: 인코딩을 UTF-8로 읽을 수 없음 ({e})", p.display()))
}

fn sorted_dir(p: &Path) -> Vec<PathBuf> {
    let mut v: Vec<PathBuf> = fs::read_dir(p)
        .map(|d| d.filter_map(|e| e.ok()).map(|e| e.path()).collect())
        .unwrap_or_default();
    v.sort();
    v
}

fn write_jsonl(path: &Path, ps: &[Passage]) -> Result<(), String> {
    let f = fs::File::create(path).map_err(|e| format!("{}: {e}", path.display()))?;
    let mut w = std::io::BufWriter::new(f);
    for p in ps {
        serde_json::to_writer(&mut w, p).map_err(|e| e.to_string())?;
        w.write_all(b"\n").map_err(|e| e.to_string())?;
    }
    Ok(())
}

#[derive(Default, Clone)]
struct Stat {
    n: usize,
    chars: usize,
    timing: usize,
    low_num: usize,
    low_den: usize,
}

fn add_stat(s: &mut Stat, p: &Passage) {
    s.n += 1;
    s.chars += p.text.chars().count();
    if p.tags.iter().any(|t| t.c == "timing") {
        s.timing += 1;
    }
    if p.src != "전서" && p.src != "전집" && p.src != "OCR" {
        return;
    }
    match &p.lowconf {
        Value::Bool(b) => {
            s.low_den += 1;
            if *b {
                s.low_num += 1;
            }
        }
        Value::Array(a) => {
            s.low_den += p.line_offsets.len();
            s.low_num += a.len();
        }
        _ => {}
    }
}

fn row(label: &str, s: &Stat, unit: &str) -> String {
    let ratio = if s.low_den == 0 { "-".to_string() } else { format!("{:.1}% ({}/{} {unit})", 100.0 * s.low_num as f64 / s.low_den as f64, s.low_num, s.low_den) };
    format!("| {label} | {} | {} | {} | {ratio} |\n", s.n, s.chars, s.timing)
}

fn table(title: &str, groups: &BTreeMap<String, Stat>, unit: &str) -> String {
    let mut t = Stat::default();
    for s in groups.values() {
        t.n += s.n;
        t.chars += s.chars;
        t.timing += s.timing;
        t.low_num += s.low_num;
        t.low_den += s.low_den;
    }
    let mut o = format!("## {title}\n\n| 출전 | 구절 수 | 글자 수 | timing 태그 구절 수 | 저신뢰 비율 |\n|---|---|---|---|---|\n");
    for (k, s) in groups {
        o.push_str(&row(k, s, unit));
    }
    o.push_str(&row("합계", &t, unit));
    o.push('\n');
    o
}

fn group(ps: &[Passage], key: impl Fn(&Passage) -> String) -> BTreeMap<String, Stat> {
    let mut m: BTreeMap<String, Stat> = BTreeMap::new();
    for p in ps {
        add_stat(m.entry(key(p)).or_default(), p);
    }
    m
}

fn load_canon(o: &Opts) -> Result<(Vec<JeonseoPara>, Vec<Passage>, Vec<Passage>), String> {
    let (c, _) = read_text(&o.jeonseo)?;
    let paras = parse_jeonseo(&c);
    let js = jeonseo_passages(&paras);
    let mut frags = Vec::new();
    for n in 1..=6 {
        let (c, _) = read_text(&o.jeonjip.join(format!("권{n}.txt")))?;
        frags.extend(split_jeonjip(&c));
    }
    let jj = jeonjip_passages(&frags);
    Ok((paras, js, jj))
}

fn cmd_index(args: &[String]) -> Result<(), String> {
    let o = opts(args);
    fs::create_dir_all(&o.out).map_err(|e| e.to_string())?;
    let mut summary = String::from("# 원전 색인 요약\n\n");
    let mut notes = String::new();

    let (_, js, jj) = load_canon(&o)?;
    let mut canon = js;
    canon.extend(jj);
    write_jsonl(&o.out.join("passages_canon.jsonl"), &canon)?;
    summary.push_str(&table("전서·전집 (tier=원전)", &group(&canon, |p| p.src.to_string()), "구절"));
    summary.push_str(&format!("봉인 표시(sealed) 구절: {}\n\n", canon.iter().filter(|p| p.sealed).count()));

    // OCR
    let mut ocr = Vec::new();
    for p in sorted_dir(&o.ocr) {
        let name = p.file_name().and_then(|s| s.to_str()).unwrap_or("").to_string();
        if !name.ends_with(".md") || name == "00_목록.md" {
            continue;
        }
        let (c, _) = read_text(&p)?;
        let key = name.trim_end_matches(".md");
        ocr.extend(ocr_passages(key, &c));
    }
    write_jsonl(&o.out.join("passages_ocr.jsonl"), &ocr)?;
    summary.push_str(&table("기계 OCR 未校 (책별)", &group(&ocr, |p| p.book.clone()), "줄"));

    // 해설 TXT
    let mut com = Vec::new();
    for f in TXT_FILES {
        let p = o.txt.join(f);
        match read_text(&p) {
            Ok((c, enc)) => {
                if enc != "utf-8" {
                    notes.push_str(&format!("- {f}: 인코딩 {enc} -> UTF-8 변환\n"));
                }
                com.extend(commentary_passages(f, &c));
            }
            Err(e) => notes.push_str(&format!("- 읽기 실패: {e}\n")),
        }
    }
    write_jsonl(&o.out.join("passages_commentary.jsonl"), &com)?;
    summary.push_str(&table("해설 TXT (tier=해설, 줄=문단)", &group(&com, |p| p.id.split('-').nth(1).unwrap_or("").to_string() + " " + &p.book), "-"));

    // 달밭
    let mut dal = Vec::new();
    for d in sorted_dir(&o.dalbat) {
        let name = d.file_name().and_then(|s| s.to_str()).unwrap_or("").to_string();
        let Some(suffix) = name.strip_prefix("dalbat1_") else { continue };
        if !d.is_dir() {
            continue;
        }
        for f in sorted_dir(&d) {
            let fname = f.file_name().and_then(|s| s.to_str()).unwrap_or("").to_string();
            if !fname.ends_with(".txt") {
                continue;
            }
            match read_text(&f) {
                Ok((c, _)) => dal.extend(dalbat_passages(suffix, &fname, &c)),
                Err(e) => notes.push_str(&format!("- 읽기 실패: {e}\n")),
            }
        }
    }
    write_jsonl(&o.out.join("passages_dalbat.jsonl"), &dal)?;
    summary.push_str(&table("달밭 블로그 (tier=2차, 폴더별)", &group(&dal, |p| p.book.clone()), "-"));
    summary.push_str(&format!(
        "## 출전별 구절 수\n\n- 원전(전서·전집): {}\n- OCR: {}\n- 해설 TXT: {}\n- 달밭: {}\n\n",
        canon.len(),
        ocr.len(),
        com.len(),
        dal.len()
    ));
    if !notes.is_empty() {
        summary.push_str("## 읽기 메모\n\n");
        summary.push_str(&notes);
    }
    fs::write(o.out.join("summary.md"), summary).map_err(|e| e.to_string())?;
    println!("canon {} ocr {} commentary {} dalbat {}", canon.len(), ocr.len(), com.len(), dal.len());
    if !notes.is_empty() {
        print!("{notes}");
    }
    Ok(())
}

fn cmd_cases(args: &[String]) -> Result<(), String> {
    let o = opts(args);
    fs::create_dir_all(&o.out).map_err(|e| e.to_string())?;
    let (paras, _, jj) = load_canon(&o)?;
    let set = collect_cases(&paras, &jj);
    let s = serde_json::to_string_pretty(&cases_json(&set)).map_err(|e| e.to_string())?;
    fs::write(o.out.join("cases.json"), s).map_err(|e| e.to_string())?;
    fs::write(o.out.join("cases_summary.md"), summary_md(&set)).map_err(|e| e.to_string())?;
    fs::write(o.out.join("_sealed_case_explanations.jsonl"), sealed_jsonl(&set)).map_err(|e| e.to_string())?;
    println!("cases {} sealed {}", set.cases.len(), set.sealed.len());
    Ok(())
}

fn cmd_find(args: &[String]) -> Result<(), String> {
    if args.len() < 2 {
        return Err("사용법: canon-index find <jsonl> <질의>".into());
    }
    let q: Vec<char> = normalize(&args[1]).chars().collect();
    if q.is_empty() {
        return Err("빈 질의".into());
    }
    let (content, _) = read_text(Path::new(&args[0]))?;
    for line in content.lines() {
        let v: Value = match serde_json::from_str(line) {
            Ok(v) => v,
            Err(_) => continue,
        };
        let (Some(id), Some(norm), Some(text)) = (v["id"].as_str(), v["norm"].as_str(), v["text"].as_str()) else { continue };
        let n: Vec<char> = norm.chars().collect();
        let t: Vec<char> = text.chars().collect();
        if n.len() < q.len() {
            continue;
        }
        for i in 0..=n.len() - q.len() {
            if n[i..i + q.len()] == q[..] {
                let a = i.saturating_sub(15);
                let e = (i + q.len() + 15).min(t.len());
                let before: String = t[a..i].iter().collect();
                let mid: String = t[i..i + q.len()].iter().collect();
                let after: String = t[i + q.len()..e].iter().collect();
                if writeln!(std::io::stdout(), "{id}@{i}+{}\t{before}「{mid}」{after}", q.len()).is_err() {
                    return Ok(());
                }
            }
        }
    }
    Ok(())
}

fn main() {
    let args: Vec<String> = std::env::args().skip(1).collect();
    let r = match args.first().map(|s| s.as_str()) {
        Some("index") => cmd_index(&args[1..]),
        Some("cases") => cmd_cases(&args[1..]),
        Some("find") => cmd_find(&args[1..]),
        _ => Err("사용법: canon-index <index|cases|find> [옵션]\n  index [--jeonseo F --jeonjip D --ocr D --txt D --dalbat D --out D]\n  cases [--jeonseo F --jeonjip D --out D]\n  find <jsonl> <질의>".into()),
    };
    if let Err(e) = r {
        eprintln!("{e}");
        std::process::exit(1);
    }
}
