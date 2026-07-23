from intellichoice_evals.registry import ALL_CATEGORIES, missing_test_refs


def test_every_registered_test_ref_exists() -> None:
    assert missing_test_refs() == []


def test_every_item_has_test_refs_or_a_documented_reason() -> None:
    for category in ALL_CATEGORIES:
        for item in category.items:
            assert item.test_refs or item.not_applicable_reason, (category.name, item.name)


def test_spec_categories_are_all_registered() -> None:
    names = {category.name for category in ALL_CATEGORIES}
    assert names == {
        "Deterministic Evaluators",
        "Executable Evaluators",
        "Golden Dataset - Learning",
        "Golden Dataset - Q&A",
        "Golden Dataset - Authored Question Bank Bad Items",
    }
