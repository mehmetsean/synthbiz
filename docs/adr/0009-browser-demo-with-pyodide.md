# 9. The demo runs in the browser with Pyodide, pinned with SRI

Status: Accepted

## Context

Visitors should try the generator without installing it, and no data should leave their machine. A server is out of scope.

## Decision

A static page in site/ loads Pyodide from one pinned version with a subresource integrity hash and a Content-Security-Policy. It installs the synthbiz wheel from the same site and calls synthbiz.demo, a Python entry point with unit tests that run in CI. A Pages workflow builds the wheel and deploys, and only when the repo is public.

## Consequences

Data stays in the browser. Upgrading Pyodide means a new version and a new hash. The page itself is not tested in a real browser by CI, only its Python entry point and its static rules.
