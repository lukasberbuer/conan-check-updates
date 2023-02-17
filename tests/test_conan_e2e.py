import os
from pathlib import Path
from unittest.mock import patch

import pytest
from conan_check_updates.conan import (
    ConanReference,
    conan_version,
    inspect_requires_conanfile,
    search_versions_parallel,
)
from conan_check_updates.version import Version
from test_conan import parse_requires_conanfile_json

HERE = Path(__file__).parent


def test_conan_version():
    version = conan_version()
    assert version
    assert version.major in (1, 2)


@patch.dict(os.environ, {"PATH": ""})
def test_conan_version_fail():
    conan_version.cache_clear()
    with pytest.raises(RuntimeError, match="Conan executable not found"):
        conan_version()


@pytest.mark.parametrize("conanfile", ["conanfile.py", "conanfile.txt"])
def test_inspect_requires_conanfile(conanfile):
    expected = parse_requires_conanfile_json(HERE / "conanfile.json")
    requires = inspect_requires_conanfile(HERE / conanfile)
    assert requires == expected


@pytest.mark.flaky(reruns=3)  # possible timeouts in CI
@pytest.mark.asyncio()
async def test_search_versions_parallel():
    refs = [
        ConanReference.parse("boost/1.79.0"),
        ConanReference.parse("fmt/9.0.0"),
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
