//! Python engine_v2 chart.build / place_stars / kong 대조 (golden: tests/golden/gen.py 로 생성).
use serde_json::Value;
use ziwei_rs::{build_chart, canonical, Input};

fn fnv(s: &str) -> String {
    let mut h: u64 = 0xcbf29ce484222325;
    for b in s.bytes() {
        h = (h ^ b as u64).wrapping_mul(0x100000001b3);
    }
    format!("{h:016x}")
}

#[test]
fn chart_matches_python_golden() {
    let g: Value = serde_json::from_str(include_str!("golden/chart_golden.json")).unwrap();
    let cases = g["cases"].as_array().unwrap();
    assert!(cases.len() >= 2000, "golden 사례 수 {}", cases.len());
    let mut full = 0;
    for (i, c) in cases.iter().enumerate() {
        let inp: Input = serde_json::from_value(c["input"].clone()).unwrap();
        let ch = build_chart(&inp).unwrap();
        let ctx = format!("case {i} {}", c["input"]);
        assert_eq!(ch["pos"], c["pos"], "pos {ctx}");
        // 별 순서까지: pos 키 순서와 palaces 별 배열 순서는 Python dict 삽입 순서를 따른다
        let a: Vec<&String> = ch["pos"].as_object().unwrap().keys().collect();
        let b: Vec<&String> = c["pos"].as_object().unwrap().keys().collect();
        assert_eq!(a, b, "pos 순서 {ctx}");
        assert_eq!(ch["ming"], c["ming"], "ming {ctx}");
        assert_eq!(ch["shen"], c["shen"], "shen {ctx}");
        assert_eq!(ch["ju"], c["ju"], "ju {ctx}");
        assert_eq!(ch["kong"], c["kong"], "kong {ctx}");
        for (z, st) in c["stems"].as_object().unwrap() {
            assert_eq!(ch["palaces"][z]["stem"], *st, "stem {z} {ctx}");
        }
        assert_eq!(fnv(&canonical(&ch)), c["hash"].as_str().unwrap(), "chart 전체 해시 {ctx}");
        if let Some(full_chart) = c.get("chart") {
            assert_eq!(canonical(&ch), canonical(full_chart), "chart 전체 {ctx}");
            full += 1;
        }
    }
    assert!(full >= 20);
}

#[test]
fn sample_chart_is_sane() {
    let inp: Input = serde_json::from_str(r#"{"year_gz":"己丑","month":3,"day":15,"hour":"戌","male":true,"leap":false}"#).unwrap();
    let ch = build_chart(&inp).unwrap();
    assert_eq!(ch["ming"], "午");
    assert_eq!(ch["ju_name"], "土五局");
    assert_eq!(ch["direction"], "역행");
}

#[test]
fn bad_input_is_error() {
    for s in [
        r#"{"year_gz":"甲丑","month":3,"day":15,"hour":"戌","male":true}"#,
        r#"{"year_gz":"己丑","month":13,"day":15,"hour":"戌","male":true}"#,
        r#"{"year_gz":"己丑","month":3,"day":31,"hour":"戌","male":true}"#,
        r#"{"year_gz":"己丑","month":3,"day":15,"hour":"X","male":true}"#,
    ] {
        let inp: Input = serde_json::from_str(s).unwrap();
        assert!(build_chart(&inp).is_err(), "{s}");
    }
}
