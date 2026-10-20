from __future__ import annotations

from pathlib import Path

import pytest

from chameleon_mcp.extractors.treesitter.extractor import TreeSitterExtractor, parse_file
from chameleon_mcp.extractors.treesitter.grammars import grammar_for_path, supported_extensions
from chameleon_mcp.extractors.treesitter.lang import swift


def _parse(tmp_path: Path, source: str):
    path = tmp_path / "Example.swift"
    path.write_text(source, encoding="utf-8")
    parsed, error = parse_file(path)
    assert error is None
    assert parsed is not None
    return parsed


@pytest.mark.parametrize("keyword", ["class", "struct", "actor", "enum", "protocol", "extension"])
def test_nominal_roles_and_declared_inheritance(tmp_path, keyword):
    parsed = _parse(tmp_path, f"@MainActor {keyword} Example: Parent, Sendable {{}}")
    role = f"Swift{keyword.title()}Declaration"
    assert parsed.top_level_node_kinds == (role,)
    assert parsed.default_export_kind is None
    assert parsed.named_export_count == 1
    assert parsed.parse_diagnostics_count == 0
    assert parsed.extras["class_shapes"] == [
        {
            "name": "Example",
            "kind": role,
            "start_line": 1,
            "bases": ["Parent", "Sendable"],
            "extends": None,
            "decorators": ["MainActor"],
            "properties": [],
        }
    ]


def test_signatures_keep_labels_defaults_types_effects_and_attributes(tmp_path):
    parsed = _parse(
        tmp_path,
        """@MainActor struct Store {
    @discardableResult func fetch(_ key: String, limit count: Int = 2,
        maybe: String?, values: Int...) async throws -> [String] { [] }
    init(value: Int = 1) {}
}""",
    )
    fetch, initializer = parsed.extras["callable_signatures"]
    assert fetch == {
        "name": "fetch",
        "kind": "method",
        "params": [
            {
                "name": "key",
                "label": "_",
                "optional": False,
                "kind": "positional",
                "type": "String",
            },
            {
                "name": "count",
                "label": "limit",
                "optional": True,
                "kind": "positional",
                "type": "Int",
            },
            {
                "name": "maybe",
                "label": "maybe",
                "optional": False,
                "kind": "positional",
                "type": "String?",
            },
            {"name": "values", "label": "values", "optional": False, "kind": "rest", "type": "Int"},
        ],
        "is_async": True,
        "enclosing_class": "Store",
        "enclosing_class_path": "Store",
        "base_class": None,
        "start_line": 2,
        "end_line": 3,
        "decorators": ["discardableResult"],
        "throws": "throws",
        "return_type": "[String]",
    }
    assert initializer["name"] == "init"
    assert initializer["params"][0]["optional"] is True
    assert "return_type" not in initializer


def test_protocol_requirements_and_qualified_extension_are_lexical(tmp_path):
    parsed = _parse(
        tmp_path,
        "protocol Repository { func load(id: Int) async throws -> String }\n"
        'extension Outer.Inner: Repository { func load(id: Int) async throws -> String { "" } }',
    )
    requirement, implementation = parsed.extras["callable_signatures"]
    assert requirement["enclosing_class_path"] == "Repository"
    assert implementation["enclosing_class_path"] == "Outer.Inner"
    assert parsed.extras["class_shapes"][1]["kind"] == "SwiftExtensionDeclaration"
    assert parsed.extras["class_shapes"][1]["bases"] == ["Repository"]


def test_nested_types_properties_and_unicode(tmp_path):
    parsed = _parse(
        tmp_path,
        "@Observable class Outer { @Published var items: [String] = []\n"
        "struct Inner { @CustomCodable func 저장(_ 값: String) {} } }",
    )
    outer, inner = parsed.extras["class_shapes"]
    assert outer["decorators"] == ["Observable"]
    assert outer["properties"] == [
        {"name": "items", "type": "[String]", "decorators": ["Published"]}
    ]
    assert inner["qualified"] == "Outer.Inner"
    method = parsed.extras["callable_signatures"][0]
    assert method["name"] == "저장"
    assert method["enclosing_class_path"] == "Outer.Inner"
    assert method["params"][0]["name"] == "값"
    assert method["decorators"] == ["CustomCodable"]
    assert parsed.parse_diagnostics_count == 0


