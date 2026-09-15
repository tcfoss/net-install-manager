"""Utilities for downloading and unpacking GitHub release assets."""

from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass
import os
from pathlib import Path
import re
import shutil
import tarfile
import tempfile
from typing import Mapping
import zipfile

import requests
import semver

from net_install_manager.runtime_config import RuntimeInfo
from net_install_manager.utilities.version_tools import parse_semver


@dataclass(frozen=True)
class AssetInfo:
    """Information about a GitHub release asset."""

    name: str
    url: str


@dataclass(frozen=True)
class GitHubRelease:
    """Information about a GitHub release."""

    tag_name: str
    name: str
    version: semver.Version | None
    assets: list[AssetInfo]


@dataclass(frozen=True)
class GitHubReleaseInfo:
    """Coordinates and asset selection rules for a GitHub release source."""

    owner: str
    repo: str
    asset_pattern: str
    tag: str | None = None


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


def get_release_info(
    owner: str, repo: str, tag: str | None = None, auth_token: str | None = None
) -> GitHubRelease:
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
    assets = [AssetInfo(name=item["name"], url=item["url"]) for item in data.get("assets", [])]
    return GitHubRelease(
        tag_name=data.get("tag_name", ""),
        name=data.get("name", ""),
        version=parse_semver(data.get("tag_name", "")),
        assets=assets,
    )


def substitute_pattern(pattern: str, runtime_info: RuntimeInfo, release: GitHubRelease) -> str:
    """Substitute runtime and release placeholders in an asset pattern."""
    substitutions = {
        "{rid}": runtime_info.platform.runtime_identifier,
        "{os}": runtime_info.platform.os.rid_string,
        "{arch}": runtime_info.platform.architecture.rid_string,
    }
    if release.version is not None:
        substitutions["{version}"] = str(release.version)
    result = pattern
    for placeholder, value in substitutions.items():
        result = result.replace(placeholder, value)
    return result


def download_asset(
    release: GitHubRelease,
    name_pattern: str,
    runtime_info: RuntimeInfo,
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


@contextmanager
def prepare_release(
    source: GitHubReleaseInfo,
    runtime_info: RuntimeInfo,
    auth_token: str | None = None,
) -> Generator[tuple[Path, GitHubRelease], None, None]:
    """Download and unpack a release into a temporary directory."""
    token = auth_token if auth_token is not None else get_github_token(runtime_info.env)
    working_dir = Path(tempfile.mkdtemp(prefix="ninman_release_"))
    download_dir = working_dir / "download"
    artifact_dir = working_dir / "artifact"
    try:
        release = get_release_info(source.owner, source.repo, source.tag, token)
        archive_path = download_asset(
            release,
            source.asset_pattern,
            runtime_info,
            download_dir,
            token,
        )
        artifact_dir.mkdir()
        formats = {suffix for _, suffixes, _ in shutil.get_unpack_formats() for suffix in suffixes}
        if any(archive_path.name.lower().endswith(suffix) for suffix in formats):
            unpack_archive_safely(archive_path, artifact_dir)
        else:
            shutil.copy2(archive_path, artifact_dir / archive_path.name)
        yield artifact_dir, release
    finally:
        shutil.rmtree(working_dir, ignore_errors=True)


__all__ = [
    "AssetInfo",
    "GitHubRelease",
    "GitHubReleaseInfo",
    "download_asset",
    "get_github_token",
    "get_release_info",
    "prepare_release",
    "substitute_pattern",
    "unpack_archive_safely",
]
