# Swift generation study preregistration

Status: Codex method fixed on 2026-10-21 before generation cells started.

The question is whether SwiftChameleon's derived context improves one model's
implementation of two small Swift features. This is a single-model study on an
independently authored fixture. It cannot establish general Swift quality or
safety. The user explicitly requires Codex. No Claude generation sessions run.

## Fixed design

- Use Codex CLI 0.163.0, exact model identifier `gpt-6-astra`, medium reasoning.
- Run two tasks, five repetitions per arm per task, for 20 cells.
- Alternate AB and BA within each task. Reverse the first order for task two.
- Use one unchanged organic prompt per task. Do not include grading criteria.
- Use a fresh repository, plugin data directory, Codex home containing only an
  auth copy, and temporary directory for every cell. Never resume or retry.
- Ignore user configuration and execution rules. Set `project_doc_max_bytes=0`
  to suppress unrelated project/user instructions. Disable multi-agent work.
- A has no plugin, profile, mirror, hook, or convention instructions. B uses
  real derived profile output through native SessionStart and PreToolUse hooks.
- B invokes the shipped `chameleon_mcp.codex_hooks` adapter. It emits only
  additional context. It is not Claude-hook or enforcement validation.
- Disable profile refresh and the Claude conventions mirror. Neither arm gets
  extra task-specific instructions, manually taught conventions, or answer code.
- Run each generation session for at most 360 seconds. Run exactly 20 cells,
  without replacements. Stop dispatch if authentication fails.
- Authentication is through the ChatGPT subscription. Codex exposes token
  usage but no dollar costs. No dollar ceiling or measured spend is claimed.
- Record the requested exact model and hook-provided native model metadata
  when available. Codex JSON event output itself does not expose resolved
  model/provider fields. Do not claim that it does.

## Fixture

`CedarStore` is a dependency-free Swift package authored for this study. Current
Repository and UseCase examples use protocols, immutable injected dependencies,
`ShopResult`, and shared DTO conversion. Two older examples use concrete
 dependencies and optionals. Git history has an older legacy implementation,
three current same-role examples, and a newer cosmetic edit to legacy code.
All cells start from identical source bytes and history.

Task one adds shipping quotes through the existing API, domain types, and
`StoreGraph`. Task two adds available pickup locations. Both require mapping,
validation, failure behavior, and composition work. Neither asks for style
adherence or identifies a preferred example. The organic requests name exactly
the entry points that the held executable checks call.

Candidate directories, source names, and prompts use ordinary project names.
The runner, held executable checks, this document, and judge instructions stay
outside those directories. Source and transcripts contain no company code.

## Held criteria

Each cell receives six independently reported dimensions. Generation failures
remain in the planned denominator. These include empty output, API errors,
timeout, compile failure, and missing requested entry points. Preflight probes
are separate from generation and never included in generation rates.

1. Changed sources compile with the recorded Swift compiler.
2. Held executable cases preserve success values, map transport failures,
   reject invalid shipping amounts, filter/deduplicate/sort pickup locations,
   preserve the requested identifier, and avoid API calls for blank identifiers.
3. Dependencies cross Repository and UseCase boundaries through protocols and
   constructor injection, as in current examples.
4. Implementations preserve `ShopResult` and existing domain entities.
5. Implementations reuse `TransportReply.domain` and `PickupCatalog.available`
   where applicable instead of duplicating those operations.
6. Existing unrelated source behavior is preserved without broad rewrites.

Behavior has priority over convention. Structural checks are explicit proxies,
not a semantic quality guarantee. An independent judge sees all outputs on one
scale under opaque labels, with neither model nor arm mapping. It scores
correctness, maintainability, local consistency, and scope from 0 to 4, gives
source evidence, and states uncertainty. The mapping is stored separately.

## Evidence and reporting

Keep every stream transcript, stderr, patch including untracked files, source
snapshot, held-check result, hook response, tool invocation, terminal reason,
and token usage. A patch does not prove a clean exit. Check actual tool events
and hook delivery rather than accepting the worker's summary.

Report per-task and pooled rates with all planned cells as the denominator,
paired wins/ties/losses, tokens, failures, and judge disagreements. With only
five pairs per task, an uncertain or tied result is a valid outcome. Do not
claim broader quality improvement from deterministic context plumbing.

## Method change before execution

An initial Claude authentication probe failed before any generation cells.
The user then explicitly required Codex. The parent verified Codex login and
approved this separate method before trials. The failed probe is preserved as
preflight evidence only. There is no remaining Claude requirement.

## Work checklist

1. Frame.
2. Set up sanitized environments.
3. Author one organic prompt.
4. Spawn N parallel candidates. Use sequential paired CLI cells as the approved
   exception to control order and keep per-cell evidence independent.
5. Spawn one blinded judge. The parent owns this independent judge.
6. Verify the chain from transcripts, not self-report.
7. Read every candidate output yourself.

Throughput checkpoint: fixture setup and profiling are free local work. The
20 sequential sessions have a 120-minute worst-case wall ceiling. Compile/run
checks follow each session. A pilot must prove actual native hook delivery
before the registered cells start.
