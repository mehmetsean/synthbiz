# 8. The CodeQL job skips while the repo is private

Status: Accepted

## Context

CodeQL code scanning needs a public repo or a paid plan. A job that cannot run would fail every build.

## Decision

The CodeQL job has a condition that skips it while the repo is private. It runs once the repo is public.

## Consequences

CI stays green in private. Code scanning starts without a workflow change when the repo goes public.
