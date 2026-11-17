# 10. All rights reserved from 0.1.1

Status: Accepted

## Context

Release 0.1.0 went out under Apache-2.0 for the code and CC BY 4.0 for the docs and sample data. The owner now wants all rights reserved.

## Decision

From 0.1.1 the code, docs, sample data and demo page are all rights reserved. See LICENSE. Release 0.1.0 stays under Apache-2.0 and CC BY 4.0, as it was released. Outside code contributions are not accepted, and the DCO rule is dropped. Bug reports by issue are welcome.

## Consequences

CONTRIBUTING.md is removed. The generated README.txt carries a copyright notice. Third-party parts keep their own licenses, listed in THIRD_PARTY_NOTICES.md. A test checks that the old license names do not return.
