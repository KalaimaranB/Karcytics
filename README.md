# 🔬 Karcytics™: The Modular Lab Analysis Hub

**Karcytics™** is a cross-platform desktop suite designed to bridge the gap between "messy" raw lab data and publication-ready results. Built on a dynamic plugin architecture, Karcytics provides a unified, mathematically rigorous environment for biological image analysis without the steep learning curve of traditional tools.

---

### 📖 Documentation Portal
Explore the full, beautifully compiled documentation portal online:
👉 **[Karcytics Documentation Portal](https://kalaimaranb.github.io/Karcytics/)**

Or read the raw Markdown guides directly in this repository:
- [**User Guide Hub**](docs/user/01_User_Guide.md) - For researchers and lab technicians.
- [**Getting Started Guide**](docs/user/02_Getting_Started.md) - Fast-track to your first analysis.
- [**Internal Architecture Hub**](docs/internal/11_Core_Nervous_System.md) - For core developers and architects.

Developer-oriented docs notes:
- The site is built with `mkdocs` + Material and uses `mkdocstrings` to auto-generate the API reference from in-source docstrings.
- Local preview / build:

```bash
python -m pip install -r reqs.txt
python -m pip install -e .[dev]
mkdocs serve    # live preview at http://127.0.0.1:8000
mkdocs build    # generate site/ for CI or local inspection
```

- The plugin template and a runnable minimal plugin example live under `plugin_template/example_minimal_plugin/` — use it as the starting point for authors.


---

## 🌟 Key Features

---

## 🚀 Installation Guide (Core App)

### Windows
1. Navigate to the [Releases](https://github.com/KalaimaranB/Karcytics/releases) page.
2. Download the latest `Karcytics-Windows.zip` asset.
3. Extract the `.zip` folder to your preferred location on your PC.
4. Open the extracted folder and double-click `Karcytics.exe` to launch the application.

### macOS
1. Navigate to the [Releases](https://github.com/KalaimaranB/Karcytics/releases) page.
2. Download the latest `Karcytics-macOS.tar.gz` asset.
3. Double-click the downloaded file to extract the `Karcytics.app` bundle.
4. Drag `Karcytics.app` into your **Applications** folder.

**⚠️ macOS Security Notice (Gatekeeper):**
Because Karcytics isn't yet notarized with an Apple Developer ID, macOS may initially block it from opening, displaying a warning that the developer cannot be verified. To safely bypass this:
* **Method 1:** Right-click (or Control-click) `Karcytics.app` and select **Open**. Click **Open** again on the pop-up warning.
* **Method 2:** Try opening the app normally. When it fails, open your Mac's **System Settings** > **Privacy & Security**, scroll down to the Security section, and click **Open Anyway** next to the Karcytics notification.

---

## 🧩 Installing Analysis Modules

Karcytics's core application is a lightweight hub. To actually analyze data, you need to download modules (like the Western Blot analyzer) directly within the app.

1. Launch the **Karcytics** core application.
2. From the Home Screen, navigate to the **Plugin Store**.
3. Browse the available modules (e.g., **Western Blot Pro**).
4. Click **Install**. Karcytics will automatically fetch the module from the cloud registry and configure it.
5. Return to the Home Screen and click the newly installed module to launch your analysis workspace.

---

## 🔄 How Updates Work

Karcytics uses a split-update architecture to ensure your tools are always cutting-edge without forcing you to constantly reinstall the main application.

* **Module Updates (Automated):** Our plugins are hosted on an independent cloud registry. Whenever a new feature or bug fix is pushed for a specific module (like CytoMetrics or Flow Cytometry), Karcytics's `NetworkUpdater` will detect it. You can update individual modules with a single click directly from the in-app **Plugin Store**.
* **Core App Updates (Manual):** Updates to the Karcytics Core (which handle the UI engine, theming, and workspace management) are less frequent. When a new core version is released, you will need to download the latest `.zip` or `.tar.gz` from the GitHub Releases page and replace your old application file. *Note: Updating the core application will not delete your installed plugins or project files.*

---

## 🛠 For Developers
Karcytics is designed to be extensible. You can build your own analysis modules using the [**Karcytics SDK**](https://github.com/KalaimaranB/Karcytics-SDK). The SDK provides a powerful CLI and a suite of UI/analysis base classes to help you build verified plugins quickly. 

For detailed instructions on setting up your environment, authoring plugins, and cryptographically signing them, see the [**Developer Onboarding & Contribution Manual**](https://kalaimaranb.github.io/Karcytics/internal/19_Developer_Onboarding/) on our documentation portal!

Docs & contribution highlights for developers:
- API docs are generated from docstrings; please keep public docstrings concise (one-line summary + args/returns) so `mkdocstrings` renders well.
- Use the `plugin_template/` example when starting a plugin repository — it includes example `pyproject.toml`, docs scaffold, and CI examples.
- When changing public APIs, update docstrings and run `mkdocs build` locally before opening a PR.

### Repository Architecture

If you are contributing to the core application itself, familiarizing yourself with the file hierarchy will help:

- **`karcytics/core/`**: The brains of the application. Handles non-UI logic like the `HistoryManager` (Tracks user edits for global Undo/Redo operations), `ProjectManager` (Handles `.karcytics` file structures and asserts lockfiles), and `ModuleManager` (Dynamically discovering, loading, and binding new analysis plugins).
- **`karcytics/ui/`**: The visual layer, strictly adhering to SOLID principles.
  - `windows/`: Top-level native OS windows (`ProjectLauncherWindow` and `WorkspaceWindow`).
  - `dashboards/`: Full screen panels living inside windows (e.g., the `WorkspaceDashboard`).
  - `components/`: Granular, reusable, mathematically distinct QWidgets (`Cards`, `Toolbars`, `Overlays`) isolated to prevent God classes.
  - `dialogs/` & `tabs/`: Specialized modal windows like the Plugin Store and contextual workflows.
- **`tests/`**: Contains all unit and integration coverage for the application logic.
- **`karcytics/themes/`**: JSON payloads mapped to the `theme.py` engine defining global application colors (e.g. `default.json`, `galactic_dark.json`).

---

> **Note:** Karcytics is currently in active development. Please report any bugs or feature requests via GitHub Issues.
