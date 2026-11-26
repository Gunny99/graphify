use ziwei_rs::solar::{solar_hour, SolarInput};

fn si(date: &str, time: &str, lon: f64) -> SolarInput {
    SolarInput { date: date.into(), time: time.into(), lon, meridian: None, utc_offset: None }
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
    s.meridian = Some(135.0);
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
