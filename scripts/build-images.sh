#!/usr/bin/env bash
# Build the manim-skill image for a target platform and fetch redis.
# Usage: scripts/build-images.sh [linux/amd64|linux/arm64]   (default: linux/amd64)
#
# amd64 is the native dev/deploy platform — on an amd64 host this is just a
# native build (buildx --load avoids needing a registry). Pass linux/arm64
# only when cross-building for the ARM64 Spark.
set -euo pipefail
PLATFORM="${1:-linux/amd64}"
cd "$(dirname "$0")/.."

echo "Building manim-skill:latest for ${PLATFORM} ..."
docker buildx build --platform "${PLATFORM}" \
    -t manim-skill:latest -f docker/Dockerfile --load .

echo "Pulling redis:7-alpine for ${PLATFORM} ..."
docker pull --platform "${PLATFORM}" redis:7-alpine

echo "Done — ${PLATFORM} images are in the local docker image store."
