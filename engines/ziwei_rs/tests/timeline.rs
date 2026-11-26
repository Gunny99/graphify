use serde_json::Value;
use ziwei_rs::common::*;
use ziwei_rs::{build_chart, build_timeline, DaxianStart, Input, TimelineOpts};

fn inp(gz: &str, male: bool) -> Input {
    serde_json::from_value(serde_json::json!({"year_gz": gz, "month": 3, "day": 15, "hour": "戌", "male": male, "leap": false})).unwrap()
}
fn tl(gz: &str, male: bool, ds: DaxianStart, dy: Option<i64>) -> Value {
    build_timeline(&inp(gz, male), TimelineOpts { daxian_start: ds, dayun_start: dy }).unwrap()
}
fn yr(t: &Value, age: usize) -> &Value {
    &t["years"][age - 1]
}
fn br(v: &Value) -> &str {
    v["branch"].as_str().unwrap()
}

#[test]
fn xiaoxian_examples() {
    // 寅午戌人 起辰, 男順 女逆
    for gz in ["甲午", "丙寅", "甲戌"] {
        let m = tl(gz, true, DaxianStart::Xusui, None);
        assert_eq!(br(&yr(&m, 1)["xiaoxian"]), "辰", "{gz}");
        assert_eq!(br(&yr(&m, 2)["xiaoxian"]), "巳", "{gz}");
        let f = tl(gz, false, DaxianStart::Xusui, None);
        assert_eq!(br(&yr(&f, 1)["xiaoxian"]), "辰", "{gz}");
        assert_eq!(br(&yr(&f, 2)["xiaoxian"]), "卯", "{gz}");
    }
    // 起宮: 申子辰 戌, 巳酉丑 未, 亥卯未 丑
    for (gz, z) in [("壬子", "戌"), ("己丑", "未"), ("乙亥", "丑"), ("丁酉", "未"), ("丙辰", "戌"), ("辛卯", "丑")] {
        assert_eq!(br(&yr(&tl(gz, true, DaxianStart::Xusui, None), 1)["xiaoxian"]), z, "{gz}");
    }
    // 열두 해마다 한 바퀴
    let m = tl("甲午", true, DaxianStart::Xusui, None);
    assert_eq!(yr(&m, 13)["xiaoxian"], yr(&m, 1)["xiaoxian"]);
}

#[test]
fn daxian_direction_and_start() {
    // 己丑 남: 陰男 → 역행, 명궁 午, 土五局
    let c = build_chart(&inp("己丑", true)).unwrap();
    assert_eq!((c["ming"].as_str().unwrap(), c["ju"].as_i64().unwrap()), ("午", 5));
    let x = tl("己丑", true, DaxianStart::Xusui, None);
    assert_eq!(x["direction"], "역행");
    assert!(yr(&x, 4)["daxian"].is_null());
    assert_eq!(br(&yr(&x, 5)["daxian"]["palace"]), "午");
    assert_eq!(br(&yr(&x, 14)["daxian"]["palace"]), "午");
    assert_eq!(br(&yr(&x, 15)["daxian"]["palace"]), "巳");
    assert_eq!(yr(&x, 5)["daxian"]["age_from"], 5);
    assert_eq!(yr(&x, 5)["daxian"]["age_to"], 14);
    assert_eq!(br(&yr(&x, 25)["daxian"]["palace"]), "辰");
    // 만 나이 규약: 虛歲 局數+1부터
    let m = tl("己丑", true, DaxianStart::Manage, None);
    assert!(yr(&m, 5)["daxian"].is_null());
    assert_eq!(yr(&m, 5)["pre_daxian"], true);
    assert_eq!(br(&yr(&m, 6)["daxian"]["palace"]), "午");
    assert_eq!(br(&yr(&m, 15)["daxian"]["palace"]), "午");
    assert_eq!(br(&yr(&m, 16)["daxian"]["palace"]), "巳");
    // 己丑 여: 陰女 → 순행
    let f = tl("己丑", false, DaxianStart::Xusui, None);
    assert_eq!(f["direction"], "순행");
    let cf = build_chart(&inp("己丑", false)).unwrap();
    let ming = cf["ming"].as_str().unwrap().chars().next().unwrap();
    let ju = cf["ju"].as_i64().unwrap() as usize;
    assert_eq!(br(&yr(&f, ju)["daxian"]["palace"]), ming.to_string());
    assert_eq!(br(&yr(&f, ju + 10)["daxian"]["palace"]), bz(bi(ming) + 1).to_string());
    // 陽男(甲子 남) 순행, 陽女 역행
    let a = tl("甲子", true, DaxianStart::Xusui, None);
    let ca = build_chart(&inp("甲子", true)).unwrap();
    let (m0, j0) = (ca["ming"].as_str().unwrap().chars().next().unwrap(), ca["ju"].as_i64().unwrap() as usize);
    assert_eq!(a["direction"], "순행");
    assert_eq!(br(&yr(&a, j0 + 10)["daxian"]["palace"]), bz(bi(m0) + 1).to_string());
    let b = tl("甲子", false, DaxianStart::Xusui, None);
    assert_eq!(b["direction"], "역행");
    let cb = build_chart(&inp("甲子", false)).unwrap();
    let (m1, j1) = (cb["ming"].as_str().unwrap().chars().next().unwrap(), cb["ju"].as_i64().unwrap() as usize);
    assert_eq!(br(&yr(&b, j1 + 10)["daxian"]["palace"]), bz(bi(m1) - 1).to_string());
}

