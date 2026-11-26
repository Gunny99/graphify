use ziwei_rs::solar::{solar_hour, SolarInput};

fn si(date: &str, time: &str, lon: f64) -> SolarInput {
    SolarInput { date: date.into(), time: time.into(), lon, meridian: None, utc_offset: None, zi_rule: None }
}
fn f(v: &serde_json::Value, k: &str) -> f64 {
    v[k].as_f64().unwrap()
}

#[test]
fn incheon_1999_current_input() {
    // 대상 명식(정정): 시계 10:10, 인천 126.7, 자오선 135 → 진태양시 09:31 전후, 巳時
    let v = solar_hour(&si("1999-08-04", "10:10", 126.7), true).unwrap();
    println!("{v}");
    assert!((f(&v, "lon_correction_min") + 33.2).abs() <= 1.0);
    let t = v["solar_time"].as_str().unwrap();
    let m: i64 = t[..2].parse::<i64>().unwrap() * 60 + t[3..5].parse::<i64>().unwrap();
    assert!((m - (9 * 60 + 31)).abs() <= 1, "{t}");
    assert_eq!(v["hour_branch"], "巳");
}

#[test]
fn seoul_1999() {
    // 옛 입력(10:14, 같은 巳時) 회귀
    let v = solar_hour(&si("1999-08-04", "10:14", 126.7), true).unwrap();
    println!("{v}");
    assert!((f(&v, "lon_correction_min") + 33.2).abs() <= 1.0);
    assert!((f(&v, "eot_min") + 6.0).abs() <= 1.0);
    // 진태양시 09:35 전후 ±1분
    let t = v["solar_time"].as_str().unwrap();
    let m: i64 = t[..2].parse::<i64>().unwrap() * 60 + t[3..5].parse::<i64>().unwrap();
    assert!((m - (9 * 60 + 35)).abs() <= 1, "{t}");
    assert_eq!(v["hour_branch"], "巳");
    let r = f(&v, "min_to_boundary");
    assert!(r > 70.0 && r < 90.0, "{r}"); // 09:00~10:59 巳, 11:00까지
}

#[test]
fn no_eot_and_offset() {
    let v = solar_hour(&si("1999-08-04", "10:14", 126.7), false).unwrap();
    assert_eq!(f(&v, "eot_min"), 0.0);
    // UTC+8:30(1954~61 한국) 입력: 자오선 127.5
    let mut s = si("1957-01-01", "12:00", 127.5);
    s.utc_offset = Some(8.5);
    let v = solar_hour(&s, false).unwrap();
    assert_eq!(f(&v, "lon_correction_min"), 0.0);
    assert_eq!(v["hour_branch"], "午");
}

#[test]
fn zi_boundary_and_date_shift() {
    let mut s = si("2000-03-01", "23:30", 135.0);
    s.zi_rule = Some("next_day".into()); // 기본값은 prev_day(Gunny 11-26 확정), next_day는 옵션
    let v = solar_hour(&s, false).unwrap();
    assert_eq!(v["hour_branch"], "子");
    assert_eq!(v["zi_next_day"], true);
    assert_eq!(v["date_for_lunar"], "2000-03-02");
    // 00:10 시계에 -33분 → 전날 23:37
    let v = solar_hour(&si("2000-03-01", "00:10", 126.7), false).unwrap();
    assert_eq!(v["solar_date"], "2000-02-29");
    assert_eq!(v["hour_branch"], "子");
    // 경계: 09:00 정각은 巳 시작
    let v = solar_hour(&si("2000-03-01", "09:00", 135.0), false).unwrap();
    assert_eq!(v["hour_branch"], "巳");
    assert_eq!(f(&v, "min_to_boundary"), 120.0);
}

fn date_for(date: &str, time: &str, lon: f64, rule: &str) -> (String, String, String) {
    let mut s = si(date, time, lon);
    s.zi_rule = Some(rule.into());
    let v = solar_hour(&s, false).unwrap();
    (v["date_for_lunar"].as_str().unwrap().into(), v["solar_date"].as_str().unwrap().into(), v["hour_branch"].as_str().unwrap().into())
}

#[test]
fn zi_is_not_a_choice_and_prev_day_rule() {
    assert!(solar_hour(&si("2000-03-01", "23:30", 135.0), false).unwrap().get("choices").is_none());
    assert_eq!(solar_hour(&si("2000-03-01", "23:30", 135.0), false).unwrap()["zi_rule"], "prev_day"); // 기본값(Gunny 11-26 확정)
    let d = solar_hour(&si("2000-03-02", "00:30", 135.0), false).unwrap();
    assert_eq!(d["date_for_lunar"], "2000-03-01"); // 기본값은 00시대도 전날
    let t = solar_hour(&si("1999-08-04", "10:10", 126.7), true).unwrap(); // 巳時 대상 명식은 규칙과 무관
    assert_eq!((t["hour_branch"].as_str(), t["date_for_lunar"].as_str()), (Some("巳"), Some("1999-08-04")));
    // 23:30: prev_day와 same_day는 그날, next_day는 다음 날
    assert_eq!(date_for("2000-03-01", "23:30", 135.0, "prev_day").0, "2000-03-01");
    assert_eq!(date_for("2000-03-01", "23:30", 135.0, "same_day").0, "2000-03-01");
    assert_eq!(date_for("2000-03-01", "23:30", 135.0, "next_day").0, "2000-03-02");
    // 00:30: prev_day만 전날
    assert_eq!(date_for("2000-03-02", "00:30", 135.0, "prev_day").0, "2000-03-01");
    assert_eq!(date_for("2000-03-02", "00:30", 135.0, "next_day").0, "2000-03-02");
    assert_eq!(date_for("2000-03-02", "00:30", 135.0, "same_day").0, "2000-03-02");
    // 시계 00:20이 경도 보정으로 진태양시 전날 23:40
    let (d, sd, b) = date_for("1999-08-05", "00:20", 126.7, "prev_day");
    assert_eq!((d.as_str(), sd.as_str(), b.as_str()), ("1999-08-04", "1999-08-04", "子"));
    assert_eq!(date_for("1999-08-05", "00:20", 126.7, "next_day").0, "1999-08-05");
    // 시계 23:10이라도 보정으로 22:30이면 亥, 날짜를 넘기지 않는다(진태양시 기준)
    let (d, _, b) = date_for("1999-08-04", "23:10", 126.7, "next_day");
    assert_eq!((d.as_str(), b.as_str()), ("1999-08-04", "亥"));
    let mut s = si("2000-03-01", "12:00", 135.0);
    s.zi_rule = Some("bogus".into());
    assert!(solar_hour(&s, false).is_err());
}
