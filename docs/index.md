# Welcome to .NET Installation Manager (`ninman`)


## Introduction

`.NET Installation Manager` (`ninman`) installs and manages versioned .NET console applications on Linux, macOS, and Windows. It can build a project from source, use a local published directory, build from a Git repository, or install an asset from a GitHub release.

Each application has a versioned installation and a launcher that points to its current version. Use `ninman upgrade` to install a newer version, `ninman rollback` to switch to an installed version, or `ninman prune` to remove older versions.


## Requirements

- Python 3.12 or newer to install `ninman`.
- The .NET SDK to install from a `.csproj` or Git source.
- Git to install from a remote Git repository.

Prebuilt directories and GitHub release assets do not need the .NET SDK. A GitHub token may be needed for private releases.


## Installing

The recommended way to install the CLI is with [pipx](https://pypa.github.io/pipx/):

```bash
pipx install net-install-manager
```

Then confirm it is available:

```bash
ninman --version
ninman --help
```

See [Installing Applications](installing.md) for source types and installation options, and [Installed Application Maintenance](maintaining.md) for upgrades, rollbacks, and cleanup.

By default, `ninman` manages applications for the current user. Add `--system` before any subcommand to manage system-wide installations; this requires administrator privileges. Ensure the installation's launcher directory is on `PATH` (`~/.local/bin` for a user install on Linux/macOS, or `%USERPROFILE%\.local\bin` for a user install on Windows). If you have successfully installed and invoked `pipx`, your path should already be correct.
