# Contributing

## Testing

Run the test suite with line and branch coverage using the Poetry development environment:

```bash
poetry run pytest --cov=net_install_manager --cov-branch --cov-report=term-missing
```

Tests isolate registries, installations, and caches in temporary directories. Platform-policy tests
exercise both Windows and POSIX configurations on either host; native POSIX permissions and
symlink tests are skipped on Windows and run on POSIX hosts.
