#!/usr/bin/env python
# Corey Goldberg, 2025
# License: MIT

"""Bump Python package dependencies in pyproject.toml"""

import argparse
import os
import re

import requests
import tomlkit
from rich.console import Console
from validate_pyproject import api as validate_pyproject_api
from validate_pyproject.errors import ValidationError


def get_dependency_name_and_operator(dependency_specifier):
    illegal_chars = ("/", ":", "@")
    if any(char in dependency_specifier for char in illegal_chars):
        raise ValueError("can't handle direct reference dependency specifiers")
    if ";" in dependency_specifier:
        dependency_specifier = dependency_specifier.split(";")[0]
    invalid_operators = ("!=", "<=", "<")
    for op in invalid_operators:
        if op in dependency_specifier:
            raise ValueError(f"skipping '{op}' version identifier")
    valid_operators = ("===", "==", "~=", ">=", ">")
    operators = re.findall("|".join(valid_operators), dependency_specifier)
    if not operators:
        raise ValueError("no version specified")
    elif len(operators) != 1:
        raise ValueError("can't handle complex dependency specifiers")
    operator = operators[0]
    dependency_name = dependency_specifier.replace(" ", "").split(operator)[0].strip()
    return dependency_name, operator


def get_dependencies_groups(pyproject_data):
    """Map each dependency group name to a list of dependency specifiers

    This includes:
        - `dependencies` list from `[project]` section
        - dependency lists from `[project.optional-dependencies]` section
        - dependency lists from `[dependency-groups]` section
    """
    groups = {}
    project_dependencies = list(pyproject_data["project"].get("dependencies", []))
    if project_dependencies:
        groups.update({"project": project_dependencies})
    optional_dependencies = dict(pyproject_data["project"].get("optional-dependencies", {}))
    if optional_dependencies:
        groups.update({"optional_dependencies": optional_dependencies})
    dependency_groups = dict(pyproject_data.get("dependency-groups", {}))
    if dependency_groups:
        groups.update({"dependency_groups": dependency_groups})
    if not groups:
        raise ValueError("no dependencies found")
    return groups


def update_dependency(dependency_specifier):
    dependency_name, operator = get_dependency_name_and_operator(dependency_specifier)
    new_dependency_version = fetch_latest_package_version(get_package_base_name(dependency_name))
    updated_dependency_specifier = None
    if new_dependency_version is not None:
        if ";" in dependency_specifier:
            after_semi = "".join(dependency_specifier.split(";")[1:])
            updated_dependency_specifier = f"{dependency_name}{operator}{new_dependency_version};{after_semi}"
        else:
            updated_dependency_specifier = f"{dependency_name}{operator}{new_dependency_version}"
    return updated_dependency_specifier


def update_dependencies(dependency_specifiers):
    updated_dependency_specifiers = []
    for dependency_specifier in dependency_specifiers:
        if isinstance(dependency_specifier, tomlkit.items.InlineTable):
            print(f"- skipping inline table: '{dependency_specifier}'")
            updated_dependency_specifiers.append(dependency_specifier)
            continue
        try:
            get_dependency_name_and_operator(dependency_specifier)
        except ValueError as e:
            print(f"- not updating: '{dependency_specifier}' ({e})")
            updated_dependency_specifiers.append(dependency_specifier)
            continue
        updated_dependency_specifier = update_dependency(dependency_specifier)
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


def get_package_base_name(package_name):
    match = re.match(r"^(.*?)\[", package_name)
    if match:
        return match.group(1).strip()
    return package_name.strip()


def fetch_latest_package_version(package_name):
    url = f"https://pypi.org/pypi/{package_name}/json"
    try:
        response = requests.get(url)
    except requests.exceptions.ConnectionError:
        print("error connecting to pypi.org")
        return None
    try:
        response.raise_for_status()  # raise an exception for bad status codes
    except requests.exceptions.HTTPError:
        return None
    return response.json()["info"]["version"]


def run(pyproject_toml_path, dry_run):
    console = Console()
    with console.status(""):
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
        try:
            dependencies_groups_map = get_dependencies_groups(pyproject_data)
        except ValueError as e:
            exit(e)

        for key, value in dependencies_groups_map.items():
            if key == "project":
                pyproject_data["project"]["dependencies"] = update_dependencies(value)
            if key == "optional_dependencies":
                pyproject_data["project"]["optional-dependencies"] = {
                    dependency_group: update_dependencies(dependency_specifiers)
                    for dependency_group, dependency_specifiers in value.items()
                }
            if key == "dependency_groups":
                pyproject_data["dependency-groups"] = {
                    dependency_group: update_dependencies(dependency_specifiers)
                    for dependency_group, dependency_specifiers in value.items()
                }

        if dry_run:
            print("\nnot writing new pyproject.toml with updated dependencies")
        else:
            with open(pyproject_toml_path, "w") as f:
                tomlkit.dump(pyproject_data, f)
            print("\ngenerated new pyproject.toml with updated dependencies")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        dest="dry_run",
        help="don't write changes to pyproject.toml",
    )
    parser.add_argument(
        "--path",
        default=os.path.join(os.getcwd(), "pyproject.toml"),
        help="path to pyproject.toml (defaults to current directory)",
    )
    args = parser.parse_args()
    run(args.path, args.dry_run)


if __name__ == "__main__":
    main()
