from typing import Dict, List
from unittest.mock import Mock, call, patch

import pytest
from conan_check_updates.conan import ConanReference, ConanSearchVersionsResult
from conan_check_updates.main import CheckUpdateResult, check_updates, upgrade_conanfile
from conan_check_updates.version import Version, VersionLike, VersionPart

MOCK_VERSIONS: Dict[str, List[VersionLike]] = {
    "fmt": [
        Version("8.0.0"),
        Version("8.0.1"),
        Version("8.1.1"),
        Version("9.0.0"),
        Version("9.1.0"),
    ],
    "rapidjson": [
        "cci.20200410",
        "cci.20211112",
        "cci.20220822",
    ],
}


async def mock_search_versions(ref: ConanReference, **_):
    return ConanSearchVersionsResult(ref, MOCK_VERSIONS.get(ref.package, []))


@pytest.mark.asyncio()
@pytest.mark.parametrize(
    ("requires", "target", "current_version", "update_version"),
    [
        ("fmt/8.0.0", VersionPart.MAJOR, Version("8.0.0"), Version("9.1.0")),
        ("fmt/8.0.0", VersionPart.MINOR, Version("8.0.0"), Version("8.1.1")),
        ("fmt/8.0.0", VersionPart.PATCH, Version("8.0.0"), Version("8.0.1")),
        ("fmt/9.1.0", VersionPart.MAJOR, Version("9.1.0"), None),
        ("fmt/[^8]", VersionPart.MAJOR, Version("8.1.1"), Version("9.1.0")),
        ("fmt/[>10]", VersionPart.MAJOR, None, None),
        ("rapidjson/cci.20211112", VersionPart.MAJOR, "cci.20211112", None),
        ("invalid/1.0", VersionPart.MAJOR, Version("1.0"), None),
    ],
)
async def test_check_updates(tmp_path, requires, target, current_version, update_version):
    conanfile = tmp_path / "conanfile.txt"
    conanfile.write_text(f"[requires]\n{requires}\n")

    progress_callback = Mock()

    with patch("conan_check_updates.conan.search_versions", side_effect=mock_search_versions):
        results = await check_updates(
            conanfile,
            target=target,
            progress_callback=progress_callback,
        )

    assert progress_callback.call_args_list == [
        call(done=0, total=1),
        call(done=1, total=1),
    ]

    ref = ConanReference.parse(requires)
    assert len(results) == 1
    assert results[0].ref == ref
    assert results[0].current_version == current_version
    assert results[0].versions == (await mock_search_versions(ref)).versions
    assert results[0].update_version == update_version


@pytest.mark.asyncio()
@pytest.mark.parametrize(
    ("package_filter", "package_list"),
    [
        ([], ["boost", "fmt", "zlib"]),
        (["*"], ["boost", "fmt", "zlib"]),
        (["!*"], []),
        (["f*"], ["fmt"]),
        (["!b*"], ["fmt", "zlib"]),
        (["boost", "fmt"], ["boost", "fmt"]),
    ],
)
async def test_check_updates_filter(tmp_path, package_filter, package_list):
    conanfile = tmp_path / "conanfile.txt"
    conanfile.write_text("\n".join(["[requires]", "boost/1.79.0", "fmt/9.0.0", "zlib/1.2.13"]))

    with patch("conan_check_updates.conan.search_versions", side_effect=mock_search_versions):
        results = await check_updates(conanfile, package_filter=package_filter)

    results_packages = [result.ref.package for result in results]
    assert results_packages == package_list


def update_result(ref: str, current_version: str, update_version: str):
    return CheckUpdateResult(
        ConanReference.parse(ref),
        [],
        Version(current_version) if current_version else None,
        Version(update_version) if update_version else None,
    )


def test_upgrade_conanfile(tmp_path):
    conanfile = tmp_path / "conanfile.txt"
    conanfile.write_text(
        (
            "[requires]\n"
            "boost/1.79.0#b5de48490dd951a2d299de5d82369cd5\n"
            "fmt/[^8.0]\n"
            "zlib/1.2.13\n"
        )
    )

    upgrade_conanfile(
        conanfile,
        [
            update_result("boost/1.79.0#b5de48490dd951a2d299de5d82369cd5", "1.79.0", "1.81.0"),
            update_result("fmt/[^8.0]", "8.1.1", "9.1.0"),
            update_result("zlib/1.2.13", "1.2.13", None),
        ],
    )

    lines = conanfile.read_text().splitlines()
    assert lines == ["[requires]", "boost/1.81.0", "fmt/9.1.0", "zlib/1.2.13"]


def test_upgrade_conanfile_fail(tmp_path):
    conanfile = tmp_path / "conanfile.txt"
    conanfile.write_text("[requires]\nboost/1.79.0\nboost/1.79.0\n")

    with pytest.raises(
        RuntimeError,
        match="Multiple occurrences of reference 'boost/1.79.0' in conanfile",
    ):
        upgrade_conanfile(conanfile, [update_result("boost/1.79.0", "1.79.0", "1.81.0")])

    with pytest.raises(
        RuntimeError,
        match="Reference 'boost/2.0.0' not found in conanfile",
    ):
        upgrade_conanfile(conanfile, [update_result("boost/2.0.0", "2.0.0", "2.0.1")])
