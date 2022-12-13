"""Top-level package for conan-check-updates."""

import asyncio
import json
import logging
import sys
from dataclasses import dataclass
from enum import Enum, auto
from fnmatch import fnmatch
from functools import total_ordering
from pathlib import Path
from typing import Collection, List, Optional, Union

from semver import SemVer

_TIMEOUT = 30

logger = logging.getLogger(__name__)


if sys.platform == "win32":
    # Proactor loop required by asyncio.create_subprocess_shell (default since Python 3.8)
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())


class VersionError(ValueError):
    pass


class ConanError(RuntimeError):
    pass


async def _run_capture_stdout(cmd: str, timeout: int = _TIMEOUT) -> bytes:
    """
    Run process asynchronously and capture stdout.

    Args:
        cmd: Command to execute
        timeout: Timeout in seconds

    Raises:
        TimeoutError: If process doesn't finish within timeout
        ConanError: If exit code != 0
    """
    process = await asyncio.create_subprocess_shell(
        cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(
            process.communicate(),  # wait for subprocess to finish
            timeout=timeout,
        )
    except asyncio.TimeoutError:
        raise TimeoutError(f"Timeout during {cmd}") from None

    if process.returncode != 0:
        raise ConanError(stderr.decode())

    return stdout


async def conan_info_requirements(path: Union[str, Path], timeout: int = _TIMEOUT) -> List[str]:
    """Get and resolve requirements with `conan info`."""
    try:
        stdout = await _run_capture_stdout(
            f"conan info {str(path)} --json",
            timeout=timeout,
        )
    except TimeoutError:
        raise TimeoutError("Timeout resolving requirements with conan info") from None

    lines = stdout.decode().splitlines()
    lines_filtered = filter(bool, lines)
    *output, result_json = lines_filtered  # last line is JSON output

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


def matches_any(value: str, *patterns: str) -> bool:
    """
    Filter package names by patterns.

    Return `True` if any of the pattern matches. Wildcards `*` and `?` are allowed.
    Patterns can be inverted with a prepended !, e.g. `!boost*`.
    """
    if not patterns:
        return True

    def is_match(pattern):
        should_match = not pattern.startswith("!")
        pattern = pattern.lstrip("!")
        return fnmatch(value, pattern) == should_match

    return any(is_match(pattern) for pattern in patterns)


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
    package: str,
    user: Optional[str] = None,
    channel: Optional[str] = None,
    *,
    timeout: int = _TIMEOUT,
) -> List[RecipeReference]:
    """Search available recipes on all remotes with `conan search`."""
    stdout = await _run_capture_stdout(
        f'conan search "{package}/*" --remote all --raw',
        timeout=timeout,
    )

    lines = stdout.decode().splitlines()
    lines_filtered = filter(lambda line: not line.startswith("Remote "), lines)
    refs = map(parse_recipe_reference, lines_filtered)
    refs_filtered = filter(lambda ref: ref.user == user and ref.channel == channel, refs)
    return list(refs_filtered)


@dataclass
class VersionSearchResult:
    ref: RecipeReference
    versions: List[Union[str, Version]]

    def semantic_versioning(self) -> bool:
        return all(isinstance(v, Version) for v in [self.ref.version, *self.versions])

    def upgrade(self) -> Optional[Version]:
        versions_filtered = filter(lambda v: isinstance(v, Version), self.versions)
        versions_sorted = sorted(versions_filtered)
        return versions_sorted[-1] if versions_sorted else None  # type: ignore


async def conan_search_versions(
    ref: RecipeReference,
    *,
    timeout: int = _TIMEOUT,
) -> VersionSearchResult:
    try:
        refs = await conan_search(ref.package, user=ref.user, channel=ref.channel, timeout=timeout)
        return VersionSearchResult(
            ref=ref,
            versions=[r.version for r in refs],  # type: ignore
        )
    except TimeoutError:
        raise TimeoutError(f"Timeout searching for {ref.package} versions") from None


async def conan_search_versions_parallel(
    refs: List[RecipeReference], **kwargs
) -> List[VersionSearchResult]:
    coros = [conan_search_versions(ref, **kwargs) for ref in refs]

    async def search():
        for coro in progressbar(asyncio.as_completed(coros), total=len(coros)):
            try:
                yield await coro
            except TimeoutError as e:
                logger.warning(e)  # noqa: G200

    results = [result async for result in search()]
    results_original_order = sorted(results, key=lambda result: refs.index(result.ref))
    return results_original_order
