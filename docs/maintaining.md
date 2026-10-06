# Installed Application Maintenance

Applications installed by `ninman` are tracked in a local registry. The commands below take the application name shown by `list-apps`.


## Listing Applications

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

For a Git source, `--new-ref` selects a different ref for the upgrade. Supply the flag with no value to switch to the repository's default ref (usually the `main` or `master` branch).

For a GitHub release source, `--new-release-tag` selects a release tag. Use the flag with no value to switch to the latest release. If the releases are private, supply `--token TOKEN` or set one of `NINMAN_GITHUB_TOKEN`, `GITHUB_TOKEN`, or `GH_TOKEN`.

If automatic version detection is unsuitable, supply `--version-override VERSION`; see [Versioning](versioning.md) for details. The `--force` flag allows overwriting an already-installed version.

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

If pruning removes the current version, `ninman` asks before switching to the newest version that remains. Pass `--yes` (or `-y`) to confirm automatically. At least one version must remain at the end of pruning.


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

