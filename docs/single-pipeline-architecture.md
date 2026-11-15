# Graphify Single-Pipeline Architecture

**Status:** Design baseline / implementation plan  
**Scope:** Graphify's coding-workflow orchestration, skill dispatch, LLM transport, task ledger, independent review, failure recovery, and Graphify's own detect→extract→build→analyze→export pipeline.  
**Decision rule:** One authoritative workflow controller; modular stages; one primary writer; a separate reviewer; delegation only when the measured benefit exceeds its total cost.

## 1. Executive decision

Graphify should have one **authoritative run lifecycle**, not one giant function and not a collection of loosely coupled agent scripts. A user request becomes a durable Run. The controller selects a plan, dispatches bounded Tasks, records immutable Attempts and Artifacts, validates acceptance criteria, obtains independent review where required, integrates accepted outputs, and closes the Run with a verifiable report.

"Single pipeline" means **one state machine, one source of truth, one owner of transitions, and one set of contracts**. It does not mean one model for every operation, one code file, or no specialized worker. Sequential and coupled work stays in one primary session. Independent review is a separate identity and context. Read-only exploration or truly disjoint parallel work is an explicit exception, never a default.

Graphify's existing components are useful foundations:
- `graphify/orchestration.py` already defines versioned run/task/result/review contracts, strategy selection, quality gates, and write-set validation.
- `graphify/task_store.py` already provides SQLite WAL persistence, leases, bounded attempts, cost reservations, immutable result/review records, and an append-only `events` table.
- `graphify/serve.py` exposes those functions through MCP.
- `graphify/llm.py` and the platform-specific skill artifacts contain provider and host execution paths that should become adapters to the common contract.
- The product graph pipeline is modular already: detect → extract → build → cluster → analyze → report/export.

The innovation is to **connect these foundations under one lifecycle and remove parallel sources of policy**, not to replace working code wholesale.

## 2. Why this structure is necessary

Today, the repository contains several valid but separate execution concepts: the product's graph-building pipeline, skills that direct host agents, direct LLM backend calls, MCP orchestration records, CLI/watch rebuilds, query logging, and generated platform instructions. Each can be locally correct while their global behavior diverges: retry rules differ, task progress is only partially visible, instructions duplicate, failure learnings do not reliably become executable guards, and an apparently successful subtask may not satisfy the user's original request.

A central run lifecycle is necessary for five reasons:

1. **Correctness:** the system needs one authoritative answer to "what is the current state, what is allowed next, and what proves completion?"
2. **Cost and context efficiency:** work should pass references and compact results, not repeatedly serialize the same corpus, instructions, cache, or history into every model context.
3. **Failure containment:** retries, repeated actions, stale artifacts, and no-progress loops need one policy boundary instead of nested local retry loops.
4. **Review independence:** a producer cannot be the sole judge of its own output. Review must be a separate, auditable stage with an explicit contract.
5. **Evolution without patch accumulation:** a recurring bug should produce a new invariant, guard, or contract test at the correct layer—not another one-off conditional.

The state machine is therefore an architectural necessity, not an orchestration fashion. It reduces ambiguity between layers while preserving modular implementation.

## 3. Target architecture

```text
User request
  │
  ▼
Run Controller ──────────────── Policy / budget / deadline / loop guard
  │
  ├── Run ledger (SQLite events, state, spans, artifacts, failure signatures)
  │
  ├── Context selector ──────── selected files, symbols, skills, time-log slices
  │
  ├── Plan ──────────────────── stages + acceptance criteria + write set
  │
  ▼
One primary execution lane
  ├── Explore (read-only unless explicitly authorized)
  ├── Implement / invoke Graphify stage
  ├── Test and collect evidence
  └── Freeze candidate diff + artifact manifest
  │
  ▼
Independent Reviewer ───────── separate identity/context; read-only by default
  │
  ├── findings with file/line/test/evidence anchors
  ├── severity + reproducibility + confidence
  └── accept / reject / request bounded correction
  │
  ▼
Coordinator adjudication ───── producer cannot silently self-approve
  │
  ▼
Integrate → Verify final state → Publish complete PR progress → Close Run
```

