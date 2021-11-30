import asyncio
import sys
from unittest.mock import Mock, patch

try:
    from unittest.mock import AsyncMock
except ImportError:
    ...  # skip tests for Python < 3.8

import pytest

from conan_check_updates import (
    ConanError,
    RecipeReference,
    Version,
    conan_info_requirements,
    conan_search,
)

pytestmark = pytest.mark.skipif(
    sys.version_info < (3, 8),
    reason="Python 3.8 required for AsyncMock mocking",
)


@pytest.fixture(name="mock_process")
async def fixture_mock_process():
    with patch(
        "asyncio.create_subprocess_shell",
        new=AsyncMock(spec=asyncio.create_subprocess_shell),
    ) as mock:
        process = Mock(spec=asyncio.subprocess.Process)  # pylint: disable=no-member
        mock.return_value = process
        yield process


CONAN_INFO_RESPONE = b"""
Version ranges solved
    Version range '>=2.10.0' required by 'conanfile.txt' resolved to 'catch2/2.13.7' in local cache
    Version range '>=3.20' required by 'conanfile.txt' resolved to 'cmake/3.22.0' in local cache

[{"reference": "conanfile.txt", "is_ref": false, "display_name": "conanfile.txt", "id": "c5cf74a5adb1e1f5ef7a73610a06eda03c72151c", "build_id": null, "context": "host", "requires": ["catch2/2.13.7", "fmt/8.0.0", "spdlog/1.9.0", "nlohmann_json/3.7.3"], "build_requires": ["cmake/3.22.0"]}, {"revision": "0", "reference": "catch2/2.13.7", "is_ref": true, "display_name": "catch2/2.13.7", "id": "5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9", "build_id": null, "context": "host", "remote": {"name": "conancenter", "url": "https://center.conan.io"}, "url": "https://github.com/conan-io/conan-center-index", "homepage": "https://github.com/catchorg/Catch2", "license": ["BSL-1.0"], "description": "A modern, C++-native, header-only, framework for unit-tests, TDD and BDD", "topics": ["conan", "catch2", "header-only", "unit-test", "tdd", "bdd"], "provides": ["catch2"], "recipe": "Cache", "package_revision": "0", "binary": "Download", "binary_remote": "conancenter", "creation_date": "2021-11-05 20:54:20 UTC", "required_by": ["conanfile.txt"]}, {"revision": "0", "reference": "cmake/3.22.0", "is_ref": true, "display_name": "cmake/3.22.0", "id": "0a420ff5c47119e668867cdb51baff0eca1fdb68", "build_id": null, "context": "host", "remote": {"name": "conancenter", "url": "https://center.conan.io"}, "url": "https://github.com/conan-io/conan-center-index", "homepage": "https://github.com/Kitware/CMake", "license": ["BSD-3-Clause"], "description": "Conan installer for CMake", "topics": ["cmake", "build", "installer"], "provides": ["cmake"], "recipe": "Cache", "package_revision": "0", "binary": "Download", "binary_remote": "conancenter", "creation_date": "2021-11-19 05:18:58 UTC", "required_by": ["conanfile.txt"]}, {"revision": "0", "reference": "fmt/8.0.0", "is_ref": true, "display_name": "fmt/8.0.0", "id": "2be90237c5e294c2f30bf6b043d047624b893db3", "build_id": null, "context": "host", "remote": {"name": "conancenter", "url": "https://center.conan.io"}, "url": "https://github.com/conan-io/conan-center-index", "homepage": "https://github.com/fmtlib/fmt", "license": ["MIT"], "description": "A safe and fast alternative to printf and IOStreams.", "topics": ["conan", "fmt", "format", "iostream", "printf"], "provides": ["fmt"], "recipe": "Cache", "package_revision": "0", "binary": "Download", "binary_remote": "conancenter", "creation_date": "2021-10-15 17:59:52 UTC", "required_by": ["spdlog/1.9.0", "conanfile.txt"]}, {"revision": "0", "reference": "nlohmann_json/3.7.3", "is_ref": true, "display_name": "nlohmann_json/3.7.3", "id": "5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9", "build_id": null, "context": "host", "remote": {"name": "conancenter", "url": "https://center.conan.io"}, "url": "https://github.com/conan-io/conan-center-index", "homepage": "https://github.com/nlohmann/json", "license": ["MIT"], "description": "JSON for Modern C++ parser and generator.", "topics": ["conan", "jsonformoderncpp", "nlohmann_json", "json", "header-only"], "provides": ["nlohmann_json"], "recipe": "Cache", "package_revision": "0", "binary": "Download", "binary_remote": "conancenter", "creation_date": "2021-08-01 11:51:22 UTC", "required_by": ["conanfile.txt"]}, {"revision": "0", "reference": "spdlog/1.9.0", "is_ref": true, "display_name": "spdlog/1.9.0", "id": "26b885d7ef0883598f1d5dc9d2e504e10115011f", "build_id": null, "context": "host", "remote": {"name": "conancenter", "url": "https://center.conan.io"}, "url": "https://github.com/conan-io/conan-center-index", "homepage": "https://github.com/gabime/spdlog", "license": ["MIT"], "description": "Fast C++ logging library", "topics": ["conan", "spdlog", "logging", "header-only"], "provides": ["spdlog"], "recipe": "Cache", "package_revision": "0", "binary": "Download", "binary_remote": "conancenter", "creation_date": "2021-07-29 19:55:23 UTC", "required_by": ["conanfile.txt"], "requires": ["fmt/8.0.0"]}]
"""  # noqa: E501


@pytest.mark.asyncio()
async def test_conan_info_requirements(mock_process):
    stdout = CONAN_INFO_RESPONE
    stderr = b""
    mock_process.communicate = AsyncMock(return_value=(stdout, stderr))
    mock_process.returncode = 0

    result = await conan_info_requirements(".")
    assert result == [
        "catch2/2.13.7",
        "fmt/8.0.0",
        "spdlog/1.9.0",
        "nlohmann_json/3.7.3",
        "cmake/3.22.0",
    ]


@pytest.mark.asyncio()
async def test_conan_search(mock_process):
    stdout = b"Remote 'conancenter':\r\n" b"fmt/5.3.0\r\n" b"fmt/6.0.0\r\n" b"fmt/6.1.0\r\n"
    stderr = b""
    mock_process.communicate = AsyncMock(return_value=(stdout, stderr))
    mock_process.returncode = 0

    refs = await conan_search("fmt")

    assert len(refs) == 3
    assert refs[0] == RecipeReference("fmt", Version("5.3.0"))
    assert refs[1] == RecipeReference("fmt", Version("6.0.0"))
    assert refs[2] == RecipeReference("fmt", Version("6.1.0"))


@pytest.mark.asyncio()
async def test_conan_search_no_results(mock_process):
    mock_process.communicate = AsyncMock(return_value=(b"", b""))
    mock_process.returncode = 0

    refs = await conan_search("")
    assert len(refs) == 0


@pytest.mark.asyncio()
async def test_conan_search_fail(mock_process):
    mock_process.communicate = AsyncMock(return_value=(b"", b"Error..."))
    mock_process.returncode = 1

    with pytest.raises(ConanError, match="Error..."):
        await conan_search("")