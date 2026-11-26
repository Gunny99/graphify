//! 자미두수 명반(chart)과 해마다 운 표지(timeline).
//! 기준: engines/ziwei_saju/engine_v2 의 chart.py·common.py·tables.py. 판정·해석은 하지 않는다.
pub mod chart;
pub mod common;
pub mod solar;
pub mod timeline;
pub mod validate;

pub use chart::{build_chart, Input};
pub use timeline::{build_timeline, DaxianStart, TimelineOpts};

/// 정규화 JSON 문자열: 키 정렬, 공백 없음, 비ASCII 그대로(Python json.dumps(sort_keys, ensure_ascii=False, separators=(',',':'))와 같다).
pub fn canonical(v: &serde_json::Value) -> String {
    let mut s = String::new();
    canon(v, &mut s);
    s
}

fn canon(v: &serde_json::Value, out: &mut String) {
    use serde_json::Value::{Array, Object};
    match v {
        Object(m) => {
            let mut keys: Vec<&String> = m.keys().collect();
            keys.sort();
            out.push('{');
            for (i, k) in keys.iter().enumerate() {
                if i > 0 {
                    out.push(',');
                }
                out.push_str(&serde_json::to_string(k).unwrap());
                out.push(':');
                canon(&m[*k], out);
            }
            out.push('}');
        }
        Array(a) => {
            out.push('[');
            for (i, x) in a.iter().enumerate() {
                if i > 0 {
                    out.push(',');
                }
                canon(x, out);
            }
            out.push(']');
        }
        other => out.push_str(&serde_json::to_string(other).unwrap()),
    }
}
