//! 명반(命盤) 표 파싱. 짐작으로 채우지 않고, 못 읽은 곳은 raw로 두고 unparsed에 적는다.
use crate::cn::{cn_num, month_num};
use crate::passage::{JeonseoPara, Passage};
use regex::Regex;
use serde::Serialize;
use serde_json::{json, Value};

pub const STEMS: &str = "甲乙丙丁戊己庚辛壬癸";
pub const BRANCHES: &str = "子丑寅卯辰巳午未申酉戌亥";
/// 명반 칸 읽는 순서
pub const CELL_ORDER: &str = "巳午未申酉戌亥子丑寅卯辰";

const MAJOR: &[&str] = &[
    "紫微", "天機", "太陽", "武曲", "天同", "廉貞", "天府", "太陰", "貪狼", "巨門", "天相", "天梁",
    "七殺", "破軍",
];
const MINOR: &[&str] = &[
    "文昌", "文曲", "左輔", "右弼", "天魁", "天鉞", "祿存", "天馬", "擎羊", "陀羅", "火星", "鈴星",
    "地劫", "天空", "地空", "天刑", "天姚", "天傷", "天使", "截空", "旬空", "三台", "八座", "龍池",
    "鳳閣", "天哭", "天虛", "封誥", "台輔", "恩光", "天貴", "天才", "天壽", "紅鸞", "天喜", "天福",
    "天官", "羊刃", "天德", "月德",
];
const PALACES: &[&str] = &[
    "命宮", "命垣", "身宮", "身垣", "身命垣", "身命同宮", "命身", "身命", "身", "兄弟", "夫妻",
    "妻妾", "妻宮", "子女", "子息", "財帛", "疾厄", "遷移", "奴僕", "官祿", "田宅", "田地", "福德",
    "父母",
];
const FLAGS: &[&str] = &[
    "大限", "小限", "太歲", "斗君", "流羊", "流陀", "流祿", "流昌", "流曲", "流魁", "流鉞", "流年",
];
const STAGES: &[&str] = &["長生", "沐浴", "冠帶", "臨官", "帝旺", "衰", "病", "死", "墓", "絕", "胎", "養"];
const HUA: &[&str] = &["祿", "權", "科", "忌"];

#[derive(Serialize, Debug, Clone, Default)]
pub struct Birth {
    pub raw: String,
    pub year_gz: Option<String>,
    pub month: Option<u32>,
    pub leap: bool,
    pub day: Option<u32>,
    pub hour_branch: Option<String>,
    pub yin_yang: Option<String>,
    pub sex: Option<String>,
    pub element: Option<String>,
    pub bureau: Option<u32>,
    pub notes: Vec<String>,
}

#[derive(Serialize, Debug, Clone, Default)]
pub struct Death {
    pub raw: String,
    pub year_gz: Option<String>,
    pub age: Option<u32>,
    pub month: Option<u32>,
    pub leap: bool,
    pub day: Option<u32>,
    pub uncertain: bool,
    pub notes: Vec<String>,
}

#[derive(Serialize, Debug, Clone)]
pub struct Star {
    pub name: String,
    pub class: &'static str,
    pub hua: Vec<String>,
    pub notes: Vec<String>,
}

#[derive(Serialize, Debug, Clone, Default)]
pub struct Cell {
    pub branch: String,
    pub raw: String,
    pub tokens: Vec<String>,
    pub stars: Vec<Star>,
    pub palace_names: Vec<String>,
    pub flags: Vec<String>,
    pub stage: Vec<String>,
    pub other: Vec<String>,
    pub parsed: bool,
}

#[derive(Serialize, Debug, Clone)]
pub struct Unparsed {
    pub field: String,
    pub raw: String,
    pub reason: String,
}

#[derive(Serialize, Debug, Clone)]
pub struct Case {
    pub id: String,
    pub source: &'static str,
    pub title: String,
    pub subtitle: Option<String>,
    pub explain_id: Option<String>,
    pub trailer: Option<String>,
    pub birth: Option<Birth>,
    pub death: Option<Death>,
    pub palaces: Vec<Cell>,
    pub unparsed: Vec<Unparsed>,
}

