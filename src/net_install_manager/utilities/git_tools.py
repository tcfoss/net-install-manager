"""Git and VCS repository tools for cloning, caching, and URL parsing."""

from dataclasses import dataclass
import hashlib
import logging
import os
from pathlib import Path
import re

from net_install_manager.runtime_config import RuntimeInfo
from net_install_manager.utilities.sh import exec_command
from net_install_manager.utilities.sys_platform import get_winpath

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class GitSourceInfo:
    """Parsed git source information.

    Attributes:
        clone_url (str): The URL to clone the repository from.
        ref (str | None): The specific branch, tag, or commit to check out.
        subpath (str | None): The subpath within the repository to use (should be a
            path to a .csproj file).
    """

    clone_url: str
    ref: str | None = None
    subpath: str | None = None


def is_git_url(source: str) -> bool:
    """Check whether a given source string is a Git/GitHub URL or shorthand."""
    if not source or not isinstance(source, str):
        return False

    source = source.strip()

    # Local paths that exist or look like local paths are not Git URLs
    if (
        os.path.exists(source)
        or source.startswith((".", "/", "\\"))
        or (len(source) > 2 and source[1] == ":")
    ):
        return False

    if source.startswith(("git@", "git://", "ssh://", "http://", "https://")):
        return True

    if source.startswith(("github.com/", "gitlab.com/", "bitbucket.org/")):
        return True

    # Check for github shorthand e.g. "owner/repo" or "owner/repo@v1.0"
    shorthand_pattern = (
        r"^[a-zA-Z0-9_-]+/[a-zA-Z0-9_.-]+(?:@[a-zA-Z0-9_./-]+)?(?:#[a-zA-Z0-9_./-]+)?$"
    )
    if re.match(shorthand_pattern, source):
        return True

    return False


def parse_git_source(source: str, project_override: str | None = None) -> GitSourceInfo:
    """Parse a Git source string into clone URL, ref, and subpath.

    Supported formats:
    - https://github.com/owner/repo.git
    - https://github.com/owner/repo.git@v1.0.0
    - https://github.com/owner/repo.git#src/MyApp
    - https://github.com/owner/repo.git@v1.0.0#src/MyApp
    - https://github.com/owner/repo/tree/branch-name/path/to/project
    - owner/repo
    - owner/repo@v1.0.0#path/to/project
    """
    clean_src = source.strip()
    subpath: str | None = None
    ref: str | None = None

    # Check for GitHub tree URL format: https://github.com/owner/repo/tree/<ref>/<subpath>
    github_tree_match = re.match(
        r"^(https?://github\.com/[^/]+/[^/]+)/tree/([^/]+)(?:/(.+))?$",
        clean_src,
        re.IGNORECASE,
    )
    if github_tree_match:
        base_repo, ref, subpath = github_tree_match.groups()
        clone_url = f"{base_repo}.git" if not base_repo.endswith(".git") else base_repo
        chosen_subpath = project_override if project_override is not None else subpath
        return GitSourceInfo(clone_url=clone_url, ref=ref, subpath=chosen_subpath)

    # Shorthand normalization: owner/repo
    if not clean_src.startswith(("git@", "git://", "ssh://", "http://", "https://")):
        if clean_src.startswith(("github.com/", "gitlab.com/", "bitbucket.org/")):
            clean_src = f"https://{clean_src}"
        elif "/" in clean_src:
            clean_src = f"https://github.com/{clean_src}"

    # Extract #subpath if present
    if "#" in clean_src:
        clean_src, _, subpath = clean_src.partition("#")
        # clean_src, subpath = clean_src.split("#", 1)

    # Extract @ref if present
    if "@" in clean_src and not clean_src.startswith("git@"):
        clean_src, ref = clean_src.rsplit("@", 1)
    elif clean_src.startswith("git@") and "@" in clean_src[4:]:
        # ssh format git@github.com:owner/repo.git@ref
        parts = clean_src.rsplit("@", 1)
        if len(parts) == 2 and parts[0] != "git":
            clean_src, ref = parts

    clone_url = clean_src
    if not clone_url.endswith(".git") and "github.com" in clone_url:
        clone_url = f"{clone_url}.git"

    chosen_subpath = project_override if project_override is not None else subpath
    return GitSourceInfo(clone_url=clone_url, ref=ref, subpath=chosen_subpath)


