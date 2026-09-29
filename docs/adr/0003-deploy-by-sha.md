# ADR 0003 — Deploy by immutable reference (commit SHA)

**Status:** Accepted

## Context
`:latest` is a moving pointer. If production runs `:latest`, "what is production running?"
has no reliable answer, and a rollback cannot name what to roll back to.

## Decision
- CD (`.github/workflows/cd.yml`) pushes `ghcr.io/manahilaftab/civicpulse-backend:<commit sha>`
  and `:latest`, only after tests pass (`needs: test`).
- Everything that deploys uses the SHA: `compose.prod.yaml` requires `IMAGE_TAG`
  (`${IMAGE_TAG:?...}`), and the Kubernetes prod overlay's tag is set to the SHA by CD.
  `:latest` may be pushed; it is never deployed.
- The build job also records the image digest, the next step towards deploying by digest.

## Consequences
- "What is production running?" is one SHA you can paste into `git show`.
- Rollback means re-applying the previous SHA — declarative and auditable (see RUNBOOK).
- Every deploy needs an image built for that commit; the build is reused across
  environments rather than rebuilt (build once, deploy many).
