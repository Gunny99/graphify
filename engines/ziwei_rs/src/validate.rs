//! 명례(명반 칸) ↔ 엔진 계산 대조. 해석하지 않고 일치·불일치를 센다.
//! 사용: zw validate-cases <cases.json> <out_dir>  →  명반대조.tsv, 명반대조.md
use crate::chart::{build_chart, place_stars_with, FireBell, Input, QUANSHU_FIREBELL};
use crate::common::*;
use crate::timeline::{build_timeline, DaxianStart, TimelineOpts};
use serde_json::Value;
use std::collections::BTreeMap;
use std::fmt::Write as _;

/// 한자 별 이름 → 엔진 한글 이름(chart.py 기준). 天空은 기본 지공(전서 卷3 0035), 地空도 지공.
/// 한 명반에 天空과 地空이 함께 나오면(전집 명경각 2건) 天空은 천공(chart.py의 年支 기준 별)으로 맞댄다.
pub(crate) const STAR_MAP: [(&str, &str); 52] = [
    ("紫微", "자미"), ("天機", "천기"), ("太陽", "태양"), ("武曲", "무곡"), ("天同", "천동"), ("廉貞", "염정"),
    ("天府", "천부"), ("太陰", "태음"), ("貪狼", "탐랑"), ("巨門", "거문"), ("天相", "천상"), ("天梁", "천량"),
    ("七殺", "칠살"), ("破軍", "파군"), ("左輔", "좌보"), ("右弼", "우필"), ("文昌", "문창"), ("文曲", "문곡"),
    ("天魁", "천괴"), ("天鉞", "천월"), ("祿存", "녹존"), ("天馬", "천마"), ("擎羊", "경양"), ("陀羅", "타라"),
    ("火星", "화성"), ("鈴星", "영성"), ("地劫", "지겁"), ("天空", "지공"), ("地空", "지공"), ("天刑", "천형"),
    ("天姚", "천요"), ("天傷", "천상(傷)"), ("天使", "천사"), ("紅鸞", "홍란"), ("天喜", "천희"), ("三台", "삼태"),
    ("八座", "팔좌"), ("鳳閣", "봉각"), ("龍池", "용지"), ("天虛", "천허"), ("天哭", "천곡"), ("台輔", "태보"),
    ("封誥", "봉고"), ("天壽", "천수"), ("天福", "천복"), ("恩光", "은광"), ("天貴", "천귀"), ("天官", "천관"),
    ("天才", "천재"), ("截空", "절공"), ("天德", "천덕"), ("天廚", "천주"),
];
const HUA_MAP: [(&str, &str); 4] = [("록", "祿"), ("권", "權"), ("과", "科"), ("기", "忌")];
const SIHUA_STARS: [&str; 18] = ["자미", "천기", "태양", "무곡", "천동", "염정", "천부", "태음", "탐랑", "거문", "천상", "천량", "칠살", "파군", "좌보", "우필", "문창", "문곡"];
/// 명궁·신궁·국에 걸려 있어 윤달 사례에서는 제외하는 별(월·명궁 기준)
const MONTH_STARS: [&str; 28] = ["자미", "천기", "태양", "무곡", "천동", "염정", "천부", "태음", "탐랑", "거문", "천상", "천량", "칠살", "파군",
    "좌보", "우필", "천형", "천요", "삼태", "팔좌", "천무", "천월(月)", "음살", "해신", "천재", "천수", "천상(傷)", "천사"];
pub(crate) const STAGE_MAP: [(&str, &str); 12] = [("長生", "장생"), ("沐浴", "목욕"), ("冠帶", "관대"), ("臨官", "임관"), ("帝旺", "제왕"), ("衰", "쇠"),
    ("病", "병"), ("死", "사"), ("墓", "묘"), ("絕", "절"), ("胎", "태"), ("養", "양")];
