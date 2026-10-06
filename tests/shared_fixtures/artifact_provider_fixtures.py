from pathlib import Path
from typing import Any

from net_install_manager.config import app_sources as aps
from net_install_manager.config.build_options import BuildOptions
from net_install_manager.core.artifact_provider import ArtifactProvider, PreparedArtifact
from net_install_manager.runtime.runtime import Runtime


def get_test_artifact_provider(
    directory: Path,
    project_path: Path | None,
    calls: dict[str, Any] | None = None,
) -> ArtifactProvider:
    real_calls = calls if calls is not None else {}

    class TestArtifactProvider:
        def prepare_and_build(
            self,
            app_source: aps.AppSource,
            build_options: BuildOptions,
            runtime: Runtime,
            working_dir: Path,
            token: str | None = None,
        ) -> PreparedArtifact:
            real_calls["prepare_and_build"] = (
                app_source,
                build_options,
                runtime,
                working_dir,
                token,
            )
            return PreparedArtifact(app_source, directory, project_path)

    return TestArtifactProvider()