/// 〔…〕 밖/안의 소괄호를 분리: (괄호 밖 글자, 최상위 괄호 안 내용들, 균형 여부)
pub fn split_parens(s: &str) -> (String, Vec<String>, bool) {
    let mut base = String::new();
    let mut notes = Vec::new();
    let mut cur = String::new();
    let mut depth = 0i32;
    for c in s.chars() {
        match c {
            '(' | '（' => {
                if depth > 0 {
                    cur.push(c);
                }
                depth += 1;
            }
            ')' | '）' => {
                if depth <= 0 {
                    return (base, notes, false);
                }
                depth -= 1;
                if depth == 0 {
                    notes.push(std::mem::take(&mut cur));
                } else {
                    cur.push(c);
                }
            }
            _ => {
                if depth > 0 {
                    cur.push(c)
                } else {
                    base.push(c)
                }
            }
        }
    }
    (base, notes, depth == 0)
}

/// 간지 검증: 천간·지지가 맞고 음양이 같아야 한다.
pub fn valid_gz(s: &str) -> bool {
    let cs: Vec<char> = s.chars().collect();
    if cs.len() != 2 {
        return false;
    }
    match (STEMS.chars().position(|c| c == cs[0]), BRANCHES.chars().position(|c| c == cs[1])) {
        (Some(a), Some(b)) => a % 2 == b % 2,
        _ => false,
    }
}

fn bureau_num(c: char) -> Option<u32> {
    Some(match c {
        '二' => 2,
        '三' => 3,
        '四' => 4,
        '五' => 5,
        '六' => 6,
        _ => return None,
    })
}

pub fn parse_birth(val: &str) -> (Birth, Vec<(String, String)>) {
    let mut b = Birth { raw: val.to_string(), ..Default::default() };
    let mut bad: Vec<(String, String)> = Vec::new();
    let (base, notes, bal) = split_parens(val);
    b.notes = notes;
    if !bal {
        bad.push(("中".into(), "괄호 불균형".into()));
    }
    let base = base.trim().to_string();
    // 年干支
    let rest = match base.split_once('年') {
        Some((gz, rest)) => {
            if valid_gz(gz) {
                b.year_gz = Some(gz.to_string());
            } else {
                bad.push(("中.年干支".into(), format!("간지로 읽을 수 없음: {gz}")));
            }
            rest.to_string()
        }
        None => {
            bad.push(("中.年干支".into(), "年 표지 없음".into()));
            base.clone()
        }
    };
    let re = Regex::new(r"^(閏)?([正臘冬一二三四五六七八九十]+)月([初廿卅十一二三四五六七八九□]+)日?([子丑寅卯辰巳午未申酉戌亥])時生?(.*)$").unwrap();
    let tail = if let Some(c) = re.captures(&rest) {
        b.leap = c.get(1).is_some();
        b.month = month_num(&c[2]);
        if b.month.is_none() {
            bad.push(("中.月".into(), format!("월 변환 실패: {}", &c[2])));
        }
        b.day = cn_num(&c[3]).filter(|d| (1..=30).contains(d));
        if b.day.is_none() {
            bad.push(("中.日".into(), format!("일 변환 실패: {}", &c[3])));
        }
        b.hour_branch = Some(c[4].to_string());
        c[5].to_string()
    } else {
        bad.push(("中.月日時".into(), format!("월일시 구문 불일치: {rest}")));
        rest.clone()
    };
    let re_s = Regex::new(r"([陰隂陽])([男女])").unwrap();
    if let Some(c) = re_s.captures(&tail) {
        b.yin_yang = Some(if &c[1] == "陽" { "陽" } else { "陰" }.to_string());
        b.sex = Some(c[2].to_string());
    } else {
        bad.push(("中.陰陽男女".into(), "없음".into()));
    }
    let re_b = Regex::new(r"([金木水火土])([二三四五六])局").unwrap();
    if let Some(c) = re_b.captures(&tail) {
        b.element = Some(c[1].to_string());
        b.bureau = c[2].chars().next().and_then(bureau_num);
    } else {
        bad.push(("中.五行局".into(), "없음".into()));
    }
    (b, bad)
}