### 3.1 The core contract

The controller owns the only authoritative transitions. Host tools and model backends are replaceable adapters. A Task has an objective, scope, input references, output contract, acceptance criteria, deadline, attempt budget, and allowed capabilities. A Result is immutable and points to artifacts and evidence. A Review references the exact Result/commit/artifact hashes. An Event records every meaningful state transition. A Span records elapsed time without copying full prompts or source contents.

Recommended hierarchical states:

- **Run:** queued → planning → ready → running → awaiting_review → integrating → completed; terminal alternatives: blocked, failed, cancelled, provisional.
- **Task:** queued → leased → submitted → validating → accepted; alternatives: retry_wait, needs_redesign, rejected, blocked, failed, cancelled.
- **Attempt:** started → checkpointed → submitted | failed | interrupted.
- **Review:** queued → reviewing → accepted | rejected | insufficient | escalated.

The state machine must validate legal transitions and record the reason for every transition. It must never infer success merely because a process exited with code 0.

### 3.2 One pipeline, modular components

- **Controller:** owns Run and Task transitions, budgets, deadlines, retry/redesign decisions, and final completion.
- **Planner:** converts the request into a minimal DAG and testable acceptance criteria. It does not own state.
- **Executor:** runs work through one primary lane; execution may be a local function, CLI command, host skill, or model adapter.
- **Adapters:** translate one stable internal request/result contract to Claude CLI, Anthropic, OpenAI-compatible, Azure, Bedrock, Ollama, Codex, OpenCode, or future hosts.
- **Reviewer:** inspects a frozen candidate and emits structured findings. It does not modify the candidate by default.
- **Ledger:** persists state, events, spans, artifacts, and failure signatures. It is not a prompt cache.
- **Skill selector:** loads only the skill/references required for the current stage.
- **Graph pipeline:** remains a composable domain pipeline invoked by a Task; it does not create a second orchestration authority.

### 3.3 Independent reviewer: benefits, costs, and controls

**Benefits:** separates implementation bias from verification; catches omitted requirements and self-confirming assumptions; creates an auditable acceptance record; enables a cheaper executor with a stronger or more skeptical reviewer; keeps one writer and avoids competing patches.

**Costs and failure modes:** extra latency and model cost; correlated errors if provider/model/prompt/evidence are too similar; false positives or overengineering; reviewer may lack the producer's exploration context; reviewer may create an endless correction loop; a reviewer can be confidently wrong.

**Controls:** one reviewer by default; separate provider/model/version and identity where feasible; reviewer receives a frozen diff and compact evidence manifest rather than the producer's full scratch context; blind the reviewer to model identity where feasible; require findings to cite exact files/lines/tests or sources; classify blocker/advisory/nit; the producer may respond but cannot erase a finding; a deterministic adjudicator checks the response; allow at most one ordinary correction cycle plus one materially justified escalation; stop on reviewer disagreement that cannot be grounded; measure false-positive and escaped-defect rates over time.

## 4. Design principles

1. One run controller, one canonical contract, one authoritative state store.
2. One primary writer; reviewer and explorers are read-only unless a bounded write-set exception is declared.
3. Prefer pure policy functions and explicit state transitions; isolate I/O in adapters.
4. Keep stage modules small. "Single pipeline" is not permission to build a monolith.
5. Store references and hashes, not duplicated source text or giant prompts.
6. Never retry a permanent error; all retries consume a shared attempt/time/cost budget.
7. A failure may be retried only when the next attempt changes a relevant condition.
8. Repeated no-progress is a redesign signal, not a reason to increase the retry count.
9. A bug fix is incomplete until its root invariant and regression guard are identified.
10. Every completion claim maps to acceptance evidence and a recorded verification outcome.
11. Generated host skills are views of canonical policy, never independent policy sources.
12. Every large change is staged, reversible, measurable, and independently reviewed.

## 5. Code rules: same result with simpler code

