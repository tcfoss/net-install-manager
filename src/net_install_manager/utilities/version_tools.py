"""Utilities for resolving application and release versions."""

import logging
from pathlib import Path
import re
import semver

from net_install_manager.utilities.sh import exec_command_output
from net_install_manager.utilities.csproj_tools import get_version_from_csproj

logger = logging.getLogger(__name__)

VPAT = re.compile(
    r"(?<![\d.])"
    r"\d+\.\d+\.\d+"
    r"(?:-[0-9A-Za-z.-]*[0-9A-Za-z])?"
    r"(?:\+[0-9A-Za-z.-]*[0-9A-Za-z])?(?!\.\d)"
)


def parse_semver(version_str: str) -> semver.Version | None:
    """Safely parse a semver version, stripping leading 'v' or 'V' if present."""
    if not version_str:
        return None
    clean_str = version_str.strip()
    if clean_str.startswith(("v", "V")):
        clean_str = clean_str[1:]
    try:
        return semver.Version.parse(clean_str)
    except ValueError:
        # Try finding semver pattern within the string
        match = VPAT.search(clean_str)
        if match:
            try:
                return semver.Version.parse(match.group(0))
            except ValueError:
                return None
        return None


def get_version_from_git(
    repo_dir: Path | None = None, branch: str = "HEAD"
) -> semver.Version | None:
    """Get the latest git tag semver version reachable from the current branch or HEAD."""
    cmd = ["git", "tag", "--merged", branch]
    try:
        cwd = str(repo_dir) if repo_dir else None
        output = exec_command_output(cmd, cwd=cwd)
        tags = output.splitlines()
        versions: list[semver.Version] = []
        for tag in tags:
            v = parse_semver(tag)
            if v is not None:
                versions.append(v)
        return max(versions) if versions else None
    except Exception as e:  # pylint: disable=broad-except
        logger.debug("Could not get version from git: %s", e)
        return None


def get_version_from_binary(executable_path: Path) -> semver.Version | None:
    """Run an executable or DLL with --version and parse the output."""
    if not executable_path.exists():
        return None

    try:
        if executable_path.suffix.lower() == ".dll":
            cmd = ["dotnet", str(executable_path), "--version"]
        else:
            cmd = [str(executable_path), "--version"]

        output = exec_command_output(cmd, cwd=str(executable_path.parent))
        return parse_semver(output.strip())
    except Exception as e:  # pylint: disable=broad-except
        logger.debug("Could not get version from binary '%s': %s", executable_path, e)
        return None


def resolve_version(
    explicit_version: str | None = None,
    csproj_path: Path | None = None,
    binary_path: Path | None = None,
    source_dir: Path | None = None,
) -> semver.Version:
    """Resolve the version using precedence: explicit > csproj > binary > git."""
    if explicit_version:
        v = parse_semver(explicit_version)
        if v is not None:
            return v
        raise ValueError(f"Invalid semver version string: '{explicit_version}'")

    if csproj_path and csproj_path.exists():
        v = get_version_from_csproj(csproj_path)
        if v is not None:
            return v

    if binary_path and binary_path.exists():
        v = get_version_from_binary(binary_path)
        if v is not None:
            return v

    # Fallback to git tags if in a git repository
    v = get_version_from_git(repo_dir=source_dir or (csproj_path.parent if csproj_path else None))
    if v is not None:
        return v

    raise ValueError(
        "Could not automatically determine application version. Please specify --app-version."
    )


__all__ = [
    "parse_semver",
    "get_version_from_git",
    "get_version_from_binary",
    "resolve_version",
]
