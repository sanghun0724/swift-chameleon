# Scoped comment review

Scope: `swift-chameleon` diff `00c79270..HEAD` plus tracked working tree; separate `swift-chameleon-history` diff against `00c79270`. Report only; source files were not edited.

Proposed deletions: **7 comment/docstring blocks, 7 lines**, across 5 files.

| Worktree | File and line | Proposed deletion | Reason |
| --- | --- | --- | --- |
| main | `plugin/mcp/chameleon_mcp/extractors/swift.py:1` | Module docstring | Repeats the module purpose and the visible bounded scanner. |
| main | `plugin/mcp/chameleon_mcp/tools.py:1476` | `_file_shape_snapshot` docstring | Internal narration; the returned `DimensionSnapshot` and extraction calls already express it. |
| main | `plugin/mcp/chameleon_mcp/tools.py:2303` | Sole-witness Swift comment | Repeats the immediately following `len(canonicals) > 1 or p.suffix == ".swift"` condition. |
| main | `tests/unit/test_swift_context.py:1` | Module docstring | Test names and assertions state the behavior. |
| main | `tests/unit/test_swift_context.py:111` | Similar-dimensions comment | Fixture construction and partition assertions state the scenario. |
| history | `tests/unit/test_swift_canonical_history.py:1` | Module docstring | Test names and assertions state the behavior. |
| history | `tests/unit/test_swift_canonical_history.py:26` | Worktree-ownership comment | Temporary implementation history, with the integration issue identified below. |

## MUST KILL

- `tests/unit/test_swift_canonical_history.py::swift_grammar`: after integration, remove this autouse registration fixture and its comment. Main already registers `.swift` in `extractors/treesitter/grammars.py`; the fixture overwrites that production registration in every history test and could conceal its accidental removal. Keep tests dependent on the production registry.

## Skips

- Public API contract docstrings: `SwiftExtractor`, `swift_role_for_path`, `swift_declaration_role`, `swift_bucket_matches`, and `swift_history_ages`.
- Swift table module contract: omitted semantic call edges and declaration counts versus visibility describe the supported extraction boundary.
- History module contract: exact token behavior, unknown-age policy, traversal order, bounded work, and Git rename heuristics describe caller-visible behavior or external Git constraints.
- `_changes` docstring and shallow-history test comments: raw Git NUL records, filenames, and shallow boundaries are external protocol constraints.
- Unchanged upstream comments, `docs/*.md`, and legal/license comments were excluded. No new suppression comments were found.
