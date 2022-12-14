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
    requirements = await run_info(cwd)

    assert len(requirements) == 5

    assert "fmt/8.0.0" in requirements
    assert "spdlog/1.9.0" in requirements
    assert "nlohmann_json/3.7.3" in requirements
