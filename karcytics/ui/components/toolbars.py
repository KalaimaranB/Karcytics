"""Analysis toolbars."""

from karcytics_sdk.plugin import SecondaryButton
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QWidget

from karcytics.ui.theme import Colors, Fonts, theme_manager


class AnalysisToolBar(QWidget):
    """Slim contextual toolbar shown above the analysis splitter."""

    def __init__(self, title: str, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("analysisToolBar")
        theme_manager.apply_style(
            self,
            f"QWidget#analysisToolBar {{"
            f"  background: {Colors.BG_DARK};"
            f"  border-bottom: 1px solid {Colors.BORDER};"
            f"}}",
        )
        self.setFixedHeight(42)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 0, 14, 0)
        layout.setSpacing(8)

        self.btn_close_project = SecondaryButton("🏠 Return to Hub")
        layout.addWidget(self.btn_close_project)

        self.btn_home = SecondaryButton("← Home")
        self.btn_home.setObjectName("btn_home")
        layout.addWidget(self.btn_home)

        # AI Chat feature is currently in the works - UI hidden for now
        # self.btn_ai = SecondaryButton("🧠 AI Chat")
        # layout.addWidget(self.btn_ai)

        self.sep = QFrame()
        self.sep.setFrameShape(QFrame.Shape.VLine)
        layout.addWidget(self.sep)

        self.title_lbl = QLabel(f"🔬  {title}")
        theme_manager.apply_style(
            self.title_lbl,
            f"font-size: {Fonts.SIZE_NORMAL}px; font-weight: 600;"
            f" color: {Colors.FG_PRIMARY}; background: transparent;",
        )
        layout.addWidget(self.title_lbl)
        layout.addStretch()

        theme_manager.theme_changed.connect(self._apply_theme_styles)

        self._apply_theme_styles()

    def set_title(self, icon: str, name: str) -> None:
        self.title_lbl.setText(f"{icon}  {name}")

    def _apply_theme_styles(self) -> None:
        theme_manager.apply_style(
            self,
            f"QWidget#analysisToolBar {{"
            f"  background: {Colors.BG_DARK};"
            f"  border-bottom: 1px solid {Colors.BORDER};"
            f"}}",
        )
        theme_manager.apply_style(
            self.title_lbl,
            f"font-size: {Fonts.SIZE_NORMAL}px; font-weight: 600;"
            f" color: {Colors.FG_PRIMARY}; background: transparent;",
        )
        theme_manager.apply_style(self.sep, f"color: {Colors.BORDER};")
