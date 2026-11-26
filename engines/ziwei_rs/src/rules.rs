//! 운 규칙 평가기: rules JSON(semantics의 키)을 해마다 궁 틀에 맞대어 선 규칙을 가린다.
//! 모르는 키·틀 값은 오류로 멈춘다(조용히 무시하지 않는다). 별 이름은 한자 낱말을 그대로 쓰고,
//! 엔진 값(한글 이름)과는 ChartCtx::from_engine에서 옮긴다. 판정·해석은 하지 않는다.
//!
//! 읽기로 정한 것(rules JSON semantics에 낱말 뜻만 있어 구현에서 고정):
//! - at의 scope(기본 同宮; 三方 = 본궁·+4·+6·+8; 對宮 = +6만). scope_any/scope_none/scope_any2는 그 목록만 따로 scope. all·grade·main_grade·no_main·cs_in은 scope를 따른다.
//! - 化祿·化權·化科·化忌 낱말은 그 별이 앉은 궁에 있으면 선다(생년 사화 + 그 틀의 운 사화). natal 조건은 생년 사화만.
//! - 二限: 기본은 rules JSON 풀이대로 大限 궁 = 小限 궁인 해(TwoLimit::SamePalace). 백테스트 명세 3절의 「둘 다 서야」는 TwoLimit::Both.
//! - 限: 大限 궁과 小限 궁 각각 검사(어느 하나). 歲限: 小限·太歲. 三限: 大限·小限·太歲 어느 하나. 三限全: 셋 모두 at_each.
//! - 流年星: 궁 틀 없이 flow_star가 on_star 자리에 앉음(+star_grade), 또는 natal 궁에 flow_on_natal의 유년 별이 듦.
//! - 旬空·截空은 엔진 공망의 正 자리, 天空은 지공.
use crate::common::*;
use serde_json::Value;
use std::collections::{HashMap, HashSet};

const MAIN14_HANJA: [&str; 14] = ["紫微", "天機", "太陽", "武曲", "天同", "廉貞", "天府", "太陰", "貪狼", "巨門", "天相", "天梁", "七殺", "破軍"];
const ROLES: [(&str, &str); 12] = [("명", "命"), ("형제", "兄弟"), ("부처", "夫妻"), ("자녀", "子女"), ("재백", "財帛"), ("질액", "疾厄"),
    ("천이", "遷移"), ("노복", "奴僕"), ("관록", "官祿"), ("전택", "田宅"), ("복덕", "福德"), ("부모", "父母")];
const HUA_TOK: [(&str, &str); 4] = [("록", "化祿"), ("권", "化權"), ("과", "化科"), ("기", "化忌")];

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum TwoLimit {
    SamePalace,
    Both,
}

/// 출생 명반(해와 무관한 값)
#[derive(Debug, Clone)]
pub struct ChartCtx {
    /// 지지(0=子)별 별 낱말
    pub stars: Vec<HashSet<String>>,
    pub grade: HashMap<(String, usize), String>,
    pub cs: Vec<String>,
    pub ming: usize,
    pub shen: usize,
    pub role_branch: HashMap<String, usize>,
    pub birth_hua: Vec<(String, String)>,
    pub birth_stem: char,
    pub male: bool,
}

impl ChartCtx {
    /// 손으로 만든 명반(시험용). stars: (낱말, 지지). 궁 이름은 명궁에서 계산.
    pub fn synthetic(stars: &[(&str, char)], ming: char, shen: char, birth_stem: char) -> ChartCtx {
        let mut st = vec![HashSet::new(); 12];
        for (n, z) in stars {
            st[bi(*z) as usize].insert(n.to_string());
        }
        let mut role_branch = HashMap::new();
        for z in BR.chars() {
            let r = role_of(ming, z);
            role_branch.insert(ROLES.iter().find(|(k, _)| *k == r).unwrap().1.to_string(), bi(z) as usize);
        }
        ChartCtx { stars: st, grade: HashMap::new(), cs: vec!["長生".into(); 12], ming: bi(ming) as usize, shen: bi(shen) as usize, role_branch, birth_hua: vec![], birth_stem, male: true }
    }
    pub fn with_male(mut self, male: bool) -> Self {
        self.male = male;
        self
    }
    pub fn with_grade(mut self, star: &str, z: char, g: &str) -> Self {
        self.grade.insert((star.into(), bi(z) as usize), g.into());
        self
    }
    pub fn with_cs(mut self, z: char, cs: &str) -> Self {
        self.cs[bi(z) as usize] = cs.into();
        self
    }
    pub fn with_birth_hua(mut self, star: &str, hua: &str) -> Self {
        self.birth_hua.push((star.into(), hua.into()));
        self
    }

