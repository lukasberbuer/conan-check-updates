import asyncio
import sys
from pathlib import Path
from unittest.mock import Mock, patch

try:
    from unittest.mock import AsyncMock
except ImportError:
    ...  # skip tests for Python < 3.8

import pytest

from conan_check_updates.conan import (
    ConanError,
    ConanReference,
    find_conanfile,
    resolve_requirements_v1,
    resolve_requirements_v2,
    search,
    search_versions,
    search_versions_parallel,
)
from conan_check_updates.version import Version

HERE = Path(__file__).parent

asyncmock_required = pytest.mark.skipif(
    sys.version_info < (3, 8),
    reason="Python 3.8 required for AsyncMock mocking",
)


@pytest.mark.parametrize("conanfile", ["conanfile.py", "conanfile.txt"])
def test_find_conanfile(tmp_path, conanfile):
    conanfile_path = tmp_path / conanfile

    with pytest.raises(ValueError, match="Could not find conanfile in path"):
        find_conanfile(tmp_path)
    with pytest.raises(ValueError, match="Invalid path"):
        find_conanfile(conanfile_path)

    conanfile_path.touch()  # create conanfile

    result_path = find_conanfile(tmp_path)
    result_file = find_conanfile(conanfile_path)

    assert result_path.name == conanfile
    assert result_path.name == conanfile
    assert result_path == result_file


@pytest.mark.parametrize(
    ("reference", "package", "version", "revision", "user", "channel"),
    [
        ("pkg/0.1.0", "pkg", Version("0.1.0"), None, None, None),
        ("pkg/0.1.0@user/stable", "pkg", Version("0.1.0"), None, "user", "stable"),
        (
            "zlib/1.2.12#87a7211557b6690ef5bf7fc599dd8349",
            "zlib",
            Version("1.2.12"),
            "87a7211557b6690ef5bf7fc599dd8349",
            None,
            None,
        ),
    ],
)
def test_parse_conan_reference(reference, package, version, revision, user, channel):
    result = ConanReference(reference)
    assert result.package == package
    assert result.version == version
    assert result.revision == revision
    assert result.user == user
    assert result.channel == channel


@pytest.mark.parametrize(
    "invalid_reference",
    ["x", "x/1.0.0", "xyz/1.0.0@user", "xyz/1.0.0@a/b"],
)
def test_validate_conan_reference(invalid_reference):
    with pytest.raises(ValueError, match="Invalid Conan reference"):
        ConanReference(invalid_reference)


@pytest.fixture(name="mock_process")
def fixture_mock_process():
    with patch("asyncio.create_subprocess_shell") as mock:
        process = Mock(spec=asyncio.subprocess.Process)  # pylint: disable=no-member
        mock.return_value = process
        yield process


@asyncmock_required
@pytest.mark.asyncio()
@pytest.mark.parametrize(
    ("func", "stdout", "stderr"),
    [
        (
            resolve_requirements_v1,
            (HERE / "output" / "conan_v1_info_stdout.txt").read_bytes(),
            (HERE / "output" / "conan_v1_info_stderr.txt").read_bytes(),
        ),
        (
            resolve_requirements_v2,
            (HERE / "output" / "conan_v2_info_stdout.txt").read_bytes(),
            (HERE / "output" / "conan_v2_info_stderr.txt").read_bytes(),
        ),
    ],
    ids=["Conan v1", "Conan v2"],
)
async def test_resolve_requirements(mock_process, func, stdout, stderr):
    mock_process.communicate = AsyncMock(return_value=(stdout, stderr))
    mock_process.returncode = 0

    requires = await func(".")
    assert len(requires) == 5
    assert ConanReference("boost/1.79.0") in requires
    assert ConanReference("catch2/3.2.0") in requires
    assert ConanReference("fmt/9.0.0") in requires
    assert ConanReference("nlohmann_json/3.10.0") in requires
    assert any(ref.package == "ninja" for ref in requires)


@asyncmock_required
@pytest.mark.asyncio()
@pytest.mark.parametrize(
    ("stdout", "stderr"),
    [
        (
            (HERE / "output" / "conan_v1_search_stdout.txt").read_bytes(),
            (HERE / "output" / "conan_v1_search_stderr.txt").read_bytes(),
        ),
        (
            (HERE / "output" / "conan_v2_search_stdout.txt").read_bytes(),
            (HERE / "output" / "conan_v2_search_stderr.txt").read_bytes(),
        ),
    ],
    ids=["Conan v1", "Conan v2"],
)
async def test_search(mock_process, stdout, stderr):
    mock_process.communicate = AsyncMock(return_value=(stdout, stderr))
    mock_process.returncode = 0

    # search
    refs = await search("fmt")
    assert len(refs) > 0
    assert ConanReference("fmt/5.3.0") in refs
    assert ConanReference("fmt/6.0.0") in refs
    assert ConanReference("fmt/6.1.0") in refs

    # search_versions
    ref = ConanReference("fmt/5.3.0")
    result = await search_versions(ref)
    assert result.ref == ref
    assert Version("5.3.0") in result.versions
    assert Version("6.0.0") in result.versions
    assert Version("6.1.0") in result.versions

    # search_versions_parallel
    results = [r async for r in search_versions_parallel([ref])]
    assert len(results) == 1
    assert results[0] == result


@asyncmock_required
@pytest.mark.asyncio()
async def test_search_no_results(mock_process):
    mock_process.communicate = AsyncMock(return_value=(b"", b""))
    mock_process.returncode = 0

    refs = await search("")
    assert len(refs) == 0


@asyncmock_required
@pytest.mark.asyncio()
async def test_search_fail(mock_process):
    mock_process.communicate = AsyncMock(return_value=(b"", b"Error..."))
    mock_process.returncode = 1

    with pytest.raises(ConanError, match="Error..."):
        await search("")
