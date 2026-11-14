**Step B2 - Dispatch subagents and paste their responses**

> **No automated subagent tool:** this host has no parallel Agent/Task API, so
> extraction is driven by hand. Dispatch a subagent per chunk however the host
> allows (a fresh conversation, a parallel pane), then paste each response back.

For each chunk of uncached files (20-25 per chunk), resolve a unique absolute output path before dispatching. CHUNK_PATH must be an **absolute** path.

```bash
PROJECT_ROOT=$(pwd)  # cwd — where Step B3 runs
# Set CHUNK_NUM to the integer assigned in Step B1 (1, 2, ...).
CHUNK_NUM=1  # replace with the actual chunk number
CHUNK_PATH="${PROJECT_ROOT}/graphify-out/.graphify_chunk_$(printf '%02d' "$CHUNK_NUM").json"
```

Give the subagent the extraction prompt below with FILE_LIST, CHUNK_NUM, TOTAL_CHUNKS, DEEP_MODE, and that chunk's CHUNK_PATH substituted. When it returns, paste its JSON response and write it to the same chunk file so Step B3 can collect it:

```bash
# After pasting a subagent's JSON for chunk N, save it (replace N and PASTED_JSON):
PROJECT_ROOT=$(pwd)  # cwd — where Part C globs graphify-out/ (NOT .graphify_root/scan dir, #1392)
cat > "${CHUNK_PATH}" <<'CHUNK_JSON'
PASTED_JSON
CHUNK_JSON
```

Repeat for every chunk. Each chunk's JSON must land in its own `graphify-out/.graphify_chunk_NN.json` before Step B3 runs.

Subagent prompt template:

See `references/extraction-spec.md` for the exact subagent prompt (JSON schema, node-ID rules, confidence rubric, hyperedge, and vision rules). Load it only here, only when at least one chunk holds a doc, paper, or image; a pure-code corpus has skipped Part B and never reads it. Pass each subagent that prompt verbatim with FILE_LIST, CHUNK_NUM, TOTAL_CHUNKS, DEEP_MODE, and its own absolute CHUNK_PATH substituted. If the subagent cannot write to the shared workspace, paste its returned JSON into CHUNK_PATH as shown above.
