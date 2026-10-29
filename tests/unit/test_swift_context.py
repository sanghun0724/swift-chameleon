from types import SimpleNamespace

import pytest

from chameleon_mcp import tools
from chameleon_mcp.bootstrap.canonical import derive_ast_query
from chameleon_mcp.bootstrap.clustering import cluster_files
from chameleon_mcp.extractors._base import ParsedFile
from chameleon_mcp.lint_engine import DimensionSnapshot, detect_language
from chameleon_mcp.signatures import (
    compute_signature,
    path_pattern_bucket_for,
    swift_bucket_matches,
    swift_role_for_path,
)


def _parsed(path, *declarations, diagnostics=0):
    return ParsedFile(
        path=path,
        content_first_200_bytes="import Foundation\n",
        top_level_node_kinds=("ImportDeclaration", "PropertyDeclaration", *declarations),
        default_export_kind=None,
        named_export_count=1,
        import_specifiers=(("Foundation", "namespace"),),
        has_jsx=False,
        parse_diagnostics_count=diagnostics,
    )


def _signature(parsed, root):
    return compute_signature(
        str(parsed.path.relative_to(root)),
        parsed.content_first_200_bytes,
        parsed.top_level_node_kinds,
        parsed.default_export_kind,
        parsed.named_export_count,
        parsed.import_specifiers,
        parsed.has_jsx,
        include_extension_in_bucket=True,
    )


def _profile(root, files):
    archetypes, canonicals = {}, {}
    for name, parsed in files.items():
        key = _signature(parsed, root)
        archetypes[name] = {"paths_pattern": key.path_pattern_bucket, "cluster_size": 100}
        canonicals[name] = [
            {
                "witness": {"path": str(parsed.path.relative_to(root))},
                "normative_shape": {"ast_query": derive_ast_query(key)},
            }
        ]
    return SimpleNamespace(
        archetypes={"archetypes": archetypes}, canonicals={"canonicals": canonicals}
    )


def _mock_parse(monkeypatch, parsed, reason=None):
    monkeypatch.setattr(
        "chameleon_mcp.extractors.treesitter.extractor.parse_file",
        lambda path: (parsed, reason),
    )


@pytest.mark.parametrize(
    ("path", "role"),
    [
        ("Sources/Accounts/AccountViewController.swift", "view-controller"),
        ("Sources/Accounts/AccountView.swift", "view"),
        ("Sources/Accounts/AccountRepositoryImpl.swift", "repository"),
        ("Sources/Accounts/AccountInteractorImpl.swift", "interactor"),
        ("Sources/Accounts/AccountInteractor.swift", "interactor"),
        ("Sources/Accounts/AccountLogger.swift", "logger"),
        ("Sources/Accounts/AccountBuildable.swift", "buildable"),
        ("Sources/Accounts/AccountViewModelFactory.swift", "view-model-factory"),
        ("Sources/Accounts/AccountMapper.swift", "mapper"),
        ("Tests/Accounts/AccountView.swift", "test"),
        ("Sources/Accounts/AccountViewTests.swift", "test"),
        ("Package.swift", "build-manifest"),
        ("Sources/Accounts/Account.swift", None),
        ("Sources/Accounts/AccountView.ts", None),
    ],
)
def test_swift_filename_role(path, role):
    assert swift_role_for_path(path) == role


def test_swift_buckets_preserve_module_and_layer():
    paths = [
        "Sources/Accounts/AccountView.swift",
        "Sources/Billing/BillingView.swift",
        "Projects/Feature/Account/Sources/AccountView.swift",
        "Projects/UI/Account/Sources/AccountView.swift",
        "Tests/Accounts/AccountView.swift",
    ]
    assert len({path_pattern_bucket_for(path)[0] for path in paths}) == len(paths)
    assert path_pattern_bucket_for(
        "Sources/Accounts/Nested/AccountView.swift"
    ) == path_pattern_bucket_for(paths[0])


