//! 한자 숫자 변환 (日·月·나이 표기용).

fn digit(c: char) -> Option<u32> {
    Some(match c {
        '一' => 1,
        '二' => 2,
        '三' => 3,
        '四' => 4,
        '五' => 5,
        '六' => 6,
        '七' => 7,
        '八' => 8,
        '九' => 9,
        _ => return None,
    })
}

/// 一..九, 十, 十N, N十, N十M (최대 99).
fn plain(s: &str) -> Option<u32> {
    let cs: Vec<char> = s.chars().collect();
    match cs.as_slice() {
        [] => None,
        [c] if *c == '十' => Some(10),
        [c] => digit(*c),
        ['十', b] => digit(*b).map(|v| 10 + v),
        [a, '十'] => digit(*a).map(|v| v * 10),
        [a, '十', b] => Some(digit(*a)? * 10 + digit(*b)?),
        _ => None,
    }
}

/// 初八=8, 初十=10, 廿一=21, 卅二=32, 十五=15, 七十三=73, 二十二=22.
pub fn cn_num(s: &str) -> Option<u32> {
    let mut it = s.chars();
    let first = it.next()?;
    let rest = it.as_str();
    match first {
        '初' => {
            let v = plain(rest)?;
            if (1..=10).contains(&v) {
                Some(v)
            } else {
                None
            }
        }
        '廿' => {
            if rest.is_empty() {
                Some(20)
            } else {
                Some(20 + digit(rest.chars().next().filter(|_| rest.chars().count() == 1)?)?)
            }
        }
        '卅' => {
            if rest.is_empty() {
                Some(30)
            } else {
                Some(30 + digit(rest.chars().next().filter(|_| rest.chars().count() == 1)?)?)
            }
        }
        _ => plain(s),
    }
}

/// 음력 월: 正=1, 冬=11, 臘=12, 十一=11, 十二=12. 1..=12 밖이면 None.
pub fn month_num(s: &str) -> Option<u32> {
    let v = match s {
        "正" => 1,
        "冬" => 11,
        "臘" => 12,
        _ => cn_num(s)?,
    };
    if (1..=12).contains(&v) {
        Some(v)
    } else {
        None
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn numbers() {
        assert_eq!(cn_num("初八"), Some(8));
        assert_eq!(cn_num("初十"), Some(10));
        assert_eq!(cn_num("廿一"), Some(21));
        assert_eq!(cn_num("卅二"), Some(32));
        assert_eq!(cn_num("十五"), Some(15));
        assert_eq!(cn_num("七十三"), Some(73));
        assert_eq!(cn_num("二十二"), Some(22));
        assert_eq!(cn_num("二十"), Some(20));
        assert_eq!(cn_num("三十"), Some(30));
        assert_eq!(cn_num("初"), None);
        assert_eq!(cn_num("□"), None);
    }
    #[test]
    fn months() {
        assert_eq!(month_num("正"), Some(1));
        assert_eq!(month_num("十一"), Some(11));
        assert_eq!(month_num("十二"), Some(12));
        assert_eq!(month_num("臘"), Some(12));
        assert_eq!(month_num("十三"), None);
    }
}