const ROLE_MAP: [(&str, &str); 19] = [("命垣", "명"), ("命宮", "명"), ("身命垣", "명"), ("身命", "명"), ("命身", "명"), ("身命同宮", "명"),
    ("兄弟", "형제"), ("夫妻", "부처"), ("妻妾", "부처"), ("妻宮", "부처"), ("子女", "자녀"), ("子息", "자녀"), ("財帛", "재백"),
    ("疾厄", "질액"), ("遷移", "천이"), ("奴僕", "노복"), ("官祿", "관록"), ("田宅", "전택"), ("田地", "전택")];
const EXTRA_ROLES: [(&str, &str); 2] = [("福德", "복덕"), ("父母", "부모")];
const MING_NAMES: [&str; 6] = ["命垣", "命宮", "身命垣", "身命", "命身", "身命同宮"];
const SHEN_NAMES: [&str; 8] = ["身", "身宮", "身垣", "身命垣", "身命", "命身", "身命同宮", "身命"];

struct Row {
    variant: &'static str,
    id: String,
    group: String,
    item: String,
    case_val: String,
    engine_val: String,
    result: &'static str, // 일치 | 불일치 | 제외
    note: String,
    delta: Option<i64>, // 지지 차(칸 − 엔진), 자리 항목만
}

fn s(v: &Value) -> Option<&str> {
    v.as_str()
}
fn map_find<'a>(m: &'a [(&str, &str)], k: &str) -> Option<&'a str> {
    m.iter().find(|(a, _)| *a == k).map(|(_, b)| *b)
}
fn hua_han(h: &Value) -> String {
    h.as_str().and_then(|x| map_find(&HUA_MAP, x)).unwrap_or("-").to_string()
}

pub fn run(cases_path: &str, out_dir: &str, quanshu: bool) -> Result<String, String> {
    let raw = std::fs::read_to_string(cases_path).map_err(|e| e.to_string())?;
    let cases: Vec<Value> = serde_json::from_str(&raw).map_err(|e| e.to_string())?;
    let mut rows: Vec<Row> = vec![];
    for c in &cases {
        case_rows(c, &mut rows, false);
    }
    if quanshu {
        let mut qrows: Vec<Row> = vec![];
        for c in &cases {
            case_rows(c, &mut qrows, true);
        }
        std::fs::create_dir_all(out_dir).map_err(|e| e.to_string())?;
        write_tsv(&format!("{out_dir}/명반대조_quanshu.tsv"), &qrows)?;
        let md = report_quanshu(&rows, &qrows, &cases);
        std::fs::write(format!("{out_dir}/명반대조_quanshu.md"), md).map_err(|e| e.to_string())?;
    }
    std::fs::create_dir_all(out_dir).map_err(|e| e.to_string())?;
    write_tsv(&format!("{out_dir}/명반대조.tsv"), &rows)?;
    let md = report(&rows, cases.len());
    std::fs::write(format!("{out_dir}/명반대조.md"), &md).map_err(|e| e.to_string())?;
    Ok(format!("{} rows → {out_dir}", rows.len()))
}

fn write_tsv(path: &str, rows: &[Row]) -> Result<(), String> {
    let mut tsv = String::from("variant\tcase_id\t항목군\t항목\t칸값\t계산값\t결과\t비고\n");
    for r in rows {
        let _ = writeln!(tsv, "{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}", r.variant, r.id, r.group, r.item, r.case_val, r.engine_val, r.result, r.note);
    }
    std::fs::write(path, tsv).map_err(|e| e.to_string())
}

pub(crate) fn guess_year(c: &Value) -> Option<(String, String)> {
    let b = &c["birth"];
    let raw: Vec<char> = s(&b["raw"])?.chars().collect();
    if raw.len() < 2 {
        return None;
    }
    let (a, z) = (raw[0], raw[1]);
    let gz = if a == '巳' {
        format!("己{z}")
    } else if a == '□' {
        let note = b["notes"].as_array()?.iter().find_map(|n| s(n))?;
        let t: Vec<char> = note.chars().collect();
        let i = t.iter().position(|&x| x == '로')?;
        t[i + 2..i + 4].iter().collect()
    } else {
        return None;
    };
    let g: Vec<char> = gz.chars().collect();
    if g.len() == 2 && k60(g[0], g[1]).is_some() {
        Some((gz, if a == '巳' { "巳→己".into() } else { "note의 乙卯".into() }))
    } else {
        None
    }
}

