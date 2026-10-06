from pathlib import Path

import pytest

from net_install_manager.config import app_sources
from net_install_manager.config.build_options import BuildOptions
from net_install_manager.core import artifact_provider, errors
from net_install_manager.runtime.runtime import Runtime


def test_prepare_source_downloads_github_release_with_token(monkeypatch, tmp_path):
    source = app_sources.GitHubReleaseAppSource("owner", "repo", "linux-{version}")
    runtime = Runtime.current()
    working_dir = tmp_path / "work"
    calls = []
    monkeypatch.setattr(
        artifact_provider.git_utils,
        "download_artifact",
        lambda *args: calls.append(args),
    )

    prepared = artifact_provider.DefaultArtifactProvider().prepare_source(
        source, runtime, working_dir, "test-token"
    )

    assert prepared is source
    assert calls == [(working_dir, source, runtime, "test-token")]


def test_prepare_source_returns_local_source_unchanged(tmp_path):
    source = app_sources.BuiltAppSource(tmp_path / "build")

    prepared = artifact_provider.DefaultArtifactProvider().prepare_source(
        source, Runtime.current(), tmp_path / "work"
    )

    assert prepared is source


def test_prepare_source_finds_nested_project_for_git_source(monkeypatch, tmp_path):
    cache_dir = tmp_path / "checkout"
    project = cache_dir / "src" / "App" / "App.csproj"
    project.parent.mkdir(parents=True)
    project.write_text("<Project></Project>", encoding="utf-8")
    source = app_sources.GitCodeAppSource(
        "https://example.com/source.git",
        None,
        Path("/dev/null"),
        BuildOptions(),
        cache_dir,
    )
    monkeypatch.setattr(artifact_provider.git_utils, "clone_or_update_repo", lambda _: None)

    prepared = artifact_provider.DefaultArtifactProvider().prepare_source(
        source, Runtime.current(), tmp_path / "work"
    )

    assert isinstance(prepared, app_sources.GitCodeAppSource)

    assert prepared.subpath == Path("src/App/App.csproj")
    assert prepared.project_path == project


def test_prepare_source_rejects_git_project_outside_cache(monkeypatch, tmp_path):
    cache_dir = tmp_path / "checkout"
    cache_dir.mkdir()
    outside_project = tmp_path / "outside.csproj"
    outside_project.touch()
    source = app_sources.GitCodeAppSource(
        "https://example.com/source.git",
        "main",
        Path("../outside.csproj"),
        BuildOptions(),
        cache_dir,
    )
    monkeypatch.setattr(artifact_provider.git_utils, "clone_or_update_repo", lambda _: None)

    with pytest.raises(errors.InvalidSourceError):
        artifact_provider.DefaultArtifactProvider().prepare_source(
            source, Runtime.current(), tmp_path / "work"
        )


@pytest.mark.parametrize("project_name", ["missing.csproj", "not-a-project.txt"])
def test_prepare_source_rejects_missing_or_non_project_git_path(
    monkeypatch, tmp_path, project_name
):
    cache_dir = tmp_path / "checkout"
    cache_dir.mkdir()
    if project_name != "missing.csproj":
        (cache_dir / project_name).touch()
    source = app_sources.GitCodeAppSource(
        "https://example.com/source.git",
        "main",
        Path(project_name),
        BuildOptions(),
        cache_dir,
    )
    monkeypatch.setattr(artifact_provider.git_utils, "clone_or_update_repo", lambda _: None)

    with pytest.raises(errors.InvalidSourceError):
        artifact_provider.DefaultArtifactProvider().prepare_source(
            source, Runtime.current(), tmp_path / "work"
        )


