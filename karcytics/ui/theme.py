"""Global Theme and Typography Engine."""

import logging
import weakref
from pathlib import Path

from PyQt6.QtCore import QObject, pyqtSignal

from karcytics.core.config import AppConfig
from karcytics.core.utils import AtomicJsonFile

logger = logging.getLogger(__name__)


class Colors:
    """Static class to hold current colors. Defaults to GitHub Dark."""

    BG_DARKEST = "#0d1117"
    BG_DARK = "#161b22"
    BG_MEDIUM = "#21262d"
    BG_LIGHT = "#30363d"
    FG_PRIMARY = "#c9d1d9"
    FG_SECONDARY = "#8b949e"
    DNA_PRIMARY = "#00f2ff"  # Default Cyan
    DNA_SECONDARY = "#a371f7"  # Default Purple
    FG_DISABLED = "#484f58"
    BORDER = "#30363d"
    BORDER_FOCUS = "#58a6ff"
    ACCENT_PRIMARY = "#2f81f7"
    ACCENT_PRIMARY_HOVER = "#388bfd"
    ACCENT_PRIMARY_PRESSED = "#0550ae"
    ACCENT_SUCCESS = "#238636"
    ACCENT_WARNING = "#d29922"
    ACCENT_DANGER = "#f85149"
    ACCENT_CRITICAL = "#f85149"  # Aliased to Danger for now
    BORDER = "#30363d"
    BORDER_DARK = "#21262d"  # Aliased to Medium
    BORDER_LIGHT = "#484f58"
    BORDER_FOCUS = "#58a6ff"
    BG_DARKER = "#0d1117"  # Aliased to Darkest
    CHART_COLORS = ["#58a6ff", "#3fb950", "#d29922", "#f85149", "#a371f7", "#f778ba"]

    # --- NEW: Enhanced Theme Properties ---
    GLOW_COLOR = "transparent"
    SCANLINE_OPACITY = 0.0
    # --------------------------------------


class _Fonts:
    """Standardized typography scales."""

    SIZE_SMALL = 11
    SIZE_NORMAL = 13
    SIZE_LARGE = 18
    SIZE_XLARGE = 24

    # --- NEW: Font Families ---
    FAMILY_HEADINGS = "Arial, Sans Serif"
    FAMILY_UI = "Arial, Sans Serif"
    FAMILY_MONO = "Monaco, 'Courier New', monospace"
    # ---------------------------

    # Standardized QFont Objects (initialized on first access or manually)
    @property
    def H1(self):  # noqa: N802
        """
        Create the primary heading font.

        Returns:
                QFont: A bold font using the heading family and extra-large size.
        """
        from PyQt6.QtGui import QFont

        f = QFont(self.FAMILY_HEADINGS, self.SIZE_XLARGE, QFont.Weight.Bold)
        return f  # noqa: RET504

    @property
    def H2(self):  # noqa: N802
        """
        Create a bold large-sized heading font using the configured heading font family.

        Returns:
                QFont: A bold font configured for large headings.
        """
        from PyQt6.QtGui import QFont

        f = QFont(self.FAMILY_HEADINGS, self.SIZE_LARGE, QFont.Weight.Bold)
        return f  # noqa: RET504

    @property
    def H3(self):  # noqa: N802
        """Create the standard third-level heading font.

        Returns:
            QFont: A bold heading font at the normal size.
        """
        from PyQt6.QtGui import QFont

        f = QFont(self.FAMILY_HEADINGS, self.SIZE_NORMAL, QFont.Weight.Bold)
        return f  # noqa: RET504

    @property
    def BODY(self):  # noqa: N802
        """
        Create the standard body font using the configured UI font family and normal size.

        Returns:
                QFont: A font configured for body text.
        """
        from PyQt6.QtGui import QFont

        f = QFont(self.FAMILY_UI, self.SIZE_NORMAL)
        return f  # noqa: RET504

    @property
    def CAPTION(self):  # noqa: N802
        """Create a font for caption text using the standard UI family and small size."""
        from PyQt6.QtGui import QFont

        f = QFont(self.FAMILY_UI, self.SIZE_SMALL)
        return f  # noqa: RET504


