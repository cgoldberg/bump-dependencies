import pytest

import bump_dependencies


@pytest.fixture(
    params=[
        "foo",
        " foo ",
        "  foo",
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


def test_get_package_base_name(package_name):
    base_name = bump_dependencies.get_package_base_name(package_name)
    assert base_name == "foo"