def get_git_cache_root(
    runtime: RuntimeInfo | None = None,
) -> Path:
    """Return the root directory used for caching Git repositories."""
    runtime = runtime or RuntimeInfo.current()

    if runtime.os.is_posix:
        if runtime.system_wide:
            return Path("/var/cache/ninman/sources")
        xdg_cache = runtime.env.get("XDG_CACHE_HOME")
        base = Path(xdg_cache) if xdg_cache else runtime.home_dir / ".cache"
        return base / "ninman" / "sources"

    if runtime.system_wide:
        program_data = get_winpath(runtime.env.get("PROGRAMDATA", r"C:\ProgramData"))
        return program_data / "ninman" / "cache" / "sources"
    local_app_data = get_winpath(
        runtime.env.get("LOCALAPPDATA", str(runtime.home_dir / "AppData" / "Local"))
    )
    return local_app_data / "ninman" / "cache" / "sources"


def clone_or_update_repo(
    source_info: GitSourceInfo,
    cache_root: Path | None = None,
    quiet: bool = False,
) -> Path:
    """Clone or update the repository and return the target directory."""
    cache_root = cache_root or get_git_cache_root()
    cache_root.mkdir(parents=True, exist_ok=True)

    # Derive unique folder name using repo stem and hash of clone URL
    url_hash = hashlib.sha256(source_info.clone_url.encode("utf-8")).hexdigest()[:10]
    repo_name = source_info.clone_url.rstrip("/").split("/")[-1].removesuffix(".git")
    repo_dir = cache_root / f"{repo_name}_{url_hash}"

    if not repo_dir.exists():
        logger.info("Cloning %s into %s...", source_info.clone_url, repo_dir)
        cmd = ["git", "clone", source_info.clone_url, str(repo_dir)]
        exec_command(cmd, quiet=quiet)
    else:
        logger.info("Updating existing repository in %s...", repo_dir)
        exec_command(["git", "fetch", "--all", "--tags"], cwd=str(repo_dir), quiet=quiet)

    if source_info.ref:
        logger.info("Checking out ref %s in %s...", source_info.ref, repo_dir)
        exec_command(["git", "checkout", source_info.ref], cwd=str(repo_dir), quiet=quiet)
        # Try fast-forward pull if ref is a branch
        try:
            exec_command(["git", "pull", "--ff-only"], cwd=str(repo_dir), quiet=True)
        except Exception as ex:  # pylint: disable=broad-except
            logger.warning("Failed to fast-forward pull in %s", repo_dir, exc_info=ex)
    else:
        # Checkout default branch and pull latest
        try:
            exec_command(["git", "pull", "--ff-only"], cwd=str(repo_dir), quiet=quiet)
        except Exception as ex:  # pylint: disable=broad-except
            logger.warning("Failed to fast-forward pull in %s", repo_dir, exc_info=ex)

    if source_info.subpath:
        target_path = repo_dir / source_info.subpath
        if not target_path.exists():
            raise FileNotFoundError(
                f"Project path '{source_info.subpath}' not found "
                f"in repository '{source_info.clone_url}'."
            )

    return repo_dir


def update_git_repo(repo_dir: Path, ref: str | None = None, quiet: bool = False) -> None:
    """Fetch and pull the latest changes in a cached Git repository."""
    if not (repo_dir / ".git").exists() and not (repo_dir.parent / ".git").exists():
        return

    actual_repo_dir = repo_dir if (repo_dir / ".git").exists() else repo_dir.parent
    exec_command(["git", "fetch", "--all", "--tags"], cwd=str(actual_repo_dir), quiet=quiet)

    if ref:
        exec_command(["git", "checkout", ref], cwd=str(actual_repo_dir), quiet=quiet)
        try:
            exec_command(["git", "pull", "--ff-only"], cwd=str(actual_repo_dir), quiet=True)
        except Exception:  # pylint: disable=broad-except
            pass
    else:
        try:
            exec_command(["git", "pull", "--ff-only"], cwd=str(actual_repo_dir), quiet=quiet)
        except Exception:  # pylint: disable=broad-except
            pass


__all__ = [
    "GitSourceInfo",
    "is_git_url",
    "parse_git_source",
    "get_git_cache_root",
    "clone_or_update_repo",
    "update_git_repo",
]
