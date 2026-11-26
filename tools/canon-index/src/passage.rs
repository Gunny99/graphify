//! 구절 구조체, 주석 스캔, 전서·전집·OCR 분할.
use crate::norm::normalize;
use crate::tags::{find_tags, Tag};
use serde::Serialize;
use serde_json::{json, Value};

#[derive(Serialize, Debug, Clone, PartialEq)]
pub struct Annot {
    pub kind: String,
    pub start: usize,
    pub len: usize,
}

#[derive(Serialize, Debug, Clone)]
pub struct Passage {
    pub id: String,
    pub src: &'static str,
    /// 원전 / 해설 / 2차
    pub tier: &'static str,
    pub book: String,
    pub juan: Option<u32>,
    pub section: Option<String>,
    pub text: String,
    pub norm: String,
    pub lowconf: Value,
    pub kind: String,
    #[serde(skip_serializing_if = "Vec::is_empty")]
    pub annots: Vec<Annot>,
    #[serde(skip_serializing_if = "Vec::is_empty")]
    pub line_offsets: Vec<usize>,
    /// 채점 전까지 봉인해야 하는 풀이 글을 담은 구절.
    #[serde(skip_serializing_if = "is_false")]
    pub sealed: bool,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub meta: Option<Value>,
    pub tags: Vec<Tag>,
}
fn is_false(b: &bool) -> bool {
    !*b
}

/// 〔…〕 주석(중첩 허용)을 찾는다. 닫히지 않으면 주석으로 보지 않는다.
pub fn scan_annots(text: &str) -> Vec<Annot> {
    let cs: Vec<char> = text.chars().collect();
    let mut out = Vec::new();
    let mut i = 0;
    while i < cs.len() {
        if cs[i] == '〔' {
            let mut depth = 0;
            let mut j = i;
            let mut end = None;
            while j < cs.len() {
                match cs[j] {
                    '〔' => depth += 1,
                    '〕' => {
                        depth -= 1;
                        if depth == 0 {
                            end = Some(j);
                            break;
                        }
                    }
                    _ => {}
                }
                j += 1;
            }
            if let Some(e) = end {
                let kind: String = cs[i + 1..e]
                    .iter()
                    .take_while(|c| !matches!(**c, ':' | '：' | '|' | '〔'))
                    .collect();
                out.push(Annot { kind, start: i, len: e - i + 1 });
                i = e + 1;
                continue;
            }
        }
        i += 1;
    }
    out
}

/// 주석을 뺀 나머지에 글자가 있으면 "본문"을 앞에 붙이고 주석 종류를 '+'로 잇는다.
pub fn kind_of(text: &str, annots: &[Annot]) -> String {
    let cs: Vec<char> = text.chars().collect();
    let mut covered = vec![false; cs.len()];
    for a in annots {
        for k in a.start..a.start + a.len {
            covered[k] = true;
        }
    }
    let has_body = cs
        .iter()
        .enumerate()
        .any(|(i, c)| !covered[i] && !c.is_whitespace() && *c != '○');
    let mut parts: Vec<String> = Vec::new();
    if has_body || annots.is_empty() {
        parts.push("본문".into());
    }
    for a in annots {
        if !parts.contains(&a.kind) {
            parts.push(a.kind.clone());
        }
    }
    parts.join("+")
}

fn lowconf_canon(text: &str) -> bool {
    text.contains("판독불완전") || text.contains('□')
}

#[allow(clippy::too_many_arguments)]
pub fn build_canon(
    id: String,
    src: &'static str,
    book: &str,
    juan: Option<u32>,
    section: Option<String>,
    text: String,
    kind_override: Option<&str>,
    sealed: bool,
) -> Passage {
    let annots = scan_annots(&text);
    let kind = kind_override
        .map(|s| s.to_string())
        .unwrap_or_else(|| kind_of(&text, &annots));
    let norm = normalize(&text);
    let tags = find_tags(&norm);
    let lowconf = json!(lowconf_canon(&text));
    Passage {
        id,
        src,
        tier: "원전",
        book: book.into(),
        juan,
        section,
        text,
        norm,
        lowconf,
        kind,
        annots,
        line_offsets: vec![],
        sealed,
        meta: None,
        tags,
    }
}