    /// build_chart 결과(Value)에서. 한글 별 이름을 한자 낱말로 옮긴다.
    pub fn from_engine(ch: &Value) -> Result<ChartCtx, String> {
        let to_han = |k: &str| -> Option<String> {
            if k == "순공" {
                return Some("旬空".into());
            }
            crate::validate::STAR_MAP.iter().find(|(_, e)| *e == k).map(|(h, _)| h.to_string())
        };
        let mut st = vec![HashSet::new(); 12];
        for (k, z) in ch["pos"].as_object().ok_or("pos")? {
            if let (Some(h), Some(zc)) = (to_han(k), z.as_str().and_then(|x| x.chars().next())) {
                st[bi(zc) as usize].insert(h);
            }
        }
        let mut grade = HashMap::new();
        let mut cs = vec![String::new(); 12];
        let mut role_branch = HashMap::new();
        for z in BR.chars() {
            let p = &ch["palaces"][z.to_string()];
            let zi = bi(z) as usize;
            for s in p["stars"].as_array().ok_or("stars")? {
                if let (Some(n), Some(g)) = (s["name"].as_str().and_then(|k| to_han(k)), s["grade"].as_str()) {
                    grade.insert((n, zi), g.to_string());
                }
            }
            cs[zi] = crate::validate::STAGE_MAP.iter().find(|(_, e)| Some(*e) == p["changsheng"].as_str()).map(|(h, _)| h.to_string()).unwrap_or_default();
            if let Some(r) = p["role"].as_str().and_then(|r| ROLES.iter().find(|(k, _)| *k == r)) {
                role_branch.insert(r.1.to_string(), zi);
            }
        }
        let mut birth_hua = vec![];
        for (h, v) in ch["birth_hua"].as_object().ok_or("birth_hua")? {
            let tok = HUA_TOK.iter().find(|(k, _)| k == h).ok_or("화")?.1;
            birth_hua.push((to_han(v["star"].as_str().unwrap_or("")).ok_or("사화 별")?, tok.to_string()));
        }
        let ys = ch["year_stem"].as_str().and_then(|x| x.chars().next()).ok_or("year_stem")?;
        let mc = ch["ming"].as_str().and_then(|x| x.chars().next()).ok_or("ming")?;
        let sc = ch["shen"].as_str().and_then(|x| x.chars().next()).ok_or("shen")?;
        Ok(ChartCtx { stars: st, grade, cs, ming: bi(mc) as usize, shen: bi(sc) as usize, role_branch, birth_hua, birth_stem: ys, male: ch["male"].as_bool().ok_or("male")? })
    }
}

/// 한 해(虛歲)의 틀 궁과 유년 별. 지지는 0=子.
#[derive(Debug, Clone)]
pub struct YearCtx {
    pub age: i64,
    pub daxian: Option<usize>,
    pub xiaoxian: usize,
    pub taisui: usize,
    pub tong: Option<usize>,
    pub liu_lu: usize,
    pub liu_yang: usize,
    pub liu_tuo: usize,
    /// 그 틀의 운 사화: (별 낱말, 化X 낱말)
    pub year_hua: Vec<(String, String)>,
}

impl YearCtx {
    /// timeline 결과의 한 해(Value)에서. hua_key: "taisui_hua"(틀 B) 또는 "dayun_hua"(틀 A).
    pub fn from_timeline(y: &Value, hua_key: &str) -> Result<YearCtx, String> {
        let b = |v: &Value| -> Result<usize, String> { Ok(bi(v["branch"].as_str().and_then(|x| x.chars().next()).ok_or("branch")?) as usize) };
        let to_han = |k: &str| crate::validate::STAR_MAP.iter().find(|(_, e)| *e == k).map(|(h, _)| h.to_string());
        let mut hua = vec![];
        if let Some(a) = y[hua_key].as_array() {
            for h in a {
                let tok = HUA_TOK.iter().find(|(k, _)| Some(*k) == h["hua"].as_str()).ok_or("화")?.1;
                hua.push((to_han(h["star"].as_str().unwrap_or("")).ok_or("운 사화 별")?, tok.to_string()));
            }
        }
        Ok(YearCtx {
            age: y["xusui"].as_i64().ok_or("xusui")?,
            daxian: if y["daxian"].is_null() { None } else { Some(b(&y["daxian"]["palace"])?) },
            xiaoxian: b(&y["xiaoxian"])?,
            taisui: b(&y["taisui"]["palace"])?,
            tong: if y["tongxian"].is_null() { None } else { Some(b(&y["tongxian"]["palace"])?) },
            liu_lu: b(&y["liu_lu"]["palace"])?,
            liu_yang: b(&y["liu_yang"]["palace"])?,
            liu_tuo: b(&y["liu_tuo"]["palace"])?,
            year_hua: hua,
        })
    }
}

