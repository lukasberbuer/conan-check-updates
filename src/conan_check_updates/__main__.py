"""CLI."""

import argparse
import asyncio
import logging
from pathlib import Path

from . import (
    _TIMEOUT,
    Version,
    conan_info_requirements,
    conan_search_versions_parallel,
    parse_recipe_reference,
    version_difference,
)

logging.basicConfig(
    level=logging.INFO,
    # format="[%(levelname)s] %(asctime)s: %(message)s",
    format="[%(levelname)s] %(message)s",
    datefmt="%d.%m.%Y %H:%M:%S",
)


async def run(path: Path):
    requirements = await conan_info_requirements(path)
    refs = [parse_recipe_reference(r) for r in requirements]

    results = await conan_search_versions_parallel(refs)

    for result in results:
        print(result.ref.package, result.ref.version)
        print(result.versions)
        has_semantic_versioning = all(
            (isinstance(v, Version) for v in [result.ref.version, *result.versions])
        )
        if has_semantic_versioning:
            latest = sorted(result.versions)[-1]
            print(f"Latest: {latest}")
            print(version_difference(result.ref.version, latest))  # type: ignore
        print()


def main():
    """Main function executed by conan-check-updates executable."""

    class Formatter(argparse.ArgumentDefaultsHelpFormatter):
        "Custom argparse formatter."

    parser = argparse.ArgumentParser(
        "conan-check-updates",
        formatter_class=Formatter,
    )
    parser.add_argument(
        "filter",
        nargs="*",
        type=str,
        default=None,
        help="list or regex of package names to check (all others will be ignored)",
    )
    parser.add_argument(
        "--version, -V",
        action="store_true",
        help="output the version number",
    )
    parser.add_argument(
        "--cwd",
        type=lambda p: Path(p).resolve(),
        default=Path.cwd().resolve(),
        help=(
            "path to a folder containing a recipe or to a recipe file directly "
            "(conanfile.py or conanfile.txt)"
        ),
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=_TIMEOUT,
        help="global timeout for `conan info|search` in seconds",
    )
    args = parser.parse_args()

    print(args.filter)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(run(args.cwd))
    except KeyboardInterrupt:
        ...