#[test]
fn tongxian_is_separate_field() {
    let x = tl("己丑", true, DaxianStart::Xusui, None);
    let c = build_chart(&inp("己丑", true)).unwrap();
    let roles = ["명", "재백", "질액", "부처", "복덕", "관록"];
    for (i, r) in roles.iter().enumerate() {
        let t = &yr(&x, i + 1)["tongxian"]["palace"];
        assert_eq!(t["role"], *r);
        assert_eq!(c["palaces"][br(t)]["role"], *r);
    }
    assert!(yr(&x, 7)["tongxian"].is_null());
    // 局數(5) 이후엔 大限이 따로 있고 童限(5, 6세)을 덮어쓰지 않는다
    assert!(!yr(&x, 5)["daxian"].is_null() && !yr(&x, 5)["tongxian"].is_null());
    assert_eq!(yr(&x, 1)["tongxian"]["palace"]["branch"], c["ming"]);
}

#[test]
fn liu_yang_is_lu_plus_one() {
    for gz in ["甲子", "乙丑", "丙寅", "丁卯", "戊辰", "己巳", "庚午", "辛未", "壬申", "癸酉"] {
        let t = tl(gz, true, DaxianStart::Xusui, None);
        for age in 1..=100 {
            let y = yr(&t, age);
            let lu = bi(y["liu_lu"]["palace"]["branch"].as_str().unwrap().chars().next().unwrap());
            let ya = bi(y["liu_yang"]["palace"]["branch"].as_str().unwrap().chars().next().unwrap());
            let tu = bi(y["liu_tuo"]["palace"]["branch"].as_str().unwrap().chars().next().unwrap());
            assert_eq!(ya, (lu + 1).rem_euclid(12));
            assert_eq!(tu, (lu - 1).rem_euclid(12));
            let stem = y["taisui"]["stem"].as_str().unwrap().chars().next().unwrap();
            assert_eq!(lu, bi("寅卯巳午巳午申酉亥子".chars().nth(si(stem)).unwrap()));
        }
    }
}

#[test]
fn taisui_and_hua() {
    let t = tl("己丑", true, DaxianStart::Xusui, None);
    assert_eq!(yr(&t, 1)["taisui"]["gz"], "己丑");
    assert_eq!(yr(&t, 2)["taisui"]["gz"], "庚寅");
    assert_eq!(yr(&t, 61)["taisui"]["gz"], "己丑");
    let c = build_chart(&inp("己丑", true)).unwrap();
    let y = yr(&t, 2);
    let hua = y["taisui_hua"].as_array().unwrap();
    assert_eq!(hua.len(), 4);
    let sihua: Value = serde_json::from_str(include_str!("../data/sihua.json")).unwrap();
    for (i, h) in ["록", "권", "과", "기"].iter().enumerate() {
        assert_eq!(hua[i]["hua"], *h);
        assert_eq!(hua[i]["star"], sihua["default"]["庚"][*h]["star"]);
        assert_eq!(hua[i]["palace"]["branch"], c["pos"][hua[i]["star"].as_str().unwrap()]);
    }
    assert_eq!(y["taisui"]["palace"]["branch"], "寅");
}