pub struct Rules {
    pub rules: Vec<Value>,
    pub groups: HashMap<String, Vec<String>>,
}

const RULE_KEYS: [&str; 25] = ["id", "cite", "frame", "at", "age", "natal", "force", "note", "partial", "also_tonghan", "flow_star", "on_star", "star_grade",
    "flow_on_natal", "year_taisui_on", "taisui_opp_xian", "any_pair_opposed", "xiaoxian_at", "birth_stem_in", "opp", "opp_or_taisui", "at_each", "branch", "sex", "taisui_same_palace"];
const AT_KEYS: [&str; 15] = ["all", "all2", "scope_all", "any", "any2", "none", "grade", "main_grade", "no_main", "cs_in", "branch_in", "scope", "scope_any", "scope_none", "scope_any2"];
const FRAMES: [&str; 10] = ["大限", "小限", "太歲", "限", "二限", "歲限", "三限", "三限全", "流年星", "童限"];

impl Rules {
    pub fn from_json(v: &Value) -> Result<Rules, String> {
        let mut groups = HashMap::new();
        for (k, l) in v["semantics"]["groups"].as_object().ok_or("semantics.groups 없음")? {
            groups.insert(k.clone(), l.as_array().ok_or("group")?.iter().filter_map(|x| x.as_str().map(String::from)).collect());
        }
        let rules = v["rules"].as_array().ok_or("rules 없음")?.clone();
        let r = Rules { rules, groups };
        for ru in &r.rules {
            r.check(ru)?;
        }
        Ok(r)
    }

    /// 모르는 키는 오류.
    pub fn check(&self, r: &Value) -> Result<(), String> {
        let id = r["id"].as_str().unwrap_or("?");
        let o = r.as_object().ok_or("규칙이 객체가 아님")?;
        for k in o.keys() {
            if !RULE_KEYS.contains(&k.as_str()) {
                return Err(format!("{id}: 모르는 키 {k}"));
            }
        }
        let f = r["frame"].as_str().ok_or_else(|| format!("{id}: frame 없음"))?;
        if !FRAMES.contains(&f) {
            return Err(format!("{id}: 모르는 frame {f}"));
        }
        for k in ["at", "xiaoxian_at", "opp", "opp_or_taisui"] {
            if !r[k].is_null() {
                self.check_at(&r[k], id)?;
            }
        }
        if !r["natal"].is_null() {
            for k in r["natal"].as_object().ok_or("natal")?.keys() {
                if !["palace", "palace_any", "palace_union", "at"].contains(&k.as_str()) {
                    return Err(format!("{id}: natal의 모르는 키 {k}"));
                }
            }
            if !r["natal"]["at"].is_null() {
                self.check_at(&r["natal"]["at"], id)?;
            }
        }
        if !r["at_each"].is_null() {
            self.check_each(&r["at_each"], id)?;
        }
        if !r["age"].is_null() {
            for k in r["age"].as_object().ok_or("age")?.keys() {
                if !["le", "ge", "lt", "gt", "in", "or_ge", "or_le"].contains(&k.as_str()) {
                    return Err(format!("{id}: age의 모르는 키 {k}"));
                }
            }
        }
        Ok(())
    }

