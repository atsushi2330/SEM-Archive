from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtWidgets import QApplication


@dataclass(frozen=True)
class Theme:
    id: str
    label: str
    stylesheet: str


def _build_stylesheet(
    *,
    window: str,
    text: str,
    border: str,
    accent: str,
    accent_text: str,
    input_bg: str,
    group_bg: str,
    tab_bg: str,
    selection: str,
    button_fill: str,
    button_fill_hover: str,
    button_fill_pressed: str,
    button_text: str,
    button_border: str,
) -> str:
    return f"""
QWidget {{
    background-color: {window};
    color: {text};
}}
QMainWindow, QDialog {{
    background-color: {window};
}}
QGroupBox {{
    background-color: {group_bg};
    border: 1px solid {border};
    border-radius: 6px;
    margin-top: 10px;
    padding: 8px 6px 6px 6px;
    font-weight: 600;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 4px;
    color: {text};
}}
QLineEdit, QTextEdit, QSpinBox, QComboBox, QListWidget, QTableWidget, QTreeWidget {{
    background-color: {input_bg};
    color: {text};
    border: 1px solid {border};
    border-radius: 4px;
    padding: 3px;
    selection-background-color: {selection};
}}
QHeaderView::section {{
    background-color: {tab_bg};
    color: {text};
    border: 1px solid {border};
    padding: 4px;
}}
QTabWidget::pane {{
    border: 1px solid {border};
    background: {window};
    border-radius: 4px;
}}
QTabBar::tab {{
    background: {tab_bg};
    color: {text};
    border: 1px solid {border};
    border-bottom: none;
    padding: 6px 14px;
    margin-right: 2px;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
}}
QTabBar::tab:selected {{
    background: {window};
    border-bottom: 1px solid {window};
    color: {accent};
    font-weight: 600;
}}
QPushButton {{
    background-color: {button_fill};
    color: {button_text};
    border: 1px solid {button_border};
    border-radius: 5px;
    padding: 6px 14px;
    font-weight: 600;
}}
QPushButton:hover {{
    background-color: {button_fill_hover};
    border-color: {button_fill_hover};
}}
QPushButton:pressed {{
    background-color: {button_fill_pressed};
    border-color: {button_fill_pressed};
}}
QPushButton:disabled {{
    background-color: {tab_bg};
    color: {border};
    border-color: {border};
}}
QMenuBar {{
    background-color: {tab_bg};
    color: {text};
}}
QMenuBar::item:selected {{
    background-color: {selection};
}}
QScrollArea, QFrame#filterPopup, QFrame#previewPane {{
    background-color: {window};
    border: 1px solid {border};
    border-radius: 4px;
}}
QSplitter::handle {{
    background-color: {border};
}}
"""


THEMES: dict[str, Theme] = {
    "default": Theme("default", "標準（システム）", ""),
    "sage": Theme(
        "sage",
        "セージグリーン",
        _build_stylesheet(
            window="#f4f7f4",
            text="#2f3d32",
            border="#c5d4c7",
            accent="#5f8f66",
            accent_text="#ffffff",
            input_bg="#fafcfa",
            group_bg="#eef3ee",
            tab_bg="#e3ebe4",
            selection="#b8cfbb",
            button_fill="#5f8f66",
            button_fill_hover="#4f7d56",
            button_fill_pressed="#3f6b46",
            button_text="#ffffff",
            button_border="#4f7d56",
        ),
    ),
    "mist": Theme(
        "mist",
        "ミストブルー",
        _build_stylesheet(
            window="#f3f6f9",
            text="#2c3a47",
            border="#c5d2de",
            accent="#4f7ba5",
            accent_text="#ffffff",
            input_bg="#fafcfe",
            group_bg="#eaf0f5",
            tab_bg="#dfe8f0",
            selection="#b5c9dc",
            button_fill="#4f7ba5",
            button_fill_hover="#3f6d94",
            button_fill_pressed="#335d82",
            button_text="#ffffff",
            button_border="#3f6d94",
        ),
    ),
    "sand": Theme(
        "sand",
        "サンドベージュ",
        _build_stylesheet(
            window="#faf8f5",
            text="#3d362f",
            border="#ddd2c4",
            accent="#c49a63",
            accent_text="#ffffff",
            input_bg="#fffdfa",
            group_bg="#f3ede6",
            tab_bg="#ebe4db",
            selection="#dcc9b0",
            button_fill="#c49a63",
            button_fill_hover="#b0864f",
            button_fill_pressed="#967242",
            button_text="#ffffff",
            button_border="#b0864f",
        ),
    ),
    "lavender": Theme(
        "lavender",
        "ソフトラベンダー",
        _build_stylesheet(
            window="#f7f5fa",
            text="#3a3545",
            border="#d4cde0",
            accent="#8a74a8",
            accent_text="#ffffff",
            input_bg="#fcfbfe",
            group_bg="#efeaf5",
            tab_bg="#e5dff0",
            selection="#cfc2e3",
            button_fill="#8a74a8",
            button_fill_hover="#766394",
            button_fill_pressed="#625380",
            button_text="#ffffff",
            button_border="#766394",
        ),
    ),
    "slate": Theme(
        "slate",
        "クールスレート",
        _build_stylesheet(
            window="#f5f6f7",
            text="#2e3438",
            border="#c8cdd1",
            accent="#5c6b78",
            accent_text="#ffffff",
            input_bg="#fafbfc",
            group_bg="#eceef0",
            tab_bg="#e2e5e8",
            selection="#b8c2cb",
            button_fill="#5c6b78",
            button_fill_hover="#4d5a66",
            button_fill_pressed="#3f4a54",
            button_text="#ffffff",
            button_border="#4d5a66",
        ),
    ),
}

DEFAULT_THEME_ID = "default"


def theme_labels() -> list[tuple[str, str]]:
    return [(t.id, t.label) for t in THEMES.values()]


def apply_theme(app: QApplication | None, theme_id: str) -> str:
    """アプリ全体にテーマを適用し、適用した theme_id を返す。"""
    if app is None:
        return DEFAULT_THEME_ID
    theme = THEMES.get(theme_id, THEMES[DEFAULT_THEME_ID])
    app.setStyleSheet(theme.stylesheet)
    return theme.id