# Create singleton instances for static-like access
Fonts = _Fonts()


_tamil_font_family: str | None = None


def get_tamil_font_family() -> str:
    """Registers the bundled Tamil font on first use and returns its family name.

    Kept separate from FAMILY_MONO/FAMILY_UI so it only affects call sites that
    explicitly opt in (e.g. the DNA loader's numeral glyphs) rather than the
    whole app's typography.
    """
    global _tamil_font_family
    if _tamil_font_family is None:
        from PyQt6.QtGui import QFontDatabase

        from karcytics.core.resource_manager import resource_path

        family = "Noto Sans Tamil"
        font_path = resource_path("resources/fonts/NotoSansTamil-Variable.ttf")
        if font_path.exists():
            font_id = QFontDatabase.addApplicationFont(str(font_path))
            families = QFontDatabase.applicationFontFamilies(font_id)
            if families:
                family = families[0]
        _tamil_font_family = family
    return _tamil_font_family


class Strings:
    """Theme-dependent text values."""

    TAGLINE = "Bio Analysis Made Simple"
    APP_TITLE = "Karcytics™ — Bio Analysis"
    GREETING = "Good morning"  # Will be adjusted by time of day if default


class ThemeManager(QObject):
    """Pub/Sub Engine for dynamic theme switching."""

    # This signal will broadcast to the whole app when colors change
    theme_changed = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.current_theme_name = "Karcytics Default"
        self._last_color_map = self._get_current_color_map()
        self._dynamic_widgets = weakref.WeakKeyDictionary()

    def _get_current_color_map(self) -> dict[str, str]:
        """Snapshots all hex codes from the Colors class."""
        return {
            name: getattr(Colors, name).lower()
            for name in dir(Colors)
            if not name.startswith("_")
            and isinstance(getattr(Colors, name), str)
            and getattr(Colors, name).startswith("#")
        }

    def apply_style(self, widget, style_template: str):
        """Applies a dynamic stylesheet to a widget and tracks it for future theme changes.

        The style_template can contain format placeholders (e.g. {BG_DARKEST}).
        They will be resolved against the current Colors class.
        """
        self._dynamic_widgets[widget] = style_template
        self._set_widget_style(widget, style_template)

    def _set_widget_style(self, widget, style_template: str):
        """Helper to resolve a template and apply it safely."""
        color_dict = {k: getattr(Colors, k) for k in dir(Colors) if not k.startswith("_")}

        compiled_qss = style_template
        for key, val in color_dict.items():
            compiled_qss = compiled_qss.replace(f"{{{key}}}", str(val))

        import contextlib

        with contextlib.suppress(RuntimeError):
            widget.setStyleSheet(compiled_qss)

    def _apply_dynamic_styles(self):
        """Re-evaluates all tracked inline styles across the app."""
        # weakref dictionary safely iterates over widgets that are still alive in Python
        for widget, style_template in list(self._dynamic_widgets.items()):
            self._set_widget_style(widget, style_template)

    def load_theme(self, theme_path: Path) -> bool:
        """Reads a theme.json and overwrites the Colors class globally.

        This method updates the global QApplication stylesheet, instantly
        repainting the UI with the new color palette.

        Args:
            theme_path (Path): Path to the JSON theme definition file.

        Returns:
            bool: True if the theme was loaded and applied successfully.
        """
        if not theme_path.exists():
            logger.error(f"Theme file not found: {theme_path}")
            return False

        try:
            data = AtomicJsonFile.load(theme_path)
            if not data:
                return False

            self.current_theme_name = data.get("name", theme_path.stem)

            # Dynamically overwrite the attributes in the Colors and Fonts classes
            for key, value in data.items():
                if hasattr(Colors, key):
                    setattr(Colors, key, value)
                elif hasattr(Strings, key):
                    setattr(Strings, key, value)

            logger.info(f"Successfully loaded theme: {self.current_theme_name}")

            # Perform Global Stylesheet Update
            self._apply_global_stylesheet()
            self._apply_dynamic_styles()

            return True

        except Exception as e:
            logger.error(f"Failed to parse theme JSON {theme_path}: {e}")
            return False

    def discover_themes(self) -> list[tuple[str, Path]]:
        """Scans both user-space and internal themes directories, returning (Name, Path) tuples."""
        from karcytics.core.resource_manager import resource_path

        user_themes_dir = AppConfig.APP_DATA_DIR / "themes"
        user_themes_dir.mkdir(parents=True, exist_ok=True)

        internal_themes_dir = resource_path("themes")

        themes = []
        seen_paths = set()

        # Scan directories
        for directory in [user_themes_dir, internal_themes_dir]:
            if directory and directory.exists():
                for theme_file in directory.glob("*.json"):
                    resolved = theme_file.resolve()
                    if resolved in seen_paths:
                        continue
                    seen_paths.add(resolved)
                    try:
                        data = AtomicJsonFile.load(theme_file)
                        if data:
                            name = data.get("name", theme_file.stem)
                            themes.append((name, theme_file))
                    except Exception as e:
                        logger.error(f"Failed to load theme {theme_file}: {e}", exc_info=True)

        # Ensure default is first if found
        themes.sort(key=lambda x: 0 if "Default" in x[0] else 1)
        return themes

    def get_categorized_themes(self) -> dict[str, list[tuple[str, Path]]]:
        """Returns themes grouped into categories: Accessible, Light, and Dark."""
        themes = self.discover_themes()
        categorized: dict[str, list[tuple[str, Path]]] = {
            "Dark Themes": [],
            "Light Themes": [],
            "Accessible Themes": [],
        }

        for name, path in themes:
            if "Accessible" in name or "Okabe" in name:
                categorized["Accessible Themes"].append((name, path))
                continue

            try:
                from karcytics.core.utils import AtomicJsonFile

                data = AtomicJsonFile.load(path)
                if data:
                    bg_hex = data.get("BG_DARKEST", "#000000").lstrip("#")
                    r, g, b = tuple(int(bg_hex[i : i + 2], 16) for i in (0, 2, 4))
                    luminance = 0.299 * r + 0.587 * g + 0.114 * b
                    if luminance > 128:
                        categorized["Light Themes"].append((name, path))
                    else:
                        categorized["Dark Themes"].append((name, path))
                else:
                    categorized["Dark Themes"].append((name, path))
            except Exception:
                categorized["Dark Themes"].append((name, path))

        # Remove empty categories
        return {k: v for k, v in categorized.items() if v}

    def _apply_global_stylesheet(self) -> None:
        """Compiles the master base.qss template using the current Colors
        and applies it natively to the global QApplication instance.
        """
        from PyQt6.QtWidgets import QApplication

        app = QApplication.instance()
        if not app:
            return

        qss_path = Path(__file__).resolve().parent / "styles" / "base.qss"
        if not qss_path.exists():
            logger.warning(f"Master stylesheet not found at {qss_path}")
            return

        try:
            with open(qss_path, encoding="utf-8") as f:
                qss_template = f.read()

            # Create a dictionary of all color properties
            color_dict = {k: getattr(Colors, k) for k in dir(Colors) if not k.startswith("_")}

            # Substitute the {VARIABLE} placeholders in the QSS string
            compiled_qss = qss_template
            for key, val in color_dict.items():
                compiled_qss = compiled_qss.replace(f"{{{key}}}", str(val))

            app.setStyleSheet(compiled_qss)

            # Re-inject app-level styles (QToolTip, QPalette) so they also reflect the new theme
            try:
                from karcytics_sdk.plugin.components import apply_global_sdk_styles

                apply_global_sdk_styles()
            except Exception as e:
                logger.error(f"Failed to apply SDK styles: {e}", exc_info=True)

            self.theme_changed.emit()

            # Notify SDK widgets running in the core process (like TutorialOverlay, Cyto)
            try:
                from karcytics_sdk.plugin.theme_fallback import theme_manager as sdk_theme_manager

                sdk_theme_manager.theme_changed.emit()
            except Exception as e:
                logger.error(f"Failed to emit SDK theme changed: {e}", exc_info=True)

            logger.info("Global stylesheet updated successfully.")

        except Exception as e:
            logger.error(f"Failed to apply global stylesheet: {e}", exc_info=True)


# Global singleton instance so the whole app shares one engine
theme_manager = ThemeManager()
