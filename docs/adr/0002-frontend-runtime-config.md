# ADR 0002 — Frontend runtime configuration

**Status:** Accepted

## Context
Vite bakes `import.meta.env` values into the JavaScript at build time. If the backend URL
is baked in, the frontend image only works in the environment it was built for, which
breaks build-once-deploy-many.

## Decision
The frontend never knows an absolute backend URL. It calls relative paths (`/api/...`).
nginx in the frontend image (`frontend/nginx.conf`) proxies `/api/` to the `backend`
service by name. In Kubernetes the Ingress routes `/api` to the backend service directly
(`k8s/base/ingress.yaml`), so the same relative paths work there too.

## Consequences
- One image runs in Compose, k3d and CI without rebuilding.
- Same origin for page and API, so no CORS configuration is needed.
- Anything in the browser bundle is public, so it contains no secrets or keys.
- Rejected alternative: generating `/config.js` at container start. It also works, but adds
  an entrypoint script and a second source of truth for configuration.
