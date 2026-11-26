//! 규칙 평가기: 키마다 합성 명반에서 서는 경우·안 서는 경우.
use serde_json::{json, Value};
use ziwei_rs::backtest::{daxian_top, percentile, sign_test_p};
use ziwei_rs::rules::{base_id, standing, stands, ChartCtx, Rules, TwoLimit, YearCtx};

fn groups() -> Value {
    json!({"@凶星": ["擎羊", "陀羅", "火星", "鈴星", "地劫", "天空"], "@吉星": ["左輔", "右弼", "文昌", "文曲", "天魁", "天鉞", "祿存", "化祿", "化權", "化科"],
           "@祿": ["祿存", "化祿"], "@空亡": ["旬空", "截空"], "@流殺": ["流羊", "流陀"]})
}
fn rules_of(rs: Vec<Value>) -> Rules {
    Rules::from_json(&json!({"semantics": {"groups": groups()}, "rules": rs})).unwrap()
}
/// 명궁 寅, 신궁 子, 생년 천간 甲, 남
fn ch(stars: &[(&str, char)]) -> ChartCtx {
    ChartCtx::synthetic(stars, '寅', '子', '甲')
}
/// 大限 午, 小限 辰, 太歲 戌, 童限 없음, 流祿 丑(流羊 寅, 流陀 子)
fn yr() -> YearCtx {
    YearCtx { age: 30, daxian: Some(6), xiaoxian: 4, taisui: 10, tong: None, liu_lu: 1, liu_yang: 2, liu_tuo: 0, year_hua: vec![] }
}
fn ok(rule: Value, c: &ChartCtx, y: &YearCtx) -> bool {
    let mut r = rule;
    r["id"] = "T".into();
    let rs = rules_of(vec![r.clone()]);
    stands(&rs, &r, c, y, TwoLimit::SamePalace).unwrap()
}
fn br(c: char) -> usize {
    "子丑寅卯辰巳午未申酉戌亥".chars().position(|x| x == c).unwrap()
}

#[test]
fn frames() {
    let c = ch(&[("擎羊", '午'), ("陀羅", '辰'), ("火星", '戌'), ("鈴星", '卯')]);
    let y = yr();
    let at = json!({"all": ["擎羊"]});
    assert!(ok(json!({"frame": "大限", "at": at}), &c, &y));
    assert!(!ok(json!({"frame": "小限", "at": at}), &c, &y));
    assert!(ok(json!({"frame": "小限", "at": {"all": ["陀羅"]}}), &c, &y));
    assert!(ok(json!({"frame": "太歲", "at": {"all": ["火星"]}}), &c, &y));
    assert!(!ok(json!({"frame": "太歲", "at": at}), &c, &y));
    // 限 = 大限 또는 小限
    assert!(ok(json!({"frame": "限", "at": at}), &c, &y));
    assert!(ok(json!({"frame": "限", "at": {"all": ["陀羅"]}}), &c, &y));
    assert!(!ok(json!({"frame": "限", "at": {"all": ["火星"]}}), &c, &y));
    // 歲限 = 小限 또는 太歲
    assert!(ok(json!({"frame": "歲限", "at": {"all": ["火星"]}}), &c, &y));
    assert!(!ok(json!({"frame": "歲限", "at": at}), &c, &y));
    // 三限 = 셋 가운데 하나
    assert!(ok(json!({"frame": "三限", "at": at}), &c, &y));
    assert!(!ok(json!({"frame": "三限", "at": {"all": ["鈴星"]}}), &c, &y));
    // 三限全: 셋 모두
    let each = json!({"or": [{"main_grade": "陷"}, {"any": ["@凶星"]}]});
    assert!(ok(json!({"frame": "三限全", "at_each": each}), &c, &y));
    let y2 = YearCtx { taisui: 0, ..yr() };
    assert!(!ok(json!({"frame": "三限全", "at_each": each}), &c, &y2));
    // 大限 없는 해(局數 이전): 大限·二限·三限全은 서지 않고 小限은 선다
    let y3 = YearCtx { daxian: None, ..yr() };
    assert!(!ok(json!({"frame": "大限", "at": at}), &c, &y3));
    assert!(ok(json!({"frame": "限", "at": {"all": ["陀羅"]}}), &c, &y3));
    // 童限
    assert!(!ok(json!({"frame": "童限", "at": at}), &c, &y));
    let y4 = YearCtx { tong: Some(6), ..yr() };
    assert!(ok(json!({"frame": "童限", "at": at}), &c, &y4));
}

