# SwiftChameleon plan review

The plan needs the amendments below before implementation. Choose candidate B, the dedicated Swift table. The existing records, walker, profile, trust gate, and context pipeline remain suitable boundaries. A grammar table alone does not complete the runtime integration.

This is a read-only review of the local upstream checkout and `docs/swift/PLAN.md`. I also read `/tmp/swift-chameleon-design-table.md`, including its coordinator refinement. The spec proposal was not present at the time of this report. No tracked file was changed and no tests were run for this review.

## Comparison

| Criterion | Candidate A, LanguageSpec expansion | Candidate B, dedicated Swift table |
| --- | --- | --- |
| Correctness | Existing name lookup reads one field and parameters require a holder. Swift repeats `name`, places parameters directly under functions, and places defaults beside parameters. Correct support needs several new procedural hooks. | Local readers can distinguish declaration keyword, repeated fields, parameter labels, defaults, return types, and attributes. |
| Reuse | Reuses the spec builder but changes its shared abstraction for Swift-specific shapes. | Reuses ParsedFile, ASTSignature, the walker, bounds, clustering, serialization, trust, hook assembly, and MCP. Only grammar interpretation is local. |
| Runtime completeness | Spec registration supplies some automatic detector and capability wiring, but cannot by itself fix context shape selection or Xcode markers. | Requires explicit detector, grammar, table, capability, security extension, and contextual snapshot wiring. The proposal names these seams. |
| Validation | Each new spec option adds regressions for existing languages as well as Swift. | Swift fixtures can assert actual parser facts while existing spec tests demonstrate isolation. Context and hook integration still need separate evidence. |

Candidate B earns its added module because it keeps Swift grammar exceptions together. The table proposal is directionally sound. Its statement that keeping separate top-level kinds alone prevents role mixing is too strong until merge and resolver tests establish that invariant.

## Required amendments

1. Register a dedicated detector and all derived language surfaces explicitly.

`extractors/registry.py` builds extraction detectors through `spec_driven.extractor_classes()`, which iterates `specs.ALL`. `language_support.py::_register_spec_languages` also iterates that list. Swift's dedicated table will not appear in either by itself. `lint_engine.security_language` reads `specs.EXTENSIONS_BY_LANGUAGE`, so its extraction-tier security promise will also be false unless Swift is added to the security recognition boundary. Add explicit Swift registrations or one small shared registry with real consumers. Do not add an empty Swift LanguageSpec just to trigger unrelated registration side effects.

Required evidence includes `select_extractor`, `TreeSitterExtractor.supports`, `language_for_path`, `capabilities_for`, `supported_languages`, actual source discovery, and `security_language` agreeing about Swift. With the grammar absent or the backend disabled, bootstrap must report unavailable rather than an empty successful profile. Keep `lint_engine.detect_language` narrow because it promises actual lint dimensions.

2. Specify Swift contextual snapshots separately from lint dimensions.

`tools.py::_file_shape_snapshot`, around lines 1469 to 1503, recognizes only TypeScript, Ruby, and Python. `_get_archetype_with_loaded` repeats that narrowing around lines 1786 to 1794. Adding a Swift table to extraction leaves existing Swift files without a truthful shape during selection. Use the Swift parser to build a contextual `DimensionSnapshot` through a shared context helper used by both paths. Avoid widening lint detection or enabling Swift conformance enforcement as a side effect.

A new file has only path evidence. Preserve `match_basis=path_only` and a truthful confidence. An unreadable, malformed, unsupported, or budget-exceeded file must not acquire an invented declaration shape. The malformed-file result should remain advisory and state its basis.

3. Make declaration role a hard applicability constraint before recency.

`bootstrap/canonical.py::select_canonicals` currently sorts demotion, recency, typicality, and path. Its demotions recognize Rails abstract bases and NestJS aggregators, with no Swift role check. `bootstrap/clustering.py::merge_shape_clusters` groups by path bucket, default export kind, and JSX before a Jaccard merge. Distinct kinds help exact clustering, but role distinctions can be diluted by files that contain multiple kinds and by later merging. Distinct kinds alone do not prove contextual applicability.

Define how protocol declarations, nominal implementations, and extensions partition or filter witnesses. Preserve that role through exact clustering, sparse merging, shape merging, profile serialization, existing-file archetype scoring, and nearest-canonical selection. The role can be a Swift-specific bucket or another explicit signature fact. Do not overload a fake Swift default export merely to exploit an existing grouping key.

The gate fixture must place protocol, concrete type, and extension in the same path family with similar imports. Commit the protocol most recently. Context for the concrete implementation must still return a compatible implementation. Also cover mixed-role files and a new path whose role is unknown. If a matching role has no eligible safe witness, return a missing or uncertain witness rather than another role with high confidence.

