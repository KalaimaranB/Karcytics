# FAQ & Troubleshooting

This page helps you solve common problems quickly and points you to the right support resources.

---

## General questions

### Is Karcytics free to use?

Yes, for academic and personal use — always. Karcytics is source-available under the [PolyForm Noncommercial License](https://polyformproject.org/licenses/noncommercial/1.0.0): students, researchers, educators, and institutions can use, modify, and study the code at no cost, indefinitely. Commercial use requires a separate paid license (not yet available).

### Does Karcytics upload my data to the cloud?

No. Karcytics stores your projects and analysis data locally. Only plugin metadata and trusted registry data are fetched from the network.

### Why does Karcytics use a Plugin Store?

The core application is intentionally lightweight. Analysis modules are installed on demand so you only add the tools you need.

### What if my operating system is not supported?

If your OS is not currently compatible (for example, if you are running an older Intel Mac), please contact the developer at **[kalaimaranb25@gmail.com](mailto:kalaimaranb25@gmail.com)** to see if it's possible to release a compatible build for your system.

---

## Why can't I open my project?

### Why is my project locked?

Karcytics creates `.karcytics.lock` in the project folder while the project is open.

* If another Karcytics instance is already running, close it before reopening the project.
* If Karcytics crashed and the lock file remains, remove `.karcytics.lock` only after confirming no instance is still using the project.

### Why am I getting a "Permission denied" error?

Make sure your operating system account has read and write access to the project folder and every file inside it. This is especially important with synced or network-mounted folders.

---

## How do I resolve plugin and module issues?

### Why does a plugin fail to install or update?

* check your internet connection,
* retry the installation from the **Marketplace**,
* use **Repair** or **Repair All Plugins** if the module state is broken.

### Why is a plugin blocked as untrusted?

Karcytics does not run untrusted plugins.

* inspect the developer identity in the Plugin Store,
* if you trust the source, approve the developer when prompted,
* if you do not trust the source, do not load the plugin.

### Why does a plugin say it is outdated?

This means the plugin requires a newer core version or module version.

* open **Available Updates** in the Marketplace,
* update the plugin,
* if needed, update the core app from the Hub update banner.

---

## How do I use logs and diagnostics?

### How do I view application logs?

Karcytics stores multiple types of runtime logs locally depending on the subsystem.

* You can view these directly in the app by navigating to **Preferences → Privacy/Diagnostics → View Log Folder**.

### When and how should I report a bug?

**The preferred method for reporting crashes is through Karcytics' built-in crash reporter.** If the app encounters a fatal error, you will be prompted to send a diagnostic report automatically via Sentry. We highly encourage opting into this feature!

Please email **[kalaimaranb25@gmail.com](mailto:kalaimaranb25@gmail.com)** for functional or visual issues, such as:
* A plot or chart is drawing incorrectly.
* A specific analysis module yields unexpected numbers.
* You would like to request a new feature.

If a plugin repeatedly fails to install or a project cannot be opened, please attach the relevant log files from your **Log Folder** in your email.

---

## How do I fix application update issues?

### Why doesn't the update banner appear?

Karcytics checks for core updates when the Hub starts.

* if you do not see a banner, your current version is likely already up to date,
* if you suspect a newer version exists, compare versions manually on the GitHub Releases page.

### How do I skip an update version?

The update banner includes **Skip This Version** so you can postpone an upgrade. If you skip a version, the banner may not return for that version again.

---

## Where can I find additional support?

* **Documentation portal:** [https://kalaimaranb.github.io/Karcytics/](https://kalaimaranb.github.io/Karcytics/)
* **Email Support:** [kalaimaranb25@gmail.com](mailto:kalaimaranb25@gmail.com)