    fn check_at(&self, at: &Value, id: &str) -> Result<(), String> {
        for k in at.as_object().ok_or_else(|| format!("{id}: at가 객체가 아님"))?.keys() {
            if !AT_KEYS.contains(&k.as_str()) {
                return Err(format!("{id}: at의 모르는 키 {k}"));
            }
        }
        for k in ["scope", "scope_all", "scope_any", "scope_none", "scope_any2"] {
            if let Some(s) = at[k].as_str() {
                if !["同宮", "三方", "對宮", "同宮_或_對宮"].contains(&s) {
                    return Err(format!("{id}: 모르는 scope {s}"));
                }
            }
        }
        for k in ["any", "any2", "none"] {
            for t in at[k].as_array().into_iter().flatten() {
                let t = t.as_str().unwrap_or("");
                if t.starts_with('@') && !self.groups.contains_key(t) {
                    return Err(format!("{id}: 모르는 무리 {t}"));
                }
            }
        }
        for k in ["all", "all2"] {
            if let Some(a) = at[k].as_array() {
                if a.iter().any(|t| t.as_str().map_or(false, |t| t.starts_with('@'))) {
                    return Err(format!("{id}: {k}에는 무리를 쓸 수 없다"));
                }
            }
        }
        Ok(())
    }

    fn check_each(&self, e: &Value, id: &str) -> Result<(), String> {
        let o = e.as_object().ok_or("at_each")?;
        if o.contains_key("or") || o.contains_key("and") {
            for k in o.keys() {
                if k != "or" && k != "and" {
                    return Err(format!("{id}: at_each의 모르는 키 {k}"));
                }
            }
            for k in ["or", "and"] {
                for x in e[k].as_array().into_iter().flatten() {
                    self.check_each(x, id)?;
                }
            }
            Ok(())
        } else {
            self.check_at(e, id)
        }
    }

    fn expand(&self, l: &Value) -> Vec<String> {
        let mut out = vec![];
        for t in l.as_array().into_iter().flatten() {
            let t = t.as_str().unwrap_or("");
            if let Some(g) = self.groups.get(t) {
                out.extend(g.iter().cloned());
            } else {
                out.push(t.to_string());
            }
        }
        out
    }
}

fn scope_palaces(z: usize, s: &str) -> Vec<usize> {
    match s {
        "三方" => vec![z, (z + 4) % 12, (z + 6) % 12, (z + 8) % 12],
        "對宮" => vec![(z + 6) % 12],
        _ => vec![z],
    }
}

struct Cx<'a> {
    ch: &'a ChartCtx,
    y: Option<&'a YearCtx>,
}

impl<'a> Cx<'a> {
    /// 그 궁에 있는 낱말: 별 + 化X(생년·운 사화 별이 앉은 궁) + 유년 별
    fn tokens(&self, z: usize) -> HashSet<String> {
        let mut t = self.ch.stars[z].clone();
        let mut hua: Vec<&(String, String)> = self.ch.birth_hua.iter().collect();
        if let Some(y) = self.y {
            hua.extend(y.year_hua.iter());
            if y.liu_lu == z {
                t.insert("流祿".into());
            }
            if y.liu_yang == z {
                t.insert("流羊".into());
            }
            if y.liu_tuo == z {
                t.insert("流陀".into());
            }
        }
        for (star, h) in hua {
            if self.ch.stars[z].contains(star) {
                t.insert(h.clone());
            }
        }
        t
    }
    fn is_main(n: &str) -> bool {
        MAIN14_HANJA.contains(&n)
    }
}

fn at_ok(rules: &Rules, cx: &Cx, at: &Value, z: usize) -> Result<bool, String> {
    at_ok_in(rules, cx, at, &[z])
}

