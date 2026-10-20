# Native Codex adapter review record

The first review preceded the frozen generation study. Boundary fixes landed only after all 20 generation cells completed. The final adapter was independently reviewed again.

## Initial findings

# Codex adapter review

Reviewed `plugin/mcp/chameleon_mcp/codex_hooks.py` and `tests/unit/test_codex_hooks.py` without changing repository files.

## Findings

1. P2. A patch targeting a nested repository bypasses that repository's skip marker. `context_response` checks suppression for the repository found from `request.cwd`, at lines 205 to 211. `_collect_context` then calls `get_pattern_context` separately for each target, at lines 164 to 168. That call can select a different nested repository. The public context tool intentionally leaves `repo_skip` and session disable enforcement to hooks, so the adapter emits context from the skipped child. A parent Git repository, trusted child Swift fixture, child `.chameleon/.skip`, and parent-relative patch produced `additionalContext` instead of `{}`. The reproducer is `/tmp/test_codex_adapter_review.py`. Running `PYTHONPATH=.:plugin/mcp plugin/mcp/.venv/bin/python -m pytest /tmp/test_codex_adapter_review.py -q` produced one failing assertion. Apply suppression to each target's actual repository and session, or refuse targets whose repository differs from the request repository.

2. P2. An optional FIFO trace destination hangs the hook before it emits its response. The `os.open` call at line 262 uses `O_WRONLY | O_CREAT | O_APPEND | O_NOFOLLOW` but does not use `O_NONBLOCK` or validate the opened descriptor as a regular file. Opening a FIFO without a reader blocks. A local subprocess calling the actual `main()` with `--trace` pointing at an `os.mkfifo` artifact timed out after two seconds with no hook JSON. Use a nonblocking open, validate `fstat` as a regular file, and fail open on an unsuitable trace destination.

Neither finding affects the current trial setup when cwd and target belong to the same repository and each trace destination is a fresh regular file. These findings do not justify changing the frozen trial source midway through its run.

## Verification

The existing scoped test file passed. `PYTHONPATH=. plugin/mcp/.venv/bin/python -m pytest tests/unit/test_codex_hooks.py -q` reported 23 passed in 9.02 seconds.

Reviewed malformed request handling, native patch header offsets, move destination containment, parent traversal, symlink refusal, trust checks, source provenance for absent paths, bounded path and context counts, and output caps. No additional actionable correctness issue was demonstrated in those paths. This was a scoped adapter review. The repository-wide QA matrix was not run.

The Prove It Works principle changed the review by requiring direct execution of the nested-repository skip case and FIFO trace case rather than relying on inspection alone.

## Scoped comment review

There are no inline comments or suppressions in either scoped file. The module docstring and `context_response` docstring describe their public contracts and are allowed by the Comment Sicko public API exception. Comment deletion count is zero. There are no MUST KILL flags, restorations, application-code edits, or user-wide setting changes.


## Final review

# Native Codex adapter final review

## Verdict

No blocking findings in the scoped final adapter, tests, or Codex setup guide.

Reviewed `plugin/mcp/chameleon_mcp/codex_hooks.py`, `tests/unit/test_codex_hooks.py`, and `docs/swift/codex.md`. Repository files were not changed. Only the focused adapter suite was executed. No Claude process, LLM generation, Windows validation, or Linux validation was run.

## Evidence

`PYTHONPATH=. plugin/mcp/.venv/bin/python -m pytest tests/unit/test_codex_hooks.py -q` completed with **27 passed in 10.72 seconds**.

The prior nested-repository suppression finding is resolved. `_collect_context` resolves each target's repository before calling the context API and applies `is_chameleon_suppressed` with that repository's computed identity and the original session ID. The same repository resolver drives the context API. The two parametrized regressions first demonstrate context is available with parent cwd and a trusted child repository, then verify an empty response after the child's `.skip` or signed session-disable marker is set. This prevents a vacuous pass caused by missing context.

The prior FIFO trace blocking finding is resolved. The trace destination is opened with `O_NONBLOCK`, and `fstat` must identify a regular file before any trace bytes are written. The real-process regression without a FIFO reader completes within its five-second bound and emits `{}`. The additional real-process regression with an available reader completes and verifies that no bytes enter the FIFO. Existing regular-file trace delivery continues to pass.

Reviewed malformed input fail-open behavior, bounded patch paths and context output, move containment, forbidden segments, symlink rejection, trust and pause checks, session identity forwarding, and native hook response shape. No additional blocking issue was demonstrated. The guide correctly describes context delivery rather than edit enforcement and states the limitation for shell-generated edits.

The generation study used its frozen earlier adapter. These fixes were applied after all 20 cells completed. Passing final edge-case regressions does not retroactively make those fixes part of the measured study source.

## Scoped comments

No inline comments or lint suppressions exist in the scoped Python files. The module docstring and response-function docstring state public contracts and meet the Comment Sicko public API exception. Zero comment deletions, zero MUST KILL findings, zero restorations, and no application-code edits.

## Principles applied

Boundary Discipline focused the review on target repository identity and filesystem trace boundaries. Prove It Works required real subprocess FIFO assertions and a fresh focused test run instead of accepting the implementation summary.