- Prefer one canonical implementation over wrappers that each reimplement policy.
- Put decision logic in pure functions; keep filesystem, network, database, and subprocess effects at the boundary.
- Use one structured contract per concept; do not maintain parallel dictionaries with slightly different names.
- Make states and transitions explicit tables, not scattered string comparisons.
- Avoid boolean parameter explosions; use a small enum/policy object when combinations matter.
- Avoid generic frameworks until at least two real callers need the abstraction.
- Do not build a second event log, cache, retry loop, or progress tracker when the existing primitive can be extended safely.
- Keep functions cohesive and short; split on changed responsibility, not arbitrary line count.
- Derive tests, docs, CLI validation, and skill schemas from canonical contracts where practical.
- Treat generated files as outputs; edit source fragments/schema and regenerate.
- Use stable IDs and content hashes for artifacts; don't infer identity from filenames or timestamps alone.
- Make destructive actions explicit and separately gated; make read-only inspection cheap.
- Every retry must be owned by exactly one layer; disable SDK/inner retries when the controller owns them.
- Every timeout derives from a propagated Run deadline and remaining budget.
- Preserve unknown errors; do not misclassify programming errors as transient.
- Avoid global mutable state; pass project/run context explicitly.
- Cache only deterministic expensive results with explicit key/version/invalidation semantics.
- Don't cache policy decisions that depend on live budgets, active agents, permissions, or deadlines.
- Every new abstraction must remove more duplication/ambiguity than it introduces.
- Reject complexity that cannot be justified by a real failure, measurable cost, or explicit product requirement.

## 6. The 120-item improvement program

Status at creation: **120 proposals catalogued; implementation is staged.** "Designed" is not "implemented". Each item must later move through proposed → accepted design → implemented → tested → independently reviewed → measured. The PR progress ledger will identify the items changed in each phase.

### A. Architectural invariants and boundaries (01–10)

01. Define one Run as the unit of user intent, from request intake to verified completion; prevents fragmented "done" states.
02. Define one controller as the sole writer of Run/Task state; prevents adapters from making contradictory transitions.
03. Separate workflow state from domain pipeline state; Graphify extraction remains modular inside an execution task.
04. Establish explicit module boundaries for controller, policy, executor, adapters, reviewer, ledger, and skill selector; prevents orchestration from leaking into transport code.
05. Make every cross-boundary message conform to a versioned envelope; prevents provider-specific payload assumptions.
06. Give every artifact a stable ID, content hash, producing attempt, and provenance; prevents stale or misattributed results.
07. Freeze the candidate diff/artifact manifest before review; prevents review findings from targeting moving content.
08. Require acceptance criteria before execution begins; prevents post-hoc success definitions.
09. Require a final completion record mapping every criterion to evidence; prevents "tests ran" from substituting for task completion.
10. Maintain an architecture decision record for every change to a core invariant; prevents silent architectural drift.

### B. Single execution pipeline and routing (11–20)

11. Introduce a hierarchical Run/Stage/Task/Attempt state machine; prevents parallel orchestration concepts.
12. Make all task creation pass through one planner/validator; prevents skill-specific task graphs from bypassing policy.
13. Default to one primary executor for sequential and coupled work; reduces handoff/context duplication and write conflicts.
14. Permit read-only explorers only for measured context-pressure or discovery benefit; preserves a single writer.
15. Permit parallel implementation only with explicit non-overlapping write sets and no shared mutable state; prevents merge races.
16. Route all model calls through one backend adapter contract; removes inconsistent retry, timeout, and telemetry behavior.
17. Route host-specific skill invocations through a host adapter contract; keeps Codex/OpenCode/Claude instructions behaviorally equivalent.
18. Make Graphify's detect→extract→build→analyze→export stages callable as one domain task with stage-level events; preserves composability and end-to-end visibility.
19. Remove duplicate retry ownership across SDK, adapter, CLI, skill, and controller; prevents multiplicative attempts.
20. Add a strategy decision record containing reason, alternatives rejected, expected total cost, and deadline effect; makes delegation measurable.

### C. Independent reviewer and adjudication (21–30)