/// zs: 조건을 보는 궁(보통 하나, natal.palace_union이면 둘 이상). scope는 궁마다 펼쳐 합친다.
fn at_ok_in(rules: &Rules, cx: &Cx, at: &Value, zs: &[usize]) -> Result<bool, String> {
    if at.as_object().map_or(true, |o| o.is_empty()) {
        return Ok(true);
    }
    // 본궁이나 대궁 어느 쪽이든: 같은 조건을 본궁(同宮)과 대궁(同宮)에서 따로 본다
    if at["scope"].as_str() == Some("同宮_或_對宮") {
        let mut plain = at.clone();
        plain["scope"] = Value::from("同宮");
        let opp: Vec<usize> = zs.iter().map(|z| (z + 6) % 12).collect();
        return Ok(at_ok_in(rules, cx, &plain, zs)? || at_ok_in(rules, cx, &plain, &opp)?);
    }
    let sc = at["scope"].as_str().unwrap_or("同宮");
    let pal = |s: &str| -> Vec<usize> {
        let mut v: Vec<usize> = zs.iter().flat_map(|z| scope_palaces(*z, s)).collect();
        v.sort();
        v.dedup();
        v
    };
    let union = |s: &str| -> HashSet<String> { pal(s).into_iter().flat_map(|p| cx.tokens(p)).collect() };
    let base = union(sc);
    if let Some(a) = at["all"].as_array() {
        let u = union(at["scope_all"].as_str().unwrap_or(sc));
        if !a.iter().all(|t| u.contains(t.as_str().unwrap_or(""))) {
            return Ok(false);
        }
    }
    if let Some(a) = at["all2"].as_array() {
        let u = union("同宮");
        if !a.iter().all(|t| u.contains(t.as_str().unwrap_or(""))) {
            return Ok(false);
        }
    }
    let _ = &base;
    for (k, sk) in [("any", "scope_any"), ("any2", "scope_any2")] {
        if !at[k].is_null() {
            let u = union(at[sk].as_str().unwrap_or(sc));
            if !rules.expand(&at[k]).iter().any(|t| u.contains(t)) {
                return Ok(false);
            }
        }
    }
    if !at["none"].is_null() {
        let u = union(at["scope_none"].as_str().unwrap_or(sc));
        if rules.expand(&at["none"]).iter().any(|t| u.contains(t)) {
            return Ok(false);
        }
    }
    let ps = pal(sc);
    if let Some(g) = at["grade"].as_object() {
        for (star, want) in g {
            let ok = ps.iter().any(|p| cx.ch.stars[*p].contains(star) && cx.ch.grade.get(&(star.clone(), *p)).map(|x| x.as_str()) == want.as_str());
            if !ok {
                return Ok(false);
            }
        }
    }
    if let Some(want) = at["main_grade"].as_str() {
        let ok = ps.iter().any(|p| cx.ch.stars[*p].iter().any(|s| Cx::is_main(s) && cx.ch.grade.get(&(s.clone(), *p)).map(|x| x.as_str()) == Some(want)));
        if !ok {
            return Ok(false);
        }
    }
    if at["no_main"].as_bool() == Some(true) && ps.iter().any(|p| cx.ch.stars[*p].iter().any(|s| Cx::is_main(s))) {
        return Ok(false);
    }
    if let Some(l) = at["cs_in"].as_array() {
        if !ps.iter().any(|p| l.iter().any(|x| x.as_str() == Some(cx.ch.cs[*p].as_str()))) {
            return Ok(false);
        }
    }
    if let Some(l) = at["branch_in"].as_array() {
        if !zs.iter().any(|z| {
            let zc = BR.chars().nth(*z).unwrap();
            l.iter().any(|x| x.as_str().and_then(|s| s.chars().next()) == Some(zc))
        }) {
            return Ok(false);
        }
    }
    Ok(true)
}

fn each_ok(rules: &Rules, cx: &Cx, e: &Value, z: usize) -> Result<bool, String> {
    if let Some(a) = e["or"].as_array() {
        for x in a {
            if each_ok(rules, cx, x, z)? {
                return Ok(true);
            }
        }
        return Ok(false);
    }
    if let Some(a) = e["and"].as_array() {
        for x in a {
            if !each_ok(rules, cx, x, z)? {
                return Ok(false);
            }
        }
        return Ok(true);
    }
    at_ok(rules, cx, e, z)
}

fn age_ok(a: &Value, age: i64) -> bool {
    if a.is_null() {
        return true;
    }
    let g = |k: &str| a[k].as_i64();
    let mut ok = true;
    if let Some(v) = g("le") { ok &= age <= v; }
    if let Some(v) = g("ge") { ok &= age >= v; }
    if let Some(v) = g("lt") { ok &= age < v; }
    if let Some(v) = g("gt") { ok &= age > v; }
    if let Some(l) = a["in"].as_array() {
        if l.len() == 2 { ok &= age >= l[0].as_i64().unwrap_or(0) && age <= l[1].as_i64().unwrap_or(-1); }
    }
    // or_ge/or_le: 다른 조건 대신 이 구간이어도 된다
    let mut alt = false;
    if let Some(v) = g("or_ge") { alt |= age >= v; }
    if let Some(v) = g("or_le") { alt |= age <= v; }
    ok || alt
}

