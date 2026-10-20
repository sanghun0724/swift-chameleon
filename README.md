# SwiftChameleon

SwiftChameleon shows an AI coding agent relevant Swift implementations from your repository before it edits code. It derives structural patterns and uses Git history to prefer recent implementations within a compatible role.

This independent project is based on [Chameleon](https://github.com/crisnahine/chameleon). The upstream history and MIT license are retained. The original project documentation is preserved in [upstream-readme.md](docs/upstream-readme.md).

## Swift support

- Parse Swift declarations, inheritance and protocol-adoption syntax, attributes, imports, and callable signatures with tree-sitter.
- Match implementation examples by role and source structure.
- Prefer recent Git changes without renewing age for whitespace-only edits or pure file moves.
- Deliver examples automatically through Claude Code's pre-edit hook.
- Expose the same context through MCP for other agents.

Swift support is extraction and contextual guidance. It does not provide compiler type resolution, macro expansion, a complete call graph, or Swift convention blocking. New files have path evidence until their source exists. Comments and identifier changes still count as Git changes.

## Install locally in Claude Code

Install `uv` and Node.js 20 or newer. In this checkout, run:

```sh
cd plugin/mcp
uv sync --frozen --extra dev
```

Add this checkout as a local marketplace in Claude Code:

```text
/plugin marketplace add /absolute/path/to/swift-chameleon
/plugin install swift-chameleon@swift-chameleon
```

Restart Claude Code. Open the Swift repository you want to analyze, then run:

```text
/chameleon-init
/chameleon-trust
```

The initial release retains the upstream `/chameleon-*` commands, `.chameleon` profiles, `CHAMELEON_*` settings, and Python package names. Use either this plugin or upstream Chameleon in a session. Loading both duplicates hooks and tool registrations.

## Retained upstream commands

The plugin also retains `/chameleon-explain`, `/chameleon-pr-review`, `/chameleon-receiving-code-review`, and `/chameleon-deep-work`. See [the upstream command guide](docs/upstream-readme.md) for their workflows. These commands do not add Swift compiler analysis or Swift lint enforcement.

## Connect through MCP

The server runs locally over stdio:

```sh
uv run --project /absolute/path/to/swift-chameleon/plugin/mcp --frozen chameleon-mcp
```

For Codex, register that command:

```sh
codex mcp add swift-chameleon -- uv run --project /absolute/path/to/swift-chameleon/plugin/mcp --frozen chameleon-mcp
```

Ask the agent to call `chameleon_lifecycle` with action `bootstrap_repo` and the repository path. Review and trust the resulting profile through action `trust_profile`. Call `get_pattern_context` with the absolute Swift file path before editing.

MCP supplies tools. This project does not install an automatic Codex pre-edit hook or modify your agent settings. Claude Code's hook integration is the automatic delivery path.

## Verify changes

```sh
cd plugin/mcp
uv sync --frozen --extra dev
uv run ruff check chameleon_mcp/ ../../tests/unit/
uv run ruff format --check chameleon_mcp/ ../../tests/unit/
cd ../..
PYTHONPATH=. plugin/mcp/.venv/bin/python -m pytest tests/unit/ -q
```

See [the implementation plan](docs/swift/PLAN.md) and [verification evidence](docs/swift/verification.md) for the release scope and unrun checks.

## Attribution

Copyright for the upstream implementation remains with Cris Nahine. See [LICENSE](LICENSE) and [NOTICE](NOTICE). This project is independently maintained and is not an upstream Chameleon release.
