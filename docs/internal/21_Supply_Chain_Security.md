# Architectural Cryptographic Specification

This document details the mathematical validation rules, serialization constraints, and file system isolation bounds enforced by the Karcytics Trust subsystem.

---

## Hashing and Verification Specification

Karcytics utilizes asymmetric cryptography (Ed25519) and SHA-256 hashing to verify code integrity.

### Validation Sequence

1. **Manifest Binding**:
   The verifier extracts `manifest_hash` from the parsed `security.json` ledger. It must exactly match the SHA-256 hash of the raw `manifest.json` file.
2. **Canonical Serialization**:
   The `security.json` structure is serialized into deterministic bytes using strict JSON canonicalization.
3. **Signature Verification**:
   The verifier executes the Ed25519 verification algorithm using the developer's public key, the canonical bytes of `security.json`, and the signature payload (`signature.bin`).

---

## Deterministic JSON Serialization

To ensure consistent verification across different environments, Karcytics mandates strict canonical JSON formatting prior to signature evaluation.

### Canonicalization Parameters
* **Key Sorting**: Dictionary keys must be sorted alphabetically at all nesting levels (`sort_keys=True`).
* **Whitespace Removal**: Separators must not contain trailing or leading spaces (`separators=(',', ':')`).
* **Encoding**: Output is strictly UTF-8 encoded.

```python
import json


def get_canonical_bytes(data: dict) -> bytes:
    return json.dumps(data, sort_keys=True, separators=(",", ":")).encode("utf-8")
```
Failure to adhere to these exact serialization rules will alter the byte payload and cause signature verification to fail.

---

## Cache Directory Isolation Bounds

To mitigate directory traversal vulnerabilities during remote asset fetches (e.g., developer avatars), Karcytics enforces a strictly sandboxed directory structure.

### Traversal Prevention
The target path for an asset is computed by resolving the plugin ID, asset type, and filename against the base cache directory (`~/.karcytics/cache/`).
The system enforces a **Descendant Boundary Constraint**: the resolved absolute path must begin with the absolute path of the base cache directory.
Inputs containing relative traversal indicators (e.g., `../`) are rejected during resolution.

---

## Exclusion Zone Auditing

The `TrustManager` prohibits executable files from residing within directories typically ignored by version control or standard validation (e.g., `/logs`, `/cache`).

During the integrity verification phase, the system recursively scans ignored directories for blacklisted extensions (e.g., `.py`, `.sh`, `.exe`). If discovered, the plugin load sequence is immediately aborted to prevent the execution of hidden code.
