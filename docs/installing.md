# Installing Applications

## Application Names

The names you choose determine both the installed files and the command users run. `binary_name` is the launcher command, `source_binary_name` is the executable or DLL in the artifact, and `app_dir_name` is the installation directory name.

For .NET projects, `ninman` derives all three from the assembly name. It lowercases the launcher name and replaces dots with dashes, so an assembly named `Company.Product.CliApp` produces the command `company-product-cliapp`. Set `--binary-name` to choose a shorter or more convenient command, such as `dbman` or `myapp`.

Prebuilt directories and GitHub release assets have no project metadata to infer these names from. Unless the artifact contains a manifest, provide all three options:

```bash
ninman install ./dist/MyApp \
	--binary-name myapp \
	--source-binary-name MyApp.dll \
	--app-dir-name MyApp
```


## Choosing an Install Source

`ninman install` accepts an optional source. With no source, it uses the current directory. A source directory containing exactly one `.csproj` is built; a directory with no project file is treated as prebuilt files. Directories containing multiple project files are ambiguous and must be narrowed to a project file or project directory.

```bash
ninman install ./src/MyApp/MyApp.csproj
ninman install
```

The .NET SDK must be installed to build projects. When building locally or from Git, `ninman` uses a Release build by default.


## Source Types

### Local .NET Projects

Pass a `.csproj` file or a directory containing exactly one `.csproj`. A project can also be discovered in the current directory:

```bash
ninman install ./src/MyApp/MyApp.csproj
ninman install ./src/MyApp
```

The app name and source binary are inferred from the project assembly name. For the version detection order and how to set `--version-override`, see [Versioning](versioning.md).

### GitHub Releases

Use `owner:repo` to select the latest release, or `owner:repo:tag` to select a specific release. `ninman` needs to select a single release asset to download. If a release contains multiple assets, supply `--asset-pattern` to narrow the selection; it is a regular expression matched against asset names. The default pattern is `{rid}-{version}`. `{rid}`, `{os}`, `{arch}`, and `{version}` are substituted before matching, and exactly one asset must match. If the release has exactly one asset, you can use `--asset-pattern '.*'` to match it.

If the release archive does not contain a manifest, pass the three naming options shown above. For example, when the release has exactly one asset:

```bash
ninman install octocat:my-app \
	--asset-pattern '.*' \
	--binary-name myapp \
	--source-binary-name MyApp.dll \
	--app-dir-name MyApp

ninman install octocat:my-app:v1.2.0 \
	--asset-pattern 'my-app-{version}.*\.tar\.gz' \
	--binary-name myapp \
	--source-binary-name MyApp.dll \
	--app-dir-name MyApp
```

For private releases, pass `--token TOKEN` or set one of `NINMAN_GITHUB_TOKEN`, `GITHUB_TOKEN`, or `GH_TOKEN`. Tokens are used for requests and are not stored in the registry.

A `ninman.yaml`/`ninman.yml` manifest inside the release asset can supply application naming information. Release assets are selected by matching their names, so choose a pattern that uniquely identifies the asset for this operating system and architecture.

### Remote Git Repositories

Pass a Git URL or GitHub shorthand. Optional `@ref` selects a branch, tag, or commit; optional `#subpath` selects a project within the repository. GitHub tree URLs are also accepted.

```bash
ninman install https://github.com/owner/repo.git
ninman install owner/repo@v1.2.0
ninman install owner/repo#src/MyApp
ninman install https://github.com/owner/repo/tree/main/src/MyApp
```

The selected subpath can be a `.csproj` file or a directory containing exactly one project. Without a subpath, `ninman` searches the repository for a project. The repository is cached locally and refreshed when it is used again.

### Local Published Applications

Pass a directory of prebuilt application files. `ninman` copies the directory into its versioned installation and requires the source binary name and version to be identifiable. Use `--source-binary-name` if the executable/DLL name cannot be inferred. See [Versioning](versioning.md) for how version detection works and when to use `--version-override`.

```bash
ninman install ./publish \
	--binary-name myapp \
	--source-binary-name MyApp.dll \
	--app-dir-name MyApp \
	--version-override 1.2.0
```

## Common Options

```bash
# Build as a self-contained app for a specific .NET Runtime Identifier
ninman install ./src/MyApp/MyApp.csproj --self-contained --rid linux-x64

# Build in Debug configuration
ninman install ./src/MyApp/MyApp.csproj --debug

# Force an installation even when the app is already registered
ninman install ./src/MyApp/MyApp.csproj --force

# Install for all users (requires administrator privileges)
ninman --system install ./src/MyApp/MyApp.csproj
```

Other install options include `--version-override` (see [Versioning](versioning.md)), `--exclude-patterns`, `--target-permissions`, and `--prefer-opt` (system installs on POSIX systems). Run `ninman install --help` for the complete option list.

## Manifest

A `ninman.yaml` or `ninman.yml` manifest can provide names for prebuilt directories and release assets. Select a manifest explicitly with `--manifest path/to/ninman.yaml`, or place it in the artifact directory. Command-line naming options take precedence over manifest values.

```yaml
binary_name: myapp
source_binary_name: MyApp.dll
app_dir_name: MyApp
```