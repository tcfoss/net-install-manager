# Versioning

`ninman` supports multiple versions of the same application simultaneously. Therefore, it must be able to determine the version of each installation accurately.

Versions use semantic versioning, such as `1.2.3`, with optional prerelease or build metadata (for example, `1.2.3-rc.1`).


## Automatic Detection

When installing or upgrading, `ninman` chooses the version in this order:

1. Use `--version-override` if supplied.
2. Run the application binary with `--version` and parse a semantic version from its output.
3. If the source is a .NET project and the binary did not report a version, check the project file's `Version`, `PackageVersion`, and `AssemblyVersion` properties, in that order.

If none of these provide a valid version, the operation fails, and the `--version-override VERSION` option must be supplied.


## Overriding the Version

Use `--version-override VERSION` when the artifact does not report a version or when you want to assign a specific version:

```bash
ninman install ./publish --version-override 1.2.3
ninman upgrade my-app --version-override 1.2.3
```

The override takes precedence over both binary output and project metadata.
