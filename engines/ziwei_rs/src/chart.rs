//! chart.py(place_stars, kong, build)의 Rust 옮김. 별 이름은 Python과 같은 한글.
use crate::common::*;
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use std::collections::HashMap;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Input {
    pub year_gz: String,
    pub month: i64,
    pub day: i64,
    pub hour: String,
    pub male: bool,
    /// 윤달 표시. 기록만 하고 계산에는 쓰지 않는다(month 그대로).
    #[serde(default)]
    pub leap: bool,
    /// 윤달 규칙: same | next | split15. 고객이 명시했을 때만 쓴다(없으면 same, choices에 선택 요청이 생김).
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub leap_rule: Option<String>,
}

pub fn chart_month(m: i64, d: i64, rule: &str) -> i64 {
    if rule == "next" || (rule == "split15" && d > 15) {
        m % 12 + 1
    } else {
        m
    }
}

/// 윤달 출생이면 고객 선택 항목. leap=false면 빈 목록.
pub fn choices(inp: &Input) -> Result<Vec<Value>, String> {
    if !inp.leap {
        return Ok(vec![]);
    }
    let g: Vec<char> = inp.year_gz.chars().collect();
    let h = bi(inp.hour.chars().next().ok_or("hour")?);
    let mut opts = vec![];
    let mut keys = vec![];
    for r in ["same", "next", "split15"] {
        let cm = chart_month(inp.month, inp.day, r);
        let pl = place_stars(g[0], g[1], cm, inp.day, h)?;
        opts.push(json!({"rule": r, "chart_month": cm, "ming": pl.ming.to_string(), "shen": pl.shen.to_string(), "ju": pl.ju, "ju_name": ju_name(pl.ju)}));
        keys.push(format!("{:?}{}{}{}", pl.pos, pl.ming, pl.shen, pl.ju));
    }
    keys.sort();
    keys.dedup();
    Ok(vec![json!({"kind": "leap", "default": "same", "chosen": inp.leap_rule, "options": opts, "same_result": keys.len() == 1})])
}

pub const NAYIN: &str = "金金火火木木土土金金火火水水土土金金木木水水土土火火木木水水金金火火木木土土金金火火水水土土金金木木水水土土火火木木水水";
const LU: &str = "寅卯巳午巳午申酉亥子"; // 安祿存, STEM 순서
const KUI: [&str; 10] = ["丑未", "子申", "亥酉", "亥酉", "丑未", "子申", "丑未", "午寅", "卯巳", "卯巳"];
const JIEKONG: [&str; 10] = ["申酉", "午未", "辰巳", "寅卯", "子丑", "申酉", "午未", "辰巳", "寅卯", "子丑"];
const FEILIAN: &str = "申酉戌巳午未寅卯辰亥子丑"; // BR 순서
const CS_START: [(i64, char); 5] = [(2, '申'), (3, '亥'), (4, '巳'), (5, '申'), (6, '寅')];

pub fn lu_of(stem: char) -> char {
    ch(LU, si(stem))
}

fn ju_of(e: char) -> i64 {
    match e {
        '水' => 2,
        '木' => 3,
        '金' => 4,
        '土' => 5,
        _ => 6,
    }
}
fn ju_name(n: i64) -> &'static str {
    match n {
        2 => "水二局",
        3 => "木三局",
        4 => "金四局",
        5 => "土五局",
        _ => "火六局",
    }
}
fn ma(b: char) -> char {
    match b {
        '寅' | '午' | '戌' => '申',
        '申' | '子' | '辰' => '寅',
        '巳' | '酉' | '丑' => '亥',
        _ => '巳',
    }
}
fn hl(b: char) -> &'static str {
    match b {
        '寅' | '午' | '戌' => "丑卯",
        '申' | '子' | '辰' => "寅戌",
        '巳' | '酉' | '丑' => "卯戌",
        _ => "酉戌",
    }
}
/// 삼합 묶음 번호: 0 寅午戌, 1 申子辰, 2 巳酉丑, 3 亥卯未
pub fn san(b: char) -> usize {
    match b {
        '寅' | '午' | '戌' => 0,
        '申' | '子' | '辰' => 1,
        '巳' | '酉' | '丑' => 2,
        _ => 3,
    }
}
fn sea(b: char) -> usize {
    (bi(b) as usize + 1) % 12 / 3 // 亥子丑 0, 寅卯辰 1, 巳午未 2, 申酉戌 3
}
fn mingzhu(z: char) -> &'static str {
    match z {
        '子' => "탐랑",
        '丑' | '亥' => "거문",
        '寅' | '戌' => "녹존",
        '卯' | '酉' => "문곡",
        '辰' | '申' => "염정",
        '巳' | '未' => "무곡",
        _ => "파군",
    }
}
fn shenzhu(z: char) -> &'static str {
    match z {
        '子' | '午' => "화성",
        '丑' | '未' => "천상",
        '寅' | '申' => "천량",
        '卯' | '酉' => "천동",
        '巳' | '亥' => "천기",
        _ => "문창",
    }
}

