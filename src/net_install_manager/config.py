"""Configuration for running the net install manager.

The expected structure of the configuration YAML file is:

app_directory: str  # The directory where the application is to be installed
binary_name: str  # The name by which the application will be invoked
source_binary_name: str  # The name of the original source binary
csproj_path: str  # Optional path to the project's .csproj file
target_permissions: str  # Optional POSIX permissions string
"""

from dataclasses import dataclass
from pathlib import Path
import yaml

from net_install_manager.utilities.csproj_tools import get_assembly_name_from_csproj
from net_install_manager.utilities.install_tools import find_csproj_files


@dataclass(frozen=True)
class Config:
    """Configuration for the net install manager."""

    app_directory: str
    binary_name: str
    source_binary_name: str
    csproj_path: Path | None = None
    target_permissions: str | None = None


def _parse_target_permissions(value: object) -> str | None:
    """Normalize YAML permission digits to a string interpreted as octal."""
    if value is None:
        return None
    if isinstance(value, bool):
        raise ValueError("target_permissions must be an octal permission value")

    permission_text = str(value)
    try:
        mode = int(permission_text, 8)
    except ValueError as error:
        raise ValueError(
            f"Invalid target_permissions value '{value}'; expected octal digits"
        ) from error
    return f"{mode:04o}"


def parse_config(content: str) -> Config:
    """Parse a configuration from a YAML string."""
    data = yaml.safe_load(content)
    if not isinstance(data, dict):
        raise ValueError("Invalid configuration: root must be a mapping.")

    csproj_path = (
        Path(data["csproj_path"]) if "csproj_path" in data and data["csproj_path"] else None
    )

    return Config(
        app_directory=data["app_directory"],
        binary_name=data["binary_name"],
        source_binary_name=data["source_binary_name"],
        csproj_path=csproj_path,
        target_permissions=_parse_target_permissions(data.get("target_permissions")),
    )


def load_config(path: Path) -> Config:
    """Load a configuration from a YAML file."""
    with path.open("r", encoding="utf-8") as f:
        return parse_config(f.read())


def _config_from_csproj(csproj_path: Path) -> Config:
    """Construct a Config object from a .csproj file."""
    assembly_name = get_assembly_name_from_csproj(csproj_path)
    bin_name = csproj_path.stem.lower().replace(".", "-")
    app_dir = assembly_name.lower().replace(".", "-")
    return Config(
        app_directory=app_dir,
        binary_name=bin_name,
        source_binary_name=f"{assembly_name}.dll",
        csproj_path=csproj_path,
    )


def auto_discover_config(start_dir: Path | None = None) -> Config | None:
    """Attempt to discover configuration from files in the directory or from a .csproj file.

    Checks for ninman.yaml, ninman.yml, or any .csproj in start_dir.
    """
    root = start_dir or Path.cwd()

    if root.is_file():
        if root.suffix.lower() == ".csproj":
            return _config_from_csproj(root)

        if root.name in ("ninman.yaml", "ninman.yml"):
            return load_config(root)

        return None

    # 1. Look for config file
    for config_filename in ("ninman.yaml", "ninman.yml"):
        candidate = root / config_filename
        if candidate.is_file():
            return load_config(candidate)

    # 2. Look for .csproj files in start_dir and immediate child directories
    csproj_files = find_csproj_files(root, include_common_subdirs=True)

    if len(csproj_files) > 1:
        found_paths = ", ".join(f"'{p}'" for p in csproj_files)
        raise ValueError(
            f"Multiple .csproj files found ({found_paths}). "
            "Please specify a configuration file via --config or specify the target project path."
        )

    if len(csproj_files) == 1:
        return _config_from_csproj(csproj_files[0])

    return None


__all__ = ["Config", "parse_config", "load_config", "auto_discover_config"]
