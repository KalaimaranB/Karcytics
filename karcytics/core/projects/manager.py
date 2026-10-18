"""Core module."""

import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from karcytics.core.event_bus import KarcyticsEvent, event_bus
from karcytics.core.history_manager import HistoryManager
from karcytics.core.projects.assets import AssetManager
from karcytics.core.projects.locking import ProjectLock
from karcytics.core.projects.workflows import WorkflowManager
from karcytics.core.utils import AtomicJsonFile

logger = logging.getLogger(__name__)


class ProjectManager:
    """Orchestrates Karcytics project operations by delegating to specialized managers."""

    def __init__(self, project_dir: Path | str):
        """Initialize project state and managers for the specified project directory.

        Parameters:
            project_dir (Path | str): Directory containing the Karcytics project files.
        """
        self.project_dir = Path(project_dir)
        self.project_file = self.project_dir / "project.karcytics"
        self.assets_dir = self.project_dir / "assets"
        self.history_file = self.project_dir / "history.json"

        # Internal State
        self.data: dict[str, Any] = {}
        self.history_manager = HistoryManager(max_steps=50)

        # Specialized Managers
        self.locker = ProjectLock(self.project_dir)
        self.assets = AssetManager(self.project_dir, self.assets_dir)
        self.workflows = WorkflowManager(self.project_dir)

    @property
    def project_name(self) -> str:
        """Return the project name, falling back to directory name when none is configured."""
        return self.data.get("project_name", self.project_dir.name)

    @property
    def config(self) -> dict:
        """Provide the current project configuration.

        Returns:
            dict: The in-memory project state.
        """
        return self.data

    # ── Lifecycle ─────────────────────────────────────────────────────

    def create_new(self, project_name: str, is_academy: bool = False) -> None:
        """Create a new Karcytics project with the specified name and academy status.

        Parameters:
            project_name (str): Name of the project.
            is_academy (bool): Whether the project is an academy project.

        Raises:
            FileExistsError: If the project directory already exists.
        """
        if self.project_dir.exists():
            raise FileExistsError("Directory already exists.")

        self.project_dir.mkdir(parents=True)
        self.assets_dir.mkdir()

        self.data = {
            "project_name": project_name,
            "is_academy": is_academy,
            "created_at": datetime.now().isoformat(),
            "last_modified": datetime.now().isoformat(),
            "assets": {},
            "analysis_state": {},
        }

        self.save()
        self.locker.acquire()
        logger.info(f"Created new project: {project_name}")

    def open_project(self) -> None:
        """Open the project, restore its saved state and history, and validate its assets.

        Raises:
            FileNotFoundError: If the project file does not exist.
        """
        try:
            legacy_project_file = self.project_dir / "project.biopro"
            if not self.project_file.exists() and legacy_project_file.exists():
                legacy_project_file.rename(self.project_file)
                logger.info(
                    f"Migrated legacy project file: {legacy_project_file.name} -> "
                    f"{self.project_file.name}"
                )

            if not self.project_file.exists():
                raise FileNotFoundError(f"Not a valid Karcytics project: {self.project_file}")

            self.locker.acquire()

            try:
                self.data = AtomicJsonFile.load(self.project_file, default=None)
                if self.data is None:
                    raise FileNotFoundError
            except Exception as e:
                logger.error(
                    f"Project file corrupted or missing: {e}. Using default state.", exc_info=True
                )
                if not self.data:
                    self.data = {
                        "project_name": self.project_dir.name,
                        "assets": {},
                        "analysis_state": {},
                    }

            if self.history_file.exists():
                try:
                    self.history_file.unlink()
                    logger.info("Deleted legacy history.json file.")
                except Exception as e:
                    logger.warning(f"Could not delete legacy history.json: {e}")

            self.validate_assets()
            logger.info(f"Opened project: {self.project_name}")
        except Exception as e:
            logger.error(f"Failed to open project: {e}", exc_info=True)
            raise e

    def save(self) -> None:
        """Persist the current project state and history to their JSON files.

        Raises:
            OSError: If the project or history data cannot be saved atomically.
            Exception: Re-raises errors encountered while saving the project state.
        """
        try:
            self.data["last_modified"] = datetime.now().isoformat()

            # Atomic Save for Project File
            if not AtomicJsonFile.save(self.project_file, self.data):
                raise OSError("Failed to atomically save project data.")
        except Exception as e:
            logger.error(f"Failed to save project: {e}", exc_info=True)
            from karcytics.core.diagnostics import diagnostics

            diagnostics.report_error(f"Failed to save project: {e}")
            raise e

    def close(self) -> None:
        """Saves the project and releases its lock.

        The project remains locked if saving fails.
        """
        self.save()
        self.locker.release()
        logger.info("Project closed and unlocked.")

    # ── Delegated Operations ──────────────────────────────────────────

    def add_image(
        self, filepath: Path | str, copy_to_workspace: bool, subfolder: str | None = None
    ) -> str:
        """Add an image to the project and persist the updated project state.

        Parameters:
                filepath (Path | str): Path to the image file.
                copy_to_workspace (bool): Whether to copy the image into the project workspace.
                subfolder (str | None): Optional workspace subfolder for the image.

        Returns:
                str: Identifier of the added image.
        """
        h = self.assets.add_image(self.data, filepath, copy_to_workspace, subfolder)
        self.save()
        return h

    def batch_add_images(
        self, filepaths: list[Path | str], copy_to_workspace: bool, subfolder: str | None = None
    ) -> list[str]:
        """Add multiple images to the project and persist the updated asset state.

        Parameters:
                filepaths (list[Path | str]): Image files to add.
                copy_to_workspace (bool): Whether to copy the images into the project workspace.
                subfolder (str | None): Optional workspace subfolder for copied images.

        Returns:
                list[str]: Asset identifiers for the added images.
        """
        hashes = [
            self.assets.add_image(self.data, fp, copy_to_workspace, subfolder) for fp in filepaths
        ]
        self.save()
        return hashes

    def validate_assets(self) -> None:
        """Validates the project's asset references and saves if changes are required."""
        if self.assets.validate_assets(self.data):
            self.save()

    def get_asset_path(self, file_hash: str) -> Path | None:
        """Return the filesystem path for a stored asset.

        Parameters:
            file_hash (str): Identifier of the asset.

        Returns:
            Path | None: The asset path if it is available, otherwise `None`.
        """
        return self.assets.get_asset_path(self.data, file_hash)

    def save_workflow(
        self,
        module_id: str,
        payload: dict,
        metadata: dict,
        filename: str | None = None,
        attachments: list[dict] | None = None,
    ) -> str:
        """Persist a workflow and notify subscribers that it was saved.

        Parameters:
            module_id (str): Identifier of the workflow module.
            payload (dict): Workflow content to persist.
            metadata (dict): Metadata associated with the workflow.
            filename (str | None): Optional workflow filename.
            attachments (list[dict] | None): Optional files associated with the workflow.

        Returns:
            str: Identifier of the saved workflow.
        """
        result = self.workflows.save(module_id, payload, metadata, filename, attachments)
        event_bus.emit(KarcyticsEvent.WORKFLOW_SAVED, result)
        return result

    def attach_workflow_file(
        self,
        wf_filename: str,
        source_path: Path | str,
        key: str,
        description: str = "",
        mime_hint: str = "application/octet-stream",
    ) -> dict:
        """Attach a file to a saved workflow.

        Parameters:
                wf_filename (str): The workflow filename.
                source_path (Path | str): The path to the file to attach.
                key (str): The attachment key.
                description (str): A description of the attachment.
                mime_hint (str): The attachment's MIME type hint.

        Returns:
                dict: Metadata for the attached file.
        """
        return self.workflows.attach_file(wf_filename, source_path, key, description, mime_hint)

    def get_attachment_path(self, wf_filename: str, key: str) -> Path | None:
        """Locate a workflow attachment by key.

        Parameters:
            wf_filename (str): Workflow filename containing the attachment.
            key (str): Attachment key to locate.

        Returns:
            Path | None: The existing attachment path, or `None` if the attachment is unavailable.
        """
        attachments = self.workflows.load_attachments(wf_filename)
        for att in attachments:
            if att.get("key") == key:
                rel_path = att.get("relative_path")
                if rel_path:
                    path = self.project_dir / rel_path
                    if path.exists():
                        return path
        return None

    def list_workflows(self) -> list[dict]:
        """List all saved workflows.

        Returns:
                list[dict]: Workflow metadata entries.
        """
        return self.workflows.list_all()

    def load_workflow_payload(self, filename: str) -> dict:
        """Load the payload for a saved workflow.

        Parameters:
                filename (str): The workflow filename.

        Returns:
                dict: The workflow payload.
        """
        return self.workflows.load_payload(filename)

    def get_workflow_hash(self, filename: str) -> str | None:
        """Get the content hash for a saved workflow.

        Parameters:
            filename (str): The workflow filename.

        Returns:
            str | None: The workflow hash, or `None` if no hash is available.
        """
        return self.workflows.get_hash(filename)

    def delete_workflow(self, module_id: str, filename: str) -> bool:  # noqa: ARG002
        """Delete a saved workflow by filename.

        Parameters:
            filename (str): Name of the workflow file.

        Returns:
            bool: `true` if the workflow was deleted, `false` otherwise.
        """
        return self.workflows.delete(filename)

    def rename_workflow(self, filename: str, new_name: str) -> bool:
        """Update the display name stored in a workflow's metadata block.

        The file on disk is not renamed; only ``metadata.name`` is updated.

        Args:
            filename: The workflow JSON filename (basename only).
            new_name: The new human-readable display name.

        Returns:
            ``True`` if the update was written successfully, ``False`` otherwise.
        """
        return self.workflows.rename(filename, new_name)

    def duplicate_workflow(self, filename: str) -> str | None:
        """Deep-copy a workflow (and its attachments) under a new filename.

        Args:
            filename: The workflow JSON filename (basename only) to duplicate.

        Returns:
            The new workflow's filename (basename), or ``None`` on failure.
        """
        return self.workflows.duplicate(filename)

    def delete_workflow_attachment(self, filename: str, key: str) -> bool:
        """Delete an attachment from a saved workflow.

        Parameters:
            filename (str): Workflow filename.
            key (str): Attachment key.

        Returns:
            bool: `True` if the attachment was deleted, `False` otherwise.
        """
        return self.workflows.delete_attachment(filename, key)
