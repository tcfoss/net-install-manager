"""Tools for extracting information from .csproj files and building/publishing them."""

from dataclasses import dataclass
from pathlib import Path
import xml.etree.ElementTree as ET
import semver

from net_install_manager.utilities.sh import exec_command


@dataclass
class BuildOpts:
    """Build options for dotnet build/publish."""

    release: bool = True
    self_contained: bool = False
    runtime_identifier: str | None = None

    def to_args(self) -> list[str]:
        """Convert the build options to a list of command-line args for dotnet build/publish."""
        args = []
        if self.release:
            args.extend(["--configuration", "Release"])
        else:
            args.extend(["--configuration", "Debug"])

        if self.self_contained:
            args.extend(["--self-contained", "true"])
            if self.runtime_identifier:
                args.extend(["-r", self.runtime_identifier])
        else:
            args.extend(["--self-contained", "false"])

        return args


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


def get_target_framework_from_csproj(csproj_path: Path) -> str | None:
    """Get the TargetFramework property from a .csproj file."""
    return get_property_from_csproj(csproj_path, "TargetFramework")


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


def build(csproj_path: Path, opts: BuildOpts | None = None, quiet: bool = False) -> None:
    """Build the .csproj file using dotnet build."""
    cmd = ["dotnet", "build", str(csproj_path)]

    opts = opts or BuildOpts()
    cmd.extend(opts.to_args())

    exec_command(cmd, quiet=quiet)


def publish(
    csproj_path: Path,
    output_dir: Path,
    opts: BuildOpts | None = None,
    quiet: bool = False,
) -> None:
    """Publish the .csproj file using dotnet publish."""
    cmd = ["dotnet", "publish", str(csproj_path), "-o", str(output_dir)]

    opts = opts or BuildOpts()
    cmd.extend(opts.to_args())

    exec_command(cmd, quiet=quiet)


__all__ = [
    "get_property_from_csproj",
    "get_target_framework_from_csproj",
    "get_version_from_csproj",
    "get_assembly_name_from_csproj",
    "build",
    "publish",
    "BuildOpts",
]
