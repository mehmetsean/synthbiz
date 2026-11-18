# 14. Badges built in the Pages job

Status: Accepted

## Context

The README should show the test count and the coverage. The repo sends no code or data to outside services and needs no sign-up for a reader or the owner.

## Options

- shields.io dynamic badge: simple, but the number must come from somewhere public, and every README view calls a third party.
- Codecov: needs an account and a token, and uploads the coverage report to an outside service.
- SVG committed to the repo and updated by a bot commit: needs write access for CI and adds noise commits to main.
- SVG built in the Pages job: no outside service, no extra commits, no write token.

## Decision

The Pages build job runs pytest with a JUnit file and a coverage JSON file in the runner temp folder. `scripts/make_badges.py` reads them and writes `coverage.svg` and `tests.svg` into `_site/badges/`. The script uses only the standard library and builds each SVG by hand. Text width comes from a small per-character table. Colors keep at least 4.5 to 1 contrast with the white text, and a test checks the ratios. Output is deterministic.

Coverage is green at 90 percent or more, yellow at 75 or more, red below. The test badge is red when any test failed.

## Trade-offs

- The badges show the numbers of the last Pages build of main, not of a pull request or of a later commit.
- Pages deploys only while the repo is public, so the images are empty while it is private.
- The Pages job now runs the full tests, so it takes longer. The job reads only files that it wrote itself.
- The width table is an estimate, not a font measurement. It errs wide, so text does not overflow.
