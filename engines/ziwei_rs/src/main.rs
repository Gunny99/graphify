use std::process::exit;
use ziwei_rs::{build_chart, build_timeline, DaxianStart, Input, TimelineOpts};

fn die(msg: &str) -> ! {
    eprintln!("{msg}");
    exit(2)
}

/// 규칙이 명시되지 않은 선택 항목이 있으면(결과가 갈리는 것만) 표준오류에 경고와 choices를 낸다.
fn warn_choices(v: &serde_json::Value) {
    let Some(cs) = v["choices"].as_array() else { return };
    let pending: Vec<&serde_json::Value> = cs.iter().filter(|c| c["chosen"].is_null() && c["same_result"] != true).collect();
    if !pending.is_empty() {
        let kinds: Vec<&str> = pending.iter().filter_map(|c| c["kind"].as_str()).collect();
        eprintln!("경고: 고객 선택 필요({}). 기본값으로 계산했다. choices: {}", kinds.join(", "), serde_json::to_string(cs).unwrap());
    }
}

fn main() {
    let a: Vec<String> = std::env::args().skip(1).collect();
    if a.len() < 2 {
        die("사용: zw chart <json> | zw hour <json> [--no-eot] | zw timeline <json> [--daxian-start xusui|manage] [--dayun-start N]");
    }
    if a[0] == "backtest" {
        // zw backtest <cases.json> <rules.json> <out_dir> --frame A|B
        if a.len() < 4 {
            die("사용: zw backtest <cases.json> <rules.json> <out_dir> --frame A|B");
        }
        let opt = |k: &str| a.iter().position(|x| x == k).and_then(|i| a.get(i + 1)).cloned();
        let frame = match opt("--frame").as_deref() {
            Some("A") => ziwei_rs::backtest::Frame::A,
            Some("B") => ziwei_rs::backtest::Frame::B,
            _ => die("--frame A|B 가 필요하다"),
        };
        match ziwei_rs::backtest::run(&a[1], &a[2], &a[3], frame) {
            Ok(m) => println!("{m}"),
            Err(e) => die(&e),
        }
        return;
    }
    if a[0] == "validate-cases" {
        let out = a.get(2).unwrap_or_else(|| die("사용: zw validate-cases <cases.json> <out_dir>"));
        match ziwei_rs::validate::run(&a[1], out, a.iter().any(|x| x == "--variant") && a.iter().any(|x| x == "quanshu")) {
            Ok(m) => println!("{m}"),
            Err(e) => die(&e),
        }
        return;
    }
    if a[0] == "hour" {
        let si: ziwei_rs::solar::SolarInput = serde_json::from_str(&a[1]).unwrap_or_else(|e| die(&format!("입력 JSON 오류: {e}")));
        let eot = !a[2..].iter().any(|x| x == "--no-eot");
        match ziwei_rs::solar::solar_hour(&si, eot) {
            Ok(v) => {
                warn_choices(&v);
                println!("{}", serde_json::to_string_pretty(&v).unwrap())
            }
            Err(e) => die(&e),
        }
        return;
    }
    let mut inp: Input = serde_json::from_str(&a[1]).unwrap_or_else(|e| die(&format!("입력 JSON 오류: {e}")));
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
                            "quanshu" => DaxianStart::Quanshu,
                            _ => die("--daxian-start 는 xusui|manage|quanshu"),
                        }
                    }
                    "--variant" => {
                        inp.variant = Some(v.clone());
                        if !a.iter().any(|x| x == "--daxian-start") && v == "quanshu" {
                            o.daxian_start = DaxianStart::Quanshu;
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
        Ok(v) => {
            warn_choices(&v);
            println!("{}", serde_json::to_string_pretty(&v).unwrap())
        }
        Err(e) => die(&e),
    }
}