fn case_rows(c: &Value, out: &mut Vec<Row>, q: bool) {
    let id = s(&c["id"]).unwrap_or("?").to_string();
    let b = &c["birth"];
    let (variant, ygz, vnote): (&'static str, String, String) = match s(&b["year_gz"]) {
        Some(g) => ("primary", g.to_string(), String::new()),
        None => match guess_year(c) {
            Some((g, n)) => ("typo_guess", g, n),
            None => {
                out.push(Row { variant: "primary", id, group: "사례".into(), item: "年干支".into(), case_val: s(&b["raw"]).unwrap_or("").into(), engine_val: "".into(), result: "제외", note: "年干支를 읽을 수 없음".into(), delta: None });
                return;
            }
        },
    };
    let (Some(month), Some(day), Some(hb)) = (b["month"].as_i64(), b["day"].as_i64(), s(&b["hour_branch"])) else {
        out.push(Row { variant, id, group: "사례".into(), item: "생월일시".into(), case_val: "".into(), engine_val: "".into(), result: "제외", note: "월·일·시 없음".into(), delta: None });
        return;
    };
    let male_opt = match s(&b["sex"]) {
        Some("男") => Some(true),
        Some("女") => Some(false),
        _ => None,
    };
    let leap = b["leap"].as_bool().unwrap_or(false);
    let inp = Input { year_gz: ygz.clone(), month, day, hour: hb.to_string(), male: male_opt.unwrap_or(true), leap, leap_rule: None, variant: if q { Some("quanshu".into()) } else { None } };
    let ch = match build_chart(&inp) {
        Ok(v) => v,
        Err(e) => {
            out.push(Row { variant, id, group: "사례".into(), item: "계산".into(), case_val: "".into(), engine_val: "".into(), result: "제외", note: e, delta: None });
            return;
        }
    };
    let push = |group: &str, item: String, cv: String, ev: String, note: String, delta: Option<i64>, out: &mut Vec<Row>| {
        let ok = cv == ev;
        out.push(Row { variant, id: id.clone(), group: group.into(), item, case_val: cv, engine_val: ev, result: if ok { "일치" } else { "불일치" }, note: if note.is_empty() { vnote.clone() } else { format!("{vnote} {note}").trim().into() }, delta });
    };
    let excl = |out: &mut Vec<Row>, group: &str, why: &str| {
        out.push(Row { variant, id: id.clone(), group: group.into(), item: "-".into(), case_val: "".into(), engine_val: "".into(), result: "제외", note: why.into(), delta: None });
    };
    let pal = c["palaces"].as_array().cloned().unwrap_or_default();
    let has_tian = pal.iter().any(|p| p["stars"].as_array().map_or(false, |a| a.iter().any(|x| s(&x["name"]) == Some("天空"))));
    let has_di = pal.iter().any(|p| p["stars"].as_array().map_or(false, |a| a.iter().any(|x| s(&x["name"]) == Some("地空"))));
    let delta = |case_b: &str, eng_b: &str| Some((bi(case_b.chars().next().unwrap()) - bi(eng_b.chars().next().unwrap())).rem_euclid(12));
    let eng_pos = |name: &str| s(&ch["pos"][name]).map(|x| x.to_string());
    if leap {
        excl(out, "윤달", "윤달 출생: 월·명궁에 걸린 항목(주성 자리, 월계 별, 命身 궁, 궁 이름, 局, 十二長生, 大限) 제외");
    }
    for p in &pal {
        let br = s(&p["branch"]).unwrap_or("?");
        let parsed = p["parsed"].as_bool().unwrap_or(false);
        if !parsed {
            excl(out, "칸", &format!("{br}궁 칸에 □ 판독불가"));
            continue;
        }
        // 별 자리·사화
        for st in p["stars"].as_array().cloned().unwrap_or_default() {
            let han = s(&st["name"]).unwrap_or("");
            if st["notes"].as_array().map_or(false, |n| !n.is_empty()) {
                continue;
            }
            let eng = if han == "天空" && has_di { Some("천공") } else { map_find(&STAR_MAP, han) };
            let Some(eng) = eng else {
                push("별자리", han.into(), br.into(), "(엔진에 없음)".into(), "".into(), None, out);
                out.last_mut().unwrap().result = "제외";
                continue;
            };
            let _ = has_tian;
            if !(leap && MONTH_STARS.contains(&eng)) {
                if let Some(e) = eng_pos(eng) {
                    push("별자리", format!("{han}({eng})"), br.into(), e.clone(), "".into(), delta(br, &e), out);
                }
            }
            if SIHUA_STARS.contains(&eng) {
                let cv = st["hua"].as_array().and_then(|a| a.first()).map(|h| hua_han(h)).unwrap_or("-".into());
                let ev = ch["birth_hua"].as_object().unwrap().iter().find(|(_, v)| s(&v["star"]) == Some(eng)).map(|(k, _)| map_find(&HUA_MAP, k).unwrap().to_string()).unwrap_or("-".into());
                push("사화", format!("{han}({eng})"), cv, ev, "".into(), None, out);
            }
        }
        // 궁 이름·命身
        let names: Vec<&str> = p["palace_names"].as_array().map(|a| a.iter().filter_map(|x| s(x)).collect()).unwrap_or_default();
        if !leap {
            let eng_role = s(&ch["palaces"][br]["role"]).unwrap_or("").to_string();
            let role = names.iter().find_map(|n| map_find(&ROLE_MAP, n).or_else(|| map_find(&EXTRA_ROLES, n)));
            if let Some(r) = role {
                push("궁이름", br.into(), r.into(), eng_role, names.join("+"), None, out);
            }
        }
        let st_han = p["stage"].as_array().and_then(|a| a.first()).and_then(|x| s(x));
        if let Some(sh) = st_han {
            if !leap {
                if male_opt.is_some() {
                    let cv = map_find(&STAGE_MAP, sh).unwrap_or(sh);
                    let ev = s(&ch["palaces"][br]["changsheng"]).unwrap_or("").to_string();
                    push("十二長生", br.into(), cv.into(), ev, "".into(), None, out);
                }
            }
        }
    }
    if !leap {
        let ming = pal.iter().find(|p| p["palace_names"].as_array().map_or(false, |a| a.iter().any(|n| s(n).map_or(false, |n| MING_NAMES.contains(&n)))));
        let shen = pal.iter().find(|p| p["palace_names"].as_array().map_or(false, |a| a.iter().any(|n| s(n).map_or(false, |n| SHEN_NAMES.contains(&n)))));
        if let Some(m) = ming {
            let cb = s(&m["branch"]).unwrap();
            let e = s(&ch["ming"]).unwrap();
            push("命궁", "命垣".into(), cb.into(), e.into(), "".into(), delta(cb, e), out);
        }
        if let Some(m) = shen {
            let cb = s(&m["branch"]).unwrap();
            let e = s(&ch["shen"]).unwrap();
            push("身궁", "身".into(), cb.into(), e.into(), "".into(), delta(cb, e), out);
        }
        if let Some(bu) = b["bureau"].as_i64() {
            push("오행국", "局".into(), bu.to_string(), ch["ju"].as_i64().unwrap().to_string(), "".into(), None, out);
        }
    }
    // 사망 나이의 운 표지
    let age = c["death"]["age"].as_i64();
    let Some(age) = age.filter(|a| (1..=100).contains(a)) else { return };
    let unc = if c["death"]["uncertain"].as_bool().unwrap_or(false) { "사망 나이 불확실" } else { "" };
    let flagged = |f: &str| -> Vec<String> { pal.iter().filter(|p| p["flags"].as_array().map_or(false, |a| a.iter().any(|x| s(x) == Some(f)))).filter_map(|p| s(&p["branch"]).map(|x| x.to_string())).collect() };
    let tl = |ds| build_timeline(&inp, TimelineOpts { daxian_start: ds, dayun_start: None }).ok();
    let (Some(tx), Some(tm)) = (tl(DaxianStart::Xusui), tl(DaxianStart::Manage)) else { return };
    let yx = &tx["years"][(age - 1) as usize];
    let ym = &tm["years"][(age - 1) as usize];
    let pb = |v: &Value| s(&v["branch"]).unwrap_or("").to_string();
    let cmp = |group: &str, flag: &str, ev: String, out: &mut Vec<Row>| {
        let f = flagged(flag);
        if f.is_empty() {
            return;
        }
        let cv = f.join("/");
        let ok = f.contains(&ev);
        let d = if ev.is_empty() { None } else { delta(&f[0], &ev) };
        out.push(Row { variant, id: id.clone(), group: group.into(), item: format!("虛歲{age}"), case_val: cv, engine_val: if ev.is_empty() { "없음".into() } else { ev }, result: if ok { "일치" } else { "불일치" }, note: format!("{vnote} {unc}").trim().into(), delta: d });
    };
    if q && male_opt.is_some() && !leap {
        if let Some(tq) = tl(DaxianStart::Quanshu) {
            let yq = &tq["years"][(age - 1) as usize];
            cmp("大限(quanshu)", "大限", if yq["daxian"].is_null() { String::new() } else { pb(&yq["daxian"]["palace"]) }, out);
        }
    }
    if male_opt.is_some() && !leap {
        cmp("大限(xusui)", "大限", if yx["daxian"].is_null() { String::new() } else { pb(&yx["daxian"]["palace"]) }, out);
        cmp("大限(manage)", "大限", if ym["daxian"].is_null() { String::new() } else { pb(&ym["daxian"]["palace"]) }, out);
    } else if leap {
        excl(out, "大限", "윤달");
    }
    if male_opt.is_some() {
        cmp("小限", "小限", pb(&yx["xiaoxian"]), out);
    }
    cmp("太歲", "太歲", pb(&yx["taisui"]["palace"]), out);
    cmp("流祿", "流祿", pb(&yx["liu_lu"]["palace"]), out);
    cmp("流羊", "流羊", pb(&yx["liu_yang"]["palace"]), out);
    cmp("流陀", "流陀", pb(&yx["liu_tuo"]["palace"]), out);
}

