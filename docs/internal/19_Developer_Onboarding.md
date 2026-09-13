# Developer Onboarding and Contribution

This guide explains the practical path for contributing to Karcytics: project setup, plugin authoring, signing, testing, and release safety.

---

## Contributor roles

Karcytics separates contributor roles to make security and responsibility clear.

1. **Contributor / Tester** — helps with QA, docs, or validation without writing executable plugin code.
2. **Developer / Publisher** — authors modules or core changes and signs release artifacts.
3. **Institutional Authority** — manages a trusted root and can issue delegated trust to internal developers.

---

## Tier 1: Contributor

Contributors who do not author executable code can still be credited in the plugin manifest.

### Manifest example

```json
{
  "authors": [
    {
      "name": "Jane Doe",
      "role": "QA Analyst",
      "permissions": ["run_tests"]
    }
  ]
}
```

Contributors are listed in the `authors` array, but they are not required to sign code unless their permission set explicitly includes `sign_code`.

---

## Tier 2: Developer

Developers must have a valid signing identity before their plugins can be distributed through a trusted workflow.

### 1. Create a developer identity

Generate an Ed25519 keypair using the SDK:

```bash
karcytics-sdk init-identity
```

This creates the local private/public keypair required for future signing steps.

### 2. Register your public key

To be recognized globally, submit the public key to the repository maintainers or registry admins. The `karcytics-sdk registry` command can produce the JSON snippet you need to submit.

### 3. Sign a plugin

Before distributing a plugin, sign the package:

```bash
karcytics-sdk sign <plugin_dir>
```

This generates signed metadata and signature files used by the runtime to confirm that the package was not modified after signing.

### 4. Test locally before release

Before publishing, run the plugin against a local Karcytics build and confirm that:

* the plugin loads without errors,
* trust checks pass,
* outputs match expected results,
* the plugin works with the target Karcytics version.

---

## Tier 3: Institutional authority

Institutions can establish a root of trust and delegate authority to internal developers.

### 1. Register the authority

Generate an authority keypair the same as a developer key and submit the public key to the Karcytics maintainers so it can be added to the official authority registry.

### 2. Issue a delegation certificate

Use the institutional private key to sign a developer’s public key:

```bash
karcytics-sdk delegate <path_to_researcher_public.pub> "Researcher Name" --authority <path_to_your_authority_private.pem>
```

The resulting delegation file is included in the developer’s workspace and is used as part of the trust chain when validating plugin signatures.

### 3. Project-level co-signing

For CI-driven release workflows, the project can also be co-signed using a project identity. This is useful when institutional validation is required beside developer signing.

```bash
karcytics-sdk project-sign <plugin_dir>
```

This typically reads the project private key from an environment variable such as `KARCYTICS_PROJECT_PRIVATE_KEY`.

---

## Recommended contributor workflow

For most contributors, the practical path is:

1. clone the repository,
2. set up a proper Python environment,
3. use the plugin template or minimal example as a starting point,
4. validate behavior locally,
5. sign the package before distribution,
6. run release checks or CI verification,
7. publish only after trust checks pass.

---

## Related documentation

* [Security and Signing Guide](20_Security_and_Signing.md) — signature model and runtime verification
* [Plugin Store & Security](../user/07_Plugin_Store_and_Security.md) — how users review and approve trusted plugins
* [Core Architecture Overview](11_Core_Nervous_System.md) — event-driven design and runtime boundaries
