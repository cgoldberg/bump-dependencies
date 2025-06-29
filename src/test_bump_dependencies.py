import pytest

import bump_dependencies


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


def test_get_package_base_name(package_name):
    base_name = bump_dependencies.get_package_base_name(package_name)
    assert base_name == "foo"


# TODO:
# change tests for > and >= (now supported)
#
# add tests for:
# "foo===1.0" # valid
# "foo === 1.0" # valid
# "foo==1!1.0" # valid
# "foo~=1.1a1" # valid
# "foo==1.1.*" # valid
# "foo==2012.4" # valid
# "foo==1.0.post2.dev3" # valid
# "foo<2" # unsupported
# "foo>=1,<2" # unsupported
# "foo <=2.0, != 1.0.1" # unsupported
# "foo~=1.0.0,!=1.0.1" # unsupported?
# "foo ~=1.0.0, != 1.0.1" # unsupported?
# "foo>=1.0,<2.0,!=1.5.7" # unsupported?
# complex?
