from pathlib import Path
from unittest.mock import Mock

import pytest

from net_install_manager.commands.helpers import installation
from net_install_manager.config import app_sources
from net_install_manager.config.build_options import BuildOptions
from net_install_manager.core import errors


def test_extract_git_source_delegates_with_build_options(runtime, monkeypatch):
    options = BuildOptions(debug_mode=True)
    source = app_sources.GitCodeAppSource(
        "https://example.com/demo.git", "main", Path("App.csproj"), options,
        runtime.home_dir / "cache",
    )
    parse = Mock(return_value=source)
    monkeypatch.setattr(installation.git_utils, "parse_git_source", parse)

    assert installation.extract_app_source(source.clone_url, options, None, runtime) is source
    parse.assert_called_once_with(source.clone_url, runtime, options)


@pytest.mark.parametrize("asset_pattern", [None, "*.zip"])
def test_extract_release_source_defaults_asset_pattern(runtime, asset_pattern):
    assert installation.extract_app_source(
        "owner:repo:v1.2.3", BuildOptions(), asset_pattern, runtime
    ) == app_sources.GitHubReleaseAppSource(
        "owner", "repo", asset_pattern or "{rid}-{version}", "v1.2.3"
    )


def test_extract_release_source_rejects_ambiguous_local_path(runtime, monkeypatch):
    monkeypatch.setattr(Path, "exists", lambda _path: True)

    with pytest.raises(errors.AmbiguousSourceError) as exc_info:
        installation.extract_app_source("owner:repo", BuildOptions(), None, runtime)

    assert exc_info.value.source == "owner:repo"


def test_extract_missing_local_source_raises(runtime, tmp_path):
    source = tmp_path / "missing"

    with pytest.raises(FileNotFoundError):
        installation.extract_app_source(str(source), BuildOptions(), None, runtime)


@pytest.mark.parametrize("explicit_source", [False, True])
@pytest.mark.parametrize("has_project", [False, True])
def test_extract_local_source_uses_project_or_build_directory(
    runtime, tmp_path, monkeypatch, explicit_source, has_project
):
    monkeypatch.chdir(tmp_path)
    options = BuildOptions(self_contained=True)
    project = tmp_path / "App.csproj"
    if has_project:
        project.write_text("<Project />", encoding="utf-8")

    source = installation.extract_app_source(
        str(tmp_path) if explicit_source else None, options, None, runtime
    )

    assert source == (
        app_sources.CodeAppSource(project, options) if has_project
        else app_sources.BuiltAppSource(tmp_path)
    )