#[test]
fn two_limit_modes_and_also_tonghan() {
    let c = ch(&[("擎羊", '午'), ("陀羅", '辰')]);
    let same = YearCtx { daxian: Some(6), xiaoxian: 6, ..yr() };
    let rule = json!({"id": "T", "frame": "二限", "at": {"all": ["擎羊"]}});
    let rs = rules_of(vec![rule.clone()]);
    assert!(stands(&rs, &rule, &c, &same, TwoLimit::SamePalace).unwrap());
    assert!(!stands(&rs, &rule, &c, &yr(), TwoLimit::SamePalace).unwrap()); // 午·辰 다른 궁
    // Both: 두 궁 모두에서 조건이 서야
    let rule2 = json!({"id": "T", "frame": "二限", "at": {"any": ["擎羊", "陀羅"]}});
    let rs2 = rules_of(vec![rule2.clone()]);
    assert!(stands(&rs2, &rule2, &c, &yr(), TwoLimit::Both).unwrap());
    assert!(!stands(&rs, &rule, &c, &yr(), TwoLimit::Both).unwrap());
    // also_tonghan: 限 + 童限 궁
    let y = YearCtx { age: 6, tong: Some(0), ..yr() };
    let c2 = ch(&[("擎羊", '子')]);
    assert!(!ok(json!({"frame": "限", "at": {"all": ["擎羊"]}}), &c2, &y));
    assert!(ok(json!({"frame": "限", "also_tonghan": true, "at": {"all": ["擎羊"]}}), &c2, &y));
}

#[test]
fn at_keys() {
    // 午: 擎羊 天機 巨門, 子(대궁): 火星, 三方 寅·戌: 文昌·鈴星
    let c = ch(&[("擎羊", '午'), ("天機", '午'), ("巨門", '午'), ("火星", '子'), ("文昌", '寅'), ("鈴星", '戌')])
        .with_grade("天機", '午', "陷").with_grade("擎羊", '午', "廟").with_cs('午', "死");
    let y = yr();
    let f = |at: Value| ok(json!({"frame": "大限", "at": at}), &c, &y);
    // all / any / any2 / none
    assert!(f(json!({"all": ["擎羊", "天機"]})) && !f(json!({"all": ["擎羊", "文昌"]})));
    assert!(f(json!({"any": ["文昌", "擎羊"]})) && !f(json!({"any": ["文昌", "火星"]})));
    assert!(f(json!({"any": ["擎羊"], "any2": ["巨門"]})) && !f(json!({"any": ["擎羊"], "any2": ["火星"]})));
    assert!(f(json!({"none": ["@吉星"]})) && !f(json!({"none": ["擎羊"]})));
    // 무리
    assert!(f(json!({"any": ["@凶星"]})) && !f(json!({"any": ["@吉星"]})));
    // grade / main_grade / no_main
    assert!(f(json!({"grade": {"天機": "陷"}})) && !f(json!({"grade": {"天機": "旺"}})) && !f(json!({"grade": {"文昌": "陷"}})));
    assert!(f(json!({"main_grade": "陷"})) && !f(json!({"main_grade": "旺"})));
    assert!(!f(json!({"no_main": true})));
    assert!(ok(json!({"frame": "小限", "at": {"no_main": true}}), &c, &y)); // 辰: 주성 없음
    // cs_in / branch_in
    assert!(f(json!({"cs_in": ["死", "絕"]})) && !f(json!({"cs_in": ["長生"]})));
    assert!(f(json!({"branch_in": ["午", "丑"]})) && !f(json!({"branch_in": ["辰", "戌"]})));
    // scope 三方 / 對宮
    assert!(f(json!({"scope": "三方", "all": ["擎羊", "文昌", "鈴星"]})));
    assert!(!f(json!({"scope": "三方", "all": ["擎羊", "火星2"]})));
    assert!(f(json!({"scope": "對宮", "all": ["火星"]})) && !f(json!({"scope": "對宮", "all": ["擎羊"]})));
    // scope_any / scope_none / scope_any2 / scope_all / all2
    assert!(f(json!({"all": ["擎羊"], "scope_any": "三方", "any": ["文昌"]})) && !f(json!({"all": ["擎羊"], "any": ["文昌"]})));
    assert!(f(json!({"scope_none": "三方", "none": ["左輔"]})) && !f(json!({"scope_none": "三方", "none": ["文昌"]})));
    assert!(f(json!({"any": ["擎羊"], "scope_any2": "三方", "any2": ["鈴星"]})) && !f(json!({"any": ["擎羊"], "any2": ["鈴星"]})));
    assert!(f(json!({"scope_all": "三方", "all": ["文昌"], "all2": ["巨門"]})) && !f(json!({"scope_all": "三方", "all": ["文昌"], "all2": ["文昌"]})));
    // 同宮_或_對宮: 본궁이나 대궁
    assert!(f(json!({"scope": "同宮_或_對宮", "all": ["火星"]})) && f(json!({"scope": "同宮_或_對宮", "all": ["擎羊"]})) && !f(json!({"scope": "同宮_或_對宮", "all": ["文昌"]})));
}

