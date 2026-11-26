//! 진태양시 보정: 시계 시각 → 평균태양시(경도 보정) → 진태양시(균시차) → 시지.
//! 균시차는 NOAA 일반식(Spencer 1971 푸리에식, 분)을 그날 정오 기준으로 쓴다.
//! 서머타임·역사적 표준시 변경은 자동 판단하지 않는다: 호출자가 그때 시계의 UTC 오프셋(또는 자오선)을 넣는다.
use crate::common::BR;
use serde::Deserialize;
use serde_json::{json, Value};

#[derive(Debug, Clone, Deserialize)]
pub struct SolarInput {
    /// 양력 YYYY-MM-DD
    pub date: String,
    /// 시계 시각 HH:MM
    pub time: String,
    /// 출생지 경도(동경 +)
    pub lon: f64,
    /// 표준시 자오선 경도(기본 135.0)
    pub meridian: Option<f64>,
    /// 표준시 UTC 오프셋 시간(자오선 = 15 × 오프셋). meridian과 함께 주면 meridian 우선.
    pub utc_offset: Option<f64>,
    /// 子時 규칙 prev_day(기본, 23:00~00:59 전체를 23:00이 시작된 날로) | next_day | same_day
    #[serde(default)]
    pub zi_rule: Option<String>,
}

fn days_from_civil(y: i64, m: i64, d: i64) -> i64 {
    let y = if m <= 2 { y - 1 } else { y };
    let era = y.div_euclid(400);
    let yoe = y - era * 400;
    let doy = (153 * (m + if m > 2 { -3 } else { 9 }) + 2) / 5 + d - 1;
    let doe = yoe * 365 + yoe / 4 - yoe / 100 + doy;
    era * 146097 + doe - 719468
}
fn civil_from_days(z: i64) -> (i64, i64, i64) {
    let z = z + 719468;
    let era = z.div_euclid(146097);
    let doe = z - era * 146097;
    let yoe = (doe - doe / 1460 + doe / 36524 - doe / 146096) / 365;
    let y = yoe + era * 400;
    let doy = doe - (365 * yoe + yoe / 4 - yoe / 100);
    let mp = (5 * doy + 2) / 153;
    let d = doy - (153 * mp + 2) / 5 + 1;
    let m = if mp < 10 { mp + 3 } else { mp - 9 };
    (if m <= 2 { y + 1 } else { y }, m, d)
}

/// 균시차(분). 진태양시 − 평균태양시. 그날 정오 기준.
pub fn equation_of_time(y: i64, m: i64, d: i64) -> f64 {
    let doy = days_from_civil(y, m, d) - days_from_civil(y, 1, 1) + 1;
    let n = if (y % 4 == 0 && y % 100 != 0) || y % 400 == 0 { 366.0 } else { 365.0 };
    let g = 2.0 * std::f64::consts::PI / n * (doy as f64 - 1.0);
    229.18 * (0.000075 + 0.001868 * g.cos() - 0.032077 * g.sin() - 0.014615 * (2.0 * g).cos() - 0.040849 * (2.0 * g).sin())
}

fn parse(inp: &SolarInput) -> Result<(i64, i64, i64, i64, i64), String> {
    let p: Vec<i64> = inp.date.split('-').map(|s| s.parse().map_err(|_| format!("date 오류: {}", inp.date))).collect::<Result<_, _>>()?;
    let t: Vec<i64> = inp.time.split(':').map(|s| s.parse().map_err(|_| format!("time 오류: {}", inp.time))).collect::<Result<_, _>>()?;
    if p.len() != 3 || t.len() != 2 || !(1..=12).contains(&p[1]) || !(1..=31).contains(&p[2]) || !(0..24).contains(&t[0]) || !(0..60).contains(&t[1]) {
        return Err(format!("date/time 오류: {} {}", inp.date, inp.time));
    }
    let (y, m, d) = civil_from_days(days_from_civil(p[0], p[1], p[2]));
    if (y, m, d) != (p[0], p[1], p[2]) {
        return Err(format!("없는 날짜: {}", inp.date));
    }
    Ok((p[0], p[1], p[2], t[0], t[1]))
}

fn hhmm(min_of_day: f64) -> String {
    let t = min_of_day.rem_euclid(1440.0);
    let r = (t * 60.0).round() as i64; // 초
    let r = r % 86400;
    format!("{:02}:{:02}:{:02}", r / 3600, r % 3600 / 60, r % 60)
}

pub fn solar_hour(inp: &SolarInput, use_eot: bool) -> Result<Value, String> {
    let (y, m, d, hh, mm) = parse(inp)?;
    let meridian = match (inp.meridian, inp.utc_offset) {
        (Some(x), _) => x,
        (None, Some(o)) => 15.0 * o,
        _ => 135.0,
    };
    let lon_corr = 4.0 * (inp.lon - meridian);
    let eot = if use_eot { equation_of_time(y, m, d) } else { 0.0 };
    let clock = (hh * 60 + mm) as f64;
    let total = clock + lon_corr + eot; // 날짜 경계를 넘을 수 있다
    let day_shift = (total / 1440.0).floor() as i64;
    let solar = total - day_shift as f64 * 1440.0;
    let (sy, sm, sd) = civil_from_days(days_from_civil(y, m, d) + day_shift);
    // 子時 23:00~00:59 → 0, 丑 01:00~02:59 → 1 …
    let shifted = (solar + 60.0).rem_euclid(1440.0);
    let idx = (shifted / 120.0).floor() as usize % 12;
    let to_next = 120.0 - shifted % 120.0; // 다음 시지 경계까지
    let since = shifted % 120.0; // 현재 시지 시작 후
    let solar_hour = (solar / 60.0).floor() as i64;
    // 子時 규칙(고객 선택이 아니라 입력 규칙): prev_day(기본, Gunny 11-26 확정) 23:00~00:59 전체를 23:00이 시작된 날로, next_day 23시대는 다음 날, same_day 그날.
    let rule = inp.zi_rule.as_deref().unwrap_or("prev_day");
    let shift = match rule {
        "next_day" => (solar_hour == 23) as i64,
        "same_day" => 0,
        "prev_day" => -((solar_hour == 0) as i64),
        other => return Err(format!("zi_rule 오류: {other}")),
    };
    let zi_next = shift == 1;
    let (ly, lm, ld) = civil_from_days(days_from_civil(sy, sm, sd) + shift);
    let r = |x: f64| (x * 100.0).round() / 100.0;
    Ok(json!({
        "input": {"date": inp.date, "time": inp.time, "lon": inp.lon, "meridian": meridian, "eot": use_eot},
        "lon_correction_min": r(lon_corr),
        "eot_min": r(eot),
        "clock_min": clock,
        "solar_date": format!("{sy:04}-{sm:02}-{sd:02}"),
        "solar_time": hhmm(solar),
        "hour_branch": BR.chars().nth(idx).unwrap().to_string(),
        "hour_index": idx,
        "min_to_boundary": r(to_next),
        "min_since_boundary": r(since),
        "zi_rule": rule,
        "zi_next_day": zi_next,
        "date_for_lunar": format!("{ly:04}-{lm:02}-{ld:02}"),
        "note": "서머타임·역사적 표준시는 자동 판단하지 않음(meridian/utc_offset 입력으로만 반영)",
    }))
}
