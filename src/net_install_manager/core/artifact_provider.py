"""Artifact providers."""

from dataclasses import dataclass, replace
from pathlib import Path
from typing import Protocol

from net_install_manager.config import app_sources as aps
from net_install_manager.config.build_options import BuildOptions
from net_install_manager.core import errors
from net_install_manager.runtime.runtime import Runtime
from net_install_manager.utilities import csproj as cs_utils
from net_install_manager.utilities import git as git_utils


@dataclass(frozen=True)
class PreparedArtifact:
    """An installable directory and source metadata used to resolve its identity."""

    app_source: aps.AppSource
    directory: Path
    project_path: Path | None


class ArtifactProvider(Protocol):  # pylint: disable=too-few-public-methods
    """Prepare source material and return a built or downloaded application directory."""

    def prepare_and_build(
        self,
        app_source: aps.AppSource,
        build_options: BuildOptions,
        runtime: Runtime,
        working_dir: Path,
        token: str | None = None,
    ) -> PreparedArtifact:
        """Prepare the source and return the resulting installable artifact."""
        ...


class DefaultArtifactProvider:
    """Prepare local, Git, and GitHub release sources using the project utilities."""

    def prepare_and_build(
        self,
        app_source: aps.AppSource,
        build_options: BuildOptions,
        runtime: Runtime,
        working_dir: Path,
        token: str | None = None,
    ) -> PreparedArtifact:
        """Prepare the artifact and build source, if necessary."""
        prepared_source = self.prepare_source(app_source, runtime, working_dir, token)
        project_path = self._project_path(prepared_source)
        artifact_dir = self._build(prepared_source, build_options, working_dir)
        return PreparedArtifact(prepared_source, artifact_dir, project_path)

    def prepare_source(
        self,
        app_source: aps.AppSource,
        runtime: Runtime,
        working_dir: Path,
        token: str | None = None,
    ) -> aps.AppSource:
        """Resolve Git project paths and download GitHub release artifacts."""

        match app_source:
            case aps.GitCodeAppSource() as git_source:
                git_utils.clone_or_update_repo(git_source)
                cache_dir = git_source.cache_dir.resolve()
                if git_source.subpath == Path("/dev/null"):
                    project_path = cs_utils.find_nested_project_file(cache_dir)
                    if project_path is None:
                        raise errors.InvalidSourceError(cache_dir)
                else:
                    project_path = (cache_dir / git_source.subpath).resolve()

                try:
                    project_path.relative_to(cache_dir)
                except ValueError as exc:
                    raise errors.InvalidSourceError(project_path) from exc

                if project_path.is_dir():
                    project_path = cs_utils.find_project_file(project_path)
                    if project_path is None:
                        raise errors.InvalidSourceError(cache_dir / git_source.subpath)
                if not project_path.is_file() or project_path.suffix.lower() != ".csproj":
                    raise errors.InvalidSourceError(project_path)

                return replace(git_source, subpath=project_path.relative_to(cache_dir))

            case aps.GitHubReleaseAppSource() as release_source:
                git_utils.download_artifact(working_dir, release_source, runtime, token)
                return release_source

            case _:
                return app_source

    @staticmethod
    def _project_path(app_source: aps.AppSource) -> Path | None:
        match app_source:
            case aps.CodeAppSource() as code_source:
                return code_source.project_path
            case aps.GitCodeAppSource() as git_source:
                return git_source.project_path
            case _:
                return None

    @staticmethod
    def _source_directory(app_source: aps.AppSource) -> Path | None:
        match app_source:
            case aps.CodeAppSource() as code_source:
                return code_source.project_path.parent
            case aps.GitCodeAppSource() as git_source:
                return git_source.project_path.parent
            case aps.BuiltAppSource() as built_source:
                return built_source.build_path
            case _:
                return None

    @staticmethod
    def _build(app_source: aps.AppSource, build_options: BuildOptions, working_dir: Path) -> Path:
        match app_source:
            case aps.CodeAppSource() as code_source:
                output_dir = working_dir / "dist"
                output_dir.mkdir(parents=True, exist_ok=True)
                cs_utils.publish(code_source.project_path, output_dir, build_options)
                return output_dir

            case aps.GitCodeAppSource() as git_source:
                output_dir = working_dir / "dist"
                output_dir.mkdir(parents=True, exist_ok=True)
                cs_utils.publish(
                    git_source.cache_dir / git_source.subpath, output_dir, build_options
                )
                return output_dir

            case aps.BuiltAppSource() as built_source:
                return built_source.build_path

            case aps.GitHubReleaseAppSource():
                return working_dir / "dist"

            case _:
                raise errors.InvalidSourceError(str(app_source))
