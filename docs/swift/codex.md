# Use SwiftChameleon with Codex

SwiftChameleon exposes repository context through MCP and native Codex hooks. The hooks supply examples. They do not enforce edits or provide Swift compiler analysis.

## Prepare the local server

From this checkout, install the locked dependencies:

```sh
uv sync --frozen --project plugin/mcp
```

Register the server using the absolute checkout path:

```sh
codex mcp add swift-chameleon --env CHAMELEON_CONVENTIONS_MD=0 -- uv run --project /absolute/path/to/swift-chameleon/plugin/mcp --frozen chameleon-mcp
```

`CHAMELEON_CONVENTIONS_MD=0` disables the inherited Claude memory-file export during profiling. No Claude CLI or Claude authentication is needed.

In Codex, ask for `chameleon_lifecycle` with action `bootstrap_repo` and `params.path` set to your Swift repository's absolute path. Review the resulting profile, then use action `trust_profile` with the same repository path and its directory name as the confirmation token. Native hooks never bootstrap or grant trust automatically.

## Configure native hooks

Add these entries to the target Swift repository's `.codex/config.toml`. Replace the checkout path in both commands.

```toml
[[hooks.SessionStart]]

[[hooks.SessionStart.hooks]]
type = "command"
command = 'uv run --project "/absolute/path/to/swift-chameleon/plugin/mcp" --frozen python -m chameleon_mcp.codex_hooks'
timeout = 30
additionalContextLimit = 24000

[[hooks.PreToolUse]]
matcher = "^apply_patch$"

[[hooks.PreToolUse.hooks]]
type = "command"
command = 'uv run --project "/absolute/path/to/swift-chameleon/plugin/mcp" --frozen python -m chameleon_mcp.codex_hooks'
timeout = 30
additionalContextLimit = 24000
```

Open Codex in the target repository and trust the project so its `.codex/config.toml` is loaded. Use `/hooks` to review and trust both hook definitions, then start a new session. Installing a hook definition does not grant trust automatically. Hooks are enabled by default in the evaluated Codex CLI 0.163.0. The [official Codex hook reference](https://learn.chatgpt.com/docs/hooks) describes configuration and trust.

SessionStart supplies up to six examples derived from the trusted profile. PreToolUse reads native `apply_patch` paths and supplies matching Swift context. New files retain path-only provenance. Changes made through shell commands do not have equivalent per-file coverage.

The adapter respects profile trust, pause, repo skip and the `CHAMELEON_DISABLE=1` switch. Invalid input or unavailable context returns an empty hook response. It does not write Claude settings or a statusline. Existing profile helpers may maintain local caches and trust metadata.

## Inspect delivery

For local diagnosis, append `--trace /absolute/path/to/delivery.jsonl` to the hook command. The trace contains the context emitted by the hook. Keep it private because it includes repository source excerpts.

The automated generation study uses fresh per-session configuration and explicit trust bypass only for its vetted hook command. That execution detail is not a recommendation to bypass trust for arbitrary project hooks.
