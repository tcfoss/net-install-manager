import logging
from pathlib import Path
import tarfile
import zipfile
from io import BytesIO
from types import SimpleNamespace

import pytest

from net_install_manager.config.app_sources import GitCodeAppSource, GitHubReleaseAppSource
from net_install_manager.config.build_options import BuildOptions
from net_install_manager.core import errors
from net_install_manager.runtime.architecture import Architecture
from net_install_manager.runtime.operating_system import OperatingSystem
from net_install_manager.runtime.platform_info import PlatformInfo
from net_install_manager.runtime.runtime import Runtime
from net_install_manager.utilities import git


def _runtime(home=Path("/home/tester"), env=None):
    return Runtime(
        platform=PlatformInfo(OperatingSystem.LINUX, Architecture.X86_64),
        env=env or {},
        registry_path=Path("/unused/registry.yaml"),
        home_dir=home,
    )


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("https://github.com/example/project.git", True),
        ("git@github.com:example/project.git", True),
        ("github.com/example/project", True),
        ("example/project@v1.2.3#src/App.csproj", True),
        ("./example/project", False),
        (r"C:\work\project", False),
        ("", False),
    ],
)
def test_is_git_url(source, expected):
    assert git.is_git_url(source) is expected


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("owner:repo", ("owner", "repo", None)),
        ("owner:repo:v1.2.3", ("owner", "repo", "v1.2.3")),
        ("https://github.com/owner/repo", None),
        ("owner:repo:bad/tag", None),
    ],
)
def test_parse_git_release(source, expected):
    assert git.parse_git_release(source) == expected


def test_parse_git_source_normalizes_shorthand_and_extracts_ref_subpath_1():
    runtime = _runtime()

    source = git.parse_git_source("owner/project@v1.2.3#src/App.csproj", runtime)

    assert source.clone_url == "https://github.com/owner/project.git"
    assert source.ref == "v1.2.3"
    assert source.subpath == Path("src/App.csproj")
    assert source.cache_dir.parent == runtime.cache_root


def test_parse_git_source_normalizes_shorthand_and_extracts_ref_subpath_2():
    runtime = _runtime()

    source = git.parse_git_source("github.com/owner/project@v1.2.3#src/App.csproj", runtime)

    assert source.clone_url == "https://github.com/owner/project.git"
    assert source.ref == "v1.2.3"
    assert source.subpath == Path("src/App.csproj")
    assert source.cache_dir.parent == runtime.cache_root


def test_parse_git_source_normalizes_shorthand_and_extracts_ref_subpath_ssh():
    runtime = _runtime()

    source = git.parse_git_source(
        "git@github.com:owner/project.git@v1.2.3#src/App.csproj", runtime
    )

    assert source.clone_url == "git@github.com:owner/project.git"
    assert source.ref == "v1.2.3"
    assert source.subpath == Path("src/App.csproj")
    assert source.cache_dir.parent == runtime.cache_root


def test_parse_git_source_handles_github_tree_url_and_project_override():
    source = git.parse_git_source(
        "https://github.com/owner/project/tree/main/apps/old",
        _runtime(),
        project_override="apps/new/App.csproj",
    )

    assert source.clone_url == "https://github.com/owner/project.git"
    assert source.ref == "main"
    assert source.subpath == Path("apps/new/App.csproj")


def test_parse_git_source_uses_sentinel_when_project_not_specified():
    source = git.parse_git_source("owner/project", _runtime())

    assert source.subpath == Path("/dev/null")
    assert source.build_options == BuildOptions()


def test_parse_git_source_uses_override_for_regular_url():
    source = git.parse_git_source(
        "https://example.com/project.git#old/path",
        _runtime(),
        project_override="new/App.csproj",
    )

    assert source.clone_url == "https://example.com/project.git"
    assert source.subpath == Path("new/App.csproj")


def test_cache_directory_is_stable_and_separates_repositories():
    runtime = _runtime()
    first = git._get_cache_dir("https://example.com/one.git", runtime)
    repeated = git._get_cache_dir("https://example.com/one.git", runtime)
    other = git._get_cache_dir("https://example.com/two.git", runtime)

    assert first == repeated
    assert first != other
    assert first.parent == runtime.cache_root


