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

At the initial 4.11.0 checkpoint, no paid Claude editing journey, live user-installed plugin session, cross-platform CI, compiler semantic analysis, or company-code evaluation was run. Hook delivery and MCP transport were exercised locally using generated fixtures. This establishes extraction and delivery behavior, not a measured improvement in LLM-generated code quality. No user-wide plugin or MCP settings were installed.

GitHub returned 404 for the requested `sanghub0724` name. The authenticated personal account is `sanghun0724`, so the coordinator inferred a spelling error under the autonomous execution grant. The private repository `sanghun0724/swift-chameleon` has been created and its owner and visibility verified. The reviewed implementation has been pushed to `main`; its remote SHA matched the local commit. The repository retains upstream history and MIT attribution.

A separate GPT-6 Astra audit checked the decision trail. Earlier pending checkpoints are superseded by the final results above. Sol and Astra are both GPT models, so this is independent model review without a different model family. The account spelling correction is an inference; repository ownership and private visibility are verified facts.


## Codex follow-up (2026-10-21 KST)

The user requires Codex only and canceled cross-platform CLI validation. The follow-up therefore uses native Codex hooks, actual Codex generation, and macOS CI. No Claude generation sessions ran.

### Native adapter

`chameleon_mcp.codex_hooks` calls the existing trusted context API from SessionStart and native apply_patch PreToolUse. The setup guide requires both project trust and hook trust. It does not bootstrap or trust a profile automatically, and it provides context rather than enforcing Swift conventions. Shell edits have no equivalent per-file coverage.

The initial independent review reproduced a FIFO trace hang and nested-repository suppression bypass. Three regression cases failed before the fix. After all generation cells completed, the adapter gained per-target repository/session suppression and nonblocking, regular-file-only trace writes. All 27 adapter tests passed, and a fresh read-only reviewer independently ran the same 27 tests with no blocking finding. See [the review record](codex-review.md).

Version 4.12.0 was built as a wheel and installed in a fresh virtual environment. Its installed adapter ran as an actual subprocess and returned valid empty JSON for invalid input. Ruff lint/format passed across the 598 files in the inherited CI scope. Version consistency, derived counts and the import-cycle check passed.

The local combined unit, journey-harness and effectiveness-harness checkpoint passed **7,666 tests with 3 skipped in 307.78 seconds**. This checkpoint includes the 27 adapter tests and precedes the additional generation-runner robustness tests. It is not an additive count over earlier checkpoints. The exact output is [preserved](validation/codex-full-suite.txt).

### Actual generation study

Two independently authored Swift tasks each ran five paired repeats. All 20 planned cells completed without replacements or retries. A had no profile or hooks. B received context through the actual native startup and edit hooks. All initial source hashes and fixture commits matched. Every session produced actual completed tool events and a completed turn. Authentication copies were removed after execution.

| Measure | A: unaided | B: native context |
| --- | ---: | ---: |
| Completed sessions | 10/10 | 10/10 |
| Swift 6 compile and held behavior checks | 10/10 | 10/10 |
| Protocol/DI, domain-type, shared-helper proxies | 10/10 each | 10/10 each |
| Actual startup and edit context delivery | 0/10 | 10/10 |
| Total input tokens, including cached input | 1,996,939 | 2,115,447 |
| Cached input tokens, already included above | 1,715,456 | 1,823,744 |
| Output tokens | 21,744 | 20,697 |

The candidate model was requested as `gpt-6-astra`, medium, using Codex CLI 0.163.0 and macOS Swift 6.4. CLI events do not expose a resolved provider/model field. Subscription-authenticated CLI usage reports tokens, not dollar spend. No dollar cost or dollar ceiling is claimed.

An independent, blinded `gpt-6.1-sol` reviewer read all 20 complete outputs and patches. Correctness, maintainability, consistency and scope each received 4/4 for every sample. This is static review, separate from the held executable checks. The 10 paired comparisons were all ties. The parent independently read all unique generated production and test files and verified every session's actual tool and terminal events.

The registered exact-scope proxy failed for all 20 outputs because each added useful Package.swift test-target support. The raw proxy is preserved. The blinded reviewer considered that support within scope, so its semantic scope score was 4/4. This disagreement exposes a proxy limitation; it is not evidence of 20 scope defects.

**The study proves actual context delivery, but does not demonstrate improved generated-code quality.** Both conditions already met the small fixture's requirements. A ceiling effect is a plausible interpretation, not an established cause. One fixture, two tasks, one generation model and a judge from the same GPT family do not establish general Swift quality. The study does not isolate Git-recency ranking. Larger, less obvious repository-boundary tasks would require a separate preregistered study.

The study froze adapter SHA256 `d4cb18223ae991808279801ba69bfa75cd3aff70695c001159757e68a20e2799`. The final adapter's FIFO and nested-repository fixes came afterwards, outside the study's fixture domain. Frozen provenance and published presentation hashes are retained separately. See [the generation protocol](generation-design.md), [reproduction guide](generation-usage.md), and [all artifacts](../../tests/effectiveness/results-published/swift-generation-codex-20261021/run.md).

### macOS CI

The [macOS baseline run](https://github.com/sanghun0724/swift-chameleon/actions/runs/39455246446) passed on Python 3.11, 3.12 and 3.13, each with 7,637 passed and 5 skipped. These are repetitions of the same suite, not independent tests to sum. The final integration run is recorded after the generation-runner review and publication checkpoint. Windows and Linux validation is skipped at the user's request.

The [final source integration run](https://github.com/sanghun0724/swift-chameleon/actions/runs/39459681285), head `593245cf6169f1ce7f093fdc72582be919dc0097`, completed successfully on all three macOS Python versions. Each job reported **7,678 passed and 5 skipped**. This includes the 27 native-adapter tests and 14 new generation-harness tests. Ruff, formatting, versions, derived counts, import cycles, portable paths, and manifest references passed. The [API summary](validation/macos-final-source.json) records the tested head and job conclusions. The subsequent commit records CI evidence only and changes no product code.
