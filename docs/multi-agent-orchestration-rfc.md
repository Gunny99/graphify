# RFC: Unified multi-agent orchestration

## Status

Proposed architecture for the next Graphify development phases. This RFC defines the task/result contract and acceptance policy; it does not claim that the current extraction pipeline already meets the quality targets below.

## Goals

- Let independent AI sessions from different hosts (Codex, Claude Code, OpenCode, Pi, Gemini clients, and future adapters) participate in one coordinated run.
- Keep each agent independently executable. Graphify coordinates work; it does not require every provider to share a proprietary sub-agent API.
- Make task ownership, dependencies, leases, retries, result provenance, quality checks, and cost observable and persistent.
- Prefer the least expensive qualified model for each task, without lowering the required result quality.
- Make unsupported claims visible and withhold results that have not passed the required quality gate.

## Non-goals for the first implementation

- Graphify will not secretly launch arbitrary desktop AI applications or impersonate a user's logged-in sessions.
- Agents will not share private chain-of-thought. They exchange task inputs, source references, structured results, evidence, and concise rationale only.
- A model's self-reported confidence is not a quality certificate.
- The system will not promise a universal 99% result guarantee from model selection alone. Quality is measured on independently checked evaluation data and on each result's evidence.

## Architecture

## Single-agent-first routing policy

The default execution strategy is `single_agent`: one main session keeps the plan, implementation, and tests in the same context. Do not create planner/developer/tester/security/reviewer teams by default, and do not generate intermediate handoff documents that merely repeat the same context.

A task may use one focused independent review after the main implementation (`single_with_review`). This is a single post-implementation check, not an agent team. Material factual claims still require independently checked evidence under the quality policy; that verification stage is not permission to delegate the entire workflow.

Use multiple agents only in these exceptions:

1. **Read-only exploration:** a large codebase or document corpus would otherwise overwhelm the main context. Explorers receive non-overlapping search questions, have no write tools, and return concise findings with file/line/source references. The main session remains the only writer. Any material factual/inference claims in explorer results still require the normal independent-verification task; read-only access does not lower the evidence standard.
2. **Independent parallel work:** at least two workstreams are genuinely independent, have no dependency ordering, do not share mutable state, and have disjoint file write sets. Parallel execution is allowed only when the expected total cost is no higher than the single-session estimate, or a hard deadline makes the verified latency reduction necessary.
3. **Independent review:** after the main work is complete, one separate reviewer checks implementation, security, edge cases, and tests. Additional reviewers are not spawned automatically; a second reviewer is an escalation only when the first review identifies a material dispute or confidence remains insufficient.

Decision gates:
- Any dependency between workstreams, overlapping write set, shared state, or need for iterative user feedback selects one main session.
- For small fixes, one-file changes, sequential design/implementation/test work, or work that requires maintaining a cumulative context, use one session.
- For wide exploration, isolate reading only; return bounded summaries instead of copying all raw context into the main session.
- For a valid independent parallel run, cap initial concurrency at three workers. Increase only when measured results show a net benefit.
- Never delegate merely to fill roles. Never allow workers to spawn more workers by default.
- Before delegating, estimate the complete cost including generation, duplicated context, result handoff, integration, verification, retries, and escalation. If cost or benefit is unknown, default to one session and collect measurements first.

Track each run's selected strategy, reason, number of spawned workers, tokens, wall time, integration defects, verified accuracy, hallucination rate, and full cost. Evaluate strategies against a single-session baseline on the same task before enabling a broader policy.


A single Orchestrator owns a persistent task queue and a run state machine. Agents connect through MCP (or a later host adapter), register their capabilities, claim eligible work, and submit structured results. A separate verifier reviews material factual claims and checks that the submitted evidence actually supports them. The Orchestrator alone changes task state and decides whether a run is accepted, provisional, or rejected.

