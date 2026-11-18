# 14. Badges built in the Pages job

Status: Accepted

## Context

The README should show the test count and the coverage. The repo sends no code or data to outside services and needs no sign-up for a reader or the owner.

## Options

- shields.io dynamic badge: simple, but the number must come from somewhere public, and every README view calls a third party.
- Codecov: sends the coverage report to an outside service.
- SVG committed to the repo and updated by a bot commit: needs write access for CI and adds noise commits to main.
- SVG built in the Pages job: no outside service, no extra commits, no write token.

## Decision

The Pages build job runs pytest with a JUnit file and a coverage JSON file in the runner temp folder. `scripts/make_badges.py` reads them and writes `coverage.svg` and `tests.svg` into `_site/badges/`. The script uses only the standard library and builds each SVG by hand. Text width comes from a small per-character width rule. Colors keep at least 4.5 to 1 contrast with the white text, and a test checks the ratios. Output is deterministic.

Coverage is green at 90 percent or more, yellow at 75 or more, red below. The Pages job runs pytest before the script, and pytest fails under 90 percent coverage, so the site only gets green coverage. A failing test stops the job, so the site never shows a red test badge. The yellow and red states are covered by unit tests only.

## Trade-offs

- The badges show the numbers of the last successful Pages build of main, not of a pull request or of a later commit. A failed build keeps the older badges up.
- The Pages build is skipped while the repo is private, so the badge URLs have no files behind them.
- The Pages build now fails when a test fails or coverage is under 90 percent, so the last good badges stay up. The build runs the full tests, so it takes longer. Pull requests run the same build without deploying.
- The widths are estimates, not font measurements. A badge can still look too wide or too narrow in some fonts.
- The build job installs the dev dependencies from PyPI without version pins, as the ci job does. The job holds no secrets and only a read-only token, so a bad release could change the published site files but not the repo. Pinning them is a possible later change.