def test_project_swift_buckets_separate_targets_scenes_variants_and_roles():
    module = "Projects/Feature/WriteForm"
    default = f"{module}/Sources/Scenes/WriteForm/Default/FormInteractor.swift"
    north_america = f"{module}/Sources/Scenes/WriteForm/NA/NAFormInteractor.swift"
    logger = f"{module}/Sources/Scenes/WriteForm/Default/FormLogger.swift"
    other_scene = f"{module}/Sources/Scenes/Other/Default/FormInteractor.swift"
    interface = f"{module}/Interface/Scenes/WriteForm/Default/FormInteractor.swift"
    assert swift_role_for_path(default) == "interactor"
    assert swift_role_for_path(logger) == "logger"
    assert (
        len(
            {
                path_pattern_bucket_for(path)[0]
                for path in [default, north_america, logger, other_scene, interface]
            }
        )
        == 5
    )


def test_domain_entity_named_view_is_not_a_ui_view():
    path = "Projects/Feature/Market/Interface/Domain/Entity/ParcelInfoView.swift"
    assert swift_role_for_path(path) == "entity"
    assert (
        swift_role_for_path("Projects/Feature/Market/Sources/Scene/ParcelInfoView.swift") == "view"
    )
    assert (
        swift_role_for_path("Projects/Feature/Market/Sources/Scene/Entity/ParcelInfoView.swift")
        == "view"
    )
    assert (
        swift_role_for_path("Projects/Feature/Market/Sources/Entity/ParcelRepository.swift")
        == "repository"
    )


def test_country_filename_prefixes_stay_separate_outside_named_variant_directory():
    base = "Projects/Feature/Market/Sources/Scenes/WriteForm/Common/"
    paths = [
        base + name
        for name in ("NAFormInteractor.swift", "KRFormInteractor.swift", "FormInteractor.swift")
    ]
    assert len({path_pattern_bucket_for(path)[0] for path in paths}) == 3
    assert (
        path_pattern_bucket_for(base + "NAFormInteractor.swift")[0]
        == path_pattern_bucket_for(base + "NAPaymentInteractor.swift")[0]
    )


def test_country_filename_prefix_matches_its_explicit_directory():
    base = "Projects/Feature/Market/Sources/Scenes/WriteForm/NA/"
    assert (
        path_pattern_bucket_for(base + "NAFormInteractor.swift")[0]
        == path_pattern_bucket_for(base + "NewInteractor.swift")[0]
    )


def test_unknown_project_roles_are_limited_to_their_parent_directory():
    base = "Projects/Feature/Market/Sources/Domain"
    first = f"{base}/Pricing/RuleEvaluator.swift"
    sibling = f"{base}/Pricing/PriceConfig.swift"
    other = f"{base}/Navigation/RouteConfig.swift"
    assert path_pattern_bucket_for(first)[0] == path_pattern_bucket_for(sibling)[0]
    assert path_pattern_bucket_for(first)[0] != path_pattern_bucket_for(other)[0]


@pytest.mark.parametrize("changed_segment", ["target", "scene", "variant"])
def test_existing_profile_does_not_match_another_boundary(tmp_path, monkeypatch, changed_segment):
    base = "Projects/Feature/Market"
    target = tmp_path / f"{base}/Sources/Scenes/WriteForm/NA/FormInteractor.swift"
    references = {
        "target": f"{base}/Interface/Scenes/WriteForm/NA/OtherInteractor.swift",
        "scene": f"{base}/Sources/Scenes/Other/NA/OtherInteractor.swift",
        "variant": f"{base}/Sources/Scenes/WriteForm/Default/OtherInteractor.swift",
    }
    target.parent.mkdir(parents=True)
    target.write_text("class FormInteractor {}")
    reference = _parsed(tmp_path / references[changed_segment], "SwiftClassDeclaration")
    loaded = _profile(tmp_path, {"other": reference})
    _mock_parse(monkeypatch, _parsed(target, "SwiftClassDeclaration"))
    result = tools._get_archetype_with_loaded(target, tmp_path, loaded, "none")["data"]
    assert result["archetype"] is None


