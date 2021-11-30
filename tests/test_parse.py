from conan_check_updates import RecipeReference, Version, parse_recipe_reference, parse_version


def test_parse_version():
    assert parse_version("0.1") == Version("0.1")


def test_recipe_reference_parse_version_post_init():
    assert isinstance(RecipeReference("pkg", "0.1.0").version, Version)
    assert RecipeReference("pkg", "0.1.0") == RecipeReference("pkg", Version("0.1.0"))


def test_parse_recipe_reference():
    assert parse_recipe_reference("pkg/0.1.0") == RecipeReference("pkg", Version("0.1.0"))

    assert parse_recipe_reference("pkg/0.1.0@user/stable") == RecipeReference(
        "pkg", Version("0.1.0"), "user", "stable"
    )
