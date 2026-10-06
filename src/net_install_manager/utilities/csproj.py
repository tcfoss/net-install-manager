"""Utilities for working with C# projects."""

from pathlib import Path
import xml.etree.ElementTree as ET

import semver

from net_install_manager.core import errors
from net_install_manager.utilities.sh import exec_command
from net_install_manager.config.build_options import BuildOptions


def get_property_from_csproj(csproj_path: Path, property_name: str) -> str | None:
    """Get the value of a property from a .csproj file."""
    if not csproj_path.exists():
        raise FileNotFoundError(f".csproj file not found at {csproj_path}")

    tree = ET.parse(csproj_path)
    root = tree.getroot()
    for property_group in root.findall("PropertyGroup"):
        prop = property_group.find(property_name)
        if prop is not None and prop.text:
            return prop.text.strip()
    return None


def get_version_from_csproj(csproj_path: Path) -> semver.Version | None:
    """Get Version or PackageVersion from a .csproj file."""
    for prop_name in ("Version", "PackageVersion", "AssemblyVersion"):
        val = get_property_from_csproj(csproj_path, prop_name)
        if val:
            try:
                return semver.Version.parse(val)
            except ValueError:
                continue
    return None


def get_assembly_name_from_csproj(csproj_path: Path) -> str:
    """Get AssemblyName, PackageId, or fallback to project file stem."""
    name = get_property_from_csproj(csproj_path, "AssemblyName")
    if name:
        return name
    pkg_id = get_property_from_csproj(csproj_path, "PackageId")
    if pkg_id:
        return pkg_id
    return csproj_path.stem


def find_project_file(search_path: Path) -> Path | None:
    """Return the sole project file at a path, or none when no project is present."""

    if search_path.is_file() and search_path.suffix.lower() == ".csproj":
        return search_path
    if not search_path.is_dir():
        raise errors.InvalidSourceError(search_path)

    project_files = [
        item
        for item in search_path.iterdir()
        if item.is_file() and item.suffix.lower() == ".csproj"
    ]
    if len(project_files) > 1:
        raise errors.MultipleCsprojFilesError(search_path, project_files)
    return project_files[0] if project_files else None


def publish(
    csproj_path: Path,
    output_dir: Path,
    opts: BuildOptions | None = None,
) -> None:
    """Publish the .csproj file using dotnet publish."""
    cmd = ["dotnet", "publish", str(csproj_path), "-o", str(output_dir)]

    opts = opts or BuildOptions()
    cmd.extend(opts.to_cmd_args())

    exec_command(cmd)
