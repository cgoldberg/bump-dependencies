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


def get_dependency_operator(dependency_specifier):
    operators = re.findall("==|~=|===", dependency_specifier)
    illegal_chars = " ',/:;@"
    if not operators:
        operator = None
    elif len(operators) != 1 or any(x in dependency_specifier for x in illegal_chars):
        print(f"not updating: {dependency_specifier} (can't handle complex dependency specifiers)")
        operator = None
    else:
        operator = operators[0]
    return operator


def get_dependencies_groups(data):
    """Map each dependency group name to a list of dependency specifiers"""
    main_dependency_specifiers = list(data["project"].get("dependencies", []))
    dependency_groups = dict(data["project"].get("optional-dependencies", {}))
    if main_dependency_specifiers:
        dependency_groups.update({".": main_dependency_specifiers})
    if not dependency_groups:
        raise ValueError("no dependencies found")
    return dependency_groups


def update_dependencies(dependency_specifiers):
    updated_dependency_specifiers = []
    for dependency_specifier in dependency_specifiers:
        operator = get_dependency_operator(dependency_specifier)
        if operator:
            dep_name = dependency_specifier.split(operator)[0]
            new_dep_version = fetch_latest_package_version(dep_name)
            if new_dep_version is not None:
                new_dependency_specifier = f"{dep_name}{operator}{new_dep_version}"
                if dependency_specifier != new_dependency_specifier:
                    print(f"updating: {dependency_specifier} to {new_dependency_specifier}")
                    updated_dependency_specifiers.append(new_dependency_specifier)
                else:
                    print(f"not updating: {dependency_specifier} (no new version available)")
                    updated_dependency_specifiers.append(dependency_specifier)
            else:
                print(f"not updating: {dependency_specifier} (error retrieving version from pypi.org)")
                updated_dependency_specifiers.append(dependency_specifier)
        else:
            print(f"not updating: {dependency_specifier} (no version specified)")
            updated_dependency_specifiers.append(dependency_specifier)
    return updated_dependency_specifiers


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


def run(pyproject_toml_path):
    console = Console()
    with console.status(""):
        print(f"reading {pyproject_toml_path}\n")
        try:
            with open(pyproject_toml_path) as f:
                data = tomlkit.load(f)
        except FileNotFoundError:
            exit("no pyproject.toml found. aborting")
        try:
            dependency_group_map = get_dependencies_groups(data)
        except ValueError as e:
            exit(e)
        updated_dependency_group_map = {
            dependency_group: update_dependencies(dependency_specifiers)
            for dependency_group, dependency_specifiers in dependency_group_map.items()
        }
        for dependency_group, dependency_specifiers in updated_dependency_group_map.items():
            if dependency_group == ".":
                data["project"]["dependencies"] = dependency_specifiers
            else:
                data["project"]["optional-dependencies"][dependency_group] = dependency_specifiers
        with open(pyproject_toml_path, "w") as f:
            tomlkit.dump(data, f)
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