21. Keep reviewer identity separate from producer identity; prevents self-review.
22. Require model/provider/version separation where available; reduces correlated failure.
23. Blind producer model metadata where feasible; reduces anchoring.
24. Send frozen diff plus compact evidence/acceptance manifest, not full scratch context; controls context cost.
25. Require every material finding to have an exact file/line, test, or source anchor; rejects vague criticism.
26. Standardize severity, confidence, reproducibility, and disposition fields; makes reviews actionable.
27. Separate correctness findings from style preferences; prevents subjective churn.
28. Let the producer respond to findings but not silently close them; preserves independent authority.
29. Add a deterministic adjudication step for disputed findings; prevents model-vs-model voting.
30. Limit routine review/correction cycles and escalate only on material unresolved issues; prevents review ping-pong.

### D. Contracts and code simplicity (31–40)

31. Establish a canonical schema registry for run, task, attempt, artifact, event, span, review, and failure records; prevents schema duplication.
32. Generate validators and host-facing schemas from the canonical contract where feasible; prevents hand-maintained drift.
33. Publish explicit compatibility and migration rules for every schema version; prevents silent data breakage.
34. Replace scattered status checks with centralized transition functions; prevents illegal transitions.
35. Make policy functions pure and deterministic; enables cheap unit/property tests.
36. Keep side effects behind narrow ports/adapters; enables offline testing and safe substitution.
37. Remove duplicate provider retry logic and duplicated response normalization; ensures a single behavior.
38. Use typed small records for internal state and JSON only at persistence/wire boundaries; reduces dictionary-key mistakes.
39. Ban new generic frameworks without at least two concrete use cases and a measured simplification; prevents abstraction sprawl.
40. Add complexity budgets to review: changed lines, new concepts, dependencies, branching, and migration risk must be justified by the defect or capability.

### E. Root-cause correction and permanent learning (41–50)

41. Require every bug fix to name the violated invariant, not only the symptom; prevents symptom-only patches.
42. Give each failure a normalized fingerprint (stage + category + stable error signature + artifact/version context); identifies recurrence.
43. Store reproduction, root cause, invariant, prevention guard, and verification evidence together; makes lessons executable.
44. Distinguish observed failures from hypotheses; unverified memories cannot become hard rules.
45. Promote a lesson only after independent confirmation or a reproducible test; prevents false institutional memory.
46. Generate a regression test from each confirmed root cause when practical; prevents recurrence.
47. Add invariant/property tests for whole classes of failure; replaces patch-by-patch examples.
48. Detect when several patches touch the same symptom without changing the root invariant; trigger redesign review.
49. Track recurrence by failure fingerprint and reject an identical retry strategy after a confirmed failure; blocks repeated mistakes.
50. Periodically retire obsolete guards only with evidence and an explicit migration note; avoids permanent defensive clutter.

### F. Skills, context, and cache discipline (51–60)

51. Keep one canonical skill policy; generated host skills are thin projections rather than independently authored workflows.
52. Use progressive disclosure: core instructions contain only the default path and hard safety/quality rules.
53. Load a reference only when the selected task type or failure category needs it; avoids cache/context overfetch.
54. Select skills from task metadata, changed files, risk class, and capabilities; avoids loading every skill on every run.
55. Store a compact skill index with stable IDs, version, scope, and invocation conditions; supports cheap selection.
56. Deduplicate reference content by content hash; avoids repeated instructions across platforms.
57. Use small task briefs with file/symbol references and acceptance criteria; avoids copying the full Run context.
58. Pass summaries plus artifact IDs between stages; allow exact detail retrieval on demand.
59. Make context budgets explicit per stage and reserve a final integration budget; prevents early stages from consuming all context.
60. Measure tokens saved, cache hit value, and re-read cost; retain a cache only when net total cost improves.

### G. Selectable time logs and progress visibility (61–70)

61. Use the existing append-only task event ledger as the canonical timeline; do not create a competing log.
62. Add structured spans for stage/task/tool/test/review work; permits duration and bottleneck analysis.
63. Record start/end timestamps, duration, outcome, attempt, and correlation IDs; makes time measurable.
64. Keep prompts, source bodies, secrets, and full outputs out of timing metadata; minimizes sensitive retention.
65. Expose timeline filters by run, task, stage, category, date range, and event ID; lets users retrieve only relevant history.
66. Return compact summaries by default and full event detail only on explicit selection; prevents context inflation.
67. Correlate local commands, model calls, CI runs, and review events to the same Run; reveals hidden waiting and duplicated work.
68. Track active time separately from queue wait, provider wait, and review wait; supports realistic latency analysis.
69. Publish progress at state transitions and meaningful milestones, not every token; avoids noisy status.
70. Keep PR body as the complete current summary and PR comments/reviews as the append-only progress/audit trail; makes external review continuously current.

