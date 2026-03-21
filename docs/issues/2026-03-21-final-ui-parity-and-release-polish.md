# Issue: Final UI Parity And Release Polish

## Goal

Close the last remaining gap between the current cockpit UI and the original `UI.html` contract after the staged promotion to `main`.

## Scope

- tighten remaining center-column spacing and line-height mismatches
- refine right-panel log density and row treatment
- align remaining open-position card details to the HTML contract
- review active-state labels, empty states, and status chips against the prototype
- keep browser baselines current while making the visual pass

## Acceptance

- the current Next.js UI is visually and behaviorally as close as practical to `UI.html`
- all five browser baseline screenshots remain green after the parity pass
- no runtime, lint, type, or backend regressions are introduced
