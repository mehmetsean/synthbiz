# 7. check accepts only known synthbiz file names in manifest.json

Status: Accepted

## Context

check reads manifest.json from a folder that may come from anywhere. A manifest could name a path outside the folder.

## Decision

check accepts only the known synthbiz file names listed in the manifest. Any other name is reported as an error and the file is not read.

## Consequences

A hostile manifest cannot make check read files outside the dataset. A new file type needs a code change.