def test_interactor_does_not_resolve_legacy_logger_witness(tmp_path, monkeypatch):
    base = tmp_path / "Projects/Feature/Market/Sources/Scenes/WriteForm"
    query = base / "NA/NAFormInteractor.swift"
    query.parent.mkdir(parents=True)
    query.write_text("class NAFormInteractor {}")
    logger = _parsed(base / "Default/FormLogger.swift", "SwiftClassDeclaration")
    loaded = _profile(tmp_path, {"legacy-logger": logger})
    _mock_parse(monkeypatch, _parsed(query, "SwiftClassDeclaration"))
    data = tools._get_archetype_with_loaded(query, tmp_path, loaded, "none")["data"]
    assert data["archetype"] is None


def test_legacy_project_profile_requires_refresh(tmp_path, monkeypatch):
    directory = tmp_path / "Projects/Feature/Market/Sources/Scenes/WriteForm/NA"
    query = directory / "NewInteractor.swift"
    query.parent.mkdir(parents=True)
    query.write_text("class NewInteractor {}")
    reference = _parsed(directory / "ExistingInteractor.swift", "SwiftClassDeclaration")
    loaded = _profile(tmp_path, {"legacy": reference})
    loaded.archetypes["archetypes"]["legacy"]["paths_pattern"] = (
        "swift/Projects/Feature/Market/unknown#declarations=class:swift"
    )
    _mock_parse(monkeypatch, _parsed(query, "SwiftClassDeclaration"))
    result = tools._get_archetype_with_loaded(query, tmp_path, loaded, "none")["data"]
    assert result["archetype"] is None
    other_scene = tmp_path / "Projects/Feature/Market/Sources/Scenes/Other/NA/NewInteractor.swift"
    assert (
        tools._get_archetype_with_loaded(other_scene, tmp_path, loaded, "none")["data"]["archetype"]
        is None
    )


def test_swift_partition_survives_both_fuzzy_merge_passes(tmp_path):
    files = [
        _parsed(tmp_path / "Sources/Account/ProtocolRepository.swift", "SwiftProtocolDeclaration"),
        _parsed(tmp_path / "Sources/Account/LiveRepository.swift", "SwiftClassDeclaration"),
        _parsed(tmp_path / "Sources/Account/OtherRepository.swift", "SwiftExtensionDeclaration"),
        _parsed(
            tmp_path / "Sources/Account/MixedRepository.swift",
            "SwiftClassDeclaration",
            "SwiftExtensionDeclaration",
        ),
    ]
    for parsed in files:
        parsed.top_level_node_kinds += ("FunctionDeclaration", "TypeAliasDeclaration")
    result = cluster_files(files, repo_root=tmp_path, min_cluster_size=5)
    assert len(result.clusters) == 4
    assert all(not cluster.is_sparse for cluster in result.clusters)
    buckets = {cluster.key.path_pattern_bucket for cluster in result.clusters}
    assert len(buckets) == 4
    assert all(
        swift_bucket_matches(
            bucket, path_pattern_bucket_for("Sources/Account/NewRepository.swift")[0]
        )
        for bucket in buckets
    )


@pytest.mark.parametrize("suffix", ["swift", "SWIFT"])
def test_existing_nominal_never_selects_larger_protocol_or_extension(tmp_path, monkeypatch, suffix):
    query = tmp_path / f"Sources/Account/NewRepository.{suffix}"
    query.parent.mkdir(parents=True)
    query.write_text("final class NewRepository {}")
    files = {
        "recent-protocol": _parsed(
            query.with_name("AccountRepository.swift"), "SwiftProtocolDeclaration"
        ),
        "recent-extension": _parsed(
            query.with_name("ExtraRepository.swift"), "SwiftExtensionDeclaration"
        ),
        "implementation": _parsed(query.with_name("LiveRepository.swift"), "SwiftClassDeclaration"),
    }
    loaded = _profile(tmp_path, files)
    loaded.archetypes["archetypes"]["implementation"]["cluster_size"] = 1
    _mock_parse(monkeypatch, _parsed(query, "SwiftClassDeclaration"))
    data = tools._get_archetype_with_loaded(query, tmp_path, loaded, "none")["data"]
    assert data["archetype"] == "implementation"
    assert data["alternatives"] == []
    assert data["match_basis"] == "path_and_ast"
    assert tools._file_shape_snapshot(query, loaded).top_level_node_kinds == list(
        _parsed(query, "SwiftClassDeclaration").top_level_node_kinds
    )
    assert detect_language(str(query)) is None