#[test]
fn opp_family_and_taisui_keys() {
    // 大限 午: 文昌, 대궁 子: 火星, 太歲 戌: 擎羊
    let c = ch(&[("文昌", '午'), ("火星", '子'), ("擎羊", '戌')]);
    let y = yr();
    assert!(ok(json!({"frame": "大限", "at": {"all": ["文昌"]}, "opp": {"any": ["火星", "化忌"]}}), &c, &y));
    assert!(!ok(json!({"frame": "大限", "at": {"all": ["文昌"]}, "opp": {"any": ["陀羅"]}}), &c, &y));
    // opp_or_taisui: 대궁 또는 太歲 궁
    assert!(ok(json!({"frame": "大限", "at": {"all": ["文昌"]}, "opp_or_taisui": {"any": ["擎羊"]}}), &c, &y));
    assert!(ok(json!({"frame": "大限", "at": {"all": ["文昌"]}, "opp_or_taisui": {"any": ["火星"]}}), &c, &y));
    assert!(!ok(json!({"frame": "大限", "at": {"all": ["文昌"]}, "opp_or_taisui": {"any": ["陀羅"]}}), &c, &y));
    // year_taisui_on: 太歲 궁에 그 별
    assert!(ok(json!({"frame": "大限", "year_taisui_on": ["擎羊"], "at": {"all": ["文昌"]}}), &c, &y));
    assert!(!ok(json!({"frame": "大限", "year_taisui_on": ["天傷"], "at": {"all": ["文昌"]}}), &c, &y));
    // taisui_opp_xian: 太歲가 大限 또는 小限의 대궁
    let y2 = YearCtx { taisui: 0, ..yr() }; // 子 = 午의 대궁
    let c2 = ch(&[("火星", '子')]);
    assert!(ok(json!({"frame": "太歲", "taisui_opp_xian": true, "at": {"any": ["火星"]}}), &c2, &y2));
    assert!(!ok(json!({"frame": "太歲", "taisui_opp_xian": true, "at": {"any": ["火星"]}}), &c2, &YearCtx { taisui: 0, daxian: Some(0), xiaoxian: 4, ..yr() }));
    // taisui_same_palace: 太歲가 그 틀 궁과 같은 궁
    let c3 = ch(&[("天馬", '午'), ("地劫", '午')]);
    let y3 = YearCtx { taisui: 6, ..yr() };
    assert!(ok(json!({"frame": "限", "at": {"all": ["天馬"], "any": ["地劫"]}, "taisui_same_palace": true}), &c3, &y3));
    assert!(!ok(json!({"frame": "限", "at": {"all": ["天馬"], "any": ["地劫"]}, "taisui_same_palace": true}), &c3, &yr()));
    // any_pair_opposed: 大限·小限·太歲 가운데 두 궁이 대궁
    let c4 = ch(&[("火星", '午')]);
    let rule = json!({"frame": "限", "any_pair_opposed": ["大限", "小限", "太歲"], "at": {"any": ["@凶星"]}});
    assert!(ok(rule.clone(), &c4, &yr())); // 午·辰·戌: 辰·戌이 대궁, 大限 午에 火星
    assert!(ok(rule.clone(), &c4, &YearCtx { taisui: 0, ..yr() })); // 午-子 대궁
    assert!(!ok(rule.clone(), &c4, &YearCtx { taisui: 1, ..yr() })); // 午·辰·丑: 대궁 쌍 없음
    assert!(!ok(rule.clone(), &ch(&[("火星", '寅')]), &yr())); // 대궁 쌍은 있으나 限 궁에 凶星 없음
    // xiaoxian_at
    let c5 = ch(&[("擎羊", '午'), ("火星", '辰')]);
    assert!(ok(json!({"frame": "大限", "at": {"all": ["擎羊"]}, "xiaoxian_at": {"any": ["@凶星"]}}), &c5, &yr()));
    assert!(!ok(json!({"frame": "大限", "at": {"all": ["擎羊"]}, "xiaoxian_at": {"any": ["@吉星"]}}), &c5, &yr()));
}