def test_clone_or_update_repo_fetches_checks_out_and_pulls_existing_repo(tmp_path, monkeypatch):
    cache_dir = tmp_path / "repo"
    (cache_dir / ".git").mkdir(parents=True)
    source = GitCodeAppSource(
        "https://example.com/repo.git",
        "main",
        Path("/dev/null"),
        BuildOptions(),
        cache_dir,
    )
    commands = []
    monkeypatch.setattr(
        git, "exec_command", lambda command, **kwargs: commands.append((command, kwargs))
    )

    git.clone_or_update_repo(source)

    assert commands == [
        (["git", "fetch", "--all", "--tags"], {"cwd": str(cache_dir)}),
        (["git", "checkout", "main"], {"cwd": str(cache_dir)}),
        (["git", "pull", "--ff-only"], {"cwd": str(cache_dir)}),
    ]


def test_clone_or_update_repo_clones_missing_repo(tmp_path, monkeypatch):
    cache_dir = tmp_path / "repo"
    source = GitCodeAppSource(
        "https://example.com/repo.git", None, Path("/dev/null"), BuildOptions(), cache_dir
    )
    commands = []
    output_commands = []
    monkeypatch.setattr(git, "exec_command", lambda command, **kwargs: commands.append(command))
    monkeypatch.setattr(
        git,
        "exec_command_output",
        lambda command, **kwargs: output_commands.append(command)
        or ("origin/trunk\n" if command[1] == "symbolic-ref" else "trunk\n"),
    )

    git.clone_or_update_repo(source)

    assert cache_dir.is_dir()
    assert commands[0] == ["git", "clone", source.clone_url, str(cache_dir)]
    assert commands[1:] == [
        ["git", "remote", "set-head", "origin", "--auto"],
        ["git", "switch", "trunk"],
        ["git", "branch", "--set-upstream-to", "origin/trunk", "trunk"],
        ["git", "pull", "--ff-only"],
    ]
    assert output_commands == [
        ["git", "symbolic-ref", "--short", "refs/remotes/origin/HEAD"],
        ["git", "branch", "--format=%(refname:short)"],
    ]


@pytest.mark.parametrize(
    ("local_branches", "expected_switch"),
    [
        ("trunk\nfeature\n", ["git", "switch", "trunk"]),
        ("feature\n", ["git", "switch", "--track", "origin/trunk"]),
    ],
)
def test_clone_or_update_repo_switches_to_remote_default_branch(
    tmp_path, monkeypatch, local_branches, expected_switch
):
    cache_dir = tmp_path / "repo"
    (cache_dir / ".git").mkdir(parents=True)
    source = GitCodeAppSource(
        "https://example.com/repo.git", None, Path("/dev/null"), BuildOptions(), cache_dir
    )
    commands = []
    output_commands = []

    def fake_output(command, **kwargs):
        output_commands.append(command)
        if command[1] == "symbolic-ref":
            return "origin/trunk\n"
        return local_branches

    monkeypatch.setattr(git, "exec_command", lambda command, **kwargs: commands.append(command))
    monkeypatch.setattr(git, "exec_command_output", fake_output)

    git.clone_or_update_repo(source)

    assert commands == [
        ["git", "fetch", "--all", "--tags"],
        ["git", "remote", "set-head", "origin", "--auto"],
        expected_switch,
        *(
            [["git", "branch", "--set-upstream-to", "origin/trunk", "trunk"]]
            if "trunk" in local_branches.splitlines()
            else []
        ),
        ["git", "pull", "--ff-only"],
    ]
    assert output_commands == [
        ["git", "symbolic-ref", "--short", "refs/remotes/origin/HEAD"],
        ["git", "branch", "--format=%(refname:short)"],
    ]


def test_clone_or_update_repo_warns_but_swallows_pull_failure(tmp_path, monkeypatch, caplog):
    cache_dir = tmp_path / "repo"
    (cache_dir / ".git").mkdir(parents=True)
    source = GitCodeAppSource(
        "https://example.com/repo.git", None, Path("/dev/null"), BuildOptions(), cache_dir
    )

    def fail_pull(command, **_kwargs):
        if command[:2] == ["git", "pull"]:
            raise RuntimeError("offline")

    monkeypatch.setattr(git, "exec_command", fail_pull)
    monkeypatch.setattr(
        git,
        "exec_command_output",
        lambda command, **kwargs: "origin/main\n" if command[1] == "symbolic-ref" else "main\n",
    )

    git.clone_or_update_repo(source)

    assert "Failed to fast-forward the default branch" in caplog.text


