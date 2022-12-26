import asyncio
import subprocess
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
    inspect_requires_conanfile_py,
    inspect_requires_conanfile_txt,
    search,
    search_versions,
    search_versions_parallel,
)
from conan_check_updates.version import Version, VersionRange

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
        # non-semanic versions
        ("rapidjson/cci.20220822", "rapidjson", "cci.20220822", None, None, None),
        # version ranges
        ("cmake/[^3.10]", "cmake", VersionRange("^3.10"), None, None, None),
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
    with patch("subprocess.run") as mock:
        process = Mock(spec=subprocess.CompletedProcess)  # pylint: disable=no-member
        process.configure_mock(args=[], returncode=0, stdout=b"", stderr=b"")
        mock.return_value = process
        yield process


@pytest.fixture(name="mock_process_async")
def fixture_mock_process_async():
    with patch("asyncio.create_subprocess_shell") as mock:
        process = Mock(spec=asyncio.subprocess.Process)  # pylint: disable=no-member
        mock.return_value = process
        yield process


@pytest.fixture(name="mock_conan_version")
def _fixture_mock_conan_version():
    with patch("conan_check_updates.conan.conan_version") as mock:
        mock.return_value = Version("2.0.0")
        yield


@pytest.mark.parametrize(
    ("stdout", "stderr"),
    [
        (
            (HERE / "output" / "conan_v1_inspect_stdout.txt").read_bytes(),
            (HERE / "output" / "conan_v1_inspect_stderr.txt").read_bytes(),
        ),
        (
            (HERE / "output" / "conan_v2_inspect_stdout.txt").read_bytes(),
            (HERE / "output" / "conan_v2_inspect_stderr.txt").read_bytes(),
        ),
    ],
    ids=["Conan v1", "Conan v2"],
)
@pytest.mark.usefixtures("mock_conan_version")
def test_inspect_requires_conanfile_py(mock_process, stdout, stderr):
    mock_process.stdout = stdout
    mock_process.stderr = stderr

    requires = inspect_requires_conanfile_py(HERE / "conanfile.py")
    assert len(requires) == 5
    assert ConanReference("boost/1.79.0") in requires
    assert ConanReference("catch2/3.2.0") in requires
    assert ConanReference("fmt/9.0.0") in requires
    assert ConanReference("nlohmann_json/3.10.0") in requires
    assert ConanReference("ninja/[^1.10]") in requires


def test_inspect_requires_conanfile_txt():
    requires = inspect_requires_conanfile_txt(HERE / "conanfile.txt")
    assert len(requires) == 5
    assert ConanReference("boost/1.79.0") in requires
    assert ConanReference("catch2/3.2.0") in requires
    assert ConanReference("fmt/9.0.0") in requires
    assert ConanReference("nlohmann_json/3.10.0") in requires
    assert ConanReference("ninja/[^1.10]") in requires


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
async def test_search(mock_process_async, stdout, stderr):
    mock_process_async.communicate = AsyncMock(return_value=(stdout, stderr))
    mock_process_async.returncode = 0

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
async def test_search_no_results(mock_process_async):
    mock_process_async.communicate = AsyncMock(return_value=(b"", b""))
    mock_process_async.returncode = 0

    refs = await search("")
    assert len(refs) == 0


@asyncmock_required
@pytest.mark.asyncio()
async def test_search_fail(mock_process_async):
    mock_process_async.communicate = AsyncMock(return_value=(b"", b"Error..."))
    mock_process_async.returncode = 1

    with pytest.raises(ConanError, match="Error..."):
        await search("")
