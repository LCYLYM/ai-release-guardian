# AI Prompt And Agent Hygiene

AI agent projects create new sensitive assets. Audit these before release:

- Project instructions: `CLAUDE.md`, `AGENTS.md`, `.cursor/rules`, skill references.
- Local state: memory, chat exports, tool logs, eval traces, generated summaries.
- Tooling config: MCP server definitions, allowlists, local endpoints, sandbox policies.
- Prompt defenses: system prompts, injection tests, red-team notes, safety assumptions.
- Model/data links: training data URLs, checkpoints, SAS tokens, bucket links.

Sanitized examples are acceptable when they are clearly synthetic and cannot be mistaken for production configuration.
