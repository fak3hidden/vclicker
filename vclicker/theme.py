"""Dark theme tokens + Qt stylesheet."""

from __future__ import annotations

from string import Template

BG = "#08090C"
SIDEBAR = "#0B0D11"
CARD = "#10131A"
CARD_HI = "#151922"
SURFACE = "#0C0E13"
BORDER = "#1F242E"
BORDER_SOFT = "#181C24"
TEXT = "#E9ECF4"
MUTED = "#929AAF"
DIM = "#5F6779"
ON_ACCENT = "#0A0B0F"
DANGER = "#F87171"
SUCCESS = "#4ADE80"
WARN = "#FBBF24"

# name: (main, hover, pressed, soft, label)
ACCENTS: dict[str, tuple[str, str, str, str, str]] = {
    "indigo": ("#7C8CFF", "#93A2FF", "#6574E8", "#1B2140", "Indigo"),
    "violet": ("#A78BFA", "#BAA3FF", "#8F73E8", "#241E3D", "Violet"),
    "cyan": ("#2ED3E8", "#5AE1F2", "#1FB6C9", "#0D2830", "Cyan"),
    "emerald": ("#34D399", "#52E3AC", "#22B981", "#0E2A20", "Emerald"),
    "amber": ("#F5B84D", "#FFC96B", "#D99E33", "#2A2213", "Amber"),
    "rose": ("#FB7185", "#FF8A9B", "#E45E72", "#2C1A20", "Rose"),
}

FONT_STACK = '"Inter", "Segoe UI Variable Text", "Segoe UI", "SF Pro Text", "Ubuntu", "DejaVu Sans", sans-serif'


def accent_tuple(name: str) -> tuple[str, str, str, str, str]:
    return ACCENTS.get(name, ACCENTS["indigo"])


