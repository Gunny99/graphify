//! 백테스트 틀(백테스트_명세.md): 사망 해 순위 백분위, 사망 대한 1위 비율, 나이만 모형, 부호 검정.
//! 규칙이 동결되기 전에는 명례로 돌리지 않는다(이 파일은 틀만 만든다).
use crate::chart::{build_chart, Input};
use crate::rules::{standing, ChartCtx, Rules, TwoLimit, YearCtx};
use crate::timeline::{build_timeline, DaxianStart, TimelineOpts};
use serde_json::Value;
use std::collections::BTreeMap;
use std::fmt::Write as _;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Frame {
    A,
    B,
}

/// 한 사례·한 설정의 해마다 점수(1~100)와 大限 번호(없으면 0), 선 규칙 ID
pub struct YearScores {
    pub score: Vec<usize>,
    pub daxian: Vec<usize>,
    pub ids: Vec<Vec<String>>,
}

/// 평균 순위 기준 백분위(%): 점수 내림차순에서 target의 순위(동점은 평균), (순위−0.5)/N×100. 낮을수록 좋다.
pub fn percentile(score: &[f64], target_idx: usize) -> (f64, f64) {
    let t = score[target_idx];
    let greater = score.iter().filter(|x| **x > t).count() as f64;
    let equal = score.iter().filter(|x| **x == t).count() as f64;
    let rank = greater + (equal + 1.0) / 2.0;
    (rank, (rank - 0.5) / score.len() as f64 * 100.0)
}

/// 대한(번호>0)별 점수 합에서 target 대한이 1위일 몫(동점이면 나눔). 대한이 없는 해(0)면 None. 반환 (몫, 대한 수)
pub fn daxian_top(score: &[f64], daxian: &[usize], target_idx: usize) -> Option<(f64, usize)> {
    let d = daxian[target_idx];
    if d == 0 {
        return None;
    }
    let mut sums: BTreeMap<usize, f64> = BTreeMap::new();
    for (s, x) in score.iter().zip(daxian) {
        if *x > 0 {
            *sums.entry(*x).or_default() += *s;
        }
    }
    let mine = sums[&d];
    let max = sums.values().cloned().fold(f64::MIN, f64::max);
    if mine < max {
        return Some((0.0, sums.len()));
    }
    let ties = sums.values().filter(|v| **v == max).count() as f64;
    Some((1.0 / ties, sums.len()))
}

/// 양측 정확 이항 검정(p=0.5)
pub fn sign_test_p(wins: usize, losses: usize) -> f64 {
    let n = wins + losses;
    if n == 0 {
        return 1.0;
    }
    let k = wins.min(losses);
    let mut ln_fact = vec![0.0f64; n + 1];
    for i in 1..=n {
        ln_fact[i] = ln_fact[i - 1] + (i as f64).ln();
    }
    let pmf = |i: usize| (ln_fact[n] - ln_fact[i] - ln_fact[n - i] - n as f64 * std::f64::consts::LN_2).exp();
    let tail: f64 = (0..=k).map(pmf).sum();
    (2.0 * tail).min(1.0)
}

pub fn median(v: &mut Vec<f64>) -> f64 {
    v.sort_by(|a, b| a.partial_cmp(b).unwrap());
    if v.is_empty() {
        return f64::NAN;
    }
    let n = v.len();
    if n % 2 == 1 { v[n / 2] } else { (v[n / 2 - 1] + v[n / 2]) / 2.0 }
}

/// 해마다 점수. frame A: 大限 manage·기본 사화·火鈴, 대운 시작 나이 dayun_start. frame B: variant quanshu 전부.
pub fn year_scores(inp: &Input, rules: &Rules, frame: Frame, dayun_start: i64, include_partial: bool, two: TwoLimit) -> Result<YearScores, String> {
    let mut inp = inp.clone();
    let (ds, hua_key, start) = match frame {
        Frame::A => (DaxianStart::Manage, "dayun_hua", Some(dayun_start)),
        Frame::B => {
            inp.variant = Some("quanshu".into());
            (DaxianStart::Quanshu, "taisui_hua", None)
        }
    };
    let ch = ChartCtx::from_engine(&build_chart(&inp)?)?;
    let tl = build_timeline(&inp, TimelineOpts { daxian_start: ds, dayun_start: start })?;
    let mut out = YearScores { score: vec![], daxian: vec![], ids: vec![] };
    for y in tl["years"].as_array().ok_or("years")? {
        let yc = YearCtx::from_timeline(y, hua_key)?;
        let ids = standing(rules, &ch, &yc, two, include_partial)?;
        out.score.push(ids.len());
        out.daxian.push(y["daxian"]["index"].as_u64().unwrap_or(0) as usize);
        out.ids.push(ids);
    }
    Ok(out)
}

