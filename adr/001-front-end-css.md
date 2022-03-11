# Build frontend CSS using node-sass via NPM

## Status

Proposed: Waiting for review by data-infrastructure team

## Context

_What is the issue that we're seeing that is motivating this decision or change?_

We currently use static CSS files copied from various sources. This raises a couple of issues
- Updating files is manual, labourious and prone to error
- Static files are not scanned by github vulnerability checks (not really issue for CSS but most static CSS have a corresponding JS file)


## Decision

_What is the change that we're proposing and/or doing?_

Use a low footprint NodeJS/NPM based solution to compile CSS.
Eventually build on this for front end JS assets.

*Trying to avoid big footprint front end bundlers like webpack or parceljs*

## Consequences

_What becomes easier or more difficult to do because of this change?_

- Easier to update frontend CSS