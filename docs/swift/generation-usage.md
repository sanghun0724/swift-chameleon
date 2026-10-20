# Run the Swift generation study

Use macOS, install the plugin's Python dependencies, sign in to Codex CLI, and
install a Swift 6 compiler. This runner uses Codex only. It does not call Claude or any
paid reviewer subprocess.

Use the plugin virtual environment so the native hook adapter resolves from
the same installation as profile derivation.

```bash
plugin/mcp/.venv/bin/python -m tests.effectiveness.swift_generation \
  --mode prepare --run-dir "$PWD/tests/effectiveness/results/cedar-prepare"

plugin/mcp/.venv/bin/python -m tests.effectiveness.swift_generation \
  --mode pilot --run-dir "$PWD/tests/effectiveness/results/cedar-pilot"

plugin/mcp/.venv/bin/python -m tests.effectiveness.swift_generation \
  --mode run --run-dir "$PWD/tests/effectiveness/results/cedar-run"

plugin/mcp/.venv/bin/python -m tests.effectiveness.swift_generation_report \
  "$PWD/tests/effectiveness/results/cedar-run" \
  "$PWD/tests/effectiveness/results-published/cedar-run"
```

Use a new output directory for every command. `prepare` derives one profile
without starting a model. `pilot` starts one non-generation session and checks
native hook delivery. `run` executes the fixed 20-cell schedule. A cell has a
360-second wall timeout. The runner records token usage, not dollar spend.

`--python` can point at another installation of the same frozen adapter. The
published study records the exact adapter and runner hashes used. Changing the
fixture, prompts, model, or hook behavior requires a new preregistration.

Each cell gets a fresh Codex home containing only a private authentication copy.
It loads no user config, rules, plugins, or project instructions. The runner
registers authentication-copy removal at process exit. If it is killed with
SIGKILL, remove only the generated `*/codex/auth.json` copies before archiving
its private run directory. The publisher copies an explicit artifact list and
never includes Codex homes, auth files, or plugin storage.

Give only `blind/` to an independent reviewer. Keep `mapping.json`,
`metrics.json`, and `evidence/` out of that review session. The blind directory
contains every output, including source and optional model-written tests.
The evidence directory contains sanitized actual tool and hook transcripts.
The held external executable checks determine behavior results.

Setup and assessment errors remain in the planned denominator. Their error
phase, session errors, and unavailable workspace state are retained in metrics.
Authentication stops dispatch; the private schedule keeps the remaining cells
as `not_run`. Publishing requires all 20 registered cells to have a recorded
outcome, so a stopped partial run remains a private forensic record.

The exact-byte scope proxy flags any pre-existing Swift file changed outside
composition, including `Package.swift` additions for useful new test targets.
Keep that raw proxy result and explain disagreements with source review.
Do not interpret it as a semantic scope judgment.
