import asyncio
import re
import shutil
import subprocess
import sys
from ast import literal_eval
from collections import defaultdict
from dataclasses import dataclass
from functools import lru_cache
from itertools import chain
from pathlib import Path
from typing import AsyncIterator, List, Optional, Tuple
import json

from .version import (
    Version,
    VersionError,
    VersionLike,
    VersionLikeOrRange,
    VersionRange,
)

if sys.platform == "win32":
    # Proactor loop required by asyncio.create_subprocess_shell (default since Python 3.8)
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())


TIMEOUT = 30


class ConanError(RuntimeError):
    """Raised when the Conan CLI returns an error."""


def _run_capture(*args: str, timeout: Optional[int]) -> Tuple[bytes, bytes]:
    """Run process synchronously and capture stdout and stderr."""
    try:
        process = subprocess.run(
            args,
            capture_output=True,
            check=False,
            timeout=timeout,
        )
    except TimeoutError:
        cmd = " ".join(args)
        raise TimeoutError(f"Timeout during {cmd}") from None

    if process.returncode != 0:
        raise ConanError(process.stderr.decode())

    return process.stdout, process.stderr


async def _run_capture_async(*args: str, timeout: Optional[int]) -> Tuple[bytes, bytes]:
    """Run process asynchronously and capture stdout and stderr."""
    process = await asyncio.create_subprocess_exec(
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(
            process.communicate(),  # wait for subprocess to finish
            timeout=timeout,
        )
    except (asyncio.TimeoutError, TimeoutError):
        cmd = " ".join(args)
        raise TimeoutError(f"Timeout during {cmd}") from None

    if process.returncode != 0:
        raise ConanError(stderr.decode())

    return stdout, stderr


@lru_cache(maxsize=1)
def conan_version() -> Version:
    """Detect Conan version."""
    if shutil.which("conan") is None:
        raise RuntimeError("Conan executable not found")
    stdout, _ = _run_capture("conan", "--version", timeout=TIMEOUT)
    return Version(stdout.strip().rsplit(maxsplit=1)[-1].decode())


def find_conanfile(path: Path) -> Path:
    """
    Find conanfile.py/conanfile.txt.

    Args:
        path: Path to a folder containing a recipe or to a recipe file

    Raises:
        ValueError: If conanfile isn't found in given path or if path is invalid
    """
    filenames = ("conanfile.py", "conanfile.txt")  # prefer conanfile.py
    if path.is_file():
        if path.name in filenames:
            return path
        raise ValueError(f"Path is not a conanfile: {path!s}")
    if path.is_dir():
        for filepath in (path / filename for filename in filenames):
            if filepath.exists():
                return filepath
        raise ValueError(f"Could not find conanfile in path: {path!s}")
    raise ValueError(f"Invalid path: {path!s}")


# https://docs.conan.io/en/1.55/reference/conanfile/attributes.html#name
_REGEX_CONAN_ATTRIBUTE_V1 = r"[a-zA-Z0-9_][a-zA-Z0-9_+.-]{1,50}"
# https://docs.conan.io/en/2.0/reference/conanfile/attributes.html#name
_REGEX_CONAN_ATTRIBUTE_V2 = r"[a-z0-9_][a-z0-9_+.-]{1,100}"
_REGEX_CONAN_ATTRIBUTE = rf"{_REGEX_CONAN_ATTRIBUTE_V1}|{_REGEX_CONAN_ATTRIBUTE_V2}"
_REGEX_CONAN_VERSION_RANGE = r"\[.+\]"
_REGEX_CONAN_VERSION = rf"{_REGEX_CONAN_ATTRIBUTE}|{_REGEX_CONAN_VERSION_RANGE}"
_REGEX_CONAN_REVISION_MD5_SHA1 = r"[a-fA-F0-9]{32,40}"

_REGEX_CONAN_REFERENCE = (
    rf"(?P<package>{_REGEX_CONAN_ATTRIBUTE})"
    rf"\/(?P<version>{_REGEX_CONAN_VERSION})"
    rf"(?:#(?P<revision>{_REGEX_CONAN_REVISION_MD5_SHA1}))?"  # optional
    rf"(?:@(?P<user>{_REGEX_CONAN_ATTRIBUTE}))?"
    rf"(?:\/(?P<channel>{_REGEX_CONAN_ATTRIBUTE}))?"  # optional
)

_PATTERN_CONAN_REFERENCE = re.compile(_REGEX_CONAN_REFERENCE)


@dataclass(frozen=True)
class ConanReference:
    """Conan recipe reference of the form `name/version#revision@user/channel`."""

    package: str
    version: VersionLikeOrRange
    revision: Optional[str] = None
    user: Optional[str] = None
    channel: Optional[str] = None

    @classmethod
    def parse(cls, reference):
        reference = reference.strip() if isinstance(reference, str) else reference["ref"].strip()
        match = _PATTERN_CONAN_REFERENCE.fullmatch(reference)
        if not match:
            raise ValueError(f"Invalid Conan reference '{reference}'")

        def parse_version(value: str, *, loose: bool) -> VersionLikeOrRange:
            if value.startswith("[") and value.endswith("]"):
                return VersionRange(value[1:-1])
            try:
                return Version(value, loose=loose)
            except VersionError:
                return value

        return cls(
            package=match.group("package"),
            version=parse_version(match.group("version"), loose=True),
            revision=match.group("revision"),
            user=match.group("user"),
            channel=match.group("channel"),
        )

    def __str__(self) -> str:
        def version_str() -> str:
            if isinstance(self.version, VersionRange):
                return f"[{self.version!s}]"
            return f"{self.version!s}"

        result = f"{self.package}/{version_str()}"
        if self.revision:
            result += f"#{self.revision}"
        if self.user and self.channel:
            result += f"@{self.user}/{self.channel}"
        return result


_REQUIRES_ATTRIBUTES = ("requires", "build_requires", "tool_requires", "test_requires")


def _dequote(s: str) -> str:
    """If a string has single or double quotes around it, remove them."""
    min_length = 2
    if (len(s) >= min_length and s[0] == s[-1]) and s.startswith(("'", '"')):
        return s[1:-1]
    return s


def inspect_requirements_conanfile_py(conanfile: Path) -> List[ConanReference]:
    """Get requirements from requirements() method of conanfile.py"""
    assert conanfile.name == "conanfile.py"
    refs = []
    with open(conanfile, mode="r", encoding="utf-8") as file:
        for line_orig in file:
            line = line_orig.strip()
            # strip end of line comment
            line = line.partition(" #")[0].strip()
            # ignore empty line or line comments
            if not line or line.startswith("#"):
                continue
            res = re.search(r'self\.(?:(tool|python)_)*requires\("(.*)"(?:(\)|,.*))', line)
            if res is None:
                res = re.search(r'(tool|python)_requires = "(.*)"', line)
            if res:
                ref = res.group(2)
                if len(ref) > 0:
                    refs.append(ref)
    return list(map(ConanReference.parse, refs))

def inspect_requires_conanfile_py(conanfile: Path) -> List[ConanReference]:
    """Get requirements of conanfile.py with `conan inspect`."""
    assert conanfile.name == "conanfile.py"

    def get_command():
        if conan_version().major == 1:
            args = chain.from_iterable(("-a", attr) for attr in _REQUIRES_ATTRIBUTES)
            return ("conan", "inspect", str(conanfile), *args)
        if conan_version().major == 2:  # noqa: PLR2004
            return ("conan", "inspect", str(conanfile), "--format=json")
        raise RuntimeError(f"Conan version {conan_version()!s} not supported")

    stdout, _ = _run_capture(*get_command(), timeout=TIMEOUT)

    attributes = dict(json.loads(stdout.decode()))

    def gen_requires():
        for key, value in attributes.items():
            if key in _REQUIRES_ATTRIBUTES:
                if isinstance(value, (list, tuple, set)):
                    yield from value
                else:
                    yield value

    return list(map(ConanReference.parse, gen_requires()))


def inspect_requires_conanfile_txt(conanfile: Path) -> List[ConanReference]:
    """Get requirements of conanfile.txt."""
    assert conanfile.name == "conanfile.txt"

    attributes = defaultdict(list)
    with open(conanfile, mode="r", encoding="utf-8") as file:
        key = None
        for line_orig in file:
            line = line_orig.strip()
            # strip end of line comment
            line = line.partition(" #")[0].strip()
            # ignore empty line or line comments
            if not line or line.startswith("#"):
                continue
            if line.startswith("[") and line.endswith("]"):
                key = line[1:-1]
                continue
            if key is None:
                continue
            attributes[key].append(line)

    def gen_requires():
        for key in _REQUIRES_ATTRIBUTES:
            yield from attributes[key]

    return list(map(ConanReference.parse, gen_requires()))


def inspect_requires_conanfile(conanfile: Path) -> List[ConanReference]:
    """Get requirements of conanfile.py/conanfile.py"""
    if conanfile.name == "conanfile.py":
        return inspect_requires_conanfile_py(conanfile) + inspect_requirements_conanfile_py(conanfile)
    if conanfile.name == "conanfile.txt":
        return inspect_requires_conanfile_txt(conanfile)
    raise ValueError(f"Invalid conanfile: {conanfile!s}")


async def search(
    package: Optional[str] = None,
    version: Optional[str] = None,
    user: Optional[str] = None,
    channel: Optional[str] = None,
    *,
    timeout: Optional[int] = TIMEOUT,
) -> List[ConanReference]:
    """Search package recipes on all remotes with `conan search`."""
    pattern = f"{package or '*'}/{version or '*'}@{user or '*'}/{channel or '*'}"

    def get_command():
        if conan_version().major == 1:
            return ("conan", "search", pattern, "--remote", "all", "--raw")
        if conan_version().major == 2:  # noqa: PLR2004
            return ("conan", "search", pattern)
        raise RuntimeError(f"Conan version {conan_version()!s} not supported")

    stdout, _ = await _run_capture_async(*get_command(), timeout=timeout)
    return [
        ConanReference.parse(match.group(0))
        for match in _PATTERN_CONAN_REFERENCE.finditer(stdout.decode())
    ]


@dataclass(frozen=True)
class ConanSearchVersionsResult:
    ref: ConanReference
    versions: List[VersionLike]


async def search_versions(
    ref: ConanReference,
    *,
    timeout: Optional[int] = TIMEOUT,
) -> ConanSearchVersionsResult:
    try:
        refs = await search(ref.package, None, ref.user, ref.channel, timeout=timeout)
        return ConanSearchVersionsResult(
            ref=ref,
            # versions from `conan search` will never be ranges
            versions=[r.version for r in refs if isinstance(r.version, (str, Version))],
        )
    except TimeoutError:
        raise TimeoutError(f"Timeout searching for {ref.package} versions") from None


async def search_versions_parallel(
    refs: List[ConanReference],
    *,
    timeout: Optional[int] = TIMEOUT,
) -> AsyncIterator[ConanSearchVersionsResult]:
    coros = asyncio.as_completed(
        [search_versions(ref, timeout=None) for ref in refs],
        timeout=timeout,  # use global timeout, disable timeout of single searches
    )
    try:
        for coro in coros:
            yield await coro
    except (asyncio.TimeoutError, TimeoutError):
        raise TimeoutError("Timeout searching for package versions") from None
