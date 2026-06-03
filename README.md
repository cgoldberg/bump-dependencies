# bump-dependencies

### Bump your Python package dependencies

*Update dependency specifiers in `pyproject.toml` to latest versions*

---

[![Supported Python Versions](https://img.shields.io/pypi/pyversions/bump-dependencies)](https://pypi.org/project/bump-dependencies)

- Copyright (c) 2025-2026 [Corey Goldberg][github-home]
- Development: [GitHub][github-repo]
- Download/Install: [PyPI][pypi-bump-dependencies]
- License: [MIT][mit-license]

----

## About:

`bump_dependencies` is a Python CLI program that generates a new packaging
configuration file (`pyproject.toml`) file with updated package dependencies.

- for more information on declaring dependencies in a configuration file, see the [PyPA pyproject.toml Spec][pypa-pyproject-dependencies]
- for more information on version specifiers, see [PEP 440][pep-440] and the [PyPA Version Specifiers Spec][pypa-version-specifiers]
- for more information on dependency specifiers, see [PEP 508][pep-508] and the [PyPA Dependency Specifiers Spec][pypa-dependency-specifiers]
- for more information on dependency groups, see [PEP 735][pep-735] and the [PyPA Dependency Groups Spec][pypa-dependency-groups]

## Requirements:

- Python 3.10+

## Installation:

Install from [PyPI][pypi-bump-dependencies]:

```
pip install bump-dependencies
```

## CLI Options:

```
usage: bump_dependencies [-h] [--dry-run] [--path PATH]

options:
  -h, --help   show this help message and exit
  --dry-run    don't write changes to pyproject.toml
  --path PATH  path to pyproject.toml (defaults to current directory)
```

## Usage:

#### Install from PyPI with pipx, Run:

```
pipx install bump-dependencies
bump_dependencies
```

#### Clone Repo, Create/Activate Virtual Environment, Install from Source, Run:

```
git clone git@github.com:cgoldberg/bump-dependencies.git
cd ./bump-dependencies
python3 -m venv venv
source venv/bin/activate
pip install .
bump_dependencies
```

## Example:

If your `pyproject.toml` contains this:

```
[project]
... some metadata ...
dependencies = ["matplotlib~=3.9", "requests==2.29.0"]

[project.optional-dependencies]
socks = ["PySocks>=1.5.6"]

[dependency-groups]
dev = ["black==23.9.1", "ruff==0.9.5"]
test = ["pytest>8", "pytest-mock>=3.11"]
```

It will update dependency specifiers to the latest versions available on [PyPI][pypi-home]:

```
[project]
... some metadata ...
dependencies = ["matplotlib~=3.10.3", "requests==2.32.4"]

[project.optional-dependencies]
socks = ["PySocks>=1.7.1"]

[dependency-groups]
dev = ["black==25.1.0", "ruff==0.12.1"]
test = ["pytest>8.4.1", "pytest-mock>=3.14.1"]
```

#### Which sections of `pyproject.toml` will be updated?

It will update dependency specifiers listed in various sections of `pyproject.toml`:

- `dependencies` list from `[project]` section
- dependency lists from `[project.optional-dependencies]` section
- dependency lists from `[dependency-groups]` section

#### Which dependency specifiers will be updated?

- will only update dependency specifiers with version identifier
  containing comparison operator: `==`, `===`, `~=`, `>`, `>=`
  - example:
    - `foo==1.0.0`
    - `foo~=1.0`
    - `foo>=1`
- will not update dependency specifiers with version identifier
  containing comparison operator: `<`, `<=`, `!=`
  - example:
    - `foo<2.0`
    - `foo>=1,<2`
    - `foo > 1.0, != 1.0.1`
- will not update unversioned dependency specifiers
  - example:
    - `foo`
    - `foo[bar]`
- will not update direct reference dependency specifiers
  - example:
    - `foo @ https://github.com/foo/foo/archive/1.0.0.zip`
    - `foo @ file:///builds/foo-1.0.0-py3-none-any.whl`

#### Supported comparison operators in version identifiers:

- `==` : version matching
- `===` : arbitrary equality
- `~=` : compatible release
- `>` : exclusive ordered comparison
- `>=` : inclusive ordered comparison

#### Unsupported comparison operators in version identifiers:

- `<` : exclusive ordered comparison
- `<=` : inclusive ordered comparison
- `!=` : version exclusion

[github-home]: https://github.com/cgoldberg
[github-repo]: https://github.com/cgoldberg/bump-dependencies
[pypi-home]: https://pypi.org
[pypi-bump-dependencies]: https://pypi.org/project/bump-dependencies
[mit-license]: https://raw.githubusercontent.com/cgoldberg/bump-dependencies/refs/heads/main/LICENSE
[pep-440]: https://peps.python.org/pep-0440
[pep-508]: https://peps.python.org/pep-0508
[pep-735]: https://peps.python.org/pep-0735
[pypa-version-specifiers]: https://packaging.python.org/en/latest/specifications/version-specifiers
[pypa-dependency-specifiers]: https://packaging.python.org/en/latest/specifications/dependency-specifiers
[pypa-dependency-groups]: https://packaging.python.org/en/latest/specifications/dependency-groups
[pypa-pyproject-dependencies]: https://packaging.python.org/en/latest/specifications/pyproject-toml/#dependencies-optional-dependencies