```text
User request
    |
    v
Orchestrator -- creates a run and a dependency graph (DAG)
    |
    +--> Task queue / durable state (SQLite, one database per project)
    |
    +--> Agent A: claim -> work -> submit
    +--> Agent B: claim -> work -> submit
    +--> Agent C: claim -> work -> submit
    |
    v
Evidence and schema validation
    |
    v
Independent verifier / adjudicator
    |
    +--> accepted
    +--> needs_review (conflict, insufficient evidence, or no qualified model)
    +--> rejected / retryable
    |
    v
Final integration and cost/quality report
```

The default path is a single main session. SQLite only coordinates work after the single-agent-first router selects one of the narrow delegation exceptions below. The first implementation should use SQLite from Python's standard library. Store the queue beside the project graph at `graphify-out/orchestrator.sqlite3`. Enable foreign keys, WAL mode, and a bounded busy timeout. Use short `BEGIN IMMEDIATE` transactions for claim/lease/state changes. MCP clients call the server; they do not open the database directly. For multiple projects, each resolved graph path gets its own store.

## Core entities

### Run

A run represents one user request and owns a DAG of tasks.

Required fields:
- `run_id`: stable UUID.
- `schema_version`: contract version.
- `request`: original user request.
- `status`: `queued | running | awaiting_review | accepted | provisional | failed | cancelled`.
- `execution_policy`: selected strategy (`single_agent | single_with_review | read_only_exploration | parallel_independent`), concurrency cap, and read/write isolation flags.
- `quality_policy`: accuracy and hallucination targets, evidence requirements, verifier policy, and confidence-bound method.
- `cost_policy`: currency, budget, and total-cost ceiling.
- `created_at`, `updated_at`, optional `deadline_at`.

### Task

Every task is an independently claimable unit of work.

```json
{
  "schema_version": 1,
  "task_id": "uuid",
  "run_id": "uuid",
  "parent_task_id": null,
  "task_type": "research|analysis|implementation|verification|integration",
  "role": "evidence_researcher",
  "domain": "technical",
  "objective": "Find primary-source support for the specified claims",
  "input": {},
  "data_scopes": ["project:demo"],
  "context_refs": [],
  "depends_on": [],
  "required_capabilities": ["web_research", "primary_sources"],
  "output_schema": {},
  "acceptance_criteria": [],
  "quality_policy_ref": "run-quality-policy",
  "cost_budget": {"currency": "USD", "max_total": 0.50},
  "deadline_at": null,
  "attempt": 0,
  "max_attempts": 2,
  "status": "queued"
}
```

Task status transitions:
- `queued -> leased -> submitted -> accepted`
- `leased -> queued` when a lease expires and attempts remain.
- `submitted -> needs_review` when verification is incomplete or conflicting.
- `submitted -> rejected` when the result fails its contract or evidence checks.
- terminal states: `accepted | failed | blocked | cancelled`.

A dependent task is claimable only after every dependency is accepted. A failed or cancelled dependency blocks its descendants and is reported to the orchestrator; the system must not silently treat a failed dependency as completed.

### Agent profile

An agent profile describes what a session can do and what it costs.

Required fields:
- `agent_id`, `provider`, `model`, `model_version`, `protocol`.
- `capabilities`: allowlisted task skills, not free-form authority.
- Every task carries a non-empty `data_scopes` list. An agent may claim it only when `allowed_data_scopes` contains every requested scope or `*`.
- `max_concurrency`, `status`, `allowed_data_scopes`.
- `cost_profile`: uncached-input, cached-input, and output pricing plus verification, retry, escalation, and orchestration costs; currency, effective date, and source.
- `quality_profile`: benchmark ID, task domain/role, sample size, verified accuracy lower bound, hallucination upper bound, evaluation date, and evaluator version.

A capability match is necessary but not sufficient: a model must also have a current quality profile that qualifies for the task's domain and quality tier.