#[test]
fn dayun() {
    // 己丑 3월: 월지 辰, 월간 五虎遁 己→丙(寅) +2 = 戊 → 戊辰. 陰男 → 역행
    let t = tl("己丑", true, DaxianStart::Xusui, None);
    assert_eq!(t["dayun"]["month_pillar"], "戊辰");
    let p: Vec<&str> = t["dayun"]["periods"].as_array().unwrap().iter().map(|x| x["gz"].as_str().unwrap()).collect();
    assert_eq!(p, ["丁卯", "丙寅", "乙丑", "甲子", "癸亥", "壬戌", "辛酉", "庚申", "己未", "戊午"]);
    assert!(yr(&t, 30)["dayun"].is_null() && yr(&t, 30)["dayun_hua"].is_null());
    // 陰女 → 순행
    let f = tl("己丑", false, DaxianStart::Xusui, None);
    assert_eq!(f["dayun"]["periods"][0]["gz"], "己巳");
    // dayun_start
    let s = tl("己丑", true, DaxianStart::Xusui, Some(8));
    assert!(yr(&s, 7)["dayun"].is_null());
    assert_eq!(yr(&s, 8)["dayun"]["gz"], "丁卯");
    assert_eq!(yr(&s, 17)["dayun"]["gz"], "丁卯");
    assert_eq!(yr(&s, 18)["dayun"]["gz"], "丙寅");
    assert_eq!(yr(&s, 18)["dayun"]["stem"], "丙");
    assert_eq!(yr(&s, 100)["dayun"]["gz"], "戊午"); // (100-8)/10 = 9번째
    let late = tl("己丑", true, DaxianStart::Xusui, Some(20));
    assert_eq!(yr(&late, 100)["dayun"]["n"], 9);
}

#[test]
fn dayun_last_period_and_hua() {
    let s = tl("己丑", true, DaxianStart::Xusui, Some(1));
    assert_eq!(yr(&s, 100)["dayun"]["gz"], "戊午");
    let hua = yr(&s, 100)["dayun_hua"].as_array().unwrap();
    assert_eq!(hua.len(), 4);
    assert_eq!(hua[0]["hua"], "록");
}

#[test]
fn leap_choices() {
    let mk = |rule: Option<&str>, day: i64| -> Input {
        serde_json::from_value(serde_json::json!({"year_gz": "癸卯", "month": 2, "day": day, "hour": "午", "male": true, "leap": true, "leap_rule": rule})).unwrap()
    };
    // 2023 윤2월 10일
    let c = build_chart(&mk(None, 10)).unwrap();
    let ch = &c["choices"][0];
    assert_eq!(ch["kind"], "leap");
    let months: Vec<i64> = ch["options"].as_array().unwrap().iter().map(|o| o["chart_month"].as_i64().unwrap()).collect();
    assert_eq!(months, [2, 3, 2]);
    assert!(ch["chosen"].is_null());
    assert_eq!(ch["same_result"], false);
    assert!(c["input"].get("leap_rule").is_none());
    // 규칙 명시: chosen 기록, 명반은 그 규칙의 월로
    let n = build_chart(&mk(Some("next"), 10)).unwrap();
    assert_eq!(n["choices"][0]["chosen"], "next");
    assert_eq!(n["ming"], ch["options"][1]["ming"]);
    assert_eq!(build_chart(&mk(Some("split15"), 20)).unwrap()["ming"], n["ming"]);
    assert!(build_timeline(&mk(Some("next"), 10), TimelineOpts::default()).unwrap()["choices"].is_array());
    // 윤달이 아니면 choices 키가 없다
    assert!(build_chart(&inp("己丑", true)).unwrap().get("choices").is_none());
    assert!(build_chart(&mk(Some("bad"), 10)).is_err());
}