pub fn parse_death(val: &str) -> (Death, Vec<(String, String)>) {
    let mut d = Death { raw: val.to_string(), ..Default::default() };
    let mut bad = Vec::new();
    let (base, notes, bal) = split_parens(val);
    if !bal {
        bad.push(("中左".to_string(), "괄호 불균형".to_string()));
    }
    d.uncertain = notes.iter().any(|n| n.contains('?') || n.contains("판독불완전"));
    d.notes = notes;
    let base = base.trim();
    let re = Regex::new(r"^(.+?)年(.+?)歲(閏)?([正臘冬一二三四五六七八九十]+)月([初廿卅十一二三四五六七八九□]+)日?故$").unwrap();
    // 판독불완전 표기가 괄호 밖에 붙은 경우(□故 등)를 위해 □ 허용
    if let Some(c) = re.captures(base) {
        if valid_gz(&c[1]) {
            d.year_gz = Some(c[1].to_string());
        } else {
            bad.push(("中左.年干支".into(), format!("간지로 읽을 수 없음: {}", &c[1])));
        }
        d.age = cn_num(&c[2]);
        if d.age.is_none() {
            bad.push(("中左.나이".into(), format!("나이 변환 실패: {}", &c[2])));
        }
        d.leap = c.get(3).is_some();
        d.month = month_num(&c[4]);
        d.day = cn_num(&c[5]).filter(|x| (1..=30).contains(x));
        if d.day.is_none() {
            bad.push(("中左.日".into(), format!("일 변환 실패: {}", &c[5])));
        }
    } else {
        bad.push(("中左".into(), format!("구문 불일치: {base}")));
    }
    (d, bad)
}

fn split_top_ws(s: &str) -> Vec<String> {
    let mut out = Vec::new();
    let mut cur = String::new();
    let mut depth = 0i32;
    for c in s.chars() {
        match c {
            '(' | '（' => depth += 1,
            ')' | '）' => depth -= 1,
            _ => {}
        }
        if c.is_whitespace() && depth <= 0 {
            if !cur.is_empty() {
                out.push(std::mem::take(&mut cur));
            }
        } else {
            cur.push(c);
        }
    }
    if !cur.is_empty() {
        out.push(cur);
    }
    out
}

pub fn parse_cell(branch: &str, val: &str) -> (Cell, Option<String>) {
    let mut cell = Cell { branch: branch.into(), raw: val.to_string(), ..Default::default() };
    let mut reasons: Vec<String> = Vec::new();
    let (_, _, bal) = split_parens(val);
    if !bal {
        reasons.push("괄호 불균형".into());
    }
    if val.contains('□') {
        reasons.push("□ 판독불가 글자".into());
    }
    cell.tokens = split_top_ws(val);
    for tok in &cell.tokens {
        let (base, notes, _) = split_parens(tok);
        let base = base.trim().to_string();
        if base.is_empty() {
            cell.other.push(tok.clone());
            continue;
        }
        let class = if MAJOR.contains(&base.as_str()) {
            Some("major")
        } else if MINOR.contains(&base.as_str()) {
            Some("minor")
        } else {
            None
        };
        if let Some(class) = class {
            let mut hua = Vec::new();
            let mut ns = Vec::new();
            for n in &notes {
                let mut after_form = false;
                for item in n.split(|c: char| c == ',' || c == '，' || c == '、' || c.is_whitespace()) {
                    if item.is_empty() {
                        continue;
                    }
                    if after_form {
                        ns.push(item.to_string());
                        after_form = false;
                    } else if item == "자형" {
                        ns.push(item.to_string());
                        after_form = true;
                    } else if HUA.contains(&item) {
                        hua.push(item.to_string());
                    } else {
                        ns.push(item.to_string());
                    }
                }
            }
            cell.stars.push(Star { name: base, class, hua, notes: ns });
        } else if PALACES.contains(&base.as_str()) {
            cell.palace_names.push(base);
        } else if FLAGS.contains(&base.as_str()) {
            cell.flags.push(base);
        } else if STAGES.contains(&base.as_str()) {
            cell.stage.push(base);
        } else {
            cell.other.push(tok.clone());
        }
    }
    if cell.tokens.is_empty() {
        reasons.push("빈 칸".into());
    }
    cell.parsed = reasons.is_empty();
    let r = if reasons.is_empty() { None } else { Some(reasons.join("; ")) };
    (cell, r)
}

