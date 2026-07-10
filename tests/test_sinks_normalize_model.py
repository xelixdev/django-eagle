from eagle.sinks import _normalize_model
from test_project.models import Location


class TestNormalizeModel:
    def test_labelled_string_unknown_model_returns_unchanged(self) -> None:
        assert _normalize_model("test_project.NoSuchModel") == "test_project.NoSuchModel"

    def test_unique_bare_class_name_resolves_to_label(self) -> None:
        assert _normalize_model("Location") == Location._meta.label

    def test_unmatched_bare_class_name_returns_unchanged(self) -> None:
        assert _normalize_model("NoSuchClassAnywhere") == "NoSuchClassAnywhere"
