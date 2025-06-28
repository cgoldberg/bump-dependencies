# bump-dependencies

## Python - bump your package dependencies

*Update pinned dependency specifiers in `pyproject.toml` to latest versions*

---

- Copyright (c) 2015-2025 [Corey Goldberg][github-home]
- Development: [GitHub][github-repo]
- Download/Install: [PyPI][pypi-bump-dependencies]
- License: [MIT][mit-license]

----

## About:

Generates a new pyproject.toml file with updated package dependencies.

Updates dependency specifiers listed in:

- `dependencies` list from `[project]` section
- dependency lists from `[project.optional-dependencies]` section
- dependency lists from `[dependency-groups]` section

----

- won't touch < or <= or > or >= or !=
- only == or ~= or ===
- doesn't handle all dependency specifiers supported by PEP508

## Usage:

```
usage: bump_dependencies [-h] [--dry_run] [--path PATH]

options:
  -h, --help   show this help message and exit
  --dry_run    don't write changes to pyproject.toml
  --path PATH  path to pyproject.toml (defaults to current directory)
```

[github-home]: https://github.com/cgoldberg
[github-repo]: https://github.com/cgoldberg/bump-dependencies
[pypi-bump-dependencies]: https://pypi.org/project/bump-dependencies
[mit-license]: https://raw.githubusercontent.com/cgoldberg/bump-dependencies/refs/heads/master/LICENSE
[pep-508]: https://peps.python.org/pep-0508
[pep-735]: https://peps.python.org/pep-0735
[pypa-dependency-specifiers]: https://packaging.python.org/en/latest/specifications/dependency-specifiers
[pypa-pyproject-dependencies]: https://packaging.python.org/en/latest/specifications/pyproject-toml/#dependencies-optional-dependencies
[pypa-dependency-groups]: https://packaging.python.org/en/latest/specifications/dependency-groups
