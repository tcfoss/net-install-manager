"""Command to install applications."""

import argparse
from pathlib import Path

from net_install_manager.commands.base_command import BaseCommand
from net_install_manager.core.installation_service import (
    InstallationRequest,
    InstallationService,
)
from net_install_manager.runtime.runtime import Runtime
from net_install_manager.commands.helpers import installation as inhelp


class InstallCommand(BaseCommand[InstallationRequest]):
    """Install an application."""

    def execute(self, runtime: Runtime, args: InstallationRequest) -> None:
        InstallationService(runtime).install(args)

    @staticmethod
    def register_command(subparsers: argparse._SubParsersAction) -> argparse.ArgumentParser:
        parser = subparsers.add_parser("install", help="Install an application")

        parser.add_argument(
            "source",
            help="Path to .csproj file, project folder, precompiled directory, or Git/GitHub URL",
            nargs="?",
            default=None,
        )
        parser.add_argument(
            "--manifest",
            type=Path,
            help="Path to a ninman YAML manifest",
            default=None,
        )

        inhelp.register_targets_arguments(parser)
        inhelp.register_build_options_arguments(parser)
        inhelp.register_installation_options_arguments(parser)

        return parser

    @staticmethod
    def parse_arguments(runtime: Runtime, args: argparse.Namespace) -> InstallationRequest:
        given_source = args.source
        build_options = inhelp.extract_build_options(args)
        installation_options = inhelp.extract_installation_options(args)
        app_source = inhelp.extract_app_source(
            given_source, build_options, args.asset_pattern, runtime
        )

        target_opts = inhelp.extract_targets(args)

        return InstallationRequest(
            app_source=app_source,
            targets=target_opts,
            installation_options=installation_options,
            build_options=build_options,
            manifest_path=args.manifest,
        )
