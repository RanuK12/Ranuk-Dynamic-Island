"""
Modern Apple/Windows 11 inspired Glassmorphism & Neon styles for Dynamic Island
"""

MAIN_STYLE = """
QWidget#IslandContainer {
    background-color: rgba(15, 17, 23, 0.94);
    border: 1px solid rgba(255, 255, 255, 0.12);
    border-radius: 19px;
}

QWidget#PillBar {
    background-color: transparent;
}

QLabel {
    color: #f0f3f6;
    font-family: 'Segoe UI Variable Display', 'Segoe UI', sans-serif;
}

QLabel#PillTitle {
    font-size: 13px;
    font-weight: 600;
    color: #ffffff;
}

QLabel#PillSub {
    font-size: 11px;
    color: #8b949e;
}

QLabel#SectionHeader {
    font-size: 13px;
    font-weight: 700;
    color: #e6edf3;
    padding-bottom: 4px;
}

QPushButton.nav-btn {
    background-color: rgba(255, 255, 255, 0.05);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 8px;
    color: #c9d1d9;
    font-size: 12px;
    font-weight: 600;
    padding: 6px 12px;
}

QPushButton.nav-btn:hover {
    background-color: rgba(255, 255, 255, 0.12);
    border: 1px solid rgba(255, 255, 255, 0.2);
    color: #ffffff;
}

QPushButton.nav-btn:checked {
    background-color: rgba(56, 139, 253, 0.25);
    border: 1px solid #388bfd;
    color: #58a6ff;
}

QFrame.card {
    background-color: rgba(255, 255, 255, 0.04);
    border: 1px solid rgba(255, 255, 255, 0.06);
    border-radius: 12px;
    padding: 10px;
}

QFrame.card:hover {
    border: 1px solid rgba(255, 255, 255, 0.14);
}

QPushButton.action-pill {
    background-color: #238636;
    color: #ffffff;
    font-weight: 600;
    font-size: 11px;
    border-radius: 6px;
    padding: 4px 10px;
    border: none;
}

QPushButton.action-pill:hover {
    background-color: #2ea043;
}

QScrollBar:vertical {
    background: transparent;
    width: 6px;
}

QScrollBar::handle:vertical {
    background: rgba(255, 255, 255, 0.15);
    border-radius: 3px;
}

QScrollBar::handle:vertical:hover {
    background: rgba(255, 255, 255, 0.3);
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}
"""
