from enum import IntEnum
from functools import total_ordering
from typing import Optional, Sequence, Union

try:
    from typing import TypeGuard
except ImportError:
    from typing_extensions import TypeGuard

from semver import SemVer


class VersionError(ValueError):
    pass


@total_ordering
class Version:
    """
    Semantic version.

    <valid semver> ::= <version core>
                    | <version core> "-" <pre-release>
                    | <version core> "+" <build>
                    | <version core> "-" <pre-release> "+" <build>

    <version core> ::= <major> "." <minor> "." <patch>

    Reference: https://semver.org/
    """

    loose = True

    def __init__(self, value: str):
        try:
            self._semver = SemVer(value, loose=self.loose)
        except ValueError:
            raise VersionError(f"Invalid semantic version '{value}'") from None

    def __str__(self) -> str:
        return str(self._semver)

    def __repr__(self) -> str:
        return f"Version({str(self._semver)})"

    @property
    def major(self) -> int:
        return self._semver.major

    @property
    def minor(self) -> int:
        return self._semver.minor

    @property
    def patch(self) -> int:
        return self._semver.patch

    @property
    def prerelease(self) -> str:
        return ".".join(map(str, self._semver.prerelease))

    @property
    def build(self) -> str:
        return ".".join(map(str, self._semver.build))

    def __eq__(self, other) -> bool:
        return self._semver.compare(other._semver) == 0

    def __lt__(self, other) -> bool:
        return self._semver.compare(other._semver) < 0


def parse_version(version: str) -> Union[str, Version]:
    """Parse version of conan recipe reference."""
    version = version.strip()
    try:
        return Version(version)
    except VersionError:
        return version


def is_semantic_version(value) -> TypeGuard[Version]:
    """Check if value is a semantic version."""
    return isinstance(value, Version)


class VersionPart(IntEnum):
    MAJOR = 5
    MINOR = 4
    PATCH = 3
    PRERELEASE = 2
    BUILD = 1


def version_difference(version1: Version, version2: Version) -> Optional[VersionPart]:
    if version1.major != version2.major:
        return VersionPart.MAJOR
    if version1.minor != version2.minor:
        return VersionPart.MINOR
    if version1.patch != version2.patch:
        return VersionPart.PATCH
    if version1.prerelease != version2.prerelease:
        return VersionPart.PRERELEASE
    if version1.build != version2.build:
        return VersionPart.BUILD
    return None


def find_upgrade(
    current_version: Union[str, Version],
    versions: Sequence[Union[str, Version]],
    target: VersionPart,
) -> Optional[Version]:
    """Find latest upgrade for given target."""
    if not is_semantic_version(current_version):
        return None

    versions_semantic = filter(is_semantic_version, versions)

    def is_upgrade(v: Version) -> bool:
        assert is_semantic_version(current_version)
        return v > current_version and (version_difference(current_version, v) or 0) <= target

    versions_upgrade = list(filter(is_upgrade, versions_semantic))
    return max(versions_upgrade) if versions_upgrade else None
