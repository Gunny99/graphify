//! 달밭(dalbat1) 블로그 원문 색인기. 사용법: dalbat-index <01_raw 경로> <출력 md 경로>
//! 각 dalbat1_<카테고리>/NNN_<글ID>_<제목>.txt 를 읽어 카테고리별 목록(번호|제목|자수)을 만든다.
//! 디렉터리·항목·파일을 읽지 못하면 건너뛰거나 0자로 세지 않고 오류로 종료한다.
//! UTF-8이 아닌 바이트는 대체 문자로 센다.
use std::{env, fmt::Display, fs, path::Path, process};

fn die(what: &str, path: &Path, e: impl Display) -> ! {
    eprintln!("{what} failed: {}: {e}", path.display());
    process::exit(1);
}

/// 디렉터리 항목을 모두 읽는다. 읽지 못한 항목이 하나라도 있으면 종료한다.
fn entries(dir: &Path) -> Vec<fs::DirEntry> {
    let rd = fs::read_dir(dir).unwrap_or_else(|e| die("read_dir", dir, e));
    let mut v: Vec<_> = rd
        .map(|e| e.unwrap_or_else(|e| die("read entry", dir, e)))
        .collect();
    v.sort_by_key(|e| e.file_name());
    v
}

fn main() {
    let a: Vec<String> = env::args().collect();
    if a.len() < 3 {
        eprintln!("usage: dalbat-index <01_raw> <out.md>");
        process::exit(2);
    }
    let root = Path::new(&a[1]);
    let cats: Vec<_> = entries(root)
        .into_iter()
        .filter(|e| e.file_name().to_string_lossy().starts_with("dalbat1_"))
        .collect();
    let mut out = String::from("# 달밭(dalbat1) 블로그 원문 색인\n\n2차 자료(네이버 블로그 번역·해설). 원문은 프로젝트 공유 폴더 ZWDS_LIBRARY/01_raw/dalbat1_<카테고리>/ 에 있고 이 표는 그 파일의 번호·제목·자수를 옮긴 것이다(글ID·작성일은 카테고리별 00_목록.md). 생성: dalbat-index.\n\n");
    let (mut tn, mut tc) = (0usize, 0usize);
    for c in cats {
        let name = c.file_name().to_string_lossy().replace("dalbat1_", "");
        let files: Vec<_> = entries(&c.path())
            .into_iter()
            .filter(|e| {
                let n = e.file_name().to_string_lossy().to_string();
                n.ends_with(".txt") && n.chars().take(3).all(|ch| ch.is_ascii_digit())
            })
            .collect();
        let mut sec = String::new();
        let mut chars = 0usize;
        for f in &files {
            let fname = f.file_name().to_string_lossy().to_string();
            let path = f.path();
            let bytes = fs::read(&path).unwrap_or_else(|e| die("read", &path, e));
            let n = String::from_utf8_lossy(&bytes).chars().count();
            chars += n;
            let mut it = fname.trim_end_matches(".txt").splitn(3, '_');
            let (no, _id, title) = (it.next().unwrap_or(""), it.next().unwrap_or(""), it.next().unwrap_or(""));
            sec.push_str(&format!("{no}|{}|{n}\n", title.replace('|', "/")));
        }
        out.push_str(&format!(
            "## {name} (글 {}편, {chars}자)\n\n번호|제목|자수\n---|---|---\n{sec}\n",
            files.len()
        ));
        tn += files.len();
        tc += chars;
    }
    out.push_str(&format!("합계 {tn}편, {tc}자\n"));
    let dst = Path::new(&a[2]);
    fs::write(dst, out).unwrap_or_else(|e| die("write", dst, e));
    println!("{tn} files, {tc} chars");
}
