# Copyright (c) 2025-2026 Corey Goldberg
# License: MIT

"""Bump Python package dependencies in pyproject.toml."""

import argparse
import os
import re
import sys
from copy import deepcopy
from pathlib import Path

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
        self._requires_python_spec = None
        self._dry_run = True
        self._force_latest = False

    @property
    def requires_python_spec(self):
        if self._requires_python_spec is not None:
            return self._requires_python_spec
        if not self.pyproject_data:
            return None
        try:
            return self.pyproject_data["project"]["requires-python"]
        except KeyError:
            raise KeyError("could not find 'project.requires-python' in pyproject.toml")

    @requires_python_spec.setter
    def requires_python_spec(self, value):
        self._requires_python_spec = value

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
            self.get_package_base_name(dependency_name), force_latest=self._force_latest
        )
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

    def _extract_bounds(self, spec):
        """Convert a SpecifierSet into inclusive lower/upper bounds.

        Supports the common requires-python forms:
            >=3.8
            >3.8
            <4
            <=3.12
            >=3.8,<4

        This is not fully PEP 440 correct. It handles the overwhelming majority of real-world requires-python values,
        but it does not correctly model exclusions such as: >=3.8,<4,!=3.9.*
        """
        min_ver = None
        max_ver = None
        for s in spec:
            if s.operator == "!=":
                continue
            if "*" in s.version:
                continue
            v = Version(s.version)
            if s.operator in (">=", ">"):
                min_ver = v if min_ver is None else max(min_ver, v)
            elif s.operator in ("<=", "<"):
                max_ver = v if max_ver is None else min(max_ver, v)
            elif s.operator == "==":
                min_ver = v
                max_ver = v
        return min_ver, max_ver

    def _intersects(self, spec_a, spec_b):
        """Check if if the two SpecifierSets have any possible overlap."""
        a_min, a_max = self._extract_bounds(spec_a)
        b_min, b_max = self._extract_bounds(spec_b)
        lower = max(
            (v for v in (a_min, b_min) if v is not None),
            default=None,
        )
        upper = min(
            (v for v in (a_max, b_max) if v is not None),
            default=None,
        )
        if lower is not None and upper is not None and lower > upper:
            return False
        return True

    def _compatible(self, requires_python, user_spec):
        """Check if requires-python constraint overlaps with the user's constraint."""
        if not requires_python:
            return True
        pkg_spec = SpecifierSet(requires_python)
        return self._intersects(user_spec, pkg_spec)

    def fetch_new_package_version(self, package_name, force_latest=False):
        url = f"https://pypi.org/pypi/{package_name}/json"
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
        except requests.exceptions.ConnectionError:
            sys.exit("error connecting to pypi.org")
        except requests.exceptions.HTTPError:
            return None
        data = response.json()
        if force_latest:
            return data["info"]["version"]
        requires_python_spec = self.requires_python_spec
        try:
            user_spec = SpecifierSet(requires_python_spec)
        except Exception as e:
            sys.exit(f"invalid requires-python specifier '{requires_python_spec}': {e}")
        for ver_str in sorted(data.get("releases", {}), key=Version, reverse=True):
            try:
                ver = Version(ver_str)
            except InvalidVersion:
                continue
            if ver.is_prerelease:
                continue
            files = data["releases"].get(ver_str, [])
            if not files:
                continue
            compatible = False
            for file_info in files:
                release_requires = file_info.get("requires_python")
                if not release_requires:
                    compatible = True
                    break
                try:
                    SpecifierSet(release_requires)
                except Exception as e:
                    sys.exit(f"invalid requires-python specifier in {package_name} {ver}: '{release_requires}': {e}")
                if self._compatible(release_requires, user_spec):
                    compatible = True
                    break
            if compatible:
                return str(ver)
        return None

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

    def update(self, force_latest=False, dry_run=True):
        self._dry_run = dry_run
        self._force_latest = force_latest
        try:
            dependencies_groups_map = self.get_dependencies_groups()
        except Exception as e:
            sys.exit(e)
        pyproject_data = deepcopy(self.pyproject_data)
        # update 'tomlkit.items` in-place to maintain the formatting from the original toml file
        for key, project_dependencies in dependencies_groups_map.items():
            if key == "project":
                updated_deps = self.update_dependencies(project_dependencies)
                dep_list = pyproject_data["project"]["dependencies"]
                for i in range(len(dep_list)):
                    dep_list[i] = updated_deps[i]
            if key == "optional-dependencies":
                dep_groups = pyproject_data["project"][key]
                for dep_group, dep_list in dep_groups.items():
                    updated_deps = self.update_dependencies(dep_list)
                    for i in range(len(dep_list)):
                        dep_list[i] = updated_deps[i]
            if key == "dependency-groups":
                dep_groups = pyproject_data[key]
                for dep_group, dep_list in dep_groups.items():
                    updated_deps = self.update_dependencies(dep_list)
                    for i in range(len(dep_list)):
                        dep_list[i] = updated_deps[i]
        if pyproject_data == self.pyproject_data:
            print("\nno dependency updates needed. not writing new pyproject.toml.")
        else:
            if dry_run:
                print("\ndry-run enabled. not generating new pyproject.toml with updated dependencies")
            else:
                with open(self.pyproject_toml_path, "w") as f:
                    tomlkit.dump(self.pyproject_data, f)
                print("\ngenerated new pyproject.toml with updated dependencies")
        return self.pyproject_data


def run(pyproject_toml_path, force_latest, dry_run):
    updater = Updater(pyproject_toml_path)
    console = Console()
    with console.status(""):
        pyproject_data = updater.update(force_latest, dry_run)
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
    args = parser.parse_args()
    run(pyproject_toml_path=args.path, force_latest=args.latest, dry_run=args.dry_run)
