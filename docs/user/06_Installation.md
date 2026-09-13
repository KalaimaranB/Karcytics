# Installation

Karcytics is distributed as a desktop application with a lightweight plugin ecosystem. Install the main app once, then add analysis modules from the in-app Plugin Store when you need them.

---

## Before you begin

Use the official GitHub release page for the latest stable download:

* [Karcytics Releases](https://github.com/KalaimaranB/Karcytics/releases)

Choose the build that matches your system:

* `Karcytics-Windows.zip` for Windows
* `Karcytics-macOS.tar.gz` for macOS

> [!NOTE]
> If you are running a source build or developer version, use the repository README and local setup instructions instead of the packaged app flow.

![1786425455778](image/06_Installation/1786425455778.png)

---

## Quick install summary

```mermaid
flowchart TD
    A[Download release] --> B[Extract app]
    B --> C[Launch Karcytics]
    C --> D[Create or open a project]
    D --> E[Install a plugin]
    E --> F[Run your first analysis]
```

---

## Windows installation

1. Download `Karcytics-Windows.zip` from the latest GitHub release.
2. Extract the ZIP to a folder you control, for example `C:\Users\<you>\Documents\Karcytics`.
3. Open the extracted folder and double-click `Karcytics.exe` to launch the app.
4. If Windows SmartScreen shows a warning, choose **More info** and then **Run anyway** only if you trust the source.

> [!NOTE]
> Keep the extracted folder in a stable location. If you move or rename the app folder after installation, local plugin data and project settings may become harder to resolve.

### First launch on Windows

The first time you launch Karcytics, it creates application state in your home directory under `~/.karcytics`.

This folder stores:

* installed plugins
* trusted developer keys
* logs
* project history metadata

---

## macOS installation

1. Download `Karcytics-macOS.tar.gz` from the latest GitHub release.
2. Double-click the downloaded file to unpack the `Karcytics.app` bundle.
3. Drag `Karcytics.app` into your **Applications** folder.
4. Open `Karcytics.app` from Applications.

### Gatekeeper / macOS security

On first launch, macOS may block the app because it is not signed through the App Store workflow.

Try one of these:

* Right-click (or Control-click) `Karcytics.app` and choose **Open**.
* If prompted again, click **Open** to allow the app to run.
* If that still fails, open **System Settings → Privacy & Security** and click **Open Anyway** next to the Karcytics warning.

> [!WARNING]
> Only override Gatekeeper when you downloaded Karcytics from the official repository and release page.

### macOS install walkthrough video

When you record the macOS install video, embed it here:

```html
<video controls width="100%" poster="assets/videos/karcytics-mac-install-poster.png">
  <source src="assets/videos/karcytics-mac-install.mp4" type="video/mp4" />
  Your browser does not support the video tag.
</video>
```

---

## Installing analysis modules

Karcytics itself is the host application. Analysis tools are delivered as plugins and installed inside the app.

1. Launch Karcytics.
2. From the Project Hub, click **Marketplace**.
3. Browse or search for a module.
4. Click **Install** to download and enable it.
5. Return to the home screen and launch the module from the installed list.

> [!TIP]
> The Plugin Store includes filters such as **All Modules**, **Available Updates**, **Installed**, and **Trusted Developers**.

### Windows install walkthrough video

When you record the Windows install video, add it here:

```html
<video controls width="100%" poster="assets/videos/karcytics-windows-install-poster.png">
  <source src="assets/videos/karcytics-windows-install.mp4" type="video/mp4" />
  Your browser does not support the video tag.
</video>
```

---

## Updating Karcytics and modules

Karcytics uses a split-update model:

* **Core app updates** are released from the GitHub Releases page.
* **Module updates** are handled from the Plugin Store.

### Core app update notifications

When the Project Hub starts, Karcytics checks for a new core version.

* If an update is available, a banner appears in the Hub.
* Click **Download Now** to open the latest release page.
* Click **Skip This Version** if you want to keep the current version temporarily.

---

## Supported platforms

Karcytics is primarily supported on modern Windows and macOS systems. Linux builds may be available through source or developer builds, but the main packaged experience is focused on Windows and macOS.

---

## Troubleshooting installation

If the app doesn't open:

* verify the archive extracted completely
* make sure `Karcytics.exe` or `Karcytics.app` is still present
* check your computer has permission to access the folder you extracted into

If a plugin won't install:

* confirm your internet connection
* check that the release page is reachable
* retry installation from the Plugin Store

> [!NOTE]
> Application logs are stored in `~/.karcytics/karcytics.log`. You can inspect them from the Help menu once Karcytics is running.

## What’s next?

* [Getting Started](02_Getting_Started.md) — create a project and learn the Hub
* [Plugin Store & Security](07_Plugin_Store_and_Security.md) — understand trust and module safety
* [FAQ & Troubleshooting](05_FAQ_Troubleshooting.md) — solve common problems quickly
