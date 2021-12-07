"""Top-level package for conan-check-updates."""

import asyncio
import json
import logging
import sys
from dataclasses import dataclass
from enum import Enum, auto
from functools import total_ordering
from pathlib import Path
from typing import Collection, List, Optional, Union

from semver import SemVer

logger = logging.getLogger(__name__)


if sys.platform == "win32":
    # Proactor loop required by asyncio.create_subprocess_shell (default since Python 3.8)
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())


class VersionError(ValueError):
    pass


class ConanError(RuntimeError):
    pass


async def conan_info_requirements(path: Union[str, Path]) -> List[str]:
    """Get and resolve requirements with `conan info`."""
    process = await asyncio.create_subprocess_shell(
        f"conan info {str(path)} --json",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate()  # wait for subprocess to finish

    if process.returncode != 0:
        raise ConanError(stderr.decode())

    lines = stdout.decode().splitlines()
    lines_filtered = filter(bool, lines)

    *output, result_json = filter(bool, lines_filtered)

    if output:
        logger.info("\n".join(output))

    result = json.loads(result_json)
    conanfile_reference = next(
        filter(
            lambda obj: obj["reference"] in ("conanfile.py", "conanfile.txt"),
            result,
        )
    )
    return [
        *conanfile_reference.get("requires", []),
        *conanfile_reference.get("build_requires", []),
    ]


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


class VersionPart(Enum):
    MAJOR = auto()
    MINOR = auto()
    PATCH = auto()
    PRERELEASE = auto()
    BUILD = auto()


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


def parse_version(version: str) -> Union[str, Version]:
    """Parse version of conan recipe reference."""
    version = version.strip()
    try:
        return Version(version)
    except VersionError:
        return version


@dataclass
class RecipeReference:
    """Parsed recipe identifier of the form `name/version@user/channel`."""

    package: str
    version: Union[str, Version]
    user: Optional[str] = None
    channel: Optional[str] = None

    def __post_init__(self):
        if isinstance(self.version, str):
            self.version = parse_version(self.version)


def parse_recipe_reference(reference: str) -> RecipeReference:
    """Parse recipe reference."""
    package_version, _, user_channel = reference.partition("@")
    package, _, version = package_version.partition("/")
    user, _, channel = user_channel.partition("/")
    return RecipeReference(
        package,
        parse_version(version),
        user if user else None,
        channel if channel else None,
    )


def progressbar(
    it: Collection, total: Optional[int] = None, desc: str = "", size: int = 20, file=sys.stderr
):
    if total is None:
        total = len(it)

    def show(j):
        n = int(size * j / total)
        file.write(f"{desc}[{'=' * n}{'-' * (size - n)}] {j}/{total} {int(100 * j / total)}%\r")
        file.flush()

    show(0)
    for i, item in enumerate(it):
        yield item
        show(i + 1)
    file.write("\n")
    file.flush()


async def conan_search(
    package: str, user: Optional[str] = None, channel: Optional[str] = None
) -> List[RecipeReference]:
    """Search available recipes on all remotes with `conan search`."""
    process = await asyncio.create_subprocess_shell(
        f'conan search "{package}/*" --remote all --raw',
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate()  # wait for subprocess to finish

    if process.returncode != 0:
        raise ConanError(stderr.decode())

    lines = stdout.decode().splitlines()
    lines_filtered = filter(lambda line: not line.startswith("Remote "), lines)
    refs = map(parse_recipe_reference, lines_filtered)
    refs_filtered = filter(lambda ref: ref.user == user and ref.channel == channel, refs)
    return list(refs_filtered)


@dataclass
class VersionSearchResult:
    ref: RecipeReference
    versions: List[Union[str, Version]]


async def conan_search_versions(ref: RecipeReference) -> VersionSearchResult:
    refs = await conan_search(ref.package, user=ref.user, channel=ref.channel)
    return VersionSearchResult(
        ref=ref,
        versions=[r.version for r in refs],  # type: ignore
    )


async def conan_search_versions_parallel(
    refs: List[RecipeReference],
) -> List[VersionSearchResult]:
    coros = [conan_search_versions(ref) for ref in refs]

    async def search():
        for coro in progressbar(asyncio.as_completed(coros), total=len(coros)):
            yield await coro

    results = [result async for result in search()]
    results_original_order = sorted(results, key=lambda result: refs.index(result.ref))
    return results_original_order
