//! 해마다 표(虛歲 1~100): 太歲·大限·小限·童限·流祿羊陀·사화·대운.
use crate::chart::{lu_of, parse_input, place_stars, san, sihua_of, Input};
use crate::common::*;
use serde_json::{json, Value};

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum DaxianStart {
    /// 局數 虛歲부터 (土五局이면 虛歲 5~14가 명궁)
    Xusui,
    /// 만 나이 局數부터 = 虛歲 局數+1부터
    Manage,
}

#[derive(Debug, Clone, Copy)]
pub struct TimelineOpts {
    pub daxian_start: DaxianStart,
    /// 첫 대운이 시작하는 虛歲. None이면 해마다 대운을 내지 않는다.
    pub dayun_start: Option<i64>,
}

impl Default for TimelineOpts {
    fn default() -> Self {
        TimelineOpts { daxian_start: DaxianStart::Xusui, dayun_start: None }
    }
}

/// 安童限訣: 虛歲 1~6 = 命·財帛·疾厄·夫妻(부처)·福德·官祿 궁
const TONG_ROLES: [&str; 6] = ["명", "재백", "질액", "부처", "복덕", "관록"];

fn palace(ming: char, z: char) -> Value {
    json!({"branch": z.to_string(), "role": role_of(ming, z)})
}

fn hua_list(stem: char, pos: &[(&'static str, char)], ming: char) -> Vec<Value> {
    sihua_of(stem)
        .into_iter()
        .map(|(h, star)| {
            let z = pos.iter().find(|(n, _)| *n == star).map(|(_, z)| *z).expect("사화성 자리");
            json!({"hua": h, "star": star, "palace": palace(ming, z)})
        })
        .collect()
}

pub fn build_timeline(inp: &Input, opts: TimelineOpts) -> Result<Value, String> {
    let (ys, yb, m, d, h) = parse_input(inp)?;
    let pl = place_stars(ys, yb, m, d, h)?;
    let ming = pl.ming;
    let mi = bi(ming);
    let ju = pl.ju;
    let fwd = yang_stem(ys) == inp.male; // 陽男陰女 순행
    let dx_start = match opts.daxian_start {
        DaxianStart::Xusui => ju,
        DaxianStart::Manage => ju + 1,
    };
    // 小限: 寅午戌→辰 申子辰→戌 巳酉丑→未 亥卯未→丑 (虛歲 1세), 남 순행 여 역행
    let xx0 = bi(['辰', '戌', '未', '丑'][san(yb)]);
    // 대운: 월주 근사
    let mb = bi('寅') + m - 1;
    let ms = ch(STEM, (si(tiger(ys)) + (m - 1) as usize) % 10);
    let month_pillar = format!("{}{}", ms, bz(mb));
    let m0 = k60(ms, bz(mb)).ok_or("월주 간지")? as i64;
    let dy: Vec<(String, char)> = (1..=10).map(|k| {
        let gz = gz60(m0 + if fwd { k } else { -k });
        let st = gz.chars().next().unwrap();
        (gz, st)
    }).collect();
    let dayun_list: Vec<Value> = dy.iter().enumerate().map(|(i, (gz, _))| json!({"n": i + 1, "gz": gz})).collect();

    let y0 = k60(ys, yb).unwrap() as i64;
    let mut years = vec![];
    for age in 1..=100i64 {
        let tgz = gz60(y0 + age - 1);
        let tc: Vec<char> = tgz.chars().collect();
        let (ts, tb) = (tc[0], tc[1]);
        // 大限
        let daxian = if age >= dx_start {
            let k = (age - dx_start) / 10;
            let z = bz(mi + if fwd { k } else { -k });
            json!({"index": k + 1, "palace": palace(ming, z), "age_from": dx_start + 10 * k, "age_to": dx_start + 10 * k + 9})
        } else {
            Value::Null
        };
        // 童限(虛歲 1~6, 大限과 별 필드)
        let tong = if age <= 6 {
            let role = TONG_ROLES[(age - 1) as usize];
            let z = BR.chars().find(|&z| role_of(ming, z) == role).unwrap();
            json!({"palace": palace(ming, z)})
        } else {
            Value::Null
        };
        let xz = bz(xx0 + if inp.male { age - 1 } else { -(age - 1) });
        let lu = bi(lu_of(ts));
        let liu = |name: &str, v: i64| json!({"star": name, "palace": palace(ming, bz(v))});
        // 대운
        let (dayun, dayun_hua) = match opts.dayun_start {
            Some(n0) if age >= n0 && (age - n0) / 10 < 10 => {
                let i = ((age - n0) / 10) as usize;
                let (gz, st) = &dy[i];
                (
                    json!({"n": i + 1, "gz": gz, "stem": st.to_string(), "age_from": n0 + 10 * i as i64, "age_to": n0 + 10 * i as i64 + 9}),
                    Value::Array(hua_list(*st, &pl.pos, ming)),
                )
            }
            _ => (Value::Null, Value::Null),
        };
        years.push(json!({
            "xusui": age,
            "taisui": {"gz": tgz, "stem": ts.to_string(), "branch": tb.to_string(), "palace": palace(ming, tb)},
            "daxian": daxian,
            "pre_daxian": age < dx_start,
            "tongxian": tong,
            "xiaoxian": palace(ming, xz),
            "liu_lu": liu("녹존", lu), "liu_yang": liu("경양", lu + 1), "liu_tuo": liu("타라", lu - 1),
            "taisui_hua": hua_list(ts, &pl.pos, ming),
            "dayun": dayun, "dayun_hua": dayun_hua,
        }));
    }
    Ok(json!({
        "input": inp,
        "year_gz": inp.year_gz, "ming": ming.to_string(), "ju": ju, "ju_name": format!("{}", ["水二局", "木三局", "金四局", "土五局", "火六局"][(ju - 2) as usize]),
        "direction": if fwd { "순행" } else { "역행" },
        "options": {"daxian_start": match opts.daxian_start { DaxianStart::Xusui => "xusui", DaxianStart::Manage => "manage" }, "dayun_start": opts.dayun_start},
        "daxian_first_age": dx_start,
        "xiaoxian_start": bz(xx0).to_string(),
        "dayun": {"month_pillar": month_pillar, "direction": if fwd { "순행" } else { "역행" }, "periods": dayun_list},
        "years": years,
    }))
}