pub fn kind_of(name: &str) -> &'static str {
    if MAIN14.contains(&name) {
        "주성"
    } else if YUKGIL.contains(&name) || name == "녹존" || name == "천마" {
        "보좌"
    } else if SAL.contains(&name) {
        "살"
    } else {
        "잡성"
    }
}

#[derive(Debug, Clone, Serialize)]
pub struct Kong {
    #[serde(rename = "순공")]
    pub xun: Vec<String>,
    #[serde(rename = "절공")]
    pub jie: Vec<String>,
    #[serde(rename = "정_절공")]
    pub zj: String,
    #[serde(rename = "정_순공")]
    pub zx: String,
    #[serde(rename = "정공")]
    pub zheng: Vec<String>,
    #[serde(rename = "방공")]
    pub pang: Vec<String>,
}

pub fn kong(ys: char, yb: char) -> Result<Kong, String> {
    let k = k60(ys, yb).ok_or_else(|| format!("간지 음양 불일치: {ys}{yb}"))? as i64;
    let x0 = k - k % 10;
    let xun = [bz(x0 + 10), bz(x0 + 11)];
    let jie: Vec<char> = JIEKONG[si(ys)].chars().collect();
    let yang = yang_stem(ys);
    let pick = |p: &[char]| *p.iter().find(|&&z| (bi(z) % 2 == 0) == yang).unwrap();
    let (zj, zx) = (pick(&jie), pick(&xun));
    let mut zheng = vec![zj, zx];
    zheng.sort_by_key(|&z| bi(z));
    zheng.dedup();
    let mut pang: Vec<char> = xun.iter().chain(jie.iter()).copied().collect();
    pang.sort_by_key(|&z| bi(z));
    pang.dedup();
    pang.retain(|z| !zheng.contains(z));
    let s = |v: &[char]| v.iter().map(|c| c.to_string()).collect::<Vec<_>>();
    Ok(Kong { xun: s(&xun), jie: s(&jie), zj: zj.to_string(), zx: zx.to_string(), zheng: s(&zheng), pang: s(&pang) })
}

