#!/usr/bin/env bash
# Build the manim-skill image for a target platform and fetch redis.
# Usage: scripts/build-images.sh [linux/arm64|linux/amd64]   (default: linux/arm64)
set -euo pipefail
PLATFORM="${1:-linux/arm64}"
cd "$(dirname "$0")/.."

echo "Building manim-skill:latest for ${PLATFORM} ..."
docker buildx build --platform "${PLATFORM}" \
    -t manim-skill:latest -f docker/Dockerfile --load .

echo "Pulling redis:7-alpine for ${PLATFORM} ..."
docker pull --platform "${PLATFORM}" redis:7-alpine

echo "Done — ${PLATFORM} images are in the local docker image store."
