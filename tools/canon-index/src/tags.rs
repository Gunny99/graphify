//! norm 문자열에서 낱말 태그(범주, 낱말, char offset)를 찾는다.
use serde::Serialize;

pub const STAR: &[&str] = &[
    "紫微", "天機", "太陽", "武曲", "天同", "廉貞", "天府", "太陰", "貪狼", "巨門", "天相", "天梁",
    "七殺", "破軍", "文昌", "文曲", "左輔", "右弼", "天魁", "天鉞", "祿存", "天馬", "擎羊", "陀羅",
    "火星", "鈴星", "地劫", "天空", "地空", "化祿", "化權", "化科", "化忌", "天刑", "天姚", "天傷",
    "天使", "截空", "旬空",
];
/// 한 글자 낱말은 이웃에 宮/垣이 있을 때만 태그한다(오탐 방지).
pub const PALACE: &[&str] = &[
    "命", "身", "兄弟", "妻", "夫", "子女", "子息", "財帛", "疾厄", "遷移", "奴僕", "官祿", "田宅",
    "福德", "父母", "夫妻",
];
pub const TIMING: &[&str] = &[
    "大限", "小限", "流年", "太歲", "歲限", "童限", "二限", "限", "斗君", "流羊", "流陀", "流祿",
    "行限", "運",
];
pub const EVENT: &[&str] = &[
    "死", "亡", "夭", "故", "卒", "刑", "傷", "災", "病", "疾", "婚", "娶", "嫁", "生男", "生女",
    "剋", "尅", "財", "發", "破", "敗", "官", "科甲", "登科", "及第", "貴", "訟", "獄", "離鄉",
    "遭配", "壽",
];

#[derive(Serialize, Debug, Clone, PartialEq)]
pub struct Tag {
    pub c: &'static str,
    pub w: &'static str,
    pub o: usize,
    /// 한글 표면형으로 찾은 경우 그 표면형(w는 대응 한자 낱말).
    #[serde(skip_serializing_if = "Option::is_none")]
    pub k: Option<&'static str>,
}

/// 한글 낱말 -> (범주, 한자 낱말). 달밭 해설용.
pub const HANGUL: &[(&str, &str, &str)] = &[
    ("대한", "timing", "大限"), ("소한", "timing", "小限"), ("유년", "timing", "流年"),
    ("태세", "timing", "太歲"), ("세한", "timing", "歲限"), ("동한", "timing", "童限"),
    ("이한", "timing", "二限"), ("행한", "timing", "行限"), ("두군", "timing", "斗君"),
    ("유양", "timing", "流羊"), ("유타", "timing", "流陀"), ("유록", "timing", "流祿"),
    ("대운", "timing", "運"), ("유운", "timing", "運"),
    ("화기", "star", "化忌"), ("화록", "star", "化祿"), ("화권", "star", "化權"), ("화과", "star", "化科"),
    ("자미", "star", "紫微"), ("천기", "star", "天機"), ("태양", "star", "太陽"), ("무곡", "star", "武曲"),
    ("천동", "star", "天同"), ("염정", "star", "廉貞"), ("천부", "star", "天府"), ("태음", "star", "太陰"),
    ("탐랑", "star", "貪狼"), ("거문", "star", "巨門"), ("천상", "star", "天相"), ("천량", "star", "天梁"),
    ("칠살", "star", "七殺"), ("파군", "star", "破軍"), ("문창", "star", "文昌"), ("문곡", "star", "文曲"),
    ("좌보", "star", "左輔"), ("우필", "star", "右弼"), ("천괴", "star", "天魁"), ("천월", "star", "天鉞"),
    ("녹존", "star", "祿存"), ("천마", "star", "天馬"), ("경양", "star", "擎羊"), ("타라", "star", "陀羅"),
    ("화성", "star", "火星"), ("영성", "star", "鈴星"), ("지겁", "star", "地劫"), ("천공", "star", "天空"),
    ("지공", "star", "地空"),
    ("명궁", "palace", "命"), ("신궁", "palace", "身"), ("형제궁", "palace", "兄弟"), ("부처궁", "palace", "夫妻"),
    ("자녀궁", "palace", "子女"), ("재백궁", "palace", "財帛"), ("질액궁", "palace", "疾厄"),
    ("천이궁", "palace", "遷移"), ("노복궁", "palace", "奴僕"), ("교우궁", "palace", "奴僕"),
    ("관록궁", "palace", "官祿"), ("전택궁", "palace", "田宅"), ("복덕궁", "palace", "福德"),
    ("부모궁", "palace", "父母"),
    ("사망", "event", "死"), ("요절", "event", "夭"), ("질병", "event", "病"), ("재앙", "event", "災"),
    ("재난", "event", "災"), ("혼인", "event", "婚"), ("결혼", "event", "婚"), ("파재", "event", "破"),
    ("소송", "event", "訟"), ("옥살이", "event", "獄"), ("수명", "event", "壽"), ("부상", "event", "傷"),
    ("형극", "event", "剋"), ("재물", "event", "財"), ("발복", "event", "發"), ("귀격", "event", "貴"),
];