#[test]
fn natal_and_flow_keys() {
    // 명궁 寅: 七殺, 신궁 子: 擎羊, 官祿 午: 巨門, 命 대궁 申
    let c = ch(&[("七殺", '寅'), ("擎羊", '子'), ("巨門", '午')]);
    let y = YearCtx { liu_yang: 2, ..yr() }; // 流羊 寅
    let flow = json!({"frame": "流年星", "natal": {"palace": "命", "at": {"all": ["七殺"]}}, "flow_on_natal": ["流羊", "流陀"]});
    assert!(ok(flow.clone(), &c, &y));
    assert!(!ok(flow.clone(), &c, &YearCtx { liu_yang: 3, liu_tuo: 5, ..yr() }));
    assert!(ok(json!({"frame": "流年星", "natal": {"palace_any": ["命", "身"], "at": {"all": ["擎羊"]}}, "flow_on_natal": ["流陀"]}), &c, &yr())); // 流陀 子 = 身
    assert!(!ok(json!({"frame": "流年星", "natal": {"palace": "命", "at": {"all": ["擎羊"]}}, "flow_on_natal": ["流羊"]}), &c, &y));
    assert!(ok(json!({"frame": "限", "natal": {"palace": "官祿", "at": {"all": ["巨門"]}}, "at": {"none": ["@吉星"]}}), &c, &yr()));
    assert!(!ok(json!({"frame": "限", "natal": {"palace": "財帛", "at": {"all": ["巨門"]}}, "at": {"none": ["@吉星"]}}), &c, &yr()));
    // palace_union: 命·身 두 궁의 별 합집합
    let u = json!({"frame": "二限", "natal": {"palace_union": ["命", "身"], "at": {"all": ["七殺", "擎羊"]}}, "at": {}});
    let same = YearCtx { xiaoxian: 6, ..yr() };
    let rs = rules_of(vec![u.clone()]);
    assert!(stands(&rs, &u, &c, &same, TwoLimit::SamePalace).unwrap());
    let u2 = json!({"frame": "二限", "natal": {"palace_union": ["命", "官祿"], "at": {"all": ["七殺", "擎羊"]}}, "at": {}});
    assert!(!stands(&rs, &u2, &c, &same, TwoLimit::SamePalace).unwrap());
    // flow_star·on_star·star_grade: 流羊이 七殺 자리에 앉고 七殺이 陷
    let c2 = ch(&[("七殺", '寅')]).with_grade("七殺", '寅', "陷");
    let q02 = json!({"frame": "流年星", "flow_star": "流羊", "on_star": "七殺", "star_grade": "陷"});
    assert!(ok(q02.clone(), &c2, &yr())); // 流羊 寅
    assert!(!ok(q02.clone(), &c2, &YearCtx { liu_yang: 5, ..yr() }));
    assert!(!ok(q02, &ch(&[("七殺", '寅')]).with_grade("七殺", '寅', "旺"), &yr()));
}

