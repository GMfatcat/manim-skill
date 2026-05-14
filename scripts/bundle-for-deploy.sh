#!/usr/bin/env bash
# Bundle the images + compose file into a directory for airgapped deploy.
# Run AFTER scripts/build-images.sh has built the target-platform images.
# Usage: scripts/bundle-for-deploy.sh [output-dir]   (default: deploy-bundle)
set -euo pipefail
cd "$(dirname "$0")/.."
OUT_DIR="${1:-deploy-bundle}"
mkdir -p "${OUT_DIR}"

echo "Saving docker images to ${OUT_DIR}/images.tar ..."
docker save manim-skill:latest redis:7-alpine -o "${OUT_DIR}/images.tar"

echo "Copying compose file, env template, and deploy guide ..."
cp docker-compose.yml "${OUT_DIR}/"
cp .env.example "${OUT_DIR}/"
cp DEPLOY.md "${OUT_DIR}/"

echo "Deploy bundle ready in ${OUT_DIR}/"
echo "  images.tar  docker-compose.yml  .env.example  DEPLOY.md"
