"""Common installation functionality."""

import argparse
from pathlib import Path
import semver

from net_install_manager.config import app_sources as aps
from net_install_manager.config.build_options import BuildOptions
from net_install_manager.core import errors
from net_install_manager.core.installation_service import InstallationOptions, TargetOptions
from net_install_manager.runtime.runtime import Runtime
from net_install_manager.utilities import git as git_utils
from net_install_manager.utilities import csproj as cs_utils


def register_targets_arguments(parser: argparse.ArgumentParser) -> None:
    """Register target-related arguments."""

    parser.add_argument(
        "--binary-name", help="The command to be executed to invoke the application", default=None
    )
    parser.add_argument(
        "--source-binary-name", help="The name of the binary in the source package", default=None
    )
    parser.add_argument(
        "--app-dir-name", help="The name of the application directory", default=None
    )


def extract_targets(args: argparse.Namespace) -> TargetOptions:
    """Extract target-related options from the command-line arguments."""

    return TargetOptions(
        binary_name=args.binary_name,
        source_binary_name=args.source_binary_name,
        app_dir_name=args.app_dir_name,
    )


def register_installation_options_arguments(parser: argparse.ArgumentParser) -> None:
    """Register common installation arguments."""

    parser.add_argument(
        "--version-override", help="The version to override auto-detected version", default=None
    )
    parser.add_argument(
        "--asset-pattern",
        help=(
            "The pattern to determine the correct asset "
            "(only used for GitHub Releases; defaults to '{rid}-{version}')"
        ),
        default=None,
    )
    parser.add_argument(
        "--force",
        help="Force the installation, even if it may overwrite existing files",
        action="store_true",
    )
    parser.add_argument(
        "--exclude-patterns",
        help="Patterns of files to exclude from installation",
        default=None,
    )
    parser.add_argument(
        "--target-permissions", help="Target permissions for installed files", default=None
    )
    parser.add_argument(
        "--prefer-opt", help="Prefer /opt over /var/local/lib", action="store_true"
    )
    parser.add_argument(
        "--token",
        help="The authentication token for accessing private releases",
        default=None,
    )


def extract_installation_options(args: argparse.Namespace) -> InstallationOptions:
    """Extract installation-related options from the command-line arguments."""

    return InstallationOptions(
        force=args.force,
        version_override=(
            semver.Version.parse(args.version_override) if args.version_override else None
        ),
        exclude_patterns=args.exclude_patterns,
        target_permissions=args.target_permissions,
        prefer_opt=args.prefer_opt,
        token=args.token,
    )


def register_build_options_arguments(parser: argparse.ArgumentParser) -> None:
    """Register build options arguments."""

    parser.add_argument(
        "--debug",
        help="Build in debug mode",
        action="store_true",
    )
    parser.add_argument(
        "--self-contained",
        help="Build as a self-contained application",
        action="store_true",
    )
    parser.add_argument(
        "--rid",
        help="Specify the Runtime Identifier (RID) for the build",
        default=None,
    )


def extract_build_options(args: argparse.Namespace) -> BuildOptions:
    """Extract build options from the command-line arguments."""

    return BuildOptions(
        debug_mode=args.debug,
        self_contained=args.self_contained,
        runtime_identifier=args.rid,
    )


def extract_app_source(
    given_source: str | None,
    build_options: BuildOptions,
    asset_pattern: str | None,
    runtime: Runtime,
) -> aps.AppSource:
    """Extract the AppSource from the command-line arguments."""

    if given_source is not None and git_utils.is_git_url(given_source):
        return git_utils.parse_git_source(given_source, runtime, build_options)

    if given_source is not None and (release_info := git_utils.parse_git_release(given_source)):

        if Path(given_source).exists():
            raise errors.AmbiguousSourceError(given_source)

        owner, repo, tag = release_info
        asset_pattern = asset_pattern or "{rid}-{version}"
        return aps.GitHubReleaseAppSource(owner, repo, tag=tag, asset_pattern=asset_pattern)

    if given_source is not None:
        source = Path(given_source).resolve()
        if not source.exists():
            raise FileNotFoundError(source)
    else:
        source = Path.cwd().resolve()

    proj_file = cs_utils.find_project_file(source)

    if proj_file is not None:
        return aps.CodeAppSource(proj_file, build_options)

    return aps.BuiltAppSource(source)
