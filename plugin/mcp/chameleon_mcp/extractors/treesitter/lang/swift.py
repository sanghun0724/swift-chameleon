"""Swift syntax facts for the shared bounded walker.

Call rows are omitted because Swift overloads and dispatch need semantic
resolution. Declaration counts do not describe public API visibility.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

language = "swift"
qualified_name_separator = "."
call_site_carries_nesting = False
class_shape_carries_qualified = True

_DECLARATION_KINDS = {
    "class": "SwiftClassDeclaration",
    "struct": "SwiftStructDeclaration",
    "protocol": "SwiftProtocolDeclaration",
    "actor": "SwiftActorDeclaration",
    "enum": "SwiftEnumDeclaration",
    "extension": "SwiftExtensionDeclaration",
}
TOP_LEVEL_KINDS = {
    "class_declaration": "SwiftClassDeclaration",
    "protocol_declaration": "SwiftProtocolDeclaration",
    "function_declaration": "FunctionDeclaration",
    "property_declaration": "PropertyDeclaration",
    "typealias_declaration": "TypeAliasDeclaration",
    "import_declaration": "ImportDeclaration",
    "comment": "",
    "multiline_comment": "",
}
CLASS_NODES = frozenset({"class_declaration", "protocol_declaration"})
FUNCTION_NODES = frozenset(
    {"function_declaration", "protocol_function_declaration", "init_declaration"}
)
BRANCH_NODES = frozenset(
    {
        "if_statement",
        "guard_statement",
        "for_statement",
        "while_statement",
        "switch_entry",
        "catch_block",
    }
)
NESTING_NODES = frozenset(
    {
        "if_statement",
        "guard_statement",
        "for_statement",
        "while_statement",
        "switch_statement",
        "do_statement",
    }
)
SKIP_SUBTREE_NODES = frozenset(
    {"comment", "multiline_comment", "line_string_literal", "multi_line_string_literal"}
)


def refine_top_level_kind(node: Any, text: Callable[[Any], str], mapped: str) -> str:
    kind = node.child_by_field_name("declaration_kind")
    return _DECLARATION_KINDS.get(text(kind), mapped) if kind is not None else mapped


def _attributes(node: Any, text: Callable[[Any], str]) -> list[str]:
    attributes = []
    for modifiers in node.named_children:
        if modifiers.type != "modifiers":
            continue
        for attribute in modifiers.named_children:
            if attribute.type != "attribute":
                continue
            name = next((c for c in attribute.named_children if c.type == "user_type"), None)
            if name is not None:
                attributes.append(text(name))
    return attributes


def _properties(node: Any, text: Callable[[Any], str]) -> list[dict[str, Any]]:
    body = node.child_by_field_name("body")
    if body is None:
        return []
    properties = []
    for child in body.named_children:
        if child.type not in {"property_declaration", "protocol_property_declaration"}:
            continue
        pattern = child.child_by_field_name("name")
        if pattern is None:
            continue
        annotation = next((c for c in child.named_children if c.type == "type_annotation"), None)
        properties.append(
            {
                "name": text(pattern),
                "type": text(annotation).lstrip(":").strip() if annotation is not None else None,
                "decorators": _attributes(child, text),
            }
        )
    return properties


def class_shape(node: Any, text: Callable[[Any], str]) -> dict[str, Any] | None:
    name = node.child_by_field_name("name")
    if name is None or name.is_missing:
        return None
    bases = []
    for child in node.named_children:
        if child.type == "inheritance_specifier":
            inherited = child.child_by_field_name("inherits_from")
            if inherited is not None:
                bases.append(text(inherited))
    return {
        "name": text(name),
        "kind": refine_top_level_kind(node, text, "SwiftClassDeclaration"),
        "start_line": node.start_point[0] + 1,
        "bases": bases,
        "extends": None,
        "decorators": _attributes(node, text),
        "properties": _properties(node, text),
    }


def _parameters(node: Any, text: Callable[[Any], str]) -> list[dict[str, Any]]:
    parameters = []
    children = node.children
    for index, child in enumerate(children):
        if child.type != "parameter":
            continue
        names = child.children_by_field_name("name")
        name = next((c for c in names if c.type == "simple_identifier"), None)
        if name is None or name.is_missing:
            continue
        external = child.child_by_field_name("external_name")
        has_default = False
        for following in range(index + 1, len(children)):
            sibling = children[following]
            if sibling.type in {",", ")", "parameter"}:
                break
            if sibling.type == "=":
                has_default = True
        variadic = any(c.type == "..." for c in child.children)
        declared = text(child).partition(":")[2].strip()
        if variadic:
            declared = declared.removesuffix("...").rstrip()
        parameter = {
            "name": text(name),
            "label": text(external) if external is not None else text(name),
            "optional": has_default,
            "kind": "rest" if variadic else "positional",
        }
        if declared:
            parameter["type"] = declared
        parameters.append(parameter)
    return parameters


def callable_signature(
    node: Any,
    text: Callable[[Any], str],
    class_ctx: tuple[str, str, str | None, tuple[str, ...]] | None,
) -> dict[str, Any] | None:
    name = node.child_by_field_name("name")
    if name is None or name.is_missing:
        return None
    if node.parent is not None and node.parent.type not in {
        "class_body",
        "enum_class_body",
        "protocol_body",
    }:
        class_ctx = None
    signature = {
        "name": text(name),
        "kind": "method" if class_ctx else "function",
        "params": _parameters(node, text),
        "is_async": any(c.type == "async" for c in node.children),
        "enclosing_class": class_ctx[0] if class_ctx else None,
        "enclosing_class_path": class_ctx[1] if class_ctx else None,
        "base_class": None,
        "start_line": node.start_point[0] + 1,
        "end_line": node.end_point[0] + 1,
        "decorators": _attributes(node, text),
    }
    for index, child in enumerate(node.children):
        if child.type == "throws":
            signature["throws"] = text(child)
        if child.type == "->" and index + 1 < len(node.children):
            result = node.children[index + 1]
            if result.is_named and not result.is_missing:
                signature["return_type"] = text(result)
    return signature


def import_specifier(node: Any, text: Callable[[Any], str]) -> list[tuple[str, str]] | None:
    if node.type != "import_declaration":
        return None
    identifier = next((c for c in node.named_children if c.type == "identifier"), None)
    if identifier is None:
        return []
    module = text(identifier).split(".", 1)[0]
    return [(module, "namespace")] if module else []


def call_site(node: Any, text: Callable[[Any], str]) -> None:
    return None


def class_body_calls(
    node: Any, text: Callable[[Any], str], class_name: str
) -> list[dict[str, Any]]:
    return []


def export_fields(top_level_kinds: list[str]) -> tuple[None, int]:
    declarations = {
        *_DECLARATION_KINDS.values(),
        "FunctionDeclaration",
        "TypeAliasDeclaration",
        "PropertyDeclaration",
    }
    return None, sum(kind in declarations for kind in top_level_kinds)
