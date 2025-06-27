#!/usr/bin/env python
#
# This script generates a new pyproject.toml file with updated package dependencies.
# won't touch < or <= or > or >= or !=
# Doesn't handle all dependency specifiers supported by PEP508

# Usage: `./bump_requirements --dir /path/to/pyproject.toml`
# (if no path is specified, pyproject.toml in the current directory is used)


import argparse
import os
import platform
import re
import shutil
import subprocess
import venv

import tomlkit
from rich.console import Console


def get_dependency_operator(dependency_specifier):
    operators = re.findall("==|~=|===", dependency_specifier)
    illegal_chars = " ',/:;@"
    if not operators:
        operator = None
    elif len(operators) != 1 or any(x in dependency_specifier for x in illegal_chars):
        print(f"can't handle complex dependency specifiers. not updating: {dependency_specifier}")
        operator = None
    else:
        operator = operators[0]
    return operator


def get_dependencies_groups(data):
    dependency_specifiers = data["project"].get("dependencies", [])
    optional_dependency_groups = list(data["project"].get("optional-dependencies", {}).keys())
    if not any((dependency_specifiers, optional_dependency_groups)):
        raise ValueError("no dependencies found")
    return dependency_specifiers, optional_dependency_groups


def replace_dependencies(dependency_specifiers, dependency_updates_map):
    updated_dependencies = dependency_specifiers.copy()
    for dependency_specifier in dependency_specifiers:
        operator = get_dependency_operator(dependency_specifier)
        if operator:
            dep_name = re.split(operator, dependency_specifier)[0]
            if dep_name in dependency_updates_map.keys():
                old = f"{dep_name}{operator}{dependency_updates_map[dep_name][0]}"
                new = f"{dep_name}{operator}{dependency_updates_map[dep_name][1]}"
                print(f"updating {old} to {new}")
                updated_dependencies = [new if item == old else item for item in updated_dependencies]
    return updated_dependencies


def create_venv(venv_path):
    try:
        shutil.rmtree(venv_path)
    except FileNotFoundError:
        pass
    venv.create(venv_path, with_pip=True)
    if platform.system() == "Windows":
        py_dir = "Scripts"
    else:
        py_dir = "bin"
    python_path = os.path.join(venv_path, py_dir, "python")
    return python_path


def remove_venv(venv_path):
    try:
        shutil.rmtree(venv_path)
    except FileNotFoundError:
        pass


def run(pyproject_toml_path, venv_name):
    console = Console()
    with console.status(""):
        print(f"reading {pyproject_toml_path}")
        try:
            with open(pyproject_toml_path) as f:
                data = tomlkit.load(f)
        except FileNotFoundError:
            exit("\nno pyproject.toml found. aborting")

        try:
            dependency_specifiers, optional_dependency_groups = get_dependencies_groups(data)
        except ValueError as e:
            exit(f"\n{e}")

        dependency_groups = ["."] + [f".[{group}]" for group in optional_dependency_groups]

        print(f"creating virtual environment: {venv_name}")
        python_path = create_venv(venv_name)

        for group in dependency_groups:
            if group == ".":
                print("installing main dependencies from [project]")
            else:
                print(f"installing {group} dependencies from [project.optional-dependencies]")
            subprocess.run([python_path, "-m", "pip", "install", group], stdout=subprocess.DEVNULL)

        print("finding outdated dependencies")
        dependency_update_lines = subprocess.run(
            [python_path, "-m", "pip", "list", "--outdated"],
            capture_output=True,
            text=True,
        ).stdout.splitlines()[2:]

        print(f"deleting virtual environment: {venv_name}")
        remove_venv(venv_name)

        if not dependency_update_lines:
            exit("\nno dependency updates needed")

        dependency_updates_map = {}
        for line in dependency_update_lines:
            splat = line.split()
            dependency_updates_map[splat[0]] = (splat[1], splat[2])

        data["project"]["dependencies"] = replace_dependencies(data["project"]["dependencies"], dependency_updates_map)
        for group in optional_dependency_groups:
            data["project"]["optional-dependencies"][group] = replace_dependencies(
                data["project"]["optional-dependencies"][group], dependency_updates_map
            )

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
    parser.add_argument("--venv", default="temp_venv", help="temporary virtual env name")
    args = parser.parse_args()
    run(args.path, args.venv)


if __name__ == "__main__":
    main()
