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


def get_dependency_operator(dependency_specifier):
    illegal_chars = "/:@"
    if any(char in dependency_specifier for char in illegal_chars):
        raise ValueError("can't handle complex dependency specifiers")
    if ";" in dependency_specifier:
        dependency_specifier = dependency_specifier.split(";")[0]
    invalid_operators = ("<=", "<", "!=", ">=", ">")
    if any(op in dependency_specifier for op in invalid_operators):
        raise ValueError("no pinned version specified")
    valid_operators = ("==", "~=", "===")
    operators = re.findall("|".join(valid_operators), dependency_specifier)
    if not operators:
        raise ValueError("no version specified")
    elif len(operators) != 1:
        raise ValueError("can't handle complex dependency specifiers")
    return operators[0]


def get_dependencies_groups(pyproject_data):
    """Map each dependency group name to a list of dependency specifiers"""
    main_dependency_specifiers = list(pyproject_data["project"].get("dependencies", []))
    dependency_groups = dict(pyproject_data["project"].get("optional-dependencies", {}))
    if main_dependency_specifiers:
        dependency_groups.update({".": main_dependency_specifiers})
    if not dependency_groups:
        raise ValueError("no dependencies found")
    return dependency_groups


def update_dependency(dependency_specifier, operator):
    dep_name = dependency_specifier.replace(" ", "").split(operator)[0]
    new_dep_version = fetch_latest_package_version(dep_name)
    updated_dependency_specifier = None
    if new_dep_version is not None:
        if ";" in dependency_specifier:
            after_semi = "".join(dependency_specifier.split(";")[1:])
            updated_dependency_specifier = f"{dep_name}{operator}{new_dep_version};{after_semi}"
        else:
            updated_dependency_specifier = f"{dep_name}{operator}{new_dep_version}"
    return updated_dependency_specifier


def update_dependencies(dependency_specifiers):
    updated_dependency_specifiers = []
    for dependency_specifier in dependency_specifiers:
        try:
            operator = get_dependency_operator(dependency_specifier)
        except ValueError as e:
            print(f"not updating: '{dependency_specifier}' ({e})")
            updated_dependency_specifiers.append(dependency_specifier)
            continue
        updated_dependency_specifier = update_dependency(dependency_specifier, operator)
        if updated_dependency_specifier is not None:
            if dependency_specifier != updated_dependency_specifier:
                print(f"updating: '{dependency_specifier}' to '{updated_dependency_specifier}'")
                updated_dependency_specifiers.append(updated_dependency_specifier)
            else:
                print(f"not updating: '{dependency_specifier}' (no new version available)")
                updated_dependency_specifiers.append(dependency_specifier)
        else:
            print(f"not updating: '{dependency_specifier}' (error retrieving version from pypi.org)")
            updated_dependency_specifiers.append(dependency_specifier)
    return updated_dependency_specifiers


def fetch_latest_package_version(package_name):
    match = re.match(r"^([^\[]+)\[.*\]$", package_name)
    if match:
        package_name = match.group(1)
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


def run(pyproject_toml_path):
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
            dependency_group_map = get_dependencies_groups(pyproject_data)
        except ValueError as e:
            exit(e)
        updated_dependency_group_map = {
            dependency_group: update_dependencies(dependency_specifiers)
            for dependency_group, dependency_specifiers in dependency_group_map.items()
        }
        for dependency_group, dependency_specifiers in updated_dependency_group_map.items():
            if dependency_group == ".":
                pyproject_data["project"]["dependencies"] = dependency_specifiers
            else:
                pyproject_data["project"]["optional-dependencies"][dependency_group] = dependency_specifiers
        with open(pyproject_toml_path, "w") as f:
            tomlkit.dump(pyproject_data, f)
        print("\ngenerated new pyproject.toml with updated dependencies")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--path",
        default=os.path.join(os.getcwd(), "pyproject.toml"),
        help="path to pyproject.toml",
    )
    args = parser.parse_args()
    run(args.path)


if __name__ == "__main__":
    main()
