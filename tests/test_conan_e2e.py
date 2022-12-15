from pathlib import Path

import pytest

from conan_check_updates.conan import RecipeReference, run_info, run_search


@pytest.mark.asyncio()
async def test_run_search():
    refs = await run_search("fmt")
    assert len(refs) > 0
    assert RecipeReference("fmt", "8.0.0") in refs


@pytest.mark.asyncio()
async def test_run_info():
    cwd = Path(__file__).parent / "conanfile.txt"
    result = await run_info(cwd)

    assert len(result.requires) == 4
    assert "fmt/8.0.0" in result.requires
    assert "spdlog/1.9.0" in result.requires
    assert "nlohmann_json/3.7.3" in result.requires

    assert len(result.build_requires) == 1
