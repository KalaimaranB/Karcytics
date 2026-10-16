import logging
import re
from pathlib import Path

import markdown
from pygments.formatters import HtmlFormatter
from PySide6.QtCore import Qt, QTimer, QUrl
from PySide6.QtWebEngineCore import QWebEnginePage
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSplitter,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
)

from karcytics.core.config import AppConfig
from karcytics.ui.theme import Colors, theme_manager

logger = logging.getLogger(__name__)


class HelpPage(QWebEnginePage):
    """Custom page to intercept links and prevent navigation crashes."""

    def __init__(self, dialog, *args, **kwargs):
        """
        Initialize the page with a reference to its owning dialog.

        Parameters:
            dialog: The dialog used to handle intercepted navigation requests.
        """
        super().__init__(*args, **kwargs)
        self.dialog = dialog

    def acceptNavigationRequest(  # noqa: N802
        self,
        url: QUrl,
        nav_type: QWebEnginePage.NavigationType,
        is_main_frame: bool,  # noqa: ARG002
    ) -> bool:
        """
        Intercept clicked Markdown links and route them to the owning help dialog.

        Parameters:
            url (QUrl): URL targeted by the navigation request.
            nav_type (QWebEnginePage.NavigationType): Type of navigation request.
            is_main_frame (bool): Whether the request targets the main frame.

        Returns:
            bool: `False` for clicked Markdown links, `True` for all other navigation requests.
        """
        if nav_type == QWebEnginePage.NavigationType.NavigationTypeLinkClicked:
            url_str = url.toString()
            if url_str.endswith(".md"):
                QTimer.singleShot(0, lambda: self.dialog.navigate_to_md(url.fileName()))
                return False
        return True