pub struct Chart {
    pub title: Option<String>,
    pub fields: Vec<(String, String)>,
    pub trailer: String,
}

/// 텍스트 안의 `〔명반…〕`을 꺼낸다. 전서는 `〔명반|중:…〕`, 전집은 `〔명반:제목|…〕`.
pub fn extract_chart(text: &str) -> Option<Chart> {
    let cs: Vec<char> = text.chars().collect();
    let start = (0..cs.len()).find(|&i| cs[i] == '〔' && cs[i + 1..].starts_with(&['명', '반']))?;
    let mut depth = 0;
    let mut end = None;
    for (j, c) in cs.iter().enumerate().skip(start) {
        match c {
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
    }
    let end = end?;
    let inner: String = cs[start + 3..end].iter().collect();
    let trailer: String = cs[end + 1..].iter().collect();
    let (title, body) = if let Some(r) = inner.strip_prefix(':') {
        match r.split_once('|') {
            Some((t, b)) => (Some(t.to_string()), b.to_string()),
            None => (Some(r.to_string()), String::new()),
        }
    } else {
        (None, inner.strip_prefix('|').unwrap_or(&inner).to_string())
    };
    let mut fields: Vec<(String, String)> = Vec::new();
    let mut it = body.split('|').peekable();
    while let Some(piece) = it.next() {
        let (k, v) = match piece.split_once(|c| c == ':' || c == '：') {
            Some((k, v)) => (k.to_string(), v.to_string()),
            None => (String::new(), piece.to_string()),
        };
        if k == "小注" {
            let mut val = v;
            for rest in it.by_ref() {
                val.push('|');
                val.push_str(rest);
            }
            fields.push((k, val));
            break;
        }
        fields.push((k, v));
    }
    Some(Chart { title, fields, trailer })
}

fn build_case(
    id: String,
    source: &'static str,
    title: String,
    chart: &Chart,
    explain_id: Option<String>,
) -> (Case, Option<String>) {
    let mut subtitle = None;
    let mut birth = None;
    let mut death = None;
    let mut cells: Vec<Option<Cell>> = vec![None; 12];
    let mut unparsed: Vec<Unparsed> = Vec::new();
    let mut explain_text = None;
    let push = |u: &mut Vec<Unparsed>, f: &str, raw: &str, r: &str| {
        u.push(Unparsed { field: f.into(), raw: raw.into(), reason: r.into() })
    };
    for (k, v) in &chart.fields {
        match k.as_str() {
            "표제小字" => subtitle = Some(v.clone()),
            "中" => {
                let (b, bad) = parse_birth(v);
                for (f, r) in bad {
                    push(&mut unparsed, &f, v, &r);
                }
                birth = Some(b);
            }
            "中左" => {
                let (d, bad) = parse_death(v);
                for (f, r) in bad {
                    push(&mut unparsed, &f, v, &r);
                }
                death = Some(d);
            }
            "小注" => explain_text = Some(v.clone()),
            k if k.chars().count() == 1 && BRANCHES.contains(k) => {
                let idx = CELL_ORDER.chars().position(|c| c.to_string() == k).unwrap();
                let (cell, why) = parse_cell(k, v);
                if let Some(w) = why {
                    push(&mut unparsed, k, v, &w);
                }
                cells[idx] = Some(cell);
            }
            _ => push(&mut unparsed, if k.is_empty() { "?" } else { k }, v, "알 수 없는 칸 이름"),
        }
    }
    if birth.is_none() {
        push(&mut unparsed, "中", "", "칸 없음");
    }
    let mut palaces = Vec::new();
    for (i, c) in cells.into_iter().enumerate() {
        match c {
            Some(c) => palaces.push(c),
            None => {
                let br = CELL_ORDER.chars().nth(i).unwrap().to_string();
                push(&mut unparsed, &br, "", "칸 없음");
            }
        }
    }
    let trailer = if chart.trailer.is_empty() { None } else { Some(chart.trailer.clone()) };
    (
        Case { id, source, title, subtitle, explain_id, trailer, birth, death, palaces, unparsed },
        explain_text,
    )
}

pub struct CaseSet {
    pub cases: Vec<Case>,
    /// 봉인 풀이: (풀이 id, 명반 id, 본문)
    pub sealed: Vec<(String, String, String)>,
}

pub fn collect_cases(jeonseo: &[JeonseoPara], jeonjip: &[Passage]) -> CaseSet {
    let mut cases = Vec::new();
    let mut sealed = Vec::new();
    for (i, p) in jeonseo.iter().enumerate() {
        if p.juan != 6 || !p.text.starts_with("〔명반|") {
            continue;
        }
        let Some(chart) = extract_chart(&p.text) else { continue };
        let next = jeonseo.get(i + 1).filter(|n| n.section == p.section);
        let explain_id = next.map(|n| n.id.clone());
        let (case, _) = build_case(p.id.clone(), "전서", p.section.clone(), &chart, explain_id);
        if let Some(n) = next {
            sealed.push((n.id.clone(), p.id.clone(), n.text.clone()));
        }
        cases.push(case);
    }
    for p in jeonjip {
        if !p.text.contains("〔명반:") {
            continue;
        }
        let Some(chart) = extract_chart(&p.text) else { continue };
        let title = chart.title.clone().unwrap_or_default();
        let (mut case, expl) = build_case(p.id.clone(), "전집", title, &chart, None);
        if let Some(t) = expl {
            let eid = format!("{}#小注", p.id);
            case.explain_id = Some(eid.clone());
            sealed.push((eid, p.id.clone(), t));
        }
        cases.push(case);
    }
    CaseSet { cases, sealed }
}

pub fn summary_md(set: &CaseSet) -> String {
    let n = set.cases.len();
    let js = set.cases.iter().filter(|c| c.source == "전서").count();
    let jj = n - js;
    let with_age = set.cases.iter().filter(|c| c.death.as_ref().map_or(false, |d| d.age.is_some())).count();
    let with_death = set.cases.iter().filter(|c| c.death.is_some()).count();
    let n_unp: usize = set.cases.iter().map(|c| c.unparsed.len()).sum();
    let cases_unp = set.cases.iter().filter(|c| !c.unparsed.is_empty()).count();
    let mut by_reason: std::collections::BTreeMap<String, usize> = Default::default();
    for c in &set.cases {
        for u in &c.unparsed {
            let key = format!("{} | {}", u.field.split('.').next().unwrap_or(""), u.reason.split(':').next().unwrap_or(""));
            *by_reason.entry(key).or_default() += 1;
        }
    }
    let mut s = String::new();
    s.push_str("# 명례(명반) 추출 요약\n\n");
    s.push_str(&format!("- 전체 {n}건 (전서 {js}, 전집 {jj})\n"));
    s.push_str(&format!("- 中左(사망) 칸 있는 것 {with_death}건, 그중 사망 나이를 읽은 것 {with_age}건\n"));
    s.push_str(&format!("- unparsed 항목 {n_unp}개, 해당 명반 {cases_unp}건\n\n"));
    s.push_str("## unparsed 유형별\n\n");
    for (k, v) in &by_reason {
        s.push_str(&format!("- {k}: {v}\n"));
    }
    s.push_str("\n## unparsed 예 (앞 12개)\n\n");
    let mut shown = 0;
    'o: for c in &set.cases {
        for u in &c.unparsed {
            let raw: String = u.raw.chars().take(60).collect();
            s.push_str(&format!("- `{}` [{}] {} -- {}\n", c.id, u.field, u.reason, raw));
            shown += 1;
            if shown >= 12 {
                break 'o;
            }
        }
    }
    s.push_str("\n풀이 글(전서의 다음 문단, 전집의 小注)은 cases.json에 넣지 않고 explain_id만 두었다.\n");
    s
}

