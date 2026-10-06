"""Command to display details about a tracked application."""

import argparse
from dataclasses import dataclass

from net_install_manager.commands.base_command import BaseCommand
from net_install_manager.config.build_options import BuildOptions
from net_install_manager.core import errors
from net_install_manager.core.registry import Registry
from net_install_manager.runtime.runtime import Runtime
from net_install_manager.config import app_sources as aps


@dataclass
class AppDetailsArgs:
    """Arguments for the app details command."""

    app_name: str


class AppDetailsCommand(BaseCommand[AppDetailsArgs]):
    """Command to display details about a tracked application."""

    def execute(self, runtime: Runtime, args: AppDetailsArgs) -> None:
        registry = Registry(runtime)
        app = registry.get(args.app_name)
        if not app:
            raise errors.AppNotRegisteredError(args.app_name, runtime.registry_path)

        print(f"Details for application '{args.app_name}':")

        print(f"    Lib path:      {app.lib_dir}")
        print(f"    Version:       {app.installed_version}")
        print(f"    Binary:        {app.binary_name}")
        print(f"    Source binary: {app.source_binary_name}")

        print("    Source:")
        match app.app_source:
            case aps.CodeAppSource() as cs:
                print("        Source type: Local Code")
                print(f"        Path:          {cs.project_path}")
                AppDetailsCommand._print_build_options(cs.build_options)
            case aps.BuiltAppSource() as bs:
                print("        Source type: Built Artifact")
                print(f"        Path:          {bs.build_path}")
            case aps.GitCodeAppSource() as gs:
                print("        Source type: Git Code")
                print(f"        Clone URL:    {gs.clone_url}")
                print(f"        Ref:         {gs.ref}")
                print(f"        Subpath:     {gs.subpath}")
                AppDetailsCommand._print_build_options(gs.build_options)
                print(f"        Cache dir:   {gs.cache_dir}")
            case aps.GitHubReleaseAppSource() as rs:
                print("        Source type: GitHub Release")
                print(f"        Owner:         {rs.owner}")
                print(f"        Repo:          {rs.repo}")
                print(f"        Tag:           {rs.tag}")
                print(f"        Asset pattern: {rs.asset_pattern}")

    @staticmethod
    def register_command(subparsers: argparse._SubParsersAction) -> argparse.ArgumentParser:
        parser = subparsers.add_parser(
            "app-details", help="Display details about a tracked application."
        )
        parser.add_argument("app_name", type=str, help="Name of the application.")
        return parser

    @staticmethod
    def parse_arguments(runtime: Runtime, args: argparse.Namespace) -> AppDetailsArgs:
        return AppDetailsArgs(app_name=args.app_name)

    @staticmethod
    def _print_build_options(build_options: BuildOptions) -> None:
        """Print build options."""
        print("        Build Options:")
        print(f"            Debug mode:     {build_options.debug_mode}")
        print(f"            Self-contained: {build_options.self_contained}")
        print(f"            RID:            {build_options.runtime_identifier}")
