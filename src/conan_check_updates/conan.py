import asyncio
import json
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import AsyncIterator, List, Optional, Union

from .version import Version, parse_version

TIMEOUT = 30


if sys.platform == "win32":
    # Proactor loop required by asyncio.create_subprocess_shell (default since Python 3.8)
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())


class ConanError(RuntimeError):
    """Raised when the Conan CLI returns an error."""


@dataclass(frozen=True)
class ConanExecutable:
    path: Path
    version: Version


@lru_cache(maxsize=1)
def find_conan() -> ConanExecutable:
    """Find Conan executable and detect version."""
    conanexe = shutil.which("conan")
    if conanexe is None:
        raise RuntimeError("Conan executable not found")

    def get_version():
        stdout = subprocess.check_output(f"{conanexe} --version")
        return parse_version(stdout.split()[-1].decode("utf-8"))

    return ConanExecutable(
        path=Path(conanexe),
        version=get_version(),
    )


def find_conanfile(path_or_reference: Path) -> Path:
    """
    Find conanfile.py/conanfile.txt.

    Args:
        path_or_reference: Path to a folder containing a recipe or path to a recipe file

    Raises:
        ValueError: If conanfile isn't found in given path or if path is invalid
    """
    filenames = ("conanfile.py", "conanfile.txt")  # prefer conanfile.py
    if path_or_reference.is_file():
        if path_or_reference.name in filenames:
            return path_or_reference
        raise ValueError(f"Path is not a conanfile: {str(path_or_reference)}")
    if path_or_reference.is_dir():
        for filepath in (path_or_reference / filename for filename in filenames):
            if filepath.exists():
                return filepath
        raise ValueError(f"Could not find conanfile in path: {str(path_or_reference)}")
    raise ValueError(f"Invalid path: {str(path_or_reference)}")


async def _run_capture_stdout(cmd: str, timeout: Optional[int] = TIMEOUT) -> bytes:
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
    except (asyncio.TimeoutError, TimeoutError):
        raise TimeoutError(f"Timeout during {cmd}") from None

    if process.returncode != 0:
        raise ConanError(stderr.decode())

    return stdout


@dataclass
class ConanInfoResult:
    reference: str
    requires: List[str]
    build_requires: List[str]
    output: Optional[str] = None  # stdout capture


async def run_info(path: Union[str, Path], timeout: Optional[int] = TIMEOUT) -> ConanInfoResult:
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

    result = json.loads(result_json)
    conanfile_reference = next(
        filter(
            lambda obj: obj["reference"] in ("conanfile.py", "conanfile.txt"),
            result,
        )
    )
    return ConanInfoResult(
        reference=conanfile_reference["reference"],
        requires=conanfile_reference.get("requires", []),
        build_requires=conanfile_reference.get("build_requires", []),
        output="\n".join(output) if output else None,
    )


# https://docs.conan.io/en/1.55/reference/conanfile/attributes.html#name
_PATTERN_CONAN_REFERENCE = re.compile(
    r"^"
    r"(?P<package>\w[\w\+\.-]+)\/(?P<version>\w[\w\+\.-]+)"
    r"(?:@(?P<user>\w[\w\+\.-]+)\/(?P<channel>\w[\w\+\.-]+))?"
    r"$"
)


@dataclass
class ConanReference:
    """Parsed Conan reference of the form `name/version@user/channel`."""

    package: str
    version: Union[str, Version]
    user: Optional[str] = None
    channel: Optional[str] = None

    def __post_init__(self):
        if isinstance(self.version, str):
            self.version = parse_version(self.version)


def parse_conan_reference(reference: str) -> ConanReference:
    """Parse Conan reference."""
    match = _PATTERN_CONAN_REFERENCE.match(reference.strip())
    if not match:
        raise ValueError(f"Invalid Conan reference '{reference}'")

    return ConanReference(
        match.group("package"),
        parse_version(match.group("version")),
        match.group("user") or None,
        match.group("channel") or None,
    )


async def run_search(
    package: str,
    user: Optional[str] = None,
    channel: Optional[str] = None,
    *,
    timeout: Optional[int] = TIMEOUT,
) -> List[ConanReference]:
    """Search available recipes on all remotes with `conan search`."""
    stdout = await _run_capture_stdout(
        f'conan search "{package}/*" --remote all --raw',
        timeout=timeout,
    )

    lines = stdout.decode().splitlines()
    lines_stripped = (line.strip() for line in lines)
    lines_filtered = filter(_PATTERN_CONAN_REFERENCE.match, lines_stripped)
    refs = map(parse_conan_reference, lines_filtered)
    refs_filtered = filter(lambda ref: ref.user == user and ref.channel == channel, refs)
    return list(refs_filtered)


@dataclass
class VersionSearchResult:
    ref: ConanReference
    versions: List[Union[str, Version]]


async def run_search_versions(
    ref: ConanReference,
    *,
    timeout: Optional[int] = TIMEOUT,
) -> VersionSearchResult:
    try:
        refs = await run_search(ref.package, user=ref.user, channel=ref.channel, timeout=timeout)
        return VersionSearchResult(
            ref=ref,
            versions=[r.version for r in refs],  # type: ignore
        )
    except TimeoutError:
        raise TimeoutError(f"Timeout searching for {ref.package} versions") from None


async def run_search_versions_parallel(
    refs: List[ConanReference],
    *,
    timeout: int = TIMEOUT,
) -> AsyncIterator[VersionSearchResult]:
    coros = asyncio.as_completed(
        [run_search_versions(ref, timeout=None) for ref in refs],
        timeout=timeout,  # use global timeout, disable timeout of single searches
    )
    try:
        for coro in coros:
            yield await coro
    except (asyncio.TimeoutError, TimeoutError):
        raise TimeoutError("Timeout searching for package versions") from None