fn report(rows: &[Row], n_cases: usize) -> String {
    let mut md = String::from("# 명례 명반 칸 ↔ 엔진(Rust) 계산 대조\n\n");
    let _ = writeln!(md, "- 사례 {n_cases}건. 칸값은 cases.json, 계산값은 ziwei_rs(chart·timeline). 해석 없이 수치만.");
    md.push_str("- 별 이름 대응: 天空→지공(전서 卷3 0035). 한 명반에 天空·地空이 함께 있으면 天空→천공, 地空→지공. 羊刃 등 엔진에 없는 별은 '제외'.\n");
    md.push_str("- 虛歲 = 사망 나이. 大限은 xusui(局數 虛歲부터)와 manage(局數+1부터) 둘 다. 윤달 사례는 월·명궁 항목 제외. 斗君은 엔진에 없어 대조하지 않음.\n\n");
    for variant in ["primary", "typo_guess"] {
        let vr: Vec<&Row> = rows.iter().filter(|r| r.variant == variant).collect();
        if vr.is_empty() {
            continue;
        }
        let _ = writeln!(md, "## 항목군별 일치율 ({variant})\n");
        md.push_str("| 항목군 | 대조 | 일치 | 불일치 | 일치율 | 제외 |\n|---|---|---|---|---|---|\n");
        let mut g: BTreeMap<&str, (usize, usize, usize)> = BTreeMap::new();
        for r in &vr {
            let e = g.entry(r.group.as_str()).or_default();
            match r.result {
                "일치" => e.0 += 1,
                "불일치" => e.1 += 1,
                _ => e.2 += 1,
            }
        }
        for (k, (m, x, e)) in &g {
            if m + x > 0 {
                let _ = writeln!(md, "| {k} | {} | {m} | {x} | {:.1}% | {e} |", m + x, 100.0 * *m as f64 / (m + x) as f64);
            } else {
                let _ = writeln!(md, "| {k} | 0 | 0 | 0 | - | {e} |");
            }
        }
        let (m, x) = vr.iter().fold((0, 0), |a, r| (a.0 + (r.result == "일치") as usize, a.1 + (r.result == "불일치") as usize));
        let _ = writeln!(md, "| 전체 | {} | {m} | {x} | {:.1}% | |\n", m + x, 100.0 * m as f64 / (m + x).max(1) as f64);
        // 사례 수(大限)
        let cases_dx = |grp: &str| vr.iter().filter(|r| r.group == grp).map(|r| r.id.as_str()).collect::<std::collections::BTreeSet<_>>().len();
        let _ = writeln!(md, "사례 수: 大限(xusui) {}, 大限(manage) {}, 小限 {}, 太歲 {}.\n", cases_dx("大限(xusui)"), cases_dx("大限(manage)"), cases_dx("小限"), cases_dx("太歲"));
        // 불일치 유형
        md.push_str("### 불일치 상위 유형\n\n| 유형 | 건수 |\n|---|---|\n");
        let mut ty: BTreeMap<String, usize> = BTreeMap::new();
        for r in vr.iter().filter(|r| r.result == "불일치") {
            let key = if r.group == "별자리" || r.group == "사화" { format!("{}:{}", r.group, r.item) } else { r.group.clone() };
            *ty.entry(key).or_default() += 1;
        }
        let mut tv: Vec<_> = ty.into_iter().collect();
        tv.sort_by(|a, b| b.1.cmp(&a.1).then(a.0.cmp(&b.0)));
        for (k, n) in tv.iter().take(15) {
            let _ = writeln!(md, "| {k} | {n} |");
        }
        md.push_str("\n### 자리 불일치의 지지 차(칸 − 엔진, 12로 나눈 나머지)\n\n| 항목군 | 차: 건수 |\n|---|---|\n");
        let mut dd: BTreeMap<String, BTreeMap<i64, usize>> = BTreeMap::new();
        for r in vr.iter().filter(|r| r.result == "불일치") {
            if let Some(d) = r.delta {
                let g = if r.group == "별자리" { "별자리".to_string() } else { r.group.clone() };
                *dd.entry(g).or_default().entry(d).or_default() += 1;
            }
        }
        for (k, m) in &dd {
            let mut v: Vec<_> = m.iter().collect();
            v.sort_by(|a, b| b.1.cmp(a.1));
            let _ = writeln!(md, "| {k} | {} |", v.iter().take(6).map(|(d, n)| format!("{d}: {n}")).collect::<Vec<_>>().join(", "));
        }
        md.push_str("\n### 불일치 예 10개\n\n| case | 항목군 | 항목 | 칸값 | 계산값 | 비고 |\n|---|---|---|---|---|---|\n");
        let mut shown = 0;
        let mut seen: std::collections::BTreeSet<&str> = Default::default();
        let mis: Vec<&&Row> = vr.iter().filter(|r| r.result == "불일치").collect();
        for pass in 0..2 {
            for r in &mis {
                if shown >= 10 {
                    break;
                }
                let first = seen.insert(r.group.as_str());
                if (pass == 0 && first) || (pass == 1 && !first && r.item != "-" && !md.contains(&format!("| {} | {} | {} |", r.id, r.group, r.item))) {
                    let _ = writeln!(md, "| {} | {} | {} | {} | {} | {} |", r.id, r.group, r.item, r.case_val, r.engine_val, r.note);
                    shown += 1;
                }
            }
        }
        md.push('\n');
    }
    md
}

