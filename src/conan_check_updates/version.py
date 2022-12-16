import re
import sys
from enum import IntEnum
from functools import total_ordering
from itertools import zip_longest
from typing import Optional, Sequence, Union

if sys.version_info >= (3, 10):
    from typing import TypeGuard
else:
    from typing_extensions import TypeGuard

# https://semver.org/#is-there-a-suggested-regular-expression-regex-to-check-a-semver-string
_PATTERN_SEMVER = re.compile(
    r"(?P<major>0|[1-9]\d*)"
    r"\.(?P<minor>0|[1-9]\d*)"
    r"\.(?P<patch>0|[1-9]\d*)"
    r"(?:-(?P<prerelease>(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)"
    r"(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?"
    r"(?:\+(?P<build>[0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?"
    r"$"
)

_PATTERN_SEMVER_LOOSE = re.compile(
    r"^"
    r"(?P<major>0|[1-9]\d*)"
    r"(?:\.(?P<minor>0|[1-9]\d*))?"  # allow empty minor -> 0
    r"(?:\.(?P<patch>0|[1-9]\d*))?"  # allow empty patch -> 0
    # allow prerelease without "-", e.g. 0.1.0rc1
    r"(?:-?(?P<prerelease>(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)"
    r"(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?"
    r"(?:\+(?P<build>[0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?"
    r"$"
)


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
        pattern = _PATTERN_SEMVER_LOOSE if self.loose else _PATTERN_SEMVER
        match = pattern.match(value)
        if not match:
            raise VersionError(f"Invalid semantic version '{value}'") from None

        self._str = value
        self._major = int(match.group("major"))
        self._minor = int(match.group("minor") or 0)
        self._patch = int(match.group("patch") or 0)
        self._prelease = match.group("prerelease") or None
        self._build = match.group("build") or None

    def __str__(self) -> str:
        return self._str

    def __repr__(self) -> str:
        return f"Version({self._str})"

    @property
    def major(self) -> int:
        return self._major

    @property
    def minor(self) -> int:
        return self._minor

    @property
    def patch(self) -> int:
        return self._patch

    @property
    def prerelease(self) -> Optional[str]:
        return self._prelease

    @property
    def build(self) -> Optional[str]:
        return self._build

    def as_tuple(self):
        return (self._major, self._minor, self._patch, self._prelease, self._build)

    def __eq__(self, other) -> bool:
        if other is None:
            return False
        if isinstance(other, str):
            other = Version(other)

        return self.as_tuple() == other.as_tuple()

    def __lt__(self, other) -> bool:
        # pylint: disable=too-many-return-statements
        # semver precedence: https://semver.org/#spec-item-11
        if other is None:
            return False
        if not isinstance(other, Version):
            other = Version(other)

        def tuple_core(v):
            return v.as_tuple()[:3]

        if tuple_core(self) < tuple_core(other):
            return True

        if tuple_core(self) == tuple_core(other):
            if self.prerelease and other.prerelease:
                # compare pre-release fields from left to right until a difference is found
                for left, right in zip_longest(
                    self.prerelease.split("."),
                    other.prerelease.split("."),
                ):
                    if left == right:
                        continue
                    # a smaller set of pre-release fields has a lower precedence
                    if left is None or right is None:
                        return left is None
                    # numeric identifiers always have lower precedence than non-numeric identifiers
                    if left.isdigit() ^ right.isdigit():  # xor
                        return left.isdigit()
                    # identifiers consisting of only digits are compared numerically
                    if left.isdigit() and right.isdigit():
                        return int(left) < int(right)
                    # identifiers with letters or hyphens are compared lexically
                    return left < right

            return self.prerelease is not None  # pre-release has lower precedence

        return False


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


def find_update(
    current_version: Union[str, Version],
    versions: Sequence[Union[str, Version]],
    target: VersionPart,
) -> Optional[Version]:
    """Find latest update for given target."""
    if not is_semantic_version(current_version):
        return None

    versions_semantic = filter(is_semantic_version, versions)

    def is_update(v: Version) -> bool:
        assert is_semantic_version(current_version)
        return v > current_version and (version_difference(current_version, v) or 0) <= target

    versions_update = list(filter(is_update, versions_semantic))
    return max(versions_update) if versions_update else None
