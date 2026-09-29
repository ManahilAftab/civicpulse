#!/usr/bin/env python3
"""Pre-submission lint for CivicPulse (assignment §5.3 / §5.7).

A lint, not a grader: it catches the mechanical failures behind most automatic
deductions. Run from the repository root:  python scripts/check_submission.py
Exit code is non-zero if any FAIL is reported.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
fails: list[str] = []
warns: list[str] = []


def ok(msg: str) -> None:
    print(f"  PASS  {msg}")


def fail(msg: str) -> None:
    fails.append(msg)
    print(f"  FAIL  {msg}")


def warn(msg: str) -> None:
    warns.append(msg)
    print(f"  WARN  {msg}")


def read(rel: str) -> str:
    p = ROOT / rel
    return p.read_text(encoding="utf-8", errors="ignore") if p.exists() else ""


def git(*args: str) -> str:
    try:
        return subprocess.run(["git", *args], cwd=ROOT, capture_output=True,
                              text=True, check=False).stdout
    except FileNotFoundError:
        return ""


REQUIRED = [
    "backend/app/routes", "backend/app/services", "backend/app/repositories",
    "backend/app/providers",
    *[f"backend/app/providers/triage/{n}.py"
      for n in ("base", "llm", "ollama", "rules", "simulated", "factory")],
    "backend/alembic/versions", "backend/tests", "backend/Dockerfile",
    "backend/.dockerignore", "backend/pyproject.toml",
    "frontend/src/api", "frontend/tests", "frontend/Dockerfile",
    "frontend/.dockerignore", "frontend/nginx.conf", "frontend/package.json",
    *[f"k8s/base/{n}.yaml" for n in (
        "namespace", "backend", "frontend", "postgres", "redis", "ingress",
        "configmap", "secret", "hpa", "vpa", "pdb", "kustomization")],
    "k8s/overlays/dev/kustomization.yaml", "k8s/overlays/prod/kustomization.yaml",
    "load/k6-script.js",
    *[f"docs/{n}.md" for n in ("ENGINEERING-NOTES", "RUNBOOK", "AI-USAGE", "TRIAGE")],
    "docs/evidence",
    *[f".github/workflows/{n}.yml" for n in ("ci", "cd", "release")],
    "compose.yaml", "compose.prod.yaml", ".env.example", ".gitignore",
    "README.md", "LICENSE",
]


def check_layout() -> None:
    print("\n[1] Repository layout (§5.7)")
    missing = [r for r in REQUIRED if not (ROOT / r).exists()]
    for m in missing:
        fail(f"missing {m}")
    adrs = sorted((ROOT / "docs/adr").glob("000*.md")) if (ROOT / "docs/adr").exists() else []
    if len(adrs) < 4:
        fail(f"expected 4 ADRs in docs/adr, found {len(adrs)}")
    if not missing and len(adrs) >= 4:
        ok("all required paths present")


SECRET_PATTERNS = [
    (r"gsk_[A-Za-z0-9]{20,}", "Groq API key"),
    (r"AIza[0-9A-Za-z_\-]{30,}", "Google API key"),
    (r"sk-[A-Za-z0-9]{32,}", "OpenAI-style key"),
    (r"ghp_[A-Za-z0-9]{30,}", "GitHub token"),
]


def check_secrets() -> None:
    print("\n[2] Secrets in Git history (−20 / −15)")
    tracked_env = [p for p in git("log", "--all", "--name-only", "--format=").split()
                   if re.search(r"(^|/)\.env$", p)]
    if tracked_env:
        fail(f".env committed in history: {sorted(set(tracked_env))}")
    else:
        ok("no .env file anywhere in history")
    history = git("log", "--all", "-p")
    found = False
    for pat, name in SECRET_PATTERNS:
        if re.search(pat, history):
            fail(f"{name} pattern found in Git history")
            found = True
    if not found:
        ok("no API key / token patterns in history")
    ignore = read(".gitignore")
    if not re.search(r"^\.env$", ignore, re.M):
        fail(".env is not in .gitignore")


def check_images() -> None:
    print("\n[3] Pinned images (−8)")
    bad = []
    files = [*ROOT.glob("**/Dockerfile"), ROOT / "compose.yaml", ROOT / "compose.prod.yaml",
             *ROOT.glob("k8s/**/*.yaml")]
    for f in files:
        if not f.exists() or "node_modules" in f.parts:
            continue
        for n, line in enumerate(f.read_text(errors="ignore").splitlines(), 1):
            m = re.match(r"\s*(?:FROM|image:)\s+([^\s#]+)", line, re.I)
            if not m:
                continue
            ref = m.group(1)
            if ref.startswith("$") or ref.startswith("civicpulse-"):
                continue  # built locally / set by overlay or ${IMAGE_TAG}
            if "@sha256:" in ref:
                continue
            name_tag = ref.split("/")[-1]
            if ":" not in name_tag or name_tag.endswith(":latest"):
                bad.append(f"{f.relative_to(ROOT)}:{n} {ref}")
    for b in bad:
        fail(f"unpinned image {b}")
    if not bad:
        ok("every base / service image carries a tag or digest")


def check_localhost() -> None:
    print("\n[4] localhost for service-to-service (−8)")
    hits = []
    for rel in ("compose.yaml", "compose.prod.yaml", "frontend/nginx.conf",
                ".env.example", *[str(p.relative_to(ROOT)) for p in ROOT.glob("k8s/**/*.yaml")]):
        for n, line in enumerate(read(rel).splitlines(), 1):
            if line.strip().startswith("#"):
                continue
            if re.search(r"(DATABASE_URL|REDIS_URL|proxy_pass|_HOST)\S*.*(localhost|127\.0\.0\.1)", line):
                hits.append(f"{rel}:{n}")
    for h in hits:
        fail(f"localhost used for a service address at {h}")
    if not hits:
        ok("no localhost service addresses in config")


def check_compose() -> None:
    print("\n[5] Compose networks, prod file (−8)")
    dev = read("compose.yaml")
    prod = read("compose.prod.yaml")
    if "internal: true" not in dev:
        fail("compose.yaml has no network with internal: true")
    else:
        ok("internal: true network present")
    if re.search(r"^\s*build:", prod, re.M):
        fail("compose.prod.yaml contains a build: key")
    else:
        ok("compose.prod.yaml has no build:")
    if "IMAGE_TAG" not in prod:
        fail("compose.prod.yaml does not use ${IMAGE_TAG}")
    for svc in ("database", "db", "postgres", "cache", "redis"):
        m = re.search(rf"^  {svc}:\n((?:    .*\n|\n)+)", prod, re.M)
        if m and re.search(r"^\s{4}ports:", m.group(1), re.M):
            fail(f"compose.prod.yaml publishes a port on '{svc}'")


def check_k8s() -> None:
    print("\n[6] Kubernetes (−8)")
    pg = read("k8s/base/postgres.yaml")
    if "kind: StatefulSet" in pg and "volumeClaimTemplates" in pg:
        ok("postgres is a StatefulSet with volumeClaimTemplates")
    else:
        fail("postgres is not a StatefulSet with volumeClaimTemplates")
    for p in ROOT.glob("k8s/**/*.yaml"):
        t = p.read_text(errors="ignore")
        for doc in t.split("\n---"):
            if "kind: Service" in doc and re.search(r"type:\s*(NodePort|LoadBalancer)", doc) \
                    and re.search(r"name:\s*(postgres|database|redis|cache)", doc):
                fail(f"{p.relative_to(ROOT)}: database/cache Service is NodePort/LoadBalancer")
    secret = read("k8s/base/secret.yaml")
    if re.search(r"gsk_|AIza", secret):
        fail("k8s/base/secret.yaml looks like it holds a real key")
    else:
        ok("secret.yaml holds placeholders only")
    for rel in ("k8s/overlays/prod/kustomization.yaml",):
        if re.search(r"newTag:\s*latest", read(rel)):
            fail(f"{rel} deploys :latest")


def check_workflows() -> None:
    print("\n[7] CI/CD workflows (−8)")
    cd = read(".github/workflows/cd.yml")
    jobs_section = cd.split("\njobs:", 1)[1] if "\njobs:" in cd else ""
    jobs = re.findall(r"^  ([\w-]+):\n((?:    .*\n|\n)+)", jobs_section + "\n", re.M)
    names = [j for j, _ in jobs]
    for j, body in jobs:
        if re.search(r"(push|deploy)", j) and "needs:" not in body:
            fail(f"cd.yml job '{j}' publishes/deploys without needs:")
    if names:
        ok(f"cd.yml jobs: {', '.join(names)}")
    for wf in ("ci", "cd", "release"):
        text = read(f".github/workflows/{wf}.yml")
        if text and "permissions:" not in text:
            fail(f"{wf}.yml has no permissions: block")
        for n, line in enumerate(text.splitlines(), 1):
            m = re.search(r"uses:\s*([^\s#]+)", line)
            if m and "@" not in m.group(1) and not m.group(1).startswith("./"):
                fail(f"{wf}.yml:{n} action not pinned: {m.group(1)}")
    if re.search(r"(kubectl|kustomize).*:latest", cd):
        fail("cd.yml appears to deploy :latest")


def check_git() -> None:
    print("\n[8] Git history (−5, rubric A)")
    direct = [l for l in git("log", "origin/main", "--first-parent", "--no-merges",
                             "--format=%h %s").splitlines()
              if l and "initial commit" not in l.lower()]
    if direct:
        warn(f"{len(direct)} non-merge commit(s) directly on main: {direct[:3]}")
    else:
        ok("no direct commits on main (besides the initial commit)")
    counts = []
    for line in git("shortlog", "-sn", "--all", "--no-merges").splitlines():
        parts = line.strip().split("\t")
        if len(parts) == 2:
            counts.append((int(parts[0]), parts[1]))
    total = sum(c for c, _ in counts)
    if total:
        print(f"        commits (no merges): {total}")
        for c, name in counts:
            pct = 100 * c / total
            line = f"{name}: {c} ({pct:.0f}%)"
            (warn if pct < 35 else ok)(line + (" — below 35%" if pct < 35 else ""))
        if total < 35:
            warn(f"only {total} commits, rubric asks for ≥ 35")


def check_docs() -> None:
    print("\n[9] Docs placeholders")
    for rel in ("README.md", "docs/ENGINEERING-NOTES.md", "docs/AI-USAGE.md",
                "docs/RUNBOOK.md", *[str(p.relative_to(ROOT)) for p in ROOT.glob("docs/adr/*.md")]):
        text = read(rel)
        for n, line in enumerate(text.splitlines(), 1):
            if re.search(r"\bTODO\b|\[TIME\]|fill in|_TBD_|FIXME", line, re.I):
                warn(f"{rel}:{n} placeholder: {line.strip()[:70]}")
    notes = read("docs/ENGINEERING-NOTES.md")
    missing_q = [str(i) for i in range(1, 9) if not re.search(rf"^##\s*{i}\.", notes, re.M)]
    if missing_q:
        warn(f"ENGINEERING-NOTES.md missing question headings: {', '.join(missing_q)}")
    else:
        ok("ENGINEERING-NOTES.md has all eight questions")


def main() -> int:
    print(f"CivicPulse submission check — {ROOT}")
    for check in (check_layout, check_secrets, check_images, check_localhost,
                  check_compose, check_k8s, check_workflows, check_git, check_docs):
        check()
    print(f"\nSummary: {len(fails)} FAIL, {len(warns)} WARN")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
