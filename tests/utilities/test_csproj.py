import pytest

from net_install_manager.config.build_options import BuildOptions
from net_install_manager.core import errors
from net_install_manager.utilities import csproj


def test_get_property_from_csproj_reads_property_group(tmp_path):
    project = tmp_path / "Sample.csproj"
    project.write_text(
        "<Project><PropertyGroup><AssemblyName>  Sample.App  </AssemblyName>"
        "</PropertyGroup></Project>",
        encoding="utf-8",
    )

    assert csproj.get_property_from_csproj(project, "AssemblyName") == "Sample.App"
    assert csproj.get_property_from_csproj(project, "Version") is None


def test_get_property_from_csproj_raises_for_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError, match=".csproj file not found"):
        csproj.get_property_from_csproj(tmp_path / "missing.csproj", "Version")


def test_get_version_from_csproj_uses_first_valid_version_property(tmp_path):
    project = tmp_path / "Sample.csproj"
    project.write_text(
        "<Project><PropertyGroup><Version>invalid</Version><PackageVersion>2.3.4</PackageVersion>"
        "<AssemblyVersion>3.0.0</AssemblyVersion></PropertyGroup></Project>",
        encoding="utf-8",
    )

    assert str(csproj.get_version_from_csproj(project)) == "2.3.4"


def test_get_version_from_csproj_returns_none_for_no_valid_version(tmp_path):
    project = tmp_path / "Sample.csproj"
    project.write_text(
        "<Project><PropertyGroup><Version>invalid</Version><PackageVersion>also.invalid</PackageVersion>"
        "<AssemblyVersion>still.invalid</AssemblyVersion></PropertyGroup></Project>",
        encoding="utf-8",
    )

    assert csproj.get_version_from_csproj(project) is None


def test_find_project_file_csproj_path_given(tmp_path):
    project = tmp_path / "Sample.csproj"
    project.write_text("<Project></Project>", encoding="utf-8")

    found = csproj.find_project_file(project)
    assert found == project


def test_find_project_file_single_csproj_in_directory(tmp_path):
    project = tmp_path / "Sample.csproj"
    project.write_text("<Project></Project>", encoding="utf-8")

    found = csproj.find_project_file(tmp_path)
    assert found == project


def test_find_project_file_given_path_not_csproj_throws(tmp_path):
    somefile = tmp_path / "not_a_csproj.txt"
    somefile.write_text("content", encoding="utf-8")

    with pytest.raises(errors.InvalidSourceError, match="Must be a .csproj file"):
        csproj.find_project_file(somefile)


def test_find_project_file_no_csproj_in_directory_returns_none(tmp_path):
    somefile = tmp_path / "not_a_csproj.txt"
    somefile.write_text("content", encoding="utf-8")

    found = csproj.find_project_file(tmp_path)
    assert found is None


def test_find_project_file_multiple_csproj_in_directory_throws(tmp_path):
    project1 = tmp_path / "Sample1.csproj"
    project1.write_text("<Project></Project>", encoding="utf-8")
    project2 = tmp_path / "Sample2.csproj"
    project2.write_text("<Project></Project>", encoding="utf-8")

    with pytest.raises(
        errors.MultipleCsprojFilesError, match="Multiple .csproj files found in directory"
    ):
        csproj.find_project_file(tmp_path)


def test_find_nested_project_file_finds_single_nested_project(tmp_path):
    project = tmp_path / "src" / "Sample" / "Sample.csproj"
    project.parent.mkdir(parents=True)
    project.write_text("<Project></Project>", encoding="utf-8")

    assert csproj.find_nested_project_file(tmp_path) == project


def test_find_nested_project_file_prefers_non_test_project(tmp_path):
    app_project = tmp_path / "src" / "App" / "App.csproj"
    test_project = tmp_path / "tests" / "App.Tests" / "App.Tests.csproj"
    app_project.parent.mkdir(parents=True)
    test_project.parent.mkdir(parents=True)
    app_project.write_text("<Project></Project>", encoding="utf-8")
    test_project.write_text("<Project></Project>", encoding="utf-8")

    assert csproj.find_nested_project_file(tmp_path) == app_project


def test_find_nested_project_file_raises_for_multiple_non_test_projects(tmp_path):
    project_one = tmp_path / "src" / "One" / "One.csproj"
    project_two = tmp_path / "src" / "Two" / "Two.csproj"
    project_one.parent.mkdir(parents=True)
    project_two.parent.mkdir(parents=True)
    project_one.write_text("<Project></Project>", encoding="utf-8")
    project_two.write_text("<Project></Project>", encoding="utf-8")

    with pytest.raises(errors.MultipleCsprojFilesError) as exc_info:
        csproj.find_nested_project_file(tmp_path)

    assert set(exc_info.value.csproj_files) == {project_one, project_two}


@pytest.mark.parametrize(
    ("xml", "expected"),
    [
        (
            "<Project><PropertyGroup><AssemblyName>Explicit</AssemblyName></PropertyGroup></Project>",
            "Explicit",
        ),
        (
            "<Project><PropertyGroup><PackageId>Package.Id</PackageId></PropertyGroup></Project>",
            "Package.Id",
        ),
        ("<Project />", "Sample"),
    ],
)
def test_get_assembly_name_from_csproj_fallback_order(tmp_path, xml, expected):
    project = tmp_path / "Sample.csproj"
    project.write_text(xml, encoding="utf-8")

    assert csproj.get_assembly_name_from_csproj(project) == expected


def test_publish_constructs_dotnet_publish_command(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(csproj, "exec_command", calls.append)

    csproj.publish(
        tmp_path / "Sample.csproj",
        tmp_path / "output",
        BuildOptions(debug_mode=True, self_contained=True, runtime_identifier="linux-x64"),
    )

    assert calls == [
        [
            "dotnet",
            "publish",
            str(tmp_path / "Sample.csproj"),
            "-o",
            str(tmp_path / "output"),
            "--configuration",
            "Debug",
            "--self-contained",
            "true",
            "-r",
            "linux-x64",
        ]
    ]
