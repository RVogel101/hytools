#!/usr/bin/env bash
set -euo pipefail

CONTAINER_NAME="hytools-test-$$"
MONGO_IMAGE="mongo:6.0"
MONGO_PORT=27017

echo "Checking docker availability..."
if ! command -v docker >/dev/null 2>&1; then
  echo "docker not found in PATH. Install Docker or run tests against an existing MongoDB instance." >&2
  exit 2
fi

echo "Pulling MongoDB image ${MONGO_IMAGE}..."
docker pull ${MONGO_IMAGE}

echo "Starting MongoDB container (${CONTAINER_NAME})..."
docker run -d --name "${CONTAINER_NAME}" -p ${MONGO_PORT}:27017 ${MONGO_IMAGE} >/dev/null

# Wait for MongoDB to be ready (best-effort). Many official images log "Waiting for connections".
echo "Waiting for MongoDB to accept connections (up to 30s)..."
READY=0
for i in {1..30}; do
  if docker logs "${CONTAINER_NAME}" 2>&1 | grep -qi "waiting for connections"; then
    READY=1
    break
  fi
  sleep 1
done
if [ "$READY" -ne 1 ]; then
  echo "Warning: MongoDB did not report readiness; continuing anyway (may still work)." >&2
fi

# Export env vars for tests
export HYTOOLS_MONGODB_URI="mongodb://localhost:${MONGO_PORT}/"
export HYTOOLS_MONGODB_DATABASE="hytools_test_$$"

# Run pytest with any args passed to the script
EXIT_CODE=0
pytest -q "$@" || EXIT_CODE=$?

# Tear down container
echo "Stopping and removing MongoDB container ${CONTAINER_NAME}..."
docker rm -f "${CONTAINER_NAME}" >/dev/null 2>&1 || true

exit ${EXIT_CODE}
