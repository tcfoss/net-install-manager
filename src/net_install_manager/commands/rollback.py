"""Command to change the current version of an installed application."""

from argparse import _SubParsersAction, ArgumentParser, Namespace
import argparse
from dataclasses import dataclass, replace
import logging
import semver

from net_install_manager.commands.base_command import BaseCommand
from net_install_manager.config.paths import get_paths_from_app_info
from net_install_manager.core import errors
from net_install_manager.core.os_ops import get_os_ops
from net_install_manager.core.registry import Registry
from net_install_manager.runtime.runtime import Runtime
from net_install_manager.utilities.version import parse_semver

logger = logging.getLogger(__name__)


@dataclass
class RollbackArguments:
    """Arguments for the rollback command."""

    app_name: str
    target_version: semver.Version


class RollbackCommand(BaseCommand[RollbackArguments]):
    """Command to change the current version."""

    def execute(self, runtime: Runtime, args: RollbackArguments) -> None:

        registry = Registry(runtime)

        app_info, installed_versions = registry.get_app_with_versions(args.app_name)

        if args.target_version not in installed_versions.versions:
            raise errors.VersionNotInstalledError(args.app_name, str(args.target_version))

        if app_info.installed_version == args.target_version:
            logger.info(
                "Application %s is already at target version %s.",
                args.app_name,
                args.target_version,
            )
            return

        paths = get_paths_from_app_info(runtime, app_info)
        os_ops = get_os_ops(runtime.os)
        logger.info(
            "Updating current to point to version %s for application %s.",
            args.target_version,
            args.app_name,
        )

        os_ops.update_current_link(paths.versions_dir, str(args.target_version), paths.current_dir)

        app_info = replace(app_info, installed_version=args.target_version)
        registry.set(app_info.binary_name, app_info)

    @staticmethod
    def register_command(subparsers: _SubParsersAction) -> ArgumentParser:
        parser = subparsers.add_parser(
            "rollback", help="Rollback the application to a previous version."
        )
        parser.add_argument("app_name", type=str, help="Name of the application to rollback.")
        parser.add_argument("target_version", type=str, help="Target version to rollback to.")
        return parser

    @staticmethod
    def parse_arguments(runtime: Runtime, args: Namespace) -> RollbackArguments:
        version = parse_semver(args.target_version)
        assert version is not None
        return RollbackArguments(app_name=args.app_name, target_version=version)

    @staticmethod
    def validate_arguments(
        parser: argparse.ArgumentParser, runtime: Runtime, args: argparse.Namespace
    ) -> None:
        if parse_semver(args.target_version) is None:
            parser.error(f"Invalid target version: {args.target_version}")