#[test]
fn hua_age_stem_sex() {
    let c = ch(&[("巨門", '午')]).with_birth_hua("巨門", "化忌");
    // 생년 사화: 化忌는 그 별이 앉은 궁에 있다
    assert!(ok(json!({"frame": "大限", "at": {"all": ["化忌"]}}), &c, &yr()));
    // 그 틀의 운 사화
    let c2 = ch(&[("武曲", '午')]);
    let y = YearCtx { year_hua: vec![("武曲".into(), "化忌".into())], ..yr() };
    assert!(ok(json!({"frame": "大限", "at": {"all": ["化忌"]}}), &c2, &y));
    assert!(!ok(json!({"frame": "大限", "at": {"all": ["化忌"]}}), &c2, &yr()));
    // 流羊·流陀 낱말(그해 太歲 기준)
    assert!(ok(json!({"frame": "歲限", "at": {"all": ["流羊"]}}), &c2, &YearCtx { liu_yang: 10, ..yr() }));
    assert!(ok(json!({"frame": "大限", "at": {"any": ["@流殺"]}}), &c2, &YearCtx { liu_tuo: 6, ..yr() }));
    // 旬空·截空 낱말
    let c3 = ch(&[("旬空", '午')]);
    assert!(ok(json!({"frame": "大限", "at": {"any": ["@空亡"]}}), &c3, &yr()));
    // age: le/or_ge, in
    let rule = json!({"frame": "限", "at": {"none": ["@吉星"]}, "age": {"le": 12, "or_ge": 60}});
    assert!(!ok(rule.clone(), &c2, &yr()));
    assert!(ok(rule.clone(), &c2, &YearCtx { age: 10, ..yr() }) && ok(rule.clone(), &c2, &YearCtx { age: 61, ..yr() }));
    let r2 = json!({"frame": "限", "at": {}, "age": {"in": [5, 7]}});
    assert!(ok(r2.clone(), &c2, &YearCtx { age: 5, ..yr() }) && ok(r2.clone(), &c2, &YearCtx { age: 7, ..yr() }) && !ok(r2, &c2, &YearCtx { age: 8, ..yr() }));
    // birth_stem_in
    let b = json!({"frame": "限", "at": {}, "birth_stem_in": ["辛", "壬", "己"]});
    assert!(!ok(b.clone(), &c2, &yr())); // 甲
    assert!(ok(b, &ChartCtx::synthetic(&[], '寅', '子', '壬'), &yr()));
    // sex
    let f = json!({"frame": "限", "at": {}, "sex": "女"});
    assert!(!ok(f.clone(), &c2, &yr()));
    assert!(ok(f, &c2.clone().with_male(false), &yr()));
}

#[test]
fn at_each_and_or() {
    let c = ch(&[("擎羊", '午'), ("擎羊", '辰'), ("擎羊", '戌')]);
    let e = json!({"and": [{"any": ["擎羊"]}, {"none": ["@吉星"]}]});
    assert!(ok(json!({"frame": "三限全", "at_each": e}), &c, &yr()));
    let e2 = json!({"and": [{"any": ["擎羊"]}, {"any": ["文昌"]}]});
    assert!(!ok(json!({"frame": "三限全", "at_each": e2}), &c, &yr()));
}

