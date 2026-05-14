# Deploying manim-skill to the DGX Spark (ARM64, airgapped)

The whole system runs as one `docker compose` stack from a single
universal image. vLLM / Ollama run separately on the Spark host; the
stack reaches them via `host.docker.internal`.

## On the build machine (amd64, has internet)

1. `scripts/build-images.sh linux/arm64`
   — cross-builds `manim-skill:latest` and pulls `redis:7-alpine`,
   both for ARM64, into the local image store.
2. `scripts/bundle-for-deploy.sh`
   — produces `deploy-bundle/` containing `images.tar`,
   `docker-compose.yml`, `.env.example`, `DEPLOY.md`.
3. Copy `deploy-bundle/` to the Spark (USB / scp / etc.).

## On the Spark (ARM64, airgapped)

1. `docker load -i images.tar`
2. `cp .env.example .env` and edit `.env`:
   - `MANIM_SKILL_LLM_BASE_URL` — where vLLM / Ollama listens on the host.
   - `MANIM_SKILL_LLM_MODEL` — the served model name.
   - `MANIM_SKILL_WORK_DIR` — an absolute host path for shared work/output.
3. `mkdir -p "$MANIM_SKILL_WORK_DIR"` (the value you set in `.env`).
4. `docker compose up -d`
5. Web UI: `http://<spark>:8501`. Job API: `http://<spark>:8000`.
   Agents using the CLI set `MANIM_SKILL_BACKEND=http://<spark>:8000`.

## Updating

Rebuild + re-bundle on the build machine, copy over, `docker load -i
images.tar`, then `docker compose up -d` (recreates changed services).

## Notes

- The `api` and `worker` services run as root: `api` writes to the
  shared work volume, `worker` needs the mounted docker socket to spawn
  render containers. The security boundary is each per-beat render
  container — those run non-root, `--network none`, read-only rootfs,
  with memory/cpu/pids caps.
- Concurrency (`MANIM_SKILL_LLM_CONCURRENCY` / `_RENDER_CONCURRENCY`)
  starts conservative; raise it in `.env` + `docker compose up -d` once
  the box's load profile is known.
