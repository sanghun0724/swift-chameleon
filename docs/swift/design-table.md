# Swift extraction through a dedicated language table

This proposal adds useful Swift archetype guidance to the Python plugin. It keeps the existing ParsedFile contract and bounded iterative walker. It does not add Swift semantic resolution or Swift lint enforcement.

## Observed constraints

The inspected base is the existing Python tree-sitter architecture requested at upstream 00c79270. The working tree has untracked docs/swift/ owned by the coordinator. No tracked file was edited for this investigation.

The grammar probe used `uv run --with tree-sitter --with tree-sitter-swift python` outside the checkout. The installed Swift wheel is 0.7.4, as independently identified by the coordinator. The probe used actual parsed nodes rather than assumed grammar fields.

* `protocol_declaration` is distinct. Its body is `protocol_body` and its requirements are `protocol_function_declaration`.
* `class_declaration` represents class, struct, actor, enum, and extension. `declaration_kind` identifies the keyword. Its body is `class_body` or `enum_class_body`.
* A function has parameters directly under the declaration. There is no parameters container.
* A function repeats the `name` field for the function name and return type. A parameter repeats `name` for its local binding and declared type.
* A default value belongs to the function declaration as a sibling after its parameter. It is not a child of the parameter.
* `import_declaration` contains an `identifier`. The identifier represents `Foundation` or a scoped path such as `Foo.Bar`. Modifiers are separate.
* `call_expression` holds its callee and a `call_suffix` as children. Navigation targets and suffixes are named fields under `navigation_expression`.

These differences require procedural readers even for a truthful first version. Adding generic LanguageSpec options for sibling defaults, repeated fields, declaration keywords, and type classification would spread Swift details across a shared abstraction.

## Usage and behavior

`bootstrap_repo` and refresh detect a Swift repository, discover its Swift files, and select `TreeSitterExtractor("swift")`. A profile describes the Swift language as extraction tier. `get_pattern_context` supplies learned archetypes, witnesses, signatures, and import conventions. The profile states that Swift lint and cross-file semantic resolution are unavailable.

Select Swift through a dedicated detector in `extractors/swift.py`. Reuse the existing marker and source scan discipline where possible. Recognize Package.swift and Tuist Project.swift together with actual Swift source. Recognize Xcode projects by a bounded check for an `.xcodeproj/project.pbxproj` plus Swift source. The detector must not claim a JavaScript repository merely because it carries an unrelated vendored Swift file. Place the detector after TypeScript and Ruby and before Python, following the existing extraction language precedence. Cover the mixed Python build-manifest case explicitly rather than silently letting one helper script win.

## Named data shape

The language table is a normal module at `extractors/treesitter/lang/swift.py` satisfying `walker.LanguageTables`. It declares the node sets and these existing entry points.

```python
language = "swift"
qualified_name_separator = "."

TOP_LEVEL_KINDS: dict[str, str]
CLASS_NODES = frozenset({"class_declaration", "protocol_declaration"})
FUNCTION_NODES = frozenset({
    "function_declaration", "protocol_function_declaration", "init_declaration"
})

def refine_top_level_kind(node, text, mapped: str) -> str: ...
def class_shape(node, text) -> dict[str, Any] | None: ...
def callable_signature(node, text, class_ctx) -> dict[str, Any] | None: ...
def call_site(node, text) -> dict[str, Any] | None: ...
def import_specifier(node, text) -> list[tuple[str, str]] | None: ...
def export_fields(top_level_kinds: list[str]) -> tuple[None, int]: ...
def class_body_calls(node, text, class_name: str) -> list[dict[str, Any]]: ...
```

Small private readers operate on one declaration and its immediate children. `_declaration_kind`, `_attributes`, `_parameters`, and `_return_type` express Swift grammar details. None recursively walks a subtree. Reading modifiers' direct attribute children follows an explicit grammar path rather than doing an independent traversal.

Keep separate top level kinds `ProtocolDeclaration`, `StructDeclaration`, `ClassDeclaration`, `ActorDeclaration`, `EnumDeclaration`, and `ExtensionDeclaration`. This prevents protocol requirements and extension implementations from becoming one kind merely because the grammar reuses `class_declaration`.