pub struct Placed {
    /// Python dict 삽입 순서 그대로 (이름, 지지)
    pub pos: Vec<(&'static str, char)>,
    pub ming: char,
    pub shen: char,
    pub ju: i64,
    pub stems: [char; 12], // 子..亥 지지별 천간
    pub kong: Kong,
}

pub fn place_stars(ys: char, yb: char, m: i64, d: i64, h: i64) -> Result<Placed, String> {
    let ming = (bi('寅') + m - 1 - h).rem_euclid(12);
    let shen = (bi('寅') + m - 1 + h).rem_euclid(12);
    let mut stems = ['甲'; 12];
    for k in 0..12i64 {
        stems[(bi('寅') + k).rem_euclid(12) as usize] = ch(STEM, (si(tiger(ys)) + k as usize) % 10);
    }
    let k = k60(stems[ming as usize], bz(ming)).ok_or("명궁 간지")?;
    let n = ju_of(ch(NAYIN, k));
    let mut x = 0;
    while (d + x) % n != 0 {
        x += 1;
    }
    let q = (d + x) / n;
    let zw = (bi('寅') + q - 1 + if x % 2 != 0 { -x } else { x }).rem_euclid(12);
    let tf = (4 - zw).rem_euclid(12);
    let y = bi(yb);
    let s = si(ys);
    let kg = kong(ys, yb)?;
    let lu = bi(lu_of(ys));
    let kui: Vec<char> = KUI[s].chars().collect();
    let hlv: Vec<char> = hl(yb).chars().collect();
    let sn = san(yb);
    let mut p: Vec<(&'static str, i64)> = vec![
        ("자미", zw), ("천기", zw - 1), ("태양", zw - 3), ("무곡", zw - 4), ("천동", zw - 5), ("염정", zw - 8),
        ("천부", tf), ("태음", tf + 1), ("탐랑", tf + 2), ("거문", tf + 3), ("천상", tf + 4), ("천량", tf + 5), ("칠살", tf + 6), ("파군", tf + 10),
        ("좌보", bi('辰') + m - 1), ("우필", bi('戌') - (m - 1)), ("문창", bi('戌') - h), ("문곡", bi('辰') + h),
        ("천괴", bi(kui[0])), ("천월", bi(kui[1])), ("녹존", lu), ("경양", lu + 1), ("타라", lu - 1),
        ("천마", bi(ma(yb))), ("화성", bi(hlv[0]) + h), ("영성", bi(hlv[1]) + h), ("지겁", bi('亥') + h), ("지공", bi('亥') - h),
        ("천형", bi('酉') + m - 1), ("천요", bi('丑') + m - 1),
        ("삼태", bi('辰') + m - 1 + d - 1), ("팔좌", bi('戌') - (m - 1) - (d - 1)),
    ];
    let wenchang = bi('戌') - h;
    let wenqu = bi('辰') + h;
    let pang_idx = pos_in("子午卯酉寅申巳亥辰戌丑未", yb).unwrap() / 4;
    let se = sea(yb);
    let mm = (m - 1) as usize;
    p.extend([
        ("홍란", bi('卯') - y), ("천희", bi('酉') - y),
        ("함지", bi(['卯', '酉', '午', '子'][sn])),
        ("천덕", bi('酉') + y), ("용덕", bi('未') + y), ("월덕", bi('巳') + y), ("년해", bi('戌') - y),
        ("대모", y + 6 + if y % 2 == 0 { 1 } else { -1 }),
        ("겁살", bi(['亥', '巳', '寅', '申'][sn])),
        ("화개", bi(['戌', '辰', '丑', '未'][sn])),
        ("고진", bi(ch("寅巳申亥", se))), ("과숙", bi(ch("戌丑辰未", se))),
        ("파쇄", bi(ch("巳酉丑", pang_idx))),
        ("용지", bi('辰') + y), ("봉각", bi('戌') - y), ("천곡", bi('午') - y), ("천허", bi('午') + y), ("천공", y + 1),
        ("천관", bi(ch("未辰巳寅卯酉亥酉戌午", s))), ("천복", bi(ch("酉申子亥卯寅午巳午巳", s))),
        ("천주", bi(ch("巳午子巳午申寅午酉戌", s))), ("홍염", bi(ch("午申寅未辰辰戌酉子申", s))),
        ("비렴", bi(ch(FEILIAN, bi(yb) as usize))),
        ("천무", bi(ch("巳申寅亥", mm % 4))), ("천월(月)", bi(ch("戌巳辰寅未卯亥未寅午戌寅", mm))),
        ("음살", bi(ch("寅子戌申午辰", mm % 6))), ("해신", bi(ch("申戌子寅辰午", mm / 2))),
        ("은광", wenchang + d - 2), ("천귀", wenqu + d - 2),
        ("태보", bi('午') + h), ("봉고", bi('寅') + h),
        ("천재", ming + y), ("천수", shen + y),
        ("천상(傷)", ming - 7), ("천사", ming - 5),
        ("절공", bi(kg.zj.chars().next().unwrap())), ("순공", bi(kg.zx.chars().next().unwrap())),
    ]);
    let pos = p.into_iter().map(|(a, b)| (a, bz(b))).collect();
    Ok(Placed { pos, ming: bz(ming), shen: bz(shen), ju: n, stems, kong: kg })
}

struct Tables {
    sihua: Value,
    cells: HashMap<(String, String), (String, String)>, // (별,지지) → (등급, 층)
    cls: HashMap<String, String>,
}

fn tables() -> Tables {
    let sihua: Value = serde_json::from_str(include_str!("../data/sihua.json")).unwrap();
    let b: Value = serde_json::from_str(include_str!("../data/brightness.json")).unwrap();
    let mut cells = HashMap::new();
    for c in b["cells"].as_array().unwrap() {
        cells.insert(
            (c["star"].as_str().unwrap().to_string(), c["branch"].as_str().unwrap().to_string()),
            (c["grade"].as_str().unwrap().to_string(), c["layer"].as_str().unwrap().to_string()),
        );
    }
    let cls = b["class"].as_object().unwrap().iter().map(|(k, v)| (k.clone(), v.as_str().unwrap().to_string())).collect();
    Tables { sihua, cells, cls }
}

/// 십간사화(기본 변형): [(화, 별)] 록권과기 순
pub fn sihua_of(stem: char) -> Vec<(&'static str, String)> {
    let t = tables();
    HUA.iter().map(|h| (*h, t.sihua["default"][stem.to_string()][*h]["star"].as_str().unwrap().to_string())).collect()
}

pub fn parse_input(inp: &Input) -> Result<(char, char, i64, i64, i64), String> {
    let g: Vec<char> = inp.year_gz.chars().collect();
    if g.len() != 2 || pos_in(STEM, g[0]).is_none() || pos_in(BR, g[1]).is_none() || k60(g[0], g[1]).is_none() {
        return Err(format!("year_gz 오류: {}", inp.year_gz));
    }
    if !(1..=12).contains(&inp.month) {
        return Err(format!("month 1~12: {}", inp.month));
    }
    if !(1..=30).contains(&inp.day) {
        return Err(format!("day 1~30: {}", inp.day));
    }
    let hc: Vec<char> = inp.hour.chars().collect();
    if hc.len() != 1 || pos_in(BR, hc[0]).is_none() {
        return Err(format!("hour 지지 한 글자: {}", inp.hour));
    }
    let rule = inp.leap_rule.as_deref().unwrap_or("same");
    if !["same", "next", "split15"].contains(&rule) {
        return Err(format!("leap_rule 오류: {rule}"));
    }
    let m = if inp.leap { chart_month(inp.month, inp.day, rule) } else { inp.month };
    Ok((g[0], g[1], m, inp.day, bi(hc[0])))
}

pub fn build_chart(inp: &Input) -> Result<Value, String> {
    let (ys, yb, m, d, h) = parse_input(inp)?;
    let pl = place_stars(ys, yb, m, d, h)?;
    let t = tables();
    let sh = sihua_of(ys);
    let fwd = yang_stem(ys) == inp.male;
    let n = pl.ju;
    let cs0 = bi(CS_START.iter().find(|(j, _)| *j == n).unwrap().1);
    let cs_at = |z: i64| -> &'static str {
        // bz(cs0 + (k or -k)) == z
        let k = if fwd { (z - cs0).rem_euclid(12) } else { (cs0 - z).rem_euclid(12) };
        CHANGSHENG[k as usize]
    };
    let pos_of = |name: &str| pl.pos.iter().find(|(n, _)| *n == name).map(|(_, z)| *z);
    let mut palaces = serde_json::Map::new();
    for z in BR.chars() {
        let mut stars = vec![];
        for (name, pz) in &pl.pos {
            if *pz != z {
                continue;
            }
            let key = (name.to_string(), z.to_string());
            let (grade, layer) = match t.cells.get(&key) {
                Some((g, l)) => (Value::from(g.clone()), Value::from(l.clone())),
                None => (Value::Null, Value::Null),
            };
            let cls = match &grade {
                Value::Null => "미확인".to_string(),
                g => t.cls[g.as_str().unwrap()].clone(),
            };
            let hua = sh.iter().find(|(_, s)| s == name).map(|(h, _)| Value::from(*h)).unwrap_or(Value::Null);
            stars.push(json!({"name": name, "kind": kind_of(name), "grade": grade, "grade_layer": layer, "cls": cls, "hua": hua}));
        }
        palaces.insert(
            z.to_string(),
            json!({"role": role_of(pl.ming, z), "stem": pl.stems[bi(z) as usize].to_string(), "stars": stars, "changsheng": cs_at(bi(z))}),
        );
    }
    let mut pos = serde_json::Map::new();
    for (n, z) in &pl.pos {
        pos.insert(n.to_string(), Value::from(z.to_string()));
    }
    let mut bh = serde_json::Map::new();
    for (h, s) in &sh {
        bh.insert(h.to_string(), json!({"star": s, "palace": pos_of(s).map(|c| c.to_string())}));
    }
    let mut cs_by = serde_json::Map::new();
    for k in 0..12i64 {
        cs_by.insert(bz(cs0 + if fwd { k } else { -k }).to_string(), Value::from(CHANGSHENG[k as usize]));
    }
    let dir = if fwd { "순행" } else { "역행" };
    let ch = choices(inp)?;
    let mut out = json!({
        "input": inp,
        "year_gz": inp.year_gz, "year_stem": ys.to_string(), "male": inp.male, "direction": dir,
        "ming": pl.ming.to_string(), "shen": pl.shen.to_string(), "shen_role": role_of(pl.ming, pl.shen),
        "ju": n, "ju_name": ju_name(n),
        "mingzhu": mingzhu(pl.ming), "shenzhu": shenzhu(yb),
        "palaces": palaces, "pos": pos, "birth_hua": bh, "kong": pl.kong,
        "changsheng": {"start": CS_START.iter().find(|(j, _)| *j == n).unwrap().1.to_string(), "direction": dir, "by_palace": cs_by},
        "sihua_variant": "default",
    });
    if !ch.is_empty() {
        out["choices"] = Value::Array(ch);
    }
    Ok(out)
}
