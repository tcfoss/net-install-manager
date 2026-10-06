"""Utilities for interacting with git."""

from collections.abc import Mapping
from dataclasses import dataclass
import hashlib
import logging
import os
import re
from pathlib import Path
import shutil
import tarfile
import zipfile

import requests
import semver

from net_install_manager.config import app_sources as aps
from net_install_manager.config.build_options import BuildOptions
from net_install_manager.core import errors
from net_install_manager.runtime.runtime import Runtime
from net_install_manager.utilities.sh import exec_command, exec_command_output
from net_install_manager.utilities.version import parse_semver

logger = logging.getLogger(__name__)


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


def parse_git_release(source: str) -> tuple[str, str, str | None] | None:
    """Parse a git release string."""
    base_pat = r"([a-zA-Z0-9-]+):([a-zA-Z0-9_.-]+)"
    tag_pat = r"([^ \040\177~^:?*\[]+)"

    match = re.fullmatch(f"{base_pat}:{tag_pat}", source)
    if match:
        owner, repo, tag = match.groups()
        if "/" in tag or "\\" in tag or ".." in tag or "@{" in tag or tag.endswith((".lock", ".")):
            return None
        return owner, repo, tag
    match = re.fullmatch(base_pat, source)
    if match:
        owner, repo = match.groups()
        return owner, repo, None
    return None


def parse_git_source(
    source: str,
    runtime: Runtime,
    build_options: BuildOptions | None = None,
    project_override: str | None = None,
) -> aps.GitCodeAppSource:
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

    build_options = build_options or BuildOptions()

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
        return aps.GitCodeAppSource(
            clone_url=clone_url,
            ref=ref,
            subpath=Path(chosen_subpath) if chosen_subpath else Path("/dev/null"),
            build_options=build_options,
            cache_dir=_get_cache_dir(clone_url, runtime),
        )

    # Shorthand normalization: owner/repo
    if not clean_src.startswith(("git@", "git://", "ssh://", "http://", "https://")):
        if clean_src.startswith(("github.com/", "gitlab.com/", "bitbucket.org/")):
            clean_src = f"https://{clean_src}"
        elif "/" in clean_src:
            clean_src = f"https://github.com/{clean_src}"

    # Extract #subpath if present
    if "#" in clean_src:
        clean_src, _, subpath = clean_src.partition("#")

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
    return aps.GitCodeAppSource(
        clone_url=clone_url,
        ref=ref,
        subpath=Path(chosen_subpath) if chosen_subpath else Path("/dev/null"),
        build_options=build_options,
        cache_dir=_get_cache_dir(clone_url, runtime),
    )


def _get_cache_dir(clone_url: str, runtime: Runtime) -> Path:
    """Return the cache directory for a given Git repository."""
    url_hash = hashlib.sha256(clone_url.encode("utf-8")).hexdigest()[:10]
    repo_name = clone_url.rstrip("/").split("/")[-1].removesuffix(".git")
    return runtime.cache_root / f"{repo_name}_{url_hash}"


def clone_or_update_repo(source_info: aps.GitCodeAppSource):
    """Clone or update the repository and return the target directory."""
    if not source_info.cache_dir.exists():
        logger.info("Cache directory %s does not exist. Creating it...", source_info.cache_dir)
        source_info.cache_dir.mkdir(parents=True, exist_ok=True)

    if not (source_info.cache_dir / ".git").exists():
        logger.info("Cloning %s into %s...", source_info.clone_url, source_info.cache_dir)
        cmd = ["git", "clone", source_info.clone_url, str(source_info.cache_dir)]
        exec_command(cmd)
    else:
        logger.info("Updating existing repository in %s...", source_info.cache_dir)
        try:
            exec_command(["git", "fetch", "--all", "--tags"], cwd=str(source_info.cache_dir))
        except Exception as ex:  # pylint: disable=broad-except
            logger.exception(
                "Failed to fetch before checking out the default branch in %s",
                source_info.cache_dir,
            )
            raise errors.GitBranchError(source_info.clone_url, source_info.ref) from ex

    if source_info.ref:
        logger.info("Checking out ref %s in %s...", source_info.ref, source_info.cache_dir)
        exec_command(["git", "checkout", source_info.ref], cwd=str(source_info.cache_dir))
        # Try fast-forward pull if ref is a branch
        _fast_forward_pull(source_info)
    else:
        _checkout_default_branch(source_info)
        _fast_forward_pull(source_info)


def _fast_forward_pull(source_info: aps.GitCodeAppSource) -> None:
    try:
        exec_command(["git", "pull", "--ff-only"], cwd=str(source_info.cache_dir))
    except Exception as ex:  # pylint: disable=broad-except
        logger.warning(
            "Failed to fast-forward the default branch in %s",
            source_info.cache_dir,
            exc_info=ex,
        )


def _checkout_default_branch(source_info: aps.GitCodeAppSource) -> None:
    try:
        exec_command(
            ["git", "remote", "set-head", "origin", "--auto"],
            cwd=str(source_info.cache_dir),
        )

        default_remote_ref = exec_command_output(
            ["git", "symbolic-ref", "--short", "refs/remotes/origin/HEAD"],
            cwd=str(source_info.cache_dir),
        ).strip()

        if not default_remote_ref.startswith("origin/"):
            raise RuntimeError(f"Could not resolve the default branch: {default_remote_ref}")

        default_branch = default_remote_ref.removeprefix("origin/")
        local_branches = exec_command_output(
            ["git", "branch", "--format=%(refname:short)"],
            cwd=str(source_info.cache_dir),
        ).splitlines()

        if default_branch in local_branches:
            exec_command(["git", "switch", default_branch], cwd=str(source_info.cache_dir))
            exec_command(
                [
                    "git",
                    "branch",
                    "--set-upstream-to",
                    default_remote_ref,
                    default_branch,
                ],
                cwd=str(source_info.cache_dir),
            )

        else:
            exec_command(
                ["git", "switch", "--track", default_remote_ref],
                cwd=str(source_info.cache_dir),
            )

    except Exception as ex:  # pylint: disable=broad-except
        logger.exception(
            "Failed to check out the default branch in %s",
            source_info.cache_dir,
        )
        raise errors.GitBranchError(source_info.clone_url, source_info.ref) from ex


