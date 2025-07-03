# Corey Goldberg, 2025
# License: MIT

"""Tests for bump_dependencies"""

import re

import pytest
import tomlkit

import bump_dependencies as bd


@pytest.fixture(
    params=[
        ("foo==1.0.0", "foo"),
        ("foo~=1.0", "foo"),
        ("foo===1.0.0", "foo"),
        ("foo==1.0.*", "foo"),
        ("foo==1.0.1dev0", "foo"),
        ("foo~=1.1a1", "foo"),
        ("foo==1.1.*", "foo"),
        ("foo>1", "foo"),
        ("foo>=1.0", "foo"),
        ("foo[bar] == 2012.4", "foo[bar]"),
        ("foo==1.0.post2.dev3", "foo"),
        ("foo[bar] >= 1.0dev1", "foo[bar]"),
        ("foo>1.0; python_version < '4.0'", "foo"),
        ("foo[bar]>=1.0", "foo[bar]"),
        ("foo[bar,baz]==1.0.0", "foo[bar,baz]"),
        ("foo[ bar, baz ] ~= 1.0.0", "foo[bar,baz]"),
        ("foo > 1.0", "foo"),
        ("foo[bar] == 1.0", "foo[bar]"),
        ("foo== 1.0", "foo"),
        ("foo ==1.0", "foo"),
        ("foo   ==   1.0", "foo"),
        (" foo==1.0 ", "foo"),
        ("  foo > 1.0  ", "foo"),
        ("foo==1.0 ; python_version < '4.0'", "foo"),
        ("foo~=1.0.0;python_version>'2.7'", "foo"),
        ("foo[bar, baz, qux]==1.0.0;python_version>'2.7'", "foo[bar,baz,qux]"),
        ("foo == 1.0; os_name=='a' or os_name=='b'", "foo"),
    ]
)
def valid_specifier_name(request):
    return request.param


@pytest.fixture(
    params=[
        "foo<1.0",
        "foo<=1.0",
        " foo <= 1.0.0 ",
        "foo!=1.0",
        "foo==1!1.0foo>=1,<2foo >= 1.0.1, <= 2.0.*",
        "foo>1.0.0,<2.0.0",
        "foo <=2.0, != 1.0.1",
        "foo~=1.0.0,!=1.0.1foo ~=1.0.0, != 1.0.1foo>=1.0,<2.0,!=1.5.7",
    ]
)
def unsupported_specifier(request):
    return request.param


@pytest.fixture(
    params=[
        "foo",
        "foo-bar2",
        " foo ",
        "foo[bar]",
        "foo [bar,baz]",
        "foo[bar, baz, qux] ;platform_version=='2'",
        "foo; os_name=='a' or os_name=='b'",
    ]
)
def unversioned_specifier(request):
    return request.param


@pytest.fixture(
    params=[
        "foo >= 1.0.1, == 1.0.*",
        "foo [bar,baz] >= 2.8.1, == 2.8.* ; python_version < '4.0'",
    ]
)
def complex_specifier(request):
    return request.param


@pytest.fixture(
    params=[
        "foo@http://foo.com",
        "foo @ https://github.com/foo/foo/archive/1.0.0.zip",
        "foo @ file:///builds/foo-1.0.0-py3-none-any.whl`",
        "foo [bar,baz] @ http://foo.com ; python_version=='3.13'",
    ]
)
def direct_reference_specifier(request):
    return request.param


@pytest.fixture(
    params=[
        "foo",
        " foo ",
        "  foo",
        "foo[",
        "foo [",
        "foo[bar]",
        "foo[ bar ]",
        "foo [bar]",
        "foo[bar,baz]",
        "foo[bar, baz]",
        "foo [ bar , baz ]",
    ]
)
def package_name(request):
    return request.param


def test_name_and_operator(valid_specifier_name):
    dependency_specifier, name = valid_specifier_name
    valid_operators = ("===", "==", "~=", ">=", ">")
    dependency_name, operator = bd.get_dependency_name_and_operator(dependency_specifier)
    assert isinstance(operator, str)
    assert operator in valid_operators
    assert isinstance(dependency_name, str)
    assert dependency_name == name


def test_name_and_operator_with_unsupported_operator(unsupported_specifier):
    with pytest.raises(ValueError, match="skipping unsupported '.*' version identifier"):
        bd.get_dependency_name_and_operator(unsupported_specifier)


def test_name_and_operator_with_unversioned_specifier(unversioned_specifier):
    with pytest.raises(ValueError, match="no version specified"):
        bd.get_dependency_name_and_operator(unversioned_specifier)


def test_name_and_operator_with_complex_specifier(complex_specifier):
    with pytest.raises(ValueError, match="can't handle complex dependency specifiers"):
        bd.get_dependency_name_and_operator(complex_specifier)


def test_name_and_operator_with_direct_reference_specifier(direct_reference_specifier):
    with pytest.raises(ValueError, match="can't handle direct reference dependency specifiers"):
        bd.get_dependency_name_and_operator(direct_reference_specifier)


def test_update_dependency(valid_specifier_name):
    dependency_specifier, name = valid_specifier_name
    dependency_name, operator = bd.get_dependency_name_and_operator(dependency_specifier)
    updated_dependency_specifier = bd.update_dependency(dependency_specifier)
    assert isinstance(updated_dependency_specifier, str)
    assert operator in updated_dependency_specifier
    assert dependency_specifier not in updated_dependency_specifier
    assert name in updated_dependency_specifier


def test_fetch_latest_package_version():
    version = bd.fetch_latest_package_version("requests")
    assert isinstance(version, str)
    assert version[0].isdigit()


def test_fetch_unavailable_package_version():
    version = bd.fetch_latest_package_version("definitely-not-a-package-found-on-pypi-1234")
    assert version is None


def test_package_base_name(package_name):
    base_name = bd.get_package_base_name(package_name)
    assert base_name == "foo"


def test_dry_run():
    data = r"""
        [project]
        name = "foo"
        requires-python = ">=3.9"
        dependencies = [
            "requests==2.32.1",
            "numpy>=1.26.4",
            "pandas~=1.4",
        ]
        [project.optional-dependencies]
        socks = [
            "pysocks>=1.5.6",
            "httpbin~=0.9.0",
        ]
        [dependency-groups]
        dev = [
            "wheel",
            "build>=1.1.2.post1",
        ]
        test = [
            "pytest>=4",
            "pytest-timeout>2.2",
        ]
        """
    pattern = r"""
        \[project\]
        name = "foo"
        requires-python = ">=3.9"
        dependencies = \[
            "requests==(.+)",
            "numpy>=(.+)",
            "pandas~=(.+)",
        \]
        \[project.optional-dependencies\]
        socks = \[
            "pysocks>=(.+)",
            "httpbin~=(.+)",
        \]
        \[dependency-groups\]
        dev = \[
            "wheel",
            "build>=(.+)",
        \]
        test = \[
            "pytest>=(.+)",
            "pytest-timeout>(.+)",
        \]
        """
    updated_data = bd.run(tomlkit.loads(data))
    assert isinstance(updated_data, tomlkit.toml_document.TOMLDocument)
    assert re.match(pattern, tomlkit.dumps(updated_data))