Before creating queue tasks, call `choose_execution_strategy`. A `single_agent` or `single_with_review` run has one main work task; the latter may create one separate verifier task after implementation. For these single-session strategies, exactly one task may have no dependencies; additional tasks are permitted only as descendants of that one main task and remain sequentially claimable after their prerequisites are accepted. Exploration tasks must be read-only and independent. Parallel implementation tasks must have no dependencies, no shared mutable state, and explicit pairwise-disjoint `write_set` declarations. The store rejects a plan that does not match its declared strategy. Normalize paths as repository-relative POSIX paths before conflict checks: remove redundant separators and `.` segments, reject absolute/drive-qualified paths, URI schemes, backslashes, and `..` segments, and treat equal or ancestor/descendant paths as overlapping (for example, `src/` conflicts with `src/module.py`).

### Claim and evidence

Every material factual statement in a result is represented as an atomic claim. A claim is not accepted just because it sounds plausible.

```json
{
  "claim_id": "uuid",
  "statement": "The API uses a lease token to authenticate a task submission",
  "claim_type": "factual",
  "evidence": [
    {
      "source_id": "source-uuid",
      "uri": "https://example.invalid/source",
      "location": "section or line range",
      "excerpt": "short supporting excerpt",
      "content_hash": "sha256:..."
    }
  ],
  "verification_status": "unverified|supported|contradicted|insufficient"
}
```

Evidence must be specific enough for another verifier to locate and re-check it. For files, use a repository path and line range plus a content hash. For web sources, preserve the canonical URL and a short excerpt. Do not copy large source documents into the queue when a stable reference is sufficient.

### Result

A submitted result is immutable evidence of one task attempt. Corrections create a new attempt/result; they do not silently overwrite the prior record.

```json
{
  "schema_version": 1,
  "result_id": "uuid",
  "run_id": "uuid",
  "task_id": "uuid",
  "attempt": 1,
  "agent": {
    "agent_id": "agent-uuid",
    "provider": "provider-name",
    "model": "model-name",
    "model_version": "version"
  },
  "status": "submitted",
  "output": {},
  "claims": [],
  "evidence": [],
  "uncertainties": [],
  "usage": {
    "input_tokens": 12000,
    "output_tokens": 1600,
    "cached_input_tokens": 0,
    "direct_cost": 0.04,
    "currency": "USD",
    "pricing_source": "provider price sheet/version"
  },
  "created_at": "ISO-8601 UTC"
}
```

The server validates the envelope, required fields, output schema, usage types, and task lease before accepting a submission. Untrusted result text is data, never executable instructions.

## Quality policy

The user's target is:
- factual-claim accuracy **greater than 99%**;
- hallucination rate **less than 1%**.

Definitions:
- **Accuracy** = independently verified correct material factual claims / all material factual claims evaluated.
- **Hallucination rate** = fabricated or source-contradicted material factual claims / all material factual claims evaluated.
- **Insufficient rate** = material claims the verifier cannot establish as supported or contradicted / all material factual claims evaluated.
- **Unreviewed rate** = material claims without an independent verdict / all material factual claims evaluated.
- **Verification-failure rate** = contradicted + insufficient + unreviewed material claims / all material factual claims evaluated. This conservative rate is a release gate, not a claim that every unresolved statement is a proven hallucination.
- **Evidence coverage** = material factual claims with traceable, relevant evidence / all material factual claims.

Every material external factual claim must include evidence. A verifier must check both that the source exists and that it supports the specific claim. A citation that merely mentions the same topic is insufficient.

Quality is certified from a held-out, independently labelled evaluation set, stratified by task type and domain. Use one-sided 95% exact binomial confidence bounds (Clopper-Pearson) for the accuracy and hallucination rates. As a reference point, zero observed errors in 299 independent evaluated claims gives a one-sided 95% upper bound below 1%; correlated claims from one document or one task do not count as 299 independent observations. Increase the sample when errors occur or when observations are clustered.

A result may be labelled `certified` only when both the producing model's and the independent verifier's applicable evaluation profiles meet both statistical targets and the run's claims pass evidence verification. Otherwise:
- use `provisional` when the content is useful but the statistical target is not yet demonstrated;
- use `needs_review` when evidence is missing, sources conflict, or the independent verifier disagrees;
- use `rejected` when the result contains unsupported/contradicted material claims or fails its output contract.