// ---------------------------------------------------------------- 전서

#[derive(Debug, Clone)]
pub struct JeonseoPara {
    pub id: String,
    pub juan: u32,
    pub section: String,
    pub text: String,
}

/// `[전서남양당-권-절이름-0001]` 머리줄 다음 줄들(빈 줄 전까지)이 문단 본문.
pub fn parse_jeonseo_id(line: &str) -> Option<(u32, String, u32)> {
    let inner = line.strip_prefix('[')?.strip_suffix(']')?;
    let rest = inner.strip_prefix("전서남양당-")?;
    let (juan, rest) = rest.split_once('-')?;
    let (section, seq) = rest.rsplit_once('-')?;
    Some((juan.parse().ok()?, section.to_string(), seq.parse().ok()?))
}

pub fn parse_jeonseo(content: &str) -> Vec<JeonseoPara> {
    let mut out: Vec<JeonseoPara> = Vec::new();
    let mut cur: Option<JeonseoPara> = None;
    for line in content.lines() {
        if let Some((juan, section, _)) = parse_jeonseo_id(line.trim_end()) {
            if let Some(p) = cur.take() {
                out.push(p);
            }
            cur = Some(JeonseoPara {
                id: line.trim_end().trim_start_matches('[').trim_end_matches(']').to_string(),
                juan,
                section,
                text: String::new(),
            });
        } else if let Some(p) = cur.as_mut() {
            p.text.push_str(line.trim_end_matches('\r'));
        }
    }
    if let Some(p) = cur.take() {
        out.push(p);
    }
    out.retain(|p| !p.text.is_empty());
    out
}

pub fn jeonseo_passages(paras: &[JeonseoPara]) -> Vec<Passage> {
    let mut out = Vec::new();
    // 卷六: 명반 다음 문단(같은 절)은 풀이 글 -> 봉인 표시
    let mut explain_next = false;
    let mut last_sec = String::new();
    for p in paras {
        if p.section != last_sec {
            explain_next = false;
            last_sec = p.section.clone();
        }
        let is_chart = p.juan == 6 && p.text.starts_with("〔명반|");
        let (ko, sealed) = if explain_next {
            (Some("풀이"), true)
        } else {
            (None, false)
        };
        explain_next = is_chart;
        out.push(build_canon(
            p.id.clone(),
            "전서",
            "紫微斗數全書",
            Some(p.juan),
            Some(p.section.clone()),
            p.text.clone(),
            ko,
            sealed,
        ));
    }
    out
}

// ---------------------------------------------------------------- 전집

/// 쪽 표지 `⟦권-PDF쪽-左|右⟧` -> (권, 쪽, 면). 면이 없으면 빈 문자열.
pub fn parse_page_marker(m: &str) -> Option<(u32, u32, String)> {
    let inner = m.strip_prefix('⟦')?.strip_suffix('⟧')?;
    let mut it = inner.splitn(3, '-');
    let juan = it.next()?.parse().ok()?;
    let pdf = it.next()?.parse().ok()?;
    let side = it.next().unwrap_or("");
    let side = if side == "左" || side == "右" { side } else { "" };
    Some((juan, pdf, side.to_string()))
}

/// 〔…〕 밖의 ○에서 조각을 나눈다. ○는 새 조각의 첫 글자로 남긴다.
pub fn split_circles(page: &str) -> Vec<String> {
    let mut out = Vec::new();
    let mut cur = String::new();
    let mut depth = 0i32;
    for c in page.chars() {
        match c {
            '〔' => depth += 1,
            '〕' => depth -= 1,
            _ => {}
        }
        if c == '○' && depth <= 0 && !cur.is_empty() {
            out.push(std::mem::take(&mut cur));
        }
        cur.push(c);
    }
    if !cur.is_empty() {
        out.push(cur);
    }
    out
}

