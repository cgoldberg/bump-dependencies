# Copyright (c) 2025-2026 Corey Goldberg
# License: MIT

"""Bump Python package dependencies in pyproject.toml."""

import argparse
import os
import re
import sys

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
    def __init__(self, pyproject_toml_path, force_latest=False):
        self.pyproject_toml_path = pyproject_toml_path
        self.force_latest = force_latest
        self.pyproject_data = self.load(pyproject_toml_path)

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
        new_dependency_version = self.fetch_new_package_version(self.get_package_base_name(dependency_name))
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
        if self.force_latest:
            return response.json()["info"]["version"]
        else:
            current_py = f"{sys.version_info.major}.{sys.version_info.minor}"
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
                        if SpecifierSet(requires_python).contains(current_py):
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

    def load(self, pyproject_toml_path):
        print(f"loading: {pyproject_toml_path}")
        try:
            with open(pyproject_toml_path) as f:
                pyproject_data = tomlkit.load(f)
        except FileNotFoundError:
            exit("\nno pyproject.toml found")
        except Exception as e:
            exit(f"\ninvalid pyproject.toml: {e}")
        print(f"validating: {os.path.basename(pyproject_toml_path)}\n")
        validator = validate_pyproject_api.Validator()
        try:
            validator(pyproject_data)
        except ValidationError as e:
            exit(f"invalid pyproject.toml: {e.message}")
        return pyproject_data

    def run(self):
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
        return self.pyproject_data


def run(pyproject_toml_path, force_latest, dry_run):
    console = Console()
    with console.status(""):
        updater = Updater(pyproject_toml_path, force_latest)
        pyproject_data = updater.run()
        if dry_run:
            print("\nnot writing new pyproject.toml with updated dependencies")
        else:
            with open(pyproject_toml_path, "w") as f:
                tomlkit.dump(pyproject_data, f)
            print("\ngenerated new pyproject.toml with updated dependencies")
        return pyproject_data


def main():
    parser = argparse.ArgumentParser()
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
        default=os.path.join(os.getcwd(), "pyproject.toml"),
        help="path to pyproject.toml (defaults to current directory)",
    )
    parser.add_argument(
        "--py-version",
        dest="py_version",
        default=f"{sys.version_info.major}.{sys.version_info.minor}",
        help="python version for package compatibility",
    )
    args = parser.parse_args()
    run(pyproject_toml_path=args.path, force_latest=args.latest, dry_run=args.dry_run)
