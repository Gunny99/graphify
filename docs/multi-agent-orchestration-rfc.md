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

The first implementation should use SQLite from Python's standard library. Store the queue beside the project graph at `graphify-out/orchestrator.sqlite3`. Enable foreign keys, WAL mode, and a bounded busy timeout. Use short `BEGIN IMMEDIATE` transactions for claim/lease/state changes. MCP clients call the server; they do not open the database directly. For multiple projects, each resolved graph path gets its own store.

## Core entities

### Run

A run represents one user request and owns a DAG of tasks.

Required fields:
- `run_id`: stable UUID.
- `schema_version`: contract version.
- `request`: original user request.
- `status`: `queued | running | awaiting_review | accepted | provisional | failed | cancelled`.
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
  "objective": "Find primary-source support for the specified claims",
  "input": {},
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
- `max_concurrency`, `status`, `allowed_data_scopes`.
- `cost_profile`: uncached-input, cached-input, and output pricing plus verification, retry, escalation, and orchestration costs; currency, effective date, and source.
- `quality_profile`: benchmark ID, task domain/role, sample size, verified accuracy lower bound, hallucination upper bound, evaluation date, and evaluator version.

A capability match is necessary but not sufficient: a model must also have a current quality profile that qualifies for the task's domain and quality tier.

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
- **Hallucination rate** = unsupported, fabricated, or source-contradicted material factual claims / all material factual claims evaluated.
- **Evidence coverage** = material factual claims with traceable, relevant evidence / all material factual claims.

Every material external factual claim must include evidence. A verifier must check both that the source exists and that it supports the specific claim. A citation that merely mentions the same topic is insufficient.

Quality is certified from a held-out, independently labelled evaluation set, stratified by task type and domain. Use one-sided 95% exact binomial confidence bounds (Clopper-Pearson) for the accuracy and hallucination rates. As a reference point, zero observed errors in 299 independent evaluated claims gives a one-sided 95% upper bound below 1%; correlated claims from one document or one task do not count as 299 independent observations. Increase the sample when errors occur or when observations are clustered.

A result may be labelled `certified` only when both the producing model's and the independent verifier's applicable evaluation profiles meet both statistical targets and the run's claims pass evidence verification. Otherwise:
- use `provisional` when the content is useful but the statistical target is not yet demonstrated;
- use `needs_review` when evidence is missing, sources conflict, or the independent verifier disagrees;
- use `rejected` when the result contains unsupported/contradicted material claims or fails its output contract.

The primary agent must not verify itself. The verifier must use a different agent identity and model/provider version from the producer and, where feasible, be blind to the producer's provider/model identity and self-reported confidence. A disputed material claim goes to an independent adjudicator or human review; do not average contradictory claims into a false consensus.

If no available model or agent meets the quality target for a task domain, report that limitation and withhold a certified answer. Do not lower the threshold to make the pipeline appear successful.

## Model selection and total-cost policy

The default routing rule is: choose the lowest-total-cost model among candidates whose measured quality is the same or better for the task's role and domain.

A model is eligible only when its current evaluation profile meets the applicable quality thresholds. Among eligible models, minimize expected end-to-end task cost:

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
1. Filter candidates by task capability, data scope, current quality profile, deadline, and remaining budget.
2. Calculate expected end-to-end cost using observed retry and verification rates for that role/domain.
3. Choose the lowest-cost qualified candidate.
4. If the result fails schema/evidence/quality checks, retry or escalate only within the task's attempt and cost budgets.
5. Record actual cost and quality outcome so future estimates improve.

When two candidates have statistically indistinguishable quality and both meet the target, choose the one with lower expected total cost. When quality is not comparable or confidence bounds overlap the threshold, do not assume equivalence; use the better-supported candidate or mark the result provisional.

## Lease, retry, and idempotency rules

- A task claim creates a random lease token and expiry. Only that agent/token pair may heartbeat, submit, or fail the task.
- A lease expiry re-queues the task only while attempts and budget remain; the old lease token becomes invalid.
- Result submission is idempotent by task/attempt/result ID. Replaying a completed submission must not duplicate state transitions or costs.
- A worker cannot claim a task whose dependencies are incomplete, whose capability set does not match, or whose task budget/deadline has expired.
- Every automatic retry is bounded by `max_attempts`, task cost budget, and run cost budget. No unbounded self-spawning or recursive delegation.
- A run is accepted only after all required tasks are accepted and the final quality gate passes.

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
