#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
IMAGE_TAG="${XCRON_CRON_IT_IMAGE:-xcron-cron-it}"
DOCKERFILE="${ROOT}/tests/integration/docker/cron.Dockerfile"

echo "Building ${IMAGE_TAG} from ${DOCKERFILE}"
docker build \
  -f "${DOCKERFILE}" \
  -t "${IMAGE_TAG}" \
  "${ROOT}/tests/integration/docker"

echo "Running isolated cron integration harness in Docker"
docker run --rm \
  --init \
  -v "${ROOT}:/workspace" \
  -w /workspace \
  -e UV_PROJECT_ENVIRONMENT=/tmp/xcron-venv \
  -e UV_CACHE_DIR=/tmp/uv-cache \
  -e XCRON_LOG_FORMAT=json \
  -e XCRON_LOG_LEVEL=INFO \
  "${IMAGE_TAG}" \
  sh -c '/root/.local/bin/uv sync --extra dev --frozen && /root/.local/bin/uv run python tests/integration/cron_real_it.py'