Keep `class_shapes` as the compatibility container for all nominal declarations and extensions. Each row retains `name`, `start_line`, `bases`, `extends`, and `decorators`. Add `kind` only if a consumer needs it. Put declared inheritance syntax in `bases`. Keep `extends=None` because syntax alone cannot determine whether the first inherited name is a superclass or a protocol. Methods still receive lexical type context through the existing walker. An extension's `name` is its extended type, including qualification. This records lexical ownership and does not imply that an extension declares a new type.

Attributes such as `@MainActor`, `@Observable`, and `@CustomCodable` enter `decorators` as observed source names. Do not infer expansion behavior. Preserve attributes on declarations and signatures. Property wrapper extraction can wait until a property-shape consumer exists.

A callable row retains the existing name, kind, params, is_async, enclosing_class, enclosing_class_path, base_class, start_line, end_line, and decorators fields. Find the declaration name before the first parameter list, using concrete tokens and fields. Read a return type after the `->` token. Read local parameter names before the `:` token and external labels separately. `optional` means a default argument exists, not that the type ends in `?`. Associate the declaration's following `=` token and default_value sibling with the immediately preceding parameter. Mark variadic parameters as rest only when the syntax says so. Preserve async and declared return types. Preserve throws as an optional explicit fact only if a consumer needs it. Unsupported syntax yields an absent fact rather than a fabricated name or type.

Swift has no JavaScript default export. Return `None` for default_export_kind. The extraction tier currently repurposes named_export_count as the count of top level declarations. Follow that convention and document it as a declaration count, not Swift public API availability.

Plain imports emit `(module, "namespace")`. Scoped imports such as `import struct Foo.Bar` identify module Foo, while an optional future binding row can preserve Bar. Do not emit `struct Foo.Bar` as a module or claim all of Foo.Bar is a namespace. `@testable` and implementation-only modifiers do not change the module name.

Call extraction is conservative. Emit bare identifiers and calls with a direct self, super, or simple identifier receiver only. Do not resolve constructors from capitalization. Do not claim a static target from `A.make()` without semantic evidence. Skip chained, subscripted, optional-navigation, closure-valued, and computed targets. The walker owns caller attribution and caps. Treat direct call records as syntax observations. Existing same-file resolver ambiguity must drop overloaded candidates rather than bind the wrong overload. Swift argument labels are relevant to overload identity, so a first version can omit unsafe overloaded edges and still retain truthful signature context.

Closures require care. Without a closure frame, calls inside a closure inherit the surrounding named function. Either explicitly describe that attribution as lexical containment or register anonymous lambda frames using the walker's existing `_anonymous` mechanism. Never claim that a closure's call executes directly as part of its enclosing method. Include this boundary in the fixture assertions.

## File map

| File | Change |
| --- | --- |
| plugin/mcp/pyproject.toml and uv.lock | Add and lock tree-sitter-swift compatible with the core. |
| extractors/treesitter/grammars.py | Register `.swift` using tree_sitter_swift.language. |
| extractors/treesitter/lang/swift.py | Implement the dedicated table and local grammar readers. |
| extractors/treesitter/extractor.py | Add swift_tables to `_TABLES`. |
| extractors/swift.py and extractors/registry.py | Add marker-aware Swift detection and explicit precedence. |
| extractors/spec_driven.py | Register Swift secondary-language markers without adding a LanguageSpec. |
| language_support.py | Explicitly register Swift as extraction tier. |
| bootstrap/discovery.py and related suffix tables | Confirm Swift files and exclusions flow through discovery. Avoid source set drift. |
| tools.py and lint_engine.py | Add extraction-only Swift shape snapshots for context scoring. Preserve lint capability gates. |
| bootstrap/canonical.py | Add substantive-change history handling as a separate concern. |
| tests/unit and Swift fixtures | Cover grammar facts, detection, context selection, and truthful capability claims. |
| docs/language-support-matrix.md and CLAUDE.md | Describe Swift's actual tier and table exception. |

All source paths in the table are relative to `plugin/mcp/chameleon_mcp/` unless they explicitly start with plugin, tests, docs, or CLAUDE.md.

## Git witness ranking

`bootstrap/canonical.py::_build_commit_time_map` currently uses one `git log --name-only` walk and records the first commit timestamp per path. `_file_recency_weight` decays from that timestamp. `select_canonicals` sorts demotion first, then recency, typicality, and path. A recent formatting-only commit therefore beats an older substantive idiom.

