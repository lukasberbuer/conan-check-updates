from pathlib import Path

import pytest

from conan_check_updates import RecipeReference, conan_info_requirements, conan_search


@pytest.mark.asyncio()
async def test_conan_search():
    refs = await conan_search("fmt")
    assert len(refs) > 0
    assert RecipeReference("fmt", "8.0.0") in refs


@pytest.mark.asyncio()
async def test_conan_info_requirements():
    cwd = Path(__file__).parent / "conanfile.txt"
    requirements = await conan_info_requirements(cwd)

    assert len(requirements) == 5

    assert "fmt/8.0.0" in requirements
    assert "spdlog/1.9.0" in requirements
    assert "nlohmann_json/3.7.3" in requirements
