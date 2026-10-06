"""Command to prune existing versions."""

import argparse
from dataclasses import dataclass, replace
import logging
import shutil

import semver

from net_install_manager.commands.base_command import BaseCommand
from net_install_manager.commands.helpers import interaction
from net_install_manager.config.paths import get_paths_from_app_info
from net_install_manager.core import errors
from net_install_manager.core.os_ops import get_os_ops
from net_install_manager.core.registry import Registry
from net_install_manager.runtime.runtime import Runtime
from net_install_manager.utilities.version import parse_semver

logger = logging.getLogger(__name__)


@dataclass
class PruneArguments:
    """Arguments for the prune command."""

    app_name: str

    keep_latest: int | None = None

    min_version: semver.Version | None = None
    max_version: semver.Version | None = None

    assume_yes: bool = False


class PruneCommand(BaseCommand[PruneArguments]):
    """Command to prune existing versions."""

    def execute(self, runtime: Runtime, args: PruneArguments) -> None:

        registry = Registry(runtime)

        app_info, installed_versions = registry.get_app_with_versions(args.app_name)

        versions_to_prune = []

        if args.keep_latest:
            all_versions = sorted(installed_versions.versions, reverse=True)
            versions_to_prune.extend(all_versions[args.keep_latest :])
        else:
            for version in installed_versions.versions:
                if args.min_version and version < args.min_version:
                    versions_to_prune.append(version)
                elif args.max_version and version > args.max_version:
                    versions_to_prune.append(version)

        if len(versions_to_prune) == len(installed_versions.versions):
            raise errors.PruneAllError(args.app_name)

        paths = get_paths_from_app_info(runtime, app_info)

        if app_info.installed_version in versions_to_prune:
            new_installed_version = max(
                (v for v in installed_versions.versions if v not in versions_to_prune)
            )
            if not args.assume_yes and not interaction.confirm(
                f"The currently installed version '{app_info.installed_version}' of "
                f"'{args.app_name}' will be removed and '{new_installed_version}' "
                "will become current. Continue?"
            ):
                logger.info("Prune of '%s' cancelled by user.", args.app_name)
                return

            os_ops = get_os_ops(runtime.os)
            logger.warning(
                "The currently installed version '%s' for application '%s' is being pruned."
                " New installed version is '%s'.",
                app_info.installed_version,
                args.app_name,
                new_installed_version,
            )
            os_ops.update_current_link(
                paths.versions_dir, str(new_installed_version), paths.current_dir
            )
            app_info = replace(app_info, installed_version=new_installed_version)
            registry.set(app_info.binary_name, app_info)

        for version in versions_to_prune:
            version_dir = paths.versions_dir / str(version)
            logger.info("Pruning version '%s' for application '%s'.", version, args.app_name)
            if version_dir.exists():
                shutil.rmtree(version_dir)
            else:
                logger.warning(
                    "Version directory '%s' does not exist for application '%s'.",
                    version_dir,
                    args.app_name,
                )

    @staticmethod
    def register_command(subparsers: argparse._SubParsersAction) -> argparse.ArgumentParser:
        parser = subparsers.add_parser("prune", help="Prune existing versions of an application.")
        parser.add_argument("app_name", type=str, help="Name of the application to prune.")
        parser.add_argument("--keep-latest", type=int, help="Number of latest versions to keep.")
        parser.add_argument("--min-version", type=str, help="Minimum version to keep.")
        parser.add_argument("--max-version", type=str, help="Maximum version to keep.")
        interaction.register_autoconfirm_argument(parser)
        return parser

    @staticmethod
    def parse_arguments(runtime: Runtime, args: argparse.Namespace) -> PruneArguments:
        keep_latest: int | None = args.keep_latest

        min_version: semver.Version | None = None
        if args.min_version is not None:
            min_version = parse_semver(args.min_version)
            assert min_version is not None, "min_version must be a valid semantic version."

        max_version: semver.Version | None = None
        if args.max_version is not None:
            max_version = parse_semver(args.max_version)
            assert max_version is not None, "max_version must be a valid semantic version."

        return PruneArguments(
            app_name=args.app_name,
            keep_latest=keep_latest,
            min_version=min_version,
            max_version=max_version,
            assume_yes=args.assume_yes,
        )

    @staticmethod
    def validate_arguments(
        parser: argparse.ArgumentParser, runtime: Runtime, args: argparse.Namespace
    ) -> None:

        if args.keep_latest is not None and args.keep_latest < 1:
            parser.error("keep_latest must be a positive integer.")

        keep_latest: int | None = args.keep_latest

        min_version: semver.Version | None = None
        if (
            args.min_version is not None
            and (min_version := parse_semver(args.min_version)) is None
        ):
            parser.error("min_version must be a valid semantic version.")

        max_version: semver.Version | None = None
        if (
            args.max_version is not None
            and (max_version := parse_semver(args.max_version)) is None
        ):
            parser.error("max_version must be a valid semantic version.")

        if min_version is not None and max_version is not None and min_version > max_version:
            parser.error("min_version cannot be greater than max_version.")

        if (min_version is not None or max_version is not None) and keep_latest is not None:
            parser.error("Cannot specify both version range and keep-latest.")

        if keep_latest is None and min_version is None and max_version is None:
            parser.error("At least one pruning criterion must be specified.")
