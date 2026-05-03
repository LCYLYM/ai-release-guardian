---
name: ai-release-guardian
description: "Use when reviewing, preparing, or publishing release artifacts, open-source repos, npm packages, mobile/desktop apps, CLIs, Codex plugins, AI agent projects, or archives for AI-era privacy and security leaks: CLAUDE.md, AGENTS.md, source maps, prompt files, memory logs, MCP configs, secrets, local paths, debug artifacts, and release-blocking governance issues."
---

# AI Release Guardian

Use this skill before any public release, open-source push, npm package publish, App Store submission, plugin packaging, or artifact handoff.

## Operating Rule

Scan the artifact that will actually ship. Do not stop at source inspection. Do not treat "no API key found" as "safe" when AI context, prompts, memory, source maps, or MCP config are present.

## Workflow

1. Identify the real artifact: repo root, built archive, `.ipa`, `.apk`, `.asar`, npm tarball, zip, tarball, or `npm pack --json` output.
2. Run the local scanner from the project root when available:

```bash
python3 scripts/ai-release-guardian scan <artifact-path> --format json --fail-on high
```

3. Read `references/rules.md` when explaining findings or deciding severity.
4. Read `references/release-checklist.md` when preparing a GitHub, npm, app store, or plugin release.
5. Read `references/ai-prompt-hygiene.md` when the project contains prompts, memory files, MCP config, local tool logs, or AI agent instructions.
6. Report concrete findings with path, rule id, severity, impact, and fix. If scan cannot run, state the exact blocker.

## Required Release Gate

- High or critical findings block release unless a written allowlist entry names `rule_id`, `path`, and `reason`.
- Allowlists must be reviewed as release exceptions, not hidden defaults.
- Synthetic examples and sanitized sample config are allowed only when clearly named as examples and free of live credentials.

## What To Look For

- AI context: `CLAUDE.md`, `AGENTS.md`, `.claude/`, `.cursor/`, prompt manifests.
- Debug reconstruction: `*.map`, `sourcesContent`, `sourceMappingURL`, `*.dSYM`.
- Runtime privacy: chat transcripts, memory caches, tool logs, database dumps.
- Tooling secrets: `.env*`, private keys, MCP configs, cloud tokens, SAS URLs.
- Internal traces: unreleased feature flags, ticket IDs, debug build markers, private endpoints.
