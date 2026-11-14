**Step B2 - Dispatch ALL subagents in a single message (OpenCode)**

> **OpenCode platform:** Uses `@mention` dispatch instead of the Agent tool. All mentions in a single message run in parallel.

Before dispatching, resolve the project working directory — the directory containing the `graphify-out/` folder where Step B3 runs. Build each chunk path from the canonical project root and output directory. Reject a symlinked output directory or chunk file; do not let an output path escape the project root. Format the chunk number as a two-digit integer rather than prefixing a literal zero:

```bash
# Set CHUNK_NUM to the integer assigned in Step B1 (1, 2, ...).
GRAPHIFY_PYTHON="$(cat graphify-out/.graphify_python)"
CHUNK_PATH="$("$GRAPHIFY_PYTHON" -c 'import sys; from pathlib import Path; root=Path.cwd().resolve(); out=root / "graphify-out"; assert not out.is_symlink(), "graphify-out must not be a symlink"; out.mkdir(exist_ok=True); out=out.resolve(strict=True); assert out.parent == root, "graphify-out resolves outside the project root"; number=int(sys.argv[1]); assert number > 0, "chunk number must be positive"; target=out / f".graphify_chunk_{number:02d}.json"; assert not target.is_symlink(), "chunk output must not be a symlink"; print(target)' "$CHUNK_NUM")"
```

Run the command separately for each chunk and substitute that chunk's resulting absolute `CHUNK_PATH` into its worker prompt.

Dispatch one `@mention` per chunk — ALL in the same response. Do not dispatch a second batch while the first is still running:

```
@agent Chunk CHUNK_NUM of TOTAL_CHUNKS: [extraction prompt with FILE_LIST, CHUNK_NUM, TOTAL_CHUNKS, DEEP_MODE, and this chunk's absolute CHUNK_PATH substituted]

@agent Chunk 2 of TOTAL_CHUNKS: [next chunk, with its own CHUNK_PATH]
```

**Use the same chunk-result handoff as every other platform.** Each worker must receive the exact extraction prompt with its own `CHUNK_PATH` substituted and should write its JSON result there as instructed. Workers must not aggregate results or write the shared semantic output.

After all mentions complete, associate each response with the chunk number used to dispatch it. For every chunk:
1. Check the expected `graphify-out/.graphify_chunk_NN.json` file. Parse it and require object-valued `nodes` and `edges` lists; `hyperedges` must be omitted or a list of objects; `coverage` must map string file paths to nonnegative integer line counts; and `input_tokens` and `output_tokens` must be nonnegative integers (booleans are not integers for this check). Empty `nodes` and `edges` lists are valid results.
2. If the file is absent or invalid but the worker returned a valid JSON response in the conversation, write or replace the chunk's expected file with that response as a fallback. Then read the file back and validate it again.
3. Preserve that chunk's `nodes`, `edges`, `hyperedges`, `input_tokens`, `output_tokens`, and `coverage` values. Never combine fields across chunks or substitute the same result for multiple chunks.
4. If neither the worker file nor its returned response is valid and persistable, report that chunk as failed and leave its expected file absent. Do not invent an empty success result.

Let the shared Step B3 apply the common missing/failed-chunk policy and retry guidance. **Do not** accumulate responses into `graphify-out/.graphify_semantic_new.json` in B2. Step B3 is the only stage that aggregates chunk files, updates the semantic cache, and produces the merged semantic result.

Subagent prompt template:

See `references/extraction-spec.md` for the exact subagent prompt (JSON schema, node-ID rules, confidence rubric, frontmatter, hyperedge, and vision rules). Load it only here, only when at least one chunk holds a doc, paper, or image; a pure-code corpus has skipped Part B and never reads it. Pass each agent that prompt verbatim with FILE_LIST, CHUNK_NUM, TOTAL_CHUNKS, DEEP_MODE, and its own absolute CHUNK_PATH substituted.
