"""Version utilities"""

import logging
from pathlib import Path
import re

import semver

from net_install_manager.utilities import sh

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


def get_version_from_binary(executable_path: Path) -> semver.Version | None:
    """Run an executable or DLL with --version and parse the output."""
    if not executable_path.exists():
        return None

    try:
        if executable_path.suffix.lower() == ".dll":
            cmd = ["dotnet", str(executable_path), "--version"]
        else:
            cmd = [str(executable_path), "--version"]

        output = sh.exec_command_output(cmd, cwd=str(executable_path.parent))
        return parse_semver(output.strip())
    except Exception as e:  # pylint: disable=broad-except
        logger.debug("Could not get version from binary '%s': %s", executable_path, e)
        return None


def get_version_from_git(
    repo_path: Path | None = None, branch: str = "HEAD"
) -> semver.Version | None:
    """Get the version from the latest git tag."""

    cmd = ["git", "tag", "--merged", branch]
    try:
        cwd = str(repo_path) if repo_path else None
        output = sh.exec_command_output(cmd, cwd=cwd)
        tags = output.strip().splitlines()
        versions: list[semver.Version] = []
        for tag in tags:
            ver = parse_semver(tag)
            if ver is not None:
                versions.append(ver)
        return max(versions) if versions else None

    except Exception as e:  # pylint: disable=broad-except
        logger.debug("Could not determine git repository path: %s", e)
        return None
