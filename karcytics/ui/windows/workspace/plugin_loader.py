"""Plugin Loader Manager for WorkspaceWindow."""

import logging

from PyQt6.QtCore import QObject, QThread, pyqtSignal, pyqtSlot

from karcytics.core.event_bus import KarcyticsEvent, event_bus

logger = logging.getLogger(__name__)


class PluginUIWorker(QObject):
    """Worker to handle the slow import of plugin modules off the main thread."""

    finished = pyqtSignal(object)
    error = pyqtSignal(str)

    def __init__(self, module_manager, module_id, parent=None):
        super().__init__(parent)
        self.module_manager = module_manager
        self.module_id = module_id

    @pyqtSlot()
    def run(self):
        """
        Load the module UI class and emit either the result or a formatted error traceback.
        """
        try:
            PanelClass = self.module_manager.load_module_ui(self.module_id)  # noqa: N806
            self.finished.emit(PanelClass)
        except Exception as e:
            import logging
            import traceback

            logging.getLogger(__name__).error(f"Failed to load module UI: {e}", exc_info=True)
            self.error.emit(traceback.format_exc())


class PluginLoaderManager:
    def __init__(self, main_window):
        self.main_window = main_window

    def open_module(self, manifest: dict) -> None:
        """
        Starts loading a module's user interface after obtaining trust approval when required.

        Parameters:
                manifest (dict): Module manifest containing the module identifier and optional display name.
        """
        mw = self.main_window
        module_id = manifest["id"]
        module_name = manifest.get("display_name", "Analysis Module")

        if getattr(mw, "_switch_in_progress", False):
            logger.warning(
                f"PluginLoader: Ignoring open_module('{module_id}') — a module switch "
                "is already in progress."
            )
            return

        logger.info(f"PluginLoader: Starting async load sequence for module '{module_id}'")

        # --- Trust Gate ---
        # Check trust BEFORE showing the loading screen. An untrusted module must
        # never begin loading; prompt the user to accept it first and abort here.
        mod_info = mw.module_manager.modules.get(module_id, {})
        trust_level = mod_info.get("trust_level", "verified")
        if trust_level == "untrusted":
            logger.warning(
                f"PluginLoader: Blocked load of untrusted module '{module_id}' — prompting user."
            )
            if mw.hub_manager.on_trust_requested(module_id):
                # User accepted: reload the (now-trusted) manifest and continue
                manifests = mw.module_manager.get_available_modules()
                manifest = next((m for m in manifests if m["id"] == module_id), manifest)
            else:
                # User declined — do not load
                return

        mw._switch_in_progress = True

        # An isolated module's real content is a separate OS window with its
        # own loading screen (see ui_daemon_runtime.run()'s GalacticLoader in
        # the SDK) — the Hub's own warp/hyperdrive cinematic has nothing
        # worth masking construction of here, and playing it in the Hub
        # before a window that isn't even the one about to show real content
        # is exactly the "loading screen in the hub view instead of the new
        # window" bug. Skipped entirely for isolated modules; on_module_loaded()
        # goes straight to instantiation once module_id is known to be one.
        is_isolated = mod_info.get("manifest", {}).get("process_model") == "isolated"
        mw._pending_is_isolated = is_isolated

        if hasattr(mw, "loader_widget") and mw.loader_widget is not None:
            mw.loader_widget.deleteLater()
        mw.loader_widget = None

        if not is_isolated:
            from karcytics.ui.widgets.galactic_loader import GalacticLoader

            mw.loader_widget = GalacticLoader(mw.root_stack)
            mw.loader_widget.set_module(module_name)
            mw.loader_widget.resize(mw.root_stack.size())
            mw.loader_widget.show()
            mw.loader_widget.raise_()

            # Connect the QML peak signal directly to instantiation
            mw.loader_widget.warp_out_finished.connect(self.on_warp_peaked)

        # 2. Cleanup existing thread if any
        if hasattr(mw, "_module_thread") and mw._module_thread and mw._module_thread.isRunning():
            mw._module_thread.quit()
            mw._module_thread.wait()

        # 3. Fully tear down the outgoing module (if any) before loading the next
        # one. The load below purges sys.modules entries that a still-alive old
        # panel may reference (matplotlib canvases, shared numpy/pandas copies) —
        # starting it before the old panel's C++ object is actually gone is what
        # produces the ModuleNotFoundError / "wrapped C/C++ object has been
        # deleted" crash this sequencing exists to prevent.
        old_panel = getattr(mw, "wizard_panel", None)
        old_module_id = getattr(mw, "current_module_id", None)
        if old_panel is not None and old_module_id is not None:
            self._begin_unload(old_panel, old_module_id, lambda: self._begin_module_load(manifest))
        else:
            self._begin_module_load(manifest)

    def _begin_unload(self, old_panel, old_module_id: str, on_complete) -> None:
        """
        Tears down the outgoing module's widget and purges its owned Python modules
        and sys.path entries before invoking `on_complete`, so the next module's
        load never races against this module's still-live objects.

        Parameters:
            old_panel: The outgoing module's panel widget.
            old_module_id (str): Identifier of the outgoing module.
            on_complete: Callback invoked once teardown is confirmed complete.
        """
        mw = self.main_window

        if hasattr(mw, "loader_widget") and mw.loader_widget:
            mw.loader_widget.set_status_message("Closing module…")

        finalized = {"done": False}

        def finalize(*_args) -> None:
            if finalized["done"]:
                return
            finalized["done"] = True
            if getattr(self, "_unload_safety", None):
                self._unload_safety.stop()
                self._unload_safety = None
            mw.module_manager.unload_module(old_module_id)
            on_complete()

        try:
            old_panel.destroyed.connect(finalize)
        except RuntimeError:
            # C++ object was already gone by the time we got here.
            finalize()
            return

        if hasattr(old_panel, "cleanup"):
            old_panel.cleanup()
        if hasattr(mw, "main_module_layout"):
            mw.main_module_layout.removeWidget(old_panel)
        if getattr(mw, "module_overlay", None) is old_panel:
            mw.module_overlay = None
        old_panel.setParent(None)
        old_panel.deleteLater()

        # Safety net: don't let a widget that never emits `destroyed` (e.g. a
        # broken plugin overriding deleteLater) hang the switch forever.
        from PyQt6.QtCore import QTimer

        self._unload_safety = QTimer(mw)
        self._unload_safety.setSingleShot(True)
        self._unload_safety.timeout.connect(finalize)
        self._unload_safety.start(5_000)

    def _begin_module_load(self, manifest: dict) -> None:
        """
        Starts the background import/load of a module's UI class.

        Parameters:
            manifest (dict): Module manifest containing the module identifier.
        """
        mw = self.main_window
        module_id = manifest["id"]

        mw._module_thread = QThread(mw)
        mw._module_worker = PluginUIWorker(mw.module_manager, module_id)
        mw._module_worker.moveToThread(mw._module_thread)

        mw._module_thread.started.connect(mw._module_worker.run)
        mw._module_worker.finished.connect(
            lambda PanelClass: self.on_module_loaded(manifest, PanelClass)  # noqa: N803
        )
        mw._module_worker.error.connect(lambda err: self.on_module_load_error(module_id, err))

        # Cleanup when done
        mw._module_worker.finished.connect(mw._module_thread.quit)
        mw._module_worker.error.connect(mw._module_thread.quit)

        mw._module_thread.start()

    def on_module_loaded(self, manifest: dict, PanelClass: type) -> None:  # noqa: N803
        """
        Stores the loaded module UI class and starts the loader's warp-out transition.

        Parameters:
            manifest (dict): Module manifest containing the module identifier.
            PanelClass (type): Loaded UI panel class.
        """
        mw = self.main_window
        module_id = manifest["id"]
        logger.info(
            f"PluginLoader: Successfully loaded UI class for module '{module_id}'. Waiting for GalacticLoader warp out..."
        )
        mw.current_module_id = module_id
        mw._pending_manifest = manifest
        mw._pending_panel_class = PanelClass

        if hasattr(mw, "loader_widget") and mw.loader_widget:
            # Step 1: Start warp-out immediately — animation keeps running natively via QML
            mw.loader_widget.warp_out()
        else:
            # Isolated module: open_module() deliberately never created a
            # loader_widget for this load, so nothing will ever emit
            # warp_out_finished — go straight to instantiating the module.
            self.on_warp_peaked()

    def on_warp_peaked(self) -> None:
        """
        Handles the loader's peak by creating the module panel and starting its initialization.

        Panels supporting the asynchronous initialization protocol remain behind the loader until
        their readiness signals allow the final crossfade. Legacy panels receive any pending
        workflow and transition immediately. Isolated modules never reach this "peak" via a real
        loader at all (see open_module()) and are routed to _instantiate_isolated_overlay()
        instead, which never touches root_stack's current page.
        """
        mw = self.main_window
        manifest = mw._pending_manifest
        PanelClass = mw._pending_panel_class  # noqa: N806
        mw._pending_manifest = None
        mw._pending_panel_class = None
        is_isolated = getattr(mw, "_pending_is_isolated", False)
        mw._pending_is_isolated = False

        if is_isolated:
            self._instantiate_isolated_overlay(manifest, PanelClass)
            return

        self.instantiate_module_panel(manifest, PanelClass)
        panel = mw.wizard_panel

        # ── Ready Gate protocol ─────────────────────────────────────────
        if (
            panel is not None
            and hasattr(panel, "panel_ready")
            and hasattr(panel, "begin_async_init")
        ):
            # Store manifest so the ready callbacks can read the module name
            mw._active_manifest = manifest

            # ── Hand off the pending workflow to the panel ──────────────────
            if (
                hasattr(mw, "_pending_workflow_payload")
                and mw._pending_workflow_payload is not None
            ):
                panel._deferred_workflow_payload = mw._pending_workflow_payload
                panel._deferred_workflow_filename = getattr(mw, "_pending_workflow_filename", None)
                panel._deferred_workflow_metadata = getattr(mw, "_pending_workflow_metadata", None)
                mw._pending_workflow_payload = None
                mw._pending_workflow_filename = None
                mw._pending_workflow_metadata = None

            # Update the loader’s secondary status line while Phase 2 builds
            if hasattr(mw, "loader_widget") and mw.loader_widget:
                mw.loader_widget.set_status_message("Rendering workspace…")

            self._panel_ready_received = False
            self._data_ready_received = False

            # Connect BOTH signals upfront so no signal is EVER missed
            panel.panel_ready.connect(self._on_panel_ready)
            if hasattr(panel, "data_ready"):
                panel.data_ready.connect(self._on_data_ready)

                from PyQt6.QtCore import QTimer

                self._data_ready_safety = QTimer(mw)
                self._data_ready_safety.setSingleShot(True)
                self._data_ready_safety.timeout.connect(self._on_data_ready_timeout)
                self._data_ready_safety.start(45_000)  # 45 s covers Numba JIT cold-start

            panel.begin_async_init()
        else:
            # ── Legacy fallback ─────────────────────────────────────────
            self._inject_pending_workflow(manifest)
            mw.status_bar.showMessage(
                f"{manifest.get('display_name', 'Analysis')} — open a project to begin"
            )
            self.crossfade_to_analysis()

    def _instantiate_isolated_overlay(self, manifest: dict, PanelClass: type) -> None:  # noqa: N803
        """Construct an isolated module's `ModuleStatusWidget` as a blocking
        overlay on top of whatever the Hub is currently showing, instead of
        embedding it into the analysis page's content area.

        An isolated module's real content is a separate OS window — the Hub
        never actually "enters" that module the way it does an in-process
        panel, so switching `root_stack` to the analysis page (and its
        module-branded toolbar/footer: "Return to Hub", the module's own
        title, Cyto Academy) would be showing chrome for a view the Hub was
        never actually going to render anything into. The overlay floats
        directly on `root_stack`; whatever page was already current stays
        current.
        """
        mw = self.main_window
        module_id = manifest["id"]
        logger.info(f"PluginLoader: Instantiating overlay for isolated module '{module_id}'.")

        has_pending_workflow = (
            hasattr(mw, "_pending_workflow_payload") and mw._pending_workflow_payload is not None
        )

        from karcytics_sdk.plugin.daemon import PluginUIDaemon

        daemon = PluginUIDaemon.get_instance(module_id)
        if has_pending_workflow:
            daemon.pending_workflow = True
        else:
            daemon.pending_workflow = False

        # core_intro's own module-phase steps can't reach across this
        # process boundary any more than anything else here can (see
        # _instantiate_isolated_overlay's own docstring) — when the Hub's
        # tour is the reason this module is opening, hand its in-module
        # continuation off to this plugin's own local Academy course
        # instead (see karcytics_plugins.flow_cytometry.tutorials
        # .core_intro_handoff, and this daemon's own pending_workflow
        # above for the identical staging pattern). The plugin reports
        # back via an "academy_handoff_complete" event once that course
        # finishes — see _wire_academy_handoff_forwarding in
        # karcytics.core.plugins.loader.
        from karcytics.core.tutorial_manager import global_tutorial_manager

        active_course = global_tutorial_manager.active_course
        current_step = global_tutorial_manager.current_step
        daemon.pending_academy_handoff = bool(
            active_course
            and active_course.id == "core_intro_v1"
            and current_step
            and current_step.id == "ws_open_module_action"
        )

        try:
            mw.wizard_panel = PanelClass()
            assert mw.wizard_panel is not None
            widget = mw.wizard_panel

            widget.setParent(mw.root_stack)
            widget.setGeometry(mw.root_stack.rect())
            widget.raise_()
            widget.show()
            mw.module_overlay = widget

            def _on_overlay_state_changed(state: str, widget=widget) -> None:
                # A user-initiated close should hand the Hub straight back —
                # unlike Crashed, there's nothing here worth keeping the
                # user blocked in front of.
                from karcytics_sdk.host.module_status_widget import ModuleStatusWidget

                if state == ModuleStatusWidget.STATE_CLOSED:
                    widget.hide()
                    if getattr(mw, "module_overlay", None) is widget:
                        mw.module_overlay = None

            widget.state_changed.connect(_on_overlay_state_changed)

            mw.current_module_id = module_id
            event_bus.emit(KarcyticsEvent.MODULE_OPENED, module_id)
        except Exception as e:
            import traceback

            logger.error(f"Failed to initialize isolated module: {e}", exc_info=True)
            self.on_module_load_error(module_id, traceback.format_exc())
            return
        finally:
            mw._switch_in_progress = False

        mw._active_manifest = manifest

        # Inject pending workflow via RPC for isolated modules
        if hasattr(mw, "_pending_workflow_payload") and mw._pending_workflow_payload is not None:
            payload = mw._pending_workflow_payload
            filename = getattr(mw, "_pending_workflow_filename", None)
            metadata = getattr(mw, "_pending_workflow_metadata", None)

            import threading

            from karcytics_sdk.plugin.daemon import PluginUIDaemon

            daemon = PluginUIDaemon.get_instance(module_id)

            def _send_workflow():
                try:
                    daemon.call(
                        "inject_workflow",
                        {"payload": payload, "filename": filename, "metadata": metadata},
                        timeout=30.0,
                    )
                except Exception as e:
                    logger.error(
                        f"Failed to inject workflow into isolated module '{module_id}': {e}"
                    )

            threading.Thread(target=_send_workflow, daemon=True).start()
            mw.status_bar.showMessage("Injecting workflow payload into isolated module...")

        mw._pending_workflow_payload = None
        mw._pending_workflow_filename = None
        mw._pending_workflow_metadata = None

    def _on_panel_ready(self) -> None:
        """Handles completion of asynchronous panel construction and advances to data loading or the final UI transition."""
        mw = self.main_window
        panel = mw.wizard_panel

        if panel is None:
            return

        # One-shot disconnect
        try:  # noqa: SIM105
            panel.panel_ready.disconnect(self._on_panel_ready)
        except Exception:
            pass

        self._panel_ready_received = True

        # Update loader message to reflect data loading phase
        if hasattr(mw, "loader_widget") and mw.loader_widget:
            mw.loader_widget.set_status_message("Loading workspace data…")

        if not hasattr(panel, "data_ready"):
            # Simple protocol: crossfade immediately
            self._trigger_crossfade()
        elif getattr(self, "_data_ready_received", False):
            # data_ready was already received! Crossfade immediately
            self._trigger_crossfade()

    def _on_data_ready(self) -> None:
        """
        Marks the active panel's data as ready and starts the final transition when the panel is ready for display.
        """
        logger.info("PluginLoader: data_ready signal received from active panel!")
        mw = self.main_window
        panel = mw.wizard_panel

        if panel is not None and hasattr(panel, "data_ready"):
            try:  # noqa: SIM105
                panel.data_ready.disconnect(self._on_data_ready)
            except Exception:
                pass

        if hasattr(self, "_data_ready_safety") and self._data_ready_safety:
            self._data_ready_safety.stop()
            self._data_ready_safety = None

        self._data_ready_received = True

        if getattr(self, "_panel_ready_received", False) or not hasattr(panel, "panel_ready"):
            self._trigger_crossfade()

    def _on_data_ready_timeout(self) -> None:
        """Safety net: force crossfade if data_ready never fires within the timeout."""
        logger.warning(
            "PluginLoader: data_ready signal not received within 45 s — forcing crossfade."
        )
        self._data_ready_safety = None
        self._trigger_crossfade()

    def _trigger_crossfade(self) -> None:
        """Updates the status message and transitions to the analysis page."""
        logger.info("PluginLoader: Triggering crossfade_to_analysis()...")
        mw = self.main_window
        manifest = getattr(mw, "_active_manifest", {})
        mw.status_bar.showMessage(
            f"{manifest.get('display_name', 'Analysis')} — open a project to begin"
        )
        self.crossfade_to_analysis()

    def _inject_pending_workflow(self, manifest: dict | None = None) -> None:  # noqa: ARG002
        """
        Load the pending workflow payload into the active wizard panel when supported.

        The payload is passed with its filename and metadata when the panel accepts
        those arguments. Pending workflow data and associated metadata are cleared
        after processing.
        """
        mw = self.main_window
        panel = mw.wizard_panel
        if panel is None:
            return
        if not (
            hasattr(mw, "_pending_workflow_payload") and mw._pending_workflow_payload is not None
        ):
            return

        if hasattr(panel, "load_workflow"):
            import inspect

            sig = inspect.signature(panel.load_workflow)
            kwargs = {}
            if "filename" in sig.parameters:
                kwargs["filename"] = getattr(mw, "_pending_workflow_filename", None)
            if "metadata" in sig.parameters:
                kwargs["metadata"] = getattr(mw, "_pending_workflow_metadata", None)

            panel.load_workflow(mw._pending_workflow_payload, **kwargs)
            mw.status_bar.showMessage("Successfully loaded workflow payload.")

        mw._pending_workflow_payload = None
        mw._pending_workflow_filename = None
        mw._pending_workflow_metadata = None

    def instantiate_module_panel(self, manifest: dict, PanelClass: type) -> None:  # noqa: N803
        """
        Instantiates the plugin panel, configures its UI integrations, and emits the module-opened event.

        Parameters:
            manifest (dict): Module metadata containing the module identifier and optional display details.
            PanelClass (type): Panel class to instantiate.
        """
        mw = self.main_window
        module_id = manifest["id"]
        logger.info(f"PluginLoader: Instantiating UI panel for '{module_id}' and wiring events.")
        try:
            # Note: the outgoing module's panel (if any) was already torn down and
            # unloaded in open_module()'s _begin_unload() step, before this module's
            # load even started — see that method for why the ordering matters.
            mw.wizard_panel = PanelClass()
            assert mw.wizard_panel is not None
            mw.wizard_panel.project_manager = mw.project_manager

            mw.main_module_layout.addWidget(mw.wizard_panel)

            if hasattr(mw.wizard_panel, "canvas") and hasattr(
                mw.wizard_panel.canvas, "zoom_changed"
            ):
                mw.wizard_panel.canvas.zoom_changed.connect(
                    lambda z: mw.zoom_label.setText(f"{z * 100:.0f}%")
                )
            elif hasattr(mw.wizard_panel, "zoom_changed"):
                mw.wizard_panel.zoom_changed.connect(
                    lambda z: mw.zoom_label.setText(f"{z * 100:.0f}%")
                )

            mw.analysis_toolbar.set_title(
                manifest.get("icon", "📦"), manifest.get("display_name", "Analysis")
            )

            if hasattr(mw.wizard_panel, "status_message"):
                mw.wizard_panel.status_message.connect(mw.status_bar.showMessage)
            if hasattr(mw.wizard_panel, "state_changed"):
                if hasattr(mw, "_push_history"):
                    mw.wizard_panel.state_changed.connect(mw._push_history)
                # Hook state_changed to detect file imports for the tutorial
                mw.wizard_panel.state_changed.connect(mw._on_wizard_state_changed)

            # Emit MODULE_OPENED for WaitForEventStep(MODULE_OPENED)
            event_bus.emit(KarcyticsEvent.MODULE_OPENED, module_id)

            # NOTE: Workflow injection is intentionally NOT done here.
            # For panels supporting the Phase 2 protocol (begin_async_init / panel_ready),
            # injection is deferred to _inject_pending_workflow() which is called from
            # _on_panel_ready() after heavy widgets are fully built.
            # For legacy panels, on_warp_peaked() calls _inject_pending_workflow() directly.

            logger.info(
                f"PluginLoader: Module '{module_id}' skeleton initialised — Phase 2 pending."
            )

        except Exception as e:
            import logging
            import traceback

            logging.getLogger(__name__).error(f"Failed to initialize module: {e}", exc_info=True)
            self.on_module_load_error(module_id, traceback.format_exc())
        finally:
            mw._switch_in_progress = False

    def crossfade_to_analysis(self) -> None:
        """
        Switches to the analysis page and fades out the loading overlay.
        """
        mw = self.main_window
        # Switch the stack to the analysis page
        mw.root_stack.setCurrentIndex(1)  # _PAGE_ANALYSIS = 1

        # Smooth hardware-accelerated QML opacity fade-out
        if hasattr(mw, "loader_widget") and mw.loader_widget:
            loader = mw.loader_widget
            # Ensure the loader stays ON TOP of Page 1 while fading out
            loader.raise_()

            def on_fade_done():
                """
                Remove the completed loader overlay when it is still the active loader widget.
                """
                if hasattr(mw, "loader_widget") and mw.loader_widget == loader:
                    mw.loader_widget.deleteLater()
                    mw.loader_widget = None

            if hasattr(loader, "fade_out_finished"):
                loader.fade_out_finished.connect(on_fade_done)

            if hasattr(loader, "fade_out"):
                loader.fade_out(700)
            else:
                from PyQt6.QtCore import QTimer

                QTimer.singleShot(700, on_fade_done)

    def on_module_load_error(self, module_id: str, error_msg: str) -> None:
        """
        Handle a module loading failure, including trust approval retries and user-facing error reporting.

        Parameters:
            module_id (str): Identifier of the module that failed to load.
            error_msg (str): Traceback or error message describing the failure.
        """
        mw = self.main_window
        mw._switch_in_progress = False

        # Cleanup loader
        if hasattr(mw, "loader_widget") and mw.loader_widget:
            mw.loader_widget.deleteLater()
            mw.loader_widget = None

        # Discard any pending warp-peaked state
        mw._pending_manifest = None
        mw._pending_panel_class = None

        # Force immediate return to home screen without animation so dialogs appear over the right UI
        mw.root_stack.setCurrentIndex(0)  # _PAGE_HOME = 0
        mw.root_stack.setGraphicsEffect(None)

        from karcytics.ui.dialogs.error_report import ErrorReportDialog

        # Extract the exact exception message from the last line of the traceback if possible
        lines = [line.strip() for line in error_msg.strip().split("\n") if line.strip()]
        exc_msg = lines[-1] if lines else error_msg

        if "PermissionError: Security Block:" in exc_msg:
            # The module is untrusted, prompt user to lock it
            if mw.hub_manager.on_trust_requested(module_id):
                # If they successfully trusted it, find the manifest and try loading again!
                manifests = mw.module_manager.get_available_modules()
                manifest = next((m for m in manifests if m["id"] == module_id), None)
                if manifest:
                    self.open_module(manifest)
            else:
                # User declined or it failed, so we should discard the pending workflow
                mw._pending_workflow_payload = None
                mw._pending_workflow_filename = None
                mw._pending_workflow_metadata = None
        else:
            # We explicitly ignore ModuleNotFoundError here since users might
            # uninstall a plugin without removing the hub metadata cache.
            # But we DO surface it if it's some other exception so they know it failed.
            if "ModuleNotFoundError" not in exc_msg:
                error_data = {
                    "plugin_id": module_id,
                    "message": f"Failed to load module '{module_id}'",
                    "traceback": error_msg,
                }
                dialog = ErrorReportDialog(error_data, mw)
                dialog.exec()