### H. Loop detection and redesign protocol (71–80)

71. Fingerprint repeated actions and normalized errors; detects exact repetition despite changing timestamps.
72. Stop after a configurable repeated-action threshold (initial default: 3); prevents blind replay.
73. Detect no-progress by unchanged artifact/test/result signatures across consecutive attempts; catches loops without identical text.
74. Enforce total Run wall-time, token, tool-call, retry, and cost budgets; prevents runaway work.
75. Propagate one absolute deadline to every child task and backend call; avoids work continuing after the user-visible deadline.
76. On loop trip, stop dispatch, checkpoint current work, preserve diffs/logs, and mark needs_redesign; prevents damage and loss of evidence.
77. Require a new hypothesis and changed intervention before a redesign retry; forbids identical replay under a new label.
78. Limit redesign cycles (initial default: 2) and require escalation after exhaustion; guarantees termination.
79. Allow the controller to roll back only the incomplete, uncommitted unit; preserves earlier valid work.
80. Require post-redesign verification to test the original failure plus adjacent invariants; prevents superficial green tests.

### I. Failure handling, recovery, and safety barriers (81–90)

81. Classify permanent, transient, timeout, context, dependency, permission, schema, and code defects; routes each to the right response.
82. Use bounded exponential backoff with jitter and a shared retry budget for transient failures; prevents retry storms.
83. Retry only if a relevant condition changed or the error is explicitly transient; prevents same-input retries.
84. Use idempotency keys for result submissions, tool actions, and artifact creation; prevents duplicate side effects.
85. Treat stale leases and stale outputs as invalid by default; prevents old attempts from being accepted.
86. Bind every submitted result/review to a task attempt and content hash; prevents cross-attempt substitution.
87. Checkpoint at safe boundaries before long operations; supports restart without repeating completed work.
88. Propagate cancellation through subprocesses, adapters, and child tasks; stops abandoned work.
89. Enforce path/symlink/write-scope boundaries centrally; prevents task-level escape from declared scope.
90. Keep a kill switch for a Run and a repository-wide pause for orchestration; enables containment.

### J. Testing, verification, and quality gates (91–100)

91. Require focused tests after each changed subsystem and full suite at integration milestones; shortens feedback.
92. Add contract tests shared by every backend/host adapter; prevents adapter drift.
93. Add state-machine transition/property tests; checks legal and terminal states.
94. Add fault injection for timeouts, expired leases, partial writes, corrupt events, and cancellation; tests recovery paths.
95. Add loop-guard tests for repeated action, repeated error, no progress, changed strategy, and exhausted redesigns; proves termination.
96. Add artifact freshness and provenance tests; prevents stale output reuse.
97. Separate product behavior failures from test-contract drift; keeps regressions meaningful.
98. Track flaky tests separately and never relabel a repeatable failure as flakiness without evidence; protects signal quality.
99. Make the independent review include test selection, missing negative cases, and whether a test actually exercises production code; raises test quality.
100. Gate release on exact target commit, test command, result count, skips/xfails, and CI identity; prevents stale green results.

### K. Observability, cost, and PR governance (101–110)

101. Give every Run a correlation ID propagated to tasks, spans, artifacts, model calls, and PR comments; joins evidence.
102. Report current stage, task owner, attempt, blocker, and next permitted transition; makes progress legible.
103. Distinguish planned, reserved, actual, and unreported costs; avoids optimistic totals.
104. Track context tokens, duplicated context, cache reads, tool calls, retries, and reviewer overhead; measures efficiency.
105. Track cycle time by queue, execution, test, review, and integration; exposes bottlenecks.
106. Publish complete design and progress to the PR at each milestone; prevents private or lost decisions.
107. Maintain one authoritative checklist in the architecture document, with PR body summarizing current item statuses; avoids duplicate tracking systems.
108. Link every finding to a commit, file, line, test, and disposition; supports audit.
109. Keep PR open as Draft while the design or validation gate is incomplete; avoids implying readiness.
110. Never report CI success from a previous revision as evidence for the current head; enforces commit-level honesty.

