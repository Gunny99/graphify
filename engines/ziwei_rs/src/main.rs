use std::process::exit;
use ziwei_rs::{build_chart, build_timeline, DaxianStart, Input, TimelineOpts};

fn die(msg: &str) -> ! {
    eprintln!("{msg}");
    exit(2)
}

fn main() {
    let a: Vec<String> = std::env::args().skip(1).collect();
    if a.len() < 2 {
        die("사용: zw chart <json> | zw hour <json> [--no-eot] | zw timeline <json> [--daxian-start xusui|manage] [--dayun-start N]");
    }
    if a[0] == "hour" {
        let si: ziwei_rs::solar::SolarInput = serde_json::from_str(&a[1]).unwrap_or_else(|e| die(&format!("입력 JSON 오류: {e}")));
        let eot = !a[2..].iter().any(|x| x == "--no-eot");
        match ziwei_rs::solar::solar_hour(&si, eot) {
            Ok(v) => println!("{}", serde_json::to_string_pretty(&v).unwrap()),
            Err(e) => die(&e),
        }
        return;
    }
    let inp: Input = serde_json::from_str(&a[1]).unwrap_or_else(|e| die(&format!("입력 JSON 오류: {e}")));
    let out = match a[0].as_str() {
        "chart" => build_chart(&inp),
        "timeline" => {
            let mut o = TimelineOpts::default();
            let mut i = 2;
            while i < a.len() {
                let v = a.get(i + 1).unwrap_or_else(|| die("옵션 값 없음"));
                match a[i].as_str() {
                    "--daxian-start" => {
                        o.daxian_start = match v.as_str() {
                            "xusui" => DaxianStart::Xusui,
                            "manage" => DaxianStart::Manage,
                            _ => die("--daxian-start 는 xusui|manage"),
                        }
                    }
                    "--dayun-start" => o.dayun_start = Some(v.parse().unwrap_or_else(|_| die("--dayun-start 는 정수"))),
                    x => die(&format!("모르는 옵션 {x}")),
                }
                i += 2;
            }
            build_timeline(&inp, o)
        }
        _ => die("명령은 chart | timeline"),
    };
    match out {
        Ok(v) => println!("{}", serde_json::to_string_pretty(&v).unwrap()),
        Err(e) => die(&e),
    }
}
