"""Tests for the configuration parsing and auto-discovery functionality."""

from unittest.mock import patch
import pytest
from net_install_manager.config import Config, parse_config, load_config, auto_discover_config
from net_install_manager.net_install_manager import load_app_config


def test_parse_config_valid():
    """Test parsing a valid configuration."""
    yaml_content = """
    app_directory: my_app
    binary_name: my_binary
    source_binary_name: MyApp.dll
    """
    config = parse_config(yaml_content)
    assert config.app_directory == "my_app"
    assert config.binary_name == "my_binary"
    assert config.source_binary_name == "MyApp.dll"
    assert isinstance(config, Config)


def test_parse_config_normalizes_unquoted_octal_permissions():
    """Treat an unquoted YAML permission value such as 755 as octal digits."""
    config = parse_config("""
        app_directory: my_app
        binary_name: my_binary
        source_binary_name: MyApp.dll
        target_permissions: 755
        """)

    assert config.target_permissions == "0755"


def test_parse_config_missing_binary_name():
    """Test parsing a configuration missing the binary_name key."""
    yaml_content = """
    app_directory: my_app
    source_binary_name: MyApp.dll
    """
    with pytest.raises(KeyError):
        parse_config(yaml_content)


def test_parse_config_missing_app_directory():
    """Test parsing a configuration missing the app_directory key."""
    yaml_content = """
    binary_name: my_binary
    source_binary_name: MyApp.dll
    """
    with pytest.raises(KeyError):
        parse_config(yaml_content)


def test_parse_config_missing_source_binary_name():
    """Test parsing a configuration missing the source_binary_name key."""
    yaml_content = """
    app_directory: my_app
    binary_name: my_binary
    """
    with pytest.raises(KeyError):
        parse_config(yaml_content)


def test_parse_config_invalid_root_not_dict():
    """Test that parsing a non-dict YAML root raises ValueError."""
    with pytest.raises(ValueError, match="root must be a mapping"):
        parse_config("- list item")


def test_load_config_file(tmp_path):
    """Test loading a configuration from a file."""
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        "app_directory: test_app\nbinary_name: test_bin\nsource_binary_name: MyApp.dll\n",
        encoding="utf-8",
    )

    config = load_config(config_file)
    assert config.app_directory == "test_app"
    assert config.binary_name == "test_bin"
    assert config.source_binary_name == "MyApp.dll"


def test_auto_discover_config_from_yaml(tmp_path):
    """Test auto-discovering a configuration from a YAML file."""
    config_file = tmp_path / "ninman.yaml"
    config_file.write_text(
        "app_directory: test_app\nbinary_name: test_bin\nsource_binary_name: MyApp.dll\n",
        encoding="utf-8",
    )
    discovered = auto_discover_config(tmp_path)
    assert discovered is not None
    assert discovered.app_directory == "test_app"


def test_auto_discover_config_from_yml_extension(tmp_path):
    """Test auto-discovering a configuration from a .yml extension file."""
    config_file = tmp_path / "ninman.yml"
    config_file.write_text(
        "app_directory: test_app\nbinary_name: test_bin\nsource_binary_name: MyApp.dll\n",
        encoding="utf-8",
    )
    discovered = auto_discover_config(tmp_path)
    assert discovered is not None
    assert discovered.app_directory == "test_app"


def test_auto_discover_config_file_direct_csproj(tmp_path):
    """Test auto-discovering when start_dir is a direct path to a .csproj file."""
    csproj = tmp_path / "DirectProj.csproj"
    csproj.write_text(
        "<Project><PropertyGroup><AssemblyName>DirectProj</AssemblyName></PropertyGroup></Project>",
        encoding="utf-8",
    )
    discovered = auto_discover_config(csproj)
    assert discovered is not None
    assert discovered.binary_name == "directproj"
    assert discovered.csproj_path == csproj


def test_auto_discover_config_file_direct_yaml(tmp_path):
    """Test auto-discovering when start_dir is a direct path to ninman.yaml or ninman.yml."""
    yaml_file = tmp_path / "ninman.yaml"
    yaml_file.write_text(
        "app_directory: direct_app\nbinary_name: direct_bin\nsource_binary_name: Direct.dll\n",
        encoding="utf-8",
    )
    discovered = auto_discover_config(yaml_file)
    assert discovered is not None
    assert discovered.app_directory == "direct_app"


