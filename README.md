# bump-deps

- Corey Goldberg, 2025
- License: MIT

## Generates a new pyproject.toml file with updated package dependencies.

- won't touch < or <= or > or >= or !=
- only == or ~= or ===
- doesn't handle all dependency specifiers supported by PEP508

# Usage:
```
usage: bump_deps [-h] [--path PATH]

options:
  -h, --help   show this help message and exit
  --path PATH  path to pyproject.toml
```
(if no path is specified, pyproject.toml in the current directory is used)