struct Case {
    id: String,
    age: usize,
    inp: Input,
    typo: bool,
    note: String,
}

fn load_cases(path: &str) -> Result<Vec<Case>, String> {
    let raw = std::fs::read_to_string(path).map_err(|e| e.to_string())?;
    let cases: Vec<Value> = serde_json::from_str(&raw).map_err(|e| e.to_string())?;
    let mut out = vec![];
    for c in &cases {
        let b = &c["birth"];
        let Some(age) = c["death"]["age"].as_i64().filter(|a| (1..=100).contains(a)) else { continue };
        let (Some(m), Some(d), Some(hb)) = (b["month"].as_i64(), b["day"].as_i64(), b["hour_branch"].as_str()) else { continue };
        let male = match b["sex"].as_str() {
            Some("男") => true,
            Some("女") => false,
            _ => continue,
        };
        let (ygz, typo, note) = match b["year_gz"].as_str() {
            Some(g) => (g.to_string(), false, String::new()),
            None => match crate::validate::guess_year(c) {
                Some((g, n)) => (g, true, n),
                None => continue,
            },
        };
        out.push(Case { id: c["id"].as_str().unwrap_or("?").into(), age: age as usize, inp: Input { year_gz: ygz, month: m, day: d, hour: hb.into(), male, leap: b["leap"].as_bool().unwrap_or(false), leap_rule: None, variant: None }, typo, note });
    }
    Ok(out)
}

/// 사례 하나의 지표 재료
struct Res {
    pct: f64,        // 설정 평균 백분위
    pct_each: Vec<f64>,
    top: Option<f64>, // 설정 평균 대한 1위 몫
    rank: f64,
    ids: Vec<String>,
}

fn run_set(cases: &[&Case], rules: &Rules, frame: Frame, partial: bool, two: TwoLimit) -> Result<Vec<Res>, String> {
    let starts: Vec<i64> = if frame == Frame::A { (1..=10).collect() } else { vec![0] };
    let mut out = vec![];
    for c in cases {
        let (mut pcts, mut tops, mut ids, mut rk) = (vec![], vec![], vec![], vec![]);
        for s in &starts {
            let ys = year_scores(&c.inp, rules, frame, *s, partial, two)?;
            let sc: Vec<f64> = ys.score.iter().map(|x| *x as f64).collect();
            let (r, p) = percentile(&sc, c.age - 1);
            pcts.push(p);
            rk.push(r);
            if let Some((t, gg)) = daxian_top(&sc, &ys.daxian, c.age - 1) {
                tops.push(t);
                let _ = gg;
            }
            if frame == Frame::A {
                ids.push(format!("s{}:{}", s, ys.ids[c.age - 1].join(",")));
            } else {
                ids.push(ys.ids[c.age - 1].join(","));
            }
        }
        let mean = |v: &Vec<f64>| v.iter().sum::<f64>() / v.len() as f64;
        out.push(Res { pct: mean(&pcts), pct_each: pcts, top: if tops.is_empty() { None } else { Some(mean(&tops)) }, rank: mean(&rk), ids: ids.join(" | ") .split(" | ").map(String::from).collect() });
    }
    Ok(out)
}

/// 나이만 모형: 다른 사례(한 사례 빼고)의 사망 나이 분포로 줄 세운 백분위·대한 1위. daxian: 사례 자기 틀의 大限 번호(해마다)
fn age_only(cases: &[&Case], daxians: &[Vec<usize>]) -> Vec<(f64, Option<f64>)> {
    cases.iter().enumerate().map(|(i, c)| {
        let mut cnt = vec![0.0f64; 100];
        for (j, o) in cases.iter().enumerate() {
            if j != i {
                cnt[o.age - 1] += 1.0;
            }
        }
        let (_, p) = percentile(&cnt, c.age - 1);
        (p, daxian_top(&cnt, &daxians[i], c.age - 1).map(|x| x.0))
    }).collect()
}

fn daxian_index(c: &Case, frame: Frame) -> Result<Vec<usize>, String> {
    let mut inp = c.inp.clone();
    let ds = match frame {
        Frame::A => DaxianStart::Manage,
        Frame::B => {
            inp.variant = Some("quanshu".into());
            DaxianStart::Quanshu
        }
    };
    let tl = build_timeline(&inp, TimelineOpts { daxian_start: ds, dayun_start: None })?;
    Ok(tl["years"].as_array().unwrap().iter().map(|y| y["daxian"]["index"].as_u64().unwrap_or(0) as usize).collect())
}

