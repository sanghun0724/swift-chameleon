# SwiftChameleon implementation review

Review scope is base `00c79270` plus the current working tree in `/Users/brady/Desktop/open-source/swift-chameleon`. Read-only source review covered the Swift parser and detector, signature partitions, runtime context selection, substantive history and fallback, and independent plugin identity. I read `docs/swift/PLAN.md` and `docs/swift/plan-review.md`. Probes used isolated generated Swift strings and temporary directories. No company source was read or copied.

The Prove It Works principle changed the review method. Findings below were reproduced through the actual `parse_file` and runtime archetype resolver rather than inferred only from code. The parent owns product journey and regression suite execution.

## Findings

1. P2. Uppercase Swift extensions bypass the declaration-role constraint.

   At the time of reproduction, `plugin/mcp/chameleon_mcp/signatures.py:557` and `:802` checked `endswith(".swift")` case sensitively. `plugin/mcp/chameleon_mcp/tools.py:1481` and `:1738` checked `p.suffix == ".swift"`. `:1446` and `:1518` repeated the case-sensitive gate for canonical selection. Swift detection and grammar selection accept `.SWIFT`. This creates files that parse as Swift but receive neither Swift signature partitions nor Swift runtime role checks.

   Concrete reproduction. Generate `Sources/Account/ProtocolRepository.SWIFT` containing `protocol ProtocolRepository {}` and `LiveRepository.SWIFT` containing `class LiveRepository {}`. Parse each with `parse_file`. Build each archetype with its real `compute_signature(..., include_extension_in_bucket=True)` and `derive_ast_query`. Give the protocol cluster size 100 and the class cluster size 1. Query an existing `Sources/Account/NewRepository.SWIFT` containing `class NewRepository {}` through `_get_archetype_with_loaded`.

   Observed result. Both archetypes have `paths_pattern="Sources/Account:SWIFT"`. `_file_shape_snapshot` yields an empty generic `DimensionSnapshot`. The resolver returns `archetype="ProtocolRepository"`, `confidence_band="medium"`, `match_quality="ast"`, and `match_basis="path_and_ast"`. This violates the required hard role gate and reports AST evidence that never came from the Swift parser. Normalize suffix recognition consistently through the Swift path, partition, snapshot, and canonical compatibility checks. Add a real grammar runtime test using `.SWIFT` or `.Swift`.

2. P2. Typed throws contracts were missing from otherwise clean callable signatures. Fixed during review.

   `plugin/mcp/chameleon_mcp/extractors/treesitter/lang/swift.py:187` originally handled only child type `throws`. The pinned grammar emits `throws_clause` for `func f() throws(MyError) -> Bool { true }`.

   Concrete reproduction. Write that function to a temporary `.swift` file and call `parse_file`. It reports `parse_diagnostics_count=0` but originally returns a signature without `throws`, while preserving `return_type="Bool"`. The parent accepted the finding and now handles both node kinds. The parent added `test_typed_throws_preserves_declared_error_contract` and reported 21 extraction tests passing. This finding is resolved, subject to the parent's final regression run.

## Other reviewed areas

No additional correctness blocker was established in the inspected bounded Git subprocess, blob and node budgets, rename traversal, unknown tracked fallback, mixed declaration role partition, marker detection, backend-unavailable handling, or independent plugin manifests. This is a bounded review, not a proof of absence of other defects. The product journey and full regression suite are being run by the parent.

The history fingerprint intentionally preserves exact comment and string source. A formatting edit inside an interpolated expression therefore changes a literal fingerprint. This follows the implementation's stated conservative string policy and is not filed as a blocker here.

## Verdict

Hold the final gate until finding 1 is fixed and its runtime reproduction passes. Finding 2 is resolved in the working tree. No repository source was changed by this reviewer.

## Final re-review

The parent normalized Swift suffix checks in `signatures.py` and `tools.py` and added uppercase filename coverage. I reran the exact finding 1 probe against the final working tree. Its protocol and class now have separate `swift/Sources/Account/repository#declarations=...:swift` buckets. The query snapshot contains `SwiftClassDeclaration`, and the resolver returns `LiveRepository` with no alternatives and `match_basis="path_and_ast"`. I also reran finding 2 against the real grammar. The signature contains `throws="throws(MyError)"`, has no parse diagnostic, and retains its Bool return type.

Both reported defects are resolved. Approve the reviewed implementation for the final regression and publication gate. No known correctness blocker remains from this review. The parent still owns the final complete suite and product journey results.