/// 한 권 파일 -> (구절ID, juan, text). `#` 줄과 빈 줄은 건너뛴다.
pub fn split_jeonjip(content: &str) -> Vec<(String, u32, String)> {
    let mut pages: Vec<((u32, u32, String), String)> = Vec::new();
    for line in content.lines() {
        if line.starts_with('#') || line.trim().is_empty() {
            continue;
        }
        let mut rest = line;
        while !rest.is_empty() {
            if let Some(p) = rest.find('⟦') {
                if p > 0 {
                    if let Some(last) = pages.last_mut() {
                        last.1.push_str(&rest[..p]);
                    }
                }
                let q = match rest[p..].find('⟧') {
                    Some(q) => p + q + '⟧'.len_utf8(),
                    None => {
                        if let Some(last) = pages.last_mut() {
                            last.1.push_str(&rest[p..]);
                        }
                        break;
                    }
                };
                if let Some(key) = parse_page_marker(&rest[p..q]) {
                    pages.push((key, String::new()));
                } else if let Some(last) = pages.last_mut() {
                    last.1.push_str(&rest[p..q]);
                }
                rest = &rest[q..];
            } else {
                if let Some(last) = pages.last_mut() {
                    last.1.push_str(rest);
                }
                break;
            }
        }
    }
    let mut out = Vec::new();
    for ((juan, pdf, side), text) in pages {
        let mut seq = 0;
        for frag in split_circles(&text) {
            if frag.trim().is_empty() {
                continue;
            }
            seq += 1;
            out.push((format!("전집명경각-{juan}-{pdf}{side}-{seq:02}"), juan, frag));
        }
    }
    out
}

pub fn jeonjip_passages(frags: &[(String, u32, String)]) -> Vec<Passage> {
    frags
        .iter()
        .map(|(id, juan, text)| {
            let chart = text.contains("〔명반:");
            build_canon(
                id.clone(),
                "전집",
                "紫微斗數全集",
                Some(*juan),
                None,
                text.clone(),
                None,
                chart,
            )
        })
        .collect()
}

// ---------------------------------------------------------------- OCR

/// `## p.NNNN` 쪽 머리. 줄 앞 `〔?〕`는 저신뢰 표지이므로 text에서 떼고 줄 번호(1부터)로 보관한다.
pub fn ocr_passages(key: &str, content: &str) -> Vec<Passage> {
    let mut pages: Vec<(String, Vec<String>)> = Vec::new();
    for line in content.lines() {
        if let Some(n) = line.strip_prefix("## p.") {
            pages.push((n.trim().to_string(), Vec::new()));
        } else if let Some(p) = pages.last_mut() {
            if !line.trim().is_empty() {
                p.1.push(line.to_string());
            }
        }
    }
    pages
        .into_iter()
        .map(|(n, lines)| {
            let mut text = String::new();
            let mut offs = Vec::new();
            let mut low = Vec::new();
            for (i, l) in lines.iter().enumerate() {
                let (flag, body) = match l.strip_prefix("〔?〕") {
                    Some(b) => (true, b),
                    None => (false, l.as_str()),
                };
                offs.push(text.chars().count());
                if flag {
                    low.push(i + 1);
                }
                text.push_str(body);
            }
            let norm = normalize(&text);
            let tags = find_tags(&norm);
            let kind = if text == "（빈 쪽 또는 그림）" { "빈쪽" } else { "본문" };
            Passage {
                id: format!("OCR-{key}-p{n}"),
                src: "OCR",
                tier: if key == "紫微斗数全集_简体" { "원전" } else { "해설" },
                book: key.to_string(),
                juan: None,
                section: None,
                text,
                norm,
                lowconf: json!(low),
                kind: kind.into(),
                annots: vec![],
                line_offsets: offs,
                sealed: false,
                meta: None,
                tags,
            }
        })
        .collect()
}