4. Define repository detection for SPM, Tuist, and Xcode, including precedence.

`spec_driven.py::_MARKERS` uses exact files. `_marker_in_child` searches only one directory below the root. `.xcodeproj` and `.xcworkspace` are directory packages. A Tuist repository can place Project.swift deeper under Projects. Merely adding marker strings does not support these forms.

Require real Swift source together with a bounded marker search. Specify supported roots and depth. Test Package.swift, root Project.swift, nested Tuist projects, `.xcodeproj/project.pbxproj`, and workspace-only repositories according to the chosen contract. Include negative fixtures with a vendored `.swift` file, a build manifest alone, excluded `.build` content, and unrelated JavaScript or Python tooling. State whether Package.swift and Project.swift are build configuration witnesses or are excluded from application archetypes.

A dedicated Swift detector must preserve the intended Python manifest precedence explicitly. `_resolve_first_class_precedence` currently runs only when the candidate is a SpecDrivenExtractor. A separate Swift class can bypass that logic. Test Swift with a Python helper and Python with Swift tooling. Also document the existing TypeScript and Ruby precedence for repositories containing their strong manifests.

5. Make substantive history and fallback semantics precise.

The current `_build_commit_time_map` uses `git log --no-renames --name-only`, so whitespace touches and pure renames renew recency. Its returned reason is discarded by `select_canonicals`; an absent per-file timestamp falls back to mtime. That behavior conflicts with the plan's explicit, conservative bounded-history fallback.

Define substantive as a nonzero whitespace-insensitive textual delta. Do not imply semantic normalization. Comments and identifier changes remain substantive unless another actual mechanism filters them. Follow pure renames to their previous paths without awarding the rename timestamp. Distinguish known timestamps, unknown due to bounds, untracked files, non-Git roots, shallow history, and disabled lookup. Unknown tracked history must not silently get a fresh-clone mtime promotion. Persist or surface the fallback reason so doctor, status, or the bootstrap report can explain it.

Use bounded subprocess time and output. Handle legal filename delimiters. Keep one effective clock. Define latest by Git history traversal rather than assuming commit epochs are monotonic. Make shared-selector changes conditional to Swift or prove that non-Swift behavior remains compatible.

Required Git cases include whitespace-only touch, pure rename, rename plus real change, real recent implementation, same-commit tie, shallow clone, output or commit cap, timeout, untracked file, non-Git root, and nested repository root. Assert the witness actually returned by context, not only a timestamp helper.

6. Replace the single happy-path done predicate with a release evidence matrix.

The existing plan has the right broad verification categories but does not yet state the load-bearing assertions. Add exact scenarios for all nominal roles, protocol requirements, extensions, init, nested types, labels, defaults versus optional types, variadics, async, throws, return type, attributes, ordinary and scoped imports, malformed syntax, and Unicode. Assert truthful records rather than only parse success. Conservative calls must not resolve overloads or receiver methods without evidence. A first release may omit Swift call rows if correctness cannot be proved.

Run an isolated committed fixture through bootstrap, trust, context, real PreToolUse subprocess, refresh, and stdio MCP. Assert the injected witness identity and text, trust refusals, malformed payload behavior, and honest unsupported lint/cross-file capabilities. Cover missing, corrupt, and stale profile artifacts and the disabled plugin state. Preserve the repository's existing required QA matrix, record failures separately, and state the exact checks that did not run. Existing unit tests and a successful MCP process launch alone do not establish the end-to-end claim.

## Distribution and scope

Independent marketplace and plugin identity must be consistent across marketplace.json, plugin.json, installation examples, and metadata. Keeping the Python module, `.chameleon` profile, and command names is a reasonable compatibility choice if documented. Preserve upstream history and MIT attribution. Verify the final GitHub repository visibility and remote revision after push. No company source, profile, repository identity, or user-wide settings enter the fixture or published repository.

Codex MCP integration can expose the context tools. Do not advertise an automatic Codex pre-edit hook without a separately implemented and exercised host integration. The plan already states this boundary correctly.

The Rust `chromatophore/languages/swift.toml` file is outside the installed Python plugin. Its presence cannot establish shipped Swift extraction or Python runtime parity.

## Review gate

Approve implementation after the coordinator amends the plan with the six required items above. Recommend candidate B with a dedicated detector, explicit capability and security registration, a contextual snapshot helper independent from lint, hard declaration-role applicability, marker-aware detection tests, and observable conservative history fallback.

`no-comments` is not applicable at this gate because the working tree contains only the new plan documentation and no new source diff. Run the requested comment review on the implementation diff before its final review.
