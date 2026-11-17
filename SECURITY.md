# Security policy

## Supported versions

| Version | Supported |
| --- | --- |
| 0.1.x | yes |

## Report a problem

Report privately with GitHub private vulnerability reporting. Open the Security tab of this repo and choose "Report a vulnerability". Please do not open a public issue for a security problem.

## In scope

- The `synthbiz check` command reading files from a folder you point it at.
- The manifest: how manifest.json names and hashes are read and verified.
- The demo page in `site/` and the way it loads Pyodide and the synthbiz wheel.

## Out of scope

- The generated data. It is synthetic and has no real secrets.
- Problems in Pyodide or in the CDN itself. Report those to their own projects.

Synthetic data for testing and learning only. Any match with a real business is unintended. Decision support only, not legal, tax, accounting or assurance advice. No guarantee of compliance.
