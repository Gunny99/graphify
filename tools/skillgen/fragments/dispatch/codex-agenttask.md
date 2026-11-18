**Step B2 - Dispatch ALL subagents in a single message (Codex)**

> **Codex platform:** Uses `spawn_agent` + `wait_agent` + `close_agent` instead of the Agent tool.
> Requires `multi_agent = true` under `[features]` in `~/.codex/config.toml`.
> If `spawn_agent` is unavailable, tell the user to add that config and restart Codex.

Call `spawn_agent` once per chunk — ALL in the same response so they run in parallel. Build the message by wrapping the extraction prompt in task-delegation framing:

```
spawn_agent(agent_type="worker", message="Your task is to perform the following. Follow the instructions below exactly.\n\n<agent-instructions>\n[extraction prompt, with FILE_LIST, CHUNK_NUM, TOTAL_CHUNKS, DEEP_MODE substituted]\n</agent-instructions>\n\nExecute this now. Output ONLY the structured JSON response.")
```

After all agents are dispatched, collect results sequentially in memory:
```
result = wait_agent(handle); close_agent(handle)   # repeat per handle
```

Collect each result in memory and associate it with the chunk number used for dispatch. Validate each response as one JSON object with object-valued `nodes` and `edges` lists; `hyperedges` may be omitted or a list of objects; `coverage` must be an object mapping string file paths to nonnegative integer line counts (booleans are not integers for this check); and `input_tokens` and `output_tokens` must be nonnegative integers. Empty `nodes` and `edges` lists are valid extraction results.

Only persist a result after it passes validation. Write each valid result separately to its matching `graphify-out/.graphify_chunk_NN.json` file, using JSON serialization and the trusted chunk number. Preserve its `nodes`, `edges`, `hyperedges`, `coverage`, `input_tokens`, and `output_tokens` values. Read every written file back and verify that it parses and retains the required fields.

If a subagent fails, returns no result or invalid JSON, or its result cannot be persisted and read back, report the affected chunk number and leave that chunk's expected file absent. Do not invent an empty success result, reuse another chunk's data, or write a partial placeholder. **Continue to shared Step B3 with the valid chunk files**: the common collector applies the same missing/failed-chunk policy on every host, merges completed chunks when within its failure threshold, and leaves omitted files unstamped so the next `--update` can retry them. If the common threshold is exceeded, Step B3 stops before Part C.

Do not aggregate results or write `graphify-out/.graphify_semantic_new.json` in B2 — shared Step B3 is the only stage that merges chunk files and updates the semantic cache.

Subagent prompt template:

See `references/extraction-spec.md` for the compact subagent prompt (rules, node-ID format, confidence rubric, hyperedge and vision rules, JSON schema). Load it only here, only when at least one chunk holds a doc, paper, or image; a pure-code corpus has skipped Part B and never reads it. Pass each agent that prompt verbatim with FILE_LIST, CHUNK_NUM, TOTAL_CHUNKS, and DEEP_MODE substituted, and have it return the JSON inline.
