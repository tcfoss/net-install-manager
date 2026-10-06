from pathlib import Path

import pytest

from net_install_manager.core import errors


@pytest.mark.parametrize(
    ("error_type", "args", "attributes", "message"),
    [
        (
            errors.AppNotRegisteredError,
            ("sample", Path("/config/apps.yaml")),
            {"app_name": "sample", "registry_path": Path("/config/apps.yaml")},
            "sample",
        ),
        (
            errors.AppAlreadyInstalledError,
            ("sample", Path("/install/sample")),
            {"app_name": "sample", "installation_path": Path("/install/sample")},
            "--force",
        ),
        (
            errors.VersionAlreadyInstalledError,
            ("sample", "1.0.0", Path("/install/sample")),
            {
                "app_name": "sample",
                "version": "1.0.0",
                "installation_path": Path("/install/sample"),
            },
            "1.0.0",
        ),
        (
            errors.InstallationDirectoryNotFoundError,
            ("sample", Path("/install/sample")),
            {"app_name": "sample", "installation_path": Path("/install/sample")},
            "not found",
        ),
        (
            errors.MultipleCsprojFilesError,
            (Path("/src"), [Path("/src/A.csproj"), Path("/src/B.csproj")]),
            {
                "directory": Path("/src"),
                "csproj_files": [Path("/src/A.csproj"), Path("/src/B.csproj")],
            },
            "A.csproj",
        ),
        (
            errors.InvalidSourceError,
            (Path("/src"),),
            {"source": Path("/src")},
            "Invalid source",
        ),
        (
            errors.UnresolvedTargetError,
            ("binary_name",),
            {"target_name": "binary_name"},
            "binary_name",
        ),
        (
            errors.UnresolvedVersionError,
            ("sample",),
            {"app_name": "sample"},
            "version-override",
        ),
        (
            errors.AmbiguousSourceError,
            ("owner:repo",),
            {"source": "owner:repo"},
            "Ambiguous source",
        ),
        (
            errors.GitBranchError,
            ("https://example.com/repo.git",),
            {"clone_url": "https://example.com/repo.git"},
            "default branch",
        ),
    ],
)
def test_domain_errors_keep_context_and_useful_messages(error_type, args, attributes, message):
    error = error_type(*args)

    assert isinstance(error, errors.BaseNinmanError)
    assert message in str(error)
    for attribute, expected in attributes.items():
        assert getattr(error, attribute) == expected
