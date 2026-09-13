# Testing Philosophy and Coverage

Karcytics enforces rigorous testing protocols to ensure data integrity and security validation across its core subsystems and the SDK.

---

## Current Core Coverage

Testing prioritizes critical pathways such as communication buses, cryptographic security architectures, and state management.

| Component | Target Coverage | Status |
| :--- | :---: | :--- |
| **Event Bus** | >90% | Satisfied |
| **Diagnostics Engine** | >90% | Satisfied |
| **Trust Architecture** | >85% | Satisfied |
| **History Manager** | >85% | Satisfied |
| **Project & Asset Manager** | >75% | Satisfied |

> [!NOTE]
> Modules exclusively handling UI rendering (e.g., `preferences.py`) may exhibit lower unit test coverage as they are primarily validated via integration testing workflows.

---

## Testing Infrastructure

### 1. Headless UI Testing
We utilize `pytest-qt` configured with an offscreen buffer to execute UI logic tests within CI pipelines without requiring a physical display server.
```bash
QT_QPA_PLATFORM=offscreen uv run python -m pytest tests/core/
```

### 2. Cryptographic Verification
Tests within the trust modules verify the rejection of tampered plugins, corrupted manifests, and invalid cryptographic signatures using mocked authority keys.

### 3. State Management Testing
The `HistoryManager` undergoes stress testing to confirm that complex analysis states are correctly serialized and deserialized without memory leaks or data loss.

---

## Execution

Local execution of the test suite is required prior to submitting code contributions.

### Standard Test Execution
```bash
uv run pytest
```

### Coverage Reporting
```bash
uv run pytest --cov=karcytics --cov-report=term-missing
```

---

## Best Practices
1. **Mocking**: Utilize `unittest.mock` for network I/O and external file system dependencies.
2. **Isolation**: Use `pytest` temporary directory fixtures to isolate test artifacts.
3. **Asynchronous Verification**: Leverage `qtbot.waitSignal` when testing event-driven UI components to prevent race conditions.
