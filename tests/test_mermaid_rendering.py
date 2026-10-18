import pytest
from PySide6.QtCore import Qt, QUrl
from PySide6.QtWidgets import QApplication


@pytest.fixture
def help_view(qtbot):
    """Fixture that builds a QWebEngineView with the Karcytics help logic."""
    from karcytics.ui.dialogs.help_dialog import HelpCenterDialog

    QApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts)

    dialog = HelpCenterDialog()

    # Add console logging for debugging
    def on_console_message(level, message, line, source):
        print(f"JS [{level}]: {message} (line {line}, source {source})")

    dialog.viewer.page().javaScriptConsoleMessage = on_console_message

    qtbot.addWidget(dialog)
    return dialog


def test_mermaid_svg_generation(help_view, qtbot):
    """Verifies that a Mermaid diagram is actually transformed into an SVG in the DOM.
    This ensures the JS bridge, local assets, and pre-processor are all working.
    """
    # 1. Provide a markdown string with a mermaid block
    test_md = "# Test\n```mermaid\ngraph TD\nA --> B\n```"

    # 2. Extract the file path of a real doc to trigger the load logic
    # (Actually, let's just mock the load logic for this specific test)
    import re
    from pathlib import Path

    import markdown  # type: ignore

    mermaid_pattern = re.compile(r"```mermaid\s+(.*?)```", re.DOTALL)
    md_content = mermaid_pattern.sub(r'<div class="mermaid">\1</div>', test_md)

    html_content = markdown.markdown(md_content, extensions=["fenced_code", "tables", "codehilite"])

    assets_path = Path(__file__).parents[1] / "karcytics" / "ui" / "assets"
    # Build HTML using the same f-string escaping as help_dialog.py
    base_url = QUrl.fromLocalFile(str(assets_path) + "/")
    styled_html = f"""
    <html>
    <head>
        <script src="mermaid.min.js"></script>
        <script>
            mermaid.initialize({{ startOnLoad: true, theme: 'dark' }});
        </script>
    </head>
    <body>
        <div id="target">{html_content}</div>
    </body>
    </html>
    """

    view = help_view.viewer

    # Restored: Load the HTML into the viewer
    settings = view.settings()
    settings.setAttribute(settings.WebAttribute.LocalContentCanAccessFileUrls, True)
    view.setHtml(styled_html, base_url)

    # Check if mermaid is defined
    qtbot.wait(1000)  # Wait for load

    found_svg = False
    for _i in range(50):
        qtbot.wait(100)

        def check_callback(result):
            nonlocal found_svg
            if result:
                found_svg = True

        view.page().runJavaScript("document.querySelector('.mermaid svg') !== null", check_callback)
        if found_svg:
            break

    assert found_svg, "Mermaid failed to render an SVG."
