use graphify_prompt_guard::{check_prompt_safety, validate_extraction};
use std::{env, fs, process};

fn usage() -> ! {
    eprintln!(
        "Usage:\n  graphify-prompt-guard validate <file-list.txt> <chunk.json>\n  graphify-prompt-guard check-prompt <extraction-spec.md>\n\nfile-list.txt contains one exact absolute FILE_LIST path per line."
    );
    process::exit(2);
}

fn fail(errors: Vec<String>) -> ! {
    for error in errors {
        eprintln!("ERROR: {error}");
    }
    process::exit(1);
}

fn main() {
    let args: Vec<String> = env::args().collect();
    if args.len() < 2 { usage(); }

    match args[1].as_str() {
        "validate" => {
            if args.len() != 4 { usage(); }
            let file_list = fs::read_to_string(&args[2]).unwrap_or_else(|error| {
                eprintln!("ERROR: cannot read file list: {error}");
                process::exit(2);
            });
            let allowed: Vec<String> = file_list
                .lines()
                .map(str::trim_end)
                .filter(|line| !line.trim().is_empty())
                .map(str::to_owned)
                .collect();
            let input_path = args.get(3).unwrap_or_else(|| usage());
            let input = fs::read_to_string(input_path).unwrap_or_else(|error| {
                eprintln!("ERROR: cannot read extraction JSON: {error}");
                process::exit(2);
            });
            match validate_extraction(&input, &allowed) {
                Ok(()) => println!("OK: extraction schema, provenance, coverage, and graph references are valid"),
                Err(errors) => fail(errors),
            }
        }
        "check-prompt" => {
            if args.len() != 3 { usage(); }
            let prompt = fs::read_to_string(&args[2]).unwrap_or_else(|error| {
                eprintln!("ERROR: cannot read prompt: {error}");
                process::exit(2);
            });
            match check_prompt_safety(&prompt) {
                Ok(()) => println!("OK: all required prompt safety invariants are present"),
                Err(errors) => fail(errors),
            }
        }
        _ => usage(),
    }
}
