# 7. check accepts only known synthbiz file names in manifest.json

Status: Accepted

## Context

check reads manifest.json from a folder that may come from anywhere. A manifest could name a path outside the folder.

## Decision

check accepts only the known synthbiz file names listed in the manifest. Any other name is reported as an error and the file is not read.

## Consequences

A manifest that names a file outside the known list is reported as an error, and that file is not read. A test checks this. A new file type needs a code change.
