from pipeline.transforms.slug import generate_slug, make_unique_slug


class TestGenerateSlug:
    def test_basic(self):
        assert generate_slug("The Bookshelf", "Guelph", "ON") == "the-bookshelf-guelph-on"

    def test_lowercase(self):
        slug = generate_slug("UPPER CASE BOOKS", "Toronto", "ON")
        assert slug == slug.lower()

    def test_spaces_become_dashes(self):
        result = generate_slug("Word Word Word", "City", "AB")
        assert " " not in result
        assert "-" in result

    def test_unicode_accents_removed(self):
        result = generate_slug("Librairie Québécoise", "Montréal", "QC")
        assert "é" not in result
        assert result == "librairie-quebecoise-montreal-qc"

    def test_ampersand_handled(self):
        result = generate_slug("Drawn & Quarterly", "Montreal", "QC")
        assert "&" not in result

    def test_special_chars_removed(self):
        result = generate_slug("Books! & More...", "City", "BC")
        assert "!" not in result
        assert "." not in result


class TestMakeUniqueSlug:
    def test_unique_slug_unchanged(self):
        existing = {"other-store-guelph-on"}
        result = make_unique_slug("the-bookshelf-guelph-on", existing)
        assert result == "the-bookshelf-guelph-on"

    def test_collision_appends_2(self):
        existing = {"the-bookshelf-guelph-on"}
        result = make_unique_slug("the-bookshelf-guelph-on", existing)
        assert result == "the-bookshelf-guelph-on-2"

    def test_multiple_collisions(self):
        existing = {
            "the-bookshelf-guelph-on",
            "the-bookshelf-guelph-on-2",
            "the-bookshelf-guelph-on-3",
        }
        result = make_unique_slug("the-bookshelf-guelph-on", existing)
        assert result == "the-bookshelf-guelph-on-4"

    def test_empty_existing_set(self):
        result = make_unique_slug("my-slug", set())
        assert result == "my-slug"

    def test_does_not_mutate_existing_set(self):
        existing = {"some-slug"}
        original_len = len(existing)
        make_unique_slug("other-slug", existing)
        assert len(existing) == original_len
