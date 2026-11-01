"""
Professional Engineering Theme QSS generation for GRaCEmo ViRa UARCC.
Engineered for clean desktop workstation usability, consistent hierarchy,
and high clarity across all modules.
"""

from .tokens import (
    COLOR_BG_MAIN,
    COLOR_SURFACE,
    COLOR_SURFACE_ALT,
    COLOR_PANEL_MAIN,
    COLOR_PANEL_SECONDARY,
    COLOR_SIDEBAR_BG,
    COLOR_SIDEBAR_ACTIVE,
    COLOR_SIDEBAR_HOVER,
    COLOR_TEXT_SIDEBAR,
    COLOR_TEXT_SIDEBAR_MUTED,
    COLOR_BORDER,
    COLOR_BORDER_LIGHT,
    COLOR_BORDER_FOCUS,
    COLOR_ACCENT_PRIMARY,
    COLOR_ACCENT_HOVER,
    COLOR_ACCENT_ACTIVE,
    COLOR_BRAND_ORANGE,
    COLOR_SUCCESS,
    COLOR_WARNING,
    COLOR_ERROR,
    COLOR_TEXT_PRIMARY,
    COLOR_TEXT_SECONDARY,
    COLOR_TEXT_MUTED,
    FONT_FAMILY_PRIMARY,
    FONT_FAMILY_MONO,
    BORDER_RADIUS_SM,
    BORDER_RADIUS_MD,
)


