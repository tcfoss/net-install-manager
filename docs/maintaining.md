# Installed Application Maintenance
Applications installed by `ninman` are tracked in a local registry. The commands below take the application name shown by `list-apps`.

## Listing Applications and Their Versions

List all tracked applications:

```bash
ninman list-apps
```

Show the installed versions of an application. The current version is marked, and the default order is newest first:

```bash
ninman list-versions my-app
ninman list-versions my-app --reverse
```

Use `ninman app-details my-app` to inspect its install path, current version, and original source.

## Upgrading Applications

Upgrade a tracked application from its recorded source:

```bash
ninman upgrade my-app
```

For a Git source, `--new-ref` selects a different ref for the upgrade. For a GitHub release source, `--new-release-tag` selects a release tag; omit the value to return to the latest release. `--version-override` supplies a version when automatic detection is unsuitable; see [Versioning](versioning.md) for the detection rules. `--force` allows overwriting an already-installed version, and `--token` authenticates to private sources.

```bash
ninman upgrade my-app --new-ref main
ninman upgrade my-app --new-release-tag v2.0.0
```

## Removing Versions of an Application

Use `rollback` to make an already-installed version current without downloading it:

```bash
ninman rollback my-app 1.2.0
```

To delete old version directories, prune all but the newest requested number:

```bash
ninman prune my-app --keep-latest 3
```

Or prune versions outside a range. Use at least one bound; versions below `--min-version` or above `--max-version` are removed:

```bash
ninman prune my-app --min-version 1.2.0 --max-version 2.0.0
```

If pruning removes the current version, `ninman` asks before switching to the newest version that remains. Pass `--yes` (or `-y`) to confirm automatically. The command will not remove every installed version.

## Uninstalling an Application Completely

Uninstall removes the application's managed files, all installed versions, its launcher, and its registry entry. It prompts for confirmation unless `--yes`/`-y` is supplied:

```bash
ninman uninstall my-app
ninman uninstall my-app --yes
```

Use `--system` before the subcommand for applications installed system-wide; administrator privileges are required:

```bash
ninman --system list-apps
ninman --system upgrade my-app
ninman --system uninstall my-app --yes
```

