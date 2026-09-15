"""Install applications from GitHub release assets."""

import argparse
from dataclasses import replace
from pathlib import Path

from net_install_manager.app_manager import AppManager, VersionRegressionError
from net_install_manager.cli_output import error, write
from net_install_manager.config import Config, auto_discover_config, load_config
from net_install_manager.registry import AppRegistry
from net_install_manager.runtime_config import InstallOptions, RuntimeInfo
from net_install_manager.utilities.github_release_tools import (
    GitHubReleaseInfo,
    prepare_release,
)
from net_install_manager.utilities.install_tools import InstallSource


def get_config(args: argparse.Namespace, root: Path) -> Config:
    """Retrieve the configuration for the application.

    Args:
        args: The command-line arguments.
        root: The root path to search for configuration files.

    Returns:
        The resolved configuration object.
    """
    config: Config | None = None
    if args.config:
        config = load_config(Path(args.config))
    else:
        config = auto_discover_config(root)

    overrides = {
        name: getattr(args, name)
        for name in ("app_directory", "binary_name", "source_binary_name", "csproj_path")
        if getattr(args, name, None) is not None
    }
    if (
        config is None
        and "app_directory" in overrides
        and "binary_name" in overrides
        and "source_binary_name" in overrides
    ):
        config = Config(
            app_directory=overrides["app_directory"],
            binary_name=overrides["binary_name"],
            source_binary_name=overrides["source_binary_name"],
            csproj_path=overrides.get("csproj_path"),
        )

    if config is None:
        raise ValueError(
            "No ninman.yml, ninman.yaml, or .csproj found in the release artifact. "
            "Specify --config or provide application metadata options."
        )

    return replace(config, **overrides) if overrides else config


def execute(
    args: argparse.Namespace,
    runtime: RuntimeInfo | None = None,
    registry: AppRegistry | None = None,
) -> int:
    """Download, unpack, discover configuration, and install a release."""
    runtime = runtime or RuntimeInfo.current(system_wide=getattr(args, "system", False))
    registry = registry or AppRegistry(runtime=runtime)
    release_info = GitHubReleaseInfo(
        owner=args.owner,
        repo=args.repo,
        asset_pattern=args.asset_pattern,
        tag=args.tag,
    )
    release_source = InstallSource(release_info=release_info)

    try:
        with prepare_release(release_info, runtime) as (artifact_dir, release):
            config = get_config(args, artifact_dir)
            manager = AppManager(
                config=config,
                prefer_opt=getattr(args, "prefer_opt", False),
                runtime=runtime,
                registry=registry,
            )
            explicit_version = args.app_version
            if explicit_version is None and release.version is not None:
                explicit_version = str(release.version)
            options = InstallOptions(
                force=args.force,
                keep_latest=args.versions_to_keep,
                explicit_version=explicit_version,
                quiet=getattr(args, "quiet", False),
            )
            installed_version = manager.install(
                source=InstallSource(local_path=str(artifact_dir)),
                options=options,
                registry_source=release_source,
            )
        write(f"Successfully installed version {installed_version} of '{config.binary_name}'.")
        return 0
    except VersionRegressionError as exception:
        error(f"Error: {exception}")
        return 6
    except Exception as exception:  # pylint: disable=broad-except
        error(f"Installation failed: {exception}")
        return 1


def register_install_release_command(
    subparsers: argparse._SubParsersAction,
) -> argparse.ArgumentParser:
    """Register the GitHub release installation command."""
    parser = subparsers.add_parser(
        "install-release", help="Install a .NET application from a GitHub release"
    )
    parser.add_argument("owner", help="GitHub repository owner")
    parser.add_argument("repo", help="GitHub repository name")
    parser.add_argument(
        "-a",
        "--asset-pattern",
        default="{rid}-{version}",
        help="Regular expression used to select the runtime asset",
    )
    parser.add_argument("--tag", default=None, help="Release tag; defaults to the latest release")
    parser.add_argument(
        "--config",
        default=argparse.SUPPRESS,
        help="Configuration file outside the artifact",
    )
    parser.add_argument("--app-directory", default=None)
    parser.add_argument("--binary-name", default=None)
    parser.add_argument("--source-binary-name", default=None)
    parser.add_argument("--csproj-path", type=Path, default=None)
    parser.add_argument("-k", "--versions-to-keep", type=int, default=None)
    parser.add_argument("-f", "--force", action="store_true")
    parser.add_argument("-v", "--app-version", default=None)
    return parser


__all__ = ["execute", "register_install_release_command"]