/// natal 조건을 만족하는 궁들. palace_union이면 두 궁의 별 합집합에 조건을 걸고, 만족하면 그 궁들 모두를 돌려준다.
fn natal_branches(rules: &Rules, ch: &ChartCtx, n: &Value) -> Result<Vec<usize>, String> {
    let cx = Cx { ch, y: None };
    let find = |nm: &str| -> Result<usize, String> {
        Ok(match nm {
            "命" => ch.ming,
            "身" => ch.shen,
            other => *ch.role_branch.get(other).ok_or_else(|| format!("모르는 natal 궁 {other}"))?,
        })
    };
    if let Some(u) = n["palace_union"].as_array() {
        let zs: Vec<usize> = u.iter().map(|x| find(x.as_str().unwrap_or(""))).collect::<Result<_, _>>()?;
        if zs.is_empty() {
            return Err("palace_union이 비었다".into());
        }
        return Ok(if n["at"].is_null() || at_ok_in(rules, &cx, &n["at"], &zs)? { zs } else { vec![] });
    }
    let names: Vec<&str> = if let Some(p) = n["palace"].as_str() { vec![p] } else { n["palace_any"].as_array().into_iter().flatten().filter_map(|x| x.as_str()).collect() };
    if names.is_empty() {
        return Err("natal에 palace·palace_any·palace_union이 없다".into());
    }
    let mut out = vec![];
    for nm in names {
        let z = find(nm)?;
        if n["at"].is_null() || at_ok(rules, &cx, &n["at"], z)? {
            out.push(z);
        }
    }
    Ok(out)
}

