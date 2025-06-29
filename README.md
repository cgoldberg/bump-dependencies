# bump-dependencies

## Python - bump your package dependencies

*Update dependency specifiers in `pyproject.toml` to latest versions*

---

- Copyright (c) 2015-2025 [Corey Goldberg][github-home]
- Development: [GitHub][github-repo]
- Download/Install: [PyPI][pypi-bump-dependencies]
- License: [MIT][mit-license]

----

## About:

`bump_dependencies` is a Python CLI program that generates a new packaging
configuration file (`pyproject.toml`) file with updated package dependencies.

For example, it would update:

```
dependencies = ["pytest==8.2.0", "requests==2.30"]
```

to the latest versions on [PyPI][pypi-home]:

```
dependencies = ["pytest==8.4.1", "requests==2.32.4"]
```

It will update dependency specifiers listed in various sections of `pyproject.toml`:

- `dependencies` list from `[project]` section
- dependency lists from `[project.optional-dependencies]` section
- dependency lists from `[dependency-groups]` section

Which dependency specifiers will be updated?

- will only update dependency specifiers with version identifier
  containing comparison operator: `==`, `===`, `~=`, `>`, `>=`
  (i.e. `package==1.0.0`)
- will not update dependency specifiers with version identifier
  containing comparison operator: `<`, `<=`, `!=`
  (i.e. `package<1.0.0`)
- will not update complex dependency specifiers with version identifiers
  (i.e. `package ~=3.1.0, != 3.1.3`)
- will not update unversioned dependency specifiers
  (i.e. `package`)

Supported comparison operators in version identifiers:

`==` : version matching
`===` : arbitrary equality
`~=` : compatible release
`>` : exclusive ordered comparison
`>=` : inclusive ordered comparison

Unsupported comparison operators in version identifiers:

`<` : exclusive ordered comparison
`<=` : inclusive ordered comparison
`!=` : version exclusion

----

## Usage:

```
usage: bump_dependencies [-h] [--dry-run] [--path PATH]

options:
  -h, --help   show this help message and exit
  --dry-run    don't write changes to pyproject.toml
  --path PATH  path to pyproject.toml (defaults to current directory)
```

[github-home]: https://github.com/cgoldberg
[github-repo]: https://github.com/cgoldberg/bump-dependencies
[pypi-bump-dependencies]: https://pypi.org/project/bump-dependencies
[mit-license]: https://raw.githubusercontent.com/cgoldberg/bump-dependencies/refs/heads/master/LICENSE
[pypi-home]: https://pypi.org
[pep-440]: https://peps.python.org/pep-0440
[pep-508]: https://peps.python.org/pep-0508
[pep-735]: https://peps.python.org/pep-0735
[pypa-version-specifiers]: https://packaging.python.org/en/latest/specifications/version-specifiers
[pypa-dependency-specifiers]: https://packaging.python.org/en/latest/specifications/dependency-specifiers
[pypa-dependency-groups]: https://packaging.python.org/en/latest/specifications/dependency-groups
[pypa-pyproject-dependencies]: https://packaging.python.org/en/latest/specifications/pyproject-toml/#dependencies-optional-dependencies