/// 火星·鈴星 후보: (이름, 방향 규칙 mode, 시 기점 off). 칸의 火星·鈴星 자리와 맞댄다.
const FB_CANDIDATES: [(&str, u8, i64); 9] = [
    ("둘 다 순행, 子時=기점(기본)", 0, 0), ("둘 다 순행, 子時=기점+1", 0, 1),
    ("火 순·鈴 역, 子時=기점", 1, 0), ("火 순·鈴 역, 子時=기점+1", 1, 1),
    ("陽男陰女 순·반대 역(둘 다), 子時=기점", 2, 0), ("陽男陰女 순·반대 역(둘 다), 子時=기점+1", 2, 1),
    ("火는 陽男陰女 순·반대 역, 鈴은 그 반대, 子時=기점", 3, 0), ("火는 陽男陰女 순·반대 역, 鈴은 그 반대, 子時=기점+1", 3, 1),
    ("시를 세지 않음(기점 고정, 시 가산 0)", 4, 0),
];

fn firebell_table(cases: &[Value]) -> String {
    let mut out = String::from("| 후보 | 火星 | 鈴星 | 합계 |\n|---|---|---|---|\n");
    for (name, mode, off) in FB_CANDIDATES {
        let (mut fm, mut fnn, mut bm, mut bn) = (0, 0, 0, 0);
        for c in cases {
            let b = &c["birth"];
            let ygz = match s(&b["year_gz"]) {
                Some(g) => g.to_string(),
                None => match guess_year(c) {
                    Some((g, _)) => g,
                    None => continue,
                },
            };
            let g: Vec<char> = ygz.chars().collect();
            let (Some(m), Some(d), Some(hb), Some(sex)) = (b["month"].as_i64(), b["day"].as_i64(), s(&b["hour_branch"]), s(&b["sex"])) else { continue };
            if b["leap"].as_bool() == Some(true) {
                continue; // 월이 걸린 별은 아니지만 사례 단위로 윤달은 제외해 위 표와 같은 사례 집합을 쓴다
            }
            let Ok(pl) = place_stars_with(g[0], g[1], m, d, bi(hb.chars().next().unwrap()), sex == "男", FireBell { mode, off }) else { continue };
            for p in c["palaces"].as_array().into_iter().flatten() {
                if !p["parsed"].as_bool().unwrap_or(false) {
                    continue;
                }
                let br = s(&p["branch"]).unwrap_or("?");
                for st in p["stars"].as_array().into_iter().flatten() {
                    let (nm, en) = match s(&st["name"]) {
                        Some("火星") => ("火", "화성"),
                        Some("鈴星") => ("鈴", "영성"),
                        _ => continue,
                    };
                    let e = pl.pos.iter().find(|(n, _)| *n == en).map(|(_, z)| z.to_string()).unwrap_or_default();
                    let ok = e == br;
                    if nm == "火" {
                        fnn += 1;
                        fm += ok as usize;
                    } else {
                        bn += 1;
                        bm += ok as usize;
                    }
                }
            }
        }
        let _ = writeln!(out, "| {name} | {fm}/{fnn} ({:.1}%) | {bm}/{bn} ({:.1}%) | {:.1}% |", 100.0 * fm as f64 / fnn.max(1) as f64, 100.0 * bm as f64 / bn.max(1) as f64, 100.0 * (fm + bm) as f64 / (fnn + bn).max(1) as f64);
    }
    out
}

