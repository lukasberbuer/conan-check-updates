import re
import sys
from dataclasses import dataclass
from enum import Enum, IntEnum
from functools import total_ordering
from itertools import zip_longest
from typing import Optional, Sequence, Tuple, Union

if sys.version_info >= (3, 10):
    from typing import TypeAlias, TypeGuard
else:
    from typing_extensions import TypeAlias, TypeGuard

# https://semver.org/#is-there-a-suggested-regular-expression-regex-to-check-a-semver-string
_REGEX_SEMVER_CORE = r"0|[1-9]\d*"
_REGEX_SEMVER_PRERELEASE_PART = r"0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*"
_REGEX_SEMVER_PRERELEASE = (
    rf"(?:{_REGEX_SEMVER_PRERELEASE_PART})" rf"(?:\.(?:{_REGEX_SEMVER_PRERELEASE_PART}))*"
)
_REGEX_SEMVER_BUILD = r"[0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*"
_REGEX_SEMVER = (
    rf"(?P<major>{_REGEX_SEMVER_CORE})"
    rf"\.(?P<minor>{_REGEX_SEMVER_CORE})"
    rf"\.(?P<patch>{_REGEX_SEMVER_CORE})"
    rf"(?:\-(?P<prerelease>{_REGEX_SEMVER_PRERELEASE}))?"
    rf"(?:\+(?P<build>{_REGEX_SEMVER_BUILD}))?"
)
_REGEX_SEMVER_LOOSE = (
    rf"(?P<major>{_REGEX_SEMVER_CORE})"
    rf"(?:\.(?P<minor>{_REGEX_SEMVER_CORE}))?"  # allow empty minor -> 0
    rf"(?:\.(?P<patch>{_REGEX_SEMVER_CORE}))?"  # allow empty patch -> 0
    rf"(?:\.(?:{_REGEX_SEMVER_CORE}))*"  # allow micro version, ...
    # allow prerelease without "-", e.g. 0.1.0rc1
    rf"(?:-?(?P<prerelease>{_REGEX_SEMVER_PRERELEASE}))?"
    rf"(?:\+(?P<build>{_REGEX_SEMVER_BUILD}))?"
)

_PATTERN_SEMVER = re.compile(_REGEX_SEMVER)
_PATTERN_SEMVER_LOOSE = re.compile(_REGEX_SEMVER_LOOSE)


class VersionError(ValueError):
    pass


class VersionPart(IntEnum):
    MAJOR = 5
    MINOR = 4
    PATCH = 3
    PRERELEASE = 2
    BUILD = 1


@total_ordering
class Version:
    """
    Semantic version.

    <valid semver> ::= <version core>
                     | <version core> "-" <pre-release>
                     | <version core> "+" <build>
                     | <version core> "-" <pre-release> "+" <build>

    <version core> ::= <major> "." <minor> "." <patch>

    Reference: https://semver.org
    """

    def __init__(self, value: str, *, loose: bool = True):
        self._str = value
        self._loose = loose

        pattern = _PATTERN_SEMVER_LOOSE if loose else _PATTERN_SEMVER
        match = pattern.fullmatch(value)
        if not match:
            raise VersionError(f"Invalid semantic version '{value}'") from None

        self._major = int(match.group("major"))
        self._minor = int(match.group("minor") or 0)
        self._patch = int(match.group("patch") or 0)
        self._prelease = match.group("prerelease") or None
        self._build = match.group("build") or None

    def __str__(self) -> str:
        return self._str

    def __repr__(self) -> str:
        return f"Version({self._str})"

    def __hash__(self) -> int:
        return hash(self._str)

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
    def core(self) -> Tuple[int, int, int]:
        return self._major, self._minor, self._patch

    @property
    def prerelease(self) -> Optional[str]:
        return self._prelease

    @property
    def build(self) -> Optional[str]:
        return self._build

    def astuple(self) -> Tuple[int, int, int, Optional[str], Optional[str]]:
        return (*self.core, self.prerelease, self.build)

    def __eq__(self, other) -> bool:
        if isinstance(other, str):
            other = Version(other, loose=self._loose)
        if not isinstance(other, Version):
            return False
        return self.astuple() == other.astuple()

    def __lt__(self, other) -> bool:
        # semver precedence: https://semver.org/#spec-item-11
        if isinstance(other, str):
            other = Version(other, loose=self._loose)
        if not isinstance(other, Version):
            raise TypeError

        if self.core < other.core:
            return True

        if self.core == other.core:
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

    def difference(self, other) -> Optional[VersionPart]:
        # pylint: disable=too-many-return-statements
        if other is None:
            return None
        if not isinstance(other, Version):
            other = Version(other, loose=self._loose)
        if self.major != other.major:
            return VersionPart.MAJOR
        if self.minor != other.minor:
            return VersionPart.MINOR
        if self.patch != other.patch:
            return VersionPart.PATCH
        if self.prerelease != other.prerelease:
            return VersionPart.PRERELEASE
        if self.build != other.build:
            return VersionPart.BUILD
        return None