// ---------------------------------------------------------------- 해설 TXT / 달밭

fn plain_passage(
    id: String,
    src: &'static str,
    tier: &'static str,
    book: &str,
    text: String,
    meta: Option<Value>,
) -> Passage {
    let norm = normalize(&text);
    let tags = find_tags(&norm);
    Passage {
        id,
        src,
        tier,
        book: book.into(),
        juan: None,
        section: None,
        text,
        norm,
        lowconf: json!(false),
        kind: "본문".into(),
        annots: vec![],
        line_offsets: vec![],
        sealed: false,
        meta,
        tags,
    }
}

fn clean_line(l: &str) -> String {
    l.chars().filter(|c| !c.is_control()).collect::<String>().trim().to_string()
}

/// 해설 텍스트: 비어 있지 않은 줄 하나가 문단 하나(빈 줄은 건너뜀). 제어문자는 뺀다.
/// ID `TXT-{파일 앞 숫자}-{순번 5자리}`. file_name은 `숫자-이름.txt`.
pub fn commentary_passages(file_name: &str, content: &str) -> Vec<Passage> {
    let stem = file_name.strip_suffix(".txt").unwrap_or(file_name);
    let (num, book) = stem.split_once('-').unwrap_or((stem, stem));
    let mut out = Vec::new();
    let mut n = 0;
    for l in content.lines() {
        let t = clean_line(l);
        if t.is_empty() {
            continue;
        }
        n += 1;
        out.push(plain_passage(format!("TXT-{num}-{n:05}"), "해설TXT", "해설", book, t, None));
    }
    out
}