fn rates(rows: &[Row]) -> BTreeMap<String, (usize, usize)> {
    let mut g: BTreeMap<String, (usize, usize)> = BTreeMap::new();
    for r in rows.iter().filter(|r| r.variant == "primary") {
        let e = g.entry(r.group.clone()).or_default();
        match r.result {
            "일치" => e.0 += 1,
            "불일치" => e.1 += 1,
            _ => {}
        }
    }
    g
}

fn report_quanshu(base: &[Row], q: &[Row], cases: &[Value]) -> String {
    let mut md = String::from("# 전서 계열 변형(quanshu) 대조\n\n");
    md.push_str("- 변형: 사화표 전서남양당-3-권본문-0031, 大限 규약 -0079(陽男陰女 父母궁=명궁+1, 陰男陽女 兄弟궁=명궁-1에서 시작), 火鈴은 아래 후보표의 최고 후보. 기본값은 바꾸지 않았다. 천간이 읽힌 사례(primary)만 센다.\n");
    let best = QUANSHU_FIREBELL;
    let _ = writeln!(md, "- 변형에 쓴 火鈴: mode {}, off {}.\n", best.mode, best.off);
    md.push_str("## 火星·鈴星 후보별 일치(천간 읽힌 비윤달 사례의 칸 별)\n\n");
    md.push_str(&firebell_table(cases));
    md.push_str("\n## 항목군별 일치율: 기본 ↔ quanshu\n\n| 항목군 | 기본 대조 | 기본 일치율 | quanshu 대조 | quanshu 일치율 |\n|---|---|---|---|---|\n");
    let (rb, rq) = (rates(base), rates(q));
    let mut keys: Vec<&String> = rb.keys().chain(rq.keys()).collect();
    keys.sort();
    keys.dedup();
    let fmt = |v: Option<&(usize, usize)>| match v {
        Some((m, x)) if m + x > 0 => (format!("{}", m + x), format!("{:.1}%", 100.0 * *m as f64 / (m + x) as f64)),
        _ => ("-".into(), "-".into()),
    };
    let (mut tb, mut tq) = ((0, 0), (0, 0));
    for k in keys {
        let (a, b) = (fmt(rb.get(k)), fmt(rq.get(k)));
        if a.0 == "-" && b.0 == "-" {
            continue;
        }
        let _ = writeln!(md, "| {k} | {} | {} | {} | {} |", a.0, a.1, b.0, b.1);
        if let Some(v) = rb.get(k) { if !k.starts_with("大限(q") { tb.0 += v.0; tb.1 += v.1; } }
        if let Some(v) = rq.get(k) { if !k.starts_with("大限(x") && !k.starts_with("大限(m") { tq.0 += v.0; tq.1 += v.1; } }
    }
    let _ = writeln!(md, "| 전체(大限은 각 변형의 규약 하나만 넣음 — 기본: xusui·manage 둘 다, quanshu: quanshu) | {} | {:.1}% | {} | {:.1}% |", tb.0 + tb.1, 100.0 * tb.0 as f64 / (tb.0 + tb.1).max(1) as f64, tq.0 + tq.1, 100.0 * tq.0 as f64 / (tq.0 + tq.1).max(1) as f64);
    md.push_str("\n## quanshu에 남은 불일치 유형\n\n| 유형 | 건수 |\n|---|---|\n");
    let mut ty: BTreeMap<String, usize> = BTreeMap::new();
    for r in q.iter().filter(|r| r.variant == "primary" && r.result == "불일치" && !r.group.starts_with("大限(x") && !r.group.starts_with("大限(m")) {
        let key = if r.group == "별자리" || r.group == "사화" { format!("{}:{}", r.group, r.item) } else { r.group.clone() };
        *ty.entry(key).or_default() += 1;
    }
    let mut tv: Vec<_> = ty.into_iter().collect();
    tv.sort_by(|a, b| b.1.cmp(&a.1).then(a.0.cmp(&b.0)));
    for (k, n) in tv.iter().take(20) {
        let _ = writeln!(md, "| {k} | {n} |");
    }
    md.push_str("\n### 자리 불일치의 지지 차(칸 − 엔진), quanshu\n\n| 항목군 | 차: 건수 |\n|---|---|\n");
    let mut dd: BTreeMap<String, BTreeMap<i64, usize>> = BTreeMap::new();
    for r in q.iter().filter(|r| r.variant == "primary" && r.result == "불일치") {
        if let Some(d) = r.delta {
            *dd.entry(r.group.clone()).or_default().entry(d).or_default() += 1;
        }
    }
    for (k, m) in &dd {
        let mut v: Vec<_> = m.iter().collect();
        v.sort_by(|a, b| b.1.cmp(a.1));
        let _ = writeln!(md, "| {k} | {} |", v.iter().take(6).map(|(d, n)| format!("{d}: {n}")).collect::<Vec<_>>().join(", "));
    }
    md
}