def test_imports_identify_the_module_for_scoped_and_modified_imports(tmp_path):
    parsed = _parse(
        tmp_path,
        "import Foundation\n@testable import Helpers\n"
        "import struct Foo.Bar\n@_implementationOnly import class Kit.Widget\n",
    )
    assert parsed.import_specifiers == (
        ("Foundation", "namespace"),
        ("Helpers", "namespace"),
        ("Foo", "namespace"),
        ("Kit", "namespace"),
    )
    assert parsed.named_export_count == 0


def test_closure_defaults_rethrows_and_local_functions(tmp_path):
    parsed = _parse(
        tmp_path,
        "struct S { func run<T>(_ value: inout T, apply: @escaping (Int) -> Void = { _ in }) "
        "async rethrows -> T { func local() {} ; fatalError() } }",
    )
    signatures = {s["name"]: s for s in parsed.extras["callable_signatures"]}
    local, run = signatures["local"], signatures["run"]
    assert local["kind"] == "function"
    assert local["enclosing_class"] is None
    assert run["throws"] == "rethrows"
    assert run["params"][0]["type"] == "inout T"
    assert run["params"][1]["type"] == "@escaping (Int) -> Void"
    assert run["params"][1]["optional"] is True


def test_calls_are_omitted_including_overloads_receivers_and_closures(tmp_path):
    parsed = _parse(
        tmp_path,
        "func f(_ value: Int) {}\nfunc f(label: String) {}\n"
        'func run() { f(1); f(label: ""); thing.make(); self.update(); [1].map { f($0) } }',
    )
    assert parsed.extras["call_sites"] == []
    assert parsed.extras["call_sites_total"] == 0
    assert parsed.extras["call_sites_truncated"] is False


@pytest.mark.parametrize("source", ["", "struct Broken { func run(", "func f() { let x = ", "\x00"])
def test_empty_and_damaged_source_preserves_diagnostics(tmp_path, source):
    parsed = _parse(tmp_path, source)
    assert parsed.parse_diagnostics_count == (0 if not source else 1)


def test_table_vocabulary_matches_pinned_grammar():
    grammar = grammar_for_path("X.swift")
    kinds = {grammar.node_kind_for_id(i) for i in range(grammar.node_kind_count)}
    declared = (
        set(swift.TOP_LEVEL_KINDS)
        | swift.CLASS_NODES
        | swift.FUNCTION_NODES
        | swift.BRANCH_NODES
        | swift.NESTING_NODES
        | swift.SKIP_SUBTREE_NODES
    )
    assert not (declared - kinds)
    assert supported_extensions("swift") == (".swift",)
    assert TreeSitterExtractor.supports("swift")


def test_shared_file_and_node_limits_apply(tmp_path, monkeypatch):
    path = tmp_path / "Example.swift"
    path.write_text("struct S {}")
    monkeypatch.setenv("CHAMELEON_TS_MAX_FILE_BYTES", "4")
    assert parse_file(path) == (None, "file_too_large")
    monkeypatch.setenv("CHAMELEON_TS_MAX_FILE_BYTES", "1000000")
    monkeypatch.setenv("CHAMELEON_TS_MAX_AST_NODES", "2")
    assert parse_file(path) == (None, "ast_node_ceiling_exceeded")


def test_deep_swift_source_uses_the_iterative_walker(tmp_path):
    parsed = _parse(tmp_path, "func nested() { let value = " + "(" * 3000 + "1" + ")" * 3000 + " }")
    assert parsed.parse_diagnostics_count == 0
    assert parsed.extras["callable_signatures"][0]["name"] == "nested"


def test_parse_repo_honors_explicit_paths_and_file_limit(tmp_path):
    first = tmp_path / "First.swift"
    second = tmp_path / "Second.swift"
    first.write_text("struct First {}")
    second.write_text("struct Second {}")
    extractor = TreeSitterExtractor("swift")
    selected = extractor.parse_repo(tmp_path, paths=[second])
    assert [row.path for row in selected.files] == [second]
    limited = extractor.parse_repo(tmp_path, paths=[first, second], limit=1)
    assert [row.path for row in limited.files] == [first]


def test_typed_throws_preserves_declared_error_contract(tmp_path):
    path = tmp_path / "Typed.swift"
    path.write_text("func load() throws(NetworkError) -> Bool { true }\n")
    parsed, reason = parse_file(path)
    assert reason is None
    assert parsed is not None
    assert parsed.parse_diagnostics_count == 0
    signature = parsed.extras["callable_signatures"][0]
    assert signature["throws"] == "throws(NetworkError)"
    assert signature["return_type"] == "Bool"
