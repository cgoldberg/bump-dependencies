# Corey Goldberg, 2025
# License: MIT

"""Tests for bump_deps"""

import pytest

import bump_deps


@pytest.fixture(
    params=[
        "requests==1.0.0",
        "requests~=1.0",
        "requests===1.0.0",
        "requests==1.0.*",
        "requests==1.0.1dev0",
        "requests[foo]==1.0",
        "requests[foo,bar]==1.0.0",
        "requests == 1.0",
        "requests[foo] == 1.0",
        "requests== 1.0",
        "requests ==1.0",
        "requests   ==   1.0",
        " requests==1.0 ",
        "  requests == 1.0  ",
        "requests==1.0 ; python_version < '4.0'",
        "requests~=1.0.0;python_version>'2.7'",
        "requests[foo, bar]==1.0.0;python_version>'2.7' and platform_version=='2'",
        "requests == 1.0; os_name=='a' or os_name=='b'",
    ]
)
def valid_specifier(request):
    return request.param


@pytest.fixture(
    params=[
        "foo>1.0",
        "foo<1.0",
        "foo>=1.0",
        "foo<=1.0",
        "foo!=1.0",
        "foo >= 1.0dev1",
        "foo >= 1.0.1, <= 2.0.*",
        "foo >= 1.0.1, == 1.0.*",
        "foo>1.0.0,<2.0.0",
        "foo>1.0; python_version < '4.0'",
        "foo [bar,baz] >= 2.8.1, == 2.8.* ; python_version < '4.0'",
    ]
)
def unpinned_specifier(request):
    return request.param


@pytest.fixture(
    params=[
        "foo",
        "foo_bar2",
        "foo[bar]",
        "foo [bar,baz]",
        "foo[bar, baz];python_version<'2.7' and platform_version=='2'",
        "foo; os_name=='a' or os_name=='b'",
    ]
)
def unversioned_specifier(request):
    return request.param


@pytest.fixture(
    params=[
        "foo@http://foo.com",
        "foo [bar,baz] @ http://foo.com ; python_version=='2.7'",
        "foo @ https://github.com/foo/foo/archive/1.0.0.zip",
    ]
)
def complex_specifier(request):
    return request.param


def test_valid_dependency_operator(valid_specifier):
    valid_operators = ("==", "~=", "===")
    operator = bump_deps.get_dependency_operator(valid_specifier)
    assert isinstance(operator, str)
    assert operator in valid_operators


def test_unpinned_dependency_operator(unpinned_specifier):
    with pytest.raises(ValueError, match="no pinned version specified"):
        bump_deps.get_dependency_operator(unpinned_specifier)


def test_complex_dependency_operator(complex_specifier):
    with pytest.raises(ValueError, match="can't handle complex dependency specifiers"):
        bump_deps.get_dependency_operator(complex_specifier)


def test_missing_dependency_operator(unversioned_specifier):
    with pytest.raises(ValueError, match="no version specified"):
        bump_deps.get_dependency_operator(unversioned_specifier)


def test_fetch_latest_package_version():
    version = bump_deps.fetch_latest_package_version("requests")
    assert isinstance(version, str)
    assert int(version[0]) >= 0


def test_fetch_unavailable_package_version():
    version = bump_deps.fetch_latest_package_version("definitely-not-a-package-found-on-pypi-1234")
    assert version is None


def test_update_dependency(valid_specifier):
    operator = bump_deps.get_dependency_operator(valid_specifier)
    updated_dependency_specifier = bump_deps.update_dependency(valid_specifier, operator)
    assert isinstance(updated_dependency_specifier, str)
    assert operator in updated_dependency_specifier
    assert valid_specifier not in updated_dependency_specifier
