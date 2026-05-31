# Copyright (c) 2025-2026 Corey Goldberg
# License: MIT

"""Bump Python package dependencies in pyproject.toml."""

import argparse
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from venv import EnvBuilder

import requests
import requirements
import tomlkit
from packaging.requirements import InvalidRequirement
from packaging.specifiers import SpecifierSet
from packaging.version import InvalidVersion, Version
from rich.console import Console
from validate_pyproject import api as validate_pyproject_api
from validate_pyproject.errors import ValidationError


class Updater:
    def __init__(self, pyproject_toml_path=None):
        self.pyproject_toml_path = pyproject_toml_path
        self.pyproject_data = self.load() if pyproject_toml_path is not None else None
        self._dry_run = True
        self._force_latest = False
        self._py_version = None

    def get_dependency_name_and_operator(self, dependency_specifier):
        illegal_chars = ("/", ":", "@")
        if any(char in dependency_specifier for char in illegal_chars):
            raise ValueError(f"can't handle direct reference dependency specifier: '{dependency_specifier}'")
        try:
            list(requirements.parse(dependency_specifier))
        except InvalidRequirement:
            raise ValueError(f"skipping invalid dependency specifier: '{dependency_specifier}'")
        if ";" in dependency_specifier:
            dependency_specifier = dependency_specifier.split(";")[0]
        invalid_operators = ("!=", "<=", "<")
        for op in invalid_operators:
            if op in dependency_specifier:
                raise ValueError(f"skipping unsupported version identifier: '{op}'")
        valid_operators = ("===", "==", "~=", ">=", ">")
        operators = re.findall("|".join(valid_operators), dependency_specifier)
        if not operators:
            raise ValueError(f"no version specified: '{dependency_specifier}'")
        elif len(operators) != 1:
            raise ValueError(f"can't handle complex dependency specifier: '{dependency_specifier}'")
        operator = operators[0]
        dependency_name = dependency_specifier.replace(" ", "").split(operator)[0].strip()
        return dependency_name, operator

    def get_dependencies_groups(self):
        """Map each dependency group name to a list of dependency specifiers.

        This includes:
            - `dependencies` list from `[project]` section
            - dependency lists from `[project.optional-dependencies]` section
            - dependency lists from `[dependency-groups]` section
        """
        data = self.pyproject_data
        groups = {}
        project_dependencies = list(data["project"].get("dependencies", []))
        if project_dependencies:
            groups.update({"project": project_dependencies})
        optional_dependencies = dict(data["project"].get("optional-dependencies", {}))
        if optional_dependencies:
            groups.update({"optional-dependencies": optional_dependencies})
        dependency_groups = dict(data.get("dependency-groups", {}))
        if dependency_groups:
            groups.update({"dependency-groups": dependency_groups})
        if not groups:
            raise ValueError("no dependencies found")
        return groups

    def update_dependency(self, dependency_specifier):
        dependency_name, operator = self.get_dependency_name_and_operator(dependency_specifier)
        new_dependency_version = self.fetch_new_package_version(
            self.get_package_base_name(dependency_name))
        updated_dependency_specifier = None
        if new_dependency_version is not None:
            if ";" in dependency_specifier:
                after_semi = "".join(dependency_specifier.split(";")[1:])
                updated_dependency_specifier = f"{dependency_name}{operator}{new_dependency_version};{after_semi}"
            else:
                updated_dependency_specifier = f"{dependency_name}{operator}{new_dependency_version}"
        return updated_dependency_specifier

    def update_dependencies(self, dependency_specifiers):
        updated_dependency_specifiers = []
        for dependency_specifier in dependency_specifiers:
            if isinstance(dependency_specifier, tomlkit.items.InlineTable):
                print(f"- skipping inline table: '{dependency_specifier}'")
                updated_dependency_specifiers.append(dependency_specifier)
                continue
            try:
                self.get_dependency_name_and_operator(dependency_specifier)
            except ValueError as e:
                print(f"- not updating: '{dependency_specifier}' ({e})")
                updated_dependency_specifiers.append(dependency_specifier)
                continue
            updated_dependency_specifier = self.update_dependency(dependency_specifier)
            if updated_dependency_specifier is not None:
                if dependency_specifier != updated_dependency_specifier:
                    print(f"- updating: '{dependency_specifier}' to '{updated_dependency_specifier}'")
                    updated_dependency_specifiers.append(updated_dependency_specifier)
                else:
                    print(f"- not updating: '{dependency_specifier}' (no new version available)")
                    updated_dependency_specifiers.append(dependency_specifier)
            else:
                print(f"- not updating: '{dependency_specifier}' (error retrieving version from pypi.org)")
                updated_dependency_specifiers.append(dependency_specifier)
        return updated_dependency_specifiers

    def get_package_base_name(self, package_name):
        match = re.match(r"^(.*?)\[", package_name)
        if match:
            return match.group(1).strip()
        return package_name.strip()

    def fetch_new_package_version(self, package_name):
        url = f"https://pypi.org/pypi/{package_name}/json"
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
        except (requests.exceptions.ConnectionError, requests.exceptions.HTTPError):
            print("error connecting to pypi.org")
            return None
        data = response.json()
        if self._force_latest:
            return response.json()["info"]["version"]
        else:
            latest = None
            for version_str, files in data.get("releases", {}).items():
                try:
                    ver = Version(version_str)
                except InvalidVersion:
                    continue
                # skip pre-releases
                if ver.is_prerelease:
                    continue
                # check Requires-Python across release files
                compatible = False
                for f in files:
                    requires_python = f.get("requires_python")
                    if not requires_python:
                        compatible = True  # no constraint, assume compatible
                        continue
                    try:
                        if SpecifierSet(requires_python).contains(self._py_version):
                            compatible = True
                        else:
                            compatible = False
                            break
                    except Exception:
                        continue
                if compatible:
                    if latest is None or ver > latest:
                        latest = ver
            return str(latest) if latest else None

    def load(self):
        print(f"loading: {self.pyproject_toml_path}")
        try:
            with open(self.pyproject_toml_path) as f:
                pyproject_data = tomlkit.load(f)
        except FileNotFoundError:
            exit("\nno pyproject.toml found")
        except Exception as e:
            exit(f"\ninvalid pyproject.toml: {e}")
        print(f"validating: {os.path.basename(self.pyproject_toml_path)}\n")
        validator = validate_pyproject_api.Validator()
        try:
            validator(pyproject_data)
        except ValidationError as e:
            exit(f"invalid pyproject.toml: {e.message}")
        return pyproject_data

    def update(self, py_version=None, force_latest=False, dry_run=False):
        self._dry_run = dry_run
        self._force_latest = force_latest
        self._py_version = py_version or self._py_version
        try:
            dependencies_groups_map = self.get_dependencies_groups()
        except ValueError as e:
            exit(e)
        # update 'tomlkit.items` in-place to maintain the formatting from the original toml file
        for key, value in dependencies_groups_map.items():
            if key == "project":
                updated_deps = self.update_dependencies(value)
                dep_list = self.pyproject_data["project"]["dependencies"]
                for i in range(len(dep_list)):
                    dep_list[i] = updated_deps[i]
            if key == "optional-dependencies":
                dep_groups = self.pyproject_data["project"][key]
                for dep_group, dep_list in dep_groups.items():
                    updated_deps = self.update_dependencies(dep_list)
                    for i in range(len(dep_list)):
                        dep_list[i] = updated_deps[i]
            if key == "dependency-groups":
                dep_groups = self.pyproject_data[key]
                for dep_group, dep_list in dep_groups.items():
                    updated_deps = self.update_dependencies(dep_list)
                    for i in range(len(dep_list)):
                        dep_list[i] = updated_deps[i]

        if dry_run:
            print("\nnot writing new pyproject.toml with updated dependencies")
        else:
            with open(self.pyproject_toml_path, "w") as f:
                tomlkit.dump(self.pyproject_data, f)

        return self.pyproject_data

    def _install_in_venv(self, dependency_groups):
        """Installs all dependencies, optional-dependencies, and dependency-groups in a virtual env."""
        with TemporaryDirectory(prefix="venv_") as tmpdir:
            venv_dir = Path(tmpdir)
            builder = EnvBuilder(with_pip=True)
            context = builder.create(venv_dir)
            venv_python = Path(context.env_exe)
            try:
                group_args = [item for group in dependency_groups for item in ("--group", group)]
                cmd = [venv_python, "-m", "pip", "install", *group_args, ".[all]"]
                subprocess.run(
                    cmd,
                    check=True,
                )
                print("Packages installed successfully.")
            except Exception:
                shutil.rmtree(venv_dir)
                raise


def run(pyproject_toml_path, py_version, force_latest, dry_run):
    updater = Updater(pyproject_toml_path)
    console = Console()
    with console.status(""):
        pyproject_data = updater.update(py_version=py_version, force_latest=force_latest, dry_run=dry_run)
        return pyproject_data


def main():
    def formatter(prog):
        return argparse.HelpFormatter(prog, max_help_position=30)

    parser = argparse.ArgumentParser(formatter_class=formatter)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        dest="dry_run",
        help="don't write changes to pyproject.toml",
    )
    parser.add_argument(
        "--latest",
        action="store_true",
        help="always use latest available package versions",
    )
    parser.add_argument(
        "--path",
        default=str(Path.cwd() / "pyproject.toml"),
        help="path to pyproject.toml (defaults to current directory)",
    )
    parser.add_argument(
        "--py-version",
        dest="py_version",
        default=f"{sys.version_info.major}.{sys.version_info.minor}",
        help="python version for package compatibility",
    )
    args = parser.parse_args()
    if args.latest and args.py_version:
        parser.error("--latest and --py_version cannot be used together")
    run(pyproject_toml_path=args.path, dry_run=args.dry_run, py_version=args.py_version, force_latest=args.latest)