def get_application_stylesheet() -> str:
    """Return the master QSS stylesheet for the control center."""
    return f"""
    /* Global Window & Base Typography */
    QMainWindow {{
        background-color: {COLOR_BG_MAIN};
        color: {COLOR_TEXT_PRIMARY};
        font-family: {FONT_FAMILY_PRIMARY};
        font-size: 13px;
    }}

    QWidget {{
        color: {COLOR_TEXT_PRIMARY};
        font-family: {FONT_FAMILY_PRIMARY};
        font-size: 13px;
    }}

    /* Top Application Bar */
    QFrame#topStatusBar {{
        background-color: {COLOR_SURFACE};
        border-bottom: 1px solid {COLOR_BORDER};
        padding: 6px 16px;
    }}

    /* Persistent Sidebar Navigation */
    QFrame#sidebarPanel {{
        background-color: {COLOR_SIDEBAR_BG};
        border-right: 1px solid {COLOR_BORDER};
    }}

    QLabel.sidebarBrandTitle {{
        color: #FFFFFF;
        font-family: {FONT_FAMILY_PRIMARY};
        font-size: 15px;
        font-weight: 700;
        letter-spacing: 0.5px;
    }}

    QLabel.sidebarBrandSubtitle {{
        color: {COLOR_BRAND_ORANGE};
        font-family: {FONT_FAMILY_MONO};
        font-size: 10px;
        font-weight: 700;
        letter-spacing: 1px;
    }}

    QLabel.sidebarCategoryHeader {{
        color: {COLOR_TEXT_SIDEBAR_MUTED};
        font-family: {FONT_FAMILY_PRIMARY};
        font-size: 11px;
        font-weight: 700;
        letter-spacing: 1px;
        padding: 10px 16px 4px 16px;
        text-transform: uppercase;
    }}

    QPushButton.navButton {{
        background-color: transparent;
        color: {COLOR_TEXT_SIDEBAR};
        border: none;
        border-left: 3px solid transparent;
        padding: 8px 16px;
        text-align: left;
        font-size: 13px;
        font-weight: 500;
        border-radius: 0px;
    }}

    QPushButton.navButton:hover {{
        background-color: {COLOR_SIDEBAR_HOVER};
        color: #FFFFFF;
    }}

    QPushButton.navButton:checked {{
        background-color: {COLOR_SIDEBAR_ACTIVE};
        color: #FFFFFF;
        border-left: 3px solid {COLOR_BRAND_ORANGE};
        font-weight: 600;
    }}

    /* Persistent Bottom Notification Bar */
    QFrame#bottomNotificationBar {{
        background-color: {COLOR_SURFACE};
        border-top: 1px solid {COLOR_BORDER};
        padding: 4px 16px;
    }}

    /* Standard Cards & Surfaces */
    QFrame.cardPanel {{
        background-color: {COLOR_SURFACE};
        border: 1px solid {COLOR_BORDER};
        border-radius: {BORDER_RADIUS_MD}px;
        padding: 14px;
    }}

    QFrame.cardPanelElevated {{
        background-color: {COLOR_SURFACE};
        border: 1px solid {COLOR_BORDER};
        border-radius: {BORDER_RADIUS_MD}px;
        padding: 14px;
    }}

    QFrame.wellPanel {{
        background-color: {COLOR_PANEL_SECONDARY};
        border: 1px solid {COLOR_BORDER};
        border-radius: {BORDER_RADIUS_SM}px;
        padding: 10px;
    }}

    /* Typography Classes */
    QLabel.brandTitle {{
        color: {COLOR_TEXT_PRIMARY};
        font-size: 15px;
        font-weight: 700;
        letter-spacing: 0.3px;
    }}

    QLabel.brandSubtitle {{
        color: {COLOR_BRAND_ORANGE};
        font-size: 10px;
        font-weight: 700;
        letter-spacing: 1px;
    }}

    QLabel.pageTitle {{
        color: {COLOR_TEXT_PRIMARY};
        font-size: 20px;
        font-weight: 700;
    }}

    QLabel.pageSubtitle {{
        color: {COLOR_TEXT_SECONDARY};
        font-size: 12px;
        font-weight: 400;
    }}

    QLabel.sectionHeader {{
        color: {COLOR_TEXT_PRIMARY};
        font-size: 14px;
        font-weight: 600;
    }}

    QLabel.fieldLabel {{
        color: {COLOR_TEXT_SECONDARY};
        font-size: 11px;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }}

    /* Action Buttons */
    QPushButton.primaryButton {{
        background-color: {COLOR_ACCENT_PRIMARY};
        color: #FFFFFF;
        border: 1px solid {COLOR_ACCENT_PRIMARY};
        border-radius: {BORDER_RADIUS_SM}px;
        padding: 6px 14px;
        font-size: 13px;
        font-weight: 600;
    }}

    QPushButton.primaryButton:hover {{
        background-color: {COLOR_ACCENT_HOVER};
        border-color: {COLOR_ACCENT_HOVER};
    }}

    QPushButton.primaryButton:pressed {{
        background-color: {COLOR_ACCENT_ACTIVE};
        border-color: {COLOR_ACCENT_ACTIVE};
    }}

    QPushButton.primaryButton:disabled {{
        background-color: {COLOR_SURFACE_ALT};
        color: {COLOR_TEXT_MUTED};
        border-color: {COLOR_BORDER};
    }}

    QPushButton.secondaryButton {{
        background-color: {COLOR_SURFACE};
        color: {COLOR_TEXT_PRIMARY};
        border: 1px solid {COLOR_BORDER};
        border-radius: {BORDER_RADIUS_SM}px;
        padding: 6px 14px;
        font-size: 13px;
        font-weight: 500;
    }}

    QPushButton.secondaryButton:hover {{
        background-color: {COLOR_SURFACE_ALT};
        border-color: #CBD5E1;
        color: {COLOR_TEXT_PRIMARY};
    }}

    QPushButton.secondaryButton:pressed {{
        background-color: #E2E8F0;
    }}

    QPushButton.dangerButton {{
        background-color: {COLOR_ERROR};
        color: #FFFFFF;
        border: 1px solid {COLOR_ERROR};
        border-radius: {BORDER_RADIUS_SM}px;
        padding: 8px 16px;
        font-size: 13px;
        font-weight: 600;
    }}

    QPushButton.dangerButton:hover {{
        background-color: #B53838;
        border-color: #B53838;
    }}

    QPushButton.dangerButton:disabled {{
        background-color: #F8D7DA;
        color: #721C24;
        border-color: #F5C6CB;
    }}

    /* Inputs, Selectors, and Spinners */
    QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {{
        background-color: {COLOR_SURFACE};
        color: {COLOR_TEXT_PRIMARY};
        border: 1px solid {COLOR_BORDER};
        border-radius: {BORDER_RADIUS_SM}px;
        padding: 6px 10px;
        font-size: 13px;
    }}

    QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {{
        border: 1px solid {COLOR_BORDER_FOCUS};
    }}

    QComboBox::drop-down {{
        subcontrol-origin: padding;
        subcontrol-position: top right;
        width: 20px;
        border-left: 1px solid {COLOR_BORDER};
    }}

    QComboBox QAbstractItemView {{
        background-color: {COLOR_SURFACE};
        color: {COLOR_TEXT_PRIMARY};
        selection-background-color: {COLOR_SURFACE_ALT};
        selection-color: {COLOR_ACCENT_PRIMARY};
        border: 1px solid {COLOR_BORDER};
    }}

    /* Tables */
    QTableWidget {{
        background-color: {COLOR_SURFACE};
        color: {COLOR_TEXT_PRIMARY};
        gridline-color: {COLOR_BORDER_LIGHT};
        border: 1px solid {COLOR_BORDER};
        border-radius: {BORDER_RADIUS_SM}px;
        font-size: 12px;
    }}

    QTableWidget::item {{
        padding: 6px 8px;
    }}

    QTableWidget::item:selected {{
        background-color: #EAF2FA;
        color: {COLOR_TEXT_PRIMARY};
    }}

    QHeaderView::section {{
        background-color: {COLOR_SURFACE_ALT};
        color: {COLOR_TEXT_SECONDARY};
        font-size: 11px;
        font-weight: 600;
        padding: 6px 8px;
        border: none;
        border-bottom: 1px solid {COLOR_BORDER};
        border-right: 1px solid {COLOR_BORDER_LIGHT};
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }}

    /* Progress Bars */
    QProgressBar {{
        background-color: {COLOR_SURFACE_ALT};
        border: 1px solid {COLOR_BORDER};
        border-radius: 3px;
        text-align: center;
        color: {COLOR_TEXT_PRIMARY};
        font-size: 11px;
        font-weight: 600;
        height: 14px;
    }}

    QProgressBar::chunk {{
        background-color: {COLOR_ACCENT_PRIMARY};
        border-radius: 2px;
    }}

    /* Scrollbars */
    QScrollBar:vertical {{
        background-color: transparent;
        width: 8px;
        margin: 0px;
    }}

    QScrollBar::handle:vertical {{
        background-color: #CBD5E1;
        border-radius: 4px;
        min-height: 24px;
    }}

    QScrollBar::handle:vertical:hover {{
        background-color: #94A3B8;
    }}

    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0px;
    }}

    QScrollBar:horizontal {{
        background-color: transparent;
        height: 8px;
        margin: 0px;
    }}

    QScrollBar::handle:horizontal {{
        background-color: #CBD5E1;
        border-radius: 4px;
        min-width: 24px;
    }}

    QScrollBar::handle:horizontal:hover {{
        background-color: #94A3B8;
    }}

    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
        width: 0px;
    }}

    /* Tab Widget */
    QTabWidget::pane {{
        border: 1px solid {COLOR_BORDER};
        background-color: {COLOR_SURFACE};
        border-radius: {BORDER_RADIUS_SM}px;
    }}

    QTabBar::tab {{
        background-color: {COLOR_SURFACE_ALT};
        color: {COLOR_TEXT_SECONDARY};
        padding: 8px 16px;
        margin-right: 2px;
        border-top-left-radius: 4px;
        border-top-right-radius: 4px;
        font-weight: 500;
    }}

    QTabBar::tab:hover {{
        background-color: #E6ECF2;
        color: {COLOR_TEXT_PRIMARY};
    }}

    QTabBar::tab:selected {{
        background-color: {COLOR_SURFACE};
        color: {COLOR_ACCENT_PRIMARY};
        font-weight: 600;
        border-bottom: 2px solid {COLOR_ACCENT_PRIMARY};
    }}
    """
