# Release Checklist

## GitHub Open Source

- Run tests and the scanner before the first public push.
- Search for local paths, session logs, generated records, screenshots with secrets, and raw prompts.
- Keep research reports sourced, but do not include leaked file bodies, mirrored source maps, or exploit paths.
- Add MIT license and make repository topics match real capabilities.

## npm / CLI

- Prefer `package.json` `files` allowlists over `.npmignore` deny-only publishing.
- Run `npm pack --dry-run --json` and scan that JSON output.
- Scan the actual `.tgz` before publish.
- Do not publish public source maps or `sourcesContent`.

## App / Desktop Artifact

- Scan the built `.ipa`, `.apk`, `.app`, `.asar`, `.dmg`, zip, or tarball.
- Treat bundled Markdown, prompts, debug symbols, source maps, and MCP config as release assets.
- Do not assume platform review catches internal documentation leaks.

## Codex Plugin / Skill

- Keep plugin files repo-local unless the user explicitly requests installation.
- Do not write `~/.codex`, `~/.agents`, or global config during packaging.
- Validate `SKILL.md` frontmatter and keep references one level deep.
