import os
from pathlib import Path
from unittest.mock import patch

import pytest

from conan_check_updates.conan import (
    ConanReference,
    find_conan,
    resolve_requirements,
    search_versions_parallel,
)
from conan_check_updates.version import Version

HERE = Path(__file__).parent


def test_find_conan():
    find_conan.cache_clear()
    result = find_conan()
    assert result.path
    assert result.path.stem.lower() == "conan"
    assert result.version
    assert result.version.major in (1, 2)


@patch.dict(os.environ, {"PATH": ""})
def test_find_conan_fail():
    find_conan.cache_clear()
    with pytest.raises(RuntimeError, match="Conan executable not found"):
        find_conan()


@pytest.mark.flaky(reruns=3)  # possible timeouts in CI
@pytest.mark.asyncio()
async def test_search_versions_parallel():
    refs = [
        ConanReference("boost/1.79.0"),
        ConanReference("fmt/9.0.0"),
    ]
    results = [r async for r in search_versions_parallel(refs)]
    assert len(results) == 2

    def get_result_by_package_name(name: str):
        return next(filter(lambda r: r.ref.package == name, results))

    result_boost = get_result_by_package_name("boost")
    assert result_boost.ref == refs[0]
    assert Version("1.79.0") in result_boost.versions
    assert Version("1.80.0") in result_boost.versions

    result_fmt = get_result_by_package_name("fmt")
    assert result_fmt.ref == refs[1]
    assert Version("9.0.0") in result_fmt.versions
    assert Version("9.1.0") in result_fmt.versions


@pytest.mark.flaky(reruns=3)  # possible timeouts in CI
@pytest.mark.asyncio()
@pytest.mark.parametrize("conanfile", ["conanfile.py", "conanfile.txt"])
async def test_resolve_requirements(conanfile):
    cwd = HERE / conanfile
    # increase timeout for CI because it takes time on clean systems:
    # - initialize default profile
    # - create remotes registry file
    # - fetch recipes from remote
    requires = await resolve_requirements(cwd, timeout=60)
    assert len(requires) == 5
    assert ConanReference("boost/1.79.0") in requires
    assert ConanReference("catch2/3.2.0") in requires
    assert ConanReference("fmt/9.0.0") in requires
    assert ConanReference("nlohmann_json/3.10.0") in requires
    assert any(ref.package == "ninja" for ref in requires)
