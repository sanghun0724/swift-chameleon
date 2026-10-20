# Swift generation evaluation review

Reviewer reviewed the current runner, fixture, publisher, regression tests, preregistration and usage guide. No model generations were started. No repository files were edited.

## Actual study

The inspected design uses two organic tasks, five paired repetitions each, fresh workspaces, the same requested Codex model and reasoning, alternating order, and identical initial source/history. Native context is the intended treatment. The held Swift executable checks cover the requested APIs and representative failure/boundary cases. The design explicitly limits inference to one small fixture and one model.

The published metrics include all 20 actual cells. Both arms have 10 behavior passes. Both blinded static review arms receive 4/4 on all four dimensions. The correct interpretation is no measured quality improvement in these tasks. Static judge agreement is not independent runtime verification. Timing and tokens are descriptive subscription usage, not demonstrated speed or dollar savings.

The latest legacy fixture edit changes visibility and introduces an initializer. The corrected design explicitly identifies it as substantive and says this experiment does not isolate recency priority. The exact-byte scope proxy incorrectly treats useful Package.swift test target additions as unrelated changes. This is now disclosed and separated from semantic scope review.

## Runner corrections confirmed by source inspection

run_cell catches setup/profile/session/assessment exceptions, keeps success false, preserves a completed session if assessment fails, and removes copied auth in finally. The planned schedule retains undispatched entries after authentication failure. These changes were made after the frozen run and must remain distinguished from frozen study provenance.

The publisher now replaces the current developer home without a hardcoded personal path. It records original and published provenance hashes separately. A scan of the 585 published files found no /Users/ paths or access_token/refresh_token strings. The only auth.json matches were three source-code filename references in frozen runner provenance, not credentials.

## Finding corrected and rechecked

P2 was confirmed in the earlier publisher. A completed 20-cell record containing a setup failure was rejected by source identity validation, and assessment error details were omitted. The worker corrected it. The current publisher compares prepared fixtures only, preserves missing-workspace cells with an opaque unavailable marker, and retains sanitized status/error/collection_error/session_errors/workspace_available fields. Completed registered errors remain in all 20 published metrics. Authentication-blocked incomplete runs remain private records with a complete planned schedule and are intentionally not publishable as a completed study.

I independently ran `python -m pytest tests/effectiveness/tests/test_swift_generation.py -q` using the plugin virtual environment after the correction. All 14 tests passed in 2.22 seconds. These include profile failure retention, assessment timeout retention, authentication-stop schedule preservation, full patch coverage, and publication of 19 setup errors plus one prepared assessment timeout. No LLM generation was invoked.

I also independently recomputed the actual published evidence counts and hashes. There are 20 unique labels, 20 successes, one initial source hash, one fixture commit, and every published provenance hash matches its file. No blocking evaluation-plumbing defect remains in the reviewed scope. This does not claim that failure recovery changes were exercised by the frozen all-success study.

## Principle applied

Explain the Number changed the verdict to a tied, ceiling-limited result. Correct context delivery proves the integration executed. It does not prove a quality improvement when unaided outputs already pass every held check.