### L. Rollout, compatibility, and performance (111–120)

111. Inventory every entry point and backend before migrating; prevents unexamined bypasses.
112. Add an adapter compatibility matrix for each host and backend; makes coverage explicit.
113. Migrate one path at a time behind compatibility wrappers; reduces blast radius.
114. Run old and new policy in shadow mode where outputs can be compared without double writes; reduces migration risk.
115. Use golden fixtures for identical request/result contract behavior across adapters; detects drift.
116. Measure end-to-end latency, cost, context, failure rate, and review escape rate before/after; validates benefits.
117. Version the ledger schema and provide forward-only transactional migrations with backups; protects durable work.
118. Preserve old CLI/skill interfaces while routing internally to the new controller; avoids breaking users.
119. Remove legacy paths only after usage and test evidence show they are unused; prevents premature cleanup.
120. Make rollout reversible by feature flag and migration checkpoint; enables safe recovery.

## 7. Delivery sequence

| Phase | Deliverable | Exit condition |
|---|---|---|
| P0 — Architecture baseline | This contract, 120-item register, system inventory, decision record | One agreed architecture boundary and measurable acceptance criteria |
| P1 — Durable observability and loop barrier | Timeline API over existing events; structured spans; pure loop guard; progress summaries | Event queries are bounded; spans redact content; loop tests prove stop/redesign |
| P2 — One controller | Run lifecycle and transition authority over existing TaskStore | Every entry path creates/updates one Run; no side-channel state changes |
| P3 — Adapter convergence | LLM + host + Graphify stage adapters use common contracts | Shared contract suite passes across adapters; one retry owner |
| P4 — Independent review | Frozen artifacts, blind reviewer input, structured findings, adjudication | Reviewer is independent and cannot self-approve or silently edit |
| P5 — Selective skill/context system | Canonical skill index, on-demand references, task-specific context manifest | No default bulk cache/reference loading; token/latency benefit measured |
| P6 — Failure prevention | Fingerprint registry, invariant promotion, loop redesign protocol, fault injection | Confirmed prior failures are blocked by executable tests/guards |
| P7 — Migration and retirement | Legacy execution paths routed through controller then removed | Compatibility matrix green; old paths proven unused; rollback tested |

P0 is complete. P1 implementation is in progress: the durable timeline, content-free spans, persistent loop guard, and coordinator-controlled redesign path are present in code and exposed through MCP. The runtime guard is opt-in at the execution boundary today: a worker must call `orchestrator_observe_step` and submit a progress fingerprint; existing host skills and direct execution paths are not yet automatically instrumented. P1 remains open until focused tests run on the exact head commit and execution adapters are wired to report progress. No phase is considered complete by documentation alone.

## 8. Acceptance metrics

The following metrics are required before calling this architecture successful:
- 100% of orchestrated tasks have a Run ID, Task ID, attempt, declared acceptance criteria, and recorded terminal outcome.
- 100% of material code changes have a frozen artifact/diff reviewed independently or an explicit, auditable reason review was waived.
- 0 accepted results from stale attempts, expired leases, invalid write scopes, or incomplete required review.
- 0 unbounded automatic retry or redesign loops.
- Every loop trip produces a checkpoint, failure fingerprint, and redesign/terminal decision.
- 100% of PR progress updates identify current head SHA and distinguish tested from untested changes.
- Median prompt/context duplication decreases against a recorded single-session baseline; cache is retained only where total measured cost improves.
- Every approved architecture item has a test or observable acceptance measure, not merely a prose declaration.

## 9. Existing gaps to address first

