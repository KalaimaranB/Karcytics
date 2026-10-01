# PluginBase & SDK Contract

The real plugin contract, as implemented in `karcytics_sdk.plugin.base.PluginBase`
and wired up via a V3 `entry_point` — not the `get_plugin()`/`karcytics_sdk.core`
shape this page used to describe, which never matched the code. See
`docs/internal/15_ModuleManager_and_PluginContract.md` for how a plugin gets
discovered and this entry point gets called in the first place.

## The `entry_point` function

A plugin's `pyproject.toml` declares one under `[tool.karcytics.plugin]`:

```toml
[tool.karcytics.plugin]
entry_point = "karcytics_plugins.flow_cytometry:initialize"
```

`module:function` — the named module is imported, the named function is
called with a `PluginContext`, and its return value (a `PluginBase`
instance, in practice) is what the Hub inserts into `WorkspaceWindow`:

```python
# karcytics_plugins/flow_cytometry/__init__.py (the real, current shape)
from karcytics_sdk.plugin.context import PluginContext


def initialize(context: PluginContext) -> Any:
    ...
    return FlowCytometryPanel(plugin_id="flow_cytometry")
```

## `PluginBase` (`karcytics_sdk/plugin/base.py`)

A `QWidget` subclass, not a bare interface — a plugin's panel *is* a
`PluginBase`, not something that owns one separately.

```python
class PluginBase(QWidget):
    def __init__(self, plugin_id: str, parent=None): ...

    # Must be implemented by every subclass:
    def get_state(self) -> PluginState: ...
    def set_state(self, state: PluginState) -> None: ...

    # Provided, ready to use:
    def push_state(self, label: str = "") -> None: ...  # record one named undo step
    def undo(self) -> bool: ...  # True if a step was undone
    def redo(self) -> bool: ...
    def can_undo(self) -> bool: ...
    def can_redo(self) -> bool: ...
    def undo_text(self) -> str: ...  # "Undo Delete Gate" — Edit menu text
    def redo_text(self) -> str: ...
    undo_history: UndoHistory  # property; created on first use
    def bind_undo_history(self, history: UndoHistory, restore) -> None: ...
    def cleanup(self) -> None: ...  # RAII-style resource release via ResourceInspector
    def publish_event(self, topic: str, data: Any = None) -> None: ...  # CentralEventBus
    def subscribe_event(self, topic: str, callback) -> None: ...  # CentralEventBus
```

`get_state()`/`set_state()` work in terms of `PluginState`
(`karcytics_sdk/plugin/state.py`), not a raw dict. `self.state_changed`
(proxied through `__getattr__` to `self.signals`, a `PluginSignals` instance
covering `status`/`state_changed`/`analysis_started`/`analysis_finished`/
`analysis_error`, etc.) fires automatically from `push_state()`/`undo()`/`redo()`.

### Undo/redo

The history lives in the plugin's own process, as an SDK `UndoHistory`
(`karcytics_sdk/plugin/history.py`). It never uses the Hub's
`HistoryManager`, which an isolated plugin can't import (see doc 24).
`UndoHistory` stores labelled snapshots, refuses to record a snapshot equal
to the current one, and tracks a saved ("clean") revision, so undoing back
to the last save reads as unsaved-changes-free again.

- **Default:** `push_state(label)` records `get_state().to_dict()` as one
  step, and `undo()`/`redo()` restore it via `set_state(type(state).from_dict(...))`.
  The first `push_state()` only sets the baseline. Call it once per finished
  user action, not on every tick of a drag.
- **Own state store:** a plugin that restores state in place calls
  `bind_undo_history(history, restore)` with its own `UndoHistory` and a
  `restore(snapshot)` callable. Flow Cytometry does this with its
  `FlowStore` (its `docs/developer/10_STATE_UNDO_AND_PERSISTENCE.md`).
- If `restore` raises, the history pointer moves back, the error is logged
  and `undo()`/`redo()` return `False`, so the history never disagrees with
  the live state.
- Any history change emits `undo_available`, `redo_available` and
  `undo_state_changed`.

The isolated window (`ui_daemon_runtime.py`) gives every plugin an
Edit → Undo/Redo menu: Cmd+Z / Cmd+Shift+Z on macOS, Ctrl+Z / Ctrl+Y
(and Ctrl+Shift+Z) elsewhere. Item text and enabled state follow
`undo_text()`/`can_undo()`. While a text field has focus, the shortcut
undoes that field's own typing instead.

### Closing and autosave

- A user-initiated close of the isolated window first calls
  `panel.confirm_close()` if the panel defines it; returning `False` keeps the
  window open, for example to offer Save / Discard / Cancel. A close the Hub
  requests is never vetoed.
- `setup_workflow_autosave(..., has_unsaved_changes=callable)` skips an
  autosave tick, including its reminder toast, when the callable reports
  nothing to save.

## Minimal example

```python
from karcytics_sdk.plugin.base import PluginBase
from karcytics_sdk.plugin.state import PluginState


class MyState(PluginState):
    threshold: float = 0.5


class MyPlugin(PluginBase):
    def __init__(self, plugin_id: str):
        super().__init__(plugin_id)
        self._state = MyState()
        # build UI here

    def get_state(self) -> MyState:
        return self._state

    def set_state(self, state: MyState) -> None:
        self._state = state
        self.update_ui()

    def cleanup(self) -> None:
        super().cleanup()  # releases heavy references via ResourceInspector
```

## Analysis workers (off-UI thread)

Long-running computation belongs in an `AnalysisBase` subclass
(`karcytics_sdk/plugin/analysis.py`), submitted to a `TaskScheduler`
(`context.get("task_scheduler")` for an in-process plugin; a local,
per-process one for an isolated plugin — see doc 25's "Where UI comes from,
where analysis comes from"). `task_started`/`task_finished`/`task_error`/
`task_progress` signals, keyed by `task_id`, are how a result gets back to
the UI thread — never a direct return value across a thread boundary.

## Signing & distribution

Covered in full by `docs/internal/20_Security_and_Signing.md` and
`21_Supply_Chain_Security.md` — summary: a plugin ships with a signed
`security.json` (per-file SHA-256 + an Ed25519 signature chaining to the
Karcytics Core Authority root key, a project CI key, or an explicit local
override), verified by `TrustManager` before `module_manager.py` will load
or spawn it. The SDK CLI's `security.py` commands (`init-identity`, `sign`,
`project-sign`) generate the identity and produce that signature.

## Testing & contract verification

`karcytics_sdk.testing.contract.ContractTestBase` — a pytest base class a
plugin author subclasses to get `test_manifest_is_valid` and
`test_headless_initialization` for free (the latter mocks every capability
the manifest declares under `requires` and confirms the plugin's
`entry_point` resolves and initializes with no running Hub at all). See
`tests/sdk/test_plugin_contract.py` in this repo for worked examples.

## Links

- `docs/internal/15_ModuleManager_and_PluginContract.md` — discovery,
  trust verification, and how `entry_point` gets invoked.
- `docs/internal/25_Core_and_SDK_Boundary.md` — which package owns
  `PluginBase` vs. `PluginContext` vs. the concrete services behind them.
- `karcytics_sdk/plugin/base.py`, `state.py`, `context.py`, `analysis.py` —
  the real source.
