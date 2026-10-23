from dataclasses import replace
from pathlib import Path
from unittest.mock import Mock

import pytest
import yaml

from net_install_manager.commands import self_migrate
from net_install_manager.commands.self_migrate import SelfMigrateCommand
from net_install_manager.config import app_sources
from net_install_manager.config.app_sources import BuiltAppSource
from net_install_manager.config.build_options import BuildOptions
from net_install_manager.core import errors
from net_install_manager.core.registry import Registry
from net_install_manager.runtime.runtime import Runtime
from net_install_manager.self_migration import mod_0_2_0_upgrade_registry as migration


def _runtime(registry_path: Path) -> Runtime:
    return replace(Runtime.current(), registry_path=registry_path)


def _legacy_entry(version: str, source: dict | None = None) -> dict:
    return {
        "binary_name": "sample",
        "app_directory": "Sample",
        "source_binary_name": "Sample",
        "source": source if source is not None else {"local_path": "/build"},
        "lib_path": "/install/Sample",
        "installed_version": version,
    }


@pytest.mark.parametrize(
    ("version", "source"),
    [("not-semver", {"local_path": "/build"}), ("1.2.3", {})],
)
def test_legacy_migration_failure_preserves_original_registry(tmp_path, version, source):
    runtime = _runtime(tmp_path / "apps.yaml")
    original = {"sample": _legacy_entry(version, source)}
    original_contents = yaml.safe_dump(original)
    runtime.registry_path.write_text(original_contents, encoding="utf-8")

    assert migration.main(runtime) == 1

    assert runtime.registry_path.read_text(encoding="utf-8") == original_contents


def test_legacy_migration_converts_registry_and_adds_version_marker(tmp_path):
    runtime = _runtime(tmp_path / "apps.yaml")
    runtime.registry_path.write_text(
        yaml.safe_dump({"sample": _legacy_entry("1.2.3")}),
        encoding="utf-8",
    )

    assert migration.main(runtime) == 0

    registry = Registry(runtime)
    app = registry.get("sample")
    assert app is not None
    assert str(app.installed_version) == "1.2.3"
    assert app.app_source == BuiltAppSource(Path("/build"))
    assert registry.version is not None


def test_self_migrate_command_raises_when_migration_fails(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(self_migrate, "migrate_main", lambda _runtime: 1)

    with pytest.raises(errors.SelfMigrationError) as exc_info:
        SelfMigrateCommand().execute(_runtime(tmp_path / "apps.yaml"), None)

    assert exc_info.value.status == 1
    assert capsys.readouterr().out == ""


def test_self_migrate_command_reports_success(runtime, monkeypatch, capsys):
    monkeypatch.setattr(self_migrate, "migrate_main", lambda _runtime: 0)

    SelfMigrateCommand().execute(runtime, None)

    assert capsys.readouterr().out == (
        f"Successfully migrated managed files for registry '{runtime.registry_path}'.\n"
    )


def test_load_old_registry_missing_file_returns_empty(tmp_path):
    assert migration._load_registry_old(tmp_path / "missing.yaml") == {}


@pytest.mark.parametrize(
    ("contents", "message"),
    [
        ("[]", "must contain a mapping"),
        ("sample: []", "entry 'sample' must be a mapping"),
        ("sample: {unexpected: value}", "unexpected"),
        ("sample: [", "expected"),
    ],
)
def test_load_old_registry_rejects_malformed_data(tmp_path, caplog, contents, message):
    path = tmp_path / "apps.yaml"
    path.write_text(contents, encoding="utf-8")

    with pytest.raises((ValueError, TypeError, yaml.YAMLError)):
        migration._load_registry_old(path)

    assert "Failed to load old registry from path" in caplog.text
    assert message in caplog.text


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        (
            {"git_info": {"clone_url": "https://example.com/demo.git", "ref": "main"}},
            migration.InstallSource(
                git_info=migration.GitSourceInfo("https://example.com/demo.git", "main")
            ),
        ),
        (
            {"release_info": {"owner": "owner", "repo": "repo", "asset_pattern": "*.zip"}},
            migration.InstallSource(
                release_info=migration.GitHubReleaseInfo("owner", "repo", "*.zip")
            ),
        ),
    ],
)
def test_load_old_registry_rehydrates_nested_sources(tmp_path, source, expected):
    path = tmp_path / "apps.yaml"
    path.write_text(yaml.safe_dump({"sample": _legacy_entry("1.2.3", source)}), encoding="utf-8")

    assert migration._load_registry_old(path)["sample"].source == expected