def test_existing_file_without_compatible_declaration_has_no_match(tmp_path, monkeypatch):
    query = tmp_path / "Sources/Account/NewRepository.swift"
    query.parent.mkdir(parents=True)
    query.write_text("class NewRepository {}")
    loaded = _profile(
        tmp_path,
        {
            "protocol": _parsed(
                query.with_name("AccountRepository.swift"), "SwiftProtocolDeclaration"
            )
        },
    )
    _mock_parse(monkeypatch, _parsed(query, "SwiftClassDeclaration"))
    assert (
        tools._get_archetype_with_loaded(query, tmp_path, loaded, "none")["data"]["archetype"]
        is None
    )


def test_new_file_has_only_path_evidence_and_no_wrong_filename_role(tmp_path):
    query = tmp_path / "Sources/Account/NewViewController.swift"
    files = {
        "reactor": _parsed(query.with_name("AccountReactor.swift"), "SwiftClassDeclaration"),
        "view-controller": _parsed(
            query.with_name("AccountViewController.swift"), "SwiftClassDeclaration"
        ),
    }
    loaded = _profile(tmp_path, files)
    data = tools._get_archetype_with_loaded(query, tmp_path, loaded, "none")["data"]
    assert data["archetype"] == "view-controller"
    assert data["match_basis"] == "path_only"
    assert data["file_exists"] is False
    assert (
        tools._get_archetype_with_loaded(
            query.with_name("Unknown.swift"), tmp_path, loaded, "none"
        )["data"]["archetype"]
        is None
    )


def test_malformed_swift_does_not_invent_ast_match(tmp_path, monkeypatch):
    query = tmp_path / "Sources/Account/NewRepository.swift"
    query.parent.mkdir(parents=True)
    query.write_text("class NewRepository {")
    loaded = _profile(
        tmp_path,
        {
            "implementation": _parsed(
                query.with_name("LiveRepository.swift"), "SwiftClassDeclaration"
            )
        },
    )
    _mock_parse(monkeypatch, _parsed(query, "SwiftClassDeclaration", diagnostics=1))
    assert tools._file_shape_snapshot(query, loaded) is None
    data = tools._get_archetype_with_loaded(query, tmp_path, loaded, "none")["data"]
    assert data["match_basis"] == "path_only"
    assert data["match_quality"] == "exact"
    assert data["file_exists"] is True


@pytest.mark.parametrize(
    "reason", ["unsupported_language", "ast_node_ceiling_exceeded", "file_too_large"]
)
def test_skipped_swift_has_no_snapshot(tmp_path, monkeypatch, reason):
    query = tmp_path / "File.swift"
    query.write_text("class File {}")
    _mock_parse(monkeypatch, None, reason)
    assert tools._file_shape_snapshot(query, None) is None


def test_nearest_witness_filters_roles_even_with_single_candidate():
    snapshot = DimensionSnapshot(top_level_node_kinds=["SwiftClassDeclaration"])
    protocol = {
        "witness": {"path": "Sources/Account/AccountRepository.swift"},
        "normative_shape": {"ast_query": {"top_level_node_kinds": ["SwiftProtocolDeclaration"]}},
    }
    assert (
        tools._nearest_canonical_entry("Sources/Account/LiveRepository.swift", [protocol], snapshot)
        == {}
    )
    reactor = {"witness": {"path": "Sources/Account/AccountReactor.swift"}}
    assert (
        tools._nearest_canonical_entry("Sources/Account/NewViewController.swift", [reactor]) == {}
    )
    assert tools._prefix_overlap_fallback(
        "Sources/Account/NewViewController.swift",
        {"reactor": {"paths_pattern": "Sources/Account:swift"}},
    ) == (None, [])


def test_uppercase_swift_extension_uses_the_same_role_partition():
    from chameleon_mcp.signatures import path_pattern_bucket_for, swift_role_for_path

    assert swift_role_for_path("Sources/App/FeedViewController.SWIFT") == "view-controller"
    assert path_pattern_bucket_for(
        "Sources/App/FeedViewController.SWIFT"
    ) == path_pattern_bucket_for("Sources/App/FeedViewController.swift")