@pytest.mark.parametrize("failure_command", ["fetch", "switch"])
def test_clone_or_update_repo_logs_and_raises_on_default_branch_failure(
    tmp_path, monkeypatch, caplog, failure_command
):
    cache_dir = tmp_path / "repo"
    (cache_dir / ".git").mkdir(parents=True)
    source = GitCodeAppSource(
        "https://example.com/repo.git", None, Path("/dev/null"), BuildOptions(), cache_dir
    )
    commands = []

    def fail_command(command, **_kwargs):
        commands.append(command)
        if command[:2] == ["git", failure_command]:
            raise RuntimeError("checkout failed")

    monkeypatch.setattr(git, "exec_command", fail_command)
    monkeypatch.setattr(
        git,
        "exec_command_output",
        lambda command, **kwargs: "origin/trunk\n" if command[1] == "symbolic-ref" else "",
    )

    with pytest.raises(errors.GitBranchError) as error:
        git.clone_or_update_repo(source)

    assert error.value.clone_url == source.clone_url
    assert isinstance(error.value.__cause__, RuntimeError)
    assert "checkout failed" in caplog.text
    assert any(
        record.levelno == logging.ERROR and record.exc_info is not None
        for record in caplog.records
    )
    assert ["git", "pull", "--ff-only"] not in commands


def test_github_token_uses_first_present_name():
    assert (
        git.get_github_token(
            {"NINMAN_GITHUB_TOKEN": "first", "GITHUB_TOKEN": "second", "GH_TOKEN": "third"}
        )
        == "first"
    )
    assert git.get_github_token({"GITHUB_TOKEN": "second", "GH_TOKEN": "third"}) == "second"
    assert git.get_github_token({}) is None


def test_request_headers_include_optional_bearer_token():
    assert git._headers("application/json", None) == {"Accept": "application/json"}
    assert git._headers("application/json", "secret") == {
        "Accept": "application/json",
        "Authorization": "Bearer secret",
    }


def test_get_release_info_requests_tag_and_parses_assets(monkeypatch):
    calls = []
    response = SimpleNamespace(
        raise_for_status=lambda: None,
        json=lambda: {
            "tag_name": "v1.2.3",
            "name": "Release",
            "assets": [{"name": "linux-x64-1.2.3.zip", "url": "https://assets/1"}],
        },
    )
    monkeypatch.setattr(
        git.requests, "get", lambda url, **kwargs: calls.append((url, kwargs)) or response
    )

    release = git._get_release_info("owner", "repo", "v1.2.3", "token")

    assert calls[0][0] == "https://api.github.com/repos/owner/repo/releases/tags/v1.2.3"
    assert calls[0][1]["headers"]["Authorization"] == "Bearer token"
    assert release.tag_name == "v1.2.3"
    assert str(release.version) == "1.2.3"
    assert release.assets[0].name == "linux-x64-1.2.3.zip"


def test_substitute_pattern_replaces_runtime_and_release_values():
    release = git._GitHubRelease("v1.2.3", "Release", git.parse_semver("v1.2.3"), [])

    result = git.substitute_pattern("{rid}-{os}-{arch}-{version}", _runtime(), release)

    assert result == "linux-x64-linux-x64-1.2.3"


def test_download_asset_selects_one_match_and_streams_bytes(monkeypatch, tmp_path):
    release = git._GitHubRelease(
        tag_name="v1.2.3",
        name="Release",
        version=git.parse_semver("v1.2.3"),
        assets=[git._AssetInfo("linux-x64-1.2.3.zip", "https://assets/1")],
    )
    response = SimpleNamespace(
        raise_for_status=lambda: None,
        iter_content=lambda chunk_size: [b"first", b"", b"second"],
    )
    calls = []
    monkeypatch.setattr(
        git.requests, "get", lambda url, **kwargs: calls.append((url, kwargs)) or response
    )

    result = git.download_asset(
        release, "{rid}-{version}", _runtime(), tmp_path / "downloads", "token"
    )

    assert result.read_bytes() == b"firstsecond"
    assert calls[0][0] == "https://assets/1"
    assert calls[0][1]["stream"] is True
    assert calls[0][1]["headers"]["Authorization"] == "Bearer token"


