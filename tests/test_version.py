import random
from typing import List, Optional

import pytest
from conan_check_updates.version import (
    Version,
    VersionError,
    VersionPart,
    VersionRange,
    VersionRangeCondition,
    find_update,
)


@pytest.mark.parametrize(
    ("version", "core", "prerelease", "build", "loose"),
    [
        # strict
        ("1.2.3", (1, 2, 3), None, None, False),
        ("1.2.3-rc1", (1, 2, 3), "rc1", None, False),
        ("1.2.3+001", (1, 2, 3), None, "001", False),
        ("1.2.3-alpha.1+001", (1, 2, 3), "alpha.1", "001", False),
        # loose
        ("1", (1, 0, 0), None, None, True),
        ("1.2", (1, 2, 0), None, None, True),
        ("1.2.3", (1, 2, 3), None, None, True),
        ("1.2.3.4", (1, 2, 3), None, None, True),
        ("1.2.3-", (1, 2, 3), "-", None, True),  # ok?
        ("1.2.3-rc1", (1, 2, 3), "rc1", None, True),
        ("1.2.3+0011", (1, 2, 3), None, "0011", True),
        ("1.2.3-alpha.1+001", (1, 2, 3), "alpha.1", "001", True),
    ],
)
def test_version(version, core, prerelease, build, loose):
    v = Version(version, loose=loose)
    assert v.core == core
    assert v.major == core[0]
    assert v.minor == core[1]
    assert v.patch == core[2]
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
    ("expression", "operator", "version", "include_prerelease"),
    [
        ("*", ">=", "0.0.0", False),
        ("*-", ">=", "0.0.0", True),
        ("1.0", "=", "1.0.0", False),
        ("^1.0-", "^", "1.0.0--", True),
        (">=1.0-rc1", ">=", "1.0.0-rc1", True),
    ],
)
def test_version_range_condition(expression, operator, version, include_prerelease):
    condition = VersionRangeCondition.parse(expression)
    assert condition.operator == operator
    assert condition.version == Version(version, loose=False)
    assert condition.include_prerelease == include_prerelease


@pytest.mark.parametrize(
    ("version_range_str", "versions_included", "versions_excluded"),
    [
        ("1.0.0", ["1.0.0"], ["1.0.1"]),
        ("=1.0.0", ["1.0.0"], ["1.0.1"]),
        (">1.0.0", ["1.0.1", "1.1.0", "2.0.0"], ["1.0.0", "0.9.9"]),
        (">=1.0.0", ["1.0.0", "1.0.1", "1.1.0", "2.0.0"], ["0.9.9"]),
        ("<1.0.0", ["0.9.9", "0.9.0"], ["1.0.0", "2.0.0"]),
        ("<=1.0.0", ["1.0.0", "0.9.9", "0.9.0"], ["2.0.0"]),
        ("~1.2.3", ["1.2.3", "1.2.4"], ["1.3.0", "2.0.0"]),
        ("^1.2.3", ["1.2.3", "1.2.4", "1.3.0"], ["2.0.0"]),
        ("^0.1.2", ["0.1.2", "0.1.3"], ["0.2.0", "1.0.0"]),
        ("^0.0.1", ["0.0.1"], ["0.0.2", "0.1.0", "1.0.0"]),
        # any
        ("", ["1.0.0"], []),
        ("*", ["1.0.0"], []),
        # sets
        (">=1.0.0 <2.0.0", ["1.0.0", "1.1.1"], ["2.0.0"]),
        # unions
        ("<=1.0.0 || >=1.2.3", ["1.0.0", "1.2.3"], ["1.0.1", "1.2.2"]),
        # pre-releases
        ("*, include_prerelease=True", ["1.0", "1.0-pre.1"], []),
        ("*-", ["1.0", "1.0-pre.1"], []),
        (">=1-", ["1.0", "1.0-pre.1"], []),
        (">1- <2.0", ["1.5.1-pre1"], ["2.1-pre1"]),
        (">1- <2.0 || ^3.2 ", ["1.5-a1", "3.3"], ["3.3-a1"]),
        ("^1.1.2-", ["1.2.3", "1.2.0-alpha1"], ["2.0.0-alpha1"]),
        ("~1.1.2-", ["1.1.3", "1.1.3-alpha1"], ["1.2.0-alpha1"]),
    ],
)
def test_version_range(version_range_str, versions_included, versions_excluded):
    version_range = VersionRange(version_range_str)
    for v in versions_included:
        print(version_range, "should include", v)
        assert version_range.satifies(Version(v))
    for v in versions_excluded:
        print(version_range, "should not include", v)
        assert not version_range.satifies(Version(v))


@pytest.mark.parametrize(
    ("version_range_str", "versions", "expected"),
    [
        ("=1.0.0", [], None),
        ("=1.2.3", ("0.9.0", "0.9.9", "1.0.0", "1.0.1", "1.1.0", "2.0.0"), None),
        ("=1.0.0", ("0.9.0", "0.9.9", "1.0.0", "1.0.1", "1.1.0", "2.0.0"), "1.0.0"),
        (">1.0.0", ("0.9.0", "0.9.9", "1.0.0", "1.0.1", "1.1.0", "2.0.0"), "2.0.0"),
        (">=1 <2", ("0.9.0", "0.9.9", "1.0.0", "1.0.1", "1.1.0", "2.0.0"), "1.1.0"),
        ("<1.0.0", ("0.9.0", "0.9.9", "1.0.0", "1.0.1", "1.1.0", "2.0.0"), "0.9.9"),
        ("~1.0.0", ("0.9.0", "0.9.9", "1.0.0", "1.0.1", "1.1.0", "2.0.0"), "1.0.1"),
        ("~0.9.0", ("0.9.0", "0.9.9", "1.0.0", "1.0.1", "1.1.0", "2.0.0"), "0.9.9"),
        ("^1.0.0", ("0.9.0", "0.9.9", "1.0.0", "1.0.1", "1.1.0", "2.0.0"), "1.1.0"),
        ("^0.9.0", ("0.9.0", "0.9.9", "1.0.0", "1.0.1", "1.1.0", "2.0.0"), "0.9.9"),
        # pre-releases
        (">=1.0", ("1.0.0", "1.1.0-rc.1", "1.1.0-rc.2"), "1.0.0"),
        (">=1.0-", ("1.0.0", "1.1.0-rc.1", "1.1.0-rc.2"), "1.1.0-rc.2"),
    ],
)
def test_version_range_max_satifies(version_range_str, versions, expected):
    version_range = VersionRange(version_range_str)
    versions = [Version(v) for v in versions]
    random.shuffle(versions)
    assert version_range.max_satifies(versions) == expected


@pytest.mark.parametrize(
    ("version", "other", "part"),
    [
        ("1.0.0", "1.0.0", None),
        ("1.0.0", "0.9.8", VersionPart.MAJOR),
        ("1.0.0", "1.1.0", VersionPart.MINOR),
        ("1.0.0", "1.0.1", VersionPart.PATCH),
        ("1.0.0", "1.0.0-rc1", VersionPart.PRERELEASE),
        ("1.0.0", "1.0.0+1", VersionPart.BUILD),
    ],
)
def test_version_difference(version: str, other: str, part: VersionPart):
    assert Version(version).difference(Version(other)) == part


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
