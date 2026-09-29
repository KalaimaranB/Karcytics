# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

Karcytics is the Hub application: a PyQt6 desktop app (`karcytics/`) that hosts dynamically-loaded analysis plugins (Western Blot, Flow Cytometry, etc., each its own sibling repo). It depends on `karcytics-sdk` (the `Karcytics-SDK` repo, resolved as an editable local path via `[tool.uv.sources]` in `pyproject.toml`) — that package is the *only* thing a plugin is allowed to import from outside its own code.

See `ECOSYSTEM.md` (this repo's root) for the full map of all 7 Karcytics repos, their process models, and shared conventions — read it before a task that spans more than one repo.

Read `docs/internal/` before making non-trivial architecture changes — it's detailed and kept current, so prefer it over re-deriving things from source. Key pages:
- `11_Core_Nervous_System.md` — event-bus-driven decoupling between host UI, plugin store, project manager, diagnostics.
- `25_Core_and_SDK_Boundary.md` — the Core/SDK package split; a plugin never imports `karcytics.*`.
- `15_ModuleManager_and_PluginContract.md` + `16_PluginBase_and_SDK_Contract.md` — how a plugin is discovered, verified, and loaded (in-process vs. isolated `.venv` process).
- `24_Plugin_Communication_Protocol.md` — the isolated-process wire protocol.
- `20_Security_and_Signing.md` / `21_Supply_Chain_Security.md` — Ed25519 plugin signing and trust verification.
- `23_Git_Branching_Engine.md` — the *why* behind the branching model below.

## Commands

```bash
uv run python -m pytest tests/ -q                     # full suite (also runs in pre-commit, see below)
uv run python -m pytest tests/core/test_x.py -q       # single test file
uv run ruff check .                                    # lint
uv run ruff format .                                   # format
uv run mypy --explicit-package-bases karcytics tests   # type check
mkdocs serve                                           # docs live preview (mkdocs build for CI-equivalent)
```

Pre-commit (`.pre-commit-config.yaml`, `fail_fast: true`) already runs ruff, mypy, pip-audit, license compliance, the pytest suite (`tests/core`, `tests/sdk`, plus a few root smoke tests, with coverage), SBOM validation, and a conventional-commit-message check on every commit. Don't pre-run the full suite before committing — let the hook gate it; run only the specific test file/module you're touching while iterating.

Qt tests need an offscreen platform: `QT_QPA_PLATFORM=offscreen`.

## Repository layout

- `karcytics/core/` — non-UI logic: `ModuleManager` (plugin discovery/load), `ProjectManager` (`.karcytics` project files, lockfiles), `HistoryManager` (undo/redo), `core/trust/` (signature verification), `core/network/` (`NetworkUpdater`, plugin registry).
- `karcytics/ui/` — `windows/` (top-level `ProjectLauncherWindow`, `WorkspaceWindow`), `dashboards/` (full-screen panels), `components/` (reusable QWidgets), `dialogs/` & `tabs/` (Plugin Store, modals).
- `karcytics/shared/` — code shared between the Hub and in-process plugin code (`analysis/`, `ui/`).
- `karcytics/themes/` — JSON theme payloads consumed by `theme.py`.
- `plugin_template/` — starting point for new plugin repos, including a runnable `example_minimal_plugin/`.
- `tests/core`, `tests/sdk`, `tests/ui`, `tests/scripts` — mirrors the source layout; `tests/ui` needs the offscreen Qt platform.

## Git workflow (enforced by CI, not just convention)

Dual-branch topology: `develop` (staging) → `main` (production).

| Branch prefix | Source | Target | Merge method |
| --- | --- | --- | --- |
| `feature/*`, `fix/*`, `chore/*`, `docs/*` | `develop` | `develop` | Squash |
| `hotfix/*` | `main` | `main` | Squash |
| promotion (`develop` → `main`) | `develop` | `main` | **Standard merge commit — never squash** |

- Commit messages and PR titles must follow Conventional Commits (`feat:`, `fix:`, `chore:`, `docs:`, …) — enforced by a commit-msg hook.
- Squashing a `develop → main` promotion breaks the shared history and causes massive merge conflicts on the next promotion — always use "Create a merge commit" for that specific direction.
- Any push to `main` triggers an automated back-merge (`back-merge.yml`) that opens a `chore/back-merge-main-<SHA>` PR into `develop` via standard merge — this is expected, not a conflict to resolve manually.
- `pyproject.toml`'s `version` is the release trigger: CI checks whether a GitHub Release for `v<version>` already exists on every push to `main`; if not, the release pipeline runs. A failed release at a given version can be retried by pushing a fix to `main` at the *same* version — no bump needed unless shipping different content. Never re-trigger an already-published release manually (it overwrites build assets and invalidates SLSA provenance for that tag).
- CodeRabbit AI only reviews PRs targeting `main` (promotions/hotfixes), not `develop`-targeted PRs — silence on a `develop` PR is expected.