class HelpCenterDialog(QDialog):
    """Categorized documentation viewer with async rendering and caching."""

    def __init__(self, module_manager=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Karcytics Help Center")
        self.setMinimumSize(1100, 800)
        theme_manager.apply_style(
            self, f"background: {Colors.BG_DARKEST}; color: {Colors.FG_PRIMARY};"
        )

        self.module_manager = module_manager
        self.docs_dir = AppConfig.get_docs_dir()
        self.lookup_table = {}
        self.render_cache = {}
        self._setup_ui()
        self._load_topics()
        self._select_initial_topic()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Top Bar
        top_bar = QFrame()
        top_bar.setFixedHeight(50)
        theme_manager.apply_style(
            top_bar, f"background: {Colors.BG_DARK}; border-bottom: 1px solid {Colors.BORDER};"
        )
        top_layout = QHBoxLayout(top_bar)

        title = QLabel("📖 Karcytics Documentation")
        theme_manager.apply_style(
            title, f"font-size: 16px; font-weight: 700; color: {Colors.ACCENT_PRIMARY};"
        )
        top_layout.addWidget(title)
        top_layout.addStretch()

        close_btn = QPushButton("✕")
        close_btn.setFixedSize(30, 30)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        theme_manager.apply_style(
            close_btn,
            "QPushButton { border: none; font-size: 18px; } QPushButton:hover { color: white; }",
        )
        close_btn.clicked.connect(self.close)
        top_layout.addWidget(close_btn)

        layout.addWidget(top_bar)

        # Main Splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(1)
        theme_manager.apply_style(splitter, f"QSplitter::handle {{ background: {Colors.BORDER}; }}")

        # Sidebar
        self.tree = QTreeWidget()
        self.tree.setFixedWidth(280)
        self.tree.setHeaderHidden(True)
        self.tree.setIndentation(15)
        theme_manager.apply_style(
            self.tree,
            f"""
            QTreeWidget {{ background: {Colors.BG_DARK}; border: none; padding: 10px; font-size: 13px; }}
            QTreeWidget::item {{ padding: 8px 5px; color: {Colors.FG_SECONDARY}; border-radius: 4px; }}
            QTreeWidget::item:selected {{ background: {Colors.BG_MEDIUM}; color: {Colors.ACCENT_PRIMARY}; font-weight: bold; }}
            QTreeWidget::item:hover {{ background: {Colors.BG_LIGHT}; }}
        """,
        )
        self.tree.itemClicked.connect(self._on_item_clicked)
        splitter.addWidget(self.tree)

        # Content Area
        self.viewer = QWebEngineView()
        self.viewer.setPage(HelpPage(self, self.viewer))
        theme_manager.apply_style(self.viewer, f"background: {Colors.BG_DARKEST};")

        # Optmization: Speed up WebEngine
        settings = self.viewer.settings()
        if settings:
            from PySide6.QtWebEngineCore import QWebEngineSettings

            settings.setAttribute(
                QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True
            )
            settings.setAttribute(
                QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True
            )
            settings.setAttribute(QWebEngineSettings.WebAttribute.ScrollAnimatorEnabled, True)
            settings.setAttribute(QWebEngineSettings.WebAttribute.ErrorPageEnabled, False)

        self.viewer.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
        splitter.addWidget(self.viewer)
        layout.addWidget(splitter)

    def _populate_tree_from_dir(self, directory: Path, parent_item: QTreeWidgetItem):
        """
        Recursively populates a tree item with markdown files and documentation subdirectories.

        Parameters:
            directory (Path): Directory to scan.
            parent_item (QTreeWidgetItem): Tree item under which files and subdirectories are added.
        """
        # 1. Add files in this directory
        for f in sorted(list(directory.glob("*.md"))):  # noqa: C414
            name = f.stem
            # Clean up display name: remove leading numbers and underscores
            display_name = (
                name.split("_", 1)[1].replace("_", " ")
                if "_" in name and name[:2].isdigit()
                else name.replace("_", " ")
            )

            item = QTreeWidgetItem(parent_item, [f"• {display_name}"])
            item.setData(0, Qt.ItemDataRole.UserRole, str(f))

            # Add to lookup table. We use the filename as key for cross-links.
            # To handle collisions, we store the full path string as well if needed,
            # but for now we'll just map the filename to the item.
            self.lookup_table[f.name] = item

        # 2. Add subdirectories recursively
        for d in sorted(list(directory.iterdir())):  # noqa: C414
            if d.is_dir() and not d.name.startswith(".") and d.name != "images":
                sub_item = QTreeWidgetItem(parent_item, [d.name.title()])
                sub_item.setFlags(sub_item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
                sub_item.setForeground(0, Qt.GlobalColor.gray)

                self._populate_tree_from_dir(d, sub_item)

                # Only add if it contains markdown files (recursively)
                if sub_item.childCount() > 0:
                    sub_item.setExpanded(True)
                else:
                    parent_item.removeChild(sub_item)

    def _load_topics(self):
        """Builds the documentation tree from core and available plugin documentation directories."""
        font = self.tree.font()
        font.setBold(True)
        font.setPointSize(11)

        # 1. Core User Docs
        self.user_group = QTreeWidgetItem(self.tree, ["📖 User Manuals"])
        self.user_group.setFlags(self.user_group.flags() & ~Qt.ItemFlag.ItemIsSelectable)
        self.user_group.setForeground(0, Qt.GlobalColor.gray)
        self.user_group.setFont(0, font)
        self.user_group.setExpanded(True)

        user_path = self.docs_dir / "user"
        if user_path.exists():
            self._populate_tree_from_dir(user_path, self.user_group)

        # 2. Core Internal Docs
        self.internal_group = QTreeWidgetItem(self.tree, ["🏗 Internal Architecture"])
        self.internal_group.setFlags(self.internal_group.flags() & ~Qt.ItemFlag.ItemIsSelectable)
        self.internal_group.setForeground(0, Qt.GlobalColor.gray)
        self.internal_group.setFont(0, font)

        internal_path = self.docs_dir / "internal"
        if internal_path.exists():
            self._populate_tree_from_dir(internal_path, self.internal_group)

        # 3. Plugin Docs
        self.plugin_group = QTreeWidgetItem(self.tree, ["🔌 Plugin Manuals"])
        self.plugin_group.setFlags(self.plugin_group.flags() & ~Qt.ItemFlag.ItemIsSelectable)
        self.plugin_group.setForeground(0, Qt.GlobalColor.gray)
        self.plugin_group.setFont(0, font)

        if self.module_manager:
            found_plugins = False
            for mod_id, mod_info in self.module_manager.modules.items():
                plugin_docs = mod_info["path"] / "docs"
                if plugin_docs.exists():
                    found_plugins = True
                    manifest = mod_info["manifest"]
                    plugin_root = QTreeWidgetItem(
                        self.plugin_group, [f"📦 {manifest.get('display_name', mod_id)}"]
                    )
                    plugin_root.setFlags(plugin_root.flags() & ~Qt.ItemFlag.ItemIsSelectable)

                    # Use recursive scan for plugins
                    self._populate_tree_from_dir(plugin_docs, plugin_root)

            if not found_plugins:
                self.plugin_group.setHidden(True)
            else:
                self.plugin_group.setExpanded(True)
        else:
            self.plugin_group.setHidden(True)

    def _select_initial_topic(self):
        for i in range(self.tree.topLevelItemCount()):
            group = self.tree.topLevelItem(i)
            if group and group.childCount() > 0:
                # Find the first item that actually has data (not a category/folder)
                item = group.child(0)
                while item and item.childCount() > 0 and not item.data(0, Qt.ItemDataRole.UserRole):
                    item = item.child(0)

                if item and item.data(0, Qt.ItemDataRole.UserRole):
                    self.tree.setCurrentItem(item)
                    self._on_item_clicked(item)
                    break

    def navigate_to_md(self, filename: str):
        if filename in self.lookup_table:
            item = self.lookup_table[filename]
            self.tree.setCurrentItem(item)
            self._on_item_clicked(item)

    def _on_item_clicked(self, item: QTreeWidgetItem):
        """Triggers the rendering flow."""
        file_path_str = item.data(0, Qt.ItemDataRole.UserRole)
        if not file_path_str:
            return

        # 1. Check Cache
        if file_path_str in self.render_cache:
            self._finalize_render(file_path_str, self.render_cache[file_path_str])
            return

        try:
            file_path = Path(file_path_str)
            with open(file_path, encoding="utf-8") as f:
                md_content = f.read()

            # Pre-processing (Alerts, Mermaid)
            alert_map = {
                "TIP": "tip",
                "NOTE": "note",
                "IMPORTANT": "important",
                "WARNING": "warning",
                "CAUTION": "caution",
            }
            for github_tag, extension_tag in alert_map.items():
                pattern = rf"^>\s*\[!{github_tag}\]\s*"
                md_content = re.sub(
                    pattern, f"!!! {extension_tag}\n    ", md_content, flags=re.MULTILINE
                )

            mermaid_pattern = re.compile(r"```mermaid\s+(.*?)```", re.DOTALL)
            md_content = mermaid_pattern.sub(r'<div class="mermaid">\1</div>', md_content)

            # Rendering
            html_body = markdown.markdown(
                md_content, extensions=["fenced_code", "tables", "codehilite", "admonition"]
            )
            self.render_cache[file_path_str] = html_body
            self._finalize_render(file_path_str, html_body)
        except Exception as e:
            logger.error(f"Render Error: {e}")
            self._finalize_render(file_path_str, f"<h3>Error</h3><p>{e}</p>")

    def _finalize_render(self, file_path_str: str, html_body: str):
        """Final UI assembly on the main thread."""
        file_path = Path(file_path_str)
        pygments_css = HtmlFormatter(style="monokai").get_style_defs(".codehilite")
        assets_path = Path(__file__).parents[1] / "assets"
        mermaid_lib = QUrl.fromLocalFile(str(assets_path / "mermaid.min.js")).toString()
        base_url = QUrl.fromLocalFile(str(file_path.parent) + "/")

        styled_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <script src="https://polyfill.io/v3/polyfill.min.js?features=es6"></script>
            <script id="MathJax-script" async src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-mml-chtml.js"></script>
            <script src="{mermaid_lib}"></script>
            <style>
                {pygments_css}
                body {{ background: {Colors.BG_DARKEST}; color: {Colors.FG_PRIMARY}; font-family: sans-serif; line-height: 1.7; padding: 40px; max-width: 900px; margin: 0 auto; }}
                h1 {{ color: {Colors.ACCENT_PRIMARY}; border-bottom: 2px solid {Colors.BORDER}; padding-bottom: 0.3em; }}
                .codehilite {{ background: {Colors.BG_MEDIUM}; padding: 16px; border-radius: 8px; }}
                .mermaid {{ background: #ffffff0a; border-radius: 8px; padding: 20px; margin: 2em 0; display: flex; justify-content: center; }}
                .admonition {{ padding: 16px; border-left: 4px solid {Colors.ACCENT_PRIMARY}; background: {Colors.BG_MEDIUM}; margin: 1.5em 0; border-radius: 4px; }}
                img {{ max-width: 100%; height: auto; border-radius: 8px; border: 1px solid {Colors.BORDER}; }}
                a {{ color: {Colors.ACCENT_PRIMARY}; text-decoration: none; }}
                table {{ border-collapse: collapse; width: 100%; margin: 2em 0; }}
                th, td {{ border: 1px solid {Colors.BORDER}; padding: 12px; }}
            </style>
            <script>
                window.MathJax = {{ tex: {{ inlineMath: [['$', '$'], ['\\\\(', '\\\\)']] }} }};
                document.addEventListener('DOMContentLoaded', () => {{
                    if (typeof mermaid !== 'undefined') {{
                        mermaid.initialize({{ startOnLoad: true, theme: 'dark', flowchart: {{ curve: 'basis' }} }});
                        setTimeout(() => {{ mermaid.init(); }}, 200);
                    }}
                }});
            </script>
        </head>
        <body><div class="content">{html_body}</div></body>
        </html>
        """
        self.viewer.setHtml(styled_html, base_url)
