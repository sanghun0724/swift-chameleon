# Swift support through a declarative spec and a small adapter

This candidate adds extraction tier Swift support through the existing tree-sitter walker. A developer editing a Swift ViewController receives another ViewController as the canonical example. The selected file favors the latest substantive Git change after safety and role eligibility.

The repository was inspected at upstream `00c79270`. No tracked file was changed. Throughput checkpoint is not applicable to this read-only investigation.

## Decision

A `LanguageSpec` alone cannot satisfy the extraction contract. Use the spec for grammar data and one Swift adapter for declaration semantics. Keep the adapter behind the existing table contract. Do not grow a general query language or alter the shared walker's traversal.

Laziness Protocol shaped the reuse of registration, extraction bounds, grammar loading, and traversal. Model the Domain shaped the explicit representation of Swift declarations and path roles.

A dedicated Swift table is an equally valid and probably clearer choice if the adapter overrides most generic behavior. The specification must not claim Swift is data-only.

## Observed grammar constraints

The isolated command `uv run --no-project --with tree-sitter==0.26.0 --with tree-sitter-swift==0.7.4 python ...` loaded and parsed actual Swift grammar nodes. No project dependency was changed.

- `class_declaration` represents class, struct, enum, actor, and extension. Its `declaration_kind` field distinguishes them. Enum bodies use `enum_class_body`, while class, actor, struct, and extension bodies use `class_body`.
- Protocol requirements are `protocol_function_declaration`, not `function_declaration`.
- Function `parameter` nodes are direct children. There is no `parameters` holder field. Generic extraction emits zero parameters.
- Function identifiers and return types reuse `name`. Parameter identifiers and types also reuse `name`. A single generic field lookup cannot reliably distinguish them.
- Attributes occur inside `modifiers`. Generic class and callable shapes always emit empty decorators. `@Published` belongs to a property declaration, so function and class decorators do not preserve property wrappers.
- Import declarations have no module field. `@testable import Foo` has `modifiers` before its `identifier`. Generic `_module_child` selects the attribute text as the module. `import struct Swift.Array` has identifier `Swift.Array`.
- Inheritance specifiers are direct declaration children, with type under `inherits_from`.
- Async is an unnamed token. Generic `is_async=False` misrepresents an async function.

The same grammar accepted an `@Observable` declaration and a generic function with variadics, defaults, `async throws(Error)`, array return, and a where constraint without parse errors. These observations establish parser syntax. They do not establish compiler semantics.

## Caller usage

The public caller remains unchanged.

```python
extractor = TreeSitterExtractor("swift")
result = extractor.parse_repo(repo_root, paths=swift_source_paths)
parsed = result.files[0]
signatures = parsed.extras["callable_signatures"]
shapes = parsed.extras["class_shapes"]
```

`get_pattern_context(repo, file_path)` resolves the existing profile. Swift role identity must enter clustering and lookup together. A nonexistent `AccountViewController.swift` must resolve without already appearing in artifacts.

## Types and interfaces

Retain `LanguageSpec` unchanged for the existing languages. Define `SWIFT` grammar data with extension `.swift`. A Swift adapter calls `spec_driven.build(SWIFT)` and replaces the table functions that need declaration semantics.

```python
def build_swift_tables(spec: LanguageSpec) -> SimpleNamespace: ...
def refine_top_level_kind(node, text, mapped: str) -> str: ...
def class_shape(node, text) -> dict | None: ...
def callable_signature(node, text, class_ctx) -> dict | None: ...
def import_specifier(node, text) -> list[tuple[str, str]] | None: ...
def file_extras(root, text, path: Path, walked) -> dict: ...
```

`class_shape` preserves the name, inherited types, attributes, and declaration kind. A first inherited Swift protocol is not proven to be a superclass. Keep syntactic inherited types under `bases`. Leave `extends` and `base_class` absent unless positively known.

`callable_signature` retains current row keys. Preserve parameter internal names, external labels, types, defaults, async, throws, return types, attributes, generic constraints, and initializer identity. Consumers may ignore additive keys. A bounded `declaration` containing the written header can retain details existing summary renderers do not model. Preserve overloads as separate source-positioned rows. Do not add Swift dispatch resolution in extraction tier.

Use `file_extras` for declaration and property records absent from the current walker contract. A property record contains its enclosing declaration, name, declared type, attributes, and source line. Store unknown `@Name` syntax as an attribute. Do not claim every attribute is a property wrapper. `@propertyWrapper` positively identifies a wrapper declaration.

A bounded iterative AST scan for file extras is acceptable if it shares or documents a node cap. Avoid hidden unbounded recursive traversal.

A pure-spec implementation needs inline parameters, repeated-field selection, declaration-kind refinement, attribute extraction, async token checks, import-child filtering, and property facts. Adding these switches for one language is harder to read than a local adapter.

## Role and Git selection

Define `swift_role_for_path(file_path: str) -> str | None` beside existing role helpers. Recognize longest basename suffixes first. ViewController precedes View. Candidate roles include ViewController, Reactor, View, Cell, Router, Builder, Assembly, Repository, UseCase, and DTO where repository evidence establishes the convention.