_REGEX_VERSION_RANGE_CONDITION = (
    rf"(?P<operator>=|>=|<=|>|<|~|\^)?"  # optional, default: "="
    rf"(?P<version>{_REGEX_SEMVER_LOOSE}|\*-?)"  # wildcard "*" / "*-" allowed
)
_PATTERN_VERSION_RANGE_CONDITION = re.compile(_REGEX_VERSION_RANGE_CONDITION)


class VersionRangeOperator(str, Enum):
    EQ = "="
    GE = ">="
    LE = "<="
    GT = ">"
    LT = "<"
    TILDE = "~"
    CARET = "^"


@dataclass(frozen=True, order=False)
class VersionRangeCondition:
    operator: VersionRangeOperator
    version: Version
    include_prerelease: bool

    @classmethod
    def parse(cls, expression: str, include_prerelease: bool = False):
        match = _PATTERN_VERSION_RANGE_CONDITION.fullmatch(expression.strip())
        if not match:
            raise VersionError(f"Invalid version range condition '{expression}'")
        operator = match.group("operator") or "="
        version_str = match.group("version")
        if version_str == "*":
            return cls(VersionRangeOperator(">="), Version("0.0.0"), include_prerelease)
        if version_str == "*-":
            return cls(VersionRangeOperator(">="), Version("0.0.0"), True)
        version = Version(version_str, loose=True)
        return cls(
            operator=VersionRangeOperator(operator),
            version=version,
            include_prerelease=include_prerelease or version.prerelease is not None,
        )

    def satifies(self, other: Version) -> bool:
        # pylint: disable=too-many-return-statements
        if other.prerelease and not self.include_prerelease:
            return False
        if self.operator == "=":
            return other == self.version
        if self.operator == ">":
            return other > self.version
        if self.operator == ">=":
            return other >= self.version
        if self.operator == "<":
            return other < self.version
        if self.operator == "<=":
            return other <= self.version
        if self.operator == "~":
            # include everything greater than a particular version in the same minor range
            return other >= self.version and other.core[:2] == self.version.core[:2]
        if self.operator == "^":
            # include everything that does not increment the first non-zero portion of semver
            if other < self.version:
                return False
            i_first_nonzero = next((i for i, e in enumerate(self.version.core) if e != 0), -1)
            return other.core[i_first_nonzero] == self.version.core[i_first_nonzero]
        return False


class VersionRange:
    """
    Range of possible versions.

    References:
        - https://semver.npmjs.com
        - https://github.com/npm/node-semver
        - https://github.com/conan-io/conan/blob/develop2/conans/model/version_range.py
        - https://github.com/conan-io/conan/blob/develop2/conans/test/unittests/model/version/test_version_range.py
    """  # noqa, pylint: disable=line-too-long

    def __init__(self, value: str):
        self._str = value
        expression, *tokens = (s.strip() for s in value.split(","))
        include_prerelease_global = any("include_prerelease" in t for t in tokens)

        def gen_condition_set(expression: str):
            include_prerelease = include_prerelease_global
            for condition in expression.split():
                result = VersionRangeCondition.parse(condition, include_prerelease)
                # inherit include_prerelease from first/previous condition
                include_prerelease |= result.include_prerelease
                yield result

        self.condition_sets = [
            list(gen_condition_set(condition_set)) for condition_set in expression.split("||")
        ]

    def __str__(self) -> str:
        return self._str

    def __repr__(self) -> str:
        return f"VersionRange({self._str})"

    def __hash__(self) -> int:
        return hash(self._str)

    def __eq__(self, other) -> bool:
        if isinstance(other, str):
            other = VersionRange(other)
        if not isinstance(other, VersionRange):
            return False
        return self.condition_sets == other.condition_sets

    def satifies(self, version: Version) -> bool:
        return any(
            all(cond.satifies(version) for cond in condition_set)
            for condition_set in self.condition_sets
        )

    def max_satifies(self, versions: Sequence[Version]) -> Optional[Version]:
        return next(
            (v for v in sorted(versions, reverse=True) if self.satifies(v)),
            None,
        )


VersionLike: TypeAlias = Union[str, Version]
VersionLikeOrRange: TypeAlias = Union[VersionLike, VersionRange]


def is_semantic_version(value) -> TypeGuard[Version]:
    """Check if value is a semantic version."""
    return isinstance(value, Version)


def find_update(
    current_version: VersionLike,
    versions: Sequence[VersionLike],
    target: VersionPart,
) -> Optional[Version]:
    """Find latest update for given target."""
    if not is_semantic_version(current_version):
        return None

    def is_update(v: Version) -> bool:
        assert is_semantic_version(current_version)
        return v > current_version and (v.difference(current_version) or 0) <= target

    versions_semantic = list(filter(is_semantic_version, versions))
    versions_update = list(filter(is_update, versions_semantic))
    return max(versions_update) if versions_update else None
