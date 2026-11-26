# Claude Handoff: Rust Prompt Guard

**Repository:** `Gunny99/graphify`  
**Base:** `v8`  
**Work branch:** `feat/rust-prompt-guard`  
**Purpose:** add deterministic Rust validation around semantic-extraction prompts and LLM-produced graph fragments without rewriting the Python extraction pipeline.

## Findings that motivated this work

1. The semantic extraction prompt accepted arbitrary corpus content but did not explicitly establish a hard untrusted-data boundary. Prompt text can reduce risk, but cannot enforce model behavior.
2. Existing Python `validate_semantic_fragment` checks payload caps and ID syntax, while `merge-chunks` merges valid fragments and writes the merged output after processing. It does not enforce exact FILE_LIST provenance, nonzero coverage, confidence-score ranges, or graph-reference integrity. The Rust validator adds those checks as a separate gate; it is not yet wired into that merge path.
3. Rust is useful for deterministic validation and repeatable CI. It is not a replacement for the model's semantic extraction or a proof against prompt injection.

## Implemented in this branch

- `tools/prompt-guard/`: standalone Rust crate using `serde_json`.
- `validate`: validates chunk JSON against the exact per-chunk FILE_LIST and coverage report.
- `check-prompt`: enforces the presence of four explicit prompt safety invariants.
- Unit tests cover valid input, malformed JSON, path escape, zero/missing coverage, dangling edges, invalid file type, out-of-range confidence, duplicate IDs, empty allowlist, hyperedge cardinality regression (2-node hyperedges rejected; prompt requires 3+), and prompt-policy regression.
- `tools/prompt-guard/README.md`: build/run instructions and explicit limitations.

## Required next integration work

1. Add the untrusted-input boundary to `tools/skillgen/fragments/references/shared/extraction-spec.md`, then regenerate committed skill artifacts using `python -m tools.skillgen`; verify `python -m tools.skillgen --check`. Do not hand-edit generated outputs.
2. Add a CI job using stable Rust that runs `cargo test --manifest-path tools/prompt-guard/Cargo.toml` and `cargo run --manifest-path tools/prompt-guard/Cargo.toml -- check-prompt tools/skillgen/fragments/references/shared/extraction-spec.md`.
3. Before Part C merges chunk JSON, invoke the Rust validator for each chunk with that chunk's exact FILE_LIST. Preserve the existing Python pipeline as the orchestrator; do not make Rust a hard runtime dependency until a cross-platform packaging strategy exists.
4. For coverage, compare model-reported counts against independently measured line/page counts. A JSON validator alone cannot establish truthful reading.
5. Test failure behavior: any invalid chunk must be rejected before merge/cache mutation; do not silently accept a partial set.

## Commands

```sh
cargo test --manifest-path tools/prompt-guard/Cargo.toml
cargo run --manifest-path tools/prompt-guard/Cargo.toml -- check-prompt tools/skillgen/fragments/references/shared/extraction-spec.md
python -m tools.skillgen --check
pytest tests/test_skillgen.py tests/test_skillgen_input_path_injection.py -q
```

## Current test status

The authoring environment used for this handoff has no `rustc` or `cargo` executable. Rust tests have therefore **not** been run locally. The PR currently has no GitHub Actions workflow run or status check visible, so compilation and tests remain **unverified**. Do not describe the Rust code as passing until a real toolchain run completes. Existing Python tests were not run as part of this change.

The crate currently has no committed `Cargo.lock`. Once a Rust toolchain is available, generate and commit the lockfile, then change CI to `cargo test --locked` for reproducible dependency resolution.

## Review focus for Claude

- Schema inspection against the `v8` extraction prompt confirms: `file_type` is one of exactly six values; each node/edge/hyperedge has `source_file`; every edge and hyperedge has `confidence_score`; hyperedges are specified for 3+ nodes; coverage is an integer line count or PDF page count for every FILE_LIST path. The Rust validator's 2-node hyperedge allowance was therefore tightened to 3+ and a regression test was added.
- The Python prompt's `coverage` counts are model-reported, not independently verified. PDF values mean pages, not lines. A separate file/page-length comparison is still needed if completeness is to be asserted.
- `merge-chunks` already calls Python `load_validated_semantic_fragment` before accumulating each chunk and only writes the output after the loop; the Rust validator is not yet called there. Review the `merge-semantic` and cache write paths separately before proposing runtime integration.
- Check that validation runs before any merge/cache writes.
- Check whether requiring confidence scores on every edge/hyperedge matches all supported extraction producers.
- Check that prompt safety language is generated from the fragment source, not edited only in rendered artifacts.
- Do not claim this eliminates prompt injection. It adds deterministic validation and an explicit model instruction boundary.
