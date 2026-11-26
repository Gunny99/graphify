# Graphify Prompt Guard (Rust)

A small, dependency-light Rust validator for the boundary between LLM semantic extraction and Graphify's deterministic merge pipeline.

## What it enforces

- Valid JSON object with required `nodes`, `edges`, and `coverage` structures.
- Every emitted node, edge, and hyperedge cites an exact path from the chunk's input FILE_LIST.
- Every FILE_LIST path has a coverage entry; no graph item may cite a path reported with zero coverage.
- Allowed `file_type` and confidence enums, finite confidence scores in `[0, 1]`, unique node IDs, valid edge references, and hyperedges with at least three existing node IDs (matching the extraction prompt).
- Required prompt-level untrusted-input safety statements remain present in the extraction specification.

This is deterministic post-generation validation. It does **not** prove that a model ignored a prompt injection, that a cited fact is semantically true, or that the model read every source line. Coverage values remain model-reported; compare them with independently measured file/page lengths before treating them as proof.

## Run

From the repository root:

```sh
cargo test --manifest-path tools/prompt-guard/Cargo.toml
cargo run --manifest-path tools/prompt-guard/Cargo.toml -- check-prompt tools/skillgen/fragments/references/shared/extraction-spec.md
printf '%s\n' '/absolute/path/a.md' '/absolute/path/b.md' > /tmp/graphify-files.txt
cargo run --manifest-path tools/prompt-guard/Cargo.toml -- validate /tmp/graphify-files.txt /path/to/chunk.json
```

The validator is a development/CI gate in this change. It is not yet linked into the installed Python runtime; doing that safely requires a packaging and cross-platform binary-distribution decision.
