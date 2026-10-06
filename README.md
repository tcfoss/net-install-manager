# Net Install Manager (`ninman`)

`ninman` installs and manages versioned .NET console applications on Linux, macOS, and Windows. It can build from a project or Git repository, install local or GitHub release artifacts, and manage upgrades, rollbacks, and cleanup.

**Documentation:** [tcfoss.github.io/net-install-manager](https://tcfoss.github.io/net-install-manager/)

## Install

Requires Python 3.12 or newer. The .NET SDK is needed to install from project source; Git is needed for remote Git sources.

```bash
pipx install net-install-manager
```

## Quick Start

```bash
ninman install ./src/MyApp/MyApp.csproj
ninman list-apps
ninman upgrade myapp
ninman rollback myapp 1.1.0
```

See the [installation guide](https://tcfoss.github.io/net-install-manager/installing/) for source formats and manifests, and the [maintenance guide](https://tcfoss.github.io/net-install-manager/maintaining/) for version management and uninstalling.
