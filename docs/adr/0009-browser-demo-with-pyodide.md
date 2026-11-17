# 9. The demo runs in the browser with Pyodide, script pinned with SRI

Status: Accepted

## Context

Visitors should try the generator without installing it, and no data should leave their machine. A server is out of scope.

## Decision

A static page in site/ loads "the Pyodide script" from one pinned version with a subresource integrity hash and a Content-Security-Policy. It installs the synthbiz wheel from the same site and calls synthbiz.demo, a Python entry point with unit tests that run in CI. A Pages workflow builds the wheel and deploys, and only when the repo is public.

## Consequences

Data stays in the browser. Upgrading Pyodide means a new version and a new hash. The page itself is not tested in a real browser by CI, only its Python entry point and its static rules.

All data stays in your browser. The page downloads Pyodide, micropip and the Python standard library from cdn.jsdelivr.net, and wheel.json and the synthbiz wheel from this site. It does not send your inputs or the generated data anywhere. You can check this in the browser's Network tab.

- Only pyodide.js has SRI. The files it loads next (pyodide.asm.js, the wasm file, the standard library zip, pyodide-lock.json and micropip) do not. A changed file on that CDN path could run code on the page.
- The page holds no secrets and only synthetic data, so the impact is small.
- Self-hosting Pyodide is an option later.
- 'unsafe-eval' is kept because the page has not yet been tested in a browser without it. Removing it is an open item.
- frame-ancestors cannot be set from a meta CSP, and GitHub Pages cannot send headers.
- The Pages build installs hatchling from PyPI without a pin.
- A test asserts the full CSP string, so any change to it shows up in review.
