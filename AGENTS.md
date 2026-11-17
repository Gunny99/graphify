## graphify

This project has a graphify knowledge graph at graphify-out/.

Rules:
- When working on Graphify itself, use the repository's existing Graphify guidance. For codebase questions, prefer scoped graph queries where available; use the report for broad orientation. Do not use the graph as evidence when the task concerns the graph's correctness itself.
- If graphify-out/wiki/index.md exists, navigate it instead of reading raw files
- After modifying code files in this session, run `graphify update .` to keep the graph current (AST-only, no API cost)
## Command execution (RTK)

- Use Rust Token Killer from rtk-ai/rtk as the command proxy for verbose shell operations: rtk git ..., rtk gh ..., rtk uv ..., rtk pytest ..., and rtk test <command...>.
- Verify the correct binary once per environment with rtk --version and rtk gain. The savings dashboard from rtk gain distinguishes Rust Token Killer from the unrelated Rust Type Kit package.
- Do not install the ambiguous crates.io package with cargo install rtk; use the official installer or the explicit https://github.com/rtk-ai/rtk Git source.
- RTK is an output-filtering wrapper, not a source-code transpiler. Preserve Graphify's existing Python runtime and use Rust for RTK itself and any separately approved native Rust components.
- Keep telemetry disabled unless a developer explicitly opts in: RTK_TELEMETRY_DISABLED=1.
- If a command has no RTK filter or filtered output would hide evidence needed for diagnosis, run the underlying command directly and preserve its complete output.