@pytest.mark.parametrize(
    ("source", "project_path", "source_directory"),
    [
        (
            app_sources.CodeAppSource(Path("/src/App.csproj"), BuildOptions()),
            Path("/src/App.csproj"),
            Path("/src"),
        ),
        (
            app_sources.GitCodeAppSource(
                "https://example.com/source.git",
                "main",
                Path("src/App.csproj"),
                BuildOptions(),
                Path("/cache"),
            ),
            Path("/cache/src/App.csproj"),
            Path("/cache/src"),
        ),
        (app_sources.BuiltAppSource(Path("/build")), None, Path("/build")),
        (app_sources.GitHubReleaseAppSource("owner", "repo", "linux"), None, None),
    ],
)
def test_source_metadata_helpers(source, project_path, source_directory):
    provider = artifact_provider.DefaultArtifactProvider()

    assert provider._project_path(source) == project_path
    assert provider._source_directory(source) == source_directory


@pytest.mark.parametrize("source_kind", ["code", "git"])
def test_build_publishes_code_sources(monkeypatch, tmp_path, source_kind):
    options = BuildOptions(debug_mode=True)
    working_dir = tmp_path / "work"
    project_path = tmp_path / "src" / "App.csproj"
    if source_kind == "code":
        source = app_sources.CodeAppSource(project_path, options)
        expected_project_path = project_path
    else:
        cache_dir = tmp_path / "cache"
        source = app_sources.GitCodeAppSource(
            "https://example.com/source.git",
            "main",
            Path("src/App.csproj"),
            options,
            cache_dir,
        )
        expected_project_path = cache_dir / "src/App.csproj"

    calls = []
    monkeypatch.setattr(
        artifact_provider.cs_utils,
        "publish",
        lambda *args: calls.append(args),
    )

    output_dir = artifact_provider.DefaultArtifactProvider._build(source, options, working_dir)

    assert output_dir == working_dir / "dist"
    assert output_dir.is_dir()
    assert calls == [(expected_project_path, output_dir, options)]


@pytest.mark.parametrize(
    ("source", "expected_directory"),
    [
        (app_sources.BuiltAppSource(Path("/build")), Path("/build")),
        (
            app_sources.GitHubReleaseAppSource("owner", "repo", "linux"),
            Path("/work/dist"),
        ),
    ],
)
def test_build_returns_existing_artifact_directory(source, expected_directory, tmp_path):
    working_dir = tmp_path / "work"
    if isinstance(source, app_sources.GitHubReleaseAppSource):
        expected_directory = working_dir / "dist"

    result = artifact_provider.DefaultArtifactProvider._build(source, BuildOptions(), working_dir)

    assert result == expected_directory


def test_build_rejects_unsupported_source(tmp_path):
    with pytest.raises(errors.InvalidSourceError):
        artifact_provider.DefaultArtifactProvider._build(
            object(), BuildOptions(), tmp_path / "work"  # type: ignore
        )


def test_prepare_and_build_returns_prepared_artifact(monkeypatch, tmp_path):
    provider = artifact_provider.DefaultArtifactProvider()
    source = app_sources.BuiltAppSource(tmp_path / "build")
    prepared_source = app_sources.GitHubReleaseAppSource("owner", "repo", "linux")
    project_path = tmp_path / "App.csproj"
    artifact_dir = tmp_path / "dist"
    options = BuildOptions()
    runtime = Runtime.current()
    working_dir = tmp_path / "work"
    calls = []
    monkeypatch.setattr(
        provider,
        "prepare_source",
        lambda given_source, given_runtime, given_working_dir, token: (
            calls.append((given_source, given_runtime, given_working_dir, token))
            or prepared_source
        ),
    )
    monkeypatch.setattr(provider, "_project_path", lambda current_source: project_path)
    monkeypatch.setattr(
        provider,
        "_build",
        lambda current_source, build_options, given_working_dir: artifact_dir,
    )

    result = provider.prepare_and_build(source, options, runtime, working_dir, "token")

    assert result == artifact_provider.PreparedArtifact(
        prepared_source, artifact_dir, project_path
    )
    assert calls == [(source, runtime, working_dir, "token")]