#[test]
fn unknown_keys_stop_with_error() {
    let bad = |r: Value| Rules::from_json(&json!({"semantics": {"groups": groups()}, "rules": [r]})).err();
    assert!(bad(json!({"id": "X", "frame": "限", "zzz": 1})).unwrap().contains("모르는 키"));
    assert!(bad(json!({"id": "X", "frame": "限", "at": {"zzz": 1}})).unwrap().contains("모르는 키"));
    assert!(bad(json!({"id": "X", "frame": "五限"})).unwrap().contains("모르는 frame"));
    assert!(bad(json!({"id": "X", "frame": "限", "at": {"scope": "六方"}})).unwrap().contains("scope"));
    assert!(bad(json!({"id": "X", "frame": "限", "at": {"any": ["@없는무리"]}})).unwrap().contains("무리"));
    assert!(bad(json!({"id": "X", "frame": "限", "natal": {"zzz": 1}})).unwrap().contains("모르는 키"));
    assert!(bad(json!({"id": "X", "frame": "限", "age": {"zzz": 1}})).unwrap().contains("모르는 키"));
    // 평가 시 sex 값 오류
    let r = json!({"id": "X", "frame": "限", "sex": "?"});
    let rs = rules_of(vec![r.clone()]);
    assert!(stands(&rs, &r, &ch(&[]), &yr(), TwoLimit::SamePalace).is_err());
}

#[test]
fn standing_ids_partial_and_branches() {
    let c = ch(&[("擎羊", '午')]);
    let rs = rules_of(vec![
        json!({"id": "Q01a", "frame": "大限", "at": {"all": ["擎羊"]}}),
        json!({"id": "Q01b", "frame": "大限", "at": {"any": ["@凶星"]}}),
        json!({"id": "Q02", "frame": "大限", "at": {"all": ["擎羊"]}, "partial": true}),
        json!({"id": "Q03", "frame": "大限", "at": {"all": ["火星"]}}),
    ]);
    assert_eq!(standing(&rs, &c, &yr(), TwoLimit::SamePalace, false).unwrap(), ["Q01"]); // 갈래는 한 번, partial 제외
    assert_eq!(standing(&rs, &c, &yr(), TwoLimit::SamePalace, true).unwrap(), ["Q01", "Q02"]);
    assert_eq!(base_id("Q07a"), "Q07");
    assert_eq!(base_id("Q07"), "Q07");
    assert_eq!(br('午'), 6);
}

#[test]
fn engine_chart_adapter_and_real_rules_file() {
    use ziwei_rs::{build_chart, build_timeline, DaxianStart, Input, TimelineOpts};
    let inp: Input = serde_json::from_value(json!({"year_gz": "己丑", "month": 3, "day": 15, "hour": "戌", "male": true})).unwrap();
    let ch = ChartCtx::from_engine(&build_chart(&inp).unwrap()).unwrap();
    assert!(ch.male && ch.ming == br('午'));
    let main = ["紫微", "天機", "太陽", "武曲", "天同", "廉貞", "天府", "太陰", "貪狼", "巨門", "天相", "天梁", "七殺", "破軍"];
    assert_eq!(ch.stars.iter().flatten().filter(|s| main.contains(&s.as_str())).count(), 14);
    assert!(ch.stars.iter().flatten().any(|s| s == "旬空") && ch.stars.iter().flatten().any(|s| s == "天空"));
    let tl = build_timeline(&inp, TimelineOpts { daxian_start: DaxianStart::Manage, dayun_start: Some(5) }).unwrap();
    let y = YearCtx::from_timeline(&tl["years"][9], "dayun_hua").unwrap();
    assert_eq!(y.age, 10);
    assert_eq!(y.year_hua.len(), 4);
    // 규칙 파일이 있으면 41개가 모르는 키 없이 읽힌다(채점은 하지 않는다)
    if let Ok(t) = std::fs::read_to_string("/mnt/project-files/간명모델_원전학습/rules/rules_death_quanshu.json") {
        let rs = Rules::from_json(&serde_json::from_str(&t).unwrap()).unwrap();
        assert_eq!(rs.rules.len(), 41);
        for yy in tl["years"].as_array().unwrap() {
            let y = YearCtx::from_timeline(yy, "dayun_hua").unwrap();
            standing(&rs, &ch, &y, TwoLimit::SamePalace, true).unwrap(); // 오류 없이 평가된다
        }
    }
}

