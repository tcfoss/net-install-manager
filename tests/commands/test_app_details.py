import argparse
from dataclasses import replace
from pathlib import Path

import pytest
import semver

from net_install_manager.commands.app_details import AppDetailsCommand
from net_install_manager.config.app_info import AppInfo
from net_install_manager.config.app_sources import (
    BuiltAppSource,
    CodeAppSource,
    GitCodeAppSource,
    GitHubReleaseAppSource,
)
from net_install_manager.config.build_options import BuildOptions
from net_install_manager.core import errors
from net_install_manager.core.registry import Registry
from net_install_manager.runtime.runtime import Runtime


def _runtime(tmp_path: Path) -> Runtime:
    return replace(
        Runtime.current(),
        home_dir=tmp_path,
        registry_path=tmp_path / "config" / "apps.yaml",
    )


@pytest.mark.parametrize(
    ("source_kind", "expected_details"),
    [
        (
            "local-code",
            [
                "Source type: Local Code",
                "Path:          /source/Sample.csproj",
                "Debug mode:     True",
            ],
        ),
        (
            "built",
            ["Source type: Built Artifact", "Path:          /artifacts/sample"],
        ),
        (
            "git-code",
            [
                "Source type: Git Code",
                "Clone URL:    https://example.com/sample.git",
                "Ref:         main",
                "Subpath:     src/Sample.csproj",
                "Cache dir:   /cache/sample",
                "Self-contained: True",
            ],
        ),
        (
            "github-release",
            [
                "Source type: GitHub Release",
                "Owner:         example",
                "Repo:          sample",
                "Tag:           v1.2.3",
                "Asset pattern: linux-x64",
            ],
        ),
    ],
)
def test_app_details_prints_common_and_source_specific_fields(
    tmp_path, capsys, source_kind, expected_details
):
    runtime = _runtime(tmp_path)
    build_options = BuildOptions(
        debug_mode=True,
        self_contained=True,
        runtime_identifier="linux-x64",
    )
    sources = {
        "local-code": CodeAppSource(Path("/source/Sample.csproj"), build_options),
        "built": BuiltAppSource(Path("/artifacts/sample")),
        "git-code": GitCodeAppSource(
            "https://example.com/sample.git",
            "main",
            Path("src/Sample.csproj"),
            build_options,
            Path("/cache/sample"),
        ),
        "github-release": GitHubReleaseAppSource("example", "sample", "linux-x64", "v1.2.3"),
    }
    app = AppInfo(
        binary_name="sample",
        source_binary_name="Sample",
        lib_dir=tmp_path / ".local" / "lib" / "Sample",
        installed_version=semver.Version(1, 2, 3),
        app_source=sources[source_kind],
    )
    Registry(runtime).set(app.binary_name, app)

    AppDetailsCommand().execute(
        runtime, AppDetailsCommand.parse_arguments(runtime, argparse.Namespace(app_name="sample"))
    )

    output = capsys.readouterr().out
    assert "Details for application 'sample':" in output
    assert f"Lib path:      {app.lib_dir}" in output
    assert "Version:       1.2.3" in output
    assert "Binary:        sample" in output
    assert "Source binary: Sample" in output
    for detail in expected_details:
        assert detail in output


def test_app_details_raises_for_unregistered_application(tmp_path):
    runtime = _runtime(tmp_path)

    with pytest.raises(errors.AppNotRegisteredError):
        AppDetailsCommand().execute(
            runtime,
            AppDetailsCommand.parse_arguments(runtime, argparse.Namespace(app_name="missing")),
        )


def test_app_details_command_parses_application_name():
    parser = argparse.ArgumentParser()
    AppDetailsCommand.register_command(parser.add_subparsers())
    namespace = parser.parse_args(["app-details", "sample"])

    assert AppDetailsCommand.parse_arguments(Runtime.current(), namespace).app_name == "sample"
