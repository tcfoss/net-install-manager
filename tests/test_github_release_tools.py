"""Tests for GitHub release download and preparation utilities."""

from unittest.mock import MagicMock, patch
import zipfile

import pytest

from net_install_manager.runtime_config import RuntimeInfo
from net_install_manager.utilities.github_release_tools import (
    AssetInfo,
    GitHubRelease,
    GitHubReleaseInfo,
    get_github_token,
    prepare_release,
    unpack_archive_safely,
)


def test_get_github_token_precedence():
    """Prefer the ninman-specific token over common GitHub token variables."""
    assert get_github_token({"GH_TOKEN": "gh", "GITHUB_TOKEN": "github"}) == "github"
    assert (
        get_github_token(
            {"GH_TOKEN": "gh", "GITHUB_TOKEN": "github", "NINMAN_GITHUB_TOKEN": "ninman"}
        )
        == "ninman"
    )


def test_unpack_archive_rejects_path_traversal(tmp_path):
    """Reject ZIP members that would escape the extraction directory."""
    archive_path = tmp_path / "unsafe.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("../outside", "unsafe")

    with pytest.raises(ValueError, match="escapes extraction directory"):
        unpack_archive_safely(archive_path, tmp_path)


def test_prepare_release_downloads_and_cleans_up(tmp_path):
    """Prepare a release asset and remove its temporary directory afterward."""
    archive_bytes = tmp_path / "release.zip"
    with zipfile.ZipFile(archive_bytes, "w") as archive:
        archive.writestr(
            "ninman.yml", "app_directory: app\nbinary_name: app\nsource_binary_name: App.dll\n"
        )
        archive.writestr("App.dll", "binary")

    response = MagicMock()
    response.iter_content.return_value = [archive_bytes.read_bytes()]
    release = GitHubRelease(
        tag_name="v1.2.3",
        name="Release",
        version=None,
        assets=[AssetInfo(name="linux.zip", url="asset-url")],
    )
    source = GitHubReleaseInfo(owner="owner", repo="repo", asset_pattern="linux\\.zip")
    runtime = RuntimeInfo(env={})

    with (
        patch(
            "net_install_manager.utilities.github_release_tools.get_release_info",
            return_value=release,
        ),
        patch(
            "net_install_manager.utilities.github_release_tools.requests.get",
            return_value=response,
        ),
        prepare_release(source, runtime) as (artifact_dir, prepared_release),
    ):
        assert prepared_release == release
        assert (artifact_dir / "ninman.yml").exists()
        assert (artifact_dir / "App.dll").read_text(encoding="utf-8") == "binary"
        assert not list(artifact_dir.glob("*.zip"))
        temporary_dir = artifact_dir

    assert not temporary_dir.exists()