pub fn sealed_jsonl(set: &CaseSet) -> String {
    let mut out = String::new();
    for (id, case_id, text) in &set.sealed {
        out.push_str(&json!({"id": id, "case_id": case_id, "text": text}).to_string());
        out.push('\n');
    }
    out
}

pub fn cases_json(set: &CaseSet) -> Value {
    serde_json::to_value(&set.cases).unwrap()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn birth_example() {
        let (b, bad) = parse_birth("己丑年三月十五日戌時生 陰男 土五局");
        assert!(bad.is_empty(), "{bad:?}");
        assert_eq!(b.year_gz.as_deref(), Some("己丑"));
        assert_eq!(b.month, Some(3));
        assert_eq!(b.day, Some(15));
        assert_eq!(b.hour_branch.as_deref(), Some("戌"));
        assert_eq!(b.yin_yang.as_deref(), Some("陰"));
        assert_eq!(b.sex.as_deref(), Some("男"));
        assert_eq!(b.element.as_deref(), Some("土"));
        assert_eq!(b.bureau, Some(5));
        assert!(!b.leap);
    }

    #[test]
    fn birth_variants() {
        let (b, bad) = parse_birth("丙申年閏十二月初十亥時生 陽男 木三局");
        assert!(bad.is_empty());
        assert!(b.leap);
        assert_eq!(b.month, Some(12));
        assert_eq!(b.day, Some(10));
        // 전집 형식: 日 없음, 局이 陰陽 앞
        let (b, bad) = parse_birth("庚子年正月二十二酉時 金四局 陽男");
        assert!(bad.is_empty(), "{bad:?}");
        assert_eq!((b.month, b.day, b.bureau), (Some(1), Some(22), Some(4)));
        // 간지 오류는 채우지 않는다
        let (b, bad) = parse_birth("巳酉年五月初一子時生 陰男 土五局");
        assert!(b.year_gz.is_none());
        assert!(bad.iter().any(|x| x.0 == "中.年干支"));
        // 판각 없음
        let (b, bad) = parse_birth("乙巳年正月十五日戌時(局名·陰陽 판각 없음)");
        assert!(b.bureau.is_none() && b.yin_yang.is_none());
        assert_eq!(bad.len(), 2);
    }

    #[test]
    fn death_example() {
        let (d, bad) = parse_death("乙亥年三十二歲二月初七故");
        assert!(bad.is_empty(), "{bad:?}");
        assert_eq!(d.year_gz.as_deref(), Some("乙亥"));
        assert_eq!(d.age, Some(32));
        assert_eq!((d.month, d.day), (Some(2), Some(7)));
        let (d, _) = parse_death("辛丑年七十三歲七月初八故");
        assert_eq!(d.age, Some(73));
        let (d, bad) = parse_death("丙申年三十二(?)歲三月初三故");
        assert!(d.uncertain);
        assert_eq!(d.age, Some(32));
        assert!(bad.is_empty());
        let (d, bad) = parse_death("丙申年三十二歲三月初□故");
        assert!(d.day.is_none());
        assert_eq!(bad.len(), 1);
    }

    #[test]
    fn chart_and_cells() {
        let t = "〔명반|中:己丑年三月十五日戌時生 陰男 土五局|中左:乙亥年三十二歲二月初七故|巳:破軍 武曲(權) 天傷 奴僕 絕 大耗|午:太陽(祿) 遷移 胎 伏兵|亥:紫微(權, 자형 忌) 大限 命宮 □〕陰男土五局";
        let ch = extract_chart(t).unwrap();
        assert_eq!(ch.trailer, "陰男土五局");
        assert_eq!(ch.fields.len(), 5);
        let (c, why) = parse_cell("巳", &ch.fields[2].1);
        assert!(why.is_none());
        assert_eq!(c.stars.len(), 3);
        assert_eq!(c.stars[1].hua, vec!["權"]);
        assert_eq!(c.palace_names, vec!["奴僕"]);
        assert_eq!(c.stage, vec!["絕"]);
        assert_eq!(c.other, vec!["大耗"]);
        let (c, why) = parse_cell("亥", &ch.fields[4].1);
        assert!(why.unwrap().contains('□'));
        assert_eq!(c.stars[0].hua, vec!["權"]);
        assert!(c.stars[0].notes.contains(&"忌".to_string()));
        assert_eq!(c.flags, vec!["大限"]);
    }

    #[test]
    fn jeonjip_chart() {
        let t = "〔명반:宰相之命|표제小字:介溪嚴氏|中:庚子年正月二十二酉時 金四局 陽男|巳:天才 武曲(權)|小注:此武貞|貪曲〕";
        let ch = extract_chart(t).unwrap();
        assert_eq!(ch.title.as_deref(), Some("宰相之命"));
        assert_eq!(ch.fields[0], ("표제小字".to_string(), "介溪嚴氏".to_string()));
        assert_eq!(ch.fields.last().unwrap().1, "此武貞|貪曲");
    }
}