The review submission uses a separate reviewer identity and records claim-level verdicts:

```json
{
  "schema_version": 1,
  "review_id": "uuid",
  "run_id": "uuid",
  "task_id": "uuid",
  "result_id": "uuid",
  "reviewer": {
    "agent_id": "independent-agent-uuid",
    "provider": "different-provider",
    "model": "independent-verifier-model",
    "model_version": "version"
  },
  "status": "accepted|provisional|needs_review|rejected",
  "usage": {
    "input_tokens": 2500,
    "output_tokens": 400,
    "cached_input_tokens": 0,
    "direct_cost": 0.01,
    "currency": "USD",
    "pricing_source": "provider price sheet/version"
  },
  "claims": [
    {
      "claim_id": "claim-uuid",
      "verdict": "supported|contradicted|insufficient",
      "evidence": [],
      "notes": "short verification note"
    }
  ],
  "created_at": "ISO-8601 UTC"
}
```

The quality gate binds the producer and reviewer evaluation profiles to the actual producer/reviewer identities. Both profiles must qualify for the task domain; a high-quality generator cannot compensate for an unqualified verifier, or vice versa. Quality profiles are maintained by the evaluator/operator, not self-asserted by the agent being measured.

The primary agent must not verify itself. The verifier must use a different agent identity and model/provider version from the producer and, where feasible, be blind to the producer's provider/model identity and self-reported confidence. A disputed material claim goes to an independent adjudicator or human review; do not average contradictory claims into a false consensus.

If no available model or agent meets the quality target for a task domain, report that limitation and withhold a certified answer. Do not lower the threshold to make the pipeline appear successful.

## Model selection and total-cost policy

The default routing rule is: choose the lowest-total-cost model among candidates whose measured quality is the same or better for the task's role and domain.

A model is eligible only when its current evaluation profile meets the applicable quality thresholds. Quality comparisons are made only within a common task-role/domain, benchmark, held-out evaluation-set hash, evaluator version, and confidence level. The cheapest model is selected only if its accuracy lower bound is within 0.1 percentage point of the cohort's best and its hallucination upper bound is within 0.1 percentage point of the cohort's best; otherwise a cheaper but measurably worse model is not considered equivalent. Models assessed on incompatible evaluation sets are not treated as interchangeable. Among quality-equivalent candidates, minimize expected end-to-end task cost:

```text
total_cost =
  generation_cost
  + independent_verification_cost
  + expected_retry_cost
  + expected_escalation_cost
  + orchestration_overhead
```

Include provider charges, input/output/cached tokens, tool costs when billed, failed attempts, reviewer/adjudicator calls, and any escalation to a stronger model. Do not compare models using generation-token cost alone.

Routing sequence:
1. Filter candidates by task capability, explicit task `data_scopes`, recent authenticated activity, current quality profile, deadline, and remaining budget. An active registration without recent authenticated activity is not considered available for cost ranking. A failed/expired owner is skipped on retry when another qualified live agent is available, but is a bounded fallback when none is available.
2. Calculate expected end-to-end cost using observed retry and verification rates for that role/domain.
3. Choose the lowest-cost qualified candidate.
4. If the result fails schema/evidence/quality checks, retry or escalate only within the task's attempt and cost budgets.
5. Record actual cost and quality outcome so future estimates improve.

When two candidates have statistically indistinguishable quality and both meet the target, choose the one with lower expected total cost. When quality is not comparable or confidence bounds overlap the threshold, do not assume equivalence; use the better-supported candidate or mark the result provisional.

## Domain extension: ziwei_saju

The `ziwei_saju` adapter keeps domain semantics inside the result payload; it does not add domain-specific states to the global run/task state machine.

### Claim evidence and source wording

