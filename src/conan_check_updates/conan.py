import asyncio
import json
import logging
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Collection, List, Optional, Union

from .version import Version, parse_version

TIMEOUT = 30

logger = logging.getLogger(__name__)


if sys.platform == "win32":
    # Proactor loop required by asyncio.create_subprocess_shell (default since Python 3.8)
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())


class ConanError(RuntimeError):
    pass


async def _run_capture_stdout(cmd: str, timeout: int = TIMEOUT) -> bytes:
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


async def run_info(path: Union[str, Path], timeout: int = TIMEOUT) -> List[str]:
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
    logger.debug("conan info result (only conanfile ref): %s", conanfile_reference)
    return [
        *conanfile_reference.get("requires", []),
        *conanfile_reference.get("build_requires", []),
    ]


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


async def run_search(
    package: str,
    user: Optional[str] = None,
    channel: Optional[str] = None,
    *,
    timeout: int = TIMEOUT,
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


async def run_search_versions(
    ref: RecipeReference,
    *,
    timeout: int = TIMEOUT,
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
    refs: List[RecipeReference], **kwargs
) -> List[VersionSearchResult]:
    coros = [run_search_versions(ref, **kwargs) for ref in refs]

    async def search():
        for coro in progressbar(asyncio.as_completed(coros), total=len(coros)):
            try:
                yield await coro
            except TimeoutError as e:
                logger.warning(e)  # noqa: G200

    results = [result async for result in search()]
    results_original_order = sorted(results, key=lambda result: refs.index(result.ref))
    return results_original_order
