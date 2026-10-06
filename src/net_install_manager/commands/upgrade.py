"""Upgrade command."""

import argparse

from net_install_manager.commands.base_command import BaseCommand
from net_install_manager.core.installation_service import (
    InstallationService,
    KEEP_EXISTING,
    UpgradeOptions,
    UpgradeRequest,
)
from net_install_manager.runtime.runtime import Runtime
from net_install_manager.utilities.version import parse_semver


class UpgradeCommand(BaseCommand[UpgradeRequest]):
    """Command to upgrade an application."""

    def execute(self, runtime: Runtime, args: UpgradeRequest) -> None:
        """Execute the upgrade command."""
        InstallationService(runtime).upgrade(args)

    @staticmethod
    def register_command(subparsers: argparse._SubParsersAction) -> argparse.ArgumentParser:
        """Register the upgrade command with the given subparsers."""
        parser = subparsers.add_parser("upgrade", help="Upgrade an installed application")

        parser.add_argument("app_name", type=str, help="Name of the application to upgrade")

        parser.add_argument(
            "--version-override",
            type=str,
            help="Override the auto-detected version",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Allow overwriting an already-installed version",
        )
        parser.add_argument("--token", help="Authentication token for private sources")
        parser.add_argument(
            "--new-ref",
            nargs="?",
            help="Git ref to use for the upgrade",
            const=None,
            default=KEEP_EXISTING,
        )
        parser.add_argument(
            "--new-release-tag",
            nargs="?",
            const=None,
            default=KEEP_EXISTING,
            help="GitHub release tag to use for the upgrade",
        )

        return parser

    @staticmethod
    def parse_arguments(runtime: Runtime, args: argparse.Namespace) -> UpgradeRequest:
        """Parse the command-line arguments for the upgrade command."""
        return UpgradeRequest(
            app_name=args.app_name,
            upgrade_options=UpgradeOptions(
                force=args.force,
                version_override=parse_semver(args.version_override),
                token=args.token,
                new_ref=args.new_ref,
                new_release_tag=args.new_release_tag,
            ),
        )
