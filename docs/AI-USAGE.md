# AI usage

| Tool | Used for | What we changed afterwards and why |
|---|---|---|
| Claude (claude.ai) | Generated most of the backend, the Dockerfiles, compose files, CI/CD workflows, Kubernetes manifests, frontend tests and documentation drafts. | **Maha:** ran and verified everything myself: 73 backend tests, the full Compose stack, a k3d cluster. Caught that `/openapi.json` documented 422 while the API returns 400. When Trivy failed CI, traced it to 3 HIGH CVEs in `starlette 0.46.2` and upgraded to 1.7.0. Ran the HPA load test, the VPA loop and the cache hit-rate test; all numbers in the notes are from my runs. Caught a PR opened against `main` instead of `dev`. Reviewed my partner's frontend PR and requested changes when the React source was missing. |
| ChatGPT | **Asifa:** Generated the Dashboard, Submit (report issue) and Stats pages | **Asifa:** After review on PR #6, added the missing React source and the typed API client, and wired the pages to the backend API |