fn find_all(hay: &str, byte_to_char: &[usize], needle: &str, mut f: impl FnMut(usize, usize)) {
    let mut from = 0;
    while let Some(p) = hay[from..].find(needle) {
        let b = from + p;
        f(b, byte_to_char[b]);
        // 다음 글자 경계로 전진(겹침 허용)
        from = b + hay[b..].chars().next().map(|c| c.len_utf8()).unwrap_or(1);
        if from >= hay.len() {
            break;
        }
    }
}

pub fn find_tags(norm: &str) -> Vec<Tag> {
    let mut byte_to_char = vec![0usize; norm.len() + 1];
    let chars: Vec<char> = norm.chars().collect();
    let mut ci = 0;
    for (b, _) in norm.char_indices() {
        byte_to_char[b] = ci;
        ci += 1;
    }
    byte_to_char[norm.len()] = ci;
    let mut out = Vec::new();
    let sets: [(&'static str, &[&'static str]); 4] =
        [("star", STAR), ("palace", PALACE), ("timing", TIMING), ("event", EVENT)];
    for (cat, words) in sets {
        for w in words {
            let wl = w.chars().count();
            find_all(norm, &byte_to_char, w, |_, co| {
                if cat == "palace" && wl == 1 {
                    let before = co.checked_sub(1).map(|i| chars[i]);
                    let after = chars.get(co + 1).copied();
                    let ok = |c: Option<char>| matches!(c, Some('宮') | Some('垣'));
                    if !(ok(before) || ok(after)) {
                        return;
                    }
                }
                out.push(Tag { c: cat, w, o: co, k: None });
            });
        }
    }
    if norm.chars().any(|c| ('\u{AC00}'..='\u{D7A3}').contains(&c)) {
        for (k, cat, w) in HANGUL {
            find_all(norm, &byte_to_char, k, |_, co| {
                out.push(Tag { c: cat, w, o: co, k: Some(k) });
            });
        }
    }
    out.sort_by(|a, b| a.o.cmp(&b.o).then(a.c.cmp(b.c)).then(a.w.cmp(b.w)));
    out
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn basic_tags() {
        let t = find_tags("紫微化祿坐命宮大限遇擎羊而死");
        assert!(t.contains(&Tag { c: "star", w: "紫微", o: 0, k: None }));
        assert!(t.contains(&Tag { c: "star", w: "化祿", o: 2, k: None }));
        assert!(t.contains(&Tag { c: "palace", w: "命", o: 5, k: None }));
        assert!(t.contains(&Tag { c: "timing", w: "大限", o: 7, k: None }));
        assert!(t.contains(&Tag { c: "timing", w: "限", o: 8, k: None }));
        assert!(t.contains(&Tag { c: "event", w: "死", o: 13, k: None }));
    }
    #[test]
    fn hangul_tags() {
        let t = find_tags("대한 화기와 사망");
        assert!(t.iter().any(|x| x.w == "大限" && x.k == Some("대한") && x.o == 0));
        assert!(t.iter().any(|x| x.w == "化忌" && x.c == "star"));
        assert!(t.iter().any(|x| x.w == "死" && x.c == "event"));
    }
    #[test]
    fn single_char_palace_needs_gong() {
        let t = find_tags("身命子妻");
        assert!(t.iter().all(|x| x.c != "palace"));
        let t = find_tags("身宮在妻垣");
        assert!(t.iter().any(|x| x.w == "身" && x.o == 0));
        assert!(t.iter().any(|x| x.w == "妻" && x.o == 3));
    }
}
