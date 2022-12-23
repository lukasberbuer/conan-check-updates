import asyncio
import json
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import AsyncIterator, List, Optional, Tuple, Union

from .version import Version, VersionLike, parse_version

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
        stdout = subprocess.check_output(("conan", "--version"))
        return parse_version(stdout.split()[-1].decode("utf-8"))

    return ConanExecutable(
        path=Path(conanexe),
        version=get_version(),
    )


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
        raise ValueError(f"Path is not a conanfile: {str(path)}")
    if path.is_dir():
        for filepath in (path / filename for filename in filenames):
            if filepath.exists():
                return filepath
        raise ValueError(f"Could not find conanfile in path: {str(path)}")
    raise ValueError(f"Invalid path: {str(path)}")


# https://docs.conan.io/en/1.55/reference/conanfile/attributes.html#name
_REGEX_CONAN_ATTRIBUTE = r"[a-zA-Z0-9_][a-zA-Z0-9_\+\.-]{1,50}"

_PATTERN_CONAN_REFERENCE = re.compile(
    rf"(?P<package>{_REGEX_CONAN_ATTRIBUTE})\/(?P<version>{_REGEX_CONAN_ATTRIBUTE})"
    rf"(?:@(?P<user>{_REGEX_CONAN_ATTRIBUTE})\/(?P<channel>{_REGEX_CONAN_ATTRIBUTE}))?"
)


class ConanReference:
    """Conan recipe reference of the form `name/version@user/channel`."""

    def __init__(self, reference: str):
        reference = reference.strip()
        match = _PATTERN_CONAN_REFERENCE.fullmatch(reference)
        if not match:
            raise ValueError(f"Invalid Conan reference '{reference}'")
        self._str = reference
        self._package = match.group("package")
        self._version = parse_version(match.group("version"))
        self._user = match.group("user")
        self._channel = match.group("channel")

    def __str__(self) -> str:
        return self._str

    def __repr__(self) -> str:
        return f"ConanReference({self._str})"

    def __eq__(self, other) -> bool:
        if not isinstance(other, ConanReference):
            return False
        return all(
            (
                self.package == other.package,
                self.version == other.version,
                self.user == other.user,
                self.channel == other.channel,
            )
        )

    @property
    def package(self) -> str:
        return self._package

    @property
    def version(self) -> Union[str, Version]:
        return self._version

    @property
    def user(self) -> Optional[str]:
        return self._user

    @property
    def channel(self) -> Optional[str]:
        return self._channel


async def _run_capture(cmd: str, timeout: Optional[int] = TIMEOUT) -> Tuple[bytes, bytes]:
    """
    Run process asynchronously and capture stdout and stderr.

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

    return stdout, stderr


async def resolve_requirements_v1(
    path: Union[str, Path],
    timeout: Optional[int] = TIMEOUT,
) -> List[ConanReference]:
    stdout, _ = await _run_capture(f"conan info {str(path)} --json", timeout)

    lines = stdout.decode().splitlines()
    obj = json.loads(lines[-1])  # last line is JSON
    node_conanfile = next(
        filter(lambda item: item["reference"] in ("conanfile.py", "conanfile.txt"), obj)
    )
    requires = (
        *node_conanfile.get("requires", []),
        *node_conanfile.get("build_requires", []),  # build/tool requirements
        *node_conanfile.get("tool_requires", []),  # currently not available
        *node_conanfile.get("test_requires", []),  # currently not available
    )
    return list(map(ConanReference, requires))


async def resolve_requirements_v2(
    path: Union[str, Path],
    timeout: Optional[int] = TIMEOUT,
) -> List[ConanReference]:
    stdout, _ = await _run_capture(f"conan graph info --format json {str(path)}", timeout)

    def strip_revision(refs_with_revision):
        return [ref.partition("#")[0] for ref in refs_with_revision]

    obj = json.loads(stdout.decode())
    node_conanfile = obj["nodes"][0]  # first node always root node?
    # assert node_conanfile["ref"] == "conanfile"
    assert node_conanfile["id"] == 0
    assert node_conanfile["recipe"] == "Consumer"
    id_requires_dict = node_conanfile.get("requires", {})  # build/tool/test requires included
    return list(map(ConanReference, strip_revision(id_requires_dict.values())))


async def resolve_requirements(
    path: Union[str, Path],
    timeout: Optional[int] = TIMEOUT,
) -> List[ConanReference]:
    """Get and resolve requirements with `conan info`."""
    conan_version = find_conan().version
    if conan_version.major == 1:
        return await resolve_requirements_v1(path, timeout)
    if conan_version.major == 2:
        return await resolve_requirements_v2(path, timeout)
    raise RuntimeError(f"Conan version {str(conan_version)} not supported")


async def search(
    package: Optional[str] = None,
    version: Optional[str] = None,
    user: Optional[str] = None,
    channel: Optional[str] = None,
    *,
    timeout: Optional[int] = TIMEOUT,
) -> List[ConanReference]:
    """Search package recipes on all remotes with `conan search`."""
    conan_version = find_conan().version
    search_string = f"{package or '*'}/{version or '*'}@{user or '*'}/{channel or '*'}"

    def get_command():
        if conan_version.major == 1:
            return f"conan search {search_string} --remote all --raw"
        if conan_version.major == 2:
            return f"conan search {search_string}"
        raise RuntimeError(f"Conan version {str(conan_version)} not supported")

    stdout, _ = await _run_capture(get_command(), timeout=timeout)
    return [
        ConanReference(match.group(0))
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
            versions=[r.version for r in refs],
        )
    except TimeoutError:
        raise TimeoutError(f"Timeout searching for {ref.package} versions") from None


async def search_versions_parallel(
    refs: List[ConanReference],
    *,
    timeout: int = TIMEOUT,
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
