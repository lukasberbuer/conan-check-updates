from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List, NamedTuple, Optional, Sequence

from .conan import (
    TIMEOUT,
    ConanReference,
    inspect_requires_conanfile,
    search_versions_parallel,
)
from .filter import matches_any
from .version import (
    Version,
    VersionLike,
    VersionLikeOrRange,
    VersionPart,
    VersionRange,
    find_update,
    is_semantic_version,
)


def resolve_version(
    version_or_range: VersionLikeOrRange,
    versions: Sequence[VersionLike],
) -> Optional[VersionLike]:
    if isinstance(version_or_range, VersionRange):
        versions_semantic = list(filter(is_semantic_version, versions))
        return version_or_range.max_satifies(versions_semantic)
    return version_or_range


@dataclass(frozen=True)
class CheckUpdateResult:
    ref: ConanReference
    versions: List[VersionLike]
    current_version: Optional[VersionLike]
    update_version: Optional[Version]


Progress = NamedTuple("Progress", [("done", int), ("total", int)])


async def check_updates(
    conanfile: Path,
    *,
    package_filter: Optional[Sequence[str]] = None,
    target: VersionPart = VersionPart.MAJOR,
    timeout: Optional[int] = TIMEOUT,
    progress_callback: Optional[Callable[[Progress], None]] = None
) -> List[CheckUpdateResult]:
    """
    Check for updates of conanfile.py/conanfile.txt requirements.

    Args:
        conanfile: Path to conanfile.py/conanfile.txt
        package_filter: Include only package names matching any of the given strings or patterns.
        target: Limit update level to given version part
        timeout: Timeout for Conan CLI in seconds
        progress_callback: Callback for progress updates
    """
    refs = inspect_requires_conanfile(conanfile)
    if package_filter:
        refs = [ref for ref in refs if matches_any(ref.package, *package_filter)]

    done = 0
    total = len(refs)
    if progress_callback:
        progress_callback(Progress(done, total))

    results: List[CheckUpdateResult] = []
    async for result in search_versions_parallel(refs, timeout=timeout):
        current_version_or_range = result.ref.version
        current_version_resolved = resolve_version(current_version_or_range, result.versions)

        update_version = (
            find_update(current_version_resolved, result.versions, target=target)
            if current_version_resolved
            else None
        )

        results.append(
            CheckUpdateResult(
                ref=result.ref,
                versions=result.versions,
                current_version=current_version_resolved,
                update_version=update_version,
            )
        )

        done += 1
        if progress_callback:
            progress_callback(Progress(done, total))

    return sorted(results, key=lambda r: r.ref.package)
