# Scanner Rules

Use this reference to explain scanner results and decide release impact.

| Rule ID | Default severity | Blocks release | Meaning |
| --- | --- | --- | --- |
| `ai-context-file` | high | yes | AI instructions or project memory may expose architecture, internal workflows, endpoints, or safety assumptions. |
| `mcp-config` | high | yes | MCP config can expose local tools, permissions, endpoints, or inline credentials. |
| `debug-source-map` | high | yes | Source maps and debug symbols can reconstruct private source and prompt logic. |
| `secret-file` | critical | yes | Credential files are present in the artifact. |
| `chat-or-memory-log` | high | yes | AI chats, memory, or tool logs may contain private code, prompts, credentials, or user data. |
| `private-key-material` | critical | yes | Private key text was detected. Rotate and investigate. |
| `token-like-secret` | critical | yes | Token-like secret text was detected. Rotate and replace with secret manager/env usage. |
| `source-map-pointer` | high | yes | Production bundle points to a source map. |
| `source-map-content` | high | yes | Source map embeds original source. |
| `internal-trace` | medium | review | Internal feature flags, ticket IDs, debug markers, or private traces are present. |
| `ai-data-share-risk` | high | yes | Model/training data URLs or SAS-like tokens may expose AI data stores. |

Release exceptions require an allowlist entry with `rule_id`, path glob, and a concrete reason.
