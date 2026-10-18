from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from karcytics.core.about_info import DEVELOPER_ABOUT
from karcytics.ui.theme import Colors, theme_manager


class AboutDeveloperDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("About the Developer")
        self.setFixedSize(500, 400)

        theme_manager.apply_style(
            self,
            f"background: {Colors.BG_DARKEST}; color: {Colors.FG_PRIMARY};",
        )

        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(20)

        # Header / Avatar row
        header_layout = QHBoxLayout()
        header_layout.setSpacing(15)

        avatar_lbl = QLabel("👨‍🔬")
        avatar_lbl.setFixedSize(64, 64)
        avatar_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        theme_manager.apply_style(
            avatar_lbl,
            f"background: {Colors.BG_DARKER}; font-size: 32px; border-radius: 32px; border: 1px solid {Colors.BORDER};",
        )
        self._load_avatar(avatar_lbl)
        header_layout.addWidget(avatar_lbl)

        title_layout = QVBoxLayout()
        title_layout.setSpacing(5)

        name_lbl = QLabel(DEVELOPER_ABOUT["name"])
        theme_manager.apply_style(
            name_lbl,
            f"color: {Colors.FG_PRIMARY}; font-size: 20px; font-weight: bold;",
        )

        role_lbl = QLabel(DEVELOPER_ABOUT["role"])
        theme_manager.apply_style(
            role_lbl,
            f"color: {Colors.FG_SECONDARY}; font-size: 14px;",
        )

        title_layout.addWidget(name_lbl)
        title_layout.addWidget(role_lbl)
        title_layout.addStretch()

        header_layout.addLayout(title_layout)
        header_layout.addStretch()

        layout.addLayout(header_layout)

        # Bio
        bio_text = "".join(
            f"<p>{paragraph}</p>" for paragraph in DEVELOPER_ABOUT["bio"].split("\n\n")
        )

        bio_lbl = QLabel(bio_text)
        bio_lbl.setWordWrap(True)
        bio_lbl.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        theme_manager.apply_style(
            bio_lbl,
            f"color: {Colors.FG_PRIMARY}; font-size: 13px; line-height: 1.5;",
        )

        layout.addWidget(bio_lbl)

        layout.addStretch()

        # Action Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(close_btn)

        layout.addLayout(btn_layout)

    def _load_avatar(self, label: QLabel):
        import urllib.request
        from pathlib import Path

        from PySide6.QtCore import Qt
        from PySide6.QtGui import QImage, QPainter, QPainterPath

        try:
            cache_dir = Path.home() / ".karcytics" / "cache"
            cache_dir.mkdir(parents=True, exist_ok=True)
            avatar_path = cache_dir / "kalaimaran_avatar.png"

            data = None
            if avatar_path.exists():
                with open(avatar_path, "rb") as f:
                    data = f.read()
            else:
                url = "https://github.com/KalaimaranB.png?size=128"
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                data = urllib.request.urlopen(req, timeout=3).read()
                with open(avatar_path, "wb") as f:
                    f.write(data)

            if data:
                img = QImage.fromData(data)
            if not img.isNull():
                img = img.scaled(
                    64,
                    64,
                    Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                    Qt.TransformationMode.SmoothTransformation,
                )

                # Create a transparent pixmap to draw the circle
                out_pixmap = QPixmap(64, 64)
                out_pixmap.fill(Qt.GlobalColor.transparent)

                painter = QPainter(out_pixmap)
                painter.setRenderHint(QPainter.RenderHint.Antialiasing)
                path = QPainterPath()
                path.addEllipse(0, 0, 64, 64)
                painter.setClipPath(path)
                painter.drawImage(0, 0, img)
                painter.end()

                label.setPixmap(out_pixmap)
                label.setText("")  # Remove emoji
        except Exception:
            pass  # Keep emoji if fetching fails