A realistic change replaces path-touch timestamps with timestamps for substantive deltas. Use one bounded `git log` stream with whitespace-ignoring diff statistics, or a bounded candidate-history batch if this is clearer to validate. The first nonzero whitespace-insensitive text change wins per file. Whitespace-only deltas must not reset the timestamp. Handle binary changes as substantive and additions as substantive. Keep the existing deterministic clock and mtime fallback for missing Git history. Bound subprocess wall time and output rather than spawning an unbounded per-file log. Preserve current ordering and scanner gates.

Do not label `-w` as full semantic change detection. It ignores whitespace. Identifier-only renames, comments, string literals, and generated edits remain changes. AST-normalized history would add historical parsing, grammar failures, caching, and much more scope. A first version should state the exact whitespace-only guarantee.

Use NUL-safe filename records where Git supports them. The existing newline parser mishandles legal newline filenames. Validate nested repository roots, deleted paths, renames, empty commits, merge history, shallow clones, absent Git, and command timeout. Newest Git traversal order is not guaranteed to be descending commit timestamps, so define latest as history order and preserve that convention rather than taking an arbitrary maximum epoch.

## Context applicability

`tools.py::_file_shape_snapshot` and `_get_archetype_with_loaded` currently restrict shape extraction to TypeScript, Ruby, and Python. A Swift table alone cannot discriminate an existing protocol file from an extension file at context time. Add a Swift read-only extraction path to dimensions so learned Swift kinds and import facts participate in AST scoring. This must not widen detect_language's lint semantics or advertise Swift enforcement.

For new files, only path evidence exists. Preserve `match_basis=path_only` and do not report that path evidence proves Swift declaration kind. For an existing file, prefer declaration-compatible witnesses and keep match_quality and confidence truthful. An uncertain match should remain advisory with its basis present. Do not invent Swift module boundaries or cross-file call knowledge from a file path.

## Verification plan

The coordinator should run the targeted checks after implementation. No repository tests were run during this read-only investigation.

1. Parse fixtures for each nominal kind, protocol requirements, extension methods, nested types, attributes, default parameters, optional types without defaults, external labels, async throws, scoped imports, and conservative calls. Assert full relevant ParsedFile facts rather than only successful parsing.
2. Parse damaged and truncated Swift, Unicode, deeply nested input, and unsupported syntax. Confirm honest diagnostics and existing bounds.
3. Build temporary marker-aware Swift repositories and exercise actual extractor selection, bootstrap, refresh, and get_pattern_context. Include Package.swift, Tuist, and Xcode markers plus mixed helper scripts and negative vendored-only cases.
4. Put protocol and extension files in the same path family. Confirm that the context tool selects a compatible witness for an existing file and reports path-only evidence for a new file.
5. Create a Git fixture with older substantive implementation, newer alternate implementation, and newest whitespace-only touch. Confirm the whitespace touch does not promote the old idiom. Confirm that real code changes do promote their candidate.
6. Assert Swift extraction tier reports, no Swift lint capability, and no fabricated cross-file or overload edge.
7. Run existing extraction-tier, language capability, and tree-sitter regression suites. Broader repository QA remains subject to the repository's required matrix before a completion claim.

## Decision and tradeoffs

Use the dedicated table. Model the Domain shaped the choice to keep one Swift grammar module with explicit declaration and parameter readers. Laziness Protocol shaped the choice to reuse the walker and ParsedFile instead of widening LanguageSpec for multiple Swift exceptions.

A declarative spec is shorter only if it omits protocol requirements, distinct nominal kinds, real parameters, defaults, attributes, and correct calls. A dedicated table costs one local module and direct tests. It keeps Swift-specific rules visible and avoids changing the meaning of existing language specs.

The first version supports extraction and truthful context selection. Defer macro expansion, SourceKit or SwiftSyntax integration, cross-file import resolution, protocol dispatch, overload resolution, Swift lint, and Rust engine parity. Git whitespace-aware recency is independently reviewable and should not depend on the Swift table.

## Coordinator refinement for implementation

Construct Swift contextual dimensions in `tools.py` with `parse_file(path)` and the existing `DimensionSnapshot` shape. This is narrower than broadening `lint_engine.detect_language` or its extraction API. Keep Swift lint detection and enforcement disabled. Include a declaration-role signature or role bucket derived from parsed Swift declarations so a recent wrong-role witness never wins against an applicable role. Partition candidates by role before applying Git recency. A protocol, its implementation, and an extension can share a directory and imports while requiring different witnesses. New files remain path-only until their declaration exists.
