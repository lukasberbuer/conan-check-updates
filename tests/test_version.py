from typing import List, Optional

import pytest

from conan_check_updates.version import (
    Version,
    VersionError,
    VersionPart,
    find_update,
    parse_version,
    version_difference,
)


@pytest.mark.parametrize(
    ("version", "major", "minor", "patch", "prerelease", "build"),
    [
        ("1", 1, 0, 0, None, None),
        ("1.2", 1, 2, 0, None, None),
        ("1.2.3", 1, 2, 3, None, None),
        ("1.2.3-rc1", 1, 2, 3, "rc1", None),
        ("1.2.3rc1", 1, 2, 3, "rc1", None),
        ("1.2.3+1", 1, 2, 3, None, "1"),
        ("1.2.3-alpha+001", 1, 2, 3, "alpha", "001"),
    ],
)
def test_version(version: str, major: int, minor: int, patch: int, prerelease: str, build: str):
    v = Version(version)
    assert v.major == major
    assert v.minor == minor
    assert v.patch == patch
    assert v.prerelease == prerelease
    assert v.build == build


@pytest.mark.parametrize(
    "version",
    [
        "abc.0.1",
        "cci.20211112",  # RapidJSON
    ],
)
def test_invalid_version(version: str):
    with pytest.raises(VersionError):
        Version(version)


@pytest.mark.parametrize(
    ("left", "right", "cmp", "expected"),
    [
        ("1.0.0", "1.0.0", "__eq__", True),
        ("1.0.0", "1.0.1", "__eq__", False),
        ("1.0.0-alpha", "1.0.0-alpha.1", "__lt__", True),
        ("1.0.0-alpha.1", "1.0.0-alpha.beta", "__lt__", True),
        ("1.0.0-alpha.beta", "1.0.0-beta", "__lt__", True),
        ("1.0.0-beta", "1.0.0-beta.2", "__lt__", True),
        ("1.0.0-beta.2", "1.0.0-beta.11", "__lt__", True),
        ("1.0.0-rc.1", "1.0.0", "__lt__", True),
        ("1.0.0", "1.0.1", "__lt__", True),
    ],
)
def test_compare_versions(left: str, right: str, cmp: str, expected: bool):
    v_left = Version(left)
    v_right = Version(right)
    func = getattr(v_left, cmp)
    assert func(v_right) == expected


@pytest.mark.parametrize(
    ("version_str", "expected"),
    [
        ("0", Version("0.0.0")),
        ("0.1", Version("0.1.0")),
        ("0.1.2", Version("0.1.2")),
        ("0.1.2-rc1", Version("0.1.2-rc1")),
        ("xyz", "xyz"),
        ("", ""),
    ],
)
def test_parse_version(version_str, expected):
    assert parse_version(version_str) == expected


@pytest.mark.parametrize(
    ("version1", "version2", "part"),
    [
        ("1.0.0", "1.0.0", None),
        ("1.0.0", "0.9.8", VersionPart.MAJOR),
        ("1.0.0", "1.1.0", VersionPart.MINOR),
        ("1.0.0", "1.0.1", VersionPart.PATCH),
        ("1.0.0", "1.0.0-rc1", VersionPart.PRERELEASE),
        ("1.0.0", "1.0.0+1", VersionPart.BUILD),
    ],
)
def test_version_difference(version1: str, version2: str, part: VersionPart):
    assert version_difference(Version(version1), Version(version2)) == part


@pytest.mark.parametrize(
    ("current", "available", "target", "expected"),
    [
        ("1.0.0", [], VersionPart.MAJOR, None),
        ("1.0.0", ("1.0.0",), VersionPart.MAJOR, None),
        ("1.0.0", ("2.0.0", "1.1.0", "1.0.1"), VersionPart.MAJOR, "2.0.0"),
        ("1.0.0", ("2.0.0", "1.1.0", "1.0.1"), VersionPart.MINOR, "1.1.0"),
        ("1.0.0", ("2.0.0", "1.1.0", "1.0.1"), VersionPart.PATCH, "1.0.1"),
    ],
)
def test_find_update(
    current: str, available: List[str], target: VersionPart, expected: Optional[str]
):
    current_version = Version(current)
    versions = [Version(v) for v in available]
    expected_version = Version(expected) if expected else None
    assert find_update(current_version, versions, target) == expected_version
