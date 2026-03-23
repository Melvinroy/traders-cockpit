# QC Determinism Hardening

> Status: Validated
> Branch: `codex/bugfix-qc-stable-symbol`
> Opened: 2026-03-23
> Closed: -
> Closing Commit: -

## Problem

The staged QC flow was brittle in four ways:

- `browser-smoke.mjs` and `fidelity-baselines.mjs` depended on the default ticker input state instead of a known-good symbol
- browser scripts raced the async auth gate and could land on the login screen after already assuming the cockpit was ready
- `run-qc.ps1` could recreate the stale `.next` dev-cache failure during the final dev restart
- after a successful entry, the cockpit could fail to eagerly apply the returned position state, leaving follow-on browser steps out of sync with the backend

## Business value

Production promotion depends on a repeatable QC path. The scripted browser checks need to be deterministic so integration and promotion evidence can be regenerated without manual intervention, and the cockpit needs to reflect backend entry state immediately enough for those browser flows to be trustworthy.

## Scope

- make browser smoke use a stable default symbol
- make fidelity baseline capture use the same stable symbol
- keep the symbol overridable via environment for future environments
- seed browser auth from the backend instead of relying on UI-login timing
- reset `.next` before the final QC dev restart
- stabilize trade-flow QC against the current cockpit entry/stop/profit path
- eagerly sync returned entry positions into the cockpit state

## Acceptance criteria

- [x] `run-qc.ps1` can load setup without relying on the default textbox value
- [x] browser smoke artifacts are created successfully
- [x] baseline capture uses the configured stable symbol by default
- [x] staged QC can authenticate without depending on the login panel timing
- [x] staged QC completes on a fresh stack without reviving the stale `.next` module failure
- [x] trade-flow QC captures the required baseline artifacts on the deterministic paper path

## Risks / constraints

- do not change actual trading behavior
- keep the QC symbol configurable rather than hard-coding environment-specific behavior into production paths
- keep browser QC strict enough to catch regressions, while allowing deterministic paper-mode end states that differ from the earlier handwritten assumptions