_QSS = Template("""
* { outline: none; }

QWidget {
    color: $text;
    font-family: $font;
    font-size: 13px;
}

QMainWindow, QDialog, #Root {
    background: $bg;
}

#Sidebar { background: $sidebar; border-right: 1px solid $border_soft; }
#ContentArea { background: $bg; }

QFrame[role="card"] {
    background: $card;
    border: 1px solid $border;
    border-radius: 16px;
}
QFrame[role="inset"] {
    background: $surface;
    border: 1px solid $border_soft;
    border-radius: 12px;
}
QFrame[role="tile"] {
    background: $card_hi;
    border: 1px solid $border_soft;
    border-radius: 14px;
}
QFrame[role="divider"] { background: $border_soft; border: none; max-height: 1px; }
QFrame[role="segmented"] {
    background: $surface;
    border: 1px solid $border_soft;
    border-radius: 11px;
}

QLabel { background: transparent; }
QLabel[role="pageTitle"] { font-size: 25px; font-weight: 700; color: $text; }
QLabel[role="pageSub"] { font-size: 13px; color: $muted; }
QLabel[role="cardTitle"] { font-size: 15px; font-weight: 600; color: $text; }
QLabel[role="cardDesc"] { font-size: 12px; color: $muted; }
QLabel[role="sectionTitle"] { font-size: 11px; font-weight: 700; color: $dim; }
QLabel[role="statValue"] { font-size: 27px; font-weight: 700; color: $text; }
QLabel[role="statUnit"] { font-size: 12px; font-weight: 600; color: $muted; }
QLabel[role="statLabel"] { font-size: 11px; font-weight: 600; color: $dim; }
QLabel[role="muted"] { color: $muted; }
QLabel[role="dim"] { color: $dim; font-size: 12px; }
QLabel[role="mono"] {
    font-family: "JetBrains Mono", "Cascadia Mono", "Consolas", monospace;
    font-size: 12px; color: $muted;
}
QLabel[role="key"] {
    background: $surface; border: 1px solid $border; border-radius: 7px;
    padding: 3px 9px; color: $text; font-size: 12px; font-weight: 600;
}
QLabel[role="pill"] {
    border-radius: 11px; padding: 5px 12px; font-size: 11px; font-weight: 700;
    background: $surface; color: $muted; border: 1px solid $border_soft;
}
QLabel[role="pill"][state="on"] {
    background: $accent_soft; color: $accent; border: 1px solid $accent_border;
}
QLabel[role="pill"][state="live"] {
    background: rgba(74, 222, 128, 0.12); color: $success;
    border: 1px solid rgba(74, 222, 128, 0.35);
}
QLabel[role="pill"][state="warn"] {
    background: rgba(251, 191, 36, 0.12); color: $warn;
    border: 1px solid rgba(251, 191, 36, 0.35);
}
QLabel[role="pill"][state="bad"] {
    background: rgba(248, 113, 113, 0.12); color: $danger;
    border: 1px solid rgba(248, 113, 113, 0.35);
}
QLabel[role="badge"] {
    background: $surface; border: 1px solid $border_soft; border-radius: 8px;
    padding: 2px 8px; font-size: 11px; color: $muted; font-weight: 600;
}
QLabel[role="badge"][tone="accent"] {
    background: $accent_soft; color: $accent; border: 1px solid $accent_border;
}

QPushButton {
    background: $card_hi;
    color: $text;
    border: 1px solid $border;
    border-radius: 10px;
    padding: 8px 14px;
    font-weight: 500;
}
QPushButton:hover { background: #1A1F29; border-color: #2B3240; }
QPushButton:pressed { background: #131720; }
QPushButton:disabled { background: #0E1117; color: $dim; border-color: $border_soft; }

QPushButton[variant="primary"] {
    background: $accent; color: $on_accent; border: 1px solid transparent; font-weight: 700;
}
QPushButton[variant="primary"]:hover { background: $accent_hover; }
QPushButton[variant="primary"]:pressed { background: $accent_press; }
QPushButton[variant="primary"]:disabled { background: #20242E; color: $dim; }

QPushButton[variant="hero"] {
    background: $accent; color: $on_accent; border: none; border-radius: 14px;
    padding: 14px 24px; font-size: 15px; font-weight: 700;
}
QPushButton[variant="hero"]:hover { background: $accent_hover; }
QPushButton[variant="hero"]:pressed { background: $accent_press; }

QPushButton[variant="danger"] {
    background: rgba(248, 113, 113, 0.13); color: $danger;
    border: 1px solid rgba(248, 113, 113, 0.32); font-weight: 600;
}
QPushButton[variant="danger"]:hover { background: rgba(248, 113, 113, 0.2); }
QPushButton[variant="danger"]:disabled {
    background: #12151B; color: #4C5464; border-color: #1B2029;
}
QPushButton[variant="ghost"]:disabled { color: #4C5464; border-color: #1A1E26; }
QPushButton[variant="hero"]:disabled { background: #1D2230; color: #59617A; }

QPushButton[variant="ghost"] { background: transparent; border: 1px solid $border; }
QPushButton[variant="ghost"]:hover { background: $card_hi; }

QPushButton[variant="icon"] {
    background: transparent; border: none; border-radius: 8px; padding: 6px;
}
QPushButton[variant="icon"]:hover { background: $card_hi; }
QPushButton[variant="icon"]:checked { background: $accent_soft; }

QPushButton[variant="nav"] {
    background: transparent; border: none; border-radius: 11px; padding: 10px 12px;
    color: $muted; font-weight: 500; text-align: left;
}
QPushButton[variant="nav"]:hover { background: #12151C; color: $text; }
QPushButton[variant="nav"]:checked {
    background: $accent_soft; color: $text; font-weight: 600;
    border: 1px solid $accent_border;
}

QPushButton[variant="segment"] {
    background: transparent; border: none; border-radius: 8px; padding: 7px 12px;
    color: $muted; font-weight: 600; font-size: 12px;
}
QPushButton[variant="segment"]:hover { color: $text; background: #171B24; }
QPushButton[variant="segment"]:checked { background: $accent_soft; color: $accent; }

QPushButton[variant="chip"] {
    background: $surface; border: 1px solid $border; border-radius: 9px;
    padding: 7px 12px; color: $text; font-weight: 600;
}
QPushButton[variant="chip"]:hover { border-color: $accent_border; color: $accent; }
QPushButton[variant="chip"][capturing="true"] {
    background: $accent_soft; border: 1px solid $accent; color: $accent;
}

QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QPlainTextEdit {
    background: $surface;
    border: 1px solid $border;
    border-radius: 9px;
    padding: 7px 10px;
    color: $text;
    selection-background-color: $accent;
    selection-color: $on_accent;
}
QLineEdit:hover, QSpinBox:hover, QDoubleSpinBox:hover, QComboBox:hover { border-color: #2B3240; }
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus, QPlainTextEdit:focus {
    border-color: $accent;
}
QLineEdit:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled, QComboBox:disabled { color: $dim; }

QSpinBox::up-button, QSpinBox::down-button,
QDoubleSpinBox::up-button, QDoubleSpinBox::down-button { width: 0px; height: 0px; border: none; }

QComboBox::drop-down { border: none; width: 22px; }
QComboBox::down-arrow { image: url($chevron); width: 11px; height: 11px; }
QComboBox QAbstractItemView {
    background: $card_hi; border: 1px solid $border; border-radius: 10px;
    selection-background-color: $accent_soft; selection-color: $text; padding: 4px;
}

QSlider::groove:horizontal {
    height: 6px; background: #1A1E27; border-radius: 3px;
}
QSlider::sub-page:horizontal { background: $accent; border-radius: 3px; }
QSlider::add-page:horizontal { background: #1A1E27; border-radius: 3px; }
QSlider::handle:horizontal {
    width: 16px; height: 16px; margin: -6px 0; border-radius: 9px;
    background: #FFFFFF; border: 3px solid $accent;
}
QSlider::handle:horizontal:hover { background: $accent_hover; }

QCheckBox { spacing: 9px; color: $text; font-size: 13px; }
QCheckBox::indicator {
    width: 18px; height: 18px; border-radius: 6px;
    border: 1px solid #2A303D; background: $surface;
}
QCheckBox::indicator:hover { border-color: $accent; }
QCheckBox::indicator:checked {
    background: $accent; border-color: $accent; image: url($check);
}

QScrollArea, QScrollArea > QWidget > QWidget { background: transparent; border: none; }
QScrollBar:vertical { background: transparent; width: 10px; margin: 4px 2px 4px 0; }
QScrollBar::handle:vertical { background: #262C38; border-radius: 4px; min-height: 34px; }
QScrollBar::handle:vertical:hover { background: #323A4A; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
QScrollBar:horizontal { background: transparent; height: 10px; margin: 0 4px 2px 4px; }
QScrollBar::handle:horizontal { background: #262C38; border-radius: 4px; min-width: 34px; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal { background: transparent; }

QListWidget, QTableWidget, QTreeWidget {
    background: transparent; border: none; outline: none;
}
QListWidget::item { border-radius: 10px; padding: 4px; margin: 2px 0; }
QListWidget::item:hover { background: #131720; }
QListWidget::item:selected { background: $accent_soft; color: $text; }
QTableWidget { gridline-color: transparent; }
QTableWidget::item { padding: 6px; border: none; }
QTableWidget::item:selected { background: $accent_soft; color: $text; }
QHeaderView::section {
    background: transparent; color: $dim; border: none; padding: 6px 4px;
    font-size: 11px; font-weight: 700;
}
QTableCornerButton::section { background: transparent; border: none; }

QProgressBar {
    background: #1A1E27; border: none; border-radius: 4px; height: 8px; text-align: center;
}
QProgressBar::chunk { background: $accent; border-radius: 4px; }

QMenu { background: $card_hi; border: 1px solid $border; border-radius: 10px; padding: 6px; }
QMenu::item { padding: 7px 20px 7px 14px; border-radius: 7px; color: $text; }
QMenu::item:selected { background: $accent_soft; }
QMenu::separator { height: 1px; background: $border; margin: 5px 8px; }

QToolTip {
    background: $card_hi; color: $text; border: 1px solid $border;
    border-radius: 8px; padding: 6px 9px; font-size: 12px;
}

QSplitter::handle { background: transparent; }

QMessageBox { background: $card; }
QMessageBox QLabel { color: $text; }
QFileDialog { background: $bg; }
""")


def build_stylesheet(accent: str = "indigo", check_icon: str = "", chevron_icon: str = "") -> str:
    main, hover, pressed, soft, _label = accent_tuple(accent)
    return _QSS.substitute(
        font=FONT_STACK,
        bg=BG,
        sidebar=SIDEBAR,
        card=CARD,
        card_hi=CARD_HI,
        surface=SURFACE,
        border=BORDER,
        border_soft=BORDER_SOFT,
        text=TEXT,
        muted=MUTED,
        dim=DIM,
        accent=main,
        accent_hover=hover,
        accent_press=pressed,
        accent_soft=soft,
        accent_border=_with_alpha(main, 0.35),
        on_accent=ON_ACCENT,
        danger=DANGER,
        success=SUCCESS,
        warn=WARN,
        check=check_icon.replace("\\", "/"),
        chevron=chevron_icon.replace("\\", "/"),
    )


def _with_alpha(hex_color: str, alpha: float) -> str:
    hex_color = hex_color.lstrip("#")
    r = int(hex_color[0:2], 16)
    g = int(hex_color[2:4], 16)
    b = int(hex_color[4:6], 16)
    return f"rgba({r}, {g}, {b}, {int(alpha * 255)})"