#[test]
fn four_flying_stars() {
    // 子년(甲子 1세): 太歲 子 → 喪門 寅, 吊客 戌, 白虎 申(喪門 대궁), 官府 辰(吊客 대궁)
    let t = tl("甲子", true, DaxianStart::Xusui, None);
    let y = yr(&t, 1);
    assert_eq!(y["taisui"]["branch"], "子");
    assert_eq!(br(&y["sangmen"]), "寅");
    assert_eq!(br(&y["diaoke"]), "戌");
    assert_eq!(br(&y["baihu"]), "申");
    assert_eq!(br(&y["guanfu"]), "辰");
    assert!(y["sangmen"]["role"].is_string());
    for age in 1..=100 {
        let y = yr(&t, age);
        let tb = bi(br(&y["taisui"]["palace"]).chars().next().unwrap());
        let b = |k: &str| bi(br(&y[k]).chars().next().unwrap());
        assert_eq!(b("sangmen"), (tb + 2).rem_euclid(12));
        assert_eq!(b("diaoke"), (tb - 2).rem_euclid(12));
        assert_eq!(b("baihu"), (b("sangmen") + 6).rem_euclid(12));
        assert_eq!(b("guanfu"), (b("diaoke") + 6).rem_euclid(12));
    }
}

#[test]
fn quanshu_variant() {
    // 大限 규약 quanshu: 陽男陰女 첫 大限 = 父母궁(명궁+1), 陰男陽女 = 兄弟궁(명궁−1), 같은 방향
    let mk = |gz: &str, male: bool| -> Input {
        serde_json::from_value(serde_json::json!({"year_gz": gz, "month": 3, "day": 15, "hour": "戌", "male": male, "variant": "quanshu"})).unwrap()
    };
    let q = |gz: &str, male: bool| build_timeline(&mk(gz, male), TimelineOpts { daxian_start: DaxianStart::Quanshu, dayun_start: None }).unwrap();
    // 己丑 남(陰男 역행): 명궁 午 → 兄弟 巳에서 시작, 다음 辰
    let t = q("己丑", true);
    assert!(yr(&t, 4)["daxian"].is_null());
    let ju = t["ju"].as_i64().unwrap() as usize;
    assert_eq!(br(&yr(&t, ju)["daxian"]["palace"]), "巳");
    assert_eq!(yr(&t, ju)["daxian"]["palace"]["role"], "형제");
    assert_eq!(br(&yr(&t, ju + 10)["daxian"]["palace"]), "辰");
    // 己丑 여(陰女 순행): 명궁 午(月·時는 같으나 성별만 다름 → 명궁은 같다) → 父母 未에서 시작
    let f = q("己丑", false);
    let jf = f["ju"].as_i64().unwrap() as usize;
    assert_eq!(yr(&f, jf)["daxian"]["palace"]["role"], "부모");
    // 사화표 전서: 庚 록 태양 권 무곡 과 태음→(전서) 천동... 표 그대로
    let c = build_chart(&mk("庚午", true)).unwrap();
    assert_eq!(c["sihua_variant"], "quanshu");
    assert_eq!(c["birth_hua"]["과"]["star"], "천동");
    assert_eq!(c["birth_hua"]["기"]["star"], "천상");
    // 기본값은 그대로(Python 대조 golden이 따로 보장): 庚 과 = 태음, 기 = 천동
    let d = build_chart(&inp("庚午", true)).unwrap();
    assert_eq!(d["birth_hua"]["과"]["star"], "태음");
    assert_eq!(d["sihua_variant"], "default");
}

#[test]
fn quanshu_firebell_fixed_at_base() {
    // 寅午戌년: 火 起宮 丑, 鈴 起宮 卯. 전서 변형은 시를 세지 않는다(명례 칸 100% 일치), 기본은 시를 센다
    let mk = |v: Option<&str>| -> Input {
        serde_json::from_value(serde_json::json!({"year_gz": "甲午", "month": 3, "day": 15, "hour": "戌", "male": true, "variant": v})).unwrap()
    };
    let q = build_chart(&mk(Some("quanshu"))).unwrap();
    assert_eq!(q["pos"]["화성"], "丑");
    assert_eq!(q["pos"]["영성"], "卯");
    let d = build_chart(&mk(None)).unwrap();
    assert_eq!(d["pos"]["화성"], "亥"); // 丑 + 戌(10) = 亥
}
