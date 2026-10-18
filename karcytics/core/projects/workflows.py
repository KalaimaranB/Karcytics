"""Core module."""

import logging
import os
import shutil
from pathlib import Path

from karcytics.core.utils import AtomicJsonFile

logger = logging.getLogger(__name__)


class WorkflowManager:
    """Manages scientific workflows stored as JSON in the project workspace."""

    def __init__(self, project_dir: Path):
        """Initialize a workflow manager for a project directory.

        Parameters:
                project_dir (Path): Root directory containing the project's workflow files.
        """
        self.project_dir = project_dir
        self.wf_dir = self.project_dir / "workflows"

    def save(
        self,
        module_id: str,
        payload: dict,
        metadata: dict,
        filename: str | None = None,
        attachments: list[dict] | None = None,
    ) -> str:
        """Saves an aggregated module payload as a JSON workflow."""
        self.wf_dir.mkdir(exist_ok=True)

        if filename:
            filepath = self.wf_dir / filename
            safe_name = filepath.stem
        else:
            safe_name = "".join([c for c in metadata["name"] if c.isalnum() or c == " "])
            safe_name = safe_name.replace(" ", "_").lower() or "untitled_workflow"

            filepath = self.wf_dir / f"{safe_name}.json"
            counter = 1
            while filepath.exists():
                filepath = self.wf_dir / f"{safe_name}_{counter}.json"
                counter += 1
                safe_name = filepath.stem

        metadata["module"] = module_id

        import typing

        workflow_data: dict[str, typing.Any] = {"metadata": metadata, "payload": payload}
        if attachments is not None:
            workflow_data["attachments"] = attachments

        if not AtomicJsonFile.save(filepath, workflow_data):
            raise OSError(f"Failed to atomically save workflow: {filepath.name}")

        return str(filepath.name)

    def attach_file(
        self,
        wf_filename: str,
        source_path: Path | str,
        key: str,
        description: str = "",
        mime_hint: str = "application/octet-stream",
    ) -> dict:
        """Copies an auxiliary file into the workflow's attachment folder and returns its record."""
        source_path = Path(source_path)
        if not source_path.exists():
            raise FileNotFoundError(f"Attachment source not found: {source_path}")

        wf_filepath = self.wf_dir / wf_filename
        wf_stem = wf_filepath.stem
        att_dir = self.wf_dir / f"{wf_stem}_attachments"
        att_dir.mkdir(parents=True, exist_ok=True)

        dest_path = att_dir / source_path.name

        # Handle filename collisions within attachments directory
        counter = 1
        while dest_path.exists():
            dest_path = att_dir / f"{source_path.stem}_{counter}{source_path.suffix}"
            counter += 1

        shutil.copy2(source_path, dest_path)

        import hashlib

        sha256 = hashlib.sha256()
        with open(dest_path, "rb") as f:
            while chunk := f.read(8192):
                sha256.update(chunk)

        rel_path = dest_path.relative_to(self.project_dir).as_posix()

        return {
            "key": key,
            "filename": dest_path.name,
            "relative_path": rel_path,
            "mime_hint": mime_hint,
            "description": description,
            "size_bytes": dest_path.stat().st_size,
            "sha256": sha256.hexdigest(),
        }

    def list_all(self) -> list[dict]:
        """Scans the workflows directory and returns metadata."""
        if not self.wf_dir.exists():
            return []

        workflows = []
        for file in self.wf_dir.glob("*.json"):
            try:
                data = AtomicJsonFile.load(file, default=None)
                if data:
                    meta = data.get("metadata", {})
                    meta["filename"] = file.name
                    workflows.append(meta)
            except Exception:
                pass

        workflows.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        return workflows

    def load_payload(self, filename: str) -> dict:
        """Extracts the exact scientific payload."""
        filepath = self.wf_dir / filename
        data = AtomicJsonFile.load(filepath, default=None)
        if not data:
            return {}
        return data.get("payload", {})

    def load_attachments(self, filename: str) -> list[dict]:
        """Extracts the attachments manifest."""
        filepath = self.wf_dir / filename
        data = AtomicJsonFile.load(filepath, default=None)
        if not data:
            return []
        return data.get("attachments", [])

    def get_hash(self, filename: str) -> str | None:
        """Returns the SHA-256 hash of a workflow file."""
        import hashlib

        filepath = self.wf_dir / filename
        if not filepath.exists():
            return None
        sha256 = hashlib.sha256()
        with open(filepath, "rb") as f:
            while chunk := f.read(8192):
                sha256.update(chunk)
        return sha256.hexdigest()

    def rename(self, filename: str, new_name: str) -> bool:
        """Updates the display name stored in a workflow's metadata block.

        Only the ``metadata.name`` field is changed; the filename on disk is
        preserved so that all existing references remain valid.

        Args:
            filename: The workflow JSON filename (basename only).
            new_name: The new human-readable display name to store.

        Returns:
            ``True`` if the update was written successfully, ``False`` otherwise.
        """
        filepath = self.wf_dir / os.path.basename(filename)
        data = AtomicJsonFile.load(filepath, default=None)
        if not data:
            return False

        try:
            data.setdefault("metadata", {})["name"] = new_name
            if not AtomicJsonFile.save(filepath, data):
                raise OSError("Atomic save failed.")
            return True
        except Exception as e:
            logger.error(f"Failed to rename workflow {filename}: {e}")
            return False

    def duplicate(self, filename: str) -> str | None:
        """Creates a deep copy of a workflow under a new conflict-free filename.

        The new workflow's ``metadata.name`` is set to ``"<original> (Copy)"``.
        If an attachments folder exists for the source workflow it is copied
        verbatim into a correspondingly named attachments folder for the
        duplicate, and the ``relative_path`` values in the manifest are
        rewritten to point at the new location.

        Args:
            filename: The workflow JSON filename (basename only) to duplicate.

        Returns:
            The new workflow's filename (basename), or ``None`` on failure.
        """
        src_path = self.wf_dir / os.path.basename(filename)
        data = AtomicJsonFile.load(src_path, default=None)
        if not data:
            return None

        try:
            import copy

            new_data = copy.deepcopy(data)

            # Build a conflict-free filename for the copy
            src_stem = src_path.stem
            base_stem = f"{src_stem}_copy"
            dest_path = self.wf_dir / f"{base_stem}.json"
            counter = 1
            while dest_path.exists():
                dest_path = self.wf_dir / f"{base_stem}_{counter}.json"
                counter += 1
            new_stem = dest_path.stem

            # Update display name in metadata
            original_name = new_data.get("metadata", {}).get("name", src_stem)
            new_data.setdefault("metadata", {})["name"] = f"{original_name} (Copy)"

            # Copy attachments folder if present and rewrite relative_path refs
            src_att_dir = self.wf_dir / f"{src_stem}_attachments"
            if src_att_dir.exists() and src_att_dir.is_dir():
                dest_att_dir = self.wf_dir / f"{new_stem}_attachments"
                shutil.copytree(src_att_dir, dest_att_dir)

                # Rewrite relative_path inside the attachments manifest
                for att in new_data.get("attachments", []):
                    rel = att.get("relative_path", "")
                    if rel:
                        # Replace the old stem segment in the path with the new one
                        att["relative_path"] = rel.replace(
                            f"workflows/{src_stem}_attachments/",
                            f"workflows/{new_stem}_attachments/",
                            1,
                        )

            if not AtomicJsonFile.save(dest_path, new_data):
                raise OSError("Atomic save failed for duplicate.")

            return dest_path.name
        except Exception as e:
            logger.error(f"Failed to duplicate workflow {filename}: {e}")
            return None

    def delete(self, filename: str) -> bool:
        """Deletes a saved workflow JSON file."""
        file_path = self.wf_dir / os.path.basename(filename)
        att_dir = self.wf_dir / f"{file_path.stem}_attachments"

        try:
            if file_path.exists() and file_path.is_file():
                os.remove(file_path)

                # Delete attachments folder if it exists
                if att_dir.exists() and att_dir.is_dir():
                    shutil.rmtree(att_dir)

                return True
        except Exception as e:
            logger.error(f"Failed to delete workflow {filename}: {e}")
        return False

    def delete_attachment(self, filename: str, key: str) -> bool:
        """Deletes a specific attachment from a workflow and updates its manifest."""
        filepath = self.wf_dir / os.path.basename(filename)
        data = AtomicJsonFile.load(filepath, default=None)
        if not data:
            return False

        try:
            attachments = data.get("attachments", [])
            target_att = None

            for att in attachments:
                if att.get("key") == key:
                    target_att = att
                    break

            if not target_att:
                return False

            # Remove from json and save
            attachments.remove(target_att)
            if not attachments:
                data.pop("attachments", None)
            else:
                data["attachments"] = attachments

            if not AtomicJsonFile.save(filepath, data):
                raise OSError("Failed to save updated workflow attachments.")

            # Delete physical file
            rel_path = target_att.get("relative_path")
            if rel_path:
                phys_path = self.project_dir / rel_path
                if phys_path.exists() and phys_path.is_file():
                    os.remove(phys_path)
            return True

        except Exception as e:
            logger.error(f"Failed to delete attachment {key} from {filename}: {e}")
            return False
