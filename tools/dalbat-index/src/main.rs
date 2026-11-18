//! 달밭(dalbat1) 블로그 원문 색인기. 사용법: dalbat-index <01_raw 경로> <출력 md 경로>
//! 각 dalbat1_<카테고리>/NNN_<글ID>_<제목>.txt 를 읽어 카테고리별 표(번호·글ID·제목·작성일·자수)를 만든다.
use std::{env, fs, path::Path};

fn main() {
    let a: Vec<String> = env::args().collect();
    if a.len() < 3 {
        eprintln!("usage: dalbat-index <01_raw> <out.md>");
        std::process::exit(2);
    }
    let mut cats: Vec<_> = fs::read_dir(&a[1])
        .expect("01_raw")
        .filter_map(|e| e.ok())
        .filter(|e| e.file_name().to_string_lossy().starts_with("dalbat1_"))
        .collect();
    cats.sort_by_key(|e| e.file_name());
    let mut out = String::from("# 달밭(dalbat1) 블로그 원문 색인\n\n2차 자료(네이버 블로그 번역·해설). 원문은 프로젝트 공유 폴더 ZWDS_LIBRARY/01_raw/dalbat1_<카테고리>/ 에 있고 이 표는 그 파일의 번호·제목·자수를 옮긴 것이다. 생성: dalbat-index.\n\n");
    let (mut tn, mut tc) = (0usize, 0usize);
    for c in cats {
        let name = c.file_name().to_string_lossy().replace("dalbat1_", "");
        let mut fs_: Vec<_> = fs::read_dir(c.path())
            .unwrap()
            .filter_map(|e| e.ok())
            .filter(|e| {
                let n = e.file_name().to_string_lossy().to_string();
                n.ends_with(".txt") && n.chars().take(3).all(|ch| ch.is_ascii_digit())
            })
            .collect();
        fs_.sort_by_key(|e| e.file_name());
        let mut sec = String::new();
        let mut chars = 0usize;
        for f in &fs_ {
            let fname = f.file_name().to_string_lossy().to_string();
            let body = fs::read_to_string(f.path()).unwrap_or_default();
            let n = body.chars().count();
            chars += n;
            let mut it = fname.trim_end_matches(".txt").splitn(3, '_');
            let (no, id, title) = (it.next().unwrap_or(""), it.next().unwrap_or(""), it.next().unwrap_or(""));
            let date = body.lines().find_map(|l| l.strip_prefix("작성일:")).unwrap_or("").trim();
            sec.push_str(&format!("| {no} | {id} | {} | {date} | {n} |\n", title.replace('|', "/")));
        }
        out.push_str(&format!("## {name} (글 {}편, {chars}자)\n\n| 번호 | 글ID | 제목 | 작성일 | 자수 |\n|---|---|---|---|---|\n{sec}\n", fs_.len()));
        tn += fs_.len();
        tc += chars;
    }
    out.push_str(&format!("합계 {tn}편, {tc}자\n"));
    let p = Path::new(&a[2]);
    fs::write(p, out).expect("write");
    println!("{tn} files, {tc} chars");
}