@pytest.mark.parametrize(
    ("subpath", "project_path", "expected_subpath"),
    [("src/App.csproj", "other.csproj", "src/App.csproj"),
     (None, "App.csproj", "App.csproj"), (None, None, ".")],
)
def test_extract_git_source_preserves_build_options_and_path_precedence(
    runtime, monkeypatch, subpath, project_path, expected_subpath
):
    cache_dir = runtime.home_dir / "cache"
    monkeypatch.setattr(migration.git_utils, "_get_cache_dir", lambda _url, _runtime: cache_dir)
    app = migration.TrackedApp(
        "sample", "Sample", "Sample",
        migration.InstallSource(
            git_info=migration.GitSourceInfo("https://example.com/demo.git", "main", subpath),
            project_path=project_path,
        ),
        release=False, self_contained=True,
    )

    assert migration._extract_install_source(app, runtime) == app_sources.GitCodeAppSource(
        "https://example.com/demo.git", "main", Path(expected_subpath),
        BuildOptions(debug_mode=True, self_contained=True), cache_dir,
    )


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        (
            migration.InstallSource(
                release_info=migration.GitHubReleaseInfo("owner", "repo", "*.zip")
            ),
            app_sources.GitHubReleaseAppSource("owner", "repo", "*.zip"),
        ),
        (
            migration.InstallSource(project_path="App.csproj"),
            app_sources.CodeAppSource(Path("App.csproj"), BuildOptions()),
        ),
        (migration.InstallSource(local_path="build"), BuiltAppSource(Path("build"))),
        (migration.InstallSource(), None),
    ],
)
def test_extract_install_source_variants(runtime, source, expected):
    app = migration.TrackedApp("sample", "Sample", "Sample", source)

    assert migration._extract_install_source(app, runtime) == expected


def test_migration_leaves_current_registry_untouched(runtime):
    runtime.registry_path.parent.mkdir(parents=True)
    contents = yaml.safe_dump({"__NINMAN_VERSION__": "0.2.0"})
    runtime.registry_path.write_text(contents, encoding="utf-8")

    assert migration.main(runtime) == 0
    assert runtime.registry_path.read_text(encoding="utf-8") == contents


@pytest.mark.parametrize("contents", ["[]", "sample: []"])
def test_migration_reports_malformed_legacy_registry(runtime, caplog, contents):
    runtime.registry_path.parent.mkdir(parents=True)
    runtime.registry_path.write_text(contents, encoding="utf-8")

    assert migration.main(runtime) == 1
    assert "Failed to load old registry:" in caplog.text
    assert runtime.registry_path.read_text(encoding="utf-8") == contents


def test_migration_missing_version_preserves_registry(runtime, caplog):
    runtime.registry_path.parent.mkdir(parents=True)
    contents = yaml.safe_dump({"sample": _legacy_entry("")})
    runtime.registry_path.write_text(contents, encoding="utf-8")

    assert migration.main(runtime) == 1
    assert "has no installed version" in caplog.text
    assert runtime.registry_path.read_text(encoding="utf-8") == contents


def test_migration_cleans_temporary_file_when_replace_fails(runtime, monkeypatch):
    runtime.registry_path.parent.mkdir(parents=True)
    contents = yaml.safe_dump({"sample": _legacy_entry("1.2.3")})
    runtime.registry_path.write_text(contents, encoding="utf-8")
    before = set(runtime.registry_path.parent.iterdir())

    def fail_replace(_path, _target):
        raise PermissionError("registry locked")

    monkeypatch.setattr(Path, "replace", fail_replace)

    with pytest.raises(PermissionError, match="registry locked"):
        migration.main(runtime)

    assert runtime.registry_path.read_text(encoding="utf-8") == contents
    assert set(runtime.registry_path.parent.iterdir()) == before


def test_migration_reports_temporary_file_creation_failure(runtime, monkeypatch):
    runtime.registry_path.parent.mkdir(parents=True)
    contents = yaml.safe_dump({"sample": _legacy_entry("1.2.3")})
    runtime.registry_path.write_text(contents, encoding="utf-8")
    monkeypatch.setattr(
        migration.tempfile, "NamedTemporaryFile",
        Mock(side_effect=PermissionError("cannot create temporary file")),
    )

    with pytest.raises(PermissionError, match="cannot create temporary file"):
        migration.main(runtime)

    assert runtime.registry_path.read_text(encoding="utf-8") == contents
    assert list(runtime.registry_path.parent.iterdir()) == [runtime.registry_path]
