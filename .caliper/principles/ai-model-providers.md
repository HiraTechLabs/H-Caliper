# AI Model Provider Principles

Caliper supports three distinct connection methods.

## 1. Provider login
Use only legitimate documented authentication flows supported by the provider, such as an official OAuth/device flow or supported credential helper. Do not scrape login pages or store account passwords as a shortcut. A website subscription/login does not automatically imply API access or API credits. Handle expiry, revocation, scopes, and reauthentication.

## 2. Ollama
Allow a configurable endpoint; validate reachability; discover models where supported; persist the selected model identifier and non-secret options. Remember that `localhost` inside a container refers to that container, not automatically the host. Distinguish endpoint reachable, model available, and inference successful.

## 3. OpenCode
Integrate with the installed CLI or another explicitly documented supported interface. Validate CLI installation/version, authentication state, and provider/model identifier. Use safe subprocess argument arrays, bounded output, timeouts, cancellation, exit-code handling, and secret redaction. Do not assume a model is available because it appears in a static list.

## Shared contract and UI
Use a common internal invocation contract with separate adapters. Represent unsupported capabilities honestly. Each connection method needs setup, validation, status, model selection/discovery where supported, diagnostics, and disconnect/removal semantics. Store secret values only through the secret-store interface. Planning, execution, and review roles must reference configured connections; do not duplicate credentials or invent model IDs.
