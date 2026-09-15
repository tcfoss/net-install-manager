"""Tests for normalized installation source handling."""

from unittest.mock import patch

import pytest

from net_install_manager.errors import AppManagerError
from net_install_manager.utilities.git_tools import GitSourceInfo
from net_install_manager.utilities.install_tools import (
    InstallSource,
    get_buildable_source,
    get_paths_no_buildable_source,
)


def test_install_source_requires_exactly_one_source_kind():
    """Test that InstallSource rejects ambiguous or empty sources."""
    with pytest.raises(ValueError):
        InstallSource()
    with pytest.raises(ValueError):
        InstallSource(local_path="local", git_info=GitSourceInfo(clone_url="repo"))


def test_get_buildable_source_resolves_git_project_path(tmp_path):
    """Test that a Git project path is applied once relative to the repository root."""
    repo_dir = tmp_path / "repo"
    project_dir = repo_dir / "src" / "MyApp"
    project_dir.mkdir(parents=True)
    csproj = project_dir / "MyApp.csproj"
    csproj.write_text("<Project />", encoding="utf-8")
    source = InstallSource(
        git_info=GitSourceInfo(clone_url="https://github.com/example/app.git"),
        project_path="src/MyApp",
    )

    with patch(
        "net_install_manager.utilities.install_tools.clone_or_update_repo",
        return_value=repo_dir,
    ) as mock_clone:
        result = get_buildable_source(source, quiet=True)

    assert result is not None
    assert result.source_root == repo_dir
    assert result.csproj_path == csproj
    assert result.source == source
    mock_clone.assert_called_once_with(source.git_info, cache_root=None, quiet=True)


def test_get_buildable_source_git_without_project_fails_when_no_csproj(tmp_path):
    """Test that a Git source without a project cannot resolve a missing project."""
    source = InstallSource(git_info=GitSourceInfo(clone_url="https://github.com/example/app.git"))

    with patch(
        "net_install_manager.utilities.install_tools.clone_or_update_repo",
        return_value=tmp_path,
    ):
        with pytest.raises(AppManagerError, match="No .csproj file found"):
            get_buildable_source(source)


def test_get_paths_no_buildable_source_applies_project_path(tmp_path):
    """Test that precompiled binaries can be selected from a source subdirectory."""
    project_dir = tmp_path / "src" / "MyApp"
    project_dir.mkdir(parents=True)
    binary = project_dir / "MyApp.dll"
    binary.write_text("binary", encoding="utf-8")
    source = InstallSource(local_path=str(tmp_path), project_path="src/MyApp")

    copy_source, binary_path = get_paths_no_buildable_source("MyApp.dll", source)

    assert copy_source == project_dir
    assert binary_path == binary