Each material domain claim must carry: Non-material contextual claims still follow the common claim envelope but are exempt from domain-specific evidence-basis, assertion-strength, and derivation-step requirements; they cannot be linked from interpretation frames.
- `evidence_basis`: `explicit_source | derived | unknown`.
- `assertion_strength`: `definite | hedged`, describing how strongly the final claim itself is stated.
- `evidence`: original-source references with `source_id`, `source_type`, repository-relative `uri`, `location`, full source-file `content_hash` (`sha256:<64 hex>), verbatim `excerpt`, bibliographic `edition`, optional `variant`, `source_assertion` (`definite | hedged`), and `source_text_status` (for example, OCR/collation status).
- `derivation_steps`: required for `evidence_basis=derived`; derived claims use `claim_type=inference`. For `explicit_source`, `claim_type` must be `factual` and `derivation_steps` must be absent. For `unknown`, `derivation_steps` must be absent; its `claim_type` remains a semantic classification, but the claim stays hedged/unconfirmed and cannot receive a `supported` verdict. An unknown material claim may coexist with determinate claims in the same result, but the result remains unresolved/provisional until that material claim is independently established; do not discard the unreadable passage or label it contradicted.

The `uri` field is a canonical repository-relative POSIX path, not a general URL: schemes, absolute/home-rooted paths, backslashes, empty path components, and `.`/`..` segments are rejected. `unknown` claims carry no supporting evidence and must remain hedged/unconfirmed. A source author's hedged wording is recorded as `source_assertion=hedged`; it is not a model-generated estimate. The `ziwei_saju` validator rejects `estimated` as an evidence basis because this domain's governing specification does not permit model-invented estimated coefficients or assumptions. A claim supported only by hedged source assertions cannot be upgraded to a definite statement. A `derived` claim must remain hedged when **any** premise evidence is hedged, even when another cited premise is definite. The result output must identify both the interpretation engine (`engine_hash` or `engine_version`) and the governing rule specification (`spec_hash` or `spec_version`). Do not include raw birth date/time, resident-registration or social-security numbers, or direct personal contact identifiers in the envelope; pass only the minimum redacted inputs needed for reproducibility.

The shared `claim_type` vocabulary already includes `inference`; do not add `hedged` as a claim type because hedging is assertion strength, not claim kind.

### Interpretive divergence

The domain output uses `interpretation_status=single_frame | convergent | divergent | indeterminate` and an `interpretations[]` collection. Each entry requires a named `frame`, a finding, an `assertion_strength` (`definite | hedged`), and traceable source evidence for determinate outcomes. A finding supported only by hedged source wording must remain hedged; one with no supporting source evidence must also remain hedged. Each interpretation also requires a `claim_id` that points to a distinct material factual/inference claim in the result; one claim cannot be reused by multiple frames. The displayed finding must exactly match that claim's statement, and the interpretation's source evidence must overlap the linked claim's evidence. This one-to-one frame/claim mapping ensures every user-visible interpretation receives its own independent claim-level verdict.

Each interpretation includes a stable `question_id` and a structured `direction`: `auspicious | inauspicious | character | indeterminate`. A `character` direction must also carry a normalized `trait_key` identifying the specific trait in canonical, trimmed, case-folded form. Every frame in one result envelope must answer the same `question_id`; emit separate question results rather than bundling unrelated questions. Convergence is not literal wording equality: auspicious/inauspicious directions must agree, while character directions must agree on both `direction` and `trait_key`.

- `single_frame`: exactly one named frame produced a determinate finding; additional frames may explicitly be indeterminate (no correspondence).
- `convergent`: at least two distinct named frames answer the same `question_id` with the same determinate direction/trait key. Their finding text may differ. Indeterminate frames may coexist and do not vote on convergence.
- `divergent`: at least two distinct named frames answer the same `question_id` with different determinate directions or character trait keys, each supported by its own evidence. The output must include `divergence_reason`. Indeterminate frames may coexist without being treated as a contrary finding.
- `indeterminate`: every frame's direction is `indeterminate`; every finding remains hedged, even when source passages are definite.

For every frame, `assertion_strength` must match the linked claim's `assertion_strength`. The frame's evidence and its linked claim's evidence must either both be absent (only for an `unknown` claim in an indeterminate frame) or share at least one identical `(source_id, location, content_hash)` tuple. Since `content_hash` identifies the full source file, the hash alone does not prove that two citations identify the same passage.

Do not aggregate different `question_id` values into one convergent/divergent status. Use separate question results.

A divergence does not change global `review.status` or `run.status`. A conflict within the same frame, unsupported findings, or untraceable sources remain `needs_review`.

### Evaluation status

Keep three evaluations distinct:
1. deterministic engine unit/regression tests against the versioned rule specification;
2. independent scoring of source extraction and condition application;
3. sealed holdout evaluation of predictions, never exposed to indexing, prompts, or tuning.

The currently described 63 regression cases do not establish the >99% accuracy / <1% hallucination statistical target. The domain quality profile remains `provisional` until an independently labelled, sufficiently large, non-leaking evaluation set establishes the confidence bounds. Report `contradicted`, `insufficient`, and `unreviewed` claims separately. An `insufficient` material claim blocks acceptance but is not automatically labelled a proven hallucination. The `verification_failure_rate` (contradicted + insufficient + unreviewed over all material claims) is the conservative release gate and must be checked explicitly by `result_meets_quality_gate`.

## Lease, retry, and idempotency rules

- A task claim creates a random lease token and expiry. Only that agent/token pair may heartbeat, submit, or fail the task.
- A lease expiry re-queues the task only while attempts and budget remain; the old lease token becomes invalid. When a failed result or review includes validated usage telemetry, its attempt estimate is released and the recorded actual cost is charged. When `fail_task` or lease expiry provides no usage telemetry, move the attempt estimate to durable `unreported_cost_reserved`; retain it across subsequent claims and include it in both task-level and run-level budget checks, rather than overwriting it with the next attempt's estimate.
- Result submission is idempotent by task/attempt/result ID. Replaying a completed submission must not duplicate state transitions or costs.
- A worker cannot claim a task whose dependencies are incomplete, whose capability set does not match, or whose task budget/deadline has expired.
- Every automatic retry is bounded by `max_attempts`, task cost budget, and run cost budget. No unbounded self-spawning or recursive delegation.
- A run is accepted only after all required tasks are accepted and the final quality gate passes. A queued task whose dependency is `needs_review` remains dormant and unclaimable; when no other work is runnable, the run is `provisional`, not `queued` or `failed`. If the dependency is later accepted, the downstream task becomes eligible without recreating the run.
- An explicit `rejected` review or a `contradicted` verdict is terminal rejection. An `insufficient` verdict is unresolved evidence, not proof of contradiction: keep the source task `needs_review` and the run `provisional` when no eligible independent verifier remains. Requeue only when a different fresh, eligible verifier is available and the attempt budget remains.

## Initial MCP contract

The first MCP surface should stay small and explicit:

| Tool | Purpose |
| --- | --- |
| `register_agent` | Register/update an agent's capabilities, model identity, concurrency, and cost profile |
| `create_run` | Create a run and its task DAG under a declared quality/cost policy |
| `claim_task` | Atomically claim the next eligible task and receive a lease token |
| `heartbeat_task` | Extend an owned lease within its deadline |
| `submit_result` | Submit the immutable structured result for the owned attempt |
| `review_result` | Submit an independent verification decision and claim-level findings |
| `get_run_status` | Return run/task states, blockers, quality status, and cumulative cost |
| `cancel_run` | Cancel pending work and invalidate active leases |

No tool should expose arbitrary SQL or direct database access.

## Delivery sequence

1. Stabilize current host-specific chunk handoff and common result preflight.
2. Add and test the versioned run/task/agent/result contracts.
3. Implement the SQLite-backed queue, atomic leases, dependency scheduling, retries, and idempotent submissions.
4. Expose the queue through MCP tools and add agent adapters.
5. Add independent evidence verification, statistical quality reporting, and the quality gate.
6. Add per-task model/cost routing using measured end-to-end costs and quality profiles.

The queue/contract layer must be testable without calling a paid model or starting a real external agent. Provider adapters and model selection remain optional layers above the stable contract.
