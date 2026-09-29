# Karcytics Ecosystem Map

Karcytics is split across 7 sibling repos on disk (all expected as siblings of this one, e.g. `../Karcytics-SDK`). This doc exists so an agent working in any one of them doesn't have to open the other 6 to understand how they relate — each repo's own `CLAUDE.md` links back here.

```
                     ┌────────────────────┐
                     │   Karcytics-SDK     │   shared package: karcytics_sdk
                     │  (no deps on any    │   the ONLY thing a plugin may import
                     │   other repo here)  │   from outside its own code
                     └─────────┬──────────┘
                        editable path dep
              ┌────────────────┼────────────────┬─────────────────────┐
              ▼                ▼                 ▼                     ▼
      ┌───────────────┐ ┌─────────────┐  ┌───────────────┐   ┌─────────────────┐
      │   Karcytics    │ │ flow-       │  │ cytometrics   │   │ SyntheticBiology │
      │   (this repo,  │ │ cytometry   │  │               │   │                  │
      │   the Hub)     │ │ (isolated)  │  │ (isolated)    │   │ (in_process)     │
      └───────┬────────┘ └─────────────┘  └───────────────┘   └──────────────────┘
              │                              ┌───────────────┐
              │ loads plugins listed in ───▶ │ western-blot  │
              │ Karcytics-Distribution        │ (isolated)    │
              ▼                              └───────────────┘
      ┌────────────────────┐
      │ Karcytics-           │  data only: registry.json (plugin → repo_url map)
      │ Distribution          │  + authorities.json (root Ed25519 trust anchor)
      └────────────────────┘
```

A plugin never imports `karcytics.*` (the Hub) — only `karcytics_sdk` — regardless of whether it runs `in_process` or `isolated`. That boundary is what makes the isolated process model possible without a rewrite (see this repo's `docs/internal/25_Core_and_SDK_Boundary.md`).

## Repo-by-repo

| Repo | Package / module | Plugin id | Process model | Role |
| --- | --- | --- | --- | --- |
| `Karcytics` | `karcytics` | — | — | Hub app: window, theming, project files, `ModuleManager`, trust verification |
| `Karcytics-SDK` | `karcytics_sdk` | — | — | Shared dependency: `PluginBase`/`AnalysisBase`, host services, signing/trust, interfaces |
| `Karcytics-flow-cytometry` | `karcytics_plugins.flow_cytometry` | `flow_cytometry` | isolated | FCS analysis, gating, compensation, UMAP |
| `Karcytics-cytometrics` | `karcytics_plugins.cytometrics` | `cytometrics` | isolated | AI (Cellpose) cell morphology quantification |
| `Karcytics-SyntheticBiology` | `karcytics_plugins.synthetic_biology` | (see its `pyproject.toml`) | in_process | Genetic circuit / logic gate design & simulation |
| `Karcytics-western-blot` | `karcytics_plugins.western_blot` | `western_blot` | isolated | Densitometry / gel-band quantification |
| `Karcytics-Distribution` | — (no code) | — | — | Plugin registry + root trust store the Hub reads at runtime |

## Conventions shared across every repo here

- Dependency management: `uv`; every plugin resolves `karcytics-sdk` via `[tool.uv.sources]` as an editable path to `../Karcytics-SDK` for local dev.
- Pre-commit (local `repo: local` hooks, not the pre-commit.com hosted ones) runs ruff, mypy, pip-audit, license compliance, and the **unit** test suite only — never the full suite — plus plugin re-signing and security-ledger verification for the isolated/in-process plugin repos. Don't pre-run the full suite yourself before a commit; let the hook gate it.
- A plugin's manifest (`[tool.karcytics.plugin]` in its `pyproject.toml`) is the single source of truth for its id, version, entry point, process model, and Ed25519 signing/delegation keys.
- Each plugin repo mirrors the same internal split: `analysis/` (pure compute, no Qt, independently testable) vs. `ui/` (PyQt6, calls into `analysis/`). See `Karcytics-SDK/CLAUDE.md` for why.