@pytest.mark.parametrize(
    ("assets", "message"),
    [([], "No asset matching"), (["linux-a.zip", "linux-b.zip"], "Multiple assets matching")],
)
def test_download_asset_requires_exactly_one_match(assets, message, tmp_path):
    release = git._GitHubRelease(
        "v1.0.0",
        "Release",
        None,
        [git._AssetInfo(name, f"https://assets/{name}") for name in assets],
    )

    with pytest.raises(ValueError, match=message):
        git.download_asset(release, "linux", _runtime(), tmp_path)


def test_unpack_archive_safely_extracts_zip_and_tar(tmp_path):
    zip_path = tmp_path / "app.zip"
    with zipfile.ZipFile(zip_path, "w") as archive:
        archive.writestr("bin/app", "zip-content")
    zip_output = tmp_path / "zip-output"
    zip_output.mkdir()
    git.unpack_archive_safely(zip_path, zip_output)
    assert (zip_output / "bin/app").read_text(encoding="utf-8") == "zip-content"

    tar_path = tmp_path / "app.tar"
    file_data = b"tar-content"
    info = tarfile.TarInfo("app")
    info.size = len(file_data)
    with tarfile.open(tar_path, "w") as archive:
        archive.addfile(info, BytesIO(file_data))
    tar_output = tmp_path / "tar-output"
    tar_output.mkdir()
    git.unpack_archive_safely(tar_path, tar_output)
    assert (tar_output / "app").read_bytes() == file_data


@pytest.mark.parametrize("member", ["../outside", "/absolute/path"])
def test_unpack_archive_safely_rejects_zip_traversal(tmp_path, member):
    archive_path = tmp_path / "unsafe.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr(member, "unsafe")

    with pytest.raises(ValueError, match="escapes extraction directory"):
        git.unpack_archive_safely(archive_path, tmp_path / "output")


def test_unpack_archive_safely_rejects_tar_traversal(tmp_path):
    archive_path = tmp_path / "unsafe.tar"
    info = tarfile.TarInfo("../outside")
    info.size = 4
    with tarfile.open(archive_path, "w") as archive:
        archive.addfile(info, BytesIO(b"evil"))

    with pytest.raises(ValueError, match="escapes extraction directory"):
        git.unpack_archive_safely(archive_path, tmp_path / "output")


def test_unpack_archive_safely_rejects_unknown_format(tmp_path):
    path = tmp_path / "unknown.bin"
    path.write_bytes(b"not an archive")

    with pytest.raises(ValueError, match="Unsupported archive format"):
        git.unpack_archive_safely(path, tmp_path / "output")


def test_download_artifact_downloads_and_unpacks_selected_release(monkeypatch, tmp_path):
    archive_path = tmp_path / "release.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("Sample.dll", "binary")
    release = git._GitHubRelease("v1.0.0", "Release", None, [])
    monkeypatch.setattr(git, "_get_release_info", lambda *args: release)
    monkeypatch.setattr(git, "download_asset", lambda *args: archive_path)
    working_dir = tmp_path / "work"
    working_dir.mkdir()
    source = GitHubReleaseAppSource("owner", "repo", "linux")

    artifact_dir, returned_release = git.download_artifact(
        working_dir, source, _runtime(), token="token"
    )

    assert returned_release is release
    assert (artifact_dir / "Sample.dll").read_text(encoding="utf-8") == "binary"


def test_download_artifact_copies_non_archive_asset(monkeypatch, tmp_path):
    working_dir = tmp_path / "work"
    working_dir.mkdir()
    asset_path = tmp_path / "Sample.dll"
    asset_path.write_bytes(b"binary")
    release = git._GitHubRelease("v1.0.0", "Release", None, [])
    monkeypatch.setattr(git, "_get_release_info", lambda *args: release)
    monkeypatch.setattr(git, "download_asset", lambda *args: asset_path)

    artifact_dir, _ = git.download_artifact(
        working_dir, GitHubReleaseAppSource("owner", "repo", "linux"), _runtime()
    )

    assert (artifact_dir / asset_path.name).read_bytes() == b"binary"