def test_auto_discover_config_file_unrelated(tmp_path):
    """Test auto-discovering when start_dir points to an unrelated file."""
    other_file = tmp_path / "README.md"
    other_file.write_text("# Documentation", encoding="utf-8")
    assert auto_discover_config(other_file) is None


def test_auto_discover_config_single_csproj(tmp_path):
    """Test auto-discovering a configuration from a single .csproj file."""
    csproj = tmp_path / "MyProject.csproj"
    csproj.write_text(
        "<Project><PropertyGroup><AssemblyName>MyProject</AssemblyName></PropertyGroup></Project>",
        encoding="utf-8",
    )
    discovered = auto_discover_config(tmp_path)
    assert discovered is not None
    assert discovered.binary_name == "myproject"
    assert discovered.source_binary_name == "MyProject.dll"
    assert discovered.csproj_path == csproj


def test_auto_discover_config_csproj_in_src_subdir(tmp_path):
    """Test discovering .csproj when located in src/<AppName>/<AppName>.csproj."""
    src_dir = tmp_path / "src" / "NestedApp"
    src_dir.mkdir(parents=True)
    csproj = src_dir / "NestedApp.csproj"
    csproj.write_text(
        "<Project><PropertyGroup><AssemblyName>NestedApp</AssemblyName></PropertyGroup></Project>",
        encoding="utf-8",
    )
    discovered = auto_discover_config(tmp_path)
    assert discovered is not None
    assert discovered.binary_name == "nestedapp"
    assert discovered.csproj_path == csproj


def test_auto_discover_config_csproj_in_direct_subdir(tmp_path):
    """Test discovering .csproj when located in <SubDir>/<SubDir>.csproj."""
    sub_dir = tmp_path / "MyModule"
    sub_dir.mkdir()
    csproj = sub_dir / "MyModule.csproj"
    csproj.write_text(
        "<Project><PropertyGroup><AssemblyName>MyModule</AssemblyName></PropertyGroup></Project>",
        encoding="utf-8",
    )
    discovered = auto_discover_config(tmp_path)
    assert discovered is not None
    assert discovered.binary_name == "mymodule"
    assert discovered.csproj_path == csproj


def test_auto_discover_config_multiple_csproj_raises(tmp_path):
    """Test that auto-discovering a configuration raises an error on multiple .csproj files."""
    (tmp_path / "App1.csproj").write_text("<Project></Project>", encoding="utf-8")
    (tmp_path / "App2.csproj").write_text("<Project></Project>", encoding="utf-8")
    with pytest.raises(ValueError, match="Multiple .csproj files found"):
        auto_discover_config(tmp_path)


def test_auto_discover_config_default_cwd(tmp_path, monkeypatch):
    """Test auto-discovering config without start_dir defaults to current working directory."""
    monkeypatch.chdir(tmp_path)
    config_file = tmp_path / "ninman.yaml"
    config_file.write_text(
        "app_directory: cwd_app\nbinary_name: cwd_bin\nsource_binary_name: Cwd.dll\n",
        encoding="utf-8",
    )
    discovered = auto_discover_config()
    assert discovered is not None
    assert discovered.app_directory == "cwd_app"


def test_auto_discover_config_none(tmp_path):
    """Test that auto-discovering a configuration returns None when no configuration is found."""
    assert auto_discover_config(tmp_path) is None


def test_load_app_config_discovers_git_project_subpath(tmp_path):
    """Test that Git source discovery descends into the requested project subpath."""
    repo_dir = tmp_path / "repo"
    project_dir = repo_dir / "src" / "MyApp"
    project_dir.mkdir(parents=True)
    (project_dir / "MyApp.csproj").write_text(
        "<Project><PropertyGroup><AssemblyName>MyApp</AssemblyName></PropertyGroup></Project>",
        encoding="utf-8",
    )

    with patch(
        "net_install_manager.net_install_manager.clone_or_update_repo",
        return_value=repo_dir,
    ):
        config = load_app_config(
            config_arg=None,
            source_arg="https://github.com/example/app.git",
            project_arg="src/MyApp",
        )

    assert config is not None
    assert config.csproj_path == project_dir / "MyApp.csproj"
