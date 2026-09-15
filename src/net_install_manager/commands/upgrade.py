"""Upgrade command for the Net Install Manager application."""

import argparse
from contextlib import nullcontext
from pathlib import Path
import logging

from net_install_manager.app_manager import AppManager, VersionRegressionError
from net_install_manager.cli_output import error, progress, write
from net_install_manager.registry import AppRegistry, TrackedApp
from net_install_manager.runtime_config import InstallOptions, RuntimeInfo
from net_install_manager.utilities.git_tools import update_git_repo
from net_install_manager.utilities.github_release_tools import prepare_release
from net_install_manager.utilities.install_tools import InstallSource

logger = logging.getLogger(__name__)


def upgrade_tracked_app(
    tracked: TrackedApp,
    runtime: RuntimeInfo | None = None,
    force: bool = False,
    debug: bool | None = None,
    quiet: bool = False,
) -> bool:
    """Upgrade a single tracked application."""
    runtime = runtime or RuntimeInfo.current()
    try:
        source_context = (
            prepare_release(tracked.source.release_info, runtime)
            if tracked.source.is_release and tracked.source.release_info
            else nullcontext((tracked.source.resolve_root(quiet=quiet), None))
        )
        with source_context as (source_path, release):
            progress(f"Upgrading '{tracked.binary_name}' from '{source_path}'...", quiet=quiet)

            if tracked.git_info:
                try:
                    progress(
                        f"Fetching latest changes for '{tracked.binary_name}'...", quiet=quiet
                    )
                    update_git_repo(source_path, ref=tracked.git_info.ref, quiet=quiet)
                except Exception as exception:  # pylint: disable=broad-except
                    logger.warning("Could not pull git repo: %s", exception)

            if not source_path.exists():
                error(f"Error: Source path '{source_path}' no longer exists.")
                return False

            config = tracked.to_config()
            sub_manager = AppManager(
                config=config,
                prefer_opt=tracked.prefer_opt,
                runtime=runtime,
            )

            options = tracked.to_install_options(force=force, debug_override=debug)
            options = InstallOptions(
                prefer_opt=options.prefer_opt,
                self_contained=options.self_contained,
                release=options.release,
                force=options.force,
                keep_latest=options.keep_latest,
                exclude_patterns=options.exclude_patterns,
                explicit_version=(
                    str(release.version)
                    if release and release.version
                    else options.explicit_version
                ),
                quiet=quiet,
            )
            install_source = (
                InstallSource(local_path=str(source_path))
                if tracked.source.is_release
                else tracked.source
            )
            new_version = sub_manager.install(
                source=install_source,
                options=options,
                registry_source=tracked.source if tracked.source.is_release else None,
            )
        write(f"Successfully upgraded '{tracked.binary_name}' to version {new_version}.")
        return True
    except VersionRegressionError as e:
        write(f"Already up to date: {e}")
        return True
    except Exception as e:  # pylint: disable=broad-except
        error(f"Failed to upgrade '{tracked.binary_name}': {e}")
        return False


def _update_all(
    registry: AppRegistry,
    runtime: RuntimeInfo,
    force: bool,
    debug: bool,
    quiet: bool,
) -> int:
    """Update all tracked applications.

    Returns the number of failed updates.
    """

    apps = registry.load()
    if not apps:
        write("No tracked applications found in registry to upgrade.")
        return 0

    failed = 0
    for tracked in apps.values():
        success = upgrade_tracked_app(
            tracked, runtime=runtime, force=force, debug=debug, quiet=quiet
        )
        if not success:
            failed += 1

    return failed


def _update_by_name(
    app_name: str,
    registry: AppRegistry,
    runtime: RuntimeInfo,
    force: bool,
    debug: bool,
    quiet: bool,
) -> int:
    """Update a tracked application by its name.

    Returns 0 if the update was successful, 1 otherwise.
    """
    tracked = registry.get(app_name)
    if not tracked:
        error(f"Error: Application '{app_name}' is not registered in ninman.")
        error("Run 'ninman list-apps' or install it first.")
        return 1

    return (
        0
        if upgrade_tracked_app(tracked, runtime=runtime, force=force, debug=debug, quiet=quiet)
        else 1
    )


def _update_by_config(
    manager: AppManager,
    registry: AppRegistry,
    force: bool,
    debug: bool | None,
    quiet: bool,
) -> int:
    """Update the application based on the current directory configuration.

    Returns 0 if the update was successful, 1 otherwise.
    """
    tracked = registry.get(manager.config.binary_name)
    source_target = (
        tracked.source
        if tracked
        else InstallSource(local_path=str(manager.config.csproj_path or Path.cwd()))
    )

    if tracked:
        options = tracked.to_install_options(force=force, debug_override=debug)
    else:
        release_mode = not debug if debug is not None else True
        options = InstallOptions(force=force, release=release_mode)
    options = InstallOptions(
        prefer_opt=options.prefer_opt,
        self_contained=options.self_contained,
        release=options.release,
        force=options.force,
        keep_latest=options.keep_latest,
        exclude_patterns=options.exclude_patterns,
        explicit_version=options.explicit_version,
        quiet=quiet,
    )

    try:
        new_version = manager.install(
            source=source_target,
            options=options,
        )
        write(f"Successfully upgraded '{manager.config.binary_name}' to version {new_version}.")
        return 0
    except VersionRegressionError as e:
        write(f"Already up to date: {e}")
        return 0
    except Exception as e:  # pylint: disable=broad-except
        error(f"Upgrade failed: {e}")
        return 1


def execute(
    args: argparse.Namespace,
    manager: AppManager | None = None,
    registry: AppRegistry | None = None,
    runtime: RuntimeInfo | None = None,
) -> int:
    """Execute the upgrade command."""
    runtime = runtime or RuntimeInfo.current(system_wide=getattr(args, "system", False))
    registry = registry or AppRegistry(runtime=runtime)

    # 1. Upgrade all tracked apps
    if getattr(args, "all", False):
        failed = _update_all(
            registry, runtime, args.force, args.debug, getattr(args, "quiet", False)
        )

        return 1 if failed > 0 else 0

    # 2. Upgrade by specific app name
    if getattr(args, "app_name", None):
        return _update_by_name(
            args.app_name,
            registry,
            runtime,
            args.force,
            args.debug,
            getattr(args, "quiet", False),
        )

    # 3. Upgrade current directory app if manager is provided
    if manager:
        return _update_by_config(
            manager,
            registry,
            args.force,
            args.debug,
            getattr(args, "quiet", False),
        )

    error("Please specify an application name, --all, or run inside an application directory.")
    return 1


def register_upgrade_command(subparsers: argparse._SubParsersAction) -> argparse.ArgumentParser:
    """Register the upgrade command arguments."""
    # pylint: disable=duplicate-code

    parser = subparsers.add_parser("upgrade", help="Upgrade an installed .NET application")
    parser.add_argument(
        "app_name",
        nargs="?",
        default=None,
        help=(
            "Name of the tracked application to upgrade "
            "(optional if running in project directory or using --all)"
        ),
    )
    parser.add_argument(
        "-a",
        "--all",
        action="store_true",
        help="Upgrade all tracked applications",
    )
    parser.add_argument(
        "-f",
        "--force",
        action="store_true",
        help="Force reinstallation even if already at latest version",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        default=None,
        help="Build using Debug configuration",
    )
    return parser


__all__ = ["execute", "register_upgrade_command", "upgrade_tracked_app"]
