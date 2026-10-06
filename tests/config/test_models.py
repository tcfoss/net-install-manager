from pathlib import Path

import pytest
import semver

from net_install_manager.config.app_info import AppInfo
from net_install_manager.config.app_sources import (
    BuiltAppSource,
    CodeAppSource,
    GitCodeAppSource,
    GitHubReleaseAppSource,
    parse_app_source,
)
from net_install_manager.config.build_options import BuildOptions
from net_install_manager.config.ninman_manifest import NinmanManifest


@pytest.mark.parametrize(
    ("options", "expected"),
    [
        (BuildOptions(), ["--configuration", "Release", "--self-contained", "false"]),
        (
            BuildOptions(debug_mode=True, self_contained=True, runtime_identifier="linux-x64"),
            [
                "--configuration",
                "Debug",
                "--self-contained",
                "true",
                "-r",
                "linux-x64",
            ],
        ),
        (
            BuildOptions(self_contained=True),
            ["--configuration", "Release", "--self-contained", "true"],
        ),
    ],
)
def test_build_options_command_arguments(options, expected):
    assert options.to_cmd_args() == expected


def test_build_options_serialization_round_trip():
    options = BuildOptions(True, True, "osx-arm64")

    assert BuildOptions.parse(options.to_dict()) == options
    assert BuildOptions.parse({}) == BuildOptions()


@pytest.mark.parametrize(
    "source",
    [
        CodeAppSource(Path("/src/App.csproj"), BuildOptions(debug_mode=True)),
        BuiltAppSource(Path("/dist")),
        GitCodeAppSource(
            "https://github.com/example/app.git",
            "v1.2.0",
            Path("src/App.csproj"),
            BuildOptions(self_contained=True),
            Path("/cache/app"),
        ),
        GitHubReleaseAppSource("example", "app", "linux-{version}", "v1.2.0"),
    ],
)
def test_app_source_serialization_round_trip(source):
    data = source.to_dict()

    assert data["kind"] == source.kind.value
    assert parse_app_source(data) == source


def test_app_source_parser_rejects_unknown_kind():
    with pytest.raises(ValueError):
        parse_app_source({"kind": "unknown"})


def test_app_info_serialization_round_trip():
    app = AppInfo(
        binary_name="sample",
        source_binary_name="Sample.dll",
        lib_dir=Path("/opt/lib/Sample"),
        installed_version=semver.Version(1, 2, 3),
        app_source=BuiltAppSource(Path("/build")),
        exclude_patterns=["*.pdb"],
        target_permissions="755",
    )

    assert AppInfo.parse(app.to_dict()) == app


def test_manifest_normalizes_keys_and_parses_project_path():
    manifest = NinmanManifest.parse(
        {
            "Binary-Name": "sample",
            "Source_Binary_Name": "Sample.dll",
            "app dir name": "Sample",
            "proj-path": "src/Sample.csproj",
        }
    )

    assert manifest == NinmanManifest("sample", "Sample.dll", "Sample", Path("src/Sample.csproj"))


def test_manifest_loads_yaml(tmp_path):
    path = tmp_path / "ninman.yaml"
    path.write_text("binary_name: sample\napp_dir_name: Sample\n", encoding="utf-8")

    assert NinmanManifest.load(path) == NinmanManifest("sample", None, "Sample")


@pytest.mark.parametrize("contents", ["", "[]", "null"])
def test_manifest_load_requires_yaml_mapping(tmp_path, contents):
    path = tmp_path / "ninman.yml"
    path.write_text(contents, encoding="utf-8")

    with pytest.raises(ValueError, match="must contain a YAML mapping"):
        NinmanManifest.load(path)


def test_manifest_load_propagates_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError):
        NinmanManifest.load(tmp_path / "missing.yml")