/// 달밭 글: 머리 4줄(제목·작성일·URL·저자)은 meta, 본문은 빈 줄 기준 문단.
/// ID `DALBAT-{폴더 접미}-{파일 앞 세 자리}-{순번 3자리}`.
pub fn dalbat_passages(suffix: &str, file_name: &str, content: &str) -> Vec<Passage> {
    let num: String = file_name.chars().take_while(|c| c.is_ascii_digit()).take(3).collect();
    let lines: Vec<&str> = content.lines().collect();
    let mut head = serde_json::Map::new();
    let mut i = 0;
    for (key, prefix) in [("title", "제목:"), ("date", "작성일:"), ("url", "URL:"), ("author", "저자:")] {
        if i < lines.len() {
            if let Some(v) = lines[i].trim().strip_prefix(prefix) {
                head.insert(key.into(), json!(v.trim()));
                i += 1;
            }
        }
    }
    let meta = Value::Object(head);
    let mut out = Vec::new();
    let mut cur: Vec<String> = Vec::new();
    let mut n = 0;
    let mut flush = |cur: &mut Vec<String>, out: &mut Vec<Passage>| {
        if cur.is_empty() {
            return;
        }
        n += 1;
        let text = cur.join("\n");
        cur.clear();
        out.push(plain_passage(
            format!("DALBAT-{suffix}-{num}-{n:03}"),
            "달밭",
            "2차",
            suffix,
            text,
            Some(meta.clone()),
        ));
    };
    for l in &lines[i..] {
        let t = clean_line(l);
        if t.is_empty() {
            flush(&mut cur, &mut out);
        } else {
            cur.push(t);
        }
    }
    flush(&mut cur, &mut out);
    out
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn commentary_and_dalbat() {
        let ps = commentary_passages("1016036253-中州派.txt", "  甲乙\x7f \n\n丙\n");
        assert_eq!(ps.len(), 2);
        assert_eq!(ps[0].id, "TXT-1016036253-00001");
        assert_eq!(ps[0].text, "甲乙");
        assert_eq!(ps[1].id, "TXT-1016036253-00002");
        assert_eq!(ps[1].tier, "해설");
        let d = dalbat_passages("60성계", "002_22_x.txt", "제목: T\n작성일: D\nURL: U\n저자: A\n\n대한과 화기\n둘째줄\n\n셋째\n");
        assert_eq!(d.len(), 2);
        assert_eq!(d[0].id, "DALBAT-60성계-002-001");
        assert_eq!(d[0].text, "대한과 화기\n둘째줄");
        assert_eq!(d[0].tier, "2차");
        assert_eq!(d[0].meta.as_ref().unwrap()["title"], "T");
        assert!(d[0].tags.iter().any(|t| t.w == "大限"));
        assert_eq!(d[1].id, "DALBAT-60성계-002-002");
    }

    #[test]
    fn jeonseo_id() {
        assert_eq!(
            parse_jeonseo_id("[전서남양당-6-孔仲尼命-0002]"),
            Some((6, "孔仲尼命".to_string(), 2))
        );
        assert_eq!(
            parse_jeonseo_id("[전서남양당-2-十二宫諸星得地合格訣-0019]"),
            Some((2, "十二宫諸星得地合格訣".to_string(), 19))
        );
        assert_eq!(parse_jeonseo_id("太微賦"), None);
    }

    #[test]
    fn jeonseo_paragraphs_and_seal() {
        let src = "# c\n\n[전서남양당-6-甲命-0001]\n甲命\n\n[전서남양당-6-甲命-0002]\n〔명반|中:x〕\n\n[전서남양당-6-甲命-0003]\n풀이글\n";
        let ps = parse_jeonseo(src);
        assert_eq!(ps.len(), 3);
        assert_eq!(ps[0].id, "전서남양당-6-甲命-0001");
        let pp = jeonseo_passages(&ps);
        assert_eq!(pp[1].kind, "명반");
        assert!(!pp[1].sealed);
        assert!(pp[2].sealed);
        assert_eq!(pp[2].kind, "풀이");
    }

    #[test]
    fn jeonjip_page_split() {
        let src = "# 卷1\n\n⟦1-8-左⟧甲乙○丙〔眉批:丁○戊〕己○庚\n⟦1-9-右⟧〔眉批:x〕辛○\n⟦1-9-左⟧壬\n";
        let f = split_jeonjip(src);
        let ids: Vec<&str> = f.iter().map(|x| x.0.as_str()).collect();
        assert_eq!(
            ids,
            vec![
                "전집명경각-1-8左-01",
                "전집명경각-1-8左-02",
                "전집명경각-1-8左-03",
                "전집명경각-1-9右-01",
                "전집명경각-1-9右-02",
                "전집명경각-1-9左-01"
            ]
        );
        assert_eq!(f[0].2, "甲乙");
        assert_eq!(f[1].2, "○丙〔眉批:丁○戊〕己");
        assert_eq!(f[2].2, "○庚");
        assert_eq!(f[4].2, "○");
        let ps = jeonjip_passages(&f);
        assert_eq!(ps[1].kind, "본문+眉批");
        assert_eq!(ps[3].kind, "본문+眉批");
        assert_eq!(ps[1].annots, vec![Annot { kind: "眉批".into(), start: 2, len: 8 }]);
    }

    #[test]
    fn page_marker() {
        assert_eq!(parse_page_marker("⟦6-21-左⟧"), Some((6, 21, "左".into())));
        assert_eq!(parse_page_marker("⟦6-0--⟧"), Some((6, 0, "".into())));
    }

    #[test]
    fn ocr_page() {
        let src = "# t\n> x\n\n## p.0001\n〔?〕甲乙\n丙\n\n## p.0002\n丁\n";
        let ps = ocr_passages("全集一", src);
        assert_eq!(ps.len(), 2);
        assert_eq!(ps[0].id, "OCR-全集一-p0001");
        assert_eq!(ps[0].text, "甲乙丙");
        assert_eq!(ps[0].line_offsets, vec![0, 2]);
        assert_eq!(ps[0].lowconf, json!([1]));
        assert_eq!(ps[1].lowconf, json!([]));
    }
}