/// 규칙 하나가 그해에 서는지.
pub fn stands(rules: &Rules, r: &Value, ch: &ChartCtx, y: &YearCtx, two: TwoLimit) -> Result<bool, String> {
    rules.check(r)?;
    let cx = Cx { ch, y: Some(y) };
    if !r["sex"].is_null() {
        match r["sex"].as_str() {
            Some("男") => if !ch.male { return Ok(false) },
            Some("女") => if ch.male { return Ok(false) },
            other => return Err(format!("sex는 男/女: {other:?}")),
        }
    }
    if !age_ok(&r["age"], y.age) {
        return Ok(false);
    }
    if let Some(l) = r["birth_stem_in"].as_array() {
        if !l.iter().any(|x| x.as_str().and_then(|s| s.chars().next()) == Some(ch.birth_stem)) {
            return Ok(false);
        }
    }
    let natal = if r["natal"].is_null() { None } else { Some(natal_branches(rules, ch, &r["natal"])?) };
    if let Some(n) = &natal {
        if n.is_empty() {
            return Ok(false);
        }
    }
    if let Some(l) = r["year_taisui_on"].as_array() {
        let t = cx.tokens(y.taisui);
        if !l.iter().any(|x| t.contains(x.as_str().unwrap_or(""))) {
            return Ok(false);
        }
    }
    let opp = |z: usize| (z + 6) % 12;
    if r["taisui_opp_xian"].as_bool() == Some(true) {
        let ok = y.daxian.map_or(false, |d| opp(d) == y.taisui) || opp(y.xiaoxian) == y.taisui;
        if !ok {
            return Ok(false);
        }
    }
    if let Some(l) = r["any_pair_opposed"].as_array() {
        let mut ps = vec![];
        for x in l {
            match x.as_str() {
                Some("大限") => ps.extend(y.daxian),
                Some("小限") => ps.push(y.xiaoxian),
                Some("太歲") => ps.push(y.taisui),
                other => return Err(format!("any_pair_opposed의 모르는 틀 {other:?}")),
            }
        }
        if !ps.iter().any(|a| ps.iter().any(|b| opp(*a) == *b)) {
            return Ok(false);
        }
    }
    if !r["xiaoxian_at"].is_null() && !at_ok(rules, &cx, &r["xiaoxian_at"], y.xiaoxian)? {
        return Ok(false);
    }
    let frame = r["frame"].as_str().unwrap();
    if frame == "流年星" {
        let mut ok = false;
        let flow = |n: &str| -> Result<usize, String> {
            Ok(match n {
                "流羊" => y.liu_yang,
                "流陀" => y.liu_tuo,
                "流祿" => y.liu_lu,
                o => return Err(format!("모르는 유년 별 {o}")),
            })
        };
        let mut any_key = false;
        if let Some(fs) = r["flow_star"].as_str() {
            any_key = true;
            let on = r["on_star"].as_str().ok_or("flow_star에는 on_star가 필요하다")?;
            let fz = flow(fs)?;
            let here = ch.stars[fz].contains(on);
            let grade_ok = r["star_grade"].as_str().map_or(true, |g| ch.grade.get(&(on.to_string(), fz)).map(|x| x.as_str()) == Some(g));
            ok = here && grade_ok;
        }
        if let Some(l) = r["flow_on_natal"].as_array() {
            any_key = true;
            let n = natal.as_ref().ok_or("flow_on_natal에는 natal이 필요하다")?;
            let mut hit = false;
            for x in l {
                hit |= n.contains(&flow(x.as_str().unwrap_or(""))?);
            }
            ok = hit;
        }
        if !any_key {
            return Err("流年星에는 flow_star 또는 flow_on_natal이 필요하다".into());
        }
        return Ok(ok);
    }
    if r["flow_star"].as_str().is_some() || r["flow_on_natal"].is_array() {
        return Err("flow_star·flow_on_natal은 流年星 틀에서만 쓴다".into());
    }
    let per = |z: usize| -> Result<bool, String> {
        if r["taisui_same_palace"].as_bool() == Some(true) && y.taisui != z {
            return Ok(false);
        }
        if !r["at"].is_null() && !at_ok(rules, &cx, &r["at"], z)? {
            return Ok(false);
        }
        if !r["opp"].is_null() && !at_ok(rules, &cx, &r["opp"], opp(z))? {
            return Ok(false);
        }
        if !r["opp_or_taisui"].is_null() && !(at_ok(rules, &cx, &r["opp_or_taisui"], opp(z))? || at_ok(rules, &cx, &r["opp_or_taisui"], y.taisui)?) {
            return Ok(false);
        }
        Ok(true)
    };
    let any_of = |zs: Vec<usize>| -> Result<bool, String> {
        for z in zs {
            if per(z)? {
                return Ok(true);
            }
        }
        Ok(false)
    };
    let mut xian: Vec<usize> = y.daxian.into_iter().collect();
    xian.push(y.xiaoxian);
    if r["also_tonghan"].as_bool() == Some(true) {
        xian.extend(y.tong);
    }
    match frame {
        "大限" => any_of(y.daxian.into_iter().collect()),
        "小限" => any_of(vec![y.xiaoxian]),
        "太歲" => any_of(vec![y.taisui]),
        "限" => any_of(xian),
        "歲限" => any_of(vec![y.xiaoxian, y.taisui]),
        "三限" => any_of(y.daxian.into_iter().chain([y.xiaoxian, y.taisui]).collect()),
        "童限" => any_of(y.tong.into_iter().collect()),
        "二限" => match (y.daxian, two) {
            (Some(d), TwoLimit::SamePalace) => if d == y.xiaoxian { per(d) } else { Ok(false) },
            (Some(d), TwoLimit::Both) => Ok(per(d)? && per(y.xiaoxian)?),
            (None, _) => Ok(false),
        },
        "三限全" => {
            let Some(d) = y.daxian else { return Ok(false) };
            if r["at_each"].is_null() {
                return Err("三限全에는 at_each가 필요하다".into());
            }
            for z in [d, y.xiaoxian, y.taisui] {
                if !each_ok(rules, &cx, &r["at_each"], z)? {
                    return Ok(false);
                }
            }
            Ok(true)
        }
        other => Err(format!("모르는 frame {other}")),
    }
}

/// 규칙 ID에서 갈래 표시(끝의 소문자)를 뗀 기본 ID. 갈래 규칙은 갈래 중 하나만 센다.
pub fn base_id(id: &str) -> &str {
    id.trim_end_matches(|c: char| c.is_ascii_lowercase())
}

/// 그해에 선 규칙 ID 목록(갈래는 기본 ID로 한 번). include_partial=false면 partial 규칙을 뺀다.
pub fn standing(rules: &Rules, ch: &ChartCtx, y: &YearCtx, two: TwoLimit, include_partial: bool) -> Result<Vec<String>, String> {
    let mut out: Vec<String> = vec![];
    for r in &rules.rules {
        if !include_partial && r["partial"].as_bool() == Some(true) {
            continue;
        }
        if stands(rules, r, ch, y, two)? {
            let b = base_id(r["id"].as_str().unwrap_or("?")).to_string();
            if !out.contains(&b) {
                out.push(b);
            }
        }
    }
    Ok(out)
}