pub fn run(cases_path: &str, rules_path: &str, out_dir: &str, frame: Frame, two: TwoLimit) -> Result<String, String> {
    let rules_json: Value = serde_json::from_str(&std::fs::read_to_string(rules_path).map_err(|e| e.to_string())?).map_err(|e| e.to_string())?;
    let rules = Rules::from_json(&rules_json)?;
    let cases = load_cases(cases_path)?;
    std::fs::create_dir_all(out_dir).map_err(|e| e.to_string())?;
    let fname = if frame == Frame::A { "A" } else { "B" };
    let mut md = format!("# 백테스트 결과 (틀 {fname})\n\n");
    let _ = writeln!(md, "- 규칙 {}개(갈래는 기본 ID로 한 번). 二限 규약: {:?}. 틀 A는 大限 manage·기본 사화·火鈴, 대운 시작 나이 1~10 각각의 평균. 틀 B는 variant quanshu.", rules.rules.len(), two);
    md.push_str("- 백분위는 낮을수록 사망 해가 위에 있다(좋음). 무작위 기대 50%, 대한 1위 무작위는 1/대한 수. 나이만 모형은 한 사례씩 빼고. 보조(吉凶) 점수는 이 규칙 집합이 死 범주뿐이라 없다.\n\n");
    let mut tsv = String::from("집합\t사례\t사망나이\t순위(완전)\t순위(부분포함)\t사망 해에 선 규칙 ID(완전)\t사망 해에 선 규칙 ID(부분포함)\n");
    for (label, typo) in [("primary", false), ("typo_guess", true)] {
        let cs: Vec<&Case> = cases.iter().filter(|c| c.typo == typo).collect();
        if cs.is_empty() {
            continue;
        }
        let comp = run_set(&cs, &rules, frame, false, two)?;
        let part = run_set(&cs, &rules, frame, true, two)?;
        let dx: Vec<Vec<usize>> = cs.iter().map(|c| daxian_index(c, frame)).collect::<Result<_, _>>()?;
        let base = age_only(&cs, &dx);
        let _ = writeln!(md, "## {label} ({}건)\n", cs.len());
        md.push_str("| 규칙 집합 | 사례 | 백분위 평균 | 중앙값 | 대한 1위 비율(사례 수) | 나이만 백분위 평균 | 나이만 대한 1위 | 모형이 나음/나쁨/같음 | 부호 검정 p |\n|---|---|---|---|---|---|---|---|---|\n");
        for (name, res) in [("완전 규칙만", &comp), ("부분 규칙 포함", &part)] {
            let mut p: Vec<f64> = res.iter().map(|r| r.pct).collect();
            let mean = p.iter().sum::<f64>() / p.len() as f64;
            let med = median(&mut p);
            let tops: Vec<f64> = res.iter().filter_map(|r| r.top).collect();
            let top = tops.iter().sum::<f64>() / tops.len().max(1) as f64;
            let bp: f64 = base.iter().map(|b| b.0).sum::<f64>() / base.len() as f64;
            let bt: Vec<f64> = base.iter().filter_map(|b| b.1).collect();
            let btm = bt.iter().sum::<f64>() / bt.len().max(1) as f64;
            let (mut w, mut l, mut t) = (0, 0, 0);
            for (r, b) in res.iter().zip(&base) {
                if r.pct < b.0 - 1e-12 { w += 1 } else if r.pct > b.0 + 1e-12 { l += 1 } else { t += 1 }
            }
            let _ = writeln!(md, "| {name} | {} | {mean:.1}% | {med:.1}% | {:.1}% ({}) | {bp:.1}% | {:.1}% | {w}/{l}/{t} | {:.4} |", res.len(), top * 100.0, tops.len(), btm * 100.0, sign_test_p(w, l));
        }
        if frame == Frame::A {
            md.push_str("\n대운 시작 나이별 백분위 평균(완전 규칙만): ");
            let n = comp.first().map_or(0, |r| r.pct_each.len());
            for s in 0..n {
                let m = comp.iter().map(|r| r.pct_each[s]).sum::<f64>() / comp.len() as f64;
                let _ = write!(md, "{}세 {m:.1}%{}", s + 1, if s + 1 < n { ", " } else { "\n" });
            }
        }
        md.push('\n');
        for (i, c) in cs.iter().enumerate() {
            let _ = writeln!(tsv, "{label}\t{}\t{}\t{:.1}\t{:.1}\t{}\t{}", c.id, c.age, comp[i].rank, part[i].rank, comp[i].ids.join(" | "), part[i].ids.join(" | "));
            let _ = &c.note;
        }
    }
    std::fs::write(format!("{out_dir}/결과_{fname}.md"), md).map_err(|e| e.to_string())?;
    std::fs::write(format!("{out_dir}/사례별_{fname}.tsv"), tsv).map_err(|e| e.to_string())?;
    Ok(format!("{} 사례 → {out_dir}", cases.len()))
}
