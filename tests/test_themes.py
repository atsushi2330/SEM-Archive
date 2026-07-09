from sem_archive.ui.themes import DEFAULT_THEME_ID, THEMES, apply_theme, theme_labels


def test_theme_catalog() -> None:
    labels = theme_labels()
    assert len(labels) >= 5
    assert labels[0][0] == DEFAULT_THEME_ID
    assert DEFAULT_THEME_ID in THEMES
    assert THEMES["sage"].label == "セージグリーン"
    assert THEMES["default"].stylesheet == ""


def test_apply_theme_default() -> None:
    # QApplicationなしでも落ちない
    assert apply_theme(None, "unknown") == DEFAULT_THEME_ID
