# Deploying manim-skill (amd64 Linux)

The whole system runs as one `docker compose` stack from a single universal
image. vLLM / Ollama run separately on the host; the stack reaches them via
`host.docker.internal`.

The deploy target is an **amd64 Linux** box. Two images are needed:
`manim-skill:latest` (built from this repo) and `redis:7-alpine`. The base
image `manimcommunity/manim:v0.20.1` is only the build's `FROM` layer —
having it pre-pulled just saves that ~1.4 GB download; you still build
`manim-skill:latest` on top of it.

## Path A — target box has internet (build in place)

Run on the target box itself:

1. `scripts/build-images.sh linux/amd64`
   — native build of `manim-skill:latest` (no cross-compile) and pulls
   `redis:7-alpine`. The build needs network: IBM Plex fonts from jsdelivr,
   Noto CJK via apt, and pip install of the package.
   (Equivalent bare command: `docker build -t manim-skill:latest -f docker/Dockerfile .`
   then `docker pull redis:7-alpine`.)
2. `cp .env.example .env` and edit `.env`:
   - `MANIM_SKILL_LLM_BASE_URL` — where vLLM / Ollama listens on the host.
   - `MANIM_SKILL_LLM_MODEL` — the served model name.
   - `MANIM_SKILL_WORK_DIR` — an absolute host path for shared work/output.
3. `mkdir -p "$MANIM_SKILL_WORK_DIR"` (the value you set in `.env`).
4. `docker compose up -d`
5. Web UI: `http://<host>:8501`. Job API: `http://<host>:8000`.
   Agents using the CLI set `MANIM_SKILL_BACKEND=http://<host>:8000`.

## Path B — target box is airgapped (build elsewhere, ship the tar)

On a **build machine with internet (also amd64)**:

1. `scripts/build-images.sh linux/amd64`
   — builds `manim-skill:latest` and pulls `redis:7-alpine` into the local
   image store. (amd64 host → no buildx cross-compile needed.)
2. `scripts/bundle-for-deploy.sh`
   — produces `deploy-bundle/` containing `images.tar`,
   `docker-compose.yml`, `.env.example`, `DEPLOY.md`.
3. Copy `deploy-bundle/` to the target (USB / scp / etc.).

On the **airgapped target**:

1. `docker load -i images.tar`
2. Steps 2–5 from Path A (`.env`, `mkdir`, `docker compose up -d`).

## ARM64 (DGX Spark)

Same as Path B but cross-build for ARM64 on the amd64 build box:
`scripts/build-images.sh linux/arm64`. The Spark host is airgapped, so the
`docker save` / `docker load` flow is the only option there. (Dev/test
happens on amd64; ARM64 is built-and-saved, not run, on the dev box.)

## Updating

Rebuild the image, then re-deploy: in place, re-run `build-images.sh` +
`docker compose up -d`; airgapped, re-bundle, copy over, `docker load -i
images.tar`, then `docker compose up -d` (recreates changed services).

## Notes

- The `api` and `worker` services run as root: `api` writes to the shared
  work volume, `worker` needs the mounted docker socket to spawn render
  containers. The security boundary is each per-beat render container —
  those run non-root, `--network none`, read-only rootfs, with
  memory/cpu/pids caps.
- `MANIM_SKILL_WORK_DIR` is bind-mounted at the SAME path inside the
  containers — the worker spawns render containers that bind-mount sub-paths
  of it, resolved by the host docker daemon. On native Linux this is a real
  host path (simpler than the Docker-Desktop dev box, where it must be a
  path the Docker VM can see).
- Concurrency (`MANIM_SKILL_LLM_CONCURRENCY` / `_RENDER_CONCURRENCY`) starts
  conservative; raise it in `.env` + `docker compose up -d` once the box's
  load profile is known.
