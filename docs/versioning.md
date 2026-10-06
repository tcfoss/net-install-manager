# Versioning

`ninman` stores each installation under a semantic version and uses that version to track the current installation, list versions, roll back, and prune old files.

## Automatic Detection

When installing or upgrading, `ninman` chooses the version in this order:

1. Use `--version-override` if supplied.
2. Run the application binary with `--version` and parse a semantic version from its output. For a `.dll`, `ninman` runs `dotnet <file>.dll --version`.
3. If the source is a .NET project and the binary did not report a version, check the project file's `Version`, `PackageVersion`, and `AssemblyVersion` properties, in that order.

If none of these provide a version, the operation fails. Prebuilt artifacts should report a version through `--version` or use `--version-override`. Project metadata is only available when installing from a project source.

Versions use semantic versioning, such as `1.2.3`, with optional prerelease or build metadata (for example, `1.2.3-rc.1`).

## Overriding the Version

Use `--version-override` when the artifact does not report a version or when you want to assign a specific version:

```bash
ninman install ./publish --version-override 1.2.3
ninman upgrade my-app --version-override 1.2.3
```

The override takes precedence over both binary output and project metadata.

## Git Refs and GitHub Release Tags

A Git ref or GitHub release tag selects source content; it does not directly set the installed application version. For Git source installs and upgrades, the version is still detected from the built binary and then the project file. For GitHub release assets, it is detected from the binary; there is no project-file fallback. Use `--version-override` if that asset does not report its version.

For GitHub release asset matching, the `{version}` asset-pattern placeholder is substituted from the release tag when that tag contains a semantic version. This is separate from the version assigned to the installed application.