Keep test roles separate. Preserve Feature, Domain, UI, Core, and Shared layer distinctions when present. UI View and Feature View have different dependency constraints. Unknown filenames remain path-bucketed.

Wire the helper into `path_pattern_bucket_for`, sparse threshold handling, and archetype lookup. If no same-role candidate exists, return no canonical example rather than another role through `_prefix_overlap_fallback`. Validate both existing and nonexistent new paths.

Existing canonical ranking already places commit-time recency above typicality. `_build_commit_time_map` uses `git log --name-only`, so comments, formatting, and substantive changes are equivalent today.

A proposed substantive definition compares source tokens after comments and whitespace are removed. Preserve literals, identifiers, operators, and attributes. This definition is proposed, not current behavior. Put the implementation at the canonical Git boundary, independent of syntax extraction. A Swift-only first rollout may restrict token fingerprinting to Swift.

A bounded history pass follows renames, compares candidate blobs to parents, and stops at the newest token change. Comment-only and formatting-only changes do not reset age. Record an unknown reason when the budget prevents a tracked file's substantive timestamp from being found. Mtime must not turn an unknown tracked timestamp into a claim of recent substantive work.

Rank same-role eligibility and safety first, substantive recency next, typicality next, and stable path last. `git log -w` alone ignores whitespace but still counts comments, so it does not prove this definition.

## File map

- `plugin/mcp/chameleon_mcp/extractors/treesitter/lang/specs.py` declares Swift grammar data.
- `plugin/mcp/chameleon_mcp/extractors/treesitter/lang/swift.py` implements the local adapter.
- `plugin/mcp/chameleon_mcp/extractors/treesitter/extractor.py` installs the Swift object after generic table construction.
- `plugin/mcp/chameleon_mcp/extractors/treesitter/grammars.py` maps Swift to `tree_sitter_swift.language`.
- `plugin/mcp/chameleon_mcp/extractors/spec_driven.py` recognizes Package.swift, Xcode project roots, workspace roots, and Tuist markers with real Swift sources. Package.swift alone misses ordinary iOS applications.
- `plugin/mcp/pyproject.toml` and `plugin/mcp/uv.lock` pin the grammar.
- `plugin/mcp/chameleon_mcp/signatures.py` owns Swift roles.
- `plugin/mcp/chameleon_mcp/bootstrap/clustering.py` handles explicit sparse role cohorts.
- `plugin/mcp/chameleon_mcp/tools.py` constrains role fallback.
- `plugin/mcp/chameleon_mcp/bootstrap/canonical.py` owns substantive Git rank.
- `tests/unit/test_spec_driven_lang.py` validates registration and actual grammar behavior. Focused new tests cover Swift syntax, roles, and Git rank.
- `docs/language-support-matrix.md` and `CLAUDE.md` describe extraction tier limits. Capability declarations must agree with actual security and symbol-index wiring.

The optional Rust engine already has `chromatophore/languages/swift.toml` with inline parameters, attribute flags, and navigation suffix handling. It is outside the shipped plugin. Its existence does not make Python Swift support available. Keep record compatibility in mind without expanding this task into a Rust migration.

## Validation plan

This investigation ran grammar probes only. Implementation needs these checks.

1. Parse class, struct, enum, actor, protocol, nested type, extension, generic extension, wrapper declarations, wrapped properties, availability attributes, macro attributes, and conditional imports. Assert exact records using the pinned grammar.
2. Parse empty arguments, external labels, underscore labels, defaults, variadics, async throws, generic returns, initializers, deinitializers, subscripts, and protocol requirements. Check typed throws only if the grammar supports it.
3. Assert imports for plain, @testable, @_exported, conditional, and scoped-symbol imports. Attributes never become module names.
4. Bootstrap a Swift fixture across modules. Query an existing and nonexistent ViewController. Its witness must never be Reactor, Repository, test, or a different layer's View.
5. Use temporary Git history with old majority, recent minority, formatting-only touch, comment-only touch, method change, attribute change, rename, absent history, and equal timestamps. Assert witness selection and degraded status.
6. Run existing registration and recency suites to preserve other languages.
7. Parse representative hoian-ios paths read-only. Inspect extraction and context. Report unsupported syntax explicitly.

## Alternatives

| Approach | Judgment |
| --- | --- |
| Append only SWIFT LanguageSpec | Reject. It loses parameters, attributes, async, correct imports, and declaration kinds. |
| Add many Swift switches to LanguageSpec | Reject for this change. Reconsider shared options after a second language needs them. |
| Spec plus local adapter | Viable candidate. It reuses registration but needs one special table installation step. |
| Dedicated Swift table | Strong alternative. It fits the existing table contract directly. It needs separate detector and capability wiring if not registered through specs.ALL. Prefer it if most generic functions are overridden. |
| SwiftSyntax subprocess | Reject for minimal support. It adds a Swift toolchain and another parser lifecycle. |
| Infer roles from import regexes | Reject. Imports do not establish screen ownership or distinguish tests. |
| Latest mtime or latest commit only | Reject for substantive priority. Clone timestamps and formatting commits select misleading examples. |
