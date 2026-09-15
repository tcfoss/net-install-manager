"""Tests for the Git tools utilities in Net Install Manager."""

from pathlib import Path
from unittest.mock import patch

from net_install_manager.runtime_config import RuntimeInfo
from net_install_manager.utilities.git_tools import (
    is_git_url,
    parse_git_source,
    GitSourceInfo,
    get_git_cache_root,
    clone_or_update_repo,
)
from net_install_manager.utilities.sys_platform import OperatingSystem, PlatformInfo, get_winpath


def test_is_git_url():
    """Test the is_git_url function."""
    assert is_git_url("https://github.com/owner/repo.git") is True
    assert is_git_url("git@github.com:owner/repo.git") is True
    assert is_git_url("https://gitlab.com/owner/repo") is True
    assert is_git_url("owner/repo") is True
    assert is_git_url("owner/repo@v1.0.0") is True
    assert is_git_url("owner/repo#src/App") is True
    assert is_git_url("./local/path") is False
    assert is_git_url("C:\\path\\to\\proj") is False
    assert is_git_url("") is False


def test_parse_git_source_standard():
    """Test parsing a standard Git source URL."""
    info = parse_git_source("https://github.com/owner/repo.git")
    assert info.clone_url == "https://github.com/owner/repo.git"
    assert info.ref is None
    assert info.subpath is None


def test_parse_git_source_with_ref_and_subpath():
    """Test parsing a Git source URL with a specific ref and subpath."""
    info = parse_git_source("https://github.com/owner/repo.git@v1.2.3#src/MyApp")
    assert info.clone_url == "https://github.com/owner/repo.git"
    assert info.ref == "v1.2.3"
    assert info.subpath == "src/MyApp"


def test_parse_git_source_github_tree_url():
    """Test parsing a GitHub tree URL."""
    url = "https://github.com/owner/repo/tree/main/src/CliApp"
    info = parse_git_source(url)
    assert info.clone_url == "https://github.com/owner/repo.git"
    assert info.ref == "main"
    assert info.subpath == "src/CliApp"


def test_parse_git_source_shorthand():
    """Test parsing a shorthand Git source URL."""
    info = parse_git_source("myorg/myrepo@beta")
    assert info.clone_url == "https://github.com/myorg/myrepo.git"
    assert info.ref == "beta"
    assert info.subpath is None


def test_parse_git_source_override_project():
    """Test parsing a Git source URL with a project override."""
    info = parse_git_source("owner/repo#ignore/this", project_override="custom/path.csproj")
    assert info.subpath == "custom/path.csproj"
    assert info.clone_url == "https://github.com/owner/repo.git"
    assert info.ref is None


def test_get_git_cache_root():
    """Test getting the Git cache root directory."""
    runtime_posix = RuntimeInfo(
        env={},
        home_dir=Path("/home/testuser"),
        platform=PlatformInfo(
            os=OperatingSystem.LINUX,
            architecture=PlatformInfo.detect().architecture,
            is_admin=False,
        ),
        system_wide=False,
    )
    path_posix = get_git_cache_root(
        runtime=runtime_posix,
    )
    assert path_posix == Path("/home/testuser/.cache/ninman/sources")

    runtime_win = RuntimeInfo(
        env={"LOCALAPPDATA": r"C:\Users\testuser\AppData\Local"},
        home_dir=get_winpath(r"C:\Users\testuser"),
        platform=PlatformInfo(
            os=OperatingSystem.WINDOWS,
            architecture=PlatformInfo.detect().architecture,
            is_admin=False,
        ),
        system_wide=False,
    )
    path_win = get_git_cache_root(
        runtime=runtime_win,
    )
    assert path_win == get_winpath(r"C:\Users\testuser\AppData\Local\ninman\cache\sources")


def test_clone_or_update_repo_mocked(tmp_path):
    """Test cloning or updating a Git repository with a mocked exec_command."""
    cache_root = tmp_path / "cache"
    info = GitSourceInfo(clone_url="https://github.com/test/app.git", ref="v1.0.0", subpath=None)

    with patch("net_install_manager.utilities.git_tools.exec_command") as mock_exec:

        def fake_clone(cmd, **kwargs):  # pylint: disable=unused-argument
            if len(cmd) > 1 and cmd[1] == "clone":
                dest = Path(cmd[3])
                dest.mkdir(parents=True, exist_ok=True)
                (dest / "App.csproj").write_text("<Project></Project>", encoding="utf-8")

        mock_exec.side_effect = fake_clone

        repo_dir = clone_or_update_repo(info, cache_root=cache_root)
        assert repo_dir.exists()
        assert (repo_dir / "App.csproj").exists()


def test_clone_or_update_repo_returns_root_for_subpath(tmp_path):
    """Test that Git project subpaths do not change the returned repository root."""
    cache_root = tmp_path / "cache"
    info = GitSourceInfo(
        clone_url="https://github.com/test/app.git",
        subpath="src/MyApp",
    )

    with patch("net_install_manager.utilities.git_tools.exec_command") as mock_exec:

        def fake_clone(cmd, **kwargs):  # pylint: disable=unused-argument
            if len(cmd) > 1 and cmd[1] == "clone":
                dest = Path(cmd[3])
                (dest / "src" / "MyApp").mkdir(parents=True, exist_ok=True)
                (dest / "src" / "MyApp" / "MyApp.csproj").write_text(
                    "<Project />", encoding="utf-8"
                )

        mock_exec.side_effect = fake_clone

        repo_dir = clone_or_update_repo(info, cache_root=cache_root)

    assert repo_dir.name.startswith("app_")
    assert repo_dir / "src" / "MyApp" / "MyApp.csproj" in repo_dir.rglob("*.csproj")