def get_github_token(env: Mapping[str, str] | None = None) -> str | None:
    """Return the first configured GitHub token from the environment."""
    values = env if env is not None else os.environ
    for name in ("NINMAN_GITHUB_TOKEN", "GITHUB_TOKEN", "GH_TOKEN"):
        token = values.get(name)
        if token:
            return token
    return None


def _headers(accept: str, auth_token: str | None) -> dict[str, str]:
    headers = {"Accept": accept}
    if auth_token:
        headers["Authorization"] = f"Bearer {auth_token}"
    return headers


@dataclass(frozen=True)
class _GitHubRelease:
    tag_name: str
    name: str
    version: semver.Version | None
    assets: list[_AssetInfo]


@dataclass(frozen=True)
class _AssetInfo:
    name: str
    url: str


def _get_release_info(
    owner: str, repo: str, tag: str | None = None, auth_token: str | None = None
) -> _GitHubRelease:
    """Fetch release metadata from GitHub."""
    endpoint = "latest" if tag is None else f"tags/{tag}"
    url = f"https://api.github.com/repos/{owner}/{repo}/releases/{endpoint}"
    response = requests.get(
        url,
        headers=_headers("application/vnd.github+json", auth_token),
        timeout=10,
    )
    response.raise_for_status()
    data = response.json()
    assets = [_AssetInfo(name=item["name"], url=item["url"]) for item in data.get("assets", [])]
    return _GitHubRelease(
        tag_name=data.get("tag_name", ""),
        name=data.get("name", ""),
        version=parse_semver(data.get("tag_name", "")),
        assets=assets,
    )


def substitute_pattern(pattern: str, runtime: Runtime, release: _GitHubRelease) -> str:
    """Substitute runtime and release placeholders in an asset pattern."""
    substitutions = {
        "{rid}": runtime.runtime_identifier,
        "{os}": runtime.platform.os.rid_string,
        "{arch}": runtime.platform.architecture.rid_string,
    }
    if release.version is not None:
        substitutions["{version}"] = str(release.version)
    result = pattern
    for placeholder, value in substitutions.items():
        result = result.replace(placeholder, value)
    return result


def download_asset(
    release: _GitHubRelease,
    name_pattern: str,
    runtime_info: Runtime,
    working_dir: Path,
    auth_token: str | None = None,
) -> Path:
    """Download one release asset selected by the broad configured pattern."""
    pattern = re.compile(substitute_pattern(name_pattern, runtime_info, release))
    matching_assets = [asset for asset in release.assets if pattern.search(asset.name)]
    if not matching_assets:
        raise ValueError(f"No asset matching pattern '{name_pattern}' found.")
    if len(matching_assets) > 1:
        raise ValueError(f"Multiple assets matching pattern '{name_pattern}' found.")

    working_dir.mkdir(parents=True, exist_ok=True)
    asset = matching_assets[0]
    response = requests.get(
        asset.url,
        headers=_headers("application/octet-stream", auth_token),
        timeout=10,
        stream=True,
    )
    response.raise_for_status()
    download_path = working_dir / asset.name
    with download_path.open("wb") as file:
        for chunk in response.iter_content(chunk_size=1024 * 1024):
            if chunk:
                file.write(chunk)
    return download_path


def _validate_archive_members(members: list[str], root: Path) -> None:
    for member in members:
        target = (root / member).resolve()
        try:
            target.relative_to(root)
        except ValueError as error:
            raise ValueError(f"Archive member escapes extraction directory: {member}") from error


def unpack_archive_safely(archive_path: Path, working_dir: Path) -> None:
    """Extract a ZIP or tar archive without allowing path traversal."""
    root = working_dir.resolve()
    if zipfile.is_zipfile(archive_path):
        with zipfile.ZipFile(archive_path) as archive:
            _validate_archive_members(archive.namelist(), root)
            archive.extractall(root)
        return
    if tarfile.is_tarfile(archive_path):
        with tarfile.open(archive_path) as archive:
            _validate_archive_members([member.name for member in archive.getmembers()], root)
            archive.extractall(root, filter="data")
        return
    raise ValueError(f"Unsupported archive format: {archive_path.name}")


def download_artifact(
    working_dir: Path,
    app_source: aps.GitHubReleaseAppSource,
    runtime: Runtime,
    token: str | None = None,
):
    """Download and unpack the release artifact."""
    token = token or get_github_token()
    download_dir = working_dir / "download"
    artifact_dir = working_dir / "dist"

    release = _get_release_info(app_source.owner, app_source.repo, app_source.tag, token)
    archive_path = download_asset(release, app_source.asset_pattern, runtime, download_dir, token)
    artifact_dir.mkdir()
    formats = {suffix for _, suffixes, _ in shutil.get_unpack_formats() for suffix in suffixes}
    if any(archive_path.name.endswith(suffix) for suffix in formats):
        unpack_archive_safely(archive_path, artifact_dir)
    else:
        shutil.copy2(archive_path, artifact_dir / archive_path.name)
    return artifact_dir, release