Grounded in the current source snapshot:
- The append-only event table remains the canonical timeline; `TaskStore.list_events()` now provides bounded cursor/time/task/type filtering, compact summaries by default, and explicit payload opt-in.
- `TaskStore.record_span()` now records content-free stage/task timing metadata in the same event ledger; active-vs-wait attribution and automatic span emission across every host remain open.
- `WorkflowLoopGuard` now fingerprints repeated actions/errors and unchanged progress, persists state in the event ledger, and pauses the whole Run for redesign. The MCP contract requires a progress fingerprint, but automatic calls from all existing skill/CLI/host execution paths remain open.
- `querylog.py` is opt-in query logging, not a task execution timeline; it should not be repurposed to hold prompts or source bodies.
- `serve.py` registers orchestration handlers separately from other command entry points; all entry points still need a common Run facade.
- The skill generator already uses a core plus references, but host-specific fragments and generated artifacts can drift unless canonical contracts and consistency tests own the policy.
- `llm.py` has a direct API path, while skill-driven host execution is a separate route; both need one internal request/result/retry contract.
- Current reviewer workflows exist for structured claims; code review needs the same frozen-artifact, finding, disposition, and cycle-limit semantics.

These are architectural gaps, not a claim that existing code is defective. Preserve working lease, budget, evidence, cache, and extraction behavior while consolidating ownership.

## 10. External engineering references

These references support the reliability principles, not Graphify-specific implementation claims:
- Google SRE, **Addressing Cascading Failures** — bounded retries, randomized backoff, retry budgets, deadline propagation, and cancellation: https://sre.google/sre-book/addressing-cascading-failures/
- OpenTelemetry, **Semantic Conventions for Events** — event timestamp and attributes should be structured, filterable, and avoid copying span attributes or sensitive/large bodies unnecessarily: https://opentelemetry.io/docs/specs/semconv/general/events/
- OpenTelemetry, **Trace Semantic Conventions** — use spans for operations and consistent attributes across components: https://opentelemetry.io/docs/specs/semconv/general/trace/
- AWS Builder Center, **When Retries Make an Outage Worse** (2026-09-24) — retry storms, deadlines, backoff, and failure containment: https://builder.aws.com/content/3JltT4T9OAxMK0W8A3cOLYYQeRV

## 11. Current implementation ledger

- [x] P0 repository inventory: `orchestration.py`, `task_store.py`, `serve.py`, `llm.py`, `querylog.py`, `tools/skillgen`, product pipeline.
- [x] P0 core design and 120 proposals recorded in this document.
- [~] P1 bounded timeline query over existing events: `TaskStore.list_events()`, cursor/time/task/type filters, 1–500 result bound, compact summaries by default, explicit payload opt-in.
- [~] P1 structured spans: `TaskStore.record_span()` records start/end, duration, outcome and allowlisted metadata in the same event table; no separate log DB/cache.
- [~] P1 loop guard: repeated action/error and unchanged-progress fingerprints, durable state restoration, required progress fingerprint, whole-Run pause, sibling lease revocation, coordinator-only redesign, maximum two redesigns, fail-closed stop and sibling blocking.
- [~] P1 MCP exposure: `orchestrator_record_span`, `orchestrator_list_events`, `orchestrator_observe_step`, `orchestrator_redesign_task`.
- [ ] P1 automatic instrumentation from every host skill, CLI/backend and task execution boundary; workers must currently call the new progress-report tool.
- [ ] P1 execute focused and full regression tests on the exact head SHA. Tests were added/updated but have not been run in this environment; the PR currently has no check runs.
- [ ] P2 one controller facade and transition authority across MCP, CLI, skills, backend and Graphify domain pipeline.
- [ ] P3 adapter convergence, one retry/deadline owner and contract tests.
- [ ] P4 frozen-artifact independent code reviewer and adjudication.
- [ ] P5 selective skill/context loading and measured cache policy.
- [ ] P6 global failure fingerprint/invariant registry and fault-injection gates.
- [ ] P7 staged migration, compatibility matrix, legacy path retirement and rollback.

**Progress rule:** update this ledger, the PR body, and the PR review thread after each completed implementation/verification milestone. Report the exact head SHA and actual test evidence. A `[~]` item has implementation code but has not passed its acceptance/verification gate.
