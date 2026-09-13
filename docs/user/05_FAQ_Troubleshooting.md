# FAQ & Troubleshooting

This page helps you solve common problems quickly and points you to the right support resources.

---

## General questions

### Is Karcytics open source?

Yes. The Karcytics core application is open-source. Some third-party plugins may carry their own licensing or usage terms.

### Does Karcytics upload my data to the cloud?

No. Karcytics stores your projects and analysis data locally. Only plugin metadata and trusted registry data are fetched from the network.

### Why does Karcytics use a Plugin Store?

The core application is intentionally lightweight. Analysis modules are installed on demand so you only add the tools you need.

---

## I cannot open a project

### The project is locked

Karcytics creates `.karcytics.lock` in the project folder while the project is open.

* If another Karcytics instance is already running, close it before reopening the project.
* If Karcytics crashed and the lock file remains, remove `.karcytics.lock` only after confirming no instance is still using the project.

### Permission denied

Make sure your operating system account has read and write access to the project folder and every file inside it. This is especially important with synced or network-mounted folders.

---

## Plugin and module issues

### A plugin fails to install or update

* check your internet connection,
* retry the installation from the **Marketplace**,
* use **Repair** or **Repair All Plugins** if the module state is broken.

### A plugin is blocked as untrusted

Karcytics does not run untrusted plugins.

* inspect the developer identity in the Plugin Store,
* if you trust the source, approve the developer when prompted,
* if you do not trust the source, do not load the plugin.

### A plugin says it is outdated

This means the plugin requires a newer core version or module version.

* open **Available Updates** in the Marketplace,
* update the plugin,
* if needed, update the core app from the Hub update banner.

---

## Logs and diagnostics

### View logs

Karcytics stores runtime logs in `~/.karcytics/karcytics.log`.

* In the workspace, open **Help → View Logs**.
* In the Project Hub, use the same Help menu option.

### When to report a bug

Report an issue when:

* Karcytics crashes unexpectedly,
* a plugin repeatedly fails to install or load,
* a project cannot be opened even after removing stale lock files.

Include the log file contents and a description of the steps that caused the problem.

---

## Application update issues

### The update banner does not appear

Karcytics checks for core updates when the Hub starts.

* if you do not see a banner, your current version is likely already up to date,
* if you suspect a newer version exists, compare versions manually on the GitHub Releases page.

### Skipping a version

The update banner includes **Skip This Version** so you can postpone an upgrade. If you skip a version, the banner may not return for that version again.

---

## Additional support

* **GitHub Issues:** [https://github.com/KalaimaranB/Karcytics/issues](https://github.com/KalaimaranB/Karcytics/issues)
* **Documentation portal:** [https://kalaimaranb.github.io/Karcytics/](https://kalaimaranb.github.io/Karcytics/)
* **Log file:** `~/.karcytics/karcytics.log`
