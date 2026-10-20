# SwiftChameleon verification

## Environment

Verification runs on macOS with Python 3.13.15, tree-sitter 0.26.0, tree-sitter-swift 0.7.4, Node.js 23.11.1 and Ruby 3.4.7 with Prism. Dependencies come from the committed uv and npm lockfiles. The independent engine release is 4.11.0 because inherited profiles require engine version 3.0.0 or newer.

## Evidence

| Check | Result | Evidence |
| --- | --- | --- |
| Upstream extraction and recency baseline | 38 passed | `test_spec_driven_lang.py`, `test_canonical_recency_git.py` before changes |
| Original full unit baseline | 7200 passed, 54 skipped, 7 failed | [upstream-baseline.log](validation/upstream-baseline.log) |
| Baseline failure repair | 80 passed | Existing TypeScript dependency installed, existing Ruby with Prism selected, statusline tests isolated from personal settings |
| First full integrated run | 7366 passed, 3 skipped, 3 failed | [first-full-run.log](validation/first-full-run.log) |
| First integration failure repair | 33 passed | README command references restored and Swift added to security registry coverage |
| Swift product matrix | 115 passed | [swift-product.log](validation/swift-product.log) |
| Journey harness library | 67 passed | [harness.log](validation/harness.log) |
| Final full unit run | 7374 passed, 3 skipped | [final-full-run.log](validation/final-full-run.log) |
| Ruff lint and format | Passed | 543 Python files checked |
| Version consistency | Passed | `bash scripts/bump-version.sh --check` |
| Wheel build and isolated installation | Passed | Installed wheel parses a real Swift file and retains typed throws |

The final full unit run is the authoritative combined-tree result. Earlier counts describe earlier checkpoints and are not added together.

## Product assertions

The deterministic fixture creates an actual Git repository with older implementations, a newer implementation, a still newer whitespace-only touch, and a recently changed incompatible protocol. Bootstrap, trust, context, refresh, the real shell hook dispatcher and real MCP stdio transport operate on that repository. Assertions check the selected witness and its text. Malformed hook payloads, disabled delivery, missing or corrupt profile artifacts, and uppercase source extensions have dedicated cases.

History tests preserve changes inside string literals and comments. They cover pure renames, changes at merge resolution, shallow histories, non-Git roots, untracked files, nested roots and bounded fallbacks. Historical parsing ignores formatting trivia, not semantic differences. The bounded shortlist favors recent Git touches before refining token changes. Unknown tracked dates do not receive clone-mtime promotion. A combined rename and formatting change still depends on Git rename detection.

## Reproduce

From the repository root, install dependencies:

```sh
uv sync --frozen --extra dev --project plugin/mcp
npm ci --ignore-scripts --prefix plugin/mcp
```

Use Ruby with Prism on PATH for legacy Ruby backend tests, then run:

```sh
PYTHONPATH=. plugin/mcp/.venv/bin/python -m pytest tests/unit/ -q
PYTHONPATH=. plugin/mcp/.venv/bin/python -m pytest tests/journey/harness/tests/ -q
```

Run the Swift slice separately:

```sh
PYTHONPATH=. plugin/mcp/.venv/bin/python -m pytest tests/unit/test_swift_extraction.py tests/unit/test_swift_detection.py tests/unit/test_swift_context.py tests/unit/test_swift_canonical_history.py tests/unit/test_swift_journey.py -q
```

## Review and remaining limits

The independent [plan review](plan-review.md) preceded implementation. The [implementation review](implementation-review.md) found typed-throws loss and an uppercase-extension role-filter bypass. Both were fixed and independently rechecked. The [comment review](comment-review.md) led to removal of the temporary history grammar override, so tests use production grammar registration.

No paid Claude editing journey, live user-installed plugin session, cross-platform CI, compiler semantic analysis, or company-code evaluation was run. Hook delivery and MCP transport were exercised locally using generated fixtures. This establishes extraction and delivery behavior, not a measured improvement in LLM-generated code quality. No user-wide plugin or MCP settings were installed.

GitHub returned 404 for the requested `sanghub0724` name. The authenticated personal account is `sanghun0724`, so the coordinator inferred a spelling error under the autonomous execution grant. The private repository `sanghun0724/swift-chameleon` has been created and its owner and visibility verified. Push verification remains pending. The repository retains upstream history and MIT attribution.