#[test]
fn metrics() {
    // 백분위: 점수 [3,1,1,0], 둘째 해(점수 1, 동점 둘) → 순위 (1 + (2+1)/2) = 2.5 → (2.5-0.5)/4 = 50%
    let (r, p) = percentile(&[3.0, 1.0, 1.0, 0.0], 1);
    assert_eq!(r, 2.5);
    assert!((p - 50.0).abs() < 1e-9);
    assert_eq!(percentile(&[5.0, 0.0, 0.0, 0.0], 0).0, 1.0);
    // 대한 1위: 대한 1(해 0~1) 합 4, 대한 2(해 2~3) 합 1
    let s = [3.0, 1.0, 1.0, 0.0];
    let d = [1, 1, 2, 2];
    assert_eq!(daxian_top(&s, &d, 0).unwrap(), (1.0, 2));
    assert_eq!(daxian_top(&s, &d, 3).unwrap(), (0.0, 2));
    assert_eq!(daxian_top(&[1.0, 1.0], &[1, 2], 0).unwrap().0, 0.5); // 동점은 나눔
    assert!(daxian_top(&s, &[0, 0, 0, 0], 0).is_none());
    // 부호 검정: 10 대 0 → p = 2/1024
    assert!((sign_test_p(10, 0) - 2.0 / 1024.0).abs() < 1e-12);
    assert!((sign_test_p(5, 5) - 1.0).abs() < 1e-12);
    assert_eq!(sign_test_p(0, 0), 1.0);
}

#[test]
fn backtest_pipeline_on_synthetic_cases() {
    // 합성 사례(명례 아님)로 틀이 끝까지 도는지만 본다. 규칙은 합성 규칙 하나.
    let dir = std::env::temp_dir().join("zw_backtest_synth");
    let _ = std::fs::remove_dir_all(&dir);
    std::fs::create_dir_all(&dir).unwrap();
    let mk = |id: &str, gz: &str, m: i64, age: i64, sex: &str| {
        json!({"id": id, "birth": {"year_gz": gz, "month": m, "day": 10, "hour_branch": "子", "sex": sex, "leap": false, "notes": [], "raw": ""},
               "death": {"age": age}, "palaces": []})
    };
    let cases = json!([mk("s1", "甲子", 3, 40, "男"), mk("s2", "乙丑", 5, 52, "女"), mk("s3", "丙寅", 7, 33, "男"), mk("s4", "丁卯", 9, 61, "男"), mk("s5", "戊辰", 2, 24, "女")]);
    std::fs::write(dir.join("cases.json"), cases.to_string()).unwrap();
    let rules = json!({"semantics": {"groups": groups()}, "rules": [
        {"id": "Q01", "frame": "限", "at": {"any": ["@凶星"]}}, {"id": "Q02", "frame": "太歲", "at": {"any": ["@凶星"]}, "partial": true}]});
    std::fs::write(dir.join("rules.json"), rules.to_string()).unwrap();
    for f in [ziwei_rs::backtest::Frame::A, ziwei_rs::backtest::Frame::B] {
        let out = dir.join("out");
        ziwei_rs::backtest::run(dir.join("cases.json").to_str().unwrap(), dir.join("rules.json").to_str().unwrap(), out.to_str().unwrap(), f, TwoLimit::SamePalace).unwrap();
        let name = if f == ziwei_rs::backtest::Frame::A { "A" } else { "B" };
        let md = std::fs::read_to_string(out.join(format!("결과_{name}.md"))).unwrap();
        assert!(md.contains("부호 검정 p") && md.contains("완전 규칙만") && md.contains("부분 규칙 포함"));
        let tsv = std::fs::read_to_string(out.join(format!("사례별_{name}.tsv"))).unwrap();
        assert_eq!(tsv.lines().count(), 6);
    }
    // 모르는 키가 있는 규칙 파일은 오류로 멈춘다
    let bad = json!({"semantics": {"groups": groups()}, "rules": [{"id": "Q", "frame": "限", "zzz": 1}]});
    std::fs::write(dir.join("bad.json"), bad.to_string()).unwrap();
    assert!(ziwei_rs::backtest::run(dir.join("cases.json").to_str().unwrap(), dir.join("bad.json").to_str().unwrap(), dir.join("o2").to_str().unwrap(), ziwei_rs::backtest::Frame::B, TwoLimit::SamePalace).is_err());
}
