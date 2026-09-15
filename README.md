# Net Install Manager (`ninman`)

A CLI tool (installable via `pipx`) for managing installations, rollbacks, versioning, and uninstallation of .NET console applications across Linux, macOS, and Windows.

## Features

- **Source, Pre-compiled & Git Support**: Install directly from `.csproj` source, pre-compiled binaries (DLLs/EXEs), or remote Git/GitHub repositories.
- **Cross-Platform**:
  - **Linux / macOS**: Installs to `~/.local/lib/<app>/<version>` (or `/usr/local/lib` for system), atomic `current` symlinks, and launchers in `~/.local/bin`.
  - **Windows**: Installs to `%LOCALAPPDATA%\<app>\versions\<version>` (or `Program Files` for system), `current` directory junctions, and `.cmd` + bash launchers in `bin/`.
- **Version Management & Rollback**: Automatic version detection (csproj, git tags, binary `--version`), version regression checks, rollback to previous versions, and version pruning (`--versions-to-keep`).
- **Application Registry & Upgrades**: Track installed applications and upgrade them directly (`ninman upgrade <app>` or `ninman upgrade --all`), including fetching the latest Git commits/tags.

## Installation

```bash
pipx install net-install-manager
```

## CLI Usage

```bash
# Install from a local .csproj file or current directory
ninman install
ninman install ./src/MyApp/MyApp.csproj
ninman install ./dist/MyApp-v1.2.0

# Install directly from GitHub / Git repository
ninman install https://github.com/owner/repo.git
ninman install owner/repo
ninman install owner/repo@v1.2.0

# Install a prebuilt asset from a GitHub release
ninman install-release owner repo --asset-pattern "{rid}-{version}"

# Multi-project repositories: select a specific project via subpath or --project
ninman install https://github.com/owner/repo.git --project src/CliApp/CliApp.csproj
ninman install https://github.com/owner/repo/tree/main/src/CliApp
ninman install owner/repo#src/CliApp

# Install as self-contained with version pruning
ninman install --self-contained --versions-to-keep 3

# Force installation / reinstallation of older version
ninman install --force --app-version 1.0.0

# List installed versions
ninman list-versions

# List all tracked applications managed by ninman
ninman list-apps

# Upgrade an application or all tracked applications
ninman upgrade
ninman upgrade myapp
ninman upgrade --all

# Rollback to the previous version
ninman rollback --previous

# Rollback to a specific version
ninman rollback --target-version 1.1.0

# Uninstall a specific version or everything
ninman uninstall --target-version 1.0.0
ninman uninstall --all
```

GitHub release installations discover `ninman.yml`, `ninman.yaml`, or a `.csproj` from the
unpacked release asset. Private repositories can use `NINMAN_GITHUB_TOKEN`, `GITHUB_TOKEN`, or
`GH_TOKEN`; tokens are used for requests only and are not stored in the application registry.

## Configuration (`ninman.yaml`)

```yaml
app_directory: my-app
binary_name: myapp
source_binary_name: MyApp.dll # or MyApp.exe
csproj_path: src/MyApp/MyApp.csproj # optional
```
