import pytest

from conan_check_updates import Version, VersionError, VersionPart, version_difference


@pytest.mark.parametrize(
    ("version", "major", "minor", "patch", "prerelease", "build"),
    [
        ("1", 1, 0, 0, "", ""),
        ("1.2", 1, 2, 0, "", ""),
        ("1.2.3", 1, 2, 3, "", ""),
        ("1.2.3-rc1", 1, 2, 3, "rc1", ""),
        ("1.2.3rc1", 1, 2, 3, "rc1", ""),
        ("1.2.3+1", 1, 2, 3, "", "1"),
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
