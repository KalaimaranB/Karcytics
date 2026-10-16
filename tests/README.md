# Karcytics Test Suite

This directory contains comprehensive tests for the Karcytics core library and SDK.

## Test Files

- **test_plugin_sdk.py** - Tests for the Plugin SDK framework (PluginBase, PluginState, WizardPanel, AnalysisBase, etc.)
- **test_history_manager.py** - Tests for the history and undo/redo functionality
- **test_sdk_utils.py** - Tests for common utilities (file dialogs, config management, validation, etc.)
- **test_sanity.py** - General sanity checks for the application
- **test_image_utils.py** - Tests for image processing utilities
- **conftest.py** - Pytest configuration and shared fixtures

## Running Tests

### Run all tests
```bash
pytest
```

### Run specific test file
```bash
pytest tests/test_plugin_sdk.py
```

### Run specific test class
```bash
pytest tests/test_plugin_sdk.py::TestPluginState
```

### Run specific test
```bash
pytest tests/test_plugin_sdk.py::TestPluginState::test_state_to_dict
```

### Run tests with verbose output
```bash
pytest -v
```

### Run only unit tests
```bash
pytest -m unit
```

### Run only integration tests
```bash
pytest -m integration
```

### Run with coverage report
```bash
pip install pytest-cov
pytest --cov=karcytics --cov-report=html
```

### Run tests in parallel (faster)
```bash
pip install pytest-xdist
pytest -n auto
```

## Test Markers

Tests are marked with markers to allow selective execution:

- `@pytest.mark.unit` - Unit tests (fast, isolated)
- `@pytest.mark.integration` - Integration tests (slower, test interactions)
- `@pytest.mark.slow` - Slow running tests
- `@pytest.mark.qt` - Tests requiring PySide6

## Fixtures

Common fixtures available to all tests:

- `qapp` - QApplication instance (auto-available in Qt tests)
- `temp_config_dir` - Temporary directory for config files
- `cleanup_plugin_configs` - Automatically clean up test config files

Example usage:
```python
def test_something(temp_config_dir):
    config_path = temp_config_dir / "test.json"
    # Use config_path in test
```

## Test Coverage

For a detailed breakdown of coverage metrics, testing layers (Unit/Integration/Security), and our TDD philosophy, see:
**[Testing Philosophy & Coverage](file:///Users/kalaimaranbalasothy/GitHub Projects/Karcytics/docs/internal/18_Testing_Philosophy.md)**

Current areas of high focus:
- **plugin_sdk.py** - PluginState, PluginSignals, AnalysisBase, WizardStep, WizardPanel, PluginBase, AnalysisWorker
- **history_manager.py** - ModuleHistory, HistoryManager, undo/redo workflows
- **sdk_utils.py** - File I/O, configuration management, validation functions

## CI/CD Integration

These tests are designed to run in CI/CD pipelines:

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run full test suite
pytest --cov=karcytics

# With xvfb for headless testing on Linux
xvfb-run pytest
```

## Building Excludes Tests

The test files are automatically excluded from:

1. **PyInstaller builds** (Karcytics.spec)
   - Tests are in the `bloat_modules` exclude list
   - Any file with 'test_' in the path is filtered out

2. **Package distribution** (pyproject.toml)
   - Tests are excluded from setuptools package discovery
   - `exclude = ["tests*", "test_*"]` in setuptools config

## Tips

### Debug a failing test
```bash
pytest -v -s tests/test_file.py::TestClass::test_method
```

The `-s` flag shows print statements.

### Run tests matching a pattern
```bash
pytest -k "history" -v
```

### Generate coverage report
```bash
pytest --cov=karcytics --cov-report=term-missing
```

### Watch tests (rerun on file changes)
```bash
pip install pytest-watch
ptw
```

## Writing New Tests

1. Create a test file named `test_*.py` in the `tests/` directory
2. Import what you're testing
3. Write test functions/classes starting with `Test` or `test_`
4. Use descriptive names: `test_<feature>_<scenario>`
5. Add docstrings explaining what's tested

Example:
```python
import pytest
from karcytics.core import PluginBase


class TestNewFeature:
    """Test the new feature."""

    def test_feature_works(self):
        """Test that feature works correctly."""
        result = new_feature()
        assert result is not None

    @pytest.mark.slow
    def test_feature_performance(self):
        """Test feature performance."""
        # ...
```

## Common Issues

### Qt platform issues
If tests fail with "Could not find the Qt platform plugin", try:
```bash
# Explicitly set platform
QT_QPA_PLATFORM=offscreen pytest

# Or on Linux with xvfb
xvfb-run pytest
```

### Import errors
Make sure the project root is in PYTHONPATH:
```bash
export PYTHONPATH=/path/to/Karcytics:$PYTHONPATH
pytest
```

### Config file conflicts
Tests automatically clean up after themselves, but if issues persist:
```bash
rm -rf ~/.karcytics/plugin_configs/*test*.json
```

## Contributing Tests

When adding new SDK features:
1. Write tests first (TDD)
2. Run tests to verify they fail
3. Implement the feature
4. Run tests to verify they pass
5. Add docstring with test example

This ensures the SDK is testable and well-documented!
