from pathlib import Path
from unittest.mock import patch

import pytest

from karcytics.core.project_manager import ProjectLockedError, ProjectManager


@pytest.fixture
def empty_project_dir(tmp_path):
    """Fixture for an empty project directory."""
    return tmp_path / "test_project"


@pytest.fixture
def open_project(empty_project_dir):
    """Fixture for an initialized and open project."""
    pm = ProjectManager(empty_project_dir)
    pm.create_new("Test Project")
    return pm


class TestProjectManager:
    """Test suite for ProjectManager."""

    def test_create_new_project(self, empty_project_dir):
        """Verifies that a new project creates the expected folder structure and files."""
        pm = ProjectManager(empty_project_dir)
        pm.create_new("My Project")

        assert empty_project_dir.exists()
        assert (empty_project_dir / "project.karcytics").exists()
        assert (empty_project_dir / "assets").exists()
        assert (empty_project_dir / ".karcytics.lock").exists()
        assert pm.data["project_name"] == "My Project"

    def test_open_project_locks(self, empty_project_dir):
        """Verifies that opening an existing project correctly acquires a lock."""
        # Setup: Create and close a project
        pm1 = ProjectManager(empty_project_dir)
        pm1.create_new("New Project")
        pm1.close()  # Release lock

        # Re-open in instance 1
        pm1.open_project()

        # Instance 2 should fail to open
        pm2 = ProjectManager(empty_project_dir)
        with pytest.raises(ProjectLockedError):
            pm2.open_project()

    def test_asset_addition_single(self, open_project, tmp_path):
        """Tests adding a single image to the project assets."""
        pm = open_project
        img_path = tmp_path / "test_image.png"
        img_path.write_text("fake binary content")

        file_hash = pm.add_image(img_path, copy_to_workspace=True)

        assert file_hash in pm.data["assets"]
        asset = pm.data["assets"][file_hash]
        assert asset["filename"] == "test_image.png"
        assert asset["copied_to_workspace"] is True

        local_path = pm.project_dir / asset["local_path"]
        assert local_path.exists()

    def test_batch_add_images_with_subfolder(self, open_project, tmp_path):
        """Tests the new batch loading feature with subdirectory support."""
        pm = open_project

        # Create 3 dummy files
        files = []
        for i in range(3):
            p = tmp_path / f"experiment_{i}.tiff"
            p.write_text(f"data_{i}")
            files.append(p)

        hashes = pm.batch_add_images(files, copy_to_workspace=True, subfolder="cohort_a")

        assert len(hashes) == 3
        # Check that the subdirectory was created
        assert (pm.assets_dir / "cohort_a").exists()

        for h in hashes:
            asset = pm.data["assets"][h]
            # Verify paths are relative and correct
            local_path_posix = Path(asset["local_path"]).as_posix()
            assert "assets/cohort_a" in local_path_posix
            assert (pm.project_dir / asset["local_path"]).exists()

    def test_validate_assets_pruning(self, open_project, tmp_path):
        """Tests that records for manually deleted files are correctly pruned."""
        pm = open_project

        # Add a file
        p = tmp_path / "to_delete.png"
        p.write_text("temp")
        h = pm.add_image(p, copy_to_workspace=True)

        asset = pm.data["assets"][h]
        local_file = pm.project_dir / asset["local_path"]
        assert local_file.exists()

        # 1. Manual deletion (delete BOTH original and local to trigger pruning)
        local_file.unlink()
        p.unlink()
        assert not local_file.exists()
        assert not p.exists()

        # 2. Record still exists before validation
        assert h in pm.data["assets"]

        # 3. RUN VALIDATION
        pm.validate_assets()

        # 4. Record should be gone
        assert h not in pm.data["assets"]

    def test_save_workflow_persistence(self, open_project):
        """Verifies that workflows can be saved and listed."""
        pm = open_project
        payload = {"data": [1, 2, 3]}
        metadata = {"name": "Test Workflow", "timestamp": "2026-04-19"}

        filename = pm.save_workflow("test_module", payload, metadata)
        assert filename.endswith(".json")

        # Try to list it
        workflows = pm.list_workflows()
        assert len(workflows) > 0
        assert workflows[0]["name"] == "Test Workflow"
        assert workflows[0]["module"] == "test_module"

    def test_save_workflow_update_overwrites_existing(self, open_project):
        """Verifies that saving with an existing filename overwrites instead of creating a new file."""
        pm = open_project
        metadata = {"name": "Test Workflow"}
        # First save
        fname1 = pm.save_workflow("mod", {"data": 1}, metadata)

        # Second save with same filename
        fname2 = pm.save_workflow("mod", {"data": 2}, metadata, filename=fname1)

        assert fname1 == fname2
        workflows = pm.list_workflows()
        assert len(workflows) == 1

        # Verify payload updated
        payload = pm.load_workflow_payload(fname1)
        assert payload["data"] == 2

    def test_save_workflow_update_missing_file_creates_new(self, open_project):
        """Verifies passing a non-existent filename acts like a new save."""
        pm = open_project
        fname = pm.save_workflow("mod", {"data": 1}, {"name": "Test"}, filename="missing.json")
        assert fname == "missing.json"
        assert len(pm.list_workflows()) == 1

    def test_attach_file_to_workflow(self, open_project, tmp_path):
        """Verifies attaching a file to a workflow copies it to the attachments folder."""
        pm = open_project
        wf_name = pm.save_workflow("mod", {}, {"name": "Test"})

        # Create dummy bin
        dummy = tmp_path / "data.bin"
        dummy.write_text("binary content")

        att = pm.attach_workflow_file(wf_name, dummy, "raw", "Raw data")
        assert att["key"] == "raw"
        assert att["filename"] == "data.bin"
        assert att["description"] == "Raw data"
        assert "sha256" in att

        # Resave with attachment
        pm.save_workflow("mod", {}, {"name": "Test"}, filename=wf_name, attachments=[att])

        # Verify get_attachment_path
        resolved = pm.get_attachment_path(wf_name, "raw")
        assert resolved is not None
        assert resolved.exists()
        assert resolved.name == "data.bin"
        assert "attachments" in resolved.parent.name

    def test_delete_workflow_also_removes_attachments(self, open_project, tmp_path):
        """Verifies that deleting a workflow cleans up its attachments folder."""
        pm = open_project
        wf_name = pm.save_workflow("mod", {}, {"name": "Test"})

        dummy = tmp_path / "data.bin"
        dummy.write_text("binary content")
        att = pm.attach_workflow_file(wf_name, dummy, "raw")
        pm.save_workflow("mod", {}, {"name": "Test"}, filename=wf_name, attachments=[att])

        att_dir = pm.project_dir / "workflows" / f"{Path(wf_name).stem}_attachments"
        assert att_dir.exists()

        pm.delete_workflow("mod", wf_name)

        assert not (pm.project_dir / "workflows" / wf_name).exists()
        assert not att_dir.exists()

    def test_load_attachments_missing_key_returns_none(self, open_project):
        """Verifies that querying a missing attachment key returns None."""
        pm = open_project
        wf_name = pm.save_workflow("mod", {}, {"name": "Test"})
        assert pm.get_attachment_path(wf_name, "missing") is None

    def test_open_corrupted_json_handles_gracefully(self, empty_project_dir):
        """Verifies that the manager doesn't crash on corrupted project files."""
        # Setup with a fixed name for predictable assertion
        proj_dir = empty_project_dir
        proj_dir.mkdir()
        with open(proj_dir / "project.karcytics", "w", encoding="utf-8") as f:
            f.write('{ "project_name": "Broken", corrupted... }')

        pm = ProjectManager(proj_dir)
        pm.open_project()

        # Verify it didn't crash and returns the name through the property
        assert pm.project_name == proj_dir.name

    def test_add_image_missing_file(self, open_project):
        """Verify FileNotFoundError when adding a non-existent file."""
        with pytest.raises(FileNotFoundError):
            open_project.add_image("non_existent.png", copy_to_workspace=True)

    def test_add_image_already_exists(self, open_project, tmp_path):
        """Verify that adding an identical file returns the same hash and doesn't duplicate."""
        p = tmp_path / "img.png"
        p.write_text("data")
        h1 = open_project.add_image(p, copy_to_workspace=True)
        h2 = open_project.add_image(p, copy_to_workspace=True)
        assert h1 == h2
        # Should log info and return existing

    def test_get_asset_path_resolution(self, open_project, tmp_path):
        """Verify best-path resolution for assets (local vs original)."""
        pm = open_project
        orig = tmp_path / "orig.png"
        orig.write_text("orig")
        h = pm.add_image(orig, copy_to_workspace=True)

        # 1. Local exists
        assert pm.get_asset_path(h).exists()

        # 2. Local missing, fallback to original
        asset = pm.data["assets"][h]
        (pm.project_dir / asset["local_path"]).unlink()
        assert pm.get_asset_path(h) == orig.absolute()

        # 3. Both missing
        orig.unlink()
        assert pm.get_asset_path(h) is None

        # 4. Unknown hash
        assert pm.get_asset_path("unknown") is None

    def test_validate_assets_edge_cases(self, open_project):
        """Verify validate_assets handles empty/missing data."""
        # Missing assets key
        data = {"other": 1}
        assert open_project.assets.validate_assets(data) is False

    def test_ingest_image_diagnostics_fallback(self, open_project, tmp_path):
        """Verify diagnostics reporting on ingestion failure."""
        p = tmp_path / "fail.png"
        p.write_text("data")

        # Mock compute_hash to fail
        with (
            patch.object(
                open_project.assets, "compute_hash", side_effect=RuntimeError("Hash fail")
            ),
            patch("karcytics.core.diagnostics.diagnostics.report_error") as mock_diag,
            pytest.raises(RuntimeError),
        ):
            open_project.add_image(p, copy_to_workspace=True)
            mock_diag.assert_called()

    def test_save_workflow_collision(self, open_project):
        """Verify that multiple workflows with the same name are handled by incrementing filenames."""
        pm = open_project
        pm.save_workflow("mod", {"p": 1}, {"name": "Test"})
        pm.save_workflow("mod", {"p": 2}, {"name": "Test"})
        workflows = pm.list_workflows()
        assert len(workflows) == 2

    def test_list_workflows_missing_dir(self, open_project):
        """Verify listing workflows when the directory hasn't been created yet."""
        # Workflows dir only created on first save
        assert open_project.list_workflows() == []

    def test_load_workflow_payload_missing(self, open_project):
        """Verify loading a non-existent workflow returns an empty payload."""
        assert open_project.load_workflow_payload("missing.json") == {}

    def test_delete_workflow_success(self, open_project):
        """Verify successful deletion of a workflow file."""
        pm = open_project
        fname = pm.save_workflow("mod", {"p": 1}, {"name": "ToDel"})
        assert pm.delete_workflow("mod", fname) is True
        assert len(pm.list_workflows()) == 0

    def test_delete_workflow_fail(self, open_project):
        """Verify that deleting a non-existent workflow returns False."""
        assert open_project.delete_workflow("mod", "non_existent.json") is False

    def test_list_workflows_corrupted_json(self, open_project):
        """Verify that corrupted workflow JSON files are skipped during listing."""
        pm = open_project
        pm.save_workflow("mod", {"p": 1}, {"name": "Good"})

        # Create corrupted one
        wf_dir = pm.project_dir / "workflows"
        wf_dir.mkdir(exist_ok=True)
        (wf_dir / "bad.json").write_text("invalid json {")

        workflows = pm.list_workflows()
        assert len(workflows) == 1
        assert workflows[0]["name"] == "Good"

    def test_create_new_already_exists(self, empty_project_dir):
        """Verify that create_new fails if the directory already exists."""
        empty_project_dir.mkdir()
        pm = ProjectManager(empty_project_dir)
        with pytest.raises(FileExistsError):
            pm.create_new("Duplicate")

    def test_open_project_missing_file(self, tmp_path):
        """Verify that open_project fails if the karcytics file is missing."""
        pm = ProjectManager(tmp_path / "not_a_project")
        with pytest.raises(FileNotFoundError):
            pm.open_project()

    def test_open_project_legacy_history_deleted(self, open_project):
        """Verify that legacy history.json files are automatically deleted upon project open."""
        pm = open_project
        pm.close()  # Release lock from fixture
        pm.history_file.write_text("legacy history data")
        assert pm.history_file.exists()

        # Opening the project should trigger the auto-delete repair
        pm.open_project()
        assert not pm.history_file.exists()

    def test_project_save_fatal_failure(self, open_project):
        """Verify that fatal save failures are reported to the diagnostics engine."""
        pm = open_project
        # Mock os.replace to fail
        with (
            patch("os.replace", side_effect=RuntimeError("Fatal FS error")),
            patch("karcytics.core.diagnostics.diagnostics.report_error") as mock_diag,
            pytest.raises(OSError),
        ):
            pm.save()
            mock_diag.assert_called()

    def test_rename_workflow_updates_name(self, open_project):
        """Verify rename_workflow changes metadata.name without altering the filename."""
        pm = open_project
        filename = pm.save_workflow("mod", {"p": 1}, {"name": "Original Name"})

        result = pm.rename_workflow(filename, "Renamed")

        assert result is True
        # The disk filename is unchanged
        assert (pm.project_dir / "workflows" / filename).exists()
        # But the in-file display name is updated
        from karcytics.core.utils import AtomicJsonFile

        data = AtomicJsonFile.load(pm.project_dir / "workflows" / filename, default={})
        assert data["metadata"]["name"] == "Renamed"

    def test_rename_workflow_missing_returns_false(self, open_project):
        """Verify rename_workflow returns False for a non-existent workflow."""
        assert open_project.rename_workflow("ghost.json", "New Name") is False

    def test_duplicate_workflow_creates_copy(self, open_project):
        """Verify duplicate_workflow creates a new JSON file with '(Copy)' in its name."""
        pm = open_project
        filename = pm.save_workflow("mod", {"value": 42}, {"name": "Source"})

        new_filename = pm.duplicate_workflow(filename)

        assert new_filename is not None
        assert new_filename != filename
        assert (pm.project_dir / "workflows" / new_filename).exists()

        from karcytics.core.utils import AtomicJsonFile

        data = AtomicJsonFile.load(pm.project_dir / "workflows" / new_filename, default={})
        assert data["metadata"]["name"] == "Source (Copy)"
        # Payload must be identical
        assert data["payload"] == {"value": 42}

    def test_duplicate_workflow_missing_returns_none(self, open_project):
        """Verify duplicate_workflow returns None for a non-existent workflow."""
        assert open_project.duplicate_workflow("ghost.json") is None

    def test_duplicate_workflow_collision_avoidance(self, open_project):
        """Verify that duplicating twice produces two distinct filenames."""
        pm = open_project
        filename = pm.save_workflow("mod", {}, {"name": "Base"})

        first = pm.duplicate_workflow(filename)
        second = pm.duplicate_workflow(filename)

        assert first is not None
        assert second is not None
        assert first != second
        # Both files must exist
        assert (pm.project_dir / "workflows" / first).exists()
        assert (pm.project_dir / "workflows" / second).exists()

    def test_duplicate_workflow_copies_attachments(self, open_project, tmp_path):
        """Verify that duplicate_workflow copies the attachments folder and rewrites paths."""
        pm = open_project

        # Create a workflow with an attachment
        filename = pm.save_workflow("mod", {"p": 1}, {"name": "With Att"})
        src_file = tmp_path / "data.txt"
        src_file.write_text("hello")
        pm.attach_workflow_file(filename, src_file, key="raw_data")

        new_filename = pm.duplicate_workflow(filename)

        assert new_filename is not None
        new_stem = new_filename.replace(".json", "")
        att_dir = pm.project_dir / "workflows" / f"{new_stem}_attachments"
        assert att_dir.exists()

        from karcytics.core.utils import AtomicJsonFile

        data = AtomicJsonFile.load(pm.project_dir / "workflows" / new_filename, default={})
        for att in data.get("attachments", []):
            assert new_stem in att["relative_path"]
