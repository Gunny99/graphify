//! common.py 상수와 궁 셈.
pub const BR: &str = "子丑寅卯辰巳午未申酉戌亥";
pub const STEM: &str = "甲乙丙丁戊己庚辛壬癸";
pub const HUA: [&str; 4] = ["록", "권", "과", "기"];
pub const MAIN14: [&str; 14] = ["자미", "천기", "태양", "무곡", "천동", "염정", "천부", "태음", "탐랑", "거문", "천상", "천량", "칠살", "파군"];
pub const YUKGIL: [&str; 6] = ["좌보", "우필", "문창", "문곡", "천괴", "천월"];
pub const SAL: [&str; 6] = ["경양", "타라", "화성", "영성", "지공", "지겁"];
pub const PAL_ROLES: [&str; 12] = ["명", "형제", "부처", "자녀", "재백", "질액", "천이", "노복", "관록", "전택", "복덕", "부모"];
pub const CHANGSHENG: [&str; 12] = ["장생", "목욕", "관대", "임관", "제왕", "쇠", "병", "사", "묘", "절", "태", "양"];

/// 五虎遁(calendar.py TIGER): 연간 → 寅月 천간.
pub fn tiger(stem: char) -> char {
    match stem {
        '甲' | '己' => '丙',
        '乙' | '庚' => '戊',
        '丙' | '辛' => '庚',
        '丁' | '壬' => '壬',
        _ => '甲',
    }
}

pub fn ch(s: &str, i: usize) -> char {
    s.chars().nth(i).expect("index")
}
pub fn pos_in(s: &str, c: char) -> Option<usize> {
    s.chars().position(|x| x == c)
}
pub fn bi(z: char) -> i64 {
    pos_in(BR, z).expect("지지") as i64
}
pub fn bz(i: i64) -> char {
    ch(BR, i.rem_euclid(12) as usize)
}
pub fn si(s: char) -> usize {
    pos_in(STEM, s).expect("천간")
}
pub fn yang_stem(s: char) -> bool {
    si(s) % 2 == 0
}
pub fn gz60(i: i64) -> String {
    let i = i.rem_euclid(60) as usize;
    format!("{}{}", ch(STEM, i % 10), ch(BR, i % 12))
}
/// 간지 → 60갑자 번호. 음양이 맞지 않으면 None(Python은 StopIteration).
pub fn k60(s: char, b: char) -> Option<usize> {
    (0..60).find(|&i| ch(STEM, i % 10) == s && ch(BR, i % 12) == b)
}
/// roles_from: 명궁 지지 → 각 지지의 궁 이름.
pub fn role_of(ming: char, z: char) -> &'static str {
    // bz(ming - k) = z  →  k = ming - z
    PAL_ROLES[(bi(ming) - bi(z)).rem_euclid(12) as usize]
}
