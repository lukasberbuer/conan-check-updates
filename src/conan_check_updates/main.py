import sys
from dataclasses import dataclass, replace
from pathlib import Path
from typing import List, Optional, Sequence

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

if sys.version_info >= (3, 8):
    from typing import Protocol
else:
    from typing_extensions import Protocol


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


class ProgressCallback(Protocol):
    def __call__(self, done: int, total: int):
        ...


async def check_updates(
    conanfile: Path,
    *,
    package_filter: Optional[Sequence[str]] = None,
    target: VersionPart = VersionPart.MAJOR,
    timeout: Optional[int] = TIMEOUT,
    progress_callback: Optional[ProgressCallback] = None,
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
        progress_callback(done=done, total=total)

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
            progress_callback(done=done, total=total)

    return sorted(results, key=lambda r: r.ref.package)


def upgrade_conanfile(conanfile: Path, update_results: Sequence[CheckUpdateResult]):
    """
    Overwrite requirements in conanfile.py/conanfile.txt.

    Args:
        conanfile: Path to conanfile.py/conanfile.txt
        update_results: Results from `check_updates`
    """
    content = conanfile.read_text(encoding="utf-8")

    for result in update_results:
        if not result.current_version or not result.update_version:
            continue

        occurrences = content.count(str(result.ref))
        if occurrences < 1:
            raise RuntimeError(f"Reference '{str(result.ref)}' not found in conanfile")
        if occurrences > 1:
            raise RuntimeError(
                f"Multiple occurrences of reference '{str(result.ref)}' in conanfile"
            )

        # generate new reference with update version
        new_ref = replace(
            result.ref,
            version=result.update_version,
            revision=None,  # will be invalidated with new version
        )

        # replace reference strings
        content = content.replace(str(result.ref), str(new_ref), 1)

    conanfile.write_text(content, encoding="utf-8")
